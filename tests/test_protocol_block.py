"""protocol_block: the head is read exactly, and every malformed field is loud."""

import tomllib
import unittest

from labkit.formats import protocol_block
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
            (h.standard, h.id, h.type, h.cost, h.frozen, h.preflight_audit),
            ("0.19", PID, "exploratory", "seconds", True, "2026-10-07 · 0 findings"),
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
        self.assertRejects(head().replace('"0.19"', '"0.18"'), "use the labkit release")

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


class TomlString(unittest.TestCase):
    """`toml_string` is the one writer of a TOML string labkit writes (a
    promise sentence, a finding's reason and effect). Until now it was held
    only through its callers; this table holds the writer itself: every
    value reads back through tomllib unchanged and stays on one line, so the
    fence walker and the one-line decision regex never cut it."""

    TRICKY = (
        'a "quoted" word',
        "back\\slash",
        "ends with \\",
        "line\nbreak",
        "tab\there",
        "del\x7fx",
        "nel\x85x",
        "ls\u2028x and ps\u2029y",
        "émoji 🧪",
        "it's",
        "",
        " leading and trailing ",
        "#not a comment",
        "'''",
        '"""',
        "key = value",
    )

    def test_every_tricky_value_reads_back_on_one_line(self):
        for value in self.TRICKY:
            with self.subTest(value=value):
                written = protocol_block.toml_string(value)
                self.assertEqual(len(written.splitlines()), 1, written)
                self.assertEqual(tomllib.loads(f"x = {written}")["x"], value)

    def test_a_lone_surrogate_is_refused_with_the_cause(self):
        with self.assertRaisesRegex(ValueError, "lone surrogate U\\+D800.*UTF-8"):
            protocol_block.toml_string("bad \ud800 byte")
