import argparse
import html
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime

import app


DB_FILE = "uil_cs_questions_v2.db"
REPORT_DIR = "reports"

SEVERITY_RANK = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2,
}

HIGH_ISSUES = {
    "missing_question_content",
    "missing_answer",
    "answer_looks_like_leaked_text",
    "answer_not_in_choices",
    "choice_answer_without_choices",
    "source_pdf_missing",
    "invalid_crop_bounds",
    "missing_question_number",
    "duplicate_question_number",
}

MEDIUM_ISSUES = {
    "missing_choice_labels",
    "choice_labels_missing_answer",
    "choice_answer_label_empty",
    "choice_labels_out_of_order",
    "duplicate_choice_labels",
    "choice_text_leaks_next_question",
    "footer_or_header_leakage",
    "garbled_text",
    "question_starts_like_code",
    "very_short_question_text",
    "crop_page_out_of_range",
    "crop_may_fall_back_to_cover",
    "missing_parsed_content_with_valid_crop",
    "shared_group_missing_context",
    "shared_group_short_context",
    "exam_unexpected_question_count",
    "exam_missing_question_numbers",
    "open_response_complex_answer",
}

LEAKAGE_PATTERNS = [
    r"uil computer science",
    r"written test",
    r"general directions",
    r"do not open",
    r"answer sheet",
    r"standard classes and interfaces",
    r"copyright",
    r"page\s+\d+",
]


def severity_for(issue_type):
    if issue_type in HIGH_ISSUES:
        return "HIGH"
    if issue_type in MEDIUM_ISSUES:
        return "MEDIUM"
    return "LOW"


def add_finding(findings, issue_type, row=None, exam_key=None, message="", details=None):
    severity = severity_for(issue_type)
    finding = {
        "severity": severity,
        "issue_type": issue_type,
        "message": message,
        "details": details or {},
    }
    if row is not None:
        finding.update(
            {
                "id": row["id"],
                "exam_name": row["exam_name"],
                "year": row["year"],
                "level": row["level"],
                "question_number": row["question_number"],
                "group_id": row["group_id"] or "",
                "group_type": row["group_type"] or "single",
                "source_test_pdf": row["source_test_pdf"],
                "question_url": f"/question/{row['id']}",
            }
        )
    if exam_key is not None:
        year, level, exam_name = exam_key
        finding.update(
            {
                "exam_name": exam_name,
                "year": year,
                "level": level,
            }
        )
    findings.append(finding)


def text_preview(value, limit=180):
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def contains_leakage(text):
    lower = (text or "").lower()
    return any(re.search(pattern, lower) for pattern in LEAKAGE_PATTERNS)


def looks_garbled(text):
    if not text:
        return False
    weird_tokens = ["Ã", "Â", "�", "¢", "€", "™", "œ", "“", "”"]
    if any(token in text for token in weird_tokens):
        return True
    chars = [ch for ch in text if not ch.isspace()]
    if len(chars) < 30:
        return False
    unusual = [ch for ch in chars if not (ch.isalnum() or ch in ".,;:!?()[]{}<>+-=*/%_#'\"&|\\~^$@ ")]
    return len(unusual) / max(1, len(chars)) > 0.08


def choice_labels_from_raw(choices):
    return [
        match.group(1).upper()
        for match in re.finditer(r"(?i)(?:^|[\s\n])([A-E])[\.)](?=\s|$)", choices or "")
    ]


def question_starts_like_code(text):
    return bool(
        re.match(
            r"(?is)^\s*(?:public|private|protected|class|interface|static|final|return|if\s*\(|for\s*\(|while\s*\(|switch\s*\(|import\b|package\b)",
            text or "",
        )
    )


def page_count_for(path, cache):
    if not path:
        return None
    resolved = app.resolve_pdf_path(path)
    if resolved in cache:
        return cache[resolved]
    if not os.path.exists(resolved):
        cache[resolved] = None
        return None
    try:
        import pdfplumber

        with pdfplumber.open(resolved) as pdf:
            cache[resolved] = len(pdf.pages)
    except Exception:
        cache[resolved] = None
    return cache[resolved]


