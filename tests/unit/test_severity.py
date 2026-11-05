"""Tests for the grader-severity add-on (evals/severity). A new file: existing tests are untouched."""
import json
import math
import random

import pytest

from evals.severity import mfrm, power
from evals.severity.generate_items import ITEMS, STRATA, generate, transform


# --- power analysis ---------------------------------------------------------------------

def test_power_formulas():
    assert power.se_for(400) == pytest.approx(0.1)
    assert power.ratings_for_se(0.1) == 400
    assert power.ratings_for_se(0.1, info=0.1) == 1000          # less information -> more ratings
    assert power.ratings_to_detect(0.3) < power.ratings_to_detect(0.2)


# --- item generator -----------------------------------------------------------------------

def test_committed_items_match_the_generator():
    """The committed dataset cannot drift silently from the code that defines it."""
    committed = [json.loads(l) for l in ITEMS.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert committed == generate()


def test_every_stratum_present_with_labels_by_construction():
    items = generate()
    assert {i["stratum"] for i in items} == set(STRATA)
    for it in items:
        expected = "grounded" if it["stratum"] in {"verbatim", "omission", "paraphrase"} else "not_grounded"
        assert it["label"] == expected
    assert len({i["id"] for i in items}) == len(items)


@pytest.mark.parametrize("stratum, sentence, check", [
    ("numeric", "Pro accounts can make 60 API requests per minute.", lambda out: "60 " not in out),
    ("negation", "It is not available on the Free plan.", lambda out: "not" not in out),
    ("negation", "Each recovery code works only once.", lambda out: True),
    ("entity_swap", "The Pro plan costs 8 US dollars per month.", lambda out: out != "The Pro plan costs 8 US dollars per month."),
    ("verbatim", "Password reset links expire after 1 hour.", lambda out: out == "Password reset links expire after 1 hour."),
])
def test_transformations(stratum, sentence, check):
    out = transform(stratum, sentence, random.Random(0))
    if out is not None:
        assert check(out)


def test_no_lowercased_product_names():
    assert not any("nimbusNotes" in i["answer"] or ", pro " in i["answer"] for i in generate())


# --- many-facet Rasch model ----------------------------------------------------------------

def simulate(n_items, severities, seed=0):
    rng = random.Random(seed)
    ease = {f"i{k}": rng.gauss(0, 1.2) for k in range(n_items)}
    ratings = []
    for r, s in severities.items():
        for i, e in ease.items():
            p = 1 / (1 + math.exp(-(e - s)))
            ratings.append((i, r, int(rng.random() < p)))
    return ratings


def test_recovers_known_severities_within_two_se():
    true = {"a": -0.5, "b": 0.5, "c": 0.0}
    f = mfrm.fit(simulate(600, true), reference=list(true))
    for r, t in true.items():
        assert abs(f.severity[r] - t) <= 2 * f.se[r], (r, f.severity[r], f.se[r])
    assert sum(f.severity.values()) == pytest.approx(0.0, abs=1e-9)   # anchored to the reference mean


def test_standard_error_shrinks_with_more_ratings():
    true = {"a": 0.0, "b": 0.3}
    small = mfrm.fit(simulate(24, true), reference=["a", "b"])
    large = mfrm.fit(simulate(600, true), reference=["a", "b"])
    assert large.se["b"] < small.se["b"] / 3


def test_damped_newton_survives_all_agree_data():
    ease = {f"i{k}": 3.0 for k in range(50)}
    sev, se = mfrm.anchored_severity(ease, [(i, 1) for i in ease])   # every rating "grounded"
    assert math.isfinite(sev) and math.isfinite(se)


def test_lean_by_stratum_finds_a_stratum_specific_lean():
    """A rater that is lenient only on one item type must be reported softer there and not elsewhere."""
    rng = random.Random(1)
    stratum_of, ratings = {}, []
    for k in range(400):
        item, s = f"i{k}", ("swap" if k % 2 else "other")
        stratum_of[item] = s
        e = rng.gauss(-1.0, 0.5)
        for r in ("h1", "h2"):
            ratings.append((item, r, int(rng.random() < 1 / (1 + math.exp(-e)))))
        judge_sev = -2.0 if s == "swap" else 0.0
        ratings.append((item, "judge", int(rng.random() < 1 / (1 + math.exp(-(e - judge_sev))))))
    _, _, rows = mfrm.lean_by_stratum(ratings, stratum_of, "judge", ["h1", "h2"])
    by = {r["stratum"]: r for r in rows}
    assert by["swap"]["verdict"] == "softer"
    assert by["other"]["verdict"] == "inconclusive"


def test_report_runs(tmp_path):
    from evals.severity.run_severity import main
    assert main(["--out", str(tmp_path)]) == 0
    report = (tmp_path / "severity_report.md").read_text(encoding="utf-8")
    assert "SIMULATED" in report and "Judge lean by item type" in report
