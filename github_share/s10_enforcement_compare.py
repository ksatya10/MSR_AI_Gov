#!/usr/bin/env python3
# Compares reviewer objections between groups of PRs from a coded sheet.

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
from scipy.stats import fisher_exact

from pipeline123.MSR_AI_Gov.github_share.s5_interrater import read_sheet

YES = {"yes", "y", "true", "1"}
NO = {"no", "n", "false", "0"}


def norm(v) -> str:
    s = "" if pd.isna(v) else str(v).strip().lower()
    return "yes" if s in YES else "no" if s in NO else s


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(c - h, 4), round(c + h, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coders", nargs="+", required=True)
    ap.add_argument("--names", nargs="*")
    ap.add_argument(
        "--resolutions",
        default=None,
        help="agreement_disagreements.csv from s5c with `resolution` filled",
    )
    ap.add_argument("--key", required=True, help="enforcement_group_key_PRIVATE.csv")
    ap.add_argument(
        "--sheet",
        required=True,
        help="enforcement_coding_sheet.csv (for comment counts)",
    )
    ap.add_argument("--out", default="out/enforcement_result")
    a = ap.parse_args()
    names = a.names or [Path(p).stem for p in a.coders]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    frames = {
        n: read_sheet(p).fillna("").set_index("case_id")
        for n, p in zip(names, a.coders)
    }
    ids = sorted(set.intersection(*[set(f.index) for f in frames.values()]))
    vals = pd.DataFrame(
        {n: f.loc[ids, "reviewer_objected"].map(norm) for n, f in frames.items()}
    )
    bad = vals[~vals.isin(["yes", "no"]).all(axis=1)]
    if len(bad):
        raise SystemExit(
            f"non yes/no values in reviewer_objected for: {list(bad.index)[:10]}"
        )
    agree = vals.nunique(axis=1) == 1
    agreed = vals[names[0]].where(agree)
    if (~agree).any():
        if not a.resolutions:
            raise SystemExit(
                f"{int((~agree).sum())} disagreement(s); pass --resolutions"
            )
        res = read_sheet(a.resolutions).fillna("")
        idcol = "case_id" if "case_id" in res.columns else res.columns[0]
        rmap = dict(zip(res[idcol].astype(str), res["resolution"].map(norm)))
        for cid in vals.index[~agree]:
            r = rmap.get(str(cid), "")
            if r not in ("yes", "no"):
                raise SystemExit(
                    f"case {cid}: coders disagree and resolution is "
                    f"'{r}' — resolve it first"
                )
            agreed[cid] = r
    raw_agreement = round(float(agree.mean()), 4)

    key = pd.read_csv(a.key).set_index("case_id")
    sheet = pd.read_csv(a.sheet).set_index("case_id")
    df = (
        pd.DataFrame({"objected": agreed})
        .join(key[["group"]])
        .join(sheet[["n_reviewer_comments", "n_keyword_comments"]])
    )
    df["objected"] = df.objected == "yes"

    tab = pd.crosstab(df.group, df.objected).reindex(
        index=["malformed", "wellformed"], columns=[True, False], fill_value=0
    )
    a_, b_ = int(tab.loc["malformed", True]), int(tab.loc["malformed", False])
    c_, d_ = int(tab.loc["wellformed", True]), int(tab.loc["wellformed", False])
    odds, p = fisher_exact([[a_, b_], [c_, d_]], alternative="two-sided")
    rows = []
    for g, k, n in (("malformed", a_, a_ + b_), ("wellformed", c_, c_ + d_)):
        lo, hi = wilson(k, n)
        sub = df[df.group == g]
        rows.append(
            {
                "group": g,
                "prs": n,
                "objected": k,
                "rate": round(k / n, 4) if n else float("nan"),
                "ci95_low": lo,
                "ci95_high": hi,
                "median_reviewer_comments": float(sub.n_reviewer_comments.median()),
                "prs_with_no_reviewer_comment": int(
                    (sub.n_reviewer_comments == 0).sum()
                ),
            }
        )
    R = pd.DataFrame(rows)
    R.to_csv(out / "enforcement_rates.csv", index=False)

    det = []
    for cid in df.index[df.objected]:
        rec = {
            "case_id": cid,
            "group": df.loc[cid, "group"],
            "url": sheet.loc[cid].get("url", ""),
        }
        for n, f in frames.items():
            rec[f"{n}_objection_type"] = f.loc[cid].get("objection_type", "")
            rec[f"{n}_note"] = f.loc[cid].get("note", "")
        det.append(rec)
    pd.DataFrame(det).to_csv(out / "enforcement_objections_detail.csv", index=False)

    summ = {
        "cases": len(df),
        "coders": names,
        "raw_agreement_before_reconciliation": raw_agreement,
        "table": {
            "malformed": {"objected": a_, "not": b_},
            "wellformed": {"objected": c_, "not": d_},
        },
        "fisher_exact_two_sided": {
            "odds_ratio": None if math.isinf(odds) else round(float(odds), 3),
            "p_value": round(float(p), 4),
        },
        "rates": rows,
        "caveats": [
            "survivorship: successful objections move PRs into the well-formed group",
            "groups not randomised; descriptive",
        ],
    }
    (out / "enforcement_summary.json").write_text(json.dumps(summ, indent=2))
    print(
        f"cases: {len(df)}; coder agreement before reconciliation: {raw_agreement:.1%}"
    )
    print(R.to_string(index=False))
    print(
        f"Fisher's exact (two-sided): odds ratio "
        f"{summ['fisher_exact_two_sided']['odds_ratio']}, p = {p:.4f}"
    )
    print(f"details of objections -> {out}/enforcement_objections_detail.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
