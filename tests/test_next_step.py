"""labkit-next — one next step per state of an area, read from the gates.

The counting skeleton walked through the chain: at every station the
step named is the command that moves it on, and taking it moves the area
to the next station.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shlex
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats.evidence import read_evidence
from labkit.gates import registered_report
from labkit.formats.area_state import state_of
from labkit.tools import report_command
from labkit.checks.report_review_inputs import review_keys, review_pieces  # noqa: E402
from labkit.formats import protocol_block, report_reviews  # noqa: E402
from labkit.formats import area_state  # noqa: E402
from labkit.formats.gate import GateFinding  # noqa: E402
from labkit.formats.repo import state_text  # noqa: E402
from labkit.gates import report_check, report_hold  # noqa: E402
from labkit.gates import undecided
from labkit.gates.report_review import discussed_under  # noqa: E402
from labkit.formats import standard_contract as sc  # noqa: E402
from labkit.gates import next_step  # noqa: E402
from labkit.tools import next_command, protocol_fill  # noqa: E402
from test_end_to_end import Lab, stamp_count  # noqa: E402


def run_next(area: Path, cwd: Path) -> tuple[int, str, str]:
    """`labkit-next AREA` from CWD: exit code, stdout, stderr."""
    out, err = io.StringIO(), io.StringIO()
    old = Path.cwd()
    os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = next_command.main([str(area)])
    finally:
        os.chdir(old)
    return rc, out.getvalue(), err.getvalue()


class BareNextFindsTheArea(unittest.TestCase):
    """`labkit-next` without an area speaks of the repo's one area, numbered
    or not (`repo.experiment_areas`); a folder without a protocol, the
    stamp's `experiments/explore/`, is no area."""

    def test_an_unnumbered_area_is_the_one_area(self):
        from labkit.formats import repo

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "experiments" / "explore").mkdir(parents=True)
            area = root / "experiments" / "lines"
            area.mkdir()
            self.assertEqual(repo.experiment_areas(root), [])
            (area / "PROTOCOL-lines.md").write_text("# x\n", encoding="utf-8")
            self.assertEqual(repo.experiment_areas(root), [area])
            (root / "experiments" / "02-other").mkdir()
            self.assertEqual(
                repo.experiment_areas(root), [root / "experiments" / "02-other", area]
            )


