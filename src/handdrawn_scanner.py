"""Fail-closed reader for MARKA's ruler-drawn A4/40 answer sheet."""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

from field_crops import encode_field_crop


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = ROOT / "data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json"
CANONICAL_PX_PER_MM = 5


class HanddrawnScanError(ValueError):
    """A safe, actionable rejection of a hand-drawn scan."""

    def __init__(self, code: str, message: str, action: str):
        super().__init__(f"{message} {action}")
        self.code = code
        self.message = message
        self.action = action


def load_handdrawn_profile(path=DEFAULT_PROFILE_PATH) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_image(image_or_path):
    if isinstance(image_or_path, (str, Path)):
        image = cv2.imread(str(image_or_path), cv2.IMREAD_COLOR)
        if image is None:
            raise HanddrawnScanError(
                "IMAGE_UNREADABLE",
                "The image could not be opened.",
                "Upload a JPEG or PNG photograph of the full sheet.",
            )
        return image
    image = np.asarray(image_or_path)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image.copy()


def assess_capture_quality(gray: np.ndarray, profile: dict) -> dict:
    minimum_height = int(profile["capture"]["minimum_image_height_px"])
    if gray.shape[0] < minimum_height:
        raise HanddrawnScanError(
            "IMAGE_TOO_SMALL",
            "The photograph is too small to read the 1 cm boxes safely.",
            "Move closer or use a higher-resolution camera.",
        )

    scale = min(1.0, 1000.0 / gray.shape[0])
    sample = cv2.resize(gray, None, fx=scale, fy=scale) if scale < 1 else gray
    sharpness = float(cv2.Laplacian(sample, cv2.CV_64F).var())
    if sharpness < 12.0:
        raise HanddrawnScanError(
            "IMAGE_BLURRY",
            "The photograph is too blurry to separate pencil marks from guide lines.",
            "Hold the camera steady and retake the photograph.",
        )

    mean = float(sample.mean())
    contrast = float(sample.std())
    if mean < 65 or mean > 252 or contrast < 8:
        raise HanddrawnScanError(
            "LIGHTING_UNSAFE",
            "The sheet does not have enough visible contrast.",
            "Move to even light and retake the photograph.",
        )
    return {
        "height_px": int(gray.shape[0]),
        "width_px": int(gray.shape[1]),
        "sharpness": round(sharpness, 2),
        "mean": round(mean, 2),
        "contrast": round(contrast, 2),
        "ok": True,
    }


