"""Erschoepfte Versuche werfen EINEN Typ — unabhaengig vom Backend.

Warum diese Datei existiert: Am 2026-08-14 starb ein 145-Item-Lauf an einem
DNS-Aussetzer. `llm.py` hatte korrekt viermal mit Backoff wiederholt und dann
`URLError` durchgereicht — aber alle vier Batch-Skripte fingen `RuntimeError`.
Bei der claude-CLI ist das vollstaendig korrekt (sie wirft `BackendError`, einen
`RuntimeError`); beim ollama-Backend faengt es nichts. Der Bug lag latent im
Code und wurde erst durch den Backend-Wechsel aktiv — die teuerste Sorte, weil
sie beim Testen auf einem Backend unsichtbar bleibt.

Der Fix liegt in `llm.py`, nicht in einer Regel: erschoepfte Versuche packen die
Ausnahme in `BackendError` und haengen das Original via `__cause__` an.
"""
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test


class TestExhaustedRetriesRaiseBackendError(unittest.TestCase):
    def setUp(self):
        from labkit import llm
        self.llm = llm
        self._once, self._sleep = llm._complete_once, llm.time.sleep
        llm.time.sleep = lambda _s: None          # Backoff ueberspringen

    def tearDown(self):
        self.llm._complete_once, self.llm.time.sleep = self._once, self._sleep

    def _fail_with(self, exc):
        self.llm._complete_once = lambda *a, **k: (_ for _ in ()).throw(exc)

    def test_urlerror_becomes_backenderror(self):
        """Der Fall vom 2026-08-14: ollama nicht aufloesbar."""
        self._fail_with(urllib.error.URLError("nodename nor servname provided"))
        with self.assertRaises(self.llm.BackendError) as ctx:
            self.llm.complete("gpt-oss", "irgendwas", attempts=2)
        self.assertIsInstance(ctx.exception, RuntimeError,
                              "'except RuntimeError' im Aufrufer muss greifen")
        self.assertIsInstance(ctx.exception.__cause__, urllib.error.URLError,
                              "die urspruengliche Ausnahme bleibt angehaengt")

    def test_timeout_becomes_backenderror(self):
        self._fail_with(TimeoutError("read timed out"))
        with self.assertRaises(self.llm.BackendError):
            self.llm.complete("gpt-oss", "irgendwas", attempts=2)

    def test_backenderror_passes_through_unwrapped(self):
        """Was schon der richtige Typ ist, wird nicht doppelt verpackt."""
        original = self.llm.BackendError("claude-cli exit 1: leer")
        self._fail_with(original)
        with self.assertRaises(self.llm.BackendError) as ctx:
            self.llm.complete("haiku", "irgendwas", attempts=2)
        self.assertIs(ctx.exception, original)

    def test_misconfiguration_is_not_retried(self):
        """Ein unbekannter Alias ist kein Transportfehler — sofort und ungefiltert."""
        # own models.toml: the package must not depend on a config file that
        # happens to sit above the current working directory.
        cfg = Path(tempfile.mkdtemp()) / "models.toml"
        cfg.write_text('[models.gpt-oss]\nbackend = "ollama"\n', encoding="utf-8")
        find = self.llm._find_models_toml
        self.llm._find_models_toml = lambda: cfg
        try:
            with self.assertRaises(KeyError):
                self.llm.complete("gibtsnicht", "irgendwas", attempts=2)
        finally:
            self.llm._find_models_toml = find

    def test_retries_are_counted(self):
        before = self.llm.retries()
        self._fail_with(urllib.error.URLError("weg"))
        with self.assertRaises(self.llm.BackendError):
            self.llm.complete("gpt-oss", "irgendwas", attempts=3)
        self.assertEqual(self.llm.retries() - before, 2,
                         "zwei Wiederholungen vor dem dritten, finalen Versuch")


if __name__ == "__main__":
    unittest.main()
