"""Standalone settings window (its own process, its own Tk root).

Launched via `python -m wisprlite --settings` (or `Pipevoice.exe --settings`).
Editing config.json here; the running app watches the file and live-reloads.
Kept in a separate process on purpose: the main app already owns a Tk root for
the overlay, and two Tk roots in one process across threads is asking for
trouble.
"""

from __future__ import annotations

import threading

from . import autostart, cleanup, config

ENGINES = [("deepgram", "Deepgram — fastest, live"),
           ("openai", "OpenAI Whisper — accurate, slight wait"),
           ("local", "Local Whisper — private & free, slower")]
MODES = [("ptt", "Push-to-talk (hold)"), ("toggle", "Toggle (tap on/off)")]
OUTPUTS = [("type", "Type keystrokes"), ("paste", "Clipboard + Ctrl+V")]
PASTE_SPEEDS = [("fast", "Fast"), ("normal", "Normal"), ("slow", "Slow")]
CLEANUP_PROVIDERS = [("openai", "OpenAI"), ("gemini", "Google Gemini (free tier)"),
                     ("openrouter", "OpenRouter (free models)"), ("ollama", "Local — Ollama (offline)")]
LOCAL_SIZES = ["tiny.en", "base.en", "small.en", "medium.en",
               "tiny", "base", "small", "medium", "large-v3"]
LANGUAGES = [
    ("", "Auto-detect"),
    ("en-US", "English — US"),
    ("en-GB", "English — UK / British"),
    ("en-AU", "English — Australian"),
    ("en-IN", "English — Indian"),
    ("en-NZ", "English — New Zealand"),
    ("es", "Spanish"), ("fr", "French"), ("de", "German"),
    ("pt", "Portuguese"), ("it", "Italian"), ("nl", "Dutch"),
    ("ja", "Japanese"), ("zh", "Chinese"),
]

BG = "#13151d"
CARD = "#1b1e29"
FG = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#e06c75"


def _input_devices():
    """Return [(label, value)] for the device picker; never raises."""
    items = [("System default", "")]
    try:
        import sounddevice as sd

        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                items.append((f"[{i}] {d['name']}", str(i)))
    except Exception:
        pass
    return items


GOOD = "#98c379"
WARN = "#e5c07b"
_URLS = {
    "deepgram": "https://console.deepgram.com/",
    "openai": "https://platform.openai.com/api-keys",
    "gemini": "https://aistudio.google.com/apikey",
    "openrouter": "https://openrouter.ai/keys",
    "ollama": "https://ollama.com/download",
    "github": "https://github.com/Powleads/PipeVoice",
}


