#!/usr/bin/env python3
# Tools named in the trailers, and how consistently authors keep disclosing.

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

FAMILIES = [("claude", r"claude"), ("copilot", r"copilot"), ("cursor", r"cursor"),
            ("codex", r"codex"), ("gemini", r"gemini"), ("chatgpt", r"chatgpt|gpt"),
            ]


def family(agent: str) -> str:
    a = (agent or "").lower()
    for name, pat in FAMILIES:
        if re.search(pat, a):
            return name
    return "other" if a else "unparsed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--policy-date", required=True)
    ap.add_argument("--until", default=None, help="last day included, YYYY-MM-DD")
    a = ap.parse_args()
    out = Path(a.out)

    L = pd.read_csv(out / "assisted_by_lines.csv")
    L = L[L.period == "post"].copy()
    if a.until:
        L = L[L.date <= a.until]
    L["agent"] = L.agent.fillna("")
    L["family"] = L.agent.map(family)
    fam = pd.crosstab(L.month, L.family)
    fam["total_lines"] = fam.sum(axis=1)
    fam.to_csv(out / "tools_by_month.csv")
    raw = L.agent.replace("", "(none)").value_counts().rename_axis("agent").reset_index(name="lines")
    raw["share"] = (raw.lines / raw.lines.sum()).round(4)
    raw.to_csv(out / "tools_overall.csv", index=False)
    fam_tot = L.family.value_counts()
    print("A. trailer lines by tool family (post-policy):")
    print((fam_tot / fam_tot.sum()).round(3).to_string())

    C = pd.read_csv(out / "commits_classified.csv.gz",
                    usecols=["sha", "commit_date", "date", "author_email", "t_assisted_by"])
    C = C[C.date >= a.policy_date]
    if a.until:
        C = C[C.date <= a.until]
    C["ts"] = pd.to_datetime(C.commit_date, utc=True, format="mixed")
    C = C.sort_values(["author_email", "ts", "sha"])
    rows = []
    for _, g in C.groupby("author_email", sort=False):
        flags = g.t_assisted_by.astype(bool).to_list()
        if not any(flags):
            continue
        i = flags.index(True)
        later = flags[i + 1:]
        rows.append({"later_commits": len(later), "later_disclosing": sum(later)})
    P = pd.DataFrame(rows)
    with_later = P[P.later_commits > 0].copy()
    with_later["share"] = with_later.later_disclosing / with_later.later_commits
    pooled = (with_later.later_disclosing.sum() / with_later.later_commits.sum()
              if len(with_later) else float("nan"))
    summ = {
        "authors_who_ever_disclosed": int(len(P)),
        "with_at_least_one_later_commit": int(len(with_later)),
        "later_commits_total": int(with_later.later_commits.sum()),
        "later_commits_disclosing_pooled_share": round(float(pooled), 4),
        "per_author_share_median": round(float(with_later.share.median()), 4) if len(with_later) else None,
        "authors_disclosing_on_every_later_commit": int((with_later.share == 1).sum()),
        "authors_disclosing_on_no_later_commit": int((with_later.share == 0).sum()),
        "note": "persistence of disclosure, not of AI use",
    }
    bins = pd.cut(with_later.share, [-0.001, 0, 0.25, 0.5, 0.75, 0.999, 1.0],
                  labels=["0", "(0-25%]", "(25-50%]", "(50-75%]", "(75-<100%)", "100%"])
    bins.value_counts().sort_index().rename_axis("share_of_later_commits_disclosing") \
        .reset_index(name="authors").to_csv(out / "disclosure_persistence_bins.csv", index=False)
    (out / "tools_and_persistence_summary.json").write_text(json.dumps(
        {"tools_family_share": (fam_tot / fam_tot.sum()).round(4).to_dict(),
         "persistence": summ}, indent=2))
    print("\nB. disclosure persistence after an author's first disclosing commit:")
    print(json.dumps(summ, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
