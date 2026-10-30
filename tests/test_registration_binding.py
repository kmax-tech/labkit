"""Tests for the registration an audit record binds (`[audit] registration`,
`protocol_check.registration_stamp`).

Why this exists (review 2026-10-23, finding 1): the question was rewritten
after the number was adopted — "mean line count" became "mean number of
causal claims" — and the analysis audit still covered the area; report-check
exited 0. A record bound the code, the promise tables and the run, not the
registration the audit judged. Now it binds the kind and every field the
kind owes; the report fields written after the run do not move it.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import findings, promises, protocol_check, scope_sha  # noqa: E402
from protocol_fixture import DEFAULT_BLOCK, head, scope_file  # noqa: E402

BODY = """
- **Question / hypothesis:** what is the mean line count per case?
- **Success / failure criterion:** [criterion-1] above the trivial decider
- **Admissibility condition:** [quality-check-1] every case parsed
- **Null condition / anchors (in the same run):** [quality-check-2] shuffled labels at chance
"""


def _protocol(kind: str = "fit") -> str:
    return (
        head(repeat_cost="high", kind=kind, frozen=True, promises=DEFAULT_BLOCK) + BODY
    )


class Stamp(unittest.TestCase):
    def test_the_fields_the_kind_owes_and_the_kind(self):
        stamp = protocol_check.registration_stamp(_protocol("fit"))
        self.assertEqual(
            list(stamp),
            [
                "kind",
                "Question / hypothesis",
                "Success / failure criterion",
                "Admissibility condition",
                "Null condition / anchors",
            ],
        )
        self.assertEqual(stamp["kind"], "fit")
        compute = protocol_check.registration_stamp(_protocol("compute"))
        self.assertEqual(list(compute), ["kind", "Question / hypothesis"])

    def test_a_reflowed_field_keeps_its_stamp_and_a_reworded_one_does_not(self):
        text = _protocol()
        stamp = protocol_check.registration_stamp(text)
        reflowed = text.replace("line count per", "line count\n  per")
        self.assertEqual(protocol_check.registration_stamp(reflowed), stamp)
        reworded = text.replace("line count", "number of causal claims")
        self.assertEqual(
            protocol_check.registration_drift(
                stamp, protocol_check.registration_stamp(reworded)
            ),
            ["Question / hypothesis"],
        )

    def test_report_fields_are_not_part_of_it(self):
        text = _protocol()
        written = text + "- **Conclusion:** eleven lines.\n- **Limits:** one corpus.\n"
        self.assertEqual(
            protocol_check.registration_stamp(written),
            protocol_check.registration_stamp(text),
        )

    def test_a_missing_field_and_an_unreadable_head_are_named_not_raised(self):
        stamp = protocol_check.registration_stamp("no head, no fields\n")
        self.assertEqual(stamp["kind"], protocol_check.REGISTRATION_ABSENT)
        self.assertEqual(
            stamp["Question / hypothesis"], protocol_check.REGISTRATION_ABSENT
        )


class PreflightRecord(unittest.TestCase):
    """The record the head names (`audit_record_gap`) is held to the
    registration it judged, and the refusal names what changed."""

    def setUp(self):
        self.area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)

    def _record(self, text: str) -> str:
        return findings.write(
            self.area,
            "preflight",
            "opus",
            scope_sha.area_stamp(self.area)[0],
            promises.block_stamp(text),
            (0, 0, 0),
            [],
            registration=protocol_check.registration_stamp(text),
        ).name

    def test_the_record_covers_the_protocol_it_judged(self):
        text = _protocol()
        self.assertIsNone(
            findings.audit_record_gap(self.area, self._record(text), text)
        )

    def test_a_rewritten_question_owes_a_new_audit_and_is_named(self):
        text = _protocol()
        name = self._record(text)
        now = text.replace("line count", "number of causal claims")
        gap = findings.audit_record_gap(self.area, name, now)
        assert gap is not None
        self.assertIn(f"the record {name} no longer covers the protocol", gap.why)
        self.assertIn(
            "the registration changed after the audit (Question / hypothesis)",
            gap.why,
        )

    def test_a_changed_kind_is_named(self):
        text = _protocol("fit")
        name = self._record(text)
        gap = findings.audit_record_gap(self.area, name, _protocol("apply"))
        assert gap is not None
        self.assertIn("(kind)", gap.why)

    def test_each_gap_carries_its_own_way_out(self):
        # an open finding is decided, not audited again; other code is
        text = _protocol()
        open_ = findings.write(
            self.area,
            "preflight",
            "opus",
            scope_sha.area_stamp(self.area)[0],
            promises.block_stamp(text),
            (0, 1, 0),
            [
                (
                    "WARNING",
                    "WARNING · scripts/01_measure.py:1 · x · y · LAB-015 Preflight audit before freezing · z",
                )
            ],
            registration=protocol_check.registration_stamp(text),
        )
        gap = findings.audit_record_gap(self.area, open_.name, text)
        assert gap is not None
        self.assertIn("still `open`", gap.why)
        self.assertEqual(
            gap.fix,
            findings.decide_way(
                self.area, findings.open_findings([findings.read(open_)])[0]
            ),
        )
        name = self._record(text)
        gap = findings.audit_record_gap(
            self.area, name, text.replace("line count", "x")
        )
        assert gap is not None
        self.assertEqual(gap.fix, findings.audit_way(self.area))

    def test_a_record_without_the_registration_is_no_longer_read(self):
        text = _protocol()
        path = self.area / findings.DIR / self._record(text)
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        path.write_text(
            "".join(ln for ln in lines if not ln.startswith("registration =")),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(findings.FindingsError, "run the audit again"):
            findings.read(path)


if __name__ == "__main__":
    unittest.main()
