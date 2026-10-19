#!/usr/bin/env python3
# Disclosure per contributor: concentration, monthly activity, disclosing authors.

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    cum = np.cumsum(x)
    return float((n + 1 - 2 * (cum / cum[-1]).sum()) / n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commits", required=True)
    ap.add_argument("--policy-date", required=True)
    ap.add_argument(
        "--policy-sha",
        default=None,
        help="commit that introduced the policy; its author is "
        "flagged as the policy author",
    )
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.commits)
    df["email"] = df.author_email.astype(str).str.lower().str.strip()
    df["disc"] = df.t_assisted_by.astype(bool)
    pre, post = df[df.date < args.policy_date], df[df.date >= args.policy_date]

    policy_author = None
    if args.policy_sha:
        hit = df[df.sha.str.startswith(args.policy_sha[:10])]
        if len(hit):
            policy_author = hit.iloc[0].email

    pre_counts = pre.groupby("email").size()
    g = (
        post.groupby("email")
        .agg(
            commits_post=("sha", "size"),
            disclosing=("disc", "sum"),
            first_disclosure=(
                "date",
                lambda s: (
                    s[post.loc[s.index, "disc"]].min()
                    if post.loc[s.index, "disc"].any()
                    else ""
                ),
            ),
        )
        .reset_index()
    )
    g["disclosing"] = g.disclosing.astype(int)
    g["disclosure_rate"] = (g.disclosing / g.commits_post).round(4)
    g["commits_pre_policy"] = g.email.map(pre_counts).fillna(0).astype(int)
    g["active_before_policy"] = g.commits_pre_policy > 0
    g["ever_disclosed"] = g.disclosing > 0
    g["always_discloses"] = g.ever_disclosed & (g.disclosing == g.commits_post)
    g["is_policy_author"] = g.email == policy_author
    q = g.commits_post.rank(pct=True)
    g["activity_tier"] = np.select(
        [q > 0.95, q > 0.75], ["top_5pct", "top_25pct"], default="other"
    )
    g["email_domain"] = g.email.str.split("@").str[-1]
    g = g.sort_values(["disclosing", "commits_post"], ascending=False).reset_index(
        drop=True
    )
    g.insert(0, "contributor", [f"C{i + 1:04d}" for i in range(len(g))])

    g[["contributor", "email"]].to_csv(out / "contributor_key_PRIVATE.csv", index=False)
    pub = g.drop(columns=["email"])
    pub.to_csv(out / "contributor_disclosure.csv", index=False)

    d = g[g.ever_disclosed]
    total = int(d.disclosing.sum())
    conc = []
    for k in (1, 2, 5, 10, 20, 50, 100):
        s = int(d.disclosing.head(k).sum())
        conc.append(
            {
                "top_k_authors": k,
                "disclosing_commits": s,
                "share_of_disclosing_commits": round(s / total, 4) if total else None,
            }
        )
    pd.DataFrame(conc).to_csv(out / "contributor_concentration.csv", index=False)

    post = post.assign(month=post.date.str[:7])
    top1 = set(d.email.head(1))
    top5 = set(d.email.head(5))
    seen: set[str] = set()
    rows = []
    for m, grp in post.groupby("month"):
        authors = set(grp.email)
        discl = set(grp[grp.disc].email)
        new = discl - seen
        seen |= discl

        def share(sub):
            return round(float(sub.disc.mean()), 4) if len(sub) else None

        rows.append(
            {
                "month": m,
                "commits": len(grp),
                "active_authors": len(authors),
                "disclosing_authors": len(discl),
                "share_of_authors_disclosing": round(len(discl) / len(authors), 4),
                "new_disclosing_authors": len(new),
                "commit_share_all": share(grp),
                "commit_share_excl_top1": share(grp[~grp.email.isin(top1)]),
                "commit_share_excl_top5": share(grp[~grp.email.isin(top5)]),
            }
        )
    pd.DataFrame(rows).to_csv(out / "contributor_monthly.csv", index=False)

    tiers = (
        g.groupby("activity_tier")
        .agg(
            authors=("contributor", "size"),
            ever_disclosed=("ever_disclosed", "sum"),
            commits=("commits_post", "sum"),
            disclosing=("disclosing", "sum"),
        )
        .reset_index()
    )
    tiers["share_authors_disclosing"] = (tiers.ever_disclosed / tiers.authors).round(4)
    tiers["commit_disclosure_rate"] = (tiers.disclosing / tiers.commits).round(4)

    S = {
        "policy_date": args.policy_date,
        "post_policy_commits": int(len(post)),
        "post_policy_authors": int(len(g)),
        "authors_ever_disclosing": int(g.ever_disclosed.sum()),
        "share_of_authors_ever_disclosing": round(float(g.ever_disclosed.mean()), 4),
        "authors_with_exactly_one_disclosing_commit": int((g.disclosing == 1).sum()),
        "authors_who_always_disclose": int(g.always_discloses.sum()),
        "disclosing_commits": total,
        "gini_of_disclosing_commits_among_disclosers": round(
            gini(d.disclosing.to_numpy()), 4
        ),
        "concentration": conc,
        "policy_author": {
            "identified": policy_author is not None,
            "pseudonym": (
                g.loc[g.is_policy_author, "contributor"].iloc[0]
                if g.is_policy_author.any()
                else None
            ),
            "disclosing_commits": (
                int(g.loc[g.is_policy_author, "disclosing"].sum())
                if g.is_policy_author.any()
                else None
            ),
            "share_of_disclosing_commits": (
                round(float(g.loc[g.is_policy_author, "disclosing"].sum() / total), 4)
                if g.is_policy_author.any() and total
                else None
            ),
        },
        "by_activity_tier": tiers.to_dict(orient="records"),
        "disclosers_active_before_policy": int(
            (g.ever_disclosed & g.active_before_policy).sum()
        ),
        "limitation": "identity = author email; multiple addresses per person inflate author counts",
    }
    (out / "contributor_summary.json").write_text(json.dumps(S, indent=2))
    print(json.dumps(S, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