class OneChainPerHold(unittest.TestCase):
    """The stop, the commit and report-check's hook entry run report-check's
    chain once per protocol: `next`'s step reads the chain the hold found
    rather than running the nested finalize (the area's tests,
    `02_analyze.py --check`) again inside the stop's budget. The twin:
    `next` alone runs it once."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = stamp_count(self.lab)
        root = self.lab.root
        run_id = self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        self.lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        self.lab.conclude(self.protocol)
        rc, out = self.lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        self.lab.commit("adopted")
        # the code changed under the adopted number: report-check holds it
        self.measure = self.area / "scripts" / "01_measure.py"
        self.measure.write_text(
            self.measure.read_text(encoding="utf-8") + "\n# changed after it\n",
            encoding="utf-8",
        )
        self.rel = self.measure.relative_to(root).as_posix()

    def counted(self, fn):
        """Run FN with report-check's chain counted: (FN's result, its
        stdout, how often the chain ran)."""
        calls: list[Path] = []
        real = report_check.chain_gaps

        def counting(ctx, **kw):
            calls.append(ctx.protocol)
            return real(ctx, **kw)

        out = io.StringIO()
        with (
            contextlib.chdir(self.lab.root),
            mock.patch.object(report_check, "chain_gaps", counting),
            contextlib.redirect_stdout(out),
        ):
            result = fn()
        return result, out.getvalue(), len(calls)

    def test_the_hook_entry_runs_the_chain_once_and_names_the_step(self):
        code, out, runs = self.counted(
            lambda: report_command.main(["--if-reported", self.rel])
        )
        self.assertEqual(code, 1, out)
        self.assertEqual(runs, 1, out)
        self.assertIn("labkit-next: experiments/01-lines", out)
        self.assertIn("--withdraw", out)

    def test_the_commit_runs_the_chain_once_and_names_the_step(self):
        from labkit.gates import agent_hooks

        self.lab.git("add", "-A")
        code, out, runs = self.counted(lambda: agent_hooks.commit_gates([]))
        self.assertEqual(code, 1, out)
        self.assertEqual(runs, 1, out)
        self.assertIn("labkit-next: experiments/01-lines", out)

    def test_the_stop_runs_the_chain_once_and_names_the_step(self):
        (code, err), _, runs = self.counted(self.lab.stop_hook)
        self.assertEqual(code, 2, err)
        self.assertEqual(runs, 1, err)
        self.assertIn("report-check holds a number", err)
        self.assertIn("labkit-next: experiments/01-lines", err)

    def test_the_twin_next_alone_runs_the_chain_once(self):
        step, _, runs = self.counted(
            lambda: next_step.next_step(self.area, self.protocol.resolve())
        )
        self.assertEqual(runs, 1)
        self.assertIn("--withdraw", step.next)


class SilentCollectors(unittest.TestCase):
    """A gate run inside another tells every line through the collector it
    is handed: a silent one writes nothing to stdout or stderr — the pre-run
    hook's answer is its own output. The twin: the console collector of the
    same call prints."""

    def test_preflight_tells_nothing_past_a_silent_collector(self):
        from labkit.formats.gate import Findings
        from labkit.gates import preflight

        lab = Lab()
        self.addCleanup(lab.close)
        area, protocol = stamp_count(lab)
        for tell, prints in ((None, False), (print, True)):
            out, err = io.StringIO(), io.StringIO()
            with (
                contextlib.chdir(lab.root),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(err),
            ):
                preflight.preflight_area(area, protocol, Findings(tell))
            with self.subTest(silent=tell is None):
                self.assertEqual(bool(out.getvalue()), prints, out.getvalue())
                self.assertEqual(err.getvalue(), "")


class TheChain(unittest.TestCase):
    """At each station the step is the one the chain owes next."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        cls.area, cls.protocol = stamp_count(cls.lab)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def step(self) -> next_step.Step:
        old = Path.cwd()
        os.chdir(self.lab.root)
        try:
            chosen = self.protocol.resolve()
            return next_step.next_step(self.area, chosen)
        finally:
            os.chdir(old)

    def test_the_walk_from_registered_to_adopted(self):
        # registered, not measured: measure; no report registered: how to
        # register one, before the first measurement only
        step = self.step()
        self.assertIn("01_measure.py", step.next, step)
        self.assertIn(
            '"report=REPORT.md"` — before the first measurement only', step.next
        )
        self.assertIn("blocker(s) stand, and this is the first", step.held)
        run_id = self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        # measured, no analysis audit: audit the run that answers; no report
        # registered, so no progress account and no registration hint
        step = self.step()
        self.assertNotIn("report=REPORT.md", step.next)
        self.assertNotIn("--discuss", step.next)
        self.assertIn("labkit-audit", step.next, step)
        self.assertIn("--mode analysis", step.next, step)
        # the slot a check leaves is filled, as a gate fills it
        self.assertNotIn("<area>", step.where + step.next)
        self.lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        # audited, the Conclusion open: the adoption owes it, so next names
        # it before the adoption
        step = self.step()
        self.assertIn("adopting " + run_id + " would owe 1 field(s)", step.where)
        self.assertIn('"Conclusion=<value>"` fills the first', step.next)
        self.assertNotIn("labkit-adopt experiments/01-lines", step.next)
        self.lab.conclude(self.protocol)
        # concluded, nothing holds: adopt that run
        step = self.step()
        self.assertIn(f"labkit-adopt experiments/01-lines {run_id}", step.next, step)
        self.assertIn("no run is adopted yet", step.where)
        rc, out = self.lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        # adopted, nothing holds: nothing owed
        step = self.step()
        self.assertIn(f"has adopted {run_id}", step.where)
        self.assertTrue(step.next.startswith("nothing"), step)
        self.assertEqual(step.held, "")
        # a report citing the adopted run without its block is what the hooks
        # hold: named here first
        report = self.lab.root / "REPORT.md"
        report.write_text(f"The mean is 3.0 (run {run_id}).\n", encoding="utf-8")
        self.addCleanup(report.unlink, missing_ok=True)
        step = self.step()
        self.assertIn("REPORT.md cites", step.where)
        self.assertIn("--into", step.next)
        rc = protocol_fill.main([str(self.protocol), "--into", str(report)])
        self.assertEqual(rc, 0)
        self.assertTrue(self.step().next.startswith("nothing"))  # the twin

    def test_an_open_run_is_the_step_before_any_other(self):
        """A run still open is not nothing: labkit-next does not send the
        agent to measure again beside it. The twin: a run that broke off
        (failure.json) is not open."""
        import json

        from labkit.formats import runs
        from protocol_fixture import run_record

        me = runs._command_of(os.getpid()) or "python"
        run_dir = self.area / "runs" / "2026-11-01T15-19-06_368b"
        run_dir.mkdir(parents=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(run_dir))
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
        step = self.step()
        self.assertIn("2026-11-01T15-19-06_368b is still running", step.where)
        self.assertIn("--wait", step.next)
        (run_dir / runs.FAILURE_FILE).write_text(
            json.dumps({"error": "RuntimeError", "message": "x"}), encoding="utf-8"
        )
        self.assertNotIn("still running", self.step().where)

    def test_the_command_prints_where_next_and_held(self):
        rc, out, err = run_next(self.area, self.lab.root)
        self.assertEqual(rc, 0, err)
        self.assertIn("labkit-next: experiments/", out)
        self.assertIn("  where: ", out)
        self.assertIn("  next:  ", out)


