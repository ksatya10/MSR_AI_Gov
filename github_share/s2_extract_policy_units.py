#!/usr/bin/env python3
# Extracts the AI-related text from the policy files and dates each change from git history.

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from pipeline123.MSR_AI_Gov.github_share.common import (
    AI_DISCOVERY_TERMS,
    NORMATIVE_TERMS,
    git,
    split_sections,
)

PR_IN_SUBJECT = re.compile(r"\(#(\d+)\)|\bPR\s*#?(\d+)\b", re.I)


def top_level_blocks(body: str) -> list[str]:
    blocks, cur, prev_blank = [], [], True
    for ln in body.split("\n"):
        starts_new = prev_blank and ln.strip() and not ln[:1].isspace()
        if starts_new and cur:
            blocks.append("\n".join(cur).rstrip())
            cur = []
        cur.append(ln)
        prev_blank = not ln.strip()
    if cur:
        blocks.append("\n".join(cur).rstrip())
    return [b for b in blocks if b.strip()]


def extract(text: str, path: str):
    kept, keys, why = [], [], []
    for title, _lvl, body in split_sections(text, path):
        if AI_DISCOVERY_TERMS.search(title):
            kept.append(body)
            keys.append([body])
            why.append(f"section '{title}' (heading names AI; whole section)")
            continue
        if not (AI_DISCOVERY_TERMS.search(body) and NORMATIVE_TERMS.search(body)):
            continue
        blocks = [b for b in top_level_blocks(body) if AI_DISCOVERY_TERMS.search(b)]
        blocks = [b for b in blocks if b.strip() != title.strip()]
        if not blocks:
            continue
        kept.append(f"[{title}]\n\n" + "\n\n".join(blocks))
        keys.append(blocks)
        why.append(f"{len(blocks)} AI block(s) in section '{title}'")

    def norm(t: str) -> str:
        return re.sub(r"\s+", " ", t).strip()

    whole = [norm(k) for k in kept]
    out_txt, out_why = [], []
    for i, blocks in enumerate(keys):
        nb = [norm(b) for b in blocks]
        if any(
            i != j and len(whole[j]) > len(whole[i]) and all(b in whole[j] for b in nb)
            for j in range(len(kept))
        ):
            continue
        out_txt.append(kept[i])
        out_why.append(why[i])
    unit = "\n\n".join(out_txt).strip()
    unit = re.sub(r"(?:\n\s*\.\. _[\w.-]+:\s*)+$", "", unit).strip()
    return unit, out_why


def adoption_events(repo: Path, path: str, max_commits: int = 2000) -> list[dict]:
    shas = [
        s
        for s in git(repo, "log", "--reverse", "--format=%H", "--", path).split("\n")
        if s.strip()
    ][:max_commits]
    events = []
    for sha in shas:
        raw = git(
            repo, "show", sha, "--format=%H\x1f%cI\x1f%s", "--unified=0", "--", path
        )
        head, _, patch = raw.partition("\n")
        parts = head.split("\x1f")
        if len(parts) < 3:
            continue
        _sha, date, subject = parts[0], parts[1], parts[2]
        added = "\n".join(
            ln[1:]
            for ln in patch.split("\n")
            if ln.startswith("+") and not ln.startswith("+++")
        )
        if not added.strip():
            continue
        if AI_DISCOVERY_TERMS.search(added) and NORMATIVE_TERMS.search(added):
            m = PR_IN_SUBJECT.search(subject)
            events.append(
                {
                    "path": path,
                    "sha": _sha,
                    "commit_date": date,
                    "subject": subject,
                    "pr_number": (m.group(1) or m.group(2)) if m else "",
                    "added_chars": len(added),
                    "ai_terms_added": len(AI_DISCOVERY_TERMS.findall(added)),
                }
            )
    return events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--tree", required=True, help="full checkout (file contents)")
    ap.add_argument(
        "--repo-history",
        default=None,
        help="clone with full history (defaults to --tree)",
    )
    ap.add_argument("--out", default="out")
    ap.add_argument(
        "--include",
        default=None,
        help="comma-separated paths to force-include, bypassing "
        "the `governance` column (for a quick first pass)",
    )
    args = ap.parse_args()

    tree = Path(args.tree).resolve()
    hist = Path(args.repo_history or args.tree).resolve()
    out = Path(args.out)
    (out / "policy_units").mkdir(parents=True, exist_ok=True)

    cand = pd.read_csv(args.candidates)
    if args.include:
        want = [p.strip() for p in args.include.split(",") if p.strip()]
    else:
        gov = cand[
            cand["governance"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["yes", "y", "true", "1"])
        ]
        want = gov["path"].tolist()
    if not want:
        print(
            "No files marked governance=yes in the candidates file.\n"
            "Fill that column (or pass --include) and re-run."
        )
        return 1

    manifest, all_events, corpus = [], [], []
    for path in want:
        f = tree / path
        if not f.exists():
            print(f"  ! missing in tree: {path}")
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        unit, why = extract(text, path)
        slug = path.replace("/", "__")
        if unit:
            (out / "policy_units" / f"{slug}.txt").write_text(unit, encoding="utf-8")
            corpus.append(f"===== {path} =====\n{unit}")
        ev = adoption_events(hist, path)
        all_events += ev
        manifest.append(
            {
                "path": path,
                "source_bytes": len(text),
                "extracted_bytes": len(unit),
                "extraction_ratio": round(len(unit) / len(text), 4) if text else 0,
                "evidence": "; ".join(why),
                "first_ai_commit_sha": ev[0]["sha"] if ev else "",
                "first_ai_commit_date": ev[0]["commit_date"] if ev else "",
                "first_ai_commit_subject": ev[0]["subject"] if ev else "",
                "first_ai_commit_pr": ev[0]["pr_number"] if ev else "",
                "n_ai_touching_commits": len(ev),
            }
        )
        print(
            f"  + {path}: {len(unit)} chars extracted from {len(text)}; "
            f"first AI commit {ev[0]['commit_date'][:10] if ev else 'n/a'} "
            f"({len(ev)} AI-touching commits)"
        )

    mdf = pd.DataFrame(manifest)
    mdf.to_csv(out / "policy_unit_manifest.csv", index=False)
    pd.DataFrame(all_events).to_csv(out / "adoption_events.csv", index=False)
    (out / "policy_unit_corpus.txt").write_text("\n\n".join(corpus), encoding="utf-8")

    dates = [d for d in mdf.first_ai_commit_date if isinstance(d, str) and d]
    summary = {
        "files_in_unit": len(mdf),
        "total_extracted_bytes": int(mdf.extracted_bytes.sum()),
        "earliest_ai_commit": min(dates) if dates else None,
        "latest_ai_commit": max(dates) if dates else None,
        "distinct_first_commit_shas": sorted(
            {s for s in mdf.first_ai_commit_sha if isinstance(s, str) and s}
        ),
    }
    (out / "extraction_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps(summary, indent=2))
    print(f"\nCoding unit -> {out}/policy_unit_corpus.txt")
    print(
        "If two files share a first_ai_commit_sha they entered in the same "
        "commit, which is evidence they form ONE policy unit."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
