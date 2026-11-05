"""Fingerprint the datasets an eval result depends on.

A label change can move a score as much as a model change. Every report
therefore records a short content hash of each dataset, label and threshold
file it used, so two scores are only compared when they were computed against
the same data.

Hashes are taken over the text with line endings normalised to "\\n", so the
same file gives the same fingerprint on Windows (CRLF checkouts) and Linux.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def fingerprint(path: Path, length: int = 12) -> str:
    text = Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def versions(*paths: Path) -> dict[str, str]:
    """{file name: fingerprint} for each path."""
    return {Path(p).name: fingerprint(p) for p in paths}


def describe(v: dict[str, str]) -> str:
    return ", ".join(f"`{name}@{digest}`" for name, digest in v.items())