class ADetachedStartBeforeItsRecord(unittest.TestCase):
    """`labkit-next` does not say "measure" while `runlog --wait` waits for
    a command `runlog start` detached that has not opened its run yet:
    following it, the area would measure twice
    (docs/notes/2026-11-04-liveness-and-wait.md). Real processes: a start
    whose command holds until a flag file exists."""

    def test_the_start_comes_first_and_the_step_returns_once_it_ended(self):
        import time

        from labkit.run import detached, runlog_command

        lab = Lab()
        self.addCleanup(lab.close)
        area, protocol = stamp_count(lab)
        flag = Path(lab.tmp.name) / "go"
        self.addCleanup(flag.touch)  # never leave the command behind
        hold = (
            "import pathlib, time\n"
            f"while not pathlib.Path({str(flag)!r}).exists():\n"
            "    time.sleep(0.05)\n"
        )
        rel = str(area.relative_to(lab.root))

        def runlog(*argv: str) -> tuple[int, str]:
            out = io.StringIO()
            old = Path.cwd()
            os.chdir(lab.root)
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                    rc = runlog_command.main(list(argv))
            finally:
                os.chdir(old)
            return rc, out.getvalue()

        def step() -> next_step.Step:
            old = Path.cwd()
            os.chdir(lab.root)
            try:
                return next_step.next_step(area, protocol.resolve())
            finally:
                os.chdir(old)

        rc, out = runlog(
            "start", rel, "--max-seconds", "0.3", "--", sys.executable, "-c", hold
        )
        self.assertEqual(rc, 3, out)  # still starting: no run record yet
        pid = out.split("pid=")[1].split()[0]
        self.assertFalse((area / "runs").exists())
        now = step()
        self.assertIn(
            f"pid {pid} (started by runlog start) is still running", now.where
        )
        self.assertIn("--wait", now.next)
        self.assertNotIn("01_measure.py", now.next)
        rc, out = runlog(rel, "--wait", "--max-seconds", "0.3", "--interval", "0.1")
        self.assertEqual(rc, 3, out)  # the same answer: still running
        # the twin: once the command ended, the step is to measure again
        flag.touch()
        deadline = time.monotonic() + 30
        while any(s.running for s in detached.starts(area)):
            self.assertLess(time.monotonic(), deadline, "the start never ended")
            time.sleep(0.05)
        now = step()
        self.assertNotIn("still running", now.where)
        self.assertIn("01_measure.py", now.next)


