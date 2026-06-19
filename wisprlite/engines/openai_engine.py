"""OpenAI Whisper API (batch). Accurate, near-zero setup, needs internet."""

from __future__ import annotations

import io
import wave
from typing import Optional

import numpy as np

from .base import Engine, OnPartial, Session

SAMPLE_RATE = 16_000


def _wav_bytes(audio: np.ndarray) -> bytes:
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


class _OpenAISession(Session):
    def __init__(self, engine: "OpenAIEngine", on_partial: Optional[OnPartial]) -> None:
        self._engine = engine
        self._on_partial = on_partial

    def finish(self, audio: np.ndarray) -> str:
        if audio is None or audio.size == 0:
            return ""
        kwargs = {
            "model": self._engine.model,
            "file": ("speech.wav", _wav_bytes(audio), "audio/wav"),
        }
        if self._engine.language:
            kwargs["language"] = self._engine.language
        resp = self._engine.client.audio.transcriptions.create(**kwargs)
        return (resp.text or "").strip()


class OpenAIEngine(Engine):
    name = "openai"
    streaming = False

    def __init__(self, model: str = "whisper-1", language: Optional[str] = None) -> None:
        from openai import OpenAI

        self.client = OpenAI()  # reads OPENAI_API_KEY from env
        self.model = model
        self.language = language or None

    def start_session(self, on_partial: Optional[OnPartial] = None) -> Session:
        return _OpenAISession(self, on_partial)
