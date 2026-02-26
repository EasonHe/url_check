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
```

## 快速检查命令

```bash
curl -s http://127.0.0.1:4000/metrics | rg '^url_check_'
curl -s 'http://127.0.0.1:9091/api/v1/query?query=count(url_check_http_status_code)'
```
