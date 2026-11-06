# Labelling rubric (v2: groundedness rules + graded completeness)

This rubric is what reviewers apply when labelling [`human_labels.jsonl`](human_labels.jsonl). It exists because two careful reviewers will disagree without one: if humans can't agree on what "correct" means, an automated judge has no target to agree with.

It has two parts, because they are different questions with different kinds of answer:

| Part | Question | Kind of rule | Why |
|---|---|---|---|
| A. Groundedness | Is anything in the answer **false or unsupported**? | **Pass/fail rules** | A slightly wrong price is not partly acceptable |
| B. Completeness | Does the answer leave out **something the user needs**? | **Graded score with a threshold per risk tier** | How much omission to forgive is a matter of degree, and of risk |

Most reviewer disagreements are about strictness, not about what the source says; in this repo's adjudicated set, three of four were. Part A removes strictness from questions of truth; Part B makes strictness about omission explicit and sets it by risk.

---

## Part A. Groundedness (pass/fail, unchanged from v1)

> **Is every claim in the ANSWER supported by the CONTEXT?**
> Label `grounded` or `not_grounded`. Judge support only. Do not judge style, length, helpfulness or completeness.

| # | Rule | Label |
|---|---|---|
| R1 | Every claim is stated in, or directly implied by, the context | grounded |
| R2 | A faithful paraphrase passes, even if it uses none of the context's words | grounded |
| R3 | An approximation passes only if it is exact in meaning ("a month" for "30 days" passes; "about 50" for "48" fails) | grounded / not_grounded |
| R4 | **Omitting** information is not a groundedness failure; score it in Part B | grounded |
| R5 | Any **changed number, date, limit or unit** fails, however small the change | not_grounded |
| R6 | A **dropped, added or moved negation** fails ("not available" → "available") | not_grounded |
| R7 | One unsupported claim fails the whole answer, even if every other claim is right | not_grounded |
| R8 | A claim the context neither states nor implies fails, even if it is true in the real world | not_grounded |
| R9 | A confident answer to a question the context cannot answer fails | not_grounded |
| R10 | If you cannot decide after applying R1–R9, label `ambiguous` and write why. Ambiguous items are fixed (better question or context) or removed, never forced | ambiguous |

### Examples

Context for the first examples: *"NimbusNotes offers a full refund within 30 days of the first payment on any paid plan."*

| Answer | Label | Rule |
|---|---|---|
| "NimbusNotes offers a full refund within 30 days of the first payment on any paid plan." | grounded | R1 |
| "You can get your money back for a month after you first pay." | grounded | R2, R3 |
| "Refunds are available within 30 days." | grounded | R4: "full" and "first payment" omitted (see Part B) |
| "Refunds are available within 60 days of the first payment." | **not_grounded** | R5 |
| "Refunds are available within about two months." | **not_grounded** | R3, R5 |

Context: *"Web access requires an internet connection; the web app does not support offline editing."*

| Answer | Label | Rule |
|---|---|---|
| "The web app does not support offline editing." | grounded | R1, R4 |
| "You can't edit offline in the web app." | grounded | R2: negation kept, reworded |
| "The web app supports offline editing." | **not_grounded** | R6 |

Context: *"The Pro plan costs 8 US dollars per month or 80 US dollars per year. Pro includes unlimited notebooks, 20 GB of storage, and sync on unlimited devices."*

| Answer | Label | Rule |
|---|---|---|
| "Pro costs 8 US dollars per month and includes 20 GB of storage." | grounded | R1, R4 |
| "Pro costs 8 US dollars per month or 80 US dollars per year and includes 200 GB of storage." | **not_grounded** | R5, R7 |
| "Pro includes unlimited notebooks and a dedicated account manager." | **not_grounded** | R7, R8 |

Context: *"The desktop and mobile apps work offline."*

| Answer | Label | Rule |
|---|---|---|
| "The desktop apps work offline on Windows, macOS and Linux." | **not_grounded** | R8, R9: platforms not stated |

---

## Part B. Completeness (graded 0–3, threshold by risk tier)

> **Given the user's question, does the answer include what the user needs from the context?**
> Score only answers that are grounded under Part A. A `not_grounded` answer fails regardless of completeness.

### Scale

| Score | Meaning | Test |
|---|---|---|
| **3** Complete | Everything the user needs to act correctly is there | Nothing in the context would change what the user does |
| **2** Minor omission | A secondary detail is missing; the answer is still correct and safe to act on | The missing detail is nice to know, not need to know |
| **1** Material omission | A **condition, limit, exception or required step** is missing, so a user could act wrongly | Acting on the answer alone could lead to the wrong outcome |
| **0** Not answered | The answer does not address the question | (Refusals of answerable questions are counted separately as over-refusals) |

