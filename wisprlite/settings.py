"""Standalone settings window (its own process, its own Tk root).

Launched via `python -m wisprlite --settings` (or `WisprLite.exe --settings`).
Editing config.json here; the running app watches the file and live-reloads.
Kept in a separate process on purpose: the main app already owns a Tk root for
the overlay, and two Tk roots in one process across threads is asking for
trouble.
"""

from __future__ import annotations

import threading

from . import autostart, config

ENGINES = [("openai", "OpenAI Whisper  (cloud)"),
           ("deepgram", "Deepgram  (streaming)"),
           ("local", "Local Whisper  (offline)")]
MODES = [("ptt", "Push-to-talk (hold)"), ("toggle", "Toggle (tap on/off)")]
OUTPUTS = [("type", "Type keystrokes"), ("paste", "Clipboard + Ctrl+V")]
LOCAL_SIZES = ["tiny.en", "base.en", "small.en", "medium.en",
               "tiny", "base", "small", "medium", "large-v3"]

BG = "#13151d"
CARD = "#1b1e29"
FG = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#34d399"


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


def main() -> None:
    import tkinter as tk
    from tkinter import ttk

    cfg = config.Config.load()
    root = tk.Tk()
    root.title("WisprLite settings")
    root.configure(bg=BG)
    root.resizable(False, False)
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
    style.configure("Accent.TButton", background=ACCENT, foreground="#06281c",
                    font=("Segoe UI", 9, "bold"), padding=7)
    style.map("Accent.TButton", background=[("active", "#2bb588")])
    style.configure("TCheckbutton", background=BG, foreground=FG)
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=FG)
    style.configure("TEntry", fieldbackground=CARD, foreground=FG)

    pad = dict(padx=14, pady=5, sticky="w")
    frm = ttk.Frame(root, padding=18)
    frm.grid(sticky="nsew")
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
    lang_var = tk.StringVar(value=cfg.language)
    devices = _input_devices()
    dev_label = next((lbl for lbl, val in devices if val == cfg.device), devices[0][0])
    device_var = tk.StringVar(value=dev_label)
    oai_var = tk.StringVar(value=cfg.openai_model)
    dg_var = tk.StringVar(value=cfg.deepgram_model)
    local_var = tk.StringVar(value=cfg.local_model_size)
    overlay_var = tk.BooleanVar(value=cfg.overlay)
    sounds_var = tk.BooleanVar(value=cfg.sounds)
    autostart_var = tk.BooleanVar(value=autostart.is_enabled())

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

    # --- Audio ---
    header("Audio")
    label("Microphone"); combo(device_var, [lbl for lbl, _ in devices], width=34); row += 1
    label("Language", "blank = auto-detect"); entry(lang_var, width=12); row += 1

    # --- Models ---
    header("Models")
    label("OpenAI model"); entry(oai_var); row += 1
    label("Deepgram model"); entry(dg_var); row += 1
    label("Local model size"); combo(local_var, LOCAL_SIZES); row += 1

    # --- Toggles ---
    header("Behaviour")
    ttk.Checkbutton(frm, text="Show live overlay", variable=overlay_var).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=14, pady=3); row += 1
    ttk.Checkbutton(frm, text="Play start/stop sounds", variable=sounds_var).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=14, pady=3); row += 1
    ttk.Checkbutton(frm, text="Start on Windows login", variable=autostart_var).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=14, pady=3); row += 1

    # --- Buttons ---
    status = ttk.Label(frm, text="", style="Muted.TLabel")
    status.grid(row=row, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 0)); row += 1

    def value_for(var, table):
        label_to_value = {l: k for k, l in table}
        return label_to_value.get(var.get(), table[0][0])

    def save(close=True):
        cfg.engine = value_for(engine_var, ENGINES)
        cfg.mode = value_for(mode_var, MODES)
        cfg.output_mode = value_for(output_var, OUTPUTS)
        cfg.hotkey = hotkey_var.get().strip() or "right ctrl"
        cfg.language = lang_var.get().strip()
        cfg.device = dict((lbl, val) for lbl, val in devices).get(device_var.get(), "")
        cfg.openai_model = oai_var.get().strip() or "whisper-1"
        cfg.deepgram_model = dg_var.get().strip() or "nova-2"
        cfg.local_model_size = local_var.get().strip() or "base.en"
        cfg.overlay = bool(overlay_var.get())
        cfg.sounds = bool(sounds_var.get())
        cfg.save()
        try:
            if autostart_var.get():
                autostart.enable()
            else:
                autostart.disable()
        except Exception:
            pass
        if close:
            root.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=3, sticky="e", padx=14, pady=(14, 4))
    ttk.Button(btns, text="Cancel", command=root.destroy).grid(row=0, column=0, padx=6)
    ttk.Button(btns, text="Save", style="Accent.TButton", command=save).grid(row=0, column=1)

    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")
    root.mainloop()


if __name__ == "__main__":
    main()
