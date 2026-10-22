"""protocol_block: the head is read exactly, and every malformed field is loud."""

import tomllib
import unittest

from labkit.formats import protocol_block
from protocol_fixture import PID, head
from labkit.formats import promises


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
            ("0.21", PID, "exploratory", "seconds", True, "2026-10-07 · 0 findings"),
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
        self.assertRejects(head().replace('"0.21"', '"0.18"'), "use the labkit release")

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


RUN = "2026-10-21T13-40-06_ad5f"


def with_result(block: str, body: str) -> str:
    """BLOCK with BODY appended inside its fence, before the closing ```."""
    k = block.rindex("```")
    return block[:k] + body.rstrip("\n") + "\n" + block[k:]


class DeclaredRun(unittest.TestCase):
    """`[result] run` is the one declaration that a protocol reports a
    number (phase 3 of the 1.0 line, 2026-10-21): absent while exploring,
    written by `protocol-fill --from-run`, exact or unreadable — a typed id
    that is no run id runlog writes is refused where it stands, not read as
    a citation the gates then chase."""

    def test_no_table_is_no_declaration(self):
        self.assertIsNone(protocol_block.declared_run(head(cost="seconds")))

    def test_the_declared_run_reads_back_and_leaves_head_and_promises_alone(self):
        plain = head(cost="seconds")
        text = with_result(plain, f'\n[result]\nrun = "{RUN}"\n')
        self.assertEqual(protocol_block.declared_run(text), RUN)
        self.assertEqual(protocol_block.head(text), protocol_block.head(plain))
        self.assertEqual(promises.block_stamp(text), promises.block_stamp(plain))

    def test_a_typed_id_an_unknown_key_and_a_scalar_are_refused_by_name(self):
        cases = (
            (
                '\n[result]\nrun = "2026-10-21T12-48-00_final"\n',
                "no run id runlog writes",
            ),
            (
                f'\n[result]\nrun = "{RUN}"\nreported = true\n',
                r"unknown field\(s\) \['reported'\]",
            ),
            ("\n[result]\n", "missing `run`"),
        )
        for body, said in cases:
            with self.subTest(body=body):
                with self.assertRaisesRegex(protocol_block.BlockError, said):
                    protocol_block.declared_run(with_result(head(cost="seconds"), body))
        # a scalar `result = …` standing before the tables is no table
        scalar = head(cost="seconds").replace(
            "```toml\n", f'```toml\nresult = "{RUN}"\n', 1
        )
        with self.assertRaisesRegex(protocol_block.BlockError, "must be a table"):
            protocol_block.declared_run(scalar)


class ModelTable(unittest.TestCase):
    """`[model]` says a model is in the loop (phase 4 of the 1.0 line,
    2026-10-21): the alias, the compared arms finalize holds to the run;
    absent is a count or an estimator. Exact or unreadable, like the head."""

    def test_no_table_is_no_model(self):
        self.assertIsNone(protocol_block.model(head(cost="seconds")))

    def test_the_alias_and_the_arms_read_back(self):
        text = head(
            cost="seconds",
            model="haiku",
            arms={
                "before": ("register/profiles/b.toml", "bcec0c37236d", None),
                "after": (
                    "register/profiles/a.toml",
                    "1d4c79af596a",
                    "gpt-oss-20b-leguin",
                ),
            },
        )
        m = protocol_block.model(text)
        assert m is not None
        self.assertEqual(m.alias, "haiku")
        self.assertEqual(
            m.arms,
            {
                "before": protocol_block.Arm(
                    "register/profiles/b.toml", "bcec0c37236d", None
                ),
                "after": protocol_block.Arm(
                    "register/profiles/a.toml", "1d4c79af596a", "gpt-oss-20b-leguin"
                ),
            },
        )
        self.assertEqual(
            protocol_block.head(text), protocol_block.head(head(cost="seconds"))
        )
        self.assertEqual(
            promises.block_stamp(text), promises.block_stamp(head(cost="seconds"))
        )

    def test_the_stamps_placeholder_alias_is_a_model_without_a_name(self):
        m = protocol_block.model(head(cost="seconds", model="<alias from models.toml>"))
        assert m is not None
        self.assertIsNone(m.alias)
        self.assertEqual(m.arms, {})

    def test_malformed_tables_are_refused_by_name(self):
        cases = (
            ('\n[model]\nalias = ""\n', "non-empty string"),
            (
                '\n[model]\nalias = "haiku"\nmodel = "x"\n',
                r"unknown field\(s\) \['model'\]",
            ),
            ("\n[model]\narms = {}\n", "missing `alias`"),
            (
                '\n[model]\nalias = "haiku"\n[model.arms.before]\nprofile = "x.toml"\n',
                r"\[model.arms.before\]: missing `fingerprint`",
            ),
            (
                '\n[model]\nalias = "haiku"\n[model.arms.before]\nprofile = "x.toml"\nfingerprint = "zz"\n',
                "8 to 64 hex digits",
            ),
            ("\n[gate]\nlabels = []\n", "non-empty list"),
            ('\n[gate]\nlabels = ["a", 1]\n', "non-empty list"),
            ('\n[gate]\naccepts = ["a"]\n', r"unknown field\(s\) \['accepts'\]"),
        )
        for body, said in cases:
            with self.subTest(body=body):
                with self.assertRaisesRegex(protocol_block.BlockError, said):
                    text = with_result(head(cost="seconds"), body)
                    protocol_block.model(text)
                    protocol_block.declared_labels(text)

    def test_gate_labels_read_back_and_absent_is_none(self):
        self.assertIsNone(protocol_block.declared_labels(head(cost="seconds")))
        text = head(cost="seconds", labels=("causal", "not_causal"))
        self.assertEqual(protocol_block.declared_labels(text), ("causal", "not_causal"))
