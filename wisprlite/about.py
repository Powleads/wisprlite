"""About / Updates window (python -m wisprlite --about).

Shows the current version, checks GitHub for a newer release, offers an
"Update now" button, and lists recent release notes as a changelog. Runs as a
short-lived separate Tk process (same pattern as settings/history), so the
"Update now" path just calls the proven updater.download_and_run() and lets the
Inno installer close + relaunch the app.
"""

from __future__ import annotations

import re
import threading
import webbrowser

from . import __version__, config

BG = "#13151d"
CARD = "#1b1e29"
FG = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#e06c75"
GOOD = "#98c379"
WARN = "#e5c07b"

RELEASES_URL = "https://github.com/Powleads/PipeVoice/releases"


def _clean_notes(body: str) -> str:
    """Tidy GitHub's auto-generated release notes into readable lines."""
    lines = []
    for raw in (body or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.lower().startswith("**full changelog**") or s.lower().startswith("## what"):
            continue
        s = re.sub(r"^#{1,6}\s*", "", s)          # drop markdown headers
        s = re.sub(r"^[\*\-]\s*", "• ", s)         # bullets
        # strip "by @user in #123" and "by @user in https://.../pull/123"
        s = re.sub(r"\s+by @\S+ in (?:#\d+|https?://\S+)", "", s)
        s = re.sub(r"\s+in https?://\S+", "", s)
        lines.append(s)
    return "\n".join(lines).strip()


def _date(iso: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    if not m:
        return ""
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    y, mo, d = m.groups()
    return f"{int(d)} {months[int(mo)]} {y}"


def main() -> None:
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return
    from . import updater

    state = {"info": None}

    root = tk.Tk()
    root.title("About Pipevoice")
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
    style.configure("TButton", background=CARD, foreground=FG, padding=7, borderwidth=0)
    style.map("TButton", background=[("active", "#262a3a")], foreground=[("disabled", MUTED)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#1a0c0d",
                    font=("Segoe UI", 9, "bold"), padding=8, borderwidth=0)
    style.map("Accent.TButton", background=[("active", "#e8838b")])
    style.configure("Vertical.TScrollbar", background=CARD, troughcolor=BG, borderwidth=0, arrowcolor=MUTED)

    head = tk.Frame(root, bg=BG, padx=26, pady=20)
    head.pack(fill="x")
    tk.Label(head, text="Pipevoice", bg=BG, fg=ACCENT, font=("Segoe UI", 21, "bold")).pack(anchor="w")
    tk.Label(head, text=f"Version {__version__}", bg=BG, fg=MUTED,
             font=("Consolas", 10)).pack(anchor="w", pady=(1, 12))

    status = tk.Label(head, text="Checking for updates…", bg=BG, fg=MUTED, font=("Segoe UI", 10))
    status.pack(anchor="w")
    btn = ttk.Button(head, text="Checking…", state="disabled", style="Accent.TButton")
    btn.pack(anchor="w", pady=(10, 0))

    tk.Label(root, text="WHAT'S NEW", bg=BG, fg=ACCENT,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=26, pady=(16, 4))

    body = tk.Frame(root, bg=BG)
    body.pack(fill="both", expand=True)
    canvas = tk.Canvas(body, bg=BG, highlightthickness=0, width=480, height=300)
    vbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vbar.set)
    vbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=BG)
    canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

    foot = tk.Frame(root, bg=BG, padx=26, pady=12)
    foot.pack(fill="x")
    link = tk.Label(foot, text="All releases on GitHub ↗", bg=BG, fg=ACCENT, cursor="hand2",
                    font=("Segoe UI", 9, "underline"))
    link.pack(side="left")
    link.bind("<Button-1>", lambda e: webbrowser.open(RELEASES_URL))
    tk.Button(foot, text="Close", command=root.destroy, bg=CARD, fg=FG, relief="flat",
              activebackground="#262a3a", activeforeground=FG, padx=16, pady=6,
              font=("Segoe UI", 9)).pack(side="right")

    # ---- update flow ----
    def do_update():
        btn.config(state="disabled", text="Downloading…")
        status.config(text="Downloading the update…", fg=MUTED)

        def work():
            ok = bool(state["info"]) and updater.download_and_run(state["info"])

            def done():
                if ok:
                    status.config(text="Installing… Pipevoice will restart in a moment.", fg=GOOD)
                    btn.config(text="Restarting…")
                else:
                    status.config(text="Update failed. Check your connection and try again.", fg=WARN)
                    btn.config(state="normal", text="Try again", command=do_update)
            root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def check():
        status.config(text="Checking for updates…", fg=MUTED)
        btn.config(state="disabled", text="Checking…")

        def work():
            rel = updater.latest_release()
            info = updater.info_from_latest(rel) if rel and rel.get("newer") else None

            def done():
                if rel is None:
                    status.config(text="Could not reach GitHub. Check your connection.", fg=WARN)
                    btn.config(state="normal", text="Check again", command=check, style="TButton")
                elif rel.get("newer") and info:
                    state["info"] = info
                    status.config(text=f"Update available: v{rel['version']}", fg=ACCENT)
                    btn.config(state="normal", text="Update now  →", command=do_update, style="Accent.TButton")
                else:
                    status.config(text="You're on the latest version.", fg=GOOD)
                    btn.config(state="normal", text="Check again", command=check, style="TButton")
            root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def render_changelog(rels):
        for w in inner.winfo_children():
            w.destroy()
        if not rels:
            tk.Label(inner, text="Could not load release notes.", bg=BG, fg=MUTED,
                     font=("Segoe UI", 10), padx=26, pady=10).pack(anchor="w")
            return
        for rel in rels:
            card = tk.Frame(inner, bg=CARD, padx=14, pady=11)
            card.pack(fill="x", padx=22, pady=5)
            top = tk.Frame(card, bg=CARD)
            top.pack(fill="x")
            tag = rel.get("tag", "")
            is_current = tag.lstrip("vV") == __version__
            tk.Label(top, text=tag, bg=CARD, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left")
            if is_current:
                tk.Label(top, text=" current ", bg=ACCENT, fg="#1a0c0d",
                         font=("Segoe UI", 7, "bold")).pack(side="left", padx=(8, 0))
            dt = _date(rel.get("published_at", ""))
            if dt:
                tk.Label(top, text=dt, bg=CARD, fg=MUTED, font=("Consolas", 8)).pack(side="right")
            notes = _clean_notes(rel.get("body", "")) or "No notes for this release."
            tk.Label(card, text=notes, bg=CARD, fg=MUTED, font=("Segoe UI", 9),
                     anchor="w", justify="left", wraplength=430).pack(fill="x", pady=(6, 0))

    def load_changelog():
        def work():
            rels = updater.recent_releases(6)
            root.after(0, lambda: render_changelog(rels))
        threading.Thread(target=work, daemon=True).start()

    tk.Label(inner, text="Loading release notes…", bg=BG, fg=MUTED,
             font=("Segoe UI", 10), padx=26, pady=10).pack(anchor="w")
    check()
    load_changelog()

    root.update_idletasks()
    w = max(540, root.winfo_reqwidth())
    h = min(640, max(420, root.winfo_reqheight()))
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")
    root.mainloop()


if __name__ == "__main__":
    main()
