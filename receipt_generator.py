"""
MARKA Assessment Receipt Generator
Fixed layout: A4 Portrait, exactly 10 slips per page (2 columns x 5 rows).
Premium "Certificate" Aesthetics:
- Beautiful double-line frame around every slip.
- Proud 12x12mm dedicated space for the school logo.
- Fixed 10-column corrections grid (no dynamic font bias).
- High contrast, ink-efficient.
"""

import math
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import black, HexColor
from reportlab.pdfgen import canvas as pdf_canvas


# ── Page Geometry (Fixed 10 per page) ─────────────────────────────
PAGE_W, PAGE_H = A4
COLS = 2
ROWS = 5
SLIP_W = PAGE_W / COLS          # 105.0 mm
SLIP_H = PAGE_H / ROWS          # 59.4 mm

# ── Colors ────────────────────────────────────────────────────────
INK        = black
DARK_GREY  = HexColor("#333333")
CUT_LINE   = HexColor("#888888")


# ── Cut Guides ───────────────────────────────────────────────────
def _draw_cut_guides(c):
    """Draw perforated cut lines with scissors."""
    c.saveState()
    c.setStrokeColor(CUT_LINE)
    c.setLineWidth(0.6)
    
    c.setFont("Helvetica", 8)
    c.setFillColor(CUT_LINE)

    # Horizontal cut lines
    for r in range(1, ROWS):
        y = r * SLIP_H
        c.setDash(4, 4)
        c.line(0, y, PAGE_W, y)
        c.drawCentredString(PAGE_W * 0.25, y - 1.5 * mm, "✂")
        c.drawCentredString(PAGE_W * 0.75, y - 1.5 * mm, "✂")
        c.drawCentredString(PAGE_W * 0.50, y - 1.5 * mm, "✂")

    # Vertical cut line
    c.setDash(4, 4)
    c.line(SLIP_W, 0, SLIP_W, PAGE_H)
    c.drawCentredString(SLIP_W, PAGE_H * 0.5, "✂")

    c.restoreState()


