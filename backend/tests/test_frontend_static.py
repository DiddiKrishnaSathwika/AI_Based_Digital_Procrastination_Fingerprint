"""Static and Node-based checks of the frontend files (no browser is available, so rendering is checked
with a minimal DOM stub; visual appearance is NOT tested here)."""
import json
import os
import re
import shutil
import subprocess

import pytest

FRONT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")
HTML = open(os.path.join(FRONT, "index.html"), encoding="utf-8").read()
JS = open(os.path.join(FRONT, "app.js"), encoding="utf-8").read()
NODE = shutil.which("node")


def privacy_section():
    a = HTML.index('id="page-privacy"')
    return HTML[a:HTML.index("</section>", a)]


def test_TC_UI_01_privacy_page_has_no_unimplemented_claims():
    """TC-UI-01: privacy text does not claim deletion or idle-time tracking is unavailable."""
    p = privacy_section().lower()
    for bad in ("export and deletion at any time", "explicit opt-in consent", "only consented real-time",
                "<li>idle time</li>", "private content"):
        assert bad not in p, bad
    assert "● enabled" not in p


def test_TC_UI_02_privacy_page_states_actual_behaviour_and_gaps():
    """TC-UI-02: privacy page lists actual collection, deletion controls, and remaining gaps."""
    p = privacy_section()
    for needed in ("Start Focus Session", "Window titles are read", "not saved to the database",
                   "Data export and a consent dialog are not implemented", "Delete Account",
                   "Confirm your password", "activity history", "Task type and difficulty you selected",
                   "marked as manual", "PostgreSQL"):
        assert needed in p, needed
    assert "Keystrokes" in p and "Screenshots" in p and "Passwords" in p


def test_TC_UI_03_landing_page_claims_corrected():
    """TC-UI-03: landing page accurately describes account deletion and other limitations."""
    low = HTML.lower()
    assert "user-controlled data deletion" not in low
    assert "monitoring consented activity" not in low
    assert "notification control" not in low
    assert "data export is not available" in low


def test_TC_UI_04_no_removed_intervention_titles_in_js():
    """TC-UI-04: removed intervention titles are no longer referenced by the frontend."""
    assert "Task Decomposition" not in JS and "Notification Control" not in JS
    assert "improvement_pct" not in JS


