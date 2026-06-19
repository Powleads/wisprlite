"""Unified engine/session interface.

Every engine exposes ``start_session(on_partial)`` which returns a Session.
The app then, for every utterance:

    session = engine.start_session(on_partial=overlay.set_text)
    recorder.start(on_frame=session.feed)   # streaming engines consume frames
    audio = recorder.stop()
    text = session.finish(audio)            # batch engines transcribe the buffer

Batch engines (OpenAI, local Whisper) ignore ``feed`` and transcribe the audio
buffer in ``finish``. Streaming engines (Deepgram) consume ``feed`` live, call
``on_partial`` with interim text, and ignore the buffer in ``finish``.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np

OnPartial = Callable[[str], None]


class Session:
    def feed(self, pcm_int16: bytes) -> None:  # noqa: D401 - simple hook
        """Consume a chunk of 16-bit PCM (streaming engines only)."""

    def finish(self, audio: np.ndarray) -> str:
        """Return the final transcript."""
        return ""

    def cancel(self) -> None:
        """Abort without typing anything."""


class Engine:
    name: str = "base"
    streaming: bool = False

    def start_session(self, on_partial: Optional[OnPartial] = None) -> Session:
        raise NotImplementedError
