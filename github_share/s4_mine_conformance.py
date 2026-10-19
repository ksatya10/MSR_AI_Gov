#!/usr/bin/env python3
# Mines commit messages for Assisted-by trailers, AI co-author lines and sign-offs.

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import sys
from pathlib import Path

import pandas as pd

from pipeline123.MSR_AI_Gov.github_share.common import (
    AI_TOOL_EXT,
    AI_TOOL_PKG,
    DET_ASSISTED_BY,
    DET_GENERATED_BY,
    DET_SIGNED_OFF,
    FMT_LENIENT,
    FMT_STRICT,
    HUMAN_AI_DOMAIN,
    TRAILER_ASSISTED_BY,
    TRAILER_COAUTHORED_AI,
    TRAILER_KEY_ANY,
    TRAILER_KEYS_STANDARD,
    TRAILER_SIGNED_OFF_AI,
    git_log_records,
)

AI_ANY_MENTION = re.compile(rf"(?i)\b{AI_TOOL_EXT}\b")


def load_package_classifier(pkg: Path):
    p = pkg / "data/classification_rules/ai_disclosure/text_classification.py"
    if not p.exists():
        raise SystemExit(f"classifier not found at {p}")
    spec = importlib.util.spec_from_file_location("pkg_text_classification", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pkg_text_classification"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-history", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--policy-date", required=True, help="YYYY-MM-DD")
    ap.add_argument(
        "--until",
        default=None,
        help="data-freeze cutoff, e.g. '2026-09-30 23:59:59 +0000'; "
        "commits after it are ignored",
    )
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pkg = Path(args.package)
    rules = load_package_classifier(pkg)

    print(f"[1/5] reading commits since {args.since}")
    recs = git_log_records(Path(args.repo_history), args.since, until=args.until)
    df = pd.DataFrame(recs)
    if df.empty:
        raise SystemExit("no commits read — check --repo-history has full history")
    df["date"] = df.commit_date.str[:10]
    df["month"] = df.date.str[:7]
    print(f"      {len(df)} commits, {df.date.min()} .. {df.date.max()}")

    print("[2/5] applying the package's own PR disclosure rule (unmodified)")
    df["pkg_rule"] = rules.contains_self_disclosed_ai_pr_trace(df.message)
    df["pkg_ai_trace"] = rules.contains_ai_trace(df.message)

    print("[3/5] applying trailer rules")
    df["t_assisted_by"] = df.message.str.contains(DET_ASSISTED_BY, regex=True, na=False)
    df["t_generated_by"] = df.message.str.contains(
        DET_GENERATED_BY, regex=True, na=False
    )
    df["t_coauthored_ai"] = df.message.str.contains(
        TRAILER_COAUTHORED_AI.pattern, regex=True, na=False
    )
    df["t_any"] = df.t_assisted_by | df.t_generated_by | df.t_coauthored_ai
    df["has_signoff"] = df.message.str.contains(DET_SIGNED_OFF, regex=True, na=False)
    df["signoff_names_ai"] = df.message.str.contains(
        TRAILER_SIGNED_OFF_AI.pattern, regex=True, na=False
    )
    df["mentions_ai_tool"] = df.message.str.contains(
        AI_ANY_MENTION.pattern, regex=True, na=False
    )
    df["disclosed_either"] = df.pkg_rule | df.t_any
    df["trailer_only"] = df.t_any & ~df.pkg_rule
    df["week_start_utc"] = (
        pd.to_datetime(df.commit_date, utc=True, format="mixed")
        .dt.tz_localize(None)
        .dt.to_period("W-SUN")
        .dt.start_time.dt.strftime("%Y-%m-%d")
    )

    POL = args.policy_date
    pre, post = df[df.date < POL], df[df.date >= POL]

    print("[4/5] trailer-level analysis")
    lines = []
    for _, r in df[df.t_assisted_by].iterrows():
        for m in TRAILER_ASSISTED_BY.finditer(r.message):
            val = " ".join(m.group(1).split())
            lines.append(
                {
                    "sha": r.sha,
                    "date": r.date,
                    "month": r.month,
                    "period": "post" if r.date >= POL else "pre",
                    "value": val,
                    "fmt_strict": bool(FMT_STRICT.match(val)),
                    "fmt_lenient": bool(FMT_LENIENT.match(val)),
                    "agent": val.split(":")[0].strip().lower() if ":" in val else "",
                    "has_signoff": r.has_signoff,
                }
            )
    ab = pd.DataFrame(lines)
    if not ab.empty:
        ab.to_csv(out / "assisted_by_lines.csv", index=False)

    keys = collections.Counter()
    for _, r in post.iterrows():
        for m in TRAILER_KEY_ANY.finditer(r.message):
            k, v = m.group(1).strip(), m.group(2).strip()
            if k.lower() in TRAILER_KEYS_STANDARD:
                continue
            if AI_ANY_MENTION.search(v) or re.search(
                r"(?i)(assist|generat|\bai\b|agent)", k
            ):
                keys[k] += 1
    kdf = pd.DataFrame(
        sorted(keys.items(), key=lambda kv: -kv[1]), columns=["trailer_key", "n_lines"]
    )
    if not kdf.empty:
        kdf["is_prescribed_key"] = kdf.trailer_key.str.lower() == "assisted-by"
        kdf.to_csv(out / "trailer_keys.csv", index=False)

    sv = []
    for _, r in df[df.signoff_names_ai].iterrows():
        for ln in r.message.split("\n"):
            if re.match(r"(?i)^\s*Signed-off-by", ln) and re.search(
                rf"(?i)\b{AI_TOOL_EXT}\b", ln
            ):
                sv.append(
                    {
                        "sha": r.sha,
                        "date": r.date,
                        "signoff_line": ln.strip(),
                        "looks_like_human_at_ai_org": bool(HUMAN_AI_DOMAIN.search(ln)),
                        "manual_verdict": "",
                    }
                )
    svdf = pd.DataFrame(sv)
    if not svdf.empty:
        svdf.to_csv(out / "signoff_ai_candidates.csv", index=False)

    print("[5/5] writing panels and summary")
    g = df.groupby("month").agg(
        commits=("sha", "size"),
        assisted_by=("t_assisted_by", "sum"),
        coauthored_ai=("t_coauthored_ai", "sum"),
        pkg_rule=("pkg_rule", "sum"),
    )
    g["assisted_by_pct"] = (100 * g.assisted_by / g.commits).round(2)
    g["pkg_rule_pct"] = (100 * g.pkg_rule / g.commits).round(2)
    g.reset_index().to_csv(out / "disclosure_monthly.csv", index=False)

    w = (
        df.groupby("week_start_utc")
        .agg(
            commits=("sha", "size"),
            assisted_by=("t_assisted_by", "sum"),
            pkg_rule=("pkg_rule", "sum"),
        )
        .reset_index()
    )
    w["assisted_by_share"] = (w.assisted_by / w.commits).round(4)
    w["pkg_rule_share"] = (w.pkg_rule / w.commits).round(4)
    w.insert(0, "repo", Path(args.repo_history).resolve().name)
    w.to_csv(out / "disclosure_weekly.csv", index=False)

    df.drop(columns=["message"]).to_csv(
        out / "commits_classified.csv.gz", index=False, compression="gzip"
    )

    abp = ab[ab.period == "post"] if not ab.empty else ab
    S = {
        "repo_history": str(Path(args.repo_history).resolve()),
        "package": str(pkg),
        "window": {
            "since": args.since,
            "until": args.until,
            "last_commit": df.date.max(),
            "policy_date": POL,
        },
        "commits": {"total": len(df), "pre_policy": len(pre), "post_policy": len(post)},
        "T_transparency": {
            "assisted_by_commits_pre": int(pre.t_assisted_by.sum()),
            "assisted_by_commits_post": int(post.t_assisted_by.sum()),
            "assisted_by_share_post": round(float(post.t_assisted_by.mean()), 4),
            "coauthored_ai_commits_post": int(post.t_coauthored_ai.sum()),
            "generated_by_commits_post": int(post.t_generated_by.sum()),
            "trailer_lines_total": int(len(ab)),
            "format_conformance_lenient_post": (
                round(float(abp.fmt_lenient.mean()), 4) if len(abp) else None
            ),
            "format_conformance_strict_post": (
                round(float(abp.fmt_strict.mean()), 4) if len(abp) else None
            ),
            "no_colon_at_all_post": int((~abp.fmt_lenient).sum()) if len(abp) else 0,
            "prescribed_key_share": (
                round(
                    float(
                        kdf.loc[kdf.is_prescribed_key, "n_lines"].sum()
                        / kdf.n_lines.sum()
                    ),
                    4,
                )
                if not kdf.empty
                else None
            ),
            "variant_key_lines": (
                int(kdf.loc[~kdf.is_prescribed_key, "n_lines"].sum())
                if not kdf.empty
                else 0
            ),
        },
        "A_attribution": {
            "disclosing_commits_with_human_signoff_post": (
                int(post[post.t_assisted_by].has_signoff.sum())
            ),
            "disclosing_commits_post": int(post.t_assisted_by.sum()),
            "signoff_lines_naming_ai_total": int(len(svdf)),
            "of_which_look_like_human_at_ai_org": (
                int(svdf.looks_like_human_at_ai_org.sum()) if not svdf.empty else 0
            ),
            "note": (
                "signoff_ai_candidates.csv requires manual verdicts; the "
                "domain filter is a screening aid, not a finding."
            ),
        },
        "baseline_package_rule": {
            "pkg_rule_hits_post": int(post.pkg_rule.sum()),
            "trailer_hits_post": int(post.t_any.sum()),
            "disclosed_by_trailer_but_missed_by_pkg_rule": int(post.trailer_only.sum()),
            "ratio_trailer_to_pkg_rule": (
                round(float(post.t_any.sum() / post.pkg_rule.sum()), 1)
                if post.pkg_rule.sum()
                else None
            ),
            "caveat": (
                "the package applies this rule to PR title+body, where "
                "commit trailers do not appear; applying it to commit "
                "messages is therefore an UPPER bound on what the "
                "published pipeline would have detected."
            ),
        },
        "limits": {
            "undisclosed_use_not_measurable": True,
            "post_policy_commits_naming_ai_without_trailer": int(
                post[~post.t_any].mentions_ai_tool.sum()
            ),
        },
        "vocabulary": {"package_tools": AI_TOOL_PKG, "extended_tools": AI_TOOL_EXT},
    }
    (out / "conformance_summary.json").write_text(json.dumps(S, indent=2))

    L = [
        "# Conformance summary",
        "",
        f"- repository history: `{S['repo_history']}`",
        f"- window: {args.since} .. {df.date.max()}; policy adopted {POL}",
        f"- commits: {len(df)} ({len(pre)} pre-policy, {len(post)} post-policy)",
        "",
        "## T — Transparency",
        "",
        f"- `Assisted-by:` commits: **{int(pre.t_assisted_by.sum())} pre** -> "
        f"**{int(post.t_assisted_by.sum())} post** "
        f"({100 * post.t_assisted_by.mean():.2f}% of post-policy commits)",
        f"- trailer lines analysed: {len(ab)}",
    ]
    if len(abp):
        L += [
            f"- format conformance (lenient): {100 * abp.fmt_lenient.mean():.1f}%",
            f"- format conformance (strict): {100 * abp.fmt_strict.mean():.1f}%",
            f"- no `Agent:Model` colon at all: {int((~abp.fmt_lenient).sum())} lines",
        ]
    if not kdf.empty:
        L += [
            f"- prescribed key `Assisted-by:` used on "
            f"{100 * kdf.loc[kdf.is_prescribed_key, 'n_lines'].sum() / kdf.n_lines.sum():.1f}% "
            f"of AI-disclosing trailer lines"
        ]
    L += [
        "",
        "## A — Attribution",
        "",
        f"- disclosing commits carrying a human `Signed-off-by`: "
        f"{int(post[post.t_assisted_by].has_signoff.sum())} / "
        f"{int(post.t_assisted_by.sum())}",
        f"- `Signed-off-by` lines naming an AI tool: {len(svdf)} "
        f"(**manual review required** — see signoff_ai_candidates.csv)",
        "",
        "## Baseline — the package's own rule",
        "",
        f"- package rule on the same text: {int(post.pkg_rule.sum())} commits",
        f"- trailer rules: {int(post.t_any.sum())} commits",
        f"- disclosed by trailer, missed by the package rule: "
        f"{int(post.trailer_only.sum())}",
        "",
        "## Monthly series",
        "",
        "| month | commits | Assisted-by | % | pkg rule |",
        "|---|---|---|---|---|",
    ]
    for m, r in g.iterrows():
        L.append(
            f"| {m} | {int(r.commits)} | {int(r.assisted_by)} | "
            f"{r.assisted_by_pct} | {int(r.pkg_rule)} |"
        )
    L += [
        "",
        "## What this does not measure",
        "",
        "Undisclosed AI use. Every count above is DISCLOSED use; the trend is "
        "consistent with more AI use, more disclosure, or both.",
        "",
    ]
    (out / "conformance_summary.md").write_text("\n".join(L), encoding="utf-8")

    print("\n" + json.dumps(S, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
