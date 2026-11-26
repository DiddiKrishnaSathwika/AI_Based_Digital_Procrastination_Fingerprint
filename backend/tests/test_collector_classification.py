"""Collector classification and bridge tests.

The collector imports Windows-only modules (win32gui, win32process, winotify, psutil) at the top of the file,
so they are replaced by stubs here. The tests cover classification and delivery queue behavior. They do NOT test
foreground-window capture, process lookup, or toast notifications; those must be tested on Windows.
"""
import http.client
import importlib.util
import json
import os
import sys
import threading
import time
import types

import pytest
from conftest import appmod

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "activity_collector.py")

if not os.path.exists(PATH):
    pytest.skip("activity_collector.py not found next to app.py: these tests read YOUR original collector file "
                "and are skipped (not passed) without it.", allow_module_level=True)

pytestmark = pytest.mark.collector


@pytest.fixture(scope="module")
def collector():
    saved = {k: sys.modules.get(k) for k in ("turtle", "win32gui", "win32process", "psutil", "winotify", "requests")}
    sys.modules["turtle"] = types.SimpleNamespace(title=lambda *a, **k: None)
    sys.modules["win32gui"] = types.ModuleType("win32gui")
    sys.modules["win32process"] = types.ModuleType("win32process")
    sys.modules["psutil"] = types.ModuleType("psutil")
    sys.modules["winotify"] = types.SimpleNamespace(Notification=object, audio=types.SimpleNamespace())
    sys.modules.setdefault("requests", types.ModuleType("requests"))
    spec = importlib.util.spec_from_file_location("activity_collector_under_test", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


def both(c, proc, title):
    return c.get_activity_name(proc, title), *c.classify_application(proc, title)


@pytest.mark.parametrize("browser", ["chrome.exe", "msedge.exe", "firefox.exe"])
def test_TC_CL_01_youtube_rule_in_every_browser(collector, browser):
    """TC-CL-01: YouTube in a browser window title -> name YouTube, category Entertainment, Distracted."""
    assert both(collector, browser, "Some video - YouTube - Microsoft Edge") == ("YouTube", "Entertainment", "Distracted")


def test_TC_CL_02_youtube_never_study_or_education(collector):
    """TC-CL-02: titles that look educational are still Entertainment/Distracted (content is not analysed)."""
    for title in ("Python tutorial for beginners - YouTube", "NPTEL lecture 4 - YouTube", "MIT OpenCourseWare - youtube"):
        name, cat, focus = both(collector, "chrome.exe", title)
        assert (name, cat, focus) == ("YouTube", "Entertainment", "Distracted"), title


def test_TC_CL_03_desktop_apps_by_process_name(collector):
    """TC-CL-03: process-name table assigns category and focus label."""
    assert collector.classify_application("code.exe", "main.py - VS Code") == ("Coding", "Focused")
    assert collector.classify_application("whatsapp.exe", "WhatsApp") == ("Communication", "Distracted")
    assert collector.classify_application("spotify.exe", "Spotify") == ("Entertainment", "Distracted")
    assert collector.classify_application("steam.exe", "Steam") == ("Gaming", "Distracted")
    assert collector.get_activity_name("code.exe", "x") == "VS Code"
    assert collector.get_activity_name("whatsapp.exe", "x") == "WhatsApp"


def test_TC_CL_04_unmatched_browser_other_and_explorer(collector):
    """TC-CL-04: unmatched browser titles -> Browser/Focused; explorer -> Work/Focused; unknown process -> Other/Focused."""
    assert collector.classify_application("msedge.exe", "New Tab") == ("Browser", "Focused")
    assert collector.classify_application("explorer.exe", "Downloads") == ("Work", "Focused")
    assert collector.classify_application("snippingtool.exe", "Snipping Tool") == ("Other", "Focused")
    assert collector.get_activity_name("msedge.exe", "New Tab") == "msedge.exe"


def test_TC_CL_05_empty_and_none_inputs(collector):
    """TC-CL-05: None / empty inputs do not raise."""
    assert collector.classify_application(None, None) == ("Other", "Focused")
    assert collector.get_activity_name(None, None) == "Unknown"


def test_TC_CL_06_website_keywords_and_focus_split(collector):
    """TC-CL-06: website keywords map to categories; social/entertainment/shopping/communication are Distracted."""
    cases = {"Instagram - Chrome": ("Social Media", "Distracted"), "Flipkart - Chrome": ("Shopping", "Distracted"),
             "web.whatsapp.com - Chrome": ("Communication", "Distracted"),
             "GitHub - repo": ("Coding", "Focused"), "ChatGPT": ("AI Assistant", "Focused"),
             "Coursera - ML": ("Study", "Focused"), "arXiv paper": ("Research", "Focused")}
    for title, expected in cases.items():
        assert collector.classify_application("chrome.exe", title) == expected, title


def test_TC_CL_07_desktop_process_table_has_priority_over_title(collector):
    """TC-CL-07: a known desktop process is classified by process name even if the title contains a website keyword."""
    assert collector.classify_application("spotify.exe", "github playlist") == ("Entertainment", "Distracted")


def test_TC_CL_08_KNOWN_LIMITATION_substring_false_positives(collector):
    """TC-CL-08 (documents known limitations): plain substring matching on the window title gives false positives."""
    # any application whose title contains 'youtube' is Distracted, not only browsers
    assert collector.classify_application("notepad.exe", "youtube_notes.txt - Notepad") == ("Entertainment", "Distracted")
    # 'box.com' contains 'x.com'
    assert collector.classify_application("chrome.exe", "Dropbox - box.com") == ("Social Media", "Distracted")
    # 'threads' (social-media keyword) matches a programming article; social keywords are checked first
    assert collector.classify_application("chrome.exe", "Python threads tutorial - Stack Overflow") == ("Social Media", "Distracted")


@pytest.mark.parametrize("failure", ["network", "http"])
def test_TC_CL_09_failed_activity_delivery_is_retained_and_retried(
    collector, monkeypatch, failure
):
    class RequestError(Exception):
        pass

    monkeypatch.setattr(
        collector.requests,
        "exceptions",
        types.SimpleNamespace(RequestException=RequestError),
        raising=False,
    )
    monkeypatch.setattr(collector, "PENDING_ACTIVITY", [])
    monkeypatch.setattr(collector, "NEXT_RETRY_AT", 0.0)
    monkeypatch.setattr(collector, "CURRENT_COLLECTOR_TOKEN", "test-token")
    monkeypatch.setattr(collector, "CURRENT_TASK_TYPE", "Study")
    monkeypatch.setattr(collector, "CURRENT_TASK_DIFFICULTY", "Medium")

    attempts = []

    def post(url, **kwargs):
        attempts.append((url, kwargs))
        if len(attempts) == 1:
            if failure == "network":
                raise RequestError("offline")
            return types.SimpleNamespace(status_code=503)
        return types.SimpleNamespace(status_code=201)

    monkeypatch.setattr(collector.requests, "post", post, raising=False)

    collector.send_activity("YouTube", "Entertainment", 30, "Distracted")

    assert len(collector.PENDING_ACTIVITY) == 1
    collector.NEXT_RETRY_AT = 0.0
    collector.flush_pending_activities()

    assert collector.PENDING_ACTIVITY == []
    assert len(attempts) == 2
    assert attempts[0][0] == collector.API_URL
    assert attempts[0][1]["headers"] == {
        "Authorization": "Bearer test-token"
    }


def test_TC_CL_10_windows_idle_time_uses_last_input_tick(collector, monkeypatch):
    def get_last_input_info(pointer):
        pointer._obj.dwTime = 1000
        return 1

    fake_windll = types.SimpleNamespace(
        user32=types.SimpleNamespace(GetLastInputInfo=get_last_input_info),
        kernel32=types.SimpleNamespace(GetTickCount=lambda: 6000),
    )
    monkeypatch.setattr(collector.os, "name", "nt")
    monkeypatch.setattr(collector.ctypes, "windll", fake_windll, raising=False)

    assert collector.get_idle_seconds() == 5


def _bridge_request(collector, method, path, headers, body=None):
    server = collector.HTTPServer(
        ("127.0.0.1", 0),
        collector.CollectorBridgeHandler,
    )
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=3
        )
        connection.request(
            method,
            path,
            body=json.dumps(body) if body is not None else None,
            headers=headers,
        )
        response = connection.getresponse()
        result = (
            response.status,
            {name.lower(): value for name, value in response.getheaders()},
        )
        response.read()
        connection.close()
        return result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _stop_bridge_request(collector, interval):
    errors = []

    def service_stop_request():
        if not collector.STOP_REQUESTED.wait(timeout=5):
            errors.append(TimeoutError("stop request was not signaled"))
            return
        try:
            collector.STOP_SUCCESS = collector.flush_activity_before_stop(
                *interval
            )
        except Exception as error:
            errors.append(error)
            collector.STOP_SUCCESS = False
        finally:
            collector.STOP_REQUESTED.clear()
            collector.STOP_COMPLETED.set()

    collector.STOP_REQUESTED.clear()
    collector.STOP_COMPLETED.clear()
    collector.STOP_SUCCESS = False
    service_thread = threading.Thread(target=service_stop_request)
    service_thread.start()
    result = _bridge_request(
        collector,
        "POST",
        "/task",
        {
            "Origin": "http://localhost:5000",
            "Content-Type": "application/json",
        },
        {"action": "stop"},
    )
    service_thread.join(timeout=3)
    assert not service_thread.is_alive()
    return result, errors


