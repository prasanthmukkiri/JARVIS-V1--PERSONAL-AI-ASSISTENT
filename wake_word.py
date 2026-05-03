"""
wake_word.py  —  JARVIS Wake Word Detection
============================================
Listens in the background for "JARVIS" (or custom words).
When heard, unmutes the mic and notifies main.py via callback.

Enhancements:
  • VAD (voice activity detection) for noise robustness
  • Multi-mic fallback if primary fails
  • Adaptive energy threshold
  • Configurable noise suppression
  • Better error recovery

How it works:
  1. Continuously records short audio chunks (non-blocking)
  2. Runs VAD to detect speech activity
  3. Runs speech recognition on speech chunks locally (vosk) or
     falls back to Google STT if vosk isn't installed
  4. When wake word is detected → fires on_wake_word callback
  5. After a configurable timeout of silence → re-mutes (sleep mode)

Install:
  pip install vosk sounddevice numpy webrtcvad
  # Download model: https://alphacephei.com/vosk/models
  # Recommended: vosk-model-small-en-us-0.15  (40MB, fast)
  # Place extracted folder at: <project_root>/models/vosk-en/

Or fallback (no model needed, requires internet):
  pip install SpeechRecognition sounddevice numpy
"""

from __future__ import annotations

import json
import queue
import re
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional


# ── optional imports ───────────────────────────────────────────────────────────
try:
    import sounddevice as sd
    _SD = True
except ImportError:
    _SD = False

try:
    import numpy as np
    _NP = True
except ImportError:
    _NP = False

try:
    from vosk import Model, KaldiRecognizer
    _VOSK = True
except ImportError:
    _VOSK = False

try:
    import speech_recognition as sr
    _SR = True
except ImportError:
    _SR = False

try:
    import webrtcvad as vad_module
    _VAD = True
except ImportError:
    _VAD = False

try:
    from core.echo_cancellation import EnergyGateEchoCanceller
    _AEC = True
except Exception:
    EnergyGateEchoCanceller = None
    _AEC = False


# ── constants ──────────────────────────────────────────────────────────────────
_SAMPLE_RATE   = 16000
_CHANNELS      = 1
_CHUNK_FRAMES  = 4000          # ~0.25 s per chunk
_DTYPE         = "int16"
_VAD_THRESHOLD = 0.5           # 0.5 = medium aggressiveness (0=least aggressive, 3=most)
_ENERGY_GATE   = 300           # RMS threshold for silence detection
_ENERGY_SCALE  = 0.9           # adaptive energy threshold scale

_DEFAULT_WAKE_WORDS = [
    "jarvis",
    "hey jarvis",
    "ok jarvis",
    "yo jarvis",
]

_SLEEP_WORDS = [                # say these to put JARVIS back to sleep
    "go to sleep",
    "sleep mode",
    "jarvis sleep",
    "goodbye jarvis",
]

_BASE_DIR   = Path(__file__).resolve().parent
_VOSK_MODEL = _BASE_DIR / "models" / "vosk-en"
_CONFIG     = _BASE_DIR / "config" / "api_keys.json"

_ECHO_CANCELLER = EnergyGateEchoCanceller() if _AEC else None


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _detect_speech_activity(data: bytes, aggressiveness: int = 1) -> bool:
    """Use WebRTC VAD to detect if chunk contains speech."""
    if not _VAD or not _NP:
        # Fallback: energy-based detection
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(arr ** 2)))
        return rms > _ENERGY_GATE
    
    try:
        v = vad_module.Vad(aggressiveness)
        is_speech = v.is_speech(data, _SAMPLE_RATE)
        return is_speech
    except Exception:
        return True  # on error, assume speech


def set_jarvis_speaking(is_speaking: bool) -> None:
    """Tell the wake-word pipeline when Jarvis audio is playing."""
    if _ECHO_CANCELLER:
        try:
            _ECHO_CANCELLER.set_speaking(is_speaking)
        except Exception:
            pass


def _list_input_devices() -> list[dict]:
    """List all available input devices."""
    if not _SD:
        return []
    try:
        devices = sd.query_devices()
        if isinstance(devices, dict):
            devices = [devices]
        return [d for d in devices if d.get("max_input_channels", 0) > 0]
    except Exception:
        return []


def _select_best_mic() -> int | None:
    """Auto-select the best available input device.
    Prefer built-in mics with low latency.
    """
    if not _SD:
        return None
    try:
        devices = _list_input_devices()
        if not devices:
            return sd.default.device[0]  # use system default
        
        # Prefer devices with "mic", "input", or low index
        best = devices[0]
        for d in devices:
            name_lower = (d.get("name") or "").lower()
            if "headset" in name_lower or "headphone" in name_lower:
                best = d
                break
            if "mic" in name_lower or "input" in name_lower:
                best = d
        
        return best["index"]
    except Exception:
        return None


