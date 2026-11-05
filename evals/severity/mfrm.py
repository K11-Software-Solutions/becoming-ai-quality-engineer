"""A small many-facet Rasch model for dichotomous ratings.

    logit P(rating = "grounded")  =  ease(item)  −  severity(rater)

Severity is a location on a logit scale with a standard error, estimated jointly
with item ease, so a harsh rater is not mistaken for a worse system and vice
versa. Positive severity = harsher (says "not grounded" more often).

Estimation: penalised joint maximum likelihood (Newton steps). A weak normal
prior on item ease keeps items that every rater agrees on finite; the scale is
anchored so that the mean severity of the reference raters (the human reviewers)
is zero. Standard errors come from the information at the solution. For
publication-grade work use established software (for example FACETS or the R
package TAM); this implementation is for teaching and for the testbed's checks.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


MAX_STEP = 1.0  # logits per Newton step


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x)) if x > -30 else 0.0


@dataclass
class Fit:
    ease: dict[str, float]
    severity: dict[str, float]
    se: dict[str, float]
    n: dict[str, int]
    iterations: int


def fit(ratings: list[tuple[str, str, int]], reference: list[str], prior_sd_ease: float = 2.0,
        prior_sd_severity: float = 10.0, max_iter: int = 500, tol: float = 1e-6,
        group_of: dict[str, str] | None = None) -> Fit:
    """With `group_of` (item -> stratum), item ease gets a hierarchical prior centred on its
    stratum's mean instead of zero. Without it, items rated only once are shrunk towards zero,
    which makes raters look lenient on easy strata and harsh on hard ones."""
    items = sorted({i for i, _, _ in ratings})
    raters = sorted({r for _, r, _ in ratings})
    ease = {i: 0.0 for i in items}
    sev = {r: 0.0 for r in raters}
    by_item: dict[str, list[tuple[str, int]]] = {i: [] for i in items}
    by_rater: dict[str, list[tuple[str, int]]] = {r: [] for r in raters}
    for i, r, x in ratings:
        by_item[i].append((r, x))
        by_rater[r].append((i, x))
    pe, ps = 1 / prior_sd_ease ** 2, 1 / prior_sd_severity ** 2
    groups = group_of or {}
    centre = {g: 0.0 for g in set(groups.values())}
    for it in range(1, max_iter + 1):
        delta = 0.0
        before = (dict(ease), dict(sev))
        for i in items:
            mu = centre.get(groups.get(i), 0.0)
            g, h = -(ease[i] - mu) * pe, pe
            for r, x in by_item[i]:
                p = _sigmoid(ease[i] - sev[r])
                g += x - p
                h += p * (1 - p)
            step = max(-MAX_STEP, min(MAX_STEP, g / h))  # damped Newton: no overshoot
            ease[i] += step
            delta = max(delta, abs(step))
        for gname in centre:  # stratum mean ease, with a weak N(0, 4^2) hyperprior so all-agree strata stay finite
            members = [ease[i] for i in items if groups.get(i) == gname]
            new = (sum(members) * pe) / (len(members) * pe + 1 / 4.0 ** 2)
            delta = max(delta, abs(new - centre[gname]))
            centre[gname] = new
        for r in raters:
            g, h = -sev[r] * ps, ps
            for i, x in by_rater[r]:
                p = _sigmoid(ease[i] - sev[r])
                g -= x - p
                h += p * (1 - p)
            step = max(-MAX_STEP, min(MAX_STEP, g / h))  # damped Newton: no overshoot
            sev[r] += step
            delta = max(delta, abs(step))
        # Re-anchor every iteration: ease and severity can drift together without changing any
        # prediction, so fix the reference raters' mean severity at zero.
        drift = sum(sev[r] for r in reference) / len(reference)
        sev = {r: v - drift for r, v in sev.items()}
        ease = {i: v - drift for i, v in ease.items()}
        centre = {g: v - drift for g, v in centre.items()}
        # Converged when the anchored parameters stop moving (raw steps can include drift that
        # the re-anchoring cancels, so they are not a reliable stopping signal).
        delta = max(max(abs(ease[i] - before[0][i]) for i in items), max(abs(sev[r] - before[1][r]) for r in raters))
        if delta < tol:
            break
    shift = sum(sev[r] for r in reference) / len(reference)
    sev = {r: v - shift for r, v in sev.items()}
    ease = {i: v - shift for i, v in ease.items()}
    se = {}
    for r in raters:
        info = ps + sum(p * (1 - p) for p in (_sigmoid(ease[i] - sev[r]) for i, _ in by_rater[r]))
        se[r] = 1 / math.sqrt(info)
    return Fit(ease, sev, se, {r: len(by_rater[r]) for r in raters}, it)


def stratum_shift(fitted: Fit, ratings: list[tuple[str, str, int]], stratum_of: dict[str, str],
                  raters: set[str], prior_sd: float = 2.0) -> dict[str, tuple[float, float, int]]:
    """Rater-by-stratum bias analysis for a group of raters, with item ease held fixed.

    For each stratum s, estimates a common shift tau_s in
        logit P(grounded) = ease(item) - severity(rater) - tau_s
    over the ratings of `raters` in that stratum. tau_s > 0: the group is harsher in s
    than its overall severity predicts. A weak prior keeps strata where everyone agrees
    (a ceiling) finite; their large SE then marks them as uninformative.

    Returns {stratum: (tau, se, n_ratings)}.
    """
    groups: dict[str, list[tuple[str, str, int]]] = {}
    for i, r, x in ratings:
        if r in raters:
            groups.setdefault(stratum_of[i], []).append((i, r, x))
    prec = 1 / prior_sd ** 2
    out = {}
    for s, obs in sorted(groups.items()):
        tau = 0.0
        for _ in range(200):
            g, h = -tau * prec, prec
            for i, r, x in obs:
                p = _sigmoid(fitted.ease[i] - fitted.severity[r] - tau)
                g -= x - p
                h += p * (1 - p)
            step = max(-MAX_STEP, min(MAX_STEP, g / h))  # damped Newton: no overshoot
            tau += step
            if abs(step) < 1e-8:
                break
        info = prec + sum(p * (1 - p) for p in (_sigmoid(fitted.ease[i] - fitted.severity[r] - tau) for i, r, _ in obs))
        out[s] = (tau, 1 / math.sqrt(info), len(obs))
    return out


def anchored_severity(ease: dict[str, float], obs: list[tuple[str, int]], prior_sd: float = 10.0) -> tuple[float, float]:
    """Severity of one rater with item ease fixed (anchored). Returns (severity, se)."""
    prec, rho = 1 / prior_sd ** 2, 0.0
    for _ in range(200):
        g, h = -rho * prec, prec
        for i, x in obs:
            p = _sigmoid(ease[i] - rho)
            g -= x - p
            h += p * (1 - p)
        step = max(-MAX_STEP, min(MAX_STEP, g / h))  # damped Newton: no overshoot
        rho += step
        if abs(step) < 1e-8:
            break
    info = prec + sum(p * (1 - p) for p in (_sigmoid(ease[i] - rho) for i, _ in obs))
    return rho, 1 / math.sqrt(info)


def lean_by_stratum(ratings: list[tuple[str, str, int]], stratum_of: dict[str, str], rater: str,
                    reference: list[str], z: float = 1.96) -> tuple[Fit, dict, list[dict]]:
    """Measure `rater` against the reference raters, per stratum.

    1. Calibrate item ease on the reference raters ONLY. If the measured rater were
       included, its systematic errors would leak into item ease and hide its own lean.
    2. Holding ease fixed, estimate the rater's severity overall and in each stratum,
       on the calibrated items.
    3. Lean in stratum s = rater severity in s - reference severity in s (the reference
       group's stratum shift), with a combined SE and a verdict: harsher, softer, or
       inconclusive when the 95% interval includes zero.
    """
    calibration = fit([t for t in ratings if t[1] in reference], reference, prior_sd_ease=1.0, group_of=stratum_of)
    obs = [(i, x) for i, r, x in ratings if r == rater and i in calibration.ease]
    overall = anchored_severity(calibration.ease, obs)
    ref_shift = stratum_shift(calibration, [t for t in ratings if t[1] in reference], stratum_of, set(reference))
    rows = []
    for s in sorted({stratum_of[i] for i, _ in obs}):
        sub = [(i, x) for i, x in obs if stratum_of[i] == s]
        sev, se_m = anchored_severity(calibration.ease, sub)
        tau_r, se_r, n_r = ref_shift.get(s, (0.0, math.inf, 0))
        lean = sev - tau_r
        se = math.sqrt(se_m ** 2 + se_r ** 2)
        verdict = "harsher" if lean - z * se > 0 else "softer" if lean + z * se < 0 else "inconclusive"
        rows.append({"stratum": s, "lean": round(lean, 3), "se": round(se, 3), "verdict": verdict,
                     "n_rater": len(sub), "n_reference": n_r})
    return calibration, {"severity": overall[0], "se": overall[1], "n": len(obs)}, rows
