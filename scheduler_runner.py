#!/usr/bin/env python
"""Separate scheduler runner for URL check service."""

import sys

sys.path.insert(0, "/home/appuser")

from view.make_check_instan import load_config


def main():
    lt = load_config()
    lt.loading_task()
    print("Scheduler started in separate process")
    import time

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