def _build_guide(parent, wheel) -> None:
    """Populate the Guide tab: how it works, engine speed, polish, tips."""
    import tkinter as tk
    import webbrowser
    from tkinter import ttk

    gc = tk.Canvas(parent, bg=BG, highlightthickness=0)
    gb = ttk.Scrollbar(parent, orient="vertical", command=gc.yview)
    gc.configure(yscrollcommand=gb.set)
    gb.pack(side="right", fill="y")
    gc.pack(side="left", fill="both", expand=True)
    g = tk.Frame(gc, bg=BG)
    gc.create_window((0, 0), window=g, anchor="nw")
    g.bind("<Configure>", lambda e: gc.configure(scrollregion=gc.bbox("all")))
    wheel(gc)

    def head(t, top=16):
        tk.Label(g, text=t, bg=BG, fg=ACCENT, font=("Segoe UI", 10, "bold"),
                 anchor="w", justify="left").pack(fill="x", padx=22, pady=(top, 5))

    def body(t):
        tk.Label(g, text=t, bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w",
                 justify="left", wraplength=470).pack(fill="x", padx=22, pady=(0, 2))

    def item(name, t, badge=None, badge_color=GOOD):
        row = tk.Frame(g, bg=BG)
        row.pack(fill="x", padx=22, pady=(7, 0))
        tk.Label(row, text=name, bg=BG, fg=FG,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        if badge:
            tk.Label(row, text=f" {badge} ", bg=badge_color, fg="#10131a",
                     font=("Segoe UI", 7, "bold")).pack(side="left", padx=(8, 0))
        tk.Label(g, text=t, bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w",
                 justify="left", wraplength=470).pack(fill="x", padx=22)

    def link(text, key):
        lk = tk.Label(g, text=text, bg=BG, fg=ACCENT, cursor="hand2",
                      font=("Segoe UI", 9, "underline"), anchor="w")
        lk.pack(anchor="w", padx=22, pady=(3, 0))
        lk.bind("<Button-1>", lambda e: webbrowser.open(_URLS[key]))

    head("How it works", top=14)
    body("Hold your hotkey, talk, then release — your words type in wherever the cursor is: "
         "editor, browser, terminal, anywhere. Default hotkey is Ctrl + \\.")
    body("The second (clipboard) hotkey copies what you say instead of typing it — handy for "
         "pasting feedback into another window.")

    head("Pick your engine — speed lives here")
    body("Transcription is the slow part; polish is fast. The engine you choose is the single "
         "biggest factor in how snappy Pipevoice feels.")
    item("Deepgram", "Streams text as you talk, so it feels instant. Best for long dictation. "
         "Free to sign up, costs pennies a day.", badge="FASTEST · LIVE", badge_color=GOOD)
    item("OpenAI Whisper", "The most accurate option, but it transcribes after you release, so "
         "expect a short few-second wait on longer clips.", badge="MOST ACCURATE", badge_color=WARN)
    item("Local Whisper", "Runs entirely on your PC — nothing leaves the machine, no key needed. "
         "It is the slowest, especially on bigger models. Start on base.en to test, then raise the "
         "model size to medium.en for much better accuracy if your PC can handle it.",
         badge="PRIVATE · FREE", badge_color=MUTED)
    body("Rule of thumb: want it fast? Use Deepgram. Want fully private and free? Use Local Whisper "
         "and bump the model size.")
    link("Get a free Deepgram key  ↗", "deepgram")
    link("Get an OpenAI key  ↗", "openai")

    head("Polish (Flow mode) — optional")
    body("Cleans up filler words, punctuation and casing after transcription. It is fast — the wait "
         "you feel is transcription, not polish. Turn it on under Transcription.")
    item("Google Gemini", "Free tier, and most people already have a Google account. The easiest "
         "free option if you don't have OpenAI credit.", badge="FREE · EASIEST", badge_color=GOOD)
    item("OpenAI", "Uses your OpenAI key — same one as the transcription engine.")
    item("OpenRouter", "Free community models via a single key.")
    item("Ollama", "For 100% private polish, install Ollama and pull a small model "
         "(e.g. llama3.2). Nothing leaves your PC.", badge="OFFLINE", badge_color=MUTED)
    link("Get a free Gemini key  ↗", "gemini")
    link("Get an OpenRouter key  ↗", "openrouter")
    link("Install Ollama  ↗", "ollama")

    head("Make it yours")
    body("• Accent / language (under Audio): pick yours for a real accuracy boost — UK, US, Indian, "
         "Australian, or Russian-accented English, and more.")
    body("• Speech notes: describe your accent, stutter or filler habits. The AI polish uses it to "
         "fix mis-hearings tailored to how you speak.")
    body("• Vocabulary: add names and jargon so they're always spelled right.")
    body("• Word fixes: wrong=right pairs, applied last so they always win.")

    head("Need a hand?")
    link("Pipevoice on GitHub — docs, issues, source  ↗", "github")
    tk.Label(g, text="", bg=BG).pack(pady=6)  # bottom breathing room


def main(first_run: bool = False) -> None:
    import tkinter as tk
    from tkinter import ttk

    cfg = config.Config.load()
    root = tk.Tk()
    root.title("Set up Pipevoice" if first_run else "Pipevoice settings")
    root.configure(bg=BG)
    root.resizable(False, True)
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
    style.configure(".", background=BG, foreground=FG, fieldbackground=CARD,
                    bordercolor="#2a2e3d", lightcolor=CARD, darkcolor=CARD)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 8))
    style.configure("Head.TLabel", background=BG, foreground=ACCENT, font=("Segoe UI", 10, "bold"))
    style.configure("TButton", background=CARD, foreground=FG, padding=6)
    style.map("TButton", background=[("active", "#262a3a")])
    style.configure("Accent.TButton", background=ACCENT, foreground="#1a0c0d",
                    font=("Segoe UI", 9, "bold"), padding=7)
    style.map("Accent.TButton", background=[("active", "#e8838b")])
    style.configure("TCheckbutton", background=BG, foreground=FG)
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(8, 6, 0, 0))
    style.configure("TNotebook.Tab", background=CARD, foreground=MUTED,
                    padding=(18, 7), font=("Segoe UI", 9, "bold"), borderwidth=0)
    style.map("TNotebook.Tab", background=[("selected", BG)],
              foreground=[("selected", ACCENT), ("active", FG)])
    style.configure("Footer.TFrame", background=CARD)
    style.configure("TCombobox", fieldbackground=CARD, background=CARD,
                    foreground=FG, arrowcolor=FG)
    style.map("TCombobox",
              fieldbackground=[("readonly", CARD), ("disabled", CARD)],
              foreground=[("readonly", FG), ("disabled", MUTED)],
              selectbackground=[("readonly", CARD)],
              selectforeground=[("readonly", FG)],
              background=[("readonly", CARD), ("active", CARD)])
    # the dropdown popup is a plain Tk Listbox, not themed by ttk
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#1a0c0d")
    style.configure("TEntry", fieldbackground=CARD, foreground=FG, insertcolor=FG)

    pad = dict(padx=14, pady=5, sticky="w")

    def _wheel(canvas):
        # Scroll whichever canvas the pointer is over (two scroll areas exist).
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    # Fixed footer (Save/Cancel always visible), then a tabbed body: the form
    # plus a Guide tab that explains engines, speed and polish options.
    footer = ttk.Frame(root, padding=(14, 9))
    footer.pack(side="bottom", fill="x")
    nb = ttk.Notebook(root)
    nb.pack(side="top", fill="both", expand=True)
    tab_settings = ttk.Frame(nb)
    tab_guide = ttk.Frame(nb)
    nb.add(tab_settings, text="Settings")
    nb.add(tab_guide, text="Guide")

    # --- Settings tab: scrollable form ---
    _canvas = tk.Canvas(tab_settings, bg=BG, highlightthickness=0)
    _vbar = ttk.Scrollbar(tab_settings, orient="vertical", command=_canvas.yview)
    _canvas.configure(yscrollcommand=_vbar.set)
    _vbar.pack(side="right", fill="y")
    _canvas.pack(side="left", fill="both", expand=True)
    frm = ttk.Frame(_canvas, padding=18)
    _canvas.create_window((0, 0), window=frm, anchor="nw")
    frm.bind("<Configure>", lambda e: _canvas.configure(scrollregion=_canvas.bbox("all")))
    _wheel(_canvas)
    _build_guide(tab_guide, _wheel)
    row = 0

    def header(text):
        nonlocal row
        ttk.Label(frm, text=text, style="Head.TLabel").grid(row=row, column=0, columnspan=3,
                                                             sticky="w", padx=14, pady=(12, 2))
        row += 1

    def label(text, hint=None):
        nonlocal row
        ttk.Label(frm, text=text).grid(row=row, column=0, **pad)
        if hint:
            ttk.Label(frm, text=hint, style="Muted.TLabel").grid(row=row, column=2, **pad)

    # --- values ---
    engine_var = tk.StringVar(value=dict(ENGINES).get(cfg.engine, ENGINES[0][1]))
    mode_var = tk.StringVar(value=dict(MODES).get(cfg.mode, MODES[0][1]))
    output_var = tk.StringVar(value=dict(OUTPUTS).get(cfg.output_mode, OUTPUTS[0][1]))
    hotkey_var = tk.StringVar(value=cfg.hotkey)
    clip_hotkey_var = tk.StringVar(value=cfg.clipboard_hotkey)
    lang_var = tk.StringVar(value=dict(LANGUAGES).get(cfg.language, LANGUAGES[0][1]))
    devices = _input_devices()
    dev_label = next((lbl for lbl, val in devices if val == cfg.device), devices[0][0])
    device_var = tk.StringVar(value=dev_label)
    oai_var = tk.StringVar(value=cfg.openai_model)
    dg_var = tk.StringVar(value=cfg.deepgram_model)
    local_var = tk.StringVar(value=cfg.local_model_size)
    oai_key_var = tk.StringVar()
    dg_key_var = tk.StringVar()
    gem_key_var = tk.StringVar()
    or_key_var = tk.StringVar()
    ai_cleanup_var = tk.BooleanVar(value=cfg.ai_cleanup)
    cleanup_var = tk.StringVar(value=dict(CLEANUP_PROVIDERS).get(cfg.cleanup_provider, CLEANUP_PROVIDERS[0][1]))
    cleanup_model_var = tk.StringVar(value=cfg.cleanup_model)
    auto_enter_var = tk.BooleanVar(value=cfg.auto_enter)
    min_seconds_var = tk.StringVar(value=str(cfg.min_seconds))
    dg_timeout_var = tk.StringVar(value=str(cfg.deepgram_finish_timeout))
    paste_speed_var = tk.StringVar(value=dict(PASTE_SPEEDS).get(cfg.paste_speed, PASTE_SPEEDS[1][1]))
    fixes_var = tk.StringVar(value=", ".join(f"{k}={v}" for k, v in cfg.replacements.items()))
    speech_notes_var = tk.StringVar(value=cfg.speech_notes)
    overlay_var = tk.BooleanVar(value=cfg.overlay)
    sounds_var = tk.BooleanVar(value=cfg.sounds)
    autostart_var = tk.BooleanVar(value=autostart.is_enabled())
    auto_update_var = tk.BooleanVar(value=cfg.auto_update)
    voice_commands_var = tk.BooleanVar(value=cfg.voice_commands)
    history_var = tk.BooleanVar(value=cfg.history_enabled)

    def combo(var, options, width=26):
        c = ttk.Combobox(frm, textvariable=var, values=options, state="readonly", width=width)
        c.grid(row=row, column=1, padx=6, pady=5, sticky="w")
        return c

    def entry(var, width=29):
        e = ttk.Entry(frm, textvariable=var, width=width)
        e.grid(row=row, column=1, padx=6, pady=5, sticky="w")
        return e

    # --- General ---
    header("General")
    label("Engine"); combo(engine_var, [l for _, l in ENGINES]); row += 1
    ttk.Label(frm, text="Deepgram is fastest (live). Local & OpenAI add a short wait — see the Guide tab.",
              style="Muted.TLabel").grid(row=row, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 2)); row += 1
    label("Mode"); combo(mode_var, [l for _, l in MODES]); row += 1
    label("Output"); combo(output_var, [l for _, l in OUTPUTS]); row += 1

    # --- Hotkey ---
    header("Hotkey")
    label("Push-to-talk key", "e.g. right ctrl, ctrl+alt, f9")
    entry(hotkey_var, width=20)
    cap_btn = ttk.Button(frm, text="Capture")
    cap_btn.grid(row=row, column=1, padx=(190, 0), pady=5, sticky="w")

    def capture():
        cap_btn.config(text="Press keys…")

        def work():
            hk = None
            try:
                import keyboard
                hk = keyboard.read_hotkey(suppress=False)
            except Exception:
                hk = None

            def done():
                if hk:
                    hotkey_var.set(hk)
                cap_btn.config(text="Capture")
            root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    cap_btn.config(command=capture)
    row += 1
    label("Clipboard hotkey", "hold to dictate to the clipboard"); entry(clip_hotkey_var, width=20)
    clip_cap_btn = ttk.Button(frm, text="Capture")
    clip_cap_btn.grid(row=row, column=1, padx=(190, 0), pady=5, sticky="w")

    def clip_capture():
        clip_cap_btn.config(text="Press keys…")

        def work():
            hk = None
            try:
                import keyboard
                hk = keyboard.read_hotkey(suppress=False)
            except Exception:
                hk = None

            def done():
                if hk:
                    clip_hotkey_var.set(hk)
                clip_cap_btn.config(text="Capture")
            root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    clip_cap_btn.config(command=clip_capture)
    row += 1

    # --- Audio ---
    header("Audio")
    label("Microphone"); combo(device_var, [lbl for lbl, _ in devices], width=34); row += 1
    label("Accent / language", "pick yours for best accuracy"); combo(lang_var, [l for _, l in LANGUAGES], width=24); row += 1

    # --- Models ---
    header("Models")
    label("OpenAI model"); entry(oai_var); row += 1
    label("Deepgram model"); entry(dg_var); row += 1
    label("Local model size"); combo(local_var, LOCAL_SIZES); row += 1

    # --- API keys ---
    header("API keys")
    label("OpenAI key", "saved" if config.openai_key() else "not set")
    e_oai = ttk.Entry(frm, textvariable=oai_key_var, width=29, show="•")
    e_oai.grid(row=row, column=1, padx=6, pady=5, sticky="w"); row += 1
    label("Deepgram key", "saved" if config.deepgram_key() else "not set")
    e_dg = ttk.Entry(frm, textvariable=dg_key_var, width=29, show="•")
    e_dg.grid(row=row, column=1, padx=6, pady=5, sticky="w"); row += 1
    label("Gemini key", "saved" if config.gemini_key() else "not set")
    ttk.Entry(frm, textvariable=gem_key_var, width=29, show="•").grid(row=row, column=1, padx=6, pady=5, sticky="w"); row += 1
    label("OpenRouter key", "saved" if config.openrouter_key() else "not set")
    ttk.Entry(frm, textvariable=or_key_var, width=29, show="•").grid(row=row, column=1, padx=6, pady=5, sticky="w"); row += 1
    ttk.Label(frm, text="Leave a key blank to keep the current one.",
              style="Muted.TLabel").grid(row=row, column=0, columnspan=3,
                                          sticky="w", padx=14); row += 1

    # --- Transcription ---
    header("Transcription")
    ttk.Checkbutton(frm, text="Polish with AI (Flow mode — tidies fillers & punctuation)",
                    variable=ai_cleanup_var).grid(row=row, column=0, columnspan=3,
                                                  sticky="w", padx=14, pady=3); row += 1
    label("Cleanup with"); combo(cleanup_var, [l for _, l in CLEANUP_PROVIDERS], width=24); row += 1
    label("Cleanup model", "blank = provider default"); entry(cleanup_model_var); row += 1

    def _on_cleanup_provider(*_):
        prov = value_for(cleanup_var, CLEANUP_PROVIDERS)
        cleanup_model_var.set(cleanup.PROVIDERS.get(prov, cleanup.PROVIDERS["openai"])[2])
    cleanup_var.trace_add("write", _on_cleanup_provider)
    ttk.Checkbutton(frm, text="Press Enter after typing (auto-send)",
                    variable=auto_enter_var).grid(row=row, column=0, columnspan=3,
                                                  sticky="w", padx=14, pady=3); row += 1
    ttk.Checkbutton(frm, text="Spoken commands (\"new line\", \"scratch that\", \"send it\")",
                    variable=voice_commands_var).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", padx=14, pady=3); row += 1
    label("Vocabulary", "names & jargon — better recognition"); row += 1
    vocab_box = tk.Frame(frm, bg=BG)
    vocab_box.grid(row=row, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 6))
    vocab_list = tk.Listbox(vocab_box, height=4, width=30, bg=CARD, fg=FG,
                            selectbackground=ACCENT, selectforeground="#1a0c0d",
                            highlightthickness=1, highlightbackground="#2a2e3d",
                            relief="flat", activestyle="none", exportselection=False,
                            font=("Segoe UI", 9))
    vocab_list.grid(row=0, column=0, rowspan=2, sticky="w")
    for _t in [t.strip() for t in (cfg.vocabulary or "").split(",") if t.strip()]:
        vocab_list.insert("end", _t)
    vocab_add_var = tk.StringVar()
    _vadd = ttk.Entry(vocab_box, textvariable=vocab_add_var, width=20)
    _vadd.grid(row=0, column=1, padx=(8, 0), sticky="nw")

    def _vocab_add(*_a):
        t = vocab_add_var.get().strip().strip(",")
        if t and t not in vocab_list.get(0, "end"):
            vocab_list.insert("end", t)
        vocab_add_var.set("")

    def _vocab_remove():
        for i in reversed(vocab_list.curselection()):
            vocab_list.delete(i)

    _vadd.bind("<Return>", _vocab_add)
    ttk.Button(vocab_box, text="Add", command=_vocab_add, width=7).grid(row=0, column=2, padx=(6, 0), sticky="nw")
    ttk.Button(vocab_box, text="Remove", command=_vocab_remove, width=7).grid(row=1, column=1, padx=(8, 0), pady=(4, 0), sticky="nw")
    row += 1
    label("Word fixes", "wrong=right, comma-sep"); entry(fixes_var); row += 1
    label("Speech notes", "accent / stutter / fillers — guides AI cleanup"); entry(speech_notes_var); row += 1

    # --- Toggles ---
    header("Behaviour")
    ttk.Checkbutton(frm, text="Show live overlay", variable=overlay_var).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=14, pady=3); row += 1
    ttk.Checkbutton(frm, text="Play start/stop sounds", variable=sounds_var).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=14, pady=3); row += 1
    ttk.Checkbutton(frm, text="Start on Windows login", variable=autostart_var).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=14, pady=3); row += 1
    ttk.Checkbutton(frm, text="Automatic updates (check on startup)", variable=auto_update_var).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=14, pady=3); row += 1
    ttk.Checkbutton(frm, text="Keep a local dictation history", variable=history_var).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=14, pady=3); row += 1

    # --- Advanced ---
    header("Advanced")
    ttk.Label(frm, text="Most people never need these.",
              style="Muted.TLabel").grid(row=row, column=0, columnspan=3, sticky="w", padx=14); row += 1
    label("Min seconds", "ignore taps shorter than this"); entry(min_seconds_var, width=8); row += 1
    label("Deepgram wait", "seconds to wait for final words"); entry(dg_timeout_var, width=8); row += 1
    label("Paste speed", "slower is more reliable in some apps"); combo(paste_speed_var, [l for _, l in PASTE_SPEEDS], width=12); row += 1

    # --- Save / Cancel (live in the fixed footer) ---
    def value_for(var, table):
        label_to_value = {l: k for k, l in table}
        return label_to_value.get(var.get(), table[0][0])

    def save(close=True):
        cfg.engine = value_for(engine_var, ENGINES)
        cfg.mode = value_for(mode_var, MODES)
        cfg.output_mode = value_for(output_var, OUTPUTS)
        cfg.hotkey = hotkey_var.get().strip() or "right ctrl"
        cfg.clipboard_hotkey = clip_hotkey_var.get().strip()
        cfg.language = value_for(lang_var, LANGUAGES)
        cfg.device = dict((lbl, val) for lbl, val in devices).get(device_var.get(), "")
        cfg.openai_model = oai_var.get().strip() or "whisper-1"
        cfg.deepgram_model = dg_var.get().strip() or "nova-2"
        cfg.local_model_size = local_var.get().strip() or "base.en"
        cfg.overlay = bool(overlay_var.get())
        cfg.sounds = bool(sounds_var.get())
        cfg.auto_update = bool(auto_update_var.get())
        cfg.voice_commands = bool(voice_commands_var.get())
        cfg.history_enabled = bool(history_var.get())
        cfg.ai_cleanup = bool(ai_cleanup_var.get())
        cfg.cleanup_provider = value_for(cleanup_var, CLEANUP_PROVIDERS)
        cfg.cleanup_model = cleanup_model_var.get().strip()
        cfg.auto_enter = bool(auto_enter_var.get())
        cfg.vocabulary = ", ".join(vocab_list.get(0, "end"))
        try:
            cfg.min_seconds = max(0.05, min(2.0, float(min_seconds_var.get())))
        except ValueError:
            pass
        try:
            cfg.deepgram_finish_timeout = max(1.0, min(30.0, float(dg_timeout_var.get())))
        except ValueError:
            pass
        cfg.paste_speed = value_for(paste_speed_var, PASTE_SPEEDS)
        cfg.speech_notes = speech_notes_var.get().strip()
        fixes = {}
        for part in fixes_var.get().split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                k = k.strip()
                if k:
                    fixes[k] = v.strip()
        cfg.replacements = fixes
        cfg.save()
        if oai_key_var.get().strip():
            config.save_api_key("OPENAI_API_KEY", oai_key_var.get())
        if dg_key_var.get().strip():
            config.save_api_key("DEEPGRAM_API_KEY", dg_key_var.get())
        if gem_key_var.get().strip():
            config.save_api_key("GEMINI_API_KEY", gem_key_var.get())
        if or_key_var.get().strip():
            config.save_api_key("OPENROUTER_API_KEY", or_key_var.get())
        try:
            if autostart_var.get():
                autostart.enable()
            else:
                autostart.disable()
        except Exception:
            pass
        if close:
            root.destroy()

    ttk.Button(footer, text="Save", style="Accent.TButton", command=save).pack(side="right")
    ttk.Button(footer, text="Cancel", command=root.destroy).pack(side="right", padx=(0, 8))
    ttk.Label(footer, text="Not sure what to pick? Open the Guide tab.",
              style="Muted.TLabel").pack(side="left")

    root.update_idletasks()
    cw = frm.winfo_reqwidth() + 22          # form width + scrollbar
    ch = frm.winfo_reqheight()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    win_w = max(cw, 530)                    # also fit the Guide tab's text width
    win_h = min(ch + 96, sh - 80)           # + tab strip + footer; never off-screen
    x = max(0, (sw - win_w) // 2)
    y = max(0, (sh - win_h) // 3)
    root.geometry(f"{win_w}x{win_h}+{x}+{y}")
    root.mainloop()


if __name__ == "__main__":
    main()
