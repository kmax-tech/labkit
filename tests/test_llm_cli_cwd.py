"""claude-cli backend (2026-10-05): the subprocess runs from a neutral
directory, not from the repo the experiment lives in."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_fixture import cli_reply, typed  # noqa: E402

from labkit.run import llm, llm_backends  # noqa: E402


class CliCwd(unittest.TestCase):
    def test_spawned_from_tempdir(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen.update(kw)
            return subprocess.CompletedProcess(cmd, 0, stdout="Causal\n", stderr="")

        with mock.patch.object(llm.subprocess, "run", fake_run):
            r = llm_backends._cli_run(["claude", "-p", "x"], timeout=5)
        self.assertEqual(r.stdout.strip(), "Causal")
        self.assertEqual(seen["cwd"], tempfile.gettempdir())
        self.assertTrue(seen["capture_output"])


class CliIsolation(unittest.TestCase):
    def test_no_settings_and_no_tools(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout=cli_reply(), stderr="")

        with (
            mock.patch.object(
                llm,
                "spec",
                typed(lambda alias: {"backend": "claude-cli", "model": "m"}),
            ),
            mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
            mock.patch.object(llm.subprocess, "run", fake_run),
        ):
            llm._complete_once("x", "prompt")
        cmd = seen["cmd"]
        self.assertEqual(cmd[cmd.index("--setting-sources") + 1], "")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")

    def test_the_prompt_goes_on_stdin_not_argv(self):
        """A 200 kB audit prompt as one argv entry is `OSError: Argument list
        too long` on Linux (128 kB per entry); macOS let it through, every
        cloud session died (audit 2026-10-15)."""
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"], seen["input"] = cmd, kw.get("input")
            return subprocess.CompletedProcess(cmd, 0, stdout=cli_reply(), stderr="")

        prompt = "x" * 200_000
        with (
            mock.patch.object(
                llm,
                "spec",
                typed(lambda alias: {"backend": "claude-cli", "model": "m"}),
            ),
            mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
            mock.patch.object(llm.subprocess, "run", fake_run),
        ):
            llm._complete_once("x", prompt)
        self.assertEqual(seen["input"], prompt)
        self.assertNotIn(prompt, seen["cmd"])
        self.assertTrue(all(len(a) < 1000 for a in seen["cmd"]))


class CliInput(unittest.TestCase):
    """`input = "prompt"` sends the prompt alone: on CLI 2.1.309 the default
    call carried a 27 k-character agent system prompt, environment
    reminders and thinking beside a registered prompt (registered pilot,
    pubmedqa50, 2026-11-01; checked behind a logging proxy)."""

    def _call(self, table, environ, system=None):
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"], seen["env"] = cmd, kw.get("env")
            return subprocess.CompletedProcess(cmd, 0, stdout=cli_reply(), stderr="")

        with (
            mock.patch.object(llm, "spec", typed(lambda alias: table)),
            mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
            mock.patch.object(llm.subprocess, "run", fake_run),
            mock.patch.dict(llm_backends.os.environ, environ, clear=True),
        ):
            llm._complete_once("x", "prompt", system=system)
        return seen

    def test_prompt_only_is_bare_with_its_own_system_prompt_and_no_thinking(self):
        seen = self._call(
            {"backend": "claude-cli", "model": "m", "input": "prompt"},
            {"ANTHROPIC_API_KEY": "k"},
        )
        cmd = seen["cmd"]
        self.assertIn("--bare", cmd)
        self.assertEqual(cmd[cmd.index("--system-prompt") + 1], "")
        self.assertNotIn("--append-system-prompt", cmd)
        self.assertEqual(seen["env"]["MAX_THINKING_TOKENS"], "0")
        self.assertEqual(seen["env"]["ANTHROPIC_API_KEY"], "k")

    def test_prompt_only_carries_the_callers_system_prompt(self):
        seen = self._call(
            {"backend": "claude-cli", "model": "m", "input": "prompt"},
            {"ANTHROPIC_API_KEY": "k"},
            system="Answer briefly.",
        )
        cmd = seen["cmd"]
        self.assertEqual(cmd[cmd.index("--system-prompt") + 1], "Answer briefly.")

    def test_prompt_only_without_an_api_key_is_refused_before_the_call(self):
        with self.assertRaisesRegex(ValueError, "needs ANTHROPIC_API_KEY"):
            self._call({"backend": "claude-cli", "model": "m", "input": "prompt"}, {})

    def test_the_harness_default_keeps_the_clis_own_call(self):
        seen = self._call(
            {"backend": "claude-cli", "model": "m"}, {}, system="Answer briefly."
        )
        cmd = seen["cmd"]
        self.assertNotIn("--bare", cmd)
        self.assertNotIn("--system-prompt", cmd)
        self.assertEqual(
            cmd[cmd.index("--append-system-prompt") + 1], "Answer briefly."
        )
        self.assertIsNone(seen["env"])

    def test_provenance_names_what_was_sent(self):
        with (
            mock.patch.object(
                llm,
                "spec",
                typed(
                    lambda a: {"backend": "claude-cli", "model": "m", "input": "prompt"}
                ),
            ),
            mock.patch.object(llm, "cli_version", lambda: "2.1.309"),
        ):
            prov = llm.provenance("x")
        self.assertEqual(prov["cli_input"], "prompt")
        self.assertIn("--bare", prov["cli_flags"])
        self.assertIn("MAX_THINKING_TOKENS=0", prov["cli_flags"])


if __name__ == "__main__":
    unittest.main()
