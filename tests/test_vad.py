import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite.vad import SilenceEndpointer

def feed_seq(ep, levels):
    return [ep.feed(x) for x in levels]

def test_leading_silence_never_triggers():
    ep = SilenceEndpointer(threshold=0.02, silence_ms=200, block_ms=50)
    assert not any(feed_seq(ep, [0.0] * 50))

def test_speech_then_silence_triggers():
    ep = SilenceEndpointer(threshold=0.02, silence_ms=200, block_ms=50)
    results = feed_seq(ep, [0.1, 0.1, 0.0, 0.0, 0.0, 0.0])
    assert results[-1] is True
    assert results[:4] == [False, False, False, False]

def test_sustained_speech_never_triggers():
    ep = SilenceEndpointer(threshold=0.02, silence_ms=200, block_ms=50)
    assert not any(feed_seq(ep, [0.1] * 50))

def test_silence_resets_on_new_speech():
    ep = SilenceEndpointer(threshold=0.02, silence_ms=200, block_ms=50)
    feed_seq(ep, [0.1, 0.0, 0.0, 0.1])
    assert ep.feed(0.0) is False

if __name__ == "__main__":
    test_leading_silence_never_triggers(); test_speech_then_silence_triggers()
    test_sustained_speech_never_triggers(); test_silence_resets_on_new_speech()
    print("OK")
