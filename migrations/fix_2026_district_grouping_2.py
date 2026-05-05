"""
Migration: group Q27/Q28, Q34-Q37, and Q39/Q40 in 2026_district.

Run once on any machine whose DB has not yet received these changes:
    python migrations/fix_2026_district_grouping_2.py
"""
import os
import sqlite3

DB_FILE = os.environ.get("UIL_CS_DB_FILE", "uil_cs_questions_v2.db")


def run(conn):
    updates = [
        # Q27/Q28: group — both reference same mystery() function
        ("shared_code", "2026_2026_district_p8_shared_27_28", 2577),
        ("shared_code", "2026_2026_district_p8_shared_27_28", 2578),
        # Q34/Q35: pull into Q36/Q37's group — all four share the HashSet code
        ("shared_code", "2026_2026_district_p9_shared_34_37", 2584),
        ("shared_code", "2026_2026_district_p9_shared_34_37", 2585),
        # Q36/Q37: rename group to match new four-question group
        ("shared_code", "2026_2026_district_p9_shared_34_37", 2586),
        ("shared_code", "2026_2026_district_p9_shared_34_37", 2587),
        # Q39/Q40: group — both ask about the same BST element list
        ("shared_code", "2026_2026_district_p10_shared_39_40", 2589),
        ("shared_code", "2026_2026_district_p10_shared_39_40", 2590),
    ]

    for group_type, group_id, qid in updates:
        result = conn.execute(
            "UPDATE questions SET group_type=?, group_id=? WHERE id=?",
            (group_type, group_id, qid),
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
