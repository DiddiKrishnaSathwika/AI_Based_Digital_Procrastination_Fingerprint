"""
Read-only check that the patch was applied correctly. Changes nothing.

  python scripts/verify_install.py            (run from the project root, the folder containing backend/ and frontend/)

Prints OK / WARN / FAIL lines and exits 1 if any FAIL.
"""
import hashlib
import os
import platform
import re
import shutil
import sys
from importlib import metadata

ROOT = os.getcwd()
fails = 0


def line(status, msg):
    global fails
    fails += status == "FAIL"
    print(f"[{status:<4}] {msg}")


def read(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        line("FAIL", f"{rel} not found (run this from the project root)")
        return ""
    return open(path, encoding="utf-8", errors="replace").read()


app, js, html = read("backend/app.py"), read("frontend/app.js"), read("frontend/index.html")

checks = [
    ("app.py has the real weekly comparison", "def build_weekly_report" in app and "random.Random(7)" not in app),
    ("app.py has rule-based interventions", "def select_interventions" in app and "Notification bursts correlate" not in app),
    ("app.py tags browser records as 'manual'", 'record_source = "manual"' in app),
    ("app.py has no 'Synthetic Demo Dataset' / demo_mode", "Synthetic Demo Dataset" not in app and '"demo_mode"' not in app),
    ("app.js weekly modal handles 'Not available'", "comparison_available" in js),
    ("app.js has no ML Pipeline script block", "loadMLPage" not in js and "PIPELINE_STAGES" not in js),
    ("index.html privacy text corrected", "Not implemented in this prototype" in html and "Privacy Mode" not in html),
    ("index.html has no ML Pipeline page", "page-ml" not in html),
]
for name, ok in checks:
    line("OK" if ok else "FAIL", name)

for rel in ("backend/requirements.txt", "backend/requirements-collector.txt", "backend/requirements-dev.txt",
            "backend/pytest.ini", "backend/tests/conftest.py"):
    line("OK" if os.path.exists(os.path.join(ROOT, rel)) else "FAIL", f"{rel} present")

col = os.path.join(ROOT, "backend", "activity_collector.py")
if os.path.exists(col):
    line("OK", "collector present, sha256=" + hashlib.sha256(open(col, "rb").read()).hexdigest()[:16] + "... (this patch does not modify it)")
else:
    line("WARN", "backend/activity_collector.py not found - collector tests will be skipped")

pins = {"Flask": "3.0.3", "Flask-Cors": "4.0.1", "Werkzeug": "3.1.9", "python-dotenv": "1.2.4"}
if platform.system() == "Windows":
    pins.update({"requests": "2.34.2", "psutil": "7.2.2", "pywin32": "312", "winotify": "1.1.0"})
for pkg, want in pins.items():
    try:
        have = metadata.version(pkg)
        line("OK" if have == want else "WARN", f"{pkg} {have}" + ("" if have == want else f" (requirements pin {want})"))
    except metadata.PackageNotFoundError:
        line("FAIL" if pkg in ("Flask", "Flask-Cors", "Werkzeug", "python-dotenv") else "WARN", f"{pkg} not installed")
try:
    import pytest  # noqa: F401
    line("OK", "pytest " + metadata.version("pytest"))
except ImportError:
    line("WARN", "pytest not installed (only needed to run the tests)")
line("OK" if shutil.which("node") else "WARN", "node: " + (shutil.which("node") or "not installed (3 frontend tests will be skipped)"))
print("\nRESULT:", "all required checks passed" if fails == 0 else f"{fails} required check(s) FAILED")
sys.exit(1 if fails else 0)
