"""
MARKA API Server
Endpoints:
  POST /scan          — Upload image → extract marks → store → return raw marks
  POST /batch-scan    — Upload multiple images at once
  POST /answer-key    — Submit answer key for an exam code → retrograde all scans
  GET  /results/{code} — Get score table for an exam code
  GET  /result/{code}/{id} — Get individual graded image (rendered on demand)
  GET  /health        — Health check
"""

import sys
import os
# Add repo root (for omr_scanner et al.) AND this api/ dir (for database, auth)
# so bare imports resolve whether launched as `api.server:app` from the repo
# root (Render) or `server:app` from inside api/ (local dev).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, Depends, Response
from fastapi.security import OAuth2PasswordBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import tempfile
import json
import os
import logging

logger = logging.getLogger("marka")

LAYOUT_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "omr_layout.json")
try:
    with open(LAYOUT_JSON_PATH, "r") as f:
        GLOBAL_LAYOUT_DATA = json.load(f)
except Exception as e:
    GLOBAL_LAYOUT_DATA = None

import time
import queue
import threading
import hmac
import hashlib
import csv
import io
import cv2
import urllib.request
import urllib.error
import urllib.parse
import base64



from omr_scanner import read_bubbles, grade_and_render
from database import supabase
from auth import generate_marka_id, generate_pin, get_password_hash, verify_password, create_access_token
from pydantic import BaseModel, constr



limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="MARKA Grading API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Static frontend
STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'demo_site', 'dist')

# Allowed browser origins. Set ALLOWED_ORIGINS in the environment to a
# comma-separated list of your deployed frontend URLs (e.g. the Vercel domain).
# Falls back to local dev origins so `npm run dev` keeps working.
_default_origins = "http://localhost:5173,http://localhost:3000"
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Score"],
)

# ── Storage ───────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
EXAMS_DIR = os.path.join(os.path.dirname(__file__), '..', 'output_packages')
OMR_DIR = os.path.join(os.path.dirname(__file__), '..', 'omr_output')


# ── Credit packs (official pricing) ───────────────────────────────
# Paid amount (₦) → credits. Tiered packs must use a lookup, not a flat formula.
CREDIT_PACKS = {
    500: 50,       # Starter
    5000: 1000,    # Growth
    12500: 3000,   # Pro
    25000: 10000,  # Enterprise
}


def credits_for_amount(amount_naira) -> int:
    """Map a paid amount (₦) to credits per the official pack table.
    Non-standard amounts fall back to the Starter pack rate."""
    try:
        amt = int(round(float(amount_naira)))
    except (ValueError, TypeError):
        return 0
    if amt in CREDIT_PACKS:
        return CREDIT_PACKS[amt]
    return amt // 10


def get_exam_dir(exam_code: str) -> str:
    """Get or create the data directory for an exam code."""
    d = os.path.join(DATA_DIR, exam_code.upper())
    os.makedirs(os.path.join(d, 'scans'), exist_ok=True)
    os.makedirs(os.path.join(d, 'images'), exist_ok=True)
    os.makedirs(os.path.join(d, 'results'), exist_ok=True)
    return d


def find_layout_json(exam_code: str) -> str:
    """Find the omr_layout.json or exam.json for an exam code."""
    code = exam_code.upper()

    # Check omr_output first
    omr_path = os.path.join(OMR_DIR, 'omr_layout.json')
    if os.path.exists(omr_path):
        with open(omr_path) as f:
            data = json.load(f)
        if data.get("exam_code", "").upper() == code:
            return omr_path

    # Check output_packages (legacy exam compiler)
    if code == "DEMO":
        demo = os.path.join(EXAMS_DIR, 'CIVIC_EDUCATION_SS2_THIRD_TERM_EXAMINATION', 'exam.json')
        if os.path.exists(demo):
            return demo

    for folder in os.listdir(EXAMS_DIR) if os.path.isdir(EXAMS_DIR) else []:
        if folder.upper() == code:
            p = os.path.join(EXAMS_DIR, folder, 'exam.json')
            if os.path.exists(p):
                return p

    # Check data directory
    data_layout = os.path.join(DATA_DIR, code, 'layout.json')
    if os.path.exists(data_layout):
        return data_layout

    return None


def get_answer_key(exam_code: str) -> dict:
    """Load the answer key for an exam code, if it exists."""
    key_path = os.path.join(get_exam_dir(exam_code), 'answer_key.json')
    if os.path.exists(key_path):
        with open(key_path) as f:
            return json.load(f)

    # Also check if it's embedded in the layout JSON
    layout_path = find_layout_json(exam_code)
    if layout_path:
        with open(layout_path) as f:
            data = json.load(f)
        answers = data.get("answers", {})
        if answers:  # Non-empty answers dict
            return answers

    return None


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Decode our MARKA JWT and return the user's UUID (raises 401 if invalid)."""
    from jose import jwt, JWTError
    from auth import JWT_SECRET, ALGORITHM
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token")
    return user_id


# ── Endpoints ─────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "supabase": "connected" if supabase else "disconnected"}


# ── Pydantic Models ───────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str = None # Optional for magic link

