"""What a step before the first measurement adds for what only the task can
say (`standard_contract.first_measurement_hint`): a report to register, and for a
computation a stated value to register as `[reference]` and the
hand-checked case to fill by hand. In usage round 24 no task-34 agent
registered the stated values before the first measurement (0 of 6), every
one filled the hand-checked case from its own run, and two reports were
never registered (docs/notes/2026-11-15-agent-guidance-replays.md). Read
from the head in memory; `labkit-next` and runlog print the same sentences
(their tests: `test_next_step.TheChain`,
`test_adoption_order.FirstStepBeforeARun`).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from labkit.formats.standard_contract import first_measurement_hint
from protocol_fixture import head  # noqa: E402

PROTOCOL = Path("experiments/02-hrv/PROTOCOL-hrv.md")
WITHIN = 'value = 760\ntolerance = 7.6\nrelation = "within"\n'


class ForAComputation(unittest.TestCase):
    def test_a_bare_head_names_report_reference_and_hand_checked_case(self):
        hint = first_measurement_hint(PROTOCOL, head(repeat_cost="low", kind="compute"))
        self.assertIn('"report=REPORT.md"', hint)
        self.assertIn("`[reference]`", hint)
        self.assertIn("`tests/test_02_hrv.py`", hint)
        self.assertIn("copied from a run's output", hint)

    def test_a_registered_reference_is_not_asked_for_again(self):
        hint = first_measurement_hint(
            PROTOCOL, head(repeat_cost="low", kind="compute", reference=WITHIN)
        )
        self.assertNotIn("`[reference]`", hint)
        self.assertIn("hand-checked case", hint)

    def test_a_registered_report_is_not_asked_for_again(self):
        hint = first_measurement_hint(
            PROTOCOL, head(repeat_cost="low", kind="compute", report="REPORT.md")
        )
        self.assertNotIn("report=REPORT.md", hint)
        self.assertIn("`[reference]`", hint)


class ForAKindWithABar(unittest.TestCase):
    """A fit or an apply compares in its criterion and carries no
    hand-checked case in its stamped test: only the report is named."""

    def test_only_the_report(self):
        for kind in ("fit", "apply"):
            with self.subTest(kind=kind):
                hint = first_measurement_hint(
                    PROTOCOL, head(repeat_cost="low", kind=kind)
                )
                self.assertIn('"report=REPORT.md"', hint)
                self.assertNotIn("[reference]", hint)
                self.assertNotIn("hand-checked", hint)


class WithoutAnId(unittest.TestCase):
    def test_nothing(self):
        self.assertEqual(
            first_measurement_hint(
                PROTOCOL, head(id="<p-id>", repeat_cost="low", kind="compute")
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()
