import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import vocab_router

# สร้างตารางใน Database (ถ้ายังไม่มี)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Spell Splash Word Service")

# ---------------------------------------------------------
# 1. CORS Setup (สำคัญมากสำหรับการเชื่อมต่อกับ Frontend/Unity)
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # อนุญาตทุก Domain (ใน Production ควรเปลี่ยนเป็น Domain ของเกม)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# 2. Static Files Setup (เพื่อให้เล่นไฟล์เสียงได้)
# ---------------------------------------------------------
# เช็คก่อนว่ามีโฟลเดอร์ static/audio หรือไม่ ถ้าไม่มีให้สร้าง (กัน Server Error)
static_dir = "static"
audio_dir = os.path.join(static_dir, "audio")

if not os.path.exists(audio_dir):
    os.makedirs(audio_dir)
    print(f"📁 Created directory: {audio_dir}")

# Mount โฟลเดอร์: เมื่อเรียก URL /static/... ให้ไปดึงไฟล์จากโฟลเดอร์ static ในเครื่อง
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ---------------------------------------------------------
# 3. Router Setup
# ---------------------------------------------------------
app.include_router(vocab_router.router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to Spell Splash API!",
        "status": "ready",
        "static_url_example": "/static/audio/test.mp3"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)