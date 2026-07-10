import cv2
import numpy as np
import json
import argparse
import sys
import os

def sort_corners(pts):
    # Sort points into [top-left, top-right, bottom-right, bottom-left]
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def find_fiducial_candidates(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive threshold to find dark regions
    thresh = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11,
        2,
    )

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    fiducials = []
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)

        # We are looking for a square (4 vertices)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = w / float(h)
            area = cv2.contourArea(c)

            # Filter by area and aspect ratio (10x10mm square -> aspect ~ 1.0)
            # Area filter is broad to account for different phone resolutions
            if 0.8 <= aspect_ratio <= 1.2 and 500 < area < 50000:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    fiducials.append([cX, cY])

    return fiducials

def select_fiducial_corners(fiducials, image_shape):
    if len(fiducials) < 4:
        raise ValueError(
            f"Found only {len(fiducials)} fiducial markers. Please ensure all 4 corner squares are clearly visible in the photo."
        )

    h, w = image_shape[:2]
    pts = np.array(fiducials, dtype="float32")
    half_w = w / 2.0
    half_h = h / 2.0

    corner_targets = [
        (np.array([0.0, 0.0], dtype="float32"), lambda p: p[0] <= half_w and p[1] <= half_h),
        (np.array([w - 1.0, 0.0], dtype="float32"), lambda p: p[0] >= half_w and p[1] <= half_h),
        (np.array([w - 1.0, h - 1.0], dtype="float32"), lambda p: p[0] >= half_w and p[1] >= half_h),
        (np.array([0.0, h - 1.0], dtype="float32"), lambda p: p[0] <= half_w and p[1] >= half_h),
    ]

    chosen = []
    used = set()

    for target, predicate in corner_targets:
        candidates = [i for i, p in enumerate(pts) if i not in used and predicate(p)]
        if not candidates:
            candidates = [i for i in range(len(pts)) if i not in used]
        if not candidates:
            break

        best_idx = min(candidates, key=lambda i: np.linalg.norm(pts[i] - target))
        chosen.append(pts[best_idx])
        used.add(best_idx)

    if len(chosen) < 4:
        raise ValueError(
            f"Found {len(fiducials)} fiducial markers, but could only confidently isolate {len(chosen)} corner markers."
        )

    return sort_corners(np.array(chosen, dtype="float32"))

def detect_fiducials(image):
    fiducials = find_fiducial_candidates(image)
    return select_fiducial_corners(fiducials, image.shape)

def draw_check_mark(image, center, radius, color=(0, 255, 0), thickness=4):
    cx, cy = int(center[0]), int(center[1])
    arm = max(6, int(radius * 0.65))
    hook = max(4, int(radius * 0.35))

    start = (cx - arm, cy + hook)
    mid = (cx - hook, cy + arm)
    end = (cx + arm, cy - arm)

    cv2.line(image, start, mid, color, thickness, cv2.LINE_8)
    cv2.line(image, mid, end, color, thickness, cv2.LINE_8)

def draw_cross_mark(image, center, radius, color=(0, 0, 255), thickness=4):
    cx, cy = int(center[0]), int(center[1])
    arm = max(6, int(radius * 0.6))

    cv2.line(
        image,
        (cx - arm, cy - arm),
        (cx + arm, cy + arm),
        color,
        thickness,
        cv2.LINE_8,
    )
    cv2.line(
        image,
        (cx - arm, cy + arm),
        (cx + arm, cy - arm),
        color,
        thickness,
        cv2.LINE_8,
    )

