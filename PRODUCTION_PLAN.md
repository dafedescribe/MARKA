# MARKA Technical Product Requirements Document & Production Plan

This document serves as the master blueprint for the production-ready MARKA platform. It outlines the rigorous, exploit-proof, and highly scalable architecture designed to handle thousands of concurrent users safely and efficiently while maintaining extremely low operational costs on free-tier infrastructure.

---

## 1. Core Philosophy: The Belief-Changing Paradigm

MARKA is not positioned as just a software tool; it is a belief-changing solution. The core messaging, **"Keep the Paper. Eliminate the Marking,"** is designed to bypass institutional friction. We do not ask schools to buy computers, train teachers on complex LMS software, or abandon physical exams. We simply remove the pain of manual grading. 

Every technical decision in this document is driven by the need for **frictionless adoption, zero-trust security, and hyper-efficiency**.

---

## 2. Frictionless Authentication & Account Recovery

Traditional SaaS relies on email verification and complex passwords, which are massive drop-off points for our target demographic. 

### 2.1 The "ID + PIN" System
Upon purchasing a credit bundle, the system instantly generates a unique **MARKA ID** (e.g., `MK-8A2F`) and a random **4-Digit PIN**. This is immediately displayed as a downloadable "Success Card" image. This is all the user needs to log in. No email verification loops.

### 2.2 Account Recovery (The "Forgot PIN" Protocol)
Because we use a PIN system, we need a safety net if the user loses their Success Card.
*   **Invisible Email Linking:** When purchasing via Paystack, an email is mandatory for the receipt. We silently map this email to their `MARKA ID` in our Postgres database.
*   **The Magic Link Recovery:** If a user clicks "Forgot PIN", they are prompted for the email they used to pay. The backend emails them a one-time, time-expiring Magic Link. Clicking this logs them in securely and displays their `MARKA ID` and `PIN` on screen so they can re-record it. This guarantees account recovery without adding friction to the signup funnel.

---

## 3. Blazing Fast UX & PWA Architecture

The application must feel instantaneous, even on 3G networks in rural areas.

*   **Progressive Web App (PWA):** The Vite/React frontend will be configured as a strict PWA using Workbox. HTML, CSS, JS bundles, and static assets are cached locally on the device on first load. Subsequent page loads will be **sub-100ms** because they do not require network requests for UI rendering.
*   **Optimistic UI Updates:** When a user taps "Upload", the UI instantly creates a "Processing..." skeleton card before the network request finishes. This prevents the screen from freezing and eliminates frustrating loading spinners.
*   **Direct-to-Supabase Uploads (Bypassing the Backend):** To handle 200,000+ simultaneous image uploads (e.g., 1,000 users × 200 sheets), images *do not* go through our FastAPI backend. The frontend requests a short-lived **Presigned URL** from the backend and pushes the 5MB images directly into the edge-cached Supabase Storage Bucket. The backend is completely unburdened and strictly handles logic, not heavy file transport.

---

## 4. Bulletproof Payment & Credit Security

Payments are the most vulnerable part of any SaaS. We implement strict anti-fraud measures.

*   **Webhook Signature Verification:** Attackers will attempt to spoof Paystack webhooks to generate free credits. The FastAPI backend will strictly validate the `x-paystack-signature` header using HMAC SHA512 against our `PAYSTACK_SECRET_KEY`. Any payload failing this check is instantly dropped (401 Unauthorized).
*   **Idempotency Keys:** Paystack may send the same successful payment webhook multiple times due to network retries. We enforce a unique database constraint on the `transaction_reference` column. If a webhook attempts to insert a duplicate reference, the database rejects it, preventing double-crediting.
*   **Row-Level Locks for Deductions:** When a scan begins, we use PostgreSQL's `SELECT ... FOR UPDATE` or an atomic `UPDATE users SET credits = credits - 1 WHERE credits > 0 RETURNING credits`. This guarantees that even if a script sends 500 concurrent requests in 1 millisecond, the database serializes them, making it impossible to bypass the credit limit.

---

## 5. The Deduction Lifecycle (Ensuring Absolute Fairness)

To build trust, we must never unfairly penalize users for system failures or bad inputs.

