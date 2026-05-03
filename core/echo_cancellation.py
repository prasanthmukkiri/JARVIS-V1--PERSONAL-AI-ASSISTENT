"""
Echo Cancellation (AEC) Module
=============================
Detects and suppresses Jarvis's own audio from microphone input.

Helps with:
- Simultaneous speech scenarios (user + Jarvis talking)
- Echo from speakers affecting wake-word detection
- Improved robustness in rooms with audio feedback

Integration:
    aec = EchoCanceller(sample_rate=16000)
    
    # During Jarvis output
    aec.set_reference_audio(jarvis_audio_chunk)
    
    # During mic capture
    cleaned = aec.process(mic_audio_chunk)
"""

from __future__ import annotations

import numpy as np
from collections import deque


class EchoCanceller:
    """Simple acoustic echo cancellation using LMS adaptive filtering."""

    def __init__(self, sample_rate: int = 16000, filter_length: int = 512, step_size: float = 0.01):
        """
        Initialize echo canceller.

        Args:
            sample_rate: Audio sample rate (default 16000 Hz)
            filter_length: Length of adaptive filter taps
            step_size: LMS step size (0.001-0.1, lower=more stable)
        """
        self.sample_rate = sample_rate
        self.filter_length = filter_length
        self.step_size = step_size

        # Adaptive filter weights
        self.weights = np.zeros(filter_length, dtype=np.float32)

        # Buffers
        self.ref_buffer = deque(maxlen=filter_length)  # Reference (speaker) signal
        self.input_buffer = deque(maxlen=filter_length)  # Microphone signal

        # Statistics
        self.ref_power = 0.0
        self.processed_count = 0

    def set_reference_audio(self, audio_chunk: bytes | np.ndarray, dtype=np.int16):
        """
        Provide reference audio from Jarvis output.

        Args:
            audio_chunk: Audio data to use as reference
            dtype: Data type (default int16)
        """
        if isinstance(audio_chunk, bytes):
            audio_chunk = np.frombuffer(audio_chunk, dtype=dtype).astype(np.float32) / 32768.0
        elif isinstance(audio_chunk, np.ndarray):
            if audio_chunk.dtype != np.float32:
                audio_chunk = audio_chunk.astype(np.float32) / 32768.0

        for sample in audio_chunk:
            self.ref_buffer.append(sample)

    def process(self, mic_audio: bytes | np.ndarray, dtype=np.int16) -> np.ndarray:
        """
        Process microphone audio and remove echo.

        Args:
            mic_audio: Microphone audio to clean
            dtype: Data type (default int16)

        Returns:
            Echo-cancelled audio
        """
        if isinstance(mic_audio, bytes):
            mic_audio = np.frombuffer(mic_audio, dtype=dtype).astype(np.float32) / 32768.0
        elif isinstance(mic_audio, np.ndarray):
            if mic_audio.dtype != np.int16 and mic_audio.dtype != np.float32:
                mic_audio = mic_audio.astype(np.float32) / 32768.0
            elif mic_audio.dtype == np.int16:
                mic_audio = mic_audio.astype(np.float32) / 32768.0

        output = np.zeros_like(mic_audio, dtype=np.float32)

        for i, sample in enumerate(mic_audio):
            self.input_buffer.append(sample)

            # Current reference signal (from speaker output)
            if len(self.ref_buffer) >= self.filter_length:
                ref_vector = np.array(list(self.ref_buffer)[:self.filter_length][::-1], dtype=np.float32)
            else:
                ref_vector = np.zeros(self.filter_length, dtype=np.float32)
                ref_vector[:len(self.ref_buffer)] = np.array(list(self.ref_buffer)[::-1], dtype=np.float32)

            # Estimate echo using adaptive filter
            echo_estimate = np.dot(self.weights, ref_vector)

            # Error signal (mic input - estimated echo)
            error = sample - echo_estimate

            # Update filter weights (LMS algorithm)
            if np.abs(echo_estimate) > 0.001:  # Only adapt if there's signal
                self.weights += self.step_size * error * ref_vector

            # Clip weights to prevent divergence
            self.weights = np.clip(self.weights, -1.0, 1.0)

            output[i] = error
            self.processed_count += 1

        return output

    def get_stats(self) -> dict:
        """Get statistics about echo cancellation."""
        return {
            "processed_samples": self.processed_count,
            "processed_duration_seconds": self.processed_count / self.sample_rate,
            "filter_length": self.filter_length,
            "weights_range": (float(self.weights.min()), float(self.weights.max())),
        }


class EnergyGateEchoCanceller:
    """Simpler echo canceller based on energy gating."""

    def __init__(self, threshold_db: float = -40, min_duration_ms: float = 100):
        """
        Initialize energy-based echo canceller.

        Args:
            threshold_db: Silence threshold in dB
            min_duration_ms: Minimum duration of speech for cancellation
        """
        self.threshold_db = threshold_db
        self.min_duration_ms = min_duration_ms
        self.is_jarvis_speaking = False
        self.jarvis_start_time = 0

    def set_speaking(self, is_speaking: bool):
        """Set whether Jarvis is currently speaking."""
        import time

        self.is_jarvis_speaking = is_speaking
        if is_speaking:
            self.jarvis_start_time = time.time()

    def process(self, audio_chunk: np.ndarray) -> np.ndarray:
        """
        Apply energy gating to suppress echo when Jarvis is speaking.

        Args:
            audio_chunk: Audio to process

        Returns:
            Potentially gated audio
        """
        if not self.is_jarvis_speaking:
            return audio_chunk

        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        db = 20 * np.log10(rms + 1e-10)

        # If Jarvis is speaking and input is above silence threshold, suppress it
        if db > self.threshold_db:
            return audio_chunk * 0.5  # Reduce by 50%

        return audio_chunk


# Export
__all__ = ["EchoCanceller", "EnergyGateEchoCanceller"]