# ── Slip Renderer ────────────────────────────────────────────────
def _draw_slip(c, ox, oy, d):
    c.saveState()
    
    # ════════════════════════════════════════════════════════════
    # THE PREMIUM FRAME
    # ════════════════════════════════════════════════════════════
    # A beautiful double-line frame inset from the cut edge
    pad = 3.5 * mm
    fx = ox + pad
    fy = oy + pad
    fw = SLIP_W - 2 * pad
    fh = SLIP_H - 2 * pad
    
    c.setStrokeColor(INK)
    # Outer thick border
    c.setLineWidth(1.2)
    c.rect(fx, fy, fw, fh, fill=0, stroke=1)
    # Inner thin border
    c.setLineWidth(0.3)
    c.rect(fx + 0.8*mm, fy + 0.8*mm, fw - 1.6*mm, fh - 1.6*mm, fill=0, stroke=1)
    
    # Internal layout bounds
    ix = fx + 2.5*mm
    iy = fy + 2.5*mm
    iw = fw - 5*mm
    ih = fh - 5*mm
    irx = ix + iw
    top = iy + ih
    
    y = top

    # ════════════════════════════════════════════════════════════
    # HEADER & STUDENT INFO (Stacked beside Logo to save space)
    # ════════════════════════════════════════════════════════════
    
    # Proud Logo Space (12x12mm)
    logo_size = 12 * mm
    c.setStrokeColor(DARK_GREY)
    c.setLineWidth(0.5)
    c.setDash(1, 1)
    c.rect(ix, y - logo_size, logo_size, logo_size)
    c.setDash()
    
    c.setFillColor(DARK_GREY)
    c.setFont("Helvetica", 4)
    c.drawCentredString(ix + logo_size/2, y - logo_size/2 - 1*mm, "[LOGO]")
    
    text_x = ix + logo_size + 2.5 * mm
    
    # Line 1: School Name
    school_name = str(d.get("school_name", "MARKA ACADEMY")).upper()
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(text_x, y - 2.5*mm, school_name)
    
    # Line 2: Subtitle & ID
    c.setFont("Helvetica-Bold", 4.5)
    c.setFillColor(DARK_GREY)
    c.drawString(text_x, y - 5*mm, "OFFICIAL ASSESSMENT RECORD")
    if d.get("receipt_id"):
        c.setFont("Helvetica", 4.5)
        c.drawString(text_x + 32*mm, y - 5*mm, f"ID: {d['receipt_id']}")
        
    # Line 3 & 4: Student Details (Handwriting Crops or Text)
    fields_b64 = d.get("fields_b64", {})
    
    if "name" in fields_b64:
        import base64
        import io
        from reportlab.lib.utils import ImageReader
        
        # Name
        img_data = base64.b64decode(fields_b64["name"].split(",")[1])
        # scale down slightly to fit gracefully (max 40mm wide)
        c.drawImage(ImageReader(io.BytesIO(img_data)), text_x, y - 9*mm, width=40*mm, height=2.8*mm, preserveAspectRatio=True)
        
        # Class / Subject
        meta_x = text_x
        if "class" in fields_b64:
            cls_data = base64.b64decode(fields_b64["class"].split(",")[1])
            c.drawImage(ImageReader(io.BytesIO(cls_data)), meta_x, y - 12.5*mm, width=15*mm, height=2.8*mm, preserveAspectRatio=True)
            meta_x += 16 * mm
        if "subject" in fields_b64:
            sub_data = base64.b64decode(fields_b64["subject"].split(",")[1])
            c.drawImage(ImageReader(io.BytesIO(sub_data)), meta_x, y - 12.5*mm, width=25*mm, height=2.8*mm, preserveAspectRatio=True)
    else:
        # Fallback to Text
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 9)
        name = str(d.get("student_name", "—")).strip()
        if len(name) > 28: name = name[:26] + "…"
        c.drawString(text_x, y - 9*mm, name)
        
        c.setFillColor(DARK_GREY)
        c.setFont("Helvetica", 6)
        meta = []
        if d.get("class_name"): meta.append(d["class_name"])
        if d.get("subject"): meta.append(d["subject"])
        c.drawString(text_x, y - 11.5*mm, "  |  ".join(meta))

    # -- Right Side: Double-Bordered Score Box
    score = d.get("score", 0)
    total = d.get("total", 0)
    
    box_w = 20 * mm
    box_h = 10 * mm
    box_x = irx - box_w
    box_y = y - box_h - 1*mm
    
    c.setStrokeColor(INK)
    c.setLineWidth(0.8)
    c.rect(box_x, box_y, box_w, box_h, fill=0, stroke=1)
    c.setLineWidth(0.3)
    c.rect(box_x + 0.6*mm, box_y + 0.6*mm, box_w - 1.2*mm, box_h - 1.2*mm)
    
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 4.5)
    c.drawCentredString(box_x + box_w/2, box_y + box_h - 2.5*mm, "FINAL SCORE")
    
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(box_x + box_w/2, box_y + 2*mm, f"{score}/{total}")

    # Elegant divider line below the entire header block
    y -= logo_size + 2 * mm
    c.setStrokeColor(INK)
    c.setLineWidth(0.4)
    c.line(ix, y, irx, y)
    y -= 3 * mm

    # ════════════════════════════════════════════════════════════
    # CORRECTIONS (Dynamic Scaling for Max Visibility)
    # ════════════════════════════════════════════════════════════
    
    missed = d.get("missed", {})
    miss_count = len(missed)
    
    if miss_count == 0:
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(INK)
        c.drawCentredString(ix + iw/2, y - 8*mm, "PERFECT SCORE — EXCELLENT WORK!")
    else:
        c.setFont("Helvetica-Bold", 5.5)
        c.setFillColor(INK)
        c.drawString(ix, y, f"CORRECTIONS REQUIRED: {miss_count}")
        y -= 3.5 * mm

        sorted_missed = sorted(missed.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)
        
        # UNIVERSAL FIXED STYLING (NO PREJUDICE)
        # To avoid bias, every single student gets the exact same font size and column structure.
        # We lock the font to 6.5pt and 10 columns. 
        # This is the mathematical maximum size that can fit 100 questions while retaining 
        # the strict 10-receipt-per-page geometry.
        cols = 10
        fs = 6.5
        row_h = 2.6 * mm
        col_w = iw / cols
        
        for idx, (qn, ans) in enumerate(sorted_missed):
            col = idx % cols
            row = idx // cols
            
            ex = ix + col * col_w
            ey = y - row * row_h
            
            c.setFont("Helvetica", fs)
            c.setFillColor(DARK_GREY)
            c.drawString(ex, ey, str(qn))
            
            qn_w = c.stringWidth(str(qn), "Helvetica", fs)
            c.drawString(ex + qn_w + 0.3*mm, ey, ".")
            
            c.setFont("Helvetica-Bold", fs)
            c.setFillColor(INK)
            c.drawString(ex + qn_w + 1.5*mm, ey, ans)

    # ════════════════════════════════════════════════════════════
    # FOOTER
    # ════════════════════════════════════════════════════════════
    fy = iy + 1*mm
    
    c.setFont("Helvetica-Bold", 5)
    c.setFillColor(INK)
    c.drawString(ix, fy, "Teacher Signature:")
    
    c.setStrokeColor(INK)
    c.setLineWidth(0.3)
    c.line(ix + 18*mm, fy, ix + 45*mm, fy)
    
    c.setFont("Helvetica", 4)
    c.setFillColor(CUT_LINE)
    c.drawRightString(irx, fy, "marka.com.ng")

    c.restoreState()


