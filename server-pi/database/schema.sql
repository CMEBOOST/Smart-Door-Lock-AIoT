-- ตารางเก็บข้อมูลผู้ใช้และลายนิ้วมือใบหน้า (Face Encoding)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    face_encoding TEXT NOT NULL, -- เก็บเป็น JSON String ของ 128-d vector
    role TEXT DEFAULT 'user',    -- 'owner' หรือ 'user'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตารางเก็บประวัติการเข้า-ออก
CREATE TABLE IF NOT EXISTS access_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    status TEXT NOT NULL,       -- 'granted', 'denied'
    image_path TEXT,            -- พาธรูปภาพที่ถ่ายไว้ตอนสแกน
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ตารางเก็บสถานะอุปกรณ์ (Arduino)
CREATE TABLE IF NOT EXISTS system_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_name TEXT UNIQUE,
    is_online INTEGER DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตารางเก็บการตั้งค่าระบบ
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ข้อมูลเริ่มต้น
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('auto_lock_delay', '5');
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('security_level', 'high');