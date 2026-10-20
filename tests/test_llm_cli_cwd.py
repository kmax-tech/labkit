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
from llm_fixture import typed  # noqa: E402

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
            return subprocess.CompletedProcess(
                cmd, 0, stdout='{"result": "Yes"}\n', stderr=""
            )

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
            return subprocess.CompletedProcess(
                cmd, 0, stdout='{"result": "Yes"}\n', stderr=""
            )

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


if __name__ == "__main__":
    unittest.main()
