import uvicorn
import json
import os
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

try:
    from database.db_manager import DatabaseManager
    from api.routes import router as api_router
    from core.face_processor import run as run_face_processor
    from core.sensor_manager import start_sensors, stop_sensors
except ImportError as e:
    print(f"❌ Error: {e}")
    print("💡 ตรวจสอบว่ามี __init__.py ในโฟลเดอร์ api/, database/, core/")


def load_config():
    config_path = "config.json"
    if not os.path.exists(config_path):
        default_config = {
            "server":  {"host": "0.0.0.0", "port": 8000},
            "arduino": {"ip": "192.168.2.15", "api_secret": "boost_secure_key_2024"},
            "paths":   {"database": "database/smart_lock.db"}
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# โหลด config
config = load_config()

# สร้าง FastAPI App
app = FastAPI(
    title="Smart Door Lock AIoT",
    description="ระบบควบคุมประตูอัจฉริยะผ่าน WiFi และหน้าเว็บ Dashboard",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
if not os.path.exists("public"):
    os.makedirs("public")
app.mount("/static", StaticFiles(directory="public"), name="static")


@app.get("/")
async def read_index():
    index_path = os.path.join("public", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "error", "message": "ไม่พบ index.html"}


@app.on_event("startup")
async def startup_event():
    db_path = config["paths"]["database"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    try:
        DatabaseManager(db_path)
        print("\n" + "="*60)
        print(f"📦 [Database]  เชื่อมต่อสำเร็จ: {db_path}")
        print(f"📡 [Arduino]   IP: {config['arduino']['ip']}")
        print(f"🌐 [Web UI]    http://localhost:8000")
        print("="*60 + "\n")
    except Exception as e:
        print(f"❌ Database Error: {e}")

    # เริ่ม Sensors (PIR, Ultrasonic, LCD, Buzzer)
    camera_event = start_sensors()

    # เริ่ม Face Processor — รอ PIR ก่อนค่อยประมวลผล
    threading.Thread(
        target=run_face_processor,
        args=(camera_event,),
        daemon=True
    ).start()
    print("🎥 [Camera] Face Processor พร้อมทำงาน (รอ PIR trigger)\n")


@app.on_event("shutdown")
async def shutdown_event():
    stop_sensors()
    print("👋 ระบบปิดเรียบร้อย")


# API routes
app.include_router(api_router, prefix="/api", tags=["Control"])


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config["server"]["host"],
        port=config["server"]["port"],
        reload=False  # ปิด reload เพราะมี thread กล้องทำงานอยู่
    )