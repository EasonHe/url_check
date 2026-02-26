import datetime


def _payload(task_name, code=200, timeout=0, content="ok"):
    return {
        "url_name": task_name,
        "url": "https://example.local/health",
        "stat_code": code,
        "timeout": timeout,
        "resp_time": 20,
        "contents": content,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "threshold": {"stat_code": 200, "math_str": "ok"},
        "expect_json": False,
        "json_path": None,
        "json_path_value": None,
    }


def test_health_endpoint_ok():
    from url_check import app

    client = app.test_client()
    resp = client.get("/health")
    payload = resp.get_json(force=True)
    assert resp.status_code == 200
    assert payload["status"] == "ok"
    assert "scheduler" in payload
    assert {"initialized", "running", "jobs"}.issubset(payload["scheduler"].keys())


def test_alert_metrics_still_emit_when_state_save_fails(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    from conf import config
    from view.checke_control import cherker, url_check_status_code_alert

    config.enable_alerts = False
    config.enable_dingding = False
    config.enable_mail = False

    def _save_fail(*args, **kwargs):
        return False

    monkeypatch.setattr("view.checke_control._save_state_data", _save_fail)

    task_name = "unit-alert-save-fail"
    checker = cherker(method="get")
    checker.make_data(_payload(task_name, code=503, timeout=0, content="bad"))

    metric = url_check_status_code_alert.labels(task_name=task_name, method="get")
    assert metric._value.get() == 1.0


def test_state_dir_created_on_first_run(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    from conf import config
    from view.checke_control import cherker

    config.enable_alerts = False
    config.enable_dingding = False
    config.enable_mail = False

    task_name = "unit-create-state-dir"
    checker = cherker(method="get")
    checker.make_data(_payload(task_name, code=200, timeout=0, content="ok"))

    assert (tmp_path / "data").exists()
    assert (tmp_path / "data" / f"{task_name}.pkl").exists()
