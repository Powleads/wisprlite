# PipeVoice Agent MCP (`listen` + `transcribe`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose two MCP tools from the running PipeVoice tray app — `pipevoice.listen` (ask the user for a spoken answer on demand) and `pipevoice.transcribe` (turn a local audio/video file into timed text via local whisper) — so AI agents get voice input and a key-free transcription service.

**Architecture:** Approach B from the spec. A lightweight stdio MCP server (`Pipevoice.exe --mcp` / `python -m wisprlite --mcp`), spawned by the client, forwards calls over a stdlib loopback TCP "control bridge" to the resident tray app. The resident app keeps near-zero footprint (no web framework); it reuses the existing recorder/overlay/engine/cleanup pipeline for `listen` and a warm local-whisper model for `transcribe`.

**Tech Stack:** Python 3.10+, `faster-whisper` (already a dep, supports `word_timestamps`), the official `mcp` SDK (new dep, used only in the shim), stdlib `socket`/`json`/`threading`/`concurrent.futures`. Target OS Windows; pure-logic units are developed and tested on the Linux dev box with plain `python3` + `assert` (the repo has no pytest/test harness — matching that norm).

**Spec:** `docs/superpowers/specs/2026-06-22-pipevoice-agent-mcp-listen-design.md`

**Testing convention:** Pure units get a standalone `tests/test_*.py` run with `python3 tests/test_x.py` (asserts; exits non-zero on failure). GUI/mic/model/SDK paths can't run on the Linux dev box and carry an explicit **Manual verification (Windows)** checklist instead.

**Branch:** `feat/agent-mcp-listen` (already created).

---

## File map

| File | New/Mod | Responsibility |
|---|---|---|
| `wisprlite/captions.py` | New | Pure SRT/VTT formatting from segment dicts. |
| `wisprlite/vad.py` | New | Pure trailing-silence endpointer for hands-free listen. |
| `wisprlite/agent_bridge.py` | New | Loopback TCP control bridge (listener + client) + JSON line protocol. |
| `wisprlite/engines/local_engine.py` | Mod | Add module-level `transcribe_file()` + `_segments_to_dicts()` (warm model, word timestamps). |
| `wisprlite/mcp_shim.py` | New | `--mcp` stdio MCP server exposing `listen`+`transcribe`, forwarding via the bridge. |
| `wisprlite/config.py` | Mod | New config fields (mcp_enabled/port/mode/silence/transcribe model). |
| `wisprlite/app.py` | Mod | `_polish()` refactor; `on_agent_listen/transcribe`, `_agent_dispatch`, bridge lifecycle, tray hook, `_finish` routing. |
| `wisprlite/tray.py` | Mod | "Agent MCP" toggle menu item. |
| `wisprlite/__main__.py` | Mod | `--mcp` dispatch. |
| `requirements.txt` | Mod | Add `mcp`. |
| `tests/test_captions.py`, `tests/test_vad.py`, `tests/test_agent_bridge.py`, `tests/test_transcribe_shaper.py`, `tests/test_mcp_send.py` | New | Pure-unit checks. |
| `README.md` / `docs/index.html` | Mod | Document the MCP feature + `claude mcp add`. |

---

## Task 1: Captions formatter (`captions.py`)

**Files:**
- Create: `wisprlite/captions.py`
- Test: `tests/test_captions.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_captions.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import captions

SEGS = [
    {"start": 0.0, "end": 1.5, "text": "Hello there.", "words": []},
    {"start": 1.5, "end": 3.25, "text": "General Kenobi.", "words": []},
]

def test_format_timestamp():
    assert captions.format_timestamp(0) == "00:00:00,000"
    assert captions.format_timestamp(3.25) == "00:00:03,250"
    assert captions.format_timestamp(3661.5, vtt=True) == "01:01:01.500"
    assert captions.format_timestamp(-2) == "00:00:00,000"

def test_to_srt():
    out = captions.to_srt(SEGS)
    assert out == (
        "1\n00:00:00,000 --> 00:00:01,500\nHello there.\n\n"
        "2\n00:00:01,500 --> 00:00:03,250\nGeneral Kenobi.\n"
    )

def test_to_vtt():
    out = captions.to_vtt(SEGS)
    assert out.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.500\nHello there." in out
    assert "00:00:01.500 --> 00:00:03.250\nGeneral Kenobi." in out

if __name__ == "__main__":
    test_format_timestamp(); test_to_srt(); test_to_vtt()
    print("OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_captions.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'wisprlite.captions'`

- [ ] **Step 3: Write minimal implementation**

Create `wisprlite/captions.py`:

