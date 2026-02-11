# K8s Reloader 配置自动重载

## 概述

Reloader 是一个 K8s Operator，可监控 ConfigMap/Secret 变更并自动重启 Pod。

**是否必须**：否。可手动执行 `kubectl rollout restart` 实现同样效果。

---

## 安装 Reloader（可选）

```bash
kubectl apply -f https://raw.githubusercontent.com/stakater/Reloader/master/deployments/kubernetes/reloader.yaml
```

验证安装：
```bash
kubectl get pods -n reloader | grep reloader
```

---

## 工作原理

1. 在 Deployment 添加注解：
   ```yaml
   metadata:
     annotations:
       configmap.reloader.stakater.com/reload: "url-check-config"
   ```
2. ConfigMap 变更后，Reloader 自动触发 Pod 重启
3. Pod 重启后加载新配置

---

## 不安装 Reloader 时的配置更新流程

```bash
# 1. 编辑 ConfigMap
kubectl edit configmap url-check-config

# 2. 手动重启 Pod
kubectl rollout restart deployment url-check

# 3. 查看日志确认配置生效
kubectl logs -l app=url-check -f
```

---

## 对比

| 方式 | 配置更新 | 适用场景 |
|------|---------|---------|
| **手动重启** | 需执行 `kubectl rollout restart` | 配置变更不频繁 |
| **Reloader** | 自动重启 | 配置变更频繁、需要自动化 |

---

## 当前项目配置

- ✅ Deployment 已添加 Reloader 注解
- ⏸️ Reloader 未安装（如需自动重启，请按上方命令安装）
