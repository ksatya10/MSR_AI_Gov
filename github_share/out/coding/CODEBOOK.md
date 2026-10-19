# TRACE Codebook for OSS AI Policy Labeling

Use this codebook to label repository policy text that governs AI-assisted
contributions. Ignore ordinary contribution rules unless they explicitly
mention AI, LLMs, agents, bots, generated content, or AI-assisted work, and do
not label agent workflow instructions unless they also govern human-submitted
contributions or project-facing communication. Use only explicit policy text.

Label each policy on five independent dimensions — Transparency (T),
Responsibility (R), Attribution (A), Constraints (C), and Enforcement (E). For
each dimension assign exactly one level; if the policy does not mention that
dimension, assign level 1. Where more than one level could apply within a
dimension, choose the highest applicable level, using the boundary guidance
under each dimension and in the Boundary Rules section.

## Output Format

Return one JSON object with exactly these five fields, using exactly one label
per field.

```json
{
  "transparency": "T1_Not_Required_or_Not_Mentioned | T2_Encouraged_or_Voluntary | T3_Basic_Disclosure_Required | T4_Detailed_Traceability_Required",
  "responsibility": "R1_Not_Mentioned | R2_Human_Ownership_Required | R3_Understanding_or_Explanation_Required | R4_Validation_or_Evidence_Required",
  "attribution": "A1_Not_Mentioned | A2_General_IP_or_Source_Responsibility | A3_License_or_Source_Compatibility_Required | A4_Documented_Rights_or_Provenance_Required",
  "constraints": "C1_No_Substantive_Restriction | C2_Form_Restricted | C3_Context_or_Channel_Restricted | C4_Generally_Excluded",
  "enforcement": "E1_Not_Mentioned | E2_Remediation_or_Review_Limitation | E3_Current_Submission_Rejected_or_Closed | E4_Future_Participation_Restricted"
}
```

## T. Transparency

Transparency captures the visibility of AI use, ordered by the strength of the
disclosure requirement.

**T1_Not_Required_or_Not_Mentioned** — No AI-use disclosure is required. This
applies when the policy never mentions disclosure, explicitly states that
disclosure is not required, or discusses AI use without asking contributors to
disclose it.

**T2_Encouraged_or_Voluntary** — Disclosure is purely optional, and a
contributor may choose not to disclose without consequence. Trigger this level
only for genuinely optional language such as *may*, *can*, *are welcome to*,
*we appreciate or prefer*, or *are encouraged to*. The modals *should* and *are
expected to* are **not** voluntary — they signal a requirement and belong in T3.

**T3_Basic_Disclosure_Required** — Disclosure is mandatory, but the policy does
not name any specific detail that must be disclosed. This level covers any
requirement language — *must*, *required to*, *shall*, *need to*, *have to*,
**as well as *should* and *are expected to*** — paired with a bare disclosure
ask such as "disclose your AI use", "state that you used AI", "check the box",
or "add a label". The policy must not name a specific detail category (no tool,
prompt, transcript, files, or metadata); vague modifiers such as
"appropriately" or "in detail" do not count as naming a category and remain T3.

**T4_Detailed_Traceability_Required** — Disclosure is mandatory and the policy
names at least one specific detail category that must be disclosed: the tool or
model name; the prompt, prompt summary, transcript, or conversation log; a
usage summary or explanation of how AI was used; the affected files, lines, or
sections; or machine-readable metadata. The requirement must be binding —
merely listing examples without requiring them ("e.g., you may note the tool")
stays in T3.

## R. Responsibility

Responsibility captures what kind of human accountability the policy demands
for AI output. The four levels are **categorical types of responsibility, not a
monotone strength order**: a policy that requires validation (R4) is not simply
"more" of ownership (R2) — it demands a qualitatively different kind of
engagement. Assign the single most applicable type; when several types appear
in the same policy, choose the most concrete one, using the priority
R4 > R3 > R2 so that the strongest, most specific obligation wins.