def draw_score_banner(image, score, total):
    width = image.shape[1]
    score_text = f"SCORE: {score}/{total} ({(score/total)*100:.1f}%)"
    org = (max(40, width // 2 - 420), 170)

    # Shadow layer for stronger contrast.
    cv2.putText(
        image,
        score_text,
        (org[0] + 4, org[1] + 4),
        cv2.FONT_HERSHEY_TRIPLEX,
        2.2,
        (0, 0, 0),
        10,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        score_text,
        org,
        cv2.FONT_HERSHEY_TRIPLEX,
        2.2,
        (0, 150, 0),
        8,
        cv2.LINE_AA,
    )

def scan_and_grade(image_path, json_path, output_path=None):
    print(f"Loading metadata from {json_path}...")
    with open(json_path, 'r') as f:
        meta = json.load(f)
        
    print(f"Loading image {image_path}...")
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image {image_path}")
        
    fiducial_candidates = find_fiducial_candidates(image)
    print(f"Found {len(fiducial_candidates)} potential fiducials. Using the four outermost corners...")
    fiducials = select_fiducial_corners(fiducial_candidates, image.shape)

    src_pts = np.array(fiducials, dtype="float32")
    
    # Scale: 10 pixels per mm
    PX_PER_MM = 10
    WIDTH = int(210 * PX_PER_MM)
    HEIGHT = int(297 * PX_PER_MM)
    
    # Fiducial theoretical centers
    # 5mm offset + 5mm (half of 10mm size) = 10mm from edge
    f_offset = 10 * PX_PER_MM
    dst_pts = np.array([
        [f_offset, f_offset],                         # Top-Left
        [WIDTH - f_offset, f_offset],                 # Top-Right
        [WIDTH - f_offset, HEIGHT - f_offset],        # Bottom-Right
        [f_offset, HEIGHT - f_offset]                 # Bottom-Left
    ], dtype="float32")
    
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    aligned = cv2.warpPerspective(image, M, (WIDTH, HEIGHT))
    aligned_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    
    print("Image aligned perfectly to A4 grid.")
    
    # Grading logic
    print("Analyzing bubbles...")
    
    answers = meta["answers"]
    bubbles = meta["bubbles"]
    
    # Group bubbles by question
    questions = {}
    for b in bubbles:
        q = str(b["question"])
        if q not in questions:
            questions[q] = []
        questions[q].append(b)
        
    score = 0
    total = len(questions)
    
    # Threshold for marking a bubble as filled.
    # We will measure average pixel value (0=black, 255=white).
    # If the average pixel value is below this threshold, it is considered marked.
    DARKNESS_THRESHOLD = 200 
    
    for q_str, q_bubbles in questions.items():
        marked_options = []
        
        for b in q_bubbles:
            # ReportLab Y is from bottom. OpenCV Y is from top.
            cx = int(b["center_x_mm"] * PX_PER_MM)
            cy = int((297 - b["center_y_mm"]) * PX_PER_MM)
            r = int(b["radius_mm"] * PX_PER_MM)
            
            # Create a circular mask to isolate the bubble
            mask = np.zeros(aligned_gray.shape, dtype="uint8")
            cv2.circle(mask, (cx, cy), int(r * 0.8), 255, -1) # Slightly smaller radius to avoid borders
            
            # Calculate mean pixel intensity inside the bubble
            mean_val = cv2.mean(aligned_gray, mask=mask)[0]
            
            if mean_val < DARKNESS_THRESHOLD:
                marked_options.append(b["option"])
                b["marked"] = True
            else:
                b["marked"] = False
                
        # Determine correctness
        correct_answer = answers.get(q_str)
        is_correct = False
        
        if len(marked_options) == 1 and marked_options[0] == correct_answer:
            score += 1
            is_correct = True
            
        # Draw visual feedback
        for b in q_bubbles:
            cx = int(b["center_x_mm"] * PX_PER_MM)
            cy = int((297 - b["center_y_mm"]) * PX_PER_MM)
            r = int(b["radius_mm"] * PX_PER_MM)
            
            if b["marked"]:
                if b["option"] == correct_answer:
                    # Correctly marked -> Green check mark
                    draw_check_mark(aligned, (cx, cy), r, color=(0, 255, 0), thickness=4)
                else:
                    # Incorrectly marked -> Red X
                    draw_cross_mark(aligned, (cx, cy), r, color=(0, 0, 255), thickness=4)
            else:
                if b["option"] == correct_answer and not is_correct:
                    # Missed correct answer -> Red check mark
                    draw_check_mark(aligned, (cx, cy), r, color=(0, 0, 255), thickness=4)

    # Add the score to the top of the page
    draw_score_banner(aligned, score, total)

    if output_path is None:
        output_path = "graded_output.jpg"
    cv2.imwrite(output_path, aligned)
    
    print("\n" + "="*40)
    print(f"FINAL SCORE: {score}/{total}")
    print(f"Percentage: {(score/total)*100:.1f}%")
    print("="*40)
    print(f"Sleek graded image saved to: {output_path}")
    
    return {"score": score, "total": total, "percentage": round((score/total)*100, 1), "output_path": output_path}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scan and Grade Exam Image')
    parser.add_argument('image', help='Path to the scanned image (JPG/PNG)')
    parser.add_argument('json', help='Path to the exam.json metadata file')
    args = parser.parse_args()
    
    scan_and_grade(args.image, args.json)
