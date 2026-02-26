#!/usr/bin/env python3
"""Simple guard to prevent documentation drift."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]


def markdown_files():
    for p in ROOT.rglob("*.md"):
        if "/.git/" in str(p):
            continue
        yield p


RULES = [
    (
        "legacy_metrics_port",
        re.compile(r"\bmetrics_port\s*=\s*9090\b"),
        "Do not document legacy metrics_port=9090; service metrics are on :4000/metrics.",
    ),
    (
        "legacy_task_ini",
        re.compile(r"conf/task\.ini|task\.ini"),
        "Do not reference legacy task.ini; use conf/tasks.yaml.",
    ),
    (
        "wrong_port_forward",
        re.compile(r"kubectl\s+port-forward[^\n]*\b9090:9090\b"),
        "Do not expose url-check on 9090 in docs; use 4000 for service access.",
    ),
    (
        "wrong_docker_port",
        re.compile(r"docker\s+run[^\n]*\b-p\s+9090:9090\b"),
        "Do not expose url-check on 9090 in docker run docs; use 4000.",
    ),
]


def main():
    errors = []
    for md in markdown_files():
        text = md.read_text(encoding="utf-8")
        for name, pattern, help_msg in RULES:
            for m in pattern.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                errors.append(f"{md.relative_to(ROOT)}:{line} [{name}] {help_msg}")

    if errors:
        print("docs_guard found issues:")
        for e in errors:
            print("-", e)
        return 1

    print("docs_guard passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
