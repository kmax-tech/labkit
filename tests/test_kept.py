"""A computation's kept number, registered in the head's `[kept]` table
(standard 0.24, docs/notes/2026-11-01-kept-key-in-the-head.md): the
metrics key and its unit, read in one place (`protocol_block.kept`), owed
or refused by kind in one (`protocol_check.kept_gaps`), filled by
`protocol-fill kept.key=… kept.unit=…`, held to the answering run by
finalize (`run_record_check.kept_number_gaps`, a guaranteed blocker) and
rendered first in the Recorded results line. Each blocking check has its
twin: the correct variant passes.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from labkit.checks import result_render
from labkit.checks.run_record_check import kept_number_gaps
from labkit.formats import gate, protocol_block, protocol_check
from labkit.gates import finalize
from labkit.tools import protocol_edit
from protocol_fixture import completed_run, head, scope_file

RUN = "2026-11-01T10-00-00_abcd"


def compute(kept: tuple[str, str] | None = ("HRV_MeanNN", "ms"), **kw) -> str:
    """A low compute head with KEPT as its `[kept]` (None: no table)."""
    return head(repeat_cost="low", kind="compute", promises=None, kept=kept, **kw)


def with_table(body: str, kind: str = "compute") -> str:
    """A low head of KIND with BODY as its `[kept]` table, written verbatim."""
    text = head(repeat_cost="low", kind=kind, promises=None, kept=None)
    return text.replace("```\n", f"\n[kept]\n{body}```\n", 1).replace(
        "```toml\n\n[kept]", "```toml\n[kept]"
    )


class KeptTable(unittest.TestCase):
    """`[kept]` reads exactly or not at all, like every table of the head."""

    def test_the_table_reads_back(self):
        self.assertEqual(
            protocol_block.kept(compute()), protocol_block.Kept("HRV_MeanNN", "ms")
        )
        self.assertEqual(protocol_block.kept_key(compute()), "HRV_MeanNN")

    def test_no_table_is_none_and_the_key_is_refused_naming_it(self):
        self.assertIsNone(protocol_block.kept(compute(None)))
        with self.assertRaisesRegex(protocol_block.BlockError, r"no \[kept\] table"):
            protocol_block.kept_key(compute(None))

    def test_placeholders_read_as_none_and_are_named_unfilled(self):
        text = compute(("<metrics key>", "<unit>"))
        k = protocol_block.kept(text)
        self.assertEqual(k, protocol_block.Kept(None, None))
        assert k is not None
        self.assertEqual(k.placeholders, ["[kept] key", "[kept] unit"])
        with self.assertRaisesRegex(protocol_block.BlockError, "still the placeholder"):
            protocol_block.kept_key(text)

    def test_malformed_tables_are_refused_by_name(self):
        for body, said in (
            ('key = "n"\n', "missing `unit`"),
            ('unit = "ms"\n', "missing `key`"),
            ('key = "two words"\nunit = "ms"\n', "one word"),
            ('key = 3\nunit = "ms"\n', "one word"),
            ('key = "n"\nunit = ""\n', "non-empty"),
            ('key = "n"\nunit = 1\n', "non-empty"),
            ('key = "n"\nunit = "ms"\nvalue = 3\n', r"unknown field\(s\) \['value'\]"),
        ):
            with self.subTest(body=body):
                with self.assertRaisesRegex(protocol_block.BlockError, said):
                    protocol_block.kept(with_table(body))

    def test_the_writer_reads_back_as_written(self):
        for k in (
            protocol_block.Kept("HRV_MeanNN", "ms"),
            protocol_block.Kept("share", protocol_block.DIMENSIONLESS),
            protocol_block.Kept(None, None),
            protocol_block.Kept("n", None),
        ):
            with self.subTest(kept=k):
                text = with_table(protocol_block.kept_toml(k).split("\n", 1)[1])
                self.assertEqual(protocol_block.kept(text), k)

    def test_the_head_reads_as_without_the_table(self):
        self.assertEqual(
            protocol_block.head(compute()), protocol_block.head(compute(None))
        )


class OwedByKind(unittest.TestCase):
    """A computation owes `[kept]`; a fit or an apply refuses it — named by
    protocol-check and at the start of a low run."""

    def gaps(self, text: str) -> list[str]:
        return protocol_check.kept_gaps(text, protocol_block.head(text))

    def test_a_computation_without_the_table_owes_it(self):
        text = compute(None)
        (gap,) = self.gaps(text)
        self.assertIn('[kept] — kind = "compute" names its kept number', gap)
        self.assertIn(gap, protocol_check.check_fields(text).missing_must)
        self.assertIn(gap, protocol_check.low_registration_missing(text))

    def test_a_placeholder_is_an_unfilled_field(self):
        text = compute(("<metrics key>", "ms"))
        self.assertEqual(self.gaps(text), ["[kept] key"])
        self.assertIn("[kept] key", protocol_check.check_fields(text).missing_must)
        self.assertIn("[kept] key", protocol_check.low_registration_missing(text))

    def test_the_twin_a_filled_table_owes_nothing(self):
        text = compute()
        self.assertEqual(self.gaps(text), [])
        self.assertEqual(
            [m for m in protocol_check.check_fields(text).missing_must if "kept" in m],
            [],
        )

    def test_a_fit_or_an_apply_refuses_the_table(self):
        for kind in ("fit", "apply"):
            with self.subTest(kind=kind):
                text = with_table('key = "n"\nunit = "1"\n', kind=kind)
                (gap,) = self.gaps(text)
                self.assertIn(f'[kept] with kind = "{kind}"', gap)
                self.assertIn("promise keys", gap)
                self.assertIn(gap, protocol_check.check_fields(text).missing_must)

    def test_the_twin_a_fit_without_the_table_owes_nothing(self):
        text = head(repeat_cost="low", kind="fit", kept=None)
        self.assertEqual(self.gaps(text), [])

    def test_a_table_that_does_not_read_is_named_by_its_sentence(self):
        (gap,) = self.gaps(with_table('key = "n"\n'))
        self.assertIn("missing `unit`", gap)


class Filled(unittest.TestCase):
    """`protocol-fill kept.key=… kept.unit=…` sets the stamped placeholders
    the way it sets every head value — inside `[kept]` only."""

    STAMPED = compute(("<metrics key>", "<unit>"))

    def test_both_values_are_filled_inside_the_table(self):
        text = protocol_edit.fill_many(
            self.STAMPED, [("kept.key", "HRV_MeanNN"), ("kept.unit", "ms")]
        )
        self.assertEqual(
            protocol_block.kept(text), protocol_block.Kept("HRV_MeanNN", "ms")
        )

    def test_a_table_label_reads_as_its_key(self):
        for label in ("[kept] key", "kept key", "[kept].key", "KEPT.KEY"):
            with self.subTest(label=label):
                self.assertEqual(protocol_edit.head_label(label), "kept.key")
                text = protocol_edit.fill_many(self.STAMPED, [(label, "n")])
                k = protocol_block.kept(text)
                assert k is not None
                self.assertEqual(k.key, "n")

    def test_a_placeholder_key_elsewhere_in_the_block_is_not_it(self):
        """A `key = "<…>"` of another table is never taken for `[kept] key`."""
        text = self.STAMPED.replace(
            "[kept]\n", '[result]\nkey = "<not this one>"\n\n[kept]\n', 1
        )
        self.assertEqual(
            protocol_edit.head_open(text, "kept.key"),
            text.splitlines().index('key = "<metrics key>"') + 1,
        )

    def test_a_filled_value_is_refused_without_force(self):
        with self.assertRaisesRegex(ValueError, "already set"):
            protocol_edit.fill_many(compute(), [("kept.key", "other")])

    def test_a_head_without_the_table_names_how_to_add_it(self):
        with self.assertRaisesRegex(ValueError, r"no \[kept\] table to fill"):
            protocol_edit.fill_many(compute(None), [("kept.key", "n")])

    def test_the_list_names_the_open_values_with_what_they_take(self):
        self.assertIsNotNone(protocol_edit.head_open(self.STAMPED, "kept.key"))
        self.assertIsNotNone(protocol_edit.head_open(self.STAMPED, "kept.unit"))
        self.assertIsNone(protocol_edit.head_open(compute(), "kept.key"))
        self.assertIn("metrics.json key", protocol_edit.HEAD_HINTS["kept.key"])


class HeldToTheRun(unittest.TestCase):
    """The guaranteed gate: the answering run holds the `[kept] key` as a
    finite number — what task 34's `hrv_computed = 1` would not pass."""

    def test_a_flag_text_nan_or_a_missing_key_blocks_naming_what_it_holds(self):
        area = Path("experiments/01-hrv")
        for metrics, said in (
            ({"hrv_computed": True}, "holds no `HRV_MeanNN`"),
            ({"HRV_MeanNN": True}, "holds `HRV_MeanNN` = True, which is no finite"),
            ({"HRV_MeanNN": "694 ms"}, "holds `HRV_MeanNN` = '694 ms'"),
            ({"HRV_MeanNN": float("nan")}, "holds `HRV_MeanNN` = nan"),
            ({"HRV_MeanNN": None}, "holds `HRV_MeanNN` = None"),
        ):
            with self.subTest(metrics=metrics):
                (gap,) = kept_number_gaps("HRV_MeanNN", metrics, RUN, area)
                self.assertIn(f"metrics.json of {RUN} {said}", gap.text)
                self.assertEqual(gap.grade, gate.BLOCKER)
                self.assertEqual(gap.evidence_kind, gate.GUARANTEED)
                self.assertIn("write `HRV_MeanNN` as a finite number", gap.fix or "")
                self.assertIn("measure anew", gap.fix or "")
        (gap,) = kept_number_gaps("HRV_MeanNN", {"hrv_computed": True}, RUN, area)
        self.assertIn("it holds hrv_computed = True", gap.text)

    def test_the_twin_a_finite_number_passes(self):
        for value in (694.07, 0, -3, 12):
            with self.subTest(value=value):
                self.assertEqual(
                    kept_number_gaps(
                        "HRV_MeanNN", {"HRV_MeanNN": value, "n": 3}, RUN, Path(".")
                    ),
                    [],
                )

    def area_with_run(self, metrics: dict, kept=("HRV_MeanNN", "ms")) -> Path:
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        scope_file(area)
        (area / "PROTOCOL-x.md").write_text(compute(kept, result=RUN), encoding="utf-8")
        completed_run(area, RUN, metrics=metrics, kept_number=False)
        return area

    def blocked(self, area: Path) -> list[str]:
        collected = gate.Findings(tell=None)
        finalize.finalize_area(area, area / "PROTOCOL-x.md", collected)
        return [b for b in collected.blocked if "kept" in b]

    def test_finalize_blocks_a_run_without_the_kept_number(self):
        (line,) = self.blocked(self.area_with_run({"hrv_computed": 1}))
        self.assertIn(f"metrics.json of {RUN} holds no `HRV_MeanNN`", line)
        self.assertIn("it holds hrv_computed = 1", line)

    def test_the_twin_finalize_passes_the_kept_number(self):
        self.assertEqual(self.blocked(self.area_with_run({"HRV_MeanNN": 694.07})), [])

    def test_finalize_blocks_a_computation_whose_kept_key_is_unfilled(self):
        (line,) = self.blocked(
            self.area_with_run({"HRV_MeanNN": 694.07}, ("<metrics key>", "ms"))
        )
        self.assertIn("[kept] key is still the placeholder", line)
        self.assertIn("protocol-fill", line)
        self.assertIn('"kept.key=<value>"', line)


