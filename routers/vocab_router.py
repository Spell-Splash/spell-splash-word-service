from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from database import get_db
from schemas import (
    DefinitionQuizResponse, 
    WordSubmission, 
    WordCheckResponse,
    CursedQuizResponse,
    PlayerCreate,
    PlayerProfileResponse,
    QuestUpdate,
    GameStateForNPC
)
from services import vocab_service

router = APIRouter(
    prefix="/vocab",
    tags=["Vocabulary & Game"]
)

# --- 1. Spelling / Word Building Mode ---

@router.get("/game/letters")
def get_letters(amount: int = 10):
    letters = vocab_service.generate_letter_pool(amount)
    return {"letters": letters}

@router.post("/game/submit", response_model=WordCheckResponse)
def submit_word(payload: WordSubmission, db: Session = Depends(get_db)):
    return vocab_service.check_word_submission(
        db, 
        payload.word, 
        payload.available_letters
    )

# --- 2. Definition Quiz Mode ---

@router.get("/quiz/definition", response_model=DefinitionQuizResponse)
def get_definition_quiz(level: str = "ALL", db: Session = Depends(get_db)):
    return vocab_service.get_definition_quiz(db, level)

# --- 3. Cursed Quiz Mode ---

@router.get("/quiz/cursed", response_model=CursedQuizResponse)
def get_cursed_quiz(level: str = "ALL", db: Session = Depends(get_db)):
    return vocab_service.get_cursed_quiz(db, level)

# --- 4. Speaking Mode ---

@router.post("/quiz/speaking/check")
def check_speaking_quiz(
    target_word: str = Form(...),
    file: UploadFile = File(...)
):
    return vocab_service.check_pronunciation(target_word, file)

# ==========================================
# 👤 5. Player & Quest Management
# ==========================================

@router.post("/player/register", response_model=PlayerProfileResponse)
def register_player(player_data: PlayerCreate, db: Session = Depends(get_db)):
    """
    ลงทะเบียนผู้เล่นครั้งแรก (หรือ Login ถ้ามี ID แล้ว)
    """
    return vocab_service.register_or_get_player(db, player_data)

@router.get("/player/{player_id}", response_model=PlayerProfileResponse)
def get_player_profile(player_id: str, db: Session = Depends(get_db)):
    """
    ดึงข้อมูลโปรไฟล์ (เอาไว้โชว์ในหน้า Menu)
    """
    return vocab_service.get_player_profile(db, player_id)

@router.post("/player/quest/update")
def update_quest_status(quest_data: QuestUpdate, db: Session = Depends(get_db)):
    """
    Unity ยิง API นี้เมื่อเควสมีการเปลี่ยนแปลง (เช่น รับเควส / ส่งเควส)
    """
    return vocab_service.update_quest_status(db, quest_data)

@router.get("/player/{player_id}/npc_context", response_model=GameStateForNPC)
def get_npc_context(player_id: str, db: Session = Depends(get_db)):
    """
    🎯 ไฮไลท์สำคัญ!
    Unity เรียก API นี้ -> ได้ Text สรุป -> ส่งไปหา NPC Service
    """
    return vocab_service.get_game_state_for_npc(db, player_id)