class LoginRequest(BaseModel):
    marka_id: str
    pin: str

class ProcessScanRequest(BaseModel):
    scan_id: str
    exam_code: constr(max_length=50) = None  # type: ignore

class ExamRequest(BaseModel):
    exam_code: constr(max_length=50)  # type: ignore
    answers: dict  # {"1": "A", "2": "C", ...}

class TokenRequest(BaseModel):
    token: str


# ── Authentication Endpoints ──────────────────────────────────────

class PurchaseIdRequest(BaseModel):
    reference: str
    email: str

@app.post("/auth/purchase-id")
def purchase_id(req: PurchaseIdRequest):
    """Verify payment and generate a new MARKA ID and PIN."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")

    PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "paystack").lower()

    if PAYMENT_PROVIDER == "monnify":
        # ── Monnify verification flow ─────────────────────────────────
        MONNIFY_API_KEY = os.environ.get("MONNIFY_API_KEY", "")
        MONNIFY_SECRET = os.environ.get("MONNIFY_SECRET_KEY", "")
        if not MONNIFY_API_KEY or not MONNIFY_SECRET:
            raise HTTPException(500, "Monnify keys not configured")

        # Step 1: Authenticate to get Bearer token
        credentials = base64.b64encode(f"{MONNIFY_API_KEY}:{MONNIFY_SECRET}".encode()).decode()
        auth_url = "https://sandbox.monnify.com/api/v1/auth/login"
        auth_headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "User-Agent": "MARKA-Server/1.0",
        }
        auth_req = urllib.request.Request(auth_url, method="POST", headers=auth_headers, data=b"")

        try:
            with urllib.request.urlopen(auth_req, timeout=30) as response:
                auth_data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            print(f"Monnify auth HTTPError {e.code}: {body}")
            raise HTTPException(400, f"Monnify auth failed ({e.code}): {body}")
        except urllib.error.URLError as e:
            print(f"Monnify auth URLError: {e.reason}")
            raise HTTPException(400, f"Could not reach Monnify: {e.reason}")

        access_token = auth_data.get("responseBody", {}).get("accessToken", "")
        if not access_token:
            raise HTTPException(400, "Monnify auth did not return an access token")

        # Step 2: Verify transaction by paymentReference
        verify_url = f"https://sandbox.monnify.com/api/v2/merchant/transactions/query?paymentReference={urllib.parse.quote(req.reference)}"
        verify_headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "MARKA-Server/1.0",
            "Accept": "application/json",
        }
        verify_req = urllib.request.Request(verify_url, headers=verify_headers)

        try:
            with urllib.request.urlopen(verify_req, timeout=30) as response:
                res_data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            print(f"Monnify verify HTTPError {e.code}: {body}")
            raise HTTPException(400, f"Monnify verify failed ({e.code}): {body}")
        except urllib.error.URLError as e:
            print(f"Monnify verify URLError: {e.reason}")
            raise HTTPException(400, f"Could not reach Monnify: {e.reason}")

        payment_status = res_data.get("responseBody", {}).get("paymentStatus", "")
        if payment_status != "PAID":
            raise HTTPException(400, "Payment was not successful")

        # Monnify returns amount in Naira directly (not kobo)
        amount = res_data.get("responseBody", {}).get("amountPaid", 0)

    else:
        # ── Paystack verification flow (original) ─────────────────────
        PAYSTACK_SECRET = os.environ.get("PAYSTACK_SECRET_KEY", "")
        if not PAYSTACK_SECRET:
            raise HTTPException(500, "Paystack secret not configured")

        # Verify transaction with Paystack
        url = f"https://api.paystack.co/transaction/verify/{req.reference}"
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET}",
            # Paystack is behind Cloudflare, which 403s the default Python-urllib
            # User-Agent (error 1010). Any normal UA passes.
            "User-Agent": "MARKA-Server/1.0",
            "Accept": "application/json",
        }
        req_obj = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req_obj, timeout=30) as response:
                res_data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            print(f"Paystack verify HTTPError {e.code}: {body}")
            raise HTTPException(400, f"Paystack verify failed ({e.code}): {body}")
        except urllib.error.URLError as e:
            print(f"Paystack verify URLError: {e.reason}")
            raise HTTPException(400, f"Could not reach Paystack: {e.reason}")

        if not res_data.get("status") or res_data.get("data", {}).get("status") != "success":
            raise HTTPException(400, "Payment was not successful")

        data = res_data["data"]
        amount = data.get("amount", 0) / 100
    credits_to_add = credits_for_amount(amount)

    # 2. Idempotency Check in transactions table (we use 'NEW_ID' as marka_id for the record)
    try:
        supabase.table("transactions").insert({
            "reference": req.reference,
            "marka_id": "NEW_USER_CREATION",
            "amount": amount,
            "credits_added": credits_to_add
        }).execute()
    except Exception as e:
        if "duplicate key value" in str(e).lower() or "23505" in str(e):
            raise HTTPException(400, "This payment reference has already been used.")
        raise HTTPException(500, "Database error recording transaction")

    # 3. Generate Credentials
    marka_id = generate_marka_id()
    pin = generate_pin()
    pin_hash = get_password_hash(pin)
    
    # 4. Create User
    try:
        supabase.table("users").insert({
            "marka_id": marka_id,
            "pin_hash": pin_hash,
            "email": req.email,
            "credits": credits_to_add
        }).execute()
        
        return {
            "marka_id": marka_id,
            "pin": pin,
            "credits": credits_to_add,
            "message": "Payment verified. Please save your MARKA ID and PIN securely!"
        }
    except Exception as e:
        if "duplicate key value" in str(e).lower() or "23505" in str(e):
            raise HTTPException(400, "Email is already registered. Please login and use 'Top Up', or use 'Forgot PIN' to recover your credentials.")
        raise HTTPException(400, f"Error creating user: {str(e)}")


@app.post("/auth/login")
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest):
    """Login with MARKA ID and PIN to get a JWT."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")
        
    try:
        res = supabase.table("users").select("*").eq("marka_id", req.marka_id.upper()).execute()
        if not res.data:
            raise HTTPException(401, "Invalid MARKA ID or PIN")
            
        user = res.data[0]
        if not verify_password(req.pin, user['pin_hash']):
            raise HTTPException(401, "Invalid MARKA ID or PIN")
            
        # Mint Custom JWT
        access_token = create_access_token(data={"sub": user['id']})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "credits": user['credits']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


