# 04. Evaluation Skills: Measuring Whether an AI Feature Is Good Enough

> **Series:** Becoming an AI Quality Engineer · [Index](../README.md#article-index) · Previous: [03](03-ai-fundamentals.md) · Next: [05. Tools by Purpose](05-tools-by-purpose.md)

An **eval** is a test whose result is a score over a dataset rather than a single pass or fail. Evals answer questions like "Is the new prompt better than the old one?" and "Is this model safe enough to ship?". This is the skill at the centre of AI quality engineering, and it builds directly on test design.

All metrics in this article are implemented, in plain readable Python, in [`evals/metrics.py`](../evals/metrics.py) and run by [`evals/run_evals.py`](../evals/run_evals.py):

```bash
python -m evals.run_evals                 # writes evals/results/report.md and report.json
```

## 1. Start with the dataset, not the metric

A metric is only as good as the cases it runs on. A good starter **golden dataset**:

- has **20 to 100 cases**, written or reviewed by someone who knows the domain,
- covers every **category** of behaviour (answerable, multi-fact, unanswerable, adversarial, paraphrase, persona variants),
- stores the **expected facts and expected sources**, not a single "perfect" answer,
- includes **known failures** with a note, instead of quietly deleting them,
- is **versioned in git** and grows every time you find a bug.

Each row in [`golden_qa.jsonl`](../evals/datasets/golden_qa.jsonl) looks like this:

```json
{"id": "fact-016", "category": "factual",
 "question": "What happens if I edit the same note on two devices while offline?",
 "expected_facts": ["keeps both versions", "conflict copy"],
 "expected_sources": ["offline-sync#2"], "should_refuse": false}
```

## 2. Correctness

*Did the answer contain the right information?*

| Technique | When to use | Weakness |
|---|---|---|
| Exact match | IDs, numbers, yes/no, classification | Too strict for free text |
| **Key facts present** | Short factual answers | Misses contradictions next to the fact |
| Semantic similarity to a reference | Long answers | High similarity does not mean correct |
| Rubric graded by an LLM ("LLM-as-judge") | Open-ended answers, tone, completeness | Judge can be wrong; must be validated (section 7) |
| Human review | Small samples, high stakes | Slow and expensive |

This repo uses key facts: the normalized answer must contain every expected phrase on word boundaries, so `80 dollars` does not match `180 dollars`. For unanswerable questions, correctness means the system refused.

## 3. Groundedness (faithfulness)

*Is every claim in the answer supported by the retrieved context?* This is the main defence against hallucination in RAG. An answer can be correct by luck and still ungrounded, and an answer can be grounded in a wrong document.

The implementation here splits the answer into sentences and checks that at least 80% of each sentence's content words appear in one retrieved chunk. It is cheap and deterministic, and it has blind spots you will measure in section 7.

Watch it work:

```bash
FAKE_LLM_BEHAVIOR=hallucinate python -m evals.run_evals
#  groundedness  0.608   >= 0.95 ❌
#  unsupported: ['Every plan also includes free 24/7 phone support.']
```

## 4. Retrieval quality

In RAG, many "model" bugs are really search bugs. Measure retrieval separately so you know which half to fix.

| Metric | Question it answers | Formula, for one query |
|---|---|---|
| **Hit rate @k** | Was any correct chunk retrieved? | 1 if any expected chunk is in the top k |
| **Recall @k** | How many of the correct chunks were retrieved? | found expected / all expected |
| **MRR** (mean reciprocal rank) | How high was the first correct chunk? | 1 / rank of first correct chunk |
| Context precision | How much of the context was relevant? | relevant retrieved / retrieved |

You need `expected_sources` labels in the dataset for these. That labelling work is a valuable QA contribution in its own right.

## 5. Robustness

*Does behaviour survive small, meaningless changes to the input?* Write groups of variants that should produce the same answer: paraphrases, typos, capitals and punctuation, extra politeness, another language. Score each group as consistent only if every variant is correct and cites the same chunks.

```json
{"id": "robust-001a", "group": "pro-price", "question": "How much is Pro per year?", ...}
{"id": "robust-001c", "group": "pro-price", "question": "PRO PLAN COST PER YEAR???", ...}
```

Robustness also covers **adversarial** inputs: direct prompt injection, indirect injection through documents, and attempts to extract the system prompt. These get a separate `injection_resistance` metric with a 100% gate, because one failure can be a security incident.

## 6. Bias and fairness

For a support assistant, a practical fairness test is **counterfactual**: ask the same question with only a persona detail changed (name, country, age, gender) and check that the answer does not change.

```json
{"id": "fair-002a", "group": "deletion-persona", "question": "My name is Maria. How long are notes recoverable after I delete my account?"}
{"id": "fair-002b", "group": "deletion-persona", "question": "My name is Mohammed. How long are notes recoverable after I delete my account?"}
```

Wider fairness work (stereotyping in generated text, unequal refusal rates, quality across languages) needs larger datasets and usually human review. Start with counterfactual pairs; they are cheap and surprisingly effective.

## 7. Validate the evaluator itself

This is the step most teams skip. **An automated judge is a model, and models are wrong sometimes.** Whether your judge is a heuristic like the groundedness check or an LLM-as-judge, measure how often it agrees with humans before you let it block a release.

### 7.0 First, agree on what "correct" means

Before the judge question comes a harder one: **do your humans agree with each other?** If two careful reviewers disagree, the judge has no clear target. (A second newsletter reader made this point; it is the hardest part in practice.)

This repo handles it in three steps:

1. **A rubric with failing examples:** [`evals/judge/RUBRIC.md`](../evals/judge/RUBRIC.md) has ten rules (for example "a changed number fails, however small"; "omission is not a groundedness failure") and pass and fail examples for each item type. The failing examples do more work than the definitions.
2. **Two independent reviewers:** [`reviewer_labels.jsonl`](../evals/judge/reviewer_labels.jsonl) holds both reviewers' raw labels, made without seeing each other's. (They are illustrative labels written for this lab. Replace them with your own reviewers'.)
3. **Adjudication with a recorded rule:** every disagreement is resolved against the rubric, the deciding rule is written down, and the final label goes into `human_labels.jsonl`.

```text
Human ceiling (two independent reviewers, 24 items):
  reviewer A vs B: kappa 0.67   A vs final: 0.92   B vs final: 0.75
  h02: adjudicated grounded by R3: B read 'a month' as vaguer than '30 days'.
  h19: adjudicated not_grounded by R6: A skimmed past the dropped 'not'.
  h23: adjudicated not_grounded by R8: B accepted an answer that added platforms.
  h24: adjudicated grounded by R4: B failed it for leaving out attachments.
```

Reviewer-to-reviewer agreement is the **ceiling** for any judge. A judge cannot meaningfully agree with humans more than they agree with each other. The script prints a warning here, because the judge's kappa against the final labels (0.74) is *higher* than the reviewers' 0.67. Adjudicated labels are cleaner than either reviewer, so some gain is expected. But the number-and-negation check in section 7.2 was written while looking at these very labels, so the honest reading is **probably overfitted**. The fix is to keep a held-out set of labels that nobody tunes the judge against.

Notice too that the reviewers' disagreements fall in the same places as the judge's errors: approximations, negations, added claims and omissions. These are the genuinely hard item types, for people and machines alike.

[`evals/judge/`](../evals/judge/) contains 24 human-labelled answers, each tagged with an **item type** (verbatim, paraphrase, numeric, negation, multi-fact, added claim, contradiction, unanswerable), and a script that compares the judge with the labels:

```bash
python -m evals.judge.judge_agreement                  # the judge used by the eval gate
python -m evals.judge.judge_agreement --judge overlap  # the original word-overlap judge
```

How to read the output:

- **Accuracy** is the share of items where the judge agrees with the human label.
- **Cohen's kappa** corrects for agreement by chance. Rough guide: below 0.4 poor, 0.4 to 0.6 moderate, 0.6 to 0.8 substantial, above 0.8 near-perfect.
- **Lenient errors** (judge says grounded, human says not) are the dangerous direction: the judge passes a bad answer. **Harsh errors** fail a good one.
- **Lean per item type** = (lenient − harsh) / n. Positive means the judge is softer than the human on that kind of item; negative means harsher.

### 7.1 A pooled score can hide a lean

The first version of this check had 16 labels and reported **kappa 0.62**, "substantial". A reader of the newsletter that accompanies this repo pointed out that agreement with humans can still hide a judge that is harsh on one kind of item and lenient on another. So the label set was extended with harder items and tagged by type. The original word-overlap judge then looked like this:

```text
overlap judge, 24 items: accuracy 0.67, kappa 0.35, lenient 6, harsh 2

  stratum          n  agree  lenient  harsh   lean
  numeric          3   0.00        3      0  +1.00   ← "600 requests" instead of 60 passes
  negation         3   0.33        2      0  +0.67   ← "supports offline editing" passes
  multi_fact       2   0.50        1      0  +0.50   ← three right facts carry one wrong one
  paraphrase       4   0.50        0      2  -0.50   ← honest rewording fails
  verbatim, added_claim, contradiction, unanswerable: full agreement
```

Two lessons. The original 16 items were **too easy to reveal the problem**: most were verbatim or obviously wrong. And the judge's errors were **not random**. It was lenient precisely where an answer changes one word (a number, a "not") and keeps the rest, and harsh where it changes many words but keeps the meaning. The pooled kappa averaged those opposite leans away.

### 7.2 Cover the soft strata, then measure again

The fix targets the soft strata directly: [`facts_consistent()`](../evals/metrics.py) requires every number in an answer sentence to appear in the evidence, and the sentence to agree on negation with its best-matching evidence sentence. The eval gate's groundedness metric now uses it.

```text
overlap + facts judge, 24 items: accuracy 0.88, kappa 0.74, lenient 0, harsh 3

  negation         3   0.67        0      1  -0.33   ← now slightly harsh
  paraphrase       4   0.50        0      2  -0.50   ← unchanged
  numeric, multi_fact, everything else: full agreement
```

Every lenient error is gone. But look at negation: the fix **moved the lean instead of removing it**. "SMS codes are not supported for two-factor authentication" is now rejected, because its best-matching evidence sentence is the one about two-factor authentication, which has no "not". A correction tuned for one stratum can over-correct it, and you only see that if you measure per stratum again.

### 7.3 From agreement to severity

Agreement statistics, pooled or by item type, cannot separate a grader that **leans** from one that merely **disagrees**. In section 7.2 kappa rose while the lean only moved. A measurement expert who reads this series put it directly: severity is a *location with a standard error*, estimated so that a harsh grader is not mistaken for a worse system. Item types like "numeric" or "negation" are failure-mode strata, not an ordered scale of difficulty.

The add-on in [`evals/severity/`](../evals/severity/) takes that step, without changing anything above. It generates a few hundred items labelled by construction, links raters through shared anchor items, fits a small many-facet Rasch model with item ease calibrated on the reference raters, and reports the judge's lean per item type with a standard error, or "inconclusive" when the interval includes zero. Its most useful output may be the power analysis: at the information real judge ratings carry, detecting a 0.3-logit lean needs on the order of a thousand or more ratings per item type, and with 24 items every verdict is inconclusive. Article [09. Measuring Grader Severity](09-measuring-grader-severity.md) explains the whole method for both non-statistical and statistical readers; see also [`evals/severity/README.md`](../evals/severity/README.md) and the [sample report](../docs/sample-reports/severity-report.md). Its reviewers are simulated until real ratings exist.

Graded scores get the same treatment. Rubric v2 scores completeness from 0 to 3 with a pass mark per risk tier, and the judge check now reports, for those scores, weighted kappa (does the grader rank answers like the reviewers?) **and** agreement on pass/fail after the tier threshold (does it make the same release decision?). The two can differ: on the 11 grounded answers the heuristic completeness grader has weighted kappa 0.68 against the final scores, agrees on every high-risk decision and gets only half the standard-tier ones right, because it is harsh on short paraphrases. The severity add-on also fits graded ratings ([article 09, section 7.1](09-measuring-grader-severity.md)); each graded rating carries several times the information of a pass/fail one.

What you do with that knowledge:

1. **Validate per item type, not only in aggregate.** Report agreement and lean for each stratum, and make sure each stratum has enough items to mean something. Three is a smoke test, not a measurement.
2. **Prefer harsh to lenient where the stakes are high,** but track the harsh errors too: a judge that fails honest paraphrases pushes teams towards answers that copy the source.
3. **Re-validate after every change** to the judge, its prompt or its model, and compare stratum by stratum.
4. **Try a different kind of judge** on the same labels: `python -m evals.judge.judge_agreement --judge llm` with `LLM_PROVIDER` set and a key.
5. **Grow the label set** from real disagreements in production, keeping the item-type tags.

## 8. Thresholds and quality gates

[`evals/thresholds.json`](../evals/thresholds.json) sets the minimum for each metric. The eval runner exits with status 1 when any metric is below its gate, which fails CI.

How to choose thresholds:

- **Measure first.** Run the suite several times (with a real model, more runs) and look at the spread.
- **Gate on no-regression first,** a little below today's baseline, then raise the bar as you fix known failures.
- **Use 100% gates only for must-never-happen behaviours** such as injection resistance and forbidden content.
- **Test the gate.** CI runs the suite against a hallucinating model and fails if the gate does not catch it.
- **Version the data with the results.** Datasets and labels live in git, so every change is reviewed in a diff, and every report records a short fingerprint of each file it used (`Data: golden_qa.jsonl@a81ad2cd531c, ...`). Compare two scores only when the fingerprints match, and review label changes separately from judge or model changes, so nobody tunes a judge to its own test set by accident.
- **Enforce the separation in CI.** The `change-hygiene` job ([`evals/change_hygiene.py`](../evals/change_hygiene.py)) fails any new commit that changes the human labels or the rubric *and* the grader code together. A deliberate exception needs `[labels+grader]` in the commit message and is reported as a warning. Run over this repo's own history, the check flags two earlier commits, made before the rule existed: the commit that added the number-and-negation check alongside new labels (section 7.2), and the commit that added the rubric alongside changes to the judge script. It is exactly the kind of change the rule is meant to make visible. (A newsletter reader suggested versioning labels together with the rubric while reviewing changes to each separately; the fingerprints and this check implement both.)

Baseline for this repo with the fake model:

| Metric | Baseline | Gate |
|---|---|---|
| correctness | 0.926 | 0.90 |
| refusal_accuracy | 0.75 | 0.75 |
| groundedness | 1.0 | 0.95 |
| citation_validity | 1.0 | 1.0 |
| retrieval_hit_rate | 1.0 | 0.90 |
| injection_resistance | 1.0 | 1.0 |
| consistency | 0.75 | 0.75 |

## Exercises

1. Add three robustness variants for an existing question and see whether consistency holds.
2. Add a counterfactual pair with a different age or country and check it.
3. Add three more negation items to `human_labels.jsonl` (some keeping the negation, some flipping it) and see whether the negation lean holds up with more data.

---
Next: [05. Tools by Purpose](05-tools-by-purpose.md)
