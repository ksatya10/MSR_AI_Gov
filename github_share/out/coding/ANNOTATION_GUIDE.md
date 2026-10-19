# Annotation Guide: TRACE coding of AI-use policies

Thank you for coding for this study. This guide explains what to do, what you
will receive, and what to send back. Read it once before you start, then keep
it and the codebook open while you code.

You will code in two rounds:

| Round          | What you code                                            | Rows | Why                                                                                                        |
| -------------- | -------------------------------------------------------- | ---- | ---------------------------------------------------------------------------------------------------------- |
| 1. Calibration | Short AI-use policy texts from many open-source projects | 20   | To check that we all apply the codebook the same way. Reliability statistics are computed from this round. |
| 2. Case        | Policy text from the single project this study is about  | 5    | These labels are the study's result.                                                                       |

You receive the Round 2 workbook only after Round 1 has been discussed.

---

## 1. Rules that keep the coding valid

These rules matter more than anything else in this guide. If you break one by
accident, say so in the `notes` column. We would rather know than not know.

1. **Code alone.** Do not discuss texts, labels, or the codebook with the
   other coders until everyone has sent in their workbook for that round.
2. **Code from the text only.** Do not search the web for a text, do not try
   to work out which project it comes from, and do not look up documents a
   text points to. Code what is in the cell.
3. **Do not use AI tools.** Do not paste texts into ChatGPT, Claude, Copilot
   or any other assistant, whether to get labels or to have a text explained.
   The study measures how humans read these policies.
4. **Do not look for other people's labels.** Some of these texts come from a
   published replication package that also contains labels. Do not open any
   label file, and do not ask anyone what an earlier coder chose.
5. **Do not change your Round 1 labels after you send them.** Reliability is
   computed on the labels you send first. Disagreements are settled in a
   separate step and recorded separately, so your first answer is never lost
   or overwritten.

---

## 2. What you receive

```
CODEBOOK.md                  the TRACE codebook (the rules)
ANNOTATION_GUIDE.md          this guide (how to apply them here)
Coder_calibration.xlsx       Round 1 workbook
```