class ForgotPinRequest(BaseModel):
    email: str

@app.post("/auth/forgot-pin")
@limiter.limit("3/minute")
def forgot_pin(request: Request, req: ForgotPinRequest):
    """Initiate the Forgot PIN flow."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")

    res = supabase.table("users").select("marka_id").eq("email", req.email).execute()
    if not res.data:
        # Don't leak whether the email exists
        return {"message": "If that email is registered, a recovery link has been sent."}

    marka_id = res.data[0]["marka_id"]

    # SECURITY: never return the MARKA ID / PIN in the API response — that would
    # let anyone recover any account from a known email (account takeover), and
    # PINs are stored unhashed. Proper recovery must email a short-lived reset
    # link (Resend/SendGrid) to the address on file. Until that's wired up, we
    # only log and return the same generic message as the not-found case.
    # TODO: send a real recovery email to req.email for MARKA ID {marka_id}.
    logger.info(f"Forgot-PIN requested for MARKA ID {marka_id} (email delivery not yet implemented)")

    return {"message": "If that email is registered, a recovery link has been sent."}


# ── Exam / Answer-Key Endpoints ───────────────────────────────────

@app.post("/exams")
@limiter.limit("10/second")
def create_or_update_exam(request: Request, req: ExamRequest, user_id: str = Depends(get_current_user)):
    """Create or update an exam's answer key (stored per-user in the DB)."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")
    code = (req.exam_code or "").strip().upper()
    if not code:
        raise HTTPException(400, "exam_code is required")
    if not req.answers:
        raise HTTPException(400, "answers cannot be empty")
    if len(req.answers) > 200:
        raise HTTPException(400, "Maximum of 200 questions allowed per exam.")

    # Normalise. A value may be a single option ("A"), a list of accepted
    # options (["A","C"]), or "*" for a bonus (any answer counts).
    def _norm(v):
        if isinstance(v, list):
            opts = [str(x).strip().upper() for x in v if str(x).strip()]
            return opts[0] if len(opts) == 1 else opts
        return str(v).strip().upper()
    answers = {str(k): _norm(v) for k, v in req.answers.items()}

    try:
        existing = supabase.table("exams").select("id").eq(
            "user_id", user_id).eq("exam_code", code).execute()
        if existing.data:
            exam_id = existing.data[0]["id"]
            supabase.table("exams").update({"answer_key": answers}).eq("id", exam_id).execute()
        else:
            ins = supabase.table("exams").insert({
                "user_id": user_id, "exam_code": code, "answer_key": answers
            }).execute()
            exam_id = ins.data[0]["id"]
    except Exception as e:
        raise HTTPException(500, f"Could not save exam: {e}")

    return {"exam_id": exam_id, "exam_code": code, "num_questions": len(answers)}


