"""Grader severity report: where does the judge sit, by item type, with standard errors?

    python -m evals.severity.run_severity                      # simulated reviewers (teaching mode)
    python -m evals.severity.run_severity --ratings my.jsonl   # real human ratings instead

Real ratings file (JSON Lines): {"item_id": "s-nume-001", "rater": "reviewer-1", "grounded": 1}

Writes evals/results/severity_report.md and .json. Informational: it does not gate CI.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from evals.severity import mfrm, power
from evals.severity.generate_items import ITEMS, STRATA
from evals.severity.raters import REVIEWERS, judge_rate, linked_design
from evals.versioning import describe, versions

HERE = Path(__file__).parent
OUT = HERE.parent / "results"


def load_items() -> list[dict]:
    return [json.loads(line) for line in ITEMS.read_text(encoding="utf-8").splitlines() if line.strip()]


def accuracy_by_stratum(ratings, items_by_id, rater_filter) -> dict[str, float]:
    hits: dict[str, list[int]] = {}
    for i, r, x in ratings:
        if rater_filter(r):
            item = items_by_id[i]
            hits.setdefault(item["stratum"], []).append(int((x == 1) == (item["label"] == "grounded")))
    return {s: sum(v) / len(v) for s, v in hits.items()}


def small_sample(items: list[dict], per_stratum: int = 3, seed: int = 0) -> list[tuple[str, str, int]]:
    """The same study at the size of a typical hand-labelled set: ~24 items, every rater rates all."""
    rng = random.Random(seed)
    chosen = []
    for s in STRATA:
        pool = [it for it in items if it["stratum"] == s]
        chosen += rng.sample(pool, min(per_stratum + (1 if s in ("numeric", "negation", "paraphrase") else 0), len(pool)))
    ratings = [(it["id"], "judge", judge_rate(it)) for it in chosen]
    for rv in REVIEWERS:
        ratings += [(it["id"], rv.name, rv.rate(it)) for it in chosen]
    return ratings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ratings", type=Path, help="real human ratings (JSONL); replaces the simulated reviewers")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    items = load_items()
    by_id = {it["id"]: it for it in items}
    stratum_of = {it["id"]: it["stratum"] for it in items}
    if args.ratings:
        rows = [json.loads(l) for l in args.ratings.read_text(encoding="utf-8").splitlines() if l.strip()]
        human = [(r["item_id"], r["rater"], int(r["grounded"])) for r in rows]
        reference = sorted({r for _, r, _ in human})
        ratings = [(it["id"], "judge", judge_rate(it)) for it in items] + human
        mode = f"real ratings from {args.ratings.name}"
    else:
        ratings = linked_design(items)
        reference = [rv.name for rv in REVIEWERS]
        mode = "SIMULATED reviewers with known severities (teaching mode, not human data)"

    calibration, judge_overall, leans = mfrm.lean_by_stratum(ratings, stratum_of, "judge", reference)
    judge_acc = accuracy_by_stratum(ratings, by_id, lambda r: r == "judge")
    human_acc = accuracy_by_stratum(ratings, by_id, lambda r: r in reference)

    small = small_sample(items)
    s_cal, s_overall, s_leans = mfrm.lean_by_stratum(small, stratum_of, "judge", reference)
    observed_info = sum(p * (1 - p) for p in (
        1 / (1 + 2.718281828 ** -(calibration.ease[i] - judge_overall["severity"]))
        for i, r, _ in ratings if r == "judge" and i in calibration.ease)) / max(judge_overall["n"], 1)

    counts = ", ".join("{} {}".format(s, sum(i["stratum"] == s for i in items)) for s in STRATA)
    L = ["# Grader severity report", "", f"Mode: **{mode}**",
         f"Data: {describe(versions(ITEMS))}", "",
         "Severity is a location on a logit scale with a standard error; positive = harsher (says "
         "\"not grounded\" more often) than the reference raters. Item ease is calibrated on the reference "
         "raters only, so the judge's own errors cannot leak into it.", "",
         "## Design", "",
         f"- Items: {len(items)} generated, labelled by construction ({counts})",
         f"- Ratings: judge {sum(r == 'judge' for _, r, _ in ratings)}, reference raters "
         + ", ".join(f"{r} {calibration.n.get(r, 0)}" for r in reference), "",
         "## Reference raters (recovery check)", "", "| Rater | True severity | Estimate | SE | Within 2 SE |", "|---|---|---|---|---|"]
    true = {rv.name: rv.severity for rv in REVIEWERS}
    for r in reference:
        t = true.get(r)
        est, se = calibration.severity[r], calibration.se[r]
        ok = "" if t is None else ("yes" if abs(est - t) <= 2 * se else "**no**")
        L.append(f"| {r} | {'' if t is None else f'{t:+.2f}'} | {est:+.2f} | {se:.2f} | {ok} |")
    L += ["", f"## Judge overall: severity {judge_overall['severity']:+.2f} ± {judge_overall['se']:.2f} "
          f"(n = {judge_overall['n']} ratings on calibrated items)", "",
          "## Judge lean by item type", "",
          "| Item type | Lean vs reference (logits) | SE | Verdict | Judge accuracy | Reference accuracy |",
          "|---|---|---|---|---|---|"]
    for row in leans:
        s = row["stratum"]
        L.append(f"| {s} | {row['lean']:+.2f} | {row['se']:.2f} | {row['verdict']} | "
                 f"{judge_acc.get(s, 0):.2f} | {human_acc.get(s, 0):.2f} |")
    L += ["", "Severity is relative to the reference raters, not to the truth: \"harsher\" is not the same as \"wrong\". "
          "Read the lean together with accuracy against the by-construction labels.", "",
          f"## The same study with {len({i for i, _, _ in small})} items", "",
          f"Every rater rates every item. Judge overall: {s_overall['severity']:+.2f} ± {s_overall['se']:.2f}.", "",
          "| Item type | Lean | SE | Verdict |", "|---|---|---|---|"]
    for row in s_leans:
        L.append(f"| {row['stratum']} | {row['lean']:+.2f} | {row['se']:.2f} | {row['verdict']} |")
    L += ["", "## Power analysis", "",
          f"Observed mean information per judge rating: {observed_info:.3f} (0.25 is the best case).", "",
          "| Ratings per rater | Approx. SE at observed information |", "|---|---|"]
    for n in (24, 100, 200, 400, 700):
        L.append(f"| {n} | {power.se_for(n, observed_info):.2f} |")
    L += ["", f"Ratings per rater to detect a 0.3-logit lean (5%, 80% power) at this information: "
          f"**{power.ratings_to_detect(0.3, observed_info)}** per stratum compared.", ""]

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "severity_report.md").write_text("\n".join(L), encoding="utf-8")
    (args.out / "severity_report.json").write_text(json.dumps({
        "mode": mode, "judge_overall": judge_overall, "leans": leans, "small_sample_leans": s_leans,
        "reference": {r: {"severity": calibration.severity[r], "se": calibration.se[r]} for r in reference},
        "judge_accuracy": judge_acc, "reference_accuracy": human_acc, "observed_information": observed_info,
        "data_versions": versions(ITEMS)}, indent=2), encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
