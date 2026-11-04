"""Runtime configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DOCS_DIR = Path(__file__).parent / "data" / "docs"


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Minimal .env loader so the project needs no extra dependency.

    Variables already set in the environment always win over the file.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "fake"  # fake | openai | anthropic
    fake_llm_behavior: str = "faithful"  # faithful | hallucinate | ignore_context
    top_k: int = 3
    docs_dir: Path = DEFAULT_DOCS_DIR
    max_question_chars: int = 500
    trace_file: str | None = None
    openai_api_key: str | None = field(default=None, repr=False)
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = field(default=None, repr=False)
    anthropic_model: str = "claude-haiku-5-5"
    request_timeout_s: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        env = os.environ.get
        return cls(
            llm_provider=env("LLM_PROVIDER", "fake").lower(),
            fake_llm_behavior=env("FAKE_LLM_BEHAVIOR", "faithful").lower(),
            top_k=int(env("RETRIEVER_TOP_K", "3")),
            docs_dir=Path(env("DOCS_DIR", str(DEFAULT_DOCS_DIR))),
            max_question_chars=int(env("MAX_QUESTION_CHARS", "500")),
            trace_file=env("TRACE_FILE") or None,
            openai_api_key=env("OPENAI_API_KEY") or None,
            openai_model=env("OPENAI_MODEL", "gpt-4o-mini"),
            anthropic_api_key=env("ANTHROPIC_API_KEY") or None,
            anthropic_model=env("ANTHROPIC_MODEL", "claude-haiku-5-5"),
            request_timeout_s=float(env("LLM_TIMEOUT_SECONDS", "30")),
        )
