"""The computation's exemption stands where the code makes it and where the
auditor reads.

A plain computation (`kind = "compute"`) at `seconds` (no `[C]/[A]/[B]` id in its prose) owes no
promise table and no criterion — `promises.promise_tables_owed` since
0.87.1. The standard the analysis audit reads said tables are owed "with
cost = seconds always", and an audit asked a count for a criterion (sandbox
probe count-3, 2026-10-21).
"""

import unittest
from pathlib import Path

from labkit.formats import promises
from labkit.gates import audit

ROOT = Path(__file__).resolve().parents[1]


class CountExemption(unittest.TestCase):
    def test_the_code_owes_a_plain_computation_no_tables(self):
        self.assertIsNone(
            promises.promise_tables_owed(
                None, frozen=False, full_run=True, registers=False
            )
        )
        self.assertIsNotNone(
            promises.promise_tables_owed(
                None, frozen=False, full_run=True, registers=True
            )
        )

    def test_the_auditor_reads_the_exemption(self):
        for mode in ("preflight", "analysis"):
            with self.subTest(mode=mode):
                _, text = audit.standard_excerpt(mode)
                self.assertIn('a computation\n  (`kind = "compute"`', text)
                self.assertIn("owes neither tables nor a\n  success criterion", text)

    def test_the_contract_states_it_too(self):
        text = (ROOT / "docs" / "promise-block.md").read_text(encoding="utf-8")
        self.assertIn("owes no tables and no success criterion", text)


if __name__ == "__main__":
    unittest.main()
