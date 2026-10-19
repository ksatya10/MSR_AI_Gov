# AI policy case study: Zephyr

Scripts for a case study of the AI-use policy of `zephyrproject-rtos/zephyr`,
using the TRACE codebook and the replication package of Chen et al.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PACKAGE=/path/to/replication_package_final_20260921
export GITHUB_TOKEN=...   # only for s7 and s9
```

## Scripts

| Step | Script |
|---|---|
| Find and extract the policy | `s1_discover_policy_files.py`, `s2_extract_policy_units.py` |
| Compare with the 385 policies | `s3_benchmark_trace.py` |
| Commit-level disclosure | `s4_mine_conformance.py`, `s6_contributor_conformance.py`, `s12_tools_and_persistence.py`, `s13_pre_post.py`, `s14_tool_rules.py` |
| PR-level disclosure and detector | `s9_pr_level.py`, `s15_detector_extension.py` |
| Coding sheets and agreement | `make_coder_sheets.py`, `s5_interrater.py`, `s5b_interrater_multi.py`, `s5c_agreement_generic.py`, `s5d_reconcile.py` |
| GitHub discussions | `s7_fetch_review_data.py`, `s10_enforcement_compare.py`, `s11_cohort_trailer_policies.py` |
| Figures | `s8_make_figures.py` |

`run_all.sh` runs the main pipeline. Each script prints its options with `-h`.

## Outputs

`out/` holds the results the paper uses (summaries, tables, figures, coding
sheets and agreement results). Raw GitHub API responses and files that contain
contributor names, e-mail addresses or logins are not included; they can be
regenerated with the scripts. In `out/commits_classified.csv.gz`, author and
committer names and e-mails are replaced by stable pseudonyms (`C0001`, ...),
and `author_domain` keeps only the e-mail domain.
