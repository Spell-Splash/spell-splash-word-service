from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
from models import Vocabulary
from fastapi import HTTPException, UploadFile
import requests
from constants import (
    SCRABBLE_SCORES, CEFR_MULTIPLIERS, 
    LETTER_WEIGHTS, TTS_SERVICE_URL, STT_SERVICE_URL
)
import schemas
from spellchecker import SpellChecker
import random
import difflib

spell = SpellChecker()

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def get_audio_url(vocab_obj):
    """
    ฟังก์ชันเลือก URL เสียง:
    1. ถ้ามีไฟล์เสียงจริงใน DB (audio_cache_path) ให้ใช้ path นั้น
    2. ถ้าไม่มี ให้สร้าง URL สำหรับเรียก TTS Service
    """
    if vocab_obj.audio_cache_path:
        # ส่ง path กลับไป (Frontend ต้องรู้ว่า Base URL คืออะไร หรือถ้าอยู่เครื่องเดียวกันก็ใช้ได้เลย)
        return vocab_obj.audio_cache_path
    
    # Fallback ไปใช้ TTS
    return f"{TTS_SERVICE_URL}/tts?text={vocab_obj.word}&voice=af_bella"

# ---------------------------------------------------------
# 1. Spelling / Word Building Mode Logic
# ---------------------------------------------------------
def generate_letter_pool(amount: int = 10):
    population = list(LETTER_WEIGHTS.keys())
    weights = list(LETTER_WEIGHTS.values())
    selected_letters = set()
    safe_amount = min(amount, 26) 
    while len(selected_letters) < safe_amount:
        char = random.choices(population, weights=weights, k=1)[0]
        selected_letters.add(char)
    return list(selected_letters)

def check_word_submission(db: Session, submitted_word: str, available_letters: list):
    word_upper = submitted_word.upper().strip()
    
    # 1. เช็คตัวอักษรในมือ
    temp_pool = available_letters.copy()
    for char in word_upper:
        if char in temp_pool:
            temp_pool.remove(char)
        else:
            return {
                "is_valid": False, 
                "message": f"คุณไม่มีตัวอักษร '{char}' ในกอง หรือใช้เกินจำนวน!"
            }

    # 2. เช็ค Dictionary
    if submitted_word.lower() not in spell.known([submitted_word.lower()]):
        return {
            "is_valid": False, 
            "message": f"'{submitted_word}' ไม่ใช่คำศัพท์ภาษาอังกฤษที่ถูกต้อง"
        }

    # 3. คำนวณคะแนน
    base_score = sum(SCRABBLE_SCORES.get(char, 0) for char in word_upper)
    db_vocab = db.query(Vocabulary).filter(Vocabulary.word == submitted_word.lower()).first()
    
    multiplier = 1.0
    cefr_level = None
    
    if db_vocab:
        cefr_level = db_vocab.cefr_level.upper() if db_vocab.cefr_level else None
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

# ---------------------------------------------------------
# 2. Definition Quiz Logic (Fixed Recursion)
# ---------------------------------------------------------
def get_definition_quiz(db: Session, level: str = "ALL"):
    # 1. เลือกคำตอบ (Target)
    query = db.query(Vocabulary)
    if level != "ALL":
        query = query.filter(Vocabulary.cefr_level == level)
    
    target_vocab = query.order_by(func.rand()).first()
    
    if not target_vocab:
        raise HTTPException(status_code=404, detail="No vocabulary found")

    # 2. เลือกตัวหลอก (Distractors)
    distractors = db.query(Vocabulary)\
        .filter(Vocabulary.vocab_id != target_vocab.vocab_id)\
        .order_by(func.rand())\
        .limit(3)\
        .all()

    # 3. แปลงเป็น Dict เพื่อตัดวงจร Recursion และเตรียม Shuffle
    choices_data = [
        {"vocab_id": target_vocab.vocab_id, "word": target_vocab.word}
    ]
    for d in distractors:
        choices_data.append({"vocab_id": d.vocab_id, "word": d.word})
    
    # สลับตำแหน่ง
    random.shuffle(choices_data)
    
    # 4. หา Index ของคำตอบที่ถูกต้อง
    correct_index = -1
    for idx, item in enumerate(choices_data):
        if item["vocab_id"] == target_vocab.vocab_id:
            correct_index = idx
            break
            
    # เตรียมข้อมูลส่งกลับ
    question_text = target_vocab.meaning if target_vocab.meaning else target_vocab.definition
    audio_url = get_audio_url(target_vocab)

    # แปลง Dict กลับเป็น Schema
    formatted_choices = [
        schemas.BaseChoiceSchema(vocab_id=c["vocab_id"], word=c["word"])
        for c in choices_data
    ]

    return schemas.DefinitionQuizResponse(
        mode="definition",
        vocab_id=target_vocab.vocab_id,
        question=question_text,
        cefr_level=target_vocab.cefr_level,
        correct_index=correct_index,
        choices=formatted_choices,
        tts_link=audio_url
    )

