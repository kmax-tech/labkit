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

import sys
import unittest
from pathlib import Path

from labkit.formats import protocol_block, protocol_check, reference
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
                self.assertIn("in a criterion", gap)
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


def ref_of(body: str) -> protocol_block.Reference:
    ref = protocol_block.reference(compute(body))
    assert ref is not None
    return ref


class Verdict(unittest.TestCase):
    """`reference_verdict` is the one home: three states, every relation."""

    def test_within_met_and_not_met_with_the_distance(self):
        ref = ref_of(WITHIN)
        met = reference.reference_verdict(0.625, ref)
        self.assertEqual(
            met,
            {
                "ref_state": "compared",
                "ref_met": True,
                "ref_distance": abs(0.625 - 0.62),
                "ref_value": 0.62,
                "ref_tolerance": 0.01,
                "ref_relation": "within",
            },
        )
        missed = reference.reference_verdict(0.475, ref)
        self.assertEqual(missed["ref_met"], False)
        self.assertEqual(missed["ref_distance"], abs(0.475 - 0.62))
        # exact float arithmetic, no rounding: 0.63 - 0.62 exceeds 0.01 by
        # float noise and reads as not met — the recorded distance says so
        self.assertEqual(reference.reference_verdict(0.628, ref)["ref_met"], True)
        self.assertEqual(reference.reference_verdict(0.63, ref)["ref_met"], False)

    def test_at_least_and_at_most_carry_no_tolerance(self):
        at_least = ref_of(AT_LEAST)
        self.assertEqual(reference.reference_verdict(0.2, at_least)["ref_met"], True)
        self.assertEqual(reference.reference_verdict(0.19, at_least)["ref_met"], False)
        self.assertIsNone(reference.reference_verdict(0.2, at_least)["ref_tolerance"])
        at_most = ref_of(AT_LEAST.replace("at_least", "at_most"))
        self.assertEqual(reference.reference_verdict(0.2, at_most)["ref_met"], True)
        self.assertEqual(reference.reference_verdict(0.21, at_most)["ref_met"], False)

    def test_a_relative_tolerance_is_resolved_to_the_keys_unit(self):
        ref = ref_of(
            'key = "k"\nvalue = 2.0\ntolerance = 0.1\nrelative = true\nrelation = "within"\n'
        )
        v = reference.reference_verdict(2.15, ref)
        self.assertEqual(v["ref_tolerance"], 0.2)
        self.assertEqual(v["ref_met"], True)

    def test_absent_or_no_finite_number_is_not_comparable(self):
        ref = ref_of(WITHIN)
        for measured in (None, "0.62", True, float("nan"), float("inf"), [0.62]):
            with self.subTest(measured=measured):
                v = reference.reference_verdict(measured, ref)
                self.assertEqual(
                    (v["ref_state"], v["ref_met"], v["ref_distance"]),
                    ("not comparable", None, None),
                )
                self.assertEqual(v["ref_value"], 0.62)


class WithVerdict(unittest.TestCase):
    """Twin 1 and 2: no reference, no `ref_*` key; a reference, the verdict
    on the registered key beside the kept number."""

    def test_no_reference_leaves_the_metrics_as_they_are(self):
        metrics = {"lines_mean": 3.0}
        self.assertIs(reference.with_verdict(metrics, None), metrics)

    def test_a_reference_adds_the_verdict_on_its_key(self):
        out = reference.with_verdict({"lines_mean": 0.475}, ref_of(WITHIN))
        self.assertEqual(out["lines_mean"], 0.475)
        self.assertEqual(out["ref_state"], "compared")
        self.assertEqual(out["ref_met"], False)
        self.assertEqual(set(out), {"lines_mean", *reference.VERDICT_KEYS})

    def test_a_key_the_metrics_lack_is_not_comparable(self):
        out = reference.with_verdict(
            {"lines_mean": 3.0}, ref_of(WITHIN.replace("lines_mean", "lines_median"))
        )
        self.assertEqual(out["ref_state"], "not comparable")
        self.assertEqual(out["lines_mean"], 3.0)

    def test_a_verdict_key_written_by_the_formula_is_refused(self):
        with self.assertRaisesRegex(ValueError, "ref_met.*never by evaluate_rows"):
            reference.with_verdict({"lines_mean": 3.0, "ref_met": True}, ref_of(WITHIN))
        with self.assertRaisesRegex(ValueError, "no \\[reference\\] is registered"):
            reference.with_verdict({"ref_state": "compared"}, None)