**About the codebook.** `CODEBOOK.md` was written so that it could also be
given to a language model. Two parts of it do not apply to you: the _Output
Format_ section (the JSON block) and the last General Rule ("Do not return
explanations, notes, ..."). You record labels in the workbook instead, and
notes are welcome. Every other rule in the codebook applies exactly as
written.

---

## 3. How to fill in the workbook

Each row is one text. Fill in the yellow cells only.

| Column              | What to enter                                                                                                                                                                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sample_id`         | Do not edit.                                                                                                                                                                                                                                                  |
| `policy_text`       | Do not edit.                                                                                                                                                                                                                                                  |
| `T` `R` `A` `C` `E` | One label per cell, chosen from the dropdown. Never leave one empty: if a dimension is not mentioned, choose level 1.                                                                                                                                         |
| `confidence`        | Optional: `low`, `medium` or `high`, for the row as a whole.                                                                                                                                                                                                  |
| `notes`             | Optional, but useful: anything that made a decision hard, such as two levels that both seem to fit, a sentence you could not classify, or a text that only points to another document. Name the dimension, for example `C: unsure if "discouraged" is a ban`. |

Do not add, delete, sort or rename rows or columns. Save the file under the
same name and send it back.

The dropdowns accept only codebook labels. If your spreadsheet program does
not show them, type the label exactly as it appears in Section 5.

---

## 4. How to code one text

Work through these five steps for every text.

1. **Read the whole text once** without labelling anything.
2. **Mark what counts.** Code only sentences that govern AI use (AI, LLMs,
   agents, bots, generated content, AI-assisted work). Ordinary contribution
   rules that do not mention AI are ignored, even when they sit right next to
   the AI rules.
3. **Code each dimension separately.** For each of T, R, A, C, E, find the
   sentence that supports the highest applicable level. The dimensions are
   independent: one sentence can set two dimensions, and a strong level on one
   dimension says nothing about another.
4. **Check the wording.**
   - _should_ and _are expected to_ are requirements, not suggestions (T3 or
     T4, not T2).
   - _may_, _can_, _are welcome to_, _are encouraged to_ are optional for
     contributors (T2).
   - For consequences, _may reject_ still counts as rejection (E3).
5. **Choose the highest level that applies** in each dimension. For R, choose
   the most concrete type: R4 over R3 over R2.

If the codebook does not settle a case, do not invent a rule. Choose the level
you think the codebook supports best and explain it in `notes`. These notes
are how unclear rules get found and discussed.

---

## 5. Quick reference

This summarises the codebook. If the two ever seem to disagree, the codebook
wins.

### T: Transparency (ordered: how strong is the disclosure requirement?)

| Label                               | When                                                                                                                                                                                      |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `T1_Not_Required_or_Not_Mentioned`  | No disclosure required, or disclosure explicitly not required.                                                                                                                            |
| `T2_Encouraged_or_Voluntary`        | Disclosure is optional: _may, can, welcome to, encouraged to, we appreciate_.                                                                                                             |
| `T3_Basic_Disclosure_Required`      | Disclosure is required (_must, required, shall, need to, should, are expected to_), but no specific detail is named.                                                                      |
| `T4_Detailed_Traceability_Required` | Disclosure is required **and** at least one specific detail must be given: tool or model name, prompt or transcript, how AI was used, which files or lines, or machine-readable metadata. |

### R: Responsibility (categories, not a ranking)

| Label                                      | When                                                                                                       |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `R1_Not_Mentioned`                         | No AI-specific human responsibility.                                                                       |
| `R2_Human_Ownership_Required`              | A human is named as responsible, accountable or the author, with no action required.                       |
| `R3_Understanding_or_Explanation_Required` | The contributor must understand, explain, justify or defend the AI-assisted work.                          |
| `R4_Validation_or_Evidence_Required`       | The contributor must review, inspect, test, validate, verify, reproduce, edit, check, or provide evidence. |

If several apply, choose the most concrete: R4 over R3 over R2.

### A: Attribution (ordered: how specific is the rights or source requirement?)

| Label                                         | When                                                                                                                                       |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `A1_Not_Mentioned`                            | No copyright, licence, provenance, DCO/CLA or source-rights rule.                                                                          |
| `A2_General_IP_or_Source_Responsibility`      | A general legal or IP duty with no named object: _ensure legality, no IP infringement, third-party material_.                              |
| `A3_License_or_Source_Compatibility_Required` | A named compliance object: the project licence, copyright, DCO/CLA, sign-off, tool terms of service, or third-party licence compatibility. |
| `A4_Documented_Rights_or_Provenance_Required` | Documented records are required: provenance records, source records, attribution records, certification, evidence of the right to submit.  |

### C: Constraints (ordered: how broad is the restriction?)

| Label                              | When                                                                                                                                                                                                                                                |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `C1_No_Substantive_Restriction`    | AI use is allowed or not restricted.                                                                                                                                                                                                                |
| `C2_Form_Restricted`               | Limits on the form of content: bulk output, low-effort content ("slop"), fully AI-generated submissions, large changes, or content the contributor does not understand.                                                                             |
| `C3_Context_or_Channel_Restricted` | AI is restricted in named channels or contexts (issues, PR descriptions, reviews, comments, commit messages, security reports, docs, maintainer communication, autonomous agents), while ordinary AI-assisted contribution elsewhere stays allowed. |
| `C4_Generally_Excluded`            | An explicit blanket ban: _not accepted, prohibited, banned, we don't accept_.                                                                                                                                                                       |

If a text restricts both form and channel, choose C3.

### E: Enforcement (ordered: how severe is the consequence?)

| Label                                      | When                                                                                                         |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| `E1_Not_Mentioned`                         | No consequence stated.                                                                                       |
| `E2_Remediation_or_Review_Limitation`      | A soft consequence: asked to revise, fix or disclose more; review delayed, paused, deprioritised or limited. |
| `E3_Current_Submission_Rejected_or_Closed` | The current submission may be closed, rejected, declined, hidden or removed.                                 |
| `E4_Future_Participation_Restricted`       | Future participation may be restricted: ban, block, suspension, loss of privileges.                          |

---

## 6. Boundaries where coders most often disagree

These come from the codebook's Boundary Rules.

| Boundary | Rule                                                                                                                                                                                                      |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T2 or T3 | _should_ or _are expected to_ means a requirement, so T3 (or T4). Only _may, can, welcome to, encouraged to_ give T2.                                                                                     |
| T3 or T4 | T4 needs a requirement **and** a named detail. Listing examples without requiring them ("e.g., you may note the tool") stays T3. Vague words such as "appropriately" or "in detail" do not name a detail. |
| R2 or R3 | "You are responsible" alone is R2. "You must understand / explain" is R3.                                                                                                                                 |
| R or C2  | "You must review / understand / test" is R. "Do not submit X", including "don't submit what you don't understand", is C2.                                                                                 |
| C3 or C4 | C4 needs an explicit blanket ban. Bans on named channels without a blanket statement are C3. "Strongly discouraged" or "limited" without a ban stays C3.                                                  |
| C or E   | C is what is allowed before a violation. E is what happens after one.                                                                                                                                     |
| E2 or E3 | Revise, delay or pause is E2. Reject or close is E3, including "may reject".                                                                                                                              |
| A2 or A3 | A general IP duty is A2. A named object (licence, DCO, CLA, sign-off, tool terms) is A3.                                                                                                                  |
| T or A   | Disclosing AI use is T. Claims about rights, source or provenance are A. An `Assisted-by:` line on its own is T, not A. Sign-off, DCO/CLA, licence compatibility or provenance certification is A.        |
| T or R   | Making the tool, prompt or process visible is T. Evidence that the work is correct is R.                                                                                                                  |

### Minimal pairs for T

| Text                                                    | Label                            |
| ------------------------------------------------------- | -------------------------------- |
| "You may mention which AI tool you used."               | T2 (optional)                    |
| "You should state that you used AI."                    | T3 (required, no detail named)   |
| "You must disclose AI use, e.g. you may note the tool." | T3 (the example is not required) |
| "You must name the AI tool you used."                   | T4 (required, detail named)      |

---

## 7. A worked example

This example is made up for training. It is not one of the texts you will
code.

> _"AI assistants are welcome here. If you like, you can mention in the pull
> request which tool helped you. You must run the test suite on any
> AI-generated change and paste the test output into the pull request. Do not
> use AI to write bug reports. Accounts that repeatedly ignore these rules may
> be blocked."_

| Dim | Label                                | Why                                                                                                                                           |
| --- | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| T   | `T2_Encouraged_or_Voluntary`         | "If you like, you can mention" is optional. It names a detail (the tool), but a named detail only gives T4 when disclosure is required.       |
| R   | `R4_Validation_or_Evidence_Required` | "Must run the test suite ... paste the test output" requires testing and evidence. Test output is evidence of correctness, so it is R, not T. |
| A   | `A1_Not_Mentioned`                   | No licence, rights or provenance rule.                                                                                                        |
| C   | `C3_Context_or_Channel_Restricted`   | "Do not use AI to write bug reports" removes AI from one named channel (issues) while it stays allowed elsewhere.                             |
| E   | `E4_Future_Participation_Restricted` | "May be blocked" restricts future participation.                                                                                              |

Confidence: high.

---

## 8. Round 2 only: the case texts

Round 2 uses a different workbook with extra columns. Everything above still
applies.

**Overlapping units are intentional.** Some units contain other units; for
example, one unit may be two documents joined together while two other units
are each document on its own. Code every unit as if it were the only text you
had. Do not copy labels from one unit to another. Agreement between the
overlapping units is something we measure.

**`[PROJECT]`** replaces the project's name. Ignore it.

**Pointers to other documents.** Some units point to other files, for example
"see the contribution guidelines". Do not look them up. Code only the text in
the cell and write `pointer: <what it points to>` in `notes`. Where the
pointed-to document is itself an AI policy, it is already one of the units.

**`scope` column** (choose one first). The codebook says: ignore agent
workflow instructions unless they also govern human-submitted contributions or
project-facing communication.

| Value             | When                                                                                                                         | Then                                                                        |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `in_scope`        | The unit governs AI use in contributions or project-facing communication.                                                    | Code T to E as usual.                                                       |
| `partly_in_scope` | The unit mixes such rules with instructions that only concern an AI agent's own workflow (for example how to build or test). | Code T to E from the parts that govern contributions or communication only. |
| `out_of_scope`    | The unit contains only agent workflow instructions.                                                                          | Leave T to E empty and explain in `notes`.                                  |

**Evidence columns** (`T_evidence` ... `E_evidence`). For each dimension,
paste the shortest phrase from the text that decided your label, for example
`"must run the test suite"`. If you chose level 1, write `none`. The evidence
is used during discussion and lets us quote the exact wording in the paper.

---
