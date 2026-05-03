"""
Emotion detection from webcam for enhanced user interaction awareness.
Detects emotions during voice commands to adapt Jarvis responses.
"""
import threading
import time
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

try:
    from fer.fer import FER
    _FER_AVAILABLE = True
except ImportError:
    try:
        from fer import FER  # type: ignore
        _FER_AVAILABLE = True
    except ImportError:
        _FER_AVAILABLE = False


@dataclass
class EmotionFrame:
    """Single emotion detection frame."""
    timestamp: float
    emotion: str
    confidence: float
    face_detected: bool


class EmotionDetector:
    """Detects user emotions from webcam during voice commands."""

    def __init__(self, enabled: bool = True, buffer_size: int = 30):
        self.enabled = enabled and _FER_AVAILABLE and _CV2_AVAILABLE
        self.buffer_size = buffer_size
        self.emotion_buffer: deque = deque(maxlen=buffer_size)
        self.camera = None
        self.detector = None
        self.lock = threading.Lock()
        self.recording = False
        self.emotion_thread = None

        if self.enabled:
            self._init_detector()
        else:
            if not _FER_AVAILABLE:
                logger.warning("[Emotion] FER not available, install with: pip install fer")
            if not _CV2_AVAILABLE:
                logger.warning("[Emotion] OpenCV not available, install with: pip install opencv-python")

    def _init_detector(self):
        """Initialize FER detector."""
        try:
            self.detector = FER(mtcnn=False)  # Use faster face detection
            logger.info("[Emotion] Detector initialized ✅")
        except Exception as e:
            logger.error(f"[Emotion] Failed to initialize detector: {e}")
            self.enabled = False

    def start_recording(self, duration_seconds: float = 5.0):
        """Start emotion recording for specified duration."""
        if not self.enabled or self.recording:
            return

        self.emotion_buffer.clear()
        self.recording = True
        
        def record():
            try:
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    logger.error("[Emotion] Cannot access webcam")
                    self.recording = False
                    return

                start_time = time.time()
                frame_count = 0

                while self.recording and (time.time() - start_time) < duration_seconds:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    # Detect emotions
                    emotion_dict = self.detector.detect_emotions(frame)
                    
                    if emotion_dict:
                        emotion_data = emotion_dict[0]['emotions']
                        dominant = max(emotion_data, key=emotion_data.get)
                        confidence = emotion_data[dominant]

                        frame_entry = EmotionFrame(
                            timestamp=time.time(),
                            emotion=dominant,
                            confidence=confidence,
                            face_detected=True
                        )
                    else:
                        frame_entry = EmotionFrame(
                            timestamp=time.time(),
                            emotion="neutral",
                            confidence=0.0,
                            face_detected=False
                        )

                    with self.lock:
                        self.emotion_buffer.append(frame_entry)

                    frame_count += 1

                cap.release()
                logger.info(f"[Emotion] Recorded {frame_count} frames over {duration_seconds}s")
                self.recording = False

            except Exception as e:
                logger.error(f"[Emotion] Recording error: {e}")
                self.recording = False

        self.emotion_thread = threading.Thread(target=record, daemon=True)
        self.emotion_thread.start()

    def stop_recording(self):
        """Stop emotion recording."""
        self.recording = False
        if self.emotion_thread:
            self.emotion_thread.join(timeout=2.0)

    def get_dominant_emotion(self) -> Optional[str]:
        """Get most common emotion from buffer."""
        if not self.emotion_buffer:
            return None

        with self.lock:
            emotion_counts = {}
            for frame in self.emotion_buffer:
                if frame.face_detected:
                    emotion_counts[frame.emotion] = emotion_counts.get(frame.emotion, 0) + 1

        if not emotion_counts:
            return None

        return max(emotion_counts, key=emotion_counts.get)

    def get_emotion_stats(self) -> Dict:
        """Get detailed emotion statistics."""
        if not self.emotion_buffer:
            return {"status": "no_data"}

        with self.lock:
            emotions = {}
            face_detected_count = 0

            for frame in self.emotion_buffer:
                if frame.face_detected:
                    emotions[frame.emotion] = emotions.get(frame.emotion, 0) + 1
                    face_detected_count += 1

        total = len(self.emotion_buffer)
        face_detection_rate = (face_detected_count / total * 100) if total > 0 else 0

        return {
            "total_frames": total,
            "face_detected_count": face_detected_count,
            "face_detection_rate": round(face_detection_rate, 1),
            "emotions": emotions,
            "dominant_emotion": self.get_dominant_emotion(),
            "recording": self.recording,
        }

    def get_emotion_for_response(self) -> str:
        """Get emotion context string for LLM response adaptation."""
        emotion = self.get_dominant_emotion()
        if not emotion:
            return "neutral"
        
        emotion_contexts = {
            "happy": "The user appears happy. Respond warmly and with enthusiasm.",
            "sad": "The user appears sad. Respond with empathy and support.",
            "angry": "The user appears frustrated. Respond calmly and help resolve quickly.",
            "neutral": "The user appears neutral. Respond professionally.",
            "fear": "The user appears concerned. Respond reassuringly.",
            "surprise": "The user appears surprised. Respond with clarity.",
            "disgust": "The user appears displeased. Respond constructively.",
        }
        return emotion_contexts.get(emotion, "neutral")


# Global instance
_emotion_detector = None


def get_emotion_detector(enabled: bool = True) -> EmotionDetector:
    global _emotion_detector
    if _emotion_detector is None:
        _emotion_detector = EmotionDetector(enabled=enabled)
    return _emotion_detector
