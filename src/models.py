from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional

class Question(BaseModel):
    number: int
    text: str
    options: Dict[str, str]
    correct_answer: str

    @field_validator('options')
    def validate_options(cls, v):
        if len(v) < 2 or len(v) > 6:
            raise ValueError("A question must have between 2 and 6 options.")
        return v
        
    @field_validator('correct_answer')
    def validate_correct_answer(cls, v, info):
        options = info.data.get('options', {})
        if v not in options:
            raise ValueError(f"Correct answer '{v}' is not among the provided options: {list(options.keys())}")
        return v

class ExamMetadata(BaseModel):
    title: str = ""
    course_class: str = ""
    subject: str = ""
    term: str = ""
    
class Exam(BaseModel):
    metadata: ExamMetadata
    questions: List[Question]
    
    @field_validator('questions')
    def validate_questions(cls, v):
        if not v:
            raise ValueError("Exam must have at least one question.")
        
        # Check for duplicate numbers
        numbers = [q.number for q in v]
        if len(numbers) != len(set(numbers)):
            duplicates = set([x for x in numbers if numbers.count(x) > 1])
            raise ValueError(f"Duplicate question numbers found: {duplicates}")
            
        return v
