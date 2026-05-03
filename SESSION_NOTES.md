# SESSION_NOTES.md — UIL CS Scraper

_Update this at the end of every session. Claude will offer to do it for you._

---

## Last Worked On

- **2026-05-03** — Major parse quality session. Worked through the `answer_sanity_queue.jsonl`
  starting with the largest category. Three commits pushed:
  1. **Shared code group detection** (`merge_code_blocks` overlap merging + `code_block_calls_declared_method`): improves grouping for questions whose code block calls a method defined in the shared context. All 80 tests pass.
  2. **`parse_choices` period-delimiter bug + sanity checker alignment**: `b.push()` was being split as a B-choice label. Fixed by requiring whitespace/end after `.` delimiter. Also aligned `evaluate_answer_sanity` with `should_use_visual_choice_fallback` — no longer flags questions the visual fallback handles gracefully. Cleared all 33 `answer_not_in_parsed_choices` entries.
  3. **`open_response_letter_answer` cleanup**: Added `question_overrides` for `college_station#17` and `college_station#25` (choices were OCR'd into question_text). Cleared all 13 entries (4 stale, 2 genuine open-response, 7 unrecoverable without PDFs).

- **2026-05-03** (earlier) — Setup session on secondary machine. Configured GitHub token (30-day expiry), stored
  credentials locally, and pushed `CLAUDE.md` + `SESSION_NOTES.md` to GitHub. No code changes — DB not
  present on this machine.

- **2026-05-02** — Initial project setup with Claude Code. Created `CLAUDE.md` and `SESSION_NOTES.md`
  to establish a cross-machine save-game system. No code changes made yet.

## Current Status

- App is **live on PythonAnywhere** — used by a UIL CS competition team for practice before state competition.
- DB has **70+ exams, 3000+ parsed questions**.
- `answer_sanity_queue.jsonl` has **9 entries remaining** across 3 categories:
  - 6 × `choice_question_non_choice_answer`
  - 2 × `missing_answer`
  - 1 × `choice_labels_not_parsed`
- 3 commits ahead of origin — **push needed** (`git push`, needs credentials).

## Active Blockers

- None

## Next Steps

- Finish the remaining 9 sanity queue entries:
  1. `choice_question_non_choice_answer` (6) — answer is H/non-letter on a choice question
  2. `missing_answer` (2) — key PDF didn't yield an answer
  3. `choice_labels_not_parsed` (1) — choice text present but labels not parsed
- Deploy fixes to PythonAnywhere (re-ingest affected exams if needed, or patch DB directly)
- Spot-check a few questions from fixed exams in the live app

## Decisions Made

| Date | Decision | Reason |
|------|----------|--------|
| 2026-05-03 | Align `evaluate_answer_sanity` with `should_use_visual_choice_fallback` | Sanity checker was flagging questions the UI handles fine via visual fallback — false positives |
| 2026-05-03 | Clear unrecoverable MCQ entries from sanity queue without fixing | Choices were never in the PDF text; visual fallback handles display; re-ingestion won't help |
| 2026-05-02 | Use `CLAUDE.md` + `SESSION_NOTES.md` committed to git for cross-machine context | Working across 3 machines; git sync is the simplest shared state |

## Parking Lot (ideas/todos not yet prioritized)

- Deploy updated code to PythonAnywhere after queue work is complete
- Consider adding a `skip_sanity` field to `question_overrides.json` to suppress specific questions from future sanity re-flags

---

_Last updated: 2026-05-03 (evening)_
