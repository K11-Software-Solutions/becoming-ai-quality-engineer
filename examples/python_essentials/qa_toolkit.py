"""Python essentials for QA engineers, in one small, runnable module.

Each function is something you will actually write when testing AI systems:
loading eval cases, summarising results, calling an HTTP API with retries,
and running many calls concurrently. See test_qa_toolkit.py for the tests and
articles/02-python-essentials-for-qa.md for the walkthrough.

Run the demo:  python examples/python_essentials/qa_toolkit.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import httpx

log = logging.getLogger("qa_toolkit")


# --- Data structures -------------------------------------------------------

@dataclass
class EvalCase:
    """One test case. A dataclass gives you a typed, readable record for free."""
    id: str
    question: str
    expected: list[str] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    latency_ms: float
    category: str = "general"


# --- JSON in and out -------------------------------------------------------

def load_cases(path: Path) -> list[EvalCase]:
    """Load cases from a JSON list or a JSON Lines file."""
    text = Path(path).read_text(encoding="utf-8")
    rows = json.loads(text) if text.lstrip().startswith("[") else [
        json.loads(line) for line in text.splitlines() if line.strip()
    ]
    cases = []
    for row in rows:
        if "id" not in row or "question" not in row:
            raise ValueError(f"case is missing 'id' or 'question': {row}")
        cases.append(EvalCase(row["id"], row["question"], row.get("expected", []), set(row.get("tags", []))))
    ids = [c.id for c in cases]
    duplicates = [i for i, n in Counter(ids).items() if n > 1]
    if duplicates:
        raise ValueError(f"duplicate case ids: {duplicates}")
    return cases


def save_results(results: list[EvalResult], path: Path) -> None:
    Path(path).write_text(json.dumps([r.__dict__ for r in results], indent=2), encoding="utf-8")


# --- Functions that summarise results -----------------------------------------

def pass_rate(results: list[EvalResult]) -> float:
    return round(sum(r.passed for r in results) / len(results), 3) if results else 0.0


def pass_rate_by_category(results: list[EvalResult]) -> dict[str, float]:
    groups: dict[str, list[EvalResult]] = {}
    for r in results:
        groups.setdefault(r.category, []).append(r)
    return {cat: pass_rate(items) for cat, items in sorted(groups.items())}


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile, e.g. percentile(latencies, 95) for p95."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    rank = max(1, round(pct / 100 * len(ordered)))
    return ordered[rank - 1]


# --- HTTP with retries -----------------------------------------------------

RETRYABLE = {429, 500, 502, 503, 504}


def post_json_with_retry(client: httpx.Client, url: str, payload: dict,
                         retries: int = 3, backoff_s: float = 0.2) -> dict:
    """POST JSON, retrying on rate limits and server errors (common with LLM APIs)."""
    for attempt in range(1, retries + 1):
        resp = client.post(url, json=payload)
        if resp.status_code not in RETRYABLE:
            resp.raise_for_status()
            return resp.json()
        log.warning("attempt %d/%d got %d from %s", attempt, retries, resp.status_code, url)
        if attempt < retries:
            wait = float(resp.headers.get("Retry-After", backoff_s * attempt))
            time.sleep(wait)
    raise RuntimeError(f"gave up after {retries} attempts: last status {resp.status_code}")


# --- Async: many calls at once, with a concurrency limit --------------------

async def ask_many(client: httpx.AsyncClient, questions: list[str], max_concurrency: int = 5) -> list[dict]:
    """Send questions concurrently but never more than max_concurrency at a time.

    Limiting concurrency is how you avoid tripping an LLM provider's rate limit.
    Results come back in the same order as the questions.
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def one(q: str) -> dict:
        async with semaphore:
            resp = await client.post("/ask", json={"question": q})
            resp.raise_for_status()
            return resp.json()

    return await asyncio.gather(*(one(q) for q in questions))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    results = [EvalResult("a", True, 120, "factual"), EvalResult("b", False, 340, "factual"),
               EvalResult("c", True, 95, "safety")]
    print("pass rate:", pass_rate(results))
    print("by category:", pass_rate_by_category(results))
    print("p95 latency:", percentile([r.latency_ms for r in results], 95), "ms")
