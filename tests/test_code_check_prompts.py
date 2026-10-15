"""The prompt drift check reads prompts as the stamped skeleton builds
them and every block under the Prompt field (re-measure 2026-10-07: it read
literals only, so it never ran on a stamped area; once it ran it read only
the first block and called a null prompt in a second block missing)."""

import tempfile
import unittest
from pathlib import Path

from labkit import code_check

SCRIPT = (
    'ANSWERS = {"Yes": "causal", "No": "not_causal"}\n'
    "ANSWER_LINE = f\"Answer with a single word, {' or '.join(ANSWERS)}.\"\n"
    'PROMPT = "Causal?\\n\\nText: {text}\\n\\n" + ANSWER_LINE\n'
    'PROMPT_NULL = "English?\\n\\nText: {text}\\n\\n" + ANSWER_LINE\n'
)
TWO_BLOCKS = """- **Prompt (verbatim, per variant):**

  ```text
  Causal?

  Text: {text}

  Answer with a single word, Yes or No.
  ```

  Null lane:

  ```text
  English?

  Text: {text}

  Answer with a single word, Yes or No.
  ```

- **Null condition / anchors (in the same run):** placebo
"""


def check(script: str, protocol_text: str) -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        area = Path(d)
        (area / "scripts").mkdir()
        (area / "scripts" / "01_measure.py").write_text(script)
        protocol = area / "PROTOCOL-x.md"
        protocol.write_text(protocol_text)
        return code_check.check_prompt_drift(area, protocol)


class Readable(unittest.TestCase):
    def test_the_skeleton_shape_is_computed(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "scripts").mkdir()
            (Path(d) / "scripts" / "m.py").write_text(SCRIPT)
            consts = code_check.prompt_constants(Path(d))
        self.assertEqual(
            consts["PROMPT"],
            "Causal?\n\nText: {text}\n\nAnswer with a single word, Yes or No.",
        )

    def test_an_uncomputable_prompt_is_said_not_passed(self):
        (f,) = check("PROMPT = build_prompt()\n", TWO_BLOCKS)
        self.assertTrue(f.startswith("WARNING"), f)
        self.assertIn("drift unchecked", f)


class Blocks(unittest.TestCase):
    def test_one_block_per_variant_holds(self):
        self.assertEqual(check(SCRIPT, TWO_BLOCKS), [])

    def test_a_changed_null_prompt_blocks(self):
        (f,) = check(SCRIPT, TWO_BLOCKS.replace("  English?", "  French?"))
        self.assertTrue(f.startswith("BLOCKER"), f)
        self.assertIn("PROMPT_NULL", f)

    def test_a_block_under_the_next_field_is_not_the_prompt(self):
        moved = TWO_BLOCKS.replace(
            "- **Null condition / anchors (in the same run):** placebo\n",
            "- **Null condition / anchors (in the same run):** placebo\n\n"
            "  ```text\n  Unrelated\n  ```\n",
        )
        self.assertEqual(len(code_check.prompt_blocks(_write(moved))), 2)

    def test_a_tilde_fence_and_a_wrapped_label_are_read(self):
        """`~~~` fences and a label wrapped onto the next line were invisible
        to the prompt check's own parsers (audit 2026-10-15); the protocol
        parser's fences and labels are read here."""
        tilde = TWO_BLOCKS.replace("```text", "~~~text").replace("  ```", "  ~~~")
        self.assertEqual(len(code_check.prompt_blocks(_write(tilde))), 2)
        wrapped = TWO_BLOCKS.replace(
            "- **Prompt (verbatim, per variant):**",
            "- **Prompt (verbatim,\n  per variant):**",
        )
        self.assertEqual(len(code_check.prompt_blocks(_write(wrapped))), 2)

    def test_an_empty_fence_is_reported_not_a_crash(self):
        # a stamped protocol whose prompt fence was left empty raised
        # IndexError (audit 2026-10-13): the first line of "" does not exist
        empty = "- **Prompt:**\n\n  ```text\n  ```\n\n- **Unit:** x\n"
        findings = check(SCRIPT, empty)
        self.assertEqual(len(findings), 2, findings)  # PROMPT and PROMPT_NULL
        for f in findings:
            self.assertTrue(f.startswith("BLOCKER"), f)


def _write(text: str) -> Path:
    path = Path(tempfile.mkdtemp()) / "PROTOCOL-x.md"
    path.write_text(text)
    return path


if __name__ == "__main__":
    unittest.main()