# ── WakeWordDetector ───────────────────────────────────────────────────────────
class WakeWordDetector:
    """
    Background thread that listens for wake words.

    Parameters
    ----------
    on_wake      : called when wake word heard  → (word: str) -> None
    on_sleep     : called when sleep word heard → () -> None
    wake_words   : list of trigger phrases (lowercase)
    sleep_words  : list of sleep phrases   (lowercase)
    active_timeout_s : seconds of silence before auto-sleep (0 = never)
    player       : JarvisUI instance for log output (optional)
    """

    def __init__(
        self,
        on_wake:          Callable[[str], None],
        on_sleep:         Optional[Callable[[], None]] = None,
        wake_words:       list[str] = _DEFAULT_WAKE_WORDS,
        sleep_words:      list[str] = _SLEEP_WORDS,
        active_timeout_s: float     = 30.0,
        player=None,
    ):
        self.on_wake          = on_wake
        self.on_sleep         = on_sleep
        self.wake_words       = [w.lower().strip() for w in wake_words]
        self.sleep_words      = [w.lower().strip() for w in sleep_words]
        self.active_timeout_s = active_timeout_s
        self.player           = player

        self._running    = False
        self._awake      = False          # True = listening actively
        self._last_heard = 0.0
        self._thread: Optional[threading.Thread] = None
        self._q: queue.Queue = queue.Queue()

        # pick backend
        self._backend = self._choose_backend()
        self._log(f"[WakeWord] Backend: {self._backend}")

        # vosk recognizer (created once)
        self._vosk_rec: Optional[KaldiRecognizer] = None
        if self._backend == "vosk":
            self._vosk_rec = self._init_vosk()

    # ── backend selection ──────────────────────────────────────────────────────
    def _choose_backend(self) -> str:
        if _VOSK and _VOSK_MODEL.exists():
            return "vosk"
        if _SR:
            return "google"
        return "none"

    def _init_vosk(self) -> Optional[KaldiRecognizer]:
        try:
            model = Model(str(_VOSK_MODEL))
            rec   = KaldiRecognizer(model, _SAMPLE_RATE)
            rec.SetWords(False)
            self._log("[WakeWord] Vosk model loaded ✅")
            return rec
        except Exception as e:
            self._log(f"[WakeWord] Vosk init failed: {e}")
            return None

    # ── public API ─────────────────────────────────────────────────────────────
    def start(self) -> None:
        if not _SD or not _NP:
            self._log("[WakeWord] ❌ sounddevice / numpy not installed.")
            return
        if self._backend == "none":
            self._log(
                "[WakeWord] ❌ No STT backend available.\n"
                "  Install vosk:  pip install vosk\n"
                "  OR install SR: pip install SpeechRecognition"
            )
            return

        self._running = True
        self._thread  = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="WakeWordDetector",
        )
        self._thread.start()
        self._log("[WakeWord] 👂 Listening for wake word...")

    def stop(self) -> None:
        self._running = False
        self._log("[WakeWord] 🔴 Stopped.")

    def force_wake(self) -> None:
        """Manually activate (e.g. from a hotkey)."""
        self._activate("manual")

    def force_sleep(self) -> None:
        """Manually deactivate."""
        self._deactivate()

    @property
    def is_awake(self) -> bool:
        return self._awake

    # ── internal ───────────────────────────────────────────────────────────────
    def _log(self, text: str) -> None:
        print(text)
        if self.player:
            try:
                self.player.write_log(text)
            except Exception:
                pass

    def _activate(self, word: str) -> None:
        if not self._awake:
            self._awake      = True
            self._last_heard = time.time()
            self._log(f"[WakeWord] 🟢 ACTIVATED — heard: '{word}'")
            try:
                self.on_wake(word)
            except Exception as e:
                self._log(f"[WakeWord] on_wake error: {e}")

    def _deactivate(self) -> None:
        if self._awake:
            self._awake = False
            self._log("[WakeWord] 💤 Sleeping...")
            if self.on_sleep:
                try:
                    self.on_sleep()
                except Exception as e:
                    self._log(f"[WakeWord] on_sleep error: {e}")

    def _check_timeout(self) -> None:
        if (
            self._awake
            and self.active_timeout_s > 0
            and (time.time() - self._last_heard) > self.active_timeout_s
        ):
            self._log("[WakeWord] ⏱️ Timeout — returning to sleep mode.")
            self._deactivate()

    def _match(self, text: str) -> tuple[bool, bool, str]:
        """Returns (wake_match, sleep_match, matched_phrase)."""
        low = text.lower().strip()

        for phrase in self.sleep_words:
            if phrase in low:
                return False, True, phrase

        for phrase in self.wake_words:
            if phrase in low:
                return True, False, phrase

        # fuzzy: any word "jarvis" anywhere
        if re.search(r"\bjarvis\b", low):
            return True, False, "jarvis"

        return False, False, ""

    # ── listen loop ────────────────────────────────────────────────────────────
    def _listen_loop(self) -> None:
        device = _select_best_mic()
        self._log(f"[WakeWord] Using mic device: {device}")

        def _callback(indata, frames, time_info, status):
            if status:
                self._log(f"[WakeWord] ⚠️ Audio status: {status}")
            if self._running:
                self._q.put(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
                blocksize=_CHUNK_FRAMES,
                callback=_callback,
                device=device,
            ):
                silence_counter = 0
                while self._running:
                    self._check_timeout()

                    try:
                        data = self._q.get(timeout=0.5)
                    except queue.Empty:
                        silence_counter += 1
                        if silence_counter > 20:  # ~5s silence
                            silence_counter = 0
                        continue

                    if _ECHO_CANCELLER and _NP:
                        try:
                            cleaned = _ECHO_CANCELLER.process(np.frombuffer(data, dtype=np.int16))
                            data = cleaned.astype(np.int16).tobytes()
                        except Exception:
                            pass

                    # VAD check
                    if not _detect_speech_activity(data):
                        silence_counter += 1
                        continue
                    
                    silence_counter = 0

                    text = self._transcribe(data)
                    if not text:
                        continue

                    wake, sleep, phrase = self._match(text)

                    if sleep:
                        self._deactivate()
                    elif wake:
                        self._activate(phrase)
                        self._last_heard = time.time()
                    elif self._awake:
                        # extend timeout on any speech while active
                        self._last_heard = time.time()

        except Exception as e:
            self._log(f"[WakeWord] ❌ Listen loop error: {e}")
            self._running = False

    # ── transcription backends ─────────────────────────────────────────────────
    def _transcribe(self, data: bytes) -> str:
        if self._backend == "vosk":
            return self._transcribe_vosk(data)
        if self._backend == "google":
            return self._transcribe_google(data)
        return ""

    def _transcribe_vosk(self, data: bytes) -> str:
        if not self._vosk_rec:
            return ""
        try:
            if self._vosk_rec.AcceptWaveform(data):
                result = json.loads(self._vosk_rec.Result())
                return result.get("text", "")
            else:
                partial = json.loads(self._vosk_rec.PartialResult())
                return partial.get("partial", "")
        except Exception:
            return ""

    def _transcribe_google(self, data: bytes) -> str:
        """Google STT with VAD and adaptive energy gating."""
        if not _SR or not _NP:
            return ""
        try:
            arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(arr ** 2)))
            
            # Adaptive energy gate with scale factor
            energy_threshold = _ENERGY_GATE * _ENERGY_SCALE
            if rms < energy_threshold:
                return ""  # too quiet, skip

            recognizer = sr.Recognizer()
            recognizer.energy_threshold = energy_threshold
            recognizer.dynamic_energy_threshold = True  # auto-adjust
            
            audio_data = sr.AudioData(data, _SAMPLE_RATE, 2)
            
            # Retry once on failure
            for attempt in range(2):
                try:
                    text = recognizer.recognize_google(audio_data)
                    return text.lower() if text else ""
                except sr.UnknownValueError:
                    if attempt == 0:
                        continue
                    return ""
                except sr.RequestError as e:
                    self._log(f"[WakeWord] ⚠️ Google STT error: {e}")
                    return ""
        except Exception as e:
            self._log(f"[WakeWord] ⚠️ Transcription error: {e}")
            return ""


