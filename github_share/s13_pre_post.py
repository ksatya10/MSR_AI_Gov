#!/usr/bin/env python3
# Weekly disclosure before and after adoption on the event-week grid of the earlier study.

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--event-week", default="2026-03-02",
                    help="Monday of the adoption week (adoption 2026-03-06 -> 2026-03-02)")
    ap.add_argument("--last-week", type=int, default=30,
                    help="last event week included (30 = week of 2026-09-28)")
    a = ap.parse_args()
    out = Path(a.out)
    ev = pd.Timestamp(a.event_week)
    if ev.dayofweek != 0:
        raise SystemExit("--event-week must be a Monday")

    c = pd.read_csv(out / "commits_classified.csv.gz",
                    usecols=["sha", "author_email", "week_start_utc", "t_assisted_by", "pkg_rule"])
    c["wk"] = pd.to_datetime(c.week_start_utc.astype(str).str[:10])
    c["ew"] = (c.wk - ev).dt.days // 7
    c = c[(c.ew >= -12) & (c.ew <= a.last_week)]
    c["t"] = c.t_assisted_by.astype(bool)
    w = c.groupby("ew").agg(commits=("sha", "size"), commit_authors=("author_email", "nunique"),
                            assisted_by_commits=("t", "sum"), pkg_rule_commits=("pkg_rule", "sum"))
    w["authors_disclosing"] = c[c.t].groupby("ew").author_email.nunique()
    w = w.fillna(0)
    w["assisted_by_share"] = (w.assisted_by_commits / w.commits).round(4)

    have_pr = (out / "pr_level.csv.gz").exists()
    if have_pr:
        p = pd.read_csv(out / "pr_level.csv.gz")
        p = p[~p.is_bot.astype(bool)]
        p["ew"] = (pd.to_datetime(p.week_start_utc) - ev).dt.days // 7
        g = p.groupby("ew").agg(prs_opened=("number", "size"),
                                paper_rule_prs=("paper_rule", "sum"))
        g["paper_rule_share"] = (g.paper_rule_prs / g.prs_opened).round(4)
        m = p[p.commits_fetched.astype(bool)].copy()
        m["mw"] = (pd.to_datetime(m.merged_at, utc=True).dt.tz_localize(None)
                   .dt.to_period("W-SUN").dt.start_time - ev).dt.days // 7
        g2 = m.groupby("mw").agg(merged_prs_checked=("number", "size"),
                                 merged_prs_with_trailer=("trailer_any", "sum"))
        g2.index.name = "ew"
        w = w.join(g, how="left").join(g2, how="left")
    w.index.name = "event_week"
    w["week_start"] = [(ev + pd.Timedelta(weeks=int(i))).strftime("%Y-%m-%d") for i in w.index]
    w.to_csv(out / "prepost_weekly.csv")

    wins = {"pre 8 (-8..-1)": (-8, -1), "post 8 (0..7) = paper's main window": (0, 7),
            "pre 4 (-4..-1)": (-4, -1), "post 4 (0..3)": (0, 3),
            "post 12 (0..11)": (0, 11),
            f"later (8..{a.last_week})": (8, a.last_week)}
    rows = []
    for name, (lo, hi) in wins.items():
        s = w.loc[lo:hi]
        r = {"window": name, "weeks": len(s),
             "commits_per_week": round(s.commits.mean(), 1),
             "commit_authors_per_week": round(s.commit_authors.mean(), 1),
             "assisted_by_share_pooled": round(s.assisted_by_commits.sum() / s.commits.sum(), 4),
             "authors_disclosing_per_week": round(s.authors_disclosing.mean(), 1),
             "pkg_rule_commits_per_week": round(s.pkg_rule_commits.mean(), 2)}
        if have_pr and "prs_opened" in s:
            r["prs_opened_per_week"] = round(s.prs_opened.mean(), 1)
            r["paper_ai_disclosure_pr_share_pooled"] = (
                round(s.paper_rule_prs.sum() / s.prs_opened.sum(), 4) if s.prs_opened.sum() else None)
            if lo >= 0 and s.merged_prs_checked.sum():
                r["merged_prs_with_trailer_share"] = round(
                    s.merged_prs_with_trailer.sum() / s.merged_prs_checked.sum(), 4)
        rows.append(r)
    W = pd.DataFrame(rows)
    W.to_csv(out / "prepost_windows.csv", index=False)

    md = ["# Zephyr before and after adoption (paper's week grid)", "",
          f"Event week 0 = {a.event_week} (adoption 2026-03-06). Weekly means for counts, "
          "pooled shares for shares. One repository, no comparison group: descriptive only.", "",
          "| " + " | ".join(W.columns) + " |", "|" + "---|" * len(W.columns)]
    for _, r in W.iterrows():
        md.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r.values) + " |")
    md += ["", "Commit counts dip in some weeks after adoption (see prepost_weekly.csv); "
           "check Zephyr's release calendar before reading anything into activity changes."]
    if not have_pr:
        md += ["", "PR measures absent: run s9_pr_level.py first, then re-run this script."]
    (out / "prepost_summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
