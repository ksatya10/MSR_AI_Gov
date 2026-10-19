#!/usr/bin/env python3
# Applies the PR-text detector and the extended detector (PR text plus commit messages) to merged PRs.

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from pipeline123.MSR_AI_Gov.github_share.common import (
    DET_ASSISTED_BY,
    DET_GENERATED_BY,
    TRAILER_COAUTHORED_AI,
)
from pipeline123.MSR_AI_Gov.github_share.s14_tool_rules import (
    GENERATED_WITH,
    CLAUDE_FOOTER,
)

ASSISTED = re.compile(DET_ASSISTED_BY)
GENERATED_BY = re.compile(DET_GENERATED_BY)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    out = Path(a.out)

    pr = pd.read_csv(out / "pr_level.csv.gz")
    pr = pr[pr.commits_fetched == True].copy()
    print(f"PRs in population: {len(pr)}")

    texts = {}
    with open(out / "pr_raw" / "pr_list.jsonl") as f:
        for line in f:
            d = json.loads(line)
            texts[d["number"]] = f"{d.get('title') or ''}\n{d.get('body') or ''}"

    rows = []
    for n in pr.number:
        msgs = [
            c.get("message") or ""
            for c in json.loads(
                (out / "pr_raw" / "commits" / f"{int(n)}.json").read_text()
            )
        ]
        text = texts[int(n)]
        rows.append(
            {
                "number": int(n),
                "n_commits_read": len(msgs),
                "c2_text_assisted": bool(ASSISTED.search(text)),
                "c3_commit_assisted": any(ASSISTED.search(m) for m in msgs),
                "c4_commit_coauthor": any(
                    TRAILER_COAUTHORED_AI.search(m) for m in msgs
                ),
                "c5_commit_generated": any(
                    GENERATED_BY.search(m)
                    or GENERATED_WITH.search(m)
                    or CLAUDE_FOOTER.search(m)
                    for m in msgs
                ),
            }
        )
    x = pr[["number", "paper_rule", "trailer_any", "body_has_assisted_by"]].merge(
        pd.DataFrame(rows), on="number", how="left"
    )
    x["c1_paper_rule"] = x.paper_rule.astype(bool)

    checks = {
        "paper_rule == 8": int(x.c1_paper_rule.sum()) == 8,
        "trailer == 1864": int(x.c3_commit_assisted.sum()) == 1864,
        "both == 4": int((x.c1_paper_rule & x.c3_commit_assisted).sum()) == 4,
        "c3 equals s9 trailer_any on every PR": bool(
            (x.c3_commit_assisted == x.trailer_any.astype(bool)).all()
        ),
        "c2 equals s9 body_has_assisted_by on every PR": bool(
            (x.c2_text_assisted == x.body_has_assisted_by.astype(bool)).all()
        ),
    }
    for k, v in checks.items():
        print(("OK   " if v else "FAIL ") + k)
    if not all(checks.values()):
        print("Stopping: the components do not reproduce s9. Find out why first.")
        return 1

    comps = [
        "c1_paper_rule",
        "c2_text_assisted",
        "c3_commit_assisted",
        "c4_commit_coauthor",
        "c5_commit_generated",
    ]
    x["extended"] = x[comps].any(axis=1)
    N = len(x)
    summary = {
        "population": "merged non-bot PRs to main, merged 2026-03-06..2026-09-30, commits fetched",
        "n_prs": N,
        "checks": checks,
        "per_component": {c: int(x[c].sum()) for c in comps},
        "extended_union": int(x.extended.sum()),
        "extended_share": round(x.extended.mean(), 4),
        "paper_rule_share": round(x.c1_paper_rule.mean(), 4),
        "added_by_extension_over_paper_rule": int(
            (x.extended & ~x.c1_paper_rule).sum()
        ),
        "only_component": {
            c: int((x[c] & (x[comps].sum(axis=1) == 1)).sum()) for c in comps
        },
        "paper_rule_only_prs_flagged_by_no_other_component": int(
            (x.c1_paper_rule & ~x[comps[1:]].any(axis=1)).sum()
        ),
        "text_only_detectors_union_c1_c2": int(
            (x.c1_paper_rule | x.c2_text_assisted).sum()
        ),
        "note": "Counts disclosures the policy asks for; recall against real AI use cannot be measured.",
    }
    (out / "detector_extension_summary.json").write_text(json.dumps(summary, indent=2))
    x.drop(columns=["paper_rule", "trailer_any", "body_has_assisted_by"]).to_csv(
        out / "detector_extension_prs.csv.gz", index=False
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
