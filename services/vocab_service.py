from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
from models import Vocabulary
from fastapi import HTTPException
from constants import SCRABBLE_SCORES, CEFR_MULTIPLIERS, LETTER_WEIGHTS
from spellchecker import SpellChecker
import random

spell = SpellChecker()

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

def get_definition_quiz(db: Session, level: str = "ALL"):
    """
    สร้างโจทย์จับคู่: โจทย์อังกฤษ -> ชอยส์ไทย (3 ตัวเลือก)
    """
    # 1. Query หาคำศัพท์ (Logic เดิม)
    query = db.query(Vocabulary)
    
    if level and level.upper() != "ALL":
        query = query.filter(Vocabulary.cefr_level == level.upper())
        
    target = query.order_by(func.rand()).first()
    
    if not target:
        raise HTTPException(status_code=404, detail="No words found")

    # 2. สุ่มตัวหลอก (Logic เดิม)
    distractors = db.query(Vocabulary)\
        .filter(Vocabulary.vocab_id != target.vocab_id)\
        .order_by(func.rand())\
        .limit(2)\
        .all()
    
    # 3. รวมและ Shuffle
    choices = [target] + distractors
    random.shuffle(choices)
    
    return {
        "mode": "definition",
        "vocab_id": target.vocab_id,
        "question": target.word,
        "cefr_level": target.cefr_level,
        "choices": [
            {"vocab_id": c.vocab_id, "meaning": c.meaning} 
            for c in choices
        ]
    }

def check_definition_answer(db: Session, vocab_id: int, answer_id: int):
    """
    ตรวจคำตอบ: เทียบ vocab_id (โจทย์) กับ answer_id (ที่ผู้เล่นตอบ)
    """
    # 1. ดึงข้อมูลโจทย์ (เฉลย)
    target = db.query(Vocabulary).filter(Vocabulary.vocab_id == vocab_id).first()
    
    if not target:
        raise HTTPException(status_code=404, detail="Question word not found")

    # 2. เช็คความถูกต้อง
    is_correct = (vocab_id == answer_id)
    
    # 3. เตรียมข้อความตอบกลับ
    if is_correct:
        msg = "Correct! เก่งมาก"
    else:
        msg = "Wrong! ลองใหม่อีกครั้งนะ"
        
    return {
        "is_correct": is_correct,
        "message": msg,
        "correct_word": target.word,
        "meaning": target.meaning
    }