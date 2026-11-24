import sqlite3
import pytest
from conftest import appmod


def test_TC_DB_01_schema_creates_all_tables_and_index(env):
    """TC-DB-01: init_db creates the six tables and the user index."""
    names = {r["name"] for r in env.query("SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    for t in ("users", "activity", "active_tasks", "collector_tokens",
              "password_reset_tokens", "email_verification_tokens", "idx_activity_user_id"):
        assert t in names


def test_TC_DB_02_init_db_is_idempotent(env):
    """TC-DB-02: running init_db twice keeps existing rows."""
    client, uid = env.make_user()
    env.insert_rows(uid, [("2026-11-01T10:00", "VS Code", "Coding", 5, "Focused")])
    appmod.init_db()
    assert env.query("SELECT COUNT(*) c FROM activity")[0]["c"] == 1
    assert env.query("SELECT COUNT(*) c FROM users")[0]["c"] == 1


def test_TC_DB_03_migration_adds_user_id_and_keeps_legacy_rows(tmp_path, monkeypatch):
    """TC-DB-03: a legacy activity table without user_id is migrated; old rows are kept (user_id NULL)."""
    db = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE activity (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
        application TEXT NOT NULL, category TEXT NOT NULL, duration_min REAL NOT NULL, task_type TEXT,
        task_difficulty TEXT, idle_seconds INTEGER DEFAULT 0, notifications INTEGER DEFAULT 0,
        focus_level TEXT NOT NULL, source TEXT DEFAULT 'synthetic')""")
    conn.execute("INSERT INTO activity (timestamp, application, category, duration_min, focus_level, source)"
                 " VALUES ('2026-09-22T10:00','Chrome','Browser',3,'Focused','realtime')")
    conn.commit(); conn.close()
    monkeypatch.setattr(appmod, "DB_PATH", db)
    appmod.init_db()
    conn = sqlite3.connect(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(activity)")]
    rows = conn.execute("SELECT user_id, application FROM activity").fetchall()
    conn.close()
    assert "user_id" in cols
    assert rows == [(None, "Chrome")]


def test_TC_DB_04_email_is_unique(env):
    """TC-DB-04: duplicate e-mail violates the UNIQUE constraint."""
    conn = sqlite3.connect(env.db_file)
    conn.execute("INSERT INTO users (full_name,email,password_hash,created_at) VALUES ('a','a@x.com','h','t')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users (full_name,email,password_hash,created_at) VALUES ('b','a@x.com','h','t')")
    conn.close()


def test_TC_DB_05_ownerless_rows_are_invisible_to_every_account(env):
    """TC-DB-05: rows with user_id NULL are not returned by any API (documents the pre-login legacy data)."""
    client, uid = env.make_user()
    conn = sqlite3.connect(env.db_file)
    conn.execute("INSERT INTO activity (timestamp, application, category, duration_min, focus_level, source)"
                 " VALUES ('2026-09-22T10:00','Chrome','Browser',3,'Focused','realtime')")
    conn.commit(); conn.close()
    assert client.get("/api/activity").get_json() == []
