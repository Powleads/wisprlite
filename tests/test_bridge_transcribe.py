import sys, pathlib, tempfile, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import agent_bridge, captions

def fake_transcribe_file(path, *, language=None, model_size="base.en", **kw):
    return {"text": "hello world", "language": "en", "duration": 1.0,
            "segments": [{"start": 0.0, "end": 1.0, "text": "hello world", "words": []}]}

def make_dispatch():
    def dispatch(req):
        if req.get("op") != "transcribe":
            return {"status": "error", "error": "unexpected op"}
        path = req["path"]
        if not os.path.exists(path):
            return {"status": "error", "error": "file not found"}
        r = fake_transcribe_file(path)
        out = {"status": "ok", "text": r["text"], "language": r["language"], "duration": r["duration"]}
        if req.get("format") == "srt":
            out["captions"] = captions.to_srt(r["segments"])
        else:
            out["segments"] = r["segments"]
        return out
    return dispatch

def test_transcribe_json_and_srt():
    listener = agent_bridge.ControlListener(0, make_dispatch())
    listener.start()
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            p = tf.name
        try:
            j = agent_bridge.send_request(listener.port, {"op": "transcribe", "path": p, "format": "json"})
            assert j["status"] == "ok" and j["text"] == "hello world" and "segments" in j, j
            srt = agent_bridge.send_request(listener.port, {"op": "transcribe", "path": p, "format": "srt"})
            assert srt["captions"].startswith("1\n00:00:00,000 --> 00:00:01,000"), srt
            miss = agent_bridge.send_request(listener.port, {"op": "transcribe", "path": "/no/such", "format": "json"})
            assert miss["status"] == "error", miss
        finally:
            os.unlink(p)
    finally:
        listener.stop()

if __name__ == "__main__":
    test_transcribe_json_and_srt()
    print("OK")
