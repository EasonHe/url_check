#!/usr/bin/env python3
"""Focused regression checks for alert state machine.

This script validates two historical false-recovery issues:
1) status_code recovery with actual=-1
2) json_path recovery with mismatch/null payload
"""

import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conf import config
from view.checke_control import cherker


def _log_file() -> Path:
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    return Path("logs") / f"alert_{today}.log"


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def _new_entries(path: Path, start: int):
    out = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()[start:]
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def _cleanup_state(task_name: str):
    p = Path("data") / f"{task_name}.pkl"
    if p.exists():
        p.unlink()


def _make_payload(
    task_name: str,
    *,
    code=200,
    timeout=0,
    content="",
    expect_json=False,
    json_path=None,
    json_path_value=None,
):
    return {
        "url_name": task_name,
        "url": "https://example.local/health",
        "stat_code": code,
        "timeout": timeout,
        "resp_time": 10,
        "contents": content,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "threshold": {"stat_code": 200, "math_str": "ok"},
        "expect_json": expect_json,
        "json_path": json_path,
        "json_path_value": json_path_value,
    }


def main():
    config.enable_dingding = False
    config.enable_mail = False
    config.enable_alerts = True

    log_path = _log_file()
    before = _line_count(log_path)

    # Case 1: status false recovery guard
    t1 = "qa-reg-status-guard"
    _cleanup_state(t1)
    c1 = cherker(method="get")
    c1.make_data(_make_payload(t1, code=503, timeout=0, content="bad"))
    c1.make_data(_make_payload(t1, code=-1, timeout=1, content=""))

    # Case 2: json false recovery guard
    t2 = "qa-reg-json-guard"
    _cleanup_state(t2)
    c2 = cherker(method="get")
    c2.make_data(
        _make_payload(
            t2,
            code=200,
            timeout=0,
            content='{"slideshow":{"author":"Yours Truly"}}',
            expect_json=True,
            json_path="$.slideshow.author",
            json_path_value="WRONG",
        )
    )
    c2.make_data(
        _make_payload(
            t2,
            code=-1,
            timeout=1,
            content="",
            expect_json=True,
            json_path="$.slideshow.author",
            json_path_value="WRONG",
        )
    )

    rows = _new_entries(log_path, before)

    bad_status = [
        x
        for x in rows
        if x.get("type") == "恢复"
        and "状态码异常" in x.get("message", "")
        and "实际: -1" in x.get("message", "")
    ]

    bad_json = [
        x
        for x in rows
        if x.get("type") == "恢复"
        and "JSON验证失败" in x.get("message", "")
        and (
            "状态: 不匹配" in x.get("message", "")
            or "实际: null" in x.get("message", "")
        )
    ]

    print("new_entries=", len(rows))
    print("bad_status_recovery_neg1=", len(bad_status))
    print("bad_json_recovery_mismatch=", len(bad_json))

    if bad_status or bad_json:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
