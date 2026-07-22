import os
import argparse
from src.parser import parse_text
from src.layout_engine import ExamLayoutEngine
import qrcode # Will be used in Phase 4 for adding the QR to the PDF

def compile_exam(input_path: str, output_dir: str):
    print(f"Reading {input_path}...")
    with open(input_path, 'r') as f:
        content = f.read()
        
    print("Parsing Exam...")
    exam = parse_text(content)
    print(f"Parsed {len(exam.questions)} questions.")
    
    # Generate an exam ID
    exam_id = f"{exam.metadata.subject.replace(' ', '_')}_{exam.metadata.course_class}_{exam.metadata.term.replace(' ', '_')}".upper()
    exam_package_dir = os.path.join(output_dir, exam_id)
    print(f"Generating Exam Package at {exam_package_dir}...")
    
    engine = ExamLayoutEngine(exam, exam_package_dir)
    engine.generate()
    
    print("Done! Exam package compiled successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Compile Exam Document into an Exam Package')
    parser.add_argument('input', help='Path to input txt/md file')
    parser.add_argument('output', help='Path to output packages directory', default='./output_packages', nargs='?')
    args = parser.parse_args()
    
    compile_exam(args.input, args.output)
