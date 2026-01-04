from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas import (
    DefinitionAnswerSubmission, 
    DefinitionAnswerResponse, 
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
    ส่งคำตอบเพื่อคิดคะแนน
    """
    # ดึงค่าจาก payload มาใช้
    result = vocab_service.check_word_submission(
        db, 
        payload.word, 
        payload.available_letters
    )
    return result

@router.get("/quiz/definition", response_model=DefinitionQuizResponse)
def get_definition_quiz_endpoint(level: str = "ALL", db: Session = Depends(get_db)):
    """
    ดึงโจทย์ Word Matching
    - level="A1" -> สุ่มเฉพาะ A1
    - level="ALL" -> สุ่มจากทุก Level (A1-C1)
    """
    return vocab_service.get_definition_quiz(db, level)

@router.post("/quiz/definition/check", response_model=DefinitionAnswerResponse)
def check_definition_answer_endpoint(payload: DefinitionAnswerSubmission, db: Session = Depends(get_db)):
    """
    ตรวจคำตอบ Word Matching
    """
    return vocab_service.check_definition_answer(
        db, 
        payload.vocab_id, 
        payload.answer_id
    )

@router.get("/quiz/cursed", response_model=CursedQuizResponse)
def get_cursed_quiz(level: str = "ALL", db: Session = Depends(get_db)):
    """
    ดึงโจทย์โหมดคำสาป (Cursed Mode):
    - Return: Audio URL สำหรับโจทย์ และตัวเลือกที่เสียง/รูปคล้ายกัน
    """
    try:
        return vocab_service.get_cursed_quiz(db, level)
    except Exception as e:
        # ดักจับ Error กรณีหาคำศัพท์ไม่ได้ หรือ Logic มีปัญหา
        raise HTTPException(status_code=500, detail=str(e))