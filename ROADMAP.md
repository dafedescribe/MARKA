# MARKA — Production Roadmap

**Purpose:** Sequenced, prioritized plan to get MARKA safely onto **Render (backend)** + **Vercel (frontend)**, then build the feature checklist on solid ground.

**Reading order matters.** Each phase depends on the one before it. Don't build the gallery (Phase 3) on a backend that doesn't boot (Phase 0) or that has two conflicting storage models (Phase 1).

**Legend:** 🔴 blocker · 🟠 high · 🟡 medium · 🟢 nice-to-have · ⏱ rough effort

---

## 📍 Current status snapshot (updated 2026-07-13)

Live: Render backend + Vercel frontend, custom domain `marka.com.ng`. ✅ = done · 🟡 = partial · ⬜ = not started.

**Phase 0 — Deploy blockers:** ✅ complete (deps, opencv-headless, render.yaml, CORS pinned, secrets in env, live). 🟡 `demo_site/.env.example` untracked.

**Phase 1 — One code path:** ✅ legacy endpoints removed · ✅ scan/exam_id wiring · ✅ per-exam export · ✅ exams table + per-exam keys · 🟡 batch = sequential queue (not parallel `/process-batch`).

**Phase 2 — Correctness/security:** ✅ credit-pack math · ✅ JWT in header · ✅ slowapi rate limit · ✅ atomic credit deduct · ✅ RLS verified · ✅ file-signature check (magic numbers, server.py) · 🟡 full field validators (MARKA ID/PIN/email regex) not confirmed.

**Phase 3 — Features:**
- 3A Dashboard: ✅ credits+buy · ✅ "mark now" · ✅ gallery
- 3B Results gallery: ✅ grid · ✅ lightbox · ✅ per-sheet download · ✅ CSV/ZIP export · 🟡 no multi-select download
- 3C Batch UX: 🟡 blur flag (client-side, advisory) · ✅ per-image status · ⬜ ~50/batch cap · 🟡 no real `needs_review` backend status
- 3D Image lifecycle: ✅ WebP compress · ✅ delete raw post-grade · ✅ delete-to-reclaim · ✅ expiry countdown · 🟡 7-day auto-wipe endpoint built, **cron NOT activated**
- 3E Payments/signup: ✅ e2e signup→buy→ID/PIN→login · ✅ Forgot PIN · 🟡 webhook idempotency (coded, unverified)
- 3F Demo/trial: 🟡 demo auth + printable sheet exist · ⬜ once-per-visitor download guard · ⬜ demo auto-wipe/rate cap
- 3G Bonuses: ⬜ undefined — needs product decision

**Phase 4 — Scale:** ⬜ Render always-on/keep-warm · ⬜ grading concurrency cap · ⬜ job queue

**Extra shipped:** scanner speed pass · pricing matches official table · bonus/multiple-answer grading + builder UI · **custom-domain sign-in outage fixed** (env-var wipe) · Tailwind UI overhaul + SEO + printable sheet (collaborator) · unset-question guard.

