# 配置参考（Config Reference）

本文档是 `url-check` 配置字段的权威说明，覆盖：
- `conf/tasks.yaml`
- `conf/alerts.yaml`
- `.env`（`URL_CHECK_*`）

## 1. tasks.yaml

顶层结构：

```yaml
tasks:
  - name: example-task
    method: get
    url: https://example.com/health
```

### 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 任务唯一标识，建议英文短横线 |
| `method` | string | 是 | `get` | `get` 或 `post` |
| `url` | string | 是 | - | 被检查 URL |
| `timeout` | int | 否 | `10` | 请求超时时间（秒） |
| `interval` | int | 否 | `10` | 调度间隔（秒） |
| `headers` | map | 否 | `{}` | 请求头 |
| `cookies` | map | 否 | `{}` | Cookie |
| `payload` | string/map | 否 | - | POST 请求体 |
| `proxy` | string | 否 | - | 代理地址，支持 `__HOST__` |
| `max_response_size` | int | 否 | - | 响应体最大字节数 |
| `threshold.stat_code` | int | 否 | `200` | 期望状态码 |
| `threshold.delay` | int | 否 | - | 响应时间上限（毫秒） |
| `threshold.math_str` | string | 否 | - | 内容关键字匹配 |
| `expect_json` | bool | 否 | `false` | 是否要求响应可解析为 JSON |
| `json_path` | string | 否 | - | JSON Path 表达式 |
| `json_path_value` | string | 否 | - | JSON Path 期望值（字符串比较） |
| `ssl.verify` | bool | 否 | `true` | 是否校验证书 |
| `ssl.warning_days` | int | 否 | `30` | 证书到期预警天数 |
| `retry.count` | int | 否 | `0` | 重试次数 |
| `retry.delay` | int | 否 | `1` | 重试间隔（秒） |

### 生效条件与注意事项

- `json_path` / `json_path_value` 仅在 `expect_json=true` 时有意义。
- `threshold.delay` 单位是毫秒（ms），不是秒。
- `proxy` 在容器中可写 `http://__HOST__:7890`，程序会替换为宿主机地址。
- `ssl.verify=false` 时不会进行证书有效性判定。

### 最小可用模板（Minimal）

```yaml
tasks:
  - name: minimal-health
    method: get
    url: https://httpbin.org/get
    timeout: 10
    interval: 60
    threshold:
      stat_code: 200
```

### 生产推荐模板（Production）

```yaml
tasks:
  - name: production-api
    method: get
    url: https://api.example.com/health
    timeout: 8
    interval: 60
    threshold:
      stat_code: 200
      delay: 800
      math_str: "ok"
    expect_json: true
    json_path: "$.status"
    json_path_value: "active"
    ssl:
      verify: true
      warning_days: 30
    retry:
      count: 2
      delay: 1
```

### 联调模板（Debug）

```yaml
tasks:
  - name: debug-json-alert
    method: get
    url: https://httpbin.org/json
    timeout: 10
    interval: 30
    threshold:
      stat_code: 200
    expect_json: true
    json_path: "$.slideshow.author"
    json_path_value: "WRONG_VALUE"
```

## 2. alerts.yaml

顶层结构：

```yaml
alerts:
  - name: status_code
    enabled: true
    channels: [dingding]
    recover: true
    suppress_minutes: 5
```

### 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 告警类型：`status_code` / `timeout` / `content_match` / `json_path` / `delay` / `ssl_expiry` |
| `enabled` | bool | 否 | `true` | 是否启用该告警类型 |
| `channels` | list | 否 | `[]` | 通知渠道：`dingding`、`mail` |
| `recover` | bool | 否 | `true` | 是否发送恢复通知 |
| `suppress_minutes` | int | 否 | `0` | 故障告警抑制窗口 |

### 行为说明

- `enabled=false`：该类型不会发送应用内通知，但相关指标仍会更新。
- `recover=true`：故障恢复后发送恢复通知。
- `suppress_minutes>0`：抑制窗口内重复故障通知会被合并。

## 3. .env（URL_CHECK_*）

### 核心开关

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `URL_CHECK_ENABLE_ALERTS` | `true` | 应用内告警总开关 |
| `URL_CHECK_ENABLE_DINGDING` | `true` | 钉钉渠道开关 |
| `URL_CHECK_ENABLE_MAIL` | `false` | 邮件渠道开关 |
| `URL_CHECK_PORT` | `4000` | 服务监听端口 |

### 钉钉与邮件

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `URL_CHECK_DINGDING_WEBHOOK` | 官方地址 | 钉钉 webhook 前缀 |
| `URL_CHECK_DINGDING_ACCESS_TOKEN` | 空 | 钉钉 token |
| `URL_CHECK_MAIL_RECEIVERS` | `ops@example.com` | 收件人（逗号分隔） |

### 报告与日志

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `URL_CHECK_REPORT_ENABLED` | `true` | 周期汇总报告开关 |
| `URL_CHECK_REPORT_INTERVAL_HOURS` | `2` | 报告间隔（小时） |
| `URL_CHECK_ALERT_LOG_ENABLED` | `true` | 告警日志开关 |
| `URL_CHECK_ALERT_LOG_RETENTION_DAYS` | `30` | 日志保留天数 |

### 运行模式推荐

#### Standalone

```bash
URL_CHECK_ENABLE_ALERTS=true
URL_CHECK_ENABLE_DINGDING=true
URL_CHECK_ENABLE_MAIL=false
```

#### Prometheus 主导

```bash
URL_CHECK_ENABLE_ALERTS=false
URL_CHECK_ENABLE_DINGDING=false
URL_CHECK_ENABLE_MAIL=false
```

## 4. 修改后验证

```bash
curl -f http://127.0.0.1:4000/health
curl -f http://127.0.0.1:4000/metrics
python3 scripts/qa/docs_guard.py
```
