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

# Per-question LOCAL threshold (gradient-proof). Each bubble is judged against
# the blank reference of its OWN row, not a global constant — so uneven lighting
# (a shadow across the bottom of the sheet) no longer makes blank paper in the
# dark region read darker than a real mark in the bright region.
#   LOCAL_FILL_RATIO  — bubble is filled if it's this fraction darker than the
#                       row's blank reference (catches faint pencil on dark photos)
#   LOCAL_MIN_MARGIN  — ...and at least this many gray levels darker in absolute
#                       terms, so an all-blank row (all bubbles similar) stays blank
LOCAL_FILL_RATIO = 0.28
LOCAL_MIN_MARGIN = 22

# CLAHE (Contrast-Limited Adaptive Histogram Equalization) normalizes local
# contrast before reading — pulls filled bubbles away from blank paper under
# shadows/yellow light without blowing out clean, well-lit scans.
CLAHE_CLIP = 2.0
CLAHE_GRID = (8, 8)

# Minimum confidence to count as a definite mark
CONFIDENCE_THRESHOLD = 0.5

# Blur detection
MIN_SHARPNESS = 15.0  # Reduced due to downscaling optimization

# Orientation: how much busier the bottom-left QR window must be than the
# top-right one before we treat the sheet as upside-down and rotate it 180°.
# Genuine flips show a strong asymmetry (~2.5x on real photos); requiring a
# clear margin means content noise on a correctly-oriented sheet never triggers
# an erroneous flip.
FLIP_MARGIN = 1.3


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

    # Extract the 4 extreme corners (TL, TR, BR, BL) from a set of points.
    def _extreme_corners(points):
        pts = np.array(points, dtype="float32")
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1).flatten()
        return [pts[np.argmin(s)], pts[np.argmin(diff)],
                pts[np.argmax(s)], pts[np.argmax(diff)]]  # tl, tr, br, bl

    def _distinct(corners, tol=25.0):
        uniq = []
        for c in corners:
            if not any(np.linalg.norm(c - u) < tol for u in uniq):
                uniq.append(c)
        return uniq

    if len(candidates) >= 4:
        corners = _extreme_corners(candidates)
        uniq = _distinct(corners)
    else:
        uniq = _distinct([np.array(c, dtype="float32") for c in candidates])

    if len(uniq) == 3:
        # Only three fiducials detected — commonly the top-right one, which sits
        # next to the QR block and can fuse with it at certain angles. The four
        # fiducials form a rectangle, so the missing corner is fully determined:
        # the two farthest-apart points are a diagonal, and the missing corner is
        # the reflection of the third point through that diagonal's midpoint.
        import itertools
        (i, j) = max(itertools.combinations(range(3), 2),
                     key=lambda pr: np.linalg.norm(uniq[pr[0]] - uniq[pr[1]]))
        k = ({0, 1, 2} - {i, j}).pop()
        center = (uniq[i] + uniq[j]) / 2.0
        missing = 2.0 * center - uniq[k]
        four = uniq + [missing]
        # Sanity: the reconstructed quad must be a plausible sheet — corners well
        # separated and spanning a large area — else fall through to the error.
        corners = _extreme_corners(four)
        min_side = min(np.linalg.norm(corners[a] - corners[b])
                       for a, b in [(0, 1), (1, 2), (2, 3), (3, 0)])
        if min_side < 50:
            uniq = []  # degenerate — trigger the error below
        else:
            return np.array(corners, dtype="float32")

    if len(uniq) < 4:
        raise ValueError(
            f"Found {len(candidates)} fiducial markers instead of 4. "
            "Ensure all 4 corner squares are clearly visible in the photo. "
            "Take the photo in good lighting with the full sheet visible."
        )

    return np.array(_extreme_corners(candidates), dtype="float32")


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


def _qr_bottom_left_score(aligned_gray):
    """
    Decide whether the sheet is flipped 180° by locating the QR block.

    The QR is always printed in the sheet's physical TOP-RIGHT corner. After a
    correct warp it sits top-right; after a 180° flip it lands bottom-left. We
    probe two tight windows — the expected QR spot (top-right header) and its
    180° opposite (bottom-left) — and compare edge density (Canny). The QR is a
    dense, high-frequency block, so whichever window is busier holds the QR.

    Targeting a tight window at the QR's known location is far more reliable than
    comparing whole corners, whose texture is polluted by student marks/writing.

    Returns (is_flipped, confidence_margin). confidence_margin is the ratio of
    the busier window to the quieter one (1.0 = indistinguishable).
    """
    h, w = aligned_gray.shape[:2]

    def edge_density(patch):
        if patch.size == 0:
            return 0.0
        return float(cv2.Canny(patch, 50, 150).mean())

    tr = aligned_gray[int(0.02 * h):int(0.16 * h), int(0.80 * w):int(0.97 * w)]
    bl = aligned_gray[int(0.84 * h):int(0.98 * h), int(0.03 * w):int(0.20 * w)]

    tr_e = edge_density(tr)
    bl_e = edge_density(bl)

    hi, lo = max(tr_e, bl_e), min(tr_e, bl_e)
    margin = (hi / lo) if lo > 1e-3 else (hi if hi > 0 else 1.0)
    return bl_e > tr_e, margin