class BeforeTheChain(unittest.TestCase):
    def _bare(self, cwd: Path) -> tuple[int, str, str]:
        """`labkit-next` without an area, from CWD."""
        out, err = io.StringIO(), io.StringIO()
        old = Path.cwd()
        os.chdir(cwd)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = next_command.main([])
        finally:
            os.chdir(old)
        return rc, out.getvalue(), err.getvalue()

    def test_without_an_area_and_none_stamped_the_step_creates_one(self):
        """A bare `labkit-next` before any area exists names the stamp
        that creates one, not the usage line."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tests").mkdir()
            rc, out, err = self._bare(Path(d))
        self.assertEqual(rc, 0, err)
        self.assertIn("no experiment area yet", out)
        self.assertIn("labkit-init exp <name> --kind", out)

    def test_without_an_area_the_one_area_is_taken(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tests").mkdir()
            (Path(d) / "experiments" / "01-x").mkdir(parents=True)
            rc, out, err = self._bare(Path(d))
        self.assertEqual(rc, 0, err)
        self.assertIn("labkit-next: experiments/01-x", out)

    def test_without_an_area_and_several_each_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tests").mkdir()
            for name in ("01-x", "02-y"):
                (Path(d) / "experiments" / name).mkdir(parents=True)
            rc, out, err = self._bare(Path(d))
        self.assertEqual(rc, 2)
        self.assertIn("experiments/01-x", err)
        self.assertIn("experiments/02-y", err)

    def test_an_area_without_a_protocol_is_told_to_register(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d) / "experiments" / "01-x"
            area.mkdir(parents=True)
            rc, out, err = run_next(area, Path(d))
        self.assertEqual(rc, 0, err)
        self.assertIn("holds no protocol", out)
        self.assertIn("labkit-init exp", out)

    def test_an_unfilled_must_field_is_the_step_before_any_run(self):
        """The stamp's placeholders: the first MUST field to fill is named,
        with the command that fills it. The twin is the chain above, whose
        protocol is filled."""
        lab = Lab()
        try:
            area, protocol = lab.exp("blank", repeat_cost="low", kind="compute")
            old = Path.cwd()
            os.chdir(lab.root)
            try:
                step = next_step.next_step(area, protocol.resolve())
                before = step.where
                # the named line fills the first field, its first value taken
                line = step.next.split("`")[1]
                argv = shlex.split(re.sub(r"<([^|>]+)[^>]*>", r"\1", line))[1:]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(protocol_fill.main(argv), 0, line)
                after = next_step.next_step(area, protocol.resolve()).where
            finally:
                os.chdir(old)
        finally:
            lab.close()
        self.assertIn("MUST field(s)", before)
        self.assertIn("--list", step.next)
        self.assertIn("--contract", step.next)
        self.assertNotEqual(before, after)

    def test_a_fill_line_is_named_only_where_one_fill_closes_the_gap(self):
        """A placeholder is filled by protocol-fill; a field absent from the
        text is not (protocol-fill knows no field it cannot see): a † field
        comes with `labkit-init exp … --report`, another absent field is a
        line to write; a freeze key or a contradiction has no single step.
        So `next` never names a fill protocol-fill answers with "no field
        labelled"."""
        area = Path("experiments/01-x")
        line = next_step._fill_line
        self.assertEqual(
            line(area / "P.md", "Unit", absent=False),
            '`protocol-fill experiments/01-x/P.md "Unit=<value>"` fills the first',
        )
        self.assertEqual(
            line(area / "P.md", "[protocol] kind", absent=True),
            '`protocol-fill experiments/01-x/P.md "kind=<compute|fit|apply>"` fills the first',
        )
        absent = line(area / "P.md", "Why this design", absent=True)
        assert absent is not None
        self.assertTrue(
            absent.startswith("`labkit-init exp experiments/01-x --report` appends"),
            absent,
        )
        absent = line(area / "P.md", "Unit", absent=True)
        assert absent is not None
        self.assertIn("write the line `- **Unit:** …`", absent)
        for gap in (
            "[protocol] preflight_audit (frozen = true without the record named)",
            "[protocol] frozen",
        ):
            self.assertIsNone(line(area / "P.md", gap, absent=True), gap)

    def test_the_adoption_names_the_fields_it_would_owe_before_adopt(self):
        """One mouth: `next` asks `check_fields` what the adoption's state
        owes (`adopting`) — a frozen protocol's † result fields — and names
        the fill before `labkit-adopt`, which would refuse the written
        result for them. The twins: filled, or unfrozen, the adoption owes
        nothing more."""
        from protocol_fixture import head

        protocol = Path("experiments/01-x/PROTOCOL-x.md")
        daggered = (
            "- **Conclusion:** the bar was met.\n"
            "- **Question †:** <…>\n- **Did †:** <…>\n- **Expected or surprising †:** <…>\n"
            "- **Rival check †:** <…>\n- **Caps/drops †:** <…>\n- **Analysis audit †:** <…>\n"
        )
        frozen = head(repeat_cost="high", frozen=True, preflight_audit="n/a — test")
        step = next_step._adoption_owes(protocol, frozen + daggered, "r1")
        assert step is not None
        self.assertIn("adopting r1 would owe 6 field(s) still open", step.where)
        self.assertIn(
            '`protocol-fill experiments/01-x/PROTOCOL-x.md "Question †=<value>"`',
            step.next,
        )
        self.assertIn("labkit-adopt refuses", step.held)
        # absent altogether: the † fields come with --report
        step = next_step._adoption_owes(protocol, frozen, "r1")
        assert step is not None
        self.assertIn("`labkit-init exp experiments/01-x --report` appends", step.next)
        filled = frozen + daggered.replace("<…>", "written")
        self.assertIsNone(next_step._adoption_owes(protocol, filled, "r1"))
        self.assertIsNone(
            next_step._adoption_owes(
                protocol, head(repeat_cost="high") + daggered, "r1"
            )
        )

    def test_no_such_area_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _, err = run_next(Path(d) / "nope", Path(d))
        self.assertEqual(rc, 2)
        self.assertIn("labkit-next", err)


if __name__ == "__main__":
    unittest.main()


