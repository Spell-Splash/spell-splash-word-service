from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from database import get_db
from schemas import (
    DefinitionQuizResponse, 
    WordSubmission, 
    WordCheckResponse,
    CursedQuizResponse
    )
from services import vocab_service

router = APIRouter(
    prefix="/vocab",
    tags=["Vocabulary"]
)

# --- 1. Spelling / Word Building Mode ---

@router.get("/game/letters")
def get_letters(amount: int = 10):
    """
    ขอรับกองตัวอักษร (Letter Pool) ไปเริ่มเกม
    """
    letters = vocab_service.generate_letter_pool(amount)
    return {"letters": letters}

@router.post("/game/submit", response_model=WordCheckResponse)
def submit_word(payload: WordSubmission, db: Session = Depends(get_db)):
    """
    ส่งคำตอบเพื่อคิดคะแนน (Mode นี้ต้องเช็คที่ Server เสมอ)
    """
    result = vocab_service.check_word_submission(
        db, 
        payload.word, 
        payload.available_letters
    )
    return result

# --- 2. Definition Quiz Mode ---

@router.get("/quiz/definition", response_model=DefinitionQuizResponse)
def get_definition_quiz(level: str = "ALL", db: Session = Depends(get_db)):
    """
    ดึงโจทย์ทายความหมาย
    - Return: โจทย์ + เฉลย (Index)
    - Frontend เช็คถูก/ผิดเองได้เลย
    """
    try:
        return vocab_service.get_definition_quiz(db, level)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. Cursed Quiz Mode ---

@router.get("/quiz/cursed", response_model=CursedQuizResponse)
def get_cursed_quiz(level: str = "ALL", db: Session = Depends(get_db)):
    """
    ดึงโจทย์โหมดคำสาป (Listening Challenge)
    """
    try:
        return vocab_service.get_cursed_quiz(db, level)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 4. Speaking Mode ---

@router.post("/quiz/speaking/check")
def check_speaking_quiz(
    target_word: str = Form(...),
    file: UploadFile = File(...)
):
    """
    รับไฟล์เสียงจากผู้เล่น -> ส่งไปตรวจ STT -> คืนผลคะแนน
    """
    return vocab_service.check_pronunciation(target_word, file)