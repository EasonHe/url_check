# URL 健康检查服务

定时检查 URL 可用性，支持状态码、响应时间、关键字、JSON Path、SSL 检查，并可选发送钉钉/邮件告警。

## 运行模式

本项目支持两种模式，Prometheus 不是必需依赖。

| 模式 | 依赖 | 告警路径 | 适用场景 |
|------|------|----------|----------|
| Standalone（默认） | 仅 `url-check` | 应用内钉钉/邮件 | 轻量部署、快速落地 |
| Prometheus | `url-check` + Prometheus（可选 Grafana） | PromQL/Alertmanager 或应用内并存 | 统一可观测体系 |

详细说明见 `docs/run-modes.md`。

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

说明：
- 业务与指标统一暴露在 `4000` 端口。
- 指标地址为 `http://<host>:4000/metrics`。

## 快速启动（本地开发）

```bash
cp .env.example .env.local
./dev.sh check
./dev.sh up
./dev.sh test
./dev.sh down
```

## Prometheus 模式（可选）

你可以在 Standalone 跑通后，再按需接入监控栈：

```bash
docker compose -f monitoring/docker-compose.monitoring.yml up -d
```

推荐 Prometheus 抓取配置：
- `monitoring/prometheus/prometheus.yml` 中 `url-check` target 指向 `url-check:4000`（容器互联场景）。

## 常用地址

- 服务健康：`http://127.0.0.1:4000/health`
- 指标暴露：`http://127.0.0.1:4000/metrics`
- 任务管理：`POST /job/opt`

## 配置入口

- 任务：`conf/tasks.yaml`
- 告警类型：`conf/alerts.yaml`
- 运行时变量：`.env`（`URL_CHECK_*`）

## 文档导航

- 部署文档：`DEPLOY.md`
- 运行模式：`docs/run-modes.md`
- 指标字典：`docs/metrics.md`
- 可观测与排障：`docs/observability.md`
- 告警专项验证：`docs/ALERT_TESTING.md`

## 质量检查

```bash
python3 -m pytest -q
python3 scripts/qa/alert_regression.py
python3 scripts/qa/docs_guard.py
```
