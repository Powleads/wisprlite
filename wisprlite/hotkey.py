"""Global hotkey detection for push-to-talk and toggle modes.

Uses a light polling loop (~100 Hz) so it handles both single keys and combos
("ctrl+alt") uniformly, and supports changing the hotkey/mode at runtime.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

import keyboard


def _all_pressed(hotkey: str) -> bool:
    parts = [p.strip() for p in hotkey.split("+") if p.strip()]
    if not parts:
        return False
    try:
        return all(keyboard.is_pressed(p) for p in parts)
    except Exception:
        return False


class HotkeyManager:
    def __init__(
        self,
        get_hotkey: Callable[[], str],
        get_mode: Callable[[], str],
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        is_paused: Callable[[], bool],
    ) -> None:
        self.get_hotkey = get_hotkey
        self.get_mode = get_mode
        self.on_start = on_start
        self.on_stop = on_stop
        self.is_paused = is_paused
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._recording = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        prev = False
        while not self._stop.is_set():
            pressed = _all_pressed(self.get_hotkey())

            if self.is_paused():
                # if we were mid-record when paused, close it out cleanly
                if self._recording:
                    self._recording = False
                    self._safe(self.on_stop)
                prev = pressed
                time.sleep(0.02)
                continue

            if self.get_mode() == "toggle":
                if pressed and not prev:  # rising edge flips state
                    self._recording = not self._recording
                    self._safe(self.on_start if self._recording else self.on_stop)
            else:  # push-to-talk: state follows the key
                if pressed and not self._recording:
                    self._recording = True
                    self._safe(self.on_start)
                elif not pressed and self._recording:
                    self._recording = False
                    self._safe(self.on_stop)

            prev = pressed
            time.sleep(0.01)

    @staticmethod
    def _safe(fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as exc:  # never let a callback kill the loop
            print("hotkey callback error:", exc)
