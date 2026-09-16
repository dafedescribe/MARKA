# MARKA Library, Receipt Fields, and Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Ship reliable image clearing, durable handwritten receipt fields, saved school branding, answer-sheet downloads, session expiry, and live Paystack configuration.

**Architecture:** Keep result rows in Supabase, make all Storage deletion retry-safe, and treat the Library as a view of live proof images. Persist small field crops inside each scan result, store one bounded sheet-profile JSON object per user, and generate PDFs on demand. Keep the existing custom seven-day JWT and enforce its expiry in the browser.

**Tech Stack:** FastAPI, Supabase/Postgres/Storage, OpenCV, ReportLab, React/Vite, pytest, Node test runner, Render, Vercel, Paystack

---

### Task 1: Repair Library deletion

**Files:** Modify `api/server.py`, `api/test_server.py`, `demo_site/src/components/Dashboard.jsx`, `DashboardHome.jsx`, `Gallery.jsx`; create `demo_site/src/lib/library.js` and test.

- [ ] Add failing API tests proving bulk clear removes both buckets, clears only successful paths, preserves results, and retains failed paths/rows for retry.
- [ ] Add failing frontend tests proving assetless scans are excluded and stored-image count ignores result-only rows.
- [ ] Implement a bounded `POST /scans/clear-library` operation and make individual deletion fail retryably instead of orphaning objects.
- [ ] Replace the misleading raw-only button, update state immediately, and show partial failures.
- [ ] Run focused Python and Node tests; commit.

### Task 2: Enforce browser session expiry

**Files:** Create `demo_site/src/lib/session.js` and test; modify `demo_site/src/App.jsx`, `Dashboard.jsx`.

- [ ] Write failing tests for malformed, expired, and live JWT expiry parsing.
- [ ] Implement `getTokenExpiryMs` and `isTokenUsable`.
- [ ] Reject expired tokens before dashboard render, schedule logout at `exp`, and log out on API 401.
- [ ] Run focused tests; commit.

### Task 3: Persist exact student handwriting

**Files:** Modify `scripts/generate_v2_omr_sheet.py`, `data/MARKA/layout.json`, `src/omr_scanner.py`, `src/handdrawn_scanner.py`, `data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json`, `api/server.py`, `src/receipt_generator.py`, and focused tests.

- [ ] Write failing geometry tests for printed canonical fields and the hand-drawn 15 cm × 2 cm Name/Class/Subject strip.
- [ ] Write failing tests that field crops are bounded WebP data and receipt payloads receive them.
- [ ] Normalize printed field coordinates, extract crops during grading, and attach only compressed field data to `raw_marks`.
- [ ] Detect/crop the hand-drawn identity strip after anchor rectification without making answer grading depend on field success.
- [ ] Pass field crops into receipt generation with scan-ID fallback.
- [ ] Regenerate the committed layouts, run focused scanner/receipt tests; commit.

### Task 4: Save school details and stream sheets

**Files:** Create a Supabase migration; modify `api/server.py`, both PDF generators, `receipt_generator.py`, `DashboardHome.jsx`, and tests.

- [ ] Create a migration adding `users.sheet_profile jsonb not null default '{}'`.
- [ ] Add failing API tests for authenticated profile read/write, length validation, branded R07-E PDF, and hand-drawn guide PDF.
- [ ] Implement profile endpoints and bounded two-line school/address fitting.
- [ ] Add a compact dashboard editor and two download buttons.
- [ ] Apply and verify the live migration, run advisors and focused tests; commit.

### Task 5: Production Paystack and release

**Files:** Deployment environments only; no credentials in Git.

- [ ] Validate the supplied file contains one live public and one live secret key without printing them.
- [ ] Set `VITE_PAYSTACK_PUBLIC_KEY` and `VITE_PAYMENT_PROVIDER=paystack` in Vercel Production.
- [ ] Set `PAYSTACK_SECRET_KEY` and `PAYMENT_PROVIDER=paystack` in Render Production using existing deployment authorization; if unavailable, report the exact single manual action without exposing the value.
- [ ] Verify server-side transaction amount/status checks and webhook HMAC remain active.
- [ ] Run the full Python, Deno, and frontend suites plus production build.
- [ ] Push `main`, observe Render/Vercel Ready, smoke-test APIs/downloads/assets, reconcile the existing orphan through the Storage API, and securely erase rollout temp files.
