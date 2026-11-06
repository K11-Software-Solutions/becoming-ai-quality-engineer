"""A many-facet rating scale model (Andrich) for graded 0-3 ratings.

    P(score = k)  is proportional to  exp( k * (ease(item) - severity(rater)) - (tau_1 + ... + tau_k) )

The binary model in mfrm.py is the special case with two categories. With four,
each rating says not just pass or fail but how far above or below the bar the
answer was, so it carries more information about the rater, and the same
standard error needs fewer ratings. The thresholds tau_1..tau_3 (where a 0 turns
into a 1, a 1 into a 2, a 2 into a 3) are shared by all raters and sum to zero.

Same estimation approach as mfrm.py: penalised joint maximum likelihood with
damped Newton steps, a hierarchical item prior per stratum, the scale anchored
on the reference raters, and item ease calibrated on the reference raters only
before the measured rater is placed on it. For teaching and testbed checks; use
FACETS or TAM for publication-grade work.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MAX_STEP = 1.0
CATEGORIES = 4   # scores 0, 1, 2, 3


def probabilities(eta: float, tau: list[float]) -> list[float]:
    """Category probabilities for location eta = ease - severity."""
    logits, acc = [0.0], 0.0
    for k in range(1, len(tau) + 1):
        acc += tau[k - 1]
        logits.append(k * eta - acc)
    m = max(logits)
    w = [math.exp(v - m) for v in logits]
    total = sum(w)
    return [v / total for v in w]


def moments(eta: float, tau: list[float]) -> tuple[float, float]:
    """Expected score and its variance. The variance is the information one rating carries."""
    p = probabilities(eta, tau)
    mean = sum(k * pk for k, pk in enumerate(p))
    return mean, sum((k - mean) ** 2 * pk for k, pk in enumerate(p))


@dataclass
class Fit:
    ease: dict[str, float]
    severity: dict[str, float]
    se: dict[str, float]
    tau: list[float]
    n: dict[str, int]
    iterations: int


def fit(ratings: list[tuple[str, str, int]], reference: list[str], prior_sd_ease: float = 1.0,
        prior_sd_severity: float = 10.0, max_iter: int = 500, tol: float = 1e-6,
        group_of: dict[str, str] | None = None) -> Fit:
    items = sorted({i for i, _, _ in ratings})
    raters = sorted({r for _, r, _ in ratings})
    ease = {i: 0.0 for i in items}
    sev = {r: 0.0 for r in raters}
    tau = [0.0] * (CATEGORIES - 1)
    by_item: dict[str, list[tuple[str, int]]] = {i: [] for i in items}
    by_rater: dict[str, list[tuple[str, int]]] = {r: [] for r in raters}
    for i, r, x in ratings:
        by_item[i].append((r, x))
        by_rater[r].append((i, x))
    pe, ps, pt = 1 / prior_sd_ease ** 2, 1 / prior_sd_severity ** 2, 1 / 4.0 ** 2
    groups = group_of or {}
    centre = {g: 0.0 for g in set(groups.values())}
    it = 0
    for it in range(1, max_iter + 1):
        before = (dict(ease), dict(sev), list(tau))
        for i in items:
            mu = centre.get(groups.get(i), 0.0)
            g, h = -(ease[i] - mu) * pe, pe
            for r, x in by_item[i]:
                m, v = moments(ease[i] - sev[r], tau)
                g += x - m
                h += v
            ease[i] += max(-MAX_STEP, min(MAX_STEP, g / h))
        for gname in centre:
            members = [ease[i] for i in items if groups.get(i) == gname]
            centre[gname] = (sum(members) * pe) / (len(members) * pe + 1 / 4.0 ** 2)
        for r in raters:
            g, h = -sev[r] * ps, ps
            for i, x in by_rater[r]:
                m, v = moments(ease[i] - sev[r], tau)
                g -= x - m
                h += v
            sev[r] += max(-MAX_STEP, min(MAX_STEP, g / h))
        for j in range(1, CATEGORIES):   # threshold j: d logL / d tau_j = P(X >= j) - [x >= j]
            g, h = -tau[j - 1] * pt, pt
            for i, r, x in ratings:
                above = sum(probabilities(ease[i] - sev[r], tau)[j:])
                g += above - (x >= j)
                h += above * (1 - above)
            tau[j - 1] += max(-MAX_STEP, min(MAX_STEP, g / h))
        mean_tau = sum(tau) / len(tau)
        tau = [t - mean_tau for t in tau]
        drift = sum(sev[r] for r in reference) / len(reference)
        sev = {r: v - drift for r, v in sev.items()}
        ease = {i: v - drift for i, v in ease.items()}
        centre = {g: v - drift for g, v in centre.items()}
        delta = max(max(abs(ease[i] - before[0][i]) for i in items),
                    max(abs(sev[r] - before[1][r]) for r in raters),
                    max(abs(a - b) for a, b in zip(tau, before[2])))
        if delta < tol:
            break
    se = {r: 1 / math.sqrt(ps + sum(moments(ease[i] - sev[r], tau)[1] for i, _ in by_rater[r])) for r in raters}
    return Fit(ease, sev, se, tau, {r: len(by_rater[r]) for r in raters}, it)


def _shift(obs: list[tuple[float, int]], tau: list[float], prior_sd: float) -> tuple[float, float]:
    """One extra severity-like shift rho over observations (eta, x): eta becomes eta - rho."""
    prec, rho = 1 / prior_sd ** 2, 0.0
    for _ in range(200):
        g, h = -rho * prec, prec
        for eta, x in obs:
            m, v = moments(eta - rho, tau)
            g -= x - m
            h += v
        step = max(-MAX_STEP, min(MAX_STEP, g / h))
        rho += step
        if abs(step) < 1e-8:
            break
    info = prec + sum(moments(eta - rho, tau)[1] for eta, _ in obs)
    return rho, 1 / math.sqrt(info)


def information(fitted: Fit, obs: list[tuple[str, int]], severity: float) -> float:
    """Mean information per rating for a rater at `severity` on these items."""
    return sum(moments(fitted.ease[i] - severity, fitted.tau)[1] for i, _ in obs) / max(len(obs), 1)


def lean_by_stratum(ratings: list[tuple[str, str, int]], stratum_of: dict[str, str], rater: str,
                    reference: list[str], z: float = 1.96) -> tuple[Fit, dict, list[dict]]:
    """Graded counterpart of mfrm.lean_by_stratum: same steps, same output shape."""
    ref = [t for t in ratings if t[1] in reference]
    calibration = fit(ref, reference, group_of=stratum_of)
    obs = [(i, x) for i, r, x in ratings if r == rater and i in calibration.ease]
    overall = _shift([(calibration.ease[i], x) for i, x in obs], calibration.tau, 10.0)
    rows = []
    for s in sorted({stratum_of[i] for i, _ in obs}):
        sub = [(calibration.ease[i], x) for i, x in obs if stratum_of[i] == s]
        sev, se_m = _shift(sub, calibration.tau, 10.0)
        ref_obs = [(calibration.ease[i] - calibration.severity[r], x) for i, r, x in ref if stratum_of[i] == s]
        tau_r, se_r = _shift(ref_obs, calibration.tau, 2.0) if ref_obs else (0.0, math.inf)
        lean = sev - tau_r
        se = math.sqrt(se_m ** 2 + se_r ** 2)
        verdict = "harsher" if lean - z * se > 0 else "softer" if lean + z * se < 0 else "inconclusive"
        rows.append({"stratum": s, "lean": round(lean, 3), "se": round(se, 3), "verdict": verdict,
                     "n_rater": len(sub), "n_reference": len(ref_obs)})
    info = information(calibration, obs, overall[0])
    return calibration, {"severity": overall[0], "se": overall[1], "n": len(obs), "information": info}, rows
