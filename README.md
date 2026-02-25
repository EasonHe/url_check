# URL 健康检查服务

定时检查 URL 可用性，支持 HTTP 状态码、内容匹配、JSON 结构化验证、Prometheus 指标暴露、钉钉/邮件告警。

## 功能特性

| 特性 | 说明 |
|------|------|
| HTTP 检查 | GET/POST 请求支持 |
| 状态码验证 | 期望状态码检查 |
| 关键字匹配 | 子字符串包含验证 |
| JSON 验证 | json_path 路径 + 值验证 |
| 响应时间 | 延迟阈值检查 |
| SSL 监控 | 证书过期天数监控 |
| 告警通知 | 钉钉/邮件（独立开关） |
| 配置热重载 | ConfigMap 变更自动重载 |
| Prometheus | /metrics 指标暴露 |

## 快速开始

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python3 url_check.py

# 服务地址
# - Web UI: http://127.0.0.1:4000
# - 指标: http://127.0.0.1:4000/metrics
# - 健康: http://127.0.0.1:4000/health
```

### Docker 运行

```bash
docker build -t easonhe/url-checker:latest .
docker run -d \
  --name url-check \
  -p 4000:4000 \
  -p 9090:9090 \
  -v $(pwd)/conf:/home/appuser/conf \
  easonhe/url-checker:latest
```

### Kubernetes 部署

```bash
# 应用配置
kubectl apply -f k8s/

# 查看状态
kubectl get pods -l app=url-check
kubectl logs -l app=url-check -f
```

## 配置说明

告警联调与专项验证请参考：`docs/ALERT_TESTING.md`

### 任务配置 (conf/tasks.yaml)

可直接使用示例文件 `conf/tasks.yaml.example` 作为起点。

```yaml
tasks:
  # 任务1：基础配置
  - name: 百度首页
    method: get
    url: https://www.baidu.com
    timeout: 5
    interval: 60
    threshold:
      stat_code: 200
      delay: [300, 2]
      math_str: "百度"
    ssl:
      verify: true
      warning_days: 30

  # 任务2：JSON 验证
  - name: api-health
    method: get
    url: https://api.example.com/health
    expect_json: true
    json_path: "$.status"
    json_path_value: "active"

  # 任务3：POST + 重试
  - name: submit-data
    method: post
    url: https://api.example.com/submit
    headers:
      Content-Type: application/json
    payload: '{"key": "value"}'
    timeout: 10
    retry:
      count: 3
      delay: 2
```

### 配置字段说明

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | 是 | - | 任务名称（唯一标识） |
| `method` | 是 | get | HTTP 方法（get/post） |
| `url` | 是 | - | 检查的 URL |
| `timeout` | 否 | 10 | 超时时间（秒） |
| `interval` | 否 | 10 | 检查间隔（秒） |
| `headers` | 否 | - | HTTP 请求头 |
| `cookies` | 否 | - | HTTP Cookie |
| `payload` | 否 | - | POST 请求体 |
| `proxy` | 否 | - | 代理地址 |

### 阈值配置 (threshold)

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `stat_code` | 否 | 200 | 期望状态码 |
| `delay` | 否 | - | `[最大响应时间(毫秒), 连续超次次数]` |
| `math_str` | 否 | - | 期望包含的关键字 |

### JSON 验证配置

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `expect_json` | 否 | false | 是否期望 JSON 响应 |
| `json_path` | 否 | - | JSON Path 表达式 |
| `json_path_value` | 否 | - | 期望值（字符串比较） |

JSON Path 示例：
```yaml
# 验证字段存在
json_path: "$.status"

# 验证值等于 "active"
json_path: "$.status"
json_path_value: "active"

# 验证布尔值
json_path_value: "true"
json_path_value: "false"

# 验证 null
json_path_value: "null"
```

### SSL 配置

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `ssl.verify` | 否 | true | 是否验证 SSL 证书 |
| `ssl.warning_days` | 否 | 30 | 证书过期告警阈值 |

### 重试配置

```yaml
retry:
  count: 3       # 重试次数
  delay: 2       # 重试间隔（秒）
