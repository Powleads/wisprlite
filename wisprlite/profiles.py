"""Per-app profiles: when the focused app matches, apply per-utterance overrides
(engine, ai_cleanup, auto_enter, output_mode). resolve() does the matching;
main() is the --profiles editor window.

A profile is {name, match:{exe|title_contains}, overrides:{...}}. Overrides never
mutate saved settings; app.py applies them for one utterance only.
"""

from __future__ import annotations

import os

from . import config

KEYS = ("engine", "ai_cleanup", "auto_enter", "output_mode", "cleanup_style", "cleanup_instruction")


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
P_STYLES = [("", "(app default)"), ("tidy", "Tidy — clean up"), ("prompt", "Prompt — for AI tools"), ("custom", "Custom…")]

# Common apps so popular targets appear even when they aren't currently running.
# Full product names so a natural search ("visual studio code") matches.
COMMON_APPS = [
    ("code.exe", "Visual Studio Code"), ("cursor.exe", "Cursor"), ("chrome.exe", "Google Chrome"),
    ("msedge.exe", "Microsoft Edge"), ("firefox.exe", "Mozilla Firefox"),
    ("windowsterminal.exe", "Windows Terminal"), ("powershell.exe", "PowerShell"),
    ("cmd.exe", "Command Prompt"), ("slack.exe", "Slack"), ("discord.exe", "Discord"),
    ("ms-teams.exe", "Microsoft Teams"), ("notepad.exe", "Notepad"), ("notepad++.exe", "Notepad++"),
    ("winword.exe", "Microsoft Word"), ("outlook.exe", "Microsoft Outlook"), ("obsidian.exe", "Obsidian"),
    ("idea64.exe", "IntelliJ IDEA"), ("explorer.exe", "File Explorer"),
    ("telegram.exe", "Telegram"), ("whatsapp.exe", "WhatsApp"),
]


def _value_for(label, table):
    return {l: k for k, l in table}.get(label, table[0][0])


