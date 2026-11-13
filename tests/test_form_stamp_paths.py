"""What `--report` on an existing area and `--change-kind` write into the
protocol, through real areas, for every kind, cost and model.

- `--report` at low repeat cost leaves the protocol as it was (nothing
  freezes there); at high repeat cost the result matches the kept file
  (`form_stamps_fixture.report_file`), and a protocol without its report
  fields gains the full form's fields with the full form's placeholders
  (`scaffold.report_blocks`; docs/notes/2026-11-13-protocol-field-selection-plan.md).
- `--change-kind` on an unfilled protocol writes exactly the stamp of the
  new kind under the same id, short form or report form. Carrying the
  author's fields is held in `test_scaffold.py`.
"""

from __future__ import annotations

import tempfile
import unittest

import pytest

from form_stamps_fixture import (
    COSTS,
    FIXED_ID,
    KINDS,
    MODELS,
    fixed_id,
    lab,
    quiet,
    report_file,
    reported,
    stamped,
)
from labkit.formats import protocol_check
from labkit.tools import protocol_cuts, scaffold

pytestmark = pytest.mark.slow


class ReportOnAnArea(unittest.TestCase):
    def test_low_repeat_cost_leaves_the_protocol_unchanged(self) -> None:
        for kind in KINDS:
            for model in MODELS:
                with self.subTest(kind=kind, model=model):
                    with tempfile.TemporaryDirectory() as tmp:
                        before, after = reported(lab(tmp), "low", kind, model)
                    self.assertEqual(after, before)

    def test_high_repeat_cost_matches_the_kept_file(self) -> None:
        for kind in KINDS:
            for model in MODELS:
                with self.subTest(kind=kind, model=model):
                    with tempfile.TemporaryDirectory() as tmp:
                        _, after = reported(lab(tmp), "high", kind, model)
                    kept = report_file(kind, model)
                    self.assertEqual(
                        after,
                        kept.read_text(encoding="utf-8"),
                        f"differs from {kept.name}",
                    )

    def test_the_fields_it_adds_are_the_full_forms(self) -> None:
        # a protocol without its report fields gains the full form's: the same
        # fields, each with the same placeholder (placed at its section's end)
        for kind in KINDS:
            for model in MODELS:
                with self.subTest(kind=kind, model=model):
                    with tempfile.TemporaryDirectory() as tmp:
                        root = lab(tmp)
                        area, _ = quiet(
                            scaffold.stamp_area,
                            root,
                            "x",
                            repeat_cost="high",
                            kind=kind,
                            model=model,
                        )
                        protocol = area / "PROTOCOL-x.md"
                        full = protocol.read_text(encoding="utf-8")
                        protocol.write_text(
                            protocol_cuts.pilot_and_report(full)[0], encoding="utf-8"
                        )
                        quiet(scaffold.stamp_area, root, "x", report=True)
                        after = protocol.read_text(encoding="utf-8")
                    self.assertEqual(self.values(after), self.values(full))

    @staticmethod
    def values(text: str) -> dict[str, str]:
        """Each field of TEXT by name to its value."""
        return {f.name: f.value for f in protocol_check.fields(text)}


class ChangeKind(unittest.TestCase):
    def test_an_unfilled_protocol_becomes_the_new_kinds_stamp(self) -> None:
        for cost in COSTS:
            for model in MODELS:
                for report in (False, True):
                    for old in KINDS:
                        for new in KINDS:
                            if old == new:
                                continue
                            with self.subTest(
                                cost=cost, model=model, report=report, old=old, new=new
                            ):
                                self.assertEqual(
                                    self.changed(cost, model, report, old, new),
                                    self.fresh(cost, model, report, new),
                                )

    @staticmethod
    def changed(cost: str, model: bool | str, report: bool, old: str, new: str) -> str:
        """The protocol of a new area of kind OLD after `--change-kind NEW`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = lab(tmp)
            area, _ = quiet(
                scaffold.stamp_area,
                root,
                "x",
                repeat_cost=cost,
                kind=old,
                model=model,
                report=report,
            )
            quiet(scaffold.change_kind, root, "x", new)
            return fixed_id((area / "PROTOCOL-x.md").read_text(encoding="utf-8"))

    @staticmethod
    def fresh(cost: str, model: bool | str, report: bool, kind: str) -> str:
        """The stamp of KIND under FIXED_ID."""
        with tempfile.TemporaryDirectory() as tmp:
            text = stamped(lab(tmp), cost, kind, model, report)
        assert FIXED_ID in text
        return text


if __name__ == "__main__":
    unittest.main()
