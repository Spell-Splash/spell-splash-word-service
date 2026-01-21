from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


# --- 1. Master Data คำศัพท์ ---
class Vocabulary(Base):
    __tablename__ = "vocabulary"

    vocab_id = Column(Integer, primary_key=True, index=True)    
    word = Column(String(100), nullable=False)    
    meaning = Column(String(255), nullable=False)     
    definition = Column(Text)    
    definition_en = Column(Text, nullable=True)    
    part_of_speech = Column(String(50))    
    cefr_level = Column(String(10), index=True)    
    phonetic_transcription = Column(String(100))
    audio_cache_path = Column(String(255), nullable=True)

# --- 2. Player Data ---
class Player(Base):
    __tablename__ = "players"

    player_id = Column(String(50), primary_key=True) # ID จาก Unity (เช่น UUID)
    username = Column(String(100), nullable=True)    # ชื่อตัวละคร
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    quests = relationship("PlayerQuest", back_populates="player")

class PlayerQuest(Base):
    __tablename__ = "player_quests"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(String(50), ForeignKey("players.player_id"))
    quest_id = Column(String(50), nullable=False) 
    status = Column(String(20), default="NOT_STARTED") 
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    player = relationship("Player", back_populates="quests")