@app.get("/exams")
@limiter.limit("10/second")
def list_exams(request: Request, user_id: str = Depends(get_current_user)):
    """List the current user's exams (for the exam picker)."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")
    res = supabase.table("exams").select("exam_code, answer_key, created_at").eq(
        "user_id", user_id).order("created_at", desc=True).execute()
    return {"exams": [
        {"exam_code": e["exam_code"],
         "num_questions": len(e.get("answer_key") or {}),
         "answer_key": e.get("answer_key") or {},
         "created_at": e.get("created_at")}
        for e in (res.data or [])
    ]}


# ── Upload Endpoints ──────────────────────────────────────────────

@app.get("/upload/presigned-url")
@limiter.limit("10/second")
def get_presigned_url(request: Request, scan_id: str, user_id: str = Depends(get_current_user)):
    """
    Generate a presigned URL for direct-to-Supabase upload.
    """
    if not supabase:
        raise HTTPException(500, "Supabase not configured")

    import re
    if not re.match(r'^[\w-]+$', scan_id):
        raise HTTPException(400, "Invalid scan_id format")

    # Check credits before allowing upload
    user_res = supabase.table("users").select("credits, marka_id").eq("id", user_id).execute()
    if user_res.data:
        user_data = user_res.data[0]
        if user_data.get("marka_id") != "DEMO-TEST" and user_data.get("credits", 0) <= 0:
            raise HTTPException(402, "Insufficient credits to upload scan")

    # Generate presigned URL for the 'raw_images' bucket
    # Path format: <user_id>/<scan_id>.jpg
    file_path = f"{user_id}/{scan_id}.jpg"
    try:
        # Supabase python client currently has create_signed_upload_url
        res = supabase.storage.from_("raw_images").create_signed_upload_url(file_path)
        return {
            "upload_url": res['signed_url'],
            "path": file_path,
            "scan_id": scan_id
        }
    except Exception as e:
        raise HTTPException(500, str(e))


def process_scan_background(scan_id: str, exam_code: str, user_id: str):
    """Background task to process a scan uploaded to Supabase."""
    if not supabase:
        print("Error: Supabase not configured")
        return

    # The frontend always uploads to this deterministic path before calling us, so
    # we can clean it up in `finally` no matter where we bail out. The raw photo is
    # the biggest storage cost (3-5MB) and is never reused once grading is attempted
    # — a retry re-uploads from the browser. Previously it was only deleted on the
    # success path, so every failed scan leaked its upload forever.
    raw_path = f"{user_id}/{scan_id}.jpg"

    try:
        code = (exam_code or "").strip().upper()

        # 1. Fetch user info
        user_res = supabase.table("users").select("credits, marka_id").eq("id", user_id).execute()
        user_data = user_res.data[0] if user_res.data else {"credits": 0, "marka_id": ""}
        
        is_demo = user_data.get("marka_id") == "DEMO-TEST"
        if not is_demo and user_data.get("credits", 0) <= 0:
            raise ValueError("Insufficient credits to process this scan.")

        # Resolve this user's exam (if they created one) → exam_id + DB answer key.
        exam_id = None
        db_answer_key = None
        exam_res = supabase.table("exams").select("id, answer_key").eq(
            "user_id", user_id).eq("exam_code", code).execute()
        if exam_res.data:
            exam_id = exam_res.data[0]["id"]
            db_answer_key = exam_res.data[0].get("answer_key")

        supabase.table("scans").insert({
            "scan_id": scan_id,
            "user_id": user_id,
            "exam_id": exam_id,
            "status": "processing"
        }).execute()


        # 2. Download image from raw_images bucket
        img_bytes = supabase.storage.from_("raw_images").download(raw_path)

        # File signature validation (magic numbers)
        if not (img_bytes.startswith(b'\xff\xd8\xff') or img_bytes.startswith(b'\x89PNG\r\n\x1a\n')):
            raise ValueError("Uploaded file is not a valid JPEG or PNG image.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name

        # 3. Process image. All exams share the standard MARKA sheet layout;
        # fall back to it when the exam_code has no bundled layout of its own.
        layout_path = find_layout_json(code) or find_layout_json("MARKA")
        if not layout_path and not GLOBAL_LAYOUT_DATA:
            raise ValueError(f"No OMR layout available for exam '{code}'.")

        result = read_bubbles(tmp_path, GLOBAL_LAYOUT_DATA or layout_path)
        result["scan_id"] = scan_id

        # Ensure answer key exists
        is_demo = user_data.get("marka_id") == "DEMO-TEST"
        answers = db_answer_key
        if not answers:
            if is_demo:
                answers = get_answer_key(code)
            else:
                raise ValueError(f"No answer key found for exam '{code}'. Please create the exam key first.")

        graded_file_path = None
        score = None
        total = None
        percentage = None

        if answers:
            out_path = tmp_path.replace(".jpg", "_graded.jpg")
            grade_result = grade_and_render(result, answers, tmp_path, GLOBAL_LAYOUT_DATA or layout_path, out_path)
            score = grade_result["score"]
            total = grade_result["total"]
            percentage = grade_result["percentage"]

            graded_img = cv2.imread(out_path)

            # Apply Heavy Watermark if DEMO-TEST
            if is_demo:
                h, w = graded_img.shape[:2]
                cv2.putText(graded_img, "MARKA DEMO", (int(w*0.1), int(h*0.4)), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 8, cv2.LINE_AA)
                cv2.putText(graded_img, "NOT FOR PRODUCTION", (int(w*0.05), int(h*0.6)), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 6, cv2.LINE_AA)

            # Compress the graded proof to WebP to protect storage budget
            ok, webp_buf = cv2.imencode(".webp", graded_img, [cv2.IMWRITE_WEBP_QUALITY, 60])
            if not ok or webp_buf is None:
                # Fallback if WebP is unsupported by this OpenCV build
                ok, img_buf = cv2.imencode(".jpg", graded_img, [cv2.IMWRITE_JPEG_QUALITY, 70])
                graded_file_path = f"{user_id}/{scan_id}.jpg"
                ctype = "image/jpeg"
            else:
                img_buf = webp_buf
                graded_file_path = f"{user_id}/{scan_id}.webp"
                ctype = "image/webp"

            supabase.storage.from_("graded_images").upload(
                graded_file_path, img_buf.tobytes(), {"content-type": ctype})
            os.unlink(out_path)

        # (the raw upload is removed in `finally` — on success *and* failure)

        # 4. Deduct credit atomically
        # Only deduct if not DEMO-TEST (DEMO-TEST has unlimited but restricted scans)
        if user_data.get("marka_id") != "DEMO-TEST":
            supabase.rpc("deduct_credit", {"user_uuid": user_id}).execute()


        # 5. Update scan record
        supabase.table("scans").update({
            "status": "success",
            "score": score,
            "total": total,
            "percentage": percentage,
            "raw_marks": result,
            "image_path": None,  # raw wiped immediately post-grade
            "graded_image_path": graded_file_path
        }).eq("scan_id", scan_id).execute()

    except Exception as e:
        logger.error(f"Error processing scan {scan_id}: {e}", exc_info=True)
        try:
            supabase.table("scans").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("scan_id", scan_id).execute()
        except Exception as db_err:
            logger.error(f"CRITICAL: Failed to mark scan {scan_id} as failed: {db_err}", exc_info=True)
    finally:
        # Always reclaim the raw upload, however grading ended. Best-effort: a
        # failure here must never mask the real outcome of the scan.
        try:
            supabase.storage.from_("raw_images").remove([raw_path])
        except Exception as e:
            logger.warning(f"Could not delete raw image {raw_path}: {e}")
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Serialized grading queue ──────────────────────────────────────
#
# Grading is memory-hungry (OpenCV decode + warp + render on multi-megapixel
# phone photos). Running several at once on a small instance exhausts it and the
# scans die with "[Errno 11] Resource temporarily unavailable" — observed live
# when a 3-sheet batch was submitted at once: two of the three failed.
#
# FastAPI's BackgroundTasks would run every scan concurrently, so instead we hand
# jobs to a single long-lived worker thread that grades them one at a time. The
# endpoint returns immediately (just an enqueue), memory stays bounded no matter
# how large a batch the user drops in, and throughput is unchanged in practice
# since grading was never actually parallel-friendly on this hardware.
#
# uvicorn runs a single process here (no --workers), so one worker thread means
# exactly one grading job in flight process-wide.
_scan_queue: "queue.Queue" = queue.Queue()


def _scan_worker():
    """Drain the scan queue, grading one sheet at a time, forever."""
    while True:
        job = _scan_queue.get()
        try:
            scan_id, exam_code, user_id = job
            process_scan_background(scan_id, exam_code, user_id)
        except Exception:
            # process_scan_background already records failures on the scan row;
            # this is a last-resort guard so one bad job can never kill the worker.
            logger.error("Scan worker crashed on job %r", job, exc_info=True)
        finally:
            _scan_queue.task_done()


@app.on_event("startup")
def _start_scan_worker():
    threading.Thread(target=_scan_worker, name="marka-scan-worker", daemon=True).start()
    logger.info("Scan worker started (grading is serialized, 1 at a time)")


@app.post("/process-scan")
@limiter.limit("10/second")
def trigger_process_scan(request: Request, req: ProcessScanRequest, user_id: str = Depends(get_current_user)):
    """Queue a scan for grading after the frontend uploads the image to Supabase."""

    # Ensure user has credits
    if supabase:
        user_res = supabase.table("users").select("credits").eq("id", user_id).execute()
        if not user_res.data or user_res.data[0]['credits'] <= 0:
            raise HTTPException(402, "Insufficient credits")

    _scan_queue.put((req.scan_id, req.exam_code, user_id))
    return {
        "message": "Processing started",
        "scan_id": req.scan_id,
        "queue_depth": _scan_queue.qsize(),
    }


def _fetch_export_scans(user_id: str, exam_code: str):
    """Shared by the CSV and PDF exports: return (code, scans, answer_key) for
    this user's successful scans, scoped to the exam when an exam row exists."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")

    code = (exam_code or "").strip().upper()
    query = supabase.table("scans").select("*").eq("user_id", user_id).eq("status", "success")
    exam_res = supabase.table("exams").select("id, answer_key").eq(
        "user_id", user_id).eq("exam_code", code).execute()
    answer_key = {}
    if exam_res.data:
        query = query.eq("exam_id", exam_res.data[0]["id"])
        answer_key = exam_res.data[0].get("answer_key") or {}
    res = query.execute()
    if not res.data:
        raise HTTPException(404, "No successful scans found to export.")
    return code, res.data, answer_key


