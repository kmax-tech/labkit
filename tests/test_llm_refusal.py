"""A run that may make no model call refuses every call through labkit's
LLM interface while it is open, in every thread of the process, before
anything is sent; after it, calls go through again.

    .venv/bin/python -m pytest tests/test_llm_refusal.py
"""

from __future__ import annotations

import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_fixture import typed  # noqa: E402

from labkit.run import llm  # noqa: E402

SPECS = {"local": {"backend": "ollama", "model": "m", "endpoint": "http://h:1"}}
WHY = "a derived run re-reads its parent's rows"


class Sent(Exception):
    """The fake backend was reached: the call would have been sent."""


def _backend():
    """The spec of SPECS and a backend that raises Sent when reached."""
    spec = mock.patch.object(llm, "spec", typed(lambda alias: SPECS[alias]))
    send = mock.patch.object(llm, "_complete_once", side_effect=Sent)
    return spec, send


class RefusingCalls(unittest.TestCase):
    def test_every_entry_refuses_before_anything_is_sent(self) -> None:
        spec, send = _backend()
        with spec, send as sent, llm.refusing_calls("run-a", WHY):
            for call in (
                lambda: llm.complete("local", "p"),
                lambda: llm.complete_response("local", "p"),
                lambda: llm.complete_many("local", ["p", "q"], workers=2),
            ):
                with self.assertRaises(llm.CallRefused) as cm:
                    call()
                self.assertIn("run run-a is open", str(cm.exception))
                self.assertIn(WHY, str(cm.exception))
        sent.assert_not_called()

    def test_a_worker_thread_is_refused_too(self) -> None:
        spec, send = _backend()
        with spec, send as sent, llm.refusing_calls("run-a", WHY):
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(llm.complete, "local", "p") for _ in range(8)]
                for f in futures:
                    self.assertIsInstance(f.exception(), llm.CallRefused)
        sent.assert_not_called()

    def test_after_the_run_calls_go_through(self) -> None:
        # the twin: outside the block the backend is reached
        spec, send = _backend()
        with spec, send:
            with llm.refusing_calls("run-a", WHY):
                pass
            with self.assertRaises(Sent):
                llm.complete("local", "p", attempts=1)

    def test_a_run_refuses_once(self) -> None:
        with llm.refusing_calls("run-a", WHY):
            with self.assertRaises(ValueError):
                with llm.refusing_calls("run-a", WHY):
                    pass
        with llm.refusing_calls("run-a", WHY):  # released after the block
            pass


if __name__ == "__main__":
    unittest.main()