def audit_row(row, findings, pdf_page_cache):
    raw_question = row["question_text"] or ""
    raw_code = row["code_block"] or ""
    raw_choices = row["choices"] or ""
    raw_answer = (row["answer"] or "").strip()
    raw_shared = row["shared_context"] or ""
    prepared = app.prepare_question(row)
    effective_answer = (prepared["answer"] or raw_answer).strip()
    parsed_choices = prepared["parsed_choices"]
    parsed_all_labels = [choice["letter"] for choice in parsed_choices]
    parsed_labels = [choice["letter"] for choice in parsed_choices if choice.get("text", "").strip()]
    raw_labels = choice_labels_from_raw(raw_choices)
    normalized_answer = prepared["answer"]
    source_path = app.resolve_pdf_path(row["source_test_pdf"])
    top = float(row["top_y"] or 0)
    bottom = float(row["bottom_y"] or 0)
    has_valid_crop_source = bool(source_path and os.path.exists(source_path) and bottom > top)

    if not (prepared["question_text"] or prepared["code_block"] or prepared["shared_context"]):
        issue_type = "missing_parsed_content_with_valid_crop" if has_valid_crop_source else "missing_question_content"
        add_finding(
            findings,
            issue_type,
            row,
            message="Question has no parsed text, code, or shared context, but the PDF crop can still render."
            if has_valid_crop_source
            else "Question has no displayable text, code, or shared context.",
        )

    if not effective_answer:
        add_finding(findings, "missing_answer", row, message="Answer is blank.")
    elif contains_leakage(raw_answer):
        add_finding(
            findings,
            "answer_looks_like_leaked_text",
            row,
            message="Answer field looks like leaked instructions or prose.",
            details={"answer": text_preview(raw_answer)},
        )
    elif not raw_choices.strip() and len(effective_answer) > 40:
        add_finding(
            findings,
            "open_response_complex_answer",
            row,
            message="Open-response answer is complex and may need manual grading/normalization review.",
            details={"answer": text_preview(effective_answer)},
        )

    if normalized_answer and re.fullmatch(r"[A-ETF]", normalized_answer):
        if parsed_all_labels and normalized_answer in parsed_all_labels and normalized_answer not in parsed_labels:
            add_finding(
                findings,
                "choice_answer_label_empty",
                row,
                message="Answer label exists, but its parsed choice text is empty and may rely on the PDF crop.",
                details={"answer": normalized_answer, "parsed_labels": parsed_all_labels},
            )
        elif parsed_labels and normalized_answer not in parsed_labels:
            add_finding(
                findings,
                "answer_not_in_choices",
                row,
                message="Answer letter is not present in parsed choices.",
                details={"answer": normalized_answer, "parsed_labels": parsed_labels},
            )
        elif not parsed_labels and not prepared["is_visual_choice"]:
            add_finding(
                findings,
                "choice_answer_without_choices",
                row,
                message="Question has a choice-letter answer but no parsed choices.",
                details={"answer": normalized_answer},
            )

    if raw_choices and not raw_labels and not parsed_choices and not prepared["is_open_response"]:
        add_finding(
            findings,
            "missing_choice_labels",
            row,
            message="Choices text exists but no A-E labels were detected.",
            details={"choices_preview": text_preview(raw_choices)},
        )

    if raw_labels:
        duplicates = sorted({label for label in raw_labels if raw_labels.count(label) > 1})
        if duplicates:
            add_finding(
                findings,
                "duplicate_choice_labels",
                row,
                message="Choice labels repeat in the raw choices text.",
                details={"labels": raw_labels, "duplicates": duplicates},
            )
        expected = ["A", "B", "C", "D", "E"][: len(raw_labels)]
        if raw_labels[: len(expected)] != expected:
            add_finding(
                findings,
                "choice_labels_out_of_order",
                row,
                message="Choice labels are missing or out of order.",
                details={"labels": raw_labels},
            )
        if normalized_answer and re.fullmatch(r"[A-E]", normalized_answer) and normalized_answer not in raw_labels:
            add_finding(
                findings,
                "choice_labels_missing_answer",
                row,
                message="Raw choice labels do not include the answer letter.",
                details={"answer": normalized_answer, "labels": raw_labels},
            )

    if re.search(r"(?i)\bquestion\s+\d+\b", raw_choices):
        add_finding(
            findings,
            "choice_text_leaks_next_question",
            row,
            message="Choices appear to include another question header.",
            details={"choices_preview": text_preview(raw_choices)},
        )

    combined = "\n".join([raw_question, raw_code, raw_choices, raw_shared])
    if contains_leakage(combined):
        add_finding(
            findings,
            "footer_or_header_leakage",
            row,
            message="Question fields contain likely test header/footer/instruction text.",
        )

    if looks_garbled(combined):
        add_finding(
            findings,
            "garbled_text",
            row,
            message="Question fields contain mojibake or unusually noisy characters.",
            details={"preview": text_preview(combined)},
        )

    if question_starts_like_code(prepared["question_text"]) and not prepared["code_block"]:
        add_finding(
            findings,
            "question_starts_like_code",
            row,
            message="Question text starts like code but no code block is displayed.",
            details={"question_preview": text_preview(prepared["question_text"])},
        )

    if prepared["question_text"] and len(prepared["question_text"].strip()) < 18 and not prepared["code_block"]:
        add_finding(
            findings,
            "very_short_question_text",
            row,
            message="Question text is suspiciously short.",
            details={"question_preview": text_preview(prepared["question_text"])},
        )

    if not os.path.exists(source_path):
        add_finding(
            findings,
            "source_pdf_missing",
            row,
            message="Source PDF path does not resolve on disk.",
            details={"resolved_path": source_path},
        )
    else:
        page_count = page_count_for(row["source_test_pdf"], pdf_page_cache)
        page_number = int(row["page_number"] or 0)
        top = float(row["top_y"] or 0)
        bottom = float(row["bottom_y"] or 0)
        if page_count is not None and not (0 <= page_number < page_count):
            add_finding(
                findings,
                "crop_page_out_of_range",
                row,
                message="Stored crop page is outside the source PDF page range.",
                details={"page_number": page_number, "page_count": page_count},
            )
        if bottom <= top:
            add_finding(
                findings,
                "invalid_crop_bounds",
                row,
                message="Stored crop bounds are missing or invalid.",
                details={"page_number": page_number, "top_y": top, "bottom_y": bottom},
            )
        elif page_number == 0 and top < 20 and bottom < 120:
            add_finding(
                findings,
                "crop_may_fall_back_to_cover",
                row,
                message="Crop starts near the top of page 0, which may render cover/instructions.",
                details={"page_number": page_number, "top_y": top, "bottom_y": bottom},
            )

    if row["group_type"] and row["group_type"] != "single":
        if not (row["group_id"] or "").strip():
            add_finding(findings, "shared_group_missing_context", row, message="Grouped row has no group_id.")
        if not raw_shared.strip():
            add_finding(findings, "shared_group_missing_context", row, message="Grouped row has no shared context.")
        elif len(raw_shared.strip()) < 40:
            add_finding(findings, "shared_group_short_context", row, message="Shared context is unusually short.")

    visual_words = re.search(r"(?i)\b(?:diagram|figure|shown|image|picture|graph)\b", raw_question)
    if prepared["is_visual_choice"] or (visual_words and not parsed_choices):
        add_finding(
            findings,
            "visual_question_manual_check",
            row,
            message="Question likely depends on the PDF image and should be spot-checked.",
        )


