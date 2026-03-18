"""
core/lcd.py
LCD 1602 I2C
ติดตั้ง library: pip install RPLCD smbus2
"""

import threading
from datetime import datetime

# I2C address: ลอง 0x27 ก่อน ถ้าไม่ได้ใช้ 0x3F
I2C_ADDRESS = 0x27
I2C_PORT    = 1
LCD_COLS    = 16
LCD_ROWS    = 2

MSG = {
    "READY":    ("  Smart Door  ", " System Ready "),
    "SCANNING": (" Scanning...  ", "  Please Wait "),
    "WELCOME":  ("  WELCOME :)  ", ""),
    "SUSPECT":  ("  !! ALERT !! ", "Suspect Found!"),
    "LOCKED":   (" Door Locked  ", "              "),
    "UNLOCKED": (" Door Opened! ", "  Welcome!    "),
    "NO_CONN":  (" System Error ", " Check WiFi   "),
}


class LCDDisplay:
    def __init__(self, address: int = I2C_ADDRESS, port: int = I2C_PORT):
        self._lock   = threading.Lock()
        self._lcd    = None
        self._active = False

        try:
            from RPLCD.i2c import CharLCD
            self._lcd = CharLCD(
                i2c_expander="PCF8574",
                address=address,
                port=port,
                cols=LCD_COLS,
                rows=LCD_ROWS,
                dotsize=8
            )
            self._lcd.clear()
            self._active = True
            print(f"[LCD] เริ่มต้น I2C 0x{address:02X}")
            self.show("READY")
        except Exception as e:
            print(f"[LCD] ไม่พบ LCD: {e} — ระบบทำงานต่อโดยไม่มี LCD")

    def show(self, status: str, name: str = ""):
        if not self._active:
            return
        row1, row2 = MSG.get(status, ("  Smart Door  ", "              "))
        if status == "WELCOME" and name:
            row2 = f"Hi {name[:12]:<12}"
        self._write(row1, row2)

    def show_custom(self, row1: str, row2: str = ""):
        if not self._active:
            return
        self._write(row1, row2)

    def show_clock(self):
        if not self._active:
            return
        now = datetime.now()
        self._write(
            f"  {now.strftime('%H:%M:%S')}    ",
            f" {now.strftime('%d/%m/%Y')}  "
        )

    def _write(self, row1: str, row2: str):
        with self._lock:
            try:
                self._lcd.clear()
                self._lcd.write_string(row1.ljust(LCD_COLS)[:LCD_COLS])
                self._lcd.cursor_pos = (1, 0)
                self._lcd.write_string(row2.ljust(LCD_COLS)[:LCD_COLS])
            except Exception as e:
                print(f"[LCD] write error: {e}")

    def clear(self):
        if not self._active:
            return
        with self._lock:
            try:
                self._lcd.clear()
            except Exception:
                pass

    def stop(self):
        self.clear()
        self._active = False
        print("[LCD] หยุดทำงาน")
