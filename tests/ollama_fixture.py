"""A stand-in ollama server on a free local port, for tests that call a
model through the real wire path (`llm.complete` → urllib → HTTP).

`/api/tags` names the handler's `model` with its `digest` (None: no
model listed, so `llm` records the digest as `unavailable`); `/api/chat`
answers `answer` with `status` (200: with token counts and a finish
reason) and counts the requests in `chats`.
"""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class StandIn(BaseHTTPRequestHandler):
    """The handler; `start` gives each test a subclass of its own."""

    status = 200
    chats = 0
    answer = " the answer "
    model = "m"
    digest: str | None = "sha256:0123456789abcdef"

    def do_GET(self) -> None:
        listed = [{"name": f"{self.model}:latest", "digest": self.digest}]
        if self.digest is None:
            listed = []
        self._send(200, {"models": listed})

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"]))
        type(self).chats += 1
        body = {
            "message": {"content": self.answer, "thinking": "because"},
            "prompt_eval_count": 7,
            "eval_count": 3,
            "done_reason": "stop",
        }
        self._send(self.status, body if self.status == 200 else {"error": "no"})

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Silent: the test output stays the test's."""


def start(case: unittest.TestCase, **settings: object) -> tuple[type[StandIn], str]:
    """A server for CASE until its end, its handler class carrying SETTINGS
    (`status`, `answer`, `model`, `digest`); (the handler class, the base URL)."""
    handler = type("Handler", (StandIn,), {"chats": 0, **settings})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    case.addCleanup(server.server_close)
    case.addCleanup(server.shutdown)
    return handler, f"http://127.0.0.1:{server.server_address[1]}"
