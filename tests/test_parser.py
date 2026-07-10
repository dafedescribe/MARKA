import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parser import parse_text, ParserError

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

# Wait, for question 3, (D) is the only one in parenthesis. Let's see if the parser picks it up.

def run_tests():
    print("Testing parser...")
    try:
        exam = parse_text(sample_text_1)
        print("Parsed successfully!")
        print("Metadata:", exam.metadata)
        for q in exam.questions:
            print(f"Q{q.number}: {q.text}")
            print(f"  Options: {q.options}")
            print(f"  Correct: {q.correct_answer}")
            
        assert exam.questions[0].correct_answer == 'A'
        assert exam.questions[1].correct_answer == 'C'
        assert exam.questions[2].correct_answer == 'D'
        print("All tests passed!")
    except ParserError as e:
        print(f"Parser error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    run_tests()
