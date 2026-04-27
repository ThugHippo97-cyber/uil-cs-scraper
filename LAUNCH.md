# Launch Notes

## Required Environment

Set these on the production host:

```text
UIL_CS_SECRET_KEY=<long random value>
UIL_CS_REQUIRE_SECRET=1
UIL_CS_DB_FILE=<path to production SQLite database>
FLASK_DEBUG=0
```

`HOST` and `PORT` are only used when running `python app.py` directly. A WSGI host can import `wsgi:app`.

## Database Handling

The live SQLite database is intentionally not committed to Git. Treat it as production state because it stores:

- questions and explanations
- user accounts
- test attempts
- saved attempt answers
- bookmarks

Before replacing or migrating the database, make a backup copy of the production `.db` file.

## Code Update Loop

Use Git for code changes:

```powershell
git pull origin main
.\.venv\Scripts\python.exe -m pytest
```

Then restart the production app process.

## Pre-Launch Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe db_quality_audit.py
```

Then smoke test:

- register and log in
- search for a question
- open a question detail page
- start test mode
- save a test attempt
- bookmark a question
- add an explanation
- report a parse issue
