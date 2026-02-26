# 可观测与排障

本文档用于快速定位“服务有/无数据”的问题。

## 最短排障路径

1. 服务是否存活

```bash
curl -f http://127.0.0.1:4000/health
```

期望最少包含：
- `status=ok`
- `scheduler.initialized`
- `scheduler.running`
- `scheduler.jobs`

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
curl -s 'http://127.0.0.1:9091/api/v1/query?query=url_check_scheduler_up'
curl -s 'http://127.0.0.1:9091/api/v1/query?query=url_check_scheduler_job_count'
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

### 现象 4：配置改了但任务数量没变化

- 检查 `url_check_config_reload_total` 中 `result=ok` 是否增长。
- 检查 `url_check_config_tasks_total` 是否变化。
- 本地模式确认热重载线程是否启动，容器模式检查是否重建/重启。

### 现象 5：应用内告警一直不发送

- 检查 `.env` 中 `URL_CHECK_ENABLE_ALERTS` 是否为 `true`。
- 检查渠道开关：`URL_CHECK_ENABLE_DINGDING` / `URL_CHECK_ENABLE_MAIL`。
- 检查 `conf/alerts.yaml` 对应 `name` 是否 `enabled=true` 且包含目标 `channels`。

## 推荐看板

- 成功率：`100 * avg(url_check_http_status_code == bool 200)`
- 失败任务数：`sum(url_check_http_status_code != bool 200)`
- 超时趋势：`sum(increase(url_check_http_timeout_total[5m]))`
- 关键字失败：`sum(url_check_content_match == bool 0)`
- 调度器状态：`url_check_scheduler_up`
- 任务总数：`url_check_scheduler_job_count`

## 配置排障速查

- 字段定义与默认值：`docs/config-reference.md`
- 运行模式开关：`docs/run-modes.md`
