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
enable_alerts = False  # 总开关
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
    ALERT_TYPE_MAP,
)

dingding_url = "https://oapi.dingtalk.com/robot/send?"
access_token = "6f3c39a23f1ce5ee22e888d9b1e61df18a61be7305ade92d179cfdfedda45e"
