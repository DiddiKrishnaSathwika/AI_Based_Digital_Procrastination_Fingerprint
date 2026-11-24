import sqlite3
from datetime import datetime, timedelta
from conftest import appmod


def reg(client, **over):
    body = {"full_name": "A B", "email": "a@x.com", "password": "password123", "confirm_password": "password123"}
    body.update(over)
    return client.post("/api/auth/register", json=body)


def test_TC_AUTH_01_register_validation(env):
    """TC-AUTH-01: invalid registration inputs are rejected with 400."""
    c = appmod.app.test_client()
    assert reg(c, full_name="").status_code == 400
    assert reg(c, email="not-an-email").status_code == 400
    assert reg(c, password="short", confirm_password="short").status_code == 400
    assert reg(c, confirm_password="different123").status_code == 400
    assert reg(c, full_name="x" * 101).status_code == 400


def test_TC_AUTH_02_register_success_stores_hash_and_hashed_token(env):
    """TC-AUTH-02: password and verification token are stored hashed, not in plain text."""
    c = appmod.app.test_client()
    r = reg(c)
    assert r.status_code == 201 and r.get_json()["user"]["is_verified"] is False
    u = env.query("SELECT * FROM users")[0]
    assert u["password_hash"] != "password123" and u["is_verified"] == 0
    raw_token = env.sent.verify[0][1]
    stored = env.query("SELECT token_hash FROM email_verification_tokens")[0]["token_hash"]
    assert stored != raw_token and len(stored) == 64


def test_TC_AUTH_03_duplicate_email_409(env):
    """TC-AUTH-03: registering the same e-mail twice returns 409."""
    c = appmod.app.test_client()
    assert reg(c).status_code == 201
    assert reg(c).status_code == 409


def test_TC_AUTH_04_login_blocked_until_verified(env):
    """TC-AUTH-04: unverified account gets 403; wrong password gets 401."""
    c = appmod.app.test_client()
    reg(c)
    assert c.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"}).status_code == 403
    assert c.post("/api/auth/login", json={"email": "a@x.com", "password": "wrongpass1"}).status_code == 401


def test_TC_AUTH_05_verification_single_use_and_invalid(env):
    """TC-AUTH-05: a verification link works once; reuse and garbage tokens fail with 400."""
    c = appmod.app.test_client()
    reg(c)
    tok = env.sent.verify[0][1]
    assert c.get(f"/api/auth/verify-email?token={tok}").status_code == 200
    assert c.get(f"/api/auth/verify-email?token={tok}").status_code == 400
    assert c.get("/api/auth/verify-email?token=garbage").status_code == 400
    assert c.get("/api/auth/verify-email").status_code == 400


def test_TC_AUTH_06_expired_verification_token(env):
    """TC-AUTH-06: an expired verification token is rejected."""
    c = appmod.app.test_client()
    reg(c)
    conn = sqlite3.connect(env.db_file)
    conn.execute("UPDATE email_verification_tokens SET expires_at = ?",
                 ((datetime.now() - timedelta(hours=1)).isoformat(),))
    conn.commit(); conn.close()
    assert c.get(f"/api/auth/verify-email?token={env.sent.verify[0][1]}").status_code == 400


def test_TC_AUTH_07_login_session_me_logout(env):
    """TC-AUTH-07: login creates a session, /me returns the user, logout clears it."""
    c, uid = env.make_user("me@x.com")
    me = c.get("/api/auth/me")
    assert me.status_code == 200 and me.get_json()["user"]["email"] == "me@x.com"
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_TC_AUTH_08_protected_routes_require_login(env):
    """TC-AUTH-08: protected endpoints return 401 without a session."""
    c = appmod.app.test_client()
    for path in ("/api/dashboard", "/api/analytics", "/api/fingerprint", "/api/prediction",
                 "/api/interventions", "/api/weekly-report", "/api/task/active"):
        assert c.get(path).status_code == 401, path
    assert c.post("/api/task/start", json={}).status_code == 401
    assert c.post("/api/collector/token").status_code == 401


def test_TC_AUTH_09_forgot_and_reset_password_flow(env):
    """TC-AUTH-09: reset link changes the password, is single-use, and unknown e-mail gives a neutral response."""
    c, uid = env.make_user("r@x.com")
    r = c.post("/api/auth/forgot-password", json={"email": "unknown@x.com"})
    assert r.status_code == 200 and env.sent.reset == []
    assert c.post("/api/auth/forgot-password", json={"email": "r@x.com"}).status_code == 200
    tok = env.sent.reset[0][1]
    body = {"token": tok, "new_password": "newpassword9", "confirm_password": "newpassword9"}
    assert c.post("/api/auth/reset-password", json=body).status_code == 200
    assert c.post("/api/auth/reset-password", json=body).status_code == 400      # reused
    fresh = appmod.app.test_client()
    assert fresh.post("/api/auth/login", json={"email": "r@x.com", "password": "password123"}).status_code == 401
    assert fresh.post("/api/auth/login", json={"email": "r@x.com", "password": "newpassword9"}).status_code == 200


def test_TC_AUTH_10_reset_validation(env):
    """TC-AUTH-10: reset rejects short, mismatching, missing and invalid tokens."""
    c = appmod.app.test_client()
    assert c.post("/api/auth/reset-password", json={}).status_code == 400
    assert c.post("/api/auth/reset-password", json={"token": "t", "new_password": "short", "confirm_password": "short"}).status_code == 400
    assert c.post("/api/auth/reset-password", json={"token": "t", "new_password": "longenough1", "confirm_password": "other12345"}).status_code == 400
    assert c.post("/api/auth/reset-password", json={"token": "nope", "new_password": "longenough1", "confirm_password": "longenough1"}).status_code == 400
