"""Tests for the alpha / power options of the severity power analysis. A new file: existing tests are untouched."""
import pytest

from evals.severity import power


def test_defaults_are_the_textbook_values():
    assert power.z_values() == (1.96, 0.84)
    assert power.ratings_to_detect(0.3, 0.10) == power.ratings_to_detect(0.3, 0.10, alpha=0.05, power=0.80)


def test_tolerating_more_uncertainty_needs_fewer_ratings():
    base = power.ratings_to_detect(0.3, 0.10)
    assert power.ratings_to_detect(0.5, 0.10) < base                  # bigger effect size
    assert power.ratings_to_detect(0.3, 0.10, alpha=0.10) < base      # more false alarms allowed
    assert power.ratings_to_detect(0.3, 0.10, power=0.70) < base      # lower chance of detection accepted
    assert power.ratings_to_detect(0.3, 0.10, power=0.90) > base


@pytest.mark.parametrize("alpha, pw", [(0, 0.8), (0.05, 1), (1.2, 0.8)])
def test_rejects_impossible_settings(alpha, pw):
    with pytest.raises(ValueError):
        power.z_values(alpha, pw)


def test_cli_accepts_several_effect_sizes(capsys):
    assert power.main(["--detect", "0.3", "0.5", "0.75", "--info", "0.1", "--alpha", "0.1", "--power", "0.75"]) == 0
    out = capsys.readouterr().out
    assert "alpha 0.1, power 75%" in out and "0.75 logits" in out
