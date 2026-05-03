# pip install deepface
from deepface import DeepFace
import cv2
from pathlib import Path

FACES_DB = Path.home() / ".jarvis" / "faces"

def recognize_face(parameters=None, player=None, **kwargs) -> str:
    FACES_DB.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(0)
    for _ in range(10): cap.read()
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return "Could not access camera."
    try:
        results = DeepFace.find(
            frame, db_path=str(FACES_DB),
            enforce_detection=False, silent=True
        )
        if results and len(results[0]) > 0:
            name = Path(results[0]["identity"].iloc[0]).parent.name
            return f"I can see {name}, sir."
    except Exception as e:
        print(f"[Face] {e}")
    return "I don't recognise this person, sir."

def register_face(parameters=None, player=None, **kwargs) -> str:
    name = (parameters or {}).get("name", "User")
    person_dir = FACES_DB / name
    person_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(0)
    saved = 0
    for i in range(5):
        for _ in range(8): cap.read()
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(str(person_dir / f"{name}_{i}.jpg"), frame)
            saved += 1
    cap.release()
    return f"Registered {saved} photos for {name}, sir."