class Phrase(unittest.TestCase):
    """The comparison as the Recorded results line carries it — from the
    recorded verdict, with every number as `plain_numbers` writes it."""

    def test_met_not_met_and_not_comparable(self):
        ref = ref_of(WITHIN)
        met = reference.with_verdict({"lines_mean": 0.625}, ref)
        self.assertEqual(
            reference.phrase(met, ref),
            f"reference 0.62 ± 0.01 (within): met, distance {abs(0.625 - 0.62)}",
        )
        missed = reference.with_verdict({"lines_mean": 0.475}, ref)
        self.assertEqual(
            reference.phrase(missed, ref),
            f"reference 0.62 ± 0.01 (within): not met, distance {abs(0.475 - 0.62)}",
        )
        absent = reference.with_verdict({"other": 1}, ref)
        self.assertEqual(
            reference.phrase(absent, ref),
            "reference 0.62 ± 0.01 (within): not comparable: lines_mean absent",
        )
        nan = reference.with_verdict({"lines_mean": float("nan")}, ref)
        self.assertEqual(
            reference.phrase(nan, ref),
            "reference 0.62 ± 0.01 (within): not comparable: lines_mean = nan is no finite number",
        )

    def test_at_least_writes_no_tolerance(self):
        ref = ref_of(AT_LEAST)
        out = reference.with_verdict({"lines_mean": 0.25}, ref)
        self.assertEqual(
            reference.phrase(out, ref),
            f"reference 0.2 (at_least): met, distance {abs(0.25 - 0.2)}",
        )

    def test_no_verdict_recorded_is_loud(self):
        with self.assertRaisesRegex(ValueError, "ref_state"):
            reference.phrase({"lines_mean": 1.0}, ref_of(WITHIN))


class ComparisonGaps(unittest.TestCase):
    """Twin 3 and 4 as data: a miss passes; absent, unreadable, unwritten
    or typed beside the number blocks, each naming the key and the way out."""

    def test_a_miss_and_a_pass_are_no_finding(self):
        ref = ref_of(WITHIN)
        for measured in (0.475, 0.625):
            with self.subTest(measured=measured):
                metrics = reference.with_verdict({"lines_mean": measured}, ref)
                self.assertEqual(reference.comparison_gaps(ref, metrics), [])

    def test_no_reference_and_no_key_is_nothing_owed(self):
        self.assertEqual(reference.comparison_gaps(None, {"lines_mean": 3.0}), [])

    def test_a_typed_verdict_without_a_reference_blocks(self):
        (gap,) = reference.comparison_gaps(None, {"lines_mean": 3.0, "ref_met": True})
        self.assertIn("registers no [reference]", gap.text)
        self.assertEqual(gap.evidence_kind, "guaranteed")

    def test_a_reference_the_run_did_not_compare_blocks(self):
        (gap,) = reference.comparison_gaps(ref_of(WITHIN), {"lines_mean": 3.0})
        self.assertIn("recorded no verdict", gap.text)
        self.assertIn("metrics_of()", gap.fix or "")

    def test_not_comparable_blocks_naming_the_key_and_the_way_out(self):
        ref = ref_of(WITHIN.replace("lines_mean", "lines_median"))
        metrics = reference.with_verdict({"lines_mean": 3.0}, ref)
        (gap,) = reference.comparison_gaps(ref, metrics)
        self.assertIn("`lines_median` is absent from metrics.json", gap.text)
        self.assertIn("no verdict can be reported", gap.text)
        self.assertIn("write `lines_median` as a finite number", gap.fix or "")
        self.assertIn("measure anew", gap.fix or "")
        unreadable = reference.with_verdict({"lines_median": float("nan")}, ref)
        (gap,) = reference.comparison_gaps(ref, unreadable)
        self.assertIn("is no finite number", gap.text)

    def test_a_reference_changed_after_the_run_blocks(self):
        ref = ref_of(WITHIN)
        metrics = reference.with_verdict({"lines_mean": 0.625}, ref)
        moved = ref_of(WITHIN.replace("0.62", "0.6"))
        (gap,) = reference.comparison_gaps(moved, metrics)
        self.assertIn("ref_value = 0.62", gap.text)
        self.assertIn("ref_value = 0.6", gap.text)
        self.assertIn("changed after the run", gap.text)


