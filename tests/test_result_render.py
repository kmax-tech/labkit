"""result_render: the result section is held to equality with its
rendering. The sources — the declared run's
metrics.json and the covering analysis records — render the Recorded results line and
the Limitation lines; `--from-run` writes them, `--render` writes them again, and
a line that differs from the rendering is a blocker whatever it says.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.checks import report_blocks, result_render  # noqa: E402
from labkit.formats.gate import TECHNICAL_RULE  # noqa: E402
from labkit.formats import findings, promises, protocol_block, runs, scope_sha  # noqa: E402
from labkit.tools import protocol_result
from protocol_fixture import (
    protocol_id_of,
    registration_of,
    completed_run,
    head,
    scope_file,
    shown_sha,
)  # noqa: E402

RUN = "2026-10-21T10-00-00_abcd"
#: an earlier run of the area a test lets RUN rest on
SOURCE = "2026-10-20T10-00-00_0a0a"
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
        (
            "WARNING",
            "WARNING · scripts/01_measure.py:1 · statement · one draw · x · LAB-019 r · z",
        )
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
        protocol_id=protocol_id_of(area),
    )
    if limit_reason is not None:
        findings.write_decision(path, 1, "limitation", limit_reason, "stands")
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
            {"criterion_1_pass": True, "accuracy": 0.83},
            "2026-10-22T09-13-08_0dc3",
            frozenset({"criterion_1_pass"}),
            kept=protocol_block.Kept("accuracy", protocol_block.DIMENSIONLESS),
        )
        self.assertEqual(
            example, f"- **Recorded results:** criterion-1 met · recorded: {expected}"
        )

    def test_the_rendering_is_the_answer_line_with_its_note_and_the_limit_lines(self):
        area, protocol = area_with_record()
        text = protocol.read_text(encoding="utf-8")
        r = result_render.rendering(area, text, area / "runs" / RUN, found=())
        self.assertEqual(
            r.recorded_results,
            f"criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: kept number: n = 1; also recorded: criterion_1_accuracy = 0.83 (run {RUN}); "
            "subject to 1 recorded limitation (the Limitation lines below)",
        )
        ((label, value),) = r.limits
        self.assertTrue(
            label.startswith("Limitation (audit ") and label.endswith(" #1)")
        )
        self.assertEqual(value, "the verdicts stand, read within this limit — one draw")

    def test_no_decided_limit_renders_a_bare_answer(self):
        area, protocol = area_with_record(limit_reason=None)
        text = protocol.read_text(encoding="utf-8")
        r = result_render.rendering(area, text, area / "runs" / RUN, found=())
        self.assertEqual(
            r.recorded_results,
            f"criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: kept number: n = 1; also recorded: criterion_1_accuracy = 0.83 (run {RUN})",
        )
        self.assertEqual(r.limits, ())


def stand_in_line(alias: str = "standin") -> dict:
    """A call-log line of a stand-in answer, as `llm_cache.store_stand_in`
    and a replay through the cache leave it."""
    return {
        "key": "70" * 32,
        "alias": alias,
        "hit": True,
        "origin": {"run": None, "written": "2026-11-21T10:48:16", "stand_in": True},
        "usage": {},
        "uncached": None,
    }


def asked_line(alias: str) -> dict:
    """A call-log line of a call that asked the model."""
    return {
        "key": "71" * 32,
        "alias": alias,
        "hit": False,
        "origin": None,
        "usage": {},
        "uncached": None,
    }


def write_calls(run: Path, calls: list[dict]) -> None:
    """RUN's `llm-calls.jsonl` holding CALLS, one line each."""
    (run / runs.LLM_CALLS_FILE).write_text(
        "".join(json.dumps(c) + "\n" for c in calls), encoding="utf-8"
    )


