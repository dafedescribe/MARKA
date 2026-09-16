# Signup Coupons and Print Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add limited, expiring marketing-coupon signup and remove unnecessary printed logo/header decoration.

**Architecture:** A locked Postgres RPC validates a hashed campaign code and atomically creates the account, increments usage, and records attribution. FastAPI owns code normalization and credential generation; the existing React signup form chooses coupon redemption or payment.

**Tech Stack:** PostgreSQL/Supabase, FastAPI, React/Vite, ReportLab, pytest, Node test runner

---

### Task 1: Coupon contract and database transaction

**Files:** Modify `supabase/migrations/20260916053959_signup_coupons.sql`; create `api/coupons.py`, `tests/test_coupons.py`.

- [ ] Write focused failing tests for `normalize_coupon_code` and SHA-256 `coupon_hash`.
- [ ] Implement trim/uppercase normalization with `^[A-Z0-9-]{4,40}$`, then hash the normalized value.
- [ ] Create RLS-enabled `coupon_campaigns` and `coupon_redemptions` tables with no client policies.
- [ ] Create `public.redeem_signup_coupon(p_code_hash, p_email, p_marka_id, p_pin_hash)` as `security invoker`; lock the campaign `FOR UPDATE`, validate active/expiry/limit, insert the user and redemption, increment usage, and return credentials/credits metadata.
- [ ] Revoke RPC execution from `public`, `anon`, and `authenticated`; grant it only to `service_role`.

### Task 2: Coupon signup endpoint and form

**Files:** Modify `api/server.py`, `api/test_server.py`, `demo_site/src/components/Auth.jsx`.

- [ ] Add rate-limited `POST /auth/redeem-coupon` accepting email and code, generating MARKA credentials, and calling the RPC with the code hash.
- [ ] Map unavailable campaigns to one neutral error and existing email to the current login/recovery guidance.
- [ ] Add optional coupon state/input to signup; when non-empty, redeem it instead of opening Paystack and reuse the existing success screen.
- [ ] Run focused backend tests, frontend tests, and the production build.

### Task 3: Print cleanup

**Files:** Modify `scripts/generate_v2_omr_sheet.py`, `src/receipt_generator.py`, `tests/test_v2_prototype_generator.py`.

- [ ] Update the generator contract test to reject the `MARKA ID / EXAM CODE` text.
- [ ] Draw a logo border only when no valid logo is rendered, on both printed sheets and receipts.
- [ ] Remove the printed `MARKA ID / EXAM CODE` header text and regenerate/inspect PDFs.

### Task 4: Apply and release

**Files:** No additional committed files.

- [ ] Run full Python/frontend/build verification and `git diff --check`; commit owned files.
- [ ] Apply the migration, verify table/RPC access, then insert the three approved campaigns directly using only their hashes.
- [ ] Push `main`, wait for Vercel/Render, and smoke-test the protected deployment without redeeming a production code.
