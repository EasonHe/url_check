# config.py
import sys, os

mail_conf = "conf/mail.ini"  # 邮件程序使用的文件
tasks_yaml = "conf/tasks.yaml"  # YAML 格式任务配置文件
# 告警设置
send_to = ["hewei@raiyee.com"]
history_datat_day = 3

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
enable_alerts = True  # 总开关（测试时开启）
enable_dingding = True  # 钉钉告警开关
enable_mail = False  # 邮件告警开关（默认关闭，需配置 mail.ini）


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

dingding_url = "https://oapi.dingtalk.com/robot/send?"
access_token = "b4b5792b89a8dd4ac97e26194ed903cee523b11c4bd31fba87819e5cf1803d2b"

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
alert_log_enabled = True
alert_log_retention_days = 30

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
report_enabled = True  # 默认开启
report_interval_hours = 2  # 默认2小时
report_dingding_enabled = True  # 钉钉汇总报告
report_mail_enabled = False  # 邮件汇总报告
