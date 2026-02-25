"""
URL 健康检查服务

功能：
    - 定时检查配置的 URL 是否正常
    - 支持 HTTP GET/POST 请求
    - 检查维度：状态码、响应时间、关键字匹配、超时
    - 异常时发送钉钉告警
    - 提供 Prometheus 指标暴露

API 端点：
    - GET /health: 健康检查
    - GET /metrics: Prometheus 指标
    - POST /job/opt: 任务操作（列表/添加/删除/暂停/恢复）
    - POST /sender/mail: 发送邮件（预留）

配置文件：
    - conf/task.ini: URL 检查任务配置
    - conf/config.py: 基础配置（告警接收人、钉钉配置等）

依赖：
    - Flask: Web 框架
    - APScheduler: 定时调度
    - prometheus_client: 指标暴露

使用方式：
    # 本地开发（支持热重载）
    python url_check.py

    # K8s 部署
    kubectl apply -k k8s/
    # 配置变更后：
    kubectl rollout restart deployment url-check
"""

from flask import Flask, request
from view.mail_server import geturl
from view.make_check_instan import load_config
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST


app = Flask(__name__)

# Global scheduler instance (initialized lazily or by post_fork hook)
scheduler_instance = None


def _get_scheduler():
    """Get the scheduler instance, initializing if necessary."""
    global scheduler_instance
    if scheduler_instance is None:
        lt = load_config()
        lt.loading_task()
        scheduler_instance = lt

        from conf import config
        from view.make_check_instan import add_report_job

        if config.report_enabled:
            add_report_job(lt.sched, interval_hours=config.report_interval_hours)
    return scheduler_instance


@app.route("/sender/mail", methods=["POST"])
def sender_mail():
    """
    发送邮件接口（预留功能）

    Returns:
        str: 邮件发送结果
    """
    return geturl.sender()


@app.route("/job/opt", methods=["POST"])
def task_opt():
    """
    任务操作接口

    支持的操作：
        - list_jobs: 列出所有任务
        - add_job: 添加新任务
        - remove_job: 删除任务
        - stop_job: 暂停任务
        - resume_job: 恢复任务
        - shut_sched: 停止调度器
        - start_sched: 启动调度器

    Request Body (JSON):
        {
            "list_jobs": 1,
            "add_job": {"section": "新任务", "url": "...", "method": "get", ...},
            "remove_job": "任务名",
            "stop_job": "任务名",
            "resume_job": "任务名",
            "shut_sched": 1,
            "start_sched": 1
        }
    """
    if request.method == "POST":
        data = request.get_json() or {}

        # 列出所有任务
        if "list_jobs" in data and data["list_jobs"] == 1:
            job_list = _get_scheduler().get_jobs()
            return "{}".format(job_list)

        # 删除任务
        if "remove_job" in data:
            try:
                _get_scheduler().remove_job(task_name=data["remove_job"])
            except Exception as e:
                print(e)
                return "{}".format(e)

        # 暂停任务
        if "stop_job" in data:
            try:
                _get_scheduler().stop_job(task_name=data["stop_job"])
            except Exception as e:
                return "{}".format(e)

        # 恢复任务
        if "resume_job" in data:
            try:
                _get_scheduler().resume_job(task_name=data["resume_job"])
            except Exception as e:
                return "{}".format(e)

        # 停止调度器
        if "shut_sched" in data and data["shut_sched"] == 1:
            try:
                _get_scheduler().shut_sched()
            except Exception as e:
                return "{}".format(e)

        # 添加任务
        if "add_job" in data:
            print(type(data))
            task_info = data["add_job"]
            print(task_info)
            return "{}".format(_get_scheduler().add_job(task_info=data["add_job"]))

        # 启动调度器
        if "start_sched" in data and data["start_sched"] == 1:
            _get_scheduler().start_sched()

        return "ok"
    return "{} False".format(data)


@app.route("/health")
def health():
    """
    健康检查接口

    用途：
        - K8s livenessProbe 探针
        - 负载均衡器健康检查

    Returns:
        JSON: 服务状态信息
    """
    return {"status": "ok", "flask": "2.3.3", "uv": "0.9.28"}


@app.route("/metrics")
def metrics():
    """
    Prometheus 指标暴露接口

    用途：
        - Prometheus 服务器抓取指标

    暴露的指标：
        - url_check_success_total: HTTP 请求计数
        - url_check_response_time_seconds: 响应时间直方图
        - url_check_timeout_total: 超时计数

    Returns:
        Response: Prometheus 格式的指标数据
    """
    from flask import Response

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import os

    # =============================================================================
    # 启动配置
    # =============================================================================
    # 本地开发模式：
    #   - 启动 watchdog 文件监听器
    #   - 修改 conf/task.ini 后自动重载配置
    #
    # K8s 生产模式：
    #   - 跳过 watchdog（使用 ConfigMap + rollout restart）
    #   - 通过环境变量 KUBERNETES_SERVICE_HOST 检测
    # =============================================================================

    port = int(os.getenv("URL_CHECK_PORT", "4000"))

    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        print("ℹ️ K8s 环境检测，跳过 watchdog 文件监听")
        print("ℹ️ 配置变更请使用: kubectl rollout restart deployment url-check")
    else:
        from view.hot_reload import start_config_watcher

        start_config_watcher()
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
