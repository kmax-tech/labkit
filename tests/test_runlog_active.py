"""Tests for `runlog._is_alive` — the question "is this run still going?".

Why this deserves tests: the working standard says what is currently running
gets **looked up, not asked about**. A wrong answer is therefore more
expensive than none — it keeps a dead run from being restarted.

Exactly that happened on 2026-08-15: `runlog` reported a run from August 13
as running because the OS had recycled its PID to a macOS service
(`RemoteManagement`). An existence check via `os.kill(pid, 0)` cannot
notice that in principle.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test

from labkit import runlog  # noqa: E402
from labkit.runlog import _command_of, _is_alive  # noqa: E402


class TestIsAlive(unittest.TestCase):

    def test_our_own_process_counts_as_alive_for_its_own_script(self):
        cmd = _command_of(os.getpid())
        self.assertIsNotNone(cmd, "ps unavailable — the test would be moot")
        token = next(t for t in cmd.split() if t)          # any real token
        self.assertTrue(_is_alive(os.getpid(), token))

    def test_a_recycled_pid_is_not_reported_as_running(self):
        """The 2026-08-15 case: the PID is alive but a different process."""
        self.assertFalse(_is_alive(os.getpid(), "05_refusal.py"))

    def test_a_dead_pid_is_false(self):
        dead = 999_999                                     # practically surely free
        try:
            os.kill(dead, 0)
        except ProcessLookupError:
            self.assertFalse(_is_alive(dead, "irgendein_skript.py"))
        except PermissionError:
            self.skipTest("PID unexpectedly taken")

    def test_unknown_is_none_not_true(self):
        """Without a script name the question is undecidable — better `None`
        than a false `True`."""
        self.assertIsNone(_is_alive(os.getpid(), None))
        self.assertIsNone(_is_alive(os.getpid(), ""))

    def test_a_missing_pid_field_is_none(self):
        self.assertIsNone(_is_alive(None, "x.py"))
        self.assertIsNone(_is_alive("81892", "x.py"))      # string, not int


if __name__ == "__main__":
    unittest.main()


class TestOutputsJson(unittest.TestCase):
    """runlog.Run.output (2026-08-18): whoever stands inside the run dir must
    be able to answer where the run wrote WITHOUT reading source code —
    config.json freezes only the INPUTS (finding by MH while reading a run)."""

    def test_registered_output_lands_in_outputs_json_with_hash(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            out = d / "output" / "x.jsonl"
            out.parent.mkdir()
            with runlog.run("t", config={}, base_dir=d) as r:
                out.write_text("a\nb\n", encoding="utf-8")
                r.output(out)
            oj = json.loads(next((d / "runs").glob("*/outputs.json")
                                 ).read_text(encoding="utf-8"))
            self.assertEqual(oj[0]["lines"], 2)
            self.assertEqual(len(oj[0]["sha256"]), 16)

    def test_a_missing_file_is_named_not_silenced(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            with runlog.run("t", config={}, base_dir=d) as r:
                r.output(d / "output" / "nie-geschrieben.jsonl")
            oj = json.loads(next((d / "runs").glob("*/outputs.json")
                                 ).read_text(encoding="utf-8"))
            self.assertIsNone(oj[0]["sha256"])
            self.assertIn("absent", oj[0]["note"])


class TestUntrackedSourceSnapshot(unittest.TestCase):
    """source-untracked/ (2026-08-18, objection by MH): the single-file
    snapshot left sibling modules unsaved — on the first run of a fresh area
    the WHOLE scripts/ folder is untracked, in no commit and no diff.
    Now: patch = tracked drift, source-untracked/ = what git does not see."""

    def _repo(self, d):
        import subprocess
        for cmd in (["git", "init", "-q"],
                    ["git", "config", "user.email", "t@t"],
                    ["git", "config", "user.name", "t"]):
            subprocess.run(cmd, cwd=d, capture_output=True)

    def test_untracked_siblings_are_copied_tracked_ones_not(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            self._repo(d)
            scripts = d / "scripts"
            scripts.mkdir()
            entry = scripts / "01_measure.py"
            entry.write_text("# entry\n")
            (scripts / "helper.py").write_text("# untracked sibling\n")
            tracked = scripts / "committed.py"
            tracked.write_text("# tracked\n")
            (scripts / "output").mkdir()
            (scripts / "output" / "x.jsonl").write_text("{}\n")
            subprocess.run(["git", "add", "scripts/committed.py"], cwd=d, capture_output=True)
            subprocess.run(["git", "commit", "-qm", "x"], cwd=d, capture_output=True)
            old_argv = sys.argv[0]
            sys.argv[0] = str(entry)
            try:
                with runlog.run("t", config={}, base_dir=d):
                    pass
            finally:
                sys.argv[0] = old_argv
            run_dir = next((d / "runs").glob("*"))
            copied = sorted(p.name for p in (run_dir / "source-untracked").rglob("*.py"))
            self.assertIn("helper.py", copied)
            self.assertIn("01_measure.py", copied)     # the entry itself is untracked too
            self.assertNotIn("committed.py", copied)   # tracked -> the diff's business
            self.assertEqual([], [p.name for p in
                                  (run_dir / "source-untracked").rglob("*.jsonl")],
                             "output/ must not enter the source snapshot")
            cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
            self.assertIn("helper.py", cfg["untracked_sources"])

    def test_outside_a_git_repo_nothing_falls_over(self):
        import sys
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            entry = d / "x.py"
            entry.write_text("# e\n")
            old_argv = sys.argv[0]
            sys.argv[0] = str(entry)
            try:
                with runlog.run("t", config={}, base_dir=d) as r:
                    r.metrics(n=1)
            finally:
                sys.argv[0] = old_argv


    def test_a_tracked_entry_does_not_trigger(self):
        # Area committed once -> from then on "commit before the run" applies,
        # not copying; a snapshot that keeps firing would hoover up data
        # (the first draft copied output/ and old runs/ along).
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            self._repo(d)
            scripts = d / "scripts"
            scripts.mkdir()
            entry = scripts / "01_measure.py"
            entry.write_text("# entry\n")
            subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True)
            subprocess.run(["git", "commit", "-qm", "x"], cwd=d, capture_output=True)
            (scripts / "later.py").write_text("# new untracked sibling\n")
            old_argv = sys.argv[0]
            sys.argv[0] = str(entry)
            try:
                with runlog.run("t", config={}, base_dir=d):
                    pass
            finally:
                sys.argv[0] = old_argv
            run_dir = next((d / "runs").glob("*"))
            self.assertFalse((run_dir / "source-untracked").exists())
