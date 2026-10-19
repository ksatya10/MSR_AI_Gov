#!/usr/bin/env python3
# Fetches policy threads and PR review discussions from the GitHub API and builds coding sheets.

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

KEYWORDS = re.compile(
    r"(?i)(assisted-by|generated-by|co-authored-by|\btrailer\b|\btag\b|"
    r"\bAI\b|\bLLM\b|copilot|claude|chatgpt|codex|cursor|gemini|disclos)")


MENTION = re.compile(r"(?<![\w/])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))")
PROFILE_URL = re.compile(r"https://github\.com/([A-Za-z0-9-]+)(?=[)\s\]]|$)")


def redact_handles(text: str, pseud: dict[str, str] | None = None) -> str:
    low = {k.lower(): v for k, v in (pseud or {}).items()}

    def sub(m):
        return "@" + low.get(m.group(1).lower(), "[user]")
    text = MENTION.sub(sub, text or "")
    return PROFILE_URL.sub(
        lambda m: "https://github.com/" + low.get(m.group(1).lower(), "[user]"), text)


class GH:
    def __init__(self, token: str | None, base: str):
        self.token, self.base, self.calls = token, base.rstrip("/"), 0

    def get(self, path_or_url: str):
        url = path_or_url if path_or_url.startswith("http") else self.base + path_or_url
        headers = {"Accept": "application/vnd.github+json",
                   "User-Agent": "trace-case-study"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(5):
            try:
                self.calls += 1
                with urllib.request.urlopen(
                        urllib.request.Request(url, headers=headers), timeout=60) as r:
                    nxt = None
                    for part in (r.headers.get("Link") or "").split(","):
                        m = re.search(r'<([^>]+)>;\s*rel="next"', part)
                        if m:
                            nxt = m.group(1)
                    return json.loads(r.read().decode("utf-8")), nxt
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None, None
                if e.code in (403, 429):
                    reset = e.headers.get("x-ratelimit-reset")
                    if e.headers.get("x-ratelimit-remaining") == "0" and reset:
                        wait = max(5, int(reset) - int(time.time()) + 2)
                        print(f"  rate limit reached; waiting {wait}s", file=sys.stderr)
                        time.sleep(min(wait, 3700))
                        continue
                    time.sleep(2 ** attempt * 2)
                    continue
                if e.code >= 500:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError) as e:
                print(f"  network error ({e}); retrying", file=sys.stderr)
                time.sleep(2 ** attempt)
        raise SystemExit(f"giving up on {url}")

    def all(self, path: str) -> list:
        sep = "&" if "?" in path else "?"
        out, url = [], f"{path}{sep}per_page=100"
        while url:
            data, url = self.get(url)
            if not data:
                break
            out += data
        return out


def discussion(gh: GH, repo: str, number: int) -> dict | None:
    issue, _ = gh.get(f"/repos/{repo}/issues/{number}")
    if issue is None:
        return None
    is_pr = "pull_request" in issue
    items = [{"kind": "opening_post", "login": (issue.get("user") or {}).get("login", ""),
              "association": issue.get("author_association", ""),
              "created_at": issue.get("created_at", ""), "text": issue.get("body") or ""}]
    for c in gh.all(f"/repos/{repo}/issues/{number}/comments"):
        items.append({"kind": "comment", "login": (c.get("user") or {}).get("login", ""),
                      "association": c.get("author_association", ""),
                      "created_at": c.get("created_at", ""), "text": c.get("body") or ""})
    if is_pr:
        for r in gh.all(f"/repos/{repo}/pulls/{number}/reviews"):
            if (r.get("body") or "").strip():
                items.append({"kind": f"review_{(r.get('state') or '').lower()}",
                              "login": (r.get("user") or {}).get("login", ""),
                              "association": r.get("author_association", ""),
                              "created_at": r.get("submitted_at") or "",
                              "text": r.get("body") or ""})
        for c in gh.all(f"/repos/{repo}/pulls/{number}/comments"):
            items.append({"kind": "inline_review_comment",
                          "login": (c.get("user") or {}).get("login", ""),
                          "association": c.get("author_association", ""),
                          "created_at": c.get("created_at", ""),
                          "text": c.get("body") or "",
                          "file": c.get("path", "")})
    items.sort(key=lambda x: x["created_at"] or "")
    return {"number": number, "is_pr": is_pr, "title": issue.get("title", ""),
            "state": issue.get("state", ""), "url": issue.get("html_url", ""),
            "merged": bool((issue.get("pull_request") or {}).get("merged_at")),
            "items": items}


