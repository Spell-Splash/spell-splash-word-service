from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
from models import Vocabulary, Player, PlayerQuest
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
    if vocab_obj.audio_cache_path:
        return vocab_obj.audio_cache_path
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
    
    # 1. เช็คตัวอักษร
    temp_pool = available_letters.copy()
    for char in word_upper:
        if char in temp_pool:
            temp_pool.remove(char)
        else:
            return {"is_valid": False, "message": f"Missing letter '{char}'!"}

    # 2. เช็ค Dictionary
    if submitted_word.lower() not in spell.known([submitted_word.lower()]):
        return {"is_valid": False, "message": "Not a valid English word."}

    # 3. คำนวณคะแนน (Game Logic ปกติ)
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
# 2. Definition Quiz Logic
# ---------------------------------------------------------
def get_definition_quiz(db: Session, level: str = "ALL"):
    query = db.query(Vocabulary)
    if level != "ALL":
        query = query.filter(Vocabulary.cefr_level == level)
    
    target_vocab = query.order_by(func.rand()).first()
    if not target_vocab:
        raise HTTPException(status_code=404, detail="No vocabulary found")

    distractors = db.query(Vocabulary)\
        .filter(Vocabulary.vocab_id != target_vocab.vocab_id)\
        .order_by(func.rand()).limit(3).all()

    choices_data = [{"vocab_id": target_vocab.vocab_id, "word": target_vocab.word}]
    for d in distractors:
        choices_data.append({"vocab_id": d.vocab_id, "word": d.word})
    
    random.shuffle(choices_data)
    
    correct_index = next(i for i, item in enumerate(choices_data) if item["vocab_id"] == target_vocab.vocab_id)
    question_text = target_vocab.meaning if target_vocab.meaning else target_vocab.definition
    audio_url = get_audio_url(target_vocab)

    formatted_choices = [schemas.BaseChoiceSchema(**c) for c in choices_data]

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
# 3. Cursed Quiz Logic
# ---------------------------------------------------------
def get_cursed_quiz(db: Session, level: str = "ALL"):
    query = db.query(Vocabulary)
    if level and level.upper() != "ALL":
        query = query.filter(Vocabulary.cefr_level == level.upper())
    
    target = query.order_by(func.rand()).first()
    if not target:
        raise HTTPException(status_code=404, detail="No words found")

    distractors = []
    # (Logic หาตัวหลอกเดิมคงไว้...)
    if target.phonetic_transcription:
        homophones = db.query(Vocabulary).filter(Vocabulary.phonetic_transcription == target.phonetic_transcription, Vocabulary.vocab_id != target.vocab_id).limit(2).all()
        distractors.extend(homophones)
    
    if len(distractors) < 3:
        needed = 3 - len(distractors)
        random_filler = db.query(Vocabulary).filter(Vocabulary.vocab_id != target.vocab_id).order_by(func.rand()).limit(needed).all()
        distractors.extend(random_filler)

    choices_data = [{"vocab_id": target.vocab_id, "word": target.word}]
    for d in distractors:
        choices_data.append({"vocab_id": d.vocab_id, "word": d.word})
        
    random.shuffle(choices_data)
    audio_link = get_audio_url(target)
    
    formatted_choices = [schemas.BaseChoiceSchema(**c) for c in choices_data]
    
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
    files = {'file': (audio_file.filename, audio_file.file, audio_file.content_type)}
    try:
        response = requests.post(STT_SERVICE_URL, files=files)
        if response.status_code != 200:
            return {"error": "STT Service failed"}
            
        data = response.json()
        spoken_text = data.get("text", "").lower().strip()
        confidence = data.get("confidence_score", 0.0)
        target = target_word.lower().strip()
        
        # Simple string matching
        spoken_clean = spoken_text.replace(".", "").replace("?", "")
        is_correct = spoken_clean == target
        score = int(confidence * 100) if is_correct else int(confidence * 30)
        
        return {
            "target_word": target,
            "spoken_text": spoken_clean,
            "is_correct": is_correct,
            "score": score,
            "feedback": "Excellent!" if score > 80 else "Try again."
        }
    except Exception as e:
        return {"error": str(e)}

# ---------------------------------------------------------
# 5. 👤 Player Management
# ---------------------------------------------------------
def register_or_get_player(db: Session, player_data: schemas.PlayerCreate):
    player = db.query(Player).filter(Player.player_id == player_data.player_id).first()
    if not player:
        player = Player(
            player_id=player_data.player_id,
            username=player_data.username
        )
        db.add(player)
        db.commit()
        db.refresh(player)
    return player

def get_player_profile(db: Session, player_id: str):
    player = db.query(Player).filter(Player.player_id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player

# ---------------------------------------------------------
# 6. Quest & Game State for NPC
# ---------------------------------------------------------
def update_quest_status(db: Session, quest_data: schemas.QuestUpdate):
    """
    Unity จะยิงมาที่นี่เมื่อผู้เล่นทำอะไรสำเร็จ
    """
    # 1. เช็คว่ามีเควสนี้อยู่แล้วไหม
    quest = db.query(PlayerQuest).filter(
        PlayerQuest.player_id == quest_data.player_id,
        PlayerQuest.quest_id == quest_data.quest_id
    ).first()

    if quest:
        quest.status = quest_data.status
    else:
        # ถ้าไม่มี ให้สร้างใหม่
        quest = PlayerQuest(
            player_id=quest_data.player_id,
            quest_id=quest_data.quest_id,
            status=quest_data.status
        )
        db.add(quest)
    
    db.commit()
    return {"status": "success", "quest_id": quest_data.quest_id, "new_status": quest_data.status}

def get_game_state_for_npc(db: Session, player_id: str) -> schemas.GameStateForNPC:
    """
    ฟังก์ชันสำคัญ! รวบรวมข้อมูลผู้เล่นเป็น String เดียว เพื่อส่งให้ AI อ่าน
    """
    player = db.query(Player).filter(Player.player_id == player_id).first()
    if not player:
        return schemas.GameStateForNPC(player_summary="Unknown Player")

    # ดึงเฉพาะเควสที่กำลังทำ หรือ เสร็จแล้ว
    active_quests = [q.quest_id for q in player.quests if q.status == "IN_PROGRESS"]
    completed_quests = [q.quest_id for q in player.quests if q.status == "COMPLETED"]

    summary = (
        f"Player Name: {player.username or 'Traveler'}. "
        f"Active Quests: {', '.join(active_quests) if active_quests else 'None'}. "
        f"Completed Achievements: {', '.join(completed_quests) if completed_quests else 'None'}."
    )

    return schemas.GameStateForNPC(player_summary=summary)