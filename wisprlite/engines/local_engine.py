"""Local Whisper via faster-whisper. Fully offline, free per-use.

The model loads once (a few seconds, and downloads ~150 MB on first ever use)
and is reused. The app pre-warms it in the background at startup.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .base import Engine, OnPartial, Session


class _LocalSession(Session):
    def __init__(self, engine: "LocalEngine", on_partial: Optional[OnPartial]) -> None:
        self._engine = engine
        self._on_partial = on_partial

    def finish(self, audio: np.ndarray) -> str:
        if audio is None or audio.size == 0:
            return ""
        if self._on_partial:
            self._on_partial("Transcribing (local)…")
        audio = audio.astype("float32").flatten()
        segments, _info = self._engine.model.transcribe(
            audio,
            language=self._engine.language,
            beam_size=1,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()


class LocalEngine(Engine):
    name = "local"
    streaming = False

    def __init__(
        self,
        model_size: str = "base.en",
        language: Optional[str] = None,
        device: str = "auto",
        compute_type: str = "int8",
    ) -> None:
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.language = language or None

    def start_session(self, on_partial: Optional[OnPartial] = None) -> Session:
        return _LocalSession(self, on_partial)
