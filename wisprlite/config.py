"""Configuration: persisted user settings + secrets from the environment.

Non-secret settings live in %APPDATA%\\Pipevoice\\config.json so the tray menu
can change them at runtime. API keys are read from the environment / .env only
and are never written to disk.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "Pipevoice"


def config_dir() -> Path:
    base = os.getenv("APPDATA") or str(Path.home())
    d = Path(base) / APP_NAME
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


CONFIG_PATH = config_dir() / "config.json"


def _load_env() -> None:
    """Load .env from cwd, next to the executable, and the config dir."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv()  # cwd / parents
    candidates = [config_dir() / ".env"]
    try:
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / ".env")
    except Exception:
        pass
    for p in candidates:
        try:
            if p.exists():
                load_dotenv(p, override=False)
        except Exception:
            pass


_load_env()


@dataclass
class Config:
    engine: str = "deepgram"        # openai | deepgram | local
    mode: str = "ptt"               # ptt | toggle
    hotkey: str = "ctrl+\\"          # any key/combo, e.g. "ctrl+alt", "f9"
    output_mode: str = "type"       # type | paste
    language: str = ""              # "" = auto-detect; else ISO code e.g. "en"
    device: str = ""                # mic index or name substring; "" = default
    openai_model: str = "whisper-1"
    deepgram_model: str = "nova-3"
    local_model_size: str = "base.en"
    overlay: bool = True
    sounds: bool = False
    min_seconds: float = 0.35       # ignore taps shorter than this
    ai_cleanup: bool = True         # polish transcript with an LLM
    cleanup_model: str = "gpt-4o-mini"
    auto_enter: bool = False        # press Enter after typing (hands-free send)
    vocabulary: str = ""            # comma-separated terms to bias recognition
    replacements: dict = field(default_factory=dict)  # {wrong: right} post-fixes

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
            except Exception:
                pass
        else:
            # First run: seed a few settings from the environment, then persist.
            cfg.engine = os.getenv("WISPRLITE_ENGINE", cfg.engine)
            cfg.hotkey = os.getenv("WISPRLITE_HOTKEY", cfg.hotkey)
            cfg.mode = os.getenv("WISPRLITE_MODE", cfg.mode)
            cfg.language = os.getenv("WISPRLITE_LANG", cfg.language)
            cfg.device = os.getenv("WISPRLITE_DEVICE", cfg.device)
            cfg.openai_model = os.getenv("WISPRLITE_MODEL", cfg.openai_model)
            cfg.save()
        return cfg

    def save(self) -> None:
        try:
            CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except Exception:
            pass


def save_api_key(env_name: str, value: str) -> None:
    """Persist an API key to %APPDATA%\\Pipevoice\\.env and the live process."""
    value = (value or "").strip()
    if not value:
        return
    os.environ[env_name] = value
    path = config_dir() / ".env"
    lines = []
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            lines = []
    out, replaced = [], False
    for ln in lines:
        if ln.strip().startswith(env_name + "="):
            out.append(f"{env_name}={value}")
            replaced = True
        else:
            out.append(ln)
    if not replaced:
        out.append(f"{env_name}={value}")
    try:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    except Exception:
        pass


def asset_path(name: str) -> str | None:
    """Locate a bundled asset (works from source and PyInstaller onefile)."""
    candidates = []
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(Path(base) / "assets" / name)
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / name)
    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except Exception:
            pass
    return None


def openai_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def deepgram_key() -> str:
    return os.getenv("DEEPGRAM_API_KEY", "").strip()


def device_arg(cfg: Config):
    """Return a sounddevice-compatible device selector (int index, name, or None)."""
    d = (cfg.device or "").strip()
    if not d:
        return None
    try:
        return int(d)
    except ValueError:
        return d
