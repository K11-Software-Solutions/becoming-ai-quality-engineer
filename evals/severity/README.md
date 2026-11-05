# Grader severity (add-on)

`evals/judge` measures how often the judge **agrees** with human labels. Agreement cannot tell a grader that leans (consistently harsh or lenient) from one that just disagrees, and a fix can raise agreement while the lean only moves elsewhere. This add-on measures **severity**: where each grader sits on a logit scale, with a standard error, by item type.

It is separate from the existing judge check. It does not change the judge, its labels, the rubric or any existing test.

```bash
python -m evals.severity.power --detect 0.3 --info 0.1   # how many ratings do I need?
python -m evals.severity.generate_items                  # regenerate items.jsonl (deterministic)
python -m evals.severity.run_severity                    # severity report (simulated reviewers)
python -m evals.severity.run_severity --ratings my.jsonl # ... with real human ratings
```

A sample report is in [`docs/sample-reports/severity-report.md`](../../docs/sample-reports/severity-report.md). For a full explanation written for both non-statistical and statistical readers, see [article 09](../../articles/09-measuring-grader-severity.md).

## How it works

1. **Items labelled by construction** ([`generate_items.py`](generate_items.py)). True sentences from the help articles, each transformed once: verbatim, omission or paraphrase (grounded); changed number, flipped negation, added claim or swapped entity (not grounded). The transformation decides the label, so 628 items need no annotation. Item types are *failure-mode strata*, not an ordered difficulty scale.
2. **A linked rating design** ([`raters.py`](raters.py)). The judge rates every item. Reviewers rate a shared set of anchor items plus their own sample, so everyone sits on one scale without everyone rating everything.
3. **A many-facet Rasch model** ([`mfrm.py`](mfrm.py)): `logit P(grounded) = ease(item) − severity(rater)`. Item ease is **calibrated on the reference raters only**, with a hierarchical prior per item type, so the judge's own errors cannot leak into item ease and hide its lean. The judge is then measured against those fixed item eases, overall and per item type.
4. **A verdict that can say "inconclusive"** ([`run_severity.py`](run_severity.py)). Each per-type lean has a standard error; the report says *harsher* or *softer* only when the 95% interval excludes zero.

## Important limits

- **The reviewers are simulated** until real ratings exist. They have known severities, which is how the model is checked (it must recover them within two standard errors), but they are not people. Never present simulated output as evidence about human reviewers.
- **Severity is relative to the reference raters, not to the truth.** "Harsher" is not "wrong"; the report shows accuracy against the by-construction labels next to the lean.
- **Generated items are cleaner than real answers.** Mix in real model outputs before drawing conclusions about a production judge.
- **This is a teaching implementation.** For publication-grade analysis use established software (for example FACETS or the R package TAM) and check fit statistics.

## Using real ratings

Collect ratings on `items.jsonl` with the rubric in [`evals/judge/RUBRIC.md`](../judge/RUBRIC.md), in a linked design (shared anchors plus individual samples), and size the study first:

```bash
python -m evals.severity.power --detect 0.3 --info 0.1
```

Then save one rating per line and run the report:

```json
{"item_id": "s-nume-001", "rater": "reviewer-1", "grounded": 0}
```
