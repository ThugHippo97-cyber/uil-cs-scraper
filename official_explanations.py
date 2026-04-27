import argparse
import json
import os
import re
import shutil
import sqlite3
from datetime import UTC, datetime

import app
import main


DB_FILE = "uil_cs_questions_v2.db"
REPORT_DIR = "reports"


def clean_explanation_text(text):
    cleaned = (text or "").replace("\r", "\n").strip()
    cleaned = re.split(r"(?im)^\s*(?:note to graders|scoring|answer key)\s*:", cleaned)[0]
    cleaned = app.remove_noise_lines(cleaned)
    cleaned = re.sub(r"(?im)^\s*(?:page\s+\d+|uil computer science written test.*)$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def explanation_section(text):
    candidates = []
    for pattern in (r"(?im)^\s*explanations?\s*:\s*$", r"(?im)^\s*solutions?\s*:\s*$"):
        match = re.search(pattern, text or "")
        if match:
            candidates.append(match.end())
    if not candidates:
        return ""
    return (text or "")[min(candidates):]


def parse_explanations_from_text(text):
    section = explanation_section(text)
    if not section:
        return {}

    heading_pattern = re.compile(r"(?m)^\s*(?:#|\*)?\s*(\d{1,2})\s*[\.)]\s+")
    matches = [
        match
        for match in heading_pattern.finditer(section)
        if 1 <= int(match.group(1)) <= 40
    ]
    if not matches:
        return {}

    explanations = {}
    for idx, match in enumerate(matches):
        qnum = int(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section)
        body = clean_explanation_text(section[start:end])
        if len(body) < 12:
            continue
        if re.fullmatch(r"[A-E]\s*", body, re.IGNORECASE):
            continue
        explanations[qnum] = body

    return explanations


def extract_pdf_explanations(pdf_path):
    text = main.extract_full_text(pdf_path)
    return parse_explanations_from_text(text)


def fetch_exam_sources(conn):
    return conn.execute(
        """
        SELECT source_key_pdf, source_test_pdf, exam_name, year, level, COUNT(*) AS question_count
        FROM questions
        GROUP BY source_key_pdf, source_test_pdf, exam_name, year, level
        ORDER BY year, level, exam_name
        """
    ).fetchall()


def fetch_question_map(conn, exam_name, year, level):
    rows = conn.execute(
        """
        SELECT *
        FROM questions
        WHERE exam_name = ?
          AND year = ?
          AND lower(level) = lower(?)
        ORDER BY question_number ASC, id DESC
        """,
        (exam_name, year, level),
    ).fetchall()
    question_map = {}
    for row in rows:
        qnum = int(row["question_number"] or 0)
        if not qnum or qnum in question_map or app.is_explanation_or_key_row(row):
            continue
        question_map[qnum] = row["id"]
    return question_map


def build_import_plan(db_path=DB_FILE):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    exams = fetch_exam_sources(conn)

    plan = []
    errors = []
    for exam in exams:
        stored_key = exam["source_key_pdf"] or exam["source_test_pdf"] or ""
        key_path = app.resolve_pdf_path(stored_key)
        if not key_path or not os.path.exists(key_path):
            errors.append({
                "exam_name": exam["exam_name"],
                "year": exam["year"],
                "level": exam["level"],
                "error": "key_pdf_missing",
                "key_pdf": stored_key,
            })
            continue

        try:
            explanations = extract_pdf_explanations(key_path)
        except Exception as exc:
            errors.append({
                "exam_name": exam["exam_name"],
                "year": exam["year"],
                "level": exam["level"],
                "error": f"{type(exc).__name__}: {exc}",
                "key_pdf": stored_key,
            })
            continue

        question_map = fetch_question_map(conn, exam["exam_name"], exam["year"], exam["level"])
        matched = []
        unmatched = []
        for qnum, explanation in sorted(explanations.items()):
            question_id = question_map.get(qnum)
            item = {
                "exam_name": exam["exam_name"],
                "year": exam["year"],
                "level": exam["level"],
                "question_number": qnum,
                "question_id": question_id,
                "source_key_pdf": stored_key,
                "explanation": explanation,
            }
            if question_id:
                matched.append(item)
            else:
                unmatched.append(item)

        plan.append({
            "exam_name": exam["exam_name"],
            "year": exam["year"],
            "level": exam["level"],
            "source_key_pdf": stored_key,
            "extracted_count": len(explanations),
            "matched_count": len(matched),
            "unmatched_count": len(unmatched),
            "matched": matched,
            "unmatched": unmatched,
        })

    conn.close()
    return plan, errors


def backup_database(db_path):
    os.makedirs(".tmp", exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(".tmp", f"uil_cs_questions_v2.before_official_explanations.{stamp}.db")
    shutil.copy2(db_path, backup_path)
    return backup_path


def apply_import_plan(plan, db_path=DB_FILE):
    backup_path = backup_database(db_path)
    conn = sqlite3.connect(db_path)
    inserted = 0
    skipped_existing = 0
    for exam in plan:
        for item in exam["matched"]:
            existing = conn.execute(
                "SELECT 1 FROM question_explanations WHERE question_id = ?",
                (item["question_id"],),
            ).fetchone()
            if existing:
                skipped_existing += 1
                continue
            conn.execute(
                """
                INSERT INTO question_explanations
                (question_id, explanation, author_user_id, updated_by_user_id)
                VALUES (?, ?, NULL, NULL)
                """,
                (item["question_id"], item["explanation"]),
            )
            inserted += 1
    conn.commit()
    conn.close()
    return {"inserted": inserted, "skipped_existing": skipped_existing, "backup_path": backup_path}


def write_report(plan, errors, output_path):
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "summary": summarize_plan(plan, errors),
        "exams": plan,
        "errors": errors,
    }
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def summarize_plan(plan, errors):
    return {
        "exam_count": len(plan),
        "error_count": len(errors),
        "exams_with_explanations": sum(1 for exam in plan if exam["extracted_count"]),
        "extracted_explanations": sum(exam["extracted_count"] for exam in plan),
        "matched_explanations": sum(exam["matched_count"] for exam in plan),
        "unmatched_explanations": sum(exam["unmatched_count"] for exam in plan),
    }


def main_cli():
    parser = argparse.ArgumentParser(description="Extract official/key PDF explanations and optionally import them.")
    parser.add_argument("--db", default=DB_FILE, help="SQLite DB path")
    parser.add_argument("--out", default=os.path.join(REPORT_DIR, "official_explanations_import.json"))
    parser.add_argument("--apply", action="store_true", help="Write matched explanations into question_explanations.")
    args = parser.parse_args()

    plan, errors = build_import_plan(args.db)
    report = write_report(plan, errors, args.out)
    summary = report["summary"]

    print(f"Exams scanned: {summary['exam_count']}")
    print(f"Exams with explanations: {summary['exams_with_explanations']}")
    print(f"Extracted explanations: {summary['extracted_explanations']}")
    print(f"Matched to questions: {summary['matched_explanations']}")
    print(f"Unmatched explanations: {summary['unmatched_explanations']}")
    print(f"Errors: {summary['error_count']}")
    print(f"Wrote report to {args.out}")

    if args.apply:
        result = apply_import_plan(plan, args.db)
        print(f"Inserted explanations: {result['inserted']}")
        print(f"Skipped existing explanations: {result['skipped_existing']}")
        print(f"Backup: {result['backup_path']}")
    else:
        print("Dry run only. Re-run with --apply to import matched explanations.")


if __name__ == "__main__":
    main_cli()
