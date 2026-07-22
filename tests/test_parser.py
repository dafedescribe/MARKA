import unittest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parser import parse_text

sample_text_1 = """Government
SS2
Second Term Examination

1. The first president of Nigeria was
*A. Nnamdi Azikiwe
B. Tafawa Balewa
C. Yakubu Gowon
D. Ibrahim Babangida

2. Which city is the capital of Kano State?
(A.) Abuja
B. Kano
*C. Kaduna
D. Jos

3. What is 2 + 2?
A) 3
B) 4
C) 5
(D) 22
"""


class TestParser(unittest.TestCase):
    def test_parse_text(self):
        exam = parse_text(sample_text_1)
        self.assertEqual(exam.metadata.subject, "Government")
        self.assertEqual(exam.metadata.course_class, "SS2")
        self.assertEqual(len(exam.questions), 3)
        self.assertEqual(exam.questions[0].correct_answer, 'A')
        self.assertEqual(exam.questions[1].correct_answer, 'C')
        self.assertEqual(exam.questions[2].correct_answer, 'D')


if __name__ == "__main__":
    unittest.main()