**⚠️ Known bugs / decisions open:**
- ✅ **A–E fix DONE** — builder `optionsCount` now 5, so E is keyable (was hardcoded to 4).
- ✅ **Over-grading DONE** — non-demo scans now require a saved key (no bundled 100-Q fallback); `total = len(your key)`, grades only keyed questions.
- ✅ **Blank-scored-correct DONE** — stricter read threshold (0.35).
- ✅ **Upside-down detection FIXED** — the original brightness heuristic false-rejected real upright sheets (footer darker than header + shadowed photos). Replaced with a QR-texture (variance top-right vs bottom-left) check, validated on a real photo (upright accepted, flipped rejected).
- ✅ **Dark/low-contrast photo reading FIXED** — replaced the single global threshold with (1) CLAHE local-contrast normalization on the aligned image and (2) a per-question *local* threshold that judges each bubble against the blank paper of its own row, so lighting gradients no longer defeat it. On the real shadowed phone photo, detection went 9 → 27 of ~30 marks with zero false positives on the blank columns and **no regression** on clean/flat/blank/synthetic sheets (identical counts old vs new). Capture-guidance tips shipped on the Scan & Grade screen. Threshold held at ratio 0.28/margin 22 by evidence: on the sample photos, loosening to recover the faintest under-filled marks *provably* introduced false positives in the sheets' own blank regions (marks that light are physically indistinguishable from paper smudges) — precision-first is correct for grading.
- ✅ **3-fiducial reconstruction FIXED** — when the top-right fiducial fuses with the adjacent QR block (happens at some angles) the detector found only 3 corners and the scan hard-failed ("didn't grade / didn't land in bucket"). The 4 fiducials form a rectangle, so a missing corner is now reconstructed geometrically (reflection through the diagonal midpoint), with a degeneracy guard. Recovered a real sample sheet (SP1) to a clean grade; **zero change** to any image that already found 4 corners.
- 🟠 **Forgot-PIN recovery disabled** — returned plaintext MARKA ID/PIN (account-takeover); now returns a generic message only. Needs real emailed reset link (Resend/SendGrid). PINs are also stored unhashed — hash them.
- ✅ **OMR Library blank / "in bucket but not in app" FIXED** — root cause: the frontend authenticated the Supabase client with `auth.setSession({ access_token, refresh_token: '' })`, which fails with "Auth session missing!" (empty refresh token) and silently falls back to the anon role. All client-side reads (scans list, credit refresh) then returned 0 rows with no error → "No scans found" even though grading succeeded and the graded image was in storage. Fix: MARKA's backend JWT is now supplied via supabase-js's `accessToken` callback (`lib/supabase.js` + `setSupabaseToken`), so every PostgREST/Storage/Realtime request is authenticated as the user and RLS returns their rows. Verified end-to-end with the real user token (scans query + signed URL both succeed). Also: `fetchScans` now surfaces a real load error instead of showing an empty "No scans found", and the empty state distinguishes "no scans yet" from a failed load.
- 🟡 **"Image not served"** — colleague's WebP→JPEG fallback added, but WebP works on Render, so the real cause is unconfirmed; needs a specific failing scan to diagnose.
- ✅ **Free-tier concurrency FIXED** — a batch graded concurrently on Render free (512 MB) exhausted memory and died with `[Errno 11] Resource temporarily unavailable` (live test: 2 of 3 sheets failed when submitted at once). FastAPI `BackgroundTasks` ran every scan in parallel; grading is now handed to a single long-lived worker thread via an in-process queue (`_scan_queue` + `_scan_worker` in `api/server.py`), so exactly one sheet grades at a time and memory stays bounded regardless of batch size. `/process-scan` still returns immediately (enqueue only) and reports `queue_depth`. uvicorn runs a single process (no `--workers`), so one worker thread = one job in flight process-wide.
- 🔑 Activate 7-day wipe cron (`CRON_SECRET` on Render + cron-job.org → `/admin/wipe-expired`).
- 💳 Paystack still TEST mode — flip `pk_live`+`sk_live` together to go live.
- 📧 Enterprise "Contact us" placeholder `hello@marka.ng` → real address.
- 💰 Render free tier (~50s cold start) — paid always-on for production.
- 🔹 Minor: tab title still "demo_site"; "Delete original images" button is a "coming soon" placeholder.

---

## Phase 0 — Deploy blockers (backend won't run without these)

> Goal: `git push` → Render builds → server boots → `/health` returns 200.

| # | Task | Why | Sev | ⏱ |
|---|------|-----|-----|----|
| 0.1 | Complete `requirements.txt`: add `supabase`, `python-jose[cryptography]`, `bcrypt`, `python-dotenv` | Server imports these; build succeeds but crashes on first import | 🔴 | S |
| 0.2 | Swap `opencv-python` → `opencv-python-headless` | Headless servers lack `libGL.so.1`; import crashes | 🔴 | S |
| 0.3 | Add `render.yaml` + start command `uvicorn api.server:app --host 0.0.0.0 --port $PORT` | Render needs a launch instruction | 🔴 | S |
| 0.4 | Pin CORS to the Vercel origin; drop `allow_origins=["*"]` while `allow_credentials=True` | Invalid combo — browsers reject it | 🔴 | S |
| 0.5 | Move all secrets to Render env vars (`JWT_SECRET`, `SUPABASE_*`, `PAYSTACK_SECRET_KEY`); remove hardcoded JWT fallback | `JWT_SECRET` silently defaults to a public string = forgeable tokens | 🔴 | S |
| 0.6 | Add `.env.example` for both backend + `demo_site` (already started — finish it) | Onboarding + deploy config clarity | 🟡 | S |
| 0.7 | Confirm `demo_site/dist` build strategy | Vercel serves the frontend; Render should **not** also mount static files in prod (the `StaticFiles` mount at server.py:822 is for local dev) | 🟠 | S |

**Exit criteria:** Backend live on Render, `/health` green, frontend on Vercel talking to it via `VITE_API_URL`.

---

## Phase 1 — Consolidate the architecture (one code path)

> There are currently **two contradictory paths**. This phase deletes one.

