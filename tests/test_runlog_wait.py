"""Tests for `runlog --wait`, `runlog start` and the long=True detach gate.

Why this is tested: the 2026-08-13 scar — a long run started in a Claude Code
foreground shell died with the tool timeout, which killed the whole process
group including the batch lock, twice in one evening. The mechanics that
prevent a repeat are (a) `runlog start` detaching the run into its OWN
session, so a killed starter/waiter is harmless (Detach-Probe), and (b) the
`long=True` gate refusing the foreground start before any work. `--wait`'s
exit codes (0 idle / 2 crashed / 3 still running) are a contract scripts
build on — a silent change would flip monitoring logic.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test

from labkit import runlog  # noqa: E402


def _run_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = runlog.main(argv)
    return code, buf.getvalue()


class TestWait(unittest.TestCase):

    def test_idle_area_exits_0_and_names_the_last_finished_run(self):
        with tempfile.TemporaryDirectory() as d:
            done = Path(d) / "runs" / "2026-09-09T10-00-00_done"
            done.mkdir(parents=True)
            (done / "config.json").write_text("{}", encoding="utf-8")
            (done / "metrics.json").write_text('{"k1": true}', encoding="utf-8")
            code, out = _run_main([d, "--wait", "--max-seconds", "1"])
            self.assertEqual(code, 0)
            self.assertIn("no open runs", out)
            self.assertIn("2026-09-09T10-00-00_done", out)

    def test_crashed_run_exits_2_and_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "runs" / "2026-09-09T10-00-00_dead"
            run_dir.mkdir(parents=True)
            (run_dir / "config.json").write_text(json.dumps(
                {"pid": 999_999_99, "script": "01_measure.py"}),
                encoding="utf-8")
            code, out = _run_main([d, "--wait", "--max-seconds", "1"])
            self.assertEqual(code, 2)
            self.assertIn("CRASHED", out)
            self.assertIn("2026-09-09T10-00-00_dead", out)

    def test_running_run_exits_3_at_max_seconds(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "runs" / "2026-09-09T10-00-00_live"
            run_dir.mkdir(parents=True)
            # own pid + our real command line -> _is_alive says True
            me = runlog._command_of(os.getpid()) or "python"
            (run_dir / "config.json").write_text(json.dumps(
                {"pid": os.getpid(), "script": me.split()[0]}),
                encoding="utf-8")
            t0 = time.monotonic()
            code, out = _run_main([d, "--wait", "--max-seconds", "0.3",
                                   "--interval", "0.1"])
            self.assertEqual(code, 3)
            self.assertIn("still running", out)
            self.assertLess(time.monotonic() - t0, 5)


class TestStartDetaches(unittest.TestCase):

    def test_child_runs_in_its_own_session_and_survives_to_completion(self):
        """Detach-Probe (K4+K5): the started command has a session of its own
        — killing the starter's group cannot take it down — and it finishes
        (marker file appears) with its output captured in the log."""
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / "done.txt"
            log = Path(d) / "start.log"
            script = (f"import os,time,pathlib; time.sleep(0.4); "
                      f"pathlib.Path({str(marker)!r}).write_text("
                      f"str(os.getsid(0))); print('lived')")
            cwd = os.getcwd()
            try:
                os.chdir(d)
                code, out = _run_main(["start", "--log", str(log), "--",
                                       sys.executable, "-c", script])
            finally:
                os.chdir(cwd)
            self.assertEqual(code, 0)
            self.assertIn("started detached", out)
            for _ in range(50):                      # wait for the marker
                if marker.exists():
                    break
                time.sleep(0.1)
            self.assertTrue(marker.exists(), "detached child never finished")
            child_sid = int(marker.read_text())
            self.assertNotEqual(child_sid, os.getsid(0),
                                "child shares our session — not detached")
            self.assertIn("lived", log.read_text(encoding="utf-8"))

    def test_start_sets_the_detached_acknowledgement_for_the_gate(self):
        with tempfile.TemporaryDirectory() as d:
            probe = Path(d) / "env.txt"
            script = (f"import os,pathlib; pathlib.Path({str(probe)!r})"
                      f".write_text(os.environ.get('LABKIT_DETACHED',''))")
            cwd = os.getcwd()
            try:
                os.chdir(d)
                code, _ = _run_main(["start", "--log", str(Path(d) / "l.log"),
                                     "--", sys.executable, "-c", script])
            finally:
                os.chdir(cwd)
            self.assertEqual(code, 0)
            for _ in range(50):
                if probe.exists():
                    break
                time.sleep(0.1)
            self.assertEqual(probe.read_text(), "1")


class TestLongGate(unittest.TestCase):

    def _spawn(self, extra_env):
        """Run a minimal long=True run in a subprocess with a chosen env."""
        code = ("import sys; sys.path.insert(0, sys.argv[1]);\n"
                "from labkit import runlog\n"
                "with runlog.run('gate-probe', config={}, base_dir='.',"
                " long=True):\n"
                "    pass\n")
        env = {**os.environ, **extra_env}
        env.pop("LABKIT_DETACHED", None)
        env.update(extra_env)
        with tempfile.TemporaryDirectory() as d:
            # long=True also passes the freeze gate (2026-10-05): the run
            # needs a frozen, audited protocol, or it is refused for a
            # different reason than the one this test is about.
            Path(d, "PROTOCOL-gate.md").write_text(
                "- **Protocol id:** p-0123456789abcdef\n"
                "- **Preflight audit:** 2026-10-05 · abc · 0 findings\n"
                "- **Frozen before run:** yes\n", encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-c", code,
                 str(Path(__file__).resolve().parents[1])],
                cwd=d, env=env, capture_output=True, text=True, timeout=30)

    def test_long_run_in_claude_foreground_is_refused(self):
        r = self._spawn({"CLAUDECODE": "1"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("runlog start", r.stderr)

    def test_long_run_with_detach_acknowledged_proceeds(self):
        r = self._spawn({"CLAUDECODE": "1", "LABKIT_DETACHED": "1",
                         "LABKIT_NOTIFY": "0"})
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
