"""
MARKA OMR Scanner — High-speed bubble reader and grader.
Target: <10ms per image for reading, ~400 images/second with 4 workers.

Robustness:
  - Relative threshold (adapts to lighting/paper color)
  - Confidence scores per answer
  - Blur detection
  - 4-fiducial perspective correction

Two core functions:
  read_bubbles()      → Extract what the student marked (the hot path)
  grade_and_render()  → Apply answer key, draw visual feedback (on demand)
"""

import cv2
import numpy as np
import json
import os
import time


# ── Constants ─────────────────────────────────────────────────────

PX_PER_MM = 10  # Resolution for the perspective-corrected image
MIN_FIDUCIAL_AREA = 300
MAX_FIDUCIAL_AREA = 60000

# Relative threshold: a bubble is "filled" if its darkness is below
# (blank_median - FILL_RATIO * (blank_median - darkest_possible))
# Lower ratio = more lenient (catches light pencil); higher = stricter
FILL_RATIO = 0.35

# Minimum confidence to count as a definite mark
CONFIDENCE_THRESHOLD = 0.5

# Blur detection
MIN_SHARPNESS = 15.0  # Reduced due to downscaling optimization


def _find_fiducials(gray):
    """Detect the 4 corner fiducial squares. Returns sorted corners."""
    h_img, w_img = gray.shape
    scale = 1200.0 / w_img
    if scale < 1.0:
        small_gray = cv2.resize(gray, (0,0), fx=scale, fy=scale)
    else:
        small_gray = gray
        scale = 1.0

    blurred = cv2.GaussianBlur(small_gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )
    contours, _ = cv2.findContours(
        thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )

    candidates = []
    min_area = MIN_FIDUCIAL_AREA * (scale ** 2)
    max_area = MAX_FIDUCIAL_AREA * (scale ** 2)

    for c in contours:
        # Cheap area gate first — skips arcLength/approxPolyDP on the hundreds
        # of small bubble/noise contours (they can never be fiducials).
        area = cv2.contourArea(c)
        if not (min_area < area < max_area):
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)
        if len(approx) == 4:
            x, y, w_box, h_box = cv2.boundingRect(approx)
            aspect = w_box / float(h_box)
            if 0.7 <= aspect <= 1.3:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    candidates.append((cx / scale, cy / scale))

    if len(candidates) < 4:
        raise ValueError(
            f"Found {len(candidates)} fiducial markers instead of 4. "
            "Ensure all 4 corner squares are clearly visible in the photo. "
            "Take the photo in good lighting with the full sheet visible."
        )

    # Extract the 4 extreme corners from all candidates
    pts = np.array(candidates, dtype="float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()

    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]

    return np.array([tl, tr, br, bl], dtype="float32")