Completeness rules:

| # | Rule |
|---|---|
| C1 | Judge against the **question asked**, not against everything the context says. Leaving out unrelated facts is not an omission |
| C2 | A missing **condition, limit, exception, deadline or required step** is at most a 1 |
| C3 | A missing **secondary detail** that does not change what the user should do is at most a 2 |
| C4 | Several minor omissions that together change what the user would do count as one material omission (score 1) |
| C5 | If you cannot decide between two scores, give the **lower** one and write why |

### Thresholds by risk tier (policy decision, approved by the project owner on 2026-11-06)

| Tier | Answer topics | Pass at | Why |
|---|---|---|---|
| **High risk** | money (pricing, billing, refunds), account security and access, data deletion and export, legal or policy limits | **score 3 only** | An omitted condition here costs users money, access or data |
| **Standard** | how-to, features, sync, integrations, limits that only affect convenience | **score ≥ 2** | A minor omission is acceptable; a material one is not |

The tier follows the **topic of the answer**, not its wording. When an answer spans tiers, the stricter tier applies. Thresholds are set by risk, recorded here, and changed only with the rubric version.

### Examples

Question: *"How long do I have to get a refund?"* (high risk). Context: *"NimbusNotes offers a full refund within 30 days of the first payment on any paid plan. Refunds requested after 30 days are not available for monthly plans. Annual plans can receive a prorated refund…"*

| Answer | Score | Pass? | Rule |
|---|---|---|---|
| "Within 30 days of the first payment. After that, monthly plans can't be refunded; annual plans get a prorated refund." | 3 | yes | C1 |
| "You get a full refund within 30 days of your first payment." | 1 | **no** | C2: omits the exception for annual plans |
| "Refunds are available within 30 days." | 1 | **no** | C2: omits "of the first payment" (the deadline's start) |

Question: *"What format are exports in?"* (standard). Context: *"Exports are delivered as a ZIP file containing Markdown files and attachments."*

| Answer | Score | Pass? | Rule |
|---|---|---|---|
| "A ZIP file of Markdown files and attachments." | 3 | yes | |
| "A ZIP file of Markdown files." | 2 | yes | C3: attachments are a secondary detail for this question |
| "You can export your notes from Settings." | 0 | **no** | does not answer the format question |

Question: *"Can I get a refund for an App Store purchase?"* (high risk). Context: *"Purchases made through the Apple App Store or Google Play must be refunded through that store, not through NimbusNotes support."*

| Answer | Score | Pass? | Rule |
|---|---|---|---|
| "Yes, but through the App Store, not through NimbusNotes support." | 3 | yes | |
| "Yes, App Store purchases can be refunded." | 1 | **no** | C2: omits the required step (where to request it) |

---

## Process

1. **Calibrate.** Before labelling, both reviewers label and score the examples above and compare. Discuss every difference until you agree on the rule or the score.
2. **Label independently.** Each reviewer labels Part A and scores Part B for the full set without seeing the other's work. Raw labels are kept in [`reviewer_labels.jsonl`](reviewer_labels.jsonl).
3. **Measure reviewer-to-reviewer agreement.** Cohen's kappa for Part A; for Part B, weighted agreement on the 0–3 scores **and** agreement on pass/fail after applying the tier threshold. This is the ceiling for any automated judge. `python -m evals.judge.judge_agreement` reports both parts.
4. **Adjudicate.** Part A: every disagreement. Part B: any pair of scores that differ by 2 or more, or that fall on opposite sides of the tier threshold. Record the rule that decided it and write the final label and score to `human_labels.jsonl`.
5. **Update the rubric** whenever an adjudication needed a rule that wasn't written down. The disagreements are the rubric's test cases.
6. **Change the rubric and the labels in their own commits**, separately from any grader change (CI enforces this). When a rule or threshold changes, find the labels it affects and re-adjudicate them.

---

## Change log

- **v2, scores collected (2026-11-06):** completeness scores for the 11 grounded answers added in [`completeness_labels.jsonl`](completeness_labels.jsonl), two adjudications (h02 by C5, h13 by C3). No rule changed.
- **v2 (2026-11-06):** Part A unchanged; R4 now points to Part B. Added Part B (graded completeness with per-tier thresholds), C1–C5, examples, and graded-agreement and adjudication steps in the process. **Existing groundedness labels remain valid:** no Part A rule changed, so no re-adjudication is needed. Completeness scores have not been collected yet.
- **v1:** groundedness rules R1–R10 with examples and the two-reviewer process.
