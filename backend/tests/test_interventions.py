import json
from datetime import datetime, timedelta
from conftest import row, appmod

BASE = datetime(2026, 11, 10, 8, 0)


def seq(spec):
    """spec: list of (application, category, minutes, level) -> consecutive rows with real timestamps."""
    out, t = [], BASE
    for app, cat, dur, lvl in spec:
        out.append(row(t.isoformat(timespec="minutes"), app, cat, dur, lvl))
        t += timedelta(minutes=max(1, int(round(dur))))
    return out


def ids(items):
    return [i["rule_id"] for i in items]


def calm_base():
    """Long focused runs, 6 one-minute distractions in 6 different apps: triggers no rule (hand-checked)."""
    spec = []
    for other in ("B", "C", "D", "E", "F", "G"):
        spec += [("A", "Coding", 7.5, "Focused")] * 4 + [(other, "Communication", 1, "Distracted")]
    return spec


def test_TC_IV_01_insufficient_data_returns_single_keep_tracking():
    """TC-IV-01: fewer than 20 tracked / 3 distraction records -> one 'Keep Tracking' item quoting the real counts."""
    rows = seq([("A", "Coding", 5, "Focused")] * 8 + [("B", "Communication", 1, "Distracted")] * 2)
    out = appmod.select_interventions(rows)
    assert ids(out) == ["insufficient_data"] and "found 10 and 2" in out[0]["reason"]


def test_TC_IV_02_unknown_and_idle_records_do_not_count():
    """TC-IV-02: Unknown/Idle records are not counted towards the sufficiency threshold."""
    rows = seq([("A", "Coding", 5, "Focused")] * 5 + [("B", "Other", 1, "Unknown")] * 30 + [("C", "X", 1, "Idle")] * 5)
    assert ids(appmod.select_interventions(rows)) == ["insufficient_data"]


def test_TC_IV_03_calm_history_triggers_no_rule():
    """TC-IV-03: sufficient data but no condition met -> single 'No Strong Pattern Detected' item."""
    out = appmod.select_interventions(seq(calm_base()))
    assert ids(out) == ["no_pattern"]


def test_TC_IV_04_remove_distraction_share_threshold():
    """TC-IV-04: top app >= 30 % of distracted minutes (min 5 min) triggers; equal split of 4 apps does not."""
    heavy = calm_base() + [("WhatsApp", "Communication", 2, "Distracted")] * 3        # 6 of 12 min = 50 %
    out = appmod.select_interventions(seq(heavy))
    rd = [i for i in out if i["rule_id"] == "remove_distraction"]
    assert rd and "WhatsApp" in rd[0]["description"] and "50%" in rd[0]["reason"] and "6.0 of 12.0 min" in rd[0]["reason"]
    split = seq([("A", "Coding", 7.5, "Focused")] * 20 +
                [("B", "X", 2, "Distracted"), ("C", "X", 2, "Distracted"), ("D", "X", 2, "Distracted"), ("E", "X", 2, "Distracted")])
    assert "remove_distraction" not in ids(appmod.select_interventions(split))   # 25 % each


def test_TC_IV_05_remove_distraction_needs_minimum_minutes():
    """TC-IV-05: even a 100 % share does not trigger with fewer than 5 distracted minutes."""
    rows = seq([("A", "Coding", 7.5, "Focused")] * 20 + [("WhatsApp", "Communication", 1, "Distracted")] * 4)
    assert "remove_distraction" not in ids(appmod.select_interventions(rows))


def _with_distractions(rows):
    """Prepend 4 distraction records so the sufficiency check passes without changing the latest-12 window."""
    pre = [row("2026-11-09T07:%02d" % i, "W%d" % i, "Communication", 1, "Distracted") for i in range(4)]
    return pre + rows


def _changes(rows):
    return sum(1 for i in range(1, len(rows)) if rows[i - 1]["application"] != rows[i]["application"])


def test_TC_IV_06_reduce_switching_threshold():
    """TC-IV-06: 11 app changes in the latest 12 records triggers; exactly 7 does not; a steady window does not."""
    alt12 = [("A" if i % 2 else "B", "X", 1, "Focused") for i in range(12)]
    busy = seq([("A", "Coding", 1, "Focused")] * 10 + alt12)
    assert _changes(busy[-12:]) == 11
    out = appmod.select_interventions(_with_distractions(busy))
    sw = [i for i in out if i["rule_id"] == "reduce_switching"]
    assert sw and "11 application changes" in sw[0]["reason"]

    seven = seq([("A", "Coding", 1, "Focused")] * 20 +
                [(a, "X", 1, "Focused") for a in ("A", "B", "A", "B", "A", "B", "A", "B", "B", "B", "B", "B")])
    assert _changes(seven[-12:]) == 7                      # fixture check: one below the threshold of 8
    assert "reduce_switching" not in ids(appmod.select_interventions(_with_distractions(seven)))

    steady = seq([("A", "Coding", 1, "Focused")] * 30)
    assert "reduce_switching" not in ids(appmod.select_interventions(_with_distractions(steady)))