**R1_Not_Mentioned** — No AI-specific human responsibility is required. Generic
project responsibility rules may appear, but they are not explicitly tied to AI
use.

**R2_Human_Ownership_Required** — A human is named as responsible,
accountable, or the author in name only, with no required cognitive action.
This is triggered by language such as *you are responsible*, *accountable*,
*remain the author*, *liable*, or *the contributor owns the contribution*,
without any requirement to understand, explain, justify, review, test, or
validate. It is a pure nominal attribution of accountability.

**R3_Understanding_or_Explanation_Required** — The contributor must perform a
cognitive action on the work: understand it, explain it, justify it, or defend
it. This is triggered by *must understand*, *be able to explain*, *justify*,
*defend*, or *reason about* the AI-assisted work. It requires cognitive
engagement but no concrete validation, testing, or evidence action.

**R4_Validation_or_Evidence_Required** — The contributor must take a concrete
verification action — review, test, validate, reproduce, edit, or provide
evidence. This is triggered by *review*, *inspect*, *test*, *validate*,
*verify*, *reproduce*, *edit*, *check*, *provide evidence*, *proof-of-concept*,
or *reproduction log*, an action explicitly tied to AI work.

## A. Attribution

Attribution captures source, rights, license, and provenance rules, ordered by
the specificity of the compliance object.

**A1_Not_Mentioned** — No copyright, license, provenance, DCO/CLA, or
source-rights rule is mentioned.

**A2_General_IP_or_Source_Responsibility** — A generic legal, IP, or source
responsibility is stated without naming a specific compliance object, for
example *ensure legality*, *no IP infringement*, *responsible for IP*, *source
cleanliness*, or *third-party material*, without reference to license, DCO/CLA,
or tool terms.

**A3_License_or_Source_Compatibility_Required** — The policy names a specific
compliance object that the AI output must satisfy: the project license,
copyright, DCO/CLA, sign-off, tool terms of service, or third-party license
compatibility.

**A4_Documented_Rights_or_Provenance_Required** — The policy requires
documented records of rights or provenance — *document provenance*, *source
records*, *attribution records*, *certification*, or *right-to-submit evidence*
— records that make source rights auditable.

## C. Constraints

Constraints capture ex ante limits on acceptable AI use, ordered by the breadth
of the restriction: no restriction (C1) → narrow form limits (C2) →
context/channel limits (C3) → broad exclusion (C4). The decisive question at
each boundary is the target of the limit. A bound on *what kind of content* is
C2; a bound on *where AI may appear* is C3; an outright refusal to accept
AI-assisted contributions at all is C4. When a policy restricts both form and
context/channel, assign the broader level (C3), since a channel-wide ban covers
more than a form-only limit (see the C tie-break in General Rules).

**C1_No_Substantive_Restriction** — AI use is allowed or not restricted. No
form or channel ban is present, and AI use is permitted generally.

