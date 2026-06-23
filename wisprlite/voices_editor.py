"""The --voices editor window: CRUD named polish 'Voices' (cfg.voices).

A Voice is a reusable per-utterance override preset (see voices.py). Each card
edits one Voice; empty fields mean "leave that setting unchanged". Save() reloads
config first so a concurrent Settings save isn't clobbered — only `voices` changes.
"""

from __future__ import annotations

from . import config, voices  # noqa: F401  (voices kept for parity / future use)

# ---- editor window --------------------------------------------------------
BG = "#13151d"
CARD = "#1b1e29"
FG = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#e06c75"

STYLES = [("tidy", "Tidy — clean up"),
          ("prompt", "Prompt — reshuffle into coherent text"),
          ("custom", "Custom…")]
ENGINES = [("", "(leave as-is)"), ("gemini", "Gemini"), ("groq", "Groq"),
           ("deepgram", "Deepgram"), ("local", "Local")]
OUTPUTS = [("", "(leave as-is)"), ("type", "Type"), ("paste", "Paste"),
           ("clipboard", "Clipboard")]
AUTO = [("leave", "(leave as-is)"), ("yes", "Yes"), ("no", "No")]
CLEANUP = [("leave", "(leave as-is)"), ("on", "On"), ("off", "Off")]


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

    root = tk.Tk()
    root.title("Pipevoice voices")
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
    tk.Label(head, text="Voices", bg=BG, fg=ACCENT, font=("Segoe UI", 16, "bold")).pack(anchor="w")
    tk.Label(head, text="Named polish presets. Bind them to hotkeys or apps. "
                        "Empty fields = leave that setting unchanged.",
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

    def add_card(voice=None):
        voice = voice or {}
        wrap = tk.Frame(holder, bg=BG)
        wrap.pack(fill="x", padx=18, pady=(0, 12))
        c = tk.Frame(wrap, bg=CARD)
        c.pack(fill="x")
        inner = tk.Frame(c, bg=CARD, padx=18, pady=16)
        inner.pack(fill="x")
        card = {}

        # Name
        toprow = tk.Frame(inner, bg=CARD)
        toprow.pack(fill="x")
        name_col = tk.Frame(toprow, bg=CARD)
        name_col.pack(side="left", fill="x", expand=True)
        tk.Label(name_col, text="NAME", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        name_var = tk.StringVar(value=voice.get("name", ""))
        ttk.Entry(name_col, textvariable=name_var, width=32).pack(anchor="w", pady=(5, 0))
        ttk.Button(toprow, text="Remove",
                   command=lambda: (wrap.destroy(), card in cards and cards.remove(card))).pack(side="right")

        # Style / Engine / Output
        ctl = tk.Frame(inner, bg=CARD)
        ctl.pack(fill="x", pady=(16, 0))

        sty_col = tk.Frame(ctl, bg=CARD)
        sty_col.pack(side="left", padx=(0, 26))
        tk.Label(sty_col, text="STYLE", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        style_var = tk.StringVar(value=dict(STYLES).get(voice.get("cleanup_style", ""), STYLES[0][1]))
        ttk.Combobox(sty_col, textvariable=style_var, values=[l for _, l in STYLES],
                     state="readonly", width=30).pack(anchor="w", pady=(5, 0))

        eng_col = tk.Frame(ctl, bg=CARD)
        eng_col.pack(side="left", padx=(0, 26))
        tk.Label(eng_col, text="ENGINE", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        engine_var = tk.StringVar(value=dict(ENGINES).get(voice.get("engine", ""), ENGINES[0][1]))
        ttk.Combobox(eng_col, textvariable=engine_var, values=[l for _, l in ENGINES],
                     state="readonly", width=14).pack(anchor="w", pady=(5, 0))

        out_col = tk.Frame(ctl, bg=CARD)
        out_col.pack(side="left")
        tk.Label(out_col, text="OUTPUT", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        output_var = tk.StringVar(value=dict(OUTPUTS).get(voice.get("output_mode", ""), OUTPUTS[0][1]))
        ttk.Combobox(out_col, textvariable=output_var, values=[l for _, l in OUTPUTS],
                     state="readonly", width=14).pack(anchor="w", pady=(5, 0))

        # Auto-Enter
        ae_row = tk.Frame(inner, bg=CARD)
        ae_row.pack(fill="x", pady=(16, 0))
        ae_col = tk.Frame(ae_row, bg=CARD)
        ae_col.pack(side="left")
        tk.Label(ae_col, text="AUTO-ENTER", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        ae = voice.get("auto_enter", None)
        ae_label = AUTO[0][1] if ae is None else (AUTO[1][1] if ae else AUTO[2][1])
        autoenter_var = tk.StringVar(value=ae_label)
        ttk.Combobox(ae_col, textvariable=autoenter_var, values=[l for _, l in AUTO],
                     state="readonly", width=14).pack(anchor="w", pady=(5, 0))

        cl_col = tk.Frame(ae_row, bg=CARD)
        cl_col.pack(side="left", padx=(26, 0))
        tk.Label(cl_col, text="AI CLEANUP", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        ac = voice.get("ai_cleanup", None)
        ac_label = CLEANUP[0][1] if ac is None else (CLEANUP[1][1] if ac else CLEANUP[2][1])
        cleanup_var = tk.StringVar(value=ac_label)
        ttk.Combobox(cl_col, textvariable=cleanup_var, values=[l for _, l in CLEANUP],
                     state="readonly", width=14).pack(anchor="w", pady=(5, 0))

        # Custom instruction
        instr_frame = tk.Frame(inner, bg=CARD)
        instr_frame.pack(fill="x", pady=(16, 0))
        tk.Label(instr_frame, text="Custom instruction (used when Style = Custom)",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")
        instr_var = tk.StringVar(value=voice.get("cleanup_instruction", ""))
        ttk.Entry(instr_frame, textvariable=instr_var, width=60).pack(anchor="w", pady=(4, 0))

        card.update(name=name_var, style=style_var, engine=engine_var, output=output_var,
                    auto_enter=autoenter_var, ai_cleanup=cleanup_var, instruction=instr_var)
        cards.append(card)

    for v in (cfg.voices or []):
        if isinstance(v, dict):
            add_card(v)
    if not cfg.voices:
        add_card()

    def save():
        out = []
        for card in cards:
            name = card["name"].get().strip()
            if not name:
                continue
            style = _value_for(card["style"].get(), STYLES)
            ae_key = _value_for(card["auto_enter"].get(), AUTO)   # "leave"/"yes"/"no"
            auto_enter = None if ae_key == "leave" else (ae_key == "yes")
            ac_key = _value_for(card["ai_cleanup"].get(), CLEANUP)  # "leave"/"on"/"off"
            ai_cleanup = None if ac_key == "leave" else (ac_key == "on")
            out.append({
                "name": name,
                "cleanup_style": style,
                "cleanup_instruction": card["instruction"].get().strip(),
                "engine": _value_for(card["engine"].get(), ENGINES),
                "auto_enter": auto_enter,
                "output_mode": _value_for(card["output"].get(), OUTPUTS),
                "ai_cleanup": ai_cleanup,
            })
        # Reload first so we only change `voices`, not other settings the user may
        # have edited in the Settings window meanwhile.
        fresh = config.Config.load()
        fresh.voices = out
        fresh.save()
        root.destroy()

    ttk.Button(footer, text="+ Add voice", command=lambda: add_card()).pack(side="left")
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
