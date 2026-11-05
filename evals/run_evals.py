"""Run the golden dataset through the RAG app, score it, and enforce quality gates.

Usage (from the repo root):

    python -m evals.run_evals                       # fake LLM, gates on
    FAKE_LLM_BEHAVIOR=hallucinate python -m evals.run_evals   # watch gates fail
    LLM_PROVIDER=openai python -m evals.run_evals   # real model (needs a key)
    python -m evals.run_evals --no-gate             # report only, always exit 0

Outputs ``evals/results/report.json`` and ``evals/results/report.md``.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

from app.rag import RAGPipeline
from evals import metrics
from evals.versioning import describe, versions

HERE = Path(__file__).parent
DEFAULT_DATASET = HERE / "datasets" / "golden_qa.jsonl"
DEFAULT_THRESHOLDS = HERE / "thresholds.json"
DEFAULT_OUT = HERE / "results"


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def evaluate_case(pipeline: RAGPipeline, case: dict) -> dict:
    resp = pipeline.ask(case["question"])
    should_refuse = case.get("should_refuse", False)
    result: dict = {
        "id": case["id"],
        "category": case["category"],
        "group": case.get("group"),
        "question": case["question"],
        "answer": resp.answer,
        "refused": resp.refused,
        "blocked": resp.blocked,
        "sources": resp.sources,
        "citations": resp.citations,
        "notes": case.get("notes"),
        "checks": {},
    }
    checks = result["checks"]

    # Correctness: refusal behaviour first, then key facts.
    if should_refuse:
        checks["correct"] = resp.refused
        checks["missing_facts"] = []
    else:
        has_facts, missing = metrics.contains_all_facts(resp.answer, case.get("expected_facts", []))
        checks["correct"] = (not resp.refused) and has_facts if case.get("expected_facts") else not resp.refused
        checks["missing_facts"] = missing

    # Groundedness: is every answer sentence supported by retrieved context?
    if resp.refused:
        g_score, unsupported = 1.0, []
    else:
        g_score, unsupported = metrics.groundedness(resp.answer, resp.contexts)
    checks["groundedness"] = round(g_score, 3)
    checks["unsupported_sentences"] = unsupported

    # Citations must point at chunks that were actually retrieved.
    checks["citations_valid"] = set(resp.citations) <= set(resp.sources)

    # Retrieval quality, only where we know the right chunk.
    if case.get("expected_sources"):
        checks["retrieval"] = metrics.retrieval_metrics(resp.sources, case["expected_sources"])

    # Safety: forbidden content must never appear.
    leaked = metrics.contains_forbidden(resp.answer, case.get("forbidden", []))
    checks["forbidden_found"] = leaked
    if case["category"] == "injection":
        checks["injection_resisted"] = not leaked and (resp.refused if should_refuse else True)

    result["passed"] = bool(
        checks["correct"] and g_score == 1.0 and checks["citations_valid"] and not leaked
    )
    return result


def consistency(results: list[dict]) -> dict[str, bool]:
    """A group is consistent when every variant passes and cites the same chunks."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        if r["group"]:
            groups[r["group"]].append(r)
    out = {}
    for name, members in groups.items():
        same_citations = len({tuple(m["citations"]) for m in members}) == 1
        out[name] = same_citations and all(m["checks"]["correct"] for m in members)
    return out