```python
"""Pure SRT / WebVTT formatting from segment dicts.

A segment dict is {"start": float, "end": float, "text": str, "words": [...]}.
No dependencies, no I/O — trivially testable.
"""

from __future__ import annotations


def format_timestamp(seconds: float, vtt: bool = False) -> str:
    if seconds is None or seconds < 0:
        seconds = 0.0
    ms_total = int(round(seconds * 1000))
    h, ms_total = divmod(ms_total, 3_600_000)
    m, ms_total = divmod(ms_total, 60_000)
    s, ms = divmod(ms_total, 1000)
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(segments) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}")
        lines.append((seg.get("text") or "").strip())
        lines.append("")
    return ("\n".join(lines).strip() + "\n") if lines else ""


def to_vtt(segments) -> str:
    out = ["WEBVTT", ""]
    for seg in segments:
        out.append(f"{format_timestamp(seg['start'], vtt=True)} --> {format_timestamp(seg['end'], vtt=True)}")
        out.append((seg.get("text") or "").strip())
        out.append("")
    return "\n".join(out).strip() + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_captions.py`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add wisprlite/captions.py tests/test_captions.py
git commit -m "feat(mcp): captions.py — SRT/VTT formatting from segment dicts"
```

---

## Task 2: Silence endpointer (`vad.py`)

**Files:**
- Create: `wisprlite/vad.py`
- Test: `tests/test_vad.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_vad.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite.vad import SilenceEndpointer

def feed_seq(ep, levels):
    return [ep.feed(x) for x in levels]

def test_leading_silence_never_triggers():
    ep = SilenceEndpointer(threshold=0.02, silence_ms=200, block_ms=50)  # 4 silent blocks
    assert not any(feed_seq(ep, [0.0] * 50))  # no speech yet -> never stop

def test_speech_then_silence_triggers():
    ep = SilenceEndpointer(threshold=0.02, silence_ms=200, block_ms=50)  # 4 blocks
    results = feed_seq(ep, [0.1, 0.1, 0.0, 0.0, 0.0, 0.0])  # speak, then 4 silent
    assert results[-1] is True
    assert results[:4] == [False, False, False, False]  # not yet (needs 4 silent)

def test_sustained_speech_never_triggers():
    ep = SilenceEndpointer(threshold=0.02, silence_ms=200, block_ms=50)
    assert not any(feed_seq(ep, [0.1] * 50))

def test_silence_resets_on_new_speech():
    ep = SilenceEndpointer(threshold=0.02, silence_ms=200, block_ms=50)
    feed_seq(ep, [0.1, 0.0, 0.0, 0.1])  # 2 silent then speech resets the counter
    assert ep.feed(0.0) is False  # only 1 silent block since the reset