*   **No Charge on Upload or Download:** Credits are **NOT** deducted when an image is uploaded, nor are they deducted when results are downloaded.
*   **Deduction on Success Only:** A credit is deducted **ONLY** when an image is successfully scanned, anchor points are detected, and it is fully graded by the OpenCV worker.
*   **Handling Bad Inputs:** If a teacher uploads a blurry photo, a picture of their desk, or a heavily damaged OMR sheet, the engine will fail to detect the OMR structure. The scan is marked as "Failed," the user is shown an error ("Image too blurry, please retake"), and **no credit is deducted**.
*   **Unlimited Downloads:** Once successfully graded, the resulting data belongs to the user. They can view the results on the dashboard or download the `.zip` archive of graded images as many times as they want for free. 

---

## 6. Storage Management & Retention Policy

Operating on the Supabase Free/Starter Tier limits us to 1GB of storage. We cannot act as an infinite cloud drive for massive image files.

*   **The 7-Day Auto-Wipe Policy:** We are a processing pipeline, not an archive. All raw uploaded images, graded images, and `.zip` files are held in the Supabase bucket for a strict **7-Day window**. A Supabase Edge Function or external Cron Job automatically deletes files older than 7 days.
*   **UI Transparency:** The dashboard will prominently display a countdown next to exams: *"Files expire in 6 days, 14 hours. Please download your backups."*
*   **Perpetual Database Storage:** The actual grades (e.g., "Student 104 scored 45/50", question choices) are stored as text in the Postgres database. This data is extremely lightweight and will be kept permanently. A user can always return months later to view or download the CSV score table, even after the visual images have been wiped.
*   **Aggressive Image Compression:** Before the OpenCV worker saves the "graded" image (the visual proof with green/red circles), it converts the image to `.webp` format at 60% quality. It does not need to be high-res; it just needs to be legible. This reduces 2MB files to ~150KB, vastly extending our 1GB runway.

---

## 7. Strict Security & Data Isolation

*   **Row-Level Security (RLS):** The Supabase database will have strict RLS policies. A user with ID `MK-1234` cannot read or write to exams belonging to `MK-5678`. The database engine itself enforces this via the JWT session token, making data leaks physically impossible at the API layer.
*   **File Signature Validation (Magic Numbers):** Attackers will try to upload executable scripts (e.g., `.php`) renamed as `.jpg`. The FastAPI backend will read the first 2048 bytes of the file to verify the true MIME type (magic numbers) before the OpenCV worker touches it.
*   **Rate Limiting:** Using `slowapi` on the FastAPI backend, we will enforce:
    *   **Login Endpoint:** Max 5 attempts per minute per IP (prevents PIN brute-forcing).
    *   **Upload/API Endpoints:** Max 10 requests per second per IP (prevents DDoS).

---

## 8. The Demo/Trial Mechanics (Preventing Abuse)

To allow marketing with a downloadable trial PDF OMR sheet without opening the system to abuse by institutions trying to bypass payments.

*   **The Static Trial Account:** We will provision a hardcoded `MARKA ID` (e.g., `DEMO-TEST`) with its PIN published publicly.
*   **Unlimited but Restricted:** This account has "unlimited" credits, but is heavily crippled for real-world use:
    1.  **Heavy Watermarking:** Every image graded by this account will have a massive red watermark across the center: **"MARKA DEMO - NOT FOR PRODUCTION EXAMS"**. This destroys its utility for actual school records.
    2.  **Volatile Storage:** Scans uploaded to the DEMO account are automatically wiped from the database and storage every **15 minutes**.
    3.  **Strict IP Rate Limiting:** The DEMO account is restricted to 20 scans per hour per IP address to prevent malicious actors from using it to drain our compute resources.

---

## 9. Result Export Pipeline

Once scans are processed asynchronously using FastAPI `BackgroundTasks` (our Render Free Tier MVP alternative to Celery/Redis):

*   **CSV Generation:** The backend instantly generates a CSV aggregating `scan_id`, `score`, `percentage`, and individual question selections.
*   **Visual Proof Archive:** The graded images (with drawn green/red circles) are bundled into a `.zip` file.
*   **Secure Delivery:** Both artifacts are saved to Supabase Storage, and the user receives a secure, time-expiring download link (valid for 1 hour) for the `.zip` to ensure student data isn't permanently sitting on a public URL.
