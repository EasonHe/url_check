# 可观测与排障

本文档用于快速定位“服务有/无数据”的问题。

## 最短排障路径

1. 服务是否存活

```bash
curl -f http://127.0.0.1:4000/health
```

2. 指标是否输出

```bash
curl -f http://127.0.0.1:4000/metrics
```

3. Prometheus target 是否 `up`

```bash
curl -s http://127.0.0.1:9091/api/v1/targets?state=active
```

4. 关键时序是否存在

```bash
curl -s 'http://127.0.0.1:9091/api/v1/query?query=count(url_check_http_status_code)'
```

5. 查看应用日志

```bash
docker logs --since 10m url-check
```

## 常见现象

### 现象 1：Prometheus target `up`，Grafana 无数据

- 排查查询语句是否使用了尚未产生样本的指标（常见于 `*_alert`）。
- 先改用 `url_check_http_status_code`、`url_check_content_match` 验证链路。

### 现象 2：`*_alert` 图表空白

- 可能是未触发过告警，指标没有样本。
- 也可能是任务执行中途异常，未走到告警态指标更新。

### 现象 3：指标突然中断

- 检查容器是否重启/不健康。
- 检查 `conf/tasks.yaml` 解析错误。
- 检查网络（Prometheus 是否能访问 `url-check:4000`）。

## 推荐看板

- 成功率：`100 * avg(url_check_http_status_code == bool 200)`
- 失败任务数：`sum(url_check_http_status_code != bool 200)`
- 超时趋势：`sum(increase(url_check_http_timeout_total[5m]))`
- 关键字失败：`sum(url_check_content_match == bool 0)`
