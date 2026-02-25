# =============================================================================
# URL 检查任务模块
# =============================================================================
# 功能：
#   - 解析配置文件 (conf/tasks.yaml)
#   - 创建 GET/POST 检查任务
#   - 使用 APScheduler 实现定时调度
#   - 支持运行时动态添加/删除任务
#
# 优化特性：
#   - 连接池复用：全局 requests.Session 减少 TCP 握手开销
#   - 响应大小限制：避免大响应耗尽资源
#   - 重试机制：网络异常时自动重试
#
# 任务生命周期：
#   1. load_config 读取配置文件
#   2. loading_task() 遍历所有任务，创建检查任务
#   3. BackgroundScheduler 按 interval 执行检查
#   4. 检查结果传递给 cherker 处理
# =============================================================================

from apscheduler.schedulers.background import BackgroundScheduler
import yaml
import requests
from requests import exceptions
from requests.exceptions import HTTPError
from conf import config
import datetime
from view.checke_control import cherker
import time
import ssl
import socket
from urllib.parse import urlparse

# 全局 Session 用于连接池复用
http_session = requests.Session()


def get_ssl_cert_expiry_days(url, verify=True):
    """
    直接获取SSL证书剩余天数

    Args:
        url: 完整URL（如 https://example.com）
        verify: 是否验证证书（如果为False则跳过检查）

    Returns:
        int: 剩余天数，获取失败或verify=False时返回 None
    """
    # 如果跳过证书验证，则不检查过期时间
    if not verify:
        return None

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        port = parsed.port or 443

        context = ssl.create_default_context()

        with socket.create_connection((hostname, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                if cert and "notAfter" in cert:
                    not_after_str = cert["notAfter"]
                    not_after = datetime.datetime.strptime(
                        not_after_str, "%b %d %H:%M:%S %Y %Z"
                    )
                    days = (not_after - datetime.datetime.now()).days
                    return days
    except Exception:
        pass
    return None


class get_method:
    """
    GET 请求检查任务
    """

    def __init__(
        self,
        task_name,
        url,
        headers=None,
        cookies=None,
        payload=None,
        timeout=10,
        threshold=None,
        max_response_size=None,
        retry_count=0,
        retry_delay=1,
        proxy=None,
        ssl_verify=True,
        ssl_warning_days=30,
        expect_json=False,
        json_path=None,
        json_path_value=None,
    ):
        """
        初始化 GET 检查任务
        """
        self.task_name = task_name
        self.url = url
        self.header = headers
        self.payload = payload
        self.timeout = timeout
        self.cookies = cookies
        self.threshold = threshold
        self.max_response_size = max_response_size
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.proxy = proxy
        self.ssl_verify = ssl_verify
        self.ssl_warning_days = ssl_warning_days
        self.expect_json = expect_json
        self.json_path = json_path
        self.json_path_value = json_path_value

    def get_instan(self):
        """
        执行 GET 请求检查
        """
        last_error = None
        for attempt in range(self.retry_count + 1):
            try:
                data = {}
                now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 处理 proxy 配置，支持 __HOST__ 关键字
                proxy = self.proxy
                if proxy:
                    from conf import config

                    host_ip = getattr(config, "HOST_IP", "host.docker.internal")
                    proxy = proxy.replace("__HOST__", host_ip)

                proxies = {"http": proxy, "https": proxy} if proxy else None

                # SSL 验证配置
                verify = self.ssl_verify

                r = http_session.get(
                    self.url,
                    headers=self.header,
                    cookies=self.cookies,
                    data=self.payload,
                    timeout=self.timeout,
                    stream=True,
                    proxies=proxies,
                    verify=verify,
                )
                r.raise_for_status()
                r.encoding = "utf-8"

                # SSL 证书有效期检查（使用独立函数）
                ssl_expiry_days = get_ssl_cert_expiry_days(self.url, verify=verify)
                if ssl_expiry_days is not None:
                    print(f"SSL 证书剩余 {ssl_expiry_days} 天")

                    # 更新 Prometheus 指标
                    from view.checke_control import url_check_ssl_expiry_days

                    url_check_ssl_expiry_days.labels(
                        task_name=self.task_name, method="get"
                    ).set(ssl_expiry_days)

                    # 证书即将过期告警
                    if ssl_expiry_days < self.ssl_warning_days:
                        print(
                            f"警告: {self.task_name} SSL 证书将在 {ssl_expiry_days} 天后过期"
                        )

                # 更新 SSL 验证状态指标
                from view.checke_control import url_check_ssl_verified

                url_check_ssl_verified.labels(
                    task_name=self.task_name, method="get", verified=str(verify).lower()
                ).inc()

                content = ""
                if self.max_response_size:
                    content_len = len(r.content)
                    if content_len > self.max_response_size:
                        print(
                            f"警告: {self.task_name} 响应大小 {content_len} 字节超过限制 {self.max_response_size}，跳过内容解析"
                        )
                        content = ""
                    else:
                        content = r.text
                else:
                    content = r.text

                retime = r.elapsed.total_seconds() * 1000
                statuscode = r.status_code
                data = {
                    "url_name": self.task_name,
                    "url": self.url,
                    "stat_code": statuscode,
                    "timeout": 0,
                    "resp_time": retime,
                    "contents": content,
                    "time": now_time,
                    "threshold": self.threshold,
                    "expect_json": self.expect_json,
                    "json_path": self.json_path,
                    "json_path_value": self.json_path_value,
                    "ssl_expiry_days": ssl_expiry_days,
                    "ssl_warning_days": self.ssl_warning_days,
                }
                print(data)
                ck = cherker(method="get")
                ck.make_data(data)
                return

            except HTTPError as e:
                last_error = e
                # 修复：使用 is not None 而不是依赖布尔值判断
                # 因为 Response 对象的 __bool__ 方法在 HTTP 错误时返回 False
                status_code = e.response.status_code if e.response is not None else 0
                print(f"警告: {self.task_name} HTTP错误: {status_code} {e}")
                data = {
                    "url_name": self.task_name,
                    "url": self.url,
                    "stat_code": status_code,
                    "timeout": 0,
                    "resp_time": 0,
                    "contents": str(e),
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "threshold": self.threshold,
                    "expect_json": self.expect_json,
                    "json_path": self.json_path,
                    "json_path_value": self.json_path_value,
                    "ssl_expiry_days": None,
                    "ssl_warning_days": self.ssl_warning_days,
                }
                print(data)
                ck = cherker(method="get")
                ck.make_data(data)
                return

            except Exception as e:
                last_error = e
                if attempt < self.retry_count:
                    print(
                        f"第 {attempt + 1} 次请求失败，{self.retry_delay} 秒后重试: {e}"
                    )
                    time.sleep(self.retry_delay)

        print(f"警告: {self.task_name} 重试 {self.retry_count} 次均失败: {last_error}")
        data = {
            "url_name": self.task_name,
            "url": self.url,
            "threshold": self.threshold,
            "timeout": 1,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expect_json": self.expect_json,
            "json_path": self.json_path,
            "json_path_value": self.json_path_value,
        }
        print(data)
        ck = cherker(method="get")
        ck.make_data(data)


class post_method:
    """
    POST 请求检查任务
    """

    def __init__(
        self,
        task_name,
        url,
        headers=None,
        cookies=None,
        payload=None,
        timeout=None,
        threshold=None,
        max_response_size=None,
        retry_count=0,
        retry_delay=1,
        proxy=None,
        ssl_verify=True,
        ssl_warning_days=30,
        expect_json=False,
        json_path=None,
        json_path_value=None,
    ):
        """
        初始化 POST 检查任务
        """
        self.task_name = task_name
        self.url = url
        self.header = headers
        self.payload = payload
        self.timeout = timeout
        self.cookies = cookies
        self.threshold = threshold
        self.max_response_size = max_response_size
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.proxy = proxy
        self.ssl_verify = ssl_verify
        self.ssl_warning_days = ssl_warning_days
        self.expect_json = expect_json
        self.json_path = json_path
        self.json_path_value = json_path_value

    def post_instan(self):
        """
        执行 POST 请求检查
        """
        last_error = None
        for attempt in range(self.retry_count + 1):
            try:
                data = {}

                # 处理 proxy 配置，支持 __HOST__ 关键字
                proxy = self.proxy
                if proxy:
                    from conf import config

                    host_ip = getattr(config, "HOST_IP", "host.docker.internal")
                    proxy = proxy.replace("__HOST__", host_ip)

                proxies = {"http": proxy, "https": proxy} if proxy else None
                r = http_session.post(
                    self.url,
                    headers=self.header,
                    cookies=self.cookies,
                    data=self.payload,
                    timeout=self.timeout,
                    stream=True,
                    proxies=proxies,
                    verify=self.ssl_verify,
                )
                r.raise_for_status()
                r.encoding = "utf-8"

                # SSL 证书有效期检查（使用独立函数）
                ssl_expiry_days = get_ssl_cert_expiry_days(
                    self.url, verify=self.ssl_verify
                )
                if ssl_expiry_days is not None:
                    print(f"SSL 证书剩余 {ssl_expiry_days} 天")

                    from view.checke_control import url_check_ssl_expiry_days

                    url_check_ssl_expiry_days.labels(
                        task_name=self.task_name, method="post"
                    ).set(ssl_expiry_days)

                    if ssl_expiry_days < self.ssl_warning_days:
                        print(
                            f"警告: {self.task_name} SSL 证书将在 {ssl_expiry_days} 天后过期"
                        )

                # 更新 SSL 验证状态指标
                from view.checke_control import url_check_ssl_verified

                url_check_ssl_verified.labels(
                    task_name=self.task_name,
                    method="post",
                    verified=str(self.ssl_verify).lower(),
                ).inc()

                content = ""
                if self.max_response_size:
                    content_len = len(r.content)
                    if content_len > self.max_response_size:
                        print(
                            f"警告: {self.task_name} 响应大小 {content_len} 字节超过限制 {self.max_response_size}，跳过内容解析"
                        )
                        content = ""
                    else:
                        content = r.text
                else:
                    content = r.text

                retime = r.elapsed.total_seconds() * 1000
                statuscode = r.status_code
                data = {
                    "url_name": self.task_name,
                    "url": self.url,
                    "stat_code": statuscode,
                    "timeout": 0,
                    "resp_time": retime,
                    "contents": content,
                    "threshold": self.threshold,
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "expect_json": self.expect_json,
                    "json_path": self.json_path,
                    "json_path_value": self.json_path_value,
                    "ssl_expiry_days": ssl_expiry_days,
                    "ssl_warning_days": self.ssl_warning_days,
                }
                print(data)
                ck = cherker(method="post")
                ck.make_data(data)
                return

            except HTTPError as e:
                last_error = e
                # 修复：使用 is not None 而不是依赖布尔值判断
                status_code = e.response.status_code if e.response is not None else 0
                print(f"警告: {self.task_name} HTTP错误: {status_code} {e}")
                data = {
                    "url_name": self.task_name,
                    "url": self.url,
                    "stat_code": status_code,
                    "timeout": 0,
                    "resp_time": 0,
                    "contents": str(e),
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "threshold": self.threshold,
                    "expect_json": self.expect_json,
                    "json_path": self.json_path,
                    "json_path_value": self.json_path_value,
                    "ssl_expiry_days": None,
                    "ssl_warning_days": self.ssl_warning_days,
                }
                print(data)
                ck = cherker(method="post")
                ck.make_data(data)
                return

            except Exception as e:
                last_error = e
                if attempt < self.retry_count:
                    print(
                        f"第 {attempt + 1} 次请求失败，{self.retry_delay} 秒后重试: {e}"
                    )
                    time.sleep(self.retry_delay)

        print(f"警告: {self.task_name} 重试 {self.retry_count} 次均失败: {last_error}")
        data = {
            "url_name": self.task_name,
            "url": self.url,
            "threshold": self.threshold,
            "timeout": 1,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expect_json": self.expect_json,
            "json_path": self.json_path,
            "json_path_value": self.json_path_value,
        }
        print(data)
        ck = cherker(method="post")
        ck.make_data(data)


class load_config:
    """
    配置加载与任务调度管理器
    """

    def __init__(self):
        with open(config.tasks_yaml, "r", encoding="utf-8") as f:
            self.tasks = yaml.safe_load(f)

        from apscheduler.executors.pool import ThreadPoolExecutor

        executors = {"default": ThreadPoolExecutor(max_workers=5)}
        job_defaults = {"coalesce": False, "max_instances": 3, "misfire_grace_time": 60}
        self.sched = BackgroundScheduler(executors=executors, job_defaults=job_defaults)

    def config_set(self, task):
        """
        解析单个任务的配置
        """
        url = task.get("url")
        threshold = task.get("threshold", {})
        timeout = task.get("timeout", 10)
        interval = task.get("interval", 10)
        headers = task.get("headers")
        cookies = task.get("cookies")
        payload = task.get("payload")
        max_response_size = task.get("max_response_size")
        retry = task.get("retry", {})
        retry_count = retry.get("count", 0)
        retry_delay = retry.get("delay", 1)
        proxy = task.get("proxy")

        # SSL 配置
        ssl = task.get("ssl", {})
        ssl_verify = ssl.get("verify", True)
        ssl_warning_days = ssl.get("warning_days", 30)

        # JSON 验证配置
        expect_json = task.get("expect_json", False)
        json_path = task.get("json_path")
        json_path_value = task.get("json_path_value")

        if "stat_code" not in threshold:
            threshold["stat_code"] = 200

        return {
            "Url": url,
            "Headers": headers,
            "Cookies": cookies,
            "Payload": payload,
            "Interval": interval,
            "Timeout": timeout,
            "threshold": threshold,
            "max_response_size": max_response_size,
            "retry_count": retry_count,
            "retry_delay": retry_delay,
            "proxy": proxy,
            "ssl_verify": ssl_verify,
            "ssl_warning_days": ssl_warning_days,
            "expect_json": expect_json,
            "json_path": json_path,
            "json_path_value": json_path_value,
        }

    def add_task(self, task):
        """
        添加单个检查任务到调度器
        """
        task_name = task.get("name")
        method = task.get("method", "get")

        if method == "post":
            print("task {} post method".format(task_name))
            conf = self.config_set(task)

            task_obj = post_method(
                task_name=task_name,
                url=conf["Url"],
                headers=conf["Headers"],
                cookies=conf["Cookies"],
                payload=conf["Payload"],
                timeout=conf["Timeout"],
                threshold=conf["threshold"],
                max_response_size=conf["max_response_size"],
                retry_count=conf["retry_count"],
                retry_delay=conf["retry_delay"],
                proxy=conf["proxy"],
                ssl_verify=conf["ssl_verify"],
                ssl_warning_days=conf["ssl_warning_days"],
                expect_json=conf["expect_json"],
                json_path=conf["json_path"],
                json_path_value=conf["json_path_value"],
            )
            self.sched.add_job(
                task_obj.post_instan,
                "interval",
                seconds=conf["Interval"],
                id=task_name,
                max_instances=10,
                replace_existing=True,
            )

        elif method == "get":
            print("task {} get method".format(task_name))
            conf = self.config_set(task)

            task_obj = get_method(
                task_name=task_name,
                url=conf["Url"],
                headers=conf["Headers"],
                cookies=conf["Cookies"],
                payload=conf["Payload"],
                timeout=conf["Timeout"],
                threshold=conf["threshold"],
                max_response_size=conf["max_response_size"],
                retry_count=conf["retry_count"],
                retry_delay=conf["retry_delay"],
                proxy=conf["proxy"],
                ssl_verify=conf["ssl_verify"],
                ssl_warning_days=conf["ssl_warning_days"],
                expect_json=conf["expect_json"],
                json_path=conf["json_path"],
                json_path_value=conf["json_path_value"],
            )
            self.sched.add_job(
                task_obj.get_instan,
                "interval",
                seconds=conf["Interval"],
                id=task_name,
                max_instances=10,
                replace_existing=True,
            )

        else:
            print(
                "{}........配置文件错误:请检查你的的请求方法，method = post ,method = get".format(
                    task_name
                )
            )

    def loading_task(self):
        """
        加载所有配置并启动调度器
        """
        task_list = self.tasks.get("tasks", [])
        for task in task_list:
            self.add_task(task=task)
        self.sched.start()
        print("start")

    def get_jobs(self):
        job_list = []
        for instan in self.sched.get_jobs():
            job_list.append(instan.id)
        return job_list

    def remove_job(self, task_name):
        self.sched.remove_job(task_name)

    def stop_job(self, task_name):
        self.sched.pause_job(job_id=task_name)
        return True

    def resume_job(self, task_name):
        self.sched.resume_job(job_id=task_name)
        return True

    def shut_sched(self):
        self.sched.shutdown()
        return True

    def add_job(self, task_info):
        """
        动态添加任务（通过 API）
        """
        job_list = self.get_jobs()
        print(job_list)
        task_name = task_info.get("section")
        if task_name not in job_list:
            task = {
                "name": task_name,
                "url": task_info.get("url"),
                "method": task_info.get("method", "get"),
                "timeout": task_info.get("timeout", 10),
                "interval": task_info.get("interval", 10),
                "headers": task_info.get("headers"),
                "cookies": task_info.get("cookies"),
                "payload": task_info.get("payload"),
                "threshold": task_info.get("threshold", {"stat_code": 200}),
            }
            print([t.get("name") for t in self.tasks.get("tasks", [])])
            self.tasks["tasks"].append(task)
            self.add_task(task=task)
            return "add success"
        else:
            print(task_name, "is exits")
            return False

    def safe_reload_config(self):
        """
        安全重新加载配置文件
        """
        import logging

        logger = logging.getLogger(__name__)
        try:
            with open(config.tasks_yaml, "r", encoding="utf-8") as f:
                new_tasks = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"配置文件解析失败: {e}")
            return False

        if not hasattr(self, "tasks"):
            logger.warning("tasks 未初始化，跳过重载")
            return False

        old_task_names = set(t.get("name") for t in self.tasks.get("tasks", []))
        new_task_names = set(t.get("name") for t in new_tasks.get("tasks", []))

        for name in old_task_names - new_task_names:
            try:
                job = self.sched.get_job(name)
                if job:
                    self.sched.remove_job(name)
                    logger.info(f"已移除任务: {name}")
            except Exception as e:
                logger.error(f"移除任务 {name} 失败: {e}")

        for task in new_tasks.get("tasks", []):
            try:
                name = task.get("name")
                job = self.sched.get_job(name)
                if job:
                    self.sched.remove_job(name)
                self.add_task(task)
                logger.info(f"已更新任务: {name}")
            except Exception as e:
                logger.error(f"任务 {name} 加载失败: {e}")
                continue

        self.tasks = new_tasks
        return True

    def start_sched(self):
        self.sched.start()


class ReportTask:
    """定时汇总报告任务"""

    def __init__(self, interval_hours=2):
        self.interval_hours = interval_hours

    @staticmethod
    def _parse_alerts(alarm):
        """将 alarm 字典转换为可读告警列表"""
        alarm = alarm or {}
        labels = []
        if alarm.get("code_warm") == 1:
            labels.append("状态码")
        if alarm.get("timeout_warm") == 1:
            labels.append("超时")
        if alarm.get("math_warm") == 1:
            labels.append("关键字")
        if alarm.get("json_warm") == 1:
            labels.append("JSON路径")
        if alarm.get("delay_warm") == 1:
            labels.append("响应时间")
        if alarm.get("ssl_warm") == 1:
            labels.append("SSL证书")
        return labels

    @staticmethod
    def _extract_latest_time(data, task_name):
        """从持久化数据中提取任务最近一次检查时间"""
        latest = None
        for key, records in data.items():
            if key in {"alarm", "alarm_notified", "last_alert_time", "last_resp_time"}:
                continue
            if not isinstance(records, list):
                continue

            for item in records:
                if not isinstance(item, dict):
                    continue
                task_block = item.get(task_name)
                if not isinstance(task_block, dict):
                    continue
                time_str = task_block.get("time")
                if not time_str:
                    continue
                try:
                    dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
                if latest is None or dt > latest:
                    latest = dt
        return latest

    def generate_report(self):
        """生成汇总报告"""
        import pickle
        import os

        report_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data_dir = "data"
        normal_tasks = []
        current_alert_tasks = []
        notified_alert_tasks = []
        no_data_tasks = []
        stale_tasks = []
        failed_tasks = []

        configured_tasks = []
        task_intervals = {}
        try:
            with open(config.tasks_yaml, "r", encoding="utf-8") as f:
                task_conf = yaml.safe_load(f) or {}
            configured_tasks = task_conf.get("tasks", [])
            for task in configured_tasks:
                name = task.get("name")
                if name:
                    task_intervals[name] = int(task.get("interval", 10))
        except Exception as e:
            return (
                "📊 URL监控汇总报告",
                f"汇总时间: {report_time}\n读取任务配置失败: {e}",
            )

        total_tasks = len([t for t in configured_tasks if t.get("name")])

        for task in configured_tasks:
            task_name = task.get("name")
            if not task_name:
                continue

            filepath = os.path.join(data_dir, f"{task_name}.pkl")
            if not os.path.exists(filepath):
                no_data_tasks.append(f"- {task_name}")
                continue

            try:
                with open(filepath, "rb") as f:
                    data = pickle.load(f)
            except Exception as e:
                failed_tasks.append(f"- {task_name}: {e}")
                continue

            current_alerts = self._parse_alerts(data.get("alarm", {}))
            notified_alerts = self._parse_alerts(
                data.get("alarm_notified", data.get("alarm", {}))
            )

            if current_alerts:
                current_alert_tasks.append(
                    f"- {task_name}: {', '.join(current_alerts)}"
                )
            else:
                normal_tasks.append(f"- {task_name}")

            if notified_alerts:
                notified_alert_tasks.append(
                    f"- {task_name}: {', '.join(notified_alerts)}"
                )

            latest_time = self._extract_latest_time(data, task_name)
            if latest_time is None:
                stale_tasks.append(f"- {task_name}: 无有效检查时间")
            else:
                interval = task_intervals.get(task_name, 10)
                stale_seconds = max(interval * 3, 180)
                age = (datetime.datetime.now() - latest_time).total_seconds()
                if age > stale_seconds:
                    stale_tasks.append(
                        f"- {task_name}: 最后检查 {latest_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )

        msg = f"汇总时间: {report_time}\n"
        msg += f"监控周期: {self.interval_hours}小时\n"
        msg += f"配置任务总数: {total_tasks}个\n"
        msg += f"有状态文件: {total_tasks - len(no_data_tasks)}个\n"
        msg += f"无状态文件: {len(no_data_tasks)}个\n\n"

        msg += f"✅ 当前正常: {len(normal_tasks)}个\n"
        for task_line in normal_tasks:
            msg += task_line + "\n"

        msg += f"\n⚠️ 当前异常(按 alarm): {len(current_alert_tasks)}个\n"
        for task_line in current_alert_tasks:
            msg += task_line + "\n"

        msg += f"\n📣 已通知异常(按 alarm_notified): {len(notified_alert_tasks)}个\n"
        for task_line in notified_alert_tasks:
            msg += task_line + "\n"

        msg += f"\n❓ 无状态文件: {len(no_data_tasks)}个\n"
        for task_line in no_data_tasks:
            msg += task_line + "\n"

        msg += f"\n🕒 数据过期/无时间: {len(stale_tasks)}个\n"
        for task_line in stale_tasks:
            msg += task_line + "\n"

        if failed_tasks:
            msg += f"\n⛔ 读取失败: {len(failed_tasks)}个\n"
            for task_line in failed_tasks:
                msg += task_line + "\n"

        return "📊 URL监控汇总报告", msg

    def send_report(self):
        """发送汇总报告"""
        from conf import config

        if not config.report_enabled:
            print("定时汇总报告未启用")
            return

        print("开始生成定时汇总报告...")
        title, msg = self.generate_report()

        if config.report_dingding_enabled:
            from view.dingding import ding_report

            ding_report(title=title, msg=msg)
            print("钉钉汇总报告已发送")

        if config.report_mail_enabled:
            pass

        print("定时汇总报告发送完成")


def add_report_job(sched, interval_hours=2):
    """添加定时汇总报告任务"""
    from conf import config

    if not config.report_enabled:
        print("定时汇总报告未启用，跳过")
        return

    report_task = ReportTask(interval_hours=interval_hours)
    sched.add_job(
        report_task.send_report,
        "interval",
        hours=interval_hours,
        id="report_task",
        replace_existing=True,
    )
    print(f"定时汇总报告任务已启动，周期: {interval_hours}小时")
