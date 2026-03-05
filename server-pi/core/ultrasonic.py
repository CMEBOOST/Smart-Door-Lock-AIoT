"""
core/ultrasonic.py
HC-SR04 — วัดระยะ แยก callback เป็น on_person_near / on_person_gone
"""

import RPi.GPIO as GPIO
import time
import threading
from datetime import datetime

TRIG_PIN         = 23
ECHO_PIN         = 24
NEAR_DISTANCE    = 150    # cm — ถือว่าคนอยู่หน้าประตู
MEASURE_INTERVAL = 0.3    # วินาที


def _ts():
    return datetime.now().strftime("%H:%M:%S")


class UltrasonicSensor:
    def __init__(self, trig: int = TRIG_PIN, echo: int = ECHO_PIN):
        self.trig            = trig
        self.echo            = echo
        self._running        = False
        self._thread         = None
        self._near_cb        = None
        self._gone_cb        = None
        self._was_near       = False

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.trig, GPIO.OUT)
        GPIO.setup(self.echo, GPIO.IN)
        GPIO.output(self.trig, GPIO.LOW)
        time.sleep(0.1)
        print(f"[Ultrasonic] TRIG=GPIO{trig} ECHO=GPIO{echo}")

    def on_person_near(self, cb):
        self._near_cb = cb
        return self

    def on_person_gone(self, cb):
        self._gone_cb = cb
        return self

    def measure_distance(self) -> float:
        try:
            GPIO.output(self.trig, GPIO.HIGH)
            time.sleep(0.00001)
            GPIO.output(self.trig, GPIO.LOW)

            t = time.time() + 0.04
            while GPIO.input(self.echo) == GPIO.LOW:
                if time.time() > t: return -1.0
            start = time.time()

            t = time.time() + 0.04
            while GPIO.input(self.echo) == GPIO.HIGH:
                if time.time() > t: return -1.0
            end = time.time()

            return round((end - start) * 17150, 1)
        except Exception:
            return -1.0

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[Ultrasonic] พร้อมวัดระยะ")

    def stop(self):
        self._running = False
        GPIO.cleanup([self.trig, self.echo])

    def _loop(self):
        while self._running:
            dist    = self.measure_distance()
            is_near = 0 < dist < NEAR_DISTANCE

            if is_near and not self._was_near:
                self._was_near = True
                if self._near_cb:
                    threading.Thread(
                        target=self._near_cb, args=(dist,), daemon=True
                    ).start()
            elif not is_near and self._was_near:
                self._was_near = False
                if self._gone_cb:
                    threading.Thread(
                        target=self._gone_cb, daemon=True
                    ).start()
            elif is_near and self._was_near:
                # อัปเดต distance ต่อเนื่อง
                if self._near_cb:
                    threading.Thread(
                        target=self._near_cb, args=(dist,), daemon=True
                    ).start()

            time.sleep(MEASURE_INTERVAL)
