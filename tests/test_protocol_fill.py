"""Tests for protocol-fill — fill a stamped placeholder by label.

Why this is tested: filling protocol fields by quoting the placeholder text
back failed in 3-round loops twice in one day (2026-09-09, PROTOCOL-67).
The label match must hit single- and multi-line placeholders, refuse
ambiguity and silent overwrites, and leave every other byte alone.
"""

from labkit.formats.runs import RunKind

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test

from labkit import PACKAGE_DIR  # noqa: E402
from labkit.tools import protocol_fill  # noqa: E402
from labkit.checks import audit_binding  # noqa: E402
from labkit.checks import prompt_check  # noqa: E402
from labkit.formats import protocol_block, protocol_check  # noqa: E402
from protocol_fixture import registration_of, run_record, PID, head, shown_sha  # noqa: E402

SAMPLE = """# Experiment protocol: x

## Summary † (write last)

- **Question †:** <the same sentence as in the Intent>
- **Conclusion †:** <number(s) + run_id>

## Intent

- **Question / hypothesis:** does Y move X?
- **Meaning of the gold label †:** <what does the positive class REALLY
  mean, in the annotator's words>
- **Model / tool:** haiku via models.toml
"""


class TestFill(unittest.TestCase):
    def test_single_line_placeholder_is_replaced_by_label(self):
        out = protocol_fill.fill(SAMPLE, "Conclusion", "K2 PASS, run 2026-x")
        self.assertIn("- **Conclusion †:** K2 PASS, run 2026-x", out)
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
        out = protocol_fill.fill(SAMPLE, "conclusion †", "filled")
        self.assertIn("- **Conclusion †:** filled", out)

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
        two = SAMPLE + "\n- **Conclusion †:** <second stamp>\n"
        with self.assertRaises(ValueError) as ctx:
            protocol_fill.fill(two, "Conclusion", "x")
        self.assertIn("--line", str(ctx.exception))
        out = protocol_fill.fill(two, "Conclusion", "x", line_no=6)
        self.assertIn("- **Conclusion †:** x", out)
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


