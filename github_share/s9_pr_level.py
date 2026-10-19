#!/usr/bin/env python3
# PR-level disclosure: merged PRs and their commits, with the package detector and the trailer check.

from __future__ import annotations

import argparse
import json
import os
import random
import re
from pathlib import Path

import pandas as pd

from pipeline123.MSR_AI_Gov.github_share.common import DET_ASSISTED_BY
from pipeline123.MSR_AI_Gov.github_share.s4_mine_conformance import (
    load_package_classifier,
)
from pipeline123.MSR_AI_Gov.github_share.s7_fetch_review_data import GH


def bot_patterns(pkg: Path) -> list[re.Pattern]:
    f = pkg / "data/classification_rules/bot_list/agent_impact_bots.csv"
    if not f.exists():
        return []
    pats = []
    for p in pd.read_csv(f).pattern.dropna():
        try:
            pats.append(re.compile(str(p), re.I))
        except re.error:
            pats.append(re.compile(re.escape(str(p)), re.I))
    return pats


def is_bot(login: str, utype: str, pats: list[re.Pattern]) -> bool:
    login = login or ""
    return (
        utype == "Bot"
        or login.lower().endswith("[bot]")
        or any(p.search(login) for p in pats)
    )


def ts(s: str) -> pd.Timestamp:
    return (
        pd.Timestamp(s, tz="UTC") if pd.Timestamp(s).tzinfo is None else pd.Timestamp(s)
    )


def list_prs(
    gh: GH,
    repo: str,
    since: pd.Timestamp,
    cache: Path,
    refresh: bool,
    max_pages: int | None,
) -> list[dict]:
    f = cache / "pr_list.jsonl"
    if f.exists() and not refresh:
        rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
        print(
            f"[1/3] PR list: {len(rows)} PRs from cache ({f}); --refresh-list to re-fetch"
        )
        return rows
    print("[1/3] listing PRs (newest first) ...")
    seen: dict[int, dict] = {}
    url = f"/repos/{repo}/pulls?state=all&sort=created&direction=desc&per_page=100"
    pages = 0
    while url:
        data, url = gh.get(url)
        pages += 1
        if not data:
            break
        oldest = None
        for p in data:
            u = p.get("user") or {}
            seen[p["number"]] = {
                "number": p["number"],
                "title": p.get("title") or "",
                "body": p.get("body") or "",
                "login": u.get("login") or "",
                "user_type": u.get("type") or "",
                "created_at": p["created_at"],
                "merged_at": p.get("merged_at"),
                "closed_at": p.get("closed_at"),
                "draft": bool(p.get("draft")),
                "base": (p.get("base") or {}).get("ref"),
            }
            oldest = p["created_at"]
        if pages % 20 == 0:
            print(f"  {pages} pages, {len(seen)} PRs, oldest so far {oldest}")
        if oldest and ts(oldest) < since:
            break
        if max_pages and pages >= max_pages:
            print(f"  stopped after --max-pages {max_pages} (test mode)")
            break
    rows = sorted(seen.values(), key=lambda r: r["number"])
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"  {len(rows)} PRs listed in {pages} pages")
    return rows


