"""
MARKA OMR Generator — Universal Answer Sheet
Premium layout: 2 sheets per A4 portrait, 100Q × 5 choices.
Designed to survive cheap printers, photocopies, bad cameras, and folded paper.
"""

import os
import json
import argparse
import qrcode
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import black, white, HexColor
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader

# ── Page ──────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4  # 210mm x 297mm portrait

SHEETS_PER_PAGE = 2
PAGE_MARGIN = 4 * mm
SHEET_GAP = 5 * mm

SHEET_W = PAGE_W - 2 * PAGE_MARGIN
SHEET_H = (PAGE_H - 2 * PAGE_MARGIN - SHEET_GAP) / 2

# ── Fiducials ─────────────────────────────────────────────────────

FID_SIZE = 5 * mm
FID_INSET = 2.5 * mm

# ── Layout zones ──────────────────────────────────────────────────

HEADER_H = 19 * mm     # header band: school branding + compact fields
FOOTER_H = 10 * mm     # instructions zone

# ── Bubbles ───────────────────────────────────────────────────────

BUBBLE_RADIUS = 2 * mm      # 4mm diameter
BUBBLE_SPACING_X = 5.5 * mm
BUBBLE_SPACING_Y = 5.2 * mm # generous vertical spacing
NUM_LABEL_W = 7 * mm
LABEL_GAP = 1.5 * mm
COL_GUTTER = 6 * mm         # wide gutter between columns
BUBBLE_LINE_W = 0.65

# ── QR ────────────────────────────────────────────────────────────

QR_SIZE = 9 * mm

# ── Colors ────────────────────────────────────────────────────────

BORDER_COLOR   = HexColor("#1a1a1a")
BUBBLE_STROKE  = HexColor("#2a2a2a")
LABEL_COLOR    = HexColor("#333333")
MUTED_COLOR    = HexColor("#999999")
DIVIDER_COLOR  = HexColor("#CCCCCC")
BAND_COLOR     = HexColor("#F5F5F5")   # subtle row shading (scanner-safe with adaptive threshold)
HEADER_BG      = HexColor("#F0F0F0")   # header band background
COL_HEADER_BG  = HexColor("#E8E8E8")   # column header bar (A B C D E)
GROUP_LINE     = HexColor("#BBBBBB")   # every-5-questions separator


