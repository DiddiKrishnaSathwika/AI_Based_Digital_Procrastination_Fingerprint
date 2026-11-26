"""Shared pytest fixtures using an isolated PostgreSQL schema per test."""
import os
import sys
import uuid
from types import SimpleNamespace

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import app as appmod  # noqa: E402


@pytest.fixture()
def env(monkeypatch):
    """Create isolated PostgreSQL tables and capture outgoing e-mails."""
    base_dsn = appmod.DATABASE_URL
    schema = "test_" + uuid.uuid4().hex
    original_connect = psycopg.connect

    with original_connect(base_dsn) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    def connect_to_schema(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.execute(
            sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
        )
        return conn

    monkeypatch.setattr(appmod.psycopg, "connect", connect_to_schema)
    try:
        appmod.init_db()
    except Exception:
        with original_connect(base_dsn) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
        raise
    appmod.app.config.update(TESTING=True)

    sent = SimpleNamespace(verify=[], reset=[])
    monkeypatch.setattr(
        appmod, "send_verification_email",
        lambda email, name, token: sent.verify.append((email, token))
    )
    monkeypatch.setattr(
        appmod, "send_password_reset_email",
        lambda email, name, token: sent.reset.append((email, token))
    )

    def _no_real_mail(*args, **kwargs):
        raise AssertionError("a real e-mail send was attempted during a test")

    monkeypatch.setattr(appmod, "send_email", _no_real_mail)

    def connect():
        return connect_to_schema(base_dsn, row_factory=dict_row)

    def make_user(email="user@example.com", name="Test User", password="password123"):
        """Register + verify + log in; returns (client, user_id)."""
        client = appmod.app.test_client()
        response = client.post("/api/auth/register", json={
            "full_name": name,
            "email": email,
            "password": password,
            "confirm_password": password,
        })
        assert response.status_code == 201, response.get_json()
        token = [value for address, value in sent.verify if address == email][-1]
        assert client.get(
            f"/api/auth/verify-email?token={token}"
        ).status_code == 200
        response = client.post("/api/auth/login", json={
            "email": email,
            "password": password,
        })
        assert response.status_code == 200, response.get_json()
        return client, response.get_json()["user"]["id"]

    def insert_rows(user_id, rows, source="realtime"):
        """rows: iterable of (timestamp, application, category, duration, focus_level)."""
        with connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO activity (
                    timestamp, application, category, duration_min,
                    task_type, task_difficulty, idle_seconds, notifications,
                    focus_level, source, user_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, 0, 0, %s, %s, %s)
                """,
                [
                    (ts, app, category, duration, "Software Development",
                     "Medium", focus_level, source, user_id)
                    for ts, app, category, duration, focus_level in rows
                ],
            )

    def query(statement, params=()):
        with connect() as conn:
            return conn.execute(statement, params).fetchall()

    try:
        yield SimpleNamespace(
            schema=schema,
            dsn=base_dsn,
            sent=sent,
            make_user=make_user,
            insert_rows=insert_rows,
            query=query,
            connect=connect,
            app=appmod,
        )
    finally:
        with original_connect(base_dsn) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


def row(ts, app, cat, dur, level):
    """Plain-dict activity row for pure-function tests."""
    return {
        "timestamp": ts,
        "application": app,
        "category": cat,
        "duration_min": dur,
        "focus_level": level,
        "task_difficulty": "Medium",
        "task_type": "Software Development",
    }


def pytest_report_header(config):
    """Printed at the top of every run so results record exactly what was tested."""
    import platform
    import shutil
    from importlib import metadata

    lines = [f"python {platform.python_version()} on {platform.system()}"]
    for package in ("Flask", "Flask-Cors", "Werkzeug", "python-dotenv", "psycopg"):
        try:
            lines.append(f"{package} {metadata.version(package)}")
        except metadata.PackageNotFoundError:
            lines.append(f"{package} NOT INSTALLED")
    lines.append(
        "node: " + (shutil.which("node") or "NOT FOUND -> Node-based frontend tests will be SKIPPED")
    )
    return lines
