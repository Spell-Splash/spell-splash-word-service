from sqlalchemy import Column, Integer, String, Text
from database import Base

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