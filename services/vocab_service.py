from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
from models import Vocabulary
from fastapi import HTTPException, UploadFile
import requests
from constants import (
    SCRABBLE_SCORES, CEFR_MULTIPLIERS, 
    LETTER_WEIGHTS, TTS_SERVICE_URL, STT_SERVICE_URL)
from spellchecker import SpellChecker
import random
import difflib

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

def get_cursed_quiz(db: Session, level: str = "ALL"):
    """
    สร้างโจทย์โหมดคำสาป (Listening Challenge):
    - โจทย์: เสียง (TTS)
    - ตัวเลือก: ศัพท์ที่เสียงเหมือน (Homophones) หรือเขียนคล้าย
    """
    # 1. สุ่มโจทย์ (Target)
    query = db.query(Vocabulary)
    if level and level.upper() != "ALL":
        query = query.filter(Vocabulary.cefr_level == level.upper())
    
    target = query.order_by(func.rand()).first()
    
    if not target:
        raise HTTPException(status_code=404, detail="No words found")

    distractors = []
    
    # --- Step 2: หาตัวหลอกแบบ "เสียงเหมือน/พ้องเสียง" (Homophones) ---
    # ถ้ามีข้อมูล Phonetic ให้ลองหาคนที่ IPA ตรงกันเลย (เช่น Meat vs Meet)
    if target.phonetic_transcription:
        homophones = db.query(Vocabulary)\
            .filter(Vocabulary.phonetic_transcription == target.phonetic_transcription)\
            .filter(Vocabulary.vocab_id != target.vocab_id)\
            .limit(2)\
            .all()
        distractors.extend(homophones)
    
    # --- Step 3: หาตัวหลอกแบบ "เขียนคล้าย" (Spelling Similarity) ---
    # (ใช้ Logic เดิมมาเติมให้เต็ม 3 ข้อ)
    if len(distractors) < 3:
        needed = 3 - len(distractors)
        
        # หาคำที่ขึ้นต้นเหมือนกัน
        candidates = db.query(Vocabulary)\
            .filter(Vocabulary.word.like(f"{target.word[0]}%"))\
            .filter(Vocabulary.vocab_id != target.vocab_id)\
            .filter(Vocabulary.vocab_id.notin_([d.vocab_id for d in distractors]))\
            .limit(50)\
            .all() # ดึงมาสัก 50 ตัวแล้วมาคัดกรองเอง
            
        # คำนวณความเหมือนด้วย difflib
        scored_candidates = []
        for cand in candidates:
            ratio = difflib.SequenceMatcher(None, target.word.lower(), cand.word.lower()).ratio()
            scored_candidates.append((ratio, cand))
        
        # เรียงลำดับเอาที่เหมือนที่สุด
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # หยิบตัวท็อปๆ มาเติม
        spelling_distractors = [item[1] for item in scored_candidates[:needed]]
        distractors.extend(spelling_distractors)
        
    # --- Step 4: ถ้ายังไม่ครบ 3 (กรณีหาคำคล้ายไม่ได้เลย) ---
    if len(distractors) < 3:
        needed = 3 - len(distractors)
        random_filler = db.query(Vocabulary)\
            .filter(Vocabulary.vocab_id != target.vocab_id)\
            .filter(Vocabulary.vocab_id.notin_([d.vocab_id for d in distractors]))\
            .order_by(func.rand())\
            .limit(needed)\
            .all()
        distractors.extend(random_filler)

    # 5. รวมและสลับตำแหน่ง
    choices = [target] + distractors
    random.shuffle(choices)
    
    # 6. สร้าง URL สำหรับ TTS (ส่ง Query Param เป็นคำศัพท์ไป)
    # ตัวอย่าง URL: http://localhost:8001/tts?text=abandon
    audio_link = f"{TTS_SERVICE_URL}?text={target.word}"
    
    return {
        "mode": "cursed_listening",
        "vocab_id": target.vocab_id,
        "question": "Listen carefully!", # ข้อความบอกผู้เล่น
        "audio_url": audio_link,
        "cefr_level": target.cefr_level,
        "choices": [
            {"vocab_id": c.vocab_id, "word": c.word} 
            for c in choices
        ]
    }

def check_pronunciation(target_word: str, audio_file: UploadFile):
    """
    ส่งไฟล์เสียงไปตรวจที่ STT Service และคำนวณคะแนน
    """
    # 1. เตรียมไฟล์เพื่อส่งต่อให้ STT Service
    files = {
        'file': (audio_file.filename, audio_file.file, audio_file.content_type)
    }

    try:
        # 2. ยิง Request ไปหา STT Service (Port 8002)
        response = requests.post(STT_SERVICE_URL, files=files)
        
        if response.status_code != 200:
            return {"error": "STT Service failed", "detail": response.text}
            
        data = response.json()
        spoken_text = data.get("text", "").lower().strip()
        confidence = data.get("confidence_score", 0.0)
        
        # 3. Logic ตัดเกรด (Scoring System)
        target = target_word.lower().strip()
        
        # ลบเครื่องหมายวรรคตอนออก (เผื่อ whisper ใส่จุด full stop มา)
        spoken_text_clean = spoken_text.replace(".", "").replace("?", "").replace("!", "")
        
        is_correct = False
        final_score = 0
        feedback = ""

        if spoken_text_clean == target:
            # กรณี: พูดถูกคำเป๊ะๆ
            is_correct = True
            final_score = int(confidence * 100) # คะแนนเต็ม 100
            
            if final_score >= 80:
                feedback = "Excellent! Perfect pronunciation."
            elif final_score >= 50:
                feedback = "Good job, but try to speak clearly."
            else:
                feedback = "Correct word, but unclear pronunciation."
        else:
            # กรณี: พูดผิดคำ (หรือ Whisper ฟังผิด)
            is_correct = False
            final_score = int(confidence * 30) # ให้คะแนนความพยายามนิดหน่อย
            feedback = f"Incorrect. You said '{spoken_text_clean}', but expected '{target}'."

        return {
            "target_word": target,
            "spoken_text": spoken_text_clean,
            "is_correct": is_correct,
            "score": final_score,         # คะแนน 0-100
            "confidence_raw": confidence, # ค่าดิบจาก AI
            "feedback": feedback
        }

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return {"error": "Cannot connect to STT Service", "detail": str(e)}