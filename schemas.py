from pydantic import BaseModel
from typing import List, Optional

class ChoiceSchema(BaseModel):
    vocab_id: int
    meaning: str

class QuizQuestionSchema(BaseModel):
    question_word: str
    part_of_speech: str
    cefr_level: str
    choices: List[ChoiceSchema]
    correct_vocab_id: int 
    correct_definition: Optional[str] = None
    phonetic: Optional[str] = None

    class Config:
        orm_mode = True

class WordSubmission(BaseModel):
    """
    รับข้อมูลคำตอบจากผู้เล่น
    """
    word: str
    available_letters: List[str]

class WordCheckResponse(BaseModel):
    """
    ส่งผลการตรวจและคะแนนกลับไป
    """
    is_valid: bool
    message: str
    word: Optional[str] = None
    base_score: int = 0
    is_in_db: bool = False
    cefr_level: Optional[str] = None
    multiplier: float = 1.0
    total_score: int = 0