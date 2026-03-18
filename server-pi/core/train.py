"""
core/train.py
Train LBPH model จาก dataset/
สามารถเรียกได้ทั้งจาก CLI และจาก routes.py (train ใหม่ผ่านเว็บ)
"""

import cv2
import os
import json
import numpy as np

SERVER_PI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR   = os.path.join(SERVER_PI_DIR, "dataset")
MODEL_PATH    = os.path.join(SERVER_PI_DIR, "storage", "trainer.yml")
NAMES_PATH    = os.path.join(SERVER_PI_DIR, "storage", "names.json")


def train():
    os.makedirs(os.path.join(SERVER_PI_DIR, "storage"), exist_ok=True)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    faces, labels, names = [], [], {}
    label_id = 0

    if not os.path.exists(DATASET_DIR):
        raise FileNotFoundError(f"ไม่พบ dataset dir: {DATASET_DIR}")

    folders = sorted([
        d for d in os.listdir(DATASET_DIR)
        if os.path.isdir(os.path.join(DATASET_DIR, d))
    ])

    if not folders:
        raise ValueError("ไม่มี user ใน dataset")

    print(f"[Train] พบ {len(folders)} user: {folders}")

    for folder in folders:
        names[label_id] = folder
        folder_path     = os.path.join(DATASET_DIR, folder)
        img_files       = [
            f for f in os.listdir(folder_path)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]

        count = 0
        for img_file in img_files:
            img_path = os.path.join(folder_path, img_file)
            img      = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            detected = face_cascade.detectMultiScale(img, 1.1, 5, minSize=(30, 30))
            for (x, y, w, h) in detected:
                faces.append(img[y:y+h, x:x+w])
                labels.append(label_id)
                count += 1

        print(f"[Train]   {folder}: {count} faces จาก {len(img_files)} รูป")
        label_id += 1

    if not faces:
        raise ValueError("ไม่พบใบหน้าในรูปภาพทั้งหมด")

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels))
    recognizer.write(MODEL_PATH)

    with open(NAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(names, f, ensure_ascii=False, indent=2)

    print(f"[Train] ✅ Train เสร็จ | {len(faces)} faces | {len(names)} users")
    print(f"[Train] บันทึก model → {MODEL_PATH}")
    return {"faces": len(faces), "users": len(names), "names": names}


if __name__ == "__main__":
    train()