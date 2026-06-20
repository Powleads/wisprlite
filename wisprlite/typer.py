"""Inject transcribed text into the focused window, plus text post-processing."""

from __future__ import annotations

import re
import time

import keyboard


def apply_replacements(text: str, mapping: dict) -> str:
    """Apply user word-fixes (case-insensitive, word-boundary aware)."""
    if not text or not mapping:
        return text
    for find, repl in mapping.items():
        if not find:
            continue
        try:
            text = re.sub(rf"\b{re.escape(find)}\b", repl, text, flags=re.IGNORECASE)
        except re.error:
            pass
    return text


def type_text(text: str, mode: str = "type", press_enter: bool = False) -> None:
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
            if prev is not None:
                time.sleep(0.15)
                try:
                    pyperclip.copy(prev)
                except Exception:
                    pass
            if press_enter:
                time.sleep(0.05)
                keyboard.send("enter")
            return
        except Exception:
            pass  # pyperclip missing or failed -> fall through to typing

    keyboard.write(text, delay=0)
    if press_enter:
        time.sleep(0.05)
        keyboard.send("enter")


def copy_clipboard(text: str) -> bool:
    """Copy text to the clipboard without typing or pasting it. True on success."""
    if not text:
        return False
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception:
        return False
