#!/usr/bin/env python3
# Agreement among two or more coders (Krippendorff's alpha with bootstrap CI, Fleiss' kappa).

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from pipeline123.MSR_AI_Gov.github_share.s5_interrater import (
    DIMS,
    LONG,
    ORDINAL,
    kappa_band,
    level_digit,
    pick_column,
    read_sheet,
)


def krippendorff_alpha(matrix: np.ndarray, ordinal: bool) -> float:
    cats = np.sort(np.unique(matrix[~np.isnan(matrix)]))
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    o = np.zeros((k, k))
    for row in matrix:
        vals = row[~np.isnan(row)]
        m = len(vals)
        if m < 2:
            continue
        for a, b in itertools.permutations(range(m), 2):
            o[idx[vals[a]], idx[vals[b]]] += 1.0 / (m - 1)
    n_c = o.sum(axis=1)
    n = n_c.sum()
    if n <= 1 or k < 2:
        return float("nan")
    d = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            if i == j:
                continue
            if ordinal:
                lo, hi = min(i, j), max(i, j)
                d[i, j] = (n_c[lo : hi + 1].sum() - (n_c[lo] + n_c[hi]) / 2.0) ** 2
            else:
                d[i, j] = 1.0
    do = (o * d).sum() / n
    de = (np.outer(n_c, n_c) * d).sum() / (n * (n - 1))
    return float(1.0 - do / de) if de else float("nan")


def bootstrap_alpha(
    M: np.ndarray, ordinal: bool, reps: int, seed: int
) -> tuple[float, float, int]:
    rng = np.random.default_rng(seed)
    vals, skipped = [], 0
    for _ in range(reps):
        a = krippendorff_alpha(M[rng.integers(0, len(M), len(M))], ordinal)
        if a == a:
            vals.append(a)
        else:
            skipped += 1
    if not vals:
        return float("nan"), float("nan"), skipped
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi), skipped


