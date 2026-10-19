#!/usr/bin/env python3
# Finds candidate AI-policy files in the repository by file name and by content.

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from pipeline123.MSR_AI_Gov.github_share.common import (
    AI_DISCOVERY_TERMS,
    NORMATIVE_TERMS,
)

EXT = r"(?:md|markdown|mdown|rst|txt|adoc|asciidoc|mdx|mdc)"

TIER1 = re.compile(
    rf"^(?:ai[_\-. ]?polic(?:y|ies)|ai[_\-. ]?usage[_\-. ]?polic(?:y|ies)|"
    rf"ai[_\-. ]?guidelines?|ai[_\-. ]?contributing|ai[_\-. ]?assistants?|"
    rf"ai[_\-. ]?coding[_\-. ]?assistants?|llm[_\-. ]?polic(?:y|ies)|"
    rf"genai[_\-. ]?(?:polic(?:y|ies)|guidelines?)|"
    rf"ai[_\-. ]?contribution[_\-. ]?polic(?:y|ies))\.{EXT}$",
    re.I,
)
TIER2 = re.compile(
    rf"^(?:contributing|contribution[_\-. ]?guidelines?|guidelines?|"
    rf"contributor[_\-. ]?expectations|reviewer[_\-. ]?expectations|"
    rf"code[_\-. ]?of[_\-. ]?conduct|governance|maintainers|security|"
    rf"development|developer|develop|readme)\.{EXT}$",
    re.I,
)
TIER3 = re.compile(
    rf"^(?:pull[_\-. ]?request[_\-. ]?template|issue[_\-. ]?template|"
    rf"agents?|claude|gemini|qwen|copilot[_\-. ]?instructions|"
    rf"\.?cursorrules|human)(?:\.{EXT})?$",
    re.I,
)

CODE_DIRS = re.compile(
    r"(?:^|/)(tests?|samples|boards|dts|drivers|soc|modules|subsys|include|"
    r"lib|kernel|arch|snippets|scripts/pylib|share|cmake)(?:/|$)"
)

DOC_EXT = re.compile(rf"\.{EXT}$|\.(?:ya?ml)$", re.I)

GOVERNANCE_DIR = re.compile(
    r"^(?:\.github|doc|docs|documentation|governance|policy|policies|"
    r"website|site|guides?|manual)(?:/|$)",
    re.I,
)


def in_governance_scope(path: str) -> bool:
    return "/" not in path or bool(GOVERNANCE_DIR.match(path))


