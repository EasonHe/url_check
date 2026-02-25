# 告警测试说明

本文档用于解释“为什么手动访问结果和告警数量看起来对不上”，并提供一套可复现的专项验证方法。

## 1. 告警触发模型

系统是边沿触发，不是每次轮询都重复告警。

- 首次从正常 -> 故障：发送故障告警
- 故障持续：在静默期内不重复发送
- 故障 -> 正常：发送恢复告警
- 正常持续：不重复发送恢复

因此，手动访问发现仍不匹配，但未看到“新告警”是正常现象，常见原因是该任务已在故障状态且已通知过。

## 2. 测试任务与预期

以下是联调用任务（见 `conf/tasks.yaml`）及预期：

- `test-keyword-alert`
  - `math_str = NON_EXISTENT_KEYWORD_XYZ`
  - 预期：关键字故障告警
- `test-jsonpath-alert`
  - `json_path = $.slideshow.author`
  - `json_path_value = WRONG_AUTHOR_NAME`
  - 预期：JSON 路径故障告警
- `test-timeout-alert`
  - 请求 `https://httpbin.org/delay/10` 且 `timeout=3`
  - 预期：超时故障告警
- `test-delay-alert`
  - 请求 `https://httpbin.org/delay/2` 且 `delay=300`
  - 预期：响应时间过长故障告警

## 3. 关键日志检查项

告警日志位于 `logs/alert_YYYY-MM-DD.log`（JSON 行）。

重点检查两类历史问题是否已消失：

- 不应出现：`【恢复】...状态码异常...实际: -1`
- 不应出现：`【恢复】...JSON验证失败...状态: 不匹配` 或 `实际: null`

## 4. 快速排查“为什么没看到告警”

1. 检查全局开关：`conf/config.py`
   - `enable_alerts`
   - `enable_dingding`
   - `enable_mail`
2. 检查类型开关：`conf/alerts.yaml`
   - 对应类型 `enabled/channels/recover/suppress_minutes`
3. 检查任务状态文件：`data/<task>.pkl`
   - `alarm`（当前状态）
   - `alarm_notified`（已通知状态）
   - `last_alert_time`（静默期判断）
4. 若需完整重放链路：
   - 停服务
   - 清理 `data/*.pkl` 与 `logs/alert_*.log`
   - 启动后只保留少量目标任务验证
