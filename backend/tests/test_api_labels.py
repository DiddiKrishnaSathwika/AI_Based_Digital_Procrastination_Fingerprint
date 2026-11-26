import json
from datetime import datetime
from conftest import appmod

LABEL = "Real-Time Activity Data"


def seed(env, client, uid):
    now = datetime.now().replace(microsecond=0)
    ts = lambda m: now.replace(hour=8, minute=m, second=0).isoformat(timespec="seconds")
    env.insert_rows(uid, [(ts(0), "VS Code", "Coding", 10, "Focused"), (ts(10), "YouTube", "Entertainment", 2, "Distracted"),
                          (ts(12), "VS Code", "Coding", 8, "Focused")])


def test_TC_LB_01_dashboard_and_metrics_labels(env):
    """TC-LB-01: dashboard and metrics report 'Real-Time Activity Data' and no demo_mode key."""
    c, uid = env.make_user()
    seed(env, c, uid)
    for path in ("/api/dashboard", "/api/metrics"):
        body = c.get(path).get_json()
        assert body["data_label"] == LABEL, path
        assert "demo_mode" not in body, path


def test_TC_LB_02_no_synthetic_or_demo_text_in_any_get_response(env):
    """TC-LB-02: none of the data endpoints returns the words 'synthetic' or 'demo'."""
    c, uid = env.make_user()
    seed(env, c, uid)
    for path in ("/api/dashboard", "/api/metrics", "/api/analytics", "/api/fingerprint", "/api/prediction",
                 "/api/interventions", "/api/weekly-report", "/api/eda", "/api/task/active", "/api/activity"):
        r = c.get(path)
        assert r.status_code == 200, path
        text = json.dumps(r.get_json()).lower()
        assert "synthetic" not in text and "demo" not in text, path


def test_TC_LB_03_existing_dashboard_fields_unchanged(env):
    """TC-LB-03: all previous dashboard fields are still returned (only the demo label/flag were removed)."""
    c, uid = env.make_user()
    seed(env, c, uid)
    keys = set(c.get("/api/dashboard").get_json())
    assert keys == {"focus_score", "distraction_probability", "today_focus_time_min", "distractions",
                    "app_switches", "avg_focus_session_min", "data_label"}


def test_TC_LB_04_activity_schema_and_email_tables(env):
    """TC-LB-04: activity columns include retry idempotency while retired auth tables are absent."""
    cols = {
        row["column_name"]
        for row in env.query(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'activity'
            """
        )
    }
    assert cols == {"id", "timestamp", "application", "category", "duration_min", "task_type", "task_difficulty",
                    "idle_seconds", "notifications", "focus_level", "source", "user_id", "idempotency_key"}
    tables = {
        row["table_name"]
        for row in env.query(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
            """
        )
    }
    assert tables == {"users", "activity", "active_tasks", "collector_tokens"}
