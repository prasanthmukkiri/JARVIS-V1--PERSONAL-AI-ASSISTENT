from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from fer.fer import FER
    print('FER module import ok', FER)
except Exception as e:
    print('FER import failed', type(e).__name__, e)

try:
    import core.emotion_detector as ed
    print('core.emotion_detector imported ok', ed._FER_AVAILABLE, ed._CV2_AVAILABLE)
    detector = ed.get_emotion_detector()
    print('detector enabled', detector.enabled)
except Exception as e:
    print('core.emotion_detector import failed', type(e).__name__, e)