def fleiss_kappa(matrix: np.ndarray) -> float:
    full = matrix[~np.isnan(matrix).any(axis=1)]
    if len(full) == 0:
        return float("nan")
    cats = np.sort(np.unique(full))
    counts = np.array([[(row == c).sum() for c in cats] for row in full], float)
    n_items, m = counts.shape[0], full.shape[1]
    p_j = counts.sum(axis=0) / (n_items * m)
    p_i = ((counts**2).sum(axis=1) - m) / (m * (m - 1))
    pe = (p_j**2).sum()
    return float((p_i.mean() - pe) / (1 - pe)) if pe < 1 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coders", nargs="+", required=True)
    ap.add_argument("--names", nargs="*", default=None)
    ap.add_argument("--id", default="sample_id")
    ap.add_argument("--out", default="out")
    ap.add_argument(
        "--boot",
        type=int,
        default=2000,
        help="bootstrap draws for the alpha interval (0 = off)",
    )
    ap.add_argument("--seed", type=int, default=20261008)
    args = ap.parse_args()
    if len(args.coders) < 2:
        raise SystemExit("need at least two coder files")
    names = args.names or [Path(p).stem for p in args.coders]
    if len(names) != len(args.coders):
        raise SystemExit("--names must match --coders in length")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    frames = [read_sheet(p) for p in args.coders]
    for f in frames:
        f[args.id] = f[args.id].astype(str).str.strip()
    ids = sorted(set.intersection(*[set(f[args.id]) for f in frames]))
    print(f"coders: {names}; items coded by all: {len(ids)}")

    res, pairs, dis = [], [], []
    for d in DIMS:
        cols = []
        for f in frames:
            c = pick_column(f, d)
            if c is None:
                raise SystemExit(f"dimension {d} not found in a coder file")
            cols.append(f.set_index(args.id).loc[ids, c].map(level_digit).to_numpy())
        M = np.column_stack(cols)
        full = M[~np.isnan(M).any(axis=1)]
        all_agree = (
            float((full == full[:, [0]]).all(axis=1).mean())
            if len(full)
            else float("nan")
        )
        pw_agree = []
        for i, j in itertools.combinations(range(len(names)), 2):
            ok = ~np.isnan(M[:, i]) & ~np.isnan(M[:, j])
            a, b = M[ok, i], M[ok, j]
            agree = float((a == b).mean())
            pw_agree.append(agree)
            pairs.append(
                {
                    "letter": d,
                    "coder_1": names[i],
                    "coder_2": names[j],
                    "n": int(ok.sum()),
                    "agreement": round(agree, 4),
                    "kappa": round(float(cohen_kappa_score(a, b)), 4),
                    "wkappa_linear": (
                        round(float(cohen_kappa_score(a, b, weights="linear")), 4)
                        if ORDINAL[d]
                        else None
                    ),
                }
            )
        alpha = krippendorff_alpha(M, ORDINAL[d])
        lo, hi, skipped = (
            bootstrap_alpha(M, ORDINAL[d], args.boot, args.seed)
            if args.boot
            else (float("nan"), float("nan"), 0)
        )
        fk = fleiss_kappa(M)
        blanks = int(np.isnan(M).sum())
        res.append(
            {
                "dim": LONG[d],
                "letter": d,
                "n_items": len(ids),
                "n_coders": len(names),
                "treated_as": "ordinal" if ORDINAL[d] else "nominal",
                "all_coders_agree": round(all_agree, 4),
                "mean_pairwise_agreement": round(float(np.mean(pw_agree)), 4),
                "krippendorff_alpha": round(alpha, 4),
                "alpha_ci95_low": round(lo, 4),
                "alpha_ci95_high": round(hi, 4),
                "boot_draws_undefined": skipped,
                "alpha_band": kappa_band(alpha) if alpha == alpha else "",
                "blank_cells": blanks,
                "fleiss_kappa_nominal": round(fk, 4),
            }
        )
        for r, item in enumerate(ids):
            row = M[r]
            if len(set(row[~np.isnan(row)])) > 1:
                rec = {
                    args.id: item,
                    "dimension": d,
                    "spread": int(np.nanmax(row) - np.nanmin(row)),
                    "resolution": "",
                    "resolution_reason": "",
                }
                rec.update({n: (int(v) if v == v else "") for n, v in zip(names, row)})
                dis.append(rec)

    R = pd.DataFrame(res)
    R.to_csv(out / "irr_multi_results.csv", index=False)
    pd.DataFrame(pairs).to_csv(out / "irr_multi_pairwise.csv", index=False)
    if dis:
        pd.DataFrame(dis).to_csv(out / "irr_multi_disagreements.csv", index=False)

    L = [
        "# Inter-rater reliability (multi-coder)",
        "",
        f"Coders: {', '.join(names)} — items coded by all: {len(ids)}",
        "",
        "| Dimension | Treated as | All agree | Mean pairwise | Krippendorff alpha | 95% CI | Fleiss kappa |",
        "|---|---|---:|---:|---:|---|---:|",
    ]
    for _, r in R.iterrows():
        L.append(
            f"| {r.dim.capitalize()} ({r.letter}) | {r.treated_as} | "
            f"{r.all_coders_agree:.3f} | {r.mean_pairwise_agreement:.3f} | "
            f"{r.krippendorff_alpha:.3f} | "
            f"[{r.alpha_ci95_low:.3f}, {r.alpha_ci95_high:.3f}] | "
            f"{r.fleiss_kappa_nominal:.3f} |"
        )
    if int(R.blank_cells.sum()):
        L += [
            "",
            f"Blank cells (treated as missing): {int(R.blank_cells.sum())} "
            "— check that no coder skipped a row by accident.",
        ]
    L += [
        "",
        "Alpha uses the ordinal metric for T, A, C, E and the nominal "
        "metric for R. Fleiss' kappa is nominal for every dimension and is "
        "reported for reference. 95% CI: bootstrap over items "
        f"({args.boot} draws, seed {args.seed}).",
        "",
        f"Cells with disagreement: {len(dis)} (see irr_multi_disagreements.csv; "
        f"fill `resolution` and `resolution_reason` at reconciliation).",
        "",
    ]
    (out / "irr_multi_summary.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