class StampedSkeleton(unittest.TestCase):
    """The compute skeleton's `metrics_of` reads the head: with a
    `[reference]` the verdict stands beside the kept number, without one
    the metrics are evaluate_rows()'s alone."""

    def setUp(self) -> None:
        import contextlib
        import io
        import tempfile

        from labkit.tools import scaffold

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "lab"
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            scaffold.stamp_lab(root, root.name)
            self.area, _ = scaffold.stamp_area(
                root, "lines", repeat_cost="low", kind="compute"
            )
        self.protocol = self.area / "PROTOCOL-lines.md"
        self.measure = _load(self.area / "scripts" / "01_measure.py", "measure_ref")
        self.addCleanup(sys.modules.pop, "measure_ref", None)
        setattr(self.measure, "METRIC_KEY", "lines_mean")
        setattr(
            self.measure,
            "evaluate_rows",
            lambda items, ids: {
                "lines_mean": sum(r["lines"] for r in items) / len(ids)
            },
        )
        self.items = [{"id": "a", "lines": 1}, {"id": "b", "lines": 3}]

    def register(self, body: str) -> None:
        text = self.protocol.read_text(encoding="utf-8")
        k = text.rindex("```")
        self.protocol.write_text(
            text[:k] + "\n[reference]\n" + body + text[k:], encoding="utf-8"
        )

    def test_without_a_reference_the_metrics_are_the_formulas(self):
        self.assertEqual(
            self.measure.metrics_of(self.items, ["a", "b"]), {"lines_mean": 2.0}
        )

    def test_with_a_reference_the_verdict_stands_beside_the_number(self):
        self.register(
            'key = "lines_mean"\nvalue = 2.5\ntolerance = 0.4\nrelation = "within"\n'
        )
        metrics = self.measure.metrics_of(self.items, ["a", "b"])
        self.assertEqual(metrics["lines_mean"], 2.0)
        self.assertEqual(metrics["ref_state"], "compared")
        self.assertEqual(metrics["ref_met"], False)
        self.assertEqual(metrics["ref_distance"], 0.5)

    def test_a_key_the_formula_does_not_write_is_not_comparable(self):
        self.register('key = "lines_median"\nvalue = 2.5\nrelation = "at_least"\n')
        metrics = self.measure.metrics_of(self.items, ["a", "b"])
        self.assertEqual(metrics["ref_state"], "not comparable")
        self.assertIsNone(metrics["ref_met"])


