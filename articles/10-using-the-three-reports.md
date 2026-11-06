# 10. Using the Three Reports: Evaluation, Judge Validation and Severity

> **Series:** Becoming an AI Quality Engineer · [Index](../README.md#article-index) · Previous: [09](09-measuring-grader-severity.md)

The testbed produces three reports. They are easy to confuse, because all three involve "scores" and "the judge". They answer three different questions, and each one checks whether you can trust the one before it:

```text
1. Evaluation report        "Is the AI app good enough?"                    → measures the APP
2. Judge validation report  "Can we trust the grader that said so?"         → measures the GRADER's agreement with people
3. Severity report          "Which way does the grader lean, where,         → measures the GRADER's bias,
                             and how sure are we?"                             with error bars
```

In one line: **report 1 decides releases, report 2 decides whether to trust report 1, and report 3 explains *how* the grader is wrong and how much evidence you need to be sure.**

All three have committed samples in [`docs/sample-reports/`](../docs/sample-reports/), and CI regenerates the live versions on every push (open any run in the Actions tab and look at the job summary).

| | Evaluation report | Judge validation report | Severity report |
|---|---|---|---|
| Command | `python -m evals.run_evals` | `python -m evals.judge.judge_agreement` | `python -m evals.severity.run_severity` |
| Sample | [eval-report.md](../docs/sample-reports/eval-report.md) | [judge-report.md](../docs/sample-reports/judge-report.md) | [severity-report.md](../docs/sample-reports/severity-report.md) |
| Measures | the RAG app | the grader vs human labels | the grader's strictness vs people |
| In CI | **blocking** gates | **blocking** (kappa ≥ 0.5) | informational only |
| Main reader | developers, QA, release owners | the evaluator's owner | evaluator owner, researchers |
| Explained in | article 04, sections 1–6 and 8 | article 04, section 7 | article 09 |

---

## 1. The evaluation report: is the app good enough?

### What it contains

```text
Model: `fake-llm:faithful`  |  Cases: 34  |  Pass rate: 91%
Data: `golden_qa.jsonl@a81ad2cd531c`, `thresholds.json@0d07186da63c`  (compare scores only when these match)

| correctness          | 0.926 | >= 0.9 ✅  |
| groundedness         | 1.0   | >= 0.95 ✅ |
| injection_resistance | 1.0   | >= 1.0 ✅  |
...
## Failing cases
- fact-002 (factual): How long do I have to request a refund?   missing facts: ['30 days']
## Gate result
PASSED
```

### How to read it

- **Gate result first.** PASSED or FAILED decides whether the change can merge; CI enforces it.
- **Then the metrics.** Each has a threshold. A metric just above its gate is a warning, not a comfort.
- **Then the failing cases.** They are your investigation list. Article 07 shows how to work through one with traces.
- **Then the `Data:` line.** The fingerprints identify the exact dataset and thresholds used. **Compare two reports only when the fingerprints match.** If `golden_qa.jsonl@…` changed, the questions changed, and a better score may only mean easier questions.

### What it cannot tell you

It trusts its graders. Groundedness, for example, is scored by an automated check. If that check is too lenient on some kind of answer, this report will look better than reality, and nothing in it will warn you. That is what reports 2 and 3 are for.

### Use it to

- block or approve a pull request;
- compare two prompts, models or retrieval settings on the same data;
- pick the next failure to investigate.

---

## 2. The judge validation report: can we trust the grader?

### What it contains

```text
Judge: heuristic   items: 24
labels: `human_labels.jsonl@212450dc77c3`, `reviewer_labels.jsonl@5bda24cd16f4`, `RUBRIC.md@1b1eccde70d9`
accuracy: 0.88   cohen_kappa: 0.74
confusion (positive = grounded): TP=8 TN=13 FP=0 FN=3

By item type (lean > 0: softer than the human labeller; < 0: harsher):
  negation         3   0.67        0      1  -0.33
  paraphrase       4   0.50        0      2  -0.50
  ...
Human ceiling (two independent reviewers):
  reviewer A vs B: kappa 0.67   ...
  Note: the judge (kappa 0.74) agrees with the final labels more than the reviewers agree with each other ...
```

### How to read it

- **Overall agreement (kappa):** how often the grader matches the human labels, corrected for chance. CI fails below 0.5.
- **False passes (FP) before false fails (FN).** A false pass means the grader approved an answer a person rejected, so report 1 will look too good. Zero false passes is the number to protect.
- **The per-type table.** A positive lean on a type means the grader is softer than people there, so report 1's score for that kind of answer is optimistic.
- **The human ceiling.** Two careful reviewers agreed at kappa 0.67. A grader cannot meaningfully beat that. When it does (here 0.74), suspect that it was tuned on these labels, and check it on labels it has never seen.
- **The `labels:` line.** Fingerprints of the labels and rubric. If they changed, re-run and compare, but never change labels and the grader in the same commit.
- **The completeness section** (rubric v2, Part B). For 0–3 scores there are two numbers to read. *Weighted kappa* asks whether the grader ranks answers like the reviewers; *same pass/fail* asks whether it makes the same decision once the tier's pass mark is applied. They can disagree: here weighted kappa is 0.68, yet the grader gets only half of the standard-tier decisions right, because it is harsh on short paraphrases. The decision is what ships, so read the per-tier pass/fail line and the false passes first.

### What it cannot tell you

Agreement mixes two different problems: a grader that **leans** one way and a grader that just **disagrees** at random. A fix can raise kappa while the lean only moves to another kind of answer, which is exactly what happened in this repo (article 04, section 7.2). With 24 items, the per-type numbers are also based on three or four examples each.

### Use it to

- decide whether report 1's grader is fit to gate releases;
- spot the answer types where report 1 is too optimistic, and add another check for them;
- re-validate after any change to the grader, its prompt, its model or the labels.

---

## 3. The severity report: which way does the grader lean, and how sure are we?

### What it contains

```text
Mode: SIMULATED reviewers with known severities (teaching mode, not human data)

| Rater          | True severity | Estimate | SE   | Within 2 SE |
| sim-reviewer-A | -0.40         | -0.47    | 0.20 | yes |

Judge overall: severity +1.57 ± 0.16

| Item type   | Lean vs reference | SE   | Verdict      | Judge accuracy | Reference accuracy |
| verbatim    | +2.62             | 0.46 | harsher      | 0.49           | 0.93 |
| negation    | +2.33             | 1.03 | harsher      | 0.99           | 0.86 |
| numeric     | +1.00             | 0.59 | inconclusive | 0.96           | 0.83 |
| entity_swap | -1.44             | 0.39 | softer       | 0.52           | 0.80 |

## The same study with 24 items
... every item type: inconclusive (SE 1.2 to 6.5)

## Power analysis
Ratings per rater to detect a 0.3-logit lean: about 1,700 per item type
```

### How to read it

- **Mode first.** "SIMULATED" means the human side is generated for teaching. Treat the method as real and the human numbers as illustrative, until you run it with real ratings.
- **Recovery check.** The simulated reviewers had known strictness, and the model must find it again within two error bars. If that row says "no", don't trust the rest.
- **Lean, error bar and verdict together.** A lean is only a finding when the verdict says *harsher* or *softer*. *Inconclusive* means the evidence is too thin, not that there is no lean.
- **Lean and accuracy together.** "Harsher" is not "wrong". On negations the judge is stricter than the reference *and* more accurate (0.99 vs 0.86). On swapped entities it is softer *and* less accurate (0.52 vs 0.80), which is a real weakness.
- **The 24-item section.** The same study at the size of a typical hand-labelled set. If everything is inconclusive there, your own small label set cannot answer this question either.
- **The power analysis.** How many ratings you need, decided before labelling.

### What it cannot tell you

It compares graders with each other, not with the truth. That is why the accuracy columns are there. Its item types are failure-mode groups, not an ordered difficulty scale, so a lean can still change across levels it has not measured. And with simulated reviewers it shows *how* to measure, not what real people would say.

### Use it to

- find leans that agreement hides (here: stricter on correct answers that begin with "Yes.", softer on swapped plan names or units);
- choose what to fix in the grader next, and confirm that a fix removed a lean rather than moving it;
- size a human labelling round before you spend anyone's time.

For graded scores, `python -m evals.severity.run_graded` gives the same report on 0–3 completeness ratings ([sample](../docs/sample-reports/graded-severity-report.md)), next to the same ratings cut to pass/fail. Graded ratings carry several times the information, so they shrink the labelling round, provided reviewers agree on the scale.

---

## 4. The three reports together

### Which report for which situation

| Situation | Read | Decision |
|---|---|---|
| A PR changes prompts, model or retrieval | 1 | Merge or not (gated) |
| Report 1 looks good, but users complain about wrong answers | 2, then 3 | Is the grader lenient on that kind of answer? |
| You change the grader (rules, prompt, model) | 2, then 3 | Did agreement improve *and* did the lean shrink, or just move? |
| You change the labels or the rubric | 2 | Re-validate; compare by fingerprint; never in the same commit as a grader change |
| You plan a human labelling round | 3 (power section) | How many ratings per answer type |
| Real human ratings arrive | 3 with `--ratings` | Measure the real grader against real people |
| You compare results across weeks or months | fingerprints on 1 and 2 | Compare only like with like |

### A worked example from this repo

1. **Report 1** passed with groundedness 1.0. Taken alone, that suggests the grader sees no problems.
2. **Report 2**, before the fix, showed the original grader with **six false passes**, concentrated on changed numbers, flipped negations and multi-fact answers. Report 1's groundedness score was therefore too optimistic on exactly those answer types.
3. **The fix** added a check that numbers and negations must match the source. Report 2 then showed **zero false passes** and kappa up from 0.35 to 0.74, but negation had moved from lenient to slightly harsh, and the kappa now beat the human ceiling, a sign of tuning to the labels.
4. **Report 3**, on 628 items, made the remaining picture visible with error bars: the grader is **stricter** on correct answers with conversational openers and **softer** on swapped plan names or units, a weakness the 24-item set had never contained. It also showed that measuring a modest lean reliably needs roughly 1,700 ratings per answer type.
5. **Next actions** follow directly: add a check for entity swaps; ignore conversational openers when checking groundedness; validate on a held-out label set; and size the first real labelling round with the power analysis.

No single report would have led there. Report 1 said "fine", report 2 said "fine, mostly", and only report 3 showed where and how the grader was still wrong.

### A routine that works

- **Every PR:** report 1 (automatic, blocking).
- **Every change to the grader or the labels:** report 2, compared by answer type and fingerprint (automatic, blocking on kappa).
- **Monthly, or before a release that depends on the grader:** report 3, and whenever real ratings are added.
- **Before any labelling effort:** report 3's power analysis.

---

## Key takeaways

- **Three questions, three reports:** is the app good enough; can we trust the grader; which way does the grader lean.
- **Each report checks the one before it.** A green evaluation report is only as trustworthy as its grader.
- **Fingerprints make comparisons honest.** Compare scores only when the data and labels are the same.
- **"Inconclusive" is a result.** It tells you to gather more evidence, and the power analysis tells you how much.

---
Back to the [index](../README.md#article-index).
