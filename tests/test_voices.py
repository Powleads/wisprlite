import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import voices, config, profiles

def test_resolve_filters_empty():
    cfg = config.Config()  # seeded with starters
    r = voices.resolve(cfg, "Code / Prompt")
    assert r == {"cleanup_style": "prompt", "ai_cleanup": True}   # starters force cleanup on
    s = voices.resolve(cfg, "Social")
    assert (s["cleanup_style"] == "custom" and s["auto_enter"] is False
            and s["ai_cleanup"] is True and "engine" not in s)

def test_unknown_voice():
    assert voices.resolve(config.Config(), "Nope") == {}

def test_starters_present():
    assert set(voices.names(config.Config())) >= {"Tidy", "Social", "Professional", "Code / Prompt"}

def test_legacy_ai_cleanup_resolves():
    # a pre-Voices profile that turned cleanup OFF for an app must keep doing so
    cfg = config.Config()
    cfg.profiles = [{"match": {"exe": "y.exe"}, "overrides": {"ai_cleanup": False}}]
    assert profiles.resolve(cfg, {"exe": "y.exe"}) == {"ai_cleanup": False}

def test_ai_cleanup_preserved_through_migration():
    cfg = config.Config()
    cfg.profiles = [{"name": "code.exe", "match": {"exe": "code.exe"},
                     "overrides": {"cleanup_style": "tidy", "ai_cleanup": False}}]
    assert voices.migrate_profiles(cfg) is True
    r = profiles.resolve(cfg, {"exe": "code.exe"})
    assert r.get("ai_cleanup") is False and r.get("cleanup_style") == "tidy"
    v = voices.by_name(cfg, cfg.profiles[0]["voice"])
    assert v["ai_cleanup"] is False          # the generated Voice carries it
    assert voices.migrate_profiles(cfg) is False   # idempotent

if __name__ == "__main__":
    test_resolve_filters_empty(); test_unknown_voice(); test_starters_present()
    test_legacy_ai_cleanup_resolves(); test_ai_cleanup_preserved_through_migration()
    print("OK")