def summarize(results: list[dict]) -> dict:
    def rate(items: list[bool]) -> float:
        return round(sum(items) / len(items), 3) if items else 1.0

    answerable = [r for r in results if r["category"] not in {"unanswerable", "injection"}]
    unanswerable = [r for r in results if r["category"] == "unanswerable"]
    with_retrieval = [r for r in results if "retrieval" in r["checks"]]
    injection = [r for r in results if r["category"] == "injection"]
    groups = consistency(results)
    by_category: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r["passed"])

    return {
        "cases": len(results),
        "pass_rate": rate([r["passed"] for r in results]),
        "correctness": rate([r["checks"]["correct"] for r in answerable]),
        "refusal_accuracy": rate([r["checks"]["correct"] for r in unanswerable]),
        "groundedness": round(mean(r["checks"]["groundedness"] for r in results), 3),
        "citation_validity": rate([r["checks"]["citations_valid"] for r in results]),
        "retrieval_hit_rate": rate([r["checks"]["retrieval"]["hit"] == 1.0 for r in with_retrieval]),
        "retrieval_mrr": round(mean(r["checks"]["retrieval"]["rr"] for r in with_retrieval), 3) if with_retrieval else 1.0,
        "injection_resistance": rate([r["checks"]["injection_resisted"] for r in injection]),
        "consistency": rate(list(groups.values())),
        "groups": groups,
        "by_category": {k: rate(v) for k, v in sorted(by_category.items())},
    }


def check_gates(summary: dict, thresholds: dict) -> list[str]:
    failures = []
    for metric, minimum in thresholds.items():
        value = summary.get(metric)
        if value is None:
            failures.append(f"{metric}: metric not found in summary")
        elif value < minimum:
            failures.append(f"{metric}: {value} < required {minimum}")
    return failures


def to_markdown(summary: dict, results: list[dict], thresholds: dict, failures: list[str], model: str,
                data_versions: dict[str, str] | None = None) -> str:
    lines = [
        "# Evaluation report",
        "",
        f"Model: `{model}`  |  Cases: {summary['cases']}  |  Pass rate: {summary['pass_rate']:.0%}",
        "",
        f"Data: {describe(data_versions)}  (compare scores only when these match)" if data_versions else "",
        "",
        "| Metric | Value | Gate |",
        "|---|---|---|",
    ]
    for key in ["correctness", "refusal_accuracy", "groundedness", "citation_validity",
                "retrieval_hit_rate", "retrieval_mrr", "injection_resistance", "consistency"]:
        gate = thresholds.get(key)
        status = "" if gate is None else (f">= {gate} ✅" if summary[key] >= gate else f">= {gate} ❌")
        lines.append(f"| {key} | {summary[key]} | {status} |")
    lines += ["", "## Failing cases", ""]
    failing = [r for r in results if not r["passed"]]
    if not failing:
        lines.append("None.")
    for r in failing:
        lines.append(f"- **{r['id']}** ({r['category']}): {r['question']}")
        lines.append(f"  - answer: {r['answer']}")
        c = r["checks"]
        if c["missing_facts"]:
            lines.append(f"  - missing facts: {c['missing_facts']}")
        if c["unsupported_sentences"]:
            lines.append(f"  - unsupported: {c['unsupported_sentences']}")
        if c["forbidden_found"]:
            lines.append(f"  - forbidden content: {c['forbidden_found']}")
        if r.get("notes"):
            lines.append(f"  - notes: {r['notes']}")
    lines += ["", "## Gate result", "", "PASSED" if not failures else "FAILED: " + "; ".join(failures), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-gate", action="store_true", help="report only; always exit 0")
    args = parser.parse_args(argv)

    pipeline = RAGPipeline.from_settings()
    cases = load_jsonl(args.dataset)
    results = [evaluate_case(pipeline, c) for c in cases]
    summary = summarize(results)
    thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
    failures = check_gates(summary, thresholds)

    args.out.mkdir(parents=True, exist_ok=True)
    data_versions = versions(args.dataset, args.thresholds)
    report = {"model": pipeline.llm.name, "data_versions": data_versions, "summary": summary,
              "thresholds": thresholds, "gate_failures": failures, "results": results}
    (args.out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = to_markdown(summary, results, thresholds, failures, pipeline.llm.name, data_versions)
    (args.out / "report.md").write_text(md, encoding="utf-8")

    print(md)
    if failures and not args.no_gate:
        print("Quality gate FAILED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
