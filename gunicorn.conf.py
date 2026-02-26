def post_fork(worker, log):
    """Initialize scheduler in worker process after fork."""
    import sys

    sys.path.insert(0, "/home/appuser")
    from url_check import _init_scheduler

    _init_scheduler(force=True)
    print(f"Scheduler reinitialized in worker {worker.pid}")
