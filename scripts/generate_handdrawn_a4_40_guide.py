#!/usr/bin/env python3
"""Generate the MARKA hand-drawn A4/40 construction guide and review image."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json"
PLUM = HexColor("#5A244C")
PALE_PLUM = HexColor("#F3EAF0")
MUTED = HexColor("#68636B")
PENCIL = Color(0.32, 0.30, 0.34)


def _title(c: canvas.Canvas, heading: str, subheading: str) -> None:
    width, height = A4
    c.setFillColor(PLUM)
    c.rect(0, height - 34 * mm, width, 34 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 19)
    c.drawString(16 * mm, height - 18 * mm, heading)
    c.setFont("Helvetica", 9)
    c.drawString(16 * mm, height - 26 * mm, subheading)


def _step(c: canvas.Canvas, number: int, y_mm: float, title: str, detail: str) -> None:
    c.setFillColor(PALE_PLUM)
    c.roundRect(16 * mm, y_mm * mm, 178 * mm, 43 * mm, 4 * mm, stroke=0, fill=1)
    c.setFillColor(PLUM)
    c.circle(31 * mm, (y_mm + 21.5) * mm, 9 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(31 * mm, (y_mm + 18.6) * mm, str(number))
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(47 * mm, (y_mm + 27) * mm, title)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(47 * mm, (y_mm + 16) * mm, detail)


def _draw_anchor(c: canvas.Canvas, left_mm: float, top_mm: float, crossed: bool) -> None:
    page_height_mm = A4[1] / mm
    bottom_mm = page_height_mm - top_mm - 10
    c.setStrokeColor(black)
    c.setLineWidth(1.3)
    c.rect(left_mm * mm, bottom_mm * mm, 10 * mm, 10 * mm, stroke=1, fill=0)
    if crossed:
        inset = 1.8
        c.line((left_mm + inset) * mm, (bottom_mm + inset) * mm,
               (left_mm + 10 - inset) * mm, (bottom_mm + 10 - inset) * mm)
        c.line((left_mm + inset) * mm, (bottom_mm + 10 - inset) * mm,
               (left_mm + 10 - inset) * mm, (bottom_mm + inset) * mm)


def _draw_grid(c: canvas.Canvas, grid: dict, start_question: int, sample: bool) -> None:
    page_height_mm = A4[1] / mm
    left, top, right, bottom = grid["bounds_mm"]
    y_bottom = page_height_mm - bottom
    c.setStrokeColor(black)
    c.setLineWidth(0.65)
    for column in range(7):
        x = left + column * 10
        c.line(x * mm, y_bottom * mm, x * mm, (page_height_mm - top) * mm)
    for row in range(21):
        y = y_bottom + row * 10
        c.line(left * mm, y * mm, right * mm, y * mm)

    c.setFont("Helvetica-Bold", 8)
    for index, option in enumerate("ABCDE"):
        c.drawCentredString((left + 15 + index * 10) * mm,
                            (page_height_mm - top + 3) * mm, option)
    c.setFont("Helvetica-Bold", 6.5)
    for row in range(20):
        question = start_question + row
        centre_y = page_height_mm - top - row * 10 - 6.3
        c.drawCentredString((left + 5) * mm, centre_y * mm, str(question))

    if not sample:
        return
    examples = {start_question + 2: (2, "x"), start_question + 7: (0, "tick")}
    c.setStrokeColor(PENCIL)
    c.setLineWidth(1.5)
    for question, (choice, mark) in examples.items():
        row = question - start_question
        cx = left + 15 + choice * 10
        cy = page_height_mm - top - row * 10 - 5
        if mark == "x":
            c.line((cx - 2.6) * mm, (cy - 2.6) * mm, (cx + 2.6) * mm, (cy + 2.6) * mm)
            c.line((cx - 2.6) * mm, (cy + 2.6) * mm, (cx + 2.6) * mm, (cy - 2.6) * mm)
        else:
            c.line((cx - 2.8) * mm, cy * mm, (cx - 0.8) * mm, (cy - 2.4) * mm)
            c.line((cx - 0.8) * mm, (cy - 2.4) * mm, (cx + 3) * mm, (cy + 2.7) * mm)


def _draw_sample(c: canvas.Canvas, profile: dict) -> None:
    width, height = A4
    c.setFillColor(white)
    c.rect(0, 0, width, height, stroke=0, fill=1)
    for anchor in profile["anchors"]:
        left, top, _, _ = anchor["bounds_mm"]
        _draw_anchor(c, left, top, anchor["orientation_x"])

    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, height - 16 * mm, "MARKA HAND-DRAWN 40")
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(width / 2, height - 23 * mm,
                       "NAME __________  STUDENT ID ______  CLASS _____  SUBJECT ______  DATE ______")
    _draw_grid(c, profile["grids"][0], 1, sample=True)
    _draw_grid(c, profile["grids"][1], 21, sample=True)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawCentredString(width / 2, 28 * mm,
                       "Draw the frame in permanent pen. Mark one answer in pencil with a clear X or tick.")


def generate_guide(profile_path: Path, output_dir: Path) -> dict[str, Path]:
    profile = json.loads(Path(profile_path).read_text())
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "marka_handdrawn_a4_40_guide.pdf"
    png_path = output_dir / "marka_handdrawn_a4_40_guide.png"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.setTitle("MARKA Hand-drawn A4 40 Construction Guide")
    _title(c, "Draw it once. Use it again.", "One ruler. One measurement. Every box is 1 cm.")
    _step(c, 1, 207, "Draw four corner squares", "Each square is 1 cm. Put an X only in the top-left square.")
    _step(c, 2, 155, "Draw two tall rectangles", "Each rectangle is 6 boxes wide and 20 boxes tall.")
    _step(c, 3, 103, "Mark every centimetre", "Join the ruler marks to make the rows and A–E columns.")
    _step(c, 4, 51, "Label and answer", "Write 1–40 and A–E. Put one clear X or tick inside a box.")
    c.setFillColor(PLUM)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(A4[0] / 2, 29 * mm, "3 cm + 6 cm + 3 cm + 6 cm + 3 cm = the full A4 width")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawCentredString(A4[0] / 2, 20 * mm, "Use permanent pen for the guide. Use HB/2B pencil for answers.")
    c.showPage()
    _draw_sample(c, profile)
    c.save()

    subprocess.run(
        [
            "pdftoppm", "-png", "-f", "1", "-singlefile", "-r", "144",
            str(pdf_path), str(png_path.with_suffix("")),
        ],
        check=True,
        capture_output=True,
    )
    return {"pdf": pdf_path, "png": png_path}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/v2_prototype"))
    args = parser.parse_args()
    outputs = generate_guide(args.profile, args.output_dir)
    print(f"PDF: {outputs['pdf']}")
    print(f"PNG: {outputs['png']}")


if __name__ == "__main__":
    main()
