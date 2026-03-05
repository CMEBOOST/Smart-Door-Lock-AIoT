import httpx
import json
import os
from fastapi import APIRouter, HTTPException

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
#  Dashboard Logs
# ----------------------------------------------------------------
@router.get("/logs/access")
async def get_access_logs(limit: int = 30):
    """ดึงประวัติการเข้า-ออก"""
    try:
        logs = get_db().get_access_logs(limit)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/suspect")
async def get_suspect_logs(limit: int = 30):
    """ดึงประวัติเหตุการณ์ผิดปกติ"""
    try:
        logs = get_db().get_suspect_logs(limit)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))