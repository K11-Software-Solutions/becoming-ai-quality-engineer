"""pytest essentials: fixtures, parametrize, tmp_path, caplog, mocking HTTP, async."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest

from examples.python_essentials.qa_toolkit import (
    EvalResult,
    ask_many,
    load_cases,
    pass_rate,
    pass_rate_by_category,
    percentile,
    post_json_with_retry,
    save_results,
)


# A fixture builds test data once and hands it to any test that names it.
@pytest.fixture
def results() -> list[EvalResult]:
    return [
        EvalResult("a", True, 100, "factual"),
        EvalResult("b", False, 300, "factual"),
        EvalResult("c", True, 200, "safety"),
        EvalResult("d", True, 400, "safety"),
    ]


def test_pass_rate(results):
    assert pass_rate(results) == 0.75


def test_pass_rate_by_category(results):
    assert pass_rate_by_category(results) == {"factual": 0.5, "safety": 1.0}


def test_pass_rate_of_nothing_is_zero():
    assert pass_rate([]) == 0.0


# parametrize turns one test into many: classic boundary-value analysis.
@pytest.mark.parametrize("pct, expected", [(50, 200), (75, 300), (95, 400), (100, 400)])
def test_percentile(results, pct, expected):
    assert percentile([r.latency_ms for r in results], pct) == expected


def test_percentile_rejects_empty():
    with pytest.raises(ValueError):
        percentile([], 95)


# tmp_path gives each test its own temporary folder.
def test_load_cases_from_jsonl(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text('{"id": "1", "question": "q1", "tags": ["smoke"]}\n{"id": "2", "question": "q2"}\n')
    cases = load_cases(path)
    assert [c.id for c in cases] == ["1", "2"]
    assert cases[0].tags == {"smoke"}


def test_load_cases_rejects_duplicates(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"id": "1", "question": "a"}, {"id": "1", "question": "b"}]))
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(path)


def test_load_cases_rejects_missing_fields(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"id": "1"}]))
    with pytest.raises(ValueError, match="missing"):
        load_cases(path)


def test_save_results_round_trip(tmp_path, results):
    out = tmp_path / "results.json"
    save_results(results, out)
    assert json.loads(out.read_text())[1] == {"case_id": "b", "passed": False, "latency_ms": 300, "category": "factual"}


# httpx.MockTransport fakes the server, so the test needs no network.
def make_client(responses: list[httpx.Response]) -> tuple[httpx.Client, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses[len(seen) - 1]

    return httpx.Client(base_url="https://api.example.test", transport=httpx.MockTransport(handler)), seen


def test_retry_then_success(caplog):
    client, seen = make_client([
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"answer": "ok"}),
    ])
    with caplog.at_level(logging.WARNING):
        assert post_json_with_retry(client, "/ask", {"question": "hi"}, backoff_s=0) == {"answer": "ok"}
    assert len(seen) == 2
    assert "got 429" in caplog.text  # caplog captures log output for assertions


def test_retry_gives_up():
    client, _ = make_client([httpx.Response(503)] * 3)
    with pytest.raises(RuntimeError, match="gave up"):
        post_json_with_retry(client, "/ask", {}, retries=3, backoff_s=0)


def test_client_errors_are_not_retried():
    client, seen = make_client([httpx.Response(400)])
    with pytest.raises(httpx.HTTPStatusError):
        post_json_with_retry(client, "/ask", {})
    assert len(seen) == 1


def test_ask_many_keeps_order_and_limits_concurrency():
    in_flight = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        question = json.loads(request.content)["question"]
        return httpx.Response(200, json={"echo": question})

    async def run() -> list[dict]:
        async with httpx.AsyncClient(base_url="https://api.example.test",
                                     transport=httpx.MockTransport(handler)) as client:
            return await ask_many(client, [f"q{i}" for i in range(10)], max_concurrency=3)

    answers = asyncio.run(run())  # no pytest-asyncio plugin needed
    assert [a["echo"] for a in answers] == [f"q{i}" for i in range(10)]
    assert peak <= 3
