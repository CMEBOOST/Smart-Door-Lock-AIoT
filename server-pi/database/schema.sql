-- 1. ตารางเก็บข้อมูลเจ้าของบ้านและใบหน้า (Face Encodings)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    -- เก็บข้อมูลใบหน้า 128 มิติเป็นข้อความ JSON string
    face_encoding TEXT NOT NULL, 
    role TEXT DEFAULT 'owner', -- 'owner', 'member', 'guest'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. ตารางเก็บประวัติการเข้า-ออก
CREATE TABLE IF NOT EXISTS access_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, -- เชื่อมกับตาราง users (ถ้าเป็นคนแปลกหน้าจะเป็น NULL)
    status TEXT NOT NULL, -- 'Success', 'Access Denied', 'Suspicious'
    image_path TEXT, -- ที่อยู่ไฟล์รูปภาพใน storage/log_captures/
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 3. ตารางเก็บสถานะอุปกรณ์ (เพื่อดูว่า Arduino/Sensors ยังออนไลน์ไหม)
CREATE TABLE IF NOT EXISTS system_status (
    device_name TEXT PRIMARY KEY, -- 'arduino_node', 'pir_sensor', 'ultrasonic'
    is_online INTEGER DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. ตารางเก็บการตั้งค่าระบบ (Dynamic Settings)
-- ตารางนี้ช่วยให้เราปรับค่า Threshold ต่างๆ ได้ผ่าน API โดยไม่ต้องแก้ Code
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY, -- 'unlock_duration', 'distance_threshold', 'api_key'
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- เพิ่มข้อมูลการตั้งค่าเริ่มต้น (Initial Settings)
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('unlock_duration', '10');
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('distance_threshold_cm', '15.0');
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('face_match_threshold', '0.6');