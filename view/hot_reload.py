"""
配置文件热重载模块

功能：
    - 监听 conf/task.ini 文件的变更
    - 变更时自动重新加载配置（无需重启服务）
    - 支持本地开发环境的热重载

使用场景：
    - 本地开发：修改 task.ini 后自动生效
    - K8s 环境：跳过此模块，使用 kubectl rollout restart 更新配置

依赖：
    - watchdog: 文件系统监听库
"""

import threading
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from conf import config

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """
    配置文件变更事件处理器

    功能：
        - 监听指定文件的 modify 事件
        - 防抖处理：避免短时间内多次修改触发多次重载
        - 调用 reload_callback 执行实际的配置重载逻辑

    属性：
        config_path: 要监听的目标文件路径
        reload_callback: 文件变更时执行的回调函数
        last_modified: 上次处理变更的时间戳（用于防抖）
        debounce_seconds: 防抖时间阈值（秒）
    """

    def __init__(self, config_path, reload_callback):
        self.config_path = config_path
        self.reload_callback = reload_callback
        self.last_modified = 0
        self.debounce_seconds = 0.3

    def on_modified(self, event):
        """
        文件被修改时触发

        逻辑：
            1. 检查是否为配置文件（排除目录和其他文件）
            2. 防抖检查：距离上次处理是否超过 0.3 秒
            3. 调用 reload_callback 执行重载
            4. 记录重载结果日志

        Args:
            event: watchdog 事件对象
        """
        if event.src_path != self.config_path:
            return
        if event.is_directory:
            return

        current_time = time.time()
        if current_time - self.last_modified < self.debounce_seconds:
            return

        self.last_modified = current_time
        logger.info(f"检测到配置文件变更: {self.config_path}")
        try:
            success = self.reload_callback()
            if success:
                logger.info("✅ 配置热重载完成")
            else:
                logger.warning("⚠️ 配置热重载失败，请检查日志")
        except Exception as e:
            logger.error(f"🔥 配置热重载异常: {e}")


def start_config_watcher():
    """
    启动配置文件监听器

    功能：
        1. 获取 load_config 单例实例
        2. 创建 Observer 并注册事件处理器
        3. 启动守护线程持续监听

    注意：
        - 在 K8s 环境中会跳过启动（由 reload operator 处理）
        - 监听器以 daemon 线程运行，主进程退出时自动终止

    Returns:
        None
    """
    from view.make_check_instan import load_config

    config_path = config.tasks_yaml
    reload_callback = None

    try:
        instance = load_config()
        reload_callback = lambda: instance.safe_reload_config()
    except Exception as e:
        logger.error(f"获取 load_config 实例失败: {e}")
        return

    event_handler = ConfigFileHandler(config_path, reload_callback)
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.daemon = True
    observer.start()

    logger.info(f"✅ 配置监听器已启动: {config_path}")
