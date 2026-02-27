import sqlite3
import json
import os

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        # สร้างโฟลเดอร์ถ้ายังไม่มี
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # ให้คืนค่าผลลัพธ์เป็น dict-like
        return conn

    def init_db(self):
        """สร้างตารางตาม schema.sql ถ้ายังไม่มีไฟล์ .db"""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if not os.path.exists(self.db_path):
            print(f"📦 Creating new database at {self.db_path}...")
            # แก้ไข: เพิ่ม encoding='utf-8' เพื่อรองรับภาษาไทยใน Comment ของ SQL
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            conn = self.get_connection()
            conn.executescript(schema_sql)
            conn.commit()
            conn.close()
            print("✅ Database initialized with 4 tables.")

    # --- ฟังก์ชันจัดการผู้ใช้งาน (Users) ---
    def add_user(self, name, face_encoding, role='owner'):
        """บันทึกผู้ใช้ใหม่พร้อมค่า Face Encoding (128-d vector)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        encoding_str = json.dumps(face_encoding.tolist() if hasattr(face_encoding, 'tolist') else face_encoding)
        cursor.execute(
            "INSERT INTO users (name, face_encoding, role) VALUES (?, ?, ?)",
            (name, encoding_str, role)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id

    def get_all_users(self):
        """ดึงข้อมูลผู้ใช้ทั้งหมดเพื่อนำไปเปรียบเทียบใบหน้า"""
        conn = self.get_connection()
        users = conn.execute("SELECT * FROM users").fetchall()
        conn.close()
        return users

    def log_access(self, user_id, status, image_path=None):
        conn = self.get_connection()
        conn.execute(
            "INSERT INTO access_logs (user_id, status, image_path) VALUES (?, ?, ?)",
            (user_id, status, image_path)
        )
        conn.commit()
        conn.close()

    def get_setting(self, key, default=None):
        conn = self.get_connection()
        row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row['value'] if row else default

    def update_device_status(self, device_name, is_online):
        conn = self.get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO system_status (device_name, is_online, last_seen) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (device_name, 1 if is_online else 0)
        )
        conn.commit()
        conn.close()