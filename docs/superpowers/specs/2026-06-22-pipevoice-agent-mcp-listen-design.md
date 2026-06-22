# PipeVoice Agent MCP — `listen` tool (design)

_Date: 2026-06-22 · App version at design time: 2.25.0 · Status: approved design, pre-plan_

## Goal

Let an AI agent (Claude Code, Cursor, Cline) ask PipeVoice for a **spoken answer
on demand**: the agent calls a `listen` tool, PipeVoice captures the user's voice
through its existing pipeline, and returns the transcript to the agent. This is
the on-brand inverse of Voicebox's agent-voice *output* — PipeVoice is the voice
*input* tool, so it exposes voice input as a service.

Hands-free coding flows: the agent asks a question, the user answers by voice,
the answer comes back as text — no keyboard.

## Non-goals (explicit)

- No `transcribe`-a-file tool (decided: listen-only for v1).
- No TTS / agent-voice *output* (that's Voicebox's game; off-brand for us).
- No cloud relay — loopback only.
- The two local-Whisper wins (Turbo model option + GPU/device toggle) ship as a
  **separate small PR**, not part of this feature.

## Decisions locked during brainstorming

1. **Use case:** Listen on demand (live mic), not file transcription.
2. **Interaction:** Push-to-talk is the default; hands-free (auto-stop on silence)
   is a configurable mode.
3. **Architecture:** **Approach B** — a lightweight stdio MCP server spawned by the
   client on demand, plus a tiny stdlib loopback bridge in the resident tray app.
   Chosen over an in-app HTTP MCP server to keep the **resident footprint near-zero**
   (no web framework loaded at rest — "light tray app" is our positioning) and to
   maximize client support (stdio is the most broadly supported MCP transport).

## Architecture (Approach B)

```
Claude Code ──spawns──▶ `Pipevoice.exe --mcp`  (ephemeral stdio MCP server, the "shim")
                              │  tool: pipevoice.listen
                              │  loopback TCP (JSON line protocol)
                              ▼
                    resident PipeVoice tray app
                    ├─ control listener thread (stdlib socket, 127.0.0.1:<mcp_port>)
                    ├─ existing recorder / overlay / engine / cleanup  ◀── reused
                    └─ _busy lock                                       ◀── reused
```

Two processes:

- **The shim** (`Pipevoice.exe --mcp`, or `python -m wisprlite --mcp` from source):
  a stdio MCP server (official `mcp` Python SDK, stdio transport — no
  uvicorn/starlette). Registers one tool, `listen`. On a call it opens a loopback
  TCP connection to the resident app, forwards the request, waits, returns the
  response. If the app isn't running (connection refused) it returns a clear
  error so the agent isn't left hanging.
- **The resident app** gains one new always-on piece: a **control listener thread**
  bound to `127.0.0.1:<mcp_port>` using only the stdlib `socket` module. It accepts
  a connection, reads one JSON request line, invokes an app callback, and writes one
  JSON response line. No web framework. Started/stopped by a tray toggle.

### Why the shim runs as the exe

For a frozen install there is no Python/venv for the client to run `python -m
wisprlite`. The client is therefore configured to spawn the installed exe with a
`--mcp` flag, which runs the shim. From source, `python -m wisprlite --mcp` is the
equivalent. Registration in Claude Code (shown to the user once when they enable
the feature):

```
claude mcp add pipevoice -- "<path>\Pipevoice.exe" --mcp     # frozen install
claude mcp add pipevoice -- python -m wisprlite --mcp        # from source
```

## The tool: `pipevoice.listen`

| Param | Type | Default | Meaning |
|---|---|---|---|
| `prompt` | string? | — | Optional context shown in the overlay so the user knows what to answer ("your agent asks: …"). |
| `timeout_seconds` | int? | 45 | Hard cap on waiting for the user. |
| `mode` | enum? | config default (`push_to_talk`) | `push_to_talk` or `hands_free`. |
| `clean` | bool? | = user's Flow-mode setting | Apply LLM cleanup to the returned text. |

Returns:

```json
{ "status": "ok" | "timeout" | "busy" | "cancelled" | "app_not_running", "text": "…" }
```

- `ok` — transcript captured (in `text`).
- `timeout` — user did not speak within `timeout_seconds`.
- `busy` — the user is mid-dictation (the `_busy` lock is held); returned immediately, no queueing.
- `cancelled` — user dismissed the prompt (Esc / cancel).
- `app_not_running` — shim could not reach the resident app.

## Data flow

1. Agent calls `listen` → shim forwards `{op:"listen", prompt, timeout, mode, clean}`
   over loopback to the resident app's control listener.
2. Control listener invokes `App.on_agent_listen(...)`, which:
   - If `_busy` is held → return `{status:"busy"}` immediately.
   - Else create a `concurrent.futures.Future`, set a `_pending_agent_listen`
     routing flag, and arm the capture for the requested mode.