def _square_candidates(gray: np.ndarray):
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        9,
    )
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    minimum_side = max(14, int(min(gray.shape[:2]) * 0.012))
    maximum_side = int(min(gray.shape[:2]) * 0.085)
    raw = []
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        polygon = cv2.approxPolyDP(contour, 0.035 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        x, y, width, height = cv2.boundingRect(polygon)
        side = max(width, height)
        if not minimum_side <= side <= maximum_side:
            continue
        aspect = width / max(float(height), 1.0)
        if not 0.68 <= aspect <= 1.32:
            continue
        area = abs(cv2.contourArea(polygon))
        if area < width * height * 0.45:
            continue

        margin = max(5, int(side * 0.45))
        left, top = max(0, x - margin), max(0, y - margin)
        right = min(gray.shape[1], x + width + margin)
        bottom = min(gray.shape[0], y + height + margin)
        surroundings = binary[top:bottom, left:right].copy()
        inner_left, inner_top = x - left, y - top
        surroundings[inner_top:inner_top + height, inner_left:inner_left + width] = 0
        outside_ratio = float(np.count_nonzero(surroundings)) / max(surroundings.size, 1)
        if outside_ratio > 0.055:
            continue

        inset_x = max(2, int(width * 0.22))
        inset_y = max(2, int(height * 0.22))
        interior = binary[y + inset_y:y + height - inset_y,
                          x + inset_x:x + width - inset_x]
        interior_ink = float(np.count_nonzero(interior)) / max(interior.size, 1)
        raw.append({
            "center": np.array([x + width / 2.0, y + height / 2.0], dtype=np.float32),
            "bbox": (x, y, width, height),
            "side": float((width + height) / 2.0),
            "interior_ink": interior_ink,
            "outside_ink": outside_ratio,
        })

    raw.sort(key=lambda item: item["side"], reverse=True)
    candidates = []
    for item in raw:
        if any(np.linalg.norm(item["center"] - other["center"]) < item["side"] * 0.35
               for other in candidates):
            continue
        candidates.append(item)
    return candidates, binary


def detect_handdrawn_anchors(gray: np.ndarray, profile: dict):
    candidates, _ = _square_candidates(gray)
    if len(candidates) < 4:
        raise HanddrawnScanError(
            "ANCHOR_MISSING",
            "We could not find all four corner squares.",
            "Move back and include all four corner squares in the photograph.",
        )

    points = np.array([item["center"] for item in candidates], dtype=np.float32)
    sums = points[:, 0] + points[:, 1]
    differences = points[:, 0] - points[:, 1]
    indices = [
        int(np.argmin(sums)),
        int(np.argmax(differences)),
        int(np.argmax(sums)),
        int(np.argmin(differences)),
    ]
    if len(set(indices)) != 4:
        raise HanddrawnScanError(
            "ANCHOR_AMBIGUOUS",
            "The four corner squares could not be separated safely.",
            "Flatten the page and retake it with all paper edges visible.",
        )
    selected = [candidates[index] for index in indices]
    selected_points = np.array([item["center"] for item in selected], dtype=np.float32)
    span_x = float(np.ptp(selected_points[:, 0]))
    span_y = float(np.ptp(selected_points[:, 1]))
    if span_x < gray.shape[1] * 0.50 or span_y < gray.shape[0] * 0.50:
        raise HanddrawnScanError(
            "ANCHOR_MISSING",
            "We could not find all four corner squares.",
            "Move back and include all four corner squares in the photograph.",
        )

    ink = np.array([item["interior_ink"] for item in selected])
    order = np.argsort(ink)[::-1]
    best, second = float(ink[order[0]]), float(ink[order[1]])
    if best < 0.055 or best - second < 0.025:
        raise HanddrawnScanError(
            "ORIENTATION_CUE_MISSING",
            "The top-left X could not be identified safely.",
            "Check that only the top-left square contains an X.",
        )

    cue = selected[int(order[0])]["center"]
    remaining = [item["center"] for index, item in enumerate(selected) if index != int(order[0])]
    remaining.sort(key=lambda point: float(np.linalg.norm(point - cue)))
    physical = np.float32([cue, remaining[0], remaining[2], remaining[1]])
    return physical, {
        "mode": "handdrawn-four-anchor",
        "anchor_count": 4,
        "candidate_count": len(candidates),
        "orientation_cue": "top_left_x",
        "orientation_margin": round(best - second, 4),
    }


def align_handdrawn_page(image_or_path, profile=None):
    profile = profile or load_handdrawn_profile()
    image = _load_image(image_or_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    quality = assess_capture_quality(gray, profile)
    source_points, diagnostics = detect_handdrawn_anchors(gray, profile)

    destination = []
    for anchor in profile["anchors"]:
        left, top, right, bottom = anchor["bounds_mm"]
        destination.append([
            ((left + right) / 2.0) * CANONICAL_PX_PER_MM,
            ((top + bottom) / 2.0) * CANONICAL_PX_PER_MM,
        ])
    destination = np.float32(destination)
    matrix = cv2.getPerspectiveTransform(source_points, destination)
    width = int(profile["paper"]["width_mm"] * CANONICAL_PX_PER_MM)
    height = int(profile["paper"]["height_mm"] * CANONICAL_PX_PER_MM)
    aligned = cv2.warpPerspective(image, matrix, (width, height), borderValue=(255, 255, 255))
    diagnostics["quality"] = quality
    diagnostics["corrected_degrees"] = 0
    return aligned, diagnostics



def _line_projection(binary: np.ndarray, orientation: str) -> np.ndarray:
    kernel_shape = (25, 1) if orientation == "vertical" else (1, 25)
    opened = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        np.ones(kernel_shape, dtype=np.uint8),
    )
    axis = 0 if orientation == "vertical" else 1
    return np.count_nonzero(opened, axis=axis).astype(np.float32)


def _find_expected_lines(
    projection: np.ndarray,
    expected_px,
    search_radius_px: int,
    minimum_evidence: float,
):
    found = []
    for expected in expected_px:
        start = max(0, int(round(expected)) - search_radius_px)
        stop = min(len(projection), int(round(expected)) + search_radius_px + 1)
        local = projection[start:stop]
        if local.size == 0 or float(local.max()) < minimum_evidence:
            raise HanddrawnScanError(
                "GRID_TOPOLOGY_UNSAFE",
                "The two 20-row grids could not be read safely.",
                "Check every ruler line and retake the photograph.",
            )
        peak = float(local.max())
        peak_indices = np.flatnonzero(local >= peak * 0.92)
        found.append(start + int(round(float(peak_indices.mean()))))
    return found


def _validate_axis_spacing(lines, minimum=40, maximum=60):
    spacing = np.diff(np.asarray(lines, dtype=np.float32))
    if np.any(spacing < minimum) or np.any(spacing > maximum):
        raise HanddrawnScanError(
            "GRID_TOPOLOGY_UNSAFE",
            "The ruler lines do not form consistent 1 cm boxes.",
            "Check both grids and redraw any missing or doubled line.",
        )


def detect_handdrawn_grid(aligned: np.ndarray, profile: dict) -> dict:
    "Find the actual 21 horizontal and seven vertical grid lines per block."
    gray = aligned if aligned.ndim == 2 else cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        9,
    )
    result = {}
    radius = 18
    for grid_definition in profile["grids"]:
        left, top, right, bottom = [
            value * CANONICAL_PX_PER_MM for value in grid_definition["bounds_mm"]
        ]
        pad = 22
        x1 = max(0, int(left - pad))
        x2 = min(gray.shape[1], int(right + pad + 1))
        y1 = max(0, int(top - pad))
        y2 = min(gray.shape[0], int(bottom + pad + 1))

        vertical_crop = binary[int(top):int(bottom) + 1, x1:x2]
        vertical_projection = _line_projection(vertical_crop, "vertical")
        expected_vertical = [
            left - x1 + index * 10 * CANONICAL_PX_PER_MM for index in range(7)
        ]
        vertical_local = _find_expected_lines(
            vertical_projection,
            expected_vertical,
            radius,
            minimum_evidence=(bottom - top) * 0.40,
        )
        vertical = [x1 + value for value in vertical_local]

        horizontal_crop = binary[y1:y2, int(left):int(right) + 1]
        horizontal_projection = _line_projection(horizontal_crop, "horizontal")
        expected_horizontal = [
            top - y1 + index * 10 * CANONICAL_PX_PER_MM for index in range(21)
        ]
        horizontal_local = _find_expected_lines(
            horizontal_projection,
            expected_horizontal,
            radius,
            minimum_evidence=(right - left) * 0.40,
        )
        horizontal = [y1 + value for value in horizontal_local]

        _validate_axis_spacing(vertical)
        _validate_axis_spacing(horizontal)
        result[grid_definition["id"]] = {
            "vertical_lines_px": vertical,
            "horizontal_lines_px": horizontal,
            "questions": list(grid_definition["questions"]),
        }
    return result


