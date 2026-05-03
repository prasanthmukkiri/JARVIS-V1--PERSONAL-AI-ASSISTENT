# pip install fer tensorflow
import cv2

_detector = None

def _get_detector():
    global _detector
    if _detector is None:
        try:
            from fer.fer import FER
        except ImportError:
            from fer import FER  # type: ignore
        _detector = FER(mtcnn=True)
    return _detector

def detect_emotion(parameters=None, player=None, **kwargs) -> str:
    cap = cv2.VideoCapture(0)
    for _ in range(8): cap.read()
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return "neutral"
    try:
        result = _get_detector().detect_emotions(frame)
        if result:
            emotions = result[0]["emotions"]
            dominant = max(emotions, key=emotions.get)
            score = emotions[dominant]
            if score > 0.4:
                return f"You appear {dominant}, sir."
    except Exception as e:
        print(f"[Emotion] {e}")
    return "You seem calm, sir."