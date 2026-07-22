import os
import tempfile
from reportlab.lib.pagesizes import A4
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Flowable
from reportlab.lib.units import mm

class TestFlowable(Flowable):
    def wrap(self, availWidth, availHeight):
        self.w, self.h = availWidth, 20*mm
        return self.w, self.h
        
    def draw(self):
        self.canv.rect(0, 0, self.w, self.h)
        print("Transform matrix:", getattr(self.canv, '_currentMatrix', 'No _currentMatrix'))

if __name__ == "__main__":
    pdf_path = os.path.join(tempfile.gettempdir(), "test_flowable.pdf")
    doc = BaseDocTemplate(pdf_path, pagesize=A4)
    frame = Frame(0, 0, A4[0], A4[1])
    doc.addPageTemplates([PageTemplate(id='T', frames=[frame])])
    doc.build([TestFlowable()])
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

