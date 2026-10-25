"""Robustness found by the audit of 0.48.0 (review 2026-10-07): each case used
to end in a traceback, a silent pass, or a statement that was not true."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from labkit.checks import intent_check, recheck
from labkit.run import runlog
from labkit.formats import promises, protocol_block, protocol_check, protocol_report
from protocol_fixture import PID, head

C1 = """[[promise]]
id = "C1"
key = "c1_pass"
sentence = "accuracy >= min_acc"
scope = ["scripts/m.py:evaluate"]
constants = { min_acc = 0.7 }
"""


def area_with_run(tmp: Path) -> tuple[Path, Path]:
    """An area with a promise-bound protocol and one completed run recorded by runlog."""
    (tmp / "scripts").mkdir()
    (tmp / "scripts" / "m.py").write_text("def evaluate(rows):\n    return 1\n")
    protocol = tmp / "PROTOCOL-x.md"
    protocol.write_text(head(promises=C1) + "\nCriterion [C1].\n")
    with contextlib.redirect_stdout(io.StringIO()):
        with runlog.run("t", {"min_acc": 0.7}, base_dir=tmp) as r:
            r.metrics(c1_pass=True)
    return protocol, r.dir


class DeclaredScope(unittest.TestCase):
    def test_gone_or_unparsable_scope_is_drift_not_a_crash(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _, run = area_with_run(tmp)
            recorded = json.loads((run / "config.json").read_text())["promises"]
            (tmp / "scripts" / "m.py").write_text("def evaluate(:\n")
            drift = promises.scope_drift(recorded, tmp)
            self.assertIn("unreadable now", drift[0])
            (tmp / "scripts" / "m.py").unlink()
            self.assertIn("unreadable now", promises.scope_drift(recorded, tmp)[0])


class RecheckByIdentity(unittest.TestCase):
    def test_a_renamed_protocol_is_found_by_its_id(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            protocol, run = area_with_run(tmp)
            protocol.rename(tmp / "PROTOCOL-renamed.md")
            recheck.block_unchanged(run, tmp)  # no FileNotFoundError, no refusal

    def test_no_protocol_with_the_id_is_a_sentence(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            protocol, run = area_with_run(tmp)
            protocol.unlink()
            with self.assertRaises(SystemExit) as cm:
                recheck.block_unchanged(run, tmp)
            self.assertIn(f"carry id {PID}", str(cm.exception))


class PromiseBlockShape(unittest.TestCase):
    def test_a_non_table_entry_names_itself(self):
        with self.assertRaises(promises.PromiseError) as cm:
            promises.parse_block("```toml\npromise = [1]\n```\n")
        self.assertIn("[[promise]] #1", str(cm.exception))

    def test_digest_follows_the_promise_not_its_spelling(self):
        plain = C1.replace("constants = { min_acc = 0.7 }\n", "")
        a = promises.parse_block(head(promises=plain))
        b = promises.parse_block(head(promises=plain + "constants = {}\n"))
        assert a is not None and b is not None
        self.assertEqual(a.sha, b.sha)

    def test_a_run_from_the_earlier_digest_is_told_apart(self):
        block = promises.parse_block(head(promises=C1))
        old = {"block_sha": "0123abcd0123", "ids": {}}  # no "digest": labkit 0.46/0.47
        msg = promises.block_drift(old, block) or ""
        self.assertIn("labkit 0.46/0.47", msg)
        self.assertNotIn("promises changed", msg)


class NestedFences(unittest.TestCase):
    PROMPT = "\n- **Prompt:**\n\n  ````text\n  Answer as:\n  ```toml\n  x = 1\n  ```\n  ````\n"

    def test_a_toml_example_inside_a_prompt_is_no_second_head(self):
        text = head() + self.PROMPT
        self.assertEqual(protocol_block.head(text).id, PID)
        self.assertEqual(protocol_report.code_blocks(text), 1)

    def test_fields_inside_a_nested_fence_are_body(self):
        text = "````text\n```\n- **Unit:** inside\n```\n````\n"
        self.assertEqual(protocol_check.fields(text), [])


class ChoiceNeverPassesAnUnreadableRun(unittest.TestCase):
    def test_a_newer_run_with_broken_config_refuses_the_choice(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            protocol, run = area_with_run(tmp)
            broken = tmp / "runs" / "9999-12-31T00-00-00_zzzz"
            broken.mkdir()
            (broken / "config.json").write_text("{")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                rc = intent_check.main([str(protocol)])
            self.assertEqual(rc, 2, buf.getvalue())
            self.assertIn("cannot say which protocol", buf.getvalue())


class EnvFlags(unittest.TestCase):
    def test_zero_is_no_acknowledgement(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "PROTOCOL-x.md").write_text(head(repeat_cost="high") + "\n")
            os.environ["LABKIT_UNFROZEN"] = "0"
            try:
                with self.assertRaises(SystemExit):
                    with contextlib.redirect_stdout(io.StringIO()):
                        runlog.Run("t", {}, tmp, run_kind="measurement")
            finally:
                os.environ.pop("LABKIT_UNFROZEN", None)
            self.assertFalse((tmp / "runs").exists())


if __name__ == "__main__":
    unittest.main()
