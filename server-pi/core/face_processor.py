"""
core/face_processor.py
ระบบตรวจจับและจดจำใบหน้า — เชื่อมกับ FastAPI (/api/unlock) → Arduino Relay
วางที่: server-pi/core/face_processor.py
"""

import cv2
import numpy as np
import time
import os
import json
import httpx
import threading
from datetime import datetime
from picamera2 import Picamera2

# ============================================================
#  PATH CONFIG
#    __file__       = .../server-pi/core/face_processor.py
#    SERVER_PI_DIR  = .../server-pi/
# ============================================================
SERVER_PI_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_PATH      = os.path.join(SERVER_PI_DIR, "storage", "trainer.yml")
NAMES_PATH      = os.path.join(SERVER_PI_DIR, "storage", "names.json")
SUSPECT_LOG_DIR = os.path.join(SERVER_PI_DIR, "storage", "log_captures")

# ============================================================
#  TUNING CONFIG
# ============================================================
CONFIDENCE_THRESHOLD = 50     # ต่ำกว่า = รู้จักหน้า | สูงกว่า = ไม่รู้จัก
SUSPECT_TIMEOUT      = 10     # วินาทีก่อนประกาศ SUSPECT
SAVE_COOLDOWN        = 5      # วินาทีขั้นต่ำระหว่างบันทึกรูป suspect
AUTO_LOCK_DELAY      = 10     # วินาทีแล้ว lock อัตโนมัติหลัง unlock
DETECT_SCALE         = 0.75   # ย่อภาพก่อน detect (ประหยัด CPU)
CAM_WIDTH, CAM_HEIGHT = 640, 480

FASTAPI_BASE = "http://localhost:8000/api"
# ============================================================


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def call_unlock():
    """เรียก /api/unlock แบบ non-blocking"""
    def _call():
        try:
            httpx.get(f"{FASTAPI_BASE}/unlock", timeout=5.0)
            print(f"[{_ts()}] ✅ UNLOCK → Arduino สำเร็จ")
        except Exception as e:
            print(f"[{_ts()}] ⚠️  UNLOCK failed: {e}")
    threading.Thread(target=_call, daemon=True).start()


def call_lock():
    """เรียก /api/lock แบบ non-blocking"""
    def _call():
        try:
            httpx.get(f"{FASTAPI_BASE}/lock", timeout=5.0)
            print(f"[{_ts()}] 🔒 LOCK → Arduino สำเร็จ")
        except Exception as e:
            print(f"[{_ts()}] ⚠️  LOCK failed: {e}")
    threading.Thread(target=_call, daemon=True).start()


# ----------------------------------------------------------------
#  FaceTracker — ติดตาม timer แยกต่อใบหน้า
# ----------------------------------------------------------------
class FaceTracker:

    def __init__(self):
        self._tracks: dict[int, dict] = {}
        self._next_id      = 0
        self._last_save_ts = 0.0
        self._unlock_sent: set[int] = set()
        self._lock_timer: threading.Timer | None = None

    def _iou(self, a, b) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        ix = max(0, min(ax+aw, bx+bw) - max(ax, bx))
        iy = max(0, min(ay+ah, by+bh) - max(ay, by))
        inter = ix * iy
        union = aw*ah + bw*bh - inter
        return inter / union if union > 0 else 0.0

    def _schedule_auto_lock(self):
        if self._lock_timer:
            self._lock_timer.cancel()
        self._lock_timer = threading.Timer(AUTO_LOCK_DELAY, call_lock)
        self._lock_timer.daemon = True
        self._lock_timer.start()

    def update(self, faces_info: list, names: list) -> list[dict]:
        now = time.time()
        results = []

        for (x, y, w, h), label_id, conf in faces_info:
            bbox = (x, y, w, h)

            # จับคู่กับ track เดิม (IoU)
            best_id, best_iou = None, 0.3
            for tid, track in self._tracks.items():
                iou = self._iou(bbox, track["bbox"])
                if iou > best_iou:
                    best_iou, best_id = iou, tid

            if best_id is not None:
                t = self._tracks[best_id]
                t["bbox"]       = bbox
                t["label_id"]   = label_id
                t["confidence"] = conf
                t["last_seen"]  = now
            else:
                best_id = self._next_id
                self._next_id += 1
                self._tracks[best_id] = dict(
                    bbox=bbox, label_id=label_id, confidence=conf,
                    first_seen=now, last_seen=now
                )

            t       = self._tracks[best_id]
            elapsed = now - t["first_seen"]
            name    = names[label_id] if label_id < len(names) else "Unknown"

            # ---- ตัดสินสถานะ ----
            if conf < CONFIDENCE_THRESHOLD:
                status, color = "WELCOME", (0, 255, 0)
                t["first_seen"] = now  # reset suspect timer

                # ส่ง unlock ครั้งแรกที่รู้จัก
                if best_id not in self._unlock_sent:
                    print(f"[{_ts()}] 👤 รู้จัก: {name} (conf={conf:.0f}) → UNLOCK")
                    call_unlock()
                    self._schedule_auto_lock()
                    self._unlock_sent.add(best_id)

            elif elapsed > SUSPECT_TIMEOUT:
                status, color = "SUSPECT", (0, 0, 255)

            else:
                status, color = "SCANNING", (0, 220, 255)
                self._unlock_sent.discard(best_id)

            results.append(dict(
                tid=best_id, bbox=bbox, label_id=label_id,
                name=name, confidence=conf,
                elapsed=elapsed, status=status, color=color
            ))

        # ลบ track ที่หายไปนานกว่า 2 วินาที
        dead = [tid for tid, t in self._tracks.items()
                if now - t["last_seen"] > 2.0]
        for tid in dead:
            self._tracks.pop(tid, None)
            self._unlock_sent.discard(tid)

        return results

    def can_save(self) -> bool:
        return time.time() - self._last_save_ts > SAVE_COOLDOWN

    def mark_saved(self):
        self._last_save_ts = time.time()