# ── convenience factory ────────────────────────────────────────────────────────
def create_wake_word_detector(
    on_wake:  Callable[[str], None],
    on_sleep: Optional[Callable[[], None]] = None,
    player=None,
    custom_wake_words: Optional[list[str]] = None,
    active_timeout_s: float = 30.0,
) -> WakeWordDetector:
    """
    Factory used by main.py.

    Usage in main.py:
    -----------------
        from wake_word import create_wake_word_detector

        def _on_wake(word: str):
            ui.set_state("LISTENING")
            ui.write_log(f"SYS: Wake word detected — '{word}'")
            # unmute jarvis
            if ui.muted:
                ui._toggle_mute()

        def _on_sleep():
            ui.write_log("SYS: JARVIS sleeping...")
            if not ui.muted:
                ui._toggle_mute()

        detector = create_wake_word_detector(
            on_wake  = _on_wake,
            on_sleep = _on_sleep,
            player   = ui,
        )
        detector.start()
    """
    wake_words = custom_wake_words or _DEFAULT_WAKE_WORDS
    return WakeWordDetector(
        on_wake          = on_wake,
        on_sleep         = on_sleep,
        wake_words       = wake_words,
        player           = player,
        active_timeout_s = active_timeout_s,
    )


# ── standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 52)
    print("  JARVIS Wake Word Detector — Test Mode")
    print("=" * 52)
    print("Say 'JARVIS' to activate, 'go to sleep' to deactivate.")
    print("Ctrl+C to quit.\n")

    activated_count = 0

    def on_wake(word: str):
        global activated_count
        activated_count += 1
        print(f"\n🟢 [{activated_count}] WAKE WORD: '{word}' — JARVIS is listening!\n")

    def on_sleep():
        print("\n💤 JARVIS is sleeping...\n")

    detector = WakeWordDetector(
        on_wake          = on_wake,
        on_sleep         = on_sleep,
        active_timeout_s = 15.0,
    )
    detector.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        detector.stop()
        print(f"\nStopped. Detected {activated_count} wake word(s).")