class OMRGenerator:
    def __init__(self, num_questions=100, num_choices=5):
        self.num_questions = num_questions
        self.num_choices = num_choices

        (self.num_cols, self.rows_per_col,
         self.spacing_x, self.spacing_y,
         self.col_w) = self._compute_layout()

        self.sheet_layouts = []

    def _compute_layout(self):
        """Compute optimal column × row layout for available space."""
        safe_x = FID_INSET + FID_SIZE + 2.5 * mm
        avail_w = SHEET_W - 2 * safe_x
        
        # Total height minus top/bottom fiducials, header, footer, column headers (4mm), and gaps
        # Leave an extra 5mm so the bottom bubbles don't touch the footer line.
        avail_h = SHEET_H - (2 * FID_INSET) - (2 * FID_SIZE) - HEADER_H - FOOTER_H - 13 * mm

        base_col_w = NUM_LABEL_W + LABEL_GAP + (self.num_choices - 1) * BUBBLE_SPACING_X
        max_cols = max(1, int((avail_w + COL_GUTTER) // (base_col_w + COL_GUTTER)))
        max_rows = max(1, int(avail_h // BUBBLE_SPACING_Y))

        min_cols = -(-self.num_questions // max_rows)
        num_cols = min(max(min_cols, 1), max_cols)
        rows_per_col = -(-self.num_questions // num_cols)

        sp_x = BUBBLE_SPACING_X
        sp_y = BUBBLE_SPACING_Y
        col_w = base_col_w

        if rows_per_col > max_rows:
            sp_y = max(avail_h / rows_per_col, 3.5 * mm)

        total_w = num_cols * col_w + (num_cols - 1) * COL_GUTTER
        if total_w > avail_w:
            scale = avail_w / total_w
            sp_x *= scale
            col_w = NUM_LABEL_W + LABEL_GAP + (self.num_choices - 1) * sp_x

        return num_cols, rows_per_col, sp_x, sp_y, col_w

    def generate(self, output_dir, num_pages=1):
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, "omr_sheets.pdf")
        json_path = os.path.join(output_dir, "omr_layout.json")

        c = pdf_canvas.Canvas(pdf_path, pagesize=A4)
        sheet_counter = 0

        for page_num in range(num_pages):
            if page_num > 0:
                c.showPage()
            self._draw_crop_line(c)

            for slot in range(SHEETS_PER_PAGE):
                sheet_counter += 1
                sx = PAGE_MARGIN
                sy = PAGE_MARGIN + (1 - slot) * (SHEET_H + SHEET_GAP)
                sheet_id = f"{sheet_counter:04d}"
                self._draw_sheet(c, sx, sy, sheet_id, page_num + 1)

        c.save()
        self._export_layout(json_path)
        print(f"✓ PDF → {pdf_path}")
        print(f"✓ Layout → {json_path}")
        print(f"✓ {sheet_counter} sheets ({num_pages} page{'s' if num_pages > 1 else ''})")
        print(f"  {self.num_questions}Q × {self.num_choices} choices "
              f"| {self.num_cols} cols × {self.rows_per_col} rows "
              f"| {BUBBLE_RADIUS*2/mm:.0f}mm bubbles")

    # ──────────────────────────────────────────────────────────────

    def _draw_sheet(self, c, sx, sy, sheet_id, page_num):
        bubbles = []
        c.saveState()

        # ── Border — clean, bold single line ──
        c.setStrokeColor(BORDER_COLOR)
        c.setLineWidth(1.2)
        c.rect(sx, sy, SHEET_W, SHEET_H, stroke=1, fill=0)

        # ── 4 Fiducials with white moat ──
        # The "moat" is just generous inset so ink bleed never reaches content
        fx1 = sx + FID_INSET
        fy1 = sy + FID_INSET
        fx2 = sx + SHEET_W - FID_INSET - FID_SIZE
        fy2 = sy + SHEET_H - FID_INSET - FID_SIZE

        c.setFillColor(black)
        for x, y in [(fx1, fy1), (fx2, fy1), (fx1, fy2), (fx2, fy2)]:
            c.rect(x, y, FID_SIZE, FID_SIZE, fill=1, stroke=0)

        fid_centers = {
            "top_left":     [round((fx1 - sx + FID_SIZE/2) / mm, 2), round((fy2 - sy + FID_SIZE/2) / mm, 2)],
            "top_right":    [round((fx2 - sx + FID_SIZE/2) / mm, 2), round((fy2 - sy + FID_SIZE/2) / mm, 2)],
            "bottom_left":  [round((fx1 - sx + FID_SIZE/2) / mm, 2), round((fy1 - sy + FID_SIZE/2) / mm, 2)],
            "bottom_right": [round((fx2 - sx + FID_SIZE/2) / mm, 2), round((fy1 - sy + FID_SIZE/2) / mm, 2)],
        }

        safe_left  = fx1 + FID_SIZE + 3 * mm
        safe_right = fx2 - 2 * mm

        # ── Header band ──
        header_top = sy + SHEET_H - FID_INSET - FID_SIZE - 1 * mm
        header_bot = header_top - HEADER_H

        # Header background
        c.setFillColor(HEADER_BG)
        c.rect(sx + 1 * mm, header_bot, SHEET_W - 2 * mm, HEADER_H, fill=1, stroke=0)

        # Bottom border of header
        c.setStrokeColor(BORDER_COLOR)
        c.setLineWidth(0.6)
        c.line(sx + 1 * mm, header_bot, sx + SHEET_W - 1 * mm, header_bot)

        # ══════════════════════════════════════════════════════════
        # ROW 1: School Branding (Logo + Name + Contact Info)
        # ══════════════════════════════════════════════════════════
        
        # School logo placeholder (square, dashed border)
        logo_size = 13 * mm
        logo_x = safe_left
        logo_y = header_top - logo_size - 1 * mm
        c.setStrokeColor(MUTED_COLOR)
        c.setLineWidth(0.4)
        c.setDash(1.5, 1.5)
        c.rect(logo_x, logo_y, logo_size, logo_size, fill=0, stroke=1)
        c.setDash()
        c.setFont("Helvetica", 4)
        c.setFillColor(MUTED_COLOR)
        c.drawCentredString(logo_x + logo_size / 2, logo_y + logo_size / 2 - 1 * mm, "SCHOOL")
        c.drawCentredString(logo_x + logo_size / 2, logo_y + logo_size / 2 - 4 * mm, "LOGO")

        # School name (large, bold)
        text_x = logo_x + logo_size + 4 * mm
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(LABEL_COLOR)
        c.drawString(text_x, header_top - 5 * mm, "SCHOOL NAME")

        # Contact info line (address, phone)
        c.setFont("Helvetica", 6)
        c.setFillColor(MUTED_COLOR)
        c.drawString(text_x, header_top - 9 * mm, "Address / Contact Info")

        # ── QR — inside header right edge ──
        qr_data = f"MARKA|{sheet_id}|Q{self.num_questions}|C{self.num_choices}"
        qr = qrcode.QRCode(version=1, box_size=8, border=1)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        qr_x = safe_right - QR_SIZE
        qr_y = header_top - QR_SIZE - 1 * mm
        c.drawImage(ImageReader(buf), qr_x, qr_y, width=QR_SIZE, height=QR_SIZE)

        # ══════════════════════════════════════════════════════════
        # ROW 2: Student Input Fields (compact bounded boxes in ONE ROW)
        # ══════════════════════════════════════════════════════════
        box_h = 3.5 * mm
        row2_y = header_bot + 1 * mm
        
        # Define fields and their explicit box widths to fit on one line
        fields_def = [
            ("Name:", 50 * mm, "name"),
            ("ID No:", 22 * mm, "id"),
            ("Class:", 18 * mm, "class"),
            ("Subject:", 30 * mm, "subject"),
            ("Date:", 22 * mm, "date"),
        ]
        
        # Calculate spacing
        from reportlab.pdfbase.pdfmetrics import stringWidth
        total_content_w = 0
        for label, bw, _ in fields_def:
            total_content_w += stringWidth(label, "Helvetica", 5) + 1 * mm + bw
            
        avail_w = safe_right - safe_left
        gap = (avail_w - total_content_w) / (len(fields_def) - 1)
        
        fx = safe_left
        for label, bw, key in fields_def:
            c.setFillColor(black)
            c.setFont("Helvetica", 5)
            c.drawString(fx, row2_y + 0.5 * mm, label)
            
            lbl_w = stringWidth(label, "Helvetica", 5) + 1 * mm
            box_x = fx + lbl_w
            
            c.setStrokeColor(LABEL_COLOR)
            c.setLineWidth(0.4)
            c.rect(box_x, row2_y - 0.5 * mm, bw, box_h, fill=0, stroke=1)
            
            fx += lbl_w + bw + gap

        # ── Bubble Grid ──
        grid_top = header_bot - 2.5 * mm

        # Center grid horizontally
        total_grid_w = self.num_cols * self.col_w + (self.num_cols - 1) * COL_GUTTER
        grid_left = sx + (SHEET_W - total_grid_w) / 2

        choice_letters = [chr(65 + i) for i in range(self.num_choices)]

        # Column header bar height
        col_header_h = 4 * mm
        col_header_top = grid_top - 0.5 * mm

        for col_idx in range(self.num_cols):
            col_x = grid_left + col_idx * (self.col_w + COL_GUTTER)

            # ── Column header bar (dark strip with letters) ──
            bar_x = col_x + NUM_LABEL_W + LABEL_GAP - 2 * mm
            bar_w = (self.num_choices - 1) * self.spacing_x + 4 * mm
            c.setFillColor(COL_HEADER_BG)
            c.rect(bar_x, col_header_top - col_header_h, bar_w, col_header_h, fill=1, stroke=0)

            c.setFont("Helvetica-Bold", 5.5)
            c.setFillColor(LABEL_COLOR)
            for ci, letter in enumerate(choice_letters):
                lx = col_x + NUM_LABEL_W + LABEL_GAP + ci * self.spacing_x
                c.drawCentredString(lx, col_header_top - 3 * mm, letter)

            # ── Column divider ──
            if col_idx < self.num_cols - 1:
                div_x = col_x + self.col_w + COL_GUTTER / 2
                c.setStrokeColor(DIVIDER_COLOR)
                c.setLineWidth(0.3)
                c.line(div_x, col_header_top,
                       div_x, col_header_top - col_header_h - self.rows_per_col * self.spacing_y - 1 * mm)

            # ── Question rows ──
            for row_idx in range(self.rows_per_col):
                q_num = col_idx * self.rows_per_col + row_idx + 1
                if q_num > self.num_questions:
                    break

                row_y = col_header_top - col_header_h - (row_idx + 1) * self.spacing_y

                # Alternating row shading (very light — scanner-safe)
                if row_idx % 2 == 0:
                    band_x = col_x - 1 * mm
                    band_w = self.col_w + 2 * mm
                    # Band from half-spacing above to half-spacing below the row center
                    c.setFillColor(BAND_COLOR)
                    c.rect(band_x, row_y - self.spacing_y / 2,
                           band_w, self.spacing_y, fill=1, stroke=0)

                # Group separator every 5 questions
                if row_idx > 0 and row_idx % 5 == 0:
                    c.setStrokeColor(GROUP_LINE)
                    c.setLineWidth(0.4)
                    sep_y = row_y + self.spacing_y / 2
                    c.line(col_x - 1 * mm, sep_y, col_x + self.col_w + 1 * mm, sep_y)

                # Question number
                c.setFillColor(LABEL_COLOR)
                c.setFont("Helvetica-Bold", 5.5)
                c.drawRightString(col_x + NUM_LABEL_W - 1.5 * mm, row_y - 0.8 * mm, str(q_num))

                # Bubbles
                for ci in range(self.num_choices):
                    bx = col_x + NUM_LABEL_W + LABEL_GAP + ci * self.spacing_x
                    by = row_y

                    c.setStrokeColor(BUBBLE_STROKE)
                    c.setFillColor(white)
                    c.setLineWidth(BUBBLE_LINE_W)
                    c.circle(bx, by, BUBBLE_RADIUS, stroke=1, fill=1)

                    bubbles.append({
                        "question": q_num,
                        "option": choice_letters[ci],
                        "x_mm": round((bx - sx) / mm, 2),
                        "y_mm": round((by - sy) / mm, 2),
                        "radius_mm": round(BUBBLE_RADIUS / mm, 2)
                    })

        # ── Footer zone (Instructions & Branding) ──
        foot_top = fy1 + FID_SIZE + FOOTER_H
        
        # Instruction Box — hard to ignore
        box_w = 130 * mm
        box_h = FOOTER_H - 2 * mm
        box_x = sx + (SHEET_W - box_w) / 2
        box_y = fy1 + FID_SIZE + 1 * mm
        
        c.setFillColor(HexColor("#F2F2F2"))
        c.setStrokeColor(BORDER_COLOR)
        c.setLineWidth(0.8)
        c.rect(box_x, box_y, box_w, box_h, fill=1, stroke=1)

        # Bold top instruction
        c.setFont("Helvetica-Bold", 5.5)
        c.setFillColor(black)
        c.drawCentredString(sx + SHEET_W / 2, box_y + box_h - 3.5 * mm,
            "IMPORTANT: USE A DARK PENCIL OR PEN. FILL BUBBLES COMPLETELY.")

        # Second warning line
        c.setFont("Helvetica-Bold", 4.5)
        c.setFillColor(LABEL_COLOR)
        c.drawCentredString(sx + SHEET_W / 2, box_y + 2.5 * mm,
            "DO NOT FOLD SHEET. KEEP ALL 4 CORNER SQUARES VISIBLE WHEN SCANNING.")

        # Cheeky brand — bottom right
        c.setFont("Helvetica-Bold", 4.5)
        c.setFillColor(MUTED_COLOR)
        c.drawRightString(safe_right, sy + FID_INSET + 0.5 * mm, 
            "Paper Exams. Instant Results. marka.com.ng")

        c.restoreState()

        # Compute handwriting field bounding boxes (mm, relative to sheet origin)
        # These match the exact rect() positions drawn above so the scanner can
        # crop the handwritten text directly — pixel-perfect coordinate lifting.
        _safe_left = FID_INSET + FID_SIZE + 3 * mm
        _safe_right = SHEET_W - FID_INSET - FID_SIZE - 2 * mm
        _header_top = SHEET_H - FID_INSET - FID_SIZE - 1 * mm
        _header_bot = _header_top - HEADER_H
        
        _box_h = 3.5 * mm
        _row2_y = _header_bot + 1 * mm
        
        _fields_def = [
            ("Name:", 50 * mm, "name"),
            ("ID No:", 22 * mm, "id"),
            ("Class:", 18 * mm, "class"),
            ("Subject:", 30 * mm, "subject"),
            ("Date:", 22 * mm, "date"),
        ]
        
        from reportlab.pdfbase.pdfmetrics import stringWidth
        _total_content_w = 0
        for label, bw, _ in _fields_def:
            _total_content_w += stringWidth(label, "Helvetica", 5) + 1 * mm + bw
            
        _avail_w = _safe_right - _safe_left
        _gap = (_avail_w - _total_content_w) / (len(_fields_def) - 1)
        
        _fx = _safe_left
        fields_mm = {}
        
        for label, bw, key in _fields_def:
            lbl_w = stringWidth(label, "Helvetica", 5) + 1 * mm
            box_x = _fx + lbl_w
            
            fields_mm[key] = {
                "x": round(box_x / mm, 2),
                "y": round((_row2_y - 0.5 * mm) / mm, 2),
                "w": round(bw / mm, 2),
                "h": round(_box_h / mm, 2),
            }
            
            _fx += lbl_w + bw + _gap

        self.sheet_layouts.append({
            "sheet_id": sheet_id,
            "page": page_num,
            "origin_on_page_mm": [round(sx / mm, 2), round(sy / mm, 2)],
            "sheet_size_mm": [round(SHEET_W / mm, 2), round(SHEET_H / mm, 2)],
            "fiducial_centers_mm": fid_centers,
            "fiducial_size_mm": round(FID_SIZE / mm, 2),
            "fields_mm": fields_mm,
            "bubbles": bubbles
        })

    # ──────────────────────────────────────────────────────────────

    def _draw_crop_line(self, c):
        c.saveState()
        c.setStrokeColor(MUTED_COLOR)
        c.setLineWidth(0.3)
        c.setDash(3, 3)
        cy = PAGE_MARGIN + SHEET_H + SHEET_GAP / 2
        c.line(PAGE_MARGIN - 2 * mm, cy, PAGE_W - PAGE_MARGIN + 2 * mm, cy)
        c.setFont("Helvetica", 5)
        c.setFillColor(MUTED_COLOR)
        c.drawCentredString(PAGE_W / 2, cy + 1 * mm, "✂")
        c.restoreState()

    def _export_layout(self, json_path):
        layout = {
            "num_questions": self.num_questions,
            "num_choices": self.num_choices,
            "sheets_per_page": SHEETS_PER_PAGE,
            "page_size_mm": [round(PAGE_W / mm, 2), round(PAGE_H / mm, 2)],
            "answers": {},
            "sheets": self.sheet_layouts
        }
        with open(json_path, "w") as f:
            json.dump(layout, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MARKA — Universal Answer Sheet Generator")
    parser.add_argument("--questions", type=int, default=100, help="Questions (default: 100)")
    parser.add_argument("--choices", type=int, default=5, help="Choices per question (default: 5)")
    parser.add_argument("--pages", type=int, default=1, help="A4 pages (2 sheets per page)")
    parser.add_argument("--output", default="omr_output", help="Output directory")
    args = parser.parse_args()

    gen = OMRGenerator(num_questions=args.questions, num_choices=args.choices)
    gen.generate(args.output, num_pages=args.pages)