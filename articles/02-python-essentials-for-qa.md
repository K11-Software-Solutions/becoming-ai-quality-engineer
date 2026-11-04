# 02. Python Essentials for QA Engineers

> **Series:** Becoming an AI Quality Engineer · [Index](../README.md#article-index) · Previous: [01](01-transferable-qa-skills.md) · Next: [03. AI Fundamentals](03-ai-fundamentals.md)

Most AI evaluation tools, model SDKs and tracing libraries are Python-first. You do not need to be a software engineer, but you do need to read and write everyday Python comfortably. This article covers the parts you will use every week, with runnable code and tests in [`examples/python_essentials/`](../examples/python_essentials/).

```bash
python examples/python_essentials/qa_toolkit.py        # run the demo
pytest examples/python_essentials -v                   # run its tests
```

If you know Java or JavaScript, the concepts are the same. Focus on the syntax and the testing idioms.

## 1. Data structures you will use constantly

| Structure | Use it for | Example |
|---|---|---|
| `list` | ordered results, ranked retrieval | `["refund-policy#1", "pricing-plans#3"]` |
| `dict` | a JSON object, a test case, a metric summary | `{"correctness": 0.93}` |
| `set` | membership and comparison, ignoring order | `set(citations) <= set(sources)` |
| `collections.Counter` | counting, finding duplicates | `Counter(ids)` |
| `dataclass` | a typed record with named fields | `EvalCase`, `EvalResult` |

```python
from dataclasses import dataclass, field

@dataclass
class EvalCase:
    id: str
    question: str
    expected: list[str] = field(default_factory=list)  # never use a bare [] default
    tags: set[str] = field(default_factory=set)
```

The set comparison `set(resp.citations) <= set(resp.sources)` reads as "every citation is one of the retrieved chunks", and it is a real check in this repo's eval harness.

## 2. Functions with type hints

Small, pure functions are easy to test. Type hints make intent obvious and let your editor catch mistakes.

```python
def pass_rate(results: list[EvalResult]) -> float:
    return round(sum(r.passed for r in results) / len(results), 3) if results else 0.0
```

Note the guard for the empty list. Division by zero on an empty result set is a classic bug in hand-written eval scripts.

## 3. JSON and JSON Lines

Eval datasets are usually **JSON Lines** (`.jsonl`): one JSON object per line. It is easy to append to, diff and stream.

```python
import json
from pathlib import Path

def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
```

Always pass `encoding="utf-8"` on Windows. Validate what you load: `load_cases` in the example raises an error on missing fields and duplicate IDs, because a broken dataset silently produces wrong metrics.

## 4. HTTP requests with httpx

`httpx` works like `requests` but also supports async and has a built-in mock transport. LLM APIs rate-limit (429) and have transient errors (5xx), so retries are a normal part of client code:

```python
RETRYABLE = {429, 500, 502, 503, 504}

def post_json_with_retry(client, url, payload, retries=3, backoff_s=0.2):
    for attempt in range(1, retries + 1):
        resp = client.post(url, json=payload)
        if resp.status_code not in RETRYABLE:
            resp.raise_for_status()      # 4xx other than 429: fail fast, do not retry
            return resp.json()
        time.sleep(float(resp.headers.get("Retry-After", backoff_s * attempt)))
    raise RuntimeError("gave up")
```

## 5. pytest: the essentials

pytest is the test runner for everything in this repo, including the DeepEval suite.

**Plain asserts.** No `assertEqual` methods; pytest rewrites `assert` to show useful diffs.

**Fixtures** build test data or objects and inject them by name:

```python
@pytest.fixture
def results() -> list[EvalResult]:
    return [EvalResult("a", True, 100, "factual"), EvalResult("b", False, 300, "factual")]

def test_pass_rate(results):
    assert pass_rate(results) == 0.5
```

Fixtures can have `scope="session"` (built once per run, like the retriever in [`tests/conftest.py`](../tests/conftest.py)) and can be **factories** that return a function, like `make_pipeline(behavior="hallucinate", top_k=1)`.

**Parametrize** runs one test over many inputs. It is boundary-value analysis in one decorator:

```python
@pytest.mark.parametrize("pct, expected", [(50, 200), (75, 300), (95, 400), (100, 400)])
def test_percentile(results, pct, expected):
    assert percentile([r.latency_ms for r in results], pct) == expected
```

**Built-in fixtures** worth knowing:

| Fixture | What it gives you |
|---|---|
| `tmp_path` | a fresh temporary directory per test |
| `caplog` | captured log records, so you can assert on warnings |
| `monkeypatch` | set env vars or replace attributes for one test |

**Markers** tag tests so you can select them: this repo marks browser tests with `@pytest.mark.ui` and excludes them by default (`pytest -m ui` runs them).

## 6. Mocking HTTP without a network

Never call a paid API in a unit test. `httpx.MockTransport` takes a function that receives the request and returns a response:

```python
def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(429, headers={"Retry-After": "0"}) if first_call() else httpx.Response(200, json={"answer": "ok"})

client = httpx.Client(base_url="https://api.example.test", transport=httpx.MockTransport(handler))
```

The same technique tests the real OpenAI and Anthropic clients in [`tests/unit/test_llm.py`](../tests/unit/test_llm.py) with no key.

## 7. Logging instead of print

```python
import logging
log = logging.getLogger("qa_toolkit")
log.warning("attempt %d/%d got %d from %s", attempt, retries, resp.status_code, url)
```

Use `%s` placeholders (formatted lazily), configure the format once with `logging.basicConfig`, and assert on logs with `caplog`. In AI systems, logs and traces are often the only record of what the model actually saw.

## 8. Async calls: many requests at once

Evals send hundreds of requests. Running them one at a time is slow; running all at once trips rate limits. Use `asyncio.gather` with a `Semaphore`:

```python
async def ask_many(client: httpx.AsyncClient, questions: list[str], max_concurrency: int = 5) -> list[dict]:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def one(q: str) -> dict:
        async with semaphore:                       # at most N in flight
            resp = await client.post("/ask", json={"question": q})
            resp.raise_for_status()
            return resp.json()

    return await asyncio.gather(*(one(q) for q in questions))   # keeps input order
```

The test `test_ask_many_keeps_order_and_limits_concurrency` proves both properties. It calls `asyncio.run(...)` inside a normal test, so no extra pytest plugin is needed.

## 9. Virtual environments

Keep each project's dependencies isolated:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

Pin versions in `requirements*.txt` (this repo does) so your evals are reproducible.

## Checklist

You are ready for the next articles when you can, without looking things up:

- [ ] load a JSONL file into a list of dataclasses and validate it
- [ ] write a parametrized pytest test with a fixture
- [ ] mock an HTTP API with `httpx.MockTransport`
- [ ] explain why the retry helper does not retry a 400
- [ ] run 20 requests concurrently with a limit of 5

---
Next: [03. AI Fundamentals for Testers](03-ai-fundamentals.md)
