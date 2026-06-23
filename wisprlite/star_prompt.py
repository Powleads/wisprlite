"""One-time, dismissible nudge to star PipeVoice on GitHub.

Counts launches and, once the user has actually used the app a few times, shows a
single friendly "star us" dialog (never again after that). Tiny Tk root on the main
thread, torn down before anything else starts — same pattern as keyprompt/welcome.
Any failure is swallowed so it can never block startup.
"""

from __future__ import annotations

import webbrowser

from . import config

GITHUB_URL = "https://github.com/Powleads/PipeVoice"
_AFTER_LAUNCHES = 3  # show on the 3rd launch — they've used it by now, not day one

BG = "#13151d"
CARD = "#1b1e29"
FG = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#e06c75"


def maybe_show(cfg) -> None:
    """Count this launch; once past the threshold, show the star nudge exactly once."""
    try:
        cfg.launches = int(getattr(cfg, "launches", 0) or 0) + 1
        show = (not getattr(cfg, "star_prompt_shown", False)
                and cfg.launches >= _AFTER_LAUNCHES)
        if show:
            cfg.star_prompt_shown = True
        cfg.save()
    except Exception:
        return
    if show:
        try:
            _dialog()
        except Exception:
            pass  # headless / no Tk -> never block startup


def _dialog() -> None:
    import tkinter as tk

    root = tk.Tk()
    root.title("PipeVoice")
    root.configure(bg=BG)
    root.resizable(False, False)
    ico = config.asset_path("wisprlite.ico")
    if ico:
        try:
            root.iconbitmap(ico)
        except Exception:
            pass

    wrap = tk.Frame(root, bg=BG, padx=28, pady=24)
    wrap.pack()
    tk.Label(wrap, text="Enjoying PipeVoice?", bg=BG, fg=ACCENT,
             font=("Segoe UI", 16, "bold")).pack(anchor="w")
    tk.Label(wrap, text="It's free and open-source. A quick GitHub star genuinely helps\n"
                        "more people find it — it only takes a second. 🙏",
             bg=BG, fg=FG, font=("Segoe UI", 10), justify="left").pack(anchor="w", pady=(6, 16))

    btns = tk.Frame(wrap, bg=BG)
    btns.pack(fill="x")

    def star():
        try:
            webbrowser.open(GITHUB_URL)
        except Exception:
            pass
        root.destroy()

    tk.Button(btns, text="Maybe later", command=root.destroy, bg=CARD, fg=FG,
              activebackground="#262a3a", activeforeground=FG, relief="flat",
              padx=12, pady=7, font=("Segoe UI", 9)).pack(side="left")
    tk.Button(btns, text="⭐ Star it on GitHub", command=star, bg=ACCENT, fg="#1a0c0d",
              activebackground="#e8838b", relief="flat", padx=16, pady=7,
              font=("Segoe UI", 9, "bold")).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")
    try:
        from . import winui
        winui.dark_titlebar(root)
    except Exception:
        pass
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    root.mainloop()