def _missed_answers(marks: dict, answer_key: dict) -> dict:
    """Questions the student did NOT get right, mapped to the correct answer.
    Mirrors grade_and_render's rules: "A" single, ["A","C"] any-accepted, "*"
    bonus (never missed). A blank/None student answer counts as missed."""
    missed = {}
    for q, correct in (answer_key or {}).items():
        if correct == "*" or correct == ["*"]:
            continue  # bonus — cannot be missed
        accepted = {str(c).strip().upper() for c in (correct if isinstance(correct, list) else [correct])}
        student = marks.get(str(q))
        if student not in accepted:
            missed[str(q)] = sorted(accepted)[0] if accepted else "?"
    return missed


@app.get("/export/{exam_code}/csv")
@limiter.limit("10/second")
def export_results_csv(request: Request, exam_code: str, user_id: str = Depends(get_current_user)):
    """Download the results as a single CSV (one row per scan, per-question marks)."""
    code, scans, _ = _fetch_export_scans(user_id, exam_code)

    all_questions = set()
    for s in scans:
        marks = (s.get("raw_marks") or {}).get("marks", {})
        all_questions.update(marks.keys())

    q_keys = sorted(all_questions, key=lambda x: int(x) if str(x).isdigit() else x)

    csv_io = io.StringIO()
    writer = csv.writer(csv_io)
    writer.writerow(["Scan ID", "Score", "Total", "Percentage"] + [f"Q{k}" for k in q_keys])
    for s in scans:
        marks = (s.get("raw_marks") or {}).get("marks", {})
        writer.writerow(
            [s["scan_id"], s["score"], s["total"], s["percentage"]]
            + [marks.get(str(k), "") for k in q_keys]
        )

    return Response(
        content=csv_io.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{code}_results.csv"'},
    )


