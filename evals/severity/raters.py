"""Raters for the severity study, and the linked rating design.

SIMULATED reviewers stand in for humans until real ratings exist. Each has a
known severity, so the model can be checked by whether it recovers them. They
are clearly not people and nothing here should be presented as human data.

The automated judge is the real one from evals/judge (imported, not modified).
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass

from evals.judge.judge_agreement import heuristic_judge

# How clearly each stratum reads as grounded (+) or not (−) to a careful human, in logits.
STRATUM_EASE = {"verbatim": 3.0, "omission": 2.0, "paraphrase": 1.5,
                "added_claim": -3.0, "negation": -2.0, "numeric": -1.5, "entity_swap": -1.5}


def _unit_noise(key: str) -> float:
    """Deterministic per-item variation, approximately N(0, 1)."""
    h = int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)
    return random.Random(h).gauss(0, 1)


def item_ease(item: dict) -> float:
    return STRATUM_EASE[item["stratum"]] + 0.5 * _unit_noise(item["id"])


@dataclass(frozen=True)
class SimulatedReviewer:
    name: str
    severity: float  # true severity in logits; positive = harsher (more "not grounded")

    def rate(self, item: dict, seed: int = 0) -> int:
        """1 = grounded, 0 = not grounded."""
        p = 1 / (1 + math.exp(-(item_ease(item) - self.severity)))
        rng = random.Random(f"{self.name}:{item['id']}:{seed}")
        return int(rng.random() < p)


REVIEWERS = [SimulatedReviewer("sim-reviewer-A", -0.4), SimulatedReviewer("sim-reviewer-B", 0.4),
             SimulatedReviewer("sim-reviewer-C", 0.0)]


def judge_rate(item: dict) -> int:
    return int(heuristic_judge(item["context"], item["answer"]) == "grounded")


def linked_design(items: list[dict], anchors_per_stratum: int = 7, own_per_reviewer: int = 150,
                  seed: int = 0) -> list[tuple[str, str, int]]:
    """Ratings as (item_id, rater, x).

    The judge rates every item. Each simulated reviewer rates a shared set of
    anchor items (stratified, so every stratum is linked) plus its own sample.
    Anchors put all raters on one scale without everyone rating everything.
    """
    rng = random.Random(seed)
    by_stratum: dict[str, list[dict]] = {}
    for it in items:
        by_stratum.setdefault(it["stratum"], []).append(it)
    anchors = [it for s in sorted(by_stratum) for it in rng.sample(by_stratum[s], min(anchors_per_stratum, len(by_stratum[s])))]
    anchor_ids = {a["id"] for a in anchors}
    rest = [it for it in items if it["id"] not in anchor_ids]
    ratings = [(it["id"], "judge", judge_rate(it)) for it in items]
    for reviewer in REVIEWERS:
        own = rng.sample(rest, min(own_per_reviewer, len(rest)))
        for it in anchors + own:
            ratings.append((it["id"], reviewer.name, reviewer.rate(it, seed)))
    return ratings
