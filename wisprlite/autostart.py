"""Run Pipevoice at Windows login via the HKCU Run registry key.

Works both from source (launches pythonw + a tiny generated launcher with an
absolute sys.path so cwd doesn't matter) and from a PyInstaller .exe.
"""

from __future__ import annotations

import os
import sys

from .config import config_dir

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Pipevoice"

try:
    import winreg  # Windows only
except Exception:  # pragma: no cover
    winreg = None


def _pythonw() -> str:
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        pyw = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(pyw):
            return pyw
    return exe


def _write_launcher() -> str:
    """Generate a no-console launcher that runs the package by absolute path."""
    pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    launcher = config_dir() / "wisprlite_launch.pyw"
    launcher.write_text(
        "import sys\n"
        f"sys.path.insert(0, r'{pkg_parent}')\n"
        "from wisprlite.app import main\n"
        "main()\n",
        encoding="utf-8",
    )
    return str(launcher)


def _command() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller exe
        return f'"{sys.executable}"'
    return f'"{_pythonw()}" "{_write_launcher()}"'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return False
    except Exception:
        return False


def enable() -> None:
    if winreg is None:
        return
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
    finally:
        winreg.CloseKey(key)


def disable() -> None:
    if winreg is None:
        return
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, VALUE_NAME)
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    except Exception:
        pass
