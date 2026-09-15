#!/usr/bin/env python3
"""Generate the high-visibility, deformation-aware MARKA R07-E OMR sheet."""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


PAGE_W_MM = 210.0
PAGE_H_MM = 297.0
SHEET_W_MM = 198.0
SHEET_H_MM = 140.0
SHEET_GAP_MM = 5.0
PAGE_MARGIN_MM = 6.0
FORM_MARGIN_MM = 3.0

ARUCO_DICTIONARY = "DICT_4X4_50"
ARUCO_MARKER_SIZE_MM = 7.5
OPTIONAL_ARUCO_MARKER_SIZE_MM = 6.0
ARUCO_MOAT_MM = 1.7

BUBBLE_RADIUS_MM = 1.9
BUBBLE_SPACING_MM = 4.8
BUBBLE_STROKE_WIDTH_PT = 0.8
QUESTION_NUMBER_FONT_SIZE_PT = 8.0
QUESTION_NUMBER_BASELINE_OFFSET_MM = 0.75
QUESTION_NUMBER_RIGHT_OFFSET_MM = 6.0
OPTION_HEADER_FONT_SIZE_PT = 8.0
RANGE_HEADER_FONT_SIZE_PT = 7.0
FIELD_LABEL_FONT_SIZE_PT = 6.8
INSTRUCTION_FONT_SIZE_PT = 6.5
FOOTER_FONT_SIZE_PT = 6.0
GROUP_HEADER_Y_MM = 99.3
GROUP_HEADER_HEIGHT_MM = 4.2
GROUP_HEADER_BASELINE_MM = 100.5
RANGE_HEADER_RIGHT_OFFSET_MM = 6.0
TIMING_TRACK_WIDTH_MM = 1.0
TIMING_TRACK_HEIGHT_MM = 2.2
TIMING_TRACK_LEFT_X_MM = 12.9
TIMING_TRACK_RIGHT_X_MM = 182.5

BRAND_PLUM = colors.HexColor("#3B2545")
BRAND_PLUM_LIGHT = colors.HexColor("#F1ECF3")
INK = colors.HexColor("#242027")
MUTED_INK = colors.HexColor("#655C68")
RULE = colors.HexColor("#D3CCD6")
PAPER_TINT = colors.HexColor("#FCFBFD")

ANCHOR_X_MM = 8.0
ANCHOR_Y_MM = 8.0
SHEET_CENTER_X_MM = SHEET_W_MM / 2.0
SHEET_CENTER_Y_MM = SHEET_H_MM / 2.0

# Five columns × 20 questions gives 100 questions with more comfortable row
# spacing than the previous four-column/25-row layout.
COLUMN_X_MM = [12.0, 47.0, 82.0, 117.0, 152.0]
# Every answer column uses the same x rhythm.
BUBBLE_OFFSETS_MM = [8.5, 8.5, 8.5, 8.5, 8.5]
GRID_TOP_MM = 96.9
GRID_BOTTOM_MM = 15.2

FIELD_DEFS = (
    ("name", "Name", 12.0, 104.0, 55.0, 8.4),
    ("student_id", "Student ID", 70.0, 104.0, 21.0, 8.4),
    ("class", "Class", 105.0, 104.0, 22.0, 8.4),
    ("subject", "Subject", 130.0, 104.0, 32.0, 8.4),
    ("date", "Date", 165.0, 104.0, 24.0, 8.4),
)


def _aruco_marker_png(marker_id: int, pixels: int = 256) -> bytes:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    if hasattr(cv2.aruco, "generateImageMarker"):
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, pixels)
    else:
        marker = cv2.aruco.drawMarker(dictionary, marker_id, pixels)
    ok, encoded = cv2.imencode(".png", marker)
    if not ok:
        raise RuntimeError(f"Could not encode ArUco marker {marker_id}")
    return encoded.tobytes()


