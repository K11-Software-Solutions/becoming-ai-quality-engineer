# Groundedness labelling rubric

This rubric is what reviewers apply when labelling [`human_labels.jsonl`](human_labels.jsonl). It exists because two careful reviewers will disagree without one: if humans can't agree on what "correct" means, an automated judge has no target to agree with.

## The question

> **Is every claim in the ANSWER supported by the CONTEXT?**
> Label `grounded` or `not_grounded`. Judge support only. Do not judge style, length or helpfulness.

## Rules

| # | Rule | Label |
|---|---|---|
| R1 | Every claim is stated in, or directly implied by, the context | grounded |
| R2 | A faithful paraphrase passes, even if it uses none of the context's words | grounded |
| R3 | An approximation passes only if it is exact in meaning ("a month" for "30 days" passes; "about 50" for "48" fails) | grounded / not_grounded |
| R4 | **Omitting** information is not a groundedness failure (completeness is a separate metric) | grounded |
| R5 | Any **changed number, date, limit or unit** fails, however small the change | not_grounded |
| R6 | A **dropped, added or moved negation** fails ("not available" → "available") | not_grounded |
| R7 | One unsupported claim fails the whole answer, even if every other claim is right | not_grounded |
| R8 | A claim the context neither states nor implies fails, even if it is true in the real world | not_grounded |
| R9 | A confident answer to a question the context cannot answer fails | not_grounded |
| R10 | If you cannot decide after applying R1–R9, label `ambiguous` and write why. Ambiguous items are fixed (better question or context) or removed, never forced | ambiguous |

## Examples

Context for the first examples: *"NimbusNotes offers a full refund within 30 days of the first payment on any paid plan."*

| Answer | Label | Rule |
|---|---|---|
| "NimbusNotes offers a full refund within 30 days of the first payment on any paid plan." | grounded | R1 |
| "You can get your money back for a month after you first pay." | grounded | R2, R3 |
| "Refunds are available within 30 days." | grounded | R4: "full" and "first payment" omitted |
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

## Process

1. **Calibrate.** Before labelling, both reviewers label the examples above and compare. Discuss every difference until you agree on the rule.
2. **Label independently.** Each reviewer labels the full set without seeing the other's labels. Raw labels are kept in [`reviewer_labels.jsonl`](reviewer_labels.jsonl).
3. **Measure reviewer-to-reviewer agreement** (Cohen's kappa). This is the ceiling for any automated judge. `python -m evals.judge.judge_agreement` reports it.
4. **Adjudicate every disagreement** against the rubric, record the rule that decided it, and write the final label to `human_labels.jsonl`.
5. **Update the rubric** whenever an adjudication needed a rule that wasn't written down. The disagreements are the rubric's test cases.
