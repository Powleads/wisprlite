"""Detect the focused (foreground) window: exe basename + title + class.

Windows-only via ctypes; returns {} on any failure or non-Windows, matching the
codebase's fault-tolerant style. Also flags the case where there is clearly no
text target (the desktop, the taskbar, or no window), so dictation can fall back
to the clipboard instead of typing into the void.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

# window classes that mean "no app text target" (desktop / taskbar / start menu)
_SHELL_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow", "MultitaskingViewFrame", "XamlExplorerHostIslandWindow",
}

# system/background processes that shouldn't appear in the app picker
_NOISE_EXES = {
    "explorer.exe", "textinputhost.exe", "applicationframehost.exe", "searchhost.exe",
    "searchapp.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
    "systemsettings.exe", "lockapp.exe", "widgets.exe", "widgetboard.exe",
    "dwm.exe", "sihost.exe", "pipevoice.exe", "python.exe", "pythonw.exe",
}


def _exe_for_pid(pid: int) -> str:
    try:
        k = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ""
        try:
            size = wintypes.DWORD(260)
            buf = ctypes.create_unicode_buffer(260)
            if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                path = buf.value or ""
                return path.replace("\\", "/").split("/")[-1].lower()
            return ""
        finally:
            k.CloseHandle(h)
    except Exception:
        return ""


def detect() -> dict:
    """Return {'exe','title','cls'} for the foreground window, or {} on failure."""
    try:
        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return {}
        n = u.GetWindowTextLengthW(hwnd)
        tbuf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, tbuf, n + 1)
        cbuf = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(hwnd, cbuf, 256)
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return {"exe": _exe_for_pid(pid.value), "title": tbuf.value or "", "cls": cbuf.value or ""}
    except Exception:
        return {}


def list_windows() -> list:
    """Visible top-level windows for an app picker: [{'exe','title'}], deduped by
    exe and sorted. Returns [] off Windows (the picker still allows typing)."""
    import os

    fake = os.getenv("PV_FAKE_WINDOWS")  # test seam for headless rendering
    if fake:
        return [{"exe": e.strip(), "title": e.strip().split(".")[0].title()}
                for e in fake.split(",") if e.strip()]
    found = {}
    try:
        u = ctypes.windll.user32

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def _cb(hwnd, lparam):
            try:
                if not u.IsWindowVisible(hwnd):
                    return True
                n = u.GetWindowTextLengthW(hwnd)
                if n == 0:
                    return True  # skip title-less windows (usually not real apps)
                tbuf = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(hwnd, tbuf, n + 1)
                pid = wintypes.DWORD()
                u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                exe = _exe_for_pid(pid.value)
                if exe and exe not in _NOISE_EXES and exe not in found:
                    found[exe] = tbuf.value or ""
            except Exception:
                pass
            return True

        u.EnumWindows(_cb, 0)
    except Exception:
        return []
    return [{"exe": e, "title": t} for e, t in sorted(found.items())]


def is_no_text_target(ctx: dict) -> bool:
    """True only when we POSITIVELY know there is no text target (desktop / shell /
    nothing). Returns False when unknown, so we never wrongly divert a real app's
    text to the clipboard (Chromium apps hide their caret, so we don't guess)."""
    if not ctx:
        return False
    if ctx.get("cls", "") in _SHELL_CLASSES:
        return True
    # the desktop is explorer.exe with no window title
    if ctx.get("exe", "") == "explorer.exe" and not ctx.get("title", ""):
        return True
    return False