@pytest.mark.node
@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_TC_UI_05_app_js_syntax():
    """TC-UI-05: app.js parses without syntax errors (node --check)."""
    r = subprocess.run([NODE, "--check", os.path.join(FRONT, "app.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def _extract(name, kind="function"):
    m = re.search(rf"^(async )?function {name}\(.*?^\}}", JS, re.S | re.M)
    assert m, name
    return m.group(0)


def _run_js(fn_name, payload):
    script = f"""
const store = {{}};
const document = {{ getElementById: id => ({{ set innerHTML(v) {{ store[id] = v; }}, classList: {{ add() {{}} }} }}) }};
const API = "";
const fetch = (u) => Promise.resolve({{ json: () => ({json.dumps(payload)}) }});
{_extract('fmtMin')}
{_extract(fn_name)}
(async () => {{ await {fn_name}(); console.log(JSON.stringify(store)); }})();
"""
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _run_fingerprint(fp_payload, activity_payload, fingerprint_status=200, activity_status=200):
    responses = [
        {"ok": fingerprint_status == 200, "status": fingerprint_status, "payload": fp_payload},
        {"ok": activity_status == 200, "status": activity_status, "payload": activity_payload},
    ]
    script = f"""
const values = {{}};
const elements = {{}};
const makeElement = (tagName, id = null) => {{
  const element = {{
    tagName,
    className: "",
    style: {{}},
    children: [],
    append(...children) {{ this.children.push(...children); }},
    replaceChildren(...children) {{
      this.children = children;
      if (id) values[id + ":children"] = children.map(serialize);
    }}
  }};
  Object.defineProperty(element, "textContent", {{
    set(value) {{
      this._textContent = String(value);
      this.children = [];
      if (id) values[id + ":text"] = this._textContent;
    }},
    get() {{ return this._textContent || ""; }}
  }});
  Object.defineProperty(element, "innerHTML", {{
    set(value) {{
      this._innerHTML = String(value);
      if (id) values[id + ":html"] = this._innerHTML;
    }},
    get() {{ return this._innerHTML || ""; }}
  }});
  return element;
}};
const serialize = element => ({{
  tagName: element.tagName,
  className: element.className,
  textContent: element.textContent,
  children: element.children.map(serialize)
}});
const document = {{
  getElementById(id) {{
    return elements[id] ||= makeElement("div", id);
  }},
  createElement: tagName => makeElement(tagName)
}};
const responses = {json.dumps(responses)};
const activityRows = responses[1].payload;
const fetch = async url => {{
  const response = responses.shift();
  return {{ ok: response.ok, status: response.status, json: async () => response.payload }};
}};
const showToast = message => {{ values.toast = message; }};
const console = {{ error: (...args) => {{ values.error = args.map(String).join(" "); }} }};
const API = "";
{_extract("drawFingerprintRing")}
{_extract("loadFingerprint")}
(async () => {{
  await loadFingerprint();
  values.draw = {{
    id: "fingerprint-viz",
    rows: activityRows,
    size: 300,
    html: elements["fingerprint-viz"].innerHTML
  }};
  process.stdout.write(JSON.stringify(values));
}})().catch(error => {{ process.stderr.write(String(error)); process.exitCode = 1; }});
"""
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.node
@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_TC_UI_06_weekly_modal_renders_comparison_and_unavailable_and_empty():
    """TC-UI-06: the weekly-report modal renders (a) a real change, (b) 'Not available', (c) the no-data message."""
    base = {"has_data": True, "total_focus_time_min": 61, "total_distraction_time_min": 14, "avg_focus_session_min": 0.3,
            "distraction_events": 25, "most_distracting_category": "Communication", "best_day": "2026-11-13",
            "worst_day": "2026-11-10", "label": "Real-Time Activity Data"}
    ok = _run_js("openReport", {**base, "comparison_available": True, "focus_score_change_pp": 4.5,
                                "current_focus_score": 70.0, "previous_focus_score": 65.5, "comparison_note": ""})
    assert "+4.5 percentage points" in ok["report-body"] and "70" in ok["report-body"] and "1h 1m" in ok["report-body"]
    na = _run_js("openReport", {**base, "comparison_available": False, "focus_score_change_pp": None,
                                "comparison_note": "Previous-week comparison unavailable: test."})
    assert "Not available" in na["report-body"] and "undefined" not in na["report-body"] and "null" not in na["report-body"]
    empty = _run_js("openReport", {"has_data": False, "comparison_note": "No activity was recorded in the last 7 days.",
                                   "label": "Real-Time Activity Data"})
    assert "No activity was recorded" in empty["report-body"]
    nobest = _run_js("openReport", {**base, "best_day": None, "worst_day": None, "comparison_available": False,
                                    "comparison_note": "x"})
    assert "Needs at least 2 days" in nobest["report-body"]


@pytest.mark.node
@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_TC_UI_07_interventions_render_reasons_with_evidence():
    """TC-UI-07: intervention cards render title, description and the evidence string."""
    out = _run_js("loadInterventions", [{"rule_id": "remove_distraction", "title": "Remove Distraction",
                                         "description": "Temporarily close or block WhatsApp.",
                                         "reason": "WhatsApp accounts for 50% of your recorded distracted time.", "priority": 0.5}])
    html = out["interv-grid"]
    assert "Remove Distraction" in html and "block WhatsApp" in html and "50%" in html


def test_TC_UI_08_no_demo_or_synthetic_labels_in_frontend():
    """TC-UI-08: no 'Synthetic' / 'demo_mode' / 'for demo purposes' text remains in the frontend files."""
    for name, text in (("index.html", HTML), ("app.js", JS)):
        low = text.lower()
        assert "synthetic" not in low, name
        assert "demo_mode" not in low, name
        assert "demo purposes" not in low, name


def test_TC_UI_09_ml_pipeline_page_and_privacy_mode_removed():
    """TC-UI-09: the unreachable ML Pipeline page and its script are gone; 'Privacy Mode' wording is gone."""
    for needle in ("ML Pipeline", "page-ml", "loadMLPage", "PIPELINE_STAGES", "MODELS", "temporal-demo"):
        assert needle not in HTML and needle not in JS, needle
    assert "Privacy Mode" not in HTML
    assert "What the Collector Records" in privacy_section()
    assert "not part of the current implementation" in HTML          # prediction page footer


def test_TC_UI_10_every_element_id_used_by_js_exists_and_nav_pages_have_sections():
    """TC-UI-10: no dangling getElementById() targets, and every sidebar page has a matching section."""
    html_ids = set(re.findall(r'\bid="([^"]+)"', HTML))
    js_created = set(re.findall(r'\bid="([^"$]+)"', JS))
    used = set(re.findall(r'getElementById\(\s*["\']([^"\']+)["\']\s*\)', JS))
    assert used, "no getElementById calls found"
    assert sorted(i for i in used if i not in html_ids and i not in js_created) == []
    pages = re.findall(r'\{ id: "(\w+)",\s+label', JS)
    assert len(pages) == 8
    for p in pages:
        assert f'id="page-{p}"' in HTML, p


def test_TC_UI_11_break_message_is_accurate():
    """TC-UI-11: the 'Take a break' message no longer claims the session is paused or a demo."""
    assert "keeps running and the collector keeps recording" in JS


def test_TC_UI_12_email_auth_forms_removed_and_toast_visible():
    """Retired email forms are absent, and authentication feedback is outside the hidden app."""
    for needle in ("forgot-form", "reset-form", "Forgot Password?", "register-confirm-password"):
        assert needle not in HTML, needle
    for needle in ("requestPasswordReset", "forgot-password", "reset-password"):
        assert needle not in JS, needle
    assert HTML.index('id="toast"') < HTML.index('id="app"')
    assert 'id="delete-account-form"' in HTML


@pytest.mark.node
@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_TC_UI_13_fingerprint_handles_empty_null_and_missing_window():
    empty = {
        "typical_focus_duration_min": None,
        "typical_distraction_window": None,
        "app_switching_pattern": "Insufficient data",
        "most_frequent_distraction": "Insufficient data",
        "most_risky_task": "Insufficient data",
        "most_risky_time": "Insufficient data",
        "average_recovery_time_min": None,
        "narrative": "No activity recorded.",
        "label": "Insufficient real-time activity data",
    }

    for window in (None, "unexpected"):
        payload = {**empty, "typical_distraction_window": window}
        result = _run_fingerprint(payload, [])
        metric_text = [child["textContent"] for tile in result["fp-metrics:children"]
                       for child in tile["children"]]
        assert "TYPICAL DISTRACTION WINDOW" in metric_text
        assert "Insufficient data" in metric_text
        assert result["draw"]["rows"] == []

    missing = {key: value for key, value in empty.items()
               if key != "typical_distraction_window"}
    result = _run_fingerprint(missing, [])
    metric_text = [child["textContent"] for tile in result["fp-metrics:children"]
                   for child in tile["children"]]
    assert "Insufficient data" in metric_text


@pytest.mark.node
@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_TC_UI_14_fingerprint_displays_recorded_window_and_activity():
    activities = [{
        "application": "VS Code",
        "duration_min": 6,
        "focus_level": "Focused",
    }]
    result = _run_fingerprint({
        "typical_focus_duration_min": 6,
        "typical_distraction_window": [6, 11],
        "app_switching_pattern": "Low",
        "most_frequent_distraction": "Insufficient data",
        "most_risky_task": "Insufficient data",
        "most_risky_time": "Insufficient data",
        "average_recovery_time_min": None,
        "narrative": "Recorded focused activity.",
        "label": "Generated from Real-Time Activity Data",
    }, activities)

    metric_text = [child["textContent"] for tile in result["fp-metrics:children"]
                   for child in tile["children"]]
    assert "6" in metric_text[3] and "11 min" in metric_text[3]
    assert result["draw"]["rows"] == activities
    assert result["fp-narrative:text"] == "Recorded focused activity."


@pytest.mark.node
@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_TC_UI_16_fingerprint_escapes_malicious_activity_values():
    malicious = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    result = _run_fingerprint({
        "typical_focus_duration_min": 6,
        "typical_distraction_window": [6, 11],
        "app_switching_pattern": "Low",
        "most_frequent_distraction": malicious,
        "most_risky_task": "High",
        "most_risky_time": "12:00 - 14:00",
        "average_recovery_time_min": None,
        "narrative": "Recorded activity.",
        "label": "Generated from Real-Time Activity Data",
    }, [{
        "application": malicious,
        "duration_min": 6,
        "focus_level": "Distracted",
    }])

    metric_text = [child["textContent"] for tile in result["fp-metrics:children"]
                   for child in tile["children"]]
    assert malicious in metric_text
    assert "<img" not in result["draw"]["html"]
    assert "<script>" not in result["draw"]["html"]
    assert "&lt;img" in result["draw"]["html"]
    assert "&lt;script&gt;" in result["draw"]["html"]
    assert "fp-metrics:html" not in result


@pytest.mark.node
@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_TC_UI_15_fingerprint_api_failure_is_reported_without_rejection():
    result = _run_fingerprint({}, [], fingerprint_status=503)

    assert result["toast"] == "Unable to load fingerprint data. Please try again."
    assert result["fp-narrative:text"] == "Fingerprint data could not be loaded."
    assert "HTTP 503" in result["error"]
