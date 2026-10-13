"""Tests for protocol-fill — fill a stamped placeholder by label.

Why this is tested: filling protocol fields by quoting the placeholder text
back failed in 3-round loops twice in one day (2026-09-09, PROTOCOL-67).
The label match must hit single- and multi-line placeholders, refuse
ambiguity and silent overwrites, and leave every other byte alone.
"""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test

from labkit import code_check, protocol_block, protocol_check, protocol_fill  # noqa: E402

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
"""
    RUN = "2026-10-12T21-37-53_c3be"

    def _area(self, metrics: dict) -> Path:
        import json

        area = Path(tempfile.mkdtemp())
        run = area / "runs" / self.RUN
        run.mkdir(parents=True)
        (run / "config.json").write_text(
            json.dumps({"schema_version": 2}), encoding="utf-8"
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

    def test_a_named_run_that_is_not_completed_refuses(self):
        area = self._area({"x": 1})
        with self.assertRaises(SystemExit):
            protocol_fill.from_run(
                self.PROTOCOL, area, run_id="2026-01-01T00-00-00_0000"
            )

    def test_the_command(self):
        import contextlib
        import io

        area = self._area({"mean_docs_per_case": 3.5})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = protocol_fill.main([str(area / "PROTOCOL-count.md"), "--from-run"])
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("filled from run " + self.RUN, buf.getvalue())
        self.assertIn(
            "mean_docs_per_case = 3.5",
            (area / "PROTOCOL-count.md").read_text(encoding="utf-8"),
        )
