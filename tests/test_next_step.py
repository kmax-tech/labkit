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
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import standard_contract as sc  # noqa: E402
from labkit.tools import next_step  # noqa: E402
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
        # registered, not measured: measure
        step = self.step()
        self.assertIn("01_measure.py", step.next, step)
        self.assertIn("blocker(s) in report-check", step.held)
        run_id = self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        # measured, no analysis audit: audit the run that answers
        step = self.step()
        self.assertIn("labkit-audit", step.next, step)
        self.assertIn("--mode analysis", step.next, step)
        self.lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        # audited, nothing holds: adopt that run
        step = self.step()
        self.assertIn(f"--from-run {run_id}", step.next, step)
        self.assertIn("no run is adopted yet", step.where)
        rc, out = self.lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        # adopted, nothing holds: nothing owed
        step = self.step()
        self.assertIn(f"has adopted {run_id}", step.where)
        self.assertTrue(step.next.startswith("nothing"), step)
        self.assertEqual(step.held, "")

    def test_the_command_prints_where_next_and_held(self):
        rc, out, err = run_next(self.area, self.lab.root)
        self.assertEqual(rc, 0, err)
        self.assertIn("labkit-next: experiments/", out)
        self.assertIn("  where: ", out)
        self.assertIn("  next:  ", out)


class BeforeTheChain(unittest.TestCase):
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
            finally:
                os.chdir(old)
        finally:
            lab.close()
        self.assertIn("MUST field(s)", step.where)
        self.assertIn("protocol-fill", step.next)
        self.assertIn("--contract", step.next)

    def test_no_such_area_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _, err = run_next(Path(d) / "nope", Path(d))
        self.assertEqual(rc, 2)
        self.assertIn("labkit-next", err)


if __name__ == "__main__":
    unittest.main()
