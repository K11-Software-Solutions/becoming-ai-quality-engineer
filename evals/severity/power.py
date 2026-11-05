"""A priori power analysis for grader-severity estimates.

For dichotomous ratings under a Rasch model, the standard error of a rater's
severity is approximately

    SE = 1 / sqrt( sum over ratings of p(1 - p) )

where p is the probability of a "pass" for that rating. Items far from 50/50
carry little information, so the average p(1 - p) is usually well below the
0.25 maximum. Plan with a realistic value, not the best case.

    python -m evals.severity.power --target-se 0.15
    python -m evals.severity.power --detect 0.3 --info 0.15
"""
from __future__ import annotations

import argparse
import math

Z_ALPHA = 1.96   # two-sided 5%
Z_POWER = 0.84   # 80% power


def se_for(n: int, info: float = 0.25) -> float:
    """Approximate SE of a severity estimate from n ratings with mean information `info` per rating."""
    return 1 / math.sqrt(n * info) if n > 0 else math.inf


def ratings_for_se(target_se: float, info: float = 0.25) -> int:
    """Ratings needed for a target SE."""
    return math.ceil(1 / (target_se ** 2 * info))


def ratings_to_detect(difference: float, info: float = 0.25) -> int:
    """Ratings per rater to detect a severity difference between two raters (5% two-sided, 80% power).

    Two independent estimates with equal SE: SE_diff = sqrt(2) * SE, and we need
    difference >= (z_alpha + z_power) * SE_diff.
    """
    se_each = difference / ((Z_ALPHA + Z_POWER) * math.sqrt(2))
    return ratings_for_se(se_each, info)


def table(info: float = 0.25) -> list[dict]:
    return [{"ratings": n, "se": round(se_for(n, info), 3)} for n in (24, 50, 100, 180, 400, 700, 1000)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target-se", type=float)
    parser.add_argument("--detect", type=float, help="smallest severity difference (logits) worth detecting")
    parser.add_argument("--info", type=float, default=0.25, help="mean p(1-p) per rating (0.25 = best case)")
    args = parser.parse_args(argv)
    print(f"Mean information per rating assumed: {args.info} (0.25 is the best case)\n")
    print("ratings   approx. SE (logits)")
    for row in table(args.info):
        print(f"{row['ratings']:>7}   {row['se']:.3f}")
    if args.target_se:
        print(f"\nRatings for SE <= {args.target_se}: {ratings_for_se(args.target_se, args.info)}")
    if args.detect:
        print(f"Ratings per rater to detect a {args.detect}-logit difference (5%, 80% power): "
              f"{ratings_to_detect(args.detect, args.info)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
