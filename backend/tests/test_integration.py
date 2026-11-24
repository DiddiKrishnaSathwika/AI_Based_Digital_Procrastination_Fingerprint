"""End-to-end API workflow with simulated collector payloads (the real Windows collector is NOT run here)."""
from datetime import datetime, timedelta
from conftest import appmod


def build_records():
    """8 cycles of 4 x 2-min VS Code (Focused) + 1 distraction (YouTube 1.5 min / WhatsApp 1 min alternately)."""
    day = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    out, t = [], day
    for cycle in range(8):
        for _ in range(4):
            out.append(dict(timestamp=t.isoformat(timespec="seconds"), application="VS Code", category="Coding",
                            duration_min=2.0, focus_level="Focused"))
            t += timedelta(minutes=2)
        if cycle % 2 == 0:
            out.append(dict(timestamp=t.isoformat(timespec="seconds"), application="YouTube", category="Entertainment",
                            duration_min=1.5, focus_level="Distracted"))
        else:
            out.append(dict(timestamp=t.isoformat(timespec="seconds"), application="WhatsApp", category="Communication",
                            duration_min=1.0, focus_level="Distracted"))
        t += timedelta(minutes=2)
    return out


def run_workflow(env):
    c, uid = env.make_user("flow@x.com", name="Flow User")
    assert c.post("/api/task/start", json={"task_type": "Software Development", "task_difficulty": "Medium"}).status_code == 200
    tok = c.post("/api/collector/token").get_json()["token"]
    collector = appmod.app.test_client()                       # no cookies, like the desktop collector
    for rec in build_records():
        payload = dict(rec, task_type="Software Development", task_difficulty="Medium", idle_seconds=0, notifications=0)
        assert collector.post("/api/activity", json=payload, headers={"Authorization": f"Bearer {tok}"}).status_code == 201
    # one record typed into the Data Collection form from the logged-in browser
    assert c.post("/api/activity", json=dict(application="ManualApp", category="Other", duration_min=30,
                                             focus_level="Distracted", timestamp=datetime.now().isoformat(timespec="minutes"))).status_code == 201
    return c, uid, tok


def test_TC_INT_01_full_pipeline_values_match_independent_calculation(env):
    """TC-INT-01: collector posts -> database -> dashboard/analytics/fingerprint/prediction/interventions/weekly, checked against hand totals."""
    c, uid, _ = run_workflow(env)
    recs = build_records()
    assert len(c.get("/api/activity?limit=500").get_json()) == len(recs) + 1
    sources = {r["source"]: r["n"] for r in map(dict, env.query("SELECT source, COUNT(*) n FROM activity GROUP BY source"))}
    assert sources == {"realtime": 40, "manual": 1}

    # dashboard covers ALL of the user's rows (collector + manual): focus 64 min, distracted 10 + 30 manual
    dash = c.get("/api/dashboard").get_json()
    assert dash["distractions"] == 9 and dash["today_focus_time_min"] == 64
    assert dash["focus_score"] == round(64 / (64 + 10 + 30) * 100)

    # fingerprint and interventions use collector rows only: the 30-min manual row must not appear
    fp = c.get("/api/fingerprint").get_json()
    assert "ManualApp" not in [a["application"] for a in fp["most_used_applications"]]
    assert fp["distracted_time_min"] == 10.0 and fp["productive_time_min"] == 64.0

    iv = c.get("/api/interventions").get_json()
    rd = [i for i in iv if i["rule_id"] == "remove_distraction"]
    assert rd and "YouTube" in rd[0]["description"] and "60%" in rd[0]["reason"] and "ManualApp" not in str(iv)
    assert any(i["rule_id"] == "focus_sprint" and "8-minute" in i["description"] for i in iv)

    cats = {x["category"]: x["minutes"] for x in c.get("/api/analytics").get_json()["category_usage"]}
    assert cats["Entertainment"] == 6 and cats["Coding"] == 64

    pred = c.get("/api/prediction").get_json()
    assert pred["risk_level"] in ("LOW", "MODERATE", "HIGH") and pred["confidence"] is None

    wk = c.get("/api/weekly-report").get_json()
    assert wk["has_data"] and wk["comparison_available"] is False and wk["most_distracting_category"] == "Other"


def test_TC_INT_02_youtube_record_round_trip(env):
    """TC-INT-02: a YouTube record posted by the collector is stored and returned as Entertainment / Distracted."""
    c, uid, _ = run_workflow(env)
    yt = [r for r in c.get("/api/activity?limit=500").get_json() if r["application"] == "YouTube"]
    assert yt and all(r["category"] == "Entertainment" and r["focus_level"] == "Distracted" for r in yt)


def test_TC_INT_03_collector_token_stays_valid_after_session_end_KNOWN_LIMITATION(env):
    """TC-INT-03 (characterisation): ending the task session does not revoke the server-side collector token."""
    c, uid, tok = run_workflow(env)
    assert c.post("/api/task/stop").status_code == 200
    r = appmod.app.test_client().post("/api/activity", headers={"Authorization": f"Bearer {tok}"},
                                      json=dict(application="X", category="Other", duration_min=1, focus_level="Focused"))
    assert r.status_code == 201        # still accepted: stopping collection relies on the collector clearing its own token


def test_TC_INT_04_two_users_stay_separate_through_the_pipeline(env):
    """TC-INT-04: a second user's records never influence the first user's results."""
    c1, u1, _ = run_workflow(env)
    c2, u2 = env.make_user("other@x.com")
    env.insert_rows(u2, [(datetime.now().isoformat(timespec="seconds"), "Steam", "Gaming", 500, "Distracted")])
    assert c1.get("/api/fingerprint").get_json()["distracted_time_min"] == 10.0
    assert c2.get("/api/fingerprint").get_json()["distracted_time_min"] == 500.0
