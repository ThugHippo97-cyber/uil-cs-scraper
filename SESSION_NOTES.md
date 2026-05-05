# SESSION_NOTES.md — UIL CS Scraper

_Update this at the end of every session. Claude will offer to do it for you._

---

## Last Worked On

- **2026-05-04** — Parse feedback infrastructure + 2026_district bulk fix session. Several commits pushed:
  - **Admin feedback download** (`4aa2cfe`): Added `/admin/feedback` route that dumps the entire `parse_issue_reports` DB table as a downloadable JSONL file. Gated by `UIL_CS_ADMIN_USER` env var (set in PythonAnywhere WSGI file). Also documented that all reports were being saved to the DB table all along — the local `parse_feedback.jsonl` was stale because teammates used the live site. Synced the local file with the full server history (52 reports).
  - **2026_district parse fixes** (`a75abe7`): Bulk `question_overrides.json` fixes for 20 reported issues across the exam. Fixes: Q4 code_block trimmed (Q5's boolean code leaked in); Q10 code_block trimmed (Scanner code leaked in); Q11 OCR artifact `is new File` fixed; Q15 question_text and code_block reconstructed (ArrayList init leaked into question_text, leading catch/finally stripped); Q16 code_block restructured (try/catch order inverted); Q17-19 correct shared_context (full LinkedHashSet code); Q27/Q28 shared_context added (complete mystery() function, question_text cleaned); Q29 question_text cleaned (function signature leaked in); Q34-Q37 shared_context added (full HashSet<byte[]> code); Q38 question_text fixed (BST element list from Q39/40 leaked in, threading code reordered); Q40 question_text fixed (first half of BST element list was missing).
  - **2026_district DB grouping migration 1** (`b7859f7`): `migrations/fix_2026_district_grouping.py` — un-groups Q4/Q5 and Q10/Q11 (two separate unrelated questions falsely merged on same page); de-groups Q15/Q16 from Q17-19 (they're standalone, not part of the LinkedHashSet group); renames Q17-19 group_id to `p6_shared_17_19`. Must be run with correct DB path: `UIL_CS_DB_FILE=.../instance/uil_cs_questions_v2.db python migrations/fix_2026_district_grouping.py`. **Already run on PythonAnywhere.**
  - **Image disk cache + browser cache headers** (`8c61825`): PDF crops were being re-rendered at 350 DPI from scratch on every request with no caching, causing 5-10 second delays. Added `serve_image()` helper that checks `.crop_cache/` before rendering; saves result to disk on first render; adds `Cache-Control: public, max-age=86400`. Cache key includes `top_y`/`bottom_y` so fixing crop bounds auto-invalidates. Applied to all three image routes: `question_image`, `question_page_image`, `group_image`.
  - **2026_district DB grouping migration 2 + neighbor crop fix** (current, not yet pushed as separate commit): `migrations/fix_2026_district_grouping_2.py` — groups Q27/Q28 as `shared_code` (mystery function); groups Q34-Q37 as `shared_code` (HashSet code); groups Q39/Q40 as `shared_code` (same BST element list). Also fixed `needs_neighbor_context` to not trigger on "client code" — this was expanding crop bounds for Q29/Q30/Q31 unnecessarily (they have full code in code_block already; "client code" is a section label, not a reference to a neighboring question). Only `line #N`, `comment #N`, and `<*N>` patterns now trigger neighbor crop expansion. **Migration 2 not yet run on PythonAnywhere.**

- **2026-05-04** — Missed question drill mode + dashboard QoL. Two commits pushed (`7a37ea7`, `0a5a1b5`):
  - **Drill mode** (`7a37ea7`): Full missed-question drill feature. New `user_drill_queue` table. `update_drill_queue()` fires after every regular test. New `/drill` route. `test_mode.html` gains `is_drill` flag. `drill_empty.html` for users with no queue. Dashboard shows "Missed Question Drill" section.
  - **Attempts collapse** (`0a5a1b5`): Dashboard "Recent Test Attempts" shows 3 by default with inline expand toggle.

- **2026-05-04** — Parse audit skill design + Pass 1 run. No code commits.

- **2026-05-04** — Clean academic UI redesign + shared context fixes + UI features. Several commits pushed (`cdec25f`, `a76c9b0`, `53d1ea9`, `5f6722b`).

- **2026-05-03** — DB duplicate purge, OCR fix, UI overhaul, major parse quality session. Multiple commits.

- **2026-05-02** — Initial project setup with Claude Code.

## Current Status

- App is **live on PythonAnywhere** — used by a UIL CS competition team for practice before state competition.
- DB has **4064 questions** across ~100 exams. Sanity queue is empty.
- **Migration 2 still needs to be run on PythonAnywhere** — see Next Steps.
- Image disk cache is live; site should be dramatically faster after first pass through questions.
- `parse_feedback.jsonl` is now synced from the server (52 reports total).

## Active Blockers

- **Migration 2 not yet run on PythonAnywhere**: run `UIL_CS_DB_FILE=.../instance/uil_cs_questions_v2.db python migrations/fix_2026_district_grouping_2.py` to group Q27/Q28, Q34-Q37, Q39/Q40 as shared_code.
- Pass 2 vision audit requires `ANTHROPIC_API_KEY` — not currently available locally.

## Next Steps

- **Run migration 2 on PythonAnywhere** (`fix_2026_district_grouping_2.py`) then reload — fixes Q27/Q28, Q34-Q37, Q39/Q40 grouping issues in 2026_district.
- **Remaining parse feedback items** (from the 52-report sync):
  - `2025_invitationala` Q31/32/33: BST element list missing from image — visual-only, needs PDF investigation. Q35/37/38: shared_context incomplete (DataStruct class).
  - `2025_invitationalb` Q24: missing shared context. Q19: references prior questions (graph).
  - `2025_stacey_tests_test_02` Q22: crop cuts off code.
  - `2023_invitationala` Q3 / `2024_state` Q3: first 1-2 questions missing from exam — likely ingestion issue.
  - `2024_stacey_armstrong_written_tests_sample_test_1` Q25: shared context missing code.
  - `2026_stacey_tests_test_01` Q22/23/25: graph images missing.
- **Feature 2 (Leaderboard)**: Global leaderboard from homepage. Columns: correct answers all-time, tests taken, avg score. Decisions: opt-in vs. automatic, drill attempts filtered or not.
- **Feature 3 (Coach/Student accounts)**: Coach builds team, assigns questions/tests to students.
- When API key available: run Pass 2 on 43 `garbled_text` questions — IDs in `reports/pass2_garbled_results.json`.
- Fix `answer_not_in_choices` × 3 for Sample Test 2 Q39 (Roman numeral Big-O; "I." parsed as choice label).
- Continue MEDIUM audit findings: `choice_labels_out_of_order` (187), `duplicate_choice_labels` (119), `footer_or_header_leakage` (53).

## Decisions Made

| Date | Decision | Reason |
|------|----------|--------|
| 2026-05-04 | Remove "client code" from `needs_neighbor_context` trigger pattern | "client code" is a section label in UIL exams, not a reference to a neighboring question — was causing crop expansion for Q29/Q30/Q31 which already had full code extracted |
| 2026-05-04 | Use disk cache (.crop_cache/) for rendered PDF images | PDF rendering at 350 DPI on every request was the primary cause of 5-10s page load times; disk cache eliminates re-renders after first load |
| 2026-05-04 | Use `UIL_CS_ADMIN_USER` env var to gate `/admin/feedback` | No admin flag on users table; env var is simpler than a DB migration and sufficient for single-admin use |
| 2026-05-04 | Use one traditional Light/Dark toggle instead of multiple novelty themes | Keeps the interface practical and academic |
| 2026-05-04 | shared_context recompute: only update DB directly when anchor code_block is empty | question_overrides.json now supports shared_context field for future patches without DB changes |
| 2026-05-04 | Leave 2026_college_station crop bounds unfixed for now | PDF is fully image-only; fixing requires full OCR re-ingestion |
| 2026-05-03 | Align `evaluate_answer_sanity` with `should_use_visual_choice_fallback` | Sanity checker was flagging questions the UI handles fine via visual fallback |
| 2026-05-03 | Clear unrecoverable MCQ entries from sanity queue without fixing | Choices were never in the PDF text; visual fallback handles display |
| 2026-05-02 | Use `CLAUDE.md` + `SESSION_NOTES.md` committed to git for cross-machine context | Working across 3 machines; git sync is the simplest shared state |

## Parking Lot (ideas/todos not yet prioritized)

- Consider adding a `skip_sanity` field to `question_overrides.json` to suppress specific questions from future sanity re-flags
- Clear `.crop_cache/` on PythonAnywhere if crop bounds are ever fixed for a batch of questions (stale cache won't auto-invalidate for those specific files)

---

_Last updated: 2026-05-04_
