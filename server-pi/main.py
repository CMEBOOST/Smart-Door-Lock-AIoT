import uvicorn
import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# นำเข้าโมดูลจัดการฐานข้อมูลและเส้นทาง API
try:
    from database.db_manager import DatabaseManager
    from api.routes import router as api_router
except ImportError as e:
    print(f"❌ Error: ไม่สามารถนำเข้าโมดูลได้: {e}")
    print("💡 ตรวจสอบว่ามีไฟล์ __init__.py ในโฟลเดอร์ api/ และ database/ หรือยัง")

def load_config():
    """โหลดค่าการตั้งค่าจากไฟล์ config.json พร้อมรองรับภาษาไทย"""
    config_path = "config.json"
    if not os.path.exists(config_path):
        # สร้างค่าเริ่มต้นหากไม่พบไฟล์
        default_config = {
            "server": {"host": "0.0.0.0", "port": 8000},
            "arduino": {"ip": "192.168.2.15", "api_secret": "boost_secure_key_2024"},
            "paths": {"database": "database/smart_lock.db"}
        }
        with open(config_path, "w", encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    
    with open(config_path, "r", encoding='utf-8') as f:
        return json.load(f)

# 1. โหลดการตั้งค่า
config = load_config()

# 2. เริ่มต้น FastAPI App
app = FastAPI(
    title="Smart Door Lock AIoT",
    description="ระบบควบคุมประตูอัจฉริยะผ่าน WiFi และหน้าเว็บ Dashboard",
    version="1.0.0"
)

# 3. ตั้งค่าความปลอดภัย CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. จัดการไฟล์หน้าเว็บ (Static Files)
# ตรวจสอบว่ามีโฟลเดอร์ public สำหรับเก็บหน้าเว็บ index.html หรือไม่
if not os.path.exists("public"):
    os.makedirs("public")

# สั่งให้ FastAPI สามารถเรียกใช้งานไฟล์ในโฟลเดอร์ public ได้ (เช่น CSS, JS, Images)
app.mount("/static", StaticFiles(directory="public"), name="static")

# 5. กำหนด Route สำหรับหน้าแรก (Dashboard)
@app.get("/")
async def read_index():
    """ส่งหน้า index.html ให้กับบราวเซอร์เมื่อเข้าที่ http://localhost:8000"""
    index_path = os.path.join("public", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "error", "message": "ไม่พบไฟล์ index.html ในโฟลเดอร์ public"}

# 6. ตรวจสอบสถานะฐานข้อมูลเมื่อเริ่มรันระบบ
@app.on_event("startup")
async def startup_event():
    db_path = config["paths"]["database"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    try:
        DatabaseManager(db_path)
        print("\n" + "="*60)
        print(f"📦 [Database] เชื่อมต่อสำเร็จ: {db_path}")
        print(f"📡 [Target] ส่งคำสั่งไปที่ Arduino IP: {config['arduino']['ip']}")
        print(f"🌐 [Web UI] เข้าใช้งานได้ที่: http://localhost:8000")
        print("="*60 + "\n")
    except Exception as e:
        print(f"❌ Database Error: {e}")

# 7. รวมเส้นทางคำสั่ง API (/api/unlock, /api/lock, /api/status)
app.include_router(api_router, prefix="/api", tags=["Control"])

# 8. สั่งให้ Server เริ่มทำงาน
if __name__ == "__main__":
    port = config["server"]["port"]
    host = config["server"]["host"]
    
    # รันด้วย Uvicorn พร้อมเปิดโหมด Reload
    uvicorn.run(
        "main:app", 
        host=host, 
        port=port, 
        reload=True
    )