def _searchable(combo, all_values):
    """Type-to-filter a combobox: narrows the dropdown to matches as you type."""
    def on_key(event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab", "Left", "Right",
                             "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        typed = combo.get().strip().lower()
        if not typed:
            combo["values"] = all_values
        else:
            matches = [v for v in all_values if typed in v.lower()]
            combo["values"] = matches or all_values
    combo.bind("<KeyRelease>", on_key)


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
    # Lighter than the card so in-card buttons (Browse) read as buttons, not text.
    style.configure("Pick.TButton", background="#2a2f3d", foreground=FG, padding=6, borderwidth=0)
    style.map("Pick.TButton", background=[("active", "#333a4a")])
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
                        "Editor: no AI cleanup. Search your open apps, or Browse to pick any program.",
             bg=BG, fg=MUTED, font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(5, 0))

    footer = tk.Frame(root, bg=BG, padx=22, pady=12)
    footer.pack(side="bottom", fill="x")

    bodyf = tk.Frame(root, bg=BG)
    bodyf.pack(fill="both", expand=True)
    canvas = tk.Canvas(bodyf, bg=BG, highlightthickness=0, width=640, height=360)
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
        wrap = tk.Frame(holder, bg=BG)
        wrap.pack(fill="x", padx=18, pady=(0, 12))
        c = tk.Frame(wrap, bg=CARD)
        c.pack(fill="x")
        inner = tk.Frame(c, bg=CARD, padx=18, pady=16)
        inner.pack(fill="x")
        card = {}

        tk.Label(inner, text="APP", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(inner, text="Type to search your open apps, or Browse to pick any program (.exe).",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
        pick = tk.Frame(inner, bg=CARD)
        pick.pack(fill="x", pady=(6, 0))
        exe_var = tk.StringVar(value=exe)
        cb = ttk.Combobox(pick, textvariable=exe_var, values=app_values, width=32)
        cb.pack(side="left")
        _searchable(cb, app_values)

        def browse(var=exe_var):
            # Native file picker, so the user can grab any installed program by
            # navigating to its .exe instead of guessing the process name.
            from tkinter import filedialog
            la = os.environ.get("LOCALAPPDATA")
            cands = [os.path.join(la, "Programs")] if la else []
            cands += [la, os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432")]
            initial = next((c for c in cands if c and os.path.isdir(c)), os.path.expanduser("~"))
            path = filedialog.askopenfilename(
                parent=root, title="Pick a program",
                initialdir=initial,
                filetypes=[("Programs", "*.exe"), ("All files", "*.*")])
            if path:
                var.set(os.path.basename(path))

        ttk.Button(pick, text="Browse…", style="Pick.TButton", command=browse).pack(side="left", padx=(8, 0))
        ttk.Button(pick, text="Remove",
                   command=lambda: (wrap.destroy(), card in cards and cards.remove(card))).pack(side="right")

        ctl = tk.Frame(inner, bg=CARD)
        ctl.pack(fill="x", pady=(16, 0))
        eng_col = tk.Frame(ctl, bg=CARD)
        eng_col.pack(side="left", padx=(0, 26))
        tk.Label(eng_col, text="ENGINE", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        engine_var = tk.StringVar(value=dict(P_ENGINES).get(overrides.get("engine", ""), P_ENGINES[0][1]))
        ttk.Combobox(eng_col, textvariable=engine_var, values=[l for _, l in P_ENGINES],
                     state="readonly", width=14).pack(anchor="w", pady=(5, 0))
        out_col = tk.Frame(ctl, bg=CARD)
        out_col.pack(side="left")
        tk.Label(out_col, text="OUTPUT", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        output_var = tk.StringVar(value=dict(P_OUTPUTS).get(overrides.get("output_mode", cfg.output_mode), P_OUTPUTS[0][1]))
        ttk.Combobox(out_col, textvariable=output_var, values=[l for _, l in P_OUTPUTS],
                     state="readonly", width=12).pack(anchor="w", pady=(5, 0))

        sty_col = tk.Frame(ctl, bg=CARD)
        sty_col.pack(side="left", padx=(26, 0))
        tk.Label(sty_col, text="POLISH STYLE", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        style_var = tk.StringVar(value=dict(P_STYLES).get(overrides.get("cleanup_style", ""), P_STYLES[0][1]))
        ttk.Combobox(sty_col, textvariable=style_var, values=[l for _, l in P_STYLES],
                     state="readonly", width=16).pack(anchor="w", pady=(5, 0))

        chk = tk.Frame(inner, bg=CARD)
        chk.pack(fill="x", pady=(16, 0))
        cleanup_var = tk.BooleanVar(value=bool(overrides.get("ai_cleanup", cfg.ai_cleanup)))
        autoenter_var = tk.BooleanVar(value=bool(overrides.get("auto_enter", cfg.auto_enter)))
        ttk.Checkbutton(chk, text="AI cleanup", variable=cleanup_var).pack(side="left")
        ttk.Checkbutton(chk, text="Auto-Enter", variable=autoenter_var).pack(side="left", padx=(22, 0))

        instr_frame = tk.Frame(inner, bg=CARD)
        instr_frame.pack(fill="x", pady=(12, 0))
        tk.Label(instr_frame, text="Custom polish instruction (used when style = Custom)",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")
        instr_var = tk.StringVar(value=overrides.get("cleanup_instruction", ""))
        ttk.Entry(instr_frame, textvariable=instr_var, width=60).pack(anchor="w", pady=(4, 0))

        card.update(exe=exe_var, engine=engine_var, output=output_var,
                    cleanup=cleanup_var, autoenter=autoenter_var, style=style_var, instruction=instr_var)
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
            sty = _value_for(card["style"].get(), P_STYLES)
            if sty:
                ov["cleanup_style"] = sty
            ci = card["instruction"].get().strip()
            if ci:
                ov["cleanup_instruction"] = ci
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
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w = max(700, root.winfo_reqwidth())
    h = min(max(460, root.winfo_reqheight() + 16), sh - 150)
    root.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(16, (sh - h) // 5)}")
    winui.dark_titlebar(root)
    root.mainloop()


if __name__ == "__main__":
    main()
