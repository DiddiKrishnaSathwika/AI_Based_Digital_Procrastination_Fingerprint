from conftest import appmod
from werkzeug.security import check_password_hash


def reg(client, **over):
    body = {
        "full_name": "A B",
        "email": "a@x.com",
        "password": "password123",
    }
    body.update(over)
    return client.post("/api/auth/register", json=body)


def test_TC_AUTH_01_register_validation(env):
    """Registration validates required fields, password length, and optional confirmation."""
    client = appmod.app.test_client()
    assert reg(client, full_name="").status_code == 400
    assert reg(client, email="not-an-email").status_code == 400
    assert reg(client, password="short").status_code == 400
    assert reg(client, confirm_password="different123").status_code == 400
    assert reg(client, full_name="x" * 101).status_code == 400


def test_TC_AUTH_02_register_is_active_and_password_is_hashed(env):
    """New accounts can log in immediately and store only a password hash."""
    client = appmod.app.test_client()
    response = reg(client)
    assert response.status_code == 201

    user = env.query("SELECT * FROM users")[0]
    assert user["password_hash"] != "password123"
    assert check_password_hash(user["password_hash"], "password123")

    login_response = client.post(
        "/api/auth/login",
        json={"email": "a@x.com", "password": "password123"},
    )
    assert login_response.status_code == 200
    assert login_response.get_json()["user"]["id"] == user["id"]


def test_TC_AUTH_03_duplicate_email_returns_conflict(env):
    client = appmod.app.test_client()
    assert reg(client).status_code == 201
    assert reg(client).status_code == 409


def test_TC_AUTH_04_login_session_and_logout(env):
    client, user_id = env.make_user("me@x.com")
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["email"] == "me@x.com"
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": "me@x.com", "password": "wrongpass1"},
    ).status_code == 401


def test_TC_AUTH_05_protected_routes_require_login(env):
    client = appmod.app.test_client()
    for path in (
        "/api/dashboard", "/api/analytics", "/api/fingerprint",
        "/api/prediction", "/api/interventions", "/api/weekly-report",
        "/api/task/active",
    ):
        assert client.get(path).status_code == 401, path
    assert client.post("/api/task/start", json={}).status_code == 401
    assert client.post("/api/collector/token").status_code == 401
    assert client.post(
        "/api/auth/delete-account",
        json={"password": "password123"},
    ).status_code == 401


def test_TC_AUTH_06_account_deletion_requires_password_and_is_user_scoped(env):
    client_a, user_a = env.make_user("a@x.com")
    client_b, user_b = env.make_user("b@x.com")
    env.insert_rows(
        user_a,
        [("2026-11-01T10:00", "VS Code", "Coding", 5, "Focused")],
    )
    env.insert_rows(
        user_b,
        [("2026-11-01T10:00", "Browser", "Entertainment", 2, "Distracted")],
    )
    with env.connect() as conn:
        conn.execute(
            """
            INSERT INTO active_tasks (user_id, task_type, task_difficulty, started_at)
            VALUES (%s, %s, %s, %s)
            """,
            (user_a, "Coding", "Medium", "2026-11-01T10:00"),
        )
        conn.execute(
            """
            INSERT INTO collector_tokens (user_id, token_hash, created_at)
            VALUES (%s, %s, %s)
            """,
            (user_a, "hashed-token-a", "2026-11-01T10:00"),
        )

    assert client_a.post("/api/auth/delete-account", json={}).status_code == 400
    wrong_password = client_a.post(
        "/api/auth/delete-account",
        json={"password": "wrongpass1"},
    )
    assert wrong_password.status_code == 401
    assert env.query(
        "SELECT id FROM users WHERE id = %s", (user_a,)
    )

    response = client_a.post(
        "/api/auth/delete-account",
        json={"password": "password123"},
    )
    assert response.status_code == 200
    assert env.query("SELECT id FROM users WHERE id = %s", (user_a,)) == []
    assert env.query("SELECT id FROM activity WHERE user_id = %s", (user_a,)) == []
    assert env.query("SELECT user_id FROM active_tasks WHERE user_id = %s", (user_a,)) == []
    assert env.query("SELECT user_id FROM collector_tokens WHERE user_id = %s", (user_a,)) == []

    assert len(env.query("SELECT id FROM users WHERE id = %s", (user_b,))) == 1
    assert len(env.query("SELECT id FROM activity WHERE user_id = %s", (user_b,))) == 1
    assert client_a.get("/api/auth/me").status_code == 401
    assert client_b.get("/api/activity").status_code == 200
    assert len(client_b.get("/api/activity").get_json()) == 1


def test_TC_AUTH_07_retired_email_auth_routes_are_not_found(env):
    client = appmod.app.test_client()
    for path, method in (
        ("/api/auth/verify-email", "get"),
        ("/api/auth/resend-verification", "post"),
        ("/api/auth/forgot-password", "post"),
        ("/api/auth/reset-password", "post"),
    ):
        response = getattr(client, method)(path, json={}) if method == "post" else client.get(path)
        assert response.status_code == 404, path
        assert response.is_json
