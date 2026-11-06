# Sample reports

Snapshots of the reports CI produces, committed so they can be linked permanently.
CI regenerates the live versions on every push (Actions tab: job summary and the `eval-report` artifact).

| Report | What it shows |
|---|---|
| [eval-report.md](eval-report.md) | Golden-dataset metrics and quality gates, failing cases, and the `Data:` fingerprints of the dataset and thresholds used |
| [severity-report.md](severity-report.md) | Grader severity by answer type with error bars, a 24-item comparison and the power analysis (simulated reviewers) |
| [graded-severity-report.md](graded-severity-report.md) | The same severity question on 0-3 completeness scores, compared with the same ratings cut to pass/fail (simulated reviewers) |
| [judge-report.md](judge-report.md) | Judge vs human labels: agreement and lean per item type, the two-reviewer human ceiling, graded completeness agreement and pass/fail after the tier threshold, and the label-file fingerprints |

Snapshots taken at the commits named at the top of each file. Regenerate with:

```bash
python -m evals.run_evals
python -m evals.judge.judge_agreement
python -m evals.severity.run_severity
python -m evals.severity.run_graded
```

How to read and use them together: [article 10](../../articles/10-using-the-three-reports.md).
