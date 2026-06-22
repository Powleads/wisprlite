"""Trailing-silence endpointer for hands-free capture.

Pure decision logic over the recorder's smoothed RMS level (audio.py:24).
Stop only after speech has started AND the level has stayed below `threshold`
for `silence_ms`. No DSP, no deps.
"""

from __future__ import annotations


class SilenceEndpointer:
    def __init__(self, threshold: float = 0.02, silence_ms: int = 800, block_ms: int = 50) -> None:
        self.threshold = threshold
        self.silence_blocks_needed = max(1, int(round(silence_ms / max(1, block_ms))))
        self._speech_started = False
        self._silent_blocks = 0

    @property
    def heard_speech(self) -> bool:
        """True once any above-threshold audio has been seen this capture."""
        return self._speech_started

    def feed(self, level: float) -> bool:
        """Return True when the capture should stop."""
        if level >= self.threshold:
            self._speech_started = True
            self._silent_blocks = 0
            return False
        if self._speech_started:
            self._silent_blocks += 1
            if self._silent_blocks >= self.silence_blocks_needed:
                return True
        return False
