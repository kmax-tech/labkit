"""What `--report` on an existing area and `--change-kind` write into the
protocol, through real areas, for every kind, cost and model.

- `--report` at low repeat cost leaves the protocol as it was (nothing
  freezes there); at high repeat cost the result matches the kept file
  (`form_stamps_fixture.report_file`). Kept as found on 2026-11-13: a
  computation gains Noise ceiling, and without a model Answer form +
  resolution, which its full form leaves out — whether it should is a
  separate decision (docs/notes/2026-11-13-protocol-field-selection-plan.md).
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
from labkit.tools import scaffold

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