@app.get("/export/{exam_code}/pdf")
@limiter.limit("10/second")
def export_results_pdf(request: Request, exam_code: str, user_id: str = Depends(get_current_user)):
    """Download printable assessment receipts (one slip per scan: score + the
    corrections the student needs). Replaces the old graded-image ZIP."""
    from receipt_generator import generate_receipts_pdf

    code, scans, answer_key = _fetch_export_scans(user_id, exam_code)

    results_list = []
    for s in scans:
        marks = (s.get("raw_marks") or {}).get("marks", {})
        results_list.append({
            "subject": code,
            "student_name": s["scan_id"],
            "score": s.get("score") or 0,
            "total": s.get("total") or 0,
            "missed": _missed_answers(marks, answer_key),
            "receipt_id": s["scan_id"],
        })

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        pdf_path = tmp_pdf.name
    try:
        generate_receipts_pdf(results_list, pdf_path)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{code}_receipts.pdf"'},
    )


# ── Retention: 7-day image wipe ───────────────────────────────────

def wipe_expired_images(days: int = 7) -> dict:
    """Delete raw + graded images for standard scans older than `days`, 
    and DEMO-TEST scans older than 15 minutes. Scores and records are kept."""
    if not supabase:
        return {"error": "supabase not configured"}
    import datetime as _dt
    
    now = _dt.datetime.now(_dt.timezone.utc)
    standard_cutoff = (now - _dt.timedelta(days=days)).isoformat()
    demo_cutoff = (now - _dt.timedelta(minutes=15)).isoformat()

    # Find DEMO-TEST user
    demo_res = supabase.table("users").select("id").eq("marka_id", "DEMO-TEST").execute()
    demo_user_id = demo_res.data[0]["id"] if demo_res.data else None

    # Get standard scans older than 7 days OR demo scans older than 15 mins
    res = supabase.table("scans").select(
        "id, user_id, image_path, graded_image_path, created_at"
    ).or_(f"image_path.not.is.null,graded_image_path.not.is.null").execute()
    
    targets = []
    for s in (res.data or []):
        is_demo = (s["user_id"] == demo_user_id)
        created = s["created_at"]
        if is_demo and created < demo_cutoff:
            targets.append(s)
        elif not is_demo and created < standard_cutoff:
            targets.append(s)

    files_deleted = 0
    for s in targets:
        for bucket, col in (("raw_images", "image_path"),
                            ("graded_images", "graded_image_path")):
            p = s.get(col)
            if p:
                try:
                    supabase.storage.from_(bucket).remove([p])
                    files_deleted += 1
                except Exception as e:
                    logger.warning(f"wipe: {bucket}/{p} failed: {e}")
        try:
            supabase.table("scans").update(
                {"image_path": None, "graded_image_path": None}).eq("id", s["id"]).execute()
        except Exception as e:
            logger.error(f"wipe: db update failed for scan {s['id']}: {e}")

    return {"scans_affected": len(targets), "files_deleted": files_deleted}


@app.post("/admin/wipe-expired")
def admin_wipe_expired(days: int = 7, x_cron_secret: str = Header(None)):
    """Delete images older than `days` (default 7). Call daily from a cron
    (e.g. cron-job.org) with the X-Cron-Secret header set to CRON_SECRET."""
    secret = os.environ.get("CRON_SECRET", "")
    if not secret or x_cron_secret != secret:
        raise HTTPException(401, "Invalid or missing cron secret")
    return wipe_expired_images(days)