class ProgressAccount(unittest.TestCase):
    """With a registered report, the step after a measurement
    is the progress account — a discussion block of the answering run —,
    before the audit and before any gap; it releases nothing, the commit
    takes it, the stop names the next step once, and the adoption puts the
    result block where it stood, so an attempt cut off before the end still
    leaves a report."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = stamp_count(self.lab, report_file="REPORT.md")
        self.report = self.lab.root / "REPORT.md"

    def step(self) -> next_step.Step:
        old = Path.cwd()
        os.chdir(self.lab.root)
        try:
            return next_step.next_step(self.area, self.protocol.resolve())
        finally:
            os.chdir(old)

    def measure(self) -> str:
        """The count measured and its Conclusion written: the adoption owes it."""
        run_id = self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        self.lab.concluded(self.protocol)
        return run_id

    def account(self, run_id: str) -> None:
        rc = protocol_fill.main(
            [
                str(self.protocol),
                "--discuss",
                run_id,
                "--why",
                "lines counted; the analysis audit is still open",
                "--into",
                str(self.report),
            ]
        )
        self.assertEqual(rc, 0)

    def test_before_the_measurement_no_account_and_no_report_hint(self):
        step = self.step()
        self.assertIn("01_measure.py", step.next, step)
        self.assertNotIn("--discuss", step.next)
        self.assertNotIn("report=REPORT.md", step.next)  # registered already

    def test_the_account_comes_first_then_the_audit_and_the_stop_names_it_once(self):
        run_id = self.measure()
        step = self.step()
        self.assertIn(f"--discuss {run_id}", step.next, step)
        self.assertIn("<what was measured, what is still open>", step.next)
        self.assertIn("carries no account of it yet", step.where)
        self.assertIn("only the adoption releases it", step.held)
        self.account(run_id)
        step = self.step()
        self.assertIn("labkit-audit", step.next, step)
        self.assertIn("--mode analysis", step.next)
        # the commit takes the account; the release is unchanged: nothing adopted
        from labkit.gates import report_check

        self.lab.git("add", "-A")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = report_check.if_reported(
                [self.report, self.protocol], self.lab.root, staged=True
            )
        self.assertEqual(rc, 0, out.getvalue())
        self.lab.commit("progress")
        self.assertIsNone(protocol_block.declared_run(self.protocol.read_text("utf-8")))
        # the stop names the next step: the adoption or the handover
        rc, err = self.lab.stop_hook()
        self.assertEqual(rc, 2, err)
        self.assertIn("progress account", err)

    def test_an_interrupted_audit_leaves_the_account_and_the_audit_owed(self):
        import signal
        import subprocess

        run_id = self.measure()
        self.account(run_id)
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys, time; from pathlib import Path;"
                "from labkit.formats import attempts;"
                "attempts.begin(Path(sys.argv[1]), 'analysis', 'opus', 's', "
                "block_sha='b', protocol='PROTOCOL-lines.md');"
                "print('begun', flush=True); time.sleep(60)",
                str(self.area),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert child.stdout is not None
            self.assertEqual(child.stdout.readline().strip(), "begun")
        finally:
            os.kill(child.pid, signal.SIGKILL)
            child.wait()
        self.assertIn(f"Run {run_id} — discussed", self.report.read_text("utf-8"))
        step = self.step()
        self.assertNotIn("--discuss", step.next)
        self.assertIn("labkit-audit", step.next, step)
        self.assertIsNone(protocol_block.declared_run(self.protocol.read_text("utf-8")))

    def test_an_open_audit_blocker_still_holds_the_commit_beside_the_account(self):
        """Retained protection: the account changes the commit rule for the
        report only; an undecided audit BLOCKER still holds the commit."""
        from labkit.formats import findings, promises, scope_sha
        from protocol_fixture import registration_of, shown_sha

        run_id = self.measure()
        self.account(run_id)
        findings.write(
            self.area,
            sc.ANALYSIS_AUDIT,
            "test",
            scope_sha.area_stamp(self.area)[0],
            promises.block_stamp(self.protocol.read_text(encoding="utf-8")),
            (1, 0, 0),
            [
                (
                    "BLOCKER",
                    "BLOCKER · a.py:1 · statement · the mean counts a hidden file",
                )
            ],
            run_id=run_id,
            shown_sha=shown_sha(self.area, self.area / "runs" / run_id),
            registration=registration_of(self.area),
        )
        self.lab.git("add", "-A")
        lines = undecided.undecided_blockers(
            self.lab.root, [self.report, self.protocol], staged=True
        )
        self.assertTrue(
            any("the mean counts a hidden file" in ln for ln in lines), lines
        )
        step = self.step()
        self.assertNotIn("--discuss", step.next)
        self.assertIn("--decide", step.next, step)

    def test_a_code_change_after_the_run_keeps_its_blocker_after_the_account(self):
        run_id = self.measure()
        script = self.area / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text(encoding="utf-8") + "\n# changed after the run\n",
            encoding="utf-8",
        )
        step = self.step()
        self.assertIn(f"--discuss {run_id}", step.next, step)  # saved first
        self.account(run_id)
        step = self.step()
        self.assertNotIn("--discuss", step.next)
        self.assertIn("01_measure.py", step.where + step.next, step)
        self.assertIn("blocker(s) stand", step.held, step)
        # the account lifts nothing: the adoption is still refused
        self.lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out = self.lab.adopt(self.protocol, run_id)
        self.assertNotEqual(rc, 0, out)

    def test_the_adoption_puts_the_result_block_where_the_account_stood(self):
        from labkit.checks import report_blocks
        from labkit.tools import adopt

        run_id = self.measure()
        self.report.write_text("# Report\n\nIntro.\n\n", encoding="utf-8")
        self.account(run_id)
        with self.report.open("a", encoding="utf-8") as f:
            f.write("\nClosing words.\n")
        self.lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        old = Path.cwd()
        os.chdir(self.lab.root)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = adopt.adopt_in_one_step(self.area, self.protocol, run_id)
        finally:
            os.chdir(old)
        self.assertEqual(rc, 0)
        text = self.report.read_text(encoding="utf-8")
        self.assertEqual(report_blocks.discussions(text), [])
        (block,) = report_blocks.blocks(text)
        self.assertEqual(block.run_id, run_id)
        self.assertLess(text.index("Intro."), text.index(block.body))
        self.assertLess(text.index(block.body), text.index("Closing words."))

    def test_the_finished_step_names_the_registered_report(self):
        from unittest import mock

        from labkit.gates import audit
        from labkit.tools import adopt

        self.lab.fill(self.protocol, "--force", "report=SUMMARY.md")
        self.lab.commit("register the required summary")
        self.report = self.lab.root / "SUMMARY.md"
        run_id = self.measure()
        self.account(run_id)
        self.lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        old = Path.cwd()
        os.chdir(self.lab.root)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    adopt.adopt_in_one_step(self.area, self.protocol, run_id), 0
                )
            with (
                mock.patch.object(
                    audit.llm, "complete", return_value="verdict: 0 claim(s)\n"
                ),
                mock.patch.object(audit.llm, "takes_max_tokens", return_value=True),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(
                    audit.main([str(self.area), "--report-review", str(self.report)]),
                    0,
                )
        finally:
            os.chdir(old)
        step = self.step()
        self.assertTrue(step.next.startswith("nothing"), step)
        self.assertIn("SUMMARY.md", step.next)
        self.assertNotIn("the head does not register", step.next)


class DiscussingReport(unittest.TestCase):
    """A report that discusses a run owes a report review of its state.
    The stop and the commit hold it (`report_hold.hold_report`), and gate,
    hooks and `next` read the one finding
    (`report_hold.discussion_review_findings`) of the one state — the tree
    at the stop, the index at the commit — and a review of the state
    releases all three."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = stamp_count(self.lab)
        self.run_id = self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        self.lab.conclude(self.protocol)  # the adoption owes it
        # the analysis audit done: the chain names it before the report, and
        # `next` names the first hold — with it done, the review is the one left
        self.lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, self.run_id)
        self.report = self.lab.root / "REPORT.md"
        self.report.write_text("# Report\n\nlooked at, nothing reported\n")
        rc = protocol_fill.main(
            [
                str(self.protocol),
                "--discuss",
                self.run_id,
                "--why",
                "the analysis is not done",
                "--into",
                str(self.report),
            ]
        )
        self.assertEqual(rc, 0)

    def step(self, state: str = area_state.TREE) -> next_step.Step:
        with contextlib.chdir(self.lab.root):
            return next_step.next_step(self.area, self.protocol.resolve(), state=state)

    def gate(self, *, staged: bool) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.chdir(self.lab.root), contextlib.redirect_stdout(out):
            rc = report_check.if_reported([self.report], self.lab.root, staged=staged)
        return rc, out.getvalue()

    def finding(self, *, staged: bool) -> GateFinding:
        text = (
            state_text(self.lab.root, self.protocol, staged=True)
            if staged
            else self.protocol.read_text(encoding="utf-8")
        )
        assert text is not None
        with contextlib.chdir(self.lab.root):
            area = self.protocol.parent
            found = report_hold.discussion_review_findings(
                self.protocol,
                text,
                self.lab.root,
                staged=staged,
                state=state_of(
                    area, file_state=area_state.INDEX if staged else area_state.TREE
                ),
                held=read_evidence(area, staged=staged),
            )
        self.assertEqual(len(found), 1, found)
        return found[0]

    def reviewed(self) -> None:
        """A report review of the state now, naming no claim — what
        `--report-review` writes."""
        text = self.report.read_text(encoding="utf-8")
        proto_text = self.protocol.read_text(encoding="utf-8")
        pieces = review_pieces(
            self.area,
            self.report,
            text,
            self.protocol,
            proto_text,
            discussed_under(self.report, text, self.protocol),
            state_of(self.area),
            read_evidence(self.area, staged=False),
        )
        whole, parts = report_hold.review_fingerprint(pieces)
        rkey, pkey = review_keys(self.area, self.report, self.protocol)
        report_reviews.write_report_review(
            self.area,
            model="m",
            report=rkey,
            protocol=pkey,
            whole=whole,
            parts=parts,
            claims=[],
            again=False,
        )

    def test_in_the_tree_gate_stop_and_next_hold_and_name_the_one_finding(self):
        owed = self.finding(staged=False)
        self.assertIn("has no clean report review of this state", owed.text)
        step = self.step()
        self.assertEqual(step.where, owed.text)
        self.assertEqual(step.next, owed.fix)
        self.assertIn("--report-review REPORT.md", step.next)
        rc, out = self.gate(staged=False)
        self.assertEqual(rc, 1, out)
        self.assertIn(owed.text, out)
        with contextlib.chdir(self.lab.root):
            rc, err = self.lab.stop_hook()
        self.assertEqual(rc, 2, err)
        self.assertIn(owed.text, err)

    def test_in_the_index_the_commit_and_next_read_the_staged_state(self):
        """The commit judges the index. A review of the staged state
        releases the commit and `next --staged`, while the tree, edited
        after it, owes a review still: the two states apart."""
        self.lab.git("add", "-A")
        owed = self.finding(staged=True)
        step = self.step(area_state.INDEX)
        self.assertEqual(step.where, owed.text)
        self.assertEqual(step.next, owed.fix)
        with contextlib.chdir(self.lab.root):
            rc, out = self.lab.pre_commit(self.report)
        self.assertEqual(rc, 1, out)
        self.assertIn(owed.text, out)
        # the review of the staged state, staged with it
        self.reviewed()
        self.lab.git("add", "-A")
        with contextlib.chdir(self.lab.root):
            rc, out = self.lab.pre_commit(self.report)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("--report-review", self.step(area_state.INDEX).next)
        # the tree moves on: it owes a review of its own state, the index not
        with self.report.open("a", encoding="utf-8") as f:
            f.write("\nmore prose\n")
        self.assertIn("--report-review", self.step().next)
        self.assertEqual(self.gate(staged=False)[0], 1)
        self.assertNotIn("--report-review", self.step(area_state.INDEX).next)
        self.assertEqual(self.gate(staged=True)[0], 0)

    def test_the_counter_case_a_review_of_the_state_releases_all_three(self):
        self.reviewed()
        self.assertEqual(self.gate(staged=False)[0], 0)
        with contextlib.chdir(self.lab.root):
            found = report_hold.discussion_review_findings(
                self.protocol,
                self.protocol.read_text(encoding="utf-8"),
                self.lab.root,
                staged=False,
                state=state_of(self.protocol.parent),
                held=read_evidence(self.protocol.parent, staged=False),
            )
        self.assertEqual(found, [])
        step = self.step()
        self.assertNotIn("--report-review", step.where + step.next)
        self.assertIn("labkit-adopt", step.next)  # the chain moves on: the adoption
        with contextlib.chdir(self.lab.root):
            rc, err = self.lab.stop_hook()
        self.assertNotIn("--report-review", err)