def _align_sheet(image, sheet):
    """
    Find the sheet, correct its perspective AND its orientation, and return the
    upright aligned image. Handles all four rotations (0/90/180/270) so a photo
    taken sideways or upside-down still grades correctly.

    Two phases:
      1. Sideways (90°/270°): the sheet is non-square, so if the fiducial bounding
         box comes out portrait when the layout is landscape (or vice-versa), the
         photo is rotated a quarter turn — rotate the source 90° and re-detect so
         the warp maps a same-shaped quad (no aspect distortion).
      2. Upside-down (180°): after warping, if the QR block is in the bottom-left
         instead of the top-right, rotate the aligned image 180°.

    Works on grayscale or colour images (the same transforms are applied to
    whichever is passed, so marks and rendered overlays stay consistent).

    Returns (aligned_image, info) where info = {
        "corrected_degrees": 0|90|180|270,   # how much the source was rotated
        "flip_confidence": float,            # >1; closer to 1 = less certain
    }.
    """
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    src_pts = _find_fiducials(gray)

    # ── Phase 1: quarter-turn (aspect) correction ──
    sheet_w_mm, sheet_h_mm = sheet["sheet_size_mm"][0], sheet["sheet_size_mm"][1]
    expected_landscape = sheet_w_mm >= sheet_h_mm
    xs, ys = src_pts[:, 0], src_pts[:, 1]
    measured_landscape = (xs.max() - xs.min()) >= (ys.max() - ys.min())

    quarter_turn = False
    if expected_landscape != measured_landscape:
        # Rotate the source a quarter turn so its long axis matches the layout,
        # then re-detect the fiducials on the now-upright-shaped sheet.
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        gray = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
        src_pts = _find_fiducials(gray)
        quarter_turn = True

    aligned, w, h = _perspective_transform(image, src_pts, sheet)

    # ── Phase 2: 180° (upside-down) correction ──
    # Only act on a clear signal: a genuinely upside-down sheet shows a strong
    # QR-density asymmetry, whereas a weak margin means the QR wasn't cleanly
    # located, so we trust the as-warped orientation rather than risk flipping a
    # correct sheet into a silently-wrong score.
    aligned_gray = aligned if aligned.ndim == 2 else cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    bl_busier, margin = _qr_bottom_left_score(aligned_gray)
    flipped = bl_busier and margin >= FLIP_MARGIN
    if flipped:
        aligned = cv2.rotate(aligned, cv2.ROTATE_180)

    corrected = (90 if quarter_turn else 0) + (180 if flipped else 0)
    return aligned, {"corrected_degrees": corrected % 360, "flip_confidence": round(margin, 2)}


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

    # Find fiducials, correct perspective AND auto-correct orientation. A photo
    # taken sideways or upside-down is rotated back to upright here, so it grades
    # correctly instead of silently producing a wrong score (or erroring out).
    aligned_gray, orientation = _align_sheet(gray, sheet)
    h, w = aligned_gray.shape[:2]

    # Normalize local contrast. On evenly-lit scans this is nearly a no-op; on
    # shadowed / yellow-lit phone photos it lifts faint marks out of the paper
    # so the per-question threshold below can separate them reliably.
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=CLAHE_GRID)
    aligned_gray = clahe.apply(aligned_gray)

    # Compute adaptive threshold from the actual paper (kept for reporting and as
    # a coarse global reference; the real decision below is per-question local).
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

        # Local blank reference for THIS question: the 2nd-brightest bubble in
        # the row. Using the row's own paper as the baseline makes the decision
        # immune to lighting gradients across the sheet. The 2nd-brightest (not
        # the brightest) tolerates a single specular glare spike, and is still a
        # genuine blank as long as at most 3 of the 5 options are marked.
        row_means = sorted((mv for _, mv in q_bubbles), reverse=True)
        local_blank = row_means[1] if len(row_means) >= 2 else row_means[0]

        option_scores = []
        for opt, mean_val in q_bubbles:
            margin = local_blank - mean_val
            # 1.0 = far darker than the row's blank paper, 0.0 = same as blank
            fill_pct = max(0.0, margin / local_blank) if local_blank > 0 else 0.0
            # Filled = clearly darker than this row's paper, both in relative and
            # absolute terms (the absolute floor keeps all-blank rows blank).
            is_filled = fill_pct >= LOCAL_FILL_RATIO and margin >= LOCAL_MIN_MARGIN
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
        "orientation": orientation,
        "threshold_used": round(threshold, 1),
        "blank_median": round(blank_median, 1),
        "time_ms": round(elapsed, 2)
    }


