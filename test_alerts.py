#!/usr/bin/env python
"""测试所有告警类型 - 使用 httpbin.org 系列服务"""

import sys

sys.path.insert(0, "/home/appuser")

from view.make_check_instan import load_config
from conf import config
import datetime

# httpbin.org 响应示例
# GET https://httpbin.org/json: {"slideshow": {"author": "Yours Truly", ...}}
# GET https://httpbin.org/get: {"args": {}, "headers": {}, ...}


def test_status_code_404():
    """测试状态码告警 - 返回404"""
    print("\n" + "=" * 60)
    print("测试1: 状态码404")
    print("URL: https://httpbin.org/status/404")
    print("期望: 200, 实际: 404")
    print("=" * 60)

    from view.make_check_instan import get_method

    task = get_method(
        task_name="test-status-404",
        url="https://httpbin.org/status/404",
        timeout=10,
        threshold={"stat_code": 200},
    )
    task.get_instan()


def test_status_code_500():
    """测试状态码告警 - 返回500"""
    print("\n" + "=" * 60)
    print("测试2: 状态码500")
    print("URL: https://httpbin.org/status/500")
    print("期望: 200, 实际: 500")
    print("=" * 60)

    from view.make_check_instan import get_method

    task = get_method(
        task_name="test-status-500",
        url="https://httpbin.org/status/500",
        timeout=10,
        threshold={"stat_code": 200},
    )
    task.get_instan()


def test_timeout():
    """测试超时告警"""
    print("\n" + "=" * 60)
    print("测试3: 超时告警")
    print("URL: https://httpbin.org/delay/10")
    print("超时设置: 3秒")
    print("=" * 60)

    from view.make_check_instan import get_method

    task = get_method(
        task_name="test-timeout",
        url="https://httpbin.org/delay/10",
        timeout=3,
        threshold={"stat_code": 200},
    )
    task.get_instan()


def test_keyword():
    """测试关键字匹配告警"""
    print("\n" + "=" * 60)
    print("测试4: 关键字匹配")
    print("URL: https://httpbin.org/json")
    print("期望包含: NON_EXISTENT_KEYWORD_XYZ")
    print("响应包含: Slideshow, Yours Truly")
    print("=" * 60)

    from view.make_check_instan import get_method

    task = get_method(
        task_name="test-keyword",
        url="https://httpbin.org/json",
        timeout=10,
        threshold={"stat_code": 200, "math_str": "NON_EXISTENT_KEYWORD_XYZ"},
    )
    task.get_instan()


def test_json_path():
    """测试JSON路径匹配告警"""
    print("\n" + "=" * 60)
    print("测试5: JSON路径匹配")
    print("URL: https://httpbin.org/json")
    print("JSON路径: $.slideshow.author")
    print("期望值: NonExistentAuthor")
    print("实际值: Yours Truly")
    print("=" * 60)

    from view.make_check_instan import get_method

    task = get_method(
        task_name="test-json-path",
        url="https://httpbin.org/json",
        timeout=10,
        threshold={"stat_code": 200},
        expect_json=True,
        json_path="$.slideshow.author",
        json_path_value="NonExistentAuthor",
    )
    task.get_instan()


def test_delay():
    """测试响应时间告警"""
    print("\n" + "=" * 60)
    print("测试6: 响应时间告警")
    print("URL: https://httpbin.org/delay/3")
    print("阈值: 300ms")
    print("期望: >300ms")
    print("=" * 60)

    from view.make_check_instan import get_method

    task = get_method(
        task_name="test-delay",
        url="https://httpbin.org/delay/3",
        timeout=10,
        threshold={"stat_code": 200, "delay": 300},  # 降低阈值到 300ms
    )
    task.get_instan()
    task.get_instan()


def test_normal():
    """测试正常请求 - 验证恢复通知"""
    print("\n" + "=" * 60)
    print("测试7: 正常请求 (验证恢复)")
    print("URL: https://httpbin.org/json")
    print("期望: 200, 包含 'slideshow'")
    print("=" * 60)

    from view.make_check_instan import get_method

    task = get_method(
        task_name="test-normal",
        url="https://httpbin.org/json",
        timeout=10,
        threshold={"stat_code": 200, "math_str": "slideshow"},
    )
    task.get_instan()


if __name__ == "__main__":
    print("=" * 60)
    print("URL健康检查告警测试")
    print("测试URL来源: httpbin.org 系列")
    print("=" * 60)

    tests = [
        ("状态码404", test_status_code_404),
        ("状态码500", test_status_code_500),
        ("超时告警", test_timeout),
        ("关键字匹配", test_keyword),
        ("JSON路径匹配", test_json_path),
        ("响应时间告警", test_delay),
        ("正常请求(恢复)", test_normal),
    ]

    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name} 测试完成")
        except Exception as e:
            print(f"✗ {name} 测试失败: {e}")
        import time

        time.sleep(3)

    print("\n" + "=" * 60)
    print("所有告警测试完成!")
    print("请检查钉钉消息和日志确认告警发送情况")
    print("=" * 60)
