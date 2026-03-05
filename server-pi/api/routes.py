import httpx
import json
import os
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse

router = APIRouter()

BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUSPECT_LOG_DIR = os.path.join(BASE_DIR, "storage", "log_captures")


def get_arduino_config():
    config_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f).get("arduino", {})
    return {}


def get_headers():
    config = get_arduino_config()
    return {"X-API-Key": config.get("api_secret", "")}


def get_db():
    from database.db_manager import DatabaseManager
    db_path = os.path.join(BASE_DIR, "database", "smart_lock.db")
    return DatabaseManager(db_path)


# ----------------------------------------------------------------
#  Door Control
# ----------------------------------------------------------------
@router.get("/unlock")
async def unlock():
    config = get_arduino_config()
    ip = config.get("ip")
    if not ip:
        raise HTTPException(status_code=500, detail="ไม่พบ IP ของ Arduino")
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"http://{ip}/unlock", headers=get_headers(), timeout=5.0
            )
            if res.status_code == 200:
                get_db().update_device_status("arduino_nano33", True, ip)
                return {"status": "success", "action": "UNLOCKED", "arduino_reply": res.json()}
            elif res.status_code == 401:
                raise HTTPException(status_code=401, detail="API Secret ไม่ถูกต้อง")
            else:
                return {"status": "error", "message": f"Arduino error: {res.status_code}"}
    except HTTPException:
        raise
    except Exception as e:
        get_db().update_device_status("arduino_nano33", False)
        raise HTTPException(status_code=503, detail=f"ติดต่อ Arduino ไม่ได้: {str(e)}")


@router.get("/lock")
async def lock():
    config = get_arduino_config()
    ip = config.get("ip")
    if not ip:
        raise HTTPException(status_code=500, detail="ไม่พบ IP ของ Arduino")
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"http://{ip}/lock", headers=get_headers(), timeout=5.0
            )
            if res.status_code == 200:
                get_db().update_device_status("arduino_nano33", True, ip)
                return {"status": "success", "action": "LOCKED", "arduino_reply": res.json()}
            elif res.status_code == 401:
                raise HTTPException(status_code=401, detail="API Secret ไม่ถูกต้อง")
            else:
                return {"status": "error", "message": f"Arduino error: {res.status_code}"}
    except HTTPException:
        raise
    except Exception as e:
        get_db().update_device_status("arduino_nano33", False)
        raise HTTPException(status_code=503, detail=f"ติดต่อ Arduino ไม่ได้: {str(e)}")


@router.get("/status")
async def status():
    config = get_arduino_config()
    ip = config.get("ip")
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"http://{ip}/ping", headers=get_headers(), timeout=2.0
            )
            online = res.status_code == 200
            get_db().update_device_status("arduino_nano33", online, ip)
            return {"arduino_online": online}
    except Exception:
        get_db().update_device_status("arduino_nano33", False)
        return {"arduino_online": False}


# ----------------------------------------------------------------
#  Buzzer
# ----------------------------------------------------------------
@router.get("/buzzer")
async def trigger_buzzer():
    """สั่ง buzzer ดังจาก Dashboard"""
    try:
        from core.sensor_manager import manual_buzz
        manual_buzz()
        return {"status": "success", "action": "BUZZER_ON"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------
#  Dashboard Logs
# ----------------------------------------------------------------
@router.get("/logs/access")
async def get_access_logs(limit: int = 30):
    try:
        return {"logs": get_db().get_access_logs(limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/suspect")
async def get_suspect_logs(limit: int = 30):
    try:
        return {"logs": get_db().get_suspect_logs(limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------
#  Suspect Images
# ----------------------------------------------------------------
@router.get("/suspects/images")
async def get_suspect_images():
    """ดึงรายการไฟล์รูป suspect ทั้งหมด เรียงจากใหม่ไปเก่า"""
    if not os.path.exists(SUSPECT_LOG_DIR):
        return {"images": []}
    files = sorted(
        [f for f in os.listdir(SUSPECT_LOG_DIR) if f.endswith(".jpg")],
        reverse=True  # ใหม่สุดก่อน
    )
    return {"images": [{"filename": f, "url": f"/api/suspects/image/{f}"} for f in files]}


@router.get("/suspects/image/{filename}")
async def get_suspect_image(filename: str):
    """ส่งไฟล์รูป suspect"""
    # ป้องกัน path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(SUSPECT_LOG_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="ไม่พบรูปภาพ")
    return FileResponse(path, media_type="image/jpeg")


@router.delete("/suspects/image/{filename}")
async def delete_suspect_image(filename: str):
    """ลบรูป suspect"""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(SUSPECT_LOG_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="ไม่พบรูปภาพ")
    os.remove(path)
    return {"status": "deleted", "filename": filename}


# ----------------------------------------------------------------
#  MJPEG Stream
# ----------------------------------------------------------------
from core.face_processor import get_latest_frame


async def _mjpeg_generator():
    while True:
        frame, active = get_latest_frame()
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame +
                b"\r\n"
            )
        await asyncio.sleep(0.04)


@router.get("/stream")
async def video_stream():
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )