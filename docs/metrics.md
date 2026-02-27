# 指标字典

业务服务统一从 `:4000/metrics` 暴露指标。

## 核心指标

| 指标名 | 类型 | 常见标签 | 单位 | 含义 |
|--------|------|----------|------|------|
| `url_check_http_status_code` | Gauge | `task_name`,`method` | code | 最近一次状态码 |
| `url_check_http_response_time_ms` | Histogram | `task_name`,`method` | ms | 响应时间分布 |
| `url_check_http_timeout_total` | Counter | `task_name`,`method` | count | 超时累计次数 |
| `url_check_content_match` | Gauge | `task_name`,`method` | 0/1 | 关键字是否匹配 |
| `url_check_json_valid` | Gauge | `task_name`,`method` | 0/1 | JSON 解析是否成功 |
| `url_check_json_path_match` | Gauge | `task_name`,`method` | 0/1 | JSON Path 是否匹配 |
| `url_check_status_code_alert` | Gauge | `task_name`,`method` | 0/1 | 状态码告警态 |
| `url_check_timeout_alert` | Gauge | `task_name`,`method` | 0/1 | 超时告警态 |
| `url_check_content_alert` | Gauge | `task_name`,`method` | 0/1 | 关键字告警态 |
| `url_check_json_path_alert` | Gauge | `task_name`,`method` | 0/1 | JSON Path 告警态 |
| `url_check_ssl_expiry_alert` | Gauge | `task_name`,`method` | 0/1 | SSL 到期告警态 |
| `url_check_delay_alert` | Gauge | `task_name`,`method` | 0/1 | 响应时间告警态 |
| `url_check_task_checks_total` | Counter | `task_name`,`method`,`result` | count | 检查总次数（success/failed） |
| `url_check_task_failures_total` | Counter | `task_name`,`method`,`reason` | count | 失败分类累计 |
| `url_check_scheduler_init_total` | Counter | `result` | count | 调度器初始化次数 |
| `url_check_scheduler_up` | Gauge | - | 0/1 | 调度器运行状态 |
| `url_check_scheduler_job_count` | Gauge | - | count | 当前任务数 |
| `url_check_config_reload_total` | Counter | `result` | count | 配置热重载结果统计 |
| `url_check_config_tasks_total` | Gauge | - | count | 当前配置任务总数 |

## 关于 `*_alert` 空样本

部分部署中，某些 `*_alert` 指标在未触发过对应告警前可能没有样本；这是“未产生时序”，不等同于异常。可在 Grafana 里做兜底（例如 `or on() vector(0)`）。

## 常用 PromQL

```promql
# 成功率（按状态码）
100 * avg(url_check_http_status_code == bool 200)

# 最近 5 分钟超时率
sum(increase(url_check_http_timeout_total[5m])) / clamp_min(count(url_check_http_status_code), 1)

# 当前失败任务数（状态码维度）
sum(url_check_http_status_code != bool 200)

# 响应时间 P95（毫秒）
histogram_quantile(0.95, sum(rate(url_check_http_response_time_ms_bucket[5m])) by (le))

# 告警健康度（你的面板公式）
100 * avg(1 - clamp_max(url_check_status_code_alert + url_check_timeout_alert, 1))

# 告警矩阵（任务 x 告警类型）
label_replace(url_check_status_code_alert, "alert_type", "status_code", "", "")
or label_replace(url_check_timeout_alert, "alert_type", "timeout", "", "")
or label_replace(url_check_content_alert, "alert_type", "content", "", "")
or label_replace(url_check_json_path_alert, "alert_type", "json_path", "", "")
or label_replace(url_check_ssl_expiry_alert, "alert_type", "ssl_expiry", "", "")
or label_replace(url_check_delay_alert, "alert_type", "delay", "", "")

# 失败原因 TopN
topk(5, sum by (reason) (increase(url_check_task_failures_total[30m])))

# 最近 10 分钟配置重载失败次数
sum(increase(url_check_config_reload_total{result!="ok"}[10m]))
```

## 快速检查命令

```bash
curl -s http://127.0.0.1:4000/metrics | rg '^url_check_'
curl -s 'http://127.0.0.1:9091/api/v1/query?query=count(url_check_http_status_code)'
```
