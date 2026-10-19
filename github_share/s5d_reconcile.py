#!/usr/bin/env python3
# Checks and freezes returned coding sheets, builds the reconciliation sheet, writes agreed labels.

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import stat
from pathlib import Path

import pandas as pd

from pipeline123.MSR_AI_Gov.github_share.make_coder_sheets import (
    CONFIDENCE,
    DIMS,
    LEVELS,
    SCOPE,
    write_workbook,
)
from pipeline123.MSR_AI_Gov.github_share.s5_interrater import read_sheet

VALID = {d: set(LEVELS[d]) for d in DIMS}


def norm(v) -> str:
    return "" if pd.isna(v) else str(v).strip()


def short(label: str) -> str:
    m = re.match(r"([TRACE][1-4])", label)
    return m.group(1) if m else label


def check(a) -> int:
    master = pd.read_csv(a.master, dtype=str).fillna("")
    master_ids = list(master.sample_id)
    texts = dict(zip(master.sample_id, master.policy_text))
    dest = Path(a.out) / a.round
    dest.mkdir(parents=True, exist_ok=True)
    ok_all = True
    manifest = []
    for path in a.coders:
        p = Path(path)
        f = read_sheet(p).fillna("")
        problems = []
        ids = [norm(x) for x in f.get("sample_id", [])]
        if sorted(ids) != sorted(master_ids):
            problems.append(
                f"ids differ from master: missing "
                f"{sorted(set(master_ids) - set(ids))}, extra "
                f"{sorted(set(ids) - set(master_ids))}"
            )
        if len(ids) != len(set(ids)):
            problems.append("duplicate sample_id rows")
        for _, r in f.iterrows():
            sid = norm(r.get("sample_id"))
            if (
                sid in texts
                and "policy_text" in f.columns
                and norm(r["policy_text"]) != texts[sid].strip()
            ):
                problems.append(f"{sid}: policy_text was edited")
            out_scope = False
            if a.round == "subject":
                sc = norm(r.get("scope", ""))
                if sc not in SCOPE:
                    problems.append(f"{sid}: scope '{sc}' not one of {SCOPE}")
                out_scope = sc == "out_of_scope"
            for d in DIMS:
                v = norm(r.get(d, ""))
                if out_scope:
                    if v:
                        problems.append(
                            f"{sid}: {d} filled although unit is out_of_scope"
                        )
                    continue
                if not v:
                    problems.append(f"{sid}: {d} is blank")
                elif v not in VALID[d]:
                    problems.append(f"{sid}: {d} '{v}' is not a codebook label")
                if a.round == "subject" and not norm(r.get(f"{d}_evidence", "")):
                    problems.append(
                        f"{sid}: {d}_evidence is blank (write 'none' for level 1)"
                    )
            c = norm(r.get("confidence", ""))
            if c and c not in CONFIDENCE:
                problems.append(f"{sid}: confidence '{c}' not one of {CONFIDENCE}")
        if problems:
            ok_all = False
            print(
                f"\n✗ {p.name}: {len(problems)} problem(s) — send back to the coder "
                "to fix ONLY these cells:"
            )
            for x in problems:
                print("   -", x)
            continue
        target = dest / p.name
        if target.exists():
            target.chmod(stat.S_IWUSR | stat.S_IRUSR)
        shutil.copy2(p, target)
        target.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        h = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest.append({"file": p.name, "sha256": h, "rows": len(f)})
        print(f"✓ {p.name}: {len(f)} rows valid -> frozen as {target}")
    if manifest:
        mf = dest / "MANIFEST.csv"
        old = pd.read_csv(mf) if mf.exists() else pd.DataFrame()
        new = pd.concat([old, pd.DataFrame(manifest)]).drop_duplicates(
            "file", keep="last"
        )
        new.to_csv(mf, index=False)
        print(f"hashes -> {mf}")
    if not ok_all:
        print("\nFix the files marked ✗, then run check again on those files only.")
        return 1
    return 0


