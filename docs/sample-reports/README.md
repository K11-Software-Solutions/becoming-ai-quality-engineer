# Sample reports

Snapshots of the two reports CI produces, committed so they can be linked permanently.
CI regenerates the live versions on every push (Actions tab: job summary and the `eval-report` artifact).

| Report | What it shows |
|---|---|
| [eval-report.md](eval-report.md) | Golden-dataset metrics and quality gates, failing cases, and the `Data:` fingerprints of the dataset and thresholds used |
| [judge-report.md](judge-report.md) | Judge vs human labels: agreement and lean per item type, the two-reviewer human ceiling, and the label-file fingerprints |

Snapshot taken at commit `959ccbe`. Regenerate with:

```bash
python -m evals.run_evals
python -m evals.judge.judge_agreement
```
