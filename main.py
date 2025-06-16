from fastapi import FastAPI, HTTPException
from typing import List
import pandas as pd
import random

app = FastAPI()

# Load the dataset
word_df = pd.read_csv("data/oxford_words_cefr_pos.csv")

# Normalize case for lookup
word_df['Word_lower'] = word_df['Word'].str.lower()

@app.get("/words/by-difficulty/{cefr_level}", response_model=List[str])
def get_words_by_difficulty(cefr_level: str):
    filtered = word_df[word_df['CEFR'].str.upper() == cefr_level.upper()]
    if filtered.empty:
        raise HTTPException(status_code=404, detail="No words found for this CEFR level.")
    return filtered['Word'].tolist()

@app.get("/words/random", response_model=str)
def get_random_word():
    return random.choice(word_df['Word'].tolist())

@app.get("/pos/by-word/{word}", response_model=str)
def get_pos_by_word(word: str):
    matches = word_df[word_df['Word_lower'] == word.lower()]
    if matches.empty:
        raise HTTPException(status_code=404, detail="Word not found.")
    return matches.iloc[0]['POS']

@app.get("/pos/random", response_model=dict)
def get_random_word_with_pos():
    row = word_df.sample(n=1).iloc[0]
    return {"word": row['Word'], "pos": row['POS']}

# Optional root endpoint
@app.get("/")
def root():
    return {"message": "Oxford Word API - Endpoints: /words/by-difficulty/{CEFR}, /words/random, /pos/by-word/{word}, /pos/random"}