def sheet(a) -> int:
    names = a.names or [Path(p).stem for p in a.coders]
    if len(names) != len(a.coders):
        raise SystemExit("--names must match --coders")
    blind = a.blind or names
    missing = [b for b in blind if b not in names]
    if missing:
        raise SystemExit(f"--blind names not in --names: {missing}")
    frames = {
        n: read_sheet(p).fillna("").set_index("sample_id")
        for n, p in zip(names, a.coders)
    }
    ids = sorted(set.intersection(*[set(f.index) for f in frames.values()]))
    fields = (["scope"] if a.round == "subject" else []) + DIMS
    rows, agree_rows = [], []
    for sid in ids:
        for d in fields:
            rec = {"sample_id": sid, "dimension": d}
            vals = {}
            for n, f in frames.items():
                v = norm(f.loc[sid].get(d, ""))
                vals[n] = v
                rec[n] = v
                ev = norm(f.loc[sid].get(f"{d}_evidence", "")) if d != "scope" else ""
                if a.round == "subject" and d != "scope":
                    rec[f"{n}_evidence"] = ev
                rec[f"{n}_notes"] = norm(f.loc[sid].get("notes", ""))
            bv = [vals[n] for n in blind]
            agree = len(set(bv)) == 1
            rec["blind_agree"] = "yes" if agree else "no"
            rec["agreed"] = bv[0] if agree else ""
            rec["reason"] = ""
            rows.append(rec)
            agree_rows.append(
                {
                    "sample_id": sid,
                    "dimension": d,
                    "agree": agree,
                    "spread": (
                        max(int(short(x)[1]) for x in bv if x)
                        - min(int(short(x)[1]) for x in bv if x)
                    )
                    if d != "scope" and all(bv)
                    else "",
                }
            )
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    cols = ["sample_id", "dimension"]
    for n in names:
        cols += [c for c in (n, f"{n}_evidence", f"{n}_notes") if c in df.columns]
    df = df[cols + ["blind_agree", "agreed", "reason"]].fillna("")
    df = df.sort_values(["blind_agree", "sample_id", "dimension"]).reset_index(
        drop=True
    )
    cols = list(df.columns)
    lists: dict[str, list[str]] = {}
    path = out / f"reconcile_{a.round}.xlsx"
    write_workbook(path, df.to_dict("records"), cols, lists, f"reconcile {a.round}")
    df.to_csv(out / f"reconcile_{a.round}.csv", index=False)
    A = pd.DataFrame(agree_rows)
    summ = A.groupby("dimension", sort=False).agree.agg(["sum", "count"])
    summ["raw_agreement"] = (summ["sum"] / summ["count"]).round(3)
    summ.columns = ["cells_agree", "cells", "raw_agreement"]
    tot = A.agree.sum(), len(A)
    summ.loc["ALL"] = [int(tot[0]), int(tot[1]), round(tot[0] / tot[1], 3)]
    summ[["cells_agree", "cells"]] = summ[["cells_agree", "cells"]].astype(int)
    summ.to_csv(out / f"cell_agreement_{a.round}.csv")
    print(f"blind coders: {', '.join(blind)}; items: {len(ids)}")
    print(summ.to_string())
    n_dis = int((df.blind_agree == "no").sum())
    print(f"\n{n_dis} row(s) to discuss -> {path}")
    print(
        "Fill `agreed` (a full codebook label, or a scope value) and `reason` "
        "(which codebook rule decided it) for every row marked blind_agree=no. "
        "Rows already agreed are pre-filled; change them only with a reason."
    )
    return 0


def finalize(a) -> int:
    df = read_sheet(a.sheet).fillna("")
    bad = []
    for i, r in df.iterrows():
        d, v = r["dimension"], norm(r["agreed"])
        allowed = SCOPE if d == "scope" else LEVELS[d]
        scope_out = d != "scope" and (
            (
                df[(df.sample_id == r.sample_id) & (df.dimension == "scope")].agreed
                == "out_of_scope"
            ).any()
        )
        if scope_out and v == "":
            continue
        if v not in allowed:
            bad.append(f"{r.sample_id} {d}: agreed '{v}' is not a valid value")
        if r["blind_agree"] == "no" and not norm(r["reason"]):
            bad.append(f"{r.sample_id} {d}: disagreement resolved without a reason")
    if bad:
        print("✗ reconciliation incomplete:")
        for x in bad:
            print("   -", x)
        return 1
    out = Path(a.out)
    wide = df.pivot(index="sample_id", columns="dimension", values="agreed")
    order = [c for c in ["scope", *DIMS] if c in wide.columns]
    wide = wide[order].reset_index()
    wide.to_csv(out / f"agreed_labels_{a.round}.csv", index=False)
    coder_cols = [
        c
        for c in df.columns
        if c not in ("sample_id", "dimension", "blind_agree", "agreed", "reason")
        and not c.endswith(("_evidence", "_notes"))
    ]
    log = df[df.blind_agree == "no"][
        ["sample_id", "dimension", *coder_cols, "agreed", "reason"]
    ]
    log.to_csv(out / f"reconciliation_log_{a.round}.csv", index=False)
    changed = {c: int((df[c] != df.agreed).sum()) for c in coder_cols}
    print(
        f"agreed labels -> {out}/agreed_labels_{a.round}.csv "
        f"({len(wide)} items); {len(log)} resolved disagreement(s) logged"
    )
    print("cells where the agreed label differs from each coder's own:", changed)
    if a.vector_unit:
        row = wide[wide.sample_id == a.vector_unit]
        if row.empty:
            raise SystemExit(f"unit {a.vector_unit} not found")
        vec = ",".join(short(row.iloc[0][d]) for d in DIMS)
        (out / f"agreed_vector_{a.vector_unit}.txt").write_text(vec + "\n")
        print(f"\nagreed vector for {a.vector_unit}: {vec}")
        print(
            f"next: python3 s3_benchmark_trace.py --package $PACKAGE "
            f"--subject zephyrproject-rtos/zephyr --vector {vec} "
            f"--match-dims T,A --out out/"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="step", required=True)
    c = sub.add_parser("check")
    c.add_argument(
        "--master", required=True, help="<round>_sheet.csv from make_coder_sheets"
    )
    c.add_argument("--coders", nargs="+", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("--coders", nargs="+", required=True)
    s.add_argument("--names", nargs="*")
    s.add_argument(
        "--blind", nargs="*", help="names whose agreement counts (default: all)"
    )
    f = sub.add_parser("finalize")
    f.add_argument("--sheet", required=True)
    f.add_argument(
        "--vector-unit",
        default=None,
        help="Round 2: unit whose vector goes to s3, e.g. U1",
    )
    for p in (c, s, f):
        p.add_argument(
            "--round", required=True, choices=["calibration", "calibration2", "subject"]
        )
        p.add_argument("--out", default="out/reconcile")
    a = ap.parse_args()
    return {"check": check, "sheet": sheet, "finalize": finalize}[a.step](a)


if __name__ == "__main__":
    raise SystemExit(main())
