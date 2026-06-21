"""Per-app profiles: when the focused app matches, apply per-utterance overrides
(engine, ai_cleanup, auto_enter, output_mode). resolve() does the matching;
main() is the --profiles editor window.

A profile is {name, match:{exe|title_contains}, overrides:{...}}. Overrides never
mutate saved settings; app.py applies them for one utterance only.
"""

from __future__ import annotations

from . import config

KEYS = ("engine", "ai_cleanup", "auto_enter", "output_mode")


def resolve(profiles, ctx) -> dict:
    """Overrides of the first profile whose match fits ctx, else {}."""
    if not profiles or not ctx:
        return {}
    exe = (ctx.get("exe") or "").lower()
    title = (ctx.get("title") or "").lower()
    for p in profiles:
        if not isinstance(p, dict):
            continue
        match = p.get("match") or {}
        m_exe = (match.get("exe") or "").lower()
        m_title = (match.get("title_contains") or "").lower()
        if not (m_exe or m_title):
            continue
        ok = True
        if m_exe:
            ok = ok and exe == m_exe
        if m_title:
            ok = ok and m_title in title
        if ok:
            ov = p.get("overrides") or {}
            return {k: v for k, v in ov.items() if k in KEYS}
    return {}


# ---- editor window --------------------------------------------------------
BG = "#13151d"
CARD = "#1b1e29"
FG = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#e06c75"

P_ENGINES = [("", "(app default)"), ("deepgram", "Deepgram"), ("openai", "OpenAI"), ("local", "Local")]
P_OUTPUTS = [("type", "Type"), ("paste", "Paste"), ("clipboard", "Clipboard")]

# Common apps so popular targets appear even when they aren't currently running.
COMMON_APPS = [
    ("code.exe", "VS Code"), ("cursor.exe", "Cursor"), ("chrome.exe", "Chrome"),
    ("msedge.exe", "Edge"), ("firefox.exe", "Firefox"),
    ("windowsterminal.exe", "Windows Terminal"), ("powershell.exe", "PowerShell"),
    ("cmd.exe", "Command Prompt"), ("slack.exe", "Slack"), ("discord.exe", "Discord"),
    ("ms-teams.exe", "Teams"), ("notepad.exe", "Notepad"), ("notepad++.exe", "Notepad++"),
    ("winword.exe", "Word"), ("outlook.exe", "Outlook"), ("obsidian.exe", "Obsidian"),
    ("idea64.exe", "IntelliJ IDEA"), ("explorer.exe", "File Explorer"),
    ("telegram.exe", "Telegram"), ("whatsapp.exe", "WhatsApp"),
]


def _value_for(label, table):
    return {l: k for k, l in table}.get(label, table[0][0])