def _perspective_transform(image, src_pts, layout):
    """Warp the image to a flat grid using fiducial positions."""
    sheet_w_mm = layout["sheet_size_mm"][0]
    sheet_h_mm = layout["sheet_size_mm"][1]
    fids = layout["fiducial_centers_mm"]

    width = int(sheet_w_mm * PX_PER_MM)
    height = int(sheet_h_mm * PX_PER_MM)

    # Destination points from the layout JSON (mm → px)
    dst_pts = np.array([
        [fids["top_left"][0] * PX_PER_MM, (sheet_h_mm - fids["top_left"][1]) * PX_PER_MM],
        [fids["top_right"][0] * PX_PER_MM, (sheet_h_mm - fids["top_right"][1]) * PX_PER_MM],
        [fids["bottom_right"][0] * PX_PER_MM, (sheet_h_mm - fids["bottom_right"][1]) * PX_PER_MM],
        [fids["bottom_left"][0] * PX_PER_MM, (sheet_h_mm - fids["bottom_left"][1]) * PX_PER_MM],
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    aligned = cv2.warpPerspective(image, M, (width, height))
    return aligned, width, height


def _check_image_quality(gray):
    """Check if the image is too blurry. Returns sharpness score."""
    h, w = gray.shape
    scale = 800.0 / w
    if scale < 1.0:
        small = cv2.resize(gray, (0,0), fx=scale, fy=scale)
    else:
        small = gray
    laplacian_var = cv2.Laplacian(small, cv2.CV_64F).var()
    return float(laplacian_var)


def _compute_adaptive_threshold(gray, bubbles, sheet_h_mm):
    """
    Sample ALL bubble regions and compute a threshold relative to the
    actual paper brightness. This handles:
    - Yellow lighting
    - Shadows
    - Colored paper
    - Printer ink variations
    
    Returns (threshold, blank_median) where any bubble with mean < threshold
    is considered filled.
    """
    all_means = []
    for b in bubbles:
        cx = int(b["x_mm"] * PX_PER_MM)
        cy = int((sheet_h_mm - b["y_mm"]) * PX_PER_MM)
        r = max(int(b["radius_mm"] * PX_PER_MM * 0.65), 2)

        y1, y2 = max(0, cy - r), min(gray.shape[0], cy + r)
        x1, x2 = max(0, cx - r), min(gray.shape[1], cx + r)

        if y2 > y1 and x2 > x1:
            roi = gray[y1:y2, x1:x2]
            all_means.append(float(roi.mean()))

    if not all_means:
        return 180, 230  # fallback

    all_means.sort()

    # The majority of bubbles are BLANK (unfilled).
    # Blank bubbles cluster near the top (bright).
    # Filled bubbles cluster near the bottom (dark).
    # The blank median is the 75th percentile (since at most ~20% are filled).
    blank_median = np.percentile(all_means, 75)

    # The threshold is set relative to the blank median.
    # threshold = blank_median - FILL_RATIO * blank_median
    # A bubble darker than this is considered filled.
    threshold = blank_median * (1 - FILL_RATIO)

    return threshold, blank_median


def _read_all_bubbles(gray, bubbles, sheet_h_mm, threshold):
    """
    Read all bubbles using fast numpy ROI slicing.
    Returns dict: {question_num: [(option, mean_darkness, confidence), ...]}
    """
    results = {}
    for b in bubbles:
        q = b["question"]
        opt = b["option"]
        cx = int(b["x_mm"] * PX_PER_MM)
        cy = int((sheet_h_mm - b["y_mm"]) * PX_PER_MM)  # flip Y
        r = max(int(b["radius_mm"] * PX_PER_MM * 0.65), 2)  # sample 65% to avoid border

        # Bounds check
        y1, y2 = max(0, cy - r), min(gray.shape[0], cy + r)
        x1, x2 = max(0, cx - r), min(gray.shape[1], cx + r)

        if y2 > y1 and x2 > x1:
            roi = gray[y1:y2, x1:x2]
            mean_val = float(roi.mean())
        else:
            mean_val = 255  # white = unmarked

        if q not in results:
            results[q] = []
        results[q].append((opt, mean_val))

    return results


def read_bubbles(image_path, layout_data_or_path):
    """
    THE HOT PATH. Extract what the student marked.
    No scoring. No drawing. Pure speed.

    Returns:
        {
            "sheet_id": layout's sheet_id,
            "marks": {"1": "B", "2": "D", "3": null, ...},
            "multi_marks": {"15": ["A", "C"]},
            "confidence": {"1": 0.92, "2": 0.87, ...},
            "ambiguous": ["12", "45"],
            "image_quality": {"sharpness": 120.5, "ok": true},
            "threshold_used": 155,
            "time_ms": 8.3
        }
    """
    t0 = time.perf_counter()

    # Load layout
    if isinstance(layout_data_or_path, str):
        with open(layout_data_or_path, "r") as f:
            layout_data = json.load(f)
    else:
        layout_data = layout_data_or_path

    # Use the first sheet's layout (all sheets have identical bubble positions)
    sheet = layout_data["sheets"][0]
    sheet_h_mm = sheet["sheet_size_mm"][1]

    # Load as grayscale — the hot path never needs colour, and a single-channel
    # warp is ~3x cheaper than warping BGR (also skips two cvtColor passes).
    gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError(f"Could not load image: {image_path}")

    # Image quality check
    sharpness = _check_image_quality(gray)
    quality_ok = sharpness >= MIN_SHARPNESS

    # Find fiducials and align (all grayscale)
    src_pts = _find_fiducials(gray)
    aligned_gray, w, h = _perspective_transform(gray, src_pts, sheet)

    # Orientation Check: If rotated 180 degrees, the bottom (blank) will be darker than the top (MARKA header)
    top_roi = aligned_gray[: int(h * 0.1), :]
    bot_roi = aligned_gray[int(h * 0.9):, :]
    if bot_roi.mean() < top_roi.mean() - 10:
        raise ValueError("Image appears to be upside down. Please rotate 180 degrees.")

    # Compute adaptive threshold from the actual paper
    threshold, blank_median = _compute_adaptive_threshold(
        aligned_gray, sheet["bubbles"], sheet_h_mm
    )

    # Read all bubbles
    raw = _read_all_bubbles(aligned_gray, sheet["bubbles"], sheet_h_mm, threshold)

    # Determine marked options per question with confidence
    marks = {}
    multi_marks = {}
    confidence = {}
    ambiguous = []
    num_questions = layout_data["num_questions"]

    for q_num in range(1, num_questions + 1):
        q_bubbles = raw.get(q_num, [])
        if not q_bubbles:
            marks[str(q_num)] = None
            confidence[str(q_num)] = 0
            continue

        # Calculate confidence for each option:
        # confidence = how far below the threshold the bubble is, relative to blank
        option_scores = []
        for opt, mean_val in q_bubbles:
            if blank_median > 0:
                # 1.0 = completely black, 0.0 = same as blank paper
                fill_pct = max(0, (blank_median - mean_val) / blank_median)
            else:
                fill_pct = 0
            is_filled = mean_val < threshold
            option_scores.append((opt, mean_val, fill_pct, is_filled))

        filled = [(opt, score) for opt, _, score, is_filled in option_scores if is_filled]

        if len(filled) == 1:
            marks[str(q_num)] = filled[0][0]
            confidence[str(q_num)] = round(filled[0][1], 2)
        elif len(filled) > 1:
            marks[str(q_num)] = None  # ambiguous - multiple filled
            multi_marks[str(q_num)] = [opt for opt, _ in filled]
            confidence[str(q_num)] = 0
            ambiguous.append(str(q_num))
        else:
            # Nothing clearly filled. Check for light marks.
            best = max(option_scores, key=lambda x: x[2])
            if best[2] > 0.35:  # Very light mark detected
                marks[str(q_num)] = best[0]
                confidence[str(q_num)] = round(best[2], 2)
                if best[2] < CONFIDENCE_THRESHOLD:
                    ambiguous.append(str(q_num))
            else:
                marks[str(q_num)] = None  # genuinely blank
                confidence[str(q_num)] = 0

    elapsed = (time.perf_counter() - t0) * 1000

    return {
        "sheet_id": sheet.get("sheet_id", "unknown"),
        "marks": marks,
        "multi_marks": multi_marks,
        "confidence": confidence,
        "ambiguous": ambiguous,
        "image_quality": {
            "sharpness": round(sharpness, 1),
            "ok": quality_ok
        },
        "threshold_used": round(threshold, 1),
        "blank_median": round(blank_median, 1),
        "time_ms": round(elapsed, 2)
    }


def grade_and_render(marks_data, answers, image_path, layout_data_or_path, output_path):
    """
    Apply answer key to extracted marks. Draw visual feedback.
    Only called when answer key exists AND visual is requested.
    """
    if isinstance(layout_data_or_path, str):
        with open(layout_data_or_path, "r") as f:
            layout_data = json.load(f)
    else:
        layout_data = layout_data_or_path

    sheet = layout_data["sheets"][0]
    sheet_h_mm = sheet["sheet_size_mm"][1]

    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    src_pts = _find_fiducials(gray)
    aligned, w, h = _perspective_transform(image, src_pts, sheet)

    marks = marks_data["marks"]
    conf = marks_data.get("confidence", {})
    score = 0
    total = len(answers)

    # Group bubbles by question for drawing
    bubble_map = {}
    for b in sheet["bubbles"]:
        q = b["question"]
        if q not in bubble_map:
            bubble_map[q] = []
        bubble_map[q].append(b)

    for q_str, correct in answers.items():
        q_num = int(q_str)
        student_answer = marks.get(q_str)

        # An answer-key entry may be:
        #   "A"          → single correct option
        #   ["A", "C"]   → any of these options is accepted
        #   "*"          → bonus: any answer (or none) is correct
        if correct == "*" or correct == ["*"]:
            is_bonus = True
            accepted = set()
        elif isinstance(correct, list):
            is_bonus = False
            accepted = {str(c).strip().upper() for c in correct}
        else:
            is_bonus = False
            accepted = {str(correct).strip().upper()}

        is_correct = is_bonus or (student_answer in accepted)
        if is_correct:
            score += 1

        # Draw visual feedback on aligned image
        for b in bubble_map.get(q_num, []):
            cx = int(b["x_mm"] * PX_PER_MM)
            cy = int((sheet_h_mm - b["y_mm"]) * PX_PER_MM)
            r = int(b["radius_mm"] * PX_PER_MM)
            opt = b["option"]

            if opt == student_answer:
                color = (0, 200, 0) if is_correct else (0, 0, 220)
                cv2.circle(aligned, (cx, cy), r + 2, color, 3)  # ring
                cv2.circle(aligned, (cx, cy), r, color, -1)     # fill
            elif opt in accepted and not is_correct:
                cv2.circle(aligned, (cx, cy), r + 2, (0, 200, 0), 3)   # missed correct option

            # Mark ambiguous answers with orange
            if q_str in marks_data.get("ambiguous", []):
                if opt in marks_data.get("multi_marks", {}).get(q_str, []):
                    cv2.circle(aligned, (cx, cy), r + 2, (0, 165, 255), 3)  # orange

    # Score overlay
    pct = (score / total * 100) if total > 0 else 0
    label = f"SCORE: {score}/{total} ({pct:.0f}%)"
    # Scale text to image width
    font_scale = max(1.0, w / 800)
    thickness = max(2, int(font_scale * 3))
    cv2.putText(aligned, label, (int(w * 0.1), int(h * 0.05)),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 140, 0), thickness)

    cv2.imwrite(output_path, aligned)

    return {
        "score": score,
        "total": total,
        "percentage": round(pct, 1),
        "output_path": output_path
    }


# ── CLI for testing ───────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MARKA OMR Scanner")
    parser.add_argument("image", help="Path to the photo of the filled OMR sheet")
    parser.add_argument("layout", help="Path to omr_layout.json")
    parser.add_argument("--answers", default=None, help="Path to answer_key.json (optional)")
    parser.add_argument("--output", default="graded_output.jpg", help="Output path for graded image")
    args = parser.parse_args()

    # Step 1: Read bubbles (always)
    result = read_bubbles(args.image, args.layout)
    print(f"\n{'='*60}")
    print(f"  Bubbles read in {result['time_ms']}ms")
    print(f"  Image quality: sharpness={result['image_quality']['sharpness']}"
          f" ({'OK' if result['image_quality']['ok'] else 'BLURRY - retake!'})")
    print(f"  Threshold: {result['threshold_used']} (blank median: {result['blank_median']})")
    if result['ambiguous']:
        print(f"  ⚠ Ambiguous answers: Q{', Q'.join(result['ambiguous'])}")
    print(f"{'='*60}")

    for q, ans in sorted(result["marks"].items(), key=lambda x: int(x[0])):
        conf_val = result["confidence"].get(q, 0)
        flag = ""
        if q in result["multi_marks"]:
            flag = f"  ⚠ MULTI: {result['multi_marks'][q]}"
        elif conf_val > 0 and conf_val < CONFIDENCE_THRESHOLD:
            flag = f"  ⚠ LOW CONFIDENCE ({conf_val:.0%})"
        print(f"  Q{q:>3}: {ans or '—'}  (conf: {conf_val:.0%}){flag}")

    # Step 2: Grade (only if answer key provided)
    if args.answers:
        with open(args.answers) as f:
            answers = json.load(f)
        grade_result = grade_and_render(
            result, answers, args.image, args.layout, args.output
        )
        print(f"\n{'='*60}")
        print(f"  SCORE: {grade_result['score']}/{grade_result['total']} ({grade_result['percentage']}%)")
        print(f"  Graded image saved to: {grade_result['output_path']}")
        print(f"{'='*60}")
    else:
        print(f"\nNo answer key provided. Raw marks saved.")
        raw_path = args.image.rsplit(".", 1)[0] + "_marks.json"
        with open(raw_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Raw marks saved to: {raw_path}")