class StandInLabel(unittest.TestCase):
    """A result resting on stand-in answers says so in the generated line,
    before the recorded results; the label is counted from the call logs."""

    BARE = (
        "criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: "
        f"kept number: n = 1; also recorded: criterion_1_accuracy = 0.83 (run {RUN})"
    )

    def render(self, area: Path, protocol: Path) -> str:
        text = protocol.read_text(encoding="utf-8")
        return result_render.rendering(
            area, text, area / "runs" / RUN, found=()
        ).recorded_results

    def test_a_run_of_stand_ins_only_is_labelled_no_measurement(self):
        area, protocol = area_with_record(limit_reason=None)
        write_calls(area / "runs" / RUN, [stand_in_line(), stand_in_line()])
        self.assertEqual(
            self.render(area, protocol),
            "fixed stand-in answers: 2 logged uses of alias standin; not a measurement of "
            f"standin · {self.BARE}",
        )

    def test_stand_ins_beside_other_answers_are_labelled_not_pure(self):
        area, protocol = area_with_record(limit_reason=None)
        write_calls(
            area / "runs" / RUN,
            [stand_in_line(), asked_line("standin"), stand_in_line("judge")],
        )
        self.assertEqual(
            self.render(area, protocol),
            "fixed stand-in answers: 1 logged use of alias judge; not a measurement of judge · "
            "includes fixed stand-in answers: 1 logged use of alias standin; not a pure model "
            f"measurement · {self.BARE}",
        )

    def test_the_twin_a_run_without_stand_ins_renders_unchanged(self):
        area, protocol = area_with_record(limit_reason=None)
        bare = self.render(area, protocol)  # no call log at all
        stored = {**stand_in_line(), "origin": {"run": SOURCE, "written": "x"}}
        unmarked = {**stand_in_line(), "origin": {"run": None, "written": "x"}}
        write_calls(area / "runs" / RUN, [asked_line("standin"), stored, unmarked])
        earlier = completed_run(
            area, SOURCE
        )  # stored the replayed answer; read stand-ins
        write_calls(earlier, [stand_in_line()])
        self.assertEqual((bare, self.render(area, protocol)), (self.BARE, self.BARE))

    def test_stand_ins_a_replay_reads_again_are_in_its_own_call_log(self):
        """A replay of an earlier run that read stand-ins hits the same
        stand-in entries: its own call log carries the mark, so it is
        labelled whether or not the earlier run is a source."""
        area, protocol = area_with_record(limit_reason=None)
        earlier = completed_run(area, SOURCE)
        write_calls(earlier, [stand_in_line(), stand_in_line()])
        write_calls(area / "runs" / RUN, [stand_in_line(), stand_in_line()])
        self.assertTrue(
            self.render(area, protocol).startswith(
                "fixed stand-in answers: 2 logged uses of alias standin; not a measurement of "
                "standin · "
            )
        )

    def source_with_stand_ins(self, area: Path) -> None:
        """Run SOURCE of AREA, whose call log holds two stand-ins."""
        write_calls(completed_run(area, SOURCE), [stand_in_line(), stand_in_line()])

    def edit_record(self, area: Path, **fields: object) -> None:
        """RUN's config.json with FIELDS replaced."""
        path = area / "runs" / RUN / "config.json"
        cfg = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps({**cfg, **fields}), encoding="utf-8")

    LABEL = "fixed stand-in answers: 2 logged uses of alias standin; not a measurement of standin · "

    def test_a_derived_runs_label_counts_its_parents_stand_ins(self):
        area, protocol = area_with_record(limit_reason=None)
        self.source_with_stand_ins(area)
        self.edit_record(area, derived_from=SOURCE)
        self.assertTrue(self.render(area, protocol).startswith(self.LABEL))

    def test_continued_rows_bring_the_stand_ins_of_the_run_they_came_from(self):
        area, protocol = area_with_record(limit_reason=None)
        self.source_with_stand_ins(area)
        (area / "runs" / RUN / "outputs.json").write_text(
            json.dumps(
                [
                    {
                        "path": "rows.jsonl",
                        "sha256": None,
                        "lines": None,
                        "continues": [SOURCE],
                    }
                ]
            ),
            encoding="utf-8",
        )
        self.assertTrue(self.render(area, protocol).startswith(self.LABEL))

    def test_an_input_written_by_another_run_brings_that_runs_stand_ins(self):
        area, protocol = area_with_record(limit_reason=None)
        self.source_with_stand_ins(area)
        entry = {
            "path": "x.jsonl",
            "sha256": "0" * 16,
            "rows": 2,
            runs.ORIGIN_RUN_KEY: SOURCE,
            runs.ORIGIN_CHOSEN_KEY: True,
            runs.ORIGIN_UNREADABLE_KEY: [],
        }
        self.edit_record(area, data={"rows": entry})
        line = self.render(area, protocol)
        self.assertTrue(line.startswith(self.LABEL), line)
        self.assertIn(" · sources: ", line)  # the source's own values, unlabelled

    def test_a_source_run_that_does_not_read_stops_the_rendering(self):
        area, protocol = area_with_record(limit_reason=None)
        self.edit_record(area, derived_from="2026-10-19T10-00-00_9999")  # no such run
        with self.assertRaisesRegex(
            ValueError, f"the stand-in answers behind run {RUN} cannot be counted"
        ):
            self.render(area, protocol)

    def test_a_line_or_block_whose_label_differs_from_the_call_logs_is_refused(self):
        area, protocol = area_with_record(limit_reason=None)
        write_calls(area / "runs" / RUN, [stand_in_line(), stand_in_line()])
        text, _, _ = protocol_result.from_run(
            protocol.read_text(encoding="utf-8"), area
        )
        expected = result_render.rendering(area, text, area / "runs" / RUN, found=())
        self.assertEqual(result_render.render_gaps(text, expected), [])
        line = next(
            ln for ln in text.splitlines() if result_render.RECORDED_RESULTS_LABEL in ln
        )
        mixed = "includes fixed stand-in answers: 2 logged uses of alias standin; not a pure model measurement"
        for edited in (
            line.replace(self.LABEL, ""),  # missing
            line.replace(
                "2 logged uses of alias", "1 logged use of alias"
            ),  # wrong count
            line.replace("alias standin", "alias other"),  # wrong alias
            line.replace(self.LABEL.removesuffix(" · "), mixed),  # pure read as mixed
        ):
            (gap,) = result_render.render_gaps(text.replace(line, edited), expected)
            self.assertIn("Recorded results line differs from its rendering", gap.text)
        # the fixture's protocol writes no question or Conclusion; a block needs both
        body = report_blocks.block_body(replace(expected, question="q", conclusion="a"))
        self.assertIn(self.LABEL, body)
        report = area / "REPORT.md"
        found = [
            report_blocks.Block(
                "PROTOCOL-x.md", RUN, 1, 5, body.replace(self.LABEL, "")
            )
        ]
        (gap,) = report_blocks.block_gaps(
            found, {"PROTOCOL-x.md": report_blocks.BlockSource(RUN, body)}, report
        )
        self.assertIn("differs from the protocol's rendering", gap.text)

    def test_a_label_without_stand_ins_behind_it_is_refused(self):
        area, protocol = area_with_record(limit_reason=None)
        text, _, _ = protocol_result.from_run(
            protocol.read_text(encoding="utf-8"), area
        )
        expected = result_render.rendering(area, text, area / "runs" / RUN, found=())
        line = next(
            ln for ln in text.splitlines() if result_render.RECORDED_RESULTS_LABEL in ln
        )
        typed = line.replace("** ", "** " + self.LABEL, 1)
        (gap,) = result_render.render_gaps(text.replace(line, typed), expected)
        self.assertIn("Recorded results line differs from its rendering", gap.text)


