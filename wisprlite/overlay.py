"""The Wispr-style HUD: a small frameless pill near the bottom of the screen.

Shows a pulsing status dot, a live mic VU meter while listening, and the live
(streaming) transcript as it comes in. Runs its own tkinter mainloop on a
dedicated thread; the app talks to it through a thread-safe queue. If tkinter
is unavailable it silently becomes a no-op.
"""

from __future__ import annotations

import math
import queue
import threading
import time
from typing import Callable, Optional

FRAME_MS = 33          # ~30 fps
METER_N = 16           # number of VU bars
METER_BW = 4           # bar width
METER_GAP = 3          # gap between bars
WIN_W, WIN_H = 380, 68
TRANSPARENT = "#010203"  # color key punched out to give rounded corners

ACCENT = {
    "listening": "#e06c75",
    "transcribing": "#fbbf24",
    "error": "#f87171",
    "done": "#60a5fa",
    "idle": "#64748b",
    "picker": "#a78bfa",
}


class Overlay:
    def __init__(
        self,
        level_provider: Optional[Callable[[], float]] = None,
        enabled: bool = True,
    ) -> None:
        self.level_provider = level_provider or (lambda: 0.0)
        self.enabled = enabled
        self._q: "queue.Queue[tuple]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._started = False

    # ---- public, thread-safe API -----------------------------------------
    def start(self) -> None:
        if not self.enabled or self._started:
            return
        self._started = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def show(self, state: str, text: str = "") -> None:
        self._q.put(("show", state, text))

    def set_state(self, state: str, text: Optional[str] = None) -> None:
        self._q.put(("state", state, text))

    def set_text(self, text: str) -> None:
        self._q.put(("text", None, text))

    def hide(self) -> None:
        self._q.put(("hide", None, ""))

    def stop(self) -> None:
        self._q.put(("quit", None, ""))

    def show_picker(self, items: list, title: str = "Pick a voice") -> None:
        self._q.put(("picker", title, list(items or [])))

    # ---- tkinter thread ---------------------------------------------------
    def _run(self) -> None:
        try:
            import tkinter as tk
        except Exception:
            return

        root = tk.Tk()
        root.overrideredirect(True)
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        bg = TRANSPARENT
        try:
            root.configure(bg=bg)
            root.attributes("-transparentcolor", bg)  # Windows: rounded pill
        except Exception:
            bg = "#13151d"
            root.configure(bg=bg)
        try:
            root.attributes("-alpha", 0.96)
        except Exception:
            pass

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        x = 24                       # bottom-left corner, out of the way
        y = sh - WIN_H - 60
        root.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        canvas = tk.Canvas(root, width=WIN_W, height=WIN_H, bg=bg, highlightthickness=0)
        canvas.pack()
        root.withdraw()

        st = {
            "name": "idle",
            "text": "",
            "phase": 0.0,
            "hist": [0.0] * METER_N,
            "visible": False,
            "hide_at": 0.0,
            "picker_title": "",
            "picker_items": [],
        }

        def reveal():
            st["visible"] = True
            try:
                root.deiconify()
                root.lift()
                root.attributes("-topmost", True)
            except Exception:
                pass

        def conceal():
            st["visible"] = False
            st["hide_at"] = 0.0
            try:
                root.withdraw()
            except Exception:
                pass

        def drain() -> bool:
            try:
                while True:
                    kind, state, text = self._q.get_nowait()
                    if kind == "quit":
                        root.quit()
                        return False
                    if kind == "hide":
                        st["name"] = "idle"
                        conceal()
                    elif kind == "show":
                        st["name"] = state or "listening"
                        st["text"] = text or ""
                        st["hide_at"] = 0.0
                        reveal()
                    elif kind == "state":
                        if state:
                            st["name"] = state
                        if text is not None:
                            st["text"] = text
                        reveal()
                        if state in ("done", "error"):
                            st["hide_at"] = time.time() + (2.2 if state == "error" else 1.4)
                    elif kind == "text":
                        st["text"] = text or ""
                        reveal()
                    elif kind == "picker":
                        st["name"] = "picker"
                        st["picker_title"] = state or "Pick a voice"
                        st["picker_items"] = text if isinstance(text, list) else []
                        st["hide_at"] = 0.0
                        reveal()
            except queue.Empty:
                pass
            return True

        def tick():
            if not drain():
                return
            if st["hide_at"] and time.time() >= st["hide_at"]:
                conceal()
            if st["visible"]:
                self._draw(canvas, st)
            root.after(FRAME_MS, tick)

        root.after(FRAME_MS, tick)
        try:
            root.mainloop()
        except Exception:
            pass

    # ---- drawing ----------------------------------------------------------
    def _draw(self, c, st) -> None:
        c.delete("all")
        accent = ACCENT.get(st["name"], ACCENT["idle"])
        self._round_rect(c, 3, 3, WIN_W - 3, WIN_H - 3, 24, fill="#13151d", outline=accent, width=2)

        if st["name"] == "picker":
            title = st["picker_title"] or "Pick a voice"
            items = st["picker_items"][:6]
            line = "  ".join(f"{i + 1} {name}" for i, name in enumerate(items))
            line = self._fit(line, WIN_W - 20)
            title_y = WIN_H // 2 - 12
            items_y = WIN_H // 2 + 8
            c.create_text(WIN_W // 2, title_y, text=title, anchor="center",
                          fill=accent, font=("Segoe UI", 8, "bold"))
            c.create_text(WIN_W // 2, items_y, text=line, anchor="center",
                          fill="#e5e7eb", font=("Segoe UI", 11))
            return

        st["phase"] += 0.18
        cy = WIN_H // 2
        cx = 28

        # pulsing status dot
        r = 6 + (2.4 * abs(math.sin(st["phase"])) if st["name"] == "listening" else 0)
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=accent, outline="")

        if st["name"] == "listening":
            try:
                lvl = float(self.level_provider())
            except Exception:
                lvl = 0.0
            hist = st["hist"]
            hist.pop(0)
            hist.append(lvl)
            mx = 50
            for i, v in enumerate(hist):
                bx = mx + i * (METER_BW + METER_GAP)
                bh = max(3, min(34, v * 700 + 3))
                c.create_rectangle(bx, cy - bh / 2, bx + METER_BW, cy + bh / 2, fill=accent, outline="")
            text_x = mx + METER_N * (METER_BW + METER_GAP) + 14
        else:
            text_x = 50

        txt = st["text"]
        if not txt:
            txt = {
                "listening": "Listening…",
                "transcribing": "Transcribing",
                "done": "",
                "error": "Error",
                "idle": "",
            }.get(st["name"], "")
        if st["name"] == "transcribing" and not st["text"]:
            txt = "Transcribing" + "." * (1 + int(st["phase"]) % 3)

        txt = self._fit(txt, WIN_W - text_x - 18)
        c.create_text(text_x, cy, text=txt, anchor="w", fill="#e5e7eb", font=("Segoe UI", 12))

    @staticmethod
    def _round_rect(c, x1, y1, x2, y2, r, **kw):
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return c.create_polygon(pts, smooth=True, **kw)

    @staticmethod
    def _fit(txt: str, maxw: float) -> str:
        maxchars = max(8, int(maxw / 7.2))
        if len(txt) > maxchars:
            return "…" + txt[-(maxchars - 1):]  # keep the latest words visible
        return txt
