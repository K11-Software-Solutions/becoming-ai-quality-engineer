"""Validate the evaluator: how often does our groundedness judge agree with humans?

An automated judge (a heuristic or an LLM-as-judge) is itself a model that can
be wrong. Before you let it gate a release, measure it against a small set of
human labels and look at every disagreement.

Usage (from the repo root):

    python -m evals.judge.judge_agreement                 # heuristic judge, offline
    python -m evals.judge.judge_agreement --judge llm     # LLM judge (needs LLM_PROVIDER + key)
    python -m evals.judge.judge_agreement --min-kappa 0.5 # change the gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import Settings
from app.llm import get_llm
from evals import metrics
from evals.versioning import describe, versions

HERE = Path(__file__).parent
LABELS = HERE / "human_labels.jsonl"

JUDGE_SYSTEM = """You are a strict evaluator. Decide whether the ANSWER is fully supported
by the CONTEXT. Paraphrases are fine; any added, changed, or contradicted fact is not.
Reply with exactly one word: GROUNDED or NOT_GROUNDED."""


def heuristic_judge(context: str, answer: str) -> str:
    """Word overlap plus the number/negation check (the judge used by the eval gate)."""
    score, _ = metrics.groundedness(answer, [context])
    return "grounded" if score == 1.0 else "not_grounded"


def overlap_judge(context: str, answer: str) -> str:
    """Word overlap only: the original judge, kept for comparison."""
    score, _ = metrics.groundedness(answer, [context], check_facts=False)
    return "grounded" if score == 1.0 else "not_grounded"


def make_llm_judge():
    settings = Settings.from_env()
    if settings.llm_provider == "fake":
        raise SystemExit("--judge llm needs LLM_PROVIDER=openai or anthropic and an API key")
    llm = get_llm(settings)

    def judge(context: str, answer: str) -> str:
        reply = llm.generate(JUDGE_SYSTEM, f"CONTEXT:\n{context}\n\nANSWER:\n{answer}").upper()
        return "not_grounded" if "NOT" in reply else "grounded"

    return judge


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Agreement corrected for chance. 1 = perfect, 0 = chance level."""
    n = len(a)
    labels = sorted(set(a) | set(b))
    observed = sum(x == y for x, y in zip(a, b)) / n
    expected = sum((a.count(lbl) / n) * (b.count(lbl) / n) for lbl in labels)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def stratified(rows: list[dict], predicted: list[str]) -> list[dict]:
    """Agreement and lean per item type.

    A single pooled kappa can hide a judge that is lenient on one kind of item
    and harsh on another: the errors cancel out in the average. Per stratum:
      lenient = judge said grounded, human said not   (false pass: the dangerous direction)
      harsh   = judge said not grounded, human said grounded   (false fail)
      lean    = (lenient - harsh) / n   >0 softer than the human, <0 harsher
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    for r, p in zip(rows, predicted):
        groups.setdefault(r.get("stratum", "unlabelled"), []).append((r["human"], p))
    out = []
    for name, pairs in sorted(groups.items()):
        n = len(pairs)
        lenient = sum(h == "not_grounded" and p == "grounded" for h, p in pairs)
        harsh = sum(h == "grounded" and p == "not_grounded" for h, p in pairs)
        out.append({"stratum": name, "n": n, "agreement": round(sum(h == p for h, p in pairs) / n, 2),
                    "lenient": lenient, "harsh": harsh, "lean": round((lenient - harsh) / n, 2)})
    return out


REVIEWERS = HERE / "reviewer_labels.jsonl"


def reviewer_agreement(final: dict[str, str]) -> dict | None:
    """Agreement between the two independent human reviewers, before adjudication.

    This is the ceiling for any automated judge: if two careful people agree at
    kappa 0.7, a judge "agreeing" at 0.9 is more likely overfitted to the labels
    than better than the humans.
    """
    if not REVIEWERS.is_file():
        return None
    rows = [json.loads(line) for line in REVIEWERS.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if "id" in r]
    a = [r["reviewer_a"] for r in rows]
    b = [r["reviewer_b"] for r in rows]
    return {
        "n": len(rows),
        "kappa_a_b": round(cohen_kappa(a, b), 2),
        "kappa_a_final": round(cohen_kappa(a, [final[r["id"]] for r in rows]), 2),
        "kappa_b_final": round(cohen_kappa(b, [final[r["id"]] for r in rows]), 2),
        "disagreements": [{"id": r["id"], **r["adjudication"]} for r in rows if r["reviewer_a"] != r["reviewer_b"]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--judge", choices=["heuristic", "overlap", "llm"], default="heuristic")
    parser.add_argument("--min-kappa", type=float, default=0.5)
    args = parser.parse_args(argv)

    judge = {"heuristic": heuristic_judge, "overlap": overlap_judge}.get(args.judge) or make_llm_judge()
    rows = [json.loads(line) for line in LABELS.read_text(encoding="utf-8").splitlines() if line.strip()]
    human = [r["human"] for r in rows]
    predicted = [judge(r["context"], r["answer"]) for r in rows]

    tp = sum(h == p == "grounded" for h, p in zip(human, predicted))
    tn = sum(h == p == "not_grounded" for h, p in zip(human, predicted))
    fp = sum(h == "not_grounded" and p == "grounded" for h, p in zip(human, predicted))
    fn = sum(h == "grounded" and p == "not_grounded" for h, p in zip(human, predicted))
    accuracy = (tp + tn) / len(rows)
    kappa = cohen_kappa(human, predicted)

    print(f"Judge: {args.judge}   items: {len(rows)}")
    label_files = [p for p in (LABELS, HERE / "reviewer_labels.jsonl", HERE / "RUBRIC.md") if p.is_file()]
    print(f"labels: {describe(versions(*label_files))}")
    print(f"accuracy: {accuracy:.2f}   cohen_kappa: {kappa:.2f}")
    print(f"confusion (positive = grounded): TP={tp} TN={tn} FP={fp} FN={fn}")
    print("\nDisagreements:")
    for r, p in zip(rows, predicted):
        if p != r["human"]:
            print(f"  {r['id']}: human={r['human']} judge={p}\n      answer: {r['answer']}\n      why: {r['why']}")
    if fp:
        print("\nFalse positives are the dangerous ones: the judge passed an answer a human rejected.")

    strata = stratified(rows, predicted)
    print("\nBy item type (lean > 0: softer than the human labeller; < 0: harsher):")
    print(f"  {'stratum':<14} {'n':>3} {'agree':>6} {'lenient':>8} {'harsh':>6} {'lean':>6}")
    for s in strata:
        print(f"  {s['stratum']:<14} {s['n']:>3} {s['agreement']:>6.2f} {s['lenient']:>8} {s['harsh']:>6} {s['lean']:>+6.2f}")
    soft = [s["stratum"] for s in strata if s["lean"] > 0]
    if soft:
        print(f"\nThe judge is softer than the human on: {', '.join(soft)}. Cover these with another check.")

    reviewers = reviewer_agreement({r["id"]: r["human"] for r in rows})
    if reviewers:
        print(f"\nHuman ceiling (two independent reviewers, rubric in evals/judge/RUBRIC.md, {reviewers['n']} items):")
        print(f"  reviewer A vs B: kappa {reviewers['kappa_a_b']:.2f}   "
              f"A vs final: {reviewers['kappa_a_final']:.2f}   B vs final: {reviewers['kappa_b_final']:.2f}")
        for d in reviewers["disagreements"]:
            print(f"  {d['id']}: adjudicated {d['final']} by {d['rule']}: {d['note']}")
        if kappa > reviewers["kappa_a_b"]:
            print(f"  Note: the judge (kappa {kappa:.2f}) agrees with the final labels more than the reviewers agree with "
                  "each other. Final labels are adjudicated, so some gain is expected, but also suspect overfitting: "
                  "check the judge on labels it was not tuned on.")

    if kappa < args.min_kappa:
        print(f"\nJudge agreement gate FAILED: kappa {kappa:.2f} < {args.min_kappa}", file=sys.stderr)
        return 1
    print(f"\nJudge agreement gate passed (kappa >= {args.min_kappa}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
