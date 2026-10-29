"""A computation compared with a stated value: the `[reference]` table of
the head (docs/notes/2026-10-29-reference-comparison.md). Three states,
each its own: no reference (a pure computation, nothing owed), compared
(met or not met — a miss is a valid outcome), not comparable (the
registered key absent from the run's metrics, or no finite number — a
blocker, no "met" rendered). The table is read in one place
(`protocol_block.reference`), judged in one (`reference.reference_verdict`)
and refused on a kind with a bar in one (`protocol_check.reference_gap`).
"""

from __future__ import annotations

import unittest

from labkit.formats import protocol_block, protocol_check
from protocol_fixture import head  # noqa: E402

WITHIN = 'key = "lines_mean"\nvalue = 0.62\ntolerance = 0.01\nrelation = "within"\n'
AT_LEAST = 'key = "lines_mean"\nvalue = 0.2\nrelation = "at_least"\n'


def compute(reference: str | None) -> str:
    """A low compute head, with REFERENCE as its `[reference]` table."""
    return head(repeat_cost="low", kind="compute", promises=None, reference=reference)


class ReferenceTable(unittest.TestCase):
    """`[reference]` reads exactly or not at all, like every table of the head."""

    def test_no_table_is_a_pure_computation(self):
        self.assertIsNone(protocol_block.reference(compute(None)))

    def test_the_table_reads_back_with_its_source(self):
        ref = protocol_block.reference(
            compute(WITHIN + 'source = "the project\'s expectation (task text)"\n')
        )
        self.assertEqual(
            ref,
            protocol_block.Reference(
                key="lines_mean",
                value=0.62,
                tolerance=0.01,
                relative=False,
                relation="within",
                source="the project's expectation (task text)",
            ),
        )
        assert ref is not None
        self.assertEqual(ref.absolute_tolerance, 0.01)

    def test_a_relative_tolerance_is_a_fraction_of_the_value(self):
        ref = protocol_block.reference(
            compute(
                'key = "k"\nvalue = -2.0\ntolerance = 0.5\nrelative = true\nrelation = "within"\n'
            )
        )
        assert ref is not None
        self.assertTrue(ref.relative)
        self.assertEqual(ref.absolute_tolerance, 1.0)

    def test_at_least_carries_no_tolerance_and_no_source_is_none(self):
        ref = protocol_block.reference(compute(AT_LEAST))
        assert ref is not None
        self.assertEqual((ref.tolerance, ref.relative, ref.source), (None, False, None))
        self.assertIsNone(ref.absolute_tolerance)

    def test_the_head_and_the_promises_read_as_without_the_table(self):
        text = compute(WITHIN)
        self.assertEqual(protocol_block.head(text), protocol_block.head(compute(None)))

    def test_malformed_tables_are_refused_by_name(self):
        cases = (
            ('value = 0.62\nrelation = "within"\ntolerance = 0.01\n', "missing `key`"),
            ('key = "k"\nrelation = "within"\ntolerance = 0.01\n', "missing `value`"),
            ('key = "k"\nvalue = 0.62\ntolerance = 0.01\n', "missing `relation`"),
            ('key = "k"\nvalue = "0.62"\nrelation = "at_least"\n', "finite number"),
            ('key = "k"\nvalue = true\nrelation = "at_least"\n', "finite number"),
            ('key = "k"\nvalue = inf\nrelation = "at_least"\n', "finite number"),
            ('key = "k"\nvalue = 0.62\nrelation = "within"\n', "missing `tolerance`"),
            (
                'key = "k"\nvalue = 0.62\nrelation = "within"\ntolerance = -0.1\n',
                "finite number >= 0",
            ),
            (
                'key = "k"\nvalue = 0.62\nrelation = "at_least"\ntolerance = 0.1\n',
                "takes no tolerance",
            ),
            (
                'key = "k"\nvalue = 0.62\nrelation = "at_most"\nrelative = true\n',
                "takes no tolerance",
            ),
            (
                'key = "k"\nvalue = 0.62\nrelation = "near"\n',
                "one of within, at_least, at_most",
            ),
            (
                'key = "k"\nvalue = 0.62\nrelation = "within"\ntolerance = 0.1\nrelative = 1\n',
                "relative = 1 — true or false",
            ),
            ('key = "two words"\nvalue = 0.62\nrelation = "at_least"\n', "one word"),
            (
                'key = "k"\nvalue = 0.62\nrelation = "at_least"\nsource = ""\n',
                "non-empty",
            ),
            (
                'key = "k"\nvalue = 0.62\nrelation = "at_least"\nunit = "ms"\n',
                r"unknown field\(s\) \['unit'\]",
            ),
        )
        for body, said in cases:
            with self.subTest(body=body):
                with self.assertRaisesRegex(protocol_block.BlockError, said):
                    protocol_block.reference(compute(body))

    def test_the_writer_reads_back_as_written(self):
        for body in (
            WITHIN,
            AT_LEAST,
            'key = "k"\nvalue = 3\ntolerance = 0.5\nrelative = true\nrelation = "within"\nsource = "the task"\n',
        ):
            with self.subTest(body=body):
                ref = protocol_block.reference(compute(body))
                assert ref is not None
                text = compute(protocol_block.reference_toml(ref).split("\n", 1)[1])
                self.assertEqual(protocol_block.reference(text), ref)