3. Capture (reuses the existing path; see `app.py` references below):
   - **push_to_talk:** overlay shows `🎙 your agent is listening` + `prompt`; the
     next hotkey hold→release records and transcribes exactly as a normal dictation.
     If no hotkey press within `timeout_seconds` → resolve `{status:"timeout"}`,
     clear the armed state and overlay.
   - **hands_free:** start the recorder immediately; run VAD endpointing (below);
     stop on trailing silence or at `timeout_seconds`; the hotkey acts as a manual
     stop/cancel.
4. Transcription + optional cleanup reuse the existing engine `finish()` and
   `cleanup.py`. Because `_pending_agent_listen` is set, the result is **routed to
   the Future and returned — not typed, and not written to history** (v1; history
   opt-in could come later).
5. Control listener writes the JSON response → shim → agent.

## New / changed code (everything else is reused)

- **NEW `wisprlite/agent_bridge.py`** — the control listener thread + JSON line
  protocol (encode/decode request/response). Stdlib `socket` + `json` only.
  Lazy-imported; if it fails to bind, the feature logs and stays off (follows the
  app's existing fault-tolerant-import pattern).
- **NEW shim entry** — `wisprlite/__main__.py` (or a small `mcp_shim.py`) handles
  the `--mcp` flag: builds an `mcp` stdio server exposing `listen`, which round-trips
  to the resident app over loopback. `mcp` SDK imported **only** in this path.
- **CHANGED `app.py`** — add `on_agent_listen(...)` and a `_pending_agent_listen`
  routing flag honored in `_finish()` (route text to the Future instead of
  typing/history). Start/stop the control listener from the tray toggle. Reuses
  `_on_start` (`app.py:113`), `_on_stop` (`app.py:140`), `_finish` (`app.py:149`),
  `_get_engine` (`app.py:91`), and the `_busy` lock.
- **NEW `wisprlite/vad.py`** (hands-free only) — trailing-silence endpointer over
  the audio frames. Reuses the per-frame RMS level the overlay VU meter already
  computes (`audio.py` / overlay); no new DSP. Pure decision logic: "speech started,
  then level < threshold for `hands_free_silence_ms` → stop."
- **CHANGED `config.py`** — add `mcp_enabled: bool=False`, `mcp_port: int=49518`,
  `mcp_default_mode: str="push_to_talk"`, `hands_free_silence_ms: int=800`. Add the
  engine/`_watch_config` reload list where relevant.
- **CHANGED `settings.py`** — tray toggle "Agent mic (MCP)" (on/off + show the
  `claude mcp add` command); settings fields for port, default mode, silence threshold.

Audio format is unchanged: 16 kHz mono, float32 / 16-bit PCM (`audio.py:16`).
Port `49518` is distinct from the single-instance lock on `49517` (`app.py:475`).

## Concurrency & safety

- One in-flight `listen` at a time, gated by the existing `_busy` lock; concurrent
  calls get `{status:"busy"}` (no queue).
- Control listener binds `127.0.0.1` only.
- The Future bridges the listener thread (waits) and the app/Tk thread (captures);
  the listener uses a bounded `Future.result(timeout=timeout_seconds + margin)` so a
  wedged capture can't hang the socket forever.

## Known ceilings (deliberate, documented)

- **No auth token in v1** — any local process can connect to the loopback control
  port and call `listen` (same posture as Voicebox's loopback MCP). Upgrade path: a
  shared token in `config.json` that the shim must present. *(// ponytail: loopback +
  opt-in toggle is the v1 trust boundary; add a token if a real threat appears.)*
- **No request queueing** — busy = rejected, not queued.
- **stdio only** — an in-app HTTP MCP transport (Approach A) can be added later for
  URL-based clients; not built now.
- **Exe size** — bundling the stdio `mcp` SDK (mcp + pydantic + anyio; *not*
  uvicorn/starlette) grows the installer by a few MB. The **resident runtime**
  footprint is unchanged (the SDK loads only in the `--mcp` shim process). If the
  exe bump ever matters, the fallback is hand-rolling the single-tool MCP stdio
  JSON-RPC (~150 lines, no SDK) — documented alternative, not the default.

## Testing (one runnable check per non-trivial unit)

- **`vad.py`** — feed synthetic frame levels (speech → silence) and assert the
  endpointer fires after `hands_free_silence_ms`, and does *not* fire on a leading
  pause before speech. Assert-based `demo()`/`test_vad.py`.
- **`agent_bridge.py`** — round-trip the JSON line protocol over a real loopback
  socket: send a `listen` request to a stub callback, assert the response shape and
  the `busy`/`timeout` status paths. One small `test_agent_bridge.py`.
- PTT/hands-free wiring in `app.py` is verified manually on Windows (no test
  harness exists in the repo; consistent with the project's no-test-suite norm).

## Implementation note for the plan

When wiring the `mcp` SDK in the shim, consult the MCP tool-definition reference
(and the `claude-api` skill if any Anthropic specifics arise) so the tool schema
and stdio handshake are correct — do not hand-write the protocol unless we hit the
exe-size ceiling above.
