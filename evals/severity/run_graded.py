"""Graded severity report: the same severity question on 0-3 completeness scores, and what grading buys.

    python -m evals.severity.run_graded                       # simulated graded reviewers (teaching mode)
    python -m evals.severity.run_graded --ratings my.jsonl    # real 0-3 ratings instead

Real ratings file (JSON Lines): {"item_id": "s-para-001", "rater": "reviewer-1", "score": 2}

Uses the grounded strata of evals/severity/items.jsonl (verbatim, omission, paraphrase): completeness
is only scored on grounded answers (rubric v2, Part B). The automated rater is the real completeness
grader, evals/completeness.py, judging each answer against the sentence it was made from.

The comparison: the SAME ratings are also cut to pass/fail (score >= 2, the standard-tier bar) and fitted
with the binary model. Grading should give a smaller standard error relative to the lean, so fewer
ratings for the same precision. Logit scales differ between the two models, so compare z = lean / SE
and the ratings-needed figures, not raw logits.

Writes evals/results/graded_severity_report.md and .json. Informational: it does not gate CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from evals import completeness
from evals.severity import mfrm, power, rsm
from evals.severity.generate_items import ITEMS
from evals.versioning import describe, versions

OUT = Path(__file__).parent.parent / "results"
GROUNDED = ("verbatim", "omission", "paraphrase")
PASS_AT = completeness.THRESHOLDS["standard"]

# How complete each stratum's answers read to a careful reviewer, in logits, and the true thresholds.
STRATUM_EASE = {"verbatim": 2.5, "paraphrase": 1.0, "omission": -1.0}
TRUE_TAU = [-1.2, 0.0, 1.2]


def _unit_noise(key: str) -> float:
    return random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)).gauss(0, 1)


def item_ease(item: dict) -> float:
    return STRATUM_EASE[item["stratum"]] + 0.5 * _unit_noise("graded:" + item["id"])


@dataclass(frozen=True)
class GradedReviewer:
    """SIMULATED reviewer with a known severity. Not a person; never present as human data."""
    name: str
    severity: float

    def rate(self, item: dict, seed: int = 0) -> int:
        p = rsm.probabilities(item_ease(item) - self.severity, TRUE_TAU)
        u, acc = random.Random(f"{self.name}:{item['id']}:{seed}").random(), 0.0
        for k, pk in enumerate(p):
            acc += pk
            if u < acc:
                return k
        return len(p) - 1


REVIEWERS = [GradedReviewer("sim-reviewer-A", -0.4), GradedReviewer("sim-reviewer-B", 0.4),
             GradedReviewer("sim-reviewer-C", 0.0)]


def grader_score(item: dict) -> int:
    """The real completeness grader, judged against the sentence the answer was made from."""
    return completeness.score(item["answer"], item["source_sentence"], item["source_sentence"])


def load_items() -> list[dict]:
    rows = [json.loads(line) for line in ITEMS.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [it for it in rows if it["stratum"] in GROUNDED]


def linked_design(items: list[dict], anchors_per_stratum: int = 7, own_per_reviewer: int = 100,
                  seed: int = 0) -> list[tuple[str, str, int]]:
    rng = random.Random(seed)
    by_stratum: dict[str, list[dict]] = {}
    for it in items:
        by_stratum.setdefault(it["stratum"], []).append(it)
    anchors = [it for s in sorted(by_stratum) for it in rng.sample(by_stratum[s], min(anchors_per_stratum, len(by_stratum[s])))]
    ids = {a["id"] for a in anchors}
    rest = [it for it in items if it["id"] not in ids]
    ratings = [(it["id"], "grader", grader_score(it)) for it in items]
    for rv in REVIEWERS:
        for it in anchors + rng.sample(rest, min(own_per_reviewer, len(rest))):
            ratings.append((it["id"], rv.name, rv.rate(it, seed)))
    return ratings


def dichotomise(ratings: list[tuple[str, str, int]]) -> list[tuple[str, str, int]]:
    return [(i, r, int(x >= PASS_AT)) for i, r, x in ratings]


def binary_information(calibration: mfrm.Fit, obs: list[tuple[str, int]], severity: float) -> float:
    ps = [1 / (1 + math.exp(-(calibration.ease[i] - severity))) for i, _ in obs if i in calibration.ease]
    return sum(p * (1 - p) for p in ps) / max(len(ps), 1)


def compare(ratings: list[tuple[str, str, int]], stratum_of: dict[str, str], reference: list[str]) -> dict:
    g_cal, g_all, g_rows = rsm.lean_by_stratum(ratings, stratum_of, "grader", reference)
    binary = dichotomise(ratings)
    b_cal, b_all, b_rows = mfrm.lean_by_stratum(binary, stratum_of, "grader", reference)
    obs = [(i, x) for i, r, x in binary if r == "grader"]
    b_info = binary_information(b_cal, obs, b_all["severity"])
    b_rows_by = {r["stratum"]: r for r in b_rows}
    strata = []
    for g in g_rows:
        b = b_rows_by.get(g["stratum"], {"lean": 0.0, "se": math.inf, "verdict": "n/a"})
        strata.append({"stratum": g["stratum"], "n": g["n_rater"],
                       "graded": {k: g[k] for k in ("lean", "se", "verdict")},
                       "binary": {k: b[k] for k in ("lean", "se", "verdict")},
                       "z_graded": round(g["lean"] / g["se"], 2) if g["se"] else 0.0,
                       "z_binary": round(b["lean"] / b["se"], 2) if b["se"] not in (0, math.inf) else 0.0})
    return {
        "graded": {"calibration": g_cal, "overall": g_all},
        "binary": {"calibration": b_cal, "overall": {**b_all, "information": b_info}},
        "strata": strata,
        "z_overall_graded": g_all["severity"] / g_all["se"],
        "z_overall_binary": b_all["severity"] / b_all["se"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ratings", type=Path, help="real 0-3 ratings (JSONL); replaces the simulated reviewers")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    items = load_items()
    stratum_of = {it["id"]: it["stratum"] for it in items}
    if args.ratings:
        rows = [json.loads(l) for l in args.ratings.read_text(encoding="utf-8").splitlines() if l.strip()]
        human = [(r["item_id"], r["rater"], int(r["score"])) for r in rows if r["item_id"] in stratum_of]
        reference = sorted({r for _, r, _ in human})
        ratings = [(it["id"], "grader", grader_score(it)) for it in items] + human
        mode = f"real ratings from {args.ratings.name}"
    else:
        ratings = linked_design(items)
        reference = [rv.name for rv in REVIEWERS]
        mode = "SIMULATED graded reviewers with known severities (teaching mode, not human data)"

    c = compare(ratings, stratum_of, reference)
    g_cal, g_all = c["graded"]["calibration"], c["graded"]["overall"]
    b_all = c["binary"]["overall"]
    counts = ", ".join(f"{s} {sum(i['stratum'] == s for i in items)}" for s in GROUNDED)
    dist = {k: sum(x == k for _, r, x in ratings if r == "grader") for k in range(4)}
    true = {rv.name: rv.severity for rv in REVIEWERS}
    lean_target = 0.3
    n_graded = power.ratings_to_detect(lean_target, g_all["information"])
    n_binary = power.ratings_to_detect(lean_target, b_all["information"])

    L = ["# Graded severity report (completeness, 0-3)", "", f"Mode: **{mode}**",
         f"Data: {describe(versions(ITEMS))}", "",
         "The same severity question as the binary report, asked of graded completeness scores "
         "(rubric v2, Part B) with a rating scale Rasch model. Positive severity = harsher (lower scores) "
         "than the reference raters.", "",
         "## Design", "",
         f"- Items: the grounded strata of the item bank ({counts})",
         f"- Ratings: grader {sum(r == 'grader' for _, r, _ in ratings)}, reference raters "
         + ", ".join(f"{r} {g_cal.n.get(r, 0)}" for r in reference),
         f"- Grader score distribution: " + ", ".join(f"{k}: {v}" for k, v in dist.items()),
         f"- Estimated thresholds (0->1, 1->2, 2->3): " + ", ".join(f"{t:+.2f}" for t in g_cal.tau)
         + ("" if args.ratings else "   (true: " + ", ".join(f"{t:+.2f}" for t in TRUE_TAU) + ")"), "",
         "## Reference raters (recovery check)", "", "| Rater | True severity | Estimate | SE | Within 2 SE |", "|---|---|---|---|---|"]
    for r in reference:
        t = true.get(r) if not args.ratings else None
        est, se = g_cal.severity[r], g_cal.se[r]
        ok = "" if t is None else ("yes" if abs(est - t) <= 2 * se else "**no**")
        L.append(f"| {r} | {'' if t is None else f'{t:+.2f}'} | {est:+.2f} | {se:.2f} | {ok} |")
    L += ["", f"## Grader overall: severity {g_all['severity']:+.2f} ± {g_all['se']:.2f} (n = {g_all['n']})", "",
          "## Grader lean by item type: graded vs the same ratings cut to pass/fail", "",
          f"Pass/fail cut: score >= {PASS_AT}. Logit scales differ between the models; compare z = lean / SE.", "",
          "| Item type | n | Graded lean | SE | z | Verdict | Binary lean | SE | z | Verdict |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s in c["strata"]:
        g, b = s["graded"], s["binary"]
        L.append(f"| {s['stratum']} | {s['n']} | {g['lean']:+.2f} | {g['se']:.2f} | {s['z_graded']:+.1f} | {g['verdict']} | "
                 f"{b['lean']:+.2f} | {b['se']:.2f} | {s['z_binary']:+.1f} | {b['verdict']} |")
    L += ["", "## What grading buys", "",
          "| | Graded (0-3) | Pass/fail |", "|---|---|---|",
          f"| Mean information per rating | {g_all['information']:.3f} | {b_all['information']:.3f} |",
          f"| Overall severity z (lean / SE) | {c['z_overall_graded']:+.1f} | {c['z_overall_binary']:+.1f} |",
          f"| Ratings to detect a {lean_target}-logit lean (5%, 80% power) | {n_graded} | {n_binary} |", "",
          "Information is in each model's own logit units, so the ratings-needed row is a planning guide, "
          "not an exact exchange rate. The z row is the like-for-like comparison on these ratings: a larger |z| "
          "means the same data give a clearer verdict.", "",
          "Grading only helps if reviewers can use the scale consistently: check reviewer-to-reviewer weighted "
          "kappa (`python -m evals.judge.judge_agreement`) before trusting the extra information.", ""]

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "graded_severity_report.md").write_text("\n".join(L), encoding="utf-8")
    (args.out / "graded_severity_report.json").write_text(json.dumps({
        "mode": mode, "grader_overall": g_all, "binary_overall": b_all, "strata": c["strata"],
        "thresholds": g_cal.tau, "reference": {r: {"severity": g_cal.severity[r], "se": g_cal.se[r]} for r in reference},
        "ratings_to_detect": {"lean": lean_target, "graded": n_graded, "binary": n_binary},
        "data_versions": versions(ITEMS)}, indent=2), encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
