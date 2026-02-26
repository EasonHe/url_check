import os
import pickle
import datetime
import logging
import ssl
import json
import glob
from datetime import timedelta
from prometheus_client import Counter, Histogram, Gauge, Info
from view.mail_server import mailconf
from view.dingding import ding_sender
from conf import config

logger = logging.getLogger(__name__)

# =============================================================================
# 告警日志配置
# =============================================================================
ALERT_LOG_DIR = "logs"
ALERT_LOG_FILE = os.path.join(ALERT_LOG_DIR, "alert.log")
STATE_DIR = "data"


def _ensure_log_dir():
    """确保日志目录存在"""
    if not os.path.exists(ALERT_LOG_DIR):
        os.makedirs(ALERT_LOG_DIR, exist_ok=True)


def _ensure_state_dir():
    """确保运行状态目录存在。"""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        return True
    except Exception as e:
        logger.warning(f"创建状态目录失败 {STATE_DIR}: {e}")
        return False


def _load_state_data(datafile):
    """读取任务状态文件，失败时返回空字典。"""
    try:
        with open(datafile, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.warning(f"读取状态文件失败 {datafile}: {e}")
        return {}


def _save_state_data(datafile, payload):
    """写入任务状态文件，失败时仅记录日志。"""
    if not _ensure_state_dir():
        return False

    try:
        with open(datafile, "wb") as f:
            pickle.dump(payload, f)
        return True
    except Exception as e:
        logger.warning(f"写入状态文件失败 {datafile}: {e}")
        return False


def _get_log_filename():
    """获取带日期的日志文件名"""
    _ensure_log_dir()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    return os.path.join(ALERT_LOG_DIR, f"alert_{today}.log")


def _cleanup_old_logs():
    """清理过期日志文件"""
    retention_days = getattr(config, "alert_log_retention_days", 30)
    if retention_days <= 0:
        return

    cutoff = datetime.datetime.now() - timedelta(days=retention_days)
    pattern = os.path.join(ALERT_LOG_DIR, "alert_*.log")

    for log_file in glob.glob(pattern):
        try:
            # 从文件名提取日期
            filename = os.path.basename(log_file)
            date_str = filename.replace("alert_", "").replace(".log", "")
            log_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            log_date = log_date.replace(hour=0, minute=0, second=0, microsecond=0)

            if log_date < cutoff:
                os.remove(log_file)
                logger.info(f"删除过期告警日志: {log_file}")
        except Exception as e:
            logger.warning(f"清理日志文件失败 {log_file}: {e}")


def _write_alert_log(alert_type, task_name, message, level="INFO"):
    """写入告警日志（JSON 格式）

    Args:
        alert_type: 告警类型（故障/恢复）
        task_name: 任务名称
        message: 告警消息
        level: 日志级别（INFO/WARNING/ERROR）
    """
    if not getattr(config, "alert_log_enabled", True):
        return

    try:
        log_entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "type": alert_type,
            "task_name": task_name,
            "message": message,
        }

        log_file = _get_log_filename()

        # 写入日志（追加模式）
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        # 每分钟清理一次过期日志
        if datetime.datetime.now().second == 0:
            _cleanup_old_logs()

    except Exception as e:
        logger.warning(f"写入告警日志失败: {e}")


# =============================================================================
# Prometheus 指标定义
# =============================================================================
# 指标分类：
#   - 原始数据指标：供 Prometheus/PromQL 判断
#   - 聚合指标：方便快速查看

# 原始数据指标（Prometheus 判断用）
url_check_http_status_code = Gauge(
    "url_check_http_status_code",
    "HTTP status code from URL check",
    ["task_name", "method"],
)

url_check_http_response_time_ms = Histogram(
    "url_check_http_response_time_ms",
    "HTTP response time in milliseconds",
    ["task_name", "method"],
    buckets=(10, 50, 100, 200, 300, 500, 1000, 2000, 5000),
)

url_check_http_contents = Info(
    "url_check_http_contents",
    "HTTP response contents (truncated)",
    ["task_name", "method"],
)

url_check_http_timeout = Counter(
    "url_check_http_timeout_total",
    "Total number of HTTP timeouts",
    ["task_name", "method"],
)

url_check_json_valid = Gauge(
    "url_check_json_valid",
    "JSON parsing result (1=valid, 0=invalid)",
    ["task_name", "method"],
)

