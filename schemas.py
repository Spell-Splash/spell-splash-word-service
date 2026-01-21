from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class BaseChoiceSchema(BaseModel):
    vocab_id: int
    word: str

# 1. Definition Quiz
class DefinitionQuizResponse(BaseModel):
    mode: str = "definition"
    vocab_id: int
    question: str
    cefr_level: str
    correct_index: int
    choices: List[BaseChoiceSchema]
    tts_link: Optional[str] = None

class DefinitionAnswerSubmission(BaseModel):
    player_id: str 
    vocab_id: int
    is_correct: bool

class SaveProgressResponse(BaseModel):
    status: str
    message: str

# 2. Spelling
class WordSubmission(BaseModel):
    player_id: str
    word: str
    available_letters: List[str]

class WordCheckResponse(BaseModel):
    is_valid: bool
    message: str
    word: Optional[str] = None
    is_in_db: bool = False

# 3. Cursed Quiz
class CursedQuizResponse(BaseModel):
    mode: str = "cursed"
    vocab_id: int
    question: str = "[Audio Clip]"
    audio_url: str
    cefr_level: str
    choices: List[BaseChoiceSchema]

# สร้าง/ลงทะเบียนผู้เล่น
class PlayerCreate(BaseModel):
    player_id: str
    username: str

# ดึงข้อมูลผู้เล่น
class PlayerProfileResponse(BaseModel):
    player_id: str
    username: str
    model_config = ConfigDict(from_attributes=True)

# อัปเดตสถานะเควส
class QuestUpdate(BaseModel):
    player_id: str
    quest_id: str
    status: str  # "IN_PROGRESS", "COMPLETED"

# Schema สำหรับสร้าง String ไปบอก NPC (ใช้กับ RAG)
class GameStateForNPC(BaseModel):
    player_summary: str  
    # ตัวอย่าง: "Player Alice. Quest 'Find Sword': COMPLETED."