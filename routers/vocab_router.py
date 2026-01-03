from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas import QuizQuestionSchema, WordSubmission, WordCheckResponse
from services import vocab_service

router = APIRouter(
    prefix="/vocab",
    tags=["Vocabulary"]
)

@router.get("/quiz/{level}", response_model=QuizQuestionSchema)
def get_quiz(level: str, db: Session = Depends(get_db)):
    """
    ดึงโจทย์คำศัพท์ 1 ข้อ พร้อมตัวเลือก 4 ข้อ
    ตัวอย่าง Level: A1, A2, B1, B2, C1
    """
    return vocab_service.get_random_quiz_by_level(db, level.upper())

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