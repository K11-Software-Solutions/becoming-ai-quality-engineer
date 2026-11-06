# 11. Pass/Fail or Graded? Building and Validating a Completeness Grader

> **Series:** Becoming an AI Quality Engineer · [Index](../README.md#article-index) · Previous: [10](10-using-the-three-reports.md)

Most reviewer disagreements are not about what the source says. They are about **how strict to be**. When this repo's two reviewers disagreed on whether an answer was grounded, three of the four adjudicated cases came down to strictness, and the strictest question of all was this one: *if an answer is true but leaves something out, is it still a good answer?*

This article follows that question all the way through, in the order it happened in the repo:

1. **Decide the rule type:** pass/fail rules for truth, a graded score for completeness (section 1).
2. **Collect graded scores** from two reviewers and adjudicate them (section 2).
3. **Measure a grader against them** with two different agreement numbers (section 3).
4. **Find out why the first grader was wrong**, and fix it (sections 4 and 5).
5. **Use the graded scores for severity**, and see what grading buys (section 6).
6. **Keep the history honest:** labels and grader in separate commits (section 7).

Each section has a plain-language part and, where it matters, a part for the statistically minded.

---

## 1. Two questions, two kinds of rule

**In plain words.** "Is anything in this answer false?" and "Does this answer leave out something the user needs?" sound alike, but they behave differently.

- A slightly wrong price is not *partly* acceptable. Truth works best as **pass/fail rules**: a changed number fails, a dropped "not" fails, however small.
- Omission really is a matter of degree, and of risk. Leaving out "and attachments" from an answer about export formats is harmless; leaving out "of the first payment" from an answer about refund deadlines can cost someone money. Completeness works best as a **graded score with a pass mark that depends on risk**.

So the rubric ([`evals/judge/RUBRIC.md`](../evals/judge/RUBRIC.md), v2) has two parts:

| Part | Question | Rule type |
|---|---|---|
| A. Groundedness | Is anything false or unsupported? | pass/fail rules R1–R10 |
| B. Completeness | Is anything the user needs missing? | score 0–3, pass mark by risk tier |

The completeness scale:

| Score | Meaning |
|---|---|
| **3** | Complete: nothing in the source would change what the user does |
| **2** | Minor omission: a secondary detail is missing; still safe to act on |
| **1** | Material omission: a condition, limit, exception or required step is missing |
| **0** | Does not answer the question |

And the pass marks, a **policy decision** recorded in the rubric rather than left to each reviewer's taste:

| Tier | Topics | Pass at |
|---|---|---|
| High risk | money, account security, data deletion and export, legal or policy limits | **3 only** |
| Standard | how-to, features, sync, convenience limits | **2 or more** |

Strictness does not disappear. It moves from each reviewer's head into one written, versioned decision that anyone can see and challenge.

---

## 2. Collecting the scores

**In plain words.** Completeness is scored only for answers that already passed groundedness: a false answer fails regardless of how complete it is. In this repo that is 11 of the 24 labelled answers. Two reviewers scored each one independently ([`completeness_labels.jsonl`](../evals/judge/completeness_labels.jsonl); the scores are illustrative, written for this learning lab).

Adjudication is needed when the two scores differ by 2 or more, or when they fall on opposite sides of the pass mark. Two cases needed it, and both are instructive:

- **h02** (high risk): *"You can get your money back for a month after you first pay."* Reviewer A gave 3; B gave 2, noting that "full" and "any paid plan" were dropped. For a high-risk topic, 2 versus 3 is the difference between pass and fail. Rule C5 (when unsure, give the lower score) decided it: **2, fails**.
- **h13** (standard): *"The web app does not support offline editing."* A gave 3; B gave 1, treating "requires an internet connection" as a required condition. The answer already says what the user asked: you can't edit offline. Rule C3 (a secondary detail is at most a 2) decided it: **2, passes**.

Both reviewers knew the rules. They disagreed about which kind of omission they were looking at, which is exactly what the rubric's examples exist to calibrate.

---

## 3. Two agreement numbers, because there are two questions

**In plain words.** For pass/fail labels, one agreement number (Cohen's kappa) is enough. For graded scores you need two, because "does the grader agree?" splits in two:

1. **Does it rank answers like the reviewers?** A grader that says 2 where people say 3 is nearly right; one that says 0 is badly wrong. *Weighted kappa* gives partial credit for near misses.
2. **Does it make the same decision?** Apply the tier's pass mark to both, then compare pass with pass and fail with fail. This is what actually ships.

They can disagree in both directions. A grader can be one point low everywhere and still decide correctly wherever the pass mark is far away, or be close on average and wrong exactly at the pass mark. So `python -m evals.judge.judge_agreement` now reports both, per tier, and lists **false passes** (the dangerous direction) separately from **false fails**.

The reviewers themselves set the ceiling:

| Reviewer A vs B | Value |
|---|---|
| Weighted kappa | 0.45 |
| Exact same score | 0.64 |
| Same pass/fail decision | 0.82 |

Moderate agreement on the score and better agreement on the decision is typical: people differ on 2 versus 3 more often than on whether an answer is good enough.

**For the statistically minded.** Quadratic-weighted kappa on K = 4 ordered categories uses disagreement weights w_ij = (i − j)² / (K − 1)²:

```text
κ_w  =  1 − Σ w_ij · O_ij  /  Σ w_ij · E_ij
```

where O is the observed joint distribution and E the product of the marginals. A one-point miss costs 1/9 of a three-point miss. Pass/fail agreement is computed after mapping each score through the tier threshold. With n = 11, any of these numbers has a confidence interval wide enough to make it a smoke test, not a measurement, which is why the report is informational and does not gate CI.

---

## 4. The first grader, and why it was harsh

**In plain words.** The first automated grader ([`evals/completeness.py`](../evals/completeness.py), first version) did the obvious thing. Keep the source sentences that relate to the question, count how many of their words appear in the answer, and map that share onto 0–3.

| | Grader vs final scores |
|---|---|
| Weighted kappa | 0.68 |
| Exact same score | 0.64 |
| Same pass/fail, high-risk tier | 7 of 7 |
| Same pass/fail, standard tier | **2 of 4** |
| False passes | none |
| False fails | h13, h24 |

The high-risk decisions were all right, and there were no false passes. But half the standard-tier answers were wrongly failed. Looking at the words each answer was "missing" showed why:

| Answer | Final | Grader | Words counted as missing |
|---|---|---|---|
| h09: "Exports arrive as a ZIP file with Markdown files and attachments." | 3 | 2 | *delivered, containing* |
| h24: "Exports come as a ZIP archive of Markdown files." | 2 | 1 | *delivered, containing, attachments* |
| h13: "The web app does not support offline editing." | 2 | 1 | *web access, requires, internet, connection* |

Two separate problems:

1. **Every word cost the same.** Losing "delivered" or "containing" (just how the fact was phrased) cost as much as losing "attachments" (an actual piece of information). An honest paraphrase was punished for rewording.
2. **A separate sentence was treated as part of the answer.** In h13, "Web access requires an internet connection" was one clause and "the web app does not support offline editing" another. The answer covered the clause that answers the question, but the grader averaged the two together.

This is the harshness the rubric warns about from the other side: a grader that fails honest paraphrases quietly pushes teams towards answers that copy the source word for word.

---

## 5. The fix

**In plain words.** The new grader follows the rubric's own rules instead of a single word count:

1. **Split the source into clauses** and keep those related to the question. The clause closest to the question is the **direct answer** (rule C1: judge against the question asked).
2. **0** if the answer barely covers the direct answer.
3. **1** if a **number or a "not"** from the relevant clauses is missing. Those are the limits, deadlines and exceptions of rule C2.
4. **2** if anything else is missing (rule C3: a secondary detail).
5. **3** if everything relevant is covered.

Word matching also became fairer: "supported" now matches "supports", and a short list of linking verbs ("delivered", "containing", "includes") is ignored, because leaving them out is rewording, not omission.

| On the 11 labelled answers | First grader | Fixed grader | Reviewer A vs B |
|---|---|---|---|
| Weighted kappa | 0.68 | 0.70 | 0.45 |
| Exact same score | 0.64 | 0.82 | 0.64 |
| Same pass/fail decision | 0.82 | **1.00** | 0.82 |
| False passes | none | none | |
| False fails | h13, h24 | none | |

Two scores still differ, and both are worth understanding, because they mark the limits of any word-based grader:

- **h02: grader 0, final 2.** "A month after you first pay" means "within 30 days of the first payment", but no word or number matches. Recognising an approximation needs meaning, not words. The decision is still right: both fail the high-risk bar.
- **h20: grader 2, final 1.** *"SMS codes are not supported for two-factor authentication"* leaves out that an authenticator app is the alternative. People see a missing required step; the grader sees a missing clause with no number or "not" in it, so it calls the omission minor. The decision is still right: 2 also fails the high-risk bar. But on a standard-tier topic, this same weakness would produce a **false pass**. That is the case to watch for when new labels arrive.

### Read these numbers with suspicion

The fixed grader now agrees with the final scores more closely than the two reviewers agree with each other. Article 04 explains why that is a warning sign rather than a triumph: **the grader was fixed while looking at these 11 answers, and judged on the same 11 answers.** Some of the gain is genuine (the rubric's own rules are a better design than a word count) and some is fitting to the labels. The only way to tell them apart is to score answers the grader has never seen. Until then, quote the numbers with that caveat attached, as the commit message does.

---

## 6. What graded scores buy for severity

**In plain words.** Article 09 showed that measuring how strict a grader is takes a lot of ratings: about 1,700 per answer type to see a modest lean with pass/fail ratings. A 0–3 score says not only "pass" or "fail" but *how far* from the bar, so each rating carries more evidence and you need fewer.

The severity add-on now fits graded ratings too (`python -m evals.severity.run_graded`), using the real completeness grader against simulated reviewers on the grounded answers in the item bank. To make the comparison fair, it also takes the **same** ratings, cuts them to pass/fail at score 2, and fits the pass/fail model:

| | Graded 0–3 | Same ratings as pass/fail |
|---|---|---|
| Evidence (information) per rating | 0.29 | 0.04 |
| Ratings to detect a 0.3-logit lean | about 600 | about 4,000 |
| Verdict on paraphrased answers | softer (z −3.3) | can't tell (z −1.7) |
| Verdict on answers with omissions | softer (z −3.5) | softer (z −3.6) |

Grading helps most where answers sit near the top of the scale, as paraphrases do. Pass/fail sees only "passed"; the score still separates a 2 from a 3. Where the evidence is already strong (omissions), the two are about equal. The finding is the same either way: the grader is **softer than reviewers on answers with omissions**, the h20 weakness from section 5 seen at scale.

Two conditions apply. The reviewers here are simulated, so this shows the method, not what real people would do. And grading only helps if reviewers can use the scale consistently: at a reviewer-to-reviewer weighted kappa of 0.45, the extra detail is partly noise. Calibrate on the rubric's examples first.

The full treatment, including the model, is in [article 09, section 7.1](09-measuring-grader-severity.md); the report is in [`docs/sample-reports/graded-severity-report.md`](../docs/sample-reports/graded-severity-report.md).

**For the statistically minded.** The graded model is a many-facet rating scale (Andrich) model, log[P(k)/P(k−1)] = β_i − ρ_r − τ_k with shared thresholds τ, fitted with the same choices as the binary model ([`evals/severity/rsm.py`](../evals/severity/rsm.py)). A rating's information about ρ is the model variance of the score, which for four categories can exceed the binary maximum of 0.25. The two models' logit scales differ, so compare z = lean / SE, not raw logits. One detail surprised me: the grader's overall severity did not change when the grader was fixed. That is not a bug. In a Rasch-family model a rater's total score is a sufficient statistic for its severity, and the fix moved points between answer types (fewer 1s, more 2s on paraphrases) while leaving the total almost unchanged. **The overall number hid the change; the per-type leans showed it.** It is the same lesson as articles 04 and 09, from a different angle.

---

## 7. Keeping the history honest

A grader that is tuned to its labels, or labels that are quietly edited to suit a grader, both produce agreement that means nothing. The repo's CI check (`python -m evals.change_hygiene`) fails any commit that changes label files and grader files together. This piece of work therefore landed as a sequence of separate commits, each one reviewable on its own:

| Step | Commit | Touches |
|---|---|---|
| Rubric v2: graded completeness, tier thresholds | [`74f8770`](https://github.com/K11-Software-Solutions/becoming-ai-quality-engineer/commit/74f8770) | labels (rubric) |
| Reviewer completeness scores, two adjudications | [`4cb4aaa`](https://github.com/K11-Software-Solutions/becoming-ai-quality-engineer/commit/4cb4aaa) | labels |
| First grader, graded agreement in the judge check | [`00555fb`](https://github.com/K11-Software-Solutions/becoming-ai-quality-engineer/commit/00555fb) | grader |
| Graded severity model | [`bdcc0c6`](https://github.com/K11-Software-Solutions/becoming-ai-quality-engineer/commit/bdcc0c6) | severity add-on |
| Grader fix: clause by clause | [`d2e9453`](https://github.com/K11-Software-Solutions/becoming-ai-quality-engineer/commit/d2e9453) | grader |

Anyone can check out the commit before the fix, run the judge check, and see the two false fails for themselves. The labels never moved to meet the grader.

---

## Key takeaways

- **Use pass/fail rules for truth and graded scores for completeness.** A wrong fact is never partly acceptable; an omission is a matter of degree and risk.
- **Write strictness down as a policy:** a pass mark per risk tier, versioned in the rubric, not left to each reviewer.
- **Graded scores need two agreement numbers:** weighted kappa (does it rank like people?) and pass/fail after the threshold (does it decide like people?). Read the decision first: it is what ships.
- **Look at what the grader counts as missing.** Both failures here were visible in a single table of "missing words".
- **Build the grader from the rubric's rules,** not from a generic similarity score.
- **Distrust a fix judged on the labels it was tuned on.** Agreement above the human ceiling is a warning.
- **Graded ratings make severity studies cheaper,** if reviewers can use the scale consistently.
- **Change labels and grader in separate commits,** so every gain can be traced and checked.

---
Back to the [index](../README.md#article-index).
