"""
Read-only profile of the ProcrastiSense activity database for the project report.

  python scripts/dataset_profile.py --db backend/procrastisense.db [--json out.json]

The database is opened in SQLite read-only mode; nothing is written, changed or deleted.
User e-mail addresses and password hashes are never read - only numeric user ids appear.

Two views are produced, side by side:
  RAW       every row in the table, grouped by owner and source
  FILTERED  per user: source = 'realtime' (collector rows) and focus_level IN ('Focused','Distracted')
            (excludes manual rows, 'Unknown' and any other label)
Filtering is applied only to this report; the stored records are untouched.
"""
import argparse
import json
import sqlite3
import sys

LEGACY_HINT = {"Video / Streaming", "Entertainment / Social", "File Management", "AI Assistant Unknown"}


def q(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def profile(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out = {}
    out["total_rows"] = q(conn, "SELECT COUNT(*) n FROM activity")[0]["n"]
    out["span"] = q(conn, "SELECT MIN(timestamp) first, MAX(timestamp) last FROM activity")[0]
    out["raw_by_owner_source"] = q(conn, """
        SELECT COALESCE(CAST(user_id AS TEXT), 'NULL (pre-login, no owner)') AS owner, source,
               COUNT(*) AS rows, ROUND(SUM(duration_min),1) AS minutes,
               MIN(timestamp) AS first, MAX(timestamp) AS last
        FROM activity GROUP BY user_id, source ORDER BY user_id, source""")
    out["raw_focus_levels"] = q(conn, """
        SELECT focus_level, COUNT(*) AS rows, ROUND(SUM(duration_min),1) AS minutes
        FROM activity GROUP BY focus_level ORDER BY rows DESC""")
    cats = q(conn, """
        SELECT category, focus_level, COUNT(*) AS rows, ROUND(SUM(duration_min),1) AS minutes
        FROM activity GROUP BY category, focus_level ORDER BY rows DESC""")
    out["raw_category_by_focus_level"] = cats
    out["categories_seen_with_unknown_label"] = sorted({c["category"] for c in cats if c["focus_level"] == "Unknown"})
    out["categories_matching_legacy_names"] = sorted({c["category"] for c in cats if c["category"] in LEGACY_HINT})
    out["youtube_rows"] = q(conn, """
        SELECT application, category, focus_level, source, COUNT(*) AS rows
        FROM activity WHERE LOWER(application) LIKE '%youtube%'
        GROUP BY application, category, focus_level, source ORDER BY rows DESC""")
    users = [r["user_id"] for r in q(conn, "SELECT DISTINCT user_id FROM activity WHERE user_id IS NOT NULL ORDER BY 1")]
    filt = []
    for uid in users:
        r = q(conn, """
            SELECT ? AS user_id, COUNT(*) AS rows,
                   SUM(focus_level='Focused') AS focused_rows, SUM(focus_level='Distracted') AS distracted_rows,
                   ROUND(SUM(CASE WHEN focus_level='Focused' THEN duration_min ELSE 0 END),1) AS focused_min,
                   ROUND(SUM(CASE WHEN focus_level='Distracted' THEN duration_min ELSE 0 END),1) AS distracted_min,
                   MIN(timestamp) AS first, MAX(timestamp) AS last
            FROM activity WHERE user_id = ? AND source='realtime' AND focus_level IN ('Focused','Distracted')""",
                (uid, uid))[0]
        tot = (r["focused_min"] or 0) + (r["distracted_min"] or 0)
        r["focus_score_pct"] = round((r["focused_min"] or 0) / tot * 100, 1) if tot else None
        r["days_with_data"] = q(conn, """SELECT COUNT(DISTINCT substr(timestamp,1,10)) n FROM activity
                                         WHERE user_id=? AND source='realtime' AND focus_level IN ('Focused','Distracted')""", (uid,))[0]["n"]
        filt.append(r)
    out["filtered_per_user"] = filt
    conn.close()
    return out


def md_table(rows):
    if not rows:
        return "(none)\n"
    keys = list(rows[0].keys())
    lines = ["| " + " | ".join(keys) + " |", "|" + "|".join("---" for _ in keys) + "|"]
    lines += ["| " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    p = profile(a.db)
    print(f"Total activity rows: {p['total_rows']}   span: {p['span']['first']} -> {p['span']['last']}\n")
    print("RAW - rows by owner and source\n" + md_table(p["raw_by_owner_source"]))
    print("RAW - focus levels\n" + md_table(p["raw_focus_levels"]))
    print("RAW - category x focus level\n" + md_table(p["raw_category_by_focus_level"]))
    print("Categories carrying the 'Unknown' label:", p["categories_seen_with_unknown_label"])
    print("Categories matching known legacy names:", p["categories_matching_legacy_names"], "\n")
    print("YouTube rows\n" + md_table(p["youtube_rows"]))
    print("FILTERED - collector rows with Focused/Distracted only, per user\n" + md_table(p["filtered_per_user"]))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(p, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
