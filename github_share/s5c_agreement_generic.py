#!/usr/bin/env python3
# Agreement on a single categorical column coded by two or more coders.

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from pipeline123.MSR_AI_Gov.github_share.s5b_interrater_multi import (
    fleiss_kappa,
    krippendorff_alpha,
    read_sheet,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coders", nargs="+", required=True)
    ap.add_argument("--names", nargs="*", default=None)
    ap.add_argument("--id", required=True)
    ap.add_argument("--column", required=True)
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    names = a.names or [Path(p).stem for p in a.coders]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    cols = []
    for p in a.coders:
        f = read_sheet(p)
        f[a.id] = f[a.id].astype(str).str.strip()
        f = f.set_index(a.id)
        cols.append(f[a.column].fillna("").str.strip().str.lower())
    ids = sorted(set.intersection(*[set(c.index) for c in cols]))
    T = pd.DataFrame({n: c.loc[ids] for n, c in zip(names, cols)})
    blank = (T == "").any(axis=1)
    if blank.any():
        print(f"  ! {int(blank.sum())} item(s) left blank by a coder — excluded")
    T = T[~blank]
    cats = sorted(set(T.values.ravel()))
    code = {c: float(i) for i, c in enumerate(cats)}
    M = T.replace(code).to_numpy(dtype=float)

    print(f"items: {len(T)}; coders: {names}; categories: {cats}")
    print(f"all coders agree: {(T.nunique(axis=1) == 1).mean():.3f}")
    rows = []
    for i, j in itertools.combinations(range(len(names)), 2):
        k = cohen_kappa_score(M[:, i], M[:, j]) if len(cats) > 1 else float("nan")
        agree = float((M[:, i] == M[:, j]).mean())
        rows.append(
            {
                "coder_1": names[i],
                "coder_2": names[j],
                "agreement": round(agree, 4),
                "kappa": round(float(k), 4),
            }
        )
        print(f"  {names[i]} vs {names[j]}: agreement {agree:.3f}, kappa {k:.3f}")
    alpha = krippendorff_alpha(M, ordinal=False)
    fk = fleiss_kappa(M)
    print(f"Krippendorff alpha (nominal): {alpha:.3f}   Fleiss kappa: {fk:.3f}")
    if len(cats) < 2:
        print(
            "  note: every coder used a single category; kappa/alpha are "
            "undefined when there is no variation — report raw agreement."
        )
    pd.DataFrame(rows).to_csv(out / "agreement_pairwise.csv", index=False)
    pd.DataFrame(
        [
            {
                "column": a.column,
                "n_items": len(T),
                "n_coders": len(names),
                "all_agree": round(float((T.nunique(axis=1) == 1).mean()), 4),
                "krippendorff_alpha_nominal": round(alpha, 4),
                "fleiss_kappa": round(fk, 4),
            }
        ]
    ).to_csv(out / "agreement_summary.csv", index=False)
    D = T[T.nunique(axis=1) > 1].copy()
    D["resolution"] = ""
    D["resolution_reason"] = ""
    D.to_csv(out / "agreement_disagreements.csv")
    print(f"disagreements: {len(D)} -> {out}/agreement_disagreements.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
