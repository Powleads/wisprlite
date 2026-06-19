"""Inject transcribed text into the focused window."""

from __future__ import annotations

import time

import keyboard


def type_text(text: str, mode: str = "type") -> None:
    if not text:
        return

    if mode == "paste":
        try:
            import pyperclip

            try:
                prev = pyperclip.paste()
            except Exception:
                prev = None
            pyperclip.copy(text)
            time.sleep(0.03)
            keyboard.send("ctrl+v")
            # restore the user's previous clipboard shortly after paste lands
            if prev is not None:
                time.sleep(0.15)
                try:
                    pyperclip.copy(prev)
                except Exception:
                    pass
            return
        except Exception:
            pass  # pyperclip missing or failed -> fall through to typing

    keyboard.write(text, delay=0)
