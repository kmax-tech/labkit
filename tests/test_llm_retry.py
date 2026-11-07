"""Exhausted retries raise ONE type — regardless of the backend.

A caller catches `RuntimeError` after the retries: the claude CLI throws
`BackendError`, a `RuntimeError`, and the ollama backend must not pass
`URLError` through instead — a difference that stays invisible when
testing on one backend.

The rule lives in `llm.py`: exhausted retries wrap the exception in
`BackendError` and attach the original via `__cause__`.
"""

import email.message
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test


class TestExhaustedRetriesRaiseBackendError(unittest.TestCase):
    def setUp(self):
        from labkit.run import llm

        self.llm = llm
        self._once, self._sleep = llm._complete_once, llm.time.sleep
        llm.time.sleep = lambda _s: None  # skip the backoff

    def tearDown(self):
        self.llm._complete_once, self.llm.time.sleep = self._once, self._sleep

    def _fail_with(self, exc):
        self.llm._complete_once = lambda *a, **k: (_ for _ in ()).throw(exc)

    def test_urlerror_becomes_backenderror(self):
        """Ollama not resolvable."""
        self._fail_with(urllib.error.URLError("nodename nor servname provided"))
        with self.assertRaises(self.llm.BackendError) as ctx:
            self.llm.complete("gpt-oss", "anything", attempts=2)
        self.assertIsInstance(
            ctx.exception,
            RuntimeError,
            "'except RuntimeError' in the caller must catch",
        )
        self.assertIsInstance(
            ctx.exception.__cause__,
            urllib.error.URLError,
            "the original exception stays attached",
        )

    def test_timeout_becomes_backenderror(self):
        self._fail_with(TimeoutError("read timed out"))
        with self.assertRaises(self.llm.BackendError):
            self.llm.complete("gpt-oss", "anything", attempts=2)

    def test_backenderror_passes_through_unwrapped(self):
        """What already is the right type is not wrapped twice."""
        original = self.llm.BackendError("claude-cli exit 1: empty")
        self._fail_with(original)
        with self.assertRaises(self.llm.BackendError) as ctx:
            self.llm.complete("haiku", "anything", attempts=2)
        self.assertIs(ctx.exception, original)

    def test_misconfiguration_is_not_retried(self):
        """An unknown alias is no transport error — immediate and unfiltered."""
        # own models.toml: the package must not depend on a config file that
        # happens to sit above the current working directory.
        cfg = Path(tempfile.mkdtemp()) / "models.toml"
        cfg.write_text('[models.gpt-oss]\nbackend = "ollama"\n', encoding="utf-8")
        find = self.llm.find_models_toml
        self.llm.find_models_toml = lambda: cfg
        try:
            with self.assertRaises(KeyError):
                self.llm.complete("no-such-alias", "anything", attempts=2)
        finally:
            self.llm.find_models_toml = find

    def test_retries_are_counted(self):
        before = self.llm.retries()
        self._fail_with(urllib.error.URLError("gone"))
        with self.assertRaises(self.llm.BackendError):
            self.llm.complete("gpt-oss", "anything", attempts=3)
        self.assertEqual(
            self.llm.retries() - before,
            2,
            "two retries before the third, final attempt",
        )


if __name__ == "__main__":
    unittest.main()


class TestServerRefusalsAreNotRetried(unittest.TestCase):
    """`HTTPError` is a `URLError`, but a 404 (wrong model id) or 401 is not
    retried through minutes of backoff: a 4xx is the server's answer about
    the request; a 5xx is an outage and keeps the retry."""

    def setUp(self):
        from labkit.run import llm

        self.llm = llm
        self._once, self._sleep = llm._complete_once, llm.time.sleep
        llm.time.sleep = lambda _s: None
        self.calls = 0

    def tearDown(self):
        self.llm._complete_once, self.llm.time.sleep = self._once, self._sleep

    def _http(self, code: int):
        def once(*a, **k):
            self.calls += 1
            raise urllib.error.HTTPError(
                "http://x/v1/chat", code, "nope", email.message.Message(), None
            )

        self.llm._complete_once = once

    def test_a_4xx_fails_at_once_with_a_sentence(self):
        for code in (400, 401, 404):
            with self.subTest(code=code):
                self.calls = 0
                self._http(code)
                with self.assertRaises(self.llm.BackendError) as ctx:
                    self.llm.complete("gpt-oss", "anything", attempts=3)
                self.assertEqual(self.calls, 1)
                self.assertIn(f"HTTP {code}", str(ctx.exception))
                self.assertIn("models.toml", str(ctx.exception))

    def test_a_5xx_is_still_retried(self):
        self._http(503)
        with self.assertRaises(self.llm.BackendError):
            self.llm.complete("gpt-oss", "anything", attempts=3)
        self.assertEqual(self.calls, 3)
