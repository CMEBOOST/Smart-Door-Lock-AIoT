import httpx
import json
import os
from fastapi import APIRouter, HTTPException

router = APIRouter()

def get_arduino_config():
    """ดึงค่า IP ของ Arduino จาก config.json"""
    # ใช้ path แบบอ้างอิงจากตำแหน่งไฟล์ปัจจุบัน
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.json")
    
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("arduino", {})
    return {}

@router.get("/unlock")
async def turn_on_led():
    """ส่งคำสั่งไปที่ Arduino เพื่อเปิดไฟ LED"""
    arduino_config = get_arduino_config()
    target_ip = arduino_config.get("ip")
    
    if not target_ip:
        raise HTTPException(status_code=500, detail="ไม่พบ IP ของ Arduino ในระบบ")

    arduino_url = f"http://{target_ip}/unlock"
    
    try:
        async with httpx.AsyncClient() as client:
            # ส่งคำสั่ง GET ไปยัง Arduino
            response = await client.get(arduino_url, timeout=5.0)
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "action": "LED ON",
                    "arduino_reply": response.json()
                }
            else:
                return {"status": "error", "message": f"Arduino error: {response.status_code}"}
                
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ไม่สามารถติดต่อ Arduino ได้: {str(e)}")

@router.get("/lock")
async def turn_off_led():
    """ส่งคำสั่งไปที่ Arduino เพื่อปิดไฟ LED"""
    arduino_config = get_arduino_config()
    target_ip = arduino_config.get("ip")
    
    if not target_ip:
        raise HTTPException(status_code=500, detail="ไม่พบ IP ของ Arduino ในระบบ")

    arduino_url = f"http://{target_ip}/lock"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(arduino_url, timeout=5.0)
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "action": "LED OFF",
                    "arduino_reply": response.json()
                }
            else:
                return {"status": "error", "message": f"Arduino error: {response.status_code}"}
                
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ไม่สามารถติดต่อ Arduino ได้: {str(e)}")

@router.get("/status")
async def check_arduino_status():
    """เช็คว่า Arduino ยังออนไลน์อยู่ไหม"""
    arduino_config = get_arduino_config()
    target_ip = arduino_config.get("ip")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{target_ip}/ping", timeout=2.0)
            return {"arduino_online": response.status_code == 200}
    except:
        return {"arduino_online": False}