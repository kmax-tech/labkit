"""result_render: the result section is held to equality with its rendering
(phase 5 of the 1.0 line, 2026-10-21). The sources — the declared run's
metrics.json and the covering analysis records — render the Recorded results line and
the Limit lines; `--from-run` writes them, `--render` writes them again, and
a line that differs from the rendering is a blocker whatever it says.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.checks import result_render  # noqa: E402
from labkit.formats import findings, promises, scope_sha  # noqa: E402
from labkit.tools import protocol_fill  # noqa: E402
from protocol_fixture import registration_of, completed_run, head, scope_file, shown_sha  # noqa: E402

RUN = "2026-10-21T10-00-00_abcd"
BODY = "\n## Result\n\n- **Recorded results:** <per registered id its verdict…>\n- **Raw output:** r\n\n## Runs\n\n- <run_id> — <one sentence>\n"


def area_with_record(limit_reason: str | None = "one draw") -> tuple[Path, Path]:
    """A low-lane area, its protocol declaring RUN, a completed run, and an
    analysis record covering it with one accepted WARNING carrying an effect
    (none when LIMIT_REASON is None)."""
    area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    scope_file(area)
    protocol = area / "PROTOCOL-x.md"
    protocol.write_text(head(repeat_cost="low", result=RUN) + BODY, encoding="utf-8")
    run = completed_run(
        area,
        RUN,
        metrics={
            "criterion_1_pass": True,
            "quality_check_1_pass": True,
            "quality_check_2_pass": True,
            "criterion_1_accuracy": 0.83,
        },
    )
    text = protocol.read_text(encoding="utf-8")
    items = [
        ("WARNING", "WARNING · scripts/01_measure.py:1 · one draw · x · LAB-019 r · z")
    ]
    path = findings.write(
        area,
        "analysis",
        "test",
        scope_sha.area_stamp(area)[0],
        promises.block_stamp(text),
        (0, 1, 0),
        items,
        run_id=run.name,
        shown_sha=shown_sha(area, run),
        registration=registration_of(area),
    )
    if limit_reason is not None:
        findings.write_decision(path, 1, "accepted", limit_reason, "stands")
    return area, protocol


class Rendering(unittest.TestCase):
    def test_the_field_guide_example_matches_the_generated_field(self):
        """The guide's example must stay usable by the exact renderer."""
        guide = (
            Path(__file__).resolve().parents[1] / "labkit/docs/protocol-field-guide.md"
        ).read_text(encoding="utf-8")
        section = guide.split("- **Recorded results:**", 1)[1]
        example = section.split("```text\n", 1)[1].split("```", 1)[0].strip()
        expected = result_render.recorded_results_line(
            {"criterion_1_pass": True, "criterion_1_accuracy": 0.83},
            "2026-10-22T09-13-08_0dc3",
            frozenset({"criterion_1_pass"}),
        )
        self.assertEqual(
            example, f"- **Recorded results:** criterion-1 met · recorded: {expected}"
        )

    def test_the_rendering_is_the_answer_line_with_its_note_and_the_limit_lines(self):
        area, protocol = area_with_record()
        text = protocol.read_text(encoding="utf-8")
        r = result_render.rendering(area, text, area / "runs" / RUN)
        self.assertEqual(
            r.recorded_results,
            f"criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: criterion_1_accuracy = 0.83 (run {RUN}); "
            "subject to 1 recorded limitation (the Limit lines below)",
        )
        ((label, value),) = r.limits
        self.assertTrue(label.startswith("Limit (audit ") and label.endswith(" #1)"))
        self.assertEqual(value, "the verdicts stand, read within this limit — one draw")

    def test_no_decided_limit_renders_a_bare_answer(self):
        area, protocol = area_with_record(limit_reason=None)
        text = protocol.read_text(encoding="utf-8")
        r = result_render.rendering(area, text, area / "runs" / RUN)
        self.assertEqual(
            r.recorded_results,
            f"criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: criterion_1_accuracy = 0.83 (run {RUN})",
        )
        self.assertEqual(r.limits, ())


