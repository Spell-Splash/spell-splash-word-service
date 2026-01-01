from fastapi import FastAPI
from database import engine, Base
from routers import vocab_router


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Spell Splash Word Service")

# รวม Router
app.include_router(vocab_router.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Spell Splash API!"}