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


def get_alert_suppress_minutes(alert_name, default=120):
    """获取告警抑制时间（分钟）

    Args:
        alert_name: 告警类型名称
        default: 默认抑制时间（分钟），默认120分钟

    Returns:
        int: 抑制时间（分钟），0表示不抑制
    """
    alert = get_alert_config(alert_name)
    return alert.get("suppress_minutes", default) if alert else default


# 告警类型映射（配置 name -> code key）
ALERT_TYPE_MAP = {
    "status_code": {
        "code_key": "code_warm",
        "msg_key": "stat_code",
        "name": "状态码异常",
    },
    "timeout": {
        "code_key": "timeout_warm",
        "msg_key": "stat_timeout",
        "name": "请求超时",
    },
    "content_match": {
        "code_key": "math_warm",
        "msg_key": "stat_math_str",
        "name": "关键字不匹配",
    },
    "json_path": {
        "code_key": "json_warm",
        "msg_key": "stat_json_path",
        "name": "JSON验证失败",
    },
    "delay": {
        "code_key": "delay_warm",
        "msg_key": "stat_delay",
        "name": "响应时间过长",
    },
    "ssl_expiry": {
        "code_key": "ssl_warm",
        "msg_key": "stat_ssl",
        "name": "SSL证书过期",
    },
}


def get_alert_type_info(alert_name):
    """获取告警类型信息"""
    return ALERT_TYPE_MAP.get(alert_name, {})


# 加载配置
alerts_config = load_alerts_config()
