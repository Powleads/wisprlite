"""Windows-only window-chrome helpers. Silent no-op on other platforms / older
Windows builds, so callers can always call them.
"""

from __future__ import annotations

import ctypes

DARK = "#13151d"


def dark_titlebar(root, color: str = DARK) -> None:
    """Force a dark title bar (Windows 10 1809+ / 11) instead of the user's
    accent color. No-op if DWM is unavailable."""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        dwm = ctypes.windll.dwmapi
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (was 19 on early 1809 builds)
        on = ctypes.c_int(1)
        if dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on)) != 0:
            dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(on), ctypes.sizeof(on))
        # DWMWA_CAPTION_COLOR = 35 (Win 11 22000+): match our dark background. 0x00BBGGRR
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        bgr = ctypes.c_int((b << 16) | (g << 8) | r)
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(bgr), ctypes.sizeof(bgr))
    except Exception:
        pass