class Rendered(unittest.TestCase):
    """The kept number comes first in the Recorded results line, named with
    its unit; the other metrics stay, as recorded."""

    def test_the_kept_number_first_then_the_rest(self):
        line = result_render.recorded_results_line(
            {"n_beats": 120, "HRV_MeanNN": 694.07, "hrv_computed": True},
            RUN,
            kept=protocol_block.Kept("HRV_MeanNN", "ms"),
        )
        self.assertEqual(
            line,
            f"kept number: HRV_MeanNN = 694.07 ms; also recorded: n_beats = 120, "
            f"hrv_computed = True (run {RUN})",
        )

    def test_a_dimensionless_number_writes_no_unit(self):
        line = result_render.recorded_results_line(
            {"share": 0.3}, RUN, kept=protocol_block.Kept("share", "1")
        )
        self.assertEqual(line, f"kept number: share = 0.3 (run {RUN})")

    def test_the_twin_without_kept_the_values_stand_as_recorded(self):
        metrics = {"n_beats": 120, "HRV_MeanNN": 694.07}
        self.assertEqual(
            result_render.recorded_results_line(metrics, RUN),
            f"n_beats = 120, HRV_MeanNN = 694.07 (run {RUN})",
        )
        # a kept key the run does not hold: nothing invented, finalize blocks
        self.assertEqual(
            result_render.recorded_results_line(
                metrics, RUN, kept=protocol_block.Kept("HRV_RMSSD", "ms")
            ),
            f"n_beats = 120, HRV_MeanNN = 694.07 (run {RUN})",
        )


if __name__ == "__main__":
    unittest.main()
