from __future__ import annotations

import cv2
import numpy as np


def _mm(value, px_per_mm):
    return int(round(value * px_per_mm))


def render_sheet(
    profile,
    marks=None,
    px_per_mm=5,
    orientation_cue=True,
    missing_anchor=None,
    broken_grid_line=None,
    cell_jitter_px=0,
    seed=7,
    identity_text=None,
):
    """Return a deterministic white BGR A4 image with ruler lines and marks."""
    paper = profile["paper"]
    width = _mm(paper["width_mm"], px_per_mm)
    height = _mm(paper["height_mm"], px_per_mm)
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    rng = np.random.default_rng(seed)
    thickness = max(2, int(round(px_per_mm * 0.45)))

    for anchor in profile["anchors"]:
        if anchor["id"] == missing_anchor:
            continue
        left, top, right, bottom = [_mm(v, px_per_mm) for v in anchor["bounds_mm"]]
        cv2.rectangle(image, (left, top), (right, bottom), (0, 0, 0), thickness)
        if anchor["orientation_x"] and orientation_cue:
            inset = _mm(2, px_per_mm)
            cv2.line(image, (left + inset, top + inset), (right - inset, bottom - inset), (0, 0, 0), thickness)
            cv2.line(image, (left + inset, bottom - inset), (right - inset, top + inset), (0, 0, 0), thickness)

    strip = profile.get("identity_fields")
    if strip:
        left, top, right, bottom = [_mm(v, px_per_mm) for v in strip["bounds_mm"]]
        cv2.rectangle(image, (left, top), (right, bottom), (0, 0, 0), thickness)
        for field in strip["fields"][:-1]:
            divider = _mm(field["right_mm"], px_per_mm)
            cv2.line(image, (divider, top), (divider, bottom), (0, 0, 0), thickness)
        for key, text in (identity_text or {}).items():
            field = next(item for item in strip["fields"] if item["key"] == key)
            cv2.putText(
                image,
                text,
                (_mm(field["left_mm"] + 2, px_per_mm), _mm(43, px_per_mm)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (30, 30, 30),
                max(1, int(px_per_mm * 0.3)),
            )

    measured = {}
    for grid in profile["grids"]:
        left, top, right, bottom = grid["bounds_mm"]
        header_left, header_top, header_right, header_bottom = grid["header_bounds_mm"]
        header_x = [_mm(header_left + i * 10, px_per_mm) for i in range(7)]
        header_y = [_mm(header_top, px_per_mm), _mm(header_bottom, px_per_mm)]
        for x in header_x:
            cv2.line(image, (x, header_y[0]), (x, header_y[1]), (0, 0, 0), thickness)
        for y in header_y:
            cv2.line(image, (header_x[0], y), (header_x[-1], y), (0, 0, 0), thickness)
        for index, option in enumerate(profile["choices"]):
            cv2.putText(image, option, (header_x[index + 1] + _mm(3, px_per_mm), header_y[1] - _mm(3, px_per_mm)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), max(1, thickness // 2))
        nominal_x = np.array([_mm(left + i * 10, px_per_mm) for i in range(7)])
        nominal_y = np.array([_mm(top + i * 10, px_per_mm) for i in range(21)])
        if cell_jitter_px:
            x_jitter = rng.integers(-cell_jitter_px, cell_jitter_px + 1, size=7)
            y_jitter = rng.integers(-cell_jitter_px, cell_jitter_px + 1, size=21)
            x_jitter[[0, -1]] = 0
            y_jitter[[0, -1]] = 0
            nominal_x += x_jitter
            nominal_y += y_jitter
        measured[grid["id"]] = {"x": nominal_x, "y": nominal_y}

        for index, x in enumerate(nominal_x):
            skip = broken_grid_line == (grid["id"], "vertical", index, "full")
            if not skip:
                cv2.line(image, (int(x), int(nominal_y[0])), (int(x), int(nominal_y[-1])), (0, 0, 0), thickness)
        for index, y in enumerate(nominal_y):
            mode = broken_grid_line == (grid["id"], "horizontal", index, "full")
            if mode:
                continue
            if broken_grid_line == (grid["id"], "horizontal", index, "small"):
                midpoint = int((nominal_x[0] + nominal_x[-1]) / 2)
                cv2.line(image, (int(nominal_x[0]), int(y)), (midpoint - 6, int(y)), (0, 0, 0), thickness)
                cv2.line(image, (midpoint + 6, int(y)), (int(nominal_x[-1]), int(y)), (0, 0, 0), thickness)
            else:
                cv2.line(image, (int(nominal_x[0]), int(y)), (int(nominal_x[-1]), int(y)), (0, 0, 0), thickness)

    choice_index = {option: index for index, option in enumerate(profile["choices"])}
    for question, mark_spec in (marks or {}).items():
        specs = mark_spec if isinstance(mark_spec, list) else [mark_spec]
        grid_id = "left" if int(question) <= 20 else "right"
        row = int(question) - (1 if grid_id == "left" else 21)
        for option, shape in specs:
            column = choice_index[option] + 1
            x_lines = measured[grid_id]["x"]
            y_lines = measured[grid_id]["y"]
            cx = int((x_lines[column] + x_lines[column + 1]) / 2)
            cy = int((y_lines[row] + y_lines[row + 1]) / 2)
            half = max(7, _mm(3, px_per_mm))
            mark_thickness = max(2, int(round(px_per_mm * 0.55)))
            if shape == "tick":
                cv2.line(image, (cx - half, cy), (cx - 2, cy + half), (50, 50, 50), mark_thickness)
                cv2.line(image, (cx - 2, cy + half), (cx + half, cy - half), (50, 50, 50), mark_thickness)
            elif shape == "x-boundary":
                boundary_x = int(x_lines[column + 1])
                cv2.line(image, (boundary_x - half, cy - half), (boundary_x + half, cy + half), (50, 50, 50), mark_thickness)
                cv2.line(image, (boundary_x - half, cy + half), (boundary_x + half, cy - half), (50, 50, 50), mark_thickness)
            else:
                cv2.line(image, (cx - half, cy - half), (cx + half, cy + half), (50, 50, 50), mark_thickness)
                cv2.line(image, (cx - half, cy + half), (cx + half, cy - half), (50, 50, 50), mark_thickness)
    return image


def transform_capture(
    image,
    rotation_degrees=0,
    perspective_ratio=0,
    shadow=False,
    blur_sigma=0,
    crop_px=0,
):
    """Return a reproducibly degraded phone-like capture."""
    height, width = image.shape[:2]
    pad = int(max(height, width) * 0.20)
    canvas = cv2.copyMakeBorder(image, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    ch, cw = canvas.shape[:2]

    if perspective_ratio:
        inset = float(min(width, height) * perspective_ratio)
        source = np.float32([[pad, pad], [pad + width, pad], [pad + width, pad + height], [pad, pad + height]])
        destination = np.float32([
            [pad + inset, pad],
            [pad + width - inset * 0.25, pad + inset * 0.35],
            [pad + width, pad + height - inset * 0.20],
            [pad, pad + height],
        ])
        matrix = cv2.getPerspectiveTransform(source, destination)
        canvas = cv2.warpPerspective(canvas, matrix, (cw, ch), borderValue=(255, 255, 255))

    if rotation_degrees:
        matrix = cv2.getRotationMatrix2D((cw / 2, ch / 2), rotation_degrees, 1.0)
        canvas = cv2.warpAffine(canvas, matrix, (cw, ch), borderValue=(255, 255, 255))

    if shadow:
        gradient = np.linspace(0.62, 1.0, cw, dtype=np.float32)[None, :, None]
        canvas = np.clip(canvas.astype(np.float32) * gradient, 0, 255).astype(np.uint8)
    if blur_sigma:
        canvas = cv2.GaussianBlur(canvas, (0, 0), blur_sigma)
    if crop_px:
        canvas = canvas[crop_px:-crop_px, crop_px:-crop_px]
    return canvas
