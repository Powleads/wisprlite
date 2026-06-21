"""Deepgram streaming transcription (websocket).

Lowest latency: words come back while you're still talking, so the overlay
shows a live partial transcript. On release we wait briefly for the final
result and type it. Handlers accept *args/**kwargs because the deepgram-sdk
has shifted callback signatures between minor versions.
"""

from __future__ import annotations

import threading
from typing import Optional

import numpy as np

from .base import Engine, OnPartial, Session

SAMPLE_RATE = 16_000


def _pick(args, kwargs, key):
    if key in kwargs and kwargs[key] is not None:
        return kwargs[key]
    # the payload is passed positionally (often after the connection instance)
    for a in reversed(args):
        if a is not None and not isinstance(a, (str, bytes)):
            return a
    return None


class _DeepgramSession(Session):
    def __init__(self, engine: "DeepgramEngine", on_partial: Optional[OnPartial]) -> None:
        from deepgram import LiveOptions, LiveTranscriptionEvents

        self._on_partial = on_partial
        self._finals: list[str] = []
        self._done = threading.Event()
        self._error: Optional[str] = None
        self._finish_timeout = getattr(engine, "finish_timeout", 6.0)

        listen = engine.client.listen
        if hasattr(listen, "websocket"):
            self.conn = listen.websocket.v("1")
        else:  # older v3 layout
            self.conn = listen.live.v("1")

        def on_transcript(*args, **kwargs):
            try:
                result = _pick(args, kwargs, "result")
                alt = result.channel.alternatives[0]
                text = (alt.transcript or "").strip()
                if not text:
                    return
                if getattr(result, "is_final", False):
                    self._finals.append(text)
                    live = " ".join(self._finals)
                else:
                    live = " ".join(self._finals + [text])
                if self._on_partial:
                    self._on_partial(live)
            except Exception:
                pass

        def on_error(*args, **kwargs):
            err = _pick(args, kwargs, "error")
            self._error = str(err) if err is not None else "deepgram error"
            self._done.set()

        def on_close(*args, **kwargs):
            self._done.set()

        self.conn.on(LiveTranscriptionEvents.Transcript, on_transcript)
        self.conn.on(LiveTranscriptionEvents.Error, on_error)
        self.conn.on(LiveTranscriptionEvents.Close, on_close)

        opts = dict(
            model=engine.model,
            language=engine.language or "en-US",
            encoding="linear16",
            sample_rate=SAMPLE_RATE,
            channels=1,
            interim_results=True,
            smart_format=True,
            punctuate=True,
        )
        if engine.keywords:
            opts["keywords"] = engine.keywords  # bias toward these terms
        try:
            options = LiveOptions(**opts)
        except TypeError:
            opts.pop("keywords", None)  # some versions reject unknown kwargs
            options = LiveOptions(**opts)
        if not self.conn.start(options):
            raise RuntimeError("Deepgram connection failed to start")

    def feed(self, pcm_int16: bytes) -> None:
        try:
            self.conn.send(pcm_int16)
        except Exception:
            pass

    def finish(self, audio: np.ndarray) -> str:
        try:
            self.conn.finish()
        except Exception:
            pass
        self._done.wait(timeout=self._finish_timeout)
        if self._error:
            raise RuntimeError(self._error)
        return " ".join(self._finals).strip()

    def cancel(self) -> None:
        try:
            self.conn.finish()
        except Exception:
            pass


class DeepgramEngine(Engine):
    name = "deepgram"
    streaming = True

    def __init__(self, api_key: str, model: str = "nova-2", language: str = "en-US",
                 keywords: Optional[list] = None, finish_timeout: float = 6.0) -> None:
        from deepgram import DeepgramClient

        self.client = DeepgramClient(api_key)
        self.model = model
        self.language = language
        self.keywords = keywords or None
        self.finish_timeout = finish_timeout

    def start_session(self, on_partial: Optional[OnPartial] = None) -> Session:
        return _DeepgramSession(self, on_partial)
