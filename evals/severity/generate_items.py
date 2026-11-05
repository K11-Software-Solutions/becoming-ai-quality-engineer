"""Generate grader-calibration items whose correct label is known by construction.

Each item takes a true sentence from the NimbusNotes help articles and applies one
controlled transformation. The transformation decides the label, so hundreds of
items need no human annotation. Humans are still needed to rate them: the items
measure the *graders*, not the other way round.

    python -m evals.severity.generate_items            # writes evals/severity/items.jsonl

Strata (failure-mode types, not difficulty levels):
    grounded:      verbatim, omission, paraphrase
    not grounded:  numeric, negation, added_claim, entity_swap
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from app.config import DEFAULT_DOCS_DIR
from app.text import split_sentences

HERE = Path(__file__).parent
ITEMS = HERE / "items.jsonl"
GROUNDED = {"verbatim", "omission", "paraphrase"}
STRATA = ["verbatim", "omission", "paraphrase", "numeric", "negation", "added_claim", "entity_swap"]

PREFIXES = ["", "Yes. ", "According to the help center, ", "Good question. "]
PARAPHRASES = {
    "costs": "is priced at", "receive": "get", "includes": "comes with", "available": "offered",
    "returns": "responds with", "requires": "needs", "expire": "stop working", "automatically": "on their own",
    "permanent": "irreversible", "within": "inside", "delivered": "provided", "created": "made",
    "select": "choose", "store": "keep", "offers": "provides", "allows": "lets you make",
}
CLAIMS = ["and this includes free 24/7 phone support", "and the limit is doubled on weekends",
          "and enterprise customers get it for free", "and it also works on smart TVs"]
SWAPS = [("Pro", "Team"), ("Team", "Pro"), ("Free", "Pro"), ("month", "year"), ("year", "month"),
         ("minute", "hour"), ("read-only", "read-write"), ("desktop", "web"), ("Settings", "Help")]
AUX = re.compile(r"\b(is|are|can|will|does|must)\b ")


def corpus() -> list[tuple[str, str, str]]:
    """(doc_id, paragraph, sentence) for the official help articles."""
    out = []
    for path in sorted(Path(DEFAULT_DOCS_DIR).glob("*.md")):
        if path.stem.startswith("community-"):
            continue  # untrusted content is not a source of truth
        for block in path.read_text(encoding="utf-8").split("\n\n"):
            block = " ".join(block.split())
            if not block or block.startswith("#"):
                continue
            for sentence in split_sentences(block):
                if len(sentence.split()) >= 5:
                    out.append((path.stem, block, sentence))
    return out


_LOWERABLE = {"The", "It", "You", "Your", "Each", "If", "When", "After", "To", "This", "Any", "Edits", "Changes"}


def lower_first(s: str) -> str:
    """Lower-case the first word only if it is a common word, never a product or plan name."""
    first, _, rest = s.partition(" ")
    return (first.lower() + " " + rest) if first in _LOWERABLE else s


def with_prefix(prefix: str, sentence: str) -> str:
    return sentence if not prefix else prefix + (lower_first(sentence) if prefix.endswith(", ") else sentence)


def transform(stratum: str, sentence: str, rng: random.Random) -> str | None:
    """Return the transformed answer, or None if this stratum does not apply to the sentence."""
    if stratum == "verbatim":
        return sentence
    if stratum == "omission":
        head = re.split(r",|;", sentence)[0].strip().rstrip(".")
        if head.split()[0] in {"To", "If", "When", "After", "Before"} or ":" in head:
            return None  # a dependent clause on its own is not a claim
        return head + "." if len(head.split()) >= 4 and head + "." != sentence else None
    if stratum == "paraphrase":
        hits = [w for w in PARAPHRASES if re.search(rf"\b{w}\b", sentence)]
        if not hits:
            return None
        out = sentence
        for w in rng.sample(hits, k=min(len(hits), rng.randint(1, 2))):
            out = re.sub(rf"\b{w}\b", PARAPHRASES[w], out, count=1)
        return out
    if stratum == "numeric":
        numbers = list(re.finditer(r"\b\d+\b", sentence))
        if not numbers:
            return None
        m = rng.choice(numbers)
        n = int(m.group())
        new = rng.choice([n * 2, n + 1, n * 10, max(1, n - 1)])
        new = new if new != n else n + 2
        return sentence[:m.start()] + str(new) + sentence[m.end():]
    if stratum == "negation":
        if re.search(r"\bnot\b ", sentence):
            return re.sub(r"\bnot\b ", "", sentence, count=1)
        m = AUX.search(sentence)
        return sentence[:m.end()] + "not " + sentence[m.end():] if m else None
    if stratum == "added_claim":
        return sentence.rstrip(".") + ", " + rng.choice(CLAIMS) + "."
    if stratum == "entity_swap":
        options = [(a, b) for a, b in SWAPS if re.search(rf"\b{re.escape(a)}\b", sentence)]
        if not options:
            return None
        a, b = rng.choice(options)
        return re.sub(rf"\b{re.escape(a)}\b", b, sentence, count=1)
    raise ValueError(stratum)


def generate(per_stratum: int = 100, seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    sentences = corpus()
    items, seen = [], set()
    for stratum in STRATA:
        made, attempts = 0, 0
        while made < per_stratum and attempts < per_stratum * 60:
            attempts += 1
            doc, context, sentence = rng.choice(sentences)
            answer = transform(stratum, sentence, rng)
            if answer is None or (stratum not in GROUNDED and answer == sentence):
                continue
            prefix = rng.choice(PREFIXES)
            answer = with_prefix(prefix, answer)
            key = (stratum, answer)
            if key in seen:
                continue
            seen.add(key)
            made += 1
            items.append({"id": f"s-{stratum[:4]}-{made:03d}", "stratum": stratum, "doc": doc, "context": context,
                          "answer": answer, "label": "grounded" if stratum in GROUNDED else "not_grounded",
                          "source_sentence": sentence, "prefix": prefix.strip()})
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-stratum", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=ITEMS)
    args = parser.parse_args(argv)
    items = generate(args.per_stratum, args.seed)
    args.out.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    counts = {s: sum(i["stratum"] == s for i in items) for s in STRATA}
    print(f"wrote {len(items)} items to {args.out}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
