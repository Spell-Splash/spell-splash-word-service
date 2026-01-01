from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas import QuizQuestionSchema
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