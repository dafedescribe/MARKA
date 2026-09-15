# MARKA Library, Receipt Fields, and Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship retry-safe image-library clearing, persistent handwritten receipt fields, saved school details, answer-sheet downloads, and truthful seven-day browser sessions.

**Architecture:** Keep large proof images in the existing Supabase buckets, but persist small field crops inside `raw_marks.fields_b64`. Add a bounded server-side image cleanup helper and account sheet-profile JSON. Keep frontend behavior in small pure helpers so expiry and Library filtering are directly testable.

**Tech Stack:** FastAPI, Supabase Python/Storage, OpenCV, ReportLab, React/Vite, Node test runner, pytest

---

### Task 1: Fix session and Library presentation

**Files:**
- Create: `demo_site/src/lib/session.js`
- Create: `demo_site/src/lib/session.test.js`
- Create: `demo_site/src/lib/library.js`
- Create: `demo_site/src/lib/library.test.js`
- Modify: `demo_site/src/App.jsx`
- Modify: `demo_site/src/components/Dashboard.jsx`
- Modify: `demo_site/src/components/DashboardHome.jsx`

- [ ] Write failing tests that `tokenExpiryMs` rejects malformed/expired JWTs and that `visibleLibraryScans` retains only scans with `graded_image_path`.
- [ ] Run `npm --prefix demo_site test -- --run` and confirm the new tests fail.
- [ ] Implement the helpers, initialize the token only when unexpired, schedule logout at `exp`, and clear auth on API 401.
- [ ] Rename the dashboard action to **Clear image library**, show stored-image count, and filter image-less cards before rendering.
- [ ] Run frontend tests and build.

### Task 2: Make image clearing retry-safe

**Files:**
- Create: `api/image_cleanup.py`
- Create: `tests/test_image_cleanup.py`
- Modify: `api/server.py`
- Modify: `api/test_server.py`

- [ ] Write failing tests for raw+graded deletion, 100-object batching, partial failure, retained paths on failure, and row retention.
- [ ] Run the focused pytest files and confirm RED.
- [ ] Implement `clear_user_image_library(supabase, user_id)` returning aggregate counts only.
- [ ] Add `POST /scans/clear-library`; keep the old raw-only route as a compatibility alias to the same safe operation.
- [ ] Make individual scan deletion stop before row deletion when any referenced Storage removal fails.
- [ ] Run focused tests and confirm GREEN.

### Task 3: Connect printed identity fields to receipts

**Files:**
- Modify: `scripts/generate_v2_omr_sheet.py`
- Modify: `data/MARKA/layout.json`
- Modify: `src/omr_scanner.py`
- Modify: `api/server.py`
- Modify: `src/receipt_generator.py`
- Modify: `tests/test_v2_prototype_generator.py`
- Modify: `tests/test_r07_scanner.py`
- Create: `tests/test_receipt_fields.py`

- [ ] Write failing tests for one canonical `fields_mm` contract, border-inset WebP crops, receipt crop passthrough, and scan-ID fallback.
- [ ] Run focused pytest and confirm RED.
- [ ] Emit `fields_mm` with keys `name`, `student_id`, `class`, `subject`, and `date`.
- [ ] Extract bounded grayscale WebP crops during printed grading and store them at `raw_marks.fields_b64`.
- [ ] Pass `fields_b64` into receipt records and render all available fields.
- [ ] Regenerate `data/MARKA/layout.json` and run focused tests.

### Task 4: Add the hand-drawn Name/Class/Subject strip

**Files:**
- Modify: `data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json`
- Modify: `src/handdrawn_scanner.py`
- Modify: `scripts/generate_handdrawn_a4_40_guide.py`
- Modify: `tests/handdrawn_synthetic.py`
- Modify: `tests/test_handdrawn_profile.py`
- Modify: `tests/test_handdrawn_registration.py`

- [ ] Write failing tests for the 15 cm × 2 cm, 8/3/4 cm strip and three border-inset crops.
- [ ] Run focused pytest and confirm RED.
- [ ] Add canonical strip geometry, draw it in the guide/synthetic sheet, and extract Name/Class/Subject from the rectified page.
- [ ] Attach crops to the existing hand-drawn result without making identity extraction a grading rejection.
- [ ] Run focused tests and benchmark contracts.

### Task 5: Save school details and deliver PDFs

**Files:**
- Create: `migrations/003_add_sheet_profile.sql`
- Modify: `migrations/001_initial_schema.sql`
- Modify: `api/server.py`
- Modify: `scripts/generate_v2_omr_sheet.py`
- Modify: `src/receipt_generator.py`
- Modify: `demo_site/src/components/DashboardHome.jsx`
- Modify: `api/test_server.py`
- Modify: `tests/test_v2_prototype_generator.py`

- [ ] Write failing tests for profile validation, two-line fitting, branded R07-E PDF, generic hand-drawn guide PDF, and receipt branding.
- [ ] Run focused tests and confirm RED.
- [ ] Add `users.sheet_profile jsonb not null default '{}'`.
- [ ] Add authenticated GET/PUT `/profile/sheet-details` with explicit length limits.
- [ ] Add authenticated GET `/templates/r07e.pdf` and `/templates/handdrawn-a4-40.pdf`.
- [ ] Add the compact saved-details form and two download buttons.
- [ ] Run focused backend/frontend tests and production build.

### Task 6: Deploy and reconcile

**Files:**
- Modify: `docs/supabase_image_retention_runbook.md`

- [ ] Run full Python, Deno, frontend test/build, lint, formatting, and `git diff --check`.
- [ ] Apply the profile migration to linked Supabase and verify the column/default.
- [ ] Deploy/push `main`, then verify Render health/routes and matching Vercel assets.
- [ ] Remove only confirmed orphaned Storage objects through the Storage API and verify aggregate object/path consistency.
- [ ] Record warnings and exact live outcomes without secrets or user data.
