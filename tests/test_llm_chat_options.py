"""Der Chat-Pfad muss `num_predict` senden — sonst laeuft die Generierung frei.

Warum diese Datei existiert: Bis 2026-08-19 setzte `llm.complete` das
Token-Budget NUR im `raw=True`-Zweig an `/api/generate`. Der Chat-Zweig, den
jedes Experiment nimmt, schickte ausschliesslich `temperature` und verwarf
`max_tokens` stumm. Folge: `gpt-oss` generierte bei nominell 2048 Tokens
tatsaechlich 3520 und war nicht fertig (Server-Log, ~19 t/s), der Request lief
ins Timeout, und das Fehlerbild — Timeouts, abgebrochene Laeufe — sah aus wie
ein ueberlasteter Cluster. Eine halbe Session ging fuer die falsche Hypothese
drauf.

Der Bug war unsichtbar, weil `max_tokens` einen Default hat: jeder Aufruf sah
korrekt aus, und die Wirkung fehlte trotzdem. Genau dagegen prueft dieser Test
die *gesendete Payload*, nicht die Signatur.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestChatPathSendsTokenBudget(unittest.TestCase):
    def setUp(self):
        from labkit import llm
        self.llm = llm
        self.sent = {}
        self._resolve, self._urlopen = llm.resolve, llm.urllib.request.urlopen
        llm.resolve = lambda alias: {"backend": "ollama", "model": "gpt-oss:latest",
                                     "endpoint": "http://example.invalid:11490"}

        def fake_urlopen(req, timeout=None):
            self.sent["url"] = req.full_url
            self.sent["payload"] = json.loads(req.data.decode("utf-8"))
            self.sent["timeout"] = timeout
            return _FakeResponse({"message": {"content": "a situation"}})

        llm.urllib.request.urlopen = fake_urlopen

    def tearDown(self):
        self.llm.resolve = self._resolve
        self.llm.urllib.request.urlopen = self._urlopen

    def test_num_predict_is_sent(self):
        self.llm.complete("gpt-oss", "prompt", max_tokens=2048, temperature=0.0)
        self.assertIn("/api/chat", self.sent["url"])
        options = self.sent["payload"].get("options", {})
        self.assertEqual(options.get("num_predict"), 2048,
                         "Chat-Pfad muss das Token-Budget senden — ohne das "
                         "generiert das Modell bis der Kontext voll ist")
        self.assertEqual(options.get("temperature"), 0.0)

    def test_default_budget_is_sent_too(self):
        """Auch ohne explizites max_tokens darf die Schranke nicht fehlen."""
        self.llm.complete("gpt-oss", "prompt")
        self.assertIsNotNone(
            self.sent["payload"].get("options", {}).get("num_predict"))

    def test_timeout_reaches_the_transport(self):
        """Das Wartefenster ist der Knopf, der die Messung NICHT anfasst."""
        self.llm.complete("gpt-oss", "prompt", timeout=900)
        self.assertEqual(self.sent["timeout"], 900)


class TestEmptyContentIsReported(unittest.TestCase):
    """Denkt das Modell und sagt nichts, darf das nicht wie eine Antwort aussehen."""

    def setUp(self):
        import io
        from labkit import llm
        self.llm, self.io = llm, io
        self._resolve, self._urlopen = llm.resolve, llm.urllib.request.urlopen
        llm.resolve = lambda alias: {"backend": "ollama", "model": "gpt-oss:latest",
                                     "endpoint": "http://example.invalid:11490"}
        llm.urllib.request.urlopen = lambda req, timeout=None: _FakeResponse(
            {"message": {"content": "", "thinking": "The user says: ..."},
             "done_reason": "length", "eval_count": 2048})

    def tearDown(self):
        self.llm.resolve = self._resolve
        self.llm.urllib.request.urlopen = self._urlopen

    def test_empty_content_returns_empty_and_warns(self):
        err = self.io.StringIO()
        stderr, sys.stderr = sys.stderr, err
        try:
            out = self.llm.complete("gpt-oss", "prompt")
        finally:
            sys.stderr = stderr
        self.assertEqual(out, "", "leerer content bleibt leer — der Aufrufer "
                                  "zaehlt ihn als unlesbar")
        self.assertIn("LEEREN content", err.getvalue())
        self.assertIn("thinking", err.getvalue())


if __name__ == "__main__":
    unittest.main()