@app.post("/scans/{scan_id}/wipe-image")
def wipe_scan_image(scan_id: str, user_id: str = Depends(get_current_user)):
    """Let a user delete a scan's stored images early to reclaim space.
    The scan record and score are kept — only the image files are removed."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")

    res = supabase.table("scans").select(
        "id, user_id, image_path, graded_image_path").eq("scan_id", scan_id).execute()
    if not res.data:
        raise HTTPException(404, "Scan not found")
    s = res.data[0]
    if s["user_id"] != user_id:
        raise HTTPException(403, "Not your scan")

    for bucket, col in (("raw_images", "image_path"), ("graded_images", "graded_image_path")):
        p = s.get(col)
        if p:
            try:
                supabase.storage.from_(bucket).remove([p])
            except Exception as e:
                logger.warning(f"wipe-image: {bucket}/{p} failed: {e}")
    supabase.table("scans").update(
        {"image_path": None, "graded_image_path": None}).eq("id", s["id"]).execute()
    return {"ok": True, "scan_id": scan_id}


@app.delete("/scans/{scan_id}")
def delete_scan(scan_id: str, user_id: str = Depends(get_current_user)):
    """Remove a scan entirely — its images and the record itself.

    Distinct from /wipe-image, which frees the image files but keeps the score.
    This is what the Library's delete button calls, so users can prune failed or
    unwanted scans without a manual DB cleanup.
    """
    if not supabase:
        raise HTTPException(500, "Supabase not configured")

    res = supabase.table("scans").select(
        "id, user_id, image_path, graded_image_path").eq("scan_id", scan_id).execute()
    if not res.data:
        raise HTTPException(404, "Scan not found")
    s = res.data[0]
    if s["user_id"] != user_id:
        raise HTTPException(403, "Not your scan")

    # Drop the stored images first so a mid-way failure can't orphan them: if the
    # row goes but the files remain, nothing points at them any more.
    for bucket, col in (("raw_images", "image_path"), ("graded_images", "graded_image_path")):
        p = s.get(col)
        if p:
            try:
                supabase.storage.from_(bucket).remove([p])
            except Exception as e:
                logger.warning(f"delete-scan: {bucket}/{p} failed: {e}")

    supabase.table("scans").delete().eq("id", s["id"]).execute()
    return {"ok": True, "scan_id": scan_id, "deleted": True}


@app.post("/scans/wipe-all-raw")
def wipe_all_raw(request: Request, user_id: str = Depends(get_current_user)):
    """Wipe all raw, original images to reclaim storage space without losing grades."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")
        
    res = supabase.table("scans").select("id, image_path").eq("user_id", user_id).not_.is_("image_path", "null").execute()
    paths = [s["image_path"] for s in res.data if s.get("image_path")]
    
    if paths:
        # Remove in chunks of 100
        for i in range(0, len(paths), 100):
            try:
                supabase.storage.from_("raw_images").remove(paths[i:i+100])
            except Exception as e:
                logger.warning(f"wipe-all-raw failed on chunk: {e}")
                
        try:
            supabase.table("scans").update({"image_path": None}).eq("user_id", user_id).not_.is_("image_path", "null").execute()
        except Exception as e:
            logger.error(f"Failed to update db after wipe-all: {e}")
            
    return {"ok": True, "deleted": len(paths)}

class OverrideRequest(BaseModel):
    q_num: str
    new_option: str

