import inspect
from datetime import datetime, timedelta
from conftest import row, appmod

NOW = datetime(2026, 11, 13, 12, 0)


def ts(days_ago, minutes=0):
    return (NOW - timedelta(days=days_ago, minutes=minutes)).isoformat(timespec="seconds")


def rows_for(cur_f, cur_d, prev_f, prev_d):
    out = []
    if cur_f: out.append(row(ts(2), "VS Code", "Coding", cur_f, "Focused"))
    if cur_d: out.append(row(ts(2, -1), "WhatsApp", "Communication", cur_d, "Distracted"))
    if prev_f: out.append(row(ts(9), "VS Code", "Coding", prev_f, "Focused"))
    if prev_d: out.append(row(ts(9, -1), "WhatsApp", "Communication", prev_d, "Distracted"))
    return sorted(out, key=lambda r: r["timestamp"])


def test_TC_WK_01_change_is_genuine_hand_computed():
    """TC-WK-01: current 30F/10D (75.0 %) vs previous 20F/20D (50.0 %) gives +25.0 percentage points."""
    r = appmod.build_weekly_report(rows_for(30, 10, 20, 20), NOW)
    assert r["comparison_available"] is True
    assert r["current_focus_score"] == 75.0 and r["previous_focus_score"] == 50.0
    assert r["focus_score_change_pp"] == 25.0


def test_TC_WK_02_negative_change():
    """TC-WK-02: a decline is reported as a negative number."""
    r = appmod.build_weekly_report(rows_for(10, 30, 30, 10), NOW)
    assert r["focus_score_change_pp"] == -50.0


def test_TC_WK_03_previous_week_missing_is_unavailable():
    """TC-WK-03: no previous-week data -> comparison unavailable with an explanatory note, no number."""
    r = appmod.build_weekly_report(rows_for(30, 10, 0, 0), NOW)
    assert r["has_data"] is True and r["comparison_available"] is False
    assert r["focus_score_change_pp"] is None and r["previous_focus_score"] is None
    assert "Previous-week comparison unavailable" in r["comparison_note"]
    assert r["total_focus_time_min"] == 30            # the current-week summary is still reported


def test_TC_WK_04_previous_week_below_threshold():
    """TC-WK-04: 7 tracked minutes in the previous week (< 10) is not enough to compare."""
    r = appmod.build_weekly_report(rows_for(30, 10, 4, 3), NOW)
    assert r["comparison_available"] is False and r["focus_score_change_pp"] is None


def test_TC_WK_05_current_week_below_threshold():
    """TC-WK-05: too little current-week data -> unavailable, note refers to the last 7 days."""
    r = appmod.build_weekly_report(rows_for(4, 3, 20, 20), NOW)
    assert r["comparison_available"] is False and "last 7 days" in r["comparison_note"]


def test_TC_WK_06_no_current_data_has_no_fallback_to_old_rows():
    """TC-WK-06: with nothing in the last 7 days the report is empty (old rows are NOT shown as 'last 7 days')."""
    old = [row(ts(20), "VS Code", "Coding", 30, "Focused"), row(ts(20, -1), "X", "Other", 5, "Distracted")]
    r = appmod.build_weekly_report(old, NOW)
    assert r["has_data"] is False and r["total_focus_time_min"] == 0
    assert r["most_distracting_category"] is None and r["focus_score_change_pp"] is None
    assert appmod.build_weekly_report([], NOW)["has_data"] is False


def test_TC_WK_07_period_boundary_minute_precision():
    """TC-WK-07: a row stamped exactly at now-7d belongs to the current week; one minute earlier to the previous."""
    edge = (NOW - timedelta(days=7)).isoformat(timespec="minutes")
    before = (NOW - timedelta(days=7, minutes=1)).isoformat(timespec="minutes")
    r = appmod.build_weekly_report([row(before, "A", "X", 12, "Focused"), row(edge, "B", "X", 3, "Focused")], NOW)
    assert r["total_focus_time_min"] == 3


def test_TC_WK_08_result_is_deterministic_and_not_random():
    """TC-WK-08: repeated calls give identical output and the function does not use random."""
    rows = rows_for(30, 10, 20, 20)
    assert appmod.build_weekly_report(rows, NOW) == appmod.build_weekly_report(rows, NOW)
    assert "random" not in inspect.getsource(appmod.build_weekly_report)


def test_TC_WK_09_best_worst_day_rules():
    """TC-WK-09: best/worst need >= 2 days with >= 5 tracked min; tiny days are ignored."""
    day_a = [row(ts(1), "A", "Coding", 9, "Focused"), row(ts(1, -1), "B", "Other", 1, "Distracted")]    # 90 %
    day_b = [row(ts(2), "A", "Coding", 2, "Focused"), row(ts(2, -1), "B", "Other", 8, "Distracted")]    # 20 %
    tiny = [row(ts(3), "A", "Coding", 1, "Distracted")]                                                 # 1 min -> ignored
    r = appmod.build_weekly_report(sorted(day_a + day_b + tiny, key=lambda x: x["timestamp"]), NOW)
    assert r["best_day"] == ts(1)[:10] and r["worst_day"] == ts(2)[:10]
    one_day = appmod.build_weekly_report(day_a + tiny, NOW)
    assert one_day["best_day"] is None and one_day["worst_day"] is None


def test_TC_WK_10_most_distracting_category_by_minutes_or_none():
    """TC-WK-10: category with most distracted minutes wins; none recorded -> None (no default label)."""
    rows = [row(ts(1), "W", "Communication", 2, "Distracted"), row(ts(1, -1), "Y", "Entertainment", 5, "Distracted"),
            row(ts(1, -2), "V", "Coding", 9, "Focused")]
    assert appmod.build_weekly_report(rows, NOW)["most_distracting_category"] == "Entertainment"
    only_focus = [row(ts(1), "V", "Coding", 9, "Focused")]
    assert appmod.build_weekly_report(only_focus, NOW)["most_distracting_category"] is None


def test_TC_WK_11_route_end_to_end_and_user_isolation(env):
    """TC-WK-11: /api/weekly-report computes from the caller's own rows only."""
    now = datetime.now()
    def t(d, m=0): return (now - timedelta(days=d, minutes=m)).isoformat(timespec="seconds")
    a, ua = env.make_user("a@x.com")
    b, ub = env.make_user("b@x.com")
    env.insert_rows(ua, [(t(1), "VS Code", "Coding", 30, "Focused"), (t(1, -1), "WhatsApp", "Communication", 10, "Distracted"),
                         (t(9), "VS Code", "Coding", 20, "Focused"), (t(9, -1), "WhatsApp", "Communication", 20, "Distracted")])
    env.insert_rows(ub, [(t(1), "X", "Other", 99, "Focused")])
    ra = a.get("/api/weekly-report").get_json()
    assert ra["comparison_available"] is True and ra["focus_score_change_pp"] == 25.0
    rb = b.get("/api/weekly-report").get_json()
    assert rb["comparison_available"] is False and rb["total_focus_time_min"] == 99
    assert "improvement_pct" not in ra
