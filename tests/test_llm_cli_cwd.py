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

from labkit import llm  # noqa: E402


class CliCwd(unittest.TestCase):
    def test_spawned_from_tempdir(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen.update(kw)
            return subprocess.CompletedProcess(cmd, 0, stdout="Causal\n", stderr="")

        with mock.patch.object(llm.subprocess, "run", fake_run):
            r = llm._cli_run(["claude", "-p", "x"], timeout=5)
        self.assertEqual(r.stdout.strip(), "Causal")
        self.assertEqual(seen["cwd"], tempfile.gettempdir())
        self.assertTrue(seen["capture_output"])


class CliIsolation(unittest.TestCase):
    def test_no_settings_and_no_tools(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout="Yes\n", stderr="")

        with (
            mock.patch.object(
                llm,
                "resolve",
                lambda alias: {"backend": "claude-cli", "model": "m", "alias": alias},
            ),
            mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
            mock.patch.object(llm.subprocess, "run", fake_run),
        ):
            llm._complete_once("x", "prompt")
        cmd = seen["cmd"]
        self.assertEqual(cmd[cmd.index("--setting-sources") + 1], "")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")


if __name__ == "__main__":
    unittest.main()
