"""
core/face_processor.py
Logic:
  รู้จักหน้า       → WELCOME + Unlock + Lock 10s + log DB
  ไม่รู้จักหน้า    → นับเวลา 10s → SUSPECT + notify_suspect + log DB
  ไม่มีคน 20s     → กล้องสลีป + ปิด window รอ PIR
"""

import cv2
import time
import os
import json
import httpx
import threading
from datetime import datetime
from picamera2 import Picamera2

from core.sensor_manager import notify_welcome, notify_locked, notify_suspect
from database.db_manager import DatabaseManager

SERVER_PI_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH      = os.path.join(SERVER_PI_DIR, "storage", "trainer.yml")
NAMES_PATH      = os.path.join(SERVER_PI_DIR, "storage", "names.json")
SUSPECT_LOG_DIR = os.path.join(SERVER_PI_DIR, "storage", "log_captures")
DB_PATH         = os.path.join(SERVER_PI_DIR, "database", "smart_lock.db")

# ============================================================
#  CONFIG
# ============================================================
CONFIDENCE_THRESHOLD  = 50
AUTO_LOCK_DELAY       = 10
UNKNOWN_TIMEOUT       = 10
DETECT_SCALE          = 0.75
CAM_WIDTH, CAM_HEIGHT = 640, 480
FASTAPI_BASE          = "http://localhost:8000/api"
WINDOW_NAME           = "Smart Door Guard"
# ============================================================

db = DatabaseManager(DB_PATH)


def _ts():
    return datetime.now().strftime("%H:%M:%S")


def call_unlock():
    def _call():
        for attempt in range(3):
            try:
                r = httpx.get(f"{FASTAPI_BASE}/unlock", timeout=8.0)
                if r.status_code == 200:
                    print(f"[{_ts()}] ✅ UNLOCK สำเร็จ")
                    db.log_access("UNLOCK")
                    # อัปเดตสถานะ Arduino
                    db.update_device_status("arduino_nano33", True)
                    return
            except Exception as e:
                print(f"[{_ts()}] ⚠️  UNLOCK attempt {attempt+1}: {e}")
                db.update_device_status("arduino_nano33", False)
            time.sleep(1)
    threading.Thread(target=_call, daemon=True).start()


def call_lock():
    def _call():
        for attempt in range(3):
            try:
                r = httpx.get(f"{FASTAPI_BASE}/lock", timeout=8.0)
                if r.status_code == 200:
                    print(f"[{_ts()}] 🔒 LOCK สำเร็จ")
                    db.log_access("LOCK")
                    notify_locked()
                    return
            except Exception as e:
                print(f"[{_ts()}] ⚠️  LOCK attempt {attempt+1}: {e}")
            time.sleep(1)
    threading.Thread(target=_call, daemon=True).start()


def schedule_auto_lock():
    t = threading.Timer(AUTO_LOCK_DELAY, call_lock)
    t.daemon = True
    t.start()


# ----------------------------------------------------------------
#  FaceTracker
# ----------------------------------------------------------------
class FaceTracker:
    def __init__(self):
        self._tracks       = {}
        self._next_id      = 0
        self._last_save    = 0.0
        self._unlock_sent  = set()
        self._suspect_sent = set()

    def _iou(self, a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        ix = max(0, min(ax+aw, bx+bw) - max(ax, bx))
        iy = max(0, min(ay+ah, by+bh) - max(ay, by))
        inter = ix * iy
        union = aw*ah + bw*bh - inter
        return inter / union if union > 0 else 0.0

    def update(self, faces_info, names):
        now     = time.time()
        results = []

        for (x, y, w, h), label_id, conf in faces_info:
            bbox = (x, y, w, h)

            best_id, best_iou = None, 0.3
            for tid, t in self._tracks.items():
                iou = self._iou(bbox, t["bbox"])
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
                    first_seen=now, last_seen=now,
                    unknown_since=None
                )

            t    = self._tracks[best_id]
            name = names[label_id] if label_id < len(names) else "Unknown"

            # ---- ตัดสินสถานะ ----
            if conf < CONFIDENCE_THRESHOLD:
                # ✅ รู้จักหน้า
                status, color      = "WELCOME", (0, 255, 0)
                t["unknown_since"] = None
                self._suspect_sent.discard(best_id)

                if best_id not in self._unlock_sent:
                    print(f"[{_ts()}] 👤 รู้จัก: {name} (conf={conf:.0f}) → UNLOCK")
                    # log WELCOME ลง DB
                    db.log_access("WELCOME", name=name, confidence=conf)
                    # เพิ่ม user ถ้ายังไม่มีใน DB
                    db.add_user(name)
                    call_unlock()
                    notify_welcome(name)
                    schedule_auto_lock()
                    self._unlock_sent.add(best_id)

            else:
                # ❌ ไม่รู้จักหน้า
                self._unlock_sent.discard(best_id)

                if t["unknown_since"] is None:
                    t["unknown_since"] = now
                    print(f"[{_ts()}] 👀 เจอหน้าไม่รู้จัก — เริ่มนับ {UNKNOWN_TIMEOUT}s")
                    db.log_access("UNKNOWN", confidence=conf)

                unknown_elapsed = now - t["unknown_since"]
                remaining       = max(0, UNKNOWN_TIMEOUT - unknown_elapsed)

                if unknown_elapsed >= UNKNOWN_TIMEOUT:
                    status, color = "SUSPECT", (0, 0, 255)
                    if best_id not in self._suspect_sent:
                        print(f"[{_ts()}] ⚠️  SUSPECT confirmed หลัง {UNKNOWN_TIMEOUT}s")
                        notify_suspect()
                        self._suspect_sent.add(best_id)
                else:
                    status = f"UNKNOWN {remaining:.0f}s"
                    color  = (0, 165, 255)

            results.append(dict(
                tid=best_id, bbox=bbox, label_id=label_id,
                name=name, confidence=conf,
                status=status, color=color
            ))

        # ลบ track เก่า
        dead = [tid for tid, t in self._tracks.items()
                if now - t["last_seen"] > 2.0]
        for tid in dead:
            self._tracks.pop(tid, None)
            self._unlock_sent.discard(tid)
            self._suspect_sent.discard(tid)

        return results

    def can_save(self):
        return time.time() - self._last_save > 5.0

    def mark_saved(self):
        self._last_save = time.time()

    def reset(self):
        self._tracks.clear()
        self._unlock_sent.clear()
        self._suspect_sent.clear()