def audit_exam_groups(rows, findings):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["year"], row["level"], row["exam_name"])].append(row)

    for exam_key, exam_rows in grouped.items():
        qnums = [int(row["question_number"] or 0) for row in exam_rows]
        positive_qnums = [qnum for qnum in qnums if qnum > 0]
        counts = Counter(positive_qnums)
        duplicates = sorted(qnum for qnum, count in counts.items() if count > 1)
        for qnum in duplicates:
            sample = next(row for row in exam_rows if int(row["question_number"] or 0) == qnum)
            add_finding(
                findings,
                "duplicate_question_number",
                sample,
                message="Exam has duplicate question numbers.",
                details={"duplicate_question_number": qnum, "count": counts[qnum]},
            )

        if any(qnum <= 0 for qnum in qnums):
            sample = next(row for row in exam_rows if int(row["question_number"] or 0) <= 0)
            add_finding(findings, "missing_question_number", sample, message="Question number is missing or invalid.")

        expected_count = 40
        unique_count = len(set(positive_qnums))
        if unique_count != expected_count:
            add_finding(
                findings,
                "exam_unexpected_question_count",
                exam_key=exam_key,
                message="Exam does not have the expected 40 unique question numbers.",
                details={"unique_question_count": unique_count, "expected": expected_count},
            )

        if positive_qnums:
            missing = [qnum for qnum in range(1, max(positive_qnums) + 1) if qnum not in counts]
            if missing:
                add_finding(
                    findings,
                    "exam_missing_question_numbers",
                    exam_key=exam_key,
                    message="Exam has gaps in its question number sequence.",
                    details={"missing_question_numbers": missing[:40]},
                )


