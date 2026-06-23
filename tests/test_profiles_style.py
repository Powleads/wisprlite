import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import profiles, voices, config


def test_voice_profile():
    """Profile with a voice key: resolve returns the Voice's overrides."""
    cfg = config.Config()
    cfg.profiles = [{"match": {"exe": "x.exe"}, "voice": "Code / Prompt"}]
    result = profiles.resolve(cfg, {"exe": "x.exe"})
    assert result == {"cleanup_style": "prompt", "ai_cleanup": True}, result  # starters force cleanup on


def test_legacy_backcompat():
    """Profile with legacy overrides (no voice key): overrides are filtered to VOICE_KEYS."""
    cfg = config.Config()
    cfg.profiles = [{"match": {"exe": "y.exe"},
                     "overrides": {"cleanup_style": "prompt", "auto_enter": True}}]
    result = profiles.resolve(cfg, {"exe": "y.exe"})
    assert result == {"cleanup_style": "prompt", "auto_enter": True}, result


def test_no_match_returns_empty():
    """No matching profile: resolve returns {}."""
    cfg = config.Config()
    cfg.profiles = [{"match": {"exe": "x.exe"}, "voice": "Tidy"}]
    assert profiles.resolve(cfg, {"exe": "other.exe"}) == {}


def test_migrate_profiles():
    """Migration converts legacy overrides to a named Voice (idempotent)."""
    cfg = config.Config()
    cfg.profiles = [
        {"name": "code.exe", "match": {"exe": "code.exe"},
         "overrides": {"cleanup_style": "prompt", "engine": "deepgram"}},
    ]

    # First run: should change something
    changed = voices.migrate_profiles(cfg)
    assert changed is True, "expected migration to report changes"

    # Profile now has voice, no overrides
    p = cfg.profiles[0]
    assert p.get("voice") is not None, "profile should have a voice key after migration"
    assert "overrides" not in p, "profile should not have overrides after migration"

    # A matching Voice was added to cfg.voices
    voice_name = p["voice"]
    v = voices.by_name(cfg, voice_name)
    assert v is not None, f"Voice '{voice_name}' not found in cfg.voices"
    assert v.get("cleanup_style") == "prompt"
    assert v.get("engine") == "deepgram"

    # Second run: idempotent — no further changes
    changed2 = voices.migrate_profiles(cfg)
    assert changed2 is False, "second run should be a no-op"


if __name__ == "__main__":
    test_voice_profile()
    test_legacy_backcompat()
    test_no_match_returns_empty()
    test_migrate_profiles()
    print("OK")
