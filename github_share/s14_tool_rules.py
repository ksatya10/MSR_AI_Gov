#!/usr/bin/env python3
# Counts violations of the rules in the tool-facing files.

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import pandas as pd

from pipeline123.MSR_AI_Gov.github_share.common import (
    TRAILER_ASSISTED_BY,
    TRAILER_COAUTHORED_AI,
)

TOOLS = r"(?:claude(?:\s+code)?|copilot|cursor|codex|gemini|chatgpt|gpt-?\d|windsurf|aider|devin|jules|kiro)"
GENERATED_WITH = re.compile(rf"(?i)\bgenerated\s+(?:with|by|using)\s+\[?{TOOLS}\b")
CLAUDE_FOOTER = re.compile(
    r"(?i)🤖\s*generated with|claude\.(?:com|ai)/(?:code|claude-code)"
)


def period(d: pd.Timestamp, pol: pd.Timestamp, ag: pd.Timestamp) -> str:
    return (
        "1 before policy"
        if d < pol
        else ("2 policy to AGENTS.md" if d < ag else "3 after AGENTS.md")
    )


def commits(history: str, since: str, until: str) -> pd.DataFrame:
    fmt = "%H%x1f%cI%x1f%B%x1e"
    raw = subprocess.run(
        [
            "git",
            "-C",
            history,
            "log",
            f"--since={since}",
            f"--until={until}",
            f"--format={fmt}",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, date, body = (rec.split("\x1f", 2) + ["", ""])[:3]
        rows.append({"sha": sha, "date": date, "msg": body})
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-history", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--policy-date", required=True)
    ap.add_argument("--agents-date", required=True)
    ap.add_argument("--until", required=True, help="last day, YYYY-MM-DD")
    a = ap.parse_args()
    out = Path(a.out)
    pol, ag = (
        pd.Timestamp(a.policy_date, tz="UTC"),
        pd.Timestamp(a.agents_date, tz="UTC"),
    )

    c = commits(a.repo_history, a.since, f"{a.until} 23:59:59 +0000")
    c["d"] = pd.to_datetime(c.date, utc=True)
    c["period"] = [period(d, pol, ag) for d in c.d]
    c["coauthor_ai"] = c.msg.str.contains(TRAILER_COAUTHORED_AI)
    c["n_assisted"] = c.msg.map(lambda m: len(TRAILER_ASSISTED_BY.findall(m)))
    c["generated_with"] = c.msg.str.contains(GENERATED_WITH) | c.msg.str.contains(
        CLAUDE_FOOTER
    )
    gc = c.groupby("period").agg(
        commits=("sha", "size"),
        R1_coauthored_by_ai=("coauthor_ai", "sum"),
        commits_with_assisted_by=("n_assisted", lambda s: int((s > 0).sum())),
        R2_more_than_one_assisted_by=("n_assisted", lambda s: int((s > 1).sum())),
        R3_generated_with_in_commit=("generated_with", "sum"),
    )
    gc.to_csv(out / "tool_rules_commits.csv")
    print("commits:\n" + gc.to_string())

    res = {"commits": gc.reset_index().to_dict("records")}
    cache = out / "pr_raw" / "pr_list.jsonl"
    if cache.exists():
        p = pd.DataFrame(
            [json.loads(x) for x in cache.read_text().splitlines() if x.strip()]
        )
        p["d"] = pd.to_datetime(p.created_at, utc=True)
        p = p[
            (p.d >= pd.Timestamp(a.since, tz="UTC"))
            & (p.d <= pd.Timestamp(f"{a.until} 23:59:59", tz="UTC"))
        ]
        p = p[
            ~(p.user_type.eq("Bot") | p.login.str.lower().str.endswith("[bot]"))
        ].copy()
        body = p.body.fillna("")
        p["period"] = [period(d, pol, ag) for d in p.d]
        p["generated_with"] = body.str.contains(GENERATED_WITH) | body.str.contains(
            CLAUDE_FOOTER
        )
        p["coauthor_ai"] = body.str.contains(TRAILER_COAUTHORED_AI)
        gp = p.groupby("period").agg(
            nonbot_prs_opened=("number", "size"),
            R3_generated_with_in_pr_body=("generated_with", "sum"),
            R1_coauthored_by_ai_in_pr_body=("coauthor_ai", "sum"),
        )
        gp.to_csv(out / "tool_rules_pr_bodies.csv")
        print("\nPR descriptions (non-bot):\n" + gp.to_string())
        res["pr_bodies"] = gp.reset_index().to_dict("records")
    else:
        print(
            "\nPR descriptions: run s9_pr_level.py first (needs out/pr_raw/pr_list.jsonl)"
        )
    (out / "tool_rules_summary.json").write_text(json.dumps(res, indent=2, default=int))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
