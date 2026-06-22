import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import profiles

def test_resolve_passes_style_overrides():
    p = [{"name": "code.exe", "match": {"exe": "code.exe"},
          "overrides": {"engine": "deepgram", "cleanup_style": "prompt",
                        "cleanup_instruction": "x", "bogus": "drop"}}]
    ov = profiles.resolve(p, {"exe": "code.exe", "title": "whatever"})
    assert ov.get("cleanup_style") == "prompt", ov
    assert ov.get("cleanup_instruction") == "x", ov
    assert ov.get("engine") == "deepgram", ov
    assert "bogus" not in ov  # still whitelisted

def test_no_match_returns_empty():
    assert profiles.resolve([{"match": {"exe": "x.exe"}, "overrides": {"cleanup_style": "prompt"}}],
                            {"exe": "other.exe"}) == {}

if __name__ == "__main__":
    test_resolve_passes_style_overrides(); test_no_match_returns_empty()
    print("OK")