def _anchor_definitions() -> List[Dict[str, object]]:
    positions = (
        (0, "top_left", [ANCHOR_X_MM, SHEET_H_MM - ANCHOR_Y_MM]),
        (1, "top", [SHEET_CENTER_X_MM, SHEET_H_MM - ANCHOR_Y_MM]),
        (2, "top_right", [SHEET_W_MM - ANCHOR_X_MM, SHEET_H_MM - ANCHOR_Y_MM]),
        (3, "right", [SHEET_W_MM - ANCHOR_X_MM, SHEET_CENTER_Y_MM]),
        (4, "bottom_right", [SHEET_W_MM - ANCHOR_X_MM, ANCHOR_Y_MM]),
        (5, "bottom", [SHEET_CENTER_X_MM, ANCHOR_Y_MM]),
        (6, "bottom_left", [ANCHOR_X_MM, ANCHOR_Y_MM]),
        (7, "left", [ANCHOR_X_MM, SHEET_CENTER_Y_MM]),
    )
    return [
        {
            "id": marker_id,
            "role": role,
            "center_mm": center,
            "size_mm": (
                ARUCO_MARKER_SIZE_MM if marker_id in {0, 2, 4, 6}
                else OPTIONAL_ARUCO_MARKER_SIZE_MM
            ),
            "required": marker_id in {0, 2, 4, 6},
        }
        for marker_id, role, center in positions
    ]


def _sheet_origins() -> List[List[float]]:
    return [[PAGE_MARGIN_MM, PAGE_MARGIN_MM + SHEET_H_MM + SHEET_GAP_MM], [PAGE_MARGIN_MM, PAGE_MARGIN_MM]]


def _field_layout() -> Dict[str, Dict[str, object]]:
    return {
        key: {"label": label, "x": x, "y": y, "w": width, "h": height}
        for key, label, x, y, width, height in FIELD_DEFS
    }


def build_layout(num_questions: int = 100) -> Dict[str, object]:
    if num_questions < 5 or num_questions % 5:
        raise ValueError("num_questions must be a positive multiple of five")

    anchors = _anchor_definitions()
    questions_per_column = num_questions // 5
    row_spacing = (GRID_TOP_MM - GRID_BOTTOM_MM) / max(questions_per_column - 1, 1)
    sheets = []

    for sheet_number, origin in enumerate(_sheet_origins(), start=1):
        timing_tracks: List[Dict[str, object]] = []
        bubbles: List[Dict[str, object]] = []

        for row_index in range(questions_per_column):
            y_mm = GRID_TOP_MM - row_index * row_spacing
            for side, x_mm in (("left", TIMING_TRACK_LEFT_X_MM), ("right", TIMING_TRACK_RIGHT_X_MM)):
                timing_tracks.append(
                    {
                        "id": len(timing_tracks),
                        "side": side,
                        "row_index": row_index,
                        "x_mm": x_mm,
                        "y_mm": round(y_mm, 3),
                        "width_mm": TIMING_TRACK_WIDTH_MM,
                        "height_mm": TIMING_TRACK_HEIGHT_MM,
                    }
                )

        for column_index, column_x in enumerate(COLUMN_X_MM):
            for row_index in range(questions_per_column):
                question = column_index * questions_per_column + row_index + 1
                y_mm = GRID_TOP_MM - row_index * row_spacing
                for option_index, option in enumerate("ABCDE"):
                    bubbles.append(
                        {
                            "question": question,
                            "option": option,
                            "x_mm": round(column_x + BUBBLE_OFFSETS_MM[column_index] + option_index * BUBBLE_SPACING_MM, 3),
                            "y_mm": round(y_mm, 3),
                            "radius_mm": BUBBLE_RADIUS_MM,
                            "column_index": column_index,
                            "row_index": row_index,
                            "timing_row_index": row_index,
                        }
                    )

        sheets.append(
            {
                "sheet_id": f"MARKA-R07E-{sheet_number:04d}",
                "page": 1,
                "origin_on_page_mm": origin,
                "sheet_size_mm": [SHEET_W_MM, SHEET_H_MM],
                "answer_columns": 5,
                "aruco_dictionary": ARUCO_DICTIONARY,
                "aruco_anchors": anchors,
                "registration": {
                    "required_anchor_ids": [0, 2, 4, 6],
                    "optional_anchor_ids": [1, 3, 5, 7],
                    "piecewise_min_optional_anchors": 2,
                    "piecewise_activation_error_px": 4.0,
                },
                "registration_safe_margin_mm": FORM_MARGIN_MM,
                "answer_grid": {
                    "column_starts_mm": COLUMN_X_MM,
                    "column_pitch_mm": 35.0,
                    "grid_top_mm": GRID_TOP_MM,
                    "grid_bottom_mm": GRID_BOTTOM_MM,
                    "bubble_radius_mm": BUBBLE_RADIUS_MM,
                    "bubble_spacing_mm": BUBBLE_SPACING_MM,
                    "question_number_right_offset_mm": QUESTION_NUMBER_RIGHT_OFFSET_MM,
                    "question_number_baseline_offset_mm": QUESTION_NUMBER_BASELINE_OFFSET_MM,
                    "timing_track_left_x_mm": TIMING_TRACK_LEFT_X_MM,
                    "timing_track_right_x_mm": TIMING_TRACK_RIGHT_X_MM,
                    "group_header": {
                        "layout": "single-line",
                        "y_mm": GROUP_HEADER_Y_MM,
                        "height_mm": GROUP_HEADER_HEIGHT_MM,
                        "baseline_mm": GROUP_HEADER_BASELINE_MM,
                        "range_right_offset_mm": RANGE_HEADER_RIGHT_OFFSET_MM,
                    },
                },
                "branding": {
                    "logo_box": {"x_mm": 12.0, "y_mm": 119.0, "w_mm": 18.0, "h_mm": 12.0},
                    "school_name": {"x_mm": 34.0, "y_mm": 128.0},
                    "contact_line": {"x_mm": 34.0, "y_mm": 122.8},
                },
                "fields_mm": _field_layout(),
                "timing_tracks": timing_tracks,
                "bubbles": bubbles,
            }
        )

    return {
        "layout_version": 4,
        "template_revision": "R07-E",
        "aruco_dictionary": ARUCO_DICTIONARY,
        "num_questions": num_questions,
        "num_choices": 5,
        "sheets_per_page": 2,
        "page_size_mm": [PAGE_W_MM, PAGE_H_MM],
        "print_spec": {
            "paper": "A4",
            "scale": "100%",
            "fit_to_page": False,
            "cut_line": True,
            "cut_instruction": "Cut on the dashed line between the two forms.",
            "safe_page_margin_mm": PAGE_MARGIN_MM,
        },
        "answers": {},
        "sheets": sheets,
    }


