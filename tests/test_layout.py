import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import Exam, ExamMetadata, Question
from src.layout_engine import ExamLayoutEngine

def run_tests():
    meta = ExamMetadata(
        title="Examination",
        course_class="SS2",
        subject="Government",
        term="Second Term Examination"
    )
    
    questions = []
    # Add a few dummy questions so it satisfies the model
    q = Question(
        number=1,
        text="Sample question",
        options={"A": "Option 1", "B": "Option 2"},
        correct_answer="A"
    )
    questions.append(q)
    
    exam = Exam(metadata=meta, questions=questions)
    
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'PHY_SS2_TERM2')
    
    print("Generating PDF...")
    engine = ExamLayoutEngine(exam, out_dir)
    engine.generate()
    print(f"Generated at: {engine.pdf_path}")

if __name__ == "__main__":
    run_tests()