def test_TC_IV_07_focus_sprint_length_from_average_run():
    """TC-IV-07: runs 12,12,12,12,16 average 12.8 -> '13-minute' sprint; averages >= 25 min give no sprint."""
    spec = []
    for _ in range(4):
        spec += [("A", "Coding", 12, "Focused"), ("B", "Communication", 1, "Distracted")]
    spec += [("A", "Coding", 1, "Focused")] * 16
    out = appmod.select_interventions(seq(spec))
    fs = [i for i in out if i["rule_id"] == "focus_sprint"]
    assert fs and "13-minute" in fs[0]["description"] and "12.8 min across 5 runs" in fs[0]["reason"]

    long_spec = []
    for _ in range(4):
        long_spec += [("A", "Coding", 30, "Focused"), ("B", "Communication", 1, "Distracted")]
    long_spec += [("A", "Coding", 30, "Focused")] * 2
    assert "focus_sprint" not in ids(appmod.select_interventions(seq(long_spec)))


def test_TC_IV_08_sprint_clamped_to_minimum_five():
    """TC-IV-08: very short runs give a 5-minute sprint (lower clamp)."""
    spec = []
    for _ in range(8):
        spec += [("A", "Coding", 1, "Focused"), ("B", "Communication", 1, "Distracted")]
    spec += [("A", "Coding", 1, "Focused")] * 6
    out = appmod.select_interventions(seq(spec))
    fs = [i for i in out if i["rule_id"] == "focus_sprint"][0]
    assert "5-minute" in fs["description"]


def test_TC_IV_09_risky_hour_rule():
    """TC-IV-09: 5 of 8 distraction records in one hour triggers; spread-out distractions do not."""
    focus = [row("2026-11-10T09:%02d" % i, "A", "Coding", 7.5, "Focused") for i in range(20)]
    clustered = [row("2026-11-10T10:%02d" % (i * 5), "W", "Communication", 1, "Distracted") for i in range(5)] + \
                [row("2026-11-10T%02d:30" % h, "W", "Communication", 1, "Distracted") for h in (13, 14, 15)]
    out = appmod.select_interventions(sorted(focus + clustered, key=lambda r: r["timestamp"]))
    rh = [i for i in out if i["rule_id"] == "risky_hour"]
    assert rh and "5 of your 8" in rh[0]["reason"] and "10:00 and 11:00" in rh[0]["reason"]
    spread = [row("2026-11-10T%02d:30" % h, "W", "Communication", 1, "Distracted") for h in (10, 11, 12, 13, 14, 15, 16, 17)]
    assert "risky_hour" not in ids(appmod.select_interventions(sorted(focus + spread, key=lambda r: r["timestamp"])))


def test_TC_IV_10_micro_break_on_high_risk_or_long_streak():
    """TC-IV-10: Micro Break appears for a HIGH prediction; absent for LOW risk with zero streak."""
    high = [row("2026-11-10T09:%02d" % i, "A" if i % 2 else "B", "X", 1, "Focused" if i % 2 else "Distracted") for i in range(24)]
    out = appmod.select_interventions(high)
    mb = [i for i in out if i["rule_id"] == "micro_break"]
    assert mb and "HIGH" in mb[0]["reason"]
    assert "micro_break" not in ids(appmod.select_interventions(seq(calm_base())))


def test_TC_IV_11_only_verified_inputs_no_difficulty_or_notification_claims():
    """TC-IV-11: no output mentions task difficulty or notifications (not used by the rules)."""
    datasets = [seq(calm_base()), seq(calm_base() + [("WhatsApp", "Communication", 2, "Distracted")] * 3)]
    for d in datasets:
        text = json.dumps(appmod.select_interventions(d)).lower()
        assert "difficult" not in text and "notification" not in text


def test_TC_IV_12_ranked_by_priority_and_capped():
    """TC-IV-12: results are sorted by priority (desc) and capped at 4."""
    high = [row("2026-11-10T10:%02d" % i, "W" if i % 2 else "B", "Communication", 1, "Focused" if i % 2 else "Distracted")
            for i in range(24)]
    out = appmod.select_interventions(high)
    pr = [i["priority"] for i in out]
    assert pr == sorted(pr, reverse=True) and len(out) <= 4 and len(out) >= 2


def test_TC_IV_13_route_uses_only_collector_rows_and_own_user(env):
    """TC-IV-13: /api/interventions ignores 'manual' rows and other users' rows."""
    a, ua = env.make_user("a@x.com")
    b, ub = env.make_user("b@x.com")
    heavy = [("2026-11-10T09:%02d:00" % i, "A", "Coding", 7.5, "Focused") for i in range(20)] + \
            [("2026-11-10T10:%02d:00" % i, "WhatsApp", "Communication", 2, "Distracted") for i in range(3)]
    env.insert_rows(ua, heavy, source="manual")
    env.insert_rows(ub, heavy, source="realtime")
    ra = a.get("/api/interventions").get_json()
    assert [i["rule_id"] for i in ra] == ["insufficient_data"]
    rb = b.get("/api/interventions").get_json()
    assert "remove_distraction" in [i["rule_id"] for i in rb]


def test_TC_IV_14_high_risk_micro_break_survives_the_cap_and_ranks_first():
    """TC-IV-14: when all five rules fire, the 4-item cap must not drop a HIGH-risk Micro Break; it ranks first."""
    five = [row("2026-11-10T09:%02d" % i, "A" if i % 2 else "B", "X", 1, "Focused" if i % 2 else "Distracted") for i in range(24)]
    full = appmod.select_interventions(five)
    assert len(full) == 4 and full[0]["rule_id"] == "micro_break"