# ----------------------------------------------------------------
#  Draw Overlay
# ----------------------------------------------------------------
def draw_overlay(frame, track: dict):
    x, y, w, h = track["bbox"]
    color       = track["color"]
    status      = track["status"]
    name        = track["name"]
    conf        = track["confidence"]

    if status == "WELCOME":
        label = f"WELCOME  {name}"
    elif status == "SUSPECT":
        label = "!!! SUSPECT !!!"
    else:
        remaining = max(0, SUSPECT_TIMEOUT - track["elapsed"])
        label = f"Scanning... {remaining:.0f}s"

    cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
    cv2.putText(frame, f"{label}  [{conf:.0f}]",
                (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


# ----------------------------------------------------------------
#  Main Loop
# ----------------------------------------------------------------
def run():
    os.makedirs(SUSPECT_LOG_DIR, exist_ok=True)

    # ตรวจสอบ model
    if not os.path.exists(MODEL_PATH):
        print(f"❌ ไม่พบ model: {MODEL_PATH}")
        print("   → รัน: python core/train.py ก่อน")
        return
    if not os.path.exists(NAMES_PATH):
        print(f"❌ ไม่พบ names.json: {NAMES_PATH}")
        return

    # โหลด model
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(MODEL_PATH)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    with open(NAMES_PATH, "r", encoding="utf-8") as f:
        nd = json.load(f)
    names = [nd[str(i)] for i in range(len(nd))]

    print(f"✅ โหลด model สำเร็จ | รู้จัก {len(names)} คน: {names}")

    # กล้อง
    picam2 = Picamera2()
    cfg = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (CAM_WIDTH, CAM_HEIGHT)}
    )
    picam2.configure(cfg)
    picam2.start()

    tracker   = FaceTracker()
    prev_time = time.time()
    inv       = 1.0 / DETECT_SCALE

    print("🎥 Face Processor พร้อมทำงาน — กด 'q' เพื่อออก\n")

    try:
        while True:
            frame   = picam2.capture_array()
            frame   = cv2.flip(frame, 1)
            display = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            gray    = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

            # Detect (ภาพย่อเพื่อความเร็ว)
            small = cv2.resize(gray, (0, 0), fx=DETECT_SCALE, fy=DETECT_SCALE)
            raws  = face_cascade.detectMultiScale(
                small, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20)
            )

            faces_info = []
            for (xs, ys, ws, hs) in (raws if len(raws) > 0 else []):
                x, y = int(xs * inv), int(ys * inv)
                w, h = int(ws * inv), int(hs * inv)
                roi  = gray[y:y+h, x:x+w]   # predict จาก gray เต็มขนาด (ถูกต้อง)
                if roi.size == 0:
                    continue
                label_id, conf = recognizer.predict(roi)
                faces_info.append(((x, y, w, h), label_id, conf))

            # Track + วาด
            tracks = tracker.update(faces_info, names)

            for track in tracks:
                draw_overlay(display, track)

                # บันทึกรูป suspect
                if track["status"] == "SUSPECT" and tracker.can_save():
                    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    path   = os.path.join(
                        SUSPECT_LOG_DIR,
                        f"suspect_{ts_str}_{track['tid']}.jpg"
                    )
                    cv2.imwrite(path, display)
                    tracker.mark_saved()
                    print(f"[{_ts()}] ⚠️  บันทึกรูป suspect → {path}")

            # FPS
            curr_time = time.time()
            fps       = 1.0 / max(curr_time - prev_time, 1e-6)
            prev_time = curr_time
            cv2.putText(
                display,
                f"FPS: {fps:.0f} | Faces: {len(tracks)}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2
            )

            cv2.imshow("Smart Door Guard", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        picam2.stop()
        cv2.destroyAllWindows()
        print("👋 ปิดระบบเรียบร้อย")


if __name__ == "__main__":
    run()