def run_threads(gh: GH, args) -> int:
    out = Path(args.out)
    (out / "threads_raw").mkdir(parents=True, exist_ok=True)
    pseud: dict[str, str] = {}
    rows, threads, bots = [], [], 0
    for n in args.numbers:
        d = discussion(gh, args.repo, n)
        if d is None:
            print(f"  ! #{n} not found")
            continue
        (out / "threads_raw" / f"thread_{n}.json").write_text(json.dumps(d, indent=2))
        threads.append((n, d))
        for it in d["items"]:
            if not it["login"].endswith("[bot]"):
                pseud.setdefault(it["login"], f"P{len(pseud)+1:02d}")
    for n, d in threads:
        i = 0
        for it in d["items"]:
            if it["login"].endswith("[bot]"):
                bots += 1
                continue
            i += 1
            rows.append({"thread": n, "thread_type": "pull_request" if d["is_pr"] else "issue",
                         "seq": i, "kind": it["kind"], "participant": pseud[it["login"]],
                         "role": it["association"], "created_at": it["created_at"],
                         "file": it.get("file", ""),
                         "text": redact_handles(it["text"], pseud),
                         "codes": "", "memo": ""})
        print(f"  #{n} ({'PR' if d['is_pr'] else 'issue'}): {i} contributions — {d['title']}")
    if bots:
        print(f"  ({bots} bot comment(s) left out of the coding sheet)")
    pd.DataFrame(rows).to_csv(out / "thread_coding_sheet.csv", index=False)
    pd.DataFrame(sorted(pseud.items(), key=lambda kv: kv[1]),
                 columns=["login", "participant"]).to_csv(
        out / "thread_participants_PRIVATE.csv", index=False)
    print(f"{len(rows)} rows -> {out}/thread_coding_sheet.csv   ({gh.calls} API calls)")
    return 0


def run_malformed(gh: GH, args) -> int:
    out = Path(args.out)
    (out / "enforcement_raw").mkdir(parents=True, exist_ok=True)
    lines = pd.read_csv(args.lines)
    post = lines[lines.period == "post"]
    bad = sorted(set(post[~post.fmt_lenient.astype(bool)].sha))
    good_pool = sorted(set(post[post.fmt_strict.astype(bool)].sha) - set(bad))
    rng = random.Random(args.seed)
    n_ctrl = len(bad) if args.control_n is None else args.control_n
    good = rng.sample(good_pool, min(n_ctrl, len(good_pool)))
    print(f"malformed commits: {len(bad)}; comparison commits sampled: {len(good)} (seed {args.seed})")

    pr_group: dict[int, str] = {}
    pr_shas: dict[int, list[str]] = {}
    unmapped = []
    for group, shas in (("malformed", bad), ("wellformed", good)):
        for sha in shas:
            prs, _ = gh.get(f"/repos/{args.repo}/commits/{sha}/pulls")
            prs = prs or []
            merged = [p for p in prs if p.get("merged_at")] or prs
            if not merged:
                unmapped.append({"sha": sha, "group": group})
                continue
            n = merged[0]["number"]
            if pr_group.get(n) != "malformed":
                pr_group[n] = group
            pr_shas.setdefault(n, []).append(sha)

    cases = sorted(pr_group)
    rng.shuffle(cases)
    sheet, key = [], []
    for i, n in enumerate(cases, 1):
        d = discussion(gh, args.repo, n)
        if d is None:
            continue
        (out / "enforcement_raw" / f"pr_{n}.json").write_text(json.dumps(d, indent=2))
        author = d["items"][0]["login"] if d["items"] else ""
        others = [it for it in d["items"][1:] if it["login"] != author
                  and not it["login"].endswith("[bot]")]
        hits = [it for it in others if KEYWORDS.search(it["text"])]
        case = f"E{i:03d}"
        sheet.append({
            "case_id": case, "pr_number": n, "url": d["url"], "title": d["title"],
            "merged": d["merged"], "n_reviewer_comments": len(others),
            "n_keyword_comments": len(hits),
            "keyword_excerpts": " ||| ".join(
                redact_handles(" ".join(h["text"].split()))[:300] for h in hits[:4]),
            "reviewer_objected": "", "objection_type": "", "note": ""})
        key.append({"case_id": case, "pr_number": n, "group": pr_group[n],
                    "commit_shas": " ".join(pr_shas[n])})
        if i % 25 == 0:
            print(f"  {i}/{len(cases)} PRs fetched ({gh.calls} API calls)")
    pd.DataFrame(sheet).to_csv(out / "enforcement_coding_sheet.csv", index=False)
    pd.DataFrame(key).to_csv(out / "enforcement_group_key_PRIVATE.csv", index=False)
    pd.DataFrame(unmapped, columns=["sha", "group"]).to_csv(
        out / "enforcement_unmapped_commits.csv", index=False)
    k = pd.DataFrame(key)
    print(f"{len(sheet)} PRs -> {out}/enforcement_coding_sheet.csv "
          f"({(k.group == 'malformed').sum()} malformed, "
          f"{(k.group == 'wellformed').sum()} comparison; "
          f"{len(unmapped)} commits had no PR; {gh.calls} API calls)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    for name in ("threads", "malformed"):
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True)
        p.add_argument("--out", default="out")
        p.add_argument("--api-base", default="https://api.github.com")
    sub.choices["threads"].add_argument("--numbers", nargs="+", type=int, required=True)
    m = sub.choices["malformed"]
    m.add_argument("--lines", required=True, help="assisted_by_lines.csv from s4")
    m.add_argument("--control-n", type=int, default=None)
    m.add_argument("--seed", type=int, default=20261005)
    args = ap.parse_args()

    token = (os.environ.get("GITHUB_TOKEN")
             or os.environ.get("GITHUB_TOKENS", "").split(",")[0].strip() or None)
    if not token and "api.github.com" in args.api_base:
        raise SystemExit("set GITHUB_TOKEN first (unauthenticated = 60 requests/hour)")
    gh = GH(token, args.api_base)
    return run_threads(gh, args) if args.mode == "threads" else run_malformed(gh, args)


if __name__ == "__main__":
    raise SystemExit(main())