url_check_json_path_match = Gauge(
    "url_check_json_path_match",
    "JSON path match result (1=match, 0=no match)",
    ["task_name", "method"],
)

url_check_content_match = Gauge(
    "url_check_content_match",
    "Content match result (1=match, 0=no match)",
    ["task_name", "method"],
)

url_check_status_code_alert = Gauge(
    "url_check_status_code_alert",
    "Status code alert state (1=alert, 0=normal)",
    ["task_name", "method"],
)

url_check_timeout_alert = Gauge(
    "url_check_timeout_alert",
    "Timeout alert state (1=alert, 0=normal)",
    ["task_name", "method"],
)

url_check_content_alert = Gauge(
    "url_check_content_alert",
    "Content alert state (1=alert, 0=normal)",
    ["task_name", "method"],
)

url_check_json_path_alert = Gauge(
    "url_check_json_path_alert",
    "JSON path alert state (1=alert, 0=normal)",
    ["task_name", "method"],
)

# 聚合指标（方便查看）
url_check_success_total = Counter(
    "url_check_success_total",
    "Total number of successful URL checks",
    ["task_name", "status_code", "method"],
)

url_check_response_time_seconds = Histogram(
    "url_check_response_time_seconds",
    "URL check response time in seconds (deprecated, use url_check_http_response_time_ms)",
    ["task_name", "method"],
    buckets=(0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0),
)

url_check_timeout_total = Counter(
    "url_check_timeout_total",
    "Total number of URL check timeouts",
    ["task_name", "method"],
)

url_check_ssl_expiry_days = Gauge(
    "url_check_ssl_expiry_days",
    "SSL certificate expiry days remaining",
    ["task_name", "method"],
)

url_check_ssl_verified = Counter(
    "url_check_ssl_verified",
    "SSL certificate verification status",
    ["task_name", "method", "verified"],
)

url_check_ssl_expiry_alert = Gauge(
    "url_check_ssl_expiry_alert",
    "SSL expiry alert state (1=alert, 0=normal)",
    ["task_name", "method"],
)