# ---------------------------------------------------------
# 3. Cursed Quiz Logic (Fixed Recursion)
# ---------------------------------------------------------
def get_cursed_quiz(db: Session, level: str = "ALL"):
    # 1. สุ่มโจทย์
    query = db.query(Vocabulary)
    if level and level.upper() != "ALL":
        query = query.filter(Vocabulary.cefr_level == level.upper())
    
    target = query.order_by(func.rand()).first()
    
    if not target:
        raise HTTPException(status_code=404, detail="No words found")

    distractors = []
    
    # 2. หา Homophones (เสียงเหมือน)
    if target.phonetic_transcription:
        homophones = db.query(Vocabulary)\
            .filter(Vocabulary.phonetic_transcription == target.phonetic_transcription)\
            .filter(Vocabulary.vocab_id != target.vocab_id)\
            .limit(2)\
            .all()
        distractors.extend(homophones)
    
    # 3. หาคำเขียนคล้าย (Spelling Similarity)
    if len(distractors) < 3:
        needed = 3 - len(distractors)
        candidates = db.query(Vocabulary)\
            .filter(Vocabulary.word.like(f"{target.word[0]}%"))\
            .filter(Vocabulary.vocab_id != target.vocab_id)\
            .filter(Vocabulary.vocab_id.notin_([d.vocab_id for d in distractors]))\
            .limit(50)\
            .all()
            
        scored_candidates = []
        for cand in candidates:
            ratio = difflib.SequenceMatcher(None, target.word.lower(), cand.word.lower()).ratio()
            scored_candidates.append((ratio, cand))
        
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        spelling_distractors = [item[1] for item in scored_candidates[:needed]]
        distractors.extend(spelling_distractors)
        
    # 4. ถ้ายังไม่ครบให้สุ่มเติม
    if len(distractors) < 3:
        needed = 3 - len(distractors)
        random_filler = db.query(Vocabulary)\
            .filter(Vocabulary.vocab_id != target.vocab_id)\
            .filter(Vocabulary.vocab_id.notin_([d.vocab_id for d in distractors]))\
            .order_by(func.rand())\
            .limit(needed)\
            .all()
        distractors.extend(random_filler)

    # 5. รวม Choice และแปลงเป็น Dict (เพื่อแก้ Recursion Error)
    choices_data = [
        {"vocab_id": target.vocab_id, "word": target.word}
    ]
    for d in distractors:
        choices_data.append({"vocab_id": d.vocab_id, "word": d.word})
        
    random.shuffle(choices_data)
    
    audio_link = get_audio_url(target)
    
    formatted_choices = [
        schemas.BaseChoiceSchema(vocab_id=c["vocab_id"], word=c["word"])
        for c in choices_data
    ]
    
    return schemas.CursedQuizResponse(
        mode="cursed",
        vocab_id=target.vocab_id,
        question="Listen carefully!",
        audio_url=audio_link,
        cefr_level=target.cefr_level,
        choices=formatted_choices
    )

# ---------------------------------------------------------
# 4. Speaking Mode Logic
# ---------------------------------------------------------
def check_pronunciation(target_word: str, audio_file: UploadFile):
    files = {
        'file': (audio_file.filename, audio_file.file, audio_file.content_type)
    }

    try:
        response = requests.post(STT_SERVICE_URL, files=files)
        
        if response.status_code != 200:
            return {"error": "STT Service failed", "detail": response.text}
            
        data = response.json()
        spoken_text = data.get("text", "").lower().strip()
        confidence = data.get("confidence_score", 0.0)
        
        target = target_word.lower().strip()
        spoken_text_clean = spoken_text.replace(".", "").replace("?", "").replace("!", "")
        
        is_correct = False
        final_score = 0
        feedback = ""

        if spoken_text_clean == target:
            is_correct = True
            final_score = int(confidence * 100)
            if final_score >= 80:
                feedback = "Excellent! Perfect pronunciation."
            elif final_score >= 50:
                feedback = "Good job, but try to speak clearly."
            else:
                feedback = "Correct word, but unclear pronunciation."
        else:
            is_correct = False
            final_score = int(confidence * 30)
            feedback = f"Incorrect. You said '{spoken_text_clean}', but expected '{target}'."

        return {
            "target_word": target,
            "spoken_text": spoken_text_clean,
            "is_correct": is_correct,
            "score": final_score,
            "confidence_raw": confidence,
            "feedback": feedback
        }

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return {"error": "Cannot connect to STT Service", "detail": str(e)}