def post_fork(worker, log):
    """Reinitialize scheduler after fork."""
    import sys

    sys.path.insert(0, "/home/appuser")
    from view.make_check_instan import load_config
    from url_check import app

    # Reinitialize scheduler in worker process
    lt = load_config()
    lt.loading_task()

    # Store in app context
    app.scheduler_instance = lt
    print(f"Scheduler reinitialized in worker {worker.pid}")