def filename_tier(path: str) -> tuple[int, str] | None:
    base = path.rsplit("/", 1)[-1]
    if TIER1.match(base):
        return 1, "dedicated_ai_policy"
    if TIER3.match(base):
        return 3, "pr_template_or_agent_file"
    if TIER2.match(base) and in_governance_scope(path):
        low = base.lower()
        kind = (
            "readme"
            if low.startswith("readme")
            else "governance_doc"
            if "governance" in low or "maintainers" in low
            else "contribution_doc"
        )
        return 2, kind
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True, help="path to a full git checkout")
    ap.add_argument("--out", default="out")
    ap.add_argument(
        "--max-bytes",
        type=int,
        default=2_000_000,
        help="skip files larger than this (default 2 MB)",
    )
    args = ap.parse_args()

    tree = Path(args.tree).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from pipeline123.MSR_AI_Gov.github_share.common import git

    all_paths = [p for p in git(tree, "ls-files").split("\n") if p.strip()]
    doc_paths = [p for p in all_paths if DOC_EXT.search(p)]

    rows: dict[str, dict] = {}

    for p in all_paths:
        t = filename_tier(p)
        if t:
            rows[p] = {
                "path": p,
                "tier": t[0],
                "file_kind": t[1],
                "matched_filename": True,
                "matched_content": False,
                "ai_terms": 0,
                "normative_terms": 0,
                "ai_near_normative": 0,
                "bytes": 0,
                "in_code_dir": bool(CODE_DIRS.search(p)),
            }

    mention_files = []
    scanned = skipped_large = skipped_code_dir = 0
    for p in doc_paths:
        f = tree / p
        try:
            if f.stat().st_size > args.max_bytes:
                skipped_large += 1
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        ai = AI_DISCOVERY_TERMS.findall(text)
        if not ai:
            continue
        mention_files.append(p)
        if CODE_DIRS.search(p) and p not in rows:
            skipped_code_dir += 1
            continue
        norm = NORMATIVE_TERMS.findall(text)
        prox = 0
        for m in AI_DISCOVERY_TERMS.finditer(text):
            lo, hi = max(0, m.start() - 300), m.end() + 300
            if NORMATIVE_TERMS.search(text[lo:hi]):
                prox += 1
        r = rows.setdefault(
            p,
            {
                "path": p,
                "tier": 0,
                "file_kind": "content_match_only",
                "matched_filename": False,
                "matched_content": False,
                "ai_terms": 0,
                "normative_terms": 0,
                "ai_near_normative": 0,
                "bytes": 0,
                "in_code_dir": bool(CODE_DIRS.search(p)),
            },
        )
        r["matched_content"] = True
        r["ai_terms"] = len(ai)
        r["normative_terms"] = len(norm)
        r["ai_near_normative"] = prox
        r["bytes"] = f.stat().st_size

    for p, r in rows.items():
        if not r["bytes"]:
            try:
                r["bytes"] = (tree / p).stat().st_size
            except OSError:
                pass

    df = pd.DataFrame(rows.values())
    if df.empty:
        print("no candidates found")
        return 1
    df["matched_by"] = df.apply(
        lambda r: (
            "both"
            if r.matched_filename and r.matched_content
            else ("filename_only" if r.matched_filename else "content_only")
        ),
        axis=1,
    )
    df["rule_like"] = df.ai_near_normative >= 3
    df["governance"] = ""
    df["governance_note"] = ""
    prev_path = out / "policy_file_candidates.csv"
    kept = 0
    if prev_path.exists():
        prev = pd.read_csv(prev_path, dtype=str).fillna("")
        if {"path", "governance"} <= set(prev.columns):
            g = dict(zip(prev.path, prev.governance))
            n = dict(zip(prev.path, prev.get("governance_note", "")))
            df["governance"] = df.path.map(g).fillna("")
            df["governance_note"] = df.path.map(n).fillna("")
            kept = int((df.governance.str.strip() != "").sum())
    df = df.sort_values(["tier", "path"]).reset_index(drop=True)
    cols = [
        "path",
        "tier",
        "file_kind",
        "matched_by",
        "matched_filename",
        "matched_content",
        "ai_terms",
        "normative_terms",
        "ai_near_normative",
        "rule_like",
        "in_code_dir",
        "bytes",
        "governance",
        "governance_note",
    ]
    df[cols].to_csv(out / "policy_file_candidates.csv", index=False)
    (out / "ai_mention_files.txt").write_text("\n".join(sorted(mention_files)) + "\n")

    summary = {
        "tree": str(tree),
        "head_sha": git(tree, "rev-parse", "HEAD").strip(),
        "tracked_files_total": len(all_paths),
        "doc_files_total": len(doc_paths),
        "doc_files_scanned": scanned,
        "doc_files_skipped_too_large": skipped_large,
        "files_with_ai_vocabulary": len(mention_files),
        "content_hits_excluded_as_code_dir": skipped_code_dir,
        "candidates_total": len(df),
        "candidates_by_match": df.matched_by.value_counts().to_dict(),
        "candidates_rule_like_threshold3": int(df.rule_like.sum()),
        "rule_like_threshold_sensitivity": {
            str(k): int((df.ai_near_normative >= k).sum()) for k in (1, 2, 3, 5, 10)
        },
    }
    (out / "discovery_summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"\n{len(df)} candidates -> {out}/policy_file_candidates.csv")
    undecided = int((df.governance.astype(str).str.strip() == "").sum())
    if kept:
        print(
            f"kept {kept} existing governance decision(s); "
            f"{undecided} candidate(s) still undecided"
        )
    if undecided:
        print(
            "NEXT: fill the `governance` column (yes/no) by reading each "
            "undecided candidate, then run s2."
        )
    print("\ncandidates needing a decision:")
    for _, r in df.iterrows():
        flag = "*" if r.rule_like else " "
        print(
            f"  {flag} [{r.matched_by:13s}] ai={r.ai_terms:<4d} "
            f"near={r.ai_near_normative:<4d} {r.path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
