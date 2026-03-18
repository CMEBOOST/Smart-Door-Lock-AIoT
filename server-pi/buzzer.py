"""
core/sensor_manager.py
รวม PIR + Ultrasonic + Buzzer
(ไม่มี LCD)
"""

import threading
import time
from datetime import datetime

from core.pir        import PIRSensor
from core.ultrasonic import UltrasonicSensor
from database.db_manager import DatabaseManager

import RPi.GPIO as GPIO

# ============================================================
#  CONFIG
# ============================================================
BUZZER_PIN        = 27
NO_PERSON_TIMEOUT = 20
BUZZER_DURATION   = 10
BEEP_FREQ         = 2500   # Hz — ความถี่เสียง (ปรับได้)
BEEP_SPEED        = 0.3    # วินาที — ความเร็ว beep (ปรับได้)
DB_PATH           = "database/smart_lock.db"
# ============================================================

db  = DatabaseManager(DB_PATH)
_pir        = None
_ultrasonic = None

camera_active = threading.Event()


class SystemState:
    def __init__(self):
        self.lock             = threading.Lock()
        self.person_near      = False
        self.near_since       = None
        self.last_person_time = None
        self.buzzer_active    = False
        self.face_recognized  = False

state = SystemState()


def _ts():
    return datetime.now().strftime("%H:%M:%S")


# ----------------------------------------------------------------
#  Buzzer (Passive — PWM)
# ----------------------------------------------------------------
_buzzer_pwm = None


def _setup_buzzer():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    global _buzzer_pwm
    _buzzer_pwm = GPIO.PWM(BUZZER_PIN, BEEP_FREQ)


def _beep_suspect():
    """PWM beep ต่อเนื่อง ตอนเจอ Suspect"""
    def _run():
        with state.lock:
            if state.buzzer_active:
                return
            state.buzzer_active = True

        print(f"[{_ts()}] 🔔 Buzzer เริ่มดัง {BUZZER_DURATION}s")
        end_time = time.time() + BUZZER_DURATION
        try:
            while time.time() < end_time:
                print('beep')
                _buzzer_pwm.start(50)
                time.sleep(BEEP_SPEED)
                _buzzer_pwm.stop()
                time.sleep(BEEP_SPEED)
        finally:
            _buzzer_pwm.stop()
            with state.lock:
                state.buzzer_active = False
            print(f"[{_ts()}] 🔕 Buzzer หยุด")

    threading.Thread(target=_run, daemon=True).start()


def _buzz(duration: float = BUZZER_DURATION):
    """Manual buzz จาก Dashboard — PWM"""
    def _run():
        with state.lock:
            if state.buzzer_active:
                return
            state.buzzer_active = True

        print(f"[{_ts()}] 🔔 Manual Buzzer {duration}s")
        end_time = time.time() + duration
        try:
            while time.time() < end_time:
                _buzzer_pwm.start(50)
                time.sleep(BEEP_SPEED)
                _buzzer_pwm.stop()
                time.sleep(BEEP_SPEED)
        finally:
            _buzzer_pwm.stop()
            with state.lock:
                state.buzzer_active = False

    threading.Thread(target=_run, daemon=True).start()


# ----------------------------------------------------------------
#  PIR Callbacks
# ----------------------------------------------------------------
def _on_pir_detected():
    print(f"[{_ts()}] 🚶 PIR เจอคน → เปิดกล้อง")
    camera_active.set()


def _on_pir_inactive():
    print(f"[{_ts()}] 😴 ไม่มีการเคลื่อนไหว → ปิดกล้อง")
    camera_active.clear()
    with state.lock:
        state.face_recognized = False
        state.person_near     = False
        state.near_since      = None


# ----------------------------------------------------------------
#  Ultrasonic Callbacks
# ----------------------------------------------------------------
def _on_person_near(distance: float):
    with state.lock:
        if not state.person_near:
            state.person_near = True
            state.near_since  = time.time()
            print(f"[{_ts()}] 📏 คนอยู่ใกล้ {distance}cm — เริ่มจับเวลา")
        state.last_person_time = time.time()

        elapsed = time.time() - state.near_since
        if elapsed >= NO_PERSON_TIMEOUT and not state.face_recognized:
            _trigger_suspect(distance=distance, duration=elapsed)


def _on_person_gone():
    with state.lock:
        was_near          = state.person_near
        state.person_near = False
        state.near_since  = None
    if was_near:
        print(f"[{_ts()}] ✅ ไม่มีคนแล้ว")


# ----------------------------------------------------------------
#  Suspect Logic
# ----------------------------------------------------------------
def _trigger_suspect(distance: float = None, duration: float = None):
    with state.lock:
        if state.buzzer_active:
            return

    print(f"[{_ts()}] ⚠️  SUSPECT — งัดแงะ!")
    _beep_suspect()   # beep 3 ครั้ง

    db.log_suspect(
        trigger_type="ULTRASONIC_LOITER",
        duration_sec=duration,
        distance_cm=distance,
        buzzer_fired=True
    )


# ----------------------------------------------------------------
#  Public API
# ----------------------------------------------------------------
def manual_buzz(duration: float = BUZZER_DURATION):
    """Dashboard เรียกเพื่อสั่ง buzzer ดังด้วยมือ"""
    print(f"[{_ts()}] 🔔 Manual buzzer จาก Dashboard")
    _buzz(duration)


def notify_welcome(name: str):
    with state.lock:
        state.face_recognized = True
    print(f"[{_ts()}] 👤 WELCOME: {name}")
    # ไม่มีเสียงตอนเปิดประตู


def notify_locked():
    with state.lock:
        state.face_recognized = False


def notify_suspect():
    """face_processor เรียกเมื่อ FACE_UNKNOWN ครบเวลา"""
    _trigger_suspect()


# ----------------------------------------------------------------
#  Start / Stop
# ----------------------------------------------------------------
def start_sensors():
    global _pir, _ultrasonic

    _setup_buzzer()

    _pir = PIRSensor()
    _pir.on_motion(_on_pir_detected).on_inactive(_on_pir_inactive).start()

    _ultrasonic = UltrasonicSensor()
    _ultrasonic.on_person_near(_on_person_near)
    _ultrasonic.on_person_gone(_on_person_gone)
    _ultrasonic.start()

    db.update_device_status("arduino_nano33", False)

    print("[SensorManager] ✅ PIR + Ultrasonic + Buzzer พร้อมทำงาน")
    return camera_active


def stop_sensors():
    if _pir:        _pir.stop()
    if _ultrasonic: _ultrasonic.stop()
    GPIO.cleanup()
    print("[SensorManager] หยุด Sensors ทั้งหมด")