"""CI check: labels (or the rubric) and the grader must change in separate commits.

If one commit changes both the human labels and the code that grades against
them, a better score cannot be attributed: did the grader improve, or did the
labels move towards the grader? Keeping them apart makes every change reviewable
on its own, and stops a grader from being tuned to its own test set by accident.

    python -m evals.change_hygiene --range BASE..HEAD     # check every commit in a range
    python -m evals.change_hygiene --files a.py b.jsonl   # check one hypothetical change

A deliberate exception is allowed when the commit message contains
"[labels+grader]"; it is reported as a warning, so reviewers still see it.
Uses only the standard library and git, so CI can run it without installing anything.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

LABEL_FILES = {
    "evals/judge/human_labels.jsonl",
    "evals/judge/reviewer_labels.jsonl",
    "evals/judge/RUBRIC.md",
}
GRADER_FILES = {
    "evals/metrics.py",                 # groundedness and fact checks used by the judge and the eval gate
    "evals/judge/judge_agreement.py",   # the judge functions themselves
}
OVERRIDE = "[labels+grader]"


def classify(files: list[str]) -> dict[str, list[str]]:
    paths = [f.replace("\\", "/") for f in files]
    return {"labels": sorted(p for p in paths if p in LABEL_FILES),
            "grader": sorted(p for p in paths if p in GRADER_FILES)}


def violates(files: list[str]) -> bool:
    c = classify(files)
    return bool(c["labels"]) and bool(c["grader"])


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def commits_in(rev_range: str) -> list[dict]:
    shas = [s for s in _git("rev-list", "--no-merges", rev_range).split() if s]
    out = []
    for sha in reversed(shas):
        files = [f for f in _git("diff-tree", "--no-commit-id", "--name-only", "-r", sha).splitlines() if f]
        message = _git("log", "-1", "--format=%B", sha)
        out.append({"sha": sha[:7], "subject": message.splitlines()[0] if message else "", "files": files,
                    "override": OVERRIDE in message})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--range", help="git revision range, e.g. origin/main..HEAD")
    group.add_argument("--files", nargs="+", help="check a single change made of these files")
    args = parser.parse_args(argv)

    commits = [{"sha": "(files)", "subject": "", "files": args.files, "override": False}] if args.files \
        else commits_in(args.range)
    failures = 0
    for c in commits:
        if not violates(c["files"]):
            continue
        parts = classify(c["files"])
        detail = f"labels {parts['labels']} and grader {parts['grader']}"
        if c["override"]:
            print(f"::warning::{c['sha']} changes {detail} together (allowed by {OVERRIDE}): {c['subject']}")
        else:
            failures += 1
            print(f"::error::{c['sha']} changes {detail} in one commit: {c['subject']}")
    if failures:
        print(f"\n{failures} commit(s) change labels and the grader together. Split them, or add {OVERRIDE} "
              "to the commit message if it is deliberate.", file=sys.stderr)
        return 1
    print(f"OK: {len(commits)} commit(s) checked; labels and grader never changed together.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
