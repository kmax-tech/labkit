"""The stop hook keeps a session log: which session, which transcript, which
runs — so a run can be traced back to what the agent did before it
(2026-10-07)."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from labkit import claude_hooks


class SessionLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.transcript = self.repo / "t.jsonl"
        # 10:00 local, written as UTC the way Claude Code writes it
        start = datetime(2026, 10, 7, 10, 0, 0).astimezone()
        self.transcript.write_text(
            json.dumps({"timestamp": start.astimezone().isoformat()}) + "\n"
        )
        self.event = {"session_id": "s-1", "transcript_path": str(self.transcript)}

    def run_dir(self, stamp: str) -> None:
        (
            self.repo / "experiments" / "01-x" / "runs" / f"2026-10-07T{stamp}_ab12"
        ).mkdir(parents=True)

    def test_runs_since_the_previous_stop_only(self):
        self.run_dir("09-59-00")  # before the session
        self.run_dir("10-05-00")
        first = claude_hooks.record_session(
            self.repo, self.event, now=datetime(2026, 10, 7, 10, 10)
        )
        self.run_dir("10-20-00")
        second = claude_hooks.record_session(
            self.repo, self.event, now=datetime(2026, 10, 7, 10, 30)
        )
        assert first is not None and second is not None
        self.assertEqual(
            first["runs"], ["experiments/01-x/runs/2026-10-07T10-05-00_ab12"]
        )
        self.assertEqual(
            second["runs"], ["experiments/01-x/runs/2026-10-07T10-20-00_ab12"]
        )
        log = claude_hooks.session_log(self.repo)
        assert log is not None
        self.assertEqual(log.parent.name, ".git")  # local, never committed

    def test_a_run_finds_its_session(self):
        self.run_dir("10-05-00")
        claude_hooks.record_session(
            self.repo, self.event, now=datetime(2026, 10, 7, 10, 10)
        )
        old = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.repo)
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = claude_hooks.sessions(["--run", "2026-10-07T10-05-00_ab12"])
            with contextlib.redirect_stdout(io.StringIO()):
                miss = claude_hooks.sessions(["--run", "2026-10-07T11-00-00_ffff"])
        finally:
            if old is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old
        self.assertEqual(rc, 0)
        self.assertIn(str(self.transcript), buf.getvalue())
        self.assertEqual(miss, 1)

    def test_no_session_id_writes_nothing(self):
        self.assertIsNone(claude_hooks.record_session(self.repo, {}))


if __name__ == "__main__":
    unittest.main()
