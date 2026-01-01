from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
from models import Vocabulary
from fastapi import HTTPException
import random

def get_random_quiz_by_level(db: Session, level: str):
    """
    1. สุ่มศัพท์ 1 คำ ตาม Level ที่ระบุ (เป็นคำตอบที่ถูก)
    2. สุ่มศัพท์อื่นอีก 3 คำ ที่มี Part of Speech เดียวกัน (เป็นตัวลวง)
    3. รวมกันแล้วสลับตำแหน่ง
    """
    # 1. หาคำตอบที่ถูก (Correct Answer)
    correct_word = db.query(Vocabulary)\
        .filter(Vocabulary.cefr_level == level)\
        .order_by(func.rand())\
        .first()

    if not correct_word:
        raise HTTPException(status_code=404, detail=f"No words found for level {level}")

    # 2. หาตัวลวง (Distractors) 3 คำ
    # เงื่อนไข: POS เดียวกัน และ ต้องไม่ใช่คำเดียวกับคำตอบ
    distractors = db.query(Vocabulary)\
        .filter(Vocabulary.part_of_speech == correct_word.part_of_speech)\
        .filter(Vocabulary.vocab_id != correct_word.vocab_id)\
        .order_by(func.rand())\
        .limit(3)\
        .all()

    # ถ้าตัวลวงไม่พอ (กรณีฐานข้อมูลน้อย) ให้ดึง POS อะไรก็ได้มาเติม
    if len(distractors) < 3:
        more_distractors = db.query(Vocabulary)\
            .filter(Vocabulary.vocab_id != correct_word.vocab_id)\
            .filter(Vocabulary.vocab_id.notin_([d.vocab_id for d in distractors]))\
            .limit(3 - len(distractors))\
            .all()
        distractors.extend(more_distractors)

    # 3. รวมและสลับตำแหน่ง (Shuffle)
    all_choices = [correct_word] + distractors
    random.shuffle(all_choices)

    # 4. แปลงข้อมูลกลับตาม Schema
    return {
        "question_word": correct_word.word,
        "part_of_speech": correct_word.part_of_speech,
        "cefr_level": correct_word.cefr_level,
        "choices": [
            {"vocab_id": w.vocab_id, "meaning": w.meaning} for w in all_choices
        ],
        "correct_vocab_id": correct_word.vocab_id,
        "correct_definition": correct_word.definition,
        "phonetic": correct_word.phonetic_transcription
    }