def build_handdrawn_cells(grid: dict, profile: dict):
    "Map questions 1–40 and A–E to measured pixel rectangles."
    cells = {}
    for grid_definition in profile["grids"]:
        measured = grid[grid_definition["id"]]
        vertical = measured["vertical_lines_px"]
        horizontal = measured["horizontal_lines_px"]
        first_question = int(grid_definition["questions"][0])
        for row in range(20):
            question = first_question + row
            cells[question] = {}
            for choice_index, option in enumerate(profile["choices"]):
                column = choice_index + 1
                cells[question][option] = (
                    int(vertical[column]),
                    int(horizontal[row]),
                    int(vertical[column + 1]),
                    int(horizontal[row + 1]),
                )
    return cells



def _binary_foreground(gray: np.ndarray) -> np.ndarray:
    normalized = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return cv2.adaptiveThreshold(
        normalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 9,
    )


def score_handdrawn_cells(gray: np.ndarray, cells: dict, profile: dict) -> dict:
    "Measure interior ink and unsafe choice-boundary leakage per question."
    foreground = _binary_foreground(gray)
    cleaned = foreground.copy()
    line_half_width = 4
    x_lines = set()
    y_lines = set()
    for options in cells.values():
        for x1, y1, x2, y2 in options.values():
            x_lines.update((x1, x2))
            y_lines.update((y1, y2))
    for x in x_lines:
        cleaned[:, max(0, x - line_half_width):x + line_half_width + 1] = 0
    for y in y_lines:
        cleaned[max(0, y - line_half_width):y + line_half_width + 1, :] = 0

    margin_ratio = float(profile["marking"]["inner_margin_ratio"])
    scores = {}
    for question, options in cells.items():
        option_scores = {}
        ordered_rects = []
        for option, (x1, y1, x2, y2) in options.items():
            margin = max(4, int(round(min(x2 - x1, y2 - y1) * margin_ratio)))
            roi = cleaned[y1 + margin:y2 - margin, x1 + margin:x2 - margin]
            option_scores[option] = float(np.count_nonzero(roi)) / max(roi.size, 1)
            ordered_rects.append((option, (x1, y1, x2, y2)))

        boundary_leakage = False
        for (_, left_rect), (_, right_rect) in zip(ordered_rects, ordered_rects[1:]):
            boundary_x = left_rect[2]
            y1 = max(left_rect[1], right_rect[1]) + 7
            y2 = min(left_rect[3], right_rect[3]) - 7
            corridor = cleaned[y1:y2, boundary_x - 7:boundary_x + 8]
            if corridor.size and float(np.count_nonzero(corridor)) / corridor.size >= 0.025:
                boundary_leakage = True
                break
        scores[question] = {
            "options": option_scores,
            "boundary_leakage": boundary_leakage,
        }
    return scores