def pr_commits(gh: GH, repo: str, number: int, cache: Path) -> list[dict]:
    f = cache / "commits" / f"{number}.json"
    if f.exists():
        return json.loads(f.read_text())
    data = gh.all(f"/repos/{repo}/pulls/{number}/commits") or []
    out = [
        {"sha": c.get("sha"), "message": (c.get("commit") or {}).get("message") or ""}
        for c in data
    ]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--until", default="2026-09-30 23:59:59")
    ap.add_argument("--policy-date", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--cache", default=None, help="default: <out>/pr_raw")
    ap.add_argument(
        "--base",
        default="main",
        help="pass 2 only fetches PRs merged into this branch, to match "
        "the commit analysis of the default branch ('' = any)",
    )
    ap.add_argument("--commits-sample", type=int, default=None)
    ap.add_argument("--seed", type=int, default=20261012)
    ap.add_argument("--refresh-list", action="store_true")
    ap.add_argument("--max-pages", type=int, default=None, help="test mode only")
    ap.add_argument("--api-base", default="https://api.github.com")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(a.cache) if a.cache else out / "pr_raw"
    since, until, pol = ts(a.since), ts(a.until), ts(a.policy_date)
    pkg = Path(a.package)
    rules = load_package_classifier(pkg)
    pats = bot_patterns(pkg)

    token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_TOKENS", "").split(",")[0].strip()
        or None
    )
    if not token and "api.github.com" in a.api_base:
        raise SystemExit("set GITHUB_TOKEN first (unauthenticated = 60 requests/hour)")
    gh = GH(token, a.api_base)

    rows = list_prs(gh, a.repo, since, cache, a.refresh_list, a.max_pages)
    df = pd.DataFrame(rows)
    df["created"] = pd.to_datetime(df.created_at, utc=True)
    df["merged"] = pd.to_datetime(df.merged_at, utc=True)
    df = df[(df.created >= since) & (df.created <= until)].copy()
    df["is_bot"] = [is_bot(l, t, pats) for l, t in zip(df.login, df.user_type)]
    text = df.title.fillna("") + "\n\n" + df.body.fillna("")
    df["paper_rule"] = rules.contains_self_disclosed_ai_pr_trace(
        text.reset_index(drop=True)
    ).values
    df["body_has_assisted_by"] = df.body.fillna("").str.contains(
        DET_ASSISTED_BY, regex=True
    )
    df["period"] = (df.created >= pol).map({True: "post", False: "pre"})
    df["month"] = df.created.dt.tz_localize(None).dt.to_period("M").astype(str)
    df["week_start_utc"] = (
        df.created.dt.tz_localize(None)
        .dt.to_period("W-SUN")
        .dt.start_time.dt.strftime("%Y-%m-%d")
    )

    target = df[
        (~df.is_bot) & df.merged.notna() & (df.merged >= pol) & (df.merged <= until)
    ]
    if a.base:
        target = target[target.base == a.base]
    nums = sorted(target.number)
    sampled = False
    if a.commits_sample and a.commits_sample < len(nums):
        nums = sorted(random.Random(a.seed).sample(nums, a.commits_sample))
        sampled = True
    print(
        f"[2/3] commits for {len(nums)} merged post-policy non-bot PRs"
        f"{' (random sample)' if sampled else ''}; cached ones are skipped"
    )
    info = {}
    for i, n in enumerate(nums, 1):
        cs = pr_commits(gh, a.repo, n, cache)
        k = sum(bool(re.search(DET_ASSISTED_BY, c["message"])) for c in cs)
        info[n] = (len(cs), k)
        if i % 250 == 0:
            print(f"  {i}/{len(nums)} PRs ({gh.calls} API calls this run)")
    df["commits_fetched"] = df.number.isin(info)
    df["n_commits"] = df.number.map(lambda n: info.get(n, (None, None))[0])
    df["n_commits_assisted"] = df.number.map(lambda n: info.get(n, (None, None))[1])
    df["trailer_any"] = df.n_commits_assisted.fillna(0) > 0
    df["trailer_all"] = (df.n_commits_assisted == df.n_commits) & df.trailer_any

    keep = [
        "number",
        "base",
        "created_at",
        "merged_at",
        "month",
        "week_start_utc",
        "period",
        "is_bot",
        "draft",
        "paper_rule",
        "body_has_assisted_by",
        "commits_fetched",
        "n_commits",
        "n_commits_assisted",
        "trailer_any",
        "trailer_all",
    ]
    df[keep].to_csv(out / "pr_level.csv.gz", index=False)

    print("[3/3] summarising")
    hum = df[~df.is_bot]
    fetched = hum[hum.commits_fetched]

    def per(group: str) -> pd.DataFrame:
        g1 = hum.groupby(group).agg(
            nonbot_prs_opened=("number", "size"), paper_rule_count=("paper_rule", "sum")
        )
        g1["paper_rule_share"] = (g1.paper_rule_count / g1.nonbot_prs_opened).round(4)
        f = fetched.copy()
        f["merge_" + group] = (
            f.merged.dt.tz_localize(None).dt.to_period("M").astype(str)
            if group == "month"
            else f.merged.dt.tz_localize(None)
            .dt.to_period("W-SUN")
            .dt.start_time.dt.strftime("%Y-%m-%d")
        )
        g2 = f.groupby("merge_" + group).agg(
            merged_prs_with_commits=("number", "size"),
            trailer_any_count=("trailer_any", "sum"),
            paper_rule_on_merged=("paper_rule", "sum"),
        )
        g2["trailer_any_share"] = (
            g2.trailer_any_count / g2.merged_prs_with_commits
        ).round(4)
        g2.index.name = group
        return g1.join(g2, how="outer").fillna(
            {"merged_prs_with_commits": 0, "trailer_any_count": 0}
        )

    per("month").to_csv(out / "pr_level_monthly.csv")
    per("week_start_utc").to_csv(out / "pr_level_weekly.csv")

    def share(s: pd.Series) -> float:
        return round(float(s.mean()), 4) if len(s) else float("nan")

    pre, post = hum[hum.period == "pre"], hum[hum.period == "post"]
    xt = pd.crosstab(fetched.trailer_any, fetched.paper_rule)
    xt_d = {
        f"trailer={bool(r)}|paper_rule={bool(c)}": int(xt.loc[r, c])
        for r in xt.index
        for c in xt.columns
    }
    multi = fetched[(fetched.n_commits >= 2) & fetched.trailer_any]
    summ = {
        "repo": a.repo,
        "window": [a.since, a.until],
        "policy_date": a.policy_date,
        "prs_listed_in_window": int(len(df)),
        "bot_prs_excluded": int(df.is_bot.sum()),
        "paper_outcome_ai_disclosure_pr_share": {
            "definition": "non-bot PRs opened whose title+body match the package's "
            "contains_self_disclosed_ai_pr_trace, / non-bot PRs opened",
            "pre": {
                "prs": int(len(pre)),
                "flagged": int(pre.paper_rule.sum()),
                "share": share(pre.paper_rule),
            },
            "post": {
                "prs": int(len(post)),
                "flagged": int(post.paper_rule.sum()),
                "share": share(post.paper_rule),
            },
        },
        "merged_post_policy_nonbot_prs": int(len(target)),
        "base_branch": a.base or "any",
        "commits_fetched_for": int(len(fetched)),
        "commits_sampled": sampled,
        "trailer_level": {
            "prs_with_any_assisted_by_commit": int(fetched.trailer_any.sum()),
            "share": share(fetched.trailer_any),
            "paper_rule_on_same_prs": int(fetched.paper_rule.sum()),
            "paper_rule_share_on_same_prs": share(fetched.paper_rule),
            "trailer_prs_missed_by_paper_rule": int(
                (fetched.trailer_any & ~fetched.paper_rule).sum()
            ),
            "paper_rule_prs_without_trailer": int(
                (~fetched.trailer_any & fetched.paper_rule).sum()
            ),
            "crosstab": xt_d,
            "trailer_prs_whose_body_contains_assisted_by": int(
                (fetched.trailer_any & fetched.body_has_assisted_by).sum()
            ),
        },
        "within_pr_consistency": {
            "multi_commit_prs_with_a_trailer": int(len(multi)),
            "of_which_not_every_commit_discloses": int((~multi.trailer_all).sum()),
            "share_not_every_commit": share(~multi.trailer_all),
        },
        "api_calls_this_run": gh.calls,
        "bot_rule": "user type Bot, login ending [bot], or package agent_impact_bots.csv pattern",
    }
    (out / "pr_level_summary.json").write_text(json.dumps(summ, indent=2))
    t = summ["trailer_level"]
    p = summ["paper_outcome_ai_disclosure_pr_share"]
    md = [
        "# PR-level disclosure",
        "",
        f"Window {a.since} .. {a.until}; policy {a.policy_date}. "
        f"{len(df)} PRs listed, {int(df.is_bot.sum())} bot PRs excluded.",
        "",
        f"## The paper's outcome, computed for {a.repo}",
        "",
        "Share of non-bot PRs opened whose title + body match the package rule:",
        "",
        f"- before adoption: {p['pre']['flagged']} / {p['pre']['prs']} = {p['pre']['share']:.2%}",
        f"- after adoption: {p['post']['flagged']} / {p['post']['prs']} = {p['post']['share']:.2%}",
        "",
        "## Same merged post-policy PRs, two measures",
        "",
        f"- merged post-policy non-bot PRs: {len(target)}; commits fetched for "
        f"{len(fetched)}{' (random sample)' if sampled else ''}",
        f"- PRs with at least one `Assisted-by:` commit: {t['prs_with_any_assisted_by_commit']} "
        f"({t['share']:.2%})",
        f"- PRs the paper's rule flags: {t['paper_rule_on_same_prs']} "
        f"({t['paper_rule_share_on_same_prs']:.2%})",
        f"- trailer PRs the paper's rule misses: {t['trailer_prs_missed_by_paper_rule']}",
        f"- paper-rule PRs with no trailer: {t['paper_rule_prs_without_trailer']}",
        f"- trailer PRs whose description itself contains `Assisted-by:`: "
        f"{t['trailer_prs_whose_body_contains_assisted_by']} (the text is there; the "
        "rule has no pattern for it)",
        "",
        "## Within-PR consistency",
        "",
        f"- multi-commit PRs with a trailer: {summ['within_pr_consistency']['multi_commit_prs_with_a_trailer']}; "
        f"not every commit discloses in {summ['within_pr_consistency']['of_which_not_every_commit_discloses']}",
        "",
        "Disclosed use only. Undisclosed AI use is not measurable from these artifacts.",
    ]
    (out / "pr_level_summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
