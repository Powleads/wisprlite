import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import captions

SEGS = [
    {"start": 0.0, "end": 1.5, "text": "Hello there.", "words": []},
    {"start": 1.5, "end": 3.25, "text": "General Kenobi.", "words": []},
]

def test_format_timestamp():
    assert captions.format_timestamp(0) == "00:00:00,000"
    assert captions.format_timestamp(3.25) == "00:00:03,250"
    assert captions.format_timestamp(3661.5, vtt=True) == "01:01:01.500"
    assert captions.format_timestamp(-2) == "00:00:00,000"

def test_to_srt():
    out = captions.to_srt(SEGS)
    assert out == (
        "1\n00:00:00,000 --> 00:00:01,500\nHello there.\n\n"
        "2\n00:00:01,500 --> 00:00:03,250\nGeneral Kenobi.\n"
    )

def test_to_vtt():
    out = captions.to_vtt(SEGS)
    assert out.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.500\nHello there." in out
    assert "00:00:01.500 --> 00:00:03.250\nGeneral Kenobi." in out

if __name__ == "__main__":
    test_format_timestamp(); test_to_srt(); test_to_vtt()
    print("OK")
