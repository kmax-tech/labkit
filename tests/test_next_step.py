"""labkit-next — one next step per state of an area, read from the gates.

The counting skeleton walked through the chain: at every station the
step named is the command that moves it on, and taking it moves the area
to the next station. The plan (docs/notes/2026-10-30-agent-surface.md,
step 2): in round 1, five agents stopped with a handover and no number,
four ran and never adopted, two never ran.
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import protocol_block  # noqa: E402
from labkit.formats import standard_contract as sc  # noqa: E402
from labkit.tools import next_step, protocol_fill  # noqa: E402
from test_end_to_end import Lab, stamp_count  # noqa: E402


def run_next(area: Path, cwd: Path) -> tuple[int, str, str]:
    """`labkit-next AREA` from CWD: exit code, stdout, stderr."""
    out, err = io.StringIO(), io.StringIO()
    old = Path.cwd()
    os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = next_step.main([str(area)])
    finally:
        os.chdir(old)
    return rc, out.getvalue(), err.getvalue()


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
            "report=REPORT.md` — before the first measurement only", step.next
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
        # audited, nothing holds: adopt that run
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
        # hold: named here first (reference pilot 2026-11-01, tasks 21 and 34)
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
        """A run still open read as nothing, and labkit-next sent the agent to
        measure again beside it (reference pilot 2026-11-01, task 15). The
        twin: a run that broke off (failure.json) is not open."""
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


class BeforeTheChain(unittest.TestCase):
    def _bare(self, cwd: Path) -> tuple[int, str, str]:
        """`labkit-next` without an area, from CWD."""
        out, err = io.StringIO(), io.StringIO()
        old = Path.cwd()
        os.chdir(cwd)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = next_step.main([])
        finally:
            os.chdir(old)
        return rc, out.getvalue(), err.getvalue()

    def test_without_an_area_and_none_stamped_the_step_creates_one(self):
        """Round 2: fourteen bare `labkit-next` calls, before any area
        existed, met the usage line."""
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
        line = next_step._fill_line
        self.assertEqual(line("P.md", "Unit"), 'protocol-fill P.md "Unit=<value>"')
        self.assertEqual(
            line("P.md", "[protocol] kind"),
            'protocol-fill P.md "kind=<compute|fit|apply>"',
        )
        for gap in (
            "[protocol] preflight_audit (frozen = true without the record named)",
            "[protocol] frozen",
        ):
            self.assertIsNone(line("P.md", gap), gap)

    def test_no_such_area_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _, err = run_next(Path(d) / "nope", Path(d))
        self.assertEqual(rc, 2)
        self.assertIn("labkit-next", err)


if __name__ == "__main__":
    unittest.main()


class ProgressAccount(unittest.TestCase):
    """B (2026-11-02): with a registered report, the step after a measurement
    is the progress account — a discussion block of the answering run —,
    before the audit and before any gap; it releases nothing, the commit
    takes it, the stop names the next step once, and the adoption puts the
    result block where it stood (labkit-paper area 17: five of six timed-out
    attempts left no report, the report being written last)."""

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
        return self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))

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
        from labkit.gates import agent_hooks
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
            [("BLOCKER", "the mean counts a hidden file")],
            run_id=run_id,
            shown_sha=shown_sha(self.area, self.area / "runs" / run_id),
            registration=registration_of(self.area),
        )
        self.lab.git("add", "-A")
        lines = agent_hooks.undecided_blockers(
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
