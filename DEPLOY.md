# URL 健康检查服务部署指南

本文档聚焦部署落地与运维验证。业务服务端口统一为 `4000`，健康与指标均由该端口提供：

- 健康检查：`/health`
- 指标暴露：`/metrics`

## 部署决策

| 方案 | 必需组件 | 告警方式 | 适合人群 |
|------|----------|----------|----------|
| Standalone | `url-check` | 内置钉钉/邮件 | 不想部署 Prometheus 的团队 |
| Prometheus | `url-check` + Prometheus | PromQL/Alertmanager（可与内置并存） | 统一监控平台团队 |

## 容器部署（Docker vs Docker Compose）

`docker run` 和 `docker compose` 是两种不同交付方式：

| 方式 | 适用场景 | 特点 |
|------|----------|------|
| Docker（`docker run`） | 单实例、快速验证、脚本化控制 | 命令显式、改参数需重建容器 |
| Docker Compose（`docker compose`） | 长期运行、多服务编排、团队协作 | 配置文件化、可复用、便于版本管理 |

### A) Docker（`docker run`）详细部署

#### 1) 准备配置

```bash
cp .env.example .env
cp conf/tasks.yaml.example conf/tasks.yaml
cp conf/alerts.yaml.example conf/alerts.yaml
mkdir -p logs
```

#### 2) 构建镜像

```bash
docker build -t easonhe/url-checker:latest .
```

#### 3) 启动容器

```bash
docker run -d \
  --name url-check \
  --restart unless-stopped \
  --env-file .env \
  -p 4000:4000 \
  -v $(pwd)/conf:/home/appuser/conf:ro \
  -v $(pwd)/logs:/home/appuser/logs \
  easonhe/url-checker:latest
```

#### 4) 验证

```bash
docker ps --filter name=url-check
curl http://127.0.0.1:4000/health
curl http://127.0.0.1:4000/metrics
docker logs --since 5m url-check
```

#### 5) 常用运维命令（docker run 模式）

```bash
# 重启
docker restart url-check

# 修改配置后重建
docker rm -f url-check
docker run -d ... # 使用上面的启动命令重建

# 升级镜像
docker pull easonhe/url-checker:latest
docker rm -f url-check
docker run -d ... # 使用新镜像重建
```

### B) Docker Compose（`docker compose`）详细部署

#### 1) 准备配置

```bash
cp .env.example .env
cp conf/tasks.yaml.example conf/tasks.yaml
cp conf/alerts.yaml.example conf/alerts.yaml
mkdir -p logs
```

#### 2) 启动服务

使用仓库内 `docker-compose.yml`：

```bash
docker build -t easonhe/url-checker:latest .
docker compose up -d
```

#### 3) 验证

```bash
docker compose ps
curl http://127.0.0.1:4000/health
curl http://127.0.0.1:4000/metrics
docker compose logs --since 5m url-check
```

#### 4) 常用运维命令（compose 模式）

```bash
# 重启单服务
docker compose restart url-check

# 修改配置后重建
docker compose up -d --force-recreate url-check

# 停止/清理
docker compose down
```

#### 5) 升级镜像（compose 模式）

```bash
docker compose pull
docker compose up -d --force-recreate
```

## Kubernetes 部署

### 1) 准备 Secret

```bash
kubectl create namespace url-check
kubectl create secret generic url-check-secrets \
  --from-literal=dingding-access-token=YOUR_TOKEN \
  --from-literal=mail-receiver=ops@example.com \
  -n url-check
```

### 2) 应用清单

```bash
kubectl apply -f k8s/
kubectl get pods -n url-check -l app=url-check
```

建议以仓库真实清单为准，避免文档片段漂移：

- `k8s/deployment.yaml`
- `k8s/service.yaml`
- `k8s/ingress.yaml`

### 3) 验证

```bash
kubectl -n url-check port-forward svc/url-check 4000:4000
curl http://127.0.0.1:4000/health
curl http://127.0.0.1:4000/metrics
```

## Prometheus / Grafana（可选）

### 启动监控栈

```bash
docker compose -f monitoring/docker-compose.monitoring.yml up -d
```

### 关键配置

- Prometheus 自身服务端口为 `9090`（容器内）。
- 业务抓取目标是 `url-check:4000`，配置见 `monitoring/prometheus/prometheus.yml`。
- Grafana 数据源默认指向 `http://prometheus:9090`。

## 配置管理

运行时参数统一使用 `URL_CHECK_*` 环境变量，核心文件：

- 任务配置：`conf/tasks.yaml`
- 告警配置：`conf/alerts.yaml`
- 默认配置：`conf/config.py`

推荐策略：
- Standalone：`URL_CHECK_ENABLE_ALERTS=true`
- Prometheus 主导：`URL_CHECK_ENABLE_ALERTS=false`（仅保留指标）

## 回滚与升级

### Docker（docker run）

```bash
# 回滚到指定 tag
docker pull easonhe/url-checker:<tag>
docker rm -f url-check
docker run -d ... easonhe/url-checker:<tag>
```

### Docker Compose

```bash
docker compose pull
docker compose up -d --force-recreate
```

### Kubernetes

```bash
kubectl -n url-check rollout restart deployment/url-check
kubectl -n url-check rollout status deployment/url-check
kubectl -n url-check rollout undo deployment/url-check
```

## 常见问题

### 图表无数据

1. 确认服务存活：`curl :4000/health`
2. 确认指标可读：`curl :4000/metrics`
3. 确认 target：Prometheus `url-check` job 为 `up`
4. 查看日志：`docker logs url-check` 或 `kubectl logs`

### 告警未发送

1. 检查全局开关：`URL_CHECK_ENABLE_ALERTS`
2. 检查渠道开关：`URL_CHECK_ENABLE_DINGDING` / `URL_CHECK_ENABLE_MAIL`
3. 检查 `conf/alerts.yaml` 对应告警类型是否启用

## 相关文档

- `README.md`
- `docs/run-modes.md`
- `docs/config-reference.md`
- `docs/metrics.md`
- `docs/observability.md`
- `docs/ALERT_TESTING.md`
