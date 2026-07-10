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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List
import tempfile
import shutil
import json
import glob
import time

from omr_scanner import read_bubbles, grade_and_render

app = FastAPI(title="MARKA Grading API")

# Static frontend
STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'demo_site', 'dist')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    return {"status": "ok"}


@app.post("/scan")
def scan_image(image: UploadFile = File(...), exam_code: str = Form(...)):
    """Upload a single image → extract marks → store → return raw marks."""
    code = exam_code.strip().upper()

    layout_path = find_layout_json(code)
    if not layout_path:
        raise HTTPException(404, f"Exam code '{code}' not found.")

    exam_dir = get_exam_dir(code)

    # Save uploaded image
    scan_id = f"{int(time.time() * 1000)}"
    img_path = os.path.join(exam_dir, 'images', f'{scan_id}.jpg')
    with open(img_path, 'wb') as f:
        shutil.copyfileobj(image.file, f)

    # Read bubbles (THE HOT PATH)
    try:
        result = read_bubbles(img_path, layout_path)
    except ValueError as e:
        os.unlink(img_path)
        raise HTTPException(400, str(e))

    result["scan_id"] = scan_id

    # Save raw marks
    marks_path = os.path.join(exam_dir, 'scans', f'{scan_id}.json')
    with open(marks_path, 'w') as f:
        json.dump(result, f, indent=2)

    # Auto-grade if answer key exists
    answers = get_answer_key(code)
    if answers:
        grade_result = grade_and_render(
            result, answers, img_path, layout_path,
            os.path.join(exam_dir, 'results', f'{scan_id}_graded.jpg')
        )
        result["score"] = grade_result["score"]
        result["total"] = grade_result["total"]
        result["percentage"] = grade_result["percentage"]
        result["graded"] = True
    else:
        result["graded"] = False

    return result


@app.post("/batch-scan")
def batch_scan(images: List[UploadFile] = File(...), exam_code: str = Form(...)):
    """Upload multiple images at once. Returns all results."""
    code = exam_code.strip().upper()

    layout_path = find_layout_json(code)
    if not layout_path:
        raise HTTPException(404, f"Exam code '{code}' not found.")

    exam_dir = get_exam_dir(code)
    answers = get_answer_key(code)
    results = []
    total_time = 0

    for img_file in images:
        scan_id = f"{int(time.time() * 1000)}"
        img_path = os.path.join(exam_dir, 'images', f'{scan_id}.jpg')
        with open(img_path, 'wb') as f:
            shutil.copyfileobj(img_file.file, f)

        try:
            result = read_bubbles(img_path, layout_path)
            result["scan_id"] = scan_id
            result["filename"] = img_file.filename
            total_time += result["time_ms"]

            # Save raw marks
            marks_path = os.path.join(exam_dir, 'scans', f'{scan_id}.json')
            with open(marks_path, 'w') as f:
                json.dump(result, f, indent=2)

            # Auto-grade if answer key exists
            if answers:
                grade_result = grade_and_render(
                    result, answers, img_path, layout_path,
                    os.path.join(exam_dir, 'results', f'{scan_id}_graded.jpg')
                )
                result["score"] = grade_result["score"]
                result["total"] = grade_result["total"]
                result["percentage"] = grade_result["percentage"]
                result["graded"] = True
            else:
                result["graded"] = False

            results.append(result)
        except ValueError as e:
            results.append({
                "scan_id": scan_id,
                "filename": img_file.filename,
                "error": str(e)
            })

        # Small delay to ensure unique scan_ids
        time.sleep(0.001)

    return {
        "exam_code": code,
        "total_images": len(images),
        "successful": len([r for r in results if "error" not in r]),
        "failed": len([r for r in results if "error" in r]),
        "total_time_ms": round(total_time, 2),
        "results": results
    }