```

### 告警配置

运行时配置统一使用 `URL_CHECK_*` 环境变量，`conf/config.py` 仅提供默认值兜底。

#### 全局开关（环境变量）

```bash
URL_CHECK_ENABLE_ALERTS=true
URL_CHECK_ENABLE_DINGDING=true
URL_CHECK_ENABLE_MAIL=false
URL_CHECK_DINGDING_ACCESS_TOKEN=REPLACE_WITH_TOKEN
URL_CHECK_MAIL_RECEIVERS=ops@example.com
```

#### 细粒度配置（新版，推荐）

可直接使用示例文件 `conf/alerts.yaml.example` 作为起点。

```yaml
# conf/alerts.yaml
alerts:
  # 状态码告警
  - name: status_code
    enabled: true
    channels: [dingding, mail]  # 通知渠道
    recover: true               # 是否发送恢复通知

  # 超时告警
  - name: timeout
    enabled: true
    channels: [dingding]
    recover: true

  # 关键字匹配告警
  - name: content_match
    enabled: true
    channels: [dingding, mail]
    recover: true

  # 响应时间告警
  - name: delay
    enabled: true
    channels: [dingding]
    recover: true
```

#### 配置字段说明

| 字段 | 说明 |
|------|------|
| `name` | 告警类型名称 |
| `enabled` | 是否启用该类型告警 |
| `channels` | 通知渠道列表：`dingding` / `mail` |
| `recover` | 是否发送恢复通知 |
| `suppress_minutes` | 故障告警抑制窗口（分钟） |

#### 工作模式

| 模式 | 配置 |
|------|------|
| Prometheus 告警 | `URL_CHECK_ENABLE_ALERTS=false` |
| 仅钉钉 | `URL_CHECK_ENABLE_ALERTS=true` + `channels: [dingding]` |
| 仅邮件 | `URL_CHECK_ENABLE_ALERTS=true` + `channels: [mail]` |
| 全部渠道 | `URL_CHECK_ENABLE_ALERTS=true` + `channels: [dingding, mail]` |

## Prometheus 指标

### 混合方案分工

| 验证类型 | 处理位置 | 说明 |
|----------|----------|------|
| 状态码 | Prometheus | 原始数据采集，PromQL 判断 |
| 响应时间 | Prometheus | 原始数据采集，PromQL 判断 |
| 关键字匹配 | 应用层 | Prometheus 难以处理大 body，应用层匹配后传结果 |
| JSON 结构化 | 应用层 | json_path + value 匹配，传结果 |

### 原始数据指标（Prometheus 判断用）

| 指标 | 类型 | 说明 |
|------|------|------|
| `url_check_http_status_code` | Gauge | HTTP 状态码（数值） |
| `url_check_http_response_time_ms` | Histogram | 响应时间（毫秒） |
| `url_check_http_contents` | Info | 响应内容（截断，仅未配置 math_str 时采集） |
| `url_check_http_timeout_total` | Counter | 超时次数 |
| `url_check_json_valid` | Gauge | JSON 解析结果 (1=valid, 0=invalid) |
| `url_check_json_path_match` | Gauge | JSON Path 匹配结果 (1=match, 0=no match) |
| `url_check_content_match` | Gauge | 关键字匹配结果 (1=match, 0=no match) |

### PromQL 判断示例

```promql
# 状态码告警（Gauge 直接判断）
url_check_http_status_code != 200

# 响应时间告警（Histogram 需要使用 >）
url_check_http_response_time_ms > 1000

# 关键字告警（应用层匹配，Prometheus 拿结果）
url_check_content_match == 0

# Prometheus 正则匹配（仅未配置 math_str 时可用）
url_check_http_contents_info{body!~".*(success|ok).*"}

# JSON 解析失败
url_check_json_valid == 0

# JSON Path 不匹配
url_check_json_path_match == 0

# 超时告警（Counter 需要使用 rate() 或 increase()）
rate(url_check_http_timeout_total[5m]) > 0
```

### PrometheusAlertmanager 告警规则示例

```yaml
groups:
  - name: url-check-alerts
    rules:
      # 状态码告警
      - alert: URLCheckStatusCodeFailed
        expr: url_check_http_status_code{task_name="api-health"} != 200
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.task_name }} 状态码异常: {{ $value }}"
          description: "期望状态码 200，实际 {{ $value }}"

      # 响应时间告警
      - alert: URLCheckSlowResponse
        expr: url_check_http_response_time_ms{task_name="api-health"} > 1000
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.task_name }} 响应时间过长"
          description: "响应时间 {{ $value }}ms，超过阈值 1000ms"

      # 超时告警
      - alert: URLCheckTimeout
        expr: rate(url_check_http_timeout_total{task_name="api-health"}[5m]) > 0
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.task_name }} 发生超时"
          description: "最近 5 分钟内发生超时"

      # JSON 解析失败
      - alert: URLCheckJSONParseFailed
        expr: url_check_json_valid{task_name="api-health"} == 0
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.task_name }} JSON 解析失败"

      # JSON Path 不匹配
      - alert: URLCheckJSONPathMismatch
        expr: url_check_json_path_match{task_name="api-health"} == 0
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.task_name }} JSON Path 验证失败"

      # 关键字匹配失败（应用层匹配，Prometheus 拿结果）
      - alert: URLCheckContentMismatch
        expr: url_check_content_match{task_name="api-health"} == 0
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.task_name }} 关键字匹配失败"
```

### 告警日志示例

应用层告警日志输出：

```
# 故障告警
【故障】api-health - 状态码
code:500, threshold:200 URL:https://api.example.com