**Legacy/local path** (`/scan`, `/batch-scan`, `/grade`, `/answer-key`, `/results`, `/result`) writes to the local `data/` folder — **no auth, no credit deduction, and wiped on every Render redeploy (ephemeral disk).**

**Production path** (`/upload/presigned-url`, `/process-scan`, `/export`) uses Supabase + JWT + credit deduction. **The frontend Dashboard already uses this one.**

| # | Task | Sev | ⏱ |
|---|------|-----|----|
| 1.1 | Delete legacy filesystem endpoints (or gate them behind a local-dev flag) | 🟠 | M |
| 1.2 | Fix `scans` insert: duplicate `scan_id` key (server.py:299–303) and actually link `exam_id` | 🟠 | S |
| 1.3 | Make `/export` filter by exam so CSV/zip are per-exam, not per-user-everything | 🟠 | S |
| 1.4 | Build **real batch upload** on the Supabase model: N presigned URLs → parallel client uploads → one `/process-batch` trigger → per-image status | 🔴 (your "check if batch works" item) | L |
| 1.5 | Establish the `exams` table + answer-key-per-exam flow in Postgres (not local JSON files) | 🟠 | M |

**Exit criteria:** Every user action flows through Supabase-backed, authenticated, credit-aware endpoints. Redeploys lose nothing.

---

## Phase 2 — Correctness, security & input validation

| # | Task | Why | Sev |
|---|------|-----|-----|
| 2.1 | **Fix credit math.** `int(amount/100)` gives ₦5,000 → 50 credits (should be 100) and ignores tiers. Use a pack lookup table (see below). | Users get half the credits they paid for | 🔴 |
| 2.2 | Move JWT/token out of query strings (`/process-scan`, presigned) into `Authorization` header | Tokens leak into logs/history | 🟠 |
| 2.3 | Add Pydantic validators for every input: `marka_id` (`^MK-[A-Z0-9]{4}$`), `pin` (4 digits), exam code, email format | Your "input validation for every field" item | 🟠 |
| 2.4 | File-signature (magic-number) validation before OpenCV touches an upload | Plan §7 — reject disguised non-images | 🟡 |
| 2.5 | Rate limiting via `slowapi`: login 5/min/IP, process 10/s/IP | Plan §7 — anti-brute-force/DDoS | 🟡 |
| 2.6 | Row-level credit deduction using atomic `UPDATE ... WHERE credits > 0 RETURNING` | Plan §4 — prevents concurrent double-spend | 🟠 |
| 2.7 | Verify Supabase RLS actually enforces per-user isolation with the custom JWT | Plan §7 — data isolation | 🟠 |

### Credit pack lookup (replace `amount/100`)

| Pack | Credits | Price (₦) | ₦/credit |
|------|--------:|----------:|---------:|
| Starter | 100 | 5,000 | 50 |
| Growth | 250 | 11,250 | 45 |
| School | 500 | 20,000 | 40 |
| Institution | 1,000 | 35,000 | 35 |
| Enterprise | 5,000+ | Custom | Negotiated |

Map the **paid amount** (or a `pack` field in Paystack metadata) to credits from this table. Reject amounts that don't match a known pack.

---

## Phase 3 — Core product features (the checklist)

Built only after Phases 0–2. Grouped by user-visible surface.

### 3A. Dashboard on login
- [ ] Credit balance count + "Buy more" CTA — 🟠
- [ ] "Mark now" primary prompt — 🟠
- [ ] Gallery of previously marked exams — 🟠 (see 3B)

### 3B. Results gallery
- [ ] Grid of all marked items (thumbnails) — 🟠
- [ ] Click to expand a single graded sheet — 🟠
- [ ] Download: individual / selected / all (zip) — 🟠 (`/export` is the seed; add selection)
- [ ] **CSV of scores** — `Paper 1, Score 1` format + per-question columns (logic exists in `/export`, needs UI) — 🟠

### 3C. Batch marking UX
- [ ] Cap **~50 images/batch** (200-image user = 4 batches) — 🟡
- [ ] **Process clear sheets, flag unclear** — never reject the whole batch — 🔴 decision (see Decisions)
- [ ] Per-image status: `success` / `needs_review` (blurry) / `failed`, with re-shoot prompt for flagged only — 🟠
- [ ] **Red warning** on unclear images identifying which photo — 🟠

