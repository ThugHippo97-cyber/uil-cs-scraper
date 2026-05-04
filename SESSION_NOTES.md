# SESSION_NOTES.md — UIL CS Scraper

_Update this at the end of every session. Claude will offer to do it for you._

---

## Last Worked On

- **2026-05-04** — Clean academic UI redesign. One local commit created (`cdec25f`, not pushed yet):
  - Replaced the flashy matrix/theme-heavy look with a compact academic practice-tool interface: neutral light background, white cards, subtle borders, restrained shadows, and a navy accent.
  - Removed novelty theme selector behavior. Added a simple Light/Dark toggle in the top nav for users who want lower brightness; dark mode is an inverse high-contrast version of the same UI, not a separate visual theme.
  - Kept **Start Full Test** as the primary home-page action and **Topic Practice Search** as the secondary workflow.
  - Simplified marketing/prototype copy in `auth.html`, `dashboard.html`, and `test_mode.html`.
  - Reworked shared component styling in `static/style.css`: buttons, pills, result cards, answer keycaps, status/result boxes, forms, dashboard stats, image/code frames, and fullscreen modal.
  - `static/theme.js` now injects the light/dark toggle and persists dark mode with `localStorage`.
  - Verification: `PYTHONPATH=.; pytest` passed with **80 tests**.

- **2026-05-04** — Shared context fixes + UI features. Several commits pushed:
  - **Fullscreen expand** (`a76c9b0`): Added expand button (⛶) to exam question image bar. Opens a full-screen modal with enlarged PDF crop + interactive answer choices. Works in both practice mode (`question.html`) and test mode (`test_mode.html`). `checkAnswer` scoped via `btn.closest` so page and modal buttons don't interfere.
  - **Static file cache-busting** (`53d1ea9`): `app.py` now computes git commit hash at startup (`STATIC_VERSION`) and appends `?v=<hash>` to `style.css` and `theme.js` URLs. Fixes browser serving stale CSS after deploy.
  - **Shared context recompute** (`5f6722b`): Reran `merge_code_blocks` across all 349 `shared_code` groups; 197 had stale/malformed `shared_context` from before the merge deduplication fix. Key improvements:
    - `2025_invitationala` Q35-38 DataStruct class now merges cleanly (no extra braces)
    - `2018_invitationalb` Q23-27 restored with full class definition (extracted directly from PDF page text) + client code
    - `prepare_question` now supports `shared_context` in `question_overrides.json` for future patches without DB changes
  - All 80 tests pass. Pushed to origin.

- **2026-05-03** (evening 3) — DB duplicate purge + OCR fix session. One commit pushed (`b31f40b`):
  - **Deleted 270 duplicate DB rows** across 7 exams (2017/2023a/2023b/2024a/2025a/2026_district/2026_invitationalb) that were double-ingested from the archive cache. HIGH severity findings: 313 → 43.
  - **OCR artifact normalization** in `normalize_answer_value`: strips leading non-alphanum chars (£, &) so garbled single-letter answers normalize correctly.
  - **College Station answer overrides**: confirmed Q1=E, Q7=B, Q11=C, Q15=E, Q23=E from visual PDF key inspection; added to `question_overrides.json`.
  - **Sanity queue fully cleared** — all 9 entries resolved (6 stale extended-choice flags, 1 stale fallback flag, 2 fixed by overrides).
  - **Discovered**: `2026_college_station` is a fully image-only scan (0 chars extractable on all 12 pages). All 40 questions have zero crop bounds — these will show invalid_crop_bounds in audit permanently unless OCR re-ingestion is done. New exam `2026_invitationalc` was found in the archive and now in DB.
  - Audit final state: **4064 questions, 721 findings (HIGH 43, MEDIUM 483, LOW 195)**. Remaining HIGHs: 40 invalid_crop_bounds (college_station image-only scan) + 3 answer_not_in_choices (Sample Test 2 Q39 across 3 exam versions).

- **2026-05-03** (evening 2) — UI overhaul session. Used the `ui-ux-pro-max` skill to redesign question content presentation. One commit pushed (`ad1967f`):
  - **Terminal-frame PDF images**: exam question crops now sit inside a styled window frame (traffic-light dots + "EXAM QUESTION" label) so they feel part of the UI rather than dropped in raw. Applied to both `question.html` and `test_mode.html` (with JS fallback handling).
  - **IDE-style code panels**: code blocks get a terminal title bar (dots + "Java" label). Long collapsible code uses the panel bar itself as the toggle. Shared context panels in test mode get same treatment.
  - **Keycap choice buttons**: A/B/C/D buttons styled as keyboard keys with 3D bottom shadow, lift-on-hover, press-on-active.
  - **Result box icons**: ✓/✗ prefix via CSS `::before`.
  - **`prefers-reduced-motion`** support added for all new animations.
  - Also fixed the desktop `.bat` launcher (was crashing on open due to `exec` replacing bash; now uses `-l` login shell + `; exec bash` to keep terminal open).

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
- DB has **4064 questions** across ~100 exams. Sanity queue is empty.
- Audit: 721 findings (HIGH 43, MEDIUM 483, LOW 195).
- Branch is ahead of `origin/main` with local UI/session-note commits not pushed yet. Deploy to PythonAnywhere pending after push.

## Active Blockers

- None

## Next Steps

- Deploy to PythonAnywhere (`git pull` + reload)
- Fix `answer_not_in_choices` × 3 for Sample Test 2 Q39 (Roman numeral Big-O question; choices parsed as empty — "I." at start gets parsed as choice label; needs PDF investigation)
- Address remaining `parse_feedback.jsonl` items:
  - `2025_district` Q17/19/20/21: graph/expression images missing — visual-only, not fixable without OCR
  - `2025_stacey_tests_test_07` Q16 / `2019_invitationala` Q27: crop shows partial code but text shared_context panel has full code — likely acceptable; users may just not notice the shared context panel
  - `2017_invitationalc` Q39: open-response with garbled choices — low priority
  - `2018_district` Q9: answer dispute already overridden as B
- Continue MEDIUM audit findings: `choice_labels_out_of_order` (187), `duplicate_choice_labels` (119), `footer_or_header_leakage` (53)

## Decisions Made

| Date | Decision | Reason |
|------|----------|--------|
| 2026-05-04 | Use one traditional Light/Dark toggle instead of multiple novelty themes | Keeps the interface practical and academic while still supporting users who prefer lower brightness |
| 2026-05-04 | shared_context recompute: only update DB directly when anchor code_block is empty | question_overrides.json now supports shared_context field for future patches without DB changes |
| 2026-05-04 | Leave 2026_college_station crop bounds unfixed for now | PDF is fully image-only (0 text chars); fixing requires full OCR re-ingestion; not worth it unless team specifically needs those Qs |
| 2026-05-03 | Align `evaluate_answer_sanity` with `should_use_visual_choice_fallback` | Sanity checker was flagging questions the UI handles fine via visual fallback — false positives |
| 2026-05-03 | Clear unrecoverable MCQ entries from sanity queue without fixing | Choices were never in the PDF text; visual fallback handles display; re-ingestion won't help |
| 2026-05-02 | Use `CLAUDE.md` + `SESSION_NOTES.md` committed to git for cross-machine context | Working across 3 machines; git sync is the simplest shared state |

## Parking Lot (ideas/todos not yet prioritized)

- Deploy updated code to PythonAnywhere after queue work is complete
- Consider adding a `skip_sanity` field to `question_overrides.json` to suppress specific questions from future sanity re-flags

---

_Last updated: 2026-05-04_
