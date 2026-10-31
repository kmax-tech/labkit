"""Adoption comes last (2026-10-28): report-check tells that order when an
adoption line (`--from-run`) stands beside a blocker adoption cannot clear,
and stays silent when the adoption line is the way out as printed — three
of three Haiku readers took `--from-run <run> --force` beside an open
BLOCKER on that run for the fix (docs/usability/2026-10-28-haiku-stuck-reading.md)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.gates import finalize  # noqa: E402
from labkit.gates.report_check import adoption_order_note  # noqa: E402
from labkit.formats import protocol_block  # noqa: E402
from labkit.run import start_check  # noqa: E402

ADOPT = "finalize: [result] names A, but the run that answers is B. Next: once that run's checks hold, `labkit-adopt E B` adopts it"
RENDER = "result section: the Recorded results line differs from its rendering — `protocol-fill <PROTOCOL> --render` writes it again"
OPEN = "finalize: 2026-10-27T22-45-analysis.toml: BLOCKER · scripts/01_measure.py:113 · the refinement is truncated"


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

    def test_the_declared_run_hint_names_its_precondition(self):
        text = '```toml\n[result]\nrun = "2026-01-01T00-00-00_aaaa"\n```\n'
        protocol = Path("experiments/01-x/PROTOCOL-x.md")
        msg = finalize.declared_run_mismatch(
            text, Path("runs/2026-01-02T00-00-00_bbbb"), protocol
        )
        self.assertIsNotNone(msg)
        assert msg is not None
        # the replacement goes through the withdrawal and an audit, never --force
        self.assertIn("withdraw the adoption", msg.fix or "")
        self.assertIn(
            "audit the run that answers and decide its findings", msg.fix or ""
        )
        self.assertIn("fix the code and measure again first", msg.fix or "")
        self.assertNotIn("--force", msg.fix or "")


HEAD = '```toml\n[protocol]\nstandard = "0.23"\nid = "p-0123456789abcdef"\ntype = "exploratory"\nrepeat_cost = "{cost}"\nkind = "compute"\nfrozen = false\npreflight_audit = ""\n```\n'


class FirstStepBeforeARun(unittest.TestCase):
    """runlog's refusal names the freeze only where the repeat cost owes one
    (Haiku start reading, 2026-10-28: two of three readers called "Freeze
    first" at low repeat cost a contradiction)."""

    def first_step(self, cost: str) -> str:
        text = HEAD.format(cost=cost)
        bound = start_check._Bound(  # noqa: SLF001
            {"id": "p-0123456789abcdef", "path": "PROTOCOL-x.md"},
            text,
            protocol_block.head(text),
        )
        return start_check._first_step(bound)  # noqa: SLF001

    def test_low_names_the_registration_not_the_freeze(self):
        step = self.first_step("low")
        self.assertIn("nothing freezes", step)
        self.assertNotIn("Freeze first", step)

    def test_high_names_the_freeze(self):
        self.assertIn("Freeze first", self.first_step("high"))


if __name__ == "__main__":
    unittest.main()
