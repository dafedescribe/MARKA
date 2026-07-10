import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Flowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
import qrcode
from reportlab.lib.utils import ImageReader
import io
import json
from src.models import Exam, Question

# A4 is 210 x 297 mm
PAGE_WIDTH, PAGE_HEIGHT = A4

# Margins
MARGIN_TOP = 0.5 * inch
MARGIN_BOTTOM = 0.8 * inch
MARGIN_LEFT = 0.4 * inch
MARGIN_RIGHT = 0.4 * inch

# Fiducials
FIDUCIAL_SIZE = 10 * mm
FIDUCIAL_OFFSET = 5 * mm # from edge

class OptionFlowable(Flowable):
    def __init__(self, q_num: int, opt_letter: str, opt_text: str, style, callback):
        Flowable.__init__(self)
        self.q_num = q_num
        self.opt_letter = opt_letter
        
        # Space between bubble and option text
        self.bubble_radius = 2.5 * mm
        self.left_padding = 9 * mm  # Space allocated for the bubble
        
        # We put the letter in bold
        self.para = Paragraph(f"<b>{opt_letter}</b>  {opt_text}", style)
        self.callback = callback

    def wrap(self, availWidth, availHeight):
        self.w, self.h = self.para.wrap(availWidth - self.left_padding, availHeight)
        # Add 2mm padding below each option
        self.h += 2 * mm
        return availWidth, self.h

    def draw(self):
        # Draw the paragraph shifted to the right
        self.para.drawOn(self.canv, self.left_padding, 2 * mm) # Y-offset for bottom padding
        
        # Calculate bubble center
        # Paragraph is drawn from 2*mm upwards. The first line of text is near the top.
        # Total flowable height is self.h. The top of the paragraph is exactly at self.h.
        # A 10pt font has a baseline ~12pt from the top (4.2mm). 
        # The center of the text is ~3mm from the top.
        bubble_cy = self.h - 3.0 * mm
        bubble_cx = self.bubble_radius + 1 * mm
        
        self.canv.saveState()
        self.canv.setLineWidth(0.5)
        self.canv.setStrokeColorRGB(0, 0, 0)
        self.canv.setFillColorRGB(1, 1, 1)
        self.canv.circle(bubble_cx, bubble_cy, self.bubble_radius, stroke=1, fill=1)
        self.canv.restoreState()
        
        # Calculate absolute position on the page
        matrix = getattr(self.canv, '_currentMatrix', (1,0,0,1,0,0))
        abs_x = bubble_cx + matrix[4]
        abs_y = bubble_cy + matrix[5]
        
        # Fire callback
        self.callback(self.q_num, self.opt_letter, abs_x, abs_y, self.bubble_radius)

