# CLAUDE.md — UIL CS Scraper / Practice Platform

## Session Start Instructions

**At the start of every session, read `SESSION_NOTES.md` before doing anything else.**
It contains what was last worked on, current blockers, next steps, and key decisions.
At the end of every session, remind the user to update `SESSION_NOTES.md` and offer to write the summary for them.

## Project Overview

This is a UIL Computer Science exam practice platform. It scrapes UIL CS exam PDFs (Java-focused competitions),
parses questions and answer keys, stores them in SQLite, and serves a Flask web app where students can
search by topic, practice in test mode, bookmark questions, and add/view explanations.

**Key flows:**
- `main.py` — PDF ingestion: parses test + key PDFs into the SQLite DB
- `app.py` — Flask web server: search, test mode, user accounts, bookmarks, explanations
- `official_explanations.py` — imports official explanation text from answer key PDFs
- `db_quality_audit.py` — audits the DB for parse issues (missing answers, bad crops, etc.)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask 3.1 |
| PDF parsing | pdfplumber, pypdfium2 (OCR fallback) |
| Database | SQLite (file: `uil_cs_questions_v2.db`) — NOT committed to git |
| Auth | Werkzeug password hashing, Flask sessions |
| Frontend | Jinja2 templates, vanilla JS, plain CSS |
| Testing | pytest |
| Deployment | WSGI (`wsgi.py`), env-var config |

## Project Structure

```
main.py                  # PDF → SQLite ingestion pipeline
app.py                   # Flask app (routes, search, auth, test mode)
official_explanations.py # Import official explanations from key PDFs
db_quality_audit.py      # DB health audit tool
wsgi.py                  # WSGI entry point for production
data/                    # PDF source files (test + key PDFs)
templates/               # Jinja2 HTML templates
static/                  # CSS + JS
tests/                   # pytest test suite
archive_overrides.json   # Overrides for archive/exam metadata
question_overrides.json  # Manual question-level overrides
answer_sanity_queue.jsonl # Queue of answers flagged for review
parse_feedback.jsonl     # User-submitted parse issue reports
LAUNCH.md                # Production deployment notes
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `UIL_CS_SECRET_KEY` | Flask secret key (required in prod) |
| `UIL_CS_REQUIRE_SECRET` | Set to `1` in prod to enforce secret key |
| `UIL_CS_DB_FILE` | Path to SQLite DB (defaults to `uil_cs_questions_v2.db`) |
| `FLASK_DEBUG` | Set to `0` in prod |
| `UIL_CS_ADMIN_USER` | Username that can access `/admin/feedback` (parse report download) |

## Coding Conventions

- **No comments unless the WHY is non-obvious** — code should be self-documenting
- Python standard style; no type annotations observed in existing code
- Flask routes are all in `app.py` — keep them there
- DB access via `sqlite3` directly (no ORM)
- `TOPIC_SYNONYMS` dict in both `main.py` and `app.py` maps search terms to related keywords — keep in sync if modified
- Tests live in `tests/` and use pytest; run with `python -m pytest`
- PDF files in `data/` follow naming convention: `{year}_{level}_{test|key}.pdf`

## How I Like to Work

- **Commit style:** Concise descriptive summaries — no conventional commit prefixes needed.
- **Tests:** Write tests for significant feature additions or larger changes. Small/simple fixes don't need new tests.
- **Parse feedback workflow:** Users report parse issues in-app → collect for a few days → fix issues → push to git → manual spot-check a few questions/tests to verify. Goal is to use Claude to speed this cycle up significantly.
- **Context:** This app is live on PythonAnywhere for a UIL CS competition team to practice before state. Teammates also use it to report parse errors, which feeds the improvement loop.

## Pre-Launch Checklist (from LAUNCH.md)

1. `python -m pytest`
2. `python db_quality_audit.py`
3. Smoke test: register/login, search, question detail, test mode, save attempt, bookmark, add explanation, report issue

## Important Notes

- The SQLite DB is **not** committed to git — treat it as production state, always back up before migrating
- OCR fallback (pypdfium2) is available but may not be installed on all machines — non-fatal warning if missing
- `archive_overrides.json` and `question_overrides.json` patch bad parses without re-ingesting PDFs
