# alerts_config.py
import yaml
import os

# 告警配置路径
ALERTS_YAML = "conf/alerts.yaml"


def load_alerts_config():
    """加载告警配置"""
    if not os.path.exists(ALERTS_YAML):
        return {"alerts": []}

    with open(ALERTS_YAML, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_alert_config(alert_name):
    """获取指定告警类型的配置"""
    config = load_alerts_config()
    for alert in config.get("alerts", []):
        if alert.get("name") == alert_name:
            return alert
    return None


def is_alert_enabled(alert_name):
    """检查指定告警类型是否启用"""
    alert = get_alert_config(alert_name)
    return alert.get("enabled", False) if alert else False


def get_alert_channels(alert_name):
    """获取指定告警类型的通知渠道"""
    alert = get_alert_config(alert_name)
    return alert.get("channels", []) if alert else []


def is_recover_enabled(alert_name):
    """检查是否发送恢复通知"""
    alert = get_alert_config(alert_name)
    return alert.get("recover", True) if alert else True


# 告警类型映射（配置 name -> code key）
ALERT_TYPE_MAP = {
    "status_code": {
        "code_key": "code_warm",
        "msg_key": "stat_code",
        "name": "状态码",
    },
    "timeout": {
        "code_key": "timeout_warm",
        "msg_key": "stat_timeout",
        "name": "超时",
    },
    "content_match": {
        "code_key": "math_warm",
        "msg_key": "stat_math_str",
        "name": "关键字",
    },
    "delay": {
        "code_key": "delay_warm",
        "msg_key": "stat_delay",
        "name": "响应时间",
    },
}


def get_alert_type_info(alert_name):
    """获取告警类型信息"""
    return ALERT_TYPE_MAP.get(alert_name, {})


# 加载配置
alerts_config = load_alerts_config()
