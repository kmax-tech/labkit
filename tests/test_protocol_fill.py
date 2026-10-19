"""Tests for protocol-fill — fill a stamped placeholder by label.

Why this is tested: filling protocol fields by quoting the placeholder text
back failed in 3-round loops twice in one day (2026-09-09, PROTOCOL-67).
The label match must hit single- and multi-line placeholders, refuse
ambiguity and silent overwrites, and leave every other byte alone.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test

from labkit import code_check, protocol_block, protocol_check, protocol_fill  # noqa: E402
from protocol_fixture import PID, head  # noqa: E402

SAMPLE = """# Experiment protocol: x

## Summary † (write last)

- **Question †:** <the same sentence as in the Intent>
- **Result †:** <number(s) + run_id>

## Intent

- **Question / hypothesis:** does Y move X?
- **Meaning of the gold label †:** <what does the positive class REALLY
  mean, in the annotator's words>
- **Model / tool:** haiku via models.toml
"""


class TestFill(unittest.TestCase):
    def test_single_line_placeholder_is_replaced_by_label(self):
        out = protocol_fill.fill(SAMPLE, "Result", "K2 PASS, run 2026-x")
        self.assertIn("- **Result †:** K2 PASS, run 2026-x", out)
        self.assertNotIn("<number(s)", out)
        self.assertIn("does Y move X?", out)  # untouched neighbours

    def test_multi_line_placeholder_collapses_to_the_filled_line(self):
        out = protocol_fill.fill(
            SAMPLE, "Meaning of the gold label", "positive = the judge prefers world A"
        )
        self.assertIn(
            "- **Meaning of the gold label †:** positive = the judge prefers world A",
            out,
        )
        self.assertNotIn("annotator's words", out)

    def test_label_match_ignores_dagger_and_case(self):
        out = protocol_fill.fill(SAMPLE, "result †", "filled")
        self.assertIn("- **Result †:** filled", out)

    def test_filled_field_is_refused_without_force(self):
        with self.assertRaises(ValueError) as ctx:
            protocol_fill.fill(SAMPLE, "Model / tool", "gpt-oss")
        self.assertIn("already filled", str(ctx.exception))
        out = protocol_fill.fill(SAMPLE, "Model / tool", "gpt-oss", force=True)
        self.assertIn("- **Model / tool:** gpt-oss", out)

    def test_unknown_label_lists_the_open_fields(self):
        with self.assertRaises(ValueError) as ctx:
            protocol_fill.fill(SAMPLE, "No such field", "x")
        msg = str(ctx.exception)
        self.assertIn("Question", msg)
        self.assertIn("Meaning of the gold label", msg)

    def test_ambiguous_label_requires_line(self):
        two = SAMPLE + "\n- **Result †:** <second stamp>\n"
        with self.assertRaises(ValueError) as ctx:
            protocol_fill.fill(two, "Result", "x")
        self.assertIn("--line", str(ctx.exception))
        out = protocol_fill.fill(two, "Result", "x", line_no=6)
        self.assertIn("- **Result †:** x", out)
        self.assertIn("<second stamp>", out)

    def test_a_wrapped_label_is_read_whole(self):
        """The stamped `Resolution check` label wraps; the old parser listed
        it as `extremes)` (usability probe 2026-10-07)."""
        text = "- **Resolution check (ZERO calls,\n  extremes):** <both numbers>\n"
        out = protocol_fill.fill(text, "Resolution check", "fires 1.0, silent 0.0")
        self.assertEqual(
            out,
            "- **Resolution check (ZERO calls, extremes):** fires 1.0, silent 0.0\n",
        )

    def test_open_fields_lists_placeholders_only(self):
        labels = [lbl for _, lbl in protocol_check.placeholder_fields(SAMPLE)]
        self.assertIn("Question †", labels)
        self.assertIn("Meaning of the gold label †", labels)
        self.assertNotIn("Model / tool", labels)


TEMPLATE = (
    Path(protocol_fill.__file__)
    .with_name("experiment-protocol.md.template")
    .read_text(encoding="utf-8")
)
# The shape the stamped measure skeleton builds its prompts in — an
# f-string answer line joined from ANSWERS (re-measure 2026-10-07: a plain
# literal in this test hid that the skeleton's prompts were unreadable).
SCRIPT = (
    'ANSWERS = {"Yes": "causal", "No": "not_causal"}\n'
    "ANSWER_LINE = f\"Answer with a single word, {' or '.join(ANSWERS)}.\"\n"
    'PROMPT = ("Does this text make a causal claim?\\n\\n"\n'
    '          "Text: {text}\\n\\n" + ANSWER_LINE + "\\n\\nAnswer:")\n'
    'PROMPT_NULL = ("Is this text written in English?\\n\\n"\n'
    '               "Text: {text}\\n\\n" + ANSWER_LINE + "\\n\\nAnswer:")\n'
)


class HeadType(unittest.TestCase):
    HEAD = (
        "# Experiment protocol: x\n\n```toml\n[protocol]\n"
        f'standard = "{protocol_block.STANDARD}"\nid = "p-0123456789abcdef"\n'
        'type = "<exploratory | confirmatory>"\ncost = "seconds"\nfrozen = false\n'
        'preflight_audit = "none"\n```\n\n'
        "- **Unit:** <what one row is>\n"
    )

    def test_list_names_the_head_type_first_and_fill_sets_it(self):
        self.assertEqual(protocol_fill.head_type_open(self.HEAD), 7)
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PROTOCOL-x.md"
            p.write_text(self.HEAD, encoding="utf-8")
            with contextlib.redirect_stdout(out):
                self.assertEqual(protocol_fill.main([str(p), "--list"]), 0)
                self.assertEqual(protocol_fill.main([str(p), "type", "exploratory"]), 0)
            text = p.read_text(encoding="utf-8")
        self.assertEqual(out.getvalue().splitlines()[0].split()[:2], ["7", "type"])
        self.assertIn('type = "exploratory"', text)
        self.assertIsNone(protocol_fill.head_type_open(text))
        # the head reads: the hook's "MISSING (must): [protocol] type" is gone
        self.assertEqual(protocol_block.head(text).type, "exploratory")

    def test_list_sets_the_fields_from_run_writes_apart(self):
        """Listed among the rest, Result and Answer read as owed before the
        run: a cold agent filled them with "pending run" and --from-run then
        refused to overwrite them (cloud, 2026-10-14)."""
        from labkit import scaffold

        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PROTOCOL-x.md"
            p.write_text(
                scaffold.PROTOCOL_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8"
            )
            with contextlib.redirect_stdout(out):
                self.assertEqual(protocol_fill.main([str(p), "--list"]), 0)
        lines = out.getvalue().splitlines()
        cut = next(i for i, ln in enumerate(lines) if ln.startswith("after the run"))
        before = " ".join(lines[:cut])
        after = " ".join(lines[cut + 1 :])
        for label in protocol_fill.WRITTEN_BY_RUN:
            self.assertNotIn(label, before)
            self.assertIn(label, after)
        self.assertIn("Question / hypothesis", before)

    def test_a_type_line_in_a_fenced_example_is_not_the_head(self):
        """A prompt quoting TOML output carried `type = "<…>"`; it was taken
        for the head (audit 2026-10-15). The head is read inside the one
        ```toml block."""
        example = (
            '- **Prompt:**\n\n  ```text\n  answer as\n  type = "<yes | no>"\n  ```\n\n'
        )
        text = example + self.HEAD.replace(
            '"<exploratory | confirmatory>"', '"exploratory"'
        )
        self.assertIsNone(protocol_fill.head_type_open(text))
        text = example + self.HEAD
        line = protocol_fill.head_type_open(text)
        assert line is not None
        self.assertEqual(
            text.splitlines()[line - 1].strip(), 'type = "<exploratory | confirmatory>"'
        )
        filled = protocol_fill.fill_head_type(text, "confirmatory")
        self.assertIn('type = "<yes | no>"', filled)  # the example is untouched
        self.assertIn('type = "confirmatory"', filled)

    def test_a_wrong_type_and_a_set_type_are_refused(self):
        with self.assertRaises(ValueError):
            protocol_fill.fill_head_type(self.HEAD, "descriptive")
        with self.assertRaises(ValueError):
            protocol_fill.fill_head_type(
                self.HEAD.replace('"<exploratory | confirmatory>"', '"exploratory"'),
                "confirmatory",
            )


class Prompts(unittest.TestCase):
    """The Prompt block written from the scripts' constants holds against
    code-check's drift check (re-measure 2026-10-07: three agents patched
    it by a Python snippet)."""

    def area(self, d: str) -> Path:
        area = Path(d)
        (area / "scripts").mkdir()
        (area / "scripts" / "01_measure.py").write_text(SCRIPT)
        protocol = area / "PROTOCOL-x.md"
        protocol.write_text(TEMPLATE)
        return protocol

    def test_the_block_passes_the_drift_check(self):
        with tempfile.TemporaryDirectory() as d:
            protocol = self.area(d)
            consts = code_check.prompt_constants(protocol.parent)
            protocol.write_text(protocol_fill.fill_prompts(TEMPLATE, consts))
            self.assertEqual(
                code_check.check_prompt_drift(protocol.parent, protocol), []
            )
            text = protocol.read_text()
        self.assertIn("  ── PROMPT ──\n  Does this text make a causal claim?", text)
        self.assertIn("── PROMPT_NULL ──", text)
        self.assertIn("  Answer with a single word, Yes or No.", text)
        self.assertNotIn("<the real prompt", text)

    def test_a_changed_constant_drifts_again(self):
        with tempfile.TemporaryDirectory() as d:
            protocol = self.area(d)
            consts = code_check.prompt_constants(protocol.parent)
            protocol.write_text(protocol_fill.fill_prompts(TEMPLATE, consts))
            (protocol.parent / "scripts" / "01_measure.py").write_text(
                SCRIPT.replace("causal claim", "claim of cause")
            )
            drift = code_check.check_prompt_drift(protocol.parent, protocol)
        self.assertTrue(drift and "drifted from PROMPT" in drift[0], drift)

    def test_filling_twice_replaces_not_appends(self):
        consts = {"PROMPT": "Q?"}
        once = protocol_fill.fill_prompts(TEMPLATE, consts)
        self.assertEqual(protocol_fill.fill_prompts(once, consts), once)

    def test_no_constant_is_a_sentence(self):
        with self.assertRaises(ValueError) as cm:
            protocol_fill.fill_prompts(TEMPLATE, {})
        self.assertIn("no PROMPT constant", str(cm.exception))


class OneCallFill(unittest.TestCase):
    """`protocol-fill P "LABEL=VALUE" ...` fills several fields at once, all or
    nothing — six calls for six fields were every cold agent's largest sink
    (cloud probes, 2026-10-13)."""

    BODY = (
        "- **Terms of this protocol:** <the terms>\n"
        "- **Unit:** <one thing>\n"
        "- **Data / scope:** <where>\n"
    )

    def test_every_word_with_an_equals_sign_is_one_assignment(self):
        self.assertEqual(
            protocol_fill.assignments_of("Unit=a = b", ["Data / scope=x"]),
            [("Unit", "a = b"), ("Data / scope", "x")],
        )

    def test_the_one_field_form_joins_the_value_words(self):
        self.assertEqual(
            protocol_fill.assignments_of("Unit", ["one", "thing"]),
            [("Unit", "one thing")],
        )
        self.assertEqual(
            protocol_fill.assignments_of("Unit", ["x = 1"]), [("Unit", "x = 1")]
        )

    def test_no_value_is_no_assignment(self):
        self.assertEqual(protocol_fill.assignments_of("Unit", []), [])
        self.assertEqual(protocol_fill.assignments_of(None, []), [])

    def test_fill_many_fills_in_order_and_sets_the_head_type(self):
        text = head(type="<exploratory | confirmatory>") + self.BODY
        new = protocol_fill.fill_many(
            text,
            [
                ("type", "confirmatory"),
                ("Unit", "one case"),
                ("Data / scope", "12 cases"),
            ],
        )
        self.assertIn('type = "confirmatory"', new)
        self.assertIn("- **Unit:** one case\n", new)
        self.assertIn("- **Data / scope:** 12 cases\n", new)
        self.assertIn("<the terms>", new)

    def test_one_bad_label_fills_nothing(self):
        text = head() + self.BODY
        with self.assertRaises(ValueError):
            protocol_fill.fill_many(text, [("Unit", "one case"), ("Nope", "x")])
        with self.assertRaises(ValueError):
            protocol_fill.fill_many(text, [("Unit", "")])

    def test_the_command_writes_once_or_not_at_all(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "PROTOCOL-x.md"
            f.write_text(head() + self.BODY)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = protocol_fill.main([str(f), "Unit=one case", "Nope=x"])
            self.assertEqual(rc, 1)
            self.assertIn("<one thing>", f.read_text())
            with contextlib.redirect_stdout(io.StringIO()):
                rc = protocol_fill.main(
                    [str(f), "Unit=one case", "Data / scope=12 cases"]
                )
            self.assertEqual(rc, 0)
            self.assertIn("- **Unit:** one case\n", f.read_text())
            self.assertIn("- **Data / scope:** 12 cases\n", f.read_text())


if __name__ == "__main__":
    unittest.main()


class TestFromRun(unittest.TestCase):
    """--from-run (0.88.0): the number is written back from metrics.json, never retyped."""

    PROTOCOL = """# Experiment protocol: count

## Summary (after the run, for a person)

- **Result:** <the answer to the question above, in at most two plain sentences…>

## Intent (before the run)

- **Question / hypothesis:** how many documents per case?

## Result (after the run — write back, don't go quiet)

- **Answer to the question:** <per registered id its verdict, and the run_id…>

## Runs (documented runs — via `runlog`, cite run_ids instead of retyping numbers)

- <run_id> — <one sentence: what this run was>

## Head (read by the checks)

""" + head()
    RUN = "2026-10-12T21-37-53_c3be"

    def _area(self, metrics: dict) -> Path:
        import json

        area = Path(tempfile.mkdtemp())
        run = area / "runs" / self.RUN
        run.mkdir(parents=True)
        (run / "config.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "protocol": {"id": PID, "path": "PROTOCOL-count.md"},
                }
            ),
            encoding="utf-8",
        )
        (run / "completion.json").write_text(
            json.dumps({"status": "completed"}), encoding="utf-8"
        )
        (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        (area / "PROTOCOL-count.md").write_text(self.PROTOCOL, encoding="utf-8")
        return area

    def test_answer_result_and_runs_line_come_from_the_run(self):
        from labkit import recheck

        area = self._area(
            {
                "mean_docs_per_case": 3.5,
                "n_cases": 12,
                "a1_pass": True,
                "duration_s": 0.02,
            }
        )
        text, filled, run_id = protocol_fill.from_run(self.PROTOCOL, area)
        self.assertEqual(run_id, self.RUN)
        self.assertEqual(filled, ["Answer to the question", "Result", "Runs"])
        line = (
            "mean_docs_per_case = 3.5, n_cases = 12, a1_pass = True (run "
            + self.RUN
            + ")"
        )
        self.assertIn("- **Answer to the question:** " + line, text)
        self.assertIn("- **Result:** " + line, text)
        self.assertIn("- " + self.RUN + " — the kept run", text)
        self.assertNotIn("duration_s", text)  # labkit's own key is not the number
        self.assertNotIn("<run_id>", text)
        # what --check holds the protocol to: every number and the run_id
        note = area / "PROTOCOL-count.md"
        note.write_text(text, encoding="utf-8")
        recheck.cited(
            note,
            recheck.plain_numbers({"mean_docs_per_case": 3.5, "n_cases": 12}),
            self.RUN,
        )

    def test_a_written_answer_is_refused_without_force_and_the_run_is_named_once(self):
        area = self._area({"mean_docs_per_case": 3.5})
        text, _, _ = protocol_fill.from_run(self.PROTOCOL, area)
        with self.assertRaises(ValueError) as cm:
            protocol_fill.from_run(text, area)
        self.assertIn("already filled", str(cm.exception))
        again, filled, _ = protocol_fill.from_run(text, area, force=True)
        self.assertNotIn("Runs", filled)  # the run line is there once, not twice
        self.assertEqual(again.count(self.RUN), 3)

    def test_the_stamped_answering_run_line_is_written(self):
        """The template stamps `none yet — …` over four lines, no `<…>`
        placeholder: fill read it as filled and --from-run skipped it
        silently, so the line a cold agent was told the command writes
        stayed `none yet` (cold Sonnet, 2026-10-14)."""
        from labkit import scaffold

        stamped = scaffold.PROTOCOL_TEMPLATE.read_text(encoding="utf-8").splitlines()
        k = next(i for i, ln in enumerate(stamped) if "**Answering run:**" in ln)
        block = [stamped[k]]
        for ln in stamped[k + 1 :]:
            if not ln.startswith("  "):
                break
            block.append(ln)
        protocol = self.PROTOCOL.replace("## Runs", "\n".join(block) + "\n\n## Runs")
        area = self._area({"mean_docs_per_case": 3.5})
        text, filled, _ = protocol_fill.from_run(protocol, area)
        self.assertIn("Answering run", filled)
        self.assertIn(f"- **Answering run:** {self.RUN}\n", text)
        self.assertNotIn("none yet", text)
        self.assertNotIn(block[-1].strip(), text)  # the stamp's continuation goes too

    def test_an_answering_run_naming_another_run_is_refused_not_skipped(self):
        protocol = self.PROTOCOL.replace(
            "## Runs", "- **Answering run:** 2026-01-01T00-00-00_0000\n\n## Runs"
        )
        area = self._area({"mean_docs_per_case": 3.5})
        with self.assertRaises(ValueError) as cm:
            protocol_fill.from_run(protocol, area)
        self.assertIn("names 2026-01-01T00-00-00_0000", str(cm.exception))
        text, filled, _ = protocol_fill.from_run(protocol, area, force=True)
        self.assertIn(f"- **Answering run:** {self.RUN}", text)

    def test_a_named_run_that_is_not_completed_refuses(self):
        area = self._area({"x": 1})
        with self.assertRaises(SystemExit):
            protocol_fill.from_run(
                self.PROTOCOL, area, run_id="2026-01-01T00-00-00_0000"
            )

    def test_the_command_refuses_an_unchecked_result_and_leaves_the_file(self):
        """The one adoption path (2026-10-19): the fixture's run has no
        analysis record and does not say it was a full run — report-check
        refuses, and the protocol is byte-identical to before."""
        area = self._area({"mean_docs_per_case": 3.5})
        before = (area / "PROTOCOL-count.md").read_text(encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = protocol_fill.main([str(area / "PROTOCOL-count.md"), "--from-run"])
        self.assertEqual(rc, 1, buf.getvalue())
        self.assertIn("filled from run " + self.RUN, buf.getvalue())
        self.assertIn("not adopted", buf.getvalue())
        self.assertIn("does not say whether it was a full run", buf.getvalue())
        self.assertEqual(
            (area / "PROTOCOL-count.md").read_text(encoding="utf-8"), before
        )


class Adopt(unittest.TestCase):
    """`protocol-fill --from-run` as the one path by which a number becomes
    the result: the twin that passes every check is written; a probe, or a
    run without its analysis record, is refused and the file is as it was."""

    RUN = "2026-10-12T21-37-53_c3be"
    BODY = """# Experiment protocol: x

## Summary (after the run, for a person)

- **Result:** <the answer to the question above, in at most two plain sentences…>

## Result (after the run — write back, don't go quiet)

- **Answer to the question:** <per registered id its verdict, and the run_id…>
- **Answering run:** none yet — the run `finalize` holds this protocol to

## Runs (documented runs)

- <run_id> — <one sentence: what this run was>

## Head (read by the checks)

"""

    def _area(self, *, long: bool = True, audited: bool = True) -> Path:
        from labkit import findings, promises, scope_sha
        from protocol_fixture import completed_run, scope_file

        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        (area / "scripts" / "02_analyze.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        scope_file(area)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(self.BODY + head(cost="seconds"), encoding="utf-8")
        run = completed_run(area, self.RUN, metrics={"c1_pass": True}, long=long)
        src = area / "data.jsonl"
        src.write_text('{"id": 1}\n', encoding="utf-8")
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["data"] = {"cases": {"path": str(src), "sha": "x", "rows": 1}}
        cfg.write_text(json.dumps(data), encoding="utf-8")
        if audited:
            findings.write(
                area,
                "analysis",
                "opus",
                scope_sha.area_stamp(area)[0],
                promises.block_stamp(proto.read_text(encoding="utf-8")),
                (0, 0, 0),
                [],
                run_id=self.RUN,
            )
        return area

    def _adopt(self, area: Path) -> tuple[int, str, str]:
        proto = area / "PROTOCOL-x.md"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = protocol_fill.main([str(proto), "--from-run"])
        return rc, buf.getvalue(), proto.read_text(encoding="utf-8")

    def test_a_checked_full_run_is_adopted(self):
        rc, out, text = self._adopt(self._area())
        self.assertEqual(rc, 0, out)
        self.assertIn("report-check: all clear", out)
        self.assertIn(f"c1_pass = True (run {self.RUN})", text)
        self.assertIn(f"- **Answering run:** {self.RUN}", text)

    def test_a_probe_is_refused_and_the_file_is_as_it_was(self):
        area = self._area(long=False)
        before = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        rc, out, text = self._adopt(area)
        self.assertEqual(rc, 1, out)
        self.assertIn("a probe (long=False), not a full run", out)
        self.assertIn("not adopted", out)
        self.assertEqual(text, before)

    def test_a_check_that_raises_puts_the_file_back_and_raises(self):
        """Only a blocker exit restored the protocol; an exception out of
        report-check left the unchecked answer standing (audit 2026-10-19)."""
        area = self._area()
        proto = area / "PROTOCOL-x.md"
        before = proto.read_text(encoding="utf-8")
        with (
            mock.patch.object(
                protocol_fill.report_check,
                "report_check",
                side_effect=RuntimeError("x"),
            ),
            self.assertRaises(RuntimeError),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            protocol_fill.main([str(proto), "--from-run"])
        self.assertEqual(proto.read_text(encoding="utf-8"), before)

    def test_a_run_without_its_analysis_record_is_refused(self):
        area = self._area(audited=False)
        before = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        rc, out, text = self._adopt(area)
        self.assertEqual(rc, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)
        self.assertEqual(text, before)
        self.assertEqual([p.name for p in area.glob(".PROTOCOL-*")], [])

    def test_the_check_is_told_it_holds_the_proposal_written_whole(self):
        """The written-back protocol goes to report-check as the proposed
        state with its text (`report_check.PROPOSED`), written through
        `runs.write_atomic`: no half-written protocol, no temp file left."""
        area = self._area()
        proto = area / "PROTOCOL-x.md"
        seen: dict = {}

        def check(area_, protocol, *, state, text):
            seen.update(state=state, text=text)
            self.assertEqual(protocol.read_text(encoding="utf-8"), text)
            return 0

        with (
            mock.patch.object(protocol_fill.report_check, "report_check", check),
            mock.patch.object(
                protocol_fill.runs,
                "write_atomic",
                wraps=protocol_fill.runs.write_atomic,
            ) as atomic,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            rc = protocol_fill.main([str(proto), "--from-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(seen["state"], protocol_fill.report_check.PROPOSED)
        self.assertIn(f"c1_pass = True (run {self.RUN})", seen["text"])
        self.assertEqual(atomic.call_count, 1)
        self.assertEqual(proto.read_text(encoding="utf-8"), seen["text"])
        self.assertEqual([p.name for p in area.glob(".PROTOCOL-*")], [])
