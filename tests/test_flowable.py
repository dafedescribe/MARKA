import os
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
        
        # Let's try to find coordinate
        # The frame translates the canvas. 
        # In platypus, canvas doesn't easily expose current translation. 
        # But wait, there is a way to get the current cursor from the flowable? No, flowable only knows relative 0,0.

doc = BaseDocTemplate("test.pdf", pagesize=A4)
frame = Frame(0, 0, A4[0], A4[1])
doc.addPageTemplates([PageTemplate(id='T', frames=[frame])])
doc.build([TestFlowable()])
