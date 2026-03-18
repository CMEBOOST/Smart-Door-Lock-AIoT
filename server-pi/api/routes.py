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


@router.post("/stream/restart")
async def stream_restart():
    """Restart กล้องใหม่ทั้งหมด"""
    try:
        from core.face_processor import restart_camera
        restart_camera()
        return {"status": "restarting"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# ----------------------------------------------------------------
#  User Management
# ----------------------------------------------------------------
import base64
import shutil
from fastapi import Body

DATASET_DIR = os.path.join(BASE_DIR, "dataset")


@router.get("/users")
async def get_users():
    """ดึงรายชื่อ users ทั้งหมด + จำนวนรูป"""
    if not os.path.exists(DATASET_DIR):
        return {"users": []}
    users = []
    for name in sorted(os.listdir(DATASET_DIR)):
        folder = os.path.join(DATASET_DIR, name)
        if not os.path.isdir(folder):
            continue
        count = len([f for f in os.listdir(folder) if f.lower().endswith((".jpg",".jpeg",".png"))])
        users.append({"name": name, "images": count})
    return {"users": users}


@router.post("/users/capture")
async def capture_face(payload: dict = Body(...)):
    """
    รับรูปจาก browser (base64) บันทึกลง dataset/{name}/
    payload: { "name": "Somchai", "image": "data:image/jpeg;base64,..." }
    """
    name  = payload.get("name", "").strip()
    image = payload.get("image", "")

    if not name:
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อ")
    if not image:
        raise HTTPException(status_code=400, detail="ไม่มีรูปภาพ")

    # ตรวจ path traversal
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="ชื่อไม่ถูกต้อง")

    folder = os.path.join(DATASET_DIR, name)
    os.makedirs(folder, exist_ok=True)

    # แปลง base64 → jpg
    if "," in image:
        image = image.split(",")[1]
    img_bytes = base64.b64decode(image)

    # นับไฟล์ที่มีอยู่แล้ว
    existing = len([f for f in os.listdir(folder) if f.endswith(".jpg")])
    filename = os.path.join(folder, f"img_{existing+1:04d}.jpg")

    with open(filename, "wb") as f:
        f.write(img_bytes)

    return {"status": "saved", "name": name, "count": existing + 1, "path": filename}


@router.post("/users/train")
async def train_model():
    """Train model ใหม่และ reload โดยไม่ restart"""
    import asyncio
    try:
        # รัน train ใน thread แยก (ไม่ block event loop)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _do_train)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _do_train():
    from core.train import train
    from core.face_processor import reload_model
    result = train()
    reload_model()
    return result


@router.delete("/users/{name}")
async def delete_user(name: str):
    """ลบ user + dataset folder"""
    if ".." in name or "/" in name:
        raise HTTPException(status_code=400, detail="ชื่อไม่ถูกต้อง")

    folder = os.path.join(DATASET_DIR, name)
    if not os.path.exists(folder):
        raise HTTPException(status_code=404, detail=f"ไม่พบ user: {name}")

    shutil.rmtree(folder)

    # ลบออกจาก DB ด้วย
    try:
        conn = __import__('sqlite3').connect(os.path.join(BASE_DIR, "database", "smart_lock.db"))
        conn.execute("DELETE FROM users WHERE name = ?", (name,))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return {"status": "deleted", "name": name}