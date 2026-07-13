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

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, Depends
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
import hmac
import hashlib
import zipfile
import csv
import io
import cv2
import urllib.request
import urllib.error



from omr_scanner import read_bubbles, grade_and_render
from database import supabase
from auth import generate_marka_id, generate_pin, get_password_hash, verify_password, create_access_token
from pydantic import BaseModel



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
# Paid amount (₦) → credits. The per-credit rate differs per pack, so this
# must be a lookup, not a flat formula.
CREDIT_PACKS = {
    5000: 100,     # Starter      — ₦50/credit
    11250: 250,    # Growth       — ₦45/credit
    20000: 500,    # School       — ₦40/credit
    35000: 1000,   # Institution  — ₦35/credit
}


def credits_for_amount(amount_naira) -> int:
    """Map a paid amount (₦) to credits per the official pack table.
    Non-standard amounts fall back to the base ₦50/credit rate."""
    amt = int(round(amount_naira))
    if amt in CREDIT_PACKS:
        return CREDIT_PACKS[amt]
    return amt // 50


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
    exam_code: str

class ExamRequest(BaseModel):
    exam_code: str
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

    PAYSTACK_SECRET = os.environ.get("PAYSTACK_SECRET_KEY", "")
    if not PAYSTACK_SECRET:
        raise HTTPException(500, "Paystack secret not configured")

    # 1. Verify transaction with Paystack
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

    try:
        code = (exam_code or "").strip().upper()

        # 1. Fetch user info
        user_res = supabase.table("users").select("credits, marka_id").eq("id", user_id).execute()
        user_data = user_res.data[0] if user_res.data else {"credits": 0, "marka_id": ""}

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
        file_path = f"{user_id}/{scan_id}.jpg"
        img_bytes = supabase.storage.from_("raw_images").download(file_path)

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

        # Answer key: the user's DB exam key takes precedence; else the bundled key.
        answers = db_answer_key or get_answer_key(code)
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
            if user_data.get("marka_id") == "DEMO-TEST":
                h, w = graded_img.shape[:2]
                cv2.putText(graded_img, "MARKA DEMO", (int(w*0.1), int(h*0.4)), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 8, cv2.LINE_AA)
                cv2.putText(graded_img, "NOT FOR PRODUCTION", (int(w*0.05), int(h*0.6)), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 6, cv2.LINE_AA)

            # Compress the graded proof to WebP (~60% quality) to protect the 1GB
            # storage budget — a ~2MB JPEG becomes ~100-150KB, still legible.
            ok, webp_buf = cv2.imencode(".webp", graded_img, [cv2.IMWRITE_WEBP_QUALITY, 60])
            graded_file_path = f"{user_id}/{scan_id}.webp"
            supabase.storage.from_("graded_images").upload(
                graded_file_path, webp_buf.tobytes(), {"content-type": "image/webp"})
            os.unlink(out_path)

        # Delete the raw upload now that grading is done — it is never reused and
        # is the biggest storage cost (3-5MB per phone photo).
        try:
            supabase.storage.from_("raw_images").remove([file_path])
        except Exception as e:
            print(f"Could not delete raw image {file_path}: {e}")


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
            "raw_marks": result["marks"],
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
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/process-scan")
@limiter.limit("10/second")
def trigger_process_scan(request: Request, req: ProcessScanRequest, background_tasks: BackgroundTasks, user_id: str = Depends(get_current_user)):
    """Trigger background grading after frontend uploads image to Supabase."""

    # Ensure user has credits
    if supabase:
        user_res = supabase.table("users").select("credits").eq("id", user_id).execute()
        if not user_res.data or user_res.data[0]['credits'] <= 0:
            raise HTTPException(402, "Insufficient credits")

    background_tasks.add_task(process_scan_background, req.scan_id, req.exam_code, user_id)
    return {"message": "Processing started", "scan_id": req.scan_id}


@app.get("/export/{exam_code}")
@limiter.limit("10/second")
def export_results(request: Request, exam_code: str, user_id: str = Depends(get_current_user)):
    """Generates a CSV and ZIP of graded images, uploads to exports bucket, returns signed URL."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")

    # Fetch this user's successful scans. If they have an exam row for this
    # exam_code, scope the export to that exam via exam_id.
    code = (exam_code or "").strip().upper()
    query = supabase.table("scans").select("*").eq("user_id", user_id).eq("status", "success")
    exam_res = supabase.table("exams").select("id").eq("user_id", user_id).eq("exam_code", code).execute()
    if exam_res.data:
        query = query.eq("exam_id", exam_res.data[0]["id"])
    res = query.execute()
    if not res.data:
        raise HTTPException(404, "No successful scans found to export.")

    scans = res.data

    # Generate CSV
    csv_io = io.StringIO()
    writer = csv.writer(csv_io)
    
    all_questions = set()
    for s in scans:
        if s.get("raw_marks"):
            all_questions.update(s["raw_marks"].keys())
            
    q_keys = sorted(list(all_questions), key=lambda x: int(x) if str(x).isdigit() else x)
    header = ["Scan ID", "Score", "Total", "Percentage"] + [f"Q{k}" for k in q_keys]
    writer.writerow(header)
    
    for s in scans:
        row = [s["scan_id"], s["score"], s["total"], s["percentage"]]
        marks = s.get("raw_marks", {})
        for k in q_keys:
            row.append(marks.get(str(k), ""))
        writer.writerow(row)

    csv_content = csv_io.getvalue()

    # Create ZIP
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_zip:
        zip_path = tmp_zip.name
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.writestr(f"{exam_code}_results.csv", csv_content)
        
        for s in scans:
            img_path = s.get("graded_image_path")
            if img_path:
                try:
                    img_bytes = supabase.storage.from_("graded_images").download(img_path)
                    zipf.writestr(f"images/{s['scan_id']}_graded.webp", img_bytes)
                except Exception as e:
                    print(f"Failed to zip image {img_path}: {e}")

    # Upload ZIP to exports bucket
    export_path = f"{user_id}/{exam_code}_{int(time.time())}.zip"
    try:
        with open(zip_path, "rb") as f:
            supabase.storage.from_("exports").upload(export_path, f, {"content-type": "application/zip"})
    except Exception as e:
        os.unlink(zip_path)
        raise HTTPException(500, f"Failed to upload export: {e}")

    os.unlink(zip_path)

    # Return signed URL (valid 1 hour)
    url_res = supabase.storage.from_("exports").create_signed_url(export_path, 3600)
    return {"export_url": url_res['signedURL']}


# ── Retention: 7-day image wipe ───────────────────────────────────

def wipe_expired_images(days: int = 7) -> dict:
    """Delete raw + graded images for scans older than `days`. Scores and the
    scan records are kept forever — only the image files (and their paths) go."""
    if not supabase:
        return {"error": "supabase not configured"}
    import datetime as _dt
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).isoformat()

    res = supabase.table("scans").select(
        "id, image_path, graded_image_path").lt("created_at", cutoff).execute()
    targets = [s for s in (res.data or [])
               if s.get("image_path") or s.get("graded_image_path")]

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
                    print(f"wipe: {bucket}/{p} failed: {e}")
        try:
            supabase.table("scans").update(
                {"image_path": None, "graded_image_path": None}).eq("id", s["id"]).execute()
        except Exception as e:
            print(f"wipe: db update failed for scan {s['id']}: {e}")

    return {"scans_affected": len(targets), "files_deleted": files_deleted, "cutoff": cutoff}


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
            supabase.rpc("add_credits_by_marka_id", {"m_id": marka_id.upper(), "amount": credits_to_add}).execute()

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