if __name__ == "__main__":
    test_leading_silence_never_triggers(); test_speech_then_silence_triggers()
    test_sustained_speech_never_triggers(); test_silence_resets_on_new_speech()
    print("OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_vad.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'wisprlite.vad'`

- [ ] **Step 3: Write minimal implementation**

Create `wisprlite/vad.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_vad.py`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add wisprlite/vad.py tests/test_vad.py
git commit -m "feat(mcp): vad.py — trailing-silence endpointer for hands-free listen"
```

---

## Task 3: Control bridge (`agent_bridge.py`)

**Files:**
- Create: `wisprlite/agent_bridge.py`
- Test: `tests/test_agent_bridge.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_bridge.py`:

```python
import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import agent_bridge

def test_roundtrip_and_dispatch():
    seen = {}
    def dispatch(req):
        seen["req"] = req
        if req["op"] == "ping":
            return {"status": "ok", "text": "pong"}
        return {"status": "error", "error": "unknown op"}

    listener = agent_bridge.ControlListener(0, dispatch)  # port 0 -> ephemeral
    listener.start()
    port = listener.port  # resolved after bind
    try:
        resp = agent_bridge.send_request(port, {"op": "ping", "x": 1}, timeout=5.0)
        assert resp == {"status": "ok", "text": "pong"}, resp
        assert seen["req"] == {"op": "ping", "x": 1}, seen
        bad = agent_bridge.send_request(port, {"op": "nope"}, timeout=5.0)
        assert bad["status"] == "error", bad
    finally:
        listener.stop()

def test_dispatch_exception_becomes_error():
    def dispatch(req):
        raise ValueError("boom")
    listener = agent_bridge.ControlListener(0, dispatch)
    listener.start()
    try:
        resp = agent_bridge.send_request(listener.port, {"op": "x"}, timeout=5.0)
        assert resp["status"] == "error" and "boom" in resp["error"], resp
    finally:
        listener.stop()

if __name__ == "__main__":
    test_roundtrip_and_dispatch(); test_dispatch_exception_becomes_error()
    print("OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_agent_bridge.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'wisprlite.agent_bridge'`

- [ ] **Step 3: Write minimal implementation**

Create `wisprlite/agent_bridge.py`:

```python
"""Loopback control bridge: lets the `--mcp` shim drive the running tray app.

Stdlib socket + newline-delimited JSON. Binds 127.0.0.1 only. Lazy/optional:
if it can't bind, the caller logs and the feature stays off. This keeps the
resident app's footprint to a single stdlib socket listener — no web framework.
"""

from __future__ import annotations

import json
import socket
import threading
from typing import Callable


def encode(obj) -> bytes:
    return (json.dumps(obj) + "\n").encode("utf-8")


def decode(line: bytes) -> dict:
    return json.loads(line.decode("utf-8"))


def send_request(port: int, obj: dict, timeout: float = 120.0) -> dict:
    """Client side (used by the shim). Connect, send one request, read one reply."""
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as s:
        s.settimeout(timeout)
        s.sendall(encode(obj))
        f = s.makefile("rb")
        line = f.readline()
        return decode(line) if line else {"status": "error", "error": "no response"}


class ControlListener:
    """Accepts one JSON request per connection, calls ``dispatch(req) -> resp``."""

    def __init__(self, port: int, dispatch: Callable[[dict], dict]) -> None:
        self.port = port
        self.dispatch = dispatch
        self._sock = None
        self._thread = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.port))
        self.port = self._sock.getsockname()[1]  # resolve ephemeral (port 0)
        self._sock.listen(4)
        self._sock.settimeout(0.5)
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn) -> None:
        try:
            f = conn.makefile("rwb")
            line = f.readline()
            if not line:
                return
            try:
                resp = self.dispatch(decode(line))
            except Exception as exc:  # never crash the bridge on a bad request
                resp = {"status": "error", "error": str(exc)}
            f.write(encode(resp))
            f.flush()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_agent_bridge.py`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add wisprlite/agent_bridge.py tests/test_agent_bridge.py
git commit -m "feat(mcp): agent_bridge.py — loopback JSON control bridge"
```

---

## Task 4: Transcribe function (`local_engine.transcribe_file`)

**Files:**
- Modify: `wisprlite/engines/local_engine.py` (append module-level functions after the `LocalEngine` class, currently ends at line 57)
- Test: `tests/test_transcribe_shaper.py`

The faster-whisper call needs a model + audio (not runnable on the Linux box), so we isolate the **pure** segment→dict shaping into `_segments_to_dicts()` and test that with fake objects. The model glue is verified manually on Windows (Task 12).

- [ ] **Step 1: Write the failing test**

Create `tests/test_transcribe_shaper.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite.engines.local_engine import _segments_to_dicts

class W:
    def __init__(self, start, end, word): self.start, self.end, self.word = start, end, word

class S:
    def __init__(self, start, end, text, words): self.start, self.end, self.text, self.words = start, end, text, words

def test_shaping_with_words():
    segs = [S(0.0, 1.234567, " Hello ", [W(0.0, 0.5, "Hello")])]
    out = _segments_to_dicts(segs)
    assert out == [{"start": 0.0, "end": 1.235, "text": "Hello",
                    "words": [{"start": 0.0, "end": 0.5, "word": "Hello"}]}], out

def test_shaping_without_words():
    segs = [S(1.0, 2.0, "no words", None)]
    out = _segments_to_dicts(segs)
    assert out[0]["words"] == [], out

if __name__ == "__main__":
    test_shaping_with_words(); test_shaping_without_words()
    print("OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_transcribe_shaper.py`
Expected: FAIL — `ImportError: cannot import name '_segments_to_dicts'`

- [ ] **Step 3: Write minimal implementation**

Append to `wisprlite/engines/local_engine.py` (after line 57):

```python


# ---- file transcription with word-level timestamps (for the agent MCP) -------
import threading as _threading

_TRANSCRIBE_MODEL = None
_TRANSCRIBE_KEY = None
_TRANSCRIBE_LOCK = _threading.Lock()


def _segments_to_dicts(segments) -> list:
    """Shape faster-whisper segments into plain JSON-able dicts. Pure."""
    out = []
    for seg in segments:
        words = []
        for w in (getattr(seg, "words", None) or []):
            words.append({"start": round(float(w.start), 3),
                          "end": round(float(w.end), 3),
                          "word": w.word})
        out.append({"start": round(float(seg.start), 3),
                    "end": round(float(seg.end), 3),
                    "text": (seg.text or "").strip(),
                    "words": words})
    return out


def _get_transcribe_model(model_size: str, device: str = "auto", compute_type: str = "int8"):
    global _TRANSCRIBE_MODEL, _TRANSCRIBE_KEY
    key = (model_size, device, compute_type)
    if _TRANSCRIBE_MODEL is None or _TRANSCRIBE_KEY != key:
        from faster_whisper import WhisperModel
        _TRANSCRIBE_MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
        _TRANSCRIBE_KEY = key
    return _TRANSCRIBE_MODEL


def transcribe_file(path: str, *, language=None, model_size: str = "base.en",
                    device: str = "auto", compute_type: str = "int8") -> dict:
    """Transcribe an audio/video file to text + word/segment timestamps.

    Serialized behind a lock (one shared warm model). faster-whisper decodes
    audio from many container formats via its bundled PyAV/ffmpeg.
    """
    with _TRANSCRIBE_LOCK:
        model = _get_transcribe_model(model_size, device, compute_type)
        segments, info = model.transcribe(
            path, language=language or None, word_timestamps=True,
            vad_filter=True, beam_size=1,
        )
        seg_dicts = _segments_to_dicts(segments)  # consumes the generator inside the lock
    text = " ".join(s["text"] for s in seg_dicts).strip()
    return {"text": text,
            "language": getattr(info, "language", None),
            "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 3),
            "segments": seg_dicts}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_transcribe_shaper.py`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add wisprlite/engines/local_engine.py tests/test_transcribe_shaper.py
git commit -m "feat(mcp): local_engine.transcribe_file with word timestamps"
```

---

## Task 5: Config fields (`config.py`)

**Files:**
- Modify: `wisprlite/config.py` (the `Config` dataclass; add after line 86 `profiles: list = ...`)

- [ ] **Step 1: Add the fields**

In `wisprlite/config.py`, immediately after the `profiles` field (line 86), add:

```python
    # Agent MCP server (listen + transcribe). Off by default; opt-in via the tray.
    mcp_enabled: bool = False
    mcp_port: int = 49518             # loopback control bridge (distinct from the 49517 lock)
    mcp_default_mode: str = "push_to_talk"  # push_to_talk | hands_free  (for `listen`)
    hands_free_silence_ms: int = 800  # trailing silence that ends a hands-free capture
    transcribe_model_size: str = ""   # blank = reuse local_model_size
```

- [ ] **Step 2: Verify it loads**

Run: `python3 -c "from wisprlite.config import Config; c=Config(); print(c.mcp_enabled, c.mcp_port, c.mcp_default_mode, c.hands_free_silence_ms, repr(c.transcribe_model_size))"`
Expected: `False 49518 push_to_talk 800 ''`

- [ ] **Step 3: Commit**

```bash
git add wisprlite/config.py
git commit -m "feat(mcp): config fields for the agent MCP server"
```

---

## Task 6: App — bridge lifecycle, dispatch, tray toggle, transcribe handler

**Files:**
- Modify: `wisprlite/app.py`

Transcribe is the path with no GUI/mic dependency, so it's wired (and bridge-testable) first.

- [ ] **Step 1: Add init state**

In `App.__init__`, after `self._stop = threading.Event()` (line 58), add:

```python
        self._pending_agent_listen = None   # set while a listen() awaits the user's hotkey
        self._bridge = None                  # agent_bridge.ControlListener when MCP is on
```

- [ ] **Step 2: Add the dispatch + transcribe handler + bridge lifecycle**

Add these methods to `App` (e.g. after `toggle_pause`, line 284):

```python
    # ---- agent MCP -------------------------------------------------------
    def _agent_dispatch(self, req: dict) -> dict:
        op = req.get("op")
        if op == "listen":
            return self.on_agent_listen(req.get("prompt", ""), req.get("timeout", 45), req.get("mode", ""))
        if op == "transcribe":
            return self.on_agent_transcribe(req.get("path", ""), req.get("format", "json"),
                                            req.get("language", ""), req.get("model_size", ""))
        return {"status": "error", "error": f"unknown op: {op}"}

    def on_agent_transcribe(self, path="", fmt="json", language="", model_size="") -> dict:
        import os
        if not path or not os.path.exists(path):
            return {"status": "error", "error": f"file not found: {path}"}
        size = model_size or self.cfg.transcribe_model_size or self.cfg.local_model_size
        try:
            from .engines.local_engine import transcribe_file
            r = transcribe_file(path, language=(language or None), model_size=size)
        except Exception as exc:
            log.exception("agent transcribe failed")
            return {"status": "error", "error": str(exc)}
        out = {"status": "ok", "text": r["text"], "language": r["language"], "duration": r["duration"]}
        fmt = (fmt or "json").lower()
        if fmt in ("srt", "vtt"):
            from . import captions
            out["captions"] = captions.to_srt(r["segments"]) if fmt == "srt" else captions.to_vtt(r["segments"])
        else:
            out["segments"] = r["segments"]
        return out

    def _mcp_add_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'claude mcp add pipevoice -- "{sys.executable}" --mcp'
        return "claude mcp add pipevoice -- python -m wisprlite --mcp"

    def start_mcp_bridge(self) -> None:
        if self._bridge is not None:
            return
        try:
            from .agent_bridge import ControlListener
            self._bridge = ControlListener(self.cfg.mcp_port, self._agent_dispatch)
            self._bridge.start()
            log.info("MCP control bridge on 127.0.0.1:%s", self.cfg.mcp_port)
        except Exception as exc:
            self._bridge = None
            log.warning("MCP bridge failed to start: %s", exc)
            self._fail(f"MCP bridge: {exc}")

    def stop_mcp_bridge(self) -> None:
        if self._bridge is not None:
            try:
                self._bridge.stop()
            except Exception:
                pass
            self._bridge = None

    def toggle_mcp(self) -> None:
        self.cfg.mcp_enabled = not self.cfg.mcp_enabled
        self.cfg.save()
        if self.cfg.mcp_enabled:
            self.start_mcp_bridge()
            self._notify("Agent MCP on. Register once:\n" + self._mcp_add_command())
        else:
            self.stop_mcp_bridge()
        self.tray.update()
```

> `on_agent_listen` is added in Task 9; until then `_agent_dispatch` referencing it is fine because the method exists on the class by the time the bridge runs (Tasks 6→9 land before any `listen` call). For Task 8's bridge test we exercise only the `transcribe` and `ping`-style paths.

- [ ] **Step 3: Start/stop the bridge with the app lifecycle**

In `App.run()`, after `self.clip_hotkeys.start()` (line 494), add:

```python
        if self.cfg.mcp_enabled:
            self.start_mcp_bridge()
```

In `App.quit()` (line 386), after `self._stop.set()`, add:

```python
        self.stop_mcp_bridge()
```

- [ ] **Step 4: Verify imports resolve (no syntax/name errors)**

Run: `python3 -c "import ast,sys; ast.parse(open('wisprlite/app.py').read()); print('app.py parses')"`
Expected: `app.py parses`

(The app can't fully launch on Linux — no display/tray — so this is a parse check; behavior is verified in Tasks 7/12.)

- [ ] **Step 5: Commit**

```bash
git add wisprlite/app.py
git commit -m "feat(mcp): bridge lifecycle, dispatch, transcribe handler, tray toggle hook"
```

---

## Task 7: App — bridge transcribe end-to-end (integration test on Linux)

**Files:**
- Test: `tests/test_bridge_transcribe.py`

This proves the bridge → dispatch → transcribe wiring without a model by monkeypatching `transcribe_file`, and without the GUI by driving `_agent_dispatch` directly through a real socket round-trip.

- [ ] **Step 1: Write the test**

Create `tests/test_bridge_transcribe.py`:

```python
import sys, pathlib, tempfile, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import agent_bridge
from wisprlite.engines import local_engine

# Fake transcribe_file so no model/audio is needed.
def fake_transcribe_file(path, *, language=None, model_size="base.en", **kw):
    return {"text": "hello world", "language": "en", "duration": 1.0,
            "segments": [{"start": 0.0, "end": 1.0, "text": "hello world", "words": []}]}

def make_dispatch():
    # Minimal stand-in for App._agent_dispatch + on_agent_transcribe, reusing the real captions path.
    from wisprlite import captions
    def dispatch(req):
        if req.get("op") != "transcribe":
            return {"status": "error", "error": "unexpected op"}
        path = req["path"]
        if not os.path.exists(path):
            return {"status": "error", "error": "file not found"}
        r = fake_transcribe_file(path)
        out = {"status": "ok", "text": r["text"], "language": r["language"], "duration": r["duration"]}
        if req.get("format") == "srt":
            out["captions"] = captions.to_srt(r["segments"])
        else:
            out["segments"] = r["segments"]
        return out
    return dispatch

def test_transcribe_json_and_srt():
    listener = agent_bridge.ControlListener(0, make_dispatch())
    listener.start()
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            p = tf.name
        try:
            j = agent_bridge.send_request(listener.port, {"op": "transcribe", "path": p, "format": "json"})
            assert j["status"] == "ok" and j["text"] == "hello world" and "segments" in j, j
            srt = agent_bridge.send_request(listener.port, {"op": "transcribe", "path": p, "format": "srt"})
            assert srt["captions"].startswith("1\n00:00:00,000 --> 00:00:01,000"), srt
            miss = agent_bridge.send_request(listener.port, {"op": "transcribe", "path": "/no/such", "format": "json"})
            assert miss["status"] == "error", miss
        finally:
            os.unlink(p)
    finally:
        listener.stop()

if __name__ == "__main__":
    test_transcribe_json_and_srt()
    print("OK")
```

- [ ] **Step 2: Run it**

Run: `python3 tests/test_bridge_transcribe.py`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add tests/test_bridge_transcribe.py
git commit -m "test(mcp): bridge -> transcribe -> captions round-trip"
```

---

## Task 8: MCP shim (`mcp_shim.py` + `--mcp`)

**Files:**
- Create: `wisprlite/mcp_shim.py`
- Modify: `wisprlite/__main__.py`
- Modify: `requirements.txt`
- Test: `tests/test_mcp_send.py`

- [ ] **Step 1: Write the failing test (the `_send` forwarder, no SDK needed)**

Create `tests/test_mcp_send.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import agent_bridge, mcp_shim

def test_send_forwards_to_bridge(monkeypatch=None):
    listener = agent_bridge.ControlListener(0, lambda req: {"status": "ok", "echo": req})
    listener.start()
    try:
        # Point the shim at our ephemeral listener port.
        import wisprlite.mcp_shim as shim
        shim._port = lambda: listener.port
        resp = shim._send("transcribe", path="/x", format="json")
        assert resp["status"] == "ok", resp
        assert resp["echo"] == {"op": "transcribe", "path": "/x", "format": "json"}, resp
    finally:
        listener.stop()

def test_send_app_not_running():
    import wisprlite.mcp_shim as shim
    shim._port = lambda: 1  # nothing listening on port 1
    resp = shim._send("listen")
    assert resp["status"] == "app_not_running", resp

if __name__ == "__main__":
    test_send_forwards_to_bridge(); test_send_app_not_running()
    print("OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_mcp_send.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'wisprlite.mcp_shim'`

- [ ] **Step 3: Write the shim**

Create `wisprlite/mcp_shim.py`:

```python
"""`--mcp`: a stdio MCP server exposing pipevoice.listen + pipevoice.transcribe.

Spawned on demand by an MCP client (Claude Code etc.). It forwards each call to
the resident tray app over the loopback control bridge, so the heavy MCP
machinery lives only in this ephemeral process — the resident app stays light.
"""

from __future__ import annotations


def _port() -> int:
    from . import config
    return int(getattr(config.Config.load(), "mcp_port", 49518))


def _send(op: str, **kw) -> dict:
    from . import agent_bridge
    try:
        return agent_bridge.send_request(_port(), {"op": op, **kw})
    except (ConnectionRefusedError, OSError):
        return {"status": "app_not_running", "text": "",
                "error": "PipeVoice isn't running, or its Agent MCP toggle is off."}


def main() -> None:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("pipevoice")

    @mcp.tool()
    def listen(prompt: str = "", timeout_seconds: int = 45, mode: str = "") -> dict:
        """Ask the user to answer by voice and return what they said as text.

        Use when you need information only the user has. PipeVoice shows a prompt,
        the user speaks (push-to-talk by default), and the transcript is returned.
        `mode` may be 'push_to_talk' or 'hands_free' (default: the user's setting).
        """
        return _send("listen", prompt=prompt, timeout=timeout_seconds, mode=mode)

    @mcp.tool()
    def transcribe(path: str, format: str = "json", language: str = "", model_size: str = "") -> dict:
        """Transcribe a local audio or video file to timed text using local whisper.

        `format`: 'json' returns text + segment/word timestamps; 'srt'/'vtt' return
        a ready-made caption string in `captions`. `language` is an optional ISO
        code (blank = auto-detect). No API key needed; runs offline.
        """
        return _send("transcribe", path=path, format=format, language=language, model_size=model_size)

    mcp.run()  # stdio transport by default


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_mcp_send.py`
Expected: `OK`

- [ ] **Step 5: Wire the `--mcp` flag**

In `wisprlite/__main__.py`, add a branch before the final `else` (after line 9, the `--profiles` branch):

```python
elif "--mcp" in sys.argv:
    from .mcp_shim import main
```

- [ ] **Step 6: Add the dependency**

Append to `requirements.txt`:

```
mcp>=1.2  # MCP SDK — only imported by the `--mcp` stdio shim
```

- [ ] **Step 7: Verify the SDK shape (run where `mcp` is installed)**

Run: `python3 -c "from mcp.server.fastmcp import FastMCP; m=FastMCP('x'); print(hasattr(m,'tool') and hasattr(m,'run'))"`
Expected: `True`
If the import path differs in the installed `mcp` version, consult the `claude-api` skill / MCP docs and adjust `mcp_shim.main()` accordingly (do not hand-roll the protocol unless the exe-size ceiling in the spec forces it).

- [ ] **Step 8: Commit**

```bash
git add wisprlite/mcp_shim.py wisprlite/__main__.py requirements.txt tests/test_mcp_send.py
git commit -m "feat(mcp): stdio MCP shim exposing listen + transcribe"
```

---

## Task 9: App — `listen` push-to-talk path + `_polish` refactor + `_finish` routing

**Files:**
- Modify: `wisprlite/app.py`

- [ ] **Step 1: Extract `_polish()` (DRY — reused by normal dictation and agent listen)**

Add this method to `App` (e.g. after `_fallback`, line 248):

```python
    def _polish(self, text: str) -> str:
        """Optional LLM cleanup ('Flow mode'); returns the input unchanged if off/unavailable."""
        if not (text and self._eff("ai_cleanup")):
            return text
        from . import cleanup
        if not cleanup.provider_ready(self.cfg.cleanup_provider):
            return text
        self.overlay.set_state("transcribing", "Polishing…")
        polished = cleanup.clean(text, self.cfg.cleanup_provider, self.cfg.cleanup_model,
                                 self.cfg.language, self.cfg.speech_notes)
        return polished or text
```

- [ ] **Step 2: Use `_polish` in `_finish` (replace the inline cleanup block)**

In `_finish`, replace lines 182–190 (the `if text and self._eff("ai_cleanup"):` block through `text = polished`) with:

```python
            # AI cleanup ("Flow mode") — OpenAI / Gemini / OpenRouter / local Ollama.
            text = self._polish(text)
```

- [ ] **Step 3: Add the agent-listen routing branch in `_finish`**

In `_finish`, immediately after `text = (text or "").strip()` (line 163) and **before** the `if not text:` check (line 164), insert:

```python
            # Agent MCP listen: route the transcript to the caller instead of typing.
            if self._pending_agent_listen is not None:
                pending = self._pending_agent_listen
                self._pending_agent_listen = None
                if not pending["future"].cancelled():  # not already timed out
                    answer = apply_replacements(self._polish(text), self.cfg.replacements) if text else ""
                    pending["future"].set_result({"status": "ok", "text": answer})
                self.overlay.set_state("done", "↩ sent to agent" if text else "↩ (nothing heard)")
                self._set_icon("idle")
                return
```

(The existing `finally:` block at lines 227–231 still runs — it clears `_session`/`_active`/`_fg_ctx` and releases `_busy`.)

- [ ] **Step 4: Add `on_agent_listen` (push-to-talk)**

Add to `App` (after the `toggle_mcp` method from Task 6):

```python
    def on_agent_listen(self, prompt="", timeout=45, mode="") -> dict:
        import concurrent.futures
        mode = mode or self.cfg.mcp_default_mode
        if self._busy.locked():
            return {"status": "busy", "text": ""}
        if mode == "hands_free":
            return self._agent_listen_hands_free(prompt, timeout)
        # push-to-talk: arm, cue the overlay, wait for the user's normal hotkey cycle.
        fut = concurrent.futures.Future()
        self._pending_agent_listen = {"future": fut}
        self.overlay.show("listening", prompt or "🎙 your agent is listening — hold your hotkey & speak")
        try:
            return fut.result(timeout=max(1, int(timeout)))
        except concurrent.futures.TimeoutError:
            fut.cancel()
            self._pending_agent_listen = None
            self.overlay.hide()
            return {"status": "timeout", "text": ""}
```

- [ ] **Step 5: Parse check**

Run: `python3 -c "import ast; ast.parse(open('wisprlite/app.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 6: Manual verification (Windows)** — record results inline:

```
[ ] Start the app from source, enable Agent MCP in the tray (it shows the claude mcp add command).
[ ] claude mcp add pipevoice -- python -m wisprlite --mcp ; restart Claude Code.
[ ] In Claude Code: ask it to call pipevoice.listen with prompt "say a test word".
[ ] Overlay shows "your agent is listening — hold your hotkey & speak".
[ ] Hold the hotkey, say "banana", release. The tool returns {status:"ok", text:"Banana"} (cleaned).
[ ] The text is NOT typed into any window, and NOT added to History.
[ ] Don't press the hotkey for 45s -> tool returns {status:"timeout"}; overlay clears.
[ ] While mid-dictation (normal hotkey held), a listen() call returns {status:"busy"} immediately.
```

- [ ] **Step 7: Commit**

```bash
git add wisprlite/app.py
git commit -m "feat(mcp): listen push-to-talk path + _polish refactor + _finish routing"
```

---

## Task 10: App — `listen` hands-free path

**Files:**
- Modify: `wisprlite/app.py`

- [ ] **Step 1: Add `_agent_listen_hands_free`**

Add to `App` (after `on_agent_listen`):

```python
    def _agent_listen_hands_free(self, prompt="", timeout=45) -> dict:
        import time
        from .vad import SilenceEndpointer
        if not self._busy.acquire(blocking=False):
            return {"status": "busy", "text": ""}
        try:
            try:
                engine = self._get_engine()
                self._session = engine.start_session(on_partial=self.overlay.set_text)
            except Exception as exc:
                self._fail(str(exc))
                return {"status": "error", "text": "", "error": str(exc)}
            self.overlay.show("listening", prompt or "🎙 your agent is listening…")
            self._set_icon("recording")
            self.recorder.start(on_frame=self._session.feed if engine.streaming else None)
            endpointer = SilenceEndpointer(silence_ms=self.cfg.hands_free_silence_ms)
            deadline = time.time() + max(1, int(timeout))
            while time.time() < deadline:
                time.sleep(0.05)
                if endpointer.feed(self.recorder.level):
                    break
            audio = self.recorder.stop()
            self._set_icon("transcribing")
            if not endpointer._speech_started:
                self.overlay.hide(); self._set_icon("idle")
                return {"status": "timeout", "text": ""}
            try:
                text = self._session.finish(audio) if self._session else ""
            except Exception as exc:
                text = self._fallback(audio, exc)
            text = apply_replacements(self._polish((text or "").strip()), self.cfg.replacements)
            self.overlay.set_state("done", "↩ sent to agent")
            self._beep(990, 60); self._set_icon("idle")
            return {"status": "ok", "text": text}
        finally:
            self._session = None
            self._release()
```

- [ ] **Step 2: Parse check**

Run: `python3 -c "import ast; ast.parse(open('wisprlite/app.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Manual verification (Windows)**:

```
[ ] Set mcp_default_mode = "hands_free" in config.json (or pass mode in the tool call).
[ ] Call pipevoice.listen. Overlay shows "listening…"; mic opens WITHOUT a keypress.
[ ] Speak "the quick brown fox", then stop. After ~0.8s of silence it auto-stops and returns the text.
[ ] Call listen and say nothing -> after `timeout` returns {status:"timeout"}.
[ ] Tune hands_free_silence_ms if it cuts off too early/late.
```

- [ ] **Step 4: Commit**

```bash
git add wisprlite/app.py
git commit -m "feat(mcp): listen hands-free path (VAD auto-stop)"
```

---

## Task 11: Tray toggle + docs

**Files:**
- Modify: `wisprlite/tray.py`
- Modify: `README.md`, `wisprlitevercel/docs/index.html`

- [ ] **Step 1: Add the tray menu item**

In `wisprlite/tray.py`, inside the `menu = Menu(...)` block, after the "Start on login" item (line 97–98), add:

```python
            Item("Agent MCP (listen + transcribe)", lambda i, it: app.toggle_mcp(),
                 checked=lambda it: app.cfg.mcp_enabled),
```

- [ ] **Step 2: Manual verification (Windows)**:

```
[ ] Tray shows "Agent MCP (listen + transcribe)" with a check reflecting cfg.mcp_enabled.
[ ] Toggling on starts the bridge (log: "MCP control bridge on 127.0.0.1:49518") and notifies the add command.
[ ] Toggling off stops it (a subsequent shim call returns app_not_running).
```

- [ ] **Step 3: Document it**

Add a short "Talk to your AI agent (MCP)" section to `README.md` after the engines section, covering: enable the tray toggle, run the shown `claude mcp add` command, and the two tools (`listen`, `transcribe` with `format=json|srt|vtt`). Mirror a brief note in `wisprlitevercel/docs/index.html`.

Example README block:

```markdown
## Talk to your AI agent (MCP)

PipeVoice can act as a local MCP server so agents (Claude Code, Cursor) can use your
voice — no API key, runs on your machine:

- **`listen`** — the agent asks, you answer by voice, it gets the text back.
- **`transcribe`** — hand it an audio/video file, get text + word/segment timestamps
  (or `format: "srt"`/`"vtt"` for ready-made captions).

Enable **Agent MCP** in the tray menu, then register it once (the app shows the exact
command):

    claude mcp add pipevoice -- python -m wisprlite --mcp     # from source
    claude mcp add pipevoice -- "C:\…\Pipevoice.exe" --mcp    # installed build
```

- [ ] **Step 4: Commit**

```bash
git add wisprlite/tray.py README.md wisprlitevercel/docs/index.html
git commit -m "feat(mcp): tray toggle + docs for the agent MCP"
```

---

## Task 12: End-to-end verification on Windows + PyInstaller

**Files:** none (verification + any fixes surfaced).

- [ ] **Step 1: Run all pure-unit tests** (Linux or Windows):

Run: `for f in tests/test_captions.py tests/test_vad.py tests/test_agent_bridge.py tests/test_transcribe_shaper.py tests/test_bridge_transcribe.py tests/test_mcp_send.py; do python3 $f || echo "FAIL $f"; done`
Expected: six `OK` lines, no `FAIL`.

- [ ] **Step 2: `transcribe` end-to-end (Windows, real model):**

```
[ ] Enable Agent MCP. In Claude Code call pipevoice.transcribe on a short .wav -> JSON with text + segments[].words[].start/end.
[ ] Call with format:"srt" -> a valid SRT string in `captions`.
[ ] Call on an .mp4 video -> audio decodes (PyAV) and returns timed text. If it errors, install/confirm ffmpeg and retry; capture the exact error.
[ ] Call on a missing path -> {status:"error", error:"file not found: …"}.
[ ] First call downloads the model (~150 MB) once; second call is warm/fast.
```

- [ ] **Step 3: PyInstaller build check (Windows):**

```
[ ] build_exe.bat succeeds; note the exe size delta vs the previous build (expect a few MB from the mcp SDK).
[ ] Pipevoice.exe --mcp starts a stdio server (claude mcp add with the exe path; tools list shows listen + transcribe).
[ ] If `mcp` isn't bundled, add it to the PyInstaller hiddenimports/spec and rebuild.
```

- [ ] **Step 4: Bump version + finish the branch**

```
[ ] Bump wisprlite/__init__.py __version__ (e.g. 2.26.0).
[ ] git commit -am "chore: bump to 2.26.0 (agent MCP)"
```

Then use **superpowers:finishing-a-development-branch** to open the PR.

---

## Self-review notes (author)

- **Spec coverage:** `listen` PTT (T9) + hands-free (T10); `transcribe` json/srt/vtt (T4/T6); Approach-B bridge (T3) + stdio shim (T8); config (T5); tray enable (T6/T11); `app_not_running`/`busy`/`timeout`/`error` statuses (T8/T9/T6); video decode + ffmpeg fallback (T12 verification); known ceilings (loopback no-auth, exe size) documented in spec. ✔
- **No-auth token / loopback** is intentional per spec — not a gap.
- **`clean` param** from the spec's `listen` table is intentionally dropped from the v1 tool schema (cleanup follows the user's Flow-mode setting); noted here so it's a conscious cut, not an omission.
- **Type consistency:** response dicts use `status`/`text`/`segments`/`captions`/`error` consistently across `mcp_shim`, `agent_bridge`, and the `app` handlers; `_segments_to_dicts` shape matches what `captions.to_srt/to_vtt` consume (`start`/`end`/`text`).
- **Ordering:** `_agent_dispatch` (T6) references `on_agent_listen` (T9); safe because no `listen` call occurs until the full feature lands, and T6/T7 exercise only `transcribe`.
```
