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

HERE = Path(__file__).parent
LABELS = HERE / "human_labels.jsonl"

JUDGE_SYSTEM = """You are a strict evaluator. Decide whether the ANSWER is fully supported
by the CONTEXT. Paraphrases are fine; any added, changed, or contradicted fact is not.
Reply with exactly one word: GROUNDED or NOT_GROUNDED."""


def heuristic_judge(context: str, answer: str) -> str:
    score, _ = metrics.groundedness(answer, [context])
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--judge", choices=["heuristic", "llm"], default="heuristic")
    parser.add_argument("--min-kappa", type=float, default=0.5)
    args = parser.parse_args(argv)

    judge = heuristic_judge if args.judge == "heuristic" else make_llm_judge()
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
    print(f"accuracy: {accuracy:.2f}   cohen_kappa: {kappa:.2f}")
    print(f"confusion (positive = grounded): TP={tp} TN={tn} FP={fp} FN={fn}")
    print("\nDisagreements:")
    for r, p in zip(rows, predicted):
        if p != r["human"]:
            print(f"  {r['id']}: human={r['human']} judge={p}\n      answer: {r['answer']}\n      why: {r['why']}")
    if fp:
        print("\nFalse positives are the dangerous ones: the judge passed an answer a human rejected.")

    if kappa < args.min_kappa:
        print(f"\nJudge agreement gate FAILED: kappa {kappa:.2f} < {args.min_kappa}", file=sys.stderr)
        return 1
    print(f"\nJudge agreement gate passed (kappa >= {args.min_kappa}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
