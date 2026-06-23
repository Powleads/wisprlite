"""Named polish 'Voices': a reusable per-utterance override preset (the same bag
app profiles apply), bound to hotkeys and/or apps. resolve() turns a name into the
non-empty overrides that App._eff reads."""
from __future__ import annotations

# the per-utterance dials a Voice may set; "" means "leave as-is" for strings,
# None means "leave as-is" for the tri-state bools (auto_enter, ai_cleanup)
VOICE_KEYS = ("cleanup_style", "cleanup_instruction", "engine", "auto_enter",
              "output_mode", "ai_cleanup")
_TRISTATE = ("auto_enter", "ai_cleanup")

# Starters force ai_cleanup=True: they ARE polish presets, so picking one should
# polish even if the user's global cleanup is off.
STARTER_VOICES = [
    {"name": "Tidy", "cleanup_style": "tidy", "cleanup_instruction": "",
     "engine": "", "auto_enter": None, "output_mode": "", "ai_cleanup": True},
    {"name": "Social", "cleanup_style": "custom",
     "cleanup_instruction": ("Rewrite as a friendly, casual social-media post in the "
        "speaker's own meaning. Natural, warm, light; emojis only if they fit. Keep it concise."),
     "engine": "", "auto_enter": False, "output_mode": "", "ai_cleanup": True},
    {"name": "Professional", "cleanup_style": "custom",
     "cleanup_instruction": ("Rewrite as clear, professional writing (e.g. an email): correct, "
        "polished, neutral-to-formal tone, British spelling. Preserve the speaker's meaning and every "
        "specific; do not add content."),
     "engine": "", "auto_enter": None, "output_mode": "", "ai_cleanup": True},
    {"name": "Code / Prompt", "cleanup_style": "prompt", "cleanup_instruction": "",
     "engine": "", "auto_enter": None, "output_mode": "", "ai_cleanup": True},
]

def names(cfg) -> list:
    return [v.get("name", "") for v in (getattr(cfg, "voices", None) or []) if v.get("name")]

def by_name(cfg, name: str) -> dict | None:
    for v in (getattr(cfg, "voices", None) or []):
        if v.get("name") == name:
            return v
    return None

def resolve(cfg, name: str) -> dict:
    """The non-empty overrides for Voice `name`, ready to drop into App._active. {} if unknown."""
    v = by_name(cfg, name)
    if not v:
        return {}
    out = {}
    for k in VOICE_KEYS:
        val = v.get(k)
        if k in _TRISTATE:
            if val is not None:
                out[k] = bool(val)
        elif val:                      # non-empty string
            out[k] = val
    return out


def migrate_profiles(cfg) -> bool:
    """One-shot, idempotent migration of legacy profile overrides into named Voices.

    For each profile that has legacy ``overrides`` and no ``voice``: create a Voice
    named "<exe-base> voice" (deduped against existing voice names), append it to
    ``cfg.voices``, set ``profile["voice"] = name``, and drop ``profile["overrides"]``.
    Returns True if anything changed so the caller can persist cfg.
    Profiles already carrying ``voice`` are skipped so re-running is a no-op.
    """
    changed = False
    existing = set(names(cfg))
    for p in (getattr(cfg, "profiles", None) or []):
        if not isinstance(p, dict) or p.get("voice") or not p.get("overrides"):
            continue
        ov = {k: v for k, v in p["overrides"].items() if k in VOICE_KEYS}
        base = ((p.get("match") or {}).get("exe") or p.get("name") or "app").split(".")[0]
        name = f"{base} voice"
        i = 2
        while name in existing:
            name = f"{base} voice {i}"
            i += 1
        existing.add(name)
        voice = {
            "name": name,
            "cleanup_style": ov.get("cleanup_style", ""),
            "cleanup_instruction": ov.get("cleanup_instruction", ""),
            "engine": ov.get("engine", ""),
            "auto_enter": ov.get("auto_enter"),
            "output_mode": ov.get("output_mode", ""),
            "ai_cleanup": ov.get("ai_cleanup"),
        }
        cfg.voices.append(voice)
        p["voice"] = name
        p.pop("overrides", None)
        changed = True
    return changed
