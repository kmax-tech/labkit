"""The replacement gate's branches no other test reached, as gate tests
from a context built in memory: a `[replaces]` table that does not read,
and a predecessor whose audit records do not read."""

from __future__ import annotations

import unittest
from unittest import mock

from labkit.formats.gate import BLOCKER, OPEN_RULE, TECHNICAL_RULE
from labkit.gates import report_replacement
from protocol_fixture import head
from state_fixture import AREA, area_evidence, checked

#: the head with a [replaces] table whose protocol is no id
UNREADABLE_REPLACES = head(repeat_cost="low").replace(
    'preflight_audit = ""\n', 'preflight_audit = ""\n\n[replaces]\nprotocol = 3\n', 1
)


class AReplacement(unittest.TestCase):
    def test_a_replaces_table_that_does_not_read_is_one_blocker(self):
        (gap,) = report_replacement.replacement_gaps(
            checked(UNREADABLE_REPLACES, run=None)
        )
        self.assertEqual((gap.grade, gap.rule), (BLOCKER, OPEN_RULE))
        self.assertTrue(gap.text.startswith("PROTOCOL-x.md: "), gap.text)
        self.assertIn("[[replaces.change]]", gap.fix or "")

    def test_the_twin_a_head_without_replaces_owes_nothing(self):
        self.assertEqual(
            report_replacement.replacement_gaps(
                checked(head(repeat_cost="low"), run=None)
            ),
            [],
        )

    def test_a_predecessor_whose_records_do_not_read_holds_the_replacement(self):
        broken = area_evidence(unreadable=["audits/x.toml: not TOML"])
        with mock.patch.object(
            report_replacement.evidence, "read_evidence", return_value=broken
        ):
            (gap,) = report_replacement._predecessor_open(
                checked(head(repeat_cost="low"), run=None), AREA / "PROTOCOL-old.md"
            )
        self.assertEqual(gap.rule, TECHNICAL_RULE)
        self.assertIn("audits/x.toml: not TOML", gap.text)


if __name__ == "__main__":
    unittest.main()