**C2_Form_Restricted** — AI use is restricted by output form, a narrow limit on
the type, quality, or quantity of content that still allows ordinary
AI-assisted collaboration. The restriction targets form features such as bulk
output, slop or low-effort content, full-AI-generated submissions, large
changes, or content the contributor does not understand (including "do not rely
on an LLM as the sole basis"). Note that "do not submit code you do not
understand" is C2: the subject is the submission limit (*don't-submit*), not
the cognitive action (*understand*), which would belong in R.

**C3_Context_or_Channel_Restricted** — AI use is restricted in named channels
or contexts, a broader limit that removes AI from an entire channel while
ordinary AI-assisted contribution elsewhere remains allowed — for example, the
policy allows ordinary PR contributions but restricts AI in other aspects such
as issues, PR descriptions, reviews, comments, commit messages, security
reports, vulnerability submissions, docs, media, maintainer communication, or
autonomous-agent interaction with workflows.

**C4_Generally_Excluded** — AI-assisted contributions are explicitly and
blanket-prohibited. The policy very directly refuses to accept any form of
AI-assisted contribution, without needing to name specific channels or forms.
This requires an explicit prohibition statement (for example *not accepted*,
*prohibited*, *banned*, *we don't accept*, or *AI contributions are not
permitted*); softer language such as "strongly discouraged" or "limited",
without an outright ban, stays in C3.

## E. Enforcement

Enforcement captures the consequences for violation, ordered by severity.

**E1_Not_Mentioned** — No consequence is stated. The policy gives rules but
does not say what happens on violation.

**E2_Remediation_or_Review_Limitation** — Violation triggers a soft,
non-rejection review action: maintainers may ask the contributor to revise,
fix, disclose more, or narrow scope, or review may be delayed, deprioritized,
paused, limited, withheld, or in mild cases simply ignored. Soft modals such as
*may* or *can* count. This does not include rejecting or closing the
submission, which is E3.

**E3_Current_Submission_Rejected_or_Closed** — The current PR, issue, or
submission may be closed, rejected, declined, hidden, removed, or not accepted,
or subject to any other form of rejection or closure of the current
contribution. "May reject" counts as E3, because rejection is an E3 action even
when stated probabilistically.

**E4_Future_Participation_Restricted** — Future participation may be restricted
if the contributor violates the policy, including banning, blocking,
suspending, blacklisting, restricting future submissions, or loss of
privileges.

## Boundary Rules

- **T2 vs T3:** T2 is purely optional (*may / can / welcome to / encouraged
  to*); *should* and *are expected to* signal a requirement and belong in T3.
- **T3 vs T4:** T4 requires a requirement modal plus a named detail category;
  T3 is a bare mandatory disclosure with no named category.
- **R is categorical, not ordinal:** R2/R3/R4 are different types of
  responsibility, not increasing strength; if several apply, choose the most
  concrete (R4 > R3 > R2).
- **C2 vs R:** "do not submit X" (a submission limit) = C; "must review /
  understand / test" (a required action) = R. "Don't submit what you don't
  understand" = C2.
- **C3 vs C4:** C4 requires an explicit blanket prohibition; named-channel bans
  without a blanket statement = C3.
- **E2 vs E3:** revise/delay/pause = E2; reject/close = E3. "May reject" = E3.
- **R2 vs R3:** nominal accountability ("you are responsible") = R2; a required
  cognitive action ("must understand/explain") = R3.
- **A2 vs A3:** generic IP responsibility = A2; a named compliance object
  (license/DCO/CLA/tool-terms) = A3.
- T vs A: AI-use disclosure is T; rights/source/provenance claims are A.
- T vs R: tool/prompt/process visibility is T; correctness evidence is R.
- C vs E: C defines what is allowed before violation; E defines what happens
  after violation.
- Assisted-by alone is T, not A; sign-off / DCO/CLA / license compatibility /
  provenance certification is A.

## External References

When the retained text only points to another policy, retrieve the referenced
policy before labeling when possible, and label the resolved policy text plus
the local AI-policy statement. If retrieval is not possible, label only the
retained local text and flag the row for manual review outside the model
output.

## General Rules

- Label only the retained AI policy text.
- Ignore ordinary contribution rules unless explicitly linked to AI use.
- Ignore agent workflow instructions unless they govern human-submitted
  contributions or project-facing communication.
- Return exactly one label for each of the five TRACE dimensions.
- If multiple labels seem possible within a dimension, choose the highest
  applicable level for that dimension (for R, "highest" means the most concrete
  responsibility type per the priority R4 > R3 > R2).
- **C tie-break:** when a policy restricts both output form (C2) and
  context/channel (C3), assign C3 — a channel-wide ban is broader than a
  form-only limit.
- Do not return explanations, notes, evidence, confidence, families, or any
  fields other than the five requested JSON fields.
