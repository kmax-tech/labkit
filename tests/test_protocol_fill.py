"""Tests for protocol-fill — fill a stamped placeholder by label.

Why this is tested: filling a protocol field by quoting its placeholder text
back is fragile, so a field is filled by its label. The label match must hit single- and multi-line placeholders, refuse
ambiguity and silent overwrites, and leave every other byte alone.
"""

from labkit.formats import run_index
from labkit.formats.repo import pending_adoption
from labkit.formats.runs import RunKind

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test

from labkit import PACKAGE_DIR  # noqa: E402
from labkit.tools import protocol_fill  # noqa: E402
from labkit.tools import protocol_edit
from labkit.tools import protocol_result
from labkit.checks import audit_binding  # noqa: E402
from labkit.checks import prompt_check  # noqa: E402
from labkit.formats import protocol_block, protocol_check  # noqa: E402
from protocol_fixture import (  # noqa: E402
    registration_of,
    run_record,
    PID,
    head,
    shown_sha,
    source_entry,
)

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
        out = protocol_edit.fill(SAMPLE, "Conclusion", "K2 PASS, run 2026-x")
        self.assertIn("- **Conclusion †:** K2 PASS, run 2026-x", out)
        self.assertNotIn("<number(s)", out)
        self.assertIn("does Y move X?", out)  # untouched neighbours

    def test_multi_line_placeholder_collapses_to_the_filled_line(self):
        out = protocol_edit.fill(
            SAMPLE, "Meaning of the gold label", "positive = the judge prefers world A"
        )
        self.assertIn(
            "- **Meaning of the gold label †:** positive = the judge prefers world A",
            out,
        )
        self.assertNotIn("annotator's words", out)

    def test_label_match_ignores_dagger_and_case(self):
        out = protocol_edit.fill(SAMPLE, "conclusion †", "filled")
        self.assertIn("- **Conclusion †:** filled", out)

    def test_filled_field_is_refused_without_force(self):
        with self.assertRaises(ValueError) as ctx:
            protocol_edit.fill(SAMPLE, "Model / tool", "gpt-oss")
        self.assertIn("already filled", str(ctx.exception))
        out = protocol_edit.fill(SAMPLE, "Model / tool", "gpt-oss", force=True)
        self.assertIn("- **Model / tool:** gpt-oss", out)

    def test_unknown_label_lists_the_open_fields(self):
        with self.assertRaises(ValueError) as ctx:
            protocol_edit.fill(SAMPLE, "No such field", "x")
        msg = str(ctx.exception)
        self.assertIn("Question", msg)
        self.assertIn("Meaning of the gold label", msg)

    def test_ambiguous_label_requires_line(self):
        two = SAMPLE + "\n- **Conclusion †:** <second stamp>\n"
        with self.assertRaises(ValueError) as ctx:
            protocol_edit.fill(two, "Conclusion", "x")
        self.assertIn("--line", str(ctx.exception))
        out = protocol_edit.fill(two, "Conclusion", "x", line_no=6)
        self.assertIn("- **Conclusion †:** x", out)
        self.assertIn("<second stamp>", out)

    def test_a_wrapped_label_is_read_whole(self):
        """The stamped `Resolution check` label wraps; it is read whole, not
        as `extremes)`."""
        text = "- **Resolution check (ZERO calls,\n  extremes):** <both numbers>\n"
        out = protocol_edit.fill(text, "Resolution check", "fires 1.0, silent 0.0")
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
# f-string answer line joined from ANSWERS (a plain literal here would hide
# a skeleton whose prompts the reader cannot read).
SCRIPT = (
    'ANSWERS = {"Yes": "causal", "No": "not_causal"}\n'
    "ANSWER_LINE = f\"Answer with a single word, {' or '.join(ANSWERS)}.\"\n"
    'PROMPT = ("Does this text make a causal claim?\\n\\n"\n'
    '          "Text: {text}\\n\\n" + ANSWER_LINE + "\\n\\nAnswer:")\n'
    'PROMPT_NULL = ("Is this text written in English?\\n\\n"\n'
    '               "Text: {text}\\n\\n" + ANSWER_LINE + "\\n\\nAnswer:")\n'
)
# A half-readable form: the registered prompt joins `ANSWERS.keys()`,
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
        self.assertEqual(protocol_edit.head_open(self.HEAD, "type"), 7)
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
        self.assertIsNone(protocol_edit.head_open(text, "type"))
        # the head reads: the hook's "MISSING (must): [protocol] type" is gone
        self.assertEqual(protocol_block.head(text).type, "exploratory")

    def test_a_head_key_named_with_its_table_is_filled(self):
        """`"[protocol] type=…"` fills the head key, not "no field labelled":
        the key named with its table is the key."""
        text = protocol_edit.fill_many(self.HEAD, [("[protocol] type", "exploratory")])
        self.assertEqual(protocol_block.head(text).type, "exploratory")

    def test_a_head_part_protocol_fill_does_not_write_names_where_it_is_written(self):
        for label, way in (
            ("[reference]", "--reference VALUE"),
            ("reference value", "--reference VALUE"),
            ("[result] run", "labkit-adopt"),
            ("standard", "stamped and never edited"),
        ):
            with self.subTest(label=label), self.assertRaises(ValueError) as cm:
                protocol_edit.fill_many(self.HEAD, [(label, "x")])
            self.assertIn("is not a field", str(cm.exception))
            self.assertIn(way, str(cm.exception))

    def test_the_twin_a_prose_field_is_still_filled_by_its_label(self):
        text = protocol_edit.fill_many(self.HEAD, [("Unit", "one row per case")])
        self.assertIn("- **Unit:** one row per case", text)

    def test_list_sets_the_fields_from_run_writes_apart(self):
        """Result and Answer are listed apart: among the rest they would read
        as owed before the run, and a value filled in by hand ("pending
        run") is one --from-run refuses to overwrite."""
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
        for label in protocol_result.WRITTEN_BY_RUN:
            self.assertNotIn(label, before)
            self.assertIn(label, after)
        self.assertIn("Question / hypothesis", before)

    def test_a_type_line_in_a_fenced_example_is_not_the_head(self):
        """A prompt quoting TOML output may carry `type = "<…>"`; it is not
        the head, which is read inside the one ```toml block."""
        example = (
            '- **Prompt:**\n\n  ```text\n  answer as\n  type = "<yes | no>"\n  ```\n\n'
        )
        text = example + self.HEAD.replace(
            '"<exploratory | confirmatory>"', '"exploratory"'
        )
        self.assertIsNone(protocol_edit.head_open(text, "type"))
        text = example + self.HEAD
        line = protocol_edit.head_open(text, "type")
        assert line is not None
        self.assertEqual(
            text.splitlines()[line - 1].strip(), 'type = "<exploratory | confirmatory>"'
        )
        filled = protocol_edit.fill_head(text, "type", "confirmatory")
        self.assertIn('type = "<yes | no>"', filled)  # the example is untouched
        self.assertIn('type = "confirmatory"', filled)

    def test_the_head_cost_left_by_the_stamp_is_listed_and_set(self):
        """`labkit-init exp` without --repeat-cost leaves `cost = "<…>"`; --list
        names it beside type and a fill sets it, so the head is never edited
        by hand."""
        text = self.HEAD.replace('repeat_cost = "low"', 'repeat_cost = "<low | high>"')
        self.assertEqual(protocol_edit.head_open(text, "repeat_cost"), 8)
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
        self.assertIsNone(protocol_edit.head_open(filled, "repeat_cost"))
        with self.assertRaisesRegex(ValueError, "repeat_cost must be one of low"):
            protocol_edit.fill_head(text, "repeat_cost", "days")
        with self.assertRaisesRegex(ValueError, "not a choice protocol-fill sets"):
            protocol_edit.head_open(text, "frozen")

    def test_the_model_alias_left_by_a_bare_model_flag_is_listed_and_set(self):
        """`labkit-init exp --model` without an alias stamps `[model] alias =
        "<alias from models.toml>"`; --list names it
        and `"model alias=haiku"` writes it as a TOML string."""
        text = self.HEAD.replace(
            'preflight_audit = "none"\n',
            'preflight_audit = "none"\n\n[model]\nalias = "<alias from models.toml>"\n',
        )
        self.assertEqual(protocol_edit.head_open(text, "alias"), 14)
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
        self.assertIsNone(protocol_edit.head_open(filled, "alias"))
        with self.assertRaisesRegex(ValueError, "alias: an empty value"):
            protocol_edit.fill_head(text, "alias", " ")

    def test_number_describes_is_listed_and_set_and_the_freeze_says_how(self):
        # a MUST of a computation with a model is listed and set by the tool,
        # and the freeze keys name `--freeze`, not "no field labelled"
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
            protocol_edit.fill_many(text, [("number_describes", "outputs")])
        for key in ("frozen", "preflight_audit"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    ValueError, "protocol-fill <PROTOCOL> --freeze"
                ):
                    protocol_edit.fill_many(text, [(key, "true")])

    def test_list_sets_apart_the_fields_this_protocol_does_not_owe(self):
        # a high computation without a model owes no data profile or prompt:
        # they are listed apart
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
            protocol_edit.fill_head(self.HEAD, "type", "descriptive")
        with self.assertRaises(ValueError):
            protocol_edit.fill_head(
                self.HEAD.replace('"<exploratory | confirmatory>"', '"exploratory"'),
                "type",
                "confirmatory",
            )


