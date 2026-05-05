"""
Migration: fix 2026_district shared_code grouping errors.

Run once on any machine whose DB has not yet received these changes:
    python migrations/fix_2026_district_grouping.py
"""
import os
import sqlite3

DB_FILE = os.environ.get("UIL_CS_DB_FILE", "uil_cs_questions_v2.db")


def run(conn):
    updates = [
        # Q4/Q5: un-group (two unrelated questions falsely merged on same page)
        ("single", "2026_2026_district_p3_q4", "", 2554),
        ("single", "2026_2026_district_p3_q5", "", 2555),
        # Q10/Q11: un-group (array code vs file I/O, unrelated)
        ("single", "2026_2026_district_p5_q10", "", 2560),
        ("single", "2026_2026_district_p5_q11", "", 2561),
        # Q15/Q16: de-group from Q17-19 (both are standalone questions)
        ("single", "2026_2026_district_p6_q15", "", 2565),
        ("single", "2026_2026_district_p6_q16", "", 2566),
        # Q17/Q18/Q19: new group_id excluding Q15/Q16; clear stale shared_context
        ("shared_code", "2026_2026_district_p6_shared_17_19", "", 2567),
        ("shared_code", "2026_2026_district_p6_shared_17_19", "", 2568),
        ("shared_code", "2026_2026_district_p6_shared_17_19", "", 2569),
    ]

    for group_type, group_id, shared_context, qid in updates:
        result = conn.execute(
            "UPDATE questions SET group_type=?, group_id=?, shared_context=? WHERE id=?",
            (group_type, group_id, shared_context, qid),
        )
        status = "OK" if result.rowcount == 1 else "NOT FOUND"
        print(f"  [{status}] id={qid} -> {group_type} / {group_id}")

    conn.commit()


if __name__ == "__main__":
    print(f"Connecting to {DB_FILE} ...")
    conn = sqlite3.connect(DB_FILE)
    run(conn)
    conn.close()
    print("Done.")
