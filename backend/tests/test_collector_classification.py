"""Collector classification tests.

The collector imports Windows-only modules (win32gui, win32process, winotify, psutil) at the top of the file,
so they are replaced by stubs here. These tests therefore exercise ONLY the pure classification functions
(classify_application, get_activity_name). They do NOT test foreground-window capture, process lookup,
the local bridge, timing or toast notifications - those must be tested on Windows.
"""
import importlib.util
import os
import sys
import types

import pytest

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
