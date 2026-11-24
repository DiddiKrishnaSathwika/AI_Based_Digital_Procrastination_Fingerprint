"""
Compare the ORIGINAL backend (app.py before the patch) with the PATCHED one on identical data.

  python scripts/compare_with_original.py <path/to/original/app.py> <path/to/patched/app.py>

Both modules are loaded side by side, each with its own temporary database (your real database is never
opened) and with e-mail sending disabled. Endpoints that were NOT meant to change must return identical
JSON; endpoints that were intentionally changed are listed separately. Exit code 0 = all unchanged
endpoints identical, 1 = a difference was found.
"""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile

from werkzeug.security import generate_password_hash

ROWS = [  # (timestamp, application, category, minutes, focus_level)
    ("2026-11-10T09:00:00", "VS Code", "Coding", 12, "Focused"),
    ("2026-11-10T09:12:00", "WhatsApp", "Communication", 1.5, "Distracted"),
    ("2026-11-10T09:14:00", "VS Code", "Coding", 6, "Focused"),
    ("2026-11-10T10:00:00", "YouTube", "Entertainment", 2, "Distracted"),
    ("2026-11-10T10:03:00", "msedge.exe", "Browser", 4, "Focused"),
    ("2026-11-10T10:07:00", "Unknown app", "Other", 3, "Unknown"),
    ("2026-11-11T11:00:00", "VS Code", "Coding", 20, "Focused"),
    ("2026-11-11T11:21:00", "Instagram", "Social Media", 3, "Distracted"),
    ("2026-11-11T11:25:00", "VS Code", "Coding", 9, "Focused"),
]
UNCHANGED = ["/api/auth/me", "/api/activity?limit=100", "/api/activity?filter=Focused", "/api/analytics",
             "/api/fingerprint", "/api/prediction", "/api/eda", "/api/task/active"]
CHANGED_ON_PURPOSE = ["/api/dashboard", "/api/metrics", "/api/interventions", "/api/weekly-report"]


def load(path, name, db_file):
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB_PATH = db_file
    mod.init_db()
    mod.send_email = lambda *a, **k: (_ for _ in ()).throw(AssertionError("real e-mail attempted"))
    mod.app.config.update(TESTING=True)
    conn = sqlite3.connect(db_file)
    conn.execute("INSERT INTO users (id, full_name, email, password_hash, is_verified, created_at) VALUES (1,'Cmp','cmp@example.com',?,1,'2026-11-01')",
                 (generate_password_hash("password123"),))
    conn.executemany("INSERT INTO activity (timestamp, application, category, duration_min, task_type, task_difficulty,"
                     " idle_seconds, notifications, focus_level, source, user_id) VALUES (?,?,?,?,'Coding','Medium',0,0,?,'realtime',1)",
                     [(t, a, c, d, f) for t, a, c, d, f in ROWS])
    conn.commit(); conn.close()
    client = mod.app.test_client()
    assert client.post("/api/auth/login", json={"email": "cmp@example.com", "password": "password123"}).status_code == 200
    return mod, client


def schema(db_file):
    conn = sqlite3.connect(db_file)
    out = sorted((r[0], r[1], r[2]) for r in conn.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
    conn.close()
    return out


def main(old_path, new_path):
    tmp = tempfile.mkdtemp()
    old_db, new_db = os.path.join(tmp, "old.db"), os.path.join(tmp, "new.db")
    _, old = load(old_path, "app_original", old_db)
    _, new = load(new_path, "app_patched", new_db)
    failures = 0
    print(f"{'Endpoint':<34}{'Expected':<22}Result")
    print("-" * 78)
    print(f"{'database schema (tables/columns)':<34}{'identical':<22}", end="")
    same = schema(old_db) == schema(new_db)
    print("IDENTICAL" if same else "DIFFERENT"); failures += (not same)
    for path in UNCHANGED:
        a, b = old.get(path), new.get(path)
        ok = a.status_code == b.status_code and a.get_json() == b.get_json()
        print(f"{path:<34}{'identical':<22}{'IDENTICAL' if ok else 'DIFFERENT'}"); failures += (not ok)
    for path in ("/api/dashboard", "/api/metrics"):
        a, b = old.get(path).get_json(), new.get(path).get_json()
        for k in ("demo_mode", "data_label"):
            a.pop(k, None); b.pop(k, None)
        ok = a == b
        print(f"{path:<34}{'same except label':<22}{'IDENTICAL (ignoring demo_mode/data_label)' if ok else 'DIFFERENT'}"); failures += (not ok)
    body = {"application": "X", "category": "Other", "duration_min": 1, "focus_level": "Focused", "timestamp": "2026-11-12T10:00"}
    ra, rb = old.post("/api/activity", json=body), new.post("/api/activity", json=body)
    def last_source(db_file):
        conn = sqlite3.connect(db_file)
        s = conn.execute("SELECT source FROM activity ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.close()
        return s
    print(f"{'POST /api/activity (browser)':<34}{'201, source differs':<22}{ra.status_code}/{rb.status_code}, stored source: original='{last_source(old_db)}' patched='{last_source(new_db)}'")
    failures += not (ra.status_code == rb.status_code == 201)
    print("\nIntentionally changed (not compared):", ", ".join(CHANGED_ON_PURPOSE))
    print("\nRESULT:", "all unchanged endpoints identical" if failures == 0 else f"{failures} difference(s) found")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