# 恢复通知
【恢复】api-health - 状态码
code:200, threshold:200 URL:https://api.example.com

# 超时告警
【故障】api-health - 超时
timeout:1 URL:https://api.example.com

# 关键字匹配失败
【故障】api-health - 关键字
匹配字段:success, stat_math_str:1 URL:https://api.example.com

# 响应时间过长
【故障】api-health - 响应时间
响应时间:1500ms, 预设:1000ms URL:https://api.example.com
```

### 告警日志配置

告警日志独立输出到 `logs/alert_YYYY-MM-DD.log`，JSON 格式，按天保留。

#### 配置项（环境变量）

```bash
URL_CHECK_ALERT_LOG_ENABLED=true
URL_CHECK_ALERT_LOG_RETENTION_DAYS=30
```

#### 日志格式（JSON）

```json
{
  "timestamp": "2024-01-01 00:00:00",
  "level": "WARNING",
  "type": "故障",
  "task_name": "api-health",
  "alert_type": "状态码",
  "message": "【故障】api-health - 状态码 | code:500 | URL:https://..."
}
```

#### 日志文件

```
logs/
├── alert_2024-01-01.log
├── alert_2024-01-02.log
├── alert_2024-01-03.log
└── ...
```

自动清理超过 `alert_log_retention_days` 天的日志文件。

### 指标类型与判断方式

| 指标类型 | 指标示例 | 正确判断方式 |
|----------|----------|--------------|
| Gauge | `url_check_http_status_code` | `!= 200` |
| Histogram | `url_check_http_response_time_ms` | `> 1000` |
| Counter | `url_check_http_timeout_total` | `rate(...[5m]) > 0` |
| Info | `url_check_http_contents_info` | `=~".*pattern.*"`（仅未配置 math_str 时） |

### 聚合指标（兼容旧版）

| 指标 | 类型 | 说明 |
|------|------|------|
| `url_check_success_total` | Counter | 检查成功次数 |
| `url_check_timeout_total` | Counter | 超时次数 |
| `url_check_response_time_seconds` | Histogram | 响应时间分布（秒） |
| `url_check_ssl_expiry_days` | Gauge | SSL 证书剩余天数 |
| `url_check_ssl_verified` | Counter | SSL 验证状态 |

## 目录结构

```
url_check/
├── conf/
│   ├── config.py        # 告警配置（全局开关）
│   ├── alerts.yaml      # 告警配置（细粒度）
│   ├── alerts_config.py # 告警配置加载模块
│   └── tasks.yaml       # 任务配置
├── view/
│   ├── checke_control.py    # 结果处理 + 指标 + 告警
│   ├── make_check_instan.py # 任务创建 + HTTP
│   └── hot_reload.py       # 配置热重载
├── k8s/
│   ├── deployment.yaml     # K8s 部署
│   ├── service.yaml       # K8s 服务
│   ├── ingress.yaml       # K8s 入口
│   ├── kustomization.yaml
│   └── RELOADER.md       # ConfigMap 热重载说明
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── url_check.py         # Flask 应用入口
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/metrics` | GET | Prometheus 指标 |
| `/health` | GET | 健康检查 |
| `/api/tasks` | GET | 获取任务列表 |
| `/api/tasks` | POST | 添加任务 |
| `/api/tasks/<name>` | DELETE | 删除任务 |
| `/api/reload` | POST | 重载配置 |

## 更新配置

### 本地
编辑 `conf/tasks.yaml`，服务会自动重载（需启用 hot_reload.py）。

### Kubernetes
```bash
# 编辑 ConfigMap
kubectl edit configmap url-check-tasks -n url-check

# 或重新应用
kubectl apply -f k8s/deployment.yaml

# ConfigMap 变更后自动重载（需部署 Reloader）
```

## 许可证

MIT
