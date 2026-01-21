from fastapi import APIRouter, Depends, HTTPException
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

# ==========================================
# 👤 5. Player & Quest Management
# ==========================================

@router.post("/player/register", response_model=PlayerProfileResponse)
def register_player(player_data: PlayerCreate, db: Session = Depends(get_db)):
    """
    Register new player (or Login if ID exists)
    """
    return vocab_service.register_or_get_player(db, player_data)

@router.get("/player/{player_id}", response_model=PlayerProfileResponse)
def get_player_profile(player_id: str, db: Session = Depends(get_db)):
    """
    Get profile data (for display in Menu)
    """
    return vocab_service.get_player_profile(db, player_id)

@router.post("/player/quest/update")
def update_quest_status(quest_data: QuestUpdate, db: Session = Depends(get_db)):
    """
    Unity calls this API when quest status changes (e.g., Accept/Complete quest)
    """
    return vocab_service.update_quest_status(db, quest_data)

@router.get("/player/{player_id}/npc_context", response_model=GameStateForNPC)
def get_npc_context(player_id: str, db: Session = Depends(get_db)):
    """
    Unity calls this -> Gets summary text -> Sends to NPC Service for context
    """
    return vocab_service.get_game_state_for_npc(db, player_id)