# ── Field Extraction (No OCR) ────────────────────────────────────

def _crop_field(aligned_img, field_box, sheet_h_mm):
    """
    Crop a handwriting field from the aligned image using mm coordinates.
    
    The layout JSON stores field boxes as {x, y, w, h} in mm, where y is
    measured from the BOTTOM of the sheet (ReportLab convention). The aligned
    image has y=0 at the TOP (OpenCV convention), so we flip.
    
    Returns: numpy array (BGR or grayscale crop), or None if coordinates invalid.
    """
    x_mm = field_box["x"]
    y_mm = field_box["y"]
    w_mm = field_box["w"]
    h_mm = field_box["h"]
    
    # Convert mm → pixels
    x1 = int(x_mm * PX_PER_MM)
    x2 = int((x_mm + w_mm) * PX_PER_MM)
    
    # Flip Y: ReportLab y=0 is bottom; OpenCV y=0 is top
    y_bottom = int((sheet_h_mm - y_mm) * PX_PER_MM)
    y_top    = int((sheet_h_mm - y_mm - h_mm) * PX_PER_MM)
    
    # Bounds check
    if len(aligned_img.shape) == 2:
        img_h, img_w = aligned_img.shape
    else:
        img_h, img_w = aligned_img.shape[:2]
    
    y_top  = max(0, min(y_top, img_h))
    y_bottom = max(0, min(y_bottom, img_h))
    x1 = max(0, min(x1, img_w))
    x2 = max(0, min(x2, img_w))
    
    if y_bottom <= y_top or x2 <= x1:
        return None
    
    return aligned_img[y_top:y_bottom, x1:x2]


def extract_fields(image_path, layout_data_or_path, output_dir=None):
    """
    Extract handwritten field images (Name, ID, Class, Date) from a scanned
    OMR sheet using coordinate-based cropping. No OCR required.
    
    The scanner aligns the image to the layout's coordinate system via
    perspective transform, then crops the exact pixel regions where
    handwriting was written.
    
    Args:
        image_path: Path to the scanned OMR sheet photo
        layout_data_or_path: Layout JSON (dict or path to file)
        output_dir: If provided, saves cropped images as PNGs here
        
    Returns:
        {
            "name_img":  numpy array (or None),
            "id_img":    numpy array (or None),
            "class_img": numpy array (or None),
            "date_img":  numpy array (or None),
            "fields_b64": {           # base64-encoded PNGs for embedding
                "name":  "data:image/png;base64,...",
                "id":    "data:image/png;base64,...",
                "class": "data:image/png;base64,...",
                "date":  "data:image/png;base64,...",
            }
        }
    """
    import base64
    
    # Load layout
    if isinstance(layout_data_or_path, str):
        with open(layout_data_or_path, "r") as f:
            layout_data = json.load(f)
    else:
        layout_data = layout_data_or_path

    sheet = layout_data["sheets"][0]
    sheet_h_mm = sheet["sheet_size_mm"][1]
    fields_mm = sheet.get("fields_mm", {})
    
    if not fields_mm:
        raise ValueError("Layout JSON does not contain 'fields_mm'. "
                         "Regenerate sheets with the latest omr_generator.py.")

    # Load and align (reuse the scanner's alignment pipeline). Align in colour so
    # the handwriting crops look natural; orientation is auto-corrected so fields
    # crop from the right place even on a rotated photo.
    color_img = cv2.imread(image_path)
    if color_img is None:
        raise ValueError(f"Could not load image: {image_path}")
    aligned_color, _ = _align_sheet(color_img, sheet)

    result = {
        "name_img": None, "id_img": None,
        "class_img": None, "subject_img": None, "date_img": None,
        "fields_b64": {}
    }
    
    for field_name in ["name", "id", "class", "subject", "date"]:
        if field_name not in fields_mm:
            continue
        
        crop = _crop_field(aligned_color, fields_mm[field_name], sheet_h_mm)
        if crop is None:
            continue
        
        result[f"{field_name}_img"] = crop
        
        # Encode to base64 PNG for embedding in receipts / API responses
        _, buf = cv2.imencode(".png", crop)
        b64 = base64.b64encode(buf).decode("utf-8")
        result["fields_b64"][field_name] = f"data:image/png;base64,{b64}"
        
        # Optionally save to disk
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            out_path = os.path.join(output_dir, f"field_{field_name}.png")
            cv2.imwrite(out_path, crop)
    
    return result


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
    # Same orientation-correcting alignment as read_bubbles, so the graded
    # overlay matches the marks that were read (both end up upright).
    aligned, _ = _align_sheet(image, sheet)
    h, w = aligned.shape[:2]

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
