"""A priori power analysis for grader-severity estimates.

For dichotomous ratings under a Rasch model, the standard error of a rater's
severity is approximately

    SE = 1 / sqrt( sum over ratings of p(1 - p) )

where p is the probability of a "pass" for that rating. Items far from 50/50
carry little information, so the average p(1 - p) is usually well below the
0.25 maximum. Plan with a realistic value, not the best case.

    python -m evals.severity.power --target-se 0.15
    python -m evals.severity.power --detect 0.3 --info 0.15
    python -m evals.severity.power --detect 0.3 0.5 0.75 --info 0.10 --alpha 0.10 --power 0.75

Power depends on four things: alpha (how often you accept a false alarm), power
(how often you want to detect a lean that is really there), the effect size (the
smallest lean that would change a decision) and the sample size. The effect size
is a business decision, and usually the hardest one: agree it first, then size
the study. A process that tolerates more uncertainty (a larger effect size, a
higher alpha, lower power) needs far fewer ratings.
"""
from __future__ import annotations

import argparse
import math
from statistics import NormalDist

ALPHA = 0.05     # default: two-sided 5% false-alarm rate
POWER = 0.80     # default: 80% chance of detecting a real lean


def z_values(alpha: float = ALPHA, power: float = POWER) -> tuple[float, float]:
    """Normal quantiles for a two-sided test, rounded to two decimals as in standard tables."""
    if not (0 < alpha < 1 and 0 < power < 1):
        raise ValueError("alpha and power must be between 0 and 1")
    nd = NormalDist()
    return round(nd.inv_cdf(1 - alpha / 2), 2), round(nd.inv_cdf(power), 2)


Z_ALPHA, Z_POWER = z_values()   # 1.96, 0.84


def se_for(n: int, info: float = 0.25) -> float:
    """Approximate SE of a severity estimate from n ratings with mean information `info` per rating."""
    return 1 / math.sqrt(n * info) if n > 0 else math.inf


def ratings_for_se(target_se: float, info: float = 0.25) -> int:
    """Ratings needed for a target SE."""
    return math.ceil(1 / (target_se ** 2 * info))


def ratings_to_detect(difference: float, info: float = 0.25, alpha: float = ALPHA, power: float = POWER) -> int:
    """Ratings per rater to detect a severity difference between two raters (two-sided test).

    Two independent estimates with equal SE: SE_diff = sqrt(2) * SE, and we need
    difference >= (z_alpha + z_power) * SE_diff.
    """
    z_alpha, z_power = z_values(alpha, power)
    se_each = difference / ((z_alpha + z_power) * math.sqrt(2))
    return ratings_for_se(se_each, info)


def table(info: float = 0.25) -> list[dict]:
    return [{"ratings": n, "se": round(se_for(n, info), 3)} for n in (24, 50, 100, 180, 400, 700, 1000)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target-se", type=float)
    parser.add_argument("--detect", type=float, nargs="+",
                        help="smallest severity difference(s) in logits that would change a decision")
    parser.add_argument("--alpha", type=float, default=ALPHA, help="two-sided false-alarm rate (default 0.05)")
    parser.add_argument("--power", type=float, default=POWER, help="chance of detecting a real lean (default 0.80)")
    parser.add_argument("--info", type=float, default=0.25, help="mean p(1-p) per rating (0.25 = best case)")
    args = parser.parse_args(argv)
    print(f"Mean information per rating assumed: {args.info} (0.25 is the best case)\n")
    print("ratings   approx. SE (logits)")
    for row in table(args.info):
        print(f"{row['ratings']:>7}   {row['se']:.3f}")
    if args.target_se:
        print(f"\nRatings for SE <= {args.target_se}: {ratings_for_se(args.target_se, args.info)}")
    if args.detect:
        print(f"\nRatings per rater to detect a difference (alpha {args.alpha:g}, power {args.power:.0%}):")
        for d in args.detect:
            print(f"  {d:g} logits: {ratings_to_detect(d, args.info, args.alpha, args.power)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
