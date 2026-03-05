-- ============================================================
--  Smart Door Lock AIoT — Database Schema
--  SQLite
-- ============================================================

-- ------------------------------------------------------------
--  1. users — เจ้าของบ้านที่ระบบรู้จัก
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,          -- ชื่อ (ตรงกับโฟลเดอร์ใน dataset/)
    role       TEXT    NOT NULL DEFAULT 'owner', -- 'owner' | 'guest'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
--  2. access_logs — ประวัติการเข้า-ออกทุก event
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS access_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,                          -- NULL ถ้าเป็น UNKNOWN
    event      TEXT    NOT NULL,                 -- 'WELCOME' | 'UNLOCK' | 'LOCK' | 'UNKNOWN'
    confidence REAL,                             -- ค่า confidence จาก LBPH (ต่ำ = ดี)
    image_path TEXT,                             -- พาธรูปภาพที่ถ่ายไว้ (ถ้ามี)
    note       TEXT,                             -- หมายเหตุเพิ่มเติม
    timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ------------------------------------------------------------
--  3. suspect_logs — เหตุการณ์ผิดปกติ / งัดแงะ
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suspect_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_type  TEXT NOT NULL,                 -- 'FACE_UNKNOWN' | 'ULTRASONIC_LOITER'
    duration_sec  REAL,                          -- อยู่หน้าประตูนานกี่วินาที
    distance_cm   REAL,                          -- ระยะจาก ultrasonic
    image_path    TEXT,                          -- พาธรูปภาพที่บันทึกไว้
    buzzer_fired  INTEGER DEFAULT 0,             -- 1 = buzzer ดังแล้ว
    timestamp     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
--  4. device_status — สถานะ Arduino online/offline
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS device_status (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_name TEXT    NOT NULL UNIQUE,         -- 'arduino_nano33'
    is_online   INTEGER NOT NULL DEFAULT 0,      -- 1 = online | 0 = offline
    ip_address  TEXT,                            -- IP ล่าสุดที่ตอบสนอง
    last_seen   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
--  5. system_settings — ค่าตั้งค่าระบบ
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
--  ข้อมูลเริ่มต้น
-- ------------------------------------------------------------
INSERT OR IGNORE INTO system_settings (key, value) VALUES
    ('auto_lock_delay',  '10'),   -- วินาที lock อัตโนมัติหลัง unlock
    ('unknown_timeout',  '10'),   -- วินาที นับก่อนเป็น SUSPECT
    ('suspect_duration', '20'),   -- วินาที ยืนอยู่ก่อน buzzer
    ('confidence_threshold', '50'),
    ('buzzer_duration',  '10');

INSERT OR IGNORE INTO device_status (device_name, is_online, ip_address) VALUES
    ('arduino_nano33', 0, '');

-- ------------------------------------------------------------
--  Indexes — เพิ่มความเร็วการ query
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp  ON access_logs  (timestamp);
CREATE INDEX IF NOT EXISTS idx_access_logs_event      ON access_logs  (event);
CREATE INDEX IF NOT EXISTS idx_suspect_logs_timestamp ON suspect_logs (timestamp);