def classify_handdrawn_marks(scores: dict, profile: dict):
    minimum = float(profile["marking"]["minimum_ink_ratio"])
    winner_gap = float(profile["marking"]["minimum_winner_gap"])
    marks, multi_marks, confidence, ambiguous = {}, {}, {}, []
    for question in range(1, int(profile["questions"]) + 1):
        item = scores[question]
        values = item["options"]
        ranked = sorted(values.items(), key=lambda pair: pair[1], reverse=True)
        baseline = float(np.median(list(values.values())))
        qualifying = [
            (option, value) for option, value in ranked
            if value >= minimum and value - baseline >= winner_gap
        ]
        key = str(question)
        if item["boundary_leakage"]:
            marks[key] = None
            confidence[key] = 0.0
            ambiguous.append(key)
        elif len(qualifying) > 1:
            marks[key] = None
            multi_marks[key] = [option for option, _ in qualifying]
            confidence[key] = 0.0
            ambiguous.append(key)
        elif len(qualifying) == 1:
            option, value = qualifying[0]
            second = ranked[1][1]
            marks[key] = option
            confidence[key] = round(float(np.clip(
                (value - second) / (winner_gap * 3.0), 0.0, 1.0
            )), 2)
        else:
            marks[key] = None
            confidence[key] = 0.0
    return marks, multi_marks, confidence, ambiguous


