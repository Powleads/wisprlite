"""First-run welcome dialog: ask for the API key, save it, then carry on.

Shown on startup only when the selected cloud engine has no key. Writes the key
to %APPDATA%\\Pipevoice\\.env so it persists. Runs a short-lived Tk root on the
main thread, fully torn down before the overlay's UI thread starts.
"""

from __future__ import annotations

import webbrowser

from . import config

BG = "#13151d"
CARD = "#1b1e29"
FG = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#e06c75"

PROVIDER = {
    "openai": ("OpenAI", "OPENAI_API_KEY", "https://platform.openai.com/api-keys", "sk-..."),
    "deepgram": ("Deepgram", "DEEPGRAM_API_KEY", "https://console.deepgram.com/", "your key"),
}


def has_key(engine: str) -> bool:
    if engine == "openai":
        return bool(config.openai_key())
    if engine == "deepgram":
        return bool(config.deepgram_key())
    return True  # local needs no key


def ensure_api_key(cfg) -> None:
    if has_key(cfg.engine) or cfg.engine not in PROVIDER:
        return
    # Don't nag every launch: if the user already dismissed the prompt for this
    # engine, stay quiet until they pick a different engine (or add a key).
    if getattr(cfg, "key_prompt_skipped_for", "") == cfg.engine:
        return
    try:
        _dialog(cfg)
    except Exception:
        pass  # headless / no Tk -> app still runs; key can be set in Settings


def _dialog(cfg) -> None:
    import tkinter as tk

    engine = cfg.engine
    label, env_name, url, placeholder = PROVIDER[engine]

    root = tk.Tk()
    root.title("Welcome to Pipevoice")
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

    tk.Label(wrap, text="Pipevoice", bg=BG, fg=ACCENT,
             font=("Segoe UI", 18, "bold")).pack(anchor="w")
    tk.Label(wrap, text=f"Paste your {label} key — it stays on this PC.",
             bg=BG, fg=FG, font=("Segoe UI", 11)).pack(anchor="w", pady=(2, 3))
    tk.Label(wrap, text="No key? Use the offline engine instead — free and fully private.",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 14))

    var = tk.StringVar()
    entry = tk.Entry(wrap, textvariable=var, width=46, show="•",
                     bg=CARD, fg=FG, insertbackground=FG, relief="flat",
                     font=("Consolas", 11))
    entry.pack(ipady=6, fill="x")
    entry.insert(0, "")
    entry.focus_set()

    rowf = tk.Frame(wrap, bg=BG)
    rowf.pack(fill="x", pady=(8, 0))
    show_var = tk.BooleanVar(value=False)

    def toggle():
        entry.config(show="" if show_var.get() else "•")

    tk.Checkbutton(rowf, text="Show", variable=show_var, command=toggle,
                   bg=BG, fg=MUTED, selectcolor=CARD, activebackground=BG,
                   activeforeground=FG, relief="flat",
                   font=("Segoe UI", 9)).pack(side="left")

    link = tk.Label(rowf, text="Get a key ↗", bg=BG, fg=ACCENT, cursor="hand2",
                    font=("Segoe UI", 9, "underline"))
    link.pack(side="right")
    link.bind("<Button-1>", lambda e: webbrowser.open(url))

    tk.Label(wrap, text="Stored locally in %APPDATA%\\Pipevoice\\.env — never uploaded.",
             bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(10, 16))

    err = tk.Label(wrap, text="", bg=BG, fg="#f87171", font=("Segoe UI", 9))
    err.pack(anchor="w", pady=(0, 6))

    btns = tk.Frame(wrap, bg=BG)
    btns.pack(fill="x")

    def _valid(k: str) -> bool:
        k = (k or "").strip()
        if not k:
            err.config(text="Paste a key, or choose Use offline.")
            return False
        if engine == "openai" and not k.startswith("sk-"):
            err.config(text="That doesn't look like an OpenAI key (it starts with 'sk-').")
            return False
        if len(k) < 16:
            err.config(text="That key looks too short — double-check it.")
            return False
        return True

    def save(_=None):
        if not _valid(var.get()):
            return
        config.save_api_key(env_name, var.get())
        root.destroy()

    def use_offline():
        cfg.engine = "local"
        cfg.key_prompt_skipped_for = ""
        try:
            cfg.save()
        except Exception:
            pass
        root.destroy()

    def skip():
        # Remember the skip so we don't re-prompt for this engine every launch.
        cfg.key_prompt_skipped_for = cfg.engine
        try:
            cfg.save()
        except Exception:
            pass
        root.destroy()

    tk.Button(btns, text="Skip for now", command=skip, bg=CARD, fg=FG,
              activebackground="#262a3a", activeforeground=FG, relief="flat",
              padx=12, pady=7, font=("Segoe UI", 9)).pack(side="left")
    tk.Button(btns, text="Use offline", command=use_offline, bg=CARD, fg=FG,
              activebackground="#262a3a", activeforeground=FG, relief="flat",
              padx=12, pady=7, font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))
    save_btn = tk.Button(btns, text="Save & start", command=save, bg=ACCENT,
                         fg="#1a0c0d", activebackground="#e8838b", relief="flat",
                         padx=16, pady=7, font=("Segoe UI", 9, "bold"))
    save_btn.pack(side="right")
    entry.bind("<Return>", save)
    # Closing via the window's X is also a dismissal: remember it like "Skip".
    root.protocol("WM_DELETE_WINDOW", skip)

    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")
    from . import winui
    winui.dark_titlebar(root)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    root.mainloop()
