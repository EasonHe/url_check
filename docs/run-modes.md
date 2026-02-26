# 运行模式说明

本项目支持两种运行模式，Prometheus 是可选项。

## 模式对比

| 维度 | Standalone | Prometheus |
|------|------------|------------|
| 必需组件 | `url-check` | `url-check` + Prometheus（可选 Grafana） |
| 告警来源 | 应用内通知（钉钉/邮件） | PromQL + Alertmanager（可与应用内并存） |
| 运维复杂度 | 低 | 中 |
| 适用场景 | 小规模、快速上线 | 平台化、统一监控 |

## Standalone 推荐配置

```bash
URL_CHECK_ENABLE_ALERTS=true
URL_CHECK_ENABLE_DINGDING=true
URL_CHECK_ENABLE_MAIL=false
URL_CHECK_DINGDING_ACCESS_TOKEN=REPLACE_ME
URL_CHECK_MAIL_RECEIVERS=ops@example.com
```

适合：希望快速落地，不额外维护 Prometheus/Alertmanager。

## Prometheus 推荐配置

```bash
# 保留指标，告警交给 Prometheus/Alertmanager
URL_CHECK_ENABLE_ALERTS=false
URL_CHECK_ENABLE_DINGDING=false
URL_CHECK_ENABLE_MAIL=false
```

适合：告警统一由 Prometheus/Alertmanager 管理，应用仅上报指标。

## 启动方式

### Standalone

```bash
docker compose up -d
```

### Prometheus

```bash
docker compose up -d
docker compose -f monitoring/docker-compose.monitoring.yml up -d
```

## 验证

```bash
curl http://127.0.0.1:4000/health
curl http://127.0.0.1:4000/metrics
```

更多字段说明见 `docs/config-reference.md`。
