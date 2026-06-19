"""Microphone capture.

Records 16 kHz mono float32 (what Whisper wants). While recording it can also
push int16 PCM frames to a streaming consumer (Deepgram) and exposes a live
input level for the overlay's VU meter.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
CHANNELS = 1
BLOCKSIZE = 800  # 50 ms chunks -> responsive meter + low-latency streaming


class Recorder:
    def __init__(self, device=None) -> None:
        self.device = device
        self.level = 0.0  # smoothed RMS, ~0..0.3 for speech
        self._frames: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._on_frame: Optional[Callable[[bytes], None]] = None
        self._lock = threading.Lock()

    def start(self, on_frame: Optional[Callable[[bytes], None]] = None) -> None:
        with self._lock:
            self._frames = []
        self._on_frame = on_frame
        self.level = 0.0
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            device=self.device,
            blocksize=BLOCKSIZE,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        if indata.size:
            rms = float(np.sqrt(np.mean(indata ** 2)))
            # attack fast, release slow -> a lively but stable meter
            self.level = rms if rms > self.level else self.level * 0.7
        with self._lock:
            self._frames.append(indata.copy())
        if self._on_frame is not None:
            pcm = (np.clip(indata, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
            try:
                self._on_frame(pcm)
            except Exception:
                pass

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.level = 0.0
        with self._lock:
            if not self._frames:
                return np.empty((0,), dtype="float32")
            return np.concatenate(self._frames, axis=0).flatten()
