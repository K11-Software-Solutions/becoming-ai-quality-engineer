"""Tests for graded severity (evals/severity/rsm.py, run_graded.py). A new file: existing tests are untouched."""
import math

import pytest

from evals.severity import rsm, run_graded


def test_probabilities_sum_to_one_and_shift_with_location():
    tau = [-1.0, 0.0, 1.0]
    low, high = rsm.probabilities(-2.0, tau), rsm.probabilities(2.0, tau)
    assert sum(low) == pytest.approx(1) and sum(high) == pytest.approx(1)
    assert rsm.moments(2.0, tau)[0] > rsm.moments(-2.0, tau)[0]


def test_two_categories_is_the_binary_rasch_model():
    eta = 0.7
    assert rsm.probabilities(eta, [0.0])[1] == pytest.approx(1 / (1 + math.exp(-eta)))


def test_a_graded_rating_carries_more_information_than_a_binary_one():
    assert rsm.moments(0.0, [-1.2, 0.0, 1.2])[1] > 0.25          # 0.25 is the binary maximum


@pytest.fixture(scope="module")
def study():
    items = run_graded.load_items()
    ratings = run_graded.linked_design(items)
    reference = [rv.name for rv in run_graded.REVIEWERS]
    return items, ratings, reference, run_graded.compare(ratings, {i["id"]: i["stratum"] for i in items}, reference)


def test_only_grounded_strata_are_scored(study):
    items, *_ = study
    assert {i["stratum"] for i in items} == set(run_graded.GROUNDED)


def test_recovers_the_simulated_reviewers_severities(study):
    *_, c = study
    cal = c["graded"]["calibration"]
    for rv in run_graded.REVIEWERS:
        assert abs(cal.severity[rv.name] - rv.severity) <= 2 * cal.se[rv.name]


def test_grading_gives_more_information_per_rating_than_the_same_ratings_cut_to_pass_fail(study):
    *_, c = study
    assert c["graded"]["overall"]["information"] > c["binary"]["overall"]["information"]


def test_grader_scores_a_verbatim_answer_as_complete():
    item = {"answer": "Exports are a ZIP file of Markdown files.", "source_sentence": "Exports are a ZIP file of Markdown files."}
    assert run_graded.grader_score(item) == 3


def test_report_is_written(tmp_path):
    assert run_graded.main(["--out", str(tmp_path)]) == 0
    text = (tmp_path / "graded_severity_report.md").read_text(encoding="utf-8")
    assert "SIMULATED" in text and "What grading buys" in text
