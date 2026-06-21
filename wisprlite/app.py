"""Pipevoice application: wires hotkey -> record -> transcribe -> type, plus the
tray icon and the live overlay. State machine: idle -> recording -> transcribing.
"""

from __future__ import annotations

import logging
import sys
import threading
import time

from . import autostart, config
from .audio import Recorder
from .hotkey import HotkeyManager
from .overlay import Overlay
from .tray import Tray
from .typer import apply_replacements, copy_clipboard, type_text

log = logging.getLogger("wisprlite")

try:
    import winsound  # Windows audio cues
except Exception:
    winsound = None


class App:
    def __init__(self) -> None:
        self.cfg = config.Config.load()
        self.paused = False

        self.recorder = Recorder(device=config.device_arg(self.cfg))
        self.overlay = Overlay(level_provider=lambda: self.recorder.level, enabled=self.cfg.overlay)
        self.tray = Tray(self)
        self.hotkeys = HotkeyManager(
            get_hotkey=lambda: self.cfg.hotkey,
            get_mode=lambda: self.cfg.mode,
            on_start=lambda: self._on_start(clipboard=False),
            on_stop=self._on_stop,
            is_paused=lambda: self.paused,
        )
        # second hotkey: same record flow, but the result goes to the clipboard
        self.clip_hotkeys = HotkeyManager(
            get_hotkey=lambda: self.cfg.clipboard_hotkey,
            get_mode=lambda: self.cfg.mode,
            on_start=lambda: self._on_start(clipboard=True),
            on_stop=self._on_stop,
            is_paused=lambda: self.paused,
        )

        self._engine = None
        self._session = None
        self._clipboard_only = False
        self._started_at = 0.0
        self._busy = threading.Lock()
        self._stop = threading.Event()

    # ---- engine -----------------------------------------------------------
    def _build_engine(self, name: str | None = None):
        name = name or self.cfg.engine
        vocab = (self.cfg.vocabulary or "").strip()
        if name == "openai":
            from .engines.openai_engine import OpenAIEngine

            if not config.openai_key():
                raise RuntimeError("OPENAI_API_KEY is not set")
            return OpenAIEngine(model=self.cfg.openai_model,
                                language=(self.cfg.language or "").split("-")[0] or None, prompt=vocab)
        if name == "deepgram":
            from .engines.deepgram_engine import DeepgramEngine

            if not config.deepgram_key():
                raise RuntimeError("DEEPGRAM_API_KEY is not set")
            kw = [t.strip() for t in vocab.split(",") if t.strip()] or None
            return DeepgramEngine(
                api_key=config.deepgram_key(),
                model=self.cfg.deepgram_model,
                language=self.cfg.language or "en-US",
                keywords=kw,
                finish_timeout=self.cfg.deepgram_finish_timeout,
            )
        if name == "local":
            from .engines.local_engine import LocalEngine

            return LocalEngine(model_size=self.cfg.local_model_size,
                               language=(self.cfg.language or "").split("-")[0] or None, prompt=vocab)
        raise RuntimeError(f"Unknown engine: {name}")

    def _get_engine(self):
        if self._engine is None:
            self._engine = self._build_engine()
        return self._engine

    def _prewarm(self) -> None:
        def work():
            try:
                self._get_engine()
            except Exception as exc:
                print("engine warm-up:", exc, file=sys.stderr)

        threading.Thread(target=work, daemon=True).start()

    # ---- hotkey callbacks (run on the hotkey thread) ----------------------
    def _on_start(self, clipboard: bool = False) -> None:
        if not self._busy.acquire(blocking=False):
            return  # still finishing the previous utterance
        self._clipboard_only = clipboard
        try:
            engine = self._get_engine()
            self._session = engine.start_session(on_partial=self.overlay.set_text)
        except Exception as exc:
            self._session = None
            log.exception("could not start session (engine=%s)", self.cfg.engine)
            self._fail(str(exc))
            self._release()
            return
        self._beep(880, 70)
        self._set_icon("recording")
        self.overlay.show("listening", "")
        self.recorder.start(on_frame=self._session.feed if engine.streaming else None)
        self._started_at = time.time()

    def _on_stop(self) -> None:
        if self._session is None and not self._busy.locked():
            return
        self._beep(620, 60)
        audio = self.recorder.stop()
        duration = time.time() - self._started_at
        self._set_icon("transcribing")
        threading.Thread(target=self._finish, args=(audio, duration), daemon=True).start()

    def _finish(self, audio, duration) -> None:
        try:
            if duration < self.cfg.min_seconds or audio.size == 0:
                self.overlay.hide()
                self._set_icon("idle")
                return

            self.overlay.set_state("transcribing", "Transcribing…")
            try:
                text = self._session.finish(audio) if self._session else ""
            except Exception as exc:
                log.exception("transcription failed (engine=%s)", self.cfg.engine)
                text = self._fallback(audio, exc)

            text = (text or "").strip()
            if not text:
                self.overlay.hide()
                self._set_icon("idle")
                return

            # Spoken commands (terminal actions) — run on the RAW transcript so
            # cleanup can't reword "scratch that" / "send it".
            from . import commands

            cmd = commands.pre(text, self.cfg.voice_commands)
            if cmd.discard:
                self.overlay.set_state("done", "✗ scratched")
                self._beep(440, 80)
                self._set_icon("idle")
                return
            text = cmd.text

            # AI cleanup ("Flow mode") — OpenAI / Gemini / OpenRouter / local Ollama; falls back to raw.
            if text and self.cfg.ai_cleanup:
                from . import cleanup

                if cleanup.provider_ready(self.cfg.cleanup_provider):
                    self.overlay.set_state("transcribing", "Polishing…")
                    polished = cleanup.clean(text, self.cfg.cleanup_provider, self.cfg.cleanup_model,
                                             self.cfg.language, self.cfg.speech_notes)
                    if polished:
                        text = polished

            # inline formatting commands ("new line") — after cleanup so newlines survive
            text = commands.inline(text, self.cfg.voice_commands)

            # user word-fixes, applied last so they always stick
            text = apply_replacements(text, self.cfg.replacements)

            press_enter = self.cfg.auto_enter or cmd.press_enter
            if not text and not press_enter:
                self.overlay.hide()
                self._set_icon("idle")
                return

            if self._clipboard_only:
                if text:
                    copy_clipboard(text)
                self.overlay.set_state("done", "Copied to clipboard" if text else "↵")
            else:
                self.overlay.set_state("done", text or "↵")
                type_text(text, self.cfg.output_mode, press_enter=press_enter,
                          paste_speed=self.cfg.paste_speed)
            if self.cfg.history_enabled and text:
                try:
                    from . import history

                    history.record(text, "clipboard" if self._clipboard_only else "typed")
                except Exception:
                    pass
            self._beep(990, 60)
            self._set_icon("idle")
        finally:
            self._session = None
            self._release()

    def _fallback(self, audio, err) -> str:
        """If a cloud engine failed (e.g. offline), try local Whisper once."""
        if self.cfg.engine == "local":
            self._fail(str(err))
            return ""
        try:
            self.overlay.set_state("transcribing", "Cloud failed — using local…")
            from .engines.local_engine import LocalEngine

            local = LocalEngine(model_size=self.cfg.local_model_size, language=(self.cfg.language or "").split("-")[0] or None)
            return local.start_session(on_partial=self.overlay.set_text).finish(audio)
        except Exception as exc:
            self._fail(f"{err} (local fallback: {exc})")
            return ""

    # ---- tray actions -----------------------------------------------------
    def set_engine(self, name: str) -> None:
        self.cfg.engine = name
        self._engine = None
        self.cfg.save()
        self.tray.update()
        self._prewarm()

    def set_mode(self, mode: str) -> None:
        self.cfg.mode = mode
        self.cfg.save()
        self.tray.update()

    def set_output(self, mode: str) -> None:
        self.cfg.output_mode = mode
        self.cfg.save()
        self.tray.update()

    def toggle_overlay(self) -> None:
        self.cfg.overlay = not self.cfg.overlay
        self.cfg.save()
        if self.cfg.overlay:
            self.overlay.enabled = True
            self.overlay.start()  # no-op if already running
        else:
            self.overlay.hide()
        self.tray.update()

    def toggle_sounds(self) -> None:
        self.cfg.sounds = not self.cfg.sounds
        self.cfg.save()
        self.tray.update()

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.tray.update()

    def open_settings(self) -> None:
        import os
        import subprocess

        try:
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable, "--settings"])
            else:
                from .autostart import _pythonw

                parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                subprocess.Popen([_pythonw(), "-m", "wisprlite", "--settings"], cwd=parent)
        except Exception as exc:
            self._fail(f"settings: {exc}")

    def open_history(self) -> None:
        import os
        import subprocess

        try:
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable, "--history"])
            else:
                from .autostart import _pythonw

                parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                subprocess.Popen([_pythonw(), "-m", "wisprlite", "--history"], cwd=parent)
        except Exception as exc:
            self._fail(f"history: {exc}")

    def open_about(self) -> None:
        import os
        import subprocess

        try:
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable, "--about"])
            else:
                from .autostart import _pythonw

                parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                subprocess.Popen([_pythonw(), "-m", "wisprlite", "--about"], cwd=parent)
        except Exception as exc:
            self._fail(f"about: {exc}")

    def autostart_enabled(self) -> bool:
        return autostart.is_enabled()

    def toggle_autostart(self) -> None:
        try:
            if autostart.is_enabled():
                autostart.disable()
            else:
                autostart.enable()
        except Exception as exc:
            self._fail(f"autostart: {exc}")
        self.tray.update()

    def _notify(self, msg: str) -> None:
        try:
            if self.tray is not None and self.tray.icon is not None:
                self.tray.icon.notify(msg, "Pipevoice")
                return
        except Exception:
            pass
        print(msg)

    def check_for_updates(self, manual: bool = False) -> None:
        def work():
            try:
                from . import updater
                info = updater.check()
                if not info:
                    if manual:
                        self._notify("Pipevoice is up to date.")
                    return
                self._notify(f"Updating Pipevoice to {info['version']}…")
                if updater.download_and_run(info):
                    self.quit()
                elif manual:
                    self._notify("Update download failed — try again later.")
            except Exception as exc:
                log.warning("update flow failed: %s", exc)
        threading.Thread(target=work, daemon=True).start()

    def quit(self) -> None:
        self._stop.set()
        self.hotkeys.stop()
        self.overlay.stop()
        self.tray.stop()

    # ---- live config reload (settings window writes config.json) ----------
    def _watch_config(self) -> None:
        try:
            last = config.CONFIG_PATH.stat().st_mtime
        except Exception:
            last = None
        while not self._stop.is_set():
            time.sleep(1.0)
            try:
                mtime = config.CONFIG_PATH.stat().st_mtime
            except Exception:
                continue
            if last is None:
                last = mtime
                continue
            if mtime != last:
                last = mtime
                try:
                    self._reload_config()
                except Exception as exc:
                    print("config reload error:", exc, file=sys.stderr)

    def _reload_config(self) -> None:
        # Pick up any API key the settings window just saved to the .env file.
        try:
            from dotenv import load_dotenv

            load_dotenv(config.config_dir() / ".env", override=True)
        except Exception:
            pass

        old, new = self.cfg, config.Config.load()
        self.cfg = new  # hotkey/mode/output read live via lambdas

        engine_keys = ("engine", "openai_model", "deepgram_model",
                       "local_model_size", "language", "device", "vocabulary",
                       "deepgram_finish_timeout")
        if any(getattr(old, k) != getattr(new, k) for k in engine_keys):
            self._engine = None
            self.recorder.device = config.device_arg(new)
            self._prewarm()
        elif self._engine is None:
            # engine wasn't built yet (e.g. key was missing) — try now
            self._prewarm()

        if new.overlay and not self.overlay._started:
            self.overlay.enabled = True
            self.overlay.start()
        elif not new.overlay:
            self.overlay.hide()

        self.tray.update()

    # ---- helpers ----------------------------------------------------------
    def _release(self) -> None:
        try:
            self._busy.release()
        except RuntimeError:
            pass

    def _set_icon(self, state: str) -> None:
        self.tray.set_state(state)

    def _fail(self, msg: str) -> None:
        log.error("Pipevoice error: %s", msg)
        self._beep(220, 200)
        self.overlay.set_state("error", msg[:80])
        self.tray.set_state("error")
        threading.Timer(1.6, lambda: self.tray.set_state("idle")).start()

    def _beep(self, freq: int, ms: int) -> None:
        if self.cfg.sounds and winsound is not None:
            try:
                winsound.Beep(freq, ms)
            except Exception:
                pass

    # ---- run --------------------------------------------------------------
    def _acquire_single_instance(self) -> bool:
        import socket

        self._lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._lock_sock.bind(("127.0.0.1", 49517))
            self._lock_sock.listen(1)
            return True
        except OSError:
            return False

    def run(self) -> None:
        if not self._acquire_single_instance():
            print("Pipevoice is already running.", file=sys.stderr)
            return

        # First run: if a cloud engine has no key, ask for it in a dialog.
        from . import keyprompt

        keyprompt.ensure_api_key(self.cfg)

        self.overlay.start()
        self.tray.start()
        self.hotkeys.start()
        self.clip_hotkeys.start()
        self._prewarm()
        threading.Thread(target=self._watch_config, daemon=True).start()
        try:
            from . import updater
            updater.cleanup_old()
        except Exception:
            pass
        # If the version changed since last run, we were just updated -> tell the user.
        from . import __version__ as _ver
        if self.cfg.last_version and self.cfg.last_version != _ver:
            self._notify(f"Updated to Pipevoice {_ver}. Tray menu, About, to see what's new.")
        if self.cfg.last_version != _ver:
            self.cfg.last_version = _ver
            try:
                self.cfg.save()
            except Exception:
                pass
        if self.cfg.auto_update:
            self.check_for_updates(manual=False)

        print("Pipevoice running.")
        print(f"  Engine: {self.cfg.engine}   Mode: {self.cfg.mode}   Hotkey: [{self.cfg.hotkey}]")
        print(f"  Output: {self.cfg.output_mode}   Overlay: {self.cfg.overlay}")
        if not self.tray.ok:
            print("  (tray icon unavailable — install pystray + Pillow for the menu)")
        print("  Right-click the tray icon for settings.  Ctrl+C here to quit.")

        try:
            while not self._stop.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:
            self.quit()


def _setup_logging() -> None:
    try:
        logging.basicConfig(
            filename=str(config.config_dir() / "pipevoice.log"),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except Exception:
        pass


def main() -> None:
    _setup_logging()
    if not config.CONFIG_PATH.exists():
        # First run: a welcome/tutorial splash, then (if they continue) the
        # settings window pre-filled with the defaults. Start-at-login on too.
        try:
            from . import autostart, settings, welcome
            autostart.enable()
            config.Config.load()  # write config.json with defaults so we don't re-prompt
            if welcome.show_welcome():
                settings.main(first_run=True)
        except Exception:
            log.exception("first-run setup failed")
    log.info("Pipevoice starting (engine=%s)", config.Config.load().engine)
    try:
        App().run()
    except Exception:
        log.exception("fatal error")
        raise


if __name__ == "__main__":
    main()
