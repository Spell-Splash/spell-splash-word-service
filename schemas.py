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