#!/usr/bin/env python3
# Places a TRACE vector among the 385 coded policies of the replication package.

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

DIMS = ["T", "R", "A", "C", "E"]
DIM_NAME = {"T": "Transparency", "R": "Responsibility", "A": "Attribution",
            "C": "Constraints", "E": "Enforcement"}
ORDINAL = {"T": True, "R": False, "A": True, "C": True, "E": True}


def parse_vector(s: str) -> dict[str, int]:
    out = {}
    for tok in s.replace(" ", "").split(","):
        if not tok:
            continue
        d, lvl = tok[0].upper(), int(tok[1:])
        if d not in DIMS or not 1 <= lvl <= 4:
            raise SystemExit(f"bad vector token: {tok}")
        out[d] = lvl
    missing = [d for d in DIMS if d not in out]
    if missing:
        raise SystemExit(f"vector missing dimensions: {missing}")
    return out


def documented_family(lv: dict[str, int]) -> str:
    C, T, E = lv["C"], lv["T"], lv["E"]
    if C == 4:
        return "Strict_Prohibition"
    if C == 1:
        return "Permissive"
    if T >= 3 and E >= 3:
        return "Regulated_Controlled"
    if T < 3:
        return "Quiet_LowReq"
    return "Disclosed_SoftEnforced"


def observed_family(lv: dict[str, int]) -> str:
    C, T, E, R = lv["C"], lv["T"], lv["E"], lv["R"]
    if C == 4:
        return "Strict_Prohibition"
    if C == 1:
        return "Permissive_Accountable" if R >= 3 else "Permissive_HandsOff"
    return "Disclosed_Regulated" if T >= 3 else "Quiet_LowReq"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True, help="replication package root")
    ap.add_argument("--subject", required=True, help="owner/name of the case repo")
    ap.add_argument("--vector", required=True, help="e.g. T4,R4,A4,C3,E1")
    ap.add_argument("--match-dims", default="T,A",
                    help="dimensions a comparator must match (default T,A)")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    pkg = Path(args.package)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    z = parse_vector(args.vector)

    cohort = pd.read_csv(pkg / "data/policy/treatment_cohort.csv")
    adopt = pd.read_csv(pkg / "data/policy/policy_adoption.csv")[
        ["repo_name", "policy_doc", "file_kind", "adoption_datetime",
         "extracted_text"]]
    n = len(cohort)
    print(f"cohort: {n} coded policies from {pkg.name}")
    if args.subject in set(cohort.repo_name):
        print(f"  NOTE: {args.subject} IS in the cohort — this is a "
              f"replication check, not an out-of-sample case.")

    rows = []
    for d in DIMS:
        col = f"{d}_level"
        for lvl in (1, 2, 3, 4):
            k = int((cohort[col] == lvl).sum())
            rows.append({
                "dimension": d, "dimension_name": DIM_NAME[d], "level": lvl,
                "n_repos": k, "pct_of_cohort": round(100 * k / n, 2),
                "is_subject_level": lvl == z[d],
                "cum_pct_at_or_below": round(
                    100 * (cohort[col] <= lvl).sum() / n, 2) if ORDINAL[d] else None,
                "treat_as_ordinal": ORDINAL[d],
            })
    dist = pd.DataFrame(rows)
    dist.to_csv(out / "trace_benchmark_distribution.csv", index=False)

    match = [d.strip().upper() for d in args.match_dims.split(",") if d.strip()]
    mask = pd.Series(True, index=cohort.index)
    for d in match:
        mask &= cohort[f"{d}_level"] == z[d]
    comp = cohort[mask].merge(adopt, on="repo_name", how="left")
    comp["matches_subject_exactly"] = True
    for d in DIMS:
        comp["matches_subject_exactly"] &= comp[f"{d}_level"] == z[d]
    comp["has_policy_text"] = comp.extracted_text.notna()
    keep = (["repo_name", "policy_doc", "file_kind", "adoption_datetime"]
            + [f"{d}_level" for d in DIMS]
            + ["trace_vector", "family", "matches_subject_exactly",
               "has_policy_text"])
    comp[keep].sort_values([f"{d}_level" for d in DIMS]).to_csv(
        out / "comparator_repos.csv", index=False)
    (out / "comparator_texts").mkdir(exist_ok=True)
    for _, r in comp[comp.has_policy_text].iterrows():
        slug = r.repo_name.replace("/", "__")
        (out / "comparator_texts" / f"{slug}.txt").write_text(
            f"# {r.repo_name}  ({r.policy_doc})\n# {r.trace_vector}\n"
            f"# adopted {r.adoption_datetime}\n\n{r.extracted_text}",
            encoding="utf-8")

    aud = cohort[["repo_name"] + [f"{d}_level" for d in DIMS] + ["family"]].copy()
    aud["family_documented_rule"] = [
        documented_family({d: r[f"{d}_level"] for d in DIMS})
        for _, r in aud.iterrows()]
    aud["family_observed_rule"] = [
        observed_family({d: r[f"{d}_level"] for d in DIMS})
        for _, r in aud.iterrows()]
    aud["observed_rule_reproduces_label"] = aud.family_observed_rule == aud.family
    aud.to_csv(out / "family_rule_audit.csv", index=False)

    exact = int(comp.matches_subject_exactly.sum())
    summary = {
        "cohort_size": n,
        "subject": args.subject,
        "subject_vector": {d: z[d] for d in DIMS},
        "subject_family_observed_rule": observed_family(z),
        "subject_family_documented_rule": documented_family(z),
        "subject_in_cohort": args.subject in set(cohort.repo_name),
        "position": {
            d: {
                "level": z[d],
                "pct_of_cohort_at_this_level": float(
                    dist[(dist.dimension == d) & (dist.level == z[d])]
                    .pct_of_cohort.iloc[0]),
                "pct_of_cohort_above_this_level": round(
                    100 * (cohort[f"{d}_level"] > z[d]).sum() / n, 2),
            } for d in DIMS
        },
        "comparators": {
            "matched_on": match,
            "n": len(comp),
            "n_with_policy_text": int(comp.has_policy_text.sum()),
            "n_matching_all_five_dims": exact,
        },
        "family_rule_audit": {
            "observed_rule_reproduces_all_labels": bool(
                aud.observed_rule_reproduces_label.all()),
            "mismatches": int((~aud.observed_rule_reproduces_label).sum()),
            "note": ("data/prompts/README.md documents the family as a function "
                     "of T, C and E only; the shipped labels additionally split "
                     "C1 on R (R>=3 -> Permissive_Accountable)."),
        },
    }
    (out / "benchmark_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"\n{len(comp)} comparators ({exact} matching all five dimensions) "
          f"-> {out}/comparator_repos.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
