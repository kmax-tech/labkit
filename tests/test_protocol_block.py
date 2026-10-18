"""protocol_block: the head is read exactly, and every malformed field is loud."""

import unittest

from labkit import protocol_block
from protocol_fixture import PID, head


class Head(unittest.TestCase):
    def test_reads_every_field(self):
        h = protocol_block.head(
            "# P\n"
            + head(
                cost="seconds", frozen=True, preflight_audit="2026-10-07 · 0 findings"
            )
        )
        self.assertEqual(
            (
                h.standard,
                h.id,
                h.type,
                h.cost,
                h.instrument,
                h.frozen,
                h.preflight_audit,
            ),
            (
                "0.20",
                PID,
                "exploratory",
                "seconds",
                "apply",
                True,
                "2026-10-07 · 0 findings",
            ),
        )
        self.assertEqual(h.placeholders, [])

    def test_placeholders_read_as_none(self):
        h = protocol_block.head(
            head(
                id="<protocol-id>",
                type="<exploratory | confirmatory>",
                cost="<seconds | minutes | hours>",
                preflight_audit="<date · scope sha>",
            )
        )
        self.assertEqual(
            (h.id, h.type, h.cost, h.preflight_audit), (None, None, None, "")
        )
        self.assertEqual(h.placeholders, ["id", "type", "cost"])

    def assertRejects(self, text: str, fragment: str):
        with self.assertRaises(protocol_block.BlockError) as cm:
            protocol_block.head(text)
        self.assertIn(fragment, str(cm.exception))

    def test_a_typo_in_a_choice_is_loud(self):
        # `Cost: second` used to read as undeclared, i.e. as `hours`
        self.assertRejects(
            head(cost="second"), "cost = 'second' — one of seconds, minutes, hours"
        )
        self.assertRejects(head(type="measurement"), "type = 'measurement'")

    def test_frozen_must_be_a_boolean(self):
        self.assertRejects(
            head().replace("frozen = false", 'frozen = "yes"'), "true or false"
        )

    def test_malformed_id(self):
        self.assertRejects(head(id="p-XYZ"), "16 lowercase hex")

    def test_missing_and_unknown_fields(self):
        self.assertRejects(head().replace('cost = "minutes"\n', ""), "missing cost")
        self.assertRejects(
            head().replace("frozen = false", "frozen = false\nowner = 'x'"),
            "unknown field(s) ['owner']",
        )

    def test_other_standard_names_the_way_out(self):
        self.assertRejects(head().replace('"0.20"', '"0.19"'), "use the labkit release")

    def test_no_block_or_no_table(self):
        self.assertRejects("# P\n- **Standard:** 0.16\n", "no [protocol] table")
        self.assertRejects(
            '```toml\n[[promise]]\nid = "C1"\n```\n', "no [protocol] table"
        )

    def test_two_blocks(self):
        self.assertRejects(head() + head(), "exactly one")

    def test_invalid_toml(self):
        self.assertRejects("```toml\n[protocol\n```\n", "not valid TOML")


if __name__ == "__main__":
    unittest.main()
