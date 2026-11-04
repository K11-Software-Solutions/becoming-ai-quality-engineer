"""BM25 keyword retriever over paragraph-sized chunks of Markdown documents."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.text import expand_query, tokenize

# Documents whose file name starts with one of these prefixes are treated as
# untrusted (user-generated) content. The prompt labels them so the model can
# weigh them accordingly, and guardrails scrub instruction-like text from them.
UNTRUSTED_PREFIXES = ("community-",)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    text: str
    trusted: bool


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


def load_chunks(docs_dir: Path) -> list[Chunk]:
    """Split every Markdown file into paragraph chunks: ``<doc_id>#<n>``."""
    chunks: list[Chunk] = []
    for path in sorted(Path(docs_dir).glob("*.md")):
        doc_id = path.stem
        title = doc_id
        paragraphs: list[str] = []
        for block in path.read_text(encoding="utf-8").split("\n\n"):
            block = " ".join(block.split())
            if not block:
                continue
            if block.startswith("# "):
                title = block[2:].strip()
                continue
            paragraphs.append(block)
        trusted = not doc_id.startswith(UNTRUSTED_PREFIXES)
        for i, para in enumerate(paragraphs, start=1):
            chunks.append(Chunk(f"{doc_id}#{i}", doc_id, title, para, trusted))
    return chunks


class BM25Retriever:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        if not chunks:
            raise ValueError("BM25Retriever needs at least one chunk")
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        # Index the title with the body so 'refund' matches the refund doc.
        self._tfs = [Counter(tokenize(f"{c.title} {c.text}")) for c in chunks]
        self._lens = [sum(tf.values()) for tf in self._tfs]
        self._avg_len = sum(self._lens) / len(self._lens)
        df: Counter[str] = Counter()
        for tf in self._tfs:
            df.update(tf.keys())
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    @classmethod
    def from_dir(cls, docs_dir: Path) -> "BM25Retriever":
        return cls(load_chunks(docs_dir))

    def search(self, query: str, k: int = 3) -> list[RetrievedChunk]:
        terms = set(expand_query(tokenize(query)))
        scored: list[RetrievedChunk] = []
        for chunk, tf, length in zip(self.chunks, self._tfs, self._lens):
            score = 0.0
            for term in terms:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                norm = freq + self.k1 * (1 - self.b + self.b * length / self._avg_len)
                score += self._idf[term] * freq * (self.k1 + 1) / norm
            if score > 0:
                scored.append(RetrievedChunk(chunk, round(score, 4)))
        scored.sort(key=lambda r: (-r.score, r.chunk.chunk_id))
        return scored[:k]
