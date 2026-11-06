"""Tests for the labels-vs-grader separation check (evals/change_hygiene.py)."""
import pytest

from evals.change_hygiene import classify, main, violates


@pytest.mark.parametrize("files, bad", [
    (["evals/judge/human_labels.jsonl"], False),                                  # labels only
    (["evals/metrics.py"], False),                                                # grader only
    (["evals/judge/RUBRIC.md", "articles/04-evaluation-skills.md"], False),       # rubric + docs
    (["evals/judge/human_labels.jsonl", "evals/metrics.py"], True),               # both: not allowed
    (["evals/judge/reviewer_labels.jsonl", "evals/judge/judge_agreement.py"], True),
    (["evals\\judge\\RUBRIC.md", "evals\\metrics.py"], True),                     # Windows paths too
    (["app/rag.py", "tests/unit/test_rag_pipeline.py"], False),                   # unrelated
])
def test_violates(files, bad):
    assert violates(files) is bad


def test_classify_lists_both_sides():
    c = classify(["evals/judge/human_labels.jsonl", "evals/metrics.py", "README.md"])
    assert c == {"labels": ["evals/judge/human_labels.jsonl"], "grader": ["evals/metrics.py"]}


def test_cli_files_mode(capsys):
    assert main(["--files", "evals/metrics.py"]) == 0
    assert main(["--files", "evals/judge/human_labels.jsonl", "evals/metrics.py"]) == 1
    assert "in one commit" in capsys.readouterr().out