class OnAKindWithABar(unittest.TestCase):
    """Twin 5: a fit or an apply compares in [C]; the table is refused
    there, naming [C] — by `protocol-check` and at the start of a low run."""

    def test_a_fit_and_an_apply_head_are_refused_naming_c(self):
        for kind in ("fit", "apply"):
            with self.subTest(kind=kind):
                text = head(repeat_cost="low", kind=kind, reference=WITHIN)
                gap = protocol_check.reference_gap(text, protocol_block.head(text))
                assert gap is not None
                self.assertIn("[C]", gap)
                self.assertIn(f'kind = "{kind}"', gap)
                report = protocol_check.check_fields(text)
                self.assertIn(gap, report.missing_must)
                self.assertIn(gap, protocol_check.low_registration_missing(text))

    def test_the_twin_a_compute_head_carries_it_without_a_finding(self):
        text = compute(WITHIN)
        self.assertIsNone(protocol_check.reference_gap(text, protocol_block.head(text)))
        self.assertEqual(
            [
                m
                for m in protocol_check.check_fields(text).missing_must
                if "reference" in m
            ],
            [],
        )

    def test_a_table_that_does_not_read_is_the_head_checks_not_the_kinds(self):
        text = head(repeat_cost="low", kind="fit", reference='key = "k"\n')
        self.assertIsNone(protocol_check.reference_gap(text, protocol_block.head(text)))


class RegistrationStamp(unittest.TestCase):
    """The stated value is part of the registration an audit judged: a
    change, an addition or a drop after the audit is drift; a protocol
    without the table carries no key, so earlier records drift nowhere."""

    def test_no_table_no_key(self):
        self.assertNotIn(
            protocol_check.REGISTRATION_REFERENCE,
            protocol_check.registration_stamp(compute(None)),
        )

    def test_a_changed_added_or_dropped_reference_is_drift(self):
        plain = protocol_check.registration_stamp(compute(None))
        stated = protocol_check.registration_stamp(compute(WITHIN))
        moved = protocol_check.registration_stamp(
            compute(WITHIN.replace("0.62", "0.6"))
        )
        self.assertEqual(
            protocol_check.registration_drift(stated, moved), ["reference"]
        )
        self.assertEqual(
            protocol_check.registration_drift(plain, stated), ["reference"]
        )
        self.assertEqual(
            protocol_check.registration_drift(stated, plain), ["reference"]
        )
        self.assertEqual(protocol_check.registration_drift(stated, stated), [])

    def test_a_source_reworded_is_drift_too(self):
        a = protocol_check.registration_stamp(compute(WITHIN + 'source = "the task"\n'))
        b = protocol_check.registration_stamp(compute(WITHIN + 'source = "a paper"\n'))
        self.assertEqual(protocol_check.registration_drift(a, b), ["reference"])


if __name__ == "__main__":
    unittest.main()