def _draw_aruco(c: canvas.Canvas, anchor: Dict[str, object]) -> None:
    x_mm, y_mm = anchor["center_mm"]  # type: ignore[index]
    size_mm = float(anchor["size_mm"])
    left = (float(x_mm) - size_mm / 2.0) * mm
    bottom = (float(y_mm) - size_mm / 2.0) * mm
    moat = ARUCO_MOAT_MM * mm
    c.setFillColor(colors.white)
    c.rect(left - moat, bottom - moat, size_mm * mm + 2 * moat, size_mm * mm + 2 * moat, fill=1, stroke=0)
    c.drawImage(ImageReader(io.BytesIO(_aruco_marker_png(int(anchor["id"])))), left, bottom,
                width=size_mm * mm, height=size_mm * mm, mask="auto")


def _draw_field(c: canvas.Canvas, field: Dict[str, object]) -> None:
    x, y = float(field["x"]), float(field["y"])
    width, height = float(field["w"]), float(field["h"])
    c.setFillColor(colors.white)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.roundRect(x * mm, y * mm, width * mm, height * mm, 0.8 * mm, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", FIELD_LABEL_FONT_SIZE_PT)
    c.drawString((x + 2.0) * mm, (y + height - 2.7) * mm, str(field["label"]).upper())
    c.setStrokeColor(RULE)
    c.setLineWidth(0.35)
    c.line((x + 1.8) * mm, (y + height - 3.8) * mm, (x + width - 1.8) * mm, (y + height - 3.8) * mm)


def _fitted_text(c, text, x, y, max_width, preferred, minimum=4.0, font="Helvetica"):
    size = preferred
    while size > minimum and c.stringWidth(text, font, size) > max_width:
        size -= 0.25
    c.setFont(font, size)
    c.drawString(x, y, text)


def _draw_sheet(c: canvas.Canvas, sheet: Dict[str, object], sheet_profile=None) -> None:
    c.saveState()
    origin_x, origin_y = sheet["origin_on_page_mm"]  # type: ignore[index]
    c.translate(float(origin_x) * mm, float(origin_y) * mm)

    # All fills are clipped to this form so tint cannot cross the cut line.
    clip_path = c.beginPath()
    clip_path.roundRect(
        FORM_MARGIN_MM * mm,
        FORM_MARGIN_MM * mm,
        (SHEET_W_MM - 2 * FORM_MARGIN_MM) * mm,
        (SHEET_H_MM - 2 * FORM_MARGIN_MM) * mm,
        1.8 * mm,
    )
    c.clipPath(clip_path, stroke=0, fill=0)
    c.setFillColor(PAPER_TINT)
    c.roundRect(
        FORM_MARGIN_MM * mm,
        FORM_MARGIN_MM * mm,
        (SHEET_W_MM - 2 * FORM_MARGIN_MM) * mm,
        (SHEET_H_MM - 2 * FORM_MARGIN_MM) * mm,
        1.8 * mm,
        fill=1,
        stroke=0,
    )
    c.setStrokeColor(BRAND_PLUM)
    c.setLineWidth(0.8)
    c.roundRect(
        FORM_MARGIN_MM * mm,
        FORM_MARGIN_MM * mm,
        (SHEET_W_MM - 2 * FORM_MARGIN_MM) * mm,
        (SHEET_H_MM - 2 * FORM_MARGIN_MM) * mm,
        1.8 * mm,
        fill=0,
        stroke=1,
    )

    # Branding block with a real logo box and readable contact line.
    c.setFillColor(BRAND_PLUM)
    c.roundRect(11 * mm, 116 * mm, (SHEET_W_MM - 22) * mm, 16.5 * mm, 1.2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.white)
    c.setLineWidth(0.45)
    c.roundRect(13 * mm, 119 * mm, 18 * mm, 12 * mm, 0.8 * mm, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 6.0)
    c.drawCentredString(22 * mm, 124.3 * mm, "LOGO")
    profile = sheet_profile or {}
    school_name = profile.get("school_name") or "SCHOOL / COMPANY NAME"
    contact = "  •  ".join(filter(None, [profile.get("address"), profile.get("phone"), profile.get("email")])) or "Address  •  Phone  •  Email"
    _fitted_text(c, school_name[:90], 34 * mm, 128 * mm, 100 * mm, 10.0, 5.5, "Helvetica-Bold")
    _fitted_text(c, contact, 34 * mm, 122.8 * mm, 100 * mm, 6.0)
    c.setFont("Helvetica-Bold", INSTRUCTION_FONT_SIZE_PT)
    c.drawString(34 * mm, 117.6 * mm, "SHADE ONE OPTION FULLY  •  DARK PENCIL OR PEN")
    c.setFont("Helvetica-Bold", 6.3)
    c.drawRightString((SHEET_W_MM - 15) * mm, 128 * mm, "STUDENT ANSWER SHEET")
    c.setFont("Helvetica", 6.0)
    c.drawRightString((SHEET_W_MM - 15) * mm, 122.8 * mm, "MARKA ID / EXAM CODE")

    for field in sheet["fields_mm"].values():  # type: ignore[union-attr]
        _draw_field(c, field)

    for column_index, column_x in enumerate(COLUMN_X_MM):
        questions = sorted({b["question"] for b in sheet["bubbles"] if b["column_index"] == column_index})  # type: ignore[index]
        c.setFillColor(BRAND_PLUM_LIGHT)
        c.roundRect(
            (column_x - 1) * mm, GROUP_HEADER_Y_MM * mm,
            32 * mm, GROUP_HEADER_HEIGHT_MM * mm, 0.7 * mm, fill=1, stroke=0)
        c.setFillColor(BRAND_PLUM)
        c.setFont("Helvetica-Bold", RANGE_HEADER_FONT_SIZE_PT)
        c.drawRightString(
            (column_x + RANGE_HEADER_RIGHT_OFFSET_MM) * mm,
            GROUP_HEADER_BASELINE_MM * mm,
            f"{questions[0]:02d}–{questions[-1]:02d}",
        )
        c.setFont("Helvetica-Bold", OPTION_HEADER_FONT_SIZE_PT)
        for option_index, option in enumerate("ABCDE"):
            c.drawCentredString((column_x + BUBBLE_OFFSETS_MM[column_index] + option_index * BUBBLE_SPACING_MM)   * mm, GROUP_HEADER_BASELINE_MM * mm, option)

    for track in sheet["timing_tracks"]:  # type: ignore[union-attr]
        y = float(track["y_mm"])
        c.setFillColor(colors.black)
        c.rect(
            float(track["x_mm"]) * mm,
            (y - float(track["height_mm"]) / 2) * mm,
            float(track["width_mm"]) * mm,
            float(track["height_mm"]) * mm,
            fill=1,
            stroke=0,
        )

    for column_index, column_x in enumerate(COLUMN_X_MM):
        rows = sorted(
            {(int(b["question"]), float(b["y_mm"])) for b in sheet["bubbles"] if b["column_index"] == column_index}
        )
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", QUESTION_NUMBER_FONT_SIZE_PT)
        for question, y in rows:
            c.drawRightString(
                (column_x + QUESTION_NUMBER_RIGHT_OFFSET_MM) * mm,
                (y - QUESTION_NUMBER_BASELINE_OFFSET_MM) * mm,
                str(question),
            )

    for bubble in sheet["bubbles"]:  # type: ignore[union-attr]
        c.setStrokeColor(INK)
        c.setLineWidth(BUBBLE_STROKE_WIDTH_PT)
        c.circle(float(bubble["x_mm"]) * mm, float(bubble["y_mm"]) * mm,
                 float(bubble["radius_mm"]) * mm, fill=0, stroke=1)

    c.setFillColor(MUTED_INK)
    c.setFont("Helvetica", FOOTER_FONT_SIZE_PT)
    c.drawString(15 * mm, 4.2 * mm, "REV R07-E  •  PRINT AT 100%  •  DO NOT FIT TO PAGE")
    c.setFont("Helvetica", FOOTER_FONT_SIZE_PT)
    c.drawString(15 * mm, 9.0 * mm, "KEEP FIDUCIALS VISIBLE  •  DO NOT FOLD")

    for anchor in sheet["aruco_anchors"]:  # type: ignore[union-attr]
        _draw_aruco(c, anchor)
    c.restoreState()


def _draw_page_controls(c: canvas.Canvas) -> None:
    cut_y = PAGE_MARGIN_MM + SHEET_H_MM + SHEET_GAP_MM / 2.0
    c.saveState()
    c.setStrokeColor(MUTED_INK)
    c.setDash(3, 2)
    c.setLineWidth(0.45)
    c.line(PAGE_MARGIN_MM * mm, cut_y * mm, (PAGE_W_MM - PAGE_MARGIN_MM) * mm, cut_y * mm)
    c.setDash()
    c.setFillColor(MUTED_INK)
    c.setFont("Helvetica-Bold", 6.0)
    c.drawCentredString(PAGE_W_MM / 2.0 * mm, (cut_y + 0.9) * mm, "CUT HERE  •  TWO EQUAL A5-LIKE FORMS")
    c.restoreState()


def generate_sheet(output_dir: str | os.PathLike[str], num_questions: int = 100, sheet_profile=None) -> Tuple[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    layout = build_layout(num_questions=num_questions)
    pdf_path = output_path / "marka_r07e_omr_prototype.pdf"
    json_path = output_path / "marka_r07e_omr_layout.json"

    pdf = canvas.Canvas(str(pdf_path), pagesize=A4)
    for sheet in layout["sheets"]:  # type: ignore[union-attr]
        _draw_sheet(pdf, sheet, sheet_profile)
    _draw_page_controls(pdf)
    pdf.setTitle("MARKA R07-E High-Visibility Two-up OMR Template")
    pdf.setAuthor("MARKA")
    pdf.save()
    json_path.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
    return str(pdf_path), str(json_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="outputs/v2_prototype")
    parser.add_argument("--questions", type=int, default=100)
    args = parser.parse_args()
    pdf_path, json_path = generate_sheet(args.output_dir, args.questions)
    print(f"PDF: {pdf_path}")
    print(f"Layout: {json_path}")


if __name__ == "__main__":
    main()
