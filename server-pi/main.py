import uvicorn
import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# นำเข้าโมดูลจัดการฐานข้อมูลและเส้นทาง API ที่เราออกแบบไว้
# ตรวจสอบให้แน่ใจว่าในโฟลเดอร์ api และ database มีไฟล์ __init__.py อยู่ด้วย
try:
    from database.db_manager import DatabaseManager
    from api.routes import router as api_router
except ImportError as e:
    print(f"❌ Error: ไม่สามารถนำเข้าโมดูลได้: {e}")
    print("💡 วิธีแก้: ตรวจสอบว่ามีไฟล์ __init__.py ในโฟลเดอร์ api/ และ database/ หรือยัง")

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
        # บันทึกไฟล์เป็น UTF-8 เพื่อป้องกัน Error บน Windows
        with open(config_path, "w", encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    
    # อ่านไฟล์ด้วย UTF-8
    with open(config_path, "r", encoding='utf-8') as f:
        return json.load(f)

# 1. โหลด Configuration
config = load_config()

# 2. เริ่มต้น FastAPI App
app = FastAPI(
    title="Smart Door Lock Controller",
    description="ระบบควบคุมเปิด-ปิดผ่าน WiFi (Manual Mode)",
    version="1.0.0"
)

# 3. ตั้งค่า CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. ตรวจสอบสถานะฐานข้อมูลเมื่อเริ่มรันระบบ
@app.on_event("startup")
async def startup_event():
    db_path = config["paths"]["database"]
    # ตรวจสอบว่าโฟลเดอร์เก็บ DB มีอยู่จริงไหม
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    try:
        # เรียกใช้ DatabaseManager (ตัวที่แก้ไข encoding ใน db_manager.py แล้ว)
        DatabaseManager(db_path)
        print("\n" + "="*50)
        print(f"📦 [Database] เชื่อมต่อสำเร็จ: {db_path}")
        print(f"📡 [Target] พร้อมส่งคำสั่งไปที่ Arduino IP: {config['arduino']['ip']}")
        print("="*50 + "\n")
    except Exception as e:
        print(f"❌ Database Error: {e}")

# 5. รวมเส้นทางคำสั่งจากไฟล์ api/routes.py
app.include_router(api_router, prefix="/api", tags=["Control"])

# 6. หน้าแสดงสถานะระบบ (Root Endpoint)
@app.get("/")
async def root():
    return {
        "status": "online",
        "mode": "Manual Control",
        "arduino_ip": config["arduino"]["ip"],
        "endpoints": {
            "turn_on_led": "/api/unlock",
            "turn_off_led": "/api/lock",
            "check_status": "/api/status"
        }
    }

# 7. สั่งรัน Server
if __name__ == "__main__":
    port = config["server"]["port"]
    host = config["server"]["host"]
    
    print(f"🚀 เซิร์ฟเวอร์กำลังเริ่มต้นที่ http://localhost:{port}")
    
    # รันด้วย Uvicorn และเปิดโหมด Reload เพื่อความสะดวกในการพัฒนา
    uvicorn.run(
        "main:app", 
        host=host, 
        port=port, 
        reload=True
    )