"""
core/train.py
เทรน LBPH Face Recognizer จาก dataset/ ที่ root ของ project
บันทึก model → server-pi/storage/trainer.yml
บันทึก names → server-pi/storage/names.json
"""

import cv2
import numpy as np
from PIL import Image
import os
import json

# ============================================================
#  PATH CONFIG
#  core/train.py อยู่ใน server-pi/core/
#    SERVER_PI_DIR  = .../server-pi/
#    ROOT_DIR       = .../SMART-DOOR-LOCK-AIOT/
# ============================================================
SERVER_PI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR      = os.path.dirname(SERVER_PI_DIR)

BASE_PATH  = os.path.join(ROOT_DIR,      "dataset")                 # SMART-DOOR-LOCK-AIOT/dataset/
MODEL_PATH = os.path.join(SERVER_PI_DIR, "storage", "trainer.yml")  # server-pi/storage/trainer.yml
NAMES_PATH = os.path.join(SERVER_PI_DIR, "storage", "names.json")   # server-pi/storage/names.json

IMAGE_EXTS    = ('.jpg', '.jpeg', '.png', '.bmp')
MIN_FACE_SIZE = (30, 30)

recognizer = cv2.face.LBPHFaceRecognizer_create()
detector   = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def get_faces_from_image(image_path: str, label: int):
    """โหลดภาพและดึงใบหน้าทั้งหมด พร้อม label"""
    try:
        img       = Image.open(image_path).convert('L')
        img_numpy = np.array(img, 'uint8')
        faces     = detector.detectMultiScale(
            img_numpy,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=MIN_FACE_SIZE
        )
        samples, labels = [], []
        for (x, y, w, h) in faces:
            samples.append(img_numpy[y:y+h, x:x+w])
            labels.append(label)
        return samples, labels
    except Exception as e:
        print(f"   ⚠️  ข้ามไฟล์ {os.path.basename(image_path)}: {e}")
        return [], []


def train_system():
    print("\n" + "="*55)
    print("  🧠  Smart Door — Face Recognition Trainer")
    print("="*55)

    # ตรวจสอบ dataset
    if not os.path.exists(BASE_PATH):
        print(f"❌ ไม่พบโฟลเดอร์ dataset: {BASE_PATH}")
        return

    user_folders = sorted([
        f for f in os.listdir(BASE_PATH)
        if os.path.isdir(os.path.join(BASE_PATH, f))
    ])

    if not user_folders:
        print("❌ ไม่พบโฟลเดอร์ผู้ใช้ใน dataset/")
        return

    print(f"\n[1/3] พบรายชื่อ: {user_folders}")
    print(f"      dataset path : {BASE_PATH}")
    print(f"      model path   : {MODEL_PATH}\n")

    # สร้างโฟลเดอร์ storage ถ้ายังไม่มี
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    face_samples, ids, names_map = [], [], {}

    for index, folder_name in enumerate(user_folders):
        names_map[index] = folder_name
        folder_path = os.path.join(BASE_PATH, folder_name)
        image_paths = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith(IMAGE_EXTS)
        ]

        if not image_paths:
            print(f"   ⚠️  ไม่มีรูปในโฟลเดอร์ '{folder_name}' — ข้ามไป")
            continue

        print(f"   > {folder_name} ({len(image_paths)} รูป)")
        face_count = 0

        for image_path in image_paths:
            samples, labels = get_faces_from_image(image_path, index)
            face_samples.extend(samples)
            ids.extend(labels)
            face_count += len(samples)

        print(f"     พบใบหน้า: {face_count} ใบหน้า")

    # ตรวจสอบว่ามีข้อมูลพอก่อน train
    if not face_samples:
        print("\n❌ ไม่พบใบหน้าเลย! ตรวจสอบ dataset และแสงในรูปภาพ")
        return

    print(f"\n   รวม: {len(face_samples)} ใบหน้า จาก {len(set(ids))} คน")

    # บันทึก names.json
    with open(NAMES_PATH, 'w', encoding='utf-8') as f:
        json.dump(names_map, f, ensure_ascii=False, indent=4)
    print(f"\n[2/3] บันทึก names.json → {NAMES_PATH}")

    # Train และบันทึก model
    print("[3/3] AI กำลังเรียนรู้... (อาจใช้เวลาสักครู่)")
    recognizer.train(face_samples, np.array(ids))
    recognizer.write(MODEL_PATH)

    print(f"\n✅ เสร็จสมบูรณ์! บันทึก model → {MODEL_PATH}")
    print("   พร้อมรันระบบด้วย: python main.py\n")


if __name__ == "__main__":
    train_system()