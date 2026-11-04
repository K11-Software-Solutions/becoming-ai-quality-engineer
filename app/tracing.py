"""A minimal local tracer.

Each request becomes one trace made of named spans (guard, retrieve,
generate) with timings and attributes. When ``TRACE_FILE`` is set, traces are
appended to that file as JSON lines so you can inspect a failure afterwards.

Tools such as Langfuse or LangSmith do the same thing with a UI, sharing and
experiment comparison on top. Article 05 shows where they would plug in.
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class Trace:
    def __init__(self, name: str, sink: str | None = None):
        self.trace_id = uuid.uuid4().hex[:16]
        self.name = name
        self.sink = sink
        self.spans: list[dict[str, Any]] = []
        self.attrs: dict[str, Any] = {}

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[dict[str, Any]]:
        record: dict[str, Any] = {"name": name, "attrs": dict(attrs)}
        start = time.perf_counter()
        try:
            yield record["attrs"]
        except Exception as exc:
            record["error"] = repr(exc)
            raise
        finally:
            record["duration_ms"] = round((time.perf_counter() - start) * 1000, 3)
            self.spans.append(record)

    def to_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "name": self.name, "attrs": self.attrs, "spans": self.spans}

    def flush(self) -> None:
        if not self.sink:
            return
        path = Path(self.sink)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(self.to_dict()) + "\n")
