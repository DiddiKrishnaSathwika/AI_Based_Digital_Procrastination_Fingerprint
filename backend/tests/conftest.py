"""Shared pytest fixtures for the ProcrastiSense AI backend tests.

Every test runs against a temporary SQLite file; the project database is never
opened. Outgoing e-mail is replaced by in-memory capture functions, and the raw
SMTP sender raises if it is ever reached.
"""
import os
import sys
import sqlite3
from types import SimpleNamespace

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import app as appmod  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Fresh database + captured e-mails. Returns a namespace with helpers."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(appmod, "DB_PATH", db_file)
    appmod.init_db()
    appmod.app.config.update(TESTING=True)

    sent = SimpleNamespace(verify=[], reset=[])
    monkeypatch.setattr(appmod, "send_verification_email",
                        lambda email, name, token: sent.verify.append((email, token)))
    monkeypatch.setattr(appmod, "send_password_reset_email",
                        lambda email, name, token: sent.reset.append((email, token)))

    def _no_real_mail(*a, **k):
        raise AssertionError("a real e-mail send was attempted during a test")
    monkeypatch.setattr(appmod, "send_email", _no_real_mail)

    def make_user(email="user@example.com", name="Test User", password="password123"):
        """Register + verify + log in; returns (client, user_id)."""
        client = appmod.app.test_client()
        r = client.post("/api/auth/register", json={
            "full_name": name, "email": email,
            "password": password, "confirm_password": password})
        assert r.status_code == 201, r.get_json()
        token = [t for e, t in sent.verify if e == email][-1]
        assert client.get(f"/api/auth/verify-email?token={token}").status_code == 200
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.get_json()
        return client, r.get_json()["user"]["id"]

    def insert_rows(user_id, rows, source="realtime"):
        """rows: iterable of (timestamp, application, category, duration, focus_level)."""
        conn = sqlite3.connect(db_file)
        conn.executemany(
            "INSERT INTO activity (timestamp, application, category, duration_min,"
            " task_type, task_difficulty, idle_seconds, notifications, focus_level,"
            " source, user_id) VALUES (?,?,?,?,?,?,0,0,?,?,?)",
            [(ts, a, c, d, "Software Development", "Medium", f, source, user_id)
             for ts, a, c, d, f in rows])
        conn.commit()
        conn.close()

    def query(sql, params=()):
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        out = conn.execute(sql, params).fetchall()
        conn.close()
        return out

    return SimpleNamespace(db_file=db_file, sent=sent, make_user=make_user,
                           insert_rows=insert_rows, query=query, app=appmod)


def row(ts, app, cat, dur, level):
    """Plain-dict activity row for pure-function tests."""
    return {"timestamp": ts, "application": app, "category": cat,
            "duration_min": dur, "focus_level": level,
            "task_difficulty": "Medium", "task_type": "Software Development"}


def pytest_report_header(config):
    """Printed at the top of every run so results record exactly what was tested."""
    import hashlib
    import platform
    import shutil
    from importlib import metadata
    lines = [f"python {platform.python_version()} on {platform.system()}"]
    for pkg in ("Flask", "Flask-Cors", "Werkzeug", "python-dotenv"):
        try:
            lines.append(f"{pkg} {metadata.version(pkg)}")
        except metadata.PackageNotFoundError:
            lines.append(f"{pkg} NOT INSTALLED")
    path = os.path.join(BACKEND_DIR, "activity_collector.py")
    if os.path.exists(path):
        lines.append("collector file: present, sha256=" + hashlib.sha256(open(path, "rb").read()).hexdigest())
    else:
        lines.append("collector file: NOT FOUND -> collector tests will be SKIPPED")
    lines.append("node: " + (shutil.which("node") or "NOT FOUND -> Node-based frontend tests will be SKIPPED"))
    return lines
