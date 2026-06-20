"""First-run welcome / tutorial splash.

Shown once on first launch (before the settings window) to explain how Pipevoice
works and how to get an API key. Returns True if the user clicked "Get started"
(so the caller opens Settings next), False if they chose to set up later.

Plain Tk on the app's dark palette; runs its own short-lived root, fully torn
down before anything else starts (same pattern as keyprompt).
"""

from __future__ import annotations

import webbrowser

from . import config

BG = "#13151d"
CARD = "#1b1e29"
FG = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#34d399"

OPENAI_URL = "https://platform.openai.com/api-keys"
DEEPGRAM_URL = "https://console.deepgram.com/"


def show_welcome() -> bool:
    """Display the welcome/tutorial. Returns True to continue to Settings."""
    try:
        import tkinter as tk
    except Exception:
        return True  # no Tk (headless) -> just go straight to settings

    result = {"go": False}

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

    wrap = tk.Frame(root, bg=BG, padx=36, pady=30)
    wrap.pack()

    # --- header ---
    tk.Label(wrap, text="Pipevoice", bg=BG, fg=ACCENT,
             font=("Segoe UI", 23, "bold")).pack(anchor="w")
    tk.Label(wrap, text="Talk faster than you type.", bg=BG, fg=FG,
             font=("Segoe UI", 13)).pack(anchor="w", pady=(2, 0))
    tk.Label(wrap, text="Push-to-talk voice typing for Windows — your words land in any app.",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 20))

    # --- how it works ---
    tk.Label(wrap, text="HOW IT WORKS", bg=BG, fg=ACCENT,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
    steps = [
        ("1", "Hold your hotkey", "default: Ctrl + \\"),
        ("2", "Talk", "just say what you want typed"),
        ("3", "Release", "your words type wherever the cursor is"),
    ]
    for n, title, sub in steps:
        row = tk.Frame(wrap, bg=BG)
        row.pack(anchor="w", fill="x", pady=3)
        tk.Label(row, text=f" {n} ", bg=CARD, fg=ACCENT,
                 font=("Consolas", 10, "bold")).pack(side="left")
        tk.Label(row, text=f"  {title}", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(row, text=f"  — {sub}", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")

    # --- get a key ---
    tk.Label(wrap, text="BEFORE YOU START — GET ONE API KEY", bg=BG, fg=ACCENT,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(22, 2))
    tk.Label(wrap, text="Pick either one. Both are free to sign up — you just add a few dollars of",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
    tk.Label(wrap, text="credit, and it costs only pennies a day to use.",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 9))

    def key_card(name, desc, url):
        row = tk.Frame(wrap, bg=CARD, padx=14, pady=10)
        row.pack(anchor="w", fill="x", pady=4)
        left = tk.Frame(row, bg=CARD)
        left.pack(side="left")
        tk.Label(left, text=name, bg=CARD, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(left, text=desc, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w")
        link = tk.Label(row, text="Get key  ↗", bg=CARD, fg=ACCENT, cursor="hand2",
                        font=("Segoe UI", 10, "underline"))
        link.pack(side="right", padx=(24, 2))
        link.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

    key_card("OpenAI Whisper", "Most accurate  ·  platform.openai.com", OPENAI_URL)
    key_card("Deepgram", "Live, lowest latency  ·  console.deepgram.com", DEEPGRAM_URL)

    tk.Label(wrap, text="No key? Pick the Offline engine on the next screen — it runs on your PC, free.",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(9, 0))

    # --- buttons ---
    btns = tk.Frame(wrap, bg=BG)
    btns.pack(fill="x", pady=(24, 0))

    def go():
        result["go"] = True
        root.destroy()

    def later():
        result["go"] = False
        root.destroy()

    tk.Button(btns, text="I'll set up later", command=later, bg=CARD, fg=FG,
              activebackground="#262a3a", activeforeground=FG, relief="flat",
              padx=16, pady=8, font=("Segoe UI", 9)).pack(side="left")
    tk.Button(btns, text="Get started   →", command=go, bg=ACCENT, fg="#06281c",
              activebackground="#2bb588", relief="flat", padx=22, pady=8,
              font=("Segoe UI", 10, "bold")).pack(side="right")

    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 4}")
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    root.mainloop()
    return result["go"]
