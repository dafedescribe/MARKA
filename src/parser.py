import re
from typing import List, Dict, Tuple
from src.models import Exam, ExamMetadata, Question

class ParserError(Exception):
    pass

def parse_text(text: str) -> Exam:
    lines = [line.strip() for line in text.split('\n')]
    
    metadata_lines = []
    questions_data = []
    
    current_question = None
    
    # Matches "1.", "1)", "1 ."
    q_start_re = re.compile(r'^(\d+)\s*[\.\)]\s*(.*)')
    
    # Matches:
    # A. or A) or (A) or (A.) 
    # Optional leading asterisk *
    # group 1: asterisk (if any)
    # group 2: the letter (A-F)
    # group 3: the rest of the text
    opt_start_re = re.compile(r'^(\*?)\s*\(?([A-F])[\.\)]?\)?\s*(.*)', re.IGNORECASE)
    
    in_questions = False
    
    for i, line in enumerate(lines):
        if "THEORY" in line.upper():
            break
            
        if not line:
            # A blank line ends the current question definition 
            # if we are already parsing one, but it doesn't strictly mean the end of all questions.
            # However, if we just saw options and now a blank line, next text might be a new question.
            continue
            
        q_match = q_start_re.match(line)
        if q_match:
            in_questions = True
            if current_question:
                questions_data.append(current_question)
            
            number = int(q_match.group(1))
            q_text = q_match.group(2).strip()
            current_question = {
                'number': number,
                'text': q_text,
                'options': {},
                'correct_answer': None,
                'raw_option_markers': [] # To store whether they were marked with parenthesis
            }
            continue
            
        if not in_questions:
            metadata_lines.append(line)
            continue
            
        opt_match = opt_start_re.match(line)
        if opt_match and current_question:
            # Wait, what if the text just happened to start with "A. "?
            # If we are in options mode, we treat it as an option.
            has_asterisk = bool(opt_match.group(1))
            opt_letter = opt_match.group(2).upper()
            opt_text = opt_match.group(3).strip()
            
            # Support trailing asterisks
            if opt_text.endswith('*'):
                has_asterisk = True
                opt_text = opt_text[:-1].strip()
            
            # Check if this line starts with (Letter.) or (Letter)
            is_parenthesis_wrapped = line.startswith('(') and (')' in line.split(opt_text)[0] if opt_text else line.endswith(')'))
            
            current_question['options'][opt_letter] = opt_text
            current_question['raw_option_markers'].append({
                'letter': opt_letter,
                'asterisk': has_asterisk,
                'parenthesis': is_parenthesis_wrapped
            })
            continue
            
        # If it's a continuation of text
        if current_question:
            if not current_question['options']:
                # Still building the question text
                if current_question['text']:
                    current_question['text'] += "\n" + line
                else:
                    current_question['text'] = line
            else:
                # Continuation of the last option
                last_opt = list(current_question['options'].keys())[-1]
                if current_question['options'][last_opt]:
                    current_question['options'][last_opt] += "\n" + line
                else:
                    current_question['options'][last_opt] = line
                
    if current_question:
        questions_data.append(current_question)
        
    # Analyze correct answers
    for qd in questions_data:
        options_info = qd.pop('raw_option_markers')
        
        # Rule 1: Asterisk always means correct.
        asterisk_corrects = [info['letter'] for info in options_info if info['asterisk']]
        if len(asterisk_corrects) > 1:
            raise ParserError(f"Question {qd['number']} has multiple correct answers marked with asterisks.")
        elif len(asterisk_corrects) == 1:
            qd['correct_answer'] = asterisk_corrects[0]
        else:
            # Rule 2: If exactly ONE is wrapped in parentheses, it's correct.
            paren_corrects = [info['letter'] for info in options_info if info['parenthesis']]
            if len(paren_corrects) == 1:
                qd['correct_answer'] = paren_corrects[0]
            elif len(paren_corrects) > 1:
                 # It might just be that all options are (A) (B) (C). So no correct answer identified.
                 pass

    # Extract metadata intelligently if possible. 
    # Defaulting to assigning first lines to specific fields as requested by MVP.
    meta = ExamMetadata()
    if len(metadata_lines) >= 1:
        meta.subject = metadata_lines[0]
    if len(metadata_lines) >= 2:
        meta.course_class = metadata_lines[1]
    if len(metadata_lines) >= 3:
        meta.term = metadata_lines[2]
    meta.title = "Examination"
        
    # Build Pydantic models
    questions = []
    for qd in questions_data:
        if not qd['correct_answer']:
            raise ParserError(f"Question {qd['number']} has no correct answer marked.")
        try:
            q = Question(**qd)
            questions.append(q)
        except ValueError as e:
            raise ParserError(f"Validation error in Question {qd['number']}: {str(e)}")
            
    try:
        exam = Exam(metadata=meta, questions=questions)
    except ValueError as e:
        raise ParserError(f"Exam validation error: {str(e)}")
        
    return exam