class Freeze(unittest.TestCase):
    """`protocol-fill --freeze`, the one writer of the freeze: it writes both
    keys once the proposed head passes the freeze gate's checks and refuses
    them otherwise, the file as it was — so a protocol with open fields or
    an undecided audit is never frozen to meet the gates one by one."""

    def _area(self) -> tuple[Path, Path]:
        from protocol_fixture import scope_file

        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        scope_file(area)
        protocol = area / "PROTOCOL-x.md"
        protocol.write_text(
            head(repeat_cost="high") + "- **Unit:** <what one thing is>\n",
            encoding="utf-8",
        )
        return area, protocol

    def _record(self, area: Path, rows: list[tuple[str, str]]) -> Path:
        from labkit.formats import findings, promises, scope_sha

        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        return findings.write(
            area,
            "preflight",
            "opus",
            scope_sha.area_stamp(area)[0],
            promises.block_stamp(text),
            (sum(g == "BLOCKER" for g, _ in rows), 0, 0),
            rows,
            registration=registration_of(area),
        )

    def test_set_freeze_rewrites_both_keys_and_nothing_else(self):
        text = head(repeat_cost="high")
        frozen = protocol_edit.set_freeze(text, "2026-01-01T00-00-preflight.toml")
        self.assertIn("\nfrozen = true\n", frozen)
        self.assertIn('\npreflight_audit = "2026-01-01T00-00-preflight.toml"\n', frozen)
        self.assertEqual(
            [
                ln
                for ln in text.splitlines()
                if not ln.startswith(("frozen", "preflight_audit"))
            ],
            [
                ln
                for ln in frozen.splitlines()
                if not ln.startswith(("frozen", "preflight_audit"))
            ],
        )
        with self.assertRaisesRegex(
            ValueError, "no frozen and no preflight_audit line"
        ):
            protocol_edit.set_freeze(
                text.replace("frozen = false", "").replace('preflight_audit = ""', ""),
                "x",
            )

    def test_without_a_preflight_record_the_freeze_is_refused_and_the_file_kept(self):
        area, protocol = self._area()
        before = protocol.read_text(encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = protocol_fill.main([str(protocol), "--freeze"])
        self.assertEqual(rc, 2)
        self.assertIn("holds no preflight audit record", err.getvalue())
        self.assertIn("--mode preflight", err.getvalue())
        self.assertEqual(protocol.read_text(encoding="utf-8"), before)

    def test_an_open_field_or_an_undecided_blocker_refuses_the_freeze(self):
        """The writer's half of the gates' rule: what protocol-check would
        hold frozen (a should field, a must at the freeze) and what
        runlog's freeze gate would refuse (an open preflight BLOCKER) refuse
        the write, named together; nothing is written."""
        area, protocol = self._area()
        record = self._record(
            area,
            [
                (
                    "BLOCKER",
                    "BLOCKER · scripts/01_measure.py:1 · statement · x · y · z · fix",
                )
            ],
        )
        before = protocol.read_text(encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = protocol_fill.main([str(protocol), "--freeze"])
        self.assertEqual(rc, 1)
        out = err.getvalue()
        self.assertIn("not frozen", out)
        self.assertIn("PROTOCOL-x.md is as it was", out)
        self.assertIn("MUST field absent", out)
        self.assertIn("MUST field still a placeholder: Unit", out)
        self.assertIn(f"finding(s) of {record.name} still `open`", out)
        self.assertEqual(protocol.read_text(encoding="utf-8"), before)
        # a record named that is not the area's
        with contextlib.redirect_stderr(io.StringIO()):
            rc = protocol_fill.main(
                [str(protocol), "--freeze", "2020-01-01T00-00-preflight.toml"]
            )
        self.assertEqual(rc, 1)
        self.assertEqual(protocol.read_text(encoding="utf-8"), before)


class Prompts(unittest.TestCase):
    """The Prompt block written from the scripts' constants holds against
    code-check's drift check, so it needs no hand patch."""

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
            protocol.write_text(protocol_result.fill_prompts(TEMPLATE, consts))
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
            protocol.write_text(protocol_result.fill_prompts(TEMPLATE, consts))
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
        once = protocol_result.fill_prompts(TEMPLATE, consts)
        self.assertEqual(protocol_result.fill_prompts(once, consts), once)

    def test_no_constant_is_a_sentence(self):
        with self.assertRaises(ValueError) as cm:
            protocol_result.fill_prompts(TEMPLATE, {})
        self.assertIn("no PROMPT constant", str(cm.exception))

    def prompts_cli(self, protocol: Path) -> tuple[int, str, str]:
        """`protocol-fill PROTOCOL --prompts`: (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = protocol_fill.main([str(protocol), "--prompts"])
        return rc, out.getvalue(), err.getvalue()

    def test_an_unreadable_constant_is_named_and_nothing_is_written(self):
        """An answer line joined from `ANSWERS.keys()` is a call the static
        reader does not compute: `--prompts` names it and writes nothing,
        never the null prompt alone said "filled"."""
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
    nothing — one call, not one per field."""

    BODY = (
        "- **Terms of this protocol:** <the terms>\n"
        "- **Unit:** <one thing>\n"
        "- **Data / scope:** <where>\n"
    )

    def test_every_word_with_an_equals_sign_is_one_assignment(self):
        self.assertEqual(
            protocol_edit.assignments_of("Unit=a = b", ["Data / scope=x"]),
            [("Unit", "a = b"), ("Data / scope", "x")],
        )

    def test_the_one_field_form_joins_the_value_words(self):
        self.assertEqual(
            protocol_edit.assignments_of("Unit", ["one", "thing"]),
            [("Unit", "one thing")],
        )
        self.assertEqual(
            protocol_edit.assignments_of("Unit", ["x = 1"]), [("Unit", "x = 1")]
        )

    def test_no_value_is_no_assignment(self):
        self.assertEqual(protocol_edit.assignments_of("Unit", []), [])
        self.assertEqual(protocol_edit.assignments_of(None, []), [])

    def test_fill_many_fills_in_order_and_sets_the_head_type(self):
        text = head(type="<exploratory | confirmatory>") + self.BODY
        new = protocol_edit.fill_many(
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
            protocol_edit.fill_many(text, [("Unit", "one case"), ("Nope", "x")])
        with self.assertRaises(ValueError):
            protocol_edit.fill_many(text, [("Unit", "")])

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
        out = protocol_edit.fill(self.TEXT, "Inference criterion", "acc >= 0.8")
        self.assertEqual(out, "- **Inference criterion:** [criterion-1] acc >= 0.8\n")

    def test_a_value_with_its_own_ids_replaces_it(self):
        out = protocol_edit.fill(
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
    """--from-run: the number is written back from metrics.json, never retyped."""

    PROTOCOL = """# Experiment protocol: count

## Summary (after the run, for a person)

- **Conclusion:** the cases hold a few documents each.

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
        text, filled, run_id = protocol_result.from_run(self.PROTOCOL, area)
        self.assertEqual(run_id, self.RUN)
        self.assertEqual(
            filled, ["Recorded results", protocol_result.RESULT_LABEL, "Runs"]
        )
        line = (
            "mean_docs_per_case = 3.5, n_cases = 12, quality_check_1_pass = True (run "
            + self.RUN
            + ")"
        )
        self.assertIn("- **Recorded results:** " + line, text)
        # the Result is the author's two sentences, not the key dump again:
        # the write-back leaves the author's Conclusion as written
        self.assertIn("- **Conclusion:** the cases hold a few documents each.", text)
        self.assertIn("Conclusion", protocol_result.WRITTEN_AFTER_RUN)
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
        text, _, _ = protocol_result.from_run(self.PROTOCOL, area)
        with self.assertRaises(ValueError) as cm:
            protocol_result.from_run(text, area)
        self.assertIn("already filled", str(cm.exception))
        again, filled, _ = protocol_result.from_run(text, area, force=True)
        self.assertNotIn("Runs", filled)  # the run line is there once, not twice
        self.assertEqual(
            again.count(self.RUN), 3
        )  # [result], the Answer, the Runs line

    def test_the_run_is_declared_in_the_head_after_the_protocol_table(self):
        """`[result] run` is the declaration: written
        once, right after the [protocol] table, read back exactly; the
        template's comment above [protocol] and every other byte stay."""
        area = self._area({"mean_docs_per_case": 3.5})
        text, filled, _ = protocol_result.from_run(self.PROTOCOL, area)
        self.assertIn(protocol_result.RESULT_LABEL, filled)
        self.assertEqual(protocol_block.declared_run(text), self.RUN)
        self.assertIn(f'preflight_audit = ""\n\n[result]\nrun = "{self.RUN}"\n', text)
        again, filled, _ = protocol_result.from_run(text, area, force=True)
        self.assertNotIn(protocol_result.RESULT_LABEL, filled)  # declared already
        self.assertEqual(again.count("[result]"), 1)

    def test_a_head_declaring_another_run_is_refused_not_skipped(self):
        other = "2026-01-01T00-00-00_0000"
        protocol = self.PROTOCOL.replace(
            'preflight_audit = ""\n',
            f'preflight_audit = ""\n\n[result]\nrun = "{other}"\n',
        )
        area = self._area({"mean_docs_per_case": 3.5})
        # the adopted run is the one the choice holds: one that cannot answer
        # is refused with the withdrawal
        with self.assertRaises(SystemExit) as cm:
            protocol_result.from_run(protocol, area)
        self.assertIn(f"[result] names {other}, which cannot answer", str(cm.exception))
        self.assertIn("--withdraw", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            protocol_result.from_run(protocol, area, run_id=self.RUN)
        self.assertIn(f"[result] names {other}, not {self.RUN}", str(cm.exception))
        # --force does not replace it either: the declaration is withdrawn first
        with self.assertRaises(ValueError) as cm:
            protocol_result.from_run(protocol, area, run_id=self.RUN, force=True)
        self.assertIn("withdraw it", str(cm.exception))

    def test_a_named_run_that_is_not_completed_refuses(self):
        area = self._area({"x": 1})
        with self.assertRaises(SystemExit):
            protocol_result.from_run(
                self.PROTOCOL, area, run_id="2026-01-01T00-00-00_0000"
            )

    def test_the_command_refuses_an_unchecked_result_and_leaves_the_file(self):
        """The one adoption path: the fixture's run has no
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

- **Conclusion:** the cases hold a few documents each.

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
        data["data"] = {"cases": source_entry(src)}
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
        # finalize's warnings on the fixture's run are told, nothing blocks
        self.assertIn("report-check: 0 blockers", out)
        self.assertIn(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})", text
        )
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
        """An exception out of report-check restores the protocol as a
        blocker exit does: the unchecked answer never stands."""
        area = self._area()
        proto = area / "PROTOCOL-x.md"
        before = proto.read_text(encoding="utf-8")
        with (
            mock.patch.object(
                protocol_fill.report_check,
                "protocol_verdict",
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
        state with its text (`area_state.PROPOSED`), written through
        `files.write_atomic`: no half-written protocol, no temp file left."""
        area = self._area()
        proto = area / "PROTOCOL-x.md"
        seen: dict = {}

        def check(area_, protocol, *, state, text):
            seen.update(state=state, text=text)
            self.assertEqual(protocol.read_text(encoding="utf-8"), text)
            return SimpleNamespace(exit=0)

        with (
            mock.patch.object(protocol_fill.report_check, "protocol_verdict", check),
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
        self.assertIn(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            seen["text"],
        )
        # the protocol as it stood, kept beside it, then the proposal — each whole
        written = [c.args[0] for c in atomic.call_args_list]
        self.assertEqual(
            written,
            [
                pending_adoption(proto.resolve()),
                proto.resolve(),
            ],
        )
        self.assertEqual(proto.read_text(encoding="utf-8"), seen["text"])
        self.assertEqual([p.name for p in area.glob(".PROTOCOL-*")], [])


class WithdrawText(unittest.TestCase):
    """`protocol_result.withdraw` on a protocol's text: the declaration gone,
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
        new, run = protocol_result.withdraw(
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
        new, _ = protocol_result.withdraw(text, "a typed run id", self.DAY)
        self.assertIsNone(protocol_block.declared_run(new))
        self.assertIn(f"withdrawn {self.DAY}: a typed run id", new)

    def test_nothing_declared_or_no_reason_is_refused(self):
        with self.assertRaises(ValueError):
            protocol_result.withdraw(self.protocol(None), "why", self.DAY)
        with self.assertRaises(ValueError):
            protocol_result.withdraw(self.protocol(self.RUN), "  ", self.DAY)

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
        self.assertEqual(protocol_result.fill_result_run(text, self.RUN), text)
        with self.assertRaises(ValueError) as cm:
            protocol_result.fill_result_run(text, "2026-01-01T00-00-00_0002")
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
    ones and `"<id> sentence=..."` fills one as a TOML string: nobody has to
    find them by reading the file, and no hand-written TOML string breaks on
    a quote."""

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
        new = protocol_edit.fill_many(self.text(), [("criterion-1 sentence", value)])
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
            protocol_edit.fill_many(self.text(), [("quality-check-1 sentence", "x")])
        new = protocol_edit.fill_many(
            self.text(), [("quality-check-1 sentence", "y")], force=True
        )
        self.assertIn('sentence = "y"', new)
        with self.assertRaisesRegex(
            ValueError,
            r"no \[\[promise\]\] 'branch-9'.*criterion-1, quality-check-1",
        ):
            protocol_edit.fill_many(self.text(), [("branch-9 sentence", "x")])

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
    """The sentence fill's edges: every valid id spelling keeps its table in
    `--list`, the line is cut as the fence walker cuts it, a value with a
    character that `str.splitlines` cuts is written as one valid string,
    and a prose label of one word plus "sentence" is no promise id."""

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
                new = protocol_edit.fill_many(text, [("criterion-1 sentence", "s")])
                self.assertIn('sentence = "s"', new)

    def test_a_line_break_character_in_the_prose_keeps_the_line(self):
        for mark in (" ", "\x85", "\x0c"):
            with self.subTest(mark=repr(mark)):
                text = self.text(prose=f"a{mark}b\n")
                self.assertIn(
                    f"{self.sentence_line(text):4d}  criterion-1 sentence",
                    self.listed(text),
                )
                new = protocol_edit.fill_many(text, [("criterion-1 sentence", "s")])
                self.assertIn(f"a{mark}b", new)
                self.assertIn('sentence = "s"', new)

    def test_every_character_a_line_cut_or_toml_refuses_reads_back(self):
        from labkit.formats import promises

        value = "a b c\x85d\x7fe\nf\tg\\h\"i'"
        new = protocol_edit.fill_many(self.text(), [("criterion-1 sentence", value)])
        block = promises.parse_block(new)
        assert block is not None
        self.assertEqual(block.promises[0].sentence, value)

    def test_a_lone_surrogate_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, "surrogate"):
            protocol_edit.fill_many(self.text(), [("criterion-1 sentence", "a\udcffb")])

    def test_a_prose_label_ending_in_sentence_stays_a_prose_field(self):
        text = self.text() + "\n- **Key sentence:** <the one sentence>\n"
        new = protocol_edit.fill_many(text, [("Key sentence", "k")])
        self.assertIn("- **Key sentence:** k", new)

    def test_line_is_refused_for_a_promise_sentence(self):
        with self.assertRaisesRegex(ValueError, "--line"):
            protocol_edit.fill_many(
                self.text(), [("criterion-1 sentence", "s")], line_no=3
            )


class FieldAddressGuidance(unittest.TestCase):
    """Misaddressed fields name the existing write path without changing input."""

    def test_a_table_prefix_without_a_space_is_read_for_every_table(self):
        """`[protocol]type=` and `[kept]key=` are both read: one rule for the
        table prefix."""
        with tempfile.TemporaryDirectory() as tmp:
            protocol = Path(tmp) / "PROTOCOL-x.md"
            protocol.write_text(
                head(
                    type="<exploratory | confirmatory>",
                    kind="compute",
                    kept=("<metrics key>", "<unit>"),
                    promises=None,
                ),
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    protocol_fill.main(
                        [
                            str(protocol),
                            "[kept]key=mean_score",
                            "[protocol]type=exploratory",
                        ]
                    ),
                    0,
                )
            text = protocol.read_text(encoding="utf-8")
        self.assertIn('key = "mean_score"', text)
        self.assertIn('type = "exploratory"', text)

    def test_head_misses_show_a_valid_address_and_leave_the_file_untouched(self):
        for wrong, correct, value in (
            ("key", "kept.key", "mean_score"),
            ("protocol.type", "type", "exploratory"),
        ):
            with self.subTest(wrong=wrong), tempfile.TemporaryDirectory() as tmp:
                protocol = Path(tmp) / "PROTOCOL-x.md"
                before = head(
                    type="<exploratory | confirmatory>",
                    kind="compute",
                    kept=("<metrics key>", "<unit>"),
                    promises=None,
                )
                protocol.write_text(before, encoding="utf-8")
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                    code = protocol_fill.main([str(protocol), f"{wrong}={value}"])
                self.assertEqual(code, 2, out.getvalue())
                self.assertIn(f'"{correct}=VALUE"', out.getvalue())
                self.assertEqual(protocol.read_text(encoding="utf-8"), before)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        protocol_fill.main([str(protocol), f"{correct}={value}"]), 0
                    )

    def test_a_bare_promise_id_points_to_its_sentence_not_a_prose_field(self):
        before = head(kind="fit", promises=PromiseSentences.BLOCK)
        before += "\n- **Inference criterion:** <the criterion>\n"
        for wrong in ("criterion-1", "[criterion-1]"):
            with self.subTest(wrong=wrong), tempfile.TemporaryDirectory() as tmp:
                protocol = Path(tmp) / "PROTOCOL-x.md"
                protocol.write_text(before, encoding="utf-8")
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                    code = protocol_fill.main([str(protocol), f"{wrong}=score >= 0.9"])
                self.assertEqual(code, 2, out.getvalue())
                self.assertIn('"criterion-1 sentence=VALUE"', out.getvalue())
                self.assertNotIn("did you mean inference criterion", out.getvalue())
                self.assertEqual(protocol.read_text(encoding="utf-8"), before)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        protocol_fill.main(
                            [str(protocol), "criterion-1 sentence=score >= 0.9"]
                        ),
                        0,
                    )

    def test_runs_points_to_adoption_instead_of_a_handwritten_field(self):
        with self.assertRaises(ValueError) as cm:
            protocol_edit.fill_many(SAMPLE, [("Runs", "some run")])
        self.assertIn("generated", str(cm.exception))
        self.assertIn("labkit-adopt", str(cm.exception))

    def test_real_prose_fields_and_ordinary_typo_suggestions_keep_working(self):
        text = SAMPLE + "\n- **Key:** <an ordinary prose field>\n"
        self.assertIn(
            "- **Key:** chosen", protocol_edit.fill_many(text, [("key", "chosen")])
        )
        with self.assertRaises(ValueError) as cm:
            protocol_edit.fill_many(SAMPLE, [("Concluion", "answer")])
        self.assertIn("did you mean conclusion", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            protocol_edit.fill_many(head(kind="fit"), [("key", "score")])
        self.assertNotIn("kept.key", str(cm.exception))


class ReportSetter(unittest.TestCase):
    """`protocol-fill P report=REPORT.md`: the head's `[protocol] report`
    registered on a stamped protocol before its first measurement — the
    route for an area stamped without `--report-file`. After the first
    measurement the registered report is bound: no fill, `--force`
    included, registers, moves or drops it."""

    def _area(self) -> tuple[Path, Path]:
        from protocol_fixture import head as fixture_head

        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        area.mkdir(parents=True)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            fixture_head(repeat_cost="low", kind="compute")
            + "- **Question / hypothesis:** does it hold?\n",
            encoding="utf-8",
        )
        return area, proto

    def _measurement(
        self, area: Path, name: str, *, metrics: dict[str, int] | None = None
    ) -> None:
        """Record a measurement against a real committed registration."""
        from protocol_fixture import completed_run, head_commit, scope_file

        scope_file(area)
        root = area.parents[1]
        for args in (
            ("init", "-q"),
            ("config", "user.email", "t@t"),
            ("config", "user.name", "t"),
            ("add", "-A"),
            ("commit", "-qm", "registration"),
        ):
            subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
        run = completed_run(area, name, metrics=metrics)
        config = run / "config.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        value.update(head_commit(root))
        config.write_text(json.dumps(value), encoding="utf-8")

    def _fill(self, proto: Path, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = protocol_fill.main([str(proto), *args])
        return code, out.getvalue()

    def test_before_the_first_measurement_one_head_line_is_added(self):
        _, proto = self._area()
        before = proto.read_text(encoding="utf-8")
        self.assertEqual(self._fill(proto, "report=REPORT.md")[0], 0)
        after = proto.read_text(encoding="utf-8")
        self.assertEqual(protocol_block.head(after).report, "REPORT.md")
        added = [line for line in after.splitlines() if line not in before.splitlines()]
        self.assertEqual(added, ['report = "REPORT.md"'])
        self.assertEqual(len(after.splitlines()), len(before.splitlines()) + 1)
        # the label with its table is the same key; the same file is unchanged
        self.assertEqual(self._fill(proto, "[protocol] report=./REPORT.md")[0], 0)
        self.assertEqual(proto.read_text(encoding="utf-8"), after)

    def test_another_file_needs_force_before_the_first_measurement(self):
        _, proto = self._area()
        self._fill(proto, "report=REPORT.md")
        code, out = self._fill(proto, "report=docs/REPORT.md")
        self.assertEqual(code, 2)
        self.assertIn("--force", out)
        self.assertEqual(
            protocol_block.head(proto.read_text("utf-8")).report, "REPORT.md"
        )
        self.assertEqual(self._fill(proto, "report=docs/REPORT.md", "--force")[0], 0)
        text = proto.read_text(encoding="utf-8")
        self.assertEqual(protocol_block.head(text).report, "docs/REPORT.md")
        self.assertEqual(text.count("report = "), 1)

    def test_a_path_the_head_cannot_hold_is_refused_and_nothing_written(self):
        _, proto = self._area()
        before = proto.read_text(encoding="utf-8")
        for bad in ("/abs/REPORT.md", "../REPORT.md", "REPORT.txt"):
            with self.subTest(bad=bad):
                self.assertEqual(self._fill(proto, f"report={bad}")[0], 2)
                self.assertEqual(proto.read_text(encoding="utf-8"), before)

    def test_after_the_first_measurement_no_fill_moves_the_bound_report(self):
        area, proto = self._area()
        self._fill(proto, "report=REPORT.md")
        self._measurement(area, "2026-01-01T00-00-00_0001")
        before = proto.read_text(encoding="utf-8")
        for args in (("report=OTHER.md",), ("report=OTHER.md", "--force")):
            with self.subTest(args=args):
                code, out = self._fill(proto, *args)
                self.assertEqual(code, 2)
                self.assertIn("before its first measurement", out)
                self.assertIn("--handover", out)
                self.assertEqual(proto.read_text(encoding="utf-8"), before)
        # the twin: the same file is no change and passes
        self.assertEqual(self._fill(proto, "report=REPORT.md")[0], 0)

    def test_after_the_first_measurement_none_is_registered_late(self):
        """Registration after the first measurement is not supported yet:
        refused, also when the run's directory is gone and runs.tsv lists it."""
        import shutil

        from labkit.run import runlog
        from protocol_fixture import completed_run

        area, proto = self._area()
        self._measurement(area, "2026-01-01T00-00-00_0001", metrics={"n": 1})
        runlog.reindex(area)
        shutil.rmtree(area / "runs")
        before = proto.read_text(encoding="utf-8")
        code, out = self._fill(proto, "report=REPORT.md")
        self.assertEqual(code, 2)
        self.assertIn("first measurement is missing", out)
        self.assertEqual(proto.read_text(encoding="utf-8"), before)
        # the twin: a probe is no measurement; nothing binds yet
        (area / run_index.RUN_INDEX).unlink()
        completed_run(area, "2026-01-01T00-00-00_0002", run_kind="probe")
        self.assertEqual(self._fill(proto, "report=REPORT.md")[0], 0)

    def test_a_short_index_row_refuses_the_registration_instead_of_hiding_a_run(self):
        """runs.tsv truncated to the run id of a deleted measurement is not
        read as no measurement: the late registration is refused, naming
        the line, the protocol unchanged."""
        import shutil

        from labkit.run import runlog

        area, proto = self._area()
        self._measurement(area, "2026-01-01T00-00-00_0001", metrics={"n": 1})
        runlog.reindex(area)
        shutil.rmtree(area / "runs")
        index = area / run_index.RUN_INDEX
        header, row = index.read_text(encoding="utf-8").splitlines()
        index.write_text(f"{header}\n{row.split(chr(9))[0]}\n", encoding="utf-8")
        before = proto.read_text(encoding="utf-8")
        code, out = self._fill(proto, "report=REPORT.md")
        self.assertEqual(code, 2, out)
        self.assertIn("runs.tsv:2", out)
        self.assertEqual(proto.read_text(encoding="utf-8"), before)