class ExamLayoutEngine:
    def __init__(self, exam: Exam, output_dir: str):
        self.exam = exam
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.pdf_path = os.path.join(output_dir, "exam.pdf")
        
        self.styles = getSampleStyleSheet()
        self.setup_styles()
        
        # Metadata storage for bubbles
        self.bubble_metadata = []
        
    def bubble_drawn_callback(self, q_num: int, opt_letter: str, abs_x: float, abs_y: float, radius: float):
        self.bubble_metadata.append({
            "question": q_num,
            "option": opt_letter,
            "center_x_mm": abs_x / mm,
            "center_y_mm": abs_y / mm,
            "radius_mm": radius / mm
        })

    def setup_styles(self):
        # Typography: Arial 10pt (We'll use Helvetica as it's the standard PDF sans-serif similar to Arial, unless custom TTF is loaded)
        self.styles.add(ParagraphStyle(
            name='Header',
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=14,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='CandidateSection',
            fontName='Helvetica',
            fontSize=10,
            leading=16
        ))
        
        self.styles.add(ParagraphStyle(
            name='QuestionText',
            fontName='Helvetica',
            fontSize=10,
            leading=12,
            spaceAfter=3
        ))
        
        self.styles.add(ParagraphStyle(
            name='OptionText',
            fontName='Helvetica',
            fontSize=10,
            leading=12
        ))

    def generate(self):
        doc = BaseDocTemplate(
            self.pdf_path,
            pagesize=A4,
            leftMargin=MARGIN_LEFT,
            rightMargin=MARGIN_RIGHT,
            topMargin=MARGIN_TOP,
            bottomMargin=MARGIN_BOTTOM
        )
        
        # Calculate Frame dimensions
        # Top reserved space for candidate info and headers: 45mm
        top_reserved = 45 * mm
        
        frame_top = PAGE_HEIGHT - MARGIN_TOP - top_reserved
        frame_height = frame_top - MARGIN_BOTTOM
        
        usable_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
        gutter = 5 * mm
        frame_width = (usable_width - (2 * gutter)) / 3.0
        
        # Create 3 Frames
        frame1 = Frame(MARGIN_LEFT, MARGIN_BOTTOM, frame_width, frame_height, id='col1', showBoundary=0)
        frame2 = Frame(MARGIN_LEFT + frame_width + gutter, MARGIN_BOTTOM, frame_width, frame_height, id='col2', showBoundary=0)
        frame3 = Frame(MARGIN_LEFT + 2*(frame_width + gutter), MARGIN_BOTTOM, frame_width, frame_height, id='col3', showBoundary=0)
        
        page_template = PageTemplate(
            id='ThreeCol',
            frames=[frame1, frame2, frame3],
            onPage=self.on_page_decorations
        )
        
        doc.addPageTemplates([page_template])
        
        # Generate flowables for questions
        flowables = []
        for q in self.exam.questions:
            q_flowables = []
            
            # Question text
            q_para = Paragraph(f"<b>{q.number}.</b> {q.text.replace(chr(10), '<br/>')}", self.styles['QuestionText'])
            q_flowables.append(q_para)
            q_flowables.append(Spacer(1, 1*mm))
            
            # Options
            for opt_letter, opt_text in q.options.items():
                opt_flowable = OptionFlowable(
                    q.number,
                    opt_letter,
                    opt_text.replace(chr(10), '<br/>'),
                    self.styles['OptionText'],
                    self.bubble_drawn_callback
                )
                q_flowables.append(opt_flowable)
                
            q_flowables.append(Spacer(1, 3*mm)) # 3pt after each question as per PRD (we use 3mm for now for good measure)
            
            # Use KeepTogether to ensure the question is never split across columns
            flowables.append(KeepTogether(q_flowables))
            
        doc.build(flowables)
        
        # Write metadata JSON
        self.export_metadata()

    def export_metadata(self):
        # Build comprehensive metadata structure
        exam_id = f"{self.exam.metadata.subject.replace(' ', '_')}_{self.exam.metadata.course_class}_{self.exam.metadata.term.replace(' ', '_')}".upper()
        
        # Answers mapping
        answers = {str(q.number): q.correct_answer for q in self.exam.questions}
        
        metadata = {
            "exam_id": exam_id,
            "title": self.exam.metadata.title,
            "subject": self.exam.metadata.subject,
            "class": self.exam.metadata.course_class,
            "term": self.exam.metadata.term,
            "fiducials": {
                "size_mm": FIDUCIAL_SIZE / mm,
                "offset_mm": FIDUCIAL_OFFSET / mm,
                "positions": ["bottom_left", "bottom_right", "top_left", "top_right"]
            },
            "qr_code": {
                "size_mm": 25,
                "position": "top_right"
            },
            "answers": answers,
            "bubbles": self.bubble_metadata
        }
        with open(os.path.join(self.output_dir, "exam.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        
    def on_page_decorations(self, canvas, doc):
        canvas.saveState()
        
        # 1. Draw Fiducials
        canvas.setFillColorRGB(0, 0, 0) # Solid black
        
        # Bottom-Left
        canvas.rect(FIDUCIAL_OFFSET, FIDUCIAL_OFFSET, FIDUCIAL_SIZE, FIDUCIAL_SIZE, fill=1, stroke=0)
        # Bottom-Right
        canvas.rect(PAGE_WIDTH - FIDUCIAL_OFFSET - FIDUCIAL_SIZE, FIDUCIAL_OFFSET, FIDUCIAL_SIZE, FIDUCIAL_SIZE, fill=1, stroke=0)
        # Top-Left
        canvas.rect(FIDUCIAL_OFFSET, PAGE_HEIGHT - FIDUCIAL_OFFSET - FIDUCIAL_SIZE, FIDUCIAL_SIZE, FIDUCIAL_SIZE, fill=1, stroke=0)
        # Top-Right
        canvas.rect(PAGE_WIDTH - FIDUCIAL_OFFSET - FIDUCIAL_SIZE, PAGE_HEIGHT - FIDUCIAL_OFFSET - FIDUCIAL_SIZE, FIDUCIAL_SIZE, FIDUCIAL_SIZE, fill=1, stroke=0)
        
        # 2. Draw Candidate Section & Headers at the top of the page (in the reserved space)
        # We use absolute coordinates
        y = PAGE_HEIGHT - MARGIN_TOP
        
        # Candidate fields
        canvas.setFont("Helvetica", 10)
        candidate_x = MARGIN_LEFT + 15 * mm # Shifted right to avoid fiducial
        canvas.drawString(candidate_x, y - 10, "Name ______________________________________")
        canvas.drawString(candidate_x, y - 25, "Admission No ______________________________")
        canvas.drawString(candidate_x, y - 40, "Class _____________________________________")
        
        # Headers (Centered)
        canvas.setFont("Helvetica-Bold", 12)
        # Title
        title_y = y - 5
        canvas.drawCentredString(PAGE_WIDTH/2.0, title_y, "ABC COLLEGE")
        canvas.drawCentredString(PAGE_WIDTH/2.0, title_y - 15, f"{self.exam.metadata.course_class} {self.exam.metadata.subject}".upper())
        canvas.drawCentredString(PAGE_WIDTH/2.0, title_y - 30, self.exam.metadata.term.upper())
        
        # 3. Footer
        canvas.setFont("Helvetica", 9)
        canvas.drawString(MARGIN_LEFT, MARGIN_BOTTOM - 5, "Print at 100%. Do not fit to page.")
        canvas.drawRightString(PAGE_WIDTH - MARGIN_RIGHT, MARGIN_BOTTOM - 5, f"Page {doc.page}")

        # 4. QR Code
        exam_id = f"{self.exam.metadata.subject.replace(' ', '_')}_{self.exam.metadata.course_class}_{self.exam.metadata.term.replace(' ', '_')}".upper()
        qr_data = f"EXAM:{exam_id}|V:1.0|P:{doc.page}"
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO to pass to ReportLab
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        
        qr_size = 25 * mm
        qr_x = PAGE_WIDTH - MARGIN_RIGHT - qr_size - 10 * mm
        qr_y = PAGE_HEIGHT - MARGIN_TOP - qr_size - 10 * mm
        
        canvas.drawImage(ImageReader(img_buffer), qr_x, qr_y, width=qr_size, height=qr_size)

        # 5. Column Dividers
        usable_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
        gutter = 5 * mm
        frame_width = (usable_width - (2 * gutter)) / 3.0
        
        canvas.setLineWidth(0.5)
        canvas.setStrokeColorRGB(0.8, 0.8, 0.8) # Light grey line
        
        col_top = PAGE_HEIGHT - MARGIN_TOP - 45 * mm
        col_bottom = MARGIN_BOTTOM
        
        line1_x = MARGIN_LEFT + frame_width + gutter / 2.0
        line2_x = MARGIN_LEFT + 2 * frame_width + 1.5 * gutter
        
        canvas.line(line1_x, col_bottom, line1_x, col_top)
        canvas.line(line2_x, col_bottom, line2_x, col_top)

        canvas.restoreState()
