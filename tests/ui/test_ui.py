"""Playwright UI tests. They start the real app with uvicorn on a free port.

Setup once:  python -m playwright install chromium
Run:         pytest -m ui
"""
from __future__ import annotations

import re
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import Page, expect

from app.config import DEFAULT_DOCS_DIR
from app.llm import FakeLLM
from app.main import create_app
from app.rag import RAGPipeline
from app.retriever import BM25Retriever

pytestmark = pytest.mark.ui


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    pipeline = RAGPipeline(BM25Retriever.from_dir(DEFAULT_DOCS_DIR), FakeLLM())
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(pipeline), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def ask(page: Page, base_url: str, question: str) -> None:
    page.goto(base_url)
    page.get_by_label("Question").fill(question)
    page.get_by_role("button", name="Ask").click()


def test_user_can_ask_and_see_cited_answer(page: Page, live_server):
    ask(page, live_server, "How much does the Pro plan cost per year?")
    expect(page.get_by_test_id("answer")).to_contain_text("80 US dollars per year")
    expect(page.get_by_test_id("meta")).to_contain_text(re.compile(r"Sources: .*pricing-plans#3"))


def test_unanswerable_question_shows_refusal(page: Page, live_server):
    ask(page, live_server, "Can I pay with cryptocurrency?")
    expect(page.get_by_test_id("answer")).to_have_text("I don't know based on the NimbusNotes documentation.")
    expect(page.get_by_test_id("meta")).to_contain_text("Sources: none")


def test_enter_key_submits(page: Page, live_server):
    page.goto(live_server)
    page.get_by_label("Question").fill("How long do password reset links last?")
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("answer")).to_contain_text("1 hour")