### 3D. Image lifecycle & storage
- [ ] **Compress graded image to `.webp` ~80–150KB** (legible, not archival) — 🔴 (storage survival)
- [ ] **Delete raw upload immediately after successful grade** — 🔴 (see Storage Model) — this is THE storage lever
- [ ] User "delete exam images to reclaim space" button — 🟠 (your image-management item)
- [ ] **7-day auto-wipe** of graded images via Supabase cron/edge function; scores persist in Postgres forever — 🟠
- [ ] **"Files expire in 6 days" red countdown** in the UI — 🟡

### 3E. Payments & signup
- [ ] End-to-end test: signup → buy credit → receive MARKA ID + PIN "success card" → login — 🔴
- [ ] Idempotent webhook (unique `reference`) — already coded, verify it — 🟡
- [ ] "Forgot PIN" magic-link recovery via email (Plan §2.2) — 🟢

### 3F. Demo / trial (landing page)
- [ ] Public `DEMO-TEST` credentials, heavy red watermark (coded — verify) — 🟡
- [ ] **Downloadable trial OMR sheet, once per visitor** — needs a one-download guard (token/cookie + server check) — 🟠
- [ ] Demo scans auto-wiped every 15 min; 20 scans/hr/IP cap — 🟡

### 3G. Bonuses
- [ ] Define what "bonuses" means (referral credits? volume bonus? promo?) — **needs product decision before build** — 🟡

---

## Phase 4 — Scale & performance hardening

| # | Task | Notes |
|---|------|-------|
| 4.1 | **Pay for Render always-on ($7/mo)** OR keep-warm ping every ~10 min (cron-job.org → `/health`) | Free tier sleeps 15 min → ~50s cold start kills the "instant" promise. On login, fire `/health` + show "warming up…" state. There is no "webhook to spin up" — keep-warm is the mechanism. |
| 4.2 | Concurrency cap on grading (semaphore, 4–8 in-flight) | `BackgroundTasks` run in-process on one dyno and are CPU-bound. 1000 concurrent = OOM. Uploads are fine (direct to Supabase). |
| 4.3 | Post-MVP: real job queue (worker + Redis, or Supabase Edge Function) | Only when volume justifies it. |
| 4.4 | Don't over-optimize the scanner | `read_bubbles` is already fast (numpy ROI). Real latency = cold start + image download, not the algorithm. "10ms" is per **image**, not per question. |

---

## Cross-cutting decisions (recommended defaults)

| Question | Recommendation |
|----------|----------------|
| Clear-and-ignore vs. stop-all on a bad batch photo? | **Process the clear ones, flag the unclear.** Per-image status; re-shoot only flagged; zero credits for non-graded. |
| Batch size? | **~50/batch.** |
| Speed target? | **<10ms/image reading** (already met). Optimize cold start, not the algorithm. |
| Keep raw images? | **No.** Delete on successful grade; keep only compressed graded webp; scores live in Postgres forever. |
| Render tier? | **Paid always-on** for production credibility. |

---

## Storage capacity model (1GB Supabase, ≥200 images/user)

The single most important number in this project.

- Raw phone photo ≈ **3–5MB**. **200 raw images × 5MB = ~1GB = your entire budget for ONE user.** Keeping raw images is fatal.
- **Fix:** delete raw the instant grading succeeds; keep only graded `.webp` at ~**120KB**.
- Then: 200 graded images ≈ **~24MB/user** → 1GB holds **~30–40 full user batches** within any active window.
- **Recommended policy:**
  - Delete raw immediately post-grade.
  - Graded webp target 80–150KB.
  - Retain graded images **~48h–7 days**, then wipe.
  - **Cap ~500 images per active window per user.**
  - Scores (Postgres text) are tiny → keep forever; users re-download CSV months later.

---

## MCPs to set up (excluding Supabase, which stays as-is)

| MCP | Purpose | Priority |
|-----|---------|----------|
| **Render** | Deploy/manage backend, env vars, tail logs | ✅ Must-have |
| **Vercel** | Deploy frontend, env vars, build/runtime logs | ✅ Must-have |
| **GitHub** | CI/CD, repo management, auto-deploy on push | ✅ Recommended |
| **Sentry** (or similar) | Production error monitoring | 🟢 Valuable |

**Note on RevenueCat (currently connected):** it targets App Store / Play Store subscriptions, **not** Paystack web card payments. For a Nigerian web credit-pack model it likely adds nothing — Paystack has no official MCP and is handled via its REST API (already done). **Consider dropping RevenueCat** unless native mobile apps are planned. Paystack: no MCP needed; keep using its API + webhook.

---

## Suggested execution order (one-line summary)

**0 (boot) → 1 (one path) → 2 (correctness/security) → 3 (features) → 4 (scale).**

Nothing in Phase 3 is worth building until Phases 0–1 make the backend deployable and single-pathed.