@pytest.mark.parametrize("origin", [
    "https://ai-based-digital-procrastination-fingerprint-de7l3c4ge.vercel.app",
    "https://ai-based-digital-procrastination-fi.vercel.app",
    "https://procrastisenseai.vercel.app",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
])
def test_TC_CL_11_bridge_preflight_allows_frontend_origins(collector, origin):
    status, headers = _bridge_request(
        collector,
        "OPTIONS",
        "/task",
        {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
            "Access-Control-Request-Private-Network": "true",
        },
    )

    assert status == 204
    assert headers["access-control-allow-origin"] == origin
    assert headers["access-control-allow-methods"] == "POST, OPTIONS"
    assert headers["access-control-allow-headers"] == "Content-Type"
    assert headers["access-control-allow-private-network"] == "true"


def test_TC_CL_12_bridge_preflight_rejects_unlisted_origin(collector):
    status, headers = _bridge_request(
        collector,
        "OPTIONS",
        "/task",
        {
            "Origin": "https://unlisted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert status == 403
    assert "access-control-allow-origin" not in headers


@pytest.mark.parametrize(
    ("path", "request_method", "request_headers", "expected_status"),
    [
        ("/task", "PUT", "content-type", 405),
        ("/task", "POST", "content-type, authorization", 403),
        ("/other", "POST", "content-type", 404),
    ],
)
def test_TC_CL_13_bridge_preflight_restricts_path_method_and_headers(
    collector, path, request_method, request_headers, expected_status
):
    status, _ = _bridge_request(
        collector,
        "OPTIONS",
        path,
        {
            "Origin": "https://procrastisenseai.vercel.app",
            "Access-Control-Request-Method": request_method,
            "Access-Control-Request-Headers": request_headers,
        },
    )

    assert status == expected_status


def test_TC_CL_14_stopping_flushes_pending_and_active_activity_before_token_clear(
    collector, monkeypatch
):
    pending = {
        "application": "Previous App",
        "category": "Coding",
        "duration_min": 1,
        "task_type": "Coding",
        "task_difficulty": "Medium",
        "focus_level": "Focused",
    }
    monkeypatch.setattr(collector, "PENDING_ACTIVITY", [(pending, "active-token")])
    monkeypatch.setattr(collector, "NEXT_RETRY_AT", time.monotonic() + 60)
    monkeypatch.setattr(collector, "CURRENT_COLLECTOR_TOKEN", "active-token")
    monkeypatch.setattr(collector, "CURRENT_TASK_TYPE", "Coding")
    monkeypatch.setattr(collector, "CURRENT_TASK_DIFFICULTY", "Medium")

    posted = []

    def post(url, **kwargs):
        posted.append(kwargs["json"])
        return types.SimpleNamespace(status_code=201)

    monkeypatch.setattr(collector.requests, "post", post, raising=False)
    result, errors = _stop_bridge_request(
        collector,
        ("Current App", "Coding", "Focused", time.time() - 30),
    )

    assert result[0] == 200 and errors == []
    assert [payload["application"] for payload in posted] == [
        "Previous App", "Current App"
    ]
    assert collector.PENDING_ACTIVITY == []
    assert collector.CURRENT_COLLECTOR_TOKEN is None


def test_TC_CL_15_stopping_without_pending_activity_clears_token_without_post(
    collector, monkeypatch
):
    monkeypatch.setattr(collector, "PENDING_ACTIVITY", [])
    monkeypatch.setattr(collector, "CURRENT_COLLECTOR_TOKEN", "active-token")
    monkeypatch.setattr(collector, "CURRENT_TASK_TYPE", "Coding")
    monkeypatch.setattr(collector, "CURRENT_TASK_DIFFICULTY", "Medium")
    posted = []
    monkeypatch.setattr(
        collector.requests,
        "post",
        lambda *args, **kwargs: posted.append(kwargs),
        raising=False,
    )

    result, errors = _stop_bridge_request(
        collector,
        (None, None, None, time.time()),
    )

    assert result[0] == 200 and errors == []
    assert posted == []
    assert collector.CURRENT_COLLECTOR_TOKEN is None


def test_TC_CL_16_normal_flush_and_repeated_stop_do_not_duplicate_records(
    collector, monkeypatch
):
    monkeypatch.setattr(collector, "PENDING_ACTIVITY", [])
    monkeypatch.setattr(collector, "NEXT_RETRY_AT", 0.0)
    monkeypatch.setattr(collector, "CURRENT_COLLECTOR_TOKEN", "active-token")
    monkeypatch.setattr(collector, "CURRENT_TASK_TYPE", "Coding")
    monkeypatch.setattr(collector, "CURRENT_TASK_DIFFICULTY", "Medium")
    posted = []

    def post(url, **kwargs):
        posted.append(kwargs["json"])
        return types.SimpleNamespace(status_code=201)

    monkeypatch.setattr(collector.requests, "post", post, raising=False)
    collector.send_activity("Previous App", "Coding", 30, "Focused")
    assert [payload["application"] for payload in posted] == ["Previous App"]

    result, errors = _stop_bridge_request(
        collector,
        ("Current App", "Coding", "Focused", time.time() - 15),
    )
    assert result[0] == 200 and errors == []
    assert [payload["application"] for payload in posted] == [
        "Previous App", "Current App"
    ]

    repeated_result, repeated_errors = _stop_bridge_request(
        collector,
        (None, None, None, time.time()),
    )
    assert repeated_result[0] == 200 and repeated_errors == []
    assert [payload["application"] for payload in posted] == [
        "Previous App", "Current App"
    ]


def test_TC_CL_17_stop_network_failure_retains_queue_and_active_token(
    collector, monkeypatch
):
    pending = {
        "application": "Queued App",
        "category": "Coding",
        "duration_min": 1,
        "focus_level": "Focused",
    }
    monkeypatch.setattr(collector, "PENDING_ACTIVITY", [(pending, "active-token")])
    monkeypatch.setattr(collector, "NEXT_RETRY_AT", 0.0)
    monkeypatch.setattr(collector, "CURRENT_COLLECTOR_TOKEN", "active-token")
    monkeypatch.setattr(collector, "CURRENT_TASK_TYPE", "Coding")
    monkeypatch.setattr(collector, "CURRENT_TASK_DIFFICULTY", "Medium")

    class RequestError(Exception):
        pass

    monkeypatch.setattr(
        collector.requests,
        "exceptions",
        types.SimpleNamespace(RequestException=RequestError),
        raising=False,
    )

    def post(url, **kwargs):
        raise RequestError("offline")

    monkeypatch.setattr(collector.requests, "post", post, raising=False)
    result, errors = _stop_bridge_request(
        collector,
        (None, None, None, time.time()),
    )

    assert result[0] == 503 and errors == []
    assert collector.PENDING_ACTIVITY == [(pending, "active-token")]
    assert collector.CURRENT_COLLECTOR_TOKEN == "active-token"


def test_TC_CL_18_retry_after_lost_success_response_inserts_one_record(
    collector, monkeypatch, env
):
    user_client, user_id = env.make_user("collector-retry@example.com")
    token = user_client.post("/api/collector/token").get_json()["token"]
    api_client = appmod.app.test_client()

    monkeypatch.setattr(collector, "PENDING_ACTIVITY", [])
    monkeypatch.setattr(collector, "NEXT_RETRY_AT", 0.0)
    monkeypatch.setattr(collector, "CURRENT_COLLECTOR_TOKEN", token)
    monkeypatch.setattr(collector, "CURRENT_TASK_TYPE", "Coding")
    monkeypatch.setattr(collector, "CURRENT_TASK_DIFFICULTY", "Medium")

    class RequestError(Exception):
        pass

    monkeypatch.setattr(
        collector.requests,
        "exceptions",
        types.SimpleNamespace(RequestException=RequestError),
        raising=False,
    )
    attempts = []

    def post(url, **kwargs):
        response = api_client.post(
            "/api/activity",
            json=kwargs["json"],
            headers=kwargs["headers"],
        )
        attempts.append(response.status_code)
        assert response.status_code == 201
        if len(attempts) == 1:
            raise RequestError("simulated lost response after database commit")
        return response

    monkeypatch.setattr(collector.requests, "post", post, raising=False)
    collector.send_activity("VS Code", "Coding", 30, "Focused", flush=False)
    first_key = collector.PENDING_ACTIVITY[0][0]["idempotency_key"]

    collector.flush_pending_activities(force=True)
    assert len(collector.PENDING_ACTIVITY) == 1
    assert collector.PENDING_ACTIVITY[0][0]["idempotency_key"] == first_key

    collector.flush_pending_activities(force=True)
    assert collector.PENDING_ACTIVITY == []
    assert attempts == [201, 201]
    stored = env.query(
        "SELECT id, idempotency_key FROM activity WHERE user_id = %s",
        (user_id,),
    )
    assert len(stored) == 1
    assert stored[0]["idempotency_key"] == first_key
    activity_response = user_client.get("/api/activity")
    assert activity_response.status_code == 200
    assert "idempotency_key" not in activity_response.get_json()[0]
