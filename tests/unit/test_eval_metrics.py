"""The evaluator is code too, so it gets unit tests."""
import pytest

from evals import metrics
from evals.judge.judge_agreement import cohen_kappa, stratified
from evals.run_evals import check_gates

CTX = ["Pro accounts can make 60 API requests per minute. The web app does not support offline editing."]


@pytest.mark.parametrize("sentence, ok", [
    ("Pro accounts can make 60 API requests per minute.", True),
    ("Pro accounts can make 600 API requests per minute.", False),   # changed number
    ("The web app does not support offline editing.", True),
    ("The web app supports offline editing.", False),                # dropped negation
    ("The web app has no offline editing.", True),                   # negation kept, reworded
])
def test_facts_consistent(sentence, ok):
    assert metrics.facts_consistent(sentence, CTX) is ok


def test_groundedness_with_and_without_fact_check():
    answer = "Pro accounts can make 600 API requests per minute."
    assert metrics.groundedness(answer, CTX, check_facts=False)[0] == 1.0   # overlap alone is fooled
    assert metrics.groundedness(answer, CTX)[0] == 0.0


def test_stratified_lean_separates_lenient_from_harsh():
    rows = [{"stratum": "numeric", "human": "not_grounded"}, {"stratum": "numeric", "human": "not_grounded"},
            {"stratum": "paraphrase", "human": "grounded"}, {"stratum": "paraphrase", "human": "grounded"}]
    pred = ["grounded", "not_grounded", "not_grounded", "grounded"]
    by = {s["stratum"]: s for s in stratified(rows, pred)}
    assert by["numeric"]["lenient"] == 1 and by["numeric"]["lean"] == 0.5
    assert by["paraphrase"]["harsh"] == 1 and by["paraphrase"]["lean"] == -0.5


def test_every_label_has_a_stratum():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "evals" / "judge" / "human_labels.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert all(r.get("stratum") for r in rows)
    assert len({r["id"] for r in rows}) == len(rows)


def test_contains_all_facts_is_case_and_punctuation_insensitive():
    ok, missing = metrics.contains_all_facts("Locked for 15 minutes.", ["locked for 15 minutes"])
    assert ok and missing == []


def test_contains_all_facts_does_not_match_partial_numbers():
    ok, _ = metrics.contains_all_facts("costs 180 dollars", ["80 dollars"])
    assert not ok


def test_groundedness_flags_unsupported_sentence():
    context = ["Pro includes unlimited notebooks and 20 GB of storage."]
    score, unsupported = metrics.groundedness(
        "Pro includes unlimited notebooks. Pro also includes a personal butler.", context)
    assert score == 0.5
    assert unsupported == ["Pro also includes a personal butler."]


def test_groundedness_ignores_citations():
    score, _ = metrics.groundedness("Links expire after 1 hour. [account-security#4]",
                                    ["Password reset links expire after 1 hour."])
    assert score == 1.0


def test_retrieval_metrics():
    m = metrics.retrieval_metrics(["a#1", "b#1", "c#1"], ["b#1"])
    assert m == {"hit": 1.0, "recall": 1.0, "rr": 0.5}


@pytest.mark.parametrize("a, b, expected", [
    (["x", "y", "x", "y"], ["x", "y", "x", "y"], 1.0),
    (["x", "x", "y", "y"], ["x", "y", "x", "y"], 0.0),
])
def test_cohen_kappa(a, b, expected):
    assert cohen_kappa(a, b) == pytest.approx(expected)


def test_check_gates_reports_failures():
    failures = check_gates({"correctness": 0.8, "groundedness": 1.0},
                           {"correctness": 0.9, "groundedness": 0.95})
    assert failures == ["correctness: 0.8 < required 0.9"]
