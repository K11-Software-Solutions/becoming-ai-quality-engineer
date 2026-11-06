"""Tests for the completeness grader (rubric v2, Part B) and its graded agreement check."""
import pytest

from evals import completeness
from evals.change_hygiene import violates
from evals.judge.judge_agreement import LABELS, completeness_agreement, weighted_kappa

CONTEXT = ("Exports are delivered as a ZIP file containing Markdown files and attachments. "
           "The desktop apps work offline.")
QUESTION = "What format are note exports in?"


def test_full_answer_scores_3_and_unrelated_context_is_ignored():
    # C1: the offline sentence is irrelevant to the question, so leaving it out is not an omission
    answer = "Exports are delivered as a ZIP file containing Markdown files and attachments."
    assert completeness.score(answer, QUESTION, CONTEXT) == 3


def test_scores_fall_as_the_answer_covers_less():
    full = completeness.coverage("A ZIP file containing Markdown files and attachments.", QUESTION, CONTEXT)
    part = completeness.coverage("A ZIP file.", QUESTION, CONTEXT)
    none = completeness.coverage("You can export your notes from Settings.", QUESTION, CONTEXT)
    assert full > part > none
    assert completeness.score("You can export your notes from Settings.", QUESTION, CONTEXT) <= 1


@pytest.mark.parametrize("value, tier, ok", [
    (3, "high", True), (2, "high", False), (2, "standard", True), (1, "standard", False),
])
def test_tier_thresholds(value, tier, ok):
    assert completeness.passes(value, tier) is ok


def test_weighted_kappa_counts_near_misses_as_partial_agreement():
    assert weighted_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == 1.0
    near = weighted_kappa([0, 1, 2, 3], [1, 1, 2, 2])
    far = weighted_kappa([0, 1, 2, 3], [3, 1, 2, 0])
    assert near > 0 > far


def test_completeness_agreement_on_the_labelled_set():
    import json
    labels = [json.loads(line) for line in LABELS.read_text(encoding="utf-8").splitlines() if line.strip()]
    comp = completeness_agreement(labels)
    assert comp["n"] == 11
    grounded = {r["id"] for r in labels if r["human"] == "grounded"}
    assert {r["id"] for r in comp["rows"]} <= grounded          # Part B scores grounded answers only
    assert -1 <= comp["judge_weighted_kappa"] <= 1
    assert 0 <= comp["judge_passfail_agreement"] <= 1
    # a false pass is the dangerous direction; the heuristic grader is harsh, so it has none
    assert comp["false_passes"] == []


def test_completeness_files_are_covered_by_the_change_hygiene_check():
    assert violates(["evals/judge/completeness_labels.jsonl", "evals/completeness.py"])
    assert not violates(["evals/judge/completeness_labels.jsonl"])
    assert not violates(["evals/completeness.py", "tests/unit/test_completeness.py"])