# ----------------------------------------------------------------
#  Draw Overlay
# ----------------------------------------------------------------
def draw_overlay(frame, track):
    x, y, w, h = track["bbox"]
    color       = track["color"]
    status      = track["status"]
    name        = track["name"]
    conf        = track["confidence"]

    if status == "WELCOME":
        label = f"WELCOME {name}"
    elif status == "SUSPECT":
        label = "!!! SUSPECT !!!"
    else:
        label = f"{status} [{conf:.0f}]"

    cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
    cv2.putText(frame, label, (x, y-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


# ----------------------------------------------------------------
#  Main Loop
# ----------------------------------------------------------------
def run(camera_event=None):
    os.makedirs(SUSPECT_LOG_DIR, exist_ok=True)

    if not os.path.exists(MODEL_PATH):
        print(f"❌ ไม่พบ model → รัน train.py ก่อน")
        return
    if not os.path.exists(NAMES_PATH):
        print(f"❌ ไม่พบ names.json")
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(MODEL_PATH)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    with open(NAMES_PATH, "r", encoding="utf-8") as f:
        nd = json.load(f)
    names = [nd[str(i)] for i in range(len(nd))]
    print(f"✅ โหลด model | รู้จัก {len(names)} คน: {names}")

    picam2 = Picamera2()
    cfg    = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (CAM_WIDTH, CAM_HEIGHT)}
    )
    picam2.configure(cfg)
    picam2.start()

    tracker     = FaceTracker()
    prev_time   = time.time()
    inv         = 1.0 / DETECT_SCALE
    window_open = False

    print("🎥 Face Processor พร้อม — รอ PIR trigger")

    try:
        while True:
            # ---- กล้องสลีป: รอ PIR ----
            if camera_event and not camera_event.is_set():
                if window_open:
                    cv2.destroyWindow(WINDOW_NAME)
                    window_open = False
                    tracker.reset()
                    print(f"[{_ts()}] 🪟 ปิด window — รอ PIR")
                time.sleep(0.2)
                continue

            # ---- กล้องทำงาน ----
            frame   = picam2.capture_array()
            frame   = cv2.flip(frame, 1)
            display = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            gray    = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

            small = cv2.resize(gray, (0, 0), fx=DETECT_SCALE, fy=DETECT_SCALE)
            raws  = face_cascade.detectMultiScale(
                small, 1.1, 5, minSize=(20, 20)
            )

            faces_info = []
            for (xs, ys, ws, hs) in (raws if len(raws) > 0 else []):
                x, y = int(xs*inv), int(ys*inv)
                w, h = int(ws*inv), int(hs*inv)
                roi  = gray[y:y+h, x:x+w]
                if roi.size == 0:
                    continue
                label_id, conf = recognizer.predict(roi)
                faces_info.append(((x, y, w, h), label_id, conf))

            tracks = tracker.update(faces_info, names)

            for track in tracks:
                draw_overlay(display, track)

                # บันทึกรูป + log DB เมื่อเป็น SUSPECT
                if track["status"] == "SUSPECT" and tracker.can_save():
                    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    path   = os.path.join(
                        SUSPECT_LOG_DIR,
                        f"suspect_{ts_str}_{track['tid']}.jpg"
                    )
                    cv2.imwrite(path, display)
                    tracker.mark_saved()
                    print(f"[{_ts()}] 📸 บันทึกรูป suspect → {path}")
                    # log ลง suspect_logs
                    db.log_suspect(
                        trigger_type="FACE_UNKNOWN",
                        image_path=path,
                        buzzer_fired=True
                    )

            # FPS
            curr_time = time.time()
            fps       = 1.0 / max(curr_time - prev_time, 1e-6)
            prev_time = curr_time
            cv2.putText(display, f"FPS:{fps:.0f} Faces:{len(tracks)}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

            cv2.imshow(WINDOW_NAME, display)
            window_open = True

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        picam2.stop()
        cv2.destroyAllWindows()
        print("👋 ปิดระบบ")