class cherker:
    def __init__(
        self,
        delay=0,
        stat_code=0,
        math_str=0,
        timeout=0,
        method=None,
        expect_json=False,
        json_path=None,
        json_path_value=None,
    ):
        """
        URL 检查结果处理器初始化

        功能：
            - 处理 URL 检查后的结果数据
            - 判定是否触发告警
            - 更新 Prometheus 指标

        属性：
            delay: 响应时间是否超阈值（0=正常，1=超时）
            stat_code: 状态码是否匹配（0=匹配，1=不匹配）
            stat_math_str: 关键字是否匹配（0=匹配，1=不匹配）
            timeout: 是否超时（0=正常，1=超时）
            method: HTTP 方法（"get" 或 "post"）
            task_name: 任务名称
            now_alarm: 当前告警状态字典
            message: 告警消息字典
            expect_json: 是否期望 JSON 响应
            json_path: JSON Path 表达式
            json_path_value: 期望的 JSON Path 值（字符串比较）
        """
        self.delay = delay
        self.stat_code = stat_code
        self.stat_math_str = math_str
        self.timeout = timeout
        self.task_name = None
        self.method = method
        self.expect_json = expect_json
        self.json_path = json_path
        self.json_path_value = json_path_value
        self.now_alarm = {
            "code_warm": 0,
            "delay_warm": 0,
            "math_warm": 0,
            "json_warm": 0,
            "timeout_warm": 0,
            "ssl_warm": 0,
        }
        self.message = {}
        self.last_alert_time = {}  # {alert_type: datetime}
        self.last_resp_time = None  # 上次响应时间（毫秒）
        self._prev_resp_time = None  # 发送告警前的响应时间
        self._has_http_response = False
        self._json_parse_ok = False
        self._json_path_ok = False

    def validate_json(
        self, content, expect_json=False, json_path_expr=None, json_path_value=None
    ):
        """
        JSON 验证方法

        功能：
            1. 尝试解析响应内容为 JSON
            2. 如果配置了 json_path，验证字段是否存在
            3. 如果配置了 json_path_value，验证值是否匹配（字符串比较）
            4. 更新 Prometheus 指标

        Args:
            content: 响应文本内容
            expect_json: 是否期望 JSON 响应
            json_path_expr: JSON Path 表达式（如 "$.status"）
            json_path_value: 期望的 JSON Path 值（字符串比较）

        Returns:
            tuple: (json_parse_ok, json_path_ok, actual_value)
                - json_parse_ok: JSON 解析是否成功
                - json_path_ok: JSON Path 验证是否通过
                - actual_value: JSON Path 提取的实际值（字符串）
        """
        json_parse_ok = False
        json_path_ok = False
        actual_value = None
        json_data = None

        if not expect_json:
            url_check_json_valid.labels(
                task_name=self.task_name or "", method=self.method or ""
            ).set(0)
            return True, True, None

        try:
            json_data = json.loads(content)
            json_parse_ok = True
            url_check_json_valid.labels(
                task_name=self.task_name or "", method=self.method or ""
            ).set(1)
        except (json.JSONDecodeError, TypeError):
            url_check_json_valid.labels(
                task_name=self.task_name or "", method=self.method or ""
            ).set(0)
            return False, False, None

        if not json_path_expr:
            return True, True, None

        try:
            from jsonpath_ng import parse

            matcher = parse(json_path_expr)
            match = matcher.find(json_data)
            if match:
                if json_path_value is not None:
                    match_value = match[0].value
                    # JSON 特殊值转换（JSON 原始值 → 字符串）
                    if match_value is True:
                        actual_value = "true"
                    elif match_value is False:
                        actual_value = "false"
                    elif match_value is None:
                        actual_value = "null"
                    else:
                        actual_value = str(match_value)

                    expected_value = str(json_path_value)
                    json_path_ok = actual_value == expected_value
                    logger.debug(
                        f"JSON Path 值比较: '{actual_value}' == '{expected_value}' -> {json_path_ok}"
                    )
                else:
                    json_path_ok = True
            else:
                json_path_ok = False
        except Exception as e:
            logger.warning(f"JSON Path 验证失败: {json_path_expr}, 错误: {e}")
            json_path_ok = False

        url_check_json_path_match.labels(
            task_name=self.task_name or "", method=self.method or ""
        ).set(1 if json_path_ok else 0)

        return json_parse_ok, json_path_ok, actual_value

    def _send_alert_if_needed(
        self, alert_name, alarm, threshold, is_recovery=False, is_first_run=False
    ):
        """统一处理告警/恢复通知

        Args:
            alert_name: 告警类型名称 (status_code, timeout, content_match, delay)
            alarm: 上次告警状态字典
            threshold: 配置阈值字典
            is_recovery: 是否是恢复通知
        """
        # 获取告警类型信息
        alert_info = config.get_alert_type_info(alert_name)
        if not alert_info:
            return None

        code_key = alert_info.get("code_key")
        msg_key = alert_info.get("msg_key")
        alert_display_name = alert_info.get("name", alert_name)

        # 检查是否启用
        if not config.enable_alerts or not config.is_alert_enabled(alert_name):
            return None

        # 获取通知渠道
        channels = config.get_alert_channels(alert_name)

        # 判断是否需要发送
        # 首次运行：只发送故障告警
        # 后续运行：
        #   - 故障发生：now_alarm=1, alarm=0
        #   - 恢复通知：now_alarm=0, alarm=1
        need_send = False
        subject = ""
        recovery_event = bool(is_recovery)

        if is_first_run:
            # 首次运行：故障发生才发送
            if self.now_alarm[code_key] == 1:
                subject = "🚨 【故障】{} - {}".format(
                    self.task_name, alert_display_name
                )
                need_send = True
        else:
            # 后续运行：故障发生或恢复才发送
            if self.now_alarm[code_key] == 1 and alarm[code_key] == 0:
                # 故障发生
                subject = "🚨 【故障】{} - {}".format(
                    self.task_name, alert_display_name
                )
                need_send = True
            elif self.now_alarm[code_key] == 0 and alarm[code_key] == 1:
                # 恢复通知
                if config.is_recover_enabled(alert_name):
                    subject = "✅ 【恢复】{} - {}".format(
                        self.task_name, alert_display_name
                    )
                    need_send = True
                    recovery_event = True

        if not need_send or not msg_key:
            return None

        # 恢复通知防呆：只有当前检查结果可验证为“恢复”时才允许发送
        if (
            recovery_event
            and alert_name == "status_code"
            and not self._has_http_response
        ):
            return None

        if (
            recovery_event
            and alert_name == "content_match"
            and not self._has_http_response
        ):
            return None

        if recovery_event and alert_name == "json_path":
            if not (
                self._has_http_response and self._json_parse_ok and self._json_path_ok
            ):
                return None

        # 对于 delay 告警，检查当前响应时间是否仍然超限
        # 如果当前响应时间超限，发送故障告警而不是恢复通知
        if recovery_event and alert_name == "delay" and self.last_resp_time is not None:
            delay_val = threshold.get("delay") if threshold else 0
            if isinstance(delay_val, list):
                expect_delay = delay_val[0]
            elif isinstance(delay_val, int):
                expect_delay = delay_val
            else:
                expect_delay = 0
            # 检查当前响应时间是否超限
            current_resp = self.last_resp_time  # 当前响应时间
            if current_resp > expect_delay:
                # 当前响应时间仍然超限，应该发送故障告警而不是恢复
                recovery_event = False
                need_send = True
                subject = "🚨 【故障】{} - {}".format(
                    self.task_name, alert_display_name
                )

        msg = self.message.get(msg_key, "")

        # 恢复通知时，显示当前响应时间
        if recovery_event and alert_name == "delay":
            # 使用当前响应时间生成消息
            current_resp = self.last_resp_time
            if current_resp is not None:
                delay_val = threshold.get("delay") if threshold else 0
                if isinstance(delay_val, list):
                    expect_delay = delay_val[0]
                elif isinstance(delay_val, int):
                    expect_delay = delay_val
                else:
                    expect_delay = 0
                current_delay_status = "超限" if current_resp > expect_delay else "正常"
                time_str = (
                    self.message.get("stat_delay", "unknown")
                    .split("时间: ")[-1]
                    .split("\n")[0]
                    if self.message.get("stat_delay")
                    else "unknown"
                )
                msg = "- 期望: <{}ms\n- 实际: {}ms\n- 状态: {}\n- 时间: {}\n- URL: {}".format(
                    expect_delay,
                    round(current_resp, 2),
                    current_delay_status,
                    time_str,
                    self.message.get("stat_delay", "").split("URL: ")[-1]
                    if self.message.get("stat_delay")
                    else self.task_name,
                )

        # 静默期检查（故障告警才检查，恢复通知和首次运行不受限制）
        suppress_minutes = config.get_alert_suppress_minutes(alert_name)
        if suppress_minutes > 0 and not recovery_event and not is_first_run:
            last_time = self.last_alert_time.get(alert_name)
            if last_time:
                elapsed = (datetime.datetime.now() - last_time).total_seconds() / 60
                if elapsed < suppress_minutes:
                    logger.info(
                        "告警抑制: %s - %s 在静默期内(%.1f/%dmin), 跳过发送",
                        self.task_name,
                        alert_display_name,
                        elapsed,
                        suppress_minutes,
                    )
                    return None

        # 发送钉钉
        if "dingding" in channels and config.enable_dingding:
            ding_sender(title=subject, msg=msg)

        # 发送邮件
        if "mail" in channels and config.enable_mail:
            mailconf(tos=config.send_to, subject=subject, content=msg)

        # 写入独立告警日志（JSON 格式）
        log_level = "WARNING" if not recovery_event else "INFO"
        _write_alert_log(
            alert_type="故障" if not recovery_event else "恢复",
            task_name=self.task_name,
            message=f"{subject} | {msg}",
            level=log_level,
        )

        # 记录故障告警发送时间（恢复通知不记录，以便故障再次发生时能立即告警）
        if not recovery_event:
            self.last_alert_time[alert_name] = datetime.datetime.now()

        return 0 if recovery_event else 1

    def send_warm(self, alarm=None, threshold=None, is_first_run=False):
        """发送告警通知（支持配置化）

        Args:
            alarm: 上次已发送告警状态字典
            threshold: 配置阈值字典
            is_first_run: 是否是首次运行
        """
        notified_alarm = (alarm or {}).copy()
        alert_types = [
            "status_code",
            "timeout",
            "content_match",
            "json_path",
            "delay",
            "ssl_expiry",
        ]

        for alert_name in alert_types:
            sent_state = self._send_alert_if_needed(
                alert_name, notified_alarm, threshold, is_first_run=is_first_run
            )
            alert_info = config.get_alert_type_info(alert_name) or {}
            code_key = alert_info.get("code_key")
            if code_key and sent_state is not None:
                notified_alarm[code_key] = sent_state

        return notified_alarm

    def _update_alert_state_metrics(self, method):
        """更新判定后告警状态指标（1=告警，0=正常）"""
        url_check_status_code_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(self.now_alarm.get("code_warm", 0))
        url_check_timeout_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(self.now_alarm.get("timeout_warm", 0))
        url_check_content_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(self.now_alarm.get("math_warm", 0))
        url_check_json_path_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(self.now_alarm.get("json_warm", 0))
        url_check_ssl_expiry_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(self.now_alarm.get("ssl_warm", 0))

    def first_run_task(self, status_data, threshold, time, datafile):
        """
        首次运行任务初始化

        功能：
            - 第一次检查某 URL 时调用
            - 初始化告警状态（默认都是正常）
            - 持久化首次检查结果到文件

        Args:
            status_data: 检查结果数据字典
            threshold: 配置阈值字典
            time: 检查时间字符串
            datafile: 持久化文件路径（data/{task_name}.pkl）
        """
        temp_dict = {}
        self.last_resp_time = status_data[self.task_name].get("delay")
        # 开始设置为0,都是对的，如果出现错误则修改状态码

        if status_data[self.task_name]["stat_code"] == 1:
            print("{} 状态码故障".format(self.task_name))
            self.now_alarm["code_warm"] = 1

        if status_data[self.task_name]["timeout"] == 1:
            self.now_alarm["timeout_warm"] = 1
            print("{} is timeout".format(self.task_name))

        if status_data[self.task_name]["stat_math_str"] == 1:
            self.now_alarm["math_warm"] = 1
            print("{} 不存在 {}这个字段".format(self.task_name, threshold["math_str"]))

        if status_data[self.task_name]["stat_delay"] == 1:
            self.now_alarm["delay_warm"] = 1
            print(
                "{},第一次运行{}响应时间超过预定设计的阈值，请检查阈值是否合理".format(
                    self.task_name, status_data[self.task_name]["delay"]
                )
            )

        # 添加 JSON 路径告警处理（修复）
        if status_data[self.task_name].get("json_warm") == 1:
            self.now_alarm["json_warm"] = 1
            print("{} JSON路径验证失败".format(self.task_name))

        # 添加 SSL 证书告警处理
        if status_data[self.task_name].get("ssl_warm") == 1:
            self.now_alarm["ssl_warm"] = 1
            print("{} SSL证书即将过期".format(self.task_name))

        # 根据内容发送消息
        # 首次运行：发送故障告警
        notified_alarm = {
            "code_warm": 0,
            "delay_warm": 0,
            "math_warm": 0,
            "timeout_warm": 0,
            "json_warm": 0,
            "ssl_warm": 0,
        }
        temp_dict["last_alert_time"] = {}
        # 第一次运行时，使用全0的已发送状态参与边沿判断
        notified_alarm = self.send_warm(
            alarm=notified_alarm, threshold=threshold, is_first_run=True
        )

        # 录入当前检查的alarm状态信息
        temp_dict["alarm"] = self.now_alarm
        temp_dict["alarm_notified"] = notified_alarm
        temp_dict["last_alert_time"] = self.last_alert_time
        temp_dict["last_resp_time"] = self.last_resp_time
        print("录入, last_alert_time=", self.last_alert_time, "alarm=", self.now_alarm)
        # 录入原始信息
        temp_dict[time.split()[0]] = [(status_data)]
        # print(temp_dict)

        if _save_state_data(datafile, temp_dict):
            print("写入完毕")

    def make_data(self, data_dict):
        """
        处理 URL 检查结果数据

        功能：
            1. 提取检查结果数据
            2. 全部验证（要数据说话）
            3. 暴露原始数据指标供 Prometheus 判断
            4. 应用层只做 JSON 结构化验证（Prometheus 难以处理）

        混合方案分工：
            - Prometheus 判断：状态码、响应时间、关键字（PromQL）
            - 应用层判断：JSON 结构化验证（json_path + json_path_value）

        Args:
            data_dict: URL 检查结果字典
        """
        self.task_name = data_dict["url_name"]
        time = data_dict["time"]
        threshold = data_dict.get("threshold", {})
        expect_json = data_dict.get("expect_json", False)
        json_path = data_dict.get("json_path")
        json_path_value = data_dict.get("json_path_value")

        method = self.method or "unknown"
        json_path_ok = False
        json_parse_ok = False
        actual_value = None

        # ==========================================================================
        # 1. 暴露原始数据指标（供 Prometheus 判断）
        # ==========================================================================

        if data_dict["timeout"] == 0:
            code = data_dict["stat_code"]
            content = data_dict["contents"]
            rs_time = data_dict["resp_time"]

            # HTTP 状态码
            url_check_http_status_code.labels(
                task_name=self.task_name, method=method
            ).set(code)

            # 响应时间（毫秒）
            url_check_http_response_time_ms.labels(
                task_name=self.task_name, method=method
            ).observe(rs_time)

            # 响应内容（截断）
            # 只有未配置 math_str 时才传给 Prometheus（供 Prometheus 正则匹配）
            if "math_str" not in threshold:
                content_info = content[:500] if content else ""
                url_check_http_contents.labels(
                    task_name=self.task_name, method=method
                ).info({"body": content_info})

            # JSON 解析结果（应用层判断）
            json_parse_ok, json_path_ok, actual_value = self.validate_json(
                content,
                expect_json=expect_json,
                json_path_expr=json_path,
                json_path_value=json_path_value,
            )

            url_check_json_valid.labels(task_name=self.task_name, method=method).set(
                1 if json_parse_ok else 0
            )

            url_check_json_path_match.labels(
                task_name=self.task_name, method=method
            ).set(1 if json_path_ok else 0)

            # 关键字匹配结果（应用层判断）
            if "math_str" in threshold:
                content_match = 1 if threshold["math_str"] in content else 0
                url_check_content_match.labels(
                    task_name=self.task_name, method=method
                ).set(content_match)

        else:
            # 超时
            code = -1  # 超时时无状态码
            content = ""
            rs_time = 0

            url_check_http_timeout.labels(task_name=self.task_name, method=method).inc()

            url_check_http_status_code.labels(
                task_name=self.task_name, method=method
            ).set(-1)

            url_check_json_valid.labels(task_name=self.task_name, method=method).set(0)

            url_check_json_path_match.labels(
                task_name=self.task_name, method=method
            ).set(0)

            url_check_content_match.labels(task_name=self.task_name, method=method).set(
                0
            )

        self._has_http_response = code >= 0
        self._json_parse_ok = json_parse_ok
        self._json_path_ok = json_path_ok

        # ==========================================================================
        # 2. 全部验证（要数据说话）
        # ==========================================================================

        # 状态码验证（非超时情况，code>=0表示有HTTP响应）
        if code >= 0 and code != threshold.get("stat_code", 200):
            self.stat_code = 1
        else:
            self.stat_code = 0

        # 关键字验证
        if code != -1 and "math_str" in threshold:
            self.stat_math_str = 0 if threshold["math_str"] in content else 1
        else:
            self.stat_math_str = 0

        # JSON路径验证状态
        if code != -1 and json_path and json_path_value is not None:
            self.now_alarm["json_warm"] = 0 if json_path_ok else 1
        else:
            self.now_alarm["json_warm"] = 0

        # 响应时间验证
        if code != -1 and "delay" in threshold:
            delay_val = threshold["delay"]
            if isinstance(delay_val, list):
                delay_threshold = delay_val[0]
            else:
                delay_threshold = delay_val
            self.delay = 0 if rs_time < delay_threshold else 1
        else:
            self.delay = 0

        # ==========================================================================
        # 3. 生成状态数据和告警消息
        # ==========================================================================

        # SSL证书告警处理（需要在生成 status_data 之前执行）
        ssl_expiry_days = data_dict.get("ssl_expiry_days")
        ssl_warning_days = data_dict.get("ssl_warning_days", 30)
        if ssl_expiry_days is not None:
            if ssl_expiry_days < ssl_warning_days:
                self.now_alarm["ssl_warm"] = 1
                self.message["stat_ssl"] = (
                    "- 剩余: {}天\n- 阈值: {}天\n- 时间: {}\n- URL: {}".format(
                        ssl_expiry_days, ssl_warning_days, time, data_dict["url"]
                    )
                )
            else:
                self.now_alarm["ssl_warm"] = 0
                self.message["stat_ssl"] = (
                    "- 剩余: {}天\n- 阈值: {}天\n- 时间: {}\n- URL: {}".format(
                        ssl_expiry_days, ssl_warning_days, time, data_dict["url"]
                    )
                )

        status_data = {
            self.task_name: {
                "url": data_dict["url"],
                "code": code,
                "stat_code": self.stat_code,
                "delay": rs_time,
                "stat_delay": self.delay,
                "stat_math_str": self.stat_math_str,
                "json_warm": self.now_alarm.get("json_warm", 0),
                "ssl_warm": self.now_alarm.get("ssl_warm", 0),
                "timeout": data_dict.get("timeout", 0),
                "time": time,
            }
        }

        # 告警消息 - 简洁版
        expect_code = threshold.get("stat_code", 200)
        self.message["stat_code"] = (
            "- 期望: {}\n- 实际: {}\n- 时间: {}\n- URL: {}".format(
                expect_code, code, time, data_dict["url"]
            )
        )

        expect_timeout = threshold.get("timeout", 10)
        timeout_actual = "超时" if data_dict.get("timeout", 0) == 1 else "正常"
        self.message["stat_timeout"] = (
            "- 期望: {}秒\n- 实际: {}\n- 时间: {}\n- URL: {}".format(
                expect_timeout,
                timeout_actual,
                time,
                data_dict["url"],
            )
        )

        math_str = threshold.get("math_str", "")
        math_status = "不匹配" if self.stat_math_str == 1 else "匹配"
        self.message["stat_math_str"] = (
            "- 关键字: {}\n- 状态: {}\n- 时间: {}\n- URL: {}".format(
                math_str, math_status, time, data_dict["url"]
            )
        )

        # 响应时间告警消息
        delay_val = threshold.get("delay")
        if isinstance(delay_val, list):
            expect_delay = delay_val[0]
        elif isinstance(delay_val, int):
            expect_delay = delay_val
        else:
            expect_delay = 0
        delay_status = "超限" if self.delay == 1 else "正常"
        self.message["stat_delay"] = (
            "- 期望: <{}ms\n- 实际: {}ms\n- 状态: {}\n- 时间: {}\n- URL: {}".format(
                expect_delay, round(rs_time, 2), delay_status, time, data_dict["url"]
            )
        )

        # JSON路径匹配告警消息
        if json_path and json_path_value is not None:
            expected_json_value = str(json_path_value)
            if not self._has_http_response:
                actual_json_value = "未校验"
                json_status = "未校验（请求失败）"
            elif not json_parse_ok:
                actual_json_value = "未校验"
                json_status = "未校验（非JSON响应）"
            else:
                actual_json_value = actual_value if actual_value else "null"
                json_status = "不匹配" if not json_path_ok else "匹配"
            self.message["stat_json_path"] = (
                "- 路径: {}\n"
                "- 期望: {}\n"
                "- 实际: {}\n"
                "- 状态: {}\n"
                "- 时间: {}\n"
                "- URL: {}".format(
                    json_path,
                    expected_json_value,
                    actual_json_value,
                    json_status,
                    time,
                    data_dict["url"],
                )
            )

        # ==========================================================================
        # 4. 持久化和告警（保持原有逻辑）
        # ==========================================================================

        # 根据任务分类，才不会出现io 冲突
        _ensure_state_dir()
        datafile = os.path.join(STATE_DIR, "{}.pkl".format(self.task_name))  # 文件名字
        # 一开始设计状态都是好的，生成一个现在的状态和之前的状态，两个对比，发出故障警告或者恢复警告
        # 第一次运行的时候没有文件，那么先生成文件并存入数据

        if not os.path.exists(datafile):
            self.first_run_task(status_data, threshold, time, datafile)

        else:
            temp_dict = _load_state_data(datafile)
            if not isinstance(temp_dict, dict):
                logger.warning(f"状态文件格式异常，使用默认状态: {datafile}")
                temp_dict = {}
            self.last_alert_time = temp_dict.get("last_alert_time", {})
            self.last_resp_time = temp_dict.get("last_resp_time")
            # 保留时间数目
            histroy_day = (
                datetime.datetime.now()
                + datetime.timedelta(days=-config.history_datat_day)
            ).strftime("%Y-%m-%d")
            # 插入的key是当天时间
            key = str(time.split()[0])
            if key in temp_dict:
                # 取出当天数据
                today_list = temp_dict[time.split()[0]]
                # print(today_list)

                # 响应时间告警：1次超限就告警（与其他告警类型一致）
                if status_data[self.task_name]["stat_delay"] == 1:
                    print(
                        "{} 响应时间超过阈值{}ms".format(
                            self.task_name,
                            status_data[self.task_name]["delay"],
                        )
                    )
                    self.now_alarm["delay_warm"] = 1

                # temp_dict 之前保存的所有数据
                temp_dict[key].append(status_data)
                # print(temp_dict)

            # key不在现有的字典
            else:
                # 响应时间告警：1次超限就告警
                if status_data[self.task_name]["stat_delay"] == 1:
                    print(
                        "{} 响应时间超过阈值{}ms".format(
                            self.task_name,
                            status_data[self.task_name]["delay"],
                        )
                    )
                    self.now_alarm["delay_warm"] = 1
                # 设置今天的第一个字典为空
                temp_dict[key] = []
                temp_dict[key].append(status_data)

            if status_data[self.task_name]["stat_code"] == 1:
                print(
                    "{} stat_code is wrong 不是第一次运行   {}".format(
                        self.task_name, code
                    )
                )
                self.now_alarm["code_warm"] = 1

            if status_data[self.task_name]["timeout"] == 1:
                print("{} is timeout".format(self.task_name))
                self.now_alarm["timeout_warm"] = 1

            if status_data[self.task_name]["stat_math_str"] == 1:
                print(
                    "{} 不存在 {}这个字段".format(self.task_name, threshold["math_str"])
                )
                self.now_alarm["math_warm"] = 1

            # 根据开关决定是否发送告警通知
            # enable_alerts = True: 发送钉钉/邮件告警
            # enable_alerts = False: 仅收集 Prometheus 指标（通过 Alertmanager 告警）
            # 先保存上次的响应时间（在更新之前）
            self._prev_resp_time = self.last_resp_time
            self.last_resp_time = status_data[self.task_name].get("delay", rs_time)

            # 仅使用“已发送状态”做故障/恢复边沿判断，避免抑制导致的伪恢复
            notified_alarm = temp_dict.get(
                "alarm_notified",
                temp_dict.get(
                    "alarm",
                    {
                        "code_warm": 0,
                        "delay_warm": 0,
                        "math_warm": 0,
                        "timeout_warm": 0,
                        "json_warm": 0,
                        "ssl_warm": 0,
                    },
                ),
            )
            if config.enable_alerts:
                notified_alarm = self.send_warm(
                    alarm=notified_alarm,
                    threshold=threshold,
                    is_first_run=False,
                )
            else:
                logger.debug("告警通知已禁用（enable_alerts=False），跳过 send_warm")
            if histroy_day in temp_dict:
                # 根据配置文件删除历史数据保留天数
                del temp_dict[histroy_day]
            temp_dict["last_alert_time"] = self.last_alert_time
            temp_dict["last_resp_time"] = self.last_resp_time
            temp_dict["alarm"] = self.now_alarm
            temp_dict["alarm_notified"] = notified_alarm
            print(
                "第二次写入, last_alert_time=",
                self.last_alert_time,
                "alarm=",
                self.now_alarm,
            )
            # print(temp_dict)
            _save_state_data(datafile, temp_dict)

        # 判定后告警状态指标（1=告警，0=正常）
        url_check_status_code_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(status_data[self.task_name].get("stat_code", 0))
        url_check_timeout_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(status_data[self.task_name].get("timeout", 0))
        url_check_content_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(status_data[self.task_name].get("stat_math_str", 0))
        url_check_json_path_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(status_data[self.task_name].get("json_warm", 0))
        url_check_ssl_expiry_alert.labels(
            task_name=self.task_name,
            method=method,
        ).set(status_data[self.task_name].get("ssl_warm", 0))

        # ==========================================================================
        # 更新 Prometheus 聚合指标（兼容旧版）
        # ==========================================================================

        if self.timeout == 1:
            url_check_timeout_total.labels(
                task_name=self.task_name, method=method
            ).inc()
        else:
            status_code = str(code)
            url_check_success_total.labels(
                task_name=self.task_name, status_code=status_code, method=method
            ).inc()

            if isinstance(rs_time, (int, float)):
                url_check_response_time_seconds.labels(
                    task_name=self.task_name, method=method
                ).observe(rs_time / 1000.0)
