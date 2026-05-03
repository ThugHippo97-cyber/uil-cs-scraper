# SESSION_NOTES.md — UIL CS Scraper

_Update this at the end of every session. Claude will offer to do it for you._

---

## Last Worked On

- **2026-05-03** — Setup session on secondary machine. Configured GitHub token (30-day expiry), stored
  credentials locally, and pushed `CLAUDE.md` + `SESSION_NOTES.md` to GitHub. No code changes — DB not
  present on this machine. Reviewed workflow for picking up on main machine tomorrow.

- **2026-05-02** — Initial project setup with Claude Code. Created `CLAUDE.md` and `SESSION_NOTES.md`
  to establish a cross-machine save-game system. No code changes made yet.

## Current Status

- App is **live on PythonAnywhere** — used by a UIL CS competition team for practice before state competition.
- DB has **70+ exams, 3000+ parsed questions**.
- Parse issues in `answer_sanity_queue.jsonl`: unknown — check next session when relevant.

## Active Blockers

- None

## Next Steps

- Investigate and fix **shared code context parse issues** (questions that share a code block are not being parsed/linked correctly).
- Once fixed, spot-check a few affected questions manually to verify.

## Decisions Made

| Date | Decision | Reason |
|------|----------|--------|
| 2026-05-02 | Use `CLAUDE.md` + `SESSION_NOTES.md` committed to git for cross-machine context | Working across 3 machines; git sync is the simplest shared state |

## Parking Lot (ideas/todos not yet prioritized)

- A few ideas in mind — will add here as they come up

---

_Last updated: 2026-05-03 (evening)_