def read_handdrawn(image_or_path, profile=None) -> dict:
    "Read one HANDDRAWN_A4_40_V1 image without grading it."
    started = time.perf_counter()
    profile = profile or load_handdrawn_profile()
    aligned, registration = align_handdrawn_page(image_or_path, profile)
    grid = detect_handdrawn_grid(aligned, profile)
    cells = build_handdrawn_cells(grid, profile)
    gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    scores = score_handdrawn_cells(gray, cells, profile)
    marks, multi_marks, confidence, ambiguous = classify_handdrawn_marks(scores, profile)
    elapsed = (time.perf_counter() - started) * 1000.0
    sharpness = registration["quality"]["sharpness"]
    fields_b64 = {}
    strip = profile.get("identity_fields", {})
    for field in strip.get("fields", []):
        inset = 1.2
        left = int((field["left_mm"] + inset) * CANONICAL_PX_PER_MM)
        right = int((field["right_mm"] - inset) * CANONICAL_PX_PER_MM)
        top = int((strip["bounds_mm"][1] + inset) * CANONICAL_PX_PER_MM)
        bottom = int((strip["bounds_mm"][3] - inset) * CANONICAL_PX_PER_MM)
        encoded = encode_field_crop(aligned[top:bottom, left:right])
        if encoded:
            fields_b64[field["key"]] = encoded
    return {
        "sheet_id": profile["profile_id"],
        "marks": marks,
        "multi_marks": multi_marks,
        "confidence": confidence,
        "ambiguous": ambiguous,
        "fields_b64": fields_b64,
        "image_quality": {"sharpness": sharpness, "ok": True},
        "orientation": {
            "corrected_degrees": registration.get("corrected_degrees", 0),
            "cue": "top_left_x",
        },
        "registration": {
            **registration,
            "mode": "handdrawn-a4-40-v1",
            "grid_topology": "two-by-twenty-by-six",
        },
        "threshold_used": "adaptive-local-ink",
        "blank_median": round(float(np.median([
            value for item in scores.values() for value in item["options"].values()
        ])), 4),
        "time_ms": round(elapsed, 2),
    }


def _accepted_answers(correct):
    if correct == "*" or correct == ["*"]:
        return True, set()
    if isinstance(correct, list):
        return False, {str(value).strip().upper() for value in correct}
    return False, {str(correct).strip().upper()}


def grade_and_render_handdrawn(
    marks_data,
    answers,
    image_path,
    profile,
    output_path,
) -> dict:
    "Grade and draw feedback around measured hand-drawn answer cells."
    profile = profile or load_handdrawn_profile()
    aligned, _ = align_handdrawn_page(image_path, profile)
    grid = detect_handdrawn_grid(aligned, profile)
    cells = build_handdrawn_cells(grid, profile)
    score = 0
    marks = marks_data["marks"]

    for question_key, correct in answers.items():
        question = int(question_key)
        bonus, accepted = _accepted_answers(correct)
        student = marks.get(str(question))
        is_correct = bonus or student in accepted
        if is_correct:
            score += 1
        for option, (x1, y1, x2, y2) in cells.get(question, {}).items():
            if option == student:
                color = (0, 170, 0) if is_correct else (0, 0, 220)
                cv2.rectangle(aligned, (x1 + 3, y1 + 3), (x2 - 3, y2 - 3), color, 3)
            elif option in accepted and not is_correct:
                cv2.rectangle(aligned, (x1 + 3, y1 + 3), (x2 - 3, y2 - 3), (0, 170, 0), 3)
            if str(question) in marks_data.get("ambiguous", []):
                detected = marks_data.get("multi_marks", {}).get(str(question), [])
                if not detected or option in detected:
                    cv2.rectangle(aligned, (x1 + 5, y1 + 5), (x2 - 5, y2 - 5), (0, 165, 255), 2)

    total = len(answers)
    percentage = score / total * 100.0 if total else 0.0
    label = f"SCORE: {score}/{total} ({percentage:.0f}%)"
    cv2.putText(aligned, label, (105, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 130, 0), 3, cv2.LINE_AA)
    if not cv2.imwrite(str(output_path), aligned):
        raise ValueError(f"Could not write graded image: {output_path}")
    return {
        "score": score,
        "total": total,
        "percentage": round(percentage, 1),
        "output_path": str(output_path),
    }
