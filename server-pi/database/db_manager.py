"""
database/db_manager.py
จัดการ SQLite ตาม schema ใหม่
ตาราง: users, access_logs, suspect_logs, device_status, system_settings
"""

import sqlite3
import os
from datetime import datetime


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        print(f"📦 เชื่อมต่อ database: {self.db_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn = self._get_conn()
        conn.executescript(schema_sql)
        conn.commit()
        conn.close()
        print("✅ Database พร้อมใช้งาน")

    # ----------------------------------------------------------------
    #  Users
    # ----------------------------------------------------------------
    def add_user(self, name: str, role: str = "owner") -> int:
        """เพิ่มผู้ใช้ใหม่ คืน user_id"""
        conn = self._get_conn()
        cur  = conn.execute(
            "INSERT OR IGNORE INTO users (name, role) VALUES (?, ?)",
            (name, role)
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        return user_id

    def get_user_by_name(self, name: str) -> dict | None:
        conn = self._get_conn()
        row  = conn.execute(
            "SELECT * FROM users WHERE name = ?", (name,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_users(self) -> list:
        conn  = self._get_conn()
        rows  = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ----------------------------------------------------------------
    #  Access Logs
    # ----------------------------------------------------------------
    def log_access(self, event: str, name: str = "",
                   confidence: float = None, image_path: str = None,
                   note: str = None):
        """
        บันทึก event การเข้า-ออก
        event: 'WELCOME' | 'UNLOCK' | 'LOCK' | 'UNKNOWN'
        """
        conn    = self._get_conn()
        user    = self.get_user_by_name(name) if name else None
        user_id = user["id"] if user else None
        conn.execute(
            """INSERT INTO access_logs
               (user_id, event, confidence, image_path, note)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, event, confidence, image_path, note)
        )
        conn.commit()
        conn.close()

    def get_access_logs(self, limit: int = 50) -> list:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT a.*, u.name, u.role
               FROM access_logs a
               LEFT JOIN users u ON a.user_id = u.id
               ORDER BY a.timestamp DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ----------------------------------------------------------------
    #  Suspect Logs
    # ----------------------------------------------------------------
    def log_suspect(self, trigger_type: str, duration_sec: float = None,
                    distance_cm: float = None, image_path: str = None,
                    buzzer_fired: bool = False):
        """
        บันทึกเหตุการณ์ผิดปกติ
        trigger_type: 'FACE_UNKNOWN' | 'ULTRASONIC_LOITER'
        """
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO suspect_logs
               (trigger_type, duration_sec, distance_cm, image_path, buzzer_fired)
               VALUES (?, ?, ?, ?, ?)""",
            (trigger_type, duration_sec, distance_cm,
             image_path, 1 if buzzer_fired else 0)
        )
        conn.commit()
        conn.close()

    def get_suspect_logs(self, limit: int = 50) -> list:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM suspect_logs ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ----------------------------------------------------------------
    #  Device Status
    # ----------------------------------------------------------------
    def update_device_status(self, device_name: str, is_online: bool,
                              ip_address: str = ""):
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO device_status (device_name, is_online, ip_address, last_seen)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(device_name) DO UPDATE SET
                   is_online   = excluded.is_online,
                   ip_address  = excluded.ip_address,
                   last_seen   = CURRENT_TIMESTAMP""",
            (device_name, 1 if is_online else 0, ip_address)
        )
        conn.commit()
        conn.close()

    def get_device_status(self, device_name: str) -> dict | None:
        conn = self._get_conn()
        row  = conn.execute(
            "SELECT * FROM device_status WHERE device_name = ?",
            (device_name,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ----------------------------------------------------------------
    #  System Settings
    # ----------------------------------------------------------------
    def get_setting(self, key: str, default=None):
        conn = self._get_conn()
        row  = conn.execute(
            "SELECT value FROM system_settings WHERE key = ?", (key,)
        ).fetchone()
        conn.close()
        return row["value"] if row else default

    def update_setting(self, key: str, value: str):
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO system_settings (key, value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET
                   value      = excluded.value,
                   updated_at = CURRENT_TIMESTAMP""",
            (key, value)
        )
        conn.commit()
        conn.close()