# ── Public API ───────────────────────────────────────────────────

def generate_receipts_pdf(results_list, output_path="receipts.pdf"):
    if not results_list:
        return None
        
    c = pdf_canvas.Canvas(output_path, pagesize=A4)
    c.setTitle("MARKA Assessment Receipts")
    
    per_page = COLS * ROWS
    pages = max(1, math.ceil(len(results_list) / per_page))

    for pi in range(pages):
        if pi > 0:
            c.showPage()
            
        _draw_cut_guides(c)

        for i, data in enumerate(results_list[pi * per_page:(pi + 1) * per_page]):
            col = i % COLS
            row = i // COLS
            
            ox = col * SLIP_W
            oy = (ROWS - 1 - row) * SLIP_H
            
            _draw_slip(c, ox, oy, data)

    c.save()
    
    return {
        "output_path": output_path,
        "total_receipts": len(results_list),
        "total_pages": pages,
        "slips_per_page": per_page
    }


if __name__ == "__main__":
    import argparse
    import random
    
    p = argparse.ArgumentParser(description="MARKA Premium Framed Receipts")
    p.add_argument("--students", type=int, default=10)
    p.add_argument("--questions", type=int, default=100)
    p.add_argument("--miss_limit", type=int, default=0)
    p.add_argument("--output", default="assessment_receipts_premium.pdf")
    a = p.parse_args()
    
    def _demo_data(n, nq, limit):
        firsts = ["Adebayo","Chioma","Emeka","Fatima","Gbenga","Halima",
                  "Ibrahim","Jumoke","Kunle"]
        lasts  = ["Adeyemi","Balogun","Chukwu","Danladi","Eze","Fashola",
                  "Garba","Hassan","Idris"]
        letters = ["A","B","C","D"]

        out = []
        for i in range(n):
            if limit > 0:
                num_missed = limit
            else:
                num_missed = random.randint(0, int(nq * 0.4))
                if random.random() < 0.1: num_missed = random.randint(int(nq*0.6), nq)
                
            missed_keys = random.sample(range(1, nq+1), num_missed)
            missed = {str(q): random.choice(letters) for q in missed_keys}
            
            out.append({
                "school_name": "CORNERSTONE INT. SCHOOL",
                "student_name": f"{random.choice(lasts)} {random.choice(firsts)}",
                "class_name": "SS2A",
                "subject": "Mathematics",
                "score": nq - len(missed),
                "total": nq,
                "missed": missed,
                "receipt_id": f"MK-{i+1:05d}",
            })
        return out
        
    print(f"Generating {a.students} premium framed layout receipts...")
    data = _demo_data(a.students, a.questions, a.miss_limit)
    r = generate_receipts_pdf(data, a.output)
    print(f"✓ {r['output_path']}")
