from conftest import appmod

REC = {"application": "YouTube", "category": "Entertainment", "duration_min": 0.5,
       "task_type": "Software Development", "task_difficulty": "Medium",
       "idle_seconds": 0, "notifications": 0, "focus_level": "Distracted",
       "timestamp": "2026-11-10T11:00:05"}


def collector_headers(client):
    tok = client.post("/api/collector/token").get_json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_TC_API_01_collector_token_stored_hashed(env):
    """TC-API-01: a collector token is returned once and only its SHA-256 hash is stored."""
    c, uid = env.make_user()
    tok = c.post("/api/collector/token").get_json()["token"]
    stored = env.query("SELECT token_hash FROM collector_tokens WHERE user_id=?", (uid,))[0]["token_hash"]
    assert stored != tok and len(stored) == 64


def test_TC_API_02_bearer_post_creates_realtime_record(env):
    """TC-API-02: collector POST with a Bearer token (no cookie) stores a 'realtime' record for the token's user."""
    c, uid = env.make_user()
    h = collector_headers(c)
    bare = appmod.app.test_client()                      # no session cookie, like the desktop collector
    r = bare.post("/api/activity", json=REC, headers=h)
    assert r.status_code == 201 and r.get_json()["source"] == "realtime"
    row_ = env.query("SELECT * FROM activity WHERE user_id=?", (uid,))[0]
    assert row_["source"] == "realtime" and row_["application"] == "YouTube"


def test_TC_API_03_invalid_or_missing_token_rejected(env):
    """TC-API-03: no auth, bad token, and malformed header all return 401 and store nothing."""
    bare = appmod.app.test_client()
    assert bare.post("/api/activity", json=REC).status_code == 401
    assert bare.post("/api/activity", json=REC, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert bare.post("/api/activity", json=REC, headers={"Authorization": "Token abc"}).status_code == 401
    assert env.query("SELECT COUNT(*) c FROM activity")[0]["c"] == 0


def test_TC_API_04_browser_post_is_tagged_manual(env):
    """TC-API-04: a record posted from the logged-in browser session is tagged 'manual' (new behaviour)."""
    c, uid = env.make_user()
    r = c.post("/api/activity", json=REC)
    assert r.status_code == 201 and r.get_json()["source"] == "manual"
    assert env.query("SELECT source FROM activity WHERE user_id=?", (uid,))[0]["source"] == "manual"


def test_TC_API_05_regenerating_token_invalidates_previous(env):
    """TC-API-05: generating a new collector token replaces the old one."""
    c, uid = env.make_user()
    old = collector_headers(c)
    new = collector_headers(c)
    bare = appmod.app.test_client()
    assert bare.post("/api/activity", json=REC, headers=old).status_code == 401
    assert bare.post("/api/activity", json=REC, headers=new).status_code == 201


def test_TC_API_06_user_isolation(env):
    """TC-API-06: one user cannot read another user's records or analysis."""
    a, ua = env.make_user("a@x.com")
    b, ub = env.make_user("b@x.com")
    env.insert_rows(ua, [("2026-11-10T10:00", "VS Code", "Coding", 5, "Focused")])
    assert len(a.get("/api/activity").get_json()) == 1
    assert b.get("/api/activity").get_json() == []
    assert b.get("/api/dashboard").get_json()["focus_score"] == 0


def test_TC_API_07_get_limit_cap_and_filter(env):
    """TC-API-07: GET /api/activity caps limit at 500 and filters by focus level."""
    c, uid = env.make_user()
    env.insert_rows(uid, [(f"2026-11-10T10:{i % 60:02d}:{i // 60:02d}", "A", "Coding", 0.1,
                           "Focused" if i % 2 else "Distracted") for i in range(600)])
    assert len(c.get("/api/activity?limit=1000").get_json()) == 500
    assert len(c.get("/api/activity?limit=10").get_json()) == 10
    d = c.get("/api/activity?filter=Distracted&limit=500").get_json()
    assert d and all(r["focus_level"] == "Distracted" for r in d)


def test_TC_API_08_task_start_validation_active_stop(env):
    """TC-API-08: task start validates input; active/stop reflect state."""
    c, uid = env.make_user()
    assert c.post("/api/task/start", json={"task_type": "Coding"}).status_code == 400
    assert c.post("/api/task/start", json={"task_type": "Coding", "task_difficulty": "Extreme"}).status_code == 400
    assert c.get("/api/task/active").get_json()["active"] is False
    assert c.post("/api/task/start", json={"task_type": "Coding", "task_difficulty": "High"}).status_code == 200
    act = c.get("/api/task/active").get_json()
    assert act["active"] and act["task_type"] == "Coding" and act["task_difficulty"] == "High"
    assert c.post("/api/task/stop").status_code == 200
    assert c.get("/api/task/active").get_json()["active"] is False


def test_TC_API_09_reset_demo_deletes_only_own_manual_rows(env):
    """TC-API-09: /api/reset-demo removes the caller's 'manual' rows only."""
    a, ua = env.make_user("a@x.com")
    b, ub = env.make_user("b@x.com")
    env.insert_rows(ua, [("2026-11-10T10:00", "X", "Other", 1, "Focused")], source="manual")
    env.insert_rows(ua, [("2026-11-10T10:01", "Y", "Other", 1, "Focused")], source="realtime")
    env.insert_rows(ub, [("2026-11-10T10:02", "Z", "Other", 1, "Focused")], source="manual")
    assert a.post("/api/reset-demo").status_code == 200
    left = {(r["user_id"], r["source"]) for r in env.query("SELECT user_id, source FROM activity")}
    assert left == {(ua, "realtime"), (ub, "manual")}
