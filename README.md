# Pipevoice

A Wispr-Flow-style voice typing tool for Windows. Hold a hotkey, talk, release —
your speech is transcribed and typed into whatever window is focused (terminal,
editor, browser). Built for dictating to Claude in a terminal.

- **Three engines, switchable from the tray:**
  - **OpenAI Whisper** (cloud) — most accurate, near-zero setup. *Default.*
  - **Deepgram** (streaming) — lowest latency; words appear live as you talk.
  - **Local Whisper** (offline) — fully private, free per-use, no internet.
- **Live overlay HUD** — a sleek pill near the bottom of the screen with a
  pulsing status dot, a real-time mic VU meter, and the live transcript.
- **System tray icon** — switch engine / mode / output, pause, autostart, quit.
- **Settings window** — edit the hotkey (with a "Capture" button), engine,
  models, mic, language and toggles in a GUI; no JSON editing. Changes apply
  live to the running app.
- **Auto-start on login** — one click in the tray menu or the installer.
- **Push-to-talk or toggle**, **type or paste** output — all switchable.
- **Automatic offline fallback** — if a cloud engine fails (no internet), it
  retries the utterance with local Whisper.

## Quick start (Windows)

1. Install [Python 3.10+](https://www.python.org/downloads/) — tick
   **"Add Python to PATH"** during install.
2. Put this folder somewhere, e.g. `C:\Tools\wisprlite`.
3. Copy `.env.example` to `.env` and add your `OPENAI_API_KEY`.
4. Double-click **`run.bat`**. First run builds a venv and installs everything,
   then starts listening. A microphone icon appears in your system tray.
5. Hold **Right Ctrl**, speak, release. Text appears at your cursor.

Right-click the tray icon to change anything — no config files to edit.

## Engines

| Engine | Latency | Cost | Internet | Notes |
|---|---|---|---|---|
| OpenAI Whisper | ~1–2s after release | ~$0.006/min | Required | Best accuracy, default. Needs `OPENAI_API_KEY`. |
| Deepgram | Live (streaming) | ~$0.0043/min | Required | Words show live in the overlay. Needs `DEEPGRAM_API_KEY`. |
| Local Whisper | ~1–4s (CPU) | Free | None | Private. First use downloads a ~150 MB model. Model size via `local_model_size`. |

Switch engines anytime in **Tray → Engine**. Your choice persists.

### Picking a local model size
`base.en` (default) is fast and good for English. For more accuracy edit
`local_model_size` in `%APPDATA%\Pipevoice\config.json` to `small.en`,
`medium.en`, or multilingual `small` / `medium` / `large-v3`. Bigger = slower
but more accurate; a GPU helps a lot (it auto-detects CUDA).

## Talk to your AI agent (MCP)

PipeVoice can act as a local MCP server so agents (Claude Code, Cursor, Cline) can use
your voice — no API key, everything runs on your machine:

- **`listen`** — the agent asks a question, you answer by voice (push-to-talk by
  default, or hands-free), and it gets the text back.
- **`transcribe`** — hand it a local audio or video file and get the transcript with
  word/segment timestamps, or ready-made captions (`format: "srt"` / `"vtt"`).

Enable **Agent MCP (listen + transcribe)** in the tray menu, then register it once with
your client (the app shows the exact command when you toggle it on):

    claude mcp add pipevoice -- python -m wisprlite --mcp        # running from source
    claude mcp add pipevoice -- "C:\Path\To\Pipevoice.exe" --mcp # installed build

The server is loopback-only and off by default.

## The overlay HUD

The pill shows what's happening:

- 🟢 **Listening** — pulsing green dot + a live VU meter reacting to your voice.
  With Deepgram you also see the transcript forming in real time.
- 🟡 **Transcribing** — animated, while the final text is produced.
- 🔵 **Done** — flashes the text it just typed (so you get confirmation).
- 🔴 **Error** — shows what went wrong.

Toggle it via **Tray → Show overlay**.

## Settings window

Right-click the tray icon → **Settings…** for a GUI covering everything:
engine, mode, output, push-to-talk key (with a **Capture** button — click it and
press your desired key/combo), microphone picker, language, the three model
names, and the overlay/sounds/autostart toggles. Hit **Save** and the running
app picks up the changes within a second (it watches `config.json`) — no restart.

The settings window runs as its own small process, so it never clashes with the
overlay's UI thread.

## Settings (quick toggles in the tray menu)

| Menu | Options |
|---|---|
| Engine | OpenAI Whisper / Deepgram / Local Whisper |
| Mode | Push-to-talk (hold) / Toggle (tap on, tap off) |
| Output | Type (keystrokes) / Paste (clipboard + Ctrl+V) |
| Show overlay | on / off |
| Sounds | on / off (the start/stop beeps) |
| Start on login | adds/removes an HKCU autostart entry |
| Paused | temporarily ignore the hotkey |
| Quit | exit |

Settings persist to `%APPDATA%\Pipevoice\config.json`. API keys live only in
`.env` and are never written there.

## Packaging: .exe and a real installer

Want it to feel like a real app? Two options, both after `run.bat` has created
`.venv`:

1. **Single .exe** — run **`build_exe.bat`** → `dist\Pipevoice.exe` (PyInstaller,
   no console window, custom icon). It bundles all three engines including the
   local Whisper runtime (`faster-whisper` + `ctranslate2`). Double-click to run.
   The icon is generated by `assets/make_icon.py` if you want to tweak it.
2. **Full installer** — install [Inno Setup 6](https://jrsoftware.org/isdl.php),
   then run **`build_installer.bat`**. It builds the exe and compiles
   `installer\Output\Pipevoice-Setup.exe`: a per-user install (no admin /UAC),
   Start Menu shortcuts, an optional "start at login" checkbox, and it pops open
   `.env` after install so you can paste your API key. Uninstalls cleanly,
   including `%APPDATA%\Pipevoice`.

Only one copy runs at a time (a single-instance lock), so the installer's
startup shortcut and the tray autostart toggle can't double-launch it.

## Tips & gotchas

- **Dedicated PTT key.** `Right Ctrl` is the default because you almost never
  use it otherwise. Avoid keys you actually type with.
- **Elevated terminals.** Windows blocks keystroke injection from a normal
  process into an *administrator* window. If your terminal runs as admin, run
  Pipevoice as admin too.
- **No Enter is sent.** Text lands at your cursor so you can review/edit before
  submitting — ideal for composing Claude prompts.
- **Wrong mic?** `python -m sounddevice` lists devices; set `device` in the
  config (index or name substring).
- **Latency** with OpenAI/local is the transcription time after you release.
  Want instant feedback? Use the **Deepgram** engine.

## Architecture (so you can hack on it)

```
wisprlite/
  app.py        orchestrator + state machine (idle -> recording -> transcribing)
  config.py     persisted settings (%APPDATA%) + secrets from .env
  audio.py      mic capture: float32 buffer + int16 stream feed + VU level
  hotkey.py     PTT/toggle detection (poll loop, supports combos, runtime swap)
  typer.py      keystroke / clipboard output
  overlay.py    tkinter HUD pill (own thread, queue-driven, ~30fps)
  tray.py       pystray icon + menu (dynamic state-colored icon)
  settings.py   standalone Tk settings window (separate process)
  autostart.py  HKCU Run key management (source + frozen exe)
  engines/
    base.py            unified Session interface
    openai_engine.py   batch Whisper API
    deepgram_engine.py streaming websocket
    local_engine.py    faster-whisper, offline
```

Every engine implements the same `start_session(on_partial) -> Session` with
`feed(pcm)` / `finish(audio) -> text`, so the app drives all three identically.
Heavy/optional dependencies are imported lazily — a missing one disables just
that feature instead of crashing the app.