class ReportableVerdicts(unittest.TestCase):
    """K2 (docs/notes/2026-10-27-new-registration-contracts.md): every
    quality check conditions every criterion. The repair case
    (2026-10-27) rendered `criterion_1_pass = True` beside "quality-check-3 not assessable"; the
    primary verdict is now the derived one, the run's metrics unchanged."""

    def block(self) -> promises.PromiseTables:
        block = promises.parse_block(head(repeat_cost="low"))
        assert block is not None
        return block

    def test_an_admissibility_not_assessable_leaves_the_criterion_unjudged(self):
        said = result_render.verdicts(
            self.block(),
            {
                "criterion_1_pass": True,
                "quality_check_1_pass": True,
                "quality_check_2_pass": True,
            },
            {"quality-check-2": "Limit (audit x #1)"},
        )
        self.assertEqual(
            said,
            [
                "criterion-1 not assessable — quality-check-2 not assessable (Limit (audit x #1))",
                "quality-check-1 met",
                "quality-check-2 not assessable (Limit (audit x #1))",
            ],
        )

    def test_an_admissibility_not_met_leaves_the_criterion_unjudged(self):
        said = result_render.verdicts(
            self.block(),
            {
                "criterion_1_pass": True,
                "quality_check_1_pass": True,
                "quality_check_2_pass": False,
            },
            {},
        )
        self.assertEqual(
            said[0], "criterion-1 not assessable — quality-check-2 not met"
        )
        self.assertEqual(said[2], "quality-check-2 not met")

    def test_the_twins_a_miss_stays_a_miss_and_a_pass_a_pass(self):
        """A failed criterion under satisfied quality checks is a
        result, not unjudged; without a limit a pass renders as met."""
        missed = {
            "criterion_1_pass": False,
            "quality_check_1_pass": True,
            "quality_check_2_pass": True,
        }
        self.assertEqual(
            result_render.verdicts(self.block(), missed, {})[0], "criterion-1 missed"
        )
        met = {
            "criterion_1_pass": True,
            "quality_check_1_pass": True,
            "quality_check_2_pass": True,
        }
        self.assertEqual(
            result_render.verdicts(self.block(), met, {})[0], "criterion-1 met"
        )

    def test_a_key_not_recorded_gives_no_verdict_and_says_so(self):
        """A missing required key is an input error intent-check holds, never
        a benign not assessable."""
        said = result_render.verdicts(
            self.block(), {"criterion_1_pass": True, "quality_check_2_pass": True}, {}
        )
        self.assertEqual(
            said[1],
            "quality-check-1: no verdict — `quality_check_1_pass` not recorded as true or false",
        )

    def test_the_rendering_leaves_the_runs_metrics_as_recorded(self):
        area, protocol = area_with_record(limit_reason=None)
        rec = findings.area_records(area)[0]
        findings.write_decision(
            rec.path, 1, "accepted", "one draw", "quality-check-2 not assessable"
        )
        text = protocol.read_text(encoding="utf-8")
        r = result_render.rendering(area, text, area / "runs" / RUN)
        self.assertTrue(
            r.recorded_results.startswith(
                "criterion-1 not assessable — quality-check-2 not assessable (Limit"
            )
        )
        self.assertNotIn("criterion_1_pass", r.recorded_results)
        self.assertIn("criterion_1_accuracy = 0.83", r.recorded_results)
        metrics = (area / "runs" / RUN / "metrics.json").read_text(encoding="utf-8")
        self.assertIn('"criterion_1_pass": true', metrics)


class RenderGaps(unittest.TestCase):
    """Exact: the written lines equal the rendering, or each difference is named."""

    def setUp(self):
        self.area, self.protocol = area_with_record()
        self.text = self.protocol.read_text(encoding="utf-8")
        self.expected = result_render.rendering(
            self.area, self.text, self.area / "runs" / RUN
        )

    def written(self) -> str:
        text, _, _ = protocol_fill.from_run(self.text, self.area)
        return text

    def test_what_from_run_writes_has_no_gap_and_render_changes_nothing(self):
        text = self.written()
        self.assertEqual(result_render.render_gaps(text, self.expected), [])
        again, written = protocol_fill.render_result(text, self.area)
        self.assertEqual((again, written), (text, []))

    def test_an_unwritten_answer_is_named(self):
        (gap,) = [
            g
            for g in result_render.render_gaps(self.text, self.expected)
            if "Recorded results" in g.text
        ]
        self.assertIn("not written", gap.text)
        self.assertIn("protocol-fill <PROTOCOL> --from-run", gap.fix or "")

    def test_a_retyped_answer_and_a_changed_limit_are_named_and_rendered_back(self):
        text = self.written()
        edited = text.replace(
            "criterion_1_accuracy = 0.83", "criterion_1_accuracy = 0.85"
        ).replace("— one draw", "— one draw, fine")
        gaps = result_render.render_gaps(edited, self.expected)
        self.assertEqual(len(gaps), 2, gaps)
        self.assertIn("Recorded results line differs from its rendering", gaps[0].text)
        self.assertIn("differs from the record", gaps[1].text)
        self.assertIn("--render", gaps[1].fix or "")
        rendered, written = protocol_fill.render_result(edited, self.area)
        self.assertEqual(rendered, text)
        self.assertEqual(len(written), 2)

    def test_a_generated_label_written_twice_is_a_gap(self):
        """Review 2026-10-22: the check kept the fields in a dict, so a wrong
        Limit line above the record's correct one — or a retyped Recorded
        results below the generated one — passed. Every line of a label is
        held."""
        exp = result_render.Rendering(
            "criterion_1_pass = True (run r1)",
            (
                (
                    "Limit (audit a #1)",
                    "the verdicts stand, read within this limit — ok",
                ),
            ),
        )
        good = (
            "- **Recorded results:** criterion_1_pass = True (run r1)\n"
            "- **Limit (audit a #1):** the verdicts stand, read within this limit — ok\n"
        )
        self.assertEqual(result_render.render_gaps(good, exp), [])
        (gap,) = result_render.render_gaps(
            "- **Limit (audit a #1):** no restriction applies\n" + good, exp
        )
        self.assertIn('"Limit (audit a #1)" is written 2 times', gap.text)
        (gap,) = result_render.render_gaps(
            good + "- **Recorded results:** criterion_1_pass = False (run r1)\n", exp
        )
        self.assertIn('"Recorded results" is written 2 times', gap.text)

    def test_a_limit_line_no_record_decides_is_named_and_dropped(self):
        text = self.written()
        stray = text.replace(
            "- **Raw output:** r",
            "- **Limit (audit 2026-10-01T00-00-analysis #9):** the verdicts stand, "
            "read within this limit — invented\n- **Raw output:** r",
        )
        (gap,) = result_render.render_gaps(stray, self.expected)
        self.assertIn("no covering record decides", gap.text)
        rendered, written = protocol_fill.render_result(stray, self.area)
        self.assertEqual(rendered, text)
        self.assertEqual(
            written, ["dropped Limit (audit 2026-10-01T00-00-analysis #9)"]
        )

    def test_render_refuses_without_a_declaration(self):
        undeclared = head(repeat_cost="low") + BODY
        with self.assertRaisesRegex(
            ValueError, "no run adopted \\(\\[result\\] run\\)"
        ):
            protocol_fill.render_result(undeclared, self.area)


if __name__ == "__main__":
    unittest.main()
