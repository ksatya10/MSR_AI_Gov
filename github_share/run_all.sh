#!/usr/bin/env bash
# Runs the main pipeline in order.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/zephyrproject-rtos/zephyr.git}"
SUBJECT="${SUBJECT:-zephyrproject-rtos/zephyr}"
PACKAGE="${PACKAGE:?set PACKAGE=/path/to/replication_package_final_20260921}"
SINCE="${SINCE:-2025-01-01}"
POLICY_DATE="${POLICY_DATE:-2026-03-06}"
VECTOR="${VECTOR:-T4,R4,A4,C3,E1}"
MATCH_DIMS="${MATCH_DIMS:-T,A}"
WORK="${WORK:-work}"
OUT="${OUT:-out}"

mkdir -p "$WORK" "$OUT"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$WORK/tree/.git" ]; then
  echo "== cloning working tree (depth 1)"
  git clone --quiet --depth 1 "$REPO_URL" "$WORK/tree"
fi
if [ ! -d "$WORK/history/.git" ]; then
  echo "== cloning full history (blobless)"
  git clone --quiet --filter=blob:none --no-checkout "$REPO_URL" "$WORK/history"
fi

echo "== tree HEAD:    $(git -C "$WORK/tree" rev-parse --short HEAD)"
echo "== history HEAD: $(git -C "$WORK/history" rev-parse --short HEAD)"
echo "== history commits: $(git -C "$WORK/history" rev-list --count HEAD)"

echo
echo "== s1: discover candidate policy files"
python3 "$HERE/s1_discover_policy_files.py" --tree "$WORK/tree" --out "$OUT"

echo
if python3 - "$OUT/policy_file_candidates.csv" <<'PY'
import sys, pandas as pd
d = pd.read_csv(sys.argv[1])
yes = d["governance"].astype(str).str.strip().str.lower().isin(
    ["yes", "y", "true", "1"]).sum()
sys.exit(0 if yes else 1)
PY
then
  echo "== s2: extract policy units"
  python3 "$HERE/s2_extract_policy_units.py" \
      --candidates "$OUT/policy_file_candidates.csv" \
      --tree "$WORK/tree" --repo-history "$WORK/history" --out "$OUT"
else
  cat <<EOF
== s2 SKIPPED.
   No rows in $OUT/policy_file_candidates.csv are marked governance=yes.
   Read each candidate, set governance to yes/no, and re-run.
   For the Zephyr case the four governance files are:
     doc/contribute/guidelines.rst
     doc/contribute/reviewer_expectations.rst
     .github/copilot-instructions.md
     AGENTS.md
   (CLAUDE.md is a 5-line import of AGENTS.md and carries no policy text.)
EOF
fi

echo
echo "== s4: mine observable conformance"
python3 "$HERE/s4_mine_conformance.py" \
    --repo-history "$WORK/history" --package "$PACKAGE" \
    --since "$SINCE" --policy-date "$POLICY_DATE" --out "$OUT" \
    ${UNTIL:+--until "$UNTIL"}

echo
echo "== s6: contributor-level disclosure"
POLICY_SHA="${POLICY_SHA:-df8b5861725396858cb31417abeb68a00750a803}"
python3 "$HERE/s6_contributor_conformance.py" \
    --commits "$OUT/commits_classified.csv.gz" \
    --policy-date "$POLICY_DATE" --policy-sha "$POLICY_SHA" --out "$OUT"

echo
echo "== s3: benchmark the coded vector against the 385-policy cohort"
echo "       using VECTOR=$VECTOR  (override after coding is reconciled)"
python3 "$HERE/s3_benchmark_trace.py" \
    --package "$PACKAGE" --subject "$SUBJECT" \
    --vector "$VECTOR" --match-dims "$MATCH_DIMS" --out "$OUT"

echo
echo "== s5: validate the IRR implementation against the package's own numbers"
python3 "$HERE/s5_interrater.py" \
    --a "$PACKAGE/data/policy/irr/coder_a_labels.csv" \
    --b "$PACKAGE/data/policy/irr/coder_b_labels.csv" \
    --id sample_id --out "$OUT/irr_replication" \
    --compare "$PACKAGE/data/policy/irr/irr_results.csv"

echo
echo "== done. outputs in $OUT/"
ls -1 "$OUT"
