"""
core/pir.py
PIR Sensor — ใช้ gpiozero แบบ event-driven
ไม่ trigger ซ้ำถ้า HIGH ค้าง
Default GPIO pin: 17
"""

import threading
import time
from datetime import datetime

try:
    from gpiozero import MotionSensor
except ImportError:
    MotionSensor = None
    print("[PIR] ⚠️  ไม่พบ gpiozero — รันในโหมด simulation")

PIR_PIN            = 17
INACTIVITY_TIMEOUT = 10.0  # วินาที ไม่มีการเคลื่อนไหว → ปิดกล้อง


def _ts():
    return datetime.now().strftime("%H:%M:%S")


class PIRSensor:
    def __init__(self, pin: int = PIR_PIN):
        self.pin              = pin
        self._on_motion_cb    = None
        self._on_inactive_cb  = None
        self._inactive_timer  = None
        self._pir             = None

        if MotionSensor:
            self._pir = MotionSensor(pin)
            print(f"[PIR] เริ่มต้น GPIO{pin} (gpiozero event-driven)")
        else:
            print(f"[PIR] Simulation mode — GPIO{pin}")

    def on_motion(self, callback):
        self._on_motion_cb = callback
        return self

    def on_inactive(self, callback):
        self._on_inactive_cb = callback
        return self

    def start(self):
        if self._pir:
            self._pir.when_motion    = self._handle_motion
            self._pir.when_no_motion = self._handle_no_motion
        # ไม่ start timer ตอนเริ่ม — กล้องปิดจนกว่าจะเจอคนครั้งแรก
        print(f"[PIR] พร้อมตรวจจับ GPIO{self.pin} | รอการเคลื่อนไหวก่อน")
        return self

    def stop(self):
        self._cancel_inactivity_timer()
        if self._pir:
            self._pir.close()
        print("[PIR] หยุดทำงาน")

    # ----------------------------------------------------------------
    #  Event Handlers
    # ----------------------------------------------------------------
    def _handle_motion(self):
        print(f"[{_ts()}] 🚶 PIR ตรวจเจอคน!")
        self._reset_inactivity_timer()
        if self._on_motion_cb:
            threading.Thread(target=self._on_motion_cb, daemon=True).start()

    def _handle_no_motion(self):
        print(f"[{_ts()}] 🔕 PIR ไม่เจอคนแล้ว — เริ่มนับ {INACTIVITY_TIMEOUT}s")
        self._reset_inactivity_timer()

    # ----------------------------------------------------------------
    #  Inactivity Timer
    # ----------------------------------------------------------------
    def _reset_inactivity_timer(self):
        self._cancel_inactivity_timer()
        self._inactive_timer = threading.Timer(
            INACTIVITY_TIMEOUT, self._on_inactivity
        )
        self._inactive_timer.daemon = True
        self._inactive_timer.start()

    def _cancel_inactivity_timer(self):
        if self._inactive_timer:
            self._inactive_timer.cancel()
            self._inactive_timer = None

    def _on_inactivity(self):
        print(f"[{_ts()}] 😴 ไม่มีการเคลื่อนไหว {INACTIVITY_TIMEOUT}s → ปิดกล้อง")
        if self._on_inactive_cb:
            threading.Thread(target=self._on_inactive_cb, daemon=True).start()