@app.post("/scans/{scan_id}/override")
def override_mark(scan_id: str, req: OverrideRequest, user_id: str = Depends(get_current_user)):
    """Manually override an ambiguous or incorrectly read mark."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")
        
    s_res = supabase.table("scans").select("*").eq("scan_id", scan_id).eq("user_id", user_id).execute()
    if not s_res.data:
        raise HTTPException(404, "Scan not found")
    scan = s_res.data[0]
    
    raw_marks = scan.get("raw_marks", {})
    if not raw_marks or "marks" not in raw_marks:
        raise HTTPException(400, "No raw marks found for this scan")
        
    # Apply override
    raw_marks["marks"][req.q_num] = req.new_option
    
    if req.q_num in raw_marks.get("ambiguous", []):
        raw_marks["ambiguous"].remove(req.q_num)
        
    # Recalculate score
    exam_id = scan.get("exam_id")
    exam_res = supabase.table("exams").select("answer_key").eq("user_id", user_id).eq("id", exam_id).execute()
    answers = exam_res.data[0]["answer_key"] if exam_res.data else {}
    
    score = 0
    total = len(answers)
    for q_str, correct in answers.items():
        student_ans = raw_marks["marks"].get(q_str)
        is_bonus = correct == "*" or correct == ["*"]
        if is_bonus:
            score += 1
            continue
        accepted = {str(c).strip().upper() for c in correct} if isinstance(correct, list) else {str(correct).strip().upper()}
        if student_ans in accepted:
            score += 1
            
    pct = round((score / total) * 100, 1) if total > 0 else 0
    
    supabase.table("scans").update({
        "raw_marks": raw_marks,
        "score": score,
        "percentage": pct
    }).eq("id", scan["id"]).execute()
    
    return {"ok": True, "score": score, "percentage": pct, "raw_marks": raw_marks}


# ── Webhook Endpoints ─────────────────────────────────────────────

@app.post("/webhook/paystack")
async def paystack_webhook(request: Request, x_paystack_signature: str = Header(None)):
    """Handle Paystack webhooks to add credits."""
    import os
    PAYSTACK_SECRET = os.environ.get("PAYSTACK_SECRET_KEY", "")
    
    payload = await request.body()
    
    # Verify signature
    hash = hmac.new(PAYSTACK_SECRET.encode('utf-8'), payload, hashlib.sha512).hexdigest()
    if hash != x_paystack_signature:
        raise HTTPException(400, "Invalid signature")
        
    data = json.loads(payload)
    
    if data.get("event") == "charge.success":
        # Extract user email or reference
        # In a real app, you'd pass the MARKA ID or user_id in the metadata
        metadata = data.get("data", {}).get("metadata", {})
        marka_id = metadata.get("marka_id")
        if not marka_id:
            for field in metadata.get("custom_fields", []):
                if field.get("variable_name") == "marka_id":
                    marka_id = field.get("value")
                    break

        amount = data.get("data", {}).get("amount", 0) / 100 # Assuming NGN/Kobo
        reference = data.get("data", {}).get("reference")
        
        credits_to_add = credits_for_amount(amount)
        
        if marka_id and reference and supabase:
            # 1. Idempotency Check: Prevent duplicate webhooks
            try:
                supabase.table("transactions").insert({
                    "reference": reference,
                    "marka_id": marka_id.upper(),
                    "amount": amount,
                    "credits_added": credits_to_add
                }).execute()
            except Exception as e:
                # 23505 is the Postgres error code for unique_violation
                if "duplicate key value" in str(e).lower() or "23505" in str(e):
                    print(f"Ignored duplicate webhook for reference: {reference}")
                    return {"status": "success", "message": "Duplicate ignored"}
                print(f"Error recording transaction: {e}")
                return {"status": "error"}

            # 2. Add Credits securely
            try:
                supabase.rpc("add_credits_by_marka_id", {"m_id": marka_id.upper(), "amount": credits_to_add}).execute()
            except Exception as rpc_err:
                print(f"RPC add_credits_by_marka_id failed (maybe not defined?): {rpc_err}")
                # Fallback to direct update
                u_res = supabase.table("users").select("id, credits").eq("marka_id", marka_id.upper()).execute()
                if u_res.data:
                    uid = u_res.data[0]["id"]
                    old_credits = u_res.data[0]["credits"]
                    supabase.table("users").update({"credits": old_credits + credits_to_add}).eq("id", uid).execute()

    return {"status": "success"}


@app.post("/webhook/monnify")
async def monnify_webhook(request: Request):
    """Handle Monnify webhooks to add credits."""
    MONNIFY_SECRET = os.environ.get("MONNIFY_SECRET_KEY", "")

    payload = await request.body()

    # Verify signature (HMAC-SHA512 of body using secret key)
    monnify_sig = request.headers.get("monnify-signature", "")
    computed_hash = hmac.new(MONNIFY_SECRET.encode('utf-8'), payload, hashlib.sha512).hexdigest()
    if computed_hash != monnify_sig:
        raise HTTPException(400, "Invalid signature")

    data = json.loads(payload)

    if data.get("eventType") == "SUCCESSFUL_TRANSACTION":
        event_data = data.get("eventData", {})
        reference = event_data.get("paymentReference")
        amount = event_data.get("amountPaid", 0)  # Already in Naira
        meta = event_data.get("metaData", {})
        marka_id = meta.get("marka_id")

        credits_to_add = credits_for_amount(amount)

        if marka_id and reference and supabase:
            # 1. Idempotency Check: Prevent duplicate webhooks
            try:
                supabase.table("transactions").insert({
                    "reference": reference,
                    "marka_id": marka_id.upper(),
                    "amount": amount,
                    "credits_added": credits_to_add
                }).execute()
            except Exception as e:
                # 23505 is the Postgres error code for unique_violation
                if "duplicate key value" in str(e).lower() or "23505" in str(e):
                    print(f"Ignored duplicate Monnify webhook for reference: {reference}")
                    return {"status": "success", "message": "Duplicate ignored"}
                print(f"Error recording Monnify transaction: {e}")
                return {"status": "error"}

            # 2. Add Credits securely
            try:
                supabase.rpc("add_credits_by_marka_id", {"m_id": marka_id.upper(), "amount": credits_to_add}).execute()
            except Exception as rpc_err:
                print(f"RPC add_credits_by_marka_id failed (maybe not defined?): {rpc_err}")
                # Fallback to direct update
                u_res = supabase.table("users").select("id, credits").eq("marka_id", marka_id.upper()).execute()
                if u_res.data:
                    uid = u_res.data[0]["id"]
                    old_credits = u_res.data[0]["credits"]
                    supabase.table("users").update({"credits": old_credits + credits_to_add}).eq("id", uid).execute()

    return {"status": "success"}


# ── Legacy filesystem endpoints removed in Phase 1 ────────────────
# /scan, /batch-scan, /answer-key, /results, /result, /grade wrote to the
# local `data/` folder — no auth, no credit deduction, and wiped on every
# Render redeploy (ephemeral disk). The single production path is now
# Supabase-backed: presigned upload → /process-scan (BackgroundTasks) →
# /export. The OMR engine can still be exercised directly via the CLI in
# `omr_scanner.py`. Real Supabase-backed batch upload is Phase 1.4.


# ── Mount frontend (must be last!) ────────────────────────────────

if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
