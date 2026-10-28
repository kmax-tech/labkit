"""Tests for `runlog --wait`, `runlog start` and the run_kind='measurement' detach gate.

Why this is tested: the 2026-08-13 scar — a long run started in a Claude Code
foreground shell died with the tool timeout, which killed the whole process
group including the batch lock, twice in one evening. The mechanics that
prevent a repeat are (a) `runlog start` detaching the run into its OWN
session, so a killed starter/waiter is harmless (Detach-Probe), and (b) the
`run_kind='measurement'` gate refusing the foreground start before any work. `--wait`'s
exit codes (0 idle / 2 crashed / 3 still running) are a contract scripts
build on — a silent change would flip monitoring logic.
"""

import contextlib
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test

from labkit.formats import findings, promises, protocol_check, runs, scope_sha  # noqa: E402
from labkit.run import runlog, runlog_command  # noqa: E402
from protocol_fixture import run_record, head, scope_file  # noqa: E402


def _run_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = runlog_command.main(argv)
    return code, buf.getvalue()


class TestWait(unittest.TestCase):
    def test_idle_area_exits_0_and_names_the_last_finished_run(self):
        with tempfile.TemporaryDirectory() as d:
            done = Path(d) / "runs" / "2026-09-09T10-00-00_done"
            done.mkdir(parents=True)
            (done / "config.json").write_text(
                json.dumps(run_record()), encoding="utf-8"
            )
            (done / "metrics.json").write_text('{"c1_pass": true}', encoding="utf-8")
            (done / "completion.json").write_text("{}", encoding="utf-8")
            code, out = _run_main([d, "--wait", "--max-seconds", "1"])
            self.assertEqual(code, 0)
            self.assertIn("no open runs", out)
            self.assertIn("2026-09-09T10-00-00_done", out)

    def test_a_pre_schema_run_is_unreadable_and_ends_the_wait(self):
        """A run without schema_version ended long ago; counting it as open
        made --wait loop until --max-seconds (found porting 0.48). Since
        0.89.0 its metadata is unreadable — a failed state, exit 2, named."""
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "runs" / "2026-08-01T10-00-00_old"
            old.mkdir(parents=True)
            (old / "config.json").write_text("{}", encoding="utf-8")
            (old / "metrics.json").write_text("{}", encoding="utf-8")
            code, out = _run_main([d, "--wait", "--max-seconds", "1"])
            self.assertEqual(code, 2, out)
            self.assertIn("UNREADABLE", out)
            self.assertIn("labkit 0.47", out)

    def test_crashed_run_exits_2_and_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "runs" / "2026-09-09T10-00-00_dead"
            run_dir.mkdir(parents=True)
            (run_dir / "config.json").write_text(
                json.dumps(
                    run_record(
                        {
                            "schema_version": 4,
                            "run_kind": "measurement",
                            "pid": 999_999_99,
                            "script": "01_measure.py",
                        }
                    )
                ),
                encoding="utf-8",
            )
            code, out = _run_main([d, "--wait", "--max-seconds", "1"])
            self.assertEqual(code, 2)
            self.assertIn("CRASHED", out)
            self.assertIn("2026-09-09T10-00-00_dead", out)

    def test_a_crashed_run_names_why_it_broke_off(self):
        """2026-10-23: a claude-cli answer another model wrote ends a run
        loudly, and the reason stood on stderr alone; runlog keeps it with
        the run, and --wait names it."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(
                head(repeat_cost="low", promises=None)
                + "\n- **Question / hypothesis:** how many?\n",
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    with runlog.run("x", {"n": 1}, area, run_kind="measurement"):
                        raise RuntimeError("claude-cli: requested m, written by o, m")
                with runlog.run("x", {"n": 2}, area, run_kind="measurement") as ok:
                    ok.metrics(count=2)

            # both runs start in the same second; the run id's random suffix
            # orders them, so tell them apart by their config, not their name
            def n_of(run_dir: Path) -> int:
                config = json.loads(
                    (run_dir / "config.json").read_text(encoding="utf-8")
                )
                return config["config"]["n"]

            dead, clean = sorted((area / "runs").iterdir(), key=n_of)
            self.assertEqual(
                runs.read_failure(dead),
                "RuntimeError: claude-cli: requested m, written by o, m",
            )
            self.assertIsNone(runs.read_failure(clean))  # a clean exit leaves none
            config = json.loads((dead / "config.json").read_text(encoding="utf-8"))
            config["pid"] = 999_999_99  # the process is gone: crashed, not running
            (dead / "config.json").write_text(json.dumps(config), encoding="utf-8")
            code, out = _run_main([d, "--wait", "--max-seconds", "1"])
        self.assertEqual(code, 2, out)
        self.assertIn("broke off with RuntimeError: claude-cli: requested m", out)

    def test_running_run_exits_3_at_max_seconds(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "runs" / "2026-09-09T10-00-00_live"
            run_dir.mkdir(parents=True)
            # own pid + our real command line -> is_alive says True
            me = runs._command_of(os.getpid()) or "python"
            (run_dir / "config.json").write_text(
                json.dumps(
                    run_record(
                        {
                            "schema_version": 4,
                            "run_kind": "measurement",
                            "pid": os.getpid(),
                            "script": me.split()[0],
                        }
                    )
                ),
                encoding="utf-8",
            )
            t0 = time.monotonic()
            code, out = _run_main(
                [d, "--wait", "--max-seconds", "0.3", "--interval", "0.1"]
            )
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
            script = (
                f"import os,time,pathlib; time.sleep(0.4); "
                f"pathlib.Path({str(marker)!r}).write_text("
                f"str(os.getsid(0))); print('lived')"
            )
            cwd = os.getcwd()
            try:
                os.chdir(d)
                code, out = _run_main(
                    ["start", d, "--log", str(log), "--", sys.executable, "-c", script]
                )
            finally:
                os.chdir(cwd)
            self.assertEqual(code, 0)
            self.assertIn("started detached", out)
            for _ in range(50):  # wait for the marker
                if marker.exists():
                    break
                time.sleep(0.1)
            self.assertTrue(marker.exists(), "detached child never finished")
            child_sid = int(marker.read_text())
            self.assertNotEqual(
                child_sid, os.getsid(0), "child shares our session — not detached"
            )
            self.assertIn("lived", log.read_text(encoding="utf-8"))

    def test_start_sets_the_detached_acknowledgement_for_the_gate(self):
        with tempfile.TemporaryDirectory() as d:
            probe = Path(d) / "env.txt"
            script = (
                f"import os,pathlib; pathlib.Path({str(probe)!r})"
                f".write_text(os.environ.get('LABKIT_DETACHED',''))"
            )
            cwd = os.getcwd()
            try:
                os.chdir(d)
                code, _ = _run_main(
                    [
                        "start",
                        d,
                        "--log",
                        str(Path(d) / "l.log"),
                        "--",
                        sys.executable,
                        "-c",
                        script,
                    ]
                )
            finally:
                os.chdir(cwd)
            self.assertEqual(code, 0)
            for _ in range(50):
                if probe.exists():
                    break
                time.sleep(0.1)
            self.assertEqual(probe.read_text(), "1")


class TestStartWaitsForTheRun(unittest.TestCase):
    """`runlog start` returned at once, so `runlog AREA --wait` right after it
    saw no open run and exited 0 before the child made its directory
    (review 2026-10-27). It returns once the run exists, says when the
    command ended first, and gives up with exit 3."""

    def _start(self, d: str, script: str, *more: str) -> tuple[int, str]:
        """`runlog start D … -- python -c SCRIPT` from D; stdout and stderr."""
        cwd = os.getcwd()
        err = io.StringIO()
        argv = ["start", d, "--log", str(Path(d) / "l.log"), *more, "--"]
        try:
            os.chdir(d)
            with contextlib.redirect_stderr(err):
                code, out = _run_main([*argv, sys.executable, "-c", script])
        finally:
            os.chdir(cwd)
        return code, out + err.getvalue()

    def test_it_returns_once_the_run_directory_exists(self):
        with tempfile.TemporaryDirectory() as d:
            record = Path(d) / "record.json"
            record.write_text(json.dumps(run_record()), encoding="utf-8")
            run = Path(d) / "runs" / "2026-10-27T20-00-00_late"
            script = (
                "import time, shutil, pathlib; time.sleep(0.6); "
                f"d = pathlib.Path({str(run)!r}); d.mkdir(parents=True); "
                "time.sleep(0.3); "
                f"shutil.copy({str(record)!r}, d / 'config.json'); time.sleep(0.3)"
            )
            code, out = self._start(d, script)
            self.assertEqual(code, 0, out)
            self.assertTrue((run / "config.json").is_file(), out)
            self.assertIn(f"run: {run.name}", out)

    def test_a_command_that_fails_first_is_named_with_its_log(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._start(d, "import sys; print('boom'); sys.exit(3)")
            self.assertEqual(code, 2, out)
            self.assertIn("ended with exit 3 before its run existed", out)
            self.assertIn("boom", out)

    def test_a_command_without_a_run_ends_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._start(d, "print('no run')")
            self.assertEqual(code, 0, out)
            self.assertIn("without a run", out)

    def test_still_starting_after_max_seconds_is_exit_3(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._start(
                d, "import time; time.sleep(5)", "--max-seconds", "0.5"
            )
            self.assertEqual(code, 3, out)
            self.assertIn("still starting", out)


class TestWaitSeesADetachedStart(unittest.TestCase):
    """`runlog start` stopped waiting after --max-seconds while its command
    still prepared rows before `runlog.run` opened the record; `runlog AREA
    --wait` then saw no open run and said "no open runs", exit 0, four
    seconds before the run opened (labkit-paper area 15, round 2, t21, D6).
    A command `runlog start` detached counts until it ends."""

    def _start(self, d: str, script: Path) -> tuple[int, str]:
        cwd = os.getcwd()
        argv = ["start", d, "--log", str(Path(d) / "l.log"), "--max-seconds", "0.3"]
        try:
            os.chdir(d)
            code, out = _run_main([*argv, "--", sys.executable, str(script)])
        finally:
            os.chdir(cwd)
        return code, out

    def test_the_area_is_not_idle_while_the_started_command_has_no_record(self):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "01_measure.py"
            script.write_text("import time\ntime.sleep(2.5)\n", encoding="utf-8")
            code, out = self._start(d, script)
            self.assertEqual(code, 3, out)  # still starting, no run yet
            pid = out.split("pid=")[1].split()[0]
            code, out = _run_main(
                [d, "--wait", "--max-seconds", "0.4", "--interval", "0.1"]
            )
            self.assertEqual(code, 3, out)
            self.assertIn("still running", out)
            self.assertIn(f"pid={pid}", out)
            code, out = _run_main([d])
            self.assertEqual(code, 0, out)
            self.assertNotIn("no open runs", out)
            self.assertIn(f"pid={pid}", out)
            self.assertIn("(detached)  starting", out)
            self.assertIn("no run record yet", out)
            # the twin: once the command ended, the area is idle again
            code, out = _run_main(
                [d, "--wait", "--max-seconds", "20", "--interval", "0.1"]
            )
            self.assertEqual(code, 0, out)
            self.assertIn("no open runs", out)
            code, out = _run_main([d])
            self.assertIn("no open runs", out)

    def test_a_record_runs_while_held_and_without_exit(self):
        """A record runs while its lock is held and its exit is null; it
        ended once the exit is written or the lock is free (exit not
        recorded). One that does not read is refused with its way out; what
        was read as ended is removed while its file holds what was read, a
        running one never."""
        import fcntl

        from labkit.formats import console
        from labkit.run import detached

        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            detached._folder(area).mkdir(parents=True, exist_ok=True)

            def record(pid: int, exit_status: int | None) -> Path:
                path = detached._record_path(area, pid)
                data = {"pid": pid, "command": ["python", "x.py"], "log": "l.log",
                        "started": "2026-10-28T17:00:00", "supervisor": 1,
                        "exit": exit_status}  # fmt: skip
                path.write_text(json.dumps(data), encoding="utf-8")
                return path

            running, done, gone = record(11, None), record(12, 3), record(13, None)
            with running.open("rb") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)  # what the supervisor's descriptor holds
                got = {s.pid: (s.running, s.exit) for s in detached.starts(area)}
                self.assertEqual(
                    got, {11: (True, None), 12: (False, 3), 13: (False, None)}
                )
                self.assertEqual(
                    detached.exit_words(detached.starts(area)[2]),
                    "exit not recorded (its supervisor ended first)",
                )
                read = detached.starts(area)
                with self.assertRaisesRegex(ValueError, "read as running"):
                    detached.remove_read(read)  # a running one is never removed
                ended = [s for s in read if not s.running]
                # rewritten since the read (a new start under the same pid): kept
                gone.write_text(
                    gone.read_text(encoding="utf-8") + " ", encoding="utf-8"
                )
                detached.remove_read(ended)
                self.assertEqual([p.exists() for p in (running, done, gone)],
                                 [True, False, True])  # fmt: skip
                running.write_text('{"pid": "11"}', encoding="utf-8")
                with self.assertRaises(console.Refused) as cm:
                    detached.starts(area)
                self.assertIn("command is None", cm.exception.why)
                self.assertIn(f"way out: remove it (`rm {running}`)", cm.exception.why)

    def test_a_command_that_cannot_start_is_refused_and_leaves_no_record(self):
        from labkit.run import detached

        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code, out = _run_main(
                    ["start", d, "--log", str(area / "l.log"), "--",
                     str(area / "no-such-command")]
                )  # fmt: skip
            self.assertEqual(code, 2, out + err.getvalue())
            self.assertIn("could not be started (exit 127)", err.getvalue())
            self.assertIn(
                "cannot run", err.getvalue()
            )  # the supervisor's reason, in the log
            self.assertEqual(
                list(detached._folder(area).glob(f"{detached._key(area)}-*")), []
            )

    def test_a_started_command_whose_run_is_open_is_that_run(self):
        """The twin: once the run names the started pid, status shows the
        run and nothing beside it, and --wait still waits for it."""
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "01_measure.py"
            run_dir = Path(d) / "runs" / "2026-10-28T17-23-36_open"
            record = run_record({"run_kind": "measurement", "script": "01_measure.py"})
            script.write_text(
                "import json, os, pathlib, time\n"
                f"d = pathlib.Path({str(run_dir)!r}); d.mkdir(parents=True)\n"
                f"record = {record!r}\n"
                "record['pid'] = os.getpid()\n"
                "(d / 'config.json').write_text(json.dumps(record))\n"
                "time.sleep(2)\n",
                encoding="utf-8",
            )
            code, out = self._start(d, script)
            self.assertEqual(code, 0, out)
            self.assertIn(f"run: {run_dir.name}", out)
            code, out = _run_main([d])
            self.assertIn(run_dir.name, out)
            self.assertNotIn("no run record yet", out)
            code, out = _run_main(
                [d, "--wait", "--max-seconds", "0.3", "--interval", "0.1"]
            )
            self.assertEqual(code, 3, out)
            self.assertIn(run_dir.name, out)


def _start_in(d: str, *command: str, max_seconds: str = "0.3") -> tuple[int, str]:
    """`runlog start D --log D/l.log --max-seconds S -- COMMAND` from D;
    stdout and stderr."""
    cwd = os.getcwd()
    err = io.StringIO()
    argv = ["start", d, "--log", str(Path(d) / "l.log"), "--max-seconds", max_seconds]
    try:
        os.chdir(d)
        with contextlib.redirect_stderr(err):
            code, out = _run_main([*argv, "--", *command])
    finally:
        os.chdir(cwd)
    return code, out + err.getvalue()


def _run_script(run_dir: Path, *, finished: bool, then: str) -> str:
    """A script that opens a run record in RUN_DIR naming its own pid —
    completed when FINISHED, else left open — and then runs THEN."""
    record = run_record({"run_kind": "measurement", "script": "01_measure.py"})
    done = (
        "(d / 'metrics.json').write_text('{}'); (d / 'completion.json').write_text('{}')\n"
        if finished
        else ""
    )
    return (
        "import json, os, pathlib, sys, time\n"
        "from labkit.formats.runs import now_stamp\n"
        f"d = pathlib.Path({str(run_dir)!r}); d.mkdir(parents=True)\n"
        f"record = {record!r}\n"
        "record.update(pid=os.getpid(), started=now_stamp())\n"
        "(d / 'config.json').write_text(json.dumps(record))\n" + done + then + "\n"
    )


def _wait_for(d: str, max_seconds: str = "20") -> tuple[int, str]:
    return _run_main([d, "--wait", "--max-seconds", max_seconds, "--interval", "0.1"])


class TestAStartThatEndsWithoutARunIsAFailure(unittest.TestCase):
    """The started command died while it prepared its rows: `runlog AREA
    --wait` said "no open runs — no finished runs", exit 0, and the error
    stood in the log alone (review of D6, 2026-10-28). A started command
    that ended without a run record, and not with exit 0, is a failed
    state: `--wait` exits 2 naming its exit and log, the status names it,
    until the next `runlog start` in the area says it once more and clears
    it."""

    def test_a_command_that_dies_while_preparing_fails_the_wait(self):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "01_measure.py"
            script.write_text("import sys, time\ntime.sleep(0.8)\nsys.exit(3)\n")
            code, out = _start_in(d, sys.executable, str(script))
            self.assertEqual(code, 3, out)  # still preparing when start gave up
            code, out = _wait_for(d)
            self.assertEqual(code, 2, out)
            self.assertIn("ENDED", out)
            self.assertIn("exit 3 without a run record", out)
            self.assertIn(f"check the log: {Path(d) / 'l.log'}", out)
            code, out = _wait_for(d, "1")
            self.assertEqual(code, 2, out)  # it stays a failure
            code, out = _run_main([d])
            self.assertNotIn("no open runs", out)
            self.assertIn("exit 3 without a run record — check the log", out)
            code, out = _start_in(d, sys.executable, "-c", "print(1)", max_seconds="5")
            self.assertEqual(code, 0, out)
            self.assertIn("earlier start, cleared now", out)
            self.assertIn("exit 3 without a run record", out)
            code, out = _wait_for(d)
            self.assertEqual(code, 0, out)  # exit 0 without a run: nothing failed
            self.assertIn("no open runs", out)

    def test_a_command_killed_before_its_record_names_the_signal(self):
        import signal

        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "01_measure.py"
            script.write_text("import time\ntime.sleep(30)\n")
            code, out = _start_in(d, sys.executable, str(script))
            self.assertEqual(code, 3, out)
            os.kill(int(out.split("pid=")[1].split()[0]), signal.SIGKILL)
            code, out = _wait_for(d)
            self.assertEqual(code, 2, out)
            self.assertIn(
                f"killed by signal {int(signal.SIGKILL)} without a run record", out
            )

    def test_a_start_clears_only_the_failures_it_read_and_showed(self):
        """Display and cleanup read the records apart: a command that ended
        between the two reads lost its record unseen — an exit 7 neither
        shown nor kept (review of 6e7e06b, 2026-10-28). The order is made
        here: the start's display read sees the command running, then its
        supervisor writes exit 7. It stays for the next `runlog AREA` and
        `--wait` (exit 2), its log untouched. The twin: the failure the
        start read and showed (exit 3) is cleared and not shown again."""
        import fcntl
        from unittest import mock

        from labkit.formats.files import write_atomic
        from labkit.run import detached

        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            detached._folder(area).mkdir(parents=True, exist_ok=True)
            log7 = area / "seven.log"
            log7.write_text("rows failed: exit 7\n", encoding="utf-8")

            def record(pid: int, exit_status: int | None, log: Path) -> Path:
                path = detached._record_path(area, pid)
                data = {"pid": pid, "command": ["python", f"{pid}.py"], "log": str(log),
                        "started": "2026-10-28T17:00:00", "supervisor": 1,
                        "exit": exit_status}  # fmt: skip
                path.write_text(json.dumps(data), encoding="utf-8")
                return path

            record(3, 3, area / "three.log")  # ended before the start: shown, cleared
            seven = record(7, None, log7)  # still running at the start's read
            lock = seven.open("rb")
            fcntl.flock(lock, fcntl.LOCK_EX)  # what the supervisor's descriptor holds
            real = detached.starts
            reads: list[int] = []

            def starts_then_the_command_ends(at: Path) -> list[detached.DetachedStart]:
                read = real(at)
                reads.append(len(read))
                if len(reads) == 1:  # the display read of `runlog start`
                    data = json.loads(seven.read_text(encoding="utf-8"))
                    write_atomic(seven, json.dumps({**data, "exit": 7}))
                    lock.close()  # the supervisor ends
                return read

            with mock.patch.object(detached, "starts", starts_then_the_command_ends):
                code, out = _start_in(
                    d, sys.executable, "-c", "print(1)", max_seconds="5"
                )
            self.assertEqual(code, 0, out)
            self.assertIn("earlier start, cleared now", out)
            self.assertIn("exit 3 without a run record", out)
            self.assertNotIn("exit 7", out)  # not read as ended, so not shown
            code, out = _run_main([d])
            self.assertIn("exit 7 without a run record", out)
            self.assertNotIn("exit 3", out)  # the shown one is gone
            code, out = _wait_for(d, "5")
            self.assertEqual(code, 2, out)
            self.assertIn(f"exit 7 without a run record — check the log: {log7}", out)
            self.assertNotIn("exit 3", out)
            self.assertEqual(log7.read_text(encoding="utf-8"), "rows failed: exit 7\n")
            code, out = _start_in(d, sys.executable, "-c", "print(1)", max_seconds="5")
            self.assertIn("earlier start, cleared now", out)  # shown now, cleared now
            self.assertIn("exit 7 without a run record", out)
            self.assertEqual(_wait_for(d, "5")[0], 0)
            self.assertTrue(log7.is_file())

    def test_a_command_whose_run_record_names_it_tells_the_runs_state(self):
        """The twins: a bound run that completed leaves the area idle, though
        the command exits 1 after it; a bound run that crashed is that run's
        CRASHED line, no ENDED line beside it."""
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "runs" / "2026-10-28T20-00-00_done"
            script = Path(d) / "01_measure.py"
            script.write_text(_run_script(run_dir, finished=True, then="sys.exit(1)"))
            code, out = _start_in(d, sys.executable, str(script), max_seconds="5")
            self.assertEqual(code, 0, out)
            code, out = _wait_for(d)
            self.assertEqual(code, 0, out)
            self.assertIn(run_dir.name, out)
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "runs" / "2026-10-28T20-00-00_dead"
            script = Path(d) / "01_measure.py"
            script.write_text(_run_script(run_dir, finished=False, then="sys.exit(1)"))
            code, out = _start_in(d, sys.executable, str(script), max_seconds="5")
            self.assertEqual(code, 0, out)
            code, out = _wait_for(d)
            self.assertEqual(code, 2, out)
            self.assertIn("CRASHED", out)
            self.assertNotIn("ENDED", out)


class TestAWrapperIsNamedForWhatItIs(unittest.TestCase):
    """A wrapper process's run records another pid; beside that open run
    the wrapper read "starting … no run record yet", like a second run still
    to come (review of D6, 2026-10-28). It reads as a started process still
    active and matched to no open run by its pid; with no open run at all it
    still reads "no run record yet"
    (`test_the_area_is_not_idle_while_the_started_command_has_no_record`)."""

    def test_a_wrapper_beside_its_open_run_is_matched_to_no_run_by_its_pid(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "runs" / "2026-10-28T20-00-00_open"
            script = Path(d) / "01_measure.py"
            script.write_text(
                _run_script(run_dir, finished=False, then="time.sleep(2)")
            )
            # `; true` keeps the shell from replacing itself with python
            wrapper = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}; true"
            code, out = _start_in(d, "sh", "-c", wrapper, max_seconds="5")
            self.assertEqual(code, 0, out)
            self.assertIn(f"run: {run_dir.name}", out)
            code, out = _run_main([d])
            self.assertIn(run_dir.name, out)
            matched = "started process still active; matched to no open run by its pid"
            self.assertIn(matched, out)
            self.assertIn("(detached)  active", out)
            self.assertNotIn("no run record yet", out)
            code, out = _wait_for(d, "0.3")
            self.assertEqual(code, 3, out)
            self.assertIn(matched, out)


class TestTheLabRootIsNoArea(unittest.TestCase):
    def test_runlog_on_the_lab_root_refuses(self):
        # `runlog .` from the root read the repo as an area: "no open runs",
        # and --wait idle while a measurement ran (audit 2026-10-27, third, I10)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "experiments" / "01-x").mkdir(parents=True)
            for argv in ([d], [d, "--wait", "--max-seconds", "1"]):
                with self.subTest(argv=argv):
                    err = io.StringIO()
                    with contextlib.redirect_stderr(err):
                        code, out = _run_main(argv)
                    self.assertEqual(code, 2, out + err.getvalue())
                    self.assertIn("is the lab root", err.getvalue())
            code, _ = _run_main([str(Path(d) / "experiments" / "01-x")])
            self.assertEqual(code, 0)


class TestStartNamesTheArea(unittest.TestCase):
    """The area is named, not guessed: the default log lands in its output/,
    and the printed wait command names it. Before, the log went to output/
    under the working directory, and a cold agent started from the repo root
    looked for it in the area (cloud judge probe, 2026-10-14)."""

    def test_the_default_log_lands_in_the_area(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d) / "experiments" / "01-x"
            area.mkdir(parents=True)
            cwd = os.getcwd()
            try:
                os.chdir(d)
                code, out = _run_main(
                    [
                        "start",
                        "experiments/01-x",
                        "--",
                        sys.executable,
                        "-c",
                        "print(1)",
                    ]
                )
            finally:
                os.chdir(cwd)
            self.assertEqual(code, 0)
            self.assertIn("wait:  runlog experiments/01-x --wait", out)
            self.assertEqual(len(list((area / "output").glob("start-*.log"))), 1)
            self.assertFalse((Path(d) / "output").exists())

    def test_a_missing_area_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            try:
                os.chdir(d)
                with self.assertRaises(SystemExit) as cm:
                    with contextlib.redirect_stderr(io.StringIO()):
                        _run_main(["start", "--", sys.executable, "-c", "print(1)"])
            finally:
                os.chdir(cwd)
            self.assertEqual(cm.exception.code, 2)


class TestLongGate(unittest.TestCase):
    def _spawn(self, extra_env):
        """Run a minimal run_kind='measurement' run in a subprocess with a chosen env."""
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]);\n"
            "from labkit.run import runlog\n"
            "with runlog.run('gate-probe', config={}, base_dir='.',"
            " run_kind='measurement'):\n"
            "    pass\n"
        )
        env = {**os.environ, **extra_env}
        env.pop("LABKIT_DETACHED", None)
        env.update(extra_env)
        with tempfile.TemporaryDirectory() as d:
            # run_kind='measurement' also passes the freeze gate (2026-10-05): the run
            # needs a frozen, audited protocol, or it is refused for a
            # different reason than the one this test is about.
            scope_file(Path(d))  # the frozen fixture's block names it
            sha = scope_sha.area_stamp(Path(d))[0]
            text = head(frozen=True, preflight_audit="x")
            # a decided record of this code and these promises, named in the
            # head: since 0.99.0 the field names an audit, `n/a` is refused
            record = findings.write(
                Path(d),
                "preflight",
                "opus",
                sha,
                promises.block_stamp(text),
                (0, 0, 0),
                [],
                registration=protocol_check.registration_stamp(text),
            )
            text = head(frozen=True, preflight_audit=record.name)
            Path(d, "PROTOCOL-gate.md").write_text(text, encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-c", code, str(Path(__file__).resolve().parents[1])],
                cwd=d,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )

    def test_long_run_in_claude_foreground_is_refused(self):
        r = self._spawn({"CLAUDECODE": "1"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("runlog start", r.stderr)

    def test_long_run_with_detach_acknowledged_proceeds(self):
        r = self._spawn(
            {"CLAUDECODE": "1", "LABKIT_DETACHED": "1", "LABKIT_NOTIFY": "0"}
        )
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
