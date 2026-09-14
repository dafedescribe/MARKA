"""Fail-closed reader for MARKA's ruler-drawn A4/40 answer sheet."""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np


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
