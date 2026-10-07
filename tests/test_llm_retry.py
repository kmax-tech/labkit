"""Exhausted retries raise ONE type — regardless of the backend.

Why this file exists: on 2026-08-14 a 145-item run died on a DNS hiccup.
`llm.py` had correctly retried four times with backoff and then passed
`URLError` through — but all four batch scripts caught `RuntimeError`. With
the claude CLI that is entirely correct (it throws `BackendError`, a
`RuntimeError`); with the ollama backend it catches nothing. The bug lay
latent in the code and only the backend switch activated it — the most
expensive kind, because it stays invisible when testing on one backend.

The fix lives in `llm.py`, not in a rule: exhausted retries wrap the
exception in `BackendError` and attach the original via `__cause__`.
"""

import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test


class TestExhaustedRetriesRaiseBackendError(unittest.TestCase):
    def setUp(self):
        from labkit import llm

        self.llm = llm
        self._once, self._sleep = llm._complete_once, llm.time.sleep
        llm.time.sleep = lambda _s: None  # skip the backoff

    def tearDown(self):
        self.llm._complete_once, self.llm.time.sleep = self._once, self._sleep

    def _fail_with(self, exc):
        self.llm._complete_once = lambda *a, **k: (_ for _ in ()).throw(exc)

    def test_urlerror_becomes_backenderror(self):
        """The 2026-08-14 case: ollama not resolvable."""
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
        find = self.llm._find_models_toml
        self.llm._find_models_toml = lambda: cfg
        try:
            with self.assertRaises(KeyError):
                self.llm.complete("no-such-alias", "anything", attempts=2)
        finally:
            self.llm._find_models_toml = find

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