@app.post("/answer-key")
def submit_answer_key(exam_code: str = Form(...), answers: str = Form(...)):
    """Submit or update the answer key for an exam code.
    Retroactively grades all existing scans."""
    code = exam_code.strip().upper()

    layout_path = find_layout_json(code)
    if not layout_path:
        raise HTTPException(404, f"Exam code '{code}' not found.")

    # Parse the answers
    try:
        answer_dict = json.loads(answers)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid answer key format. Must be JSON.")

    exam_dir = get_exam_dir(code)

    # Save answer key
    key_path = os.path.join(exam_dir, 'answer_key.json')
    with open(key_path, 'w') as f:
        json.dump(answer_dict, f, indent=2)

    # Retroactively grade all existing scans
    scan_files = glob.glob(os.path.join(exam_dir, 'scans', '*.json'))
    graded_count = 0
    results_summary = []

    for scan_file in scan_files:
        with open(scan_file) as f:
            scan_data = json.load(f)

        scan_id = scan_data.get("scan_id", os.path.basename(scan_file).replace('.json', ''))
        img_path = os.path.join(exam_dir, 'images', f'{scan_id}.jpg')

        if os.path.exists(img_path):
            try:
                grade_result = grade_and_render(
                    scan_data, answer_dict, img_path, layout_path,
                    os.path.join(exam_dir, 'results', f'{scan_id}_graded.jpg')
                )
                results_summary.append({
                    "scan_id": scan_id,
                    "score": grade_result["score"],
                    "total": grade_result["total"],
                    "percentage": grade_result["percentage"]
                })
                graded_count += 1
            except Exception as e:
                results_summary.append({
                    "scan_id": scan_id,
                    "error": str(e)
                })

    return {
        "exam_code": code,
        "answer_key_saved": True,
        "scans_retrograded": graded_count,
        "results": results_summary
    }


@app.get("/results/{exam_code}")
def get_results(exam_code: str):
    """Get the score table for an exam code."""
    code = exam_code.strip().upper()
    exam_dir = os.path.join(DATA_DIR, code)

    if not os.path.isdir(exam_dir):
        raise HTTPException(404, f"No data for exam code '{code}'.")

    # Check for answer key
    answers = get_answer_key(code)
    has_key = answers is not None

    # Load all scans
    scan_files = sorted(glob.glob(os.path.join(exam_dir, 'scans', '*.json')))
    scans = []
    for sf in scan_files:
        with open(sf) as f:
            data = json.load(f)
        scan_id = data.get("scan_id", os.path.basename(sf).replace('.json', ''))
        entry = {
            "scan_id": scan_id,
            "marks": data.get("marks", {}),
        }
        # Add score if graded
        if has_key:
            student_marks = data.get("marks", {})
            score = sum(1 for q, a in answers.items() if student_marks.get(q) == a)
            entry["score"] = score
            entry["total"] = len(answers)
            entry["percentage"] = round(score / len(answers) * 100, 1) if answers else 0
            entry["has_graded_image"] = os.path.exists(
                os.path.join(exam_dir, 'results', f'{scan_id}_graded.jpg')
            )
        scans.append(entry)

    return {
        "exam_code": code,
        "has_answer_key": has_key,
        "total_scans": len(scans),
        "scans": scans
    }


@app.get("/result/{exam_code}/{scan_id}")
def get_graded_image(exam_code: str, scan_id: str):
    """Get an individual graded image."""
    code = exam_code.strip().upper()
    img_path = os.path.join(DATA_DIR, code, 'results', f'{scan_id}_graded.jpg')

    if not os.path.exists(img_path):
        raise HTTPException(404, "Graded image not found. Submit an answer key first.")

    return FileResponse(img_path, media_type="image/jpeg")


# ── Legacy /grade endpoint for the demo frontend ─────────────────

@app.post("/grade")
def grade_exam_legacy(image: UploadFile = File(...), exam_code: str = Form(...)):
    """Legacy endpoint: upload + instant grade (for demo with embedded answer key)."""
    code = exam_code.strip().upper()

    layout_path = find_layout_json(code)
    if not layout_path:
        raise HTTPException(404, f"Exam code '{code}' not found.")

    # Save temp image
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        shutil.copyfileobj(image.file, tmp)
        tmp_path = tmp.name

    output_path = tmp_path.replace(".jpg", "_graded.jpg")

    try:
        # Read
        result = read_bubbles(tmp_path, layout_path)

        # Check for answer key
        answers = get_answer_key(code)
        if not answers:
            # No answer key — return raw marks
            return JSONResponse(content={
                "marks": result["marks"],
                "time_ms": result["time_ms"],
                "graded": False,
                "message": "No answer key found. Marks extracted but not graded."
            })

        # Grade
        grade_result = grade_and_render(
            result, answers, tmp_path, layout_path, output_path
        )
        return FileResponse(
            output_path,
            media_type="image/jpeg",
            filename="graded_result.jpg",
            headers={"X-Score": f"{grade_result['score']}/{grade_result['total']}"}
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Mount frontend (must be last!) ────────────────────────────────

if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