class ReportableVerdicts(unittest.TestCase):
    """K2 (docs/notes/2026-10-27-new-registration-contracts.md): a quality
    check recorded as not met conditions every criterion, so
    `criterion_1_pass = True` is never rendered beside "quality-check-2 not
    met"; a limitation leaves not assessable only the promises it names
    (standard 0.31, decided by the author 2026-11-14). The primary verdict
    is the derived one, the run's metrics unchanged."""

    def block(self) -> promises.PromiseTables:
        block = promises.parse_block(head(repeat_cost="low"))
        assert block is not None
        return block

    MET = {
        "criterion_1_pass": True,
        "quality_check_1_pass": True,
        "quality_check_2_pass": True,
    }

    def test_a_named_quality_check_leaves_the_criterion_its_verdict(self):
        """A doubtful null check does not by itself prevent comparing the
        score with its bar: the criterion not named reads as recorded."""
        said = result_render.verdicts(
            self.block(),
            {**self.MET, "criterion_1_pass": False},
            {"quality-check-2": "Limitation (audit x #1)"},
        )
        self.assertEqual(
            said,
            [
                "criterion-1 missed",
                "quality-check-1 met",
                "quality-check-2 not assessable (Limitation (audit x #1))",
            ],
        )

    def test_a_criterion_named_beside_the_quality_check_is_unjudged(self):
        """The twin: a fault that also prevents judging the criterion names
        it, and only then does its recorded pass not read as met."""
        limit = "Limitation (audit x #1)"
        said = result_render.verdicts(
            self.block(),
            self.MET,
            {"quality-check-2": limit, "criterion-1": limit},
        )
        self.assertEqual(
            said,
            [
                f"criterion-1 not assessable ({limit})",
                "quality-check-1 met",
                f"quality-check-2 not assessable ({limit})",
            ],
        )

    def test_a_quality_check_not_met_leaves_the_criterion_unjudged(self):
        said = result_render.verdicts(
            self.block(),
            {**self.MET, "quality_check_2_pass": False},
            {},
        )
        self.assertEqual(
            said[0], "criterion-1 not assessable — quality-check-2 not met"
        )
        self.assertEqual(said[2], "quality-check-2 not met")

    def test_a_limit_on_a_check_not_met_restores_no_verdict(self):
        """A limit hides verdicts and never restores one: a quality check
        recorded as not met still voids every criterion when a limitation
        names it alone."""
        said = result_render.verdicts(
            self.block(),
            {**self.MET, "quality_check_2_pass": False},
            {"quality-check-2": "Limitation (audit x #1)"},
        )
        self.assertEqual(
            said[0],
            "criterion-1 not assessable — quality-check-2 not met",
        )
        self.assertEqual(
            said[2], "quality-check-2 not assessable (Limitation (audit x #1))"
        )

    def test_the_reviewer_is_shown_exactly_the_named_promises(self):
        block = self.block()
        self.assertEqual(
            result_render.left_unjudged(
                block, "quality-check-2 not assessable", self.MET
            ),
            "quality-check-2 (recorded as met)",
        )
        self.assertEqual(
            result_render.left_unjudged(
                block,
                "quality-check-2, criterion-1 not assessable",
                {**self.MET, "criterion_1_pass": False},
            ),
            "criterion-1 (recorded as missed), quality-check-2 (recorded as met)",
        )
        self.assertEqual(result_render.left_unjudged(block, "stands", self.MET), "")

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
            rec.path,
            1,
            "limitation",
            "one draw",
            "quality-check-2, criterion-1 not assessable",
        )
        text = protocol.read_text(encoding="utf-8")
        r = result_render.rendering(area, text, area / "runs" / RUN, found=())
        self.assertTrue(
            r.recorded_results.startswith("criterion-1 not assessable (Limit")
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
            self.area, self.text, self.area / "runs" / RUN, found=()
        )

    def written(self) -> str:
        text, _, _ = protocol_result.from_run(self.text, self.area)
        return text

    def test_what_from_run_writes_has_no_gap_and_render_changes_nothing(self):
        text = self.written()
        self.assertEqual(result_render.render_gaps(text, self.expected), [])
        again, written = protocol_result.render_result(text, self.area)
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
        self.assertEqual([g.rule for g in gaps], [TECHNICAL_RULE, TECHNICAL_RULE])
        self.assertIn("--render", gaps[1].fix or "")
        rendered, written = protocol_result.render_result(edited, self.area)
        self.assertEqual(rendered, text)
        self.assertEqual(len(written), 2)

    def test_a_part_of_the_line_that_is_no_number_differs_the_same_way(self):
        """The line is held whole: a retyped run id is the gap a retyped
        value is, under the same contract."""
        text = self.written()
        line = next(
            ln for ln in text.splitlines() if result_render.RECORDED_RESULTS_LABEL in ln
        )
        self.assertIn("(run ", line)
        edited = text.replace(line, line.replace("(run ", "(run 0"))
        (gap,) = result_render.render_gaps(edited, self.expected)
        self.assertIn("Recorded results line differs from its rendering", gap.text)
        self.assertEqual(gap.rule, TECHNICAL_RULE)

    def test_a_generated_label_written_twice_is_a_gap(self):
        """Every line of a label is held, not one per field: a wrong
        Limitation line above the record's correct one, or a retyped Recorded
        results below the generated one, is a gap."""
        exp = result_render.Rendering(
            "criterion_1_pass = True (run r1)",
            (
                (
                    "Limitation (audit a #1)",
                    "the verdicts stand, read within this limit — ok",
                ),
            ),
            None,  # the section's check reads no question and no answer
            None,
        )
        good = (
            "- **Recorded results:** criterion_1_pass = True (run r1)\n"
            "- **Limitation (audit a #1):** the verdicts stand, read within this limit — ok\n"
        )
        self.assertEqual(result_render.render_gaps(good, exp), [])
        (gap,) = result_render.render_gaps(
            "- **Limitation (audit a #1):** no restriction applies\n" + good, exp
        )
        self.assertIn('"Limitation (audit a #1)" is written 2 times', gap.text)
        (gap,) = result_render.render_gaps(
            good + "- **Recorded results:** criterion_1_pass = False (run r1)\n", exp
        )
        self.assertIn('"Recorded results" is written 2 times', gap.text)

    def test_a_limit_line_no_record_decides_is_named_and_dropped(self):
        text = self.written()
        stray = text.replace(
            "- **Raw output:** r",
            "- **Limitation (audit 2026-10-01T00-00-analysis #9):** the verdicts stand, "
            "read within this limit — invented\n- **Raw output:** r",
        )
        (gap,) = result_render.render_gaps(stray, self.expected)
        self.assertIn("no covering record decides", gap.text)
        rendered, written = protocol_result.render_result(stray, self.area)
        self.assertEqual(rendered, text)
        self.assertEqual(
            written, ["dropped Limitation (audit 2026-10-01T00-00-analysis #9)"]
        )

    def test_render_refuses_without_a_declaration(self):
        undeclared = head(repeat_cost="low") + BODY
        with self.assertRaisesRegex(
            ValueError, "no run adopted \\(\\[result\\] run\\)"
        ):
            protocol_result.render_result(undeclared, self.area)


if __name__ == "__main__":
    unittest.main()
