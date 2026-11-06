# 09. Measuring Grader Severity: Beyond Agreement Scores

> **Series:** Becoming an AI Quality Engineer · [Index](../README.md#article-index) · Previous: [08](08-portfolio-and-interview-prep.md) · Builds on: [04, section 7](04-evaluation-skills.md#7-validate-the-evaluator-itself)

Article 04 validated the AI judge by asking **how often it agrees with humans**. This article asks a harder and more useful question: **where does each grader sit?** Is the judge consistently stricter or more lenient than people, on which kinds of answer, and how sure can we be?

The code is in [`evals/severity/`](../evals/severity/) and a full report is in [`docs/sample-reports/severity-report.md`](../docs/sample-reports/severity-report.md).

Each section has two layers:

- **In plain words**, for anyone: QA engineers, product managers, reviewers.
- **For the statistically minded**, with the model, formulas and assumptions. Skip these on a first read; the plain layer stands on its own.

---

## 1. Why agreement is not enough

**In plain words.** Imagine two kitchen thermometers. Thermometer A always reads 2 degrees too high. Thermometer B is accurate on average but jumps around by a degree. If you only count how often they "agree within a degree", both look mediocre, and you cannot tell which problem each one has. Yet the fixes are completely different: you can correct A by subtracting 2; you cannot correct B.

AI graders have the same two kinds of problem:

- a **lean**: consistently too strict or too lenient, often only on some kinds of answer;
- **noise**: disagreeing in no particular direction.

An agreement score mixes them together. Worse, a lean can be *hidden* in an agreement score: the judge can be too strict on one kind of answer and too lenient on another, and the two cancel out into a respectable number. That is exactly what happened in article 04: a fix raised agreement, but the lean only moved somewhere else.

**For the statistically minded.** Cohen's kappa summarises a confusion matrix relative to chance. It is a function of both the off-diagonal *asymmetry* (systematic lean: false passes versus false fails) and the *total* off-diagonal mass (disagreement). Different combinations of the two give the same kappa, and stratifying kappa by item type only partitions the problem; it does not separate the two components. Severity is instead modelled as a **location parameter** with a standard error, estimated jointly with item difficulty, so that a rater's lean is not confounded with the items it happened to rate or with a change in the system being graded.

---

## 2. Five ideas you need

| Idea | In plain words | Statistically |
|---|---|---|
| **Severity** | How strict a grader is. Higher = says "not grounded" more often than the other graders would on the same answers | A rater location parameter ρ on the logit scale |
| **Item ease** | How obviously correct an answer looks. A verbatim quote is very easy to pass; a cleverly changed number is hard to spot | An item location parameter β on the same scale |
| **Logit** | A way of writing chances on a scale where differences add up. 0 = 50/50; +2 ≈ 88%; −2 ≈ 12% | log(p / (1 − p)) |
| **Standard error (SE)** | The error bar on an estimate. Small SE = we know the value well; large SE = we are mostly guessing | √ of the inverse Fisher information at the estimate |
| **Inconclusive** | "We cannot tell yet." The honest answer when the error bar is wider than the effect | The 95% interval (estimate ± 1.96 SE) contains zero |

---

## 3. The model

**In plain words.** Every answer has an "ease" (how clearly it is supported by the source) and every grader has a "strictness". The chance that a grader passes an answer depends only on the **gap** between the two. A very easy answer gets passed by almost everyone; a strict grader needs an answer to be easier before it passes.

A worked example on the logit scale:

| Answer ease | Grader strictness | Gap | Chance of "grounded" |
|---|---|---|---|
| 2.0 (clear) | 0.0 (average human) | 2.0 | 88% |
| 2.0 (clear) | 1.57 (the AI judge) | 0.43 | 61% |
| −1.5 (subtle error) | 0.0 (average human) | −1.5 | 18% |
| −1.5 (subtle error) | −1.44 (judge on swapped entities) | −0.06 | 49% |

So the same clear, correct answer that an average human passes 88% of the time, the judge passes only 61% of the time: it is stricter. On one kind of subtle error, though, the judge passes it about half the time where a human passes it 18% of the time: it is more lenient there. **One grader, harsh in one place and lenient in another.**

**For the statistically minded.** This is a dichotomous many-facet Rasch model (Linacre, 1989) with two facets:

```text
logit P(X_ir = 1)  =  β_i  −  ρ_r
```

where X_ir = 1 if rater r labels item i "grounded", β_i is item ease and ρ_r is rater severity. The scale has one free location, fixed by setting the mean severity of the reference raters to zero, so every severity reads as "relative to the average human". Per-type lean is estimated by a rater-by-stratum interaction (bias) term τ_rs with β held fixed:

```text
logit P(X_ir = 1)  =  β_i  −  ρ_r  −  τ_r,s(i)
lean_s  =  (ρ_judge + τ_judge,s)  −  (mean reference ρ + τ_reference,s)
```

with SE(lean_s) = √(SE_judge,s² + SE_reference,s²) and a verdict of *harsher* or *softer* only when |lean_s| > 1.96 · SE.

---

## 4. Calibrate on the people, then measure the machine

**In plain words.** To test a thermometer you compare it against a reference you trust, and you do not let the thermometer under test decide what the right temperature was. The same applies here: **how easy each answer is gets worked out from the human reviewers only**, and the AI judge is then measured against that.

This mattered in practice. In the first version the judge's ratings were included when working out answer ease. The judge wrongly rejects many correct answers that begin with "Yes.", so those answers looked "harder" than they are, and the humans then appeared lenient on them. The judge's mistake had leaked into the yardstick.

**For the statistically minded.** Including the measured rater in item calibration lets its systematic errors bias β_i in the direction of its lean, which attenuates the estimated lean and induces spurious stratum effects in the reference raters. The fix is anchored calibration: estimate β from reference raters only, then estimate ρ_judge and τ_judge,s conditional on the fixed β. The reference raters' stratum shifts should then be approximately zero, which is a useful diagnostic; in the sample report they are.

---

## 5. Getting enough evidence: items labelled by construction and shared anchors

**In plain words.** Hand-labelling hundreds of answers is slow and expensive. So the testbed **builds** answers whose correct label is known from how they were made. It takes a true sentence from the help articles and changes it in one controlled way:

| Change | Example | Correct label |
|---|---|---|
| none (verbatim) | "Password reset links expire after 1 hour." | grounded |
| shortened (omission) | "Pro includes unlimited notebooks." | grounded |
| reworded (paraphrase) | "The Free plan comes with up to 3 notebooks…" | grounded |
| number changed | "Pro accounts can make 600 API requests per minute." | not grounded |
| negation flipped | "It is available on the Free plan." | not grounded |
| claim added | "…, and this includes free 24/7 phone support." | not grounded |
| name or unit swapped | "Team accounts can make 300 requests per hour…" | not grounded |

That gives 628 items without anyone labelling them. People are still needed, though: the items measure the **graders**, so graders must rate them.

Not every reviewer has to rate everything. Each reviewer rates a small set of **shared anchor answers** (like the common questions on different versions of an exam) plus their own sample. The shared answers put everyone on the same scale.

**For the statistically minded.** The design is a connected, incomplete rating design: the judge rates all items; each reference rater rates a stratified set of shared anchors plus a random disjoint-ish sample. Connectedness through anchors identifies all parameters on one scale. Two cautions: by-construction items are cleaner and more homogeneous than real model outputs, so mix in real answers before drawing conclusions about a production judge; and the seven types are **nominal failure-mode strata, not an ordered difficulty hierarchy**. A hierarchical scale (ordering tasks by the complexity of reasoning they demand, as in the Model of Hierarchical Complexity) would be needed for the stronger claim that severity varies systematically with difficulty, and for traceability across levels you have not stratified.

---

## 6. Reading the report

**In plain words.** The sample report's key table, with simulated human reviewers:

| Answer type | Judge vs humans | Error bar (±) | Verdict | Judge correct | Humans correct |
|---|---|---|---|---|---|
| verbatim | +2.62 | 0.46 | stricter | 49% | 93% |
| paraphrase | +2.55 | 0.43 | stricter | 36% | 85% |
| omission | +1.83 | 0.53 | stricter | 38% | 79% |
| negation | +2.33 | 1.03 | stricter | 99% | 86% |
| numeric | +1.00 | 0.59 | can't tell | 96% | 83% |
| added claim | −0.07 | 0.66 | can't tell | 94% | 94% |
| name or unit swapped | −1.44 | 0.39 | more lenient | 52% | 80% |

Three things to notice:

1. **The lean changes by answer type.** Stricter on correct answers, more lenient on swapped names or units. One overall number would hide that.
2. **"Stricter" is not the same as "wrong".** On negations the judge is stricter than the humans *and* more often right (99% vs 86%). Severity compares graders with each other; the "correct" columns compare them with the truth. Read both.
3. **"Can't tell" is a real answer.** For numbers and added claims the error bar is wider than the lean, so the honest verdict is inconclusive.

**For the statistically minded.** Leans are in logits relative to the reference mean; SE combines the judge's and the reference raters' stratum uncertainty; verdicts use a two-sided 95% criterion without multiplicity correction across the seven strata, so treat a single borderline verdict with caution. Accuracy columns use the by-construction labels and are descriptive.

---

## 7. How much evidence is enough?

**In plain words.** This is the most practical lesson. Running the same study on only **24 answers** (the size of a typical hand-labelled set) makes every error bar enormous, from ±1.2 to ±6.5 logits, and **every answer type comes out "can't tell"**. With 628 answers the error bars shrink to about ±0.4–1.0, and real patterns appear.

How many ratings do you need? Work it out **before** you start labelling:

| Ratings per grader | Error bar (SE) at the information real judge ratings carry |
|---|---|
| 24 | ±0.64 |
| 100 | ±0.32 |
| 200 | ±0.22 |
| 400 | ±0.16 |
| 700 | ±0.12 |

To reliably detect a lean of 0.3 logits (a modest one), you need **roughly 1,700 ratings per answer type** with ratings like these. In the best case (answers that are genuinely 50/50 for the grader) the number falls to about 700. A study sized by gut feeling, at a few dozen items, cannot see leans of this size at all.

**The hardest choice is the effect size, and it is a business decision.** Power depends on four things: how often you accept a false alarm (alpha), how often you want to catch a lean that is really there (power), the smallest lean that would change what you do (the effect size), and the number of ratings. The statistics cannot choose the effect size for you. If your process can live with more uncertainty, the study gets much smaller:

| Smallest lean worth detecting | Pass/fail ratings (information 0.10) | Graded 0–3 ratings (information 0.29) |
|---|---|---|
| 0.3 logits | about 1,740 | about 600 |
| 0.5 logits | about 630 | about 220 |
| 0.75 logits | about 280 | about 100 |

(5% false alarms, 80% power, per answer type.) Near a 50% pass rate, a lean of 0.5 logits is roughly a 12-point change in how often the grader passes answers, often the smallest difference a team would act on. So the practical order is: **agree the smallest lean that would change a decision, then size the study.** Accepting 10% false alarms and 75% power cuts the 0.5-logit pass/fail figure from about 630 to about 430.

**For the statistically minded.** For dichotomous Rasch ratings, the information a rating contributes to ρ is p(1 − p), at most 0.25. Hence

```text
SE(ρ)  ≈  1 / √( Σ p(1 − p) )  =  1 / √( n · ī )
```

where ī is the mean information per rating. The judge's ratings in the sample have ī ≈ 0.10, well below 0.25, because many items sit far from 50/50 for it. To detect a severity difference d between two independently estimated raters with equal SE at two-sided α = 0.05 and power 0.80:

```text
d  ≥  (1.96 + 0.84) · √2 · SE    ⇒    n  =  1 / ( ī · (d / (2.80 · √2))² )
```

For d = 0.3 and ī = 0.10 this gives n ≈ 1,700; for ī = 0.25, n ≈ 700. `python -m evals.severity.power --detect 0.3 --info 0.1` computes it. To set your own trade-off, pass several effect sizes and your own error rates: `python -m evals.severity.power --detect 0.3 0.5 0.75 --info 0.1 --alpha 0.10 --power 0.75`. The z-values come from the normal distribution, rounded to two decimals as in standard tables (1.96 and 0.84 by default).

### 7.1 Graded ratings: fewer ratings for the same precision

**In plain words.** A pass/fail rating answers one question: above or below the bar. A score from 0 to 3 also says *how far* above or below, so each rating tells you more about the grader, and you need fewer of them. Rubric v2 already scores completeness from 0 to 3 ([`RUBRIC.md`](../evals/judge/RUBRIC.md), Part B), so the add-on now measures severity on those scores too ([`run_graded.py`](../evals/severity/run_graded.py)).

To check what grading buys, the report takes the **same** ratings, cuts them to pass/fail at the standard-tier bar (score 2 or more) and fits the pass/fail model to them. On the grounded answers in the item bank, with simulated reviewers:

| | Graded (0–3) | Same ratings as pass/fail |
|---|---|---|
| Information per rating | 0.29 | 0.04 |
| Ratings to detect a 0.3-logit lean | about 600 | about 4,000 |
| Verdict on paraphrased answers (z = lean / SE) | −3.3, softer | −1.7, can't tell |

Three honest qualifications:

1. **It is not better everywhere.** On answers with omissions the two versions are about equally clear (z −3.5 graded, −3.6 pass/fail), and overall the pass/fail z is no smaller. Grading wins where answers sit near the top of the scale, as paraphrases do: pass/fail sees only "passed", while the 0–3 score still separates a 2 from a 3.
2. **The size of the gain depends on where the bar sits.** Most of these answers clear the bar easily, so a pass/fail rating rarely surprises anyone and carries little information. With a bar near the middle of the answers, the gap is smaller.
3. **It only helps if reviewers use the scale the same way.** If two people cannot agree whether an answer is a 2 or a 3, the extra detail is noise. Check reviewer-to-reviewer weighted kappa first; on the 11 labelled answers in this repo it is 0.45, which is moderate.

The result itself is worth reading too: the completeness grader is **softer than the reviewers on omissions** (it gives credit for the words an answer keeps and cannot tell which missing words matter), the weakness [`evals/completeness.py`](../evals/completeness.py) warns about.

**For the statistically minded.** [`rsm.py`](../evals/severity/rsm.py) fits a many-facet rating scale (Andrich) model,

```text
log [ P(X = k) / P(X = k − 1) ]  =  β_i − ρ_r − τ_k ,    k = 1, 2, 3,   Σ τ_k = 0
```

with thresholds τ shared by all raters, using the same estimation choices as the binary model (reference-only calibration, hierarchical item prior per stratum, damped Newton, re-anchoring). The information one rating carries about ρ is the model variance of the score, Var(X | β_i − ρ_r), which for four categories can exceed the binary maximum of 0.25 (here 0.29 on average, against 0.044 for the same ratings dichotomised). The two models put severity on different logit scales, so compare z = lean / SE rather than raw logits; the ratings-needed figures use each model's own information and are a planning guide, not an exact exchange rate. Thresholds are recovered approximately (estimated −1.71, +0.32, +1.39 against true −1.2, 0, +1.2) and reviewer severities within two SE.

---

## 8. Checking the checker

**In plain words.** A measuring method needs testing too. The simulated reviewers were given **known** strictness levels (−0.4, +0.4 and 0.0), and the model had to find them again. It did, each within two error bars (estimates −0.47 ± 0.20, +0.24 ± 0.22 and +0.23 ± 0.22). If it hadn't, its other answers couldn't be trusted.

Building it also turned up four genuine problems, each now covered by a test:

1. **The judge's errors leaked into answer ease** (section 4). Fixed by calibrating on humans only.
2. **Answers rated by only one person were pulled towards "average"**, which made humans look lenient on easy answer types and strict on hard ones. Fixed by pulling each answer towards the average **for its type**, not the overall average.
3. **The calculation could overshoot and fly off to −3,400** when nearly every rating in a group agreed. Fixed by limiting each step.
4. **The stopping check never fired**, because of harmless drift that the re-anchoring cancelled. Fixed by checking the anchored values instead.

**For the statistically minded.** Estimation is penalised joint maximum likelihood with alternating, damped (|step| ≤ 1 logit) Newton updates. Item ease has a hierarchical normal prior centred on its stratum mean (σ = 1), stratum means have a N(0, 4²) hyperprior so that ceiling strata stay finite, and severities have a weak N(0, 10²) prior. The reference mean is re-anchored to zero on every iteration to remove the translation mode, and convergence is assessed on anchored parameters. Reported SEs are conditional on the other facet's estimates, so they understate total uncertainty somewhat. JML estimates are also known to be biased with few ratings per element. This is a transparent teaching implementation; for publication use established software (FACETS; the R package TAM) with marginal or Bayesian estimation, and inspect infit and outfit statistics, which are not implemented here.

---

## 9. Using it with real people

1. **Agree on the rubric first** ([`evals/judge/RUBRIC.md`](../evals/judge/RUBRIC.md)); disagreement about what "correct" means swamps everything else.
2. **Agree the effect size, then size the study**: decide the smallest lean that would change a decision, then run the power calculation at a realistic information level (not the best case), with the false-alarm rate and power your process can tolerate.
3. **Use a linked design:** shared anchor answers for everyone, individual samples on top.
4. **Mix in real model answers**, not only constructed ones.
5. **Record ratings** one per line, `{"item_id": "s-nume-001", "rater": "reviewer-1", "grounded": 0}`, and run `python -m evals.severity.run_severity --ratings my.jsonl`.
6. **Report leans with error bars and "can't tell"**, never a bare number, and never present simulated reviewers as human results.

---

## Key takeaways

- **Agreement tells you how often graders match; severity tells you which way, where, and how sure you are.**
- **A fix can improve agreement while only moving the lean.** Measure the lean directly.
- **Calibrate against people, then measure the machine**, never the other way round.
- **"Stricter" is not "wrong"**: compare graders with each other *and* with the truth.
- **Work out the sample size before labelling.** Small label sets cannot detect modest leans, and the honest verdict is "can't tell".
- **Graded scores need fewer ratings than pass/fail**, if reviewers can use the scale consistently.

## Further reading

- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37–46.
- Rasch, G. (1960). *Probabilistic models for some intelligence and attainment tests.* Danish Institute for Educational Research.
- Linacre, J. M. (1989). *Many-facet Rasch measurement.* MESA Press.
- Eckes, T. (2015). *Introduction to many-facet Rasch measurement: Analyzing and evaluating rater-mediated assessments* (2nd ed.). Peter Lang.
- Commons, M. L. (2008). Introduction to the model of hierarchical complexity and its relationship to postformal action. *World Futures*, 64(5–7), 305–320.

*Thanks to the newsletter readers whose comments shaped sections 1, 5 and 7.*

---
Next: [10. Using the Three Reports](10-using-the-three-reports.md) · Back to the [index](../README.md#article-index).
