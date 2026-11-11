"""Adoption comes last: report-check tells that order when an adoption
line (`--from-run`) stands beside a blocker adoption cannot clear, and stays
silent when the adoption line is the way out as printed — a reader takes
`--from-run <run> --force` beside an open BLOCKER on that run for the fix."""

from __future__ import annotations

import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import commands
from labkit.gates.report_check import adoption_order_note  # noqa: E402
from labkit.formats import protocol_block  # noqa: E402
from labkit.formats.area_state import state_of  # noqa: E402
from labkit.formats.gate import blocker  # noqa: E402
from labkit.run import start_check  # noqa: E402

# the note reads the findings' steps (`GateFinding.step`), never their words
ADOPT = blocker(
    "finalize: [result] names A, which cannot answer for p-1: unfinalized",
    fix="withdraw the adoption, audit the run that answers, then `labkit-adopt E <run_id>` adopts it",
    step=commands.Command(commands.ADOPT, "labkit-adopt E <run_id>"),
)
RENDER = blocker(
    "result section: the Recorded results line differs from its rendering",
    fix=f"`{commands.render_command()}` writes it again",
    step=commands.render_command(),
)
OPEN = blocker(
    "finalize: 2026-10-27T22-45-analysis.toml: BLOCKER · scripts/01_measure.py:113 · the refinement is truncated",
    fix="decide it",
)


class AdoptionOrder(unittest.TestCase):
    def test_an_adoption_beside_another_blocker_is_told_last(self):
        note = adoption_order_note([ADOPT, OPEN])
        self.assertIsNotNone(note)
        assert note is not None
        self.assertIn("adoption comes last", note)
        self.assertIn("1 other blocker(s)", note)

    def test_projections_of_an_adoption_do_not_count_as_other(self):
        self.assertIsNone(adoption_order_note([ADOPT, RENDER]))

    def test_no_adoption_line_no_note(self):
        self.assertIsNone(adoption_order_note([OPEN, RENDER]))
        self.assertIsNone(adoption_order_note([]))


HEAD = '```toml\n[protocol]\nstandard = "0.28"\nid = "p-0123456789abcdef"\ntype = "exploratory"\nrepeat_cost = "{cost}"\nkind = "compute"\nfrozen = false\npreflight_audit = ""\n```\n'


class FirstStepBeforeARun(unittest.TestCase):
    """runlog's refusal names the freeze only where the repeat cost owes one:
    "Freeze first" at low repeat cost reads as a contradiction."""

    def first_step(self, cost: str) -> str:
        text = HEAD.format(cost=cost)
        bound = start_check._Bound(  # noqa: SLF001
            {"id": "p-0123456789abcdef", "path": "PROTOCOL-x.md"},
            text,
            protocol_block.head(text),
        )
        with mock.patch.object(start_check, "_committed_registration", return_value=[]):
            return start_check._first_step(Path.cwd(), bound, state_of(Path.cwd()))  # noqa: SLF001

    def test_low_names_the_registration_not_the_freeze(self):
        step = self.first_step("low")
        self.assertIn("nothing freezes", step)
        self.assertNotIn("Freeze first", step)

    def test_high_names_the_freeze(self):
        self.assertIn("Freeze first", self.first_step("high"))


if __name__ == "__main__":
    unittest.main()
