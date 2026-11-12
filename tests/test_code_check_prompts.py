"""The prompt drift check reads prompts as the stamped skeleton builds
them and every block under the Prompt field, so it runs on a stamped area
and finds a null prompt in a second block."""

import tempfile
import unittest
from pathlib import Path

from labkit.checks import prompt_check
from labkit.formats import protocol_check

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
        return [f.line for f in prompt_check.check_prompt_drift(area, protocol)]


class Readable(unittest.TestCase):
    def test_the_skeleton_shape_is_computed(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "scripts").mkdir()
            (Path(d) / "scripts" / "m.py").write_text(SCRIPT)
            consts = prompt_check.prompt_constants(Path(d))
        self.assertEqual(
            consts["PROMPT"],
            "Causal?\n\nText: {text}\n\nAnswer with a single word, Yes or No.",
        )

    def test_an_uncomputable_prompt_is_said_not_passed(self):
        (f,) = check("PROMPT = build_prompt()\n", TWO_BLOCKS)
        self.assertTrue(f.startswith("WARNING"), f)
        self.assertIn("drift unchecked", f)
        # the drift check did not run for it; nothing is shown to be breached
        self.assertIn("check not executable", f)


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
        self.assertEqual(len(protocol_check.prompt_blocks(_write(moved))), 2)

    def test_a_tilde_fence_and_a_wrapped_label_are_read(self):
        """`~~~` fences and a label wrapped onto the next line are read: the
        prompt check reads the protocol parser's fences and labels."""
        tilde = TWO_BLOCKS.replace("```text", "~~~text").replace("  ```", "  ~~~")
        self.assertEqual(len(protocol_check.prompt_blocks(_write(tilde))), 2)
        wrapped = TWO_BLOCKS.replace(
            "- **Prompt (verbatim, per variant):**",
            "- **Prompt (verbatim,\n  per variant):**",
        )
        self.assertEqual(len(protocol_check.prompt_blocks(_write(wrapped))), 2)

    def test_an_empty_fence_is_reported_not_a_crash(self):
        # a stamped protocol whose prompt fence is left empty: the first line
        # of "" does not exist
        empty = "- **Prompt:**\n\n  ```text\n  ```\n\n- **Unit:** x\n"
        findings = check(SCRIPT, empty)
        self.assertEqual(len(findings), 2, findings)  # PROMPT and PROMPT_NULL
        for f in findings:
            self.assertTrue(f.startswith("BLOCKER"), f)


TAGGED_SCRIPT = (
    'PROMPT = "<instructions>\\nAnswer Yes or No.\\n</instructions>\\n{text}"\n'
)
TAGGED_BLOCK = """- **Prompt (verbatim, per variant):**

  ```text
  <instructions>
  Answer Yes or No.
  </instructions>
  {text}
  ```

- **Unit:** one item
"""


class TaggedPrompts(unittest.TestCase):
    """A prompt that opens and closes with a tag is a prompt: only the
    stamp's own placeholder fence is no registration, so drift in a tagged
    prompt is seen."""

    def test_a_drifted_tagged_prompt_blocks(self):
        (f,) = check(
            TAGGED_SCRIPT.replace("Yes or No", "yes, no or maybe"), TAGGED_BLOCK
        )
        self.assertTrue(f.startswith("BLOCKER"), f)
        self.assertIn("PROMPT", f)

    def test_the_matching_tagged_prompt_passes(self):
        self.assertEqual(check(TAGGED_SCRIPT, TAGGED_BLOCK), [])

    def test_the_stamp_placeholder_is_no_registration(self):
        (stamped,) = protocol_check.stamp_block_placeholders()
        protocol = TAGGED_BLOCK.replace(
            "<instructions>\n  Answer Yes or No.\n  </instructions>\n  {text}",
            stamped,
        )
        self.assertEqual(check(TAGGED_SCRIPT, protocol), [])

    def test_the_stamp_placeholder_beside_a_drifted_prompt_still_blocks(self):
        (stamped,) = protocol_check.stamp_block_placeholders()
        protocol = TAGGED_BLOCK.replace(
            "  ```text\n", f"  ```text\n  {stamped}\n  ```\n\n  ```text\n", 1
        )
        self.assertEqual(len(protocol_check.prompt_blocks(_write(protocol))), 2)
        (f,) = check(TAGGED_SCRIPT.replace("Yes or No", "yes, no or maybe"), protocol)
        self.assertTrue(f.startswith("BLOCKER"), f)


def _write(text: str) -> Path:
    path = Path(tempfile.mkdtemp()) / "PROTOCOL-x.md"
    path.write_text(text)
    return path


if __name__ == "__main__":
    unittest.main()
