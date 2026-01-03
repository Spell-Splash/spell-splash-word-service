from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
from models import Vocabulary
from fastapi import HTTPException
from constants import SCRABBLE_SCORES, CEFR_MULTIPLIERS, LETTER_WEIGHTS
from spellchecker import SpellChecker
import random

spell = SpellChecker()

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

def generate_letter_pool(amount: int = 10):
    """
    สุ่มกองตัวอักษรแบบ Unique (ไม่ซ้ำกันเลย)
    โดยยังคงให้น้ำหนักตัวที่ใช้ง่าย (A, E, I) ออกบ่อยกว่าตัวยาก (Z, Q)
    """
    population = list(LETTER_WEIGHTS.keys())
    weights = list(LETTER_WEIGHTS.values())
    
    selected_letters = set()
    safe_amount = min(amount, 26) 
    
    while len(selected_letters) < safe_amount:
        # สุ่มมา 1 ตัว ตามน้ำหนัก
        char = random.choices(population, weights=weights, k=1)[0]
        selected_letters.add(char)
        
    return list(selected_letters)

def check_word_submission(db: Session, submitted_word: str, available_letters: list):
    """
    ตรวจสอบคำตอบและคำนวณคะแนน
    """
    word_upper = submitted_word.upper().strip()
    
    # 1. เช็คว่าผู้เล่นใช้ตัวอักษรที่มีในกองจริงไหม?
    temp_pool = available_letters.copy()
    for char in word_upper:
        if char in temp_pool:
            temp_pool.remove(char)
        else:
            return {
                "is_valid": False, 
                "message": f"คุณไม่มีตัวอักษร '{char}' ในกอง หรือใช้เกินจำนวน!"
            }

    # 2. เช็คว่าเป็นคำภาษาอังกฤษจริงไหม? (ใช้ Library)
    # spell.known รับ list ของคำ -> คืนค่า set ของคำที่รู้จัก
    if submitted_word.lower() not in spell.known([submitted_word.lower()]):
        return {
            "is_valid": False, 
            "message": f"'{submitted_word}' ไม่ใช่คำศัพท์ภาษาอังกฤษที่ถูกต้อง"
        }

    # 3. คำนวณ Base Score (Scrabble)
    base_score = sum(SCRABBLE_SCORES.get(char, 0) for char in word_upper)

    # 4. เช็ค Bonus (CEFR) จาก Database
    db_vocab = db.query(Vocabulary).filter(Vocabulary.word == submitted_word.lower()).first()
    
    multiplier = 1.0
    cefr_level = None
    
    if db_vocab:
        cefr_level = db_vocab.cefr_level.upper()
        multiplier = CEFR_MULTIPLIERS.get(cefr_level, 1.0)
    
    final_score = int(base_score * multiplier)

    return {
        "is_valid": True,
        "message": "Correct!",
        "word": submitted_word,
        "base_score": base_score,
        "is_in_db": bool(db_vocab),
        "cefr_level": cefr_level,
        "multiplier": multiplier,
        "total_score": final_score
    }