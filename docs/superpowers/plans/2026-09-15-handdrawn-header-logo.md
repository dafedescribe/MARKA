# Hand-drawn Header and Reusable Logo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate A–E into ruled header cells and add one reusable teacher logo to printed sheets and receipts.

**Architecture:** Move both 20-row answer grids down by 10 mm and render a separate six-cell header above each. Normalize one authenticated logo upload to a small WebP data URL stored in `users.sheet_profile`, preserving it when text details change.

**Tech Stack:** Python, OpenCV, ReportLab, FastAPI, Supabase JSONB, React/Vite, pytest, Node test runner

---

### Task 1: Separate the objective headers

**Files:** Modify `data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json`, `scripts/generate_handdrawn_a4_40_guide.py`, `tests/handdrawn_synthetic.py`, `tests/test_handdrawn_profile.py`, `tests/test_handdrawn_registration.py`.

- [ ] Change the profile test to require `header_bounds_mm` of `[30,50,90,60]` and `[120,50,180,60]`, with answer `bounds_mm` shifted to `[30,60,90,260]` and `[120,60,180,260]`.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_handdrawn_profile.py` and confirm the old 50–250 geometry fails.
- [ ] Update the JSON profile and make both renderers draw the header as six 1 cm cells with labels `"", "A", "B", "C", "D", "E"`; keep scanner detection bound to the answer `bounds_mm` only.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_handdrawn_profile.py tests/test_handdrawn_registration.py` and confirm they pass.

### Task 2: Normalize and persist one logo

**Files:** Create `api/logo_profile.py`, `tests/test_logo_profile.py`; modify `api/server.py`.

- [ ] Add a focused failing test calling `normalize_logo(bytes)` with a real oversized PNG and invalid bytes, expecting a `data:image/webp;base64,` result no larger than 256 px and a `ValueError` for invalid input.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_logo_profile.py` and confirm the module/function is absent.
- [ ] Implement `normalize_logo` with `cv2.imdecode`, proportional resize, WebP quality 82, and a 120 KB encoded-data limit.
- [ ] Add authenticated `POST /profile/logo` and `DELETE /profile/logo`. Read the current JSON profile, change only `logo_b64`, and enforce a 2 MB upload limit. Change `PUT /profile/sheet` to merge text fields into the current profile so it cannot erase the server-managed logo.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_logo_profile.py api/test_server.py` and confirm they pass.

### Task 3: Render and expose the logo

**Files:** Modify `scripts/generate_v2_omr_sheet.py`, `src/receipt_generator.py`, `demo_site/src/components/Dashboard.jsx`, `demo_site/src/components/DashboardHome.jsx`.

- [ ] Decode `logo_b64` with strict error fallback and draw it inside the existing printed-sheet and receipt logo boxes with `preserveAspectRatio=True`; retain the placeholder when absent.
- [ ] Add a file input accepting PNG/JPEG/WebP, an image preview, Replace/Remove controls, and authenticated upload/remove handlers. Do not add a separate frontend abstraction or snapshot suite.
- [ ] Generate both PDFs locally and verify non-empty output, run the existing receipt/generator tests, frontend tests, and production build.

### Task 4: Release

**Files:** No additional feature files.

- [ ] Run `.venv/bin/python -m pytest -q`, `npm --prefix demo_site test -- --run`, `npm --prefix demo_site run build`, and `git diff --check`.
- [ ] Commit only owned files, push `main`, wait for Vercel Ready and Render OpenAPI to expose `/profile/logo`, then smoke-test health and unauthenticated route protection.
