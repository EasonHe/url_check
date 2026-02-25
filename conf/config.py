"""Runtime configuration.

Priority: environment variables > code defaults.
Only URL_CHECK_* variables are supported.
"""

import os


def _env_str(name, default=""):
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default=0):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except Exception:
        return default


def _env_list(name, default=None):
    if default is None:
        default = []
    value = os.getenv(name)
    if value is None:
        return default
    items = [x.strip() for x in value.split(",") if x.strip()]
    return items if items else default


mail_conf = "conf/mail.ini"  # 邮件程序使用的文件
tasks_yaml = "conf/tasks.yaml"  # YAML 格式任务配置文件
# 告警设置
send_to = _env_list("URL_CHECK_MAIL_RECEIVERS", ["ops@example.com"])
history_datat_day = _env_int("URL_CHECK_HISTORY_DATA_DAYS", 3)

# =============================================================================
# 告警开关配置（兼容旧版）
# =============================================================================
# enable_alerts: 总开关，控制是否发送任何告警通知
#
#   True:  发送告警通知（需配合下面的单独开关）
#   False: 不发送告警，仅收集 Prometheus 指标（通过 Prometheus Alertmanager 告警）
#
# enable_dingding: 钉钉告警开关（仅在 enable_alerts=True 时生效）
#   True:  发送钉钉告警通知
#   False: 不发送钉钉告警
#
# enable_mail: 邮件告警开关（仅在 enable_alerts=True 时生效）
#   True:  发送邮件告警通知
#   False: 不发送邮件告警
#
# 使用场景：
#   - enable_alerts=False: 接入 Prometheus 生态，使用 Alertmanager 管理告警
#   - enable_alerts=True + enable_dingding=True + enable_mail=False: 仅钉钉告警
#   - enable_alerts=True + enable_dingding=False + enable_mail=True: 仅邮件告警
#   - enable_alerts=True + enable_dingding=True + enable_mail=True: 全部告警
#
# Prometheus 告警规则示例（prometheus-rules.yml）：
#   - alert: URLCheckFailed
#     expr: url_check_success_total{status_code!="200"} > 0
#     for: 1m
#     labels:
#       severity: critical
#     annotations:
#       summary: "URL {{ $labels.task_name }} 检查失败"
# =============================================================================
enable_alerts = _env_bool("URL_CHECK_ENABLE_ALERTS", True)
enable_dingding = _env_bool("URL_CHECK_ENABLE_DINGDING", True)
enable_mail = _env_bool("URL_CHECK_ENABLE_MAIL", False)


# =============================================================================
# 新版告警配置（conf/alerts.yaml）
# =============================================================================
# 从 alerts_config.py 导入配置访问方法
# 这些函数提供更细粒度的告警控制
# =============================================================================
from conf.alerts_config import (
    is_alert_enabled,
    get_alert_channels,
    is_recover_enabled,
    get_alert_type_info,
    get_alert_suppress_minutes,
    ALERT_TYPE_MAP,
)

dingding_url = _env_str(
    "URL_CHECK_DINGDING_WEBHOOK", "https://oapi.dingtalk.com/robot/send?"
)
access_token = _env_str("URL_CHECK_DINGDING_ACCESS_TOKEN", "")

# =============================================================================
# 告警日志配置
# =============================================================================
# alert_log_enabled: 是否启用独立告警日志
#   True:  启用，写入 logs/alert.log（JSON 格式）
#   False: 禁用
#
# alert_log_retention_days: 日志保留天数
#   0:   不限制
#   30:  保留 30 天
#
# 日志格式（JSON）：
# {
#   "timestamp": "2024-01-01 00:00:00",
#   "level": "INFO",
#   "type": "故障",
#   "task_name": "api-health",
#   "alert_type": "状态码",
#   "message": "code:500, threshold:200 URL:https://..."
# }
# =============================================================================
alert_log_enabled = _env_bool("URL_CHECK_ALERT_LOG_ENABLED", True)
alert_log_retention_days = _env_int("URL_CHECK_ALERT_LOG_RETENTION_DAYS", 30)

# =============================================================================
# 定时汇总报告配置
# =============================================================================
# report_enabled: 是否启用定时汇总报告
#   True:  启用定时汇总报告
#   False: 禁用
#
# report_interval_hours: 汇总周期（小时）
#   1: 每小时汇总一次
#   2: 每2小时汇总一次
#   24: 每天汇总一次
#
# report_dingding_enabled: 钉钉汇总报告开关
#   True:  发送钉钉汇总报告
#   False: 不发送
#
# report_mail_enabled: 邮件汇总报告开关
#   True:  发送邮件汇总报告
#   False: 不发送
# =============================================================================
report_enabled = _env_bool("URL_CHECK_REPORT_ENABLED", True)
report_interval_hours = _env_int("URL_CHECK_REPORT_INTERVAL_HOURS", 2)
report_dingding_enabled = _env_bool("URL_CHECK_REPORT_DINGDING_ENABLED", True)
report_mail_enabled = _env_bool("URL_CHECK_REPORT_MAIL_ENABLED", False)


def _masked(value):
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


def validate_config():
    if enable_alerts and enable_dingding and not access_token:
        print("[config] warning: URL_CHECK_DINGDING_ACCESS_TOKEN is empty")
    if enable_alerts and enable_mail and not send_to:
        print("[config] warning: URL_CHECK_MAIL_RECEIVERS is empty")


def print_config_summary():
    print(
        "[config] alerts={} dingding={} mail={} report={} interval={}h receivers={} token={}".format(
            enable_alerts,
            enable_dingding,
            enable_mail,
            report_enabled,
            report_interval_hours,
            len(send_to),
            _masked(access_token),
        )
    )


validate_config()
print_config_summary()
