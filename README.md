# URL 健康检查服务

`url-check` 是一个定时 URL 拨测服务，支持 HTTP 状态码、超时、关键字、JSON Path、SSL 到期检查，并可选发送钉钉/邮件通知。

业务服务与指标统一暴露在 `4000` 端口：
- 健康检查：`/health`
- 指标暴露：`/metrics`

## 运行模式

Prometheus 不是必需依赖。

| 模式 | 必需组件 | 告警路径 | 适用场景 |
|------|----------|----------|----------|
| Standalone（默认） | `url-check` | 应用内钉钉/邮件 | 轻量部署、快速上线 |
| Prometheus | `url-check` + Prometheus（可选 Grafana） | PromQL/Alertmanager（可与应用内并存） | 统一可观测平台 |

详情见 `docs/run-modes.md`。

## 5 分钟启动（Standalone）

```bash
# 1) 准备配置
cp .env.example .env
cp conf/tasks.yaml.example conf/tasks.yaml
cp conf/alerts.yaml.example conf/alerts.yaml

# 2) 启动服务
docker build -t easonhe/url-checker:latest .
docker compose up -d

# 3) 验证
curl http://127.0.0.1:4000/health
curl http://127.0.0.1:4000/metrics
```

## 功能说明（Feature Overview）

### 1) 状态码检查（Status Code）
- 作用：验证响应状态码是否满足 `threshold.stat_code`。
- 触发条件：状态码不等于阈值。
- 关键指标：`url_check_http_status_code`、`url_check_status_code_alert`。
- 常见误区：将业务重定向（302）任务仍配置成 200。

### 2) 超时检查（Timeout）
- 作用：监控请求是否在 `timeout` 秒内完成。
- 触发条件：请求超时。
- 关键指标：`url_check_http_timeout_total`、`url_check_timeout_alert`。
- 常见误区：把 `timeout` 设置得过小导致误报。

### 3) 内容检查（Content Match）
- 作用：验证响应文本是否包含 `threshold.math_str`。
- 触发条件：关键字不存在。
- 关键指标：`url_check_content_match`、`url_check_content_alert`。
- 常见误区：HTML 页面压缩/改版后关键词变化，需同步更新阈值。

### 4) JSON Path 检查（JSON Path）
- 作用：在 `expect_json=true` 时校验 JSON 路径和值。
- 触发条件：非 JSON、路径不存在、值不匹配。
- 关键指标：`url_check_json_valid`、`url_check_json_path_match`、`url_check_json_path_alert`。
- 常见误区：`json_path_value` 按字符串比较，需注意布尔/null 表示方式。

### 5) 响应时间检查（Delay）
- 作用：验证响应耗时是否超过 `threshold.delay`（毫秒）。
- 触发条件：响应时间超阈值。
- 关键指标：`url_check_http_response_time_ms`、`url_check_task_failures_total{reason="delay"}`。
- 常见误区：误把 `delay` 当秒配置。

### 6) SSL 到期检查（SSL Expiry）
- 作用：检查 HTTPS 证书剩余天数是否低于 `ssl.warning_days`。
- 触发条件：证书剩余天数过低或验证失败。
- 关键指标：`url_check_ssl_expiry_days`、`url_check_ssl_expiry_alert`。
- 常见误区：`ssl.verify=false` 时不会执行证书有效性判定。

### 7) 通知与抑制（Alert Suppression & Recover）
- 作用：通过 `conf/alerts.yaml` 对不同告警类型设置通知渠道、恢复通知、抑制窗口。
- 触发条件：某类告警 `enabled=true` 且满足故障判定。
- 关键指标：`url_check_*_alert`。
- 常见误区：`URL_CHECK_ENABLE_ALERTS=false` 时应用内通知会关闭，但指标仍会上报。

## 执行链路（Execution Flow）

1. 调度器按 `interval` 执行任务。
2. 执行 HTTP 请求并收集响应数据。
3. 按状态码/超时/内容/JSON/SSL 规则判定结果。
4. 更新 Prometheus 指标（始终执行）。
5. 若启用应用内通知，则按 `alerts.yaml` 发送故障/恢复通知。

## 配置文件

- 任务配置：`conf/tasks.yaml`
- 告警配置：`conf/alerts.yaml`
- 运行时变量：`.env`（`URL_CHECK_*`）

完整字段说明见 `docs/config-reference.md`。

## 文档导航

- 部署文档：`DEPLOY.md`
- 运行模式：`docs/run-modes.md`
- 配置参考：`docs/config-reference.md`
- 指标字典：`docs/metrics.md`
- 可观测与排障：`docs/observability.md`
- 告警专项验证：`docs/ALERT_TESTING.md`

## 质量检查

```bash
python3 -m pytest -q
python3 scripts/qa/alert_regression.py
python3 scripts/qa/docs_guard.py
```
