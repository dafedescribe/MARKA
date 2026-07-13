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

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import tempfile
import json
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



app = FastAPI(title="MARKA Grading API")

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
    token: str # In production, use Depends(oauth2_scheme)


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
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"}
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
    credits_to_add = int(amount / 100) # Example: 1 credit per 100 Naira

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
def login(req: LoginRequest):
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

# ── Upload Endpoints ──────────────────────────────────────────────

@app.get("/upload/presigned-url")
def get_presigned_url(scan_id: str, token: str):
    """
    Generate a presigned URL for direct-to-Supabase upload.
    In a real app, 'token' should be verified as a valid JWT first.
    """
    if not supabase:
        raise HTTPException(500, "Supabase not configured")
        
    # Example: we extract the user_id from the verified JWT
    # For now, we mock it or pass it. If we used FastAPI Depends, we'd verify it.
    from jose import jwt, JWTError
    from auth import JWT_SECRET, ALGORITHM
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid token")

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
        # 1. Update status to processing and fetch user info
        user_res = supabase.table("users").select("credits, marka_id").eq("id", user_id).execute()
        user_data = user_res.data[0] if user_res.data else {"credits": 0, "marka_id": ""}
        
        supabase.table("scans").insert({
            "scan_id": scan_id,
            "user_id": user_id,
            "exam_id": None,  # linked once the exams table exists (Phase 1)
            "status": "processing"
        }).execute()


        # 2. Download image from raw_images bucket
        file_path = f"{user_id}/{scan_id}.jpg"
        img_bytes = supabase.storage.from_("raw_images").download(file_path)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name

        # 3. Process image
        layout_path = find_layout_json(exam_code)
        if not layout_path:
            raise ValueError(f"Exam code '{exam_code}' not found.")

        result = read_bubbles(tmp_path, layout_path)
        result["scan_id"] = scan_id

        answers = get_answer_key(exam_code)
        graded_file_path = None
        score = None
        total = None
        percentage = None

        if answers:
            out_path = tmp_path.replace(".jpg", "_graded.jpg")
            grade_result = grade_and_render(result, answers, tmp_path, layout_path, out_path)
            score = grade_result["score"]
            total = grade_result["total"]
            percentage = grade_result["percentage"]
            
            # Apply Heavy Watermark if DEMO-TEST
            if user_data.get("marka_id") == "DEMO-TEST":
                img = cv2.imread(out_path)
                h, w = img.shape[:2]
                cv2.putText(img, "MARKA DEMO", (int(w*0.1), int(h*0.4)), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 8, cv2.LINE_AA)
                cv2.putText(img, "NOT FOR PRODUCTION", (int(w*0.05), int(h*0.6)), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 6, cv2.LINE_AA)
                cv2.imwrite(out_path, img)

            # Upload graded image to Supabase
            with open(out_path, "rb") as f:
                supabase.storage.from_("graded_images").upload(file_path, f, {"content-type": "image/jpeg"})
            graded_file_path = file_path
            os.unlink(out_path)


        # 4. Deduct credit
        credits = user_data["credits"]
        # Only deduct if not DEMO-TEST (DEMO-TEST has unlimited but restricted scans)
        if user_data.get("marka_id") != "DEMO-TEST":
            supabase.table("users").update({"credits": credits - 1}).eq("id", user_id).execute()


        # 5. Update scan record
        supabase.table("scans").update({
            "status": "success",
            "score": score,
            "total": total,
            "percentage": percentage,
            "raw_marks": result["marks"],
            "image_path": file_path,
            "graded_image_path": graded_file_path
        }).eq("scan_id", scan_id).execute()

    except Exception as e:
        print(f"Error processing scan {scan_id}: {e}")
        try:
            supabase.table("scans").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("scan_id", scan_id).execute()
        except:
            pass
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/process-scan")
def trigger_process_scan(req: ProcessScanRequest, background_tasks: BackgroundTasks):
    """Trigger background grading after frontend uploads image to Supabase."""
    from jose import jwt, JWTError
    from auth import JWT_SECRET, ALGORITHM
    try:
        payload = jwt.decode(req.token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    # Ensure user has credits
    if supabase:
        user_res = supabase.table("users").select("credits").eq("id", user_id).execute()
        if not user_res.data or user_res.data[0]['credits'] <= 0:
            raise HTTPException(402, "Insufficient credits")

    background_tasks.add_task(process_scan_background, req.scan_id, req.exam_code, user_id)
    return {"message": "Processing started", "scan_id": req.scan_id}


@app.get("/export/{exam_code}")
def export_results(exam_code: str, token: str):
    """Generates a CSV and ZIP of graded images, uploads to exports bucket, returns signed URL."""
    if not supabase:
        raise HTTPException(500, "Supabase not configured")
        
    from jose import jwt, JWTError
    from auth import JWT_SECRET, ALGORITHM
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    # Fetch successful scans
    res = supabase.table("scans").select("*").eq("user_id", user_id).eq("status", "success").execute()
    # Note: Currently not filtering by exam_code in DB since exam_id wasn't properly linked in MVP process_scan
    # In production, we'd ensure exam_code or exam_id is correctly associated and filtered.
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
                    zipf.writestr(f"images/{s['scan_id']}_graded.jpg", img_bytes)
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
        
        # Give 1 credit per 100 Naira (example)
        credits_to_add = int(amount / 100)
        
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
            user_res = supabase.table("users").select("credits").eq("marka_id", marka_id.upper()).execute()
            if user_res.data:
                current_credits = user_res.data[0]['credits']
                supabase.table("users").update({"credits": current_credits + credits_to_add}).eq("marka_id", marka_id.upper()).execute()

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
