import pytest
from conftest import row, appmod

FIX_LOW = [  # hand-computed: runs [15, 4] avg 9.5, streak 4, ratio 5/24, 2 switches -> 41 LOW, window [6, 11]
    row("2026-11-10T10:00", "A", "Coding", 10, "Focused"),
    row("2026-11-10T10:10", "A", "Coding", 5, "Focused"),
    row("2026-11-10T10:15", "B", "Communication", 5, "Distracted"),
    row("2026-11-10T10:20", "A", "Coding", 4, "Focused"),
]


def test_TC_AN_01_compute_metrics_hand_computed():
    """TC-AN-01: focus/distraction minutes, average focus record, switches and score."""
    rows = [row("t", "A", "Coding", 10, "Focused"), row("t", "A", "Coding", 5, "Focused"),
            row("t", "B", "Communication", 5, "Distracted")]
    m = appmod.compute_metrics(rows)
    assert (m["focus_time"], m["distract_time"], m["distractions"]) == (15, 5, 1)
    assert m["avg_focus"] == 7.5 and m["switches"] == 2 and m["focus_score"] == 75
    assert appmod.compute_metrics([])["focus_score"] == 0


def test_TC_AN_02_prediction_empty_input():
    """TC-AN-02: prediction with no rows reports NO DATA."""
    p = appmod.predict_distraction([])
    assert p["risk_level"] == "NO DATA" and p["distraction_probability"] is None


def test_TC_AN_03_prediction_low_hand_computed():
    """TC-AN-03: prediction probability and window match the hand calculation (41 %, LOW, [6, 11])."""
    p = appmod.predict_distraction(FIX_LOW)
    assert p["distraction_probability"] == 41 and p["risk_level"] == "LOW"
    assert p["predicted_window_min"] == [6, 11] and p["confidence"] is None
    assert any("not a trained ML model" in f for f in p["factors"])


def test_TC_AN_04_prediction_moderate_and_high_classes():
    """TC-AN-04: alternating, switch-heavy histories reach MODERATE (56 %) and HIGH (82 %)."""
    def alt(first, n=12):
        rows = []
        for i in range(n):
            f = (i % 2 == 0) == (first == "F")
            rows.append(row(f"2026-11-10T10:{i:02d}", "A" if i % 2 else "B", "X", 1, "Focused" if f else "Distracted"))
        return rows
    moderate = appmod.predict_distraction(alt("F"))     # ends on a Distracted record -> streak 0
    high = appmod.predict_distraction(alt("D"))         # ends on a Focused record
    assert (moderate["distraction_probability"], moderate["risk_level"]) == (56, "MODERATE")
    assert (high["distraction_probability"], high["risk_level"]) == (82, "HIGH")


def test_TC_AN_05_prediction_is_clamped_to_5_95():
    """TC-AN-05: probability stays within 5..95."""
    rows = [row(f"2026-11-10T10:{i:02d}", "A" if i % 2 else "B", "X", 5, "Distracted") for i in range(12)]
    p = appmod.predict_distraction(rows)["distraction_probability"]
    assert 5 <= p <= 95


def test_TC_AN_06_fingerprint_fields_hand_computed():
    """TC-AN-06: fingerprint most-frequent distraction, productive/distracted minutes and risky hour."""
    fp = appmod.build_fingerprint(FIX_LOW)
    assert fp["most_frequent_distraction"] == "Communication"
    assert fp["productive_time_min"] == 19.0 and fp["distracted_time_min"] == 5.0
    assert fp["most_risky_time"].startswith("10:00")
    assert "not verified attention" in fp["narrative"]


def test_TC_AN_07_fingerprint_merges_focus_across_distraction_KNOWN_BEHAVIOUR():
    """TC-AN-07 (characterisation): fingerprint does NOT end a focus session at a Distracted record,
    so F10, D1, F10 gives a 20-min 'session', whereas the prediction treats it as two runs of 10 min."""
    rows = [row("2026-11-10T10:00", "VS Code", "Coding", 10, "Focused"),
            row("2026-11-10T10:10", "WhatsApp", "Communication", 1, "Distracted"),
            row("2026-11-10T10:11", "VS Code", "Coding", 10, "Focused")]
    assert appmod.build_fingerprint(rows)["typical_focus_duration_min"] == 20.0
    from conftest import appmod as a
    runs, _ = a._focus_runs(rows)
    assert runs == [10.0, 10.0]


def test_TC_AN_08_analytics_route_values(env):
    """TC-AN-08: analytics route returns category minutes, hourly distraction counts and focus buckets."""
    c, uid = env.make_user()
    env.insert_rows(uid, [
        ("2026-11-10T10:00:00", "VS Code", "Coding", 12, "Focused"),
        ("2026-11-10T10:12:00", "YouTube", "Entertainment", 3, "Distracted"),
        ("2026-11-10T11:00:00", "WhatsApp", "Communication", 2, "Distracted"),
        ("2026-11-11T09:00:00", "VS Code", "Coding", 4, "Focused"),
    ])
    a = c.get("/api/analytics").get_json()
    cats = {x["category"]: x["minutes"] for x in a["category_usage"]}
    assert cats == {"Coding": 16, "Entertainment": 3, "Communication": 2}
    hours = {x["hour"]: x["events"] for x in a["distraction_by_hour"]}
    assert hours["10"] == 1 and hours["11"] == 1 and sum(hours.values()) == 2
    buckets = {x["bucket"]: x["count"] for x in a["focus_distribution"]}
    assert buckets["0-10"] == 1 and buckets["10-20"] == 1
    assert {x["date"]: x["switches"] for x in a["switching_frequency"]} == {"11-10": 3, "11-11": 1}


def test_TC_AN_09_score_definitions_differ_between_pages_KNOWN_BEHAVIOUR(env):
    """TC-AN-09 (characterisation): the analytics daily focus score divides by ALL minutes (incl. Unknown),
    the dashboard focus score divides by Focused+Distracted minutes only."""
    c, uid = env.make_user()
    today = appmod.datetime.now().strftime("%Y-%m-%d")
    env.insert_rows(uid, [
        (f"{today}T09:00:00", "A", "Coding", 6, "Focused"),
        (f"{today}T09:06:00", "B", "Communication", 2, "Distracted"),
        (f"{today}T09:08:00", "C", "Other", 2, "Unknown"),
    ])
    dash = c.get("/api/dashboard").get_json()["focus_score"]
    daily = c.get("/api/analytics").get_json()["daily_trend"][0]["productivity"]
    assert dash == 75      # 6 / (6+2)
    assert daily == 60     # 6 / (6+2+2)


def test_TC_AN_10_dashboard_uses_todays_rows_else_last_40(env):
    """TC-AN-10: dashboard summarises today's rows, falling back to the last 40 records."""
    c, uid = env.make_user()
    env.insert_rows(uid, [("2026-11-01T10:00:00", "A", "Coding", 8, "Focused"),
                          ("2026-11-01T10:08:00", "B", "Communication", 2, "Distracted")])
    d = c.get("/api/dashboard").get_json()
    assert d["focus_score"] == 80 and d["distractions"] == 1
