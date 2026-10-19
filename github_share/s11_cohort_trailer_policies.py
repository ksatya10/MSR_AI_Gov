#!/usr/bin/env python3
# Finds cohort policies that mention a commit trailer key and summarizes the coded sheet.

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

KEYS = {"assisted-by": r"\bassisted-by\b", "co-authored-by": r"\bco-authored-by\b",
        "generated-by": r"\bgenerated-by\b"}
ANY = re.compile("|".join(f"({p})" for p in KEYS.values()), re.I)
PKG_RULE_SEES = {"co-authored-by": True, "assisted-by": False, "generated-by": False}


def excerpts(text: str, width: int = 250, limit: int = 4) -> str:
    out, last = [], -1
    for m in ANY.finditer(text):
        if m.start() < last:
            continue
        lo, hi = max(0, m.start() - width), min(len(text), m.end() + width)
        out.append(" ".join(text[lo:hi].split()))
        last = hi
        if len(out) >= limit:
            break
    return " ||| ".join(out)


def sheet(a) -> int:
    pol = Path(a.package) / "data/policy/policy_adoption.csv"
    d = pd.read_csv(pol)
    cols = [c for c in ("extracted_text", "raw_text", "resolved_external_policy_text") if c in d.columns]
    text = d[cols].fillna("").astype(str).agg("\n\n".join, axis=1)
    rows = []
    for i, t in text.items():
        found = sorted(k for k, p in KEYS.items() if re.search(p, t, re.I))
        if not found:
            continue
        r = d.loc[i]
        rows.append({"policy_unit_id": r.get("policy_unit_id", i), "repo_name": r.repo_name,
                     "policy_doc": r.get("policy_doc", ""), "T_level": r.get("T_level", ""),
                     "keys_mentioned": " ".join(found), "excerpts": excerpts(t),
                     "requires_trailer": "", "trailer_key": "", "note": ""})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    S = pd.DataFrame(rows)
    S.to_csv(out / "cohort_trailer_sheet.csv", index=False)
    counts = {k: int(S.keys_mentioned.str.contains(k).sum()) for k in KEYS}
    print(f"{len(S)} of {len(d)} cohort policies mention a trailer key -> "
          f"{out}/cohort_trailer_sheet.csv")
    print("mentions per key:", counts)
    print("NEXT: two coders fill requires_trailer / trailer_key / note; then "
          "s5c_agreement_generic.py --id policy_unit_id --column requires_trailer")
    return 0


def summary(a) -> int:
    c = pd.read_csv(a.coded, dtype=str).fillna("")
    c["requires_trailer"] = c.requires_trailer.str.strip().str.lower()
    bad = c[~c.requires_trailer.isin(["yes", "no"])]
    if len(bad):
        raise SystemExit(f"{len(bad)} row(s) without a yes/no requires_trailer")
    req = c[c.requires_trailer == "yes"].copy()
    req["trailer_key"] = req.trailer_key.str.strip().str.lower()
    by = req.trailer_key.value_counts().to_dict()
    invisible = int(sum(n for k, n in by.items() if not PKG_RULE_SEES.get(k, False)))
    res = {"policies_mentioning_a_trailer": len(c), "policies_requiring_a_trailer": len(req),
           "by_key": by, "requiring_a_key_the_package_rule_cannot_match": invisible,
           "cohort_size": 385,
           "note": "package rule matches `co-authored-by: <tool>` only; "
                   "assisted-by and generated-by have no pattern"}
    out = Path(a.out)
    (out / "cohort_trailer_summary.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("--package", required=True)
    m = sub.add_parser("summary")
    m.add_argument("--coded", required=True, help="reconciled sheet")
    for p in (s, m):
        p.add_argument("--out", default="out/cohort_trailers")
    a = ap.parse_args()
    return sheet(a) if a.mode == "sheet" else summary(a)


if __name__ == "__main__":
    raise SystemExit(main())
