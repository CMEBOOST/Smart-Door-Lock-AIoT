import face_recognition
import cv2
import numpy as np
import json
import os

class FaceProcessor:
    def __init__(self, db_manager):
        self.db = db_manager
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []
        self.load_known_faces()

    def load_known_faces(self):
        """ดึงใบหน้าจากฐานข้อมูลมาเก็บไว้ใน Memory เพื่อความเร็วในการสแกน"""
        users = self.db.get_all_users()
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []

        for user in users:
            # แปลง string กลับเป็น list/numpy array
            encoding = np.array(json.loads(user['face_encoding']))
            self.known_face_encodings.append(encoding)
            self.known_face_names.append(user['name'])
            self.known_face_ids.append(user['id'])
        
        print(f"🧠 AI Loaded {len(self.known_face_names)} faces from database.")

    def process_frame(self, frame, tolerance=0.6):
        """วิเคราะห์ภาพว่ามีใบหน้าใครอยู่ในภาพบ้าง"""
        # ย่อขนาดภาพเพื่อให้ประมวลผลเร็วขึ้น (1/4 ของขนาดจริง)
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        # แปลง BGR เป็น RGB
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # ค้นหาตำแหน่งและ Encoding ของใบหน้าในภาพปัจจุบัน
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        detected_users = []

        for face_encoding in face_encodings:
            # เปรียบเทียบกับใบหน้าที่รู้จัก
            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=tolerance)
            name = "Unknown"
            user_id = None

            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name = self.known_face_names[best_match_index]
                    user_id = self.known_face_ids[best_match_index]

            detected_users.append({"id": user_id, "name": name})

        return detected_users