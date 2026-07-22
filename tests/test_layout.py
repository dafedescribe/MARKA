import unittest
import sys
import os
import tempfile
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import Exam, ExamMetadata, Question
from src.layout_engine import ExamLayoutEngine


class TestLayout(unittest.TestCase):
    def test_layout_generation(self):
        meta = ExamMetadata(
            title="Examination",
            course_class="SS2",
            subject="Government",
            term="Second Term Examination"
        )
        questions = [
            Question(
                number=1,
                text="Sample question",
                options={"A": "Option 1", "B": "Option 2"},
                correct_answer="A"
            )
        ]
        exam = Exam(metadata=meta, questions=questions)
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ExamLayoutEngine(exam, tmpdir)
            engine.generate()
            self.assertTrue(os.path.exists(engine.pdf_path))


if __name__ == "__main__":
    unittest.main()

