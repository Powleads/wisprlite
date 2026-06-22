"""Loopback control bridge: lets the `--mcp` shim drive the running tray app.

Stdlib socket + newline-delimited JSON. Binds 127.0.0.1 only. Lazy/optional:
if it can't bind, the caller logs and the feature stays off. This keeps the
resident app's footprint to a single stdlib socket listener — no web framework.
"""

from __future__ import annotations

import json
import socket
import threading
from typing import Callable


def encode(obj) -> bytes:
    return (json.dumps(obj) + "\n").encode("utf-8")


def decode(line: bytes) -> dict:
    return json.loads(line.decode("utf-8"))


def send_request(port: int, obj: dict, timeout: float = 120.0) -> dict:
    """Client side (used by the shim). Connect, send one request, read one reply."""
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as s:
        s.settimeout(timeout)
        s.sendall(encode(obj))
        f = s.makefile("rb")
        line = f.readline()
        return decode(line) if line else {"status": "error", "error": "no response"}


class ControlListener:
    """Accepts one JSON request per connection, calls ``dispatch(req) -> resp``."""

    def __init__(self, port: int, dispatch: Callable[[dict], dict]) -> None:
        self.port = port
        self.dispatch = dispatch
        self._sock = None
        self._thread = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.port))
        self.port = self._sock.getsockname()[1]  # resolve ephemeral (port 0)
        self._sock.listen(4)
        self._sock.settimeout(0.5)
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn) -> None:
        try:
            f = conn.makefile("rwb")
            line = f.readline()
            if not line:
                return
            try:
                resp = self.dispatch(decode(line))
            except Exception as exc:  # never crash the bridge on a bad request
                resp = {"status": "error", "error": str(exc)}
            f.write(encode(resp))
            f.flush()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
