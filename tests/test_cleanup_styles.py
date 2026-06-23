import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import cleanup

def test_tidy_is_default():
    assert cleanup._style_system("tidy") == cleanup._TIDY
    assert cleanup._style_system("") == cleanup._TIDY
    assert cleanup._style_system("nonsense") == cleanup._TIDY  # unknown -> tidy

def test_prompt_style():
    s = cleanup._style_system("prompt")
    assert s == cleanup._PROMPT
    low = s.lower()
    # restructure + output-only rail
    assert "reshuffle" in low or "rewrite" in low
    assert s.strip().endswith("Return ONLY the polished text, nothing else.")
    # faithfulness rail: polarity / negation must be called out and protected
    assert "negation" in low
    assert "'with'" in low and "'without'" in low
    # speech-act rail: never fabricate a command; keep the kind of utterance
    assert "fabricate a command" in low
    assert "a question stays a question" in low
    assert "stays a request for ideas" in low
    assert "what do you think" in low  # tentative brainstorm / opinion-ask preserved

def test_custom_style():
    s = cleanup._style_system("custom", "Rewrite as a git commit message.")
    assert s.startswith("Rewrite as a git commit message.")
    assert "ONLY the rewritten text" in s  # safety rails appended
    # empty custom instruction falls back to tidy (never an empty/unsafe prompt)
    assert cleanup._style_system("custom", "   ") == cleanup._TIDY

if __name__ == "__main__":
    test_tidy_is_default(); test_prompt_style(); test_custom_style()
    print("OK")
