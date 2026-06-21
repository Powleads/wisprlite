"""Shared branding: the PipeVoice wordmark lockup as a Tk image.

Uses tk.PhotoImage (Tk 8.6 reads PNG natively) so no Pillow dependency is needed
just to show the logo. Falls back to a coral text label if the asset is missing.
"""

from __future__ import annotations

from . import config

ACCENT = "#e06c75"


def lockup_label(parent, bg):
    """A Label showing the lockup (white "PipeVoice" wordmark + pink mic-P) on `bg`.
    Keeps an image reference on the widget so Tk doesn't garbage-collect it."""
    import tkinter as tk

    path = config.asset_path("pipevoice-lockup.png")
    if path:
        try:
            img = tk.PhotoImage(file=path)
            lbl = tk.Label(parent, image=img, bg=bg, bd=0, highlightthickness=0)
            lbl.image = img  # prevent GC
            return lbl
        except Exception:
            pass
    return tk.Label(parent, text="Pipevoice", bg=bg, fg=ACCENT, font=("Segoe UI", 21, "bold"))