def _load(path: Path, name: str):  # noqa: ANN202 — a test helper
    """The area script at PATH imported under NAME, as the area test loads it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUN = "2026-10-29T10-00-00_abcd"
BODY = (
    "\n## Result\n\n- **Recorded results:** <generated metrics, run_id and limits note>\n"
    "- **Conclusion:** <!-- l --> <the answer>\n\n## Runs\n\n- <run_id> — <one sentence>\n"
)


def area_with_run(reference_body: str | None, metrics: dict) -> tuple[Path, Path]:
    """A low compute area whose protocol declares RUN, with REFERENCE_BODY
    as its `[reference]` (None: a pure computation) and a completed run
    recording METRICS."""
    import tempfile

    from protocol_fixture import completed_run, scope_file

    area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    scope_file(area)
    protocol = area / "PROTOCOL-x.md"
    protocol.write_text(
        head(
            repeat_cost="low",
            kind="compute",
            promises=None,
            result=RUN,
            reference=reference_body,
        )
        + BODY,
        encoding="utf-8",
    )
    completed_run(area, RUN, metrics=metrics)
    return area, protocol


class Rendered(unittest.TestCase):
    """The Recorded results line carries the comparison as the run recorded
    it — generated, bound; a typed variant differs and is refused."""

    def rendered(self, reference_body: str | None, metrics: dict) -> str:
        from labkit.checks import result_render

        area, protocol = area_with_run(reference_body, metrics)
        text = protocol.read_text(encoding="utf-8")
        return result_render.rendering(area, text, area / "runs" / RUN).recorded_results

    def test_twin_1_without_a_reference_the_line_is_as_today(self):
        self.assertEqual(
            self.rendered(None, {"lines_mean": 3.0}), f"lines_mean = 3.0 (run {RUN})"
        )

    def test_met_not_met_and_not_comparable(self):
        ref = ref_of(WITHIN)
        met = reference.with_verdict({"lines_mean": 0.625}, ref)
        self.assertEqual(
            self.rendered(WITHIN, met),
            f"lines_mean = 0.625; reference 0.62 ± 0.01 (within): met, "
            f"distance {abs(0.625 - 0.62)} (run {RUN})",
        )
        missed = reference.with_verdict({"lines_mean": 0.475}, ref)
        self.assertEqual(
            self.rendered(WITHIN, missed),
            f"lines_mean = 0.475; reference 0.62 ± 0.01 (within): not met, "
            f"distance {abs(0.475 - 0.62)} (run {RUN})",
        )
        absent_body = WITHIN.replace("lines_mean", "lines_median")
        absent = reference.with_verdict({"lines_mean": 3.0}, ref_of(absent_body))
        self.assertEqual(
            self.rendered(absent_body, absent),
            f"lines_mean = 3.0; reference 0.62 ± 0.01 (within): not comparable: "
            f"lines_median absent (run {RUN})",
        )

    def test_a_reference_the_run_did_not_compare_renders_no_verdict(self):
        """No "met" the run did not record: the line shows the number alone;
        finalize names the missing verdict."""
        self.assertEqual(
            self.rendered(WITHIN, {"lines_mean": 3.0}), f"lines_mean = 3.0 (run {RUN})"
        )

    def test_the_written_line_is_held_and_a_typed_met_is_refused(self):
        from labkit.checks import recheck, result_render
        from labkit.tools import protocol_fill

        ref = ref_of(WITHIN)
        metrics = reference.with_verdict({"lines_mean": 0.475}, ref)
        area, protocol = area_with_run(WITHIN, metrics)
        text = protocol.read_text(encoding="utf-8")
        expected = result_render.rendering(area, text, area / "runs" / RUN)
        written, _, _ = protocol_fill.from_run(text, area)
        self.assertEqual(result_render.render_gaps(written, expected), [])
        protocol.write_text(written, encoding="utf-8")
        # the check finds every number of the verdict in the note (twin 2)
        recheck.cited(protocol, recheck.plain_numbers(metrics), RUN)
        typed = written.replace("not met, distance", "met, distance")
        self.assertNotEqual(typed, written)
        (gap,) = result_render.render_gaps(typed, expected)
        self.assertIn("differs from its rendering", gap.text)


class AuditorInstruction(unittest.TestCase):
    """Twin 6: the instruction text the auditor reads says a computation
    owes no criterion, and names the WARNING for an unregistered stated
    value — not a BLOCKER for a missing criterion (pressure pilot task 60,
    2026-10-29). A prompt test on the text, whitespace collapsed; the
    SAB-like compute case is audited by hand."""

    @staticmethod
    def one_line(text: str) -> str:
        return " ".join(text.split())

    def instruction(self) -> str:
        from labkit.gates import audit

        return self.one_line(audit.instructions("analysis"))

    def test_a_compute_protocol_owes_no_criterion(self):
        text = self.instruction()
        self.assertIn("## A computation owes no criterion", text)
        self.assertIn("never demand a criterion of a computation", text)
        self.assertIn("a `compute` owes neither", text)
        self.assertNotIn(
            "(question/hypothesis, success criterion, quality check)", text
        )

    def test_an_unregistered_stated_value_is_the_named_warning(self):
        text = self.instruction()
        self.assertIn(
            'write a WARNING — "the task states a value; no reference is registered; '
            'the report cannot claim the comparison" — never a BLOCKER for a '
            "missing criterion",
            text,
        )
        self.assertIn(
            "judge whether the code's kept number is the registered `key`", text
        )

    def test_the_agents_template_says_the_same(self):
        from labkit.tools import scaffold

        text = self.one_line(scaffold.template("AGENTS.md.template"))
        self.assertIn(
            "compares with a stated reference only through the head's `[reference]` "
            "table",
            text,
        )
        self.assertIn("ends with `not met` and a valid delivery", text)


if __name__ == "__main__":
    unittest.main()
