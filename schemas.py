from pydantic import BaseModel
from typing import List, Optional

class ChoiceSchema(BaseModel):
    vocab_id: int
    word: str

class DefinitionQuizResponse(BaseModel):
    mode: str
    vocab_id: int         
    question: str
    cefr_level: str
    choices: List[ChoiceSchema]

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