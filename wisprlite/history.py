"""Recent dictation history: a small JSONL log plus a viewer window.

The running app appends each final transcript to %APPDATA%\\Pipevoice\\history.jsonl
(newest last, capped). The viewer (``python -m wisprlite --history``) is a
separate short-lived Tk process that reads the file and lets you re-copy any
entry. JSONL is the source of truth because the viewer runs in its own process.
"""

from __future__ import annotations

import json
import time

from . import config

CAP = 200  # max lines kept on disk

BG = "#13151d"
CARD = "#1b1e29"
FG = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#e06c75"
GOOD = "#98c379"


def _path():
    return config.config_dir() / "history.jsonl"


def record(text: str, kind: str = "typed") -> None:
    """Append one entry; keep at most CAP lines. Never raises."""
    text = (text or "").strip()
    if not text:
        return
    p = _path()
    try:
        lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
        lines.append(json.dumps({"ts": time.time(), "text": text, "kind": kind}, ensure_ascii=False))
        if len(lines) > CAP:
            lines = lines[-CAP:]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def load(limit: int = 50):
    """Most recent entries, newest first. Never raises."""
    out = []
    try:
        p = _path()
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    out.reverse()
    return out[:limit]


def clear() -> None:
    try:
        _path().unlink(missing_ok=True)
    except Exception:
        pass


def _ago(ts: float) -> str:
    try:
        d = max(0, time.time() - float(ts))
    except Exception:
        return ""
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)}m ago"
    if d < 86400:
        return f"{int(d // 3600)}h ago"
    return f"{int(d // 86400)}d ago"


def main() -> None:
    """The --history viewer window."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return
    from .typer import copy_clipboard

    cfg = config.Config.load()
    entries = load(getattr(cfg, "history_size", 50) or 50)

    root = tk.Tk()
    root.title("Pipevoice history")
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
    style.configure("TButton", background=CARD, foreground=FG, padding=5, borderwidth=0)
    style.map("TButton", background=[("active", "#262a3a")])
    style.configure("Vertical.TScrollbar", background=CARD, troughcolor=BG, borderwidth=0, arrowcolor=MUTED)

    head = tk.Frame(root, bg=BG, padx=18, pady=14)
    head.pack(fill="x")
    tk.Label(head, text="Dictation history", bg=BG, fg=ACCENT,
             font=("Segoe UI", 14, "bold")).pack(side="left")
    tk.Label(head, text=f"  last {len(entries)}", bg=BG, fg=MUTED,
             font=("Segoe UI", 9)).pack(side="left")

    body = tk.Frame(root, bg=BG)
    body.pack(fill="both", expand=True)
    canvas = tk.Canvas(body, bg=BG, highlightthickness=0, width=520, height=440)
    vbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vbar.set)
    vbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=BG)
    canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

    def copy_row(text, btn):
        copy_clipboard(text)
        btn.config(text="Copied ✓")
        root.after(1100, lambda: btn.config(text="Copy"))

    if not entries:
        tk.Label(inner, text="Nothing dictated yet.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10), padx=20, pady=24).pack(anchor="w")
    for e in entries:
        card = tk.Frame(inner, bg=CARD, padx=14, pady=11)
        card.pack(fill="x", padx=16, pady=5)
        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x")
        kind = e.get("kind", "typed")
        tk.Label(top, text=("◉ clipboard" if kind == "clipboard" else "◉ typed"),
                 bg=CARD, fg=(GOOD if kind == "clipboard" else MUTED),
                 font=("Consolas", 8)).pack(side="left")
        tk.Label(top, text=_ago(e.get("ts", 0)), bg=CARD, fg=MUTED,
                 font=("Consolas", 8)).pack(side="left", padx=(10, 0))
        btn = ttk.Button(top, text="Copy")
        btn.pack(side="right")
        btn.config(command=lambda t=e.get("text", ""), b=btn: copy_row(t, b))
        tk.Label(card, text=e.get("text", ""), bg=CARD, fg=FG, font=("Segoe UI", 10),
                 anchor="w", justify="left", wraplength=460).pack(fill="x", pady=(6, 0))

    foot = tk.Frame(root, bg=BG, padx=18, pady=12)
    foot.pack(fill="x")

    def do_clear():
        clear()
        for w in inner.winfo_children():
            w.destroy()
        tk.Label(inner, text="History cleared.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10), padx=20, pady=24).pack(anchor="w")

    tk.Button(foot, text="Clear history", command=do_clear, bg=CARD, fg=MUTED,
              activebackground="#262a3a", activeforeground=FG, relief="flat",
              padx=12, pady=6, font=("Segoe UI", 9)).pack(side="left")
    tk.Button(foot, text="Close", command=root.destroy, bg=ACCENT, fg="#1a0c0d",
              activebackground="#e8838b", relief="flat", padx=18, pady=6,
              font=("Segoe UI", 9, "bold")).pack(side="right")

    root.update_idletasks()
    w = max(560, root.winfo_reqwidth())
    h = min(620, max(360, root.winfo_reqheight()))
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")
    from . import winui
    winui.dark_titlebar(root)
    root.mainloop()


if __name__ == "__main__":
    main()
