import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import agent_bridge

def test_roundtrip_and_dispatch():
    seen = {}
    def dispatch(req):
        seen["req"] = req
        if req["op"] == "ping":
            return {"status": "ok", "text": "pong"}
        return {"status": "error", "error": "unknown op"}

    listener = agent_bridge.ControlListener(0, dispatch)
    listener.start()
    port = listener.port
    try:
        resp = agent_bridge.send_request(port, {"op": "ping", "x": 1}, timeout=5.0)
        assert resp == {"status": "ok", "text": "pong"}, resp
        assert seen["req"] == {"op": "ping", "x": 1}, seen
        bad = agent_bridge.send_request(port, {"op": "nope"}, timeout=5.0)
        assert bad["status"] == "error", bad
    finally:
        listener.stop()

def test_dispatch_exception_becomes_error():
    def dispatch(req):
        raise ValueError("boom")
    listener = agent_bridge.ControlListener(0, dispatch)
    listener.start()
    try:
        resp = agent_bridge.send_request(listener.port, {"op": "x"}, timeout=5.0)
        assert resp["status"] == "error" and "boom" in resp["error"], resp
    finally:
        listener.stop()

if __name__ == "__main__":
    test_roundtrip_and_dispatch(); test_dispatch_exception_becomes_error()
    print("OK")