def make_summary(rows, findings):
    by_severity = Counter(finding["severity"] for finding in findings)
    by_issue = Counter(finding["issue_type"] for finding in findings)
    by_exam = Counter(
        f"{finding.get('year')} {finding.get('level')} {finding.get('exam_name')}"
        for finding in findings
        if finding.get("exam_name")
    )
    collection_counts = Counter(
        app.classify_exam_collection(row["exam_name"] or "", row["source_test_pdf"] or "") for row in rows
    )
    return {
        "question_count": len(rows),
        "exam_count": len({(row["year"], row["level"], row["exam_name"]) for row in rows}),
        "finding_count": len(findings),
        "by_severity": dict(by_severity),
        "by_issue": dict(by_issue.most_common()),
        "by_exam": dict(by_exam.most_common()),
        "collection_counts": dict(collection_counts),
    }


def write_json_report(path, summary, findings):
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "summary": summary,
        "findings": findings,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def write_text_summary(path, summary, findings):
    high = [finding for finding in findings if finding["severity"] == "HIGH"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("UIL CS DB Quality Summary\n")
        f.write("=========================\n\n")
        f.write(f"Questions scanned: {summary['question_count']}\n")
        f.write(f"Exams scanned: {summary['exam_count']}\n")
        f.write(f"Hidden explanation/key rows: {summary.get('hidden_explanation_or_key_rows', 0)}\n")
        f.write(f"Findings: {summary['finding_count']}\n\n")
        f.write("By severity:\n")
        for severity in ["HIGH", "MEDIUM", "LOW"]:
            f.write(f"  {severity}: {summary['by_severity'].get(severity, 0)}\n")
        f.write("\nBy issue type:\n")
        for issue, count in summary["by_issue"].items():
            f.write(f"  {issue}: {count}\n")
        f.write("\nBy collection:\n")
        for collection, count in summary["collection_counts"].items():
            f.write(f"  {collection}: {count}\n")
        f.write("\nTop exams by finding count:\n")
        for exam, count in list(summary["by_exam"].items())[:25]:
            f.write(f"  {exam}: {count}\n")
        f.write("\nTop HIGH findings:\n")
        for finding in high[:50]:
            f.write(
                f"  {finding.get('year')} {finding.get('exam_name')} Q{finding.get('question_number')}: "
                f"{finding['issue_type']} - {finding['message']}\n"
            )


def write_html_report(path, summary, findings, limit=500):
    rows = []
    for finding in findings[:limit]:
        question_url = finding.get("question_url")
        link = f'<a href="{html.escape(question_url)}">/question/{finding.get("id")}</a>' if question_url else ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(finding['severity'])}</td>"
            f"<td>{html.escape(finding['issue_type'])}</td>"
            f"<td>{html.escape(str(finding.get('year') or ''))}</td>"
            f"<td>{html.escape(str(finding.get('level') or ''))}</td>"
            f"<td>{html.escape(str(finding.get('exam_name') or ''))}</td>"
            f"<td>{html.escape(str(finding.get('question_number') or ''))}</td>"
            f"<td>{link}</td>"
            f"<td>{html.escape(finding['message'])}</td>"
            f"<td><code>{html.escape(json.dumps(finding.get('details') or {}, ensure_ascii=True)[:500])}</code></td>"
            "</tr>"
        )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>UIL CS DB Quality Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #172033; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ border: 1px solid #d6dbe8; padding: 8px; vertical-align: top; }}
    th {{ background: #eef2ff; text-align: left; position: sticky; top: 0; }}
    tr:nth-child(even) {{ background: #f8fafc; }}
    code {{ white-space: pre-wrap; }}
    .HIGH {{ color: #b42318; font-weight: 700; }}
    .MEDIUM {{ color: #9a6700; font-weight: 700; }}
    .LOW {{ color: #475467; }}
  </style>
</head>
<body>
  <h1>UIL CS DB Quality Report</h1>
  <p>Questions scanned: {summary['question_count']} | Exams: {summary['exam_count']} | Hidden explanation/key rows: {summary.get('hidden_explanation_or_key_rows', 0)} | Findings: {summary['finding_count']}</p>
  <p>Severity: HIGH {summary['by_severity'].get('HIGH', 0)}, MEDIUM {summary['by_severity'].get('MEDIUM', 0)}, LOW {summary['by_severity'].get('LOW', 0)}</p>
  <table>
    <thead>
      <tr><th>Severity</th><th>Issue</th><th>Year</th><th>Level</th><th>Exam</th><th>Q</th><th>Link</th><th>Message</th><th>Details</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
    html_text = html_text.replace("<td>HIGH</td>", '<td class="HIGH">HIGH</td>')
    html_text = html_text.replace("<td>MEDIUM</td>", '<td class="MEDIUM">MEDIUM</td>')
    html_text = html_text.replace("<td>LOW</td>", '<td class="LOW">LOW</td>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_text)


def run_audit(db_path=DB_FILE, report_dir=REPORT_DIR):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT *
        FROM questions
        ORDER BY year, level, exam_name, question_number, id
        """
    ).fetchall()
    conn.close()

    findings = []
    pdf_page_cache = {}
    hidden_rows = []
    for row in rows:
        if app.is_explanation_or_key_row(row):
            hidden_rows.append(row)
            add_finding(
                findings,
                "answer_explanation_row_hidden",
                row,
                message="Row looks like an answer-key explanation rather than a question and is hidden by the app.",
                details={"question_preview": text_preview(row["question_text"] or "")},
            )
            continue
        audit_row(row, findings, pdf_page_cache)
    visible_rows = [row for row in rows if not app.is_explanation_or_key_row(row)]
    audit_exam_groups(visible_rows, findings)

    findings.sort(
        key=lambda item: (
            SEVERITY_RANK.get(item["severity"], 9),
            item.get("year") or 0,
            item.get("exam_name") or "",
            item.get("question_number") or 0,
            item["issue_type"],
        )
    )
    summary = make_summary(visible_rows, findings)
    summary["hidden_explanation_or_key_rows"] = len(hidden_rows)

    os.makedirs(report_dir, exist_ok=True)
    write_json_report(os.path.join(report_dir, "db_quality_report.json"), summary, findings)
    write_text_summary(os.path.join(report_dir, "db_quality_summary.txt"), summary, findings)
    write_html_report(os.path.join(report_dir, "db_quality_report.html"), summary, findings)
    return summary, findings


def main():
    parser = argparse.ArgumentParser(description="Run a read-only quality audit over the UIL CS question database.")
    parser.add_argument("--db", default=DB_FILE, help="SQLite DB path")
    parser.add_argument("--out", default=REPORT_DIR, help="Report output directory")
    args = parser.parse_args()
    summary, findings = run_audit(args.db, args.out)
    print(f"Scanned {summary['question_count']} questions across {summary['exam_count']} exams.")
    print(f"Hidden explanation/key rows: {summary.get('hidden_explanation_or_key_rows', 0)}")
    print(f"Findings: {summary['finding_count']}")
    for severity in ["HIGH", "MEDIUM", "LOW"]:
        print(f"  {severity}: {summary['by_severity'].get(severity, 0)}")
    print(f"Wrote reports to {args.out}")
    if findings:
        print("Top findings:")
        for finding in findings[:10]:
            print(
                f"  {finding['severity']} {finding['issue_type']} "
                f"{finding.get('exam_name')} Q{finding.get('question_number')}: {finding['message']}"
            )


if __name__ == "__main__":
    main()
