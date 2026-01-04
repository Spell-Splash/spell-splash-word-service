from pydantic import BaseModel
from typing import List, Optional

class ChoiceSchema(BaseModel):
    vocab_id: int
    meaning: str

class DefinitionQuizResponse(BaseModel):
    mode: str
    vocab_id: int
    question: str
    cefr_level: str
    choices: List[ChoiceSchema]

class DefinitionAnswerSubmission(BaseModel):
    vocab_id: int
    answer_id: int

class DefinitionAnswerResponse(BaseModel):
    is_correct: bool
    message: str
    correct_word: str
    meaning: str

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

class CursedChoiceSchema(BaseModel):
    vocab_id: int
    word: str

class CursedQuizResponse(BaseModel):
    mode: str
    vocab_id: int
    question: str = "[Audio Clip]"
    audio_url: str
    cefr_level: str
    choices: List[CursedChoiceSchema]