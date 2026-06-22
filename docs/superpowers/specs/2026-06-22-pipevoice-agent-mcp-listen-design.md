# PipeVoice Agent MCP — `listen` + `transcribe` (design)

_Date: 2026-06-22 · App version at design time: 2.25.0 · Status: approved design, pre-plan_

## Goal

Give AI agents (Claude Code, Cursor, Cline) two voice capabilities from PipeVoice,
locally and without an API key:

1. **`listen`** — ask the user for a **spoken answer on demand**. The agent calls
   the tool, PipeVoice captures the user's voice through its existing pipeline, and
   returns the transcript. The on-brand inverse of Voicebox's agent-voice *output*.
2. **`transcribe`** — turn an **existing audio or video file into timed text** using
   local whisper. Returns plain text plus **word/segment-level timestamps**, with an
   optional `format` param for ready-made SRT/VTT captions. This makes PipeVoice the
   **local, free, offline transcription service any agent on the machine can call** —
   the exact gap behind "no transcriber or real API key on this box" (e.g. an AI
   video-editing flow that needs caption timing / cut points).

Positioning: Voicebox gives agents *a voice to speak*; PipeVoice gives agents
*ears and a timed transcript*.

## Non-goals (explicit)

- No TTS / agent-voice *output* (that's Voicebox's game; off-brand for us).
- No cloud relay — loopback only. `transcribe` uses **local** whisper specifically
  (it's the only engine that yields word timestamps with no key), regardless of the
  user's current dictation engine.
- The two local-Whisper *dictation* wins (Turbo model option + GPU/device toggle)
  ship as a **separate small PR**, not part of this feature. (The GPU/device toggle
  does, however, benefit `transcribe` once it lands.)

## Decisions locked during brainstorming

1. **Capabilities:** Two MCP tools — `listen` (live mic) **and** `transcribe`
   (file → timed text). (Originally listen-only; `transcribe` added after the
   video-captioning use case surfaced.)
2. **`listen` interaction:** Push-to-talk is the default; hands-free (auto-stop on
   silence) is a configurable mode.
3. **`transcribe` output:** structured JSON (text + segment/word timestamps) **plus**
   an optional `format` param (`json` | `srt` | `vtt`) so callers can get drop-in
   caption files from the same tool.
4. **Architecture:** **Approach B** — a lightweight stdio MCP server spawned by the
   client on demand, plus a tiny stdlib loopback bridge in the resident tray app.
   Chosen over an in-app HTTP MCP server to keep the **resident footprint near-zero**
   (no web framework at rest — "light tray app" is our positioning) and to maximize
   client support (stdio is the most broadly supported MCP transport). Both tools are
   served by the resident app (it owns the mic for `listen` and keeps the whisper
   model warm for `transcribe`).

## Architecture (Approach B)

```
Claude Code ──spawns──▶ `Pipevoice.exe --mcp`  (ephemeral stdio MCP server, the "shim")
                              │  tools: pipevoice.listen, pipevoice.transcribe
                              │  loopback TCP (JSON line protocol: op=listen|transcribe)
                              ▼
                    resident PipeVoice tray app
                    ├─ control listener thread (stdlib socket, 127.0.0.1:<mcp_port>)
                    ├─ existing recorder / overlay / dictation engine / cleanup  ◀── reused (listen)
                    ├─ dedicated local-whisper model (warm, word_timestamps)     ◀── transcribe
                    └─ _busy lock                                                 ◀── reused
```

- **The shim** (`Pipevoice.exe --mcp`, or `python -m wisprlite --mcp` from source):
  a stdio MCP server (official `mcp` Python SDK, stdio transport — no
  uvicorn/starlette). Registers `listen` and `transcribe`. Each call opens a loopback
  TCP connection to the resident app, forwards a JSON request, waits, returns the
  response. If the app isn't running (connection refused) it returns a clear error.
- **The resident app** gains a **control listener thread** bound to
  `127.0.0.1:<mcp_port>` using only the stdlib `socket` module — accepts a connection,
  reads one JSON request line, dispatches by `op`, writes one JSON response line.
  No web framework. Started/stopped by a tray toggle.

### Why the shim runs as the exe

For a frozen install there is no Python/venv for the client to run `python -m
wisprlite`. The client spawns the installed exe with `--mcp`. Registration shown to
the user once when they enable the feature:

```
claude mcp add pipevoice -- "<path>\Pipevoice.exe" --mcp     # frozen install
claude mcp add pipevoice -- python -m wisprlite --mcp        # from source
```

## Tool: `pipevoice.listen`

| Param | Type | Default | Meaning |
|---|---|---|---|
| `prompt` | string? | — | Optional context shown in the overlay ("your agent asks: …"). |
| `timeout_seconds` | int? | 45 | Hard cap on waiting for the user. |
| `mode` | enum? | config default (`push_to_talk`) | `push_to_talk` or `hands_free`. |
| `clean` | bool? | = user's Flow-mode setting | Apply LLM cleanup to the returned text. |

Returns: `{ "status": "ok"|"timeout"|"busy"|"cancelled"|"app_not_running", "text": "…" }`

- `ok` — transcript in `text`. `timeout` — user didn't speak in time. `busy` —
  user mid-dictation (the `_busy` lock is held), returned immediately, no queueing.
  `cancelled` — user dismissed (Esc). `app_not_running` — shim couldn't reach the app.

**Flow:** shim → bridge `{op:"listen",…}` → `App.on_agent_listen(...)`: if `_busy`,
return busy; else create a `Future`, set `_pending_agent_listen`, arm capture. PTT:
overlay `🎙 your agent is listening` + `prompt`; next hotkey hold→release records &
transcribes exactly like a normal dictation; no press within `timeout_seconds` →
`timeout`. Hands-free: start recorder immediately, stop on trailing silence (VAD) or
at `timeout_seconds`; hotkey = manual stop/cancel. Transcription + optional cleanup
reuse the existing engine `finish()` and `cleanup.py`; because `_pending_agent_listen`
is set, the result is **returned to the Future — not typed, not written to history**
(v1). Then bridge writes the response.

## Tool: `pipevoice.transcribe`

| Param | Type | Default | Meaning |
|---|---|---|---|
| `path` | string | — (required) | Absolute path to a local audio **or video** file. |
| `format` | enum? | `json` | `json` (timestamps), `srt`, or `vtt`. |
| `language` | string? | auto | ISO code to force the language; blank = auto-detect. |
| `model_size` | string? | config `transcribe_model_size` | Override whisper model size for this call. |

Returns (always includes `text`; the timing payload depends on `format`):

```jsonc
// format = "json"
{
  "status": "ok" | "error" | "app_not_running",
  "text": "full transcript",
  "language": "en",
  "duration": 73.4,
  "segments": [
    { "start": 0.0, "end": 3.2, "text": "…",
      "words": [ { "start": 0.0, "end": 0.4, "word": "Hello" }, … ] }
  ],
  "error": "…"            // only when status=error (e.g. file not found / decode failed)
}
// format = "srt" | "vtt"
{ "status": "ok", "text": "…", "language": "en", "duration": 73.4, "captions": "<SRT or VTT string>" }
```

**Flow:** shim → bridge `{op:"transcribe", path, format, language, model_size}` →
`App.on_agent_transcribe(...)` runs on a worker thread. It uses a **dedicated local
faster-whisper model** (lazy-created and kept warm), independent of the user's
dictation engine, calling `model.transcribe(path, word_timestamps=True, language=…)`.
Segments+words are collected into the JSON shape; if `format` is `srt`/`vtt`, the
captions string is produced by `captions.py`. Errors (missing file, decode failure)
return `{status:"error", error:…}`.

**Video input:** faster-whisper decodes audio from many container formats via its
bundled PyAV/ffmpeg. If decoding a video path fails, fall back to extracting audio
with a bundled/located `ffmpeg` to a temp WAV, then transcribe that. (See ceilings.)

**Concurrency:** `transcribe` does not touch the mic, so it does **not** take the
`_busy` lock; it runs on its own worker. Only one `transcribe` at a time (a dedicated
`threading.Lock` around the shared transcribe model) to avoid double-loading / GPU
contention; a second concurrent call waits or returns busy (plan picks one — default:
serialize behind the lock with the request's own timeout).

## New / changed code (everything else is reused)

- **NEW `wisprlite/agent_bridge.py`** — control listener thread + JSON line protocol
  (encode/decode, dispatch by `op`). Stdlib `socket` + `json` only. Lazy-imported;
  if it can't bind, log and stay off (matches the app's fault-tolerant-import pattern).
- **NEW `wisprlite/captions.py`** — pure `to_srt(segments)` / `to_vtt(segments)` and a
  `format_timestamp(seconds, vtt: bool)` helper. No deps.
- **NEW `wisprlite/vad.py`** — trailing-silence endpointer for `listen` hands-free
  mode. Pure decision logic over the per-frame RMS level the recorder already exposes
  (`Recorder.level`, `audio.py:24`). `SilenceEndpointer(threshold, silence_ms,
  block_ms).feed(level) -> bool`.
- **NEW shim** — `wisprlite/mcp_shim.py` + a `--mcp` branch in `wisprlite/__main__.py`.
  Builds an `mcp` stdio server exposing `listen` + `transcribe`, each forwarding to the
  resident app over loopback via a small `_send(op, **kw)` helper. `mcp` SDK imported
  **only** in this path.
- **NEW transcribe model accessor** — a `transcribe_file(path, *, language, model_size,
  want_words=True)` function returning `(text, language, duration, segments)`. Lives
  next to the local engine (e.g. `engines/local_engine.py` adds a module-level
  `transcribe_file(...)` that owns a cached `WhisperModel` with `word_timestamps`),
  separate from the dictation `Session` so it can run while the dictation engine is
  something else.
- **CHANGED `app.py`** — add `on_agent_listen(...)` (+ `_pending_agent_listen` routing
  honored in `_finish()`), `on_agent_transcribe(...)`, and start/stop the control
  listener from the tray toggle. Reuses `_on_start` (`app.py:113`), `_on_stop`
  (`app.py:140`), `_finish` (`app.py:149`), `_get_engine` (`app.py:91`), the `_busy`
  lock, the `Recorder` (`audio.py`), and the overlay.
- **CHANGED `config.py`** — add `mcp_enabled: bool=False`, `mcp_port: int=49518`,
  `mcp_default_mode: str="push_to_talk"`, `hands_free_silence_ms: int=800`,
  `transcribe_model_size: str=""` (blank = reuse `local_model_size`).
- **CHANGED `settings.py`** — tray toggle "Agent MCP (listen + transcribe)" (on/off +
  show the `claude mcp add` command); settings fields for port, default listen mode,
  hands-free silence threshold, transcribe model size.

Audio format unchanged: 16 kHz mono float32 / 16-bit PCM (`audio.py:16`). Control port
`49518` is distinct from the single-instance lock on `49517` (`app.py:475`).

## Known ceilings (deliberate, documented)

- **No auth token in v1** — any local process can hit the loopback control port and
  call `listen`/`transcribe` (same posture as Voicebox's loopback MCP). Upgrade path:
  a shared token in `config.json` the shim must present. *(// ponytail: loopback +
  opt-in toggle is the v1 trust boundary; add a token if a real threat appears.)*
- **`transcribe` requires the resident app running** (warm model, light shim). If the
  tray app is off, `transcribe` returns `app_not_running`. (Acceptable: the feature is
  an opt-in toggle in the running app.)
- **Video decode depends on PyAV/ffmpeg** — faster-whisper's bundled PyAV usually
  handles video audio; the ffmpeg fallback needs an `ffmpeg` binary available. If
  neither can decode, return `{status:"error"}` with a clear message.
- **No request queueing for `listen`** — busy = rejected. `transcribe` serializes
  behind a model lock.
- **stdio only** — an in-app HTTP MCP transport (Approach A) can be added later; not now.
- **Exe size** — bundling the stdio `mcp` SDK (mcp + pydantic + anyio; *not*
  uvicorn/starlette) grows the installer a few MB. Resident runtime footprint is
  unchanged (SDK loads only in the `--mcp` shim). Fallback if it ever bites: hand-roll
  the small MCP stdio JSON-RPC (~150 lines, no SDK).

## Testing (one runnable check per non-trivial unit; assert-based, no framework — the
repo has no pytest config, so tests run via `python <file>` with `assert`)

- **`captions.py`** — given fixed segments, assert `to_srt` / `to_vtt` produce exact
  expected strings (index numbering, `,`/`.` ms separators, `WEBVTT` header, 00:00:00
  formatting). Pure, fully testable on Linux.
- **`vad.py`** — feed synthetic level sequences: leading silence does NOT trigger;
  speech-then-silence triggers after `silence_ms`; sustained speech never triggers.
- **`agent_bridge.py`** — start the listener on an ephemeral port with a stub
  dispatcher, connect a client, round-trip a `listen` and a `transcribe` request;
  assert response shapes and malformed-input handling.
- **`mcp_shim.py`** — unit-test the `_send(op, **kw)` forwarding against the Task-2
  listener with a stub dispatcher (no MCP SDK needed for this part).
- **App wiring (`on_agent_listen`/`on_agent_transcribe`, PTT/hands-free, model load)**
  and the end-to-end `claude mcp add` handshake are **verified manually on Windows**
  (no test harness for the GUI/mic/Tk layer; consistent with the repo's no-test norm).
  Each such task carries an explicit manual-verification checklist.

## Implementation note for the plan

When wiring the `mcp` SDK in the shim, consult the MCP tool-definition reference (and
the `claude-api` skill if any Anthropic specifics arise) so the tool schemas and stdio
handshake are correct — do not hand-write the protocol unless we hit the exe-size
ceiling above.