def main() -> None:
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return
    from . import winui

    cfg = config.Config.load()
    cards = []
    from . import foreground
    running = foreground.list_windows()
    have = {w["exe"].lower() for w in running}
    merged = list(running) + [{"exe": e, "title": t} for e, t in COMMON_APPS if e.lower() not in have]
    app_values = sorted(
        (w["exe"] + ("  —  " + w["title"][:34] if w.get("title") else "") for w in merged),
        key=str.lower,
    )

    root = tk.Tk()
    root.title("Pipevoice app profiles")
    root.configure(bg=BG)
    ico = config.asset_path("wisprlite.ico")
    if ico:
        try:
            root.iconbitmap(ico)
        except Exception:
            pass

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
    style.configure("TButton", background=CARD, foreground=FG, padding=6, borderwidth=0)
    style.map("TButton", background=[("active", "#262a3a")])
    style.configure("Accent.TButton", background=ACCENT, foreground="#1a0c0d",
                    font=("Segoe UI", 9, "bold"), padding=7, borderwidth=0)
    style.map("Accent.TButton", background=[("active", "#e8838b")])
    style.configure("TCheckbutton", background=CARD, foreground=FG)
    style.map("TCheckbutton", background=[("active", CARD)])
    style.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=FG, arrowcolor=FG)
    style.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", CARD)], selectforeground=[("readonly", FG)],
              background=[("readonly", CARD), ("active", CARD)])
    style.configure("TEntry", fieldbackground=CARD, foreground=FG, insertcolor=FG)
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#1a0c0d")

    head = tk.Frame(root, bg=BG, padx=22, pady=18)
    head.pack(fill="x")
    tk.Label(head, text="App profiles", bg=BG, fg=ACCENT, font=("Segoe UI", 16, "bold")).pack(anchor="w")
    tk.Label(head, text="Give an app its own behaviour. Terminal: raw + Enter. Chat: polished + auto-send.\n"
                        "Editor: no AI cleanup. Pick from the dropdown (running + common apps), or type any exe name.",
             bg=BG, fg=MUTED, font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(5, 0))

    footer = tk.Frame(root, bg=BG, padx=22, pady=12)
    footer.pack(side="bottom", fill="x")

    bodyf = tk.Frame(root, bg=BG)
    bodyf.pack(fill="both", expand=True)
    canvas = tk.Canvas(bodyf, bg=BG, highlightthickness=0, width=560, height=350)
    vbar = ttk.Scrollbar(bodyf, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vbar.set)
    vbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    holder = tk.Frame(canvas, bg=BG)
    canvas.create_window((0, 0), window=holder, anchor="nw")
    holder.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Enter>", lambda e: canvas.bind_all(
        "<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    def add_card(exe="", overrides=None):
        overrides = overrides or {}
        c = tk.Frame(holder, bg=CARD, padx=14, pady=12)
        c.pack(fill="x", padx=16, pady=6)
        card = {}

        r1 = tk.Frame(c, bg=CARD)
        r1.pack(fill="x")
        tk.Label(r1, text="App:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        exe_var = tk.StringVar(value=exe)
        ttk.Combobox(r1, textvariable=exe_var, values=app_values, width=34).pack(side="left", padx=(8, 0))
        ttk.Button(r1, text="Remove", command=lambda: (c.destroy(), card in cards and cards.remove(card))).pack(side="right")

        r2 = tk.Frame(c, bg=CARD)
        r2.pack(fill="x", pady=(9, 0))
        tk.Label(r2, text="Engine", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        engine_var = tk.StringVar(value=dict(P_ENGINES).get(overrides.get("engine", ""), P_ENGINES[0][1]))
        ttk.Combobox(r2, textvariable=engine_var, values=[l for _, l in P_ENGINES],
                     state="readonly", width=13).pack(side="left", padx=(6, 18))
        tk.Label(r2, text="Output", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        output_var = tk.StringVar(value=dict(P_OUTPUTS).get(overrides.get("output_mode", cfg.output_mode), P_OUTPUTS[0][1]))
        ttk.Combobox(r2, textvariable=output_var, values=[l for _, l in P_OUTPUTS],
                     state="readonly", width=11).pack(side="left", padx=(6, 0))

        r3 = tk.Frame(c, bg=CARD)
        r3.pack(fill="x", pady=(9, 0))
        cleanup_var = tk.BooleanVar(value=bool(overrides.get("ai_cleanup", cfg.ai_cleanup)))
        autoenter_var = tk.BooleanVar(value=bool(overrides.get("auto_enter", cfg.auto_enter)))
        ttk.Checkbutton(r3, text="AI cleanup", variable=cleanup_var).pack(side="left")
        ttk.Checkbutton(r3, text="Auto-Enter", variable=autoenter_var).pack(side="left", padx=(18, 0))

        card.update(exe=exe_var, engine=engine_var, output=output_var,
                    cleanup=cleanup_var, autoenter=autoenter_var)
        cards.append(card)

    for p in (cfg.profiles or []):
        if isinstance(p, dict):
            add_card((p.get("match") or {}).get("exe", ""), p.get("overrides") or {})
    if not cfg.profiles:
        add_card()

    def save():
        out = []
        for card in cards:
            exe = card["exe"].get().split("—")[0].strip().lower()
            if not exe:
                continue
            ov = {
                "ai_cleanup": bool(card["cleanup"].get()),
                "auto_enter": bool(card["autoenter"].get()),
                "output_mode": _value_for(card["output"].get(), P_OUTPUTS),
            }
            eng = _value_for(card["engine"].get(), P_ENGINES)
            if eng:
                ov["engine"] = eng
            out.append({"name": exe, "match": {"exe": exe}, "overrides": ov})
        # Reload first so we only change `profiles`, not other settings the user
        # may have edited in the Settings window meanwhile.
        fresh = config.Config.load()
        fresh.profiles = out
        fresh.save()
        root.destroy()

    ttk.Button(footer, text="+ Add app profile", command=lambda: add_card()).pack(side="left")
    ttk.Button(footer, text="Save", style="Accent.TButton", command=save).pack(side="right")
    ttk.Button(footer, text="Cancel", command=root.destroy).pack(side="right", padx=(0, 8))

    root.update_idletasks()
    w = max(620, root.winfo_reqwidth())
    h = min(640, max(420, root.winfo_reqheight()))
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")
    winui.dark_titlebar(root)
    root.mainloop()


if __name__ == "__main__":
    main()
