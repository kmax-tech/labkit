"""max_tokens: a cap given to a backend that has none is refused, as an
unhonoured temperature is; none given leaves it to the backend (ollama and
openai still send DEFAULT_MAX_TOKENS, tests/test_llm_chat_options.py).
claude-cli has no token flag, and an explicit cap was dropped without a
word (review 2026-10-20).

    .venv/bin/python -m pytest tests/test_llm_max_tokens.py
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_fixture import cli_reply, typed  # noqa: E402

from labkit.gates import audit  # noqa: E402
from labkit.run import llm  # noqa: E402

SPECS = {
    "cli": {"backend": "claude-cli", "model": "m"},
    "local": {"backend": "ollama", "model": "m", "endpoint": "http://h:1"},
}


def _specs():
    return mock.patch.object(llm, "spec", typed(lambda alias: SPECS[alias]))


class ClaudeCli(unittest.TestCase):
    def _call(self, **kw) -> list[list[str]]:
        seen: list[list[str]] = []

        def fake_run(cmd, **_):
            seen.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout=cli_reply(), stderr="")

        with (
            _specs(),
            mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
            mock.patch.object(llm.subprocess, "run", fake_run),
        ):
            llm._complete_once("cli", "prompt", **kw)
        return seen

    def test_an_explicit_cap_is_refused_before_the_call(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_tokens=2048"):
            self._call(max_tokens=2048)

    def test_twin_no_cap_runs(self) -> None:
        self.assertEqual(len(self._call()), 1)


class TakesMaxTokens(unittest.TestCase):
    def test_the_backends_that_cap_say_so(self) -> None:
        with _specs():
            self.assertEqual(
                (llm.takes_max_tokens("cli"), llm.takes_max_tokens("local")),
                (False, True),
            )

    def test_the_audit_asks_for_room_only_where_a_backend_caps(self) -> None:
        with _specs():
            self.assertEqual(
                (audit._report_room("cli"), audit._report_room("local")),
                (None, audit.REPORT_TOKENS),
            )


if __name__ == "__main__":
    unittest.main()
