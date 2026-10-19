#!/usr/bin/env python3
# Draws the disclosure-over-time and concentration figures.

from __future__ import annotations

import argparse
import calendar
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.size": 8, "axes.edgecolor": MUTED, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": INK,
    "pdf.fonttype": 42, "ps.fonttype": 42,
})


def complete_months(months: list[str], last_commit: str) -> list[str]:
    y, m, d = (int(x) for x in last_commit.split("-"))
    if d < calendar.monthrange(y, m)[1]:
        return [x for x in months if x < f"{y:04d}-{m:02d}"]
    return months


def fig_over_time(out: Path, policy_date: str, first_month: str,
                  events: list[tuple[str, str]] | None = None) -> None:
    mon = pd.read_csv(out / "disclosure_monthly.csv", dtype={"month": str})
    con = pd.read_csv(out / "contributor_monthly.csv", dtype={"month": str})
    last = json.loads((out / "conformance_summary.json").read_text())["window"]["last_commit"]

    months = complete_months([m for m in mon.month if m >= first_month], last)
    mon = mon.set_index("month").reindex(months)
    con = con.set_index("month").reindex(months)
    pre = [m for m in months if m < policy_date[:7]]
    all_pct = mon.assisted_by_pct.astype(float)
    ex5 = (con.commit_share_excl_top5.astype(float) * 100)
    authors = (con.share_of_authors_disclosing.astype(float) * 100)
    for s in (ex5, authors):
        s.loc[pre] = 0.0
    x = list(range(len(months)))
    labels = [("" if i % 2 else
               pd.Period(m).strftime("%b\n%Y") if (i == 0 or m[5:] in ("01", "02"))
               else pd.Period(m).strftime("%b")) for i, m in enumerate(months)]
    px = months.index(policy_date[:7]) if policy_date[:7] in months else None

    fig, (a, b) = plt.subplots(2, 1, figsize=(3.5, 3.9), sharex=True,
                               gridspec_kw={"hspace": 0.28})
    a.plot(x, all_pct, color=BLUE, lw=1.6, marker="o", ms=3.5, label="All commits")
    a.plot(x, ex5, color=ORANGE, lw=1.6, marker="s", ms=3.2,
           label="Excl. top 5 authors")
    a.set_ylabel("% of commits")
    a.set_title("(a) Commits carrying Assisted-by:", loc="left", fontsize=8, color=INK)
    a.legend(frameon=False, fontsize=7, loc="center left", handlelength=1.6,
             borderaxespad=0.1, bbox_to_anchor=(0.0, 0.62))
    a.annotate(f"{all_pct.iloc[-1]:.0f}%", (x[-1], all_pct.iloc[-1]),
               xytext=(4, 0), textcoords="offset points", va="center",
               fontsize=7, color=INK)
    a.annotate(f"{ex5.iloc[-1]:.0f}%", (x[-1], ex5.iloc[-1]),
               xytext=(4, 0), textcoords="offset points", va="center",
               fontsize=7, color=INK)

    b.plot(x, authors, color=BLUE, lw=1.6, marker="o", ms=3.5)
    b.set_ylabel("% of active authors")
    b.set_title("(b) Authors disclosing at least once in the month", loc="left",
                fontsize=8, color=INK)
    b.annotate(f"{authors.iloc[-1]:.0f}%", (x[-1], authors.iloc[-1]),
               xytext=(4, 0), textcoords="offset points", va="center",
               fontsize=7, color=INK)

    top = max(all_pct.max(), ex5.max(), authors.max())
    for ax in (a, b):
        ax.set_ylim(0, top * 1.28)
        ax.set_xlim(-0.4, len(x) - 1 + 1.3)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        if px is not None:
            ax.axvline(px, color=MUTED, lw=0.8)
    if px is not None:
        b.annotate("policy adopted", (px, top * 1.28), xytext=(-3, -2),
                   textcoords="offset points", ha="right", va="top",
                   fontsize=7, color=MUTED)
    caption = []
    for k, (date, label) in enumerate(events or [], 1):
        m = date[:7]
        if m not in months:
            continue
        y_, mo, d = (int(v) for v in date.split("-"))
        xe = months.index(m) + (d - 1) / calendar.monthrange(y_, mo)[1]
        for ax in (a, b):
            ax.axvline(xe, color=MUTED, lw=0.7, ls=(0, (1.5, 1.5)))
        a.annotate(str(k), (xe, top * 1.28), xytext=(2, -2), textcoords="offset points",
                   ha="left", va="top", fontsize=6.5, color=MUTED)
        caption.append(f"{k} = {label} ({date})")
    if caption:
        (out / "fig_disclosure_over_time_events.txt").write_text(
            "Dotted lines: " + "; ".join(caption) + ".\n")
        print("event markers:", "; ".join(caption))
    b.set_xticks(x)
    b.set_xticklabels(labels)
    fig.savefig(out / "fig_disclosure_over_time.pdf", bbox_inches="tight")
    fig.savefig(out / "fig_disclosure_over_time.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"fig_disclosure_over_time: {months[0]} .. {months[-1]} "
          f"({len(months)} months)")


def fig_concentration(out: Path) -> None:
    d = pd.read_csv(out / "contributor_disclosure.csv")
    d = d[d.disclosing > 0].sort_values("disclosing", ascending=False)
    cum = d.disclosing.cumsum() / d.disclosing.sum() * 100
    n = list(range(1, len(d) + 1))

    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    ax.plot(n, cum, color=BLUE, lw=1.6)
    ax.set_xscale("log")
    ax.set_xlabel("Authors, heaviest disclosers first (log scale)")
    ax.set_ylabel("Cumulative % of\ndisclosing commits")
    ax.set_ylim(0, 105)
    ax.set_xlim(0.85, len(d) * 1.15)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for k in (1, 5, 20):
        if k <= len(d):
            y = cum.iloc[k - 1]
            ax.plot([k], [y], marker="o", ms=4, color=BLUE, mec="white", mew=0.8)
            who = "policy author" if k == 1 and bool(d.is_policy_author.iloc[0]) else f"top {k}"
            ax.annotate(f"{who}: {y:.0f}%", (k, y), xytext=(6, -9),
                        textcoords="offset points", fontsize=7, color=INK)
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100, len(d)])
    ax.set_xticklabels(["1", "2", "5", "10", "20", "50", "100", str(len(d))])
    ax.minorticks_off()
    fig.savefig(out / "fig_disclosure_concentration.pdf", bbox_inches="tight")
    fig.savefig(out / "fig_disclosure_concentration.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"fig_disclosure_concentration: {len(d)} disclosing authors")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--policy-date", required=True)
    ap.add_argument("--first-month", default="2025-10",
                    help="first month shown in the time figure")
    ap.add_argument("--events", nargs="*", default=[],
                    help='later rule changes as "YYYY-MM-DD=label", e.g. '
                         '"2026-04-22=copilot-instructions.md added"')
    a = ap.parse_args()
    out = Path(a.out)
    need = ["disclosure_monthly.csv", "contributor_monthly.csv",
            "contributor_disclosure.csv", "conformance_summary.json"]
    missing = [f for f in need if not (out / f).exists()]
    if missing:
        raise SystemExit(f"missing in {out}/: {missing} — run s4 and s6 first")
    ev = []
    for e in a.events:
        if "=" not in e:
            raise SystemExit(f"--events item '{e}' must look like YYYY-MM-DD=label")
        d, lab = e.split("=", 1)
        ev.append((d.strip(), lab.strip()))
    fig_over_time(out, a.policy_date, a.first_month, ev)
    fig_concentration(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
