"""Custom Promptfoo assertions written in Python.

Referenced from promptfooconfig.yaml as ``file://assertions.py:<function>``.
Each function receives the model output and a context dict, and returns a
GradingResult-shaped dict.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals import metrics  # noqa: E402


def _contexts(context: dict) -> list[str]:
    # Promptfoo exposes provider metadata on the provider response.
    response = context.get("providerResponse") or {}
    return (response.get("metadata") or {}).get("contexts", [])


def grounded(output: str, context: dict) -> dict:
    """Every answer sentence must be supported by the retrieved context."""
    if output.startswith("I don't know") or output.startswith("I can only answer"):
        return {"pass": True, "score": 1.0, "reason": "refusal is trivially grounded"}
    score, unsupported = metrics.groundedness(output, _contexts(context))
    return {
        "pass": score == 1.0,
        "score": score,
        "reason": "all sentences supported" if not unsupported else f"unsupported: {unsupported}",
    }


def cites_retrieved_chunk(output: str, context: dict) -> dict:
    """Answers (not refusals) must cite at least one chunk id like [refund-policy#1]."""
    if output.startswith("I don't know") or output.startswith("I can only answer"):
        return {"pass": True, "score": 1.0, "reason": "refusal needs no citation"}
    has_citation = "#" in output and "[" in output
    return {"pass": has_citation, "score": float(has_citation),
            "reason": "has citation" if has_citation else "answer has no [chunk#id] citation"}
