from pydantic import BaseModel
from typing import List, Optional

# --- Shared Schemas (ใช้ร่วมกันได้) ---

class BaseChoiceSchema(BaseModel):
    """Schema สำหรับตัวเลือก A, B, C, D"""
    vocab_id: int
    word: str  # ✅ แก้จาก meaning เป็น word ให้ตรงกับปุ่มกด

# --- 1. Definition Quiz Mode ---

class DefinitionQuizResponse(BaseModel):
    mode: str = "definition" # ใส่ default value ไว้เลย
    vocab_id: int
    question: str            # โจทย์ (ความหมายภาษาไทย หรือ Definition Eng)
    cefr_level: str
    correct_index: int       # ✅ เฉลย (0-3) สำหรับ Client-side check
    choices: List[BaseChoiceSchema] # ใช้ Schema กลาง
    tts_link: Optional[str] = None  # (Optional) เผื่ออยากให้กดฟังเสียงคำตอบได้

# ถ้า Frontend เช็คคำตอบเองได้แล้ว 2 อันล่างนี้ใช้ยิงเพื่อ "Save Progress" อย่างเดียว
class DefinitionAnswerSubmission(BaseModel):
    vocab_id: int
    is_correct: bool # ✅ ส่งแค่ว่าถูกหรือผิดไปให้ Server บันทึกก็พอ

class SaveProgressResponse(BaseModel):
    status: str
    new_xp: int

# --- 2. Spelling / Word Construction Mode ---

class WordSubmission(BaseModel):
    word: str
    available_letters: List[str]

class WordCheckResponse(BaseModel):
    is_valid: bool
    message: str
    word: Optional[str] = None
    base_score: int = 0
    is_in_db: bool = False
    cefr_level: Optional[str] = None
    multiplier: float = 1.0
    total_score: int = 0

# --- 3. Cursed Quiz Mode ---

class CursedQuizResponse(BaseModel):
    mode: str = "cursed"
    vocab_id: int
    question: str = "[Audio Clip]"
    audio_url: str           # ลิงก์ไฟล์เสียงจาก TTS
    cefr_level: str
    choices: List[BaseChoiceSchema] # ใช้ Schema กลาง (Reused)