class MissingRegisteredReport(unittest.TestCase):
    """A protocol whose registered report is not written after a
    measurement: the hold is the gate's finding
    (`registered_report.missing_report`), and the stop prints the step
    `next` names for that state, the progress account, not the finding's
    three ways — one spelling, one action."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = stamp_count(self.lab, report_file="REPORT.md")
        self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        self.report = self.lab.root / "REPORT.md"

    def test_the_stop_prints_the_step_next_reads_from_the_same_finding(self):
        from labkit.gates import agent_hooks

        with contextlib.chdir(self.lab.root):
            text = self.protocol.read_text(encoding="utf-8")
            gap = registered_report.missing_report(
                self.protocol,
                text,
                self.lab.root,
                measured=area_state.state_of(self.area).measured_of(
                    protocol_block.head(text).id
                ),
            )
            assert gap is not None
            step = next_step.next_step(self.area, self.protocol.resolve())
            # the hold is the finding; the action is the concrete command
            # `next` prefers for this state, not the finding's three ways
            self.assertIn("REPORT.md carries no account of it yet", step.where)
            self.assertIn("--discuss", step.next)
            self.assertIn("REPORT.md", gap.text)
            (line,) = agent_hooks.missing_reports(
                self.lab.root, [self.protocol]
            ).steps.values()
            self.assertEqual(line, step.render("experiments/01-lines"))
            rc, err = self.lab.stop_hook()
        self.assertEqual(rc, 2, err)
        self.assertIn(step.where, err)
        self.assertIn(step.next, err)

    def test_the_twin_a_written_report_owes_its_account_and_holds_nothing(self):
        from labkit.gates import agent_hooks

        self.report.write_text("# Report\n", encoding="utf-8")
        with contextlib.chdir(self.lab.root):
            step = next_step.next_step(self.area, self.protocol.resolve())
            self.assertEqual(
                agent_hooks.missing_reports(self.lab.root, [self.protocol]).steps, {}
            )
        self.assertIn("carries no account of it yet", step.where)
        self.assertIn("--discuss", step.next)


class TwoProtocols(unittest.TestCase):
    """The adopt line `next` names runs as named: with two protocols in the
    area it carries `--protocol`, as `commands.adopt_command` builds it — the
    one home of that line; without the flag `labkit-adopt` refuses it with
    "name one with --protocol"."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = stamp_count(self.lab)
        run_id = self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        self.lab.conclude(self.protocol)  # the adoption owes it
        self.lab.record(self.area, self.protocol, "analysis", run_id)
        text = self.protocol.read_text(encoding="utf-8")
        head = protocol_block.head(text)
        assert head.id is not None
        second = self.area / "PROTOCOL-s2-lines.md"
        second.write_text(text.replace(head.id, "p-0123456789abcdef"), encoding="utf-8")
        self.lab.commit("a second protocol")

    def test_the_adopt_step_names_the_protocol_and_runs(self):
        from labkit.tools import adopt

        with contextlib.chdir(self.lab.root):
            step = next_step.next_step(self.area, self.protocol.resolve())
            self.assertIn("labkit-adopt", step.next)
            line = re.search(r"`(labkit-adopt [^`]*)`", step.next)
            assert line is not None, step.next
            self.assertIn(
                "--protocol experiments/01-lines/PROTOCOL-lines.md", line.group(1)
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                rc = adopt.main(shlex.split(line.group(1))[1:])
        self.assertNotIn("name one with --protocol", out.getvalue())
        self.assertEqual(rc, 0, out.getvalue())


class ProtocolInTheIndexOnly(unittest.TestCase):
    """The commit holds the index: a protocol the index holds and the tree
    has deleted is held by the commit's gate, and the step printed beside
    the hold is read from the same protocols (`report_check.reached_by`),
    not from the tree's."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = stamp_count(self.lab)
        run_id = self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        self.lab.record(self.area, self.protocol, "analysis", run_id)
        rc, out = self.lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        self.lab.commit("adopted")
        self.script = self.area / "scripts" / "01_measure.py"
        with self.script.open("a", encoding="utf-8") as f:
            f.write("\n# a staged change of the area's code\n")
        self.lab.git("add", "--", str(self.script))
        self.protocol.unlink()

    def test_the_commit_gate_holds_and_prints_the_step_of_the_indexed_protocol(self):
        from labkit.gates import agent_hooks

        with contextlib.chdir(self.lab.root):
            staged = next_step.steps_for(self.lab.root, [self.script], staged=True)
            self.assertEqual(len(staged), 1, staged)
            self.assertIn("the working tree differs from the index", staged[0])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = agent_hooks.commit_gates([])
            self.assertEqual(rc, 1, out.getvalue())
            self.assertIn(staged[0], out.getvalue())
            # the twin: the tree holds no protocol, so the tree names no step
            self.assertEqual(
                next_step.steps_for(self.lab.root, [self.script], staged=False), []
            )


class ReportInTheIndexOnly(unittest.TestCase):
    """A report citing the adopted run without its block, held by the index
    and deleted in the tree: the commit's gate holds it, and `next --staged`
    names the block to write from the same state
    (`report_hold.reports_without_block` reads the index then), never
    "nothing holds it" beside the hold."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = stamp_count(self.lab)
        self.run_id = self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        self.lab.record(self.area, self.protocol, "analysis", self.run_id)
        rc, out = self.lab.adopt(self.protocol, self.run_id)
        self.assertEqual(rc, 0, out)
        self.lab.commit("adopted")
        self.report = self.lab.root / "REPORT.md"
        self.report.write_text(
            f"# Report\n\nrun {self.run_id} gave 3.0\n", encoding="utf-8"
        )
        self.lab.git("add", "--", str(self.report))
        self.report.unlink()

    def test_next_staged_names_the_block_the_commit_holds(self):
        from labkit.gates import agent_hooks

        with contextlib.chdir(self.lab.root):
            staged = next_step.next_step(
                self.area, self.protocol.resolve(), state=area_state.INDEX
            )
            self.assertIn("without its generated block", staged.where)
            self.assertIn("--into REPORT.md", staged.next)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = agent_hooks.commit_gates([])
            self.assertEqual(rc, 1, out.getvalue())
            self.assertIn(staged.render("experiments/01-lines"), out.getvalue())
            # the twin: the tree holds no such report, so nothing holds there
            tree = next_step.next_step(self.area, self.protocol.resolve())
        self.assertIn("nothing holds it", tree.where)