TEMPLATE = (PACKAGE_DIR / "templates" / "experiment-protocol.md.template").read_text(
    encoding="utf-8"
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
# The PubMedQA pilot's form: the registered prompt joins `ANSWERS.keys()`,
# a call the static reader does not compute; the null prompt is literal.
HALF_READABLE_SCRIPT = (
    'ANSWERS = {"Yes": "yes", "No": "no"}\n'
    "ANSWER_LINE = f\"Answer with a single word: {', '.join(ANSWERS.keys())}.\"\n"
    'PROMPT = "Does the study support the claim?\\n\\n{text}\\n\\n" + ANSWER_LINE\n'
    'PROMPT_NULL = "Is this text written in English?\\n\\n{text}\\n\\nAnswer Yes or No."\n'
)


class HeadType(unittest.TestCase):
    HEAD = (
        "# Experiment protocol: x\n\n```toml\n[protocol]\n"
        f'standard = "{protocol_block.STANDARD}"\nid = "p-0123456789abcdef"\n'
        'type = "<exploratory | confirmatory>"\nrepeat_cost = "low"\nkind = "compute"\n'
        'frozen = false\npreflight_audit = "none"\n```\n\n'
        "- **Unit:** <what one row is>\n"
    )

    def test_list_names_the_head_type_first_and_fill_sets_it(self):
        self.assertEqual(protocol_fill.head_open(self.HEAD, "type"), 7)
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
        self.assertIsNone(protocol_fill.head_open(text, "type"))
        # the head reads: the hook's "MISSING (must): [protocol] type" is gone
        self.assertEqual(protocol_block.head(text).type, "exploratory")

    def test_list_sets_the_fields_from_run_writes_apart(self):
        """Listed among the rest, Result and Answer read as owed before the
        run: a cold agent filled them with "pending run" and --from-run then
        refused to overwrite them (cloud, 2026-10-14)."""
        from labkit.tools import scaffold

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
        self.assertIsNone(protocol_fill.head_open(text, "type"))
        text = example + self.HEAD
        line = protocol_fill.head_open(text, "type")
        assert line is not None
        self.assertEqual(
            text.splitlines()[line - 1].strip(), 'type = "<exploratory | confirmatory>"'
        )
        filled = protocol_fill.fill_head(text, "type", "confirmatory")
        self.assertIn('type = "<yes | no>"', filled)  # the example is untouched
        self.assertIn('type = "confirmatory"', filled)

    def test_the_head_cost_left_by_the_stamp_is_listed_and_set(self):
        """`labkit-init exp` without --repeat-cost leaves `cost = "<…>"`; --list named
        only type, and the agent edited the head by hand (2026-10-21)."""
        text = self.HEAD.replace('repeat_cost = "low"', 'repeat_cost = "<low | high>"')
        self.assertEqual(protocol_fill.head_open(text, "repeat_cost"), 8)
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(out):
                self.assertEqual(protocol_fill.main([str(p), "--list"]), 0)
                rc = protocol_fill.main(
                    [str(p), "type=exploratory", "repeat_cost=high"]
                )
            self.assertEqual(rc, 0)
            filled = p.read_text(encoding="utf-8")
        listed = [ln.split()[:2] for ln in out.getvalue().splitlines()[:2]]
        self.assertEqual(listed, [["7", "type"], ["8", "repeat_cost"]])
        self.assertIn("low | high", out.getvalue())
        self.assertEqual(protocol_block.head(filled).repeat_cost, "high")
        self.assertIsNone(protocol_fill.head_open(filled, "repeat_cost"))
        with self.assertRaisesRegex(ValueError, "repeat_cost must be one of low"):
            protocol_fill.fill_head(text, "repeat_cost", "days")
        with self.assertRaisesRegex(ValueError, "not a choice protocol-fill sets"):
            protocol_fill.head_open(text, "frozen")

    def test_the_model_alias_left_by_a_bare_model_flag_is_listed_and_set(self):
        """`labkit-init exp --model` without an alias stamps `[model] alias =
        "<alias from models.toml>"` (phase 4, 2026-10-21); --list names it
        and `"model alias=haiku"` writes it as a TOML string."""
        text = self.HEAD.replace(
            'preflight_audit = "none"\n',
            'preflight_audit = "none"\n\n[model]\nalias = "<alias from models.toml>"\n',
        )
        self.assertEqual(protocol_fill.head_open(text, "alias"), 14)
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(out):
                self.assertEqual(protocol_fill.main([str(p), "--list"]), 0)
                rc = protocol_fill.main(
                    [str(p), "type=exploratory", "model alias=haiku"]
                )
            self.assertEqual(rc, 0)
            filled = p.read_text(encoding="utf-8")
        self.assertIn(
            "  14  model alias  (TOML head: the alias from models.toml)", out.getvalue()
        )
        m = protocol_block.model(filled)
        assert m is not None
        self.assertEqual(m.alias, "haiku")
        self.assertIsNone(protocol_fill.head_open(filled, "alias"))
        with self.assertRaisesRegex(ValueError, "alias: an empty value"):
            protocol_fill.fill_head(text, "alias", " ")

    def test_number_describes_is_listed_and_set_and_the_freeze_says_how(self):
        # a MUST of a computation with a model that no tool set, and the
        # freeze keys answered "no field labelled" (audit 2026-10-27, third,
        # I5, I6)
        text = self.HEAD.replace(
            'preflight_audit = "none"\n',
            'preflight_audit = "none"\n\n[model]\nalias = "haiku"\n'
            'number_describes = "<model_outputs | target_property>"\n',
        )
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(out):
                self.assertEqual(protocol_fill.main([str(p), "--list"]), 0)
                rc = protocol_fill.main([str(p), "number_describes=model_outputs"])
            self.assertEqual(rc, 0)
            filled = p.read_text(encoding="utf-8")
        self.assertIn("number_describes", out.getvalue())
        self.assertIn('number_describes = "model_outputs"', filled)
        with self.assertRaisesRegex(ValueError, "must be one of"):
            protocol_fill.fill_many(text, [("number_describes", "outputs")])
        for key in ("frozen", "preflight_audit"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "set by hand in the TOML head"):
                    protocol_fill.fill_many(text, [(key, "true")])

    def test_list_sets_apart_the_fields_this_protocol_does_not_owe(self):
        # a high computation without a model was told to fill its data
        # profile and prompt (audit 2026-10-27, third, I9)
        text = head(repeat_cost="high", kind="compute") + (
            "- **Data profile:** <your judgement of the data>\n"
            "- **Question / hypothesis:** <the one question>\n"
        )
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(out):
                self.assertEqual(protocol_fill.main([str(p), "--list"]), 0)
        listed = out.getvalue()
        spare = listed.split("not owed by this protocol", 1)
        self.assertEqual(len(spare), 2, listed)
        self.assertIn("Data profile", spare[1])
        self.assertNotIn("Data profile", spare[0])
        self.assertIn("Question / hypothesis", spare[0])

    def test_a_wrong_type_and_a_set_type_are_refused(self):
        with self.assertRaises(ValueError):
            protocol_fill.fill_head(self.HEAD, "type", "descriptive")
        with self.assertRaises(ValueError):
            protocol_fill.fill_head(
                self.HEAD.replace('"<exploratory | confirmatory>"', '"exploratory"'),
                "type",
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
            consts = prompt_check.prompt_constants(protocol.parent)
            protocol.write_text(protocol_fill.fill_prompts(TEMPLATE, consts))
            self.assertEqual(
                prompt_check.check_prompt_drift(protocol.parent, protocol), []
            )
            text = protocol.read_text()
        self.assertIn("  ── PROMPT ──\n  Does this text make a causal claim?", text)
        self.assertIn("── PROMPT_NULL ──", text)
        self.assertIn("  Answer with a single word, Yes or No.", text)
        self.assertNotIn("<the real prompt", text)

    def test_a_changed_constant_drifts_again(self):
        with tempfile.TemporaryDirectory() as d:
            protocol = self.area(d)
            consts = prompt_check.prompt_constants(protocol.parent)
            protocol.write_text(protocol_fill.fill_prompts(TEMPLATE, consts))
            (protocol.parent / "scripts" / "01_measure.py").write_text(
                SCRIPT.replace("causal claim", "claim of cause")
            )
            drift = [
                f.line
                for f in prompt_check.check_prompt_drift(protocol.parent, protocol)
            ]
        self.assertTrue(drift and "drifted from PROMPT" in drift[0], drift)

    def test_filling_twice_replaces_not_appends(self):
        consts = {"PROMPT": "Q?"}
        once = protocol_fill.fill_prompts(TEMPLATE, consts)
        self.assertEqual(protocol_fill.fill_prompts(once, consts), once)

    def test_no_constant_is_a_sentence(self):
        with self.assertRaises(ValueError) as cm:
            protocol_fill.fill_prompts(TEMPLATE, {})
        self.assertIn("no PROMPT constant", str(cm.exception))

    def prompts_cli(self, protocol: Path) -> tuple[int, str, str]:
        """`protocol-fill PROTOCOL --prompts`: (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = protocol_fill.main([str(protocol), "--prompts"])
        return rc, out.getvalue(), err.getvalue()

    def test_an_unreadable_constant_is_named_and_nothing_is_written(self):
        """The PubMedQA pilot's answer line joined `ANSWERS.keys()`, a call
        the static reader does not compute: `--prompts` wrote the null
        prompt alone and said "filled" (repro on labkit c2c5da2, 2026-10-28)."""
        with tempfile.TemporaryDirectory() as d:
            protocol = self.area(d)
            (protocol.parent / "scripts" / "01_measure.py").write_text(
                HALF_READABLE_SCRIPT
            )
            readable = prompt_check.prompt_constants(protocol.parent)
            self.assertEqual(sorted(readable), ["PROMPT_NULL"])  # the case holds
            rc, out, err = self.prompts_cli(protocol)
            self.assertEqual(protocol.read_text(), TEMPLATE)
        self.assertEqual(rc, 2)
        self.assertNotIn("filled", out)
        self.assertIn("01_measure.py:PROMPT ", err)

    def test_readable_constants_are_filled(self):
        """Twin: every constant read, the block is written and said so."""
        with tempfile.TemporaryDirectory() as d:
            protocol = self.area(d)
            rc, out, _ = self.prompts_cli(protocol)
            self.assertIn("── PROMPT_NULL ──", protocol.read_text())
        self.assertEqual(rc, 0)
        self.assertIn("filled: Prompt", out)


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
            self.assertEqual(rc, 2)  # a refusal: stderr, exit 2 (`console.refuse`)
            self.assertIn("<one thing>", f.read_text())
            with contextlib.redirect_stdout(io.StringIO()):
                rc = protocol_fill.main(
                    [str(f), "Unit=one case", "Data / scope=12 cases"]
                )
            self.assertEqual(rc, 0)
            self.assertIn("- **Unit:** one case\n", f.read_text())
            self.assertIn("- **Data / scope:** 12 cases\n", f.read_text())


class StampedId(unittest.TestCase):
    TEXT = "- **Inference criterion:** [criterion-1] <how do we recognise…>\n"

    def test_a_value_without_an_id_keeps_the_stamped_one(self):
        out = protocol_fill.fill(self.TEXT, "Inference criterion", "acc >= 0.8")
        self.assertEqual(out, "- **Inference criterion:** [criterion-1] acc >= 0.8\n")

    def test_a_value_with_its_own_ids_replaces_it(self):
        out = protocol_fill.fill(
            self.TEXT,
            "Inference criterion",
            "[criterion-1] acc >= 0.8 and [criterion-2] f1 >= 0.5",
        )
        self.assertEqual(
            out,
            "- **Inference criterion:** [criterion-1] acc >= 0.8 and [criterion-2] f1 >= 0.5\n",
        )


if __name__ == "__main__":
    unittest.main()


class TestFromRun(unittest.TestCase):
    """--from-run (0.88.0): the number is written back from metrics.json, never retyped."""

    PROTOCOL = """# Experiment protocol: count

## Summary (after the run, for a person)

- **Conclusion:** <the answer to the question above, in at most two plain sentences…>

## Intent (before the run)

- **Question / hypothesis:** how many documents per case?

## Result (after the run — write back, don't go quiet)

- **Recorded results:** <per registered id its verdict, and the run_id…>

## Runs (protocol run list — via `runlog`, cite run_ids instead of retyping numbers)

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
                run_record(
                    {
                        "schema_version": 4,
                        "run_kind": "measurement",
                        "protocol": {"id": PID, "path": "PROTOCOL-count.md"},
                    }
                )
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
        from labkit.checks import recheck

        area = self._area(
            {
                "mean_docs_per_case": 3.5,
                "n_cases": 12,
                "quality_check_1_pass": True,
                "duration_s": 0.02,
            }
        )
        text, filled, run_id = protocol_fill.from_run(self.PROTOCOL, area)
        self.assertEqual(run_id, self.RUN)
        self.assertEqual(
            filled, ["Recorded results", protocol_fill.RESULT_LABEL, "Runs"]
        )
        line = (
            "mean_docs_per_case = 3.5, n_cases = 12, quality_check_1_pass = True (run "
            + self.RUN
            + ")"
        )
        self.assertIn("- **Recorded results:** " + line, text)
        # the Result is the author's two sentences, not the key dump again
        # (three of three judge protocols carried it there, 2026-10-21)
        self.assertIn("- **Conclusion:** <the answer to the question above", text)
        self.assertIn("Conclusion", protocol_fill.WRITTEN_AFTER_RUN)
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
        self.assertEqual(
            again.count(self.RUN), 3
        )  # [result], the Answer, the Runs line

    def test_the_run_is_declared_in_the_head_after_the_protocol_table(self):
        """`[result] run` is the declaration (phase 3, 2026-10-21): written
        once, right after the [protocol] table, read back exactly; the
        template's comment above [protocol] and every other byte stay."""
        area = self._area({"mean_docs_per_case": 3.5})
        text, filled, _ = protocol_fill.from_run(self.PROTOCOL, area)
        self.assertIn(protocol_fill.RESULT_LABEL, filled)
        self.assertEqual(protocol_block.declared_run(text), self.RUN)
        self.assertIn(f'preflight_audit = ""\n\n[result]\nrun = "{self.RUN}"\n', text)
        again, filled, _ = protocol_fill.from_run(text, area, force=True)
        self.assertNotIn(protocol_fill.RESULT_LABEL, filled)  # declared already
        self.assertEqual(again.count("[result]"), 1)

    def test_a_head_declaring_another_run_is_refused_not_skipped(self):
        other = "2026-01-01T00-00-00_0000"
        protocol = self.PROTOCOL.replace(
            'preflight_audit = ""\n',
            f'preflight_audit = ""\n\n[result]\nrun = "{other}"\n',
        )
        area = self._area({"mean_docs_per_case": 3.5})
        with self.assertRaises(ValueError) as cm:
            protocol_fill.from_run(protocol, area)
        self.assertIn(f"[result] names {other}, not {self.RUN}", str(cm.exception))
        # --force does not replace it either: the declaration is withdrawn first
        with self.assertRaises(ValueError) as cm:
            protocol_fill.from_run(protocol, area, force=True)
        self.assertIn("withdraw it", str(cm.exception))

    def test_a_named_run_that_is_not_completed_refuses(self):
        area = self._area({"x": 1})
        with self.assertRaises(SystemExit):
            protocol_fill.from_run(
                self.PROTOCOL, area, run_id="2026-01-01T00-00-00_0000"
            )

    def test_the_command_refuses_an_unchecked_result_and_leaves_the_file(self):
        """The one adoption path (2026-10-19): the fixture's run has no
        analysis record — report-check
        refuses, and the protocol is byte-identical to before."""
        area = self._area({"mean_docs_per_case": 3.5})
        before = (area / "PROTOCOL-count.md").read_text(encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = protocol_fill.main([str(area / "PROTOCOL-count.md"), "--from-run"])
        self.assertEqual(rc, 1, buf.getvalue())
        self.assertIn("filled from run " + self.RUN, buf.getvalue())
        self.assertIn("not adopted", buf.getvalue())
        self.assertIn("analysis audit", buf.getvalue())
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

- **Conclusion:** <the answer to the question above, in at most two plain sentences…>

## Result (after the run — write back, don't go quiet)

- **Recorded results:** <per registered id its verdict, and the run_id…>

## Runs (protocol run list)

- <run_id> — <one sentence: what this run was>

## Head (read by the checks)

"""

    def _area(self, *, run_kind: RunKind = "measurement", audited: bool = True) -> Path:
        import subprocess

        from labkit.formats import findings, promises, scope_sha
        from protocol_fixture import (
            C1_BLOCK,
            C1_PROSE,
            completed_run,
            scope_file,
            started_at,
        )

        root = Path(tempfile.mkdtemp())
        area = root / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        (area / "scripts" / "02_analyze.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        scope_file(area)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            self.BODY.replace(
                "## Summary",
                "- **Question / hypothesis:** does it hold?\n"
                + C1_PROSE
                + "\n## Summary",
                1,
            )
            + head(repeat_cost="low", promises=C1_BLOCK),
            encoding="utf-8",
        )
        src = area / "data.jsonl"
        src.write_text('{"id": 1}\n', encoding="utf-8")
        # a repository with the registration and the source committed before
        # the run: the low lane's release holds both to git
        for args in (
            ("init", "-q", "."),
            ("config", "user.email", "t@t"),
            ("config", "user.name", "t"),
            ("add", "-A"),
            ("commit", "-qm", "registration"),
        ):
            subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
        run = completed_run(
            area, self.RUN, metrics={"criterion_1_pass": True}, run_kind=run_kind
        )
        started_at(run, root)
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
                shown_sha=shown_sha(area, area / "runs" / self.RUN),
                registration=registration_of(area),
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
        self.assertIn(f"criterion-1 met · recorded: (run {self.RUN})", text)
        self.assertEqual(protocol_block.declared_run(text), self.RUN)

    def test_a_probe_is_refused_and_the_file_is_as_it_was(self):
        area = self._area(run_kind="probe")
        before = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        rc, out, text = self._adopt(area)
        self.assertEqual(rc, 1, out)
        self.assertIn("a probe (run_kind='probe'), not a measurement", out)
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
        state with its text (`report_context.PROPOSED`), written through
        `files.write_atomic`: no half-written protocol, no temp file left."""
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
                protocol_fill.files,
                "write_atomic",
                wraps=protocol_fill.files.write_atomic,
            ) as atomic,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            rc = protocol_fill.main([str(proto), "--from-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(seen["state"], protocol_fill.report_check.PROPOSED)
        self.assertIn(f"criterion-1 met · recorded: (run {self.RUN})", seen["text"])
        self.assertEqual(atomic.call_count, 1)
        self.assertEqual(proto.read_text(encoding="utf-8"), seen["text"])
        self.assertEqual([p.name for p in area.glob(".PROTOCOL-*")], [])


class WithdrawText(unittest.TestCase):
    """`protocol_fill.withdraw` on a protocol's text: the declaration gone,
    the generated lines reset, the trace on the run's Runs entry — also for a
    `[result]` that does not read, which no audit may crash on
    (`protocol_block.declared_run_shown`). The chain through the commands
    stands in test_end_to_end.Withdraw."""

    RUN = "2026-01-01T00-00-00_0001"
    DAY = "2026-10-28"

    def protocol(self, result: str | None) -> str:
        return (
            "# Experiment protocol: x\n\n## Result\n\n"
            f"- **Recorded results:** lines_mean = 3.0 (run {self.RUN})\n"
            "- **Limitation (audit 2026-01-01T00-00-analysis #1):** the verdicts stand\n"
            "- **Deviations after freeze:** none\n\n"
            f"## Runs\n\n- {self.RUN} — the kept run\n\n## Head\n\n"
            + head(result=result)
        )

    def test_the_declaration_goes_and_the_trace_stays_on_the_runs_entry(self):
        new, run = protocol_fill.withdraw(
            self.protocol(self.RUN), "code changed", self.DAY
        )
        self.assertEqual(run, self.RUN)
        self.assertIsNone(protocol_block.declared_run(new))
        self.assertIn(
            f"- {self.RUN} — the kept run · withdrawn {self.DAY}: code changed", new
        )
        (rr,) = [f for f in protocol_check.fields(new) if f.name == "recorded results"]
        self.assertTrue(rr.placeholder)  # the next --from-run needs no --force
        self.assertIn(
            f"run {self.RUN} is no longer the result — code changed", rr.value
        )
        self.assertNotIn("Limit (audit", new)
        self.assertIn("- **Deviations after freeze:** none", new)  # the rest kept

    def test_a_declaration_that_does_not_read_is_withdrawn_too(self):
        text = self.protocol("final")
        with self.assertRaises(protocol_block.BlockError):
            protocol_block.declared_run(text)
        shown = protocol_block.declared_run_shown(text)
        assert shown is not None
        self.assertIn("does not read", shown)
        piece = audit_binding.declared_piece(None, shown)
        self.assertEqual(len(piece), 1)  # the audit shows it, never crashes on it
        new, _ = protocol_fill.withdraw(text, "a typed run id", self.DAY)
        self.assertIsNone(protocol_block.declared_run(new))
        self.assertIn(f"withdrawn {self.DAY}: a typed run id", new)

    def test_nothing_declared_or_no_reason_is_refused(self):
        with self.assertRaises(ValueError):
            protocol_fill.withdraw(self.protocol(None), "why", self.DAY)
        with self.assertRaises(ValueError):
            protocol_fill.withdraw(self.protocol(self.RUN), "  ", self.DAY)

    def test_the_declared_piece_stands_only_beside_another_run(self):
        run = Path("/x/runs") / self.RUN
        self.assertEqual(audit_binding.declared_piece(run, None), [])
        self.assertEqual(
            audit_binding.declared_piece(run, self.RUN), []
        )  # first adoption
        ((label, text),) = audit_binding.declared_piece(run, "2026-01-01T00-00-00_0000")
        self.assertEqual(label, audit_binding.DECLARED_LABEL)
        self.assertIn("2026-01-01T00-00-00_0000", text)

    def test_a_declaration_is_never_replaced_by_another_run(self):
        text = self.protocol(self.RUN)
        self.assertEqual(protocol_fill.fill_result_run(text, self.RUN), text)
        with self.assertRaises(ValueError) as cm:
            protocol_fill.fill_result_run(text, "2026-01-01T00-00-00_0002")
        self.assertIn("withdraw it", str(cm.exception))

    def test_withdraw_takes_why_and_no_other_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PROTOCOL-x.md"
            p.write_text(self.protocol(self.RUN), encoding="utf-8")
            for argv in (
                [str(p), "--withdraw"],
                [str(p), "--withdraw", "--why", "w", "--force"],
                [str(p), "--withdraw", "--why", "w", "--from-run", self.RUN],
            ):
                with self.subTest(argv=argv[1:]):
                    with (
                        self.assertRaises(SystemExit),
                        contextlib.redirect_stderr(io.StringIO()),
                    ):
                        protocol_fill.main(argv)
            self.assertEqual(p.read_text(encoding="utf-8"), self.protocol(self.RUN))


class PromiseSentences(unittest.TestCase):
    """The [[promise]] sentences of the TOML head: `--list` names the open
    ones and `"<id> sentence=..."` fills one as a TOML string. Every judge
    probe of 2026-10-20 found them only by reading the file, one lost a
    commit to them, and a hand-written TOML string broke on a quote."""

    BLOCK = (
        "[[promise]]\n"
        'id = "criterion-1"\n'
        'key = "criterion_1_pass"\n'
        'sentence = "<the criterion in one sentence>"\n'
        'scope = ["scripts/01_measure.py"]\n'
        "constants = { margin = 0.25 }\n"
        "\n"
        "[[promise]]\n"
        'id = "quality-check-1"\n'
        'key = "quality_check_1_pass"\n'
        'sentence = "at most max_empty empty answers"\n'
        'scope = ["scripts/01_measure.py"]\n'
        "constants = { max_empty = 2 }\n"
    )

    def text(self) -> str:
        return "# P\n\n" + head(repeat_cost="low", promises=self.BLOCK)

    def test_list_names_the_open_sentence_and_not_the_written_one(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(self.text(), encoding="utf-8")
            with contextlib.redirect_stdout(out):
                self.assertEqual(protocol_fill.main([str(p), "--list"]), 0)
        line = (
            self.text()
            .splitlines()
            .index('sentence = "<the criterion in one sentence>"')
        )
        self.assertIn(f"{line + 1:4d}  criterion-1 sentence", out.getvalue())
        self.assertNotIn("quality-check-1 sentence", out.getvalue())

    def test_a_fill_writes_a_toml_string_that_reads_back(self):
        value = 'registered accuracy >= null + margin; "empty" counts as wrong \\ ok'
        new = protocol_fill.fill_many(self.text(), [("criterion-1 sentence", value)])
        from labkit.formats import promises

        block = promises.parse_block(new)
        assert block is not None
        self.assertEqual(
            {p.id: p.sentence for p in block.promises}["criterion-1"], value
        )
        self.assertEqual(promises.placeholder_sentences(block), [])
        self.assertEqual(
            [ln for ln in new.splitlines() if not ln.startswith("sentence")],
            [ln for ln in self.text().splitlines() if not ln.startswith("sentence")],
        )

    def test_a_written_sentence_needs_force_and_an_unknown_id_is_named(self):
        with self.assertRaisesRegex(ValueError, "already written"):
            protocol_fill.fill_many(self.text(), [("quality-check-1 sentence", "x")])
        new = protocol_fill.fill_many(
            self.text(), [("quality-check-1 sentence", "y")], force=True
        )
        self.assertIn('sentence = "y"', new)
        with self.assertRaisesRegex(
            ValueError,
            r"no \[\[promise\]\] 'branch-9'.*criterion-1, quality-check-1",
        ):
            protocol_fill.fill_many(self.text(), [("branch-9 sentence", "x")])

    def test_one_call_fills_a_field_and_a_sentence_or_nothing(self):
        text = self.text() + "\n- **Unit:** <the unit>\n"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = protocol_fill.main(
                    [str(p), "Unit=one case", "branch-9 sentence=x"]
                )
            self.assertEqual(rc, 2)
            self.assertEqual(p.read_text(encoding="utf-8"), text)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = protocol_fill.main(
                    [str(p), "Unit=one case", "criterion-1 sentence=s"]
                )
            self.assertEqual(rc, 0)
            self.assertIn('sentence = "s"', p.read_text(encoding="utf-8"))


class PromiseSentencesReview(unittest.TestCase):
    """What an independent review of the sentence fill found (2026-10-20):
    a valid id spelling dropped the table from `--list`, a line cut other
    than the fence walker's moved the line, a value with a character that
    `str.splitlines` cuts broke the written string, and a prose label of
    one word plus "sentence" was taken for a promise id."""

    def text(self, id_line: str = 'id = "criterion-1"', prose: str = "") -> str:
        block = (
            "[[promise]]\n"
            f"{id_line}\n"
            'key = "criterion_1_pass"\n'
            'sentence = "<the criterion>"\n'
            'scope = ["scripts/01_measure.py"]\n'
        )
        return "# P\n" + prose + "\n" + head(repeat_cost="low", promises=block)

    def listed(self, text: str) -> str:
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(out):
                self.assertEqual(protocol_fill.main([str(p), "--list"]), 0)
        return out.getvalue()

    def sentence_line(self, text: str) -> int:
        return 1 + text.splitlines().index('sentence = "<the criterion>"')

    def test_every_valid_id_spelling_lists_and_fills(self):
        for id_line in (
            'id = "criterion-1"  # the criterion',
            "id = 'criterion-1'",
            '"id" = "criterion-1"',
        ):
            with self.subTest(id_line=id_line):
                text = self.text(id_line)
                self.assertIn(
                    f"{self.sentence_line(text):4d}  criterion-1 sentence",
                    self.listed(text),
                )
                new = protocol_fill.fill_many(text, [("criterion-1 sentence", "s")])
                self.assertIn('sentence = "s"', new)

    def test_a_line_break_character_in_the_prose_keeps_the_line(self):
        for mark in (" ", "\x85", "\x0c"):
            with self.subTest(mark=repr(mark)):
                text = self.text(prose=f"a{mark}b\n")
                self.assertIn(
                    f"{self.sentence_line(text):4d}  criterion-1 sentence",
                    self.listed(text),
                )
                new = protocol_fill.fill_many(text, [("criterion-1 sentence", "s")])
                self.assertIn(f"a{mark}b", new)
                self.assertIn('sentence = "s"', new)

    def test_every_character_a_line_cut_or_toml_refuses_reads_back(self):
        from labkit.formats import promises

        value = "a b c\x85d\x7fe\nf\tg\\h\"i'"
        new = protocol_fill.fill_many(self.text(), [("criterion-1 sentence", value)])
        block = promises.parse_block(new)
        assert block is not None
        self.assertEqual(block.promises[0].sentence, value)

    def test_a_lone_surrogate_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, "surrogate"):
            protocol_fill.fill_many(self.text(), [("criterion-1 sentence", "a\udcffb")])

    def test_a_prose_label_ending_in_sentence_stays_a_prose_field(self):
        text = self.text() + "\n- **Key sentence:** <the one sentence>\n"
        new = protocol_fill.fill_many(text, [("Key sentence", "k")])
        self.assertIn("- **Key sentence:** k", new)

    def test_line_is_refused_for_a_promise_sentence(self):
        with self.assertRaisesRegex(ValueError, "--line"):
            protocol_fill.fill_many(
                self.text(), [("criterion-1 sentence", "s")], line_no=3
            )
