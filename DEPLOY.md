# URL 健康检查服务 - 部署文档

## 目录

- [概述](#概述)
- [Docker 部署](#docker-部署)
- [Kubernetes 部署](#kubernetes-部署)
- [配置说明](#配置说明)
- [验证部署](#验证部署)
- [故障排查](#故障排查)
- [更新与回滚](#更新与回滚)

---

## 概述

URL 健康检查服务是一个定时检查 URL 可用性的监控系统，支持：

| 功能 | 说明 |
|------|------|
| HTTP 检查 | GET/POST 请求支持 |
| 状态码验证 | 期望状态码检查 |
| 关键字匹配 | 子字符串包含验证 |
| JSON 验证 | JSON Path 路径 + 值验证 |
| 响应时间 | 延迟阈值检查 |
| SSL 监控 | 证书过期天数监控 |
| 告警通知 | 钉钉/邮件独立开关 |
| 配置热重载 | ConfigMap 变更自动重载 |
| Prometheus | /metrics 指标暴露 |

### 本地开发统一入口

```bash
cp .env.example .env.local
./dev.sh check
./dev.sh up
./dev.sh test
./dev.sh down
```

---

## Docker 部署

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+（可选）

### 快速开始

#### 1. 构建镜像

```bash
cd /path/to/url_check

# 构建镜像
docker build -t easonhe/url-checker:latest .
```

#### 2. 准备配置文件

```bash
# 创建目录
mkdir -p conf logs

# 复制配置模板
cp conf/tasks.yaml.example conf/tasks.yaml
cp conf/alerts.yaml.example conf/alerts.yaml
cp .env.example .env
```

#### 3. 编辑配置

> **提示**: 项目提供了完整的配置模板，可直接复制使用：
> - `conf/tasks.yaml.example` - 任务配置模板（10 种场景示例）
> - `conf/alerts.yaml.example` - 告警配置模板
> - `.env.example` - 运行时环境变量模板

```bash
# 复制配置模板
cp conf/tasks.yaml.example conf/tasks.yaml
cp conf/alerts.yaml.example conf/alerts.yaml
cp .env.example .env
```

编辑 `.env`（至少填写钉钉 token）：

```bash
URL_CHECK_DINGDING_ACCESS_TOKEN=YOUR_DINGDING_ACCESS_TOKEN
URL_CHECK_ENABLE_ALERTS=true
URL_CHECK_ENABLE_DINGDING=true
URL_CHECK_ENABLE_MAIL=false
URL_CHECK_MAIL_RECEIVERS=ops@example.com
```

编辑 `conf/tasks.yaml`（完整示例见 `conf/tasks.yaml.example`）：

```yaml
tasks:
  # 任务1：基础 HTTP 检查（百度首页）
  - name: baidu-home
    method: get
    url: https://www.baidu.com
    timeout: 5
    interval: 60
    threshold:
      stat_code: 200
      delay: 300
      math_str: "百度"
    ssl:
      verify: true
      warning_days: 30

  # 任务2：JSON API 验证
  - name: api-health
    method: get
    url: https://api.example.com/health
    timeout: 10
    interval: 30
    threshold:
      stat_code: 200
    expect_json: true
    json_path: "$.status"
    json_path_value: "active"
    ssl:
      verify: true
      warning_days: 30
```

> 说明：无需手工修改 `conf/config.py`，运行时统一通过 `.env` / 环境变量注入配置。

编辑 `conf/alerts.yaml`（完整示例见 `conf/alerts.yaml.example`）：

```yaml
alerts:
  - name: status_code
    enabled: true
    channels: [dingding, mail]
    recover: true

  - name: timeout
    enabled: true
    channels: [dingding]
    recover: true

  - name: content_match
    enabled: true
    channels: [dingding, mail]
    recover: true
```

#### 4. 运行容器

**方式一：直接运行**

```bash
docker run -d \
  --name url-check \
  --env-file .env \
  -p 4000:4000 \
  -p 9090:9090 \
  -v $(pwd)/conf:/home/appuser/conf \
  -v $(pwd)/logs:/home/appuser/logs \
  -e TZ=Asia/Shanghai \
  easonhe/url-checker:latest
```

**方式二：Docker Compose（推荐）**

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  url-check:
    image: easonhe/url-checker:latest
    container_name: url-check
    restart: unless-stopped
    ports:
      - "4000:4000"
      - "9090:9090"
    volumes:
      - ./conf:/home/appuser/conf:ro
      - ./logs:/home/appuser/logs
    env_file:
      - .env
    environment:
      - TZ=Asia/Shanghai
      - URL_CHECK_ENABLE_ALERTS=true
      - URL_CHECK_ENABLE_DINGDING=true
      - URL_CHECK_ENABLE_MAIL=false
      - URL_CHECK_REPORT_ENABLED=true
      - URL_CHECK_REPORT_INTERVAL_HOURS=2
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:4000/health', timeout=2)"]
      interval: 30s
      timeout: 3s
      start_period: 10s
      retries: 3
```

启动：

```bash
docker-compose up -d
docker-compose logs -f
```

**方式三：使用预构建镜像**

```bash
# 拉取镜像
docker pull easonhe/url-checker:latest

# 运行
docker run -d \
  --name url-check \
  -p 4000:4000 \
  -p 9090:9090 \
  -v $(pwd)/conf:/home/appuser/conf \
  easonhe/url-checker:latest
```

---

## Kubernetes 部署

### 环境要求

- Kubernetes 1.20+
- kubectl 配置完成
- 镜像仓库访问权限

### 步骤 1：推送镜像到仓库

```bash
# 构建镜像
cd /path/to/url_check
docker build -t easonhe/url-checker:latest .

# 登录镜像仓库
docker login 192.168.8.8:9000

# 推送镜像
docker push easonhe/url-checker:latest
```

### 步骤 2：创建命名空间

```bash
kubectl create namespace url-check
```

### 步骤 3：创建 Secret

```bash
# 创建 Secret 存储敏感配置
kubectl create secret generic url-check-secrets \
  --from-literal=dingding-access-token=YOUR_DINGDING_ACCESS_TOKEN \
  --from-literal=mail-receiver=admin@example.com \
  -n url-check

# 验证
kubectl get secret url-check-secrets -n url-check
```

### 步骤 4：部署到 K8s

```bash
# 应用所有配置
kubectl apply -f k8s/deployment.yaml -n url-check

# 或分步应用
kubectl apply -f k8s/deployment.yaml -n url-check
kubectl apply -f k8s/service.yaml -n url-check
kubectl apply -f k8s/ingress.yaml -n url-check
```

### 步骤 5：验证部署

```bash
# 查看 Pod 状态
kubectl get pods -n url-check -l app=url-check

# 查看 Pod 详情
kubectl describe pod -n url-check -l app=url-check

# 查看日志
kubectl logs -n url-check -l app=url-check -f
```

### 步骤 6：配置热重载（可选）

部署 ConfigMap Reloader 实现配置自动重载：

```bash
# 安装 Reloader
helm repo add stakater https://stakater.github.io/stakater-charts
helm install stakater-reloader stakater/reloader -n reloader --create-namespace
```

### 配置文件说明

K8s 部署包含以下 ConfigMap：

| ConfigMap | 说明 | 挂载位置 |
|-----------|------|----------|
| url-check-tasks | 任务配置 | `/home/appuser/conf/tasks.yaml` |
| url-check-alerts | 告警规则 | `/home/appuser/conf/alerts.yaml` |
| url-check-config | 应用配置 | `/home/appuser/conf/config.py` |

---

## 配置说明

### 任务配置 (conf/tasks.yaml)

```yaml
tasks:
  # 任务1：基础 HTTP 检查
  - name: 百度首页
    method: get
    url: https://www.baidu.com
    timeout: 5
    interval: 60
    threshold:
      stat_code: 200
      delay: 300
      math_str: "百度"
    ssl:
      verify: true
      warning_days: 30

  # 任务2：JSON API 验证
  - name: api-health
    method: get
    url: https://api.example.com/health
    timeout: 10
    interval: 30
    threshold:
      stat_code: 200
    expect_json: true
    json_path: "$.status"
    json_path_value: "active"
    ssl:
      verify: true
      warning_days: 30

  # 任务3：POST 请求 + 重试
  - name: submit-data
    method: post
    url: https://api.example.com/submit
    headers:
      Content-Type: application/json
    payload: '{"key": "value"}'
    timeout: 10
    interval: 60
    retry:
      count: 3
      delay: 2
    ssl:
      verify: true
      warning_days: 30
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

### 代理使用说明

```yaml
# 本机开发（代理监听 127.0.0.1:7890）
proxy: http://127.0.0.1:7890

# 容器内运行（访问宿主机代理）
proxy: http://__HOST__:7890
```

说明：
- `proxy` 会同时应用到 HTTP 和 HTTPS。
- `__HOST__` 会在运行时替换为 `host.docker.internal`，方便容器访问宿主机代理。

### 阈值配置 (threshold)

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `stat_code` | 否 | 200 | 期望状态码 |
| `delay` | 否 | - | 最大响应时间阈值(毫秒) |
| `math_str` | 否 | - | 期望包含的关键字 |

### JSON 验证配置

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `expect_json` | 否 | false | 是否期望 JSON 响应 |
| `json_path` | 否 | - | JSON Path 表达式 |
| `json_path_value` | 否 | - | 期望值（字符串比较） |

### SSL 配置

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `ssl.verify` | 否 | true | 是否验证 SSL 证书 |
| `ssl.warning_days` | 否 | 30 | 证书过期告警阈值 |

### 告警配置 (conf/alerts.yaml)

```yaml
alerts:
  - name: status_code
    enabled: true
    channels: [dingding, mail]
    recover: true

  - name: timeout
    enabled: true
    channels: [dingding]
    recover: true

  - name: content_match
    enabled: true
    channels: [dingding, mail]
    recover: true
    suppress_minutes: 5

  - name: json_path
    enabled: true
    channels: [dingding, mail]
    recover: true
    suppress_minutes: 5

  - name: delay
    enabled: true
    channels: [dingding]
    recover: true
    suppress_minutes: 5

  - name: ssl_expiry
    enabled: true
    channels: [dingding]
    recover: true
    suppress_minutes: 5
```

### 应用配置 (conf/config.py)

```python
# Flask 配置
host = "0.0.0.0"
port = 4000
metrics_port = 9090

# 任务配置
tasks_yaml = "/home/appuser/conf/tasks.yaml"

# 告警配置
enable_alerts = True
enable_dingding = True
enable_mail = False
dingding_url = "https://oapi.dingtalk.com/robot/send?"
access_token = "${URL_CHECK_DINGDING_ACCESS_TOKEN}"
send_to = ["${URL_CHECK_MAIL_RECEIVERS}"]

# 告警日志配置
alert_log_enabled = True
alert_log_retention_days = 30
```

### 环境变量配置

| 配置项 | Docker 环境变量 | K8s Secret | 说明 |
|--------|-----------------|------------|------|
| 钉钉 Access Token | `URL_CHECK_DINGDING_ACCESS_TOKEN` | `dingding-access-token` | 钉钉机器人 access_token |
| 告警收件人 | `URL_CHECK_MAIL_RECEIVERS` | `mail-receiver` | 逗号分隔邮箱 |
| 告警总开关 | `URL_CHECK_ENABLE_ALERTS` | - | true/false |
| 钉钉开关 | `URL_CHECK_ENABLE_DINGDING` | - | true/false |
| 邮件开关 | `URL_CHECK_ENABLE_MAIL` | - | true/false |

---

## 完整配置示例

### 任务配置示例 (conf/tasks.yaml.example)

> 包含 10 种常见场景的完整配置，可直接复制使用。

```yaml
tasks:
  # =====================================================
  # 任务1：基础 HTTP 检查（百度首页）
  # =====================================================
  - name: baidu-home
    method: get
    url: https://www.baidu.com
    timeout: 5
    interval: 60
    threshold:
      stat_code: 200
      delay: 300
      math_str: "百度"
    max_response_size: 1048576
    ssl:
      verify: true
      warning_days: 30

  # =====================================================
  # 任务2：JSON API 验证（健康检查接口）
  # =====================================================
  - name: api-health
    method: get
    url: https://api.example.com/health
    timeout: 10
    interval: 30
    threshold:
      stat_code: 200
      delay: 500
    expect_json: true
    json_path: "$.status"
    json_path_value: "active"
    ssl:
      verify: true
      warning_days: 30

  # =====================================================
  # 任务3：POST 请求 + 重试机制
  # =====================================================
  - name: submit-order
    method: post
    url: https://api.example.com/orders
    headers:
      Content-Type: application/json
      Authorization: "Bearer YOUR_TOKEN"
    payload: '{"action": "query"}'
    timeout: 10
    interval: 60
    retry:
      count: 3
      delay: 2
    threshold:
      stat_code: 200
      delay: 1000
    ssl:
      verify: true
      warning_days: 30

  # =====================================================
  # 任务4：带代理的请求
  # =====================================================
  - name: proxy-check-google
    method: get
    url: https://www.google.com
    timeout: 10
    interval: 300
    threshold:
      stat_code: 200
      delay: 2000
    proxy: http://__HOST__:7890
    ssl:
      verify: true
      warning_days: 30

  # =====================================================
  # 任务5：内网服务（跳过 SSL 验证）
  # =====================================================
  - name: internal-service
    method: get
    url: https://internal.company.com/api/health
    timeout: 10
    interval: 60
    threshold:
      stat_code: 200
      delay: 1000
    ssl:
      verify: false
      warning_days: 0

  # =====================================================
  # 任务6：同时验证 JSON 和关键字
  # =====================================================
  - name: json-with-keyword
    method: get
    url: https://jsonplaceholder.typicode.com/todos/1
    timeout: 10
    interval: 30
    threshold:
      stat_code: 200
      math_str: "delectus"
    expect_json: true
    json_path: "$.completed"
    json_path_value: "false"
    ssl:
      verify: true
      warning_days: 30

  # =====================================================
  # 任务7：RESTful API（带 Path 参数）
  # =====================================================
  - name: user-info
    method: get
    url: https://api.example.com/users/123
    headers:
      Accept: application/json
    timeout: 10
    interval: 60
    threshold:
      stat_code: 200
      delay: 500
    expect_json: true
    json_path: "$.id"
    json_path_value: "123"
    ssl:
      verify: true
      warning_days: 30

  # =====================================================
  # 任务8：表单提交
  # =====================================================
  - name: login-check
    method: post
    url: https://portal.example.com/login
    headers:
      Content-Type: application/x-www-form-urlencoded
    payload: "username=admin&password=admin123"
    timeout: 10
    interval: 120
    threshold:
      stat_code: 200
      delay: 1000
      math_str: "success"
    ssl:
      verify: true
      warning_days: 30

  # =====================================================
  # 任务9：SSL 证书监控
  # =====================================================
  - name: ssl-monitor
    method: get
    url: https://www.example.com
    timeout: 10
    interval: 3600
    threshold:
      stat_code: 200
      delay: 3000
    ssl:
      verify: true
      warning_days: 14
```

### 告警配置示例 (conf/alerts.yaml.example)

```yaml
alerts:
  # 状态码告警
  - name: status_code
    enabled: true
    channels: [dingding, mail]
    recover: true

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

  # JSON 路径匹配告警
  - name: json_path
    enabled: true
    channels: [dingding, mail]
    recover: true
    suppress_minutes: 5

  # 响应时间告警
  - name: delay
    enabled: true
    channels: [dingding]
    recover: true
```

### 应用配置示例 (conf/config.py.example)

```python
# Flask 配置
host = "0.0.0.0"
port = 4000
metrics_port = 9090

# 任务配置
tasks_yaml = "/home/appuser/conf/tasks.yaml"

# 告警配置
enable_alerts = True
enable_dingding = True
enable_mail = False

# 钉钉配置
dingding_url = "https://oapi.dingtalk.com/robot/send?"
access_token = "YOUR_DINGDING_ACCESS_TOKEN"

# 邮件配置
send_to = ["admin@example.com"]

# 告警日志配置
alert_log_enabled = True
alert_log_retention_days = 30
```

### Docker Compose 完整示例 (docker-compose.yml)

```yaml
version: '3.8'

services:
  url-check:
    image: easonhe/url-checker:latest
    container_name: url-check
    restart: unless-stopped
    ports:
      - "4000:4000"
      - "9090:9090"
    volumes:
      - ./conf:/home/appuser/conf:ro
      - ./logs:/home/appuser/logs
    environment:
      - TZ=Asia/Shanghai
      - URL_CHECK_DINGDING_ACCESS_TOKEN=YOUR_DINGDING_ACCESS_TOKEN
      - URL_CHECK_MAIL_RECEIVERS=admin@example.com
      - URL_CHECK_ENABLE_ALERTS=true
      - URL_CHECK_ENABLE_DINGDING=true
      - URL_CHECK_ENABLE_MAIL=false
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4000/health"]
      interval: 30s
      timeout: 3s
      start_period: 10s
      retries: 3
    resources:
      limits:
        memory: 128Mi
        cpu: 200m
      requests:
        memory: 64Mi
        cpu: 50m
```

### K8s Secret 示例

```bash
# 创建 Secret
kubectl create secret generic url-check-secrets \
  --from-literal=dingding-access-token=YOUR_DINGDING_ACCESS_TOKEN \
  --from-literal=mail-receiver=admin@example.com \
  -n url-check
```

### K8s ConfigMap 完整示例 (k8s/deployment.yaml)

> 以下是完整的 K8s 部署配置，包含所有 ConfigMap：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: url-check
  labels:
    app: url-check
  annotations:
    configmap.reloader.stakater.com/reload: "url-check-tasks"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: url-check
  template:
    metadata:
      labels:
        app: url-check
      annotations:
        configmap.reloader.stakater.com/reload: "url-check-tasks"
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      containers:
        - name: url-check
          image: easonhe/url-checker:latest
          imagePullPolicy: Always
          ports:
            - containerPort: 4000
              name: http
            - containerPort: 9090
              name: metrics
          env:
            - name: FLASK_ENV
              value: "production"
            - name: URL_CHECK_DINGDING_ACCESS_TOKEN
              valueFrom:
                secretKeyRef:
                  name: url-check-secrets
                  key: dingding-access-token
            - name: URL_CHECK_MAIL_RECEIVERS
              valueFrom:
                secretKeyRef:
                  name: url-check-secrets
                  key: mail-receiver
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "128Mi"
              cpu: "200m"
          livenessProbe:
            httpGet:
              path: /health
              port: 4000
            initialDelaySeconds: 10
            periodSeconds: 30
            timeoutSeconds: 3
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 4000
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          volumeMounts:
            - name: tasks-volume
              mountPath: /home/appuser/conf
              readOnly: true
            - name: alerts-volume
              mountPath: /home/appuser/conf/alerts.yaml
              readOnly: true
              subPath: alerts.yaml
            - name: config-volume
              mountPath: /home/appuser/conf/config.py
              readOnly: true
              subPath: config.py
      volumes:
        - name: tasks-volume
          configMap:
            name: url-check-tasks
        - name: alerts-volume
          configMap:
            name: url-check-alerts
            items:
              - key: alerts.yaml
                path: alerts.yaml
        - name: config-volume
          configMap:
            name: url-check-config
            items:
              - key: config.py
                path: config.py
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: url-check-tasks
data:
  tasks.yaml: |
    tasks:
      - name: baidu-home
        method: get
        url: https://www.baidu.com
        timeout: 5
        interval: 60
        threshold:
          stat_code: 200
          delay: 300
          math_str: "百度"
        ssl:
          verify: true
          warning_days: 30
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: url-check-alerts
data:
  alerts.yaml: |
    alerts:
      - name: status_code
        enabled: true
        channels: [dingding, mail]
        recover: true
      - name: timeout
        enabled: true
        channels: [dingding]
        recover: true
      - name: content_match
        enabled: true
        channels: [dingding, mail]
        recover: true
      - name: json_path
        enabled: true
        channels: [dingding, mail]
        recover: true
      - name: delay
        enabled: true
        channels: [dingding]
        recover: true
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: url-check-config
data:
  config.py: |
    host = "0.0.0.0"
    port = 4000
    metrics_port = 9090
    tasks_yaml = "/home/appuser/conf/tasks.yaml"
    enable_alerts = True
    enable_dingding = True
    enable_mail = False
    dingding_url = "https://oapi.dingtalk.com/robot/send?"
    access_token = "${URL_CHECK_DINGDING_ACCESS_TOKEN}"
    send_to = ["${URL_CHECK_MAIL_RECEIVERS}"]
    alert_log_enabled = True
    alert_log_retention_days = 30
---
apiVersion: v1
kind: Service
metadata:
  name: url-check
  labels:
    app: url-check
spec:
  type: ClusterIP
  ports:
    - port: 4000
      targetPort: 4000
      name: http
    - port: 9090
      targetPort: 9090
      name: metrics
  selector:
    app: url-check
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: url-check
  labels:
    app: url-check
spec:
  rules:
    - host: url-check.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: url-check
                port:
                  number: 4000
```

### Docker 验证

```bash
# 检查容器状态
docker ps | grep url-check

# 健康检查
curl http://localhost:4000/health
# 期望输出: OK

# 查看指标
curl http://localhost:4000/metrics

# 查看日志
docker logs url-check
```

### Kubernetes 验证

```bash
# 查看 Pod 状态
kubectl get pods -n url-check -l app=url-check
# 期望: Running

# 健康检查
kubectl exec -n url-check -it $(kubectl get pod -n url-check -l app=url-check -o jsonpath='{.items[0].metadata.name}') -- curl -f http://localhost:4000/health

# 端口转发（本地测试）
kubectl port-forward -n url-check svc/url-check 4000:4000 9090:9090

# 访问服务
curl http://localhost:4000/health
curl http://localhost:4000/metrics
```

### Prometheus 指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `url_check_http_status_code` | Gauge | HTTP 状态码 |
| `url_check_http_response_time_ms` | Histogram | 响应时间（毫秒） |
| `url_check_http_contents` | Info | 响应内容 |
| `url_check_http_timeout_total` | Counter | 超时次数 |
| `url_check_json_valid` | Gauge | JSON 解析结果 |
| `url_check_json_path_match` | Gauge | JSON Path 匹配结果 |
| `url_check_content_match` | Gauge | 关键字匹配结果 |

### PromQL 示例

```promql
# 状态码告警
url_check_http_status_code != 200

# 响应时间告警
url_check_http_response_time_ms > 1000

# 关键字告警
url_check_content_match == 0

# 超时告警
rate(url_check_http_timeout_total[5m]) > 0
```

---

## 故障排查

### Docker 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 容器启动失败 | 配置文件缺失 | 检查 `conf/` 目录是否挂载正确 |
| 无法访问服务 | 端口未映射 | 检查 `-p` 参数是否正确 |
| 告警不发 | 钉钉/邮件配置错误 | 检查环境变量或 Secret |
| 配置不生效 | 配置文件格式错误 | 检查 YAML 语法 |

### Kubernetes 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Pod CrashLoopBackOff | 配置错误 | `kubectl describe pod` 查看事件 |
| ImagePullBackOff | 镜像地址错误 | 检查镜像仓库地址和权限 |
| ConfigMap 不生效 | Pod 未重启 | `kubectl rollout restart deployment url-check` |
| 无法访问服务 | Service/Ingress 配置错误 | 检查 Service 和 Ingress 配置 |

### 排查命令

**Docker**

```bash
# 查看容器日志
docker logs -f url-check

# 进入容器调试
docker exec -it url-check /bin/bash

# 检查配置文件
docker exec url-check cat /home/appuser/conf/tasks.yaml
```

**Kubernetes**

```bash
# 查看 Pod 状态和事件
kubectl describe pod -n url-check -l app=url-check

# 查看最近事件
kubectl get events -n url-check --sort-by='.lastTimestamp'

# 查看 Pod 日志
kubectl logs -n url-check -l app=url-check --tail=100

# 检查 ConfigMap
kubectl get configmap -n url-check
kubectl describe configmap url-check-tasks -n url-check

# 端口转发测试
kubectl port-forward -n url-check svc/url-check 4000:4000
```

### 日志查看

```bash
# Docker
docker logs -f url-check

# K8s
kubectl logs -n url-check -l app=url-check -f

# 查看历史日志（K8s）
kubectl logs -n url-check -l app=url-check --previous
```

### 性能问题排查

```bash
# 查看资源使用（Docker）
docker stats url-check

# 查看资源使用（K8s）
kubectl top pod -n url-check -l app=url-check

# 查看连接数
docker exec url-check netstat -ant | wc -l
```

---

## 更新与回滚

### Docker 更新

```bash
# 重新构建
docker build -t easonhe/url-checker:latest .

# 停止并删除旧容器
docker stop url-check
docker rm url-check

# 启动新容器
docker run -d ... easonhe/url-checker:latest
```

### Docker Compose 更新

```bash
docker-compose down
docker-compose build
docker-compose up -d
```

### Kubernetes 更新

**方式1：更新镜像版本**

```bash
kubectl set image deployment/url-check \
  url-check=easonhe/url-checker:latest \
  -n url-check
```

**方式2：重新应用 ConfigMap 后重启**

```bash
# 更新 ConfigMap
kubectl apply -f k8s/deployment.yaml

# 重启 Pod
kubectl rollout restart deployment/url-check -n url-check

# 查看更新进度
kubectl rollout status deployment/url-check -n url-check
```

### 回滚

```bash
# 查看历史版本
kubectl rollout history deployment/url-check -n url-check

# 回滚到上一版本
kubectl rollout undo deployment/url-check -n url-check

# 回滚到指定版本
kubectl rollout undo deployment/url-check --to-revision=2 -n url-check
```

### 零停机更新（推荐）

使用 K8s 的滚动更新策略，deployment.yaml 中已配置：

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

---

## Prometheus 监控配置

### prometheus.yml

```yaml
scrape_configs:
  - job_name: 'url-check'
    kubernetes_sd_configs:
      - namespace: url-check
        labels:
          prometheus.io/scrape: "true"
    metrics_path: /metrics
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        target_label: __metrics_path__
```

### Grafana Dashboard 指标

```
# 状态码分布
url_check_http_status_code

# 响应时间分布
url_check_http_response_time_ms

# 检查成功率
rate(url_check_success_total[5m])

# 超时次数
rate(url_check_http_timeout_total[5m])
```

---

## 最佳实践

1. **配置管理**
   - 使用 Secret 存储敏感信息
   - ConfigMap 与镜像分离管理
   - 启用热重载功能

2. **资源限制**
   - 根据实际流量设置 CPU/内存限制
   - 建议：CPU 200m，内存 128Mi

3. **高可用**
   - K8s 部署时设置 `replicas: 2`
   - 使用 Pod AntiAffinity 分散到不同节点

4. **监控告警**
   - 接入 Prometheus + Grafana
   - 配置 Alertmanager 告警通道
   - 保留告警日志 30 天

---

## 快速参考

### Docker 命令速查

```bash
# 启动
docker run -d --name url-check -p 4000:4000 -p 9090:9090 -v $(pwd)/conf:/home/appuser/conf easonhe/url-checker:latest

# 停止
docker stop url-check

# 删除
docker rm url-check

# 查看日志
docker logs -f url-check

# 进入容器
docker exec -it url-check /bin/bash
```

### Kubernetes 命令速查

```bash
# 查看状态
kubectl get pods -n url-check -l app=url-check

# 查看日志
kubectl logs -n url-check -l app=url-check -f

# 重启
kubectl rollout restart deployment/url-check -n url-check

# 更新镜像
kubectl set image deployment/url-check url-check=easonhe/url-checker:latest -n url-check

# 回滚
kubectl rollout undo deployment/url-check -n url-check

# 端口转发
kubectl port-forward -n url-check svc/url-check 4000:4000 9090:9090

# 查看配置
kubectl get configmap -n url-check
kubectl describe configmap url-check-tasks -n url-check

# 删除
kubectl delete -f k8s/deployment.yaml -n url-check
```

---

## 附录

### 目录结构

```
url_check/
├── conf/
│   ├── config.py          # 应用配置
│   ├── alerts.yaml        # 告警规则配置
│   ├── alerts_config.py   # 告警配置加载模块
│   └── tasks.yaml         # 任务配置
├── view/
│   ├── checke_control.py   # 结果处理 + 指标 + 告警
│   ├── make_check_instan.py # 任务创建 + HTTP
│   └── hot_reload.py       # 配置热重载
├── k8s/
│   ├── deployment.yaml    # K8s 部署配置
│   ├── service.yaml       # K8s 服务
│   ├── ingress.yaml       # K8s 入口
│   └── kustomization.yaml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── url_check.py           # Flask 应用入口
└── DEPLOY.md              # 本文档
```

### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/metrics` | GET | Prometheus 指标 |
| `/health` | GET | 健康检查 |
| `/api/tasks` | GET | 获取任务列表 |
| `/api/tasks` | POST | 添加任务 |
| `/api/tasks/<name>` | DELETE | 删除任务 |
| `/api/reload` | POST | 重载配置 |

---

**文档版本**: v1.0.0  
**更新日期**: 2026-02-12
