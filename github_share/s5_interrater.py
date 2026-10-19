#!/usr/bin/env python3
# Agreement between two coders on the TRACE labels (kappa, weighted kappa, alpha).

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

DIMS = ["T", "R", "A", "C", "E"]
LONG = {"T": "transparency", "R": "responsibility", "A": "attribution",
        "C": "constraints", "E": "enforcement"}
ORDINAL = {"T": True, "R": False, "A": True, "C": True, "E": True}


def read_sheet(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        xl = pd.ExcelFile(p)
        sheet = "coding" if "coding" in xl.sheet_names else xl.sheet_names[0]
        return xl.parse(sheet, dtype=str)
    return pd.read_csv(p, dtype=str)


def level_digit(v) -> float:
    if pd.isna(v):
        return np.nan
    s = str(v).strip()
    m = re.search(r"([1-4])", s)
    return float(m.group(1)) if m else np.nan


def pick_column(df: pd.DataFrame, dim: str) -> str | None:
    for cand in (dim, dim.lower(), LONG[dim], LONG[dim].capitalize()):
        if cand in df.columns:
            return cand
    return None


def krippendorff_alpha_ordinal(a: np.ndarray, b: np.ndarray) -> float:
    vals = np.concatenate([a, b])
    cats = np.sort(np.unique(vals))
    counts = {c: int((vals == c).sum()) for c in cats}
    n_total = len(vals)

    def ordinal_delta(c1, c2) -> float:
        lo, hi = (c1, c2) if c1 <= c2 else (c2, c1)
        between = [c for c in cats if lo <= c <= hi]
        s = sum(counts[c] for c in between) - (counts[lo] + counts[hi]) / 2.0
        return s ** 2

    do = np.mean([ordinal_delta(x, y) for x, y in zip(a, b)])
    num = den = 0.0
    for c1 in cats:
        for c2 in cats:
            pairs = (counts[c1] * (counts[c2] - 1) if c1 == c2
                     else counts[c1] * counts[c2])
            num += pairs * ordinal_delta(c1, c2)
            den += pairs
    de = num / den if den else 0.0
    return 1.0 - do / de if de else float("nan")


def kappa_band(k: float) -> str:
    if k < 0: return "poor"
    if k <= 0.20: return "slight"
    if k <= 0.40: return "fair"
    if k <= 0.60: return "moderate"
    if k <= 0.80: return "substantial"
    return "almost perfect"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="coder A labels (.csv or .xlsx)")
    ap.add_argument("--b", required=True, help="coder B labels (.csv or .xlsx)")
    ap.add_argument("--id", default="sample_id")
    ap.add_argument("--out", default="out")
    ap.add_argument("--compare", default=None,
                    help="an existing irr_results.csv to validate against")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    A, B = read_sheet(args.a), read_sheet(args.b)
    for f in (A, B):
        f[args.id] = f[args.id].astype(str).str.strip()
    if args.id not in A.columns or args.id not in B.columns:
        raise SystemExit(f"id column '{args.id}' missing from one of the inputs")
    merged = A.merge(B, on=args.id, suffixes=("_a", "_b"))
    print(f"items coded by both: {len(merged)} "
          f"(A={len(A)}, B={len(B)})")

    rows, disagreements = [], []
    for d in DIMS:
        ca, cb = pick_column(A, d), pick_column(B, d)
        if ca is None or cb is None:
            print(f"  ! dimension {d}: column not found (A={ca}, B={cb}); skipped")
            continue
        ka = f"{ca}_a" if f"{ca}_a" in merged.columns else ca
        kb = f"{cb}_b" if f"{cb}_b" in merged.columns else cb
        x = merged[ka].map(level_digit)
        y = merged[kb].map(level_digit)
        ok = x.notna() & y.notna()
        xa, yb = x[ok].to_numpy(), y[ok].to_numpy()
        if len(xa) == 0:
            continue
        agree = float((xa == yb).mean())
        k = float(cohen_kappa_score(xa, yb))
        rec = {
            "dim": LONG[d], "letter": d, "n": int(len(xa)),
            "agreement": round(agree, 4),
            "kappa": round(k, 4), "kappa_band": kappa_band(k),
            "treated_as": "ordinal" if ORDINAL[d] else "nominal",
        }
        if ORDINAL[d]:
            rec["wkappa_linear"] = round(float(cohen_kappa_score(
                xa, yb, weights="linear")), 4)
            rec["wkappa_quadratic"] = round(float(cohen_kappa_score(
                xa, yb, weights="quadratic")), 4)
            rec["alpha_ordinal"] = round(krippendorff_alpha_ordinal(xa, yb), 4)
            rec["measure_recommended"] = "wkappa_linear / alpha_ordinal"
        else:
            rec["wkappa_linear"] = None
            rec["wkappa_quadratic"] = None
            rec["alpha_ordinal"] = None
            rec["measure_recommended"] = "kappa (nominal)"
        rows.append(rec)

        for i, (xi, yi) in enumerate(zip(x, y)):
            if pd.notna(xi) and pd.notna(yi) and xi != yi:
                disagreements.append({
                    args.id: merged.iloc[i][args.id], "dimension": d,
                    "coder_a": merged.iloc[i][ka], "coder_b": merged.iloc[i][kb],
                    "distance": int(abs(xi - yi)), "resolution": "",
                })

    res = pd.DataFrame(rows)
    res.to_csv(out / "irr_results.csv", index=False)
    dis = pd.DataFrame(disagreements)
    if not dis.empty:
        dis.sort_values(["dimension", args.id]).to_csv(
            out / "irr_disagreements.csv", index=False)

    macro_k = round(float(res.kappa.mean()), 4) if not res.empty else None
    L = ["# Inter-rater reliability", "",
         f"Items coded by both coders: {int(res.n.max()) if not res.empty else 0}",
         "", "| Dimension | Treated as | Agreement | kappa | w-kappa (linear) "
         "| alpha (ordinal) | Band |", "|---|---|---:|---:|---:|---:|---|"]
    for _, r in res.iterrows():
        L.append(f"| {r.dim.capitalize()} ({r.letter}) | {r.treated_as} | "
                 f"{r.agreement:.3f} | {r.kappa:.3f} | "
                 f"{'' if r.wkappa_linear is None else f'{r.wkappa_linear:.3f}'} | "
                 f"{'' if r.alpha_ordinal is None else f'{r.alpha_ordinal:.3f}'} | "
                 f"{r.kappa_band} |")
    L += ["", f"Macro-mean unweighted kappa: **{macro_k}**",
          "", "Bands follow Landis & Koch (1977). R is treated as nominal "
          "because the codebook defines R2/R3/R4 as categorical types of "
          "responsibility rather than an ordered scale.", ""]
    if not dis.empty:
        L += [f"Disagreements: {len(dis)} cell(s) across "
              f"{dis[args.id].nunique()} item(s); "
              f"{int((dis.distance > 1).sum())} differ by more than one level. "
              f"See irr_disagreements.csv — fill the `resolution` column during "
              f"reconciliation.", ""]
    (out / "irr_summary.md").write_text("\n".join(L), encoding="utf-8")
    print("\n" + "\n".join(L))

    if args.compare:
        pub = pd.read_csv(args.compare)
        print("\n=== validation against published numbers ===")
        for _, r in res.iterrows():
            p = pub[pub.letter == r.letter]
            if p.empty:
                continue
            p = p.iloc[0]
            def cmp(name, mine, theirs):
                if pd.isna(theirs) or theirs is None or mine is None:
                    return ""
                return f"{name}: mine={mine:.4f} published={float(theirs):.4f} " \
                       f"{'OK' if abs(mine-float(theirs))<5e-3 else 'DIFFERS'}"
            parts = [cmp("agreement", r.agreement, p.get("agreement")),
                     cmp("kappa", r.kappa, p.get("kappa"))]
            if r.wkappa_linear is not None:
                parts.append(cmp("wkappa_linear", r.wkappa_linear,
                                 p.get("wkappa_linear")))
            if r.alpha_ordinal is not None:
                parts.append(cmp("alpha", r.alpha_ordinal, p.get("alpha")))
            print(f"  {r.letter}: " + " | ".join(x for x in parts if x))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
