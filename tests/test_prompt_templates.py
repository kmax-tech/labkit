"""Template files a pipeline loads (stagekit), registered in the protocol
and held to it exactly before the first model call.

The reader of named blocks and the exact comparison are tested from text
in memory; the writer (`protocol-fill --prompts --prompt-file`) and the
reader agree on every template (the round trip); the scenario at the end
walks the path of a two-stage area with a recording stand-in model: blocks
written from two template files, the check passing, every prompt filled
from the checked texts reaching the model — and, with one character of a
block changed, the start refused before any call. stagekit itself is not
imported: its part (which templates a run uses, its filling) is the
area's test's.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from string import Template

from command_fixture import run_main

from labkit import PACKAGE_DIR
from labkit.checks import prompt_check
from labkit.formats import protocol_check
from labkit.tools import protocol_fill, protocol_result

PROTOCOL = (PACKAGE_DIR / "templates" / "experiment-protocol.md.template").read_text(
    encoding="utf-8"
)

GENERATE = (
    "A claim is presented as being supported by a scientific study.\n"
    "\n"
    "Claim: $claim\n"
    "Finding of the study: $finding\n"
    "  - an indented line is the prompt's own\n"
    "List at most 2 objections, numbered.\n"
)
JUDGE = "Candidates:\n$candidates\n\nAnswer with the number that captures: $gap\n"


def field(*blocks: tuple[str, str]) -> str:
    """A Prompt field holding BLOCKS, (sentence name, body) each, written
    as a markdown list indents them."""
    out = ["- **Prompt (verbatim, per variant):** x", ""]
    for name_, body in blocks:
        out += [f"  `{name_}` — what it is for", "", "  ```text"]
        out += [f"  {ln}" if ln else "" for ln in body.split("\n")]
        out += ["  ```", ""]
    return "\n".join(out) + "\n"


class NamedBlocks(unittest.TestCase):
    def test_the_fence_indentation_is_removed_and_nothing_more(self) -> None:
        text = field(("generate", "a\n  b\n\nc"))
        self.assertEqual(
            protocol_check.named_prompt_blocks(text), {"generate": "a\n  b\n\nc"}
        )

    def test_a_line_left_of_its_fence_is_refused(self) -> None:
        text = "- **Prompt:** x\n\n  `g` — it\n\n  ```text\n  a\nb\n  ```\n"
        with self.assertRaisesRegex(ValueError, "stands left of its fence"):
            protocol_check.named_prompt_blocks(text)

    def test_two_blocks_of_one_name_are_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "two Prompt blocks are named `g`"):
            protocol_check.named_prompt_blocks(field(("g", "a"), ("g", "b")))

    def test_an_unnamed_block_is_left_out(self) -> None:
        text = "- **Prompt:** x\n\n  ```text\n  a\n  ```\n"
        self.assertEqual(protocol_check.named_prompt_blocks(text), {})


class TemplateDrift(unittest.TestCase):
    BLOCKS = {"judge": "Q: $q\nAnswer: $a"}

    def drift(self, text: str, name: str = "judge") -> list[str]:
        return protocol_check.template_drift({name: text}, self.BLOCKS)

    def test_the_registered_text_passes_with_crlf_and_a_final_line_ending(self) -> None:
        self.assertEqual(self.drift("Q: $q\nAnswer: $a"), [])
        self.assertEqual(self.drift("Q: $q\r\nAnswer: $a\r\n"), [])

    def test_a_changed_placeholder_line_is_caught(self) -> None:
        """What the line-wise comparison of constants never compares."""
        (told,) = self.drift("Question: $q\nAnswer: $a")
        self.assertIn("judge: line 1 differs", told)

    def test_order_trailing_space_and_leading_space_count(self) -> None:
        for text in ("Answer: $a\nQ: $q", "Q: $q \nAnswer: $a", " Q: $q\nAnswer: $a"):
            with self.subTest(text=text):
                self.assertEqual(len(self.drift(text)), 1)

    def test_a_line_more_or_less_is_caught(self) -> None:
        self.assertIn("(no line)", self.drift("Q: $q")[0])
        self.assertIn("(no line)", self.drift("Q: $q\nAnswer: $a\nmore")[0])

    def test_a_template_without_a_block_of_its_name_is_not_covered(self) -> None:
        (told,) = self.drift("Q: $q\nAnswer: $a", name="judge_strict")
        self.assertIn("judge_strict: not covered", told)


class WriterAndReaderAgree(unittest.TestCase):
    def test_every_template_reads_back_as_written(self) -> None:
        templates = {"generate_context": GENERATE, "judge": JUDGE}
        text = protocol_result.fill_prompts(PROTOCOL, {}, templates)
        blocks = protocol_check.named_prompt_blocks(text)
        self.assertEqual(protocol_check.template_drift(templates, blocks), [])
        # the sentence names the template and its `$` placeholders
        self.assertIn(
            "`generate_context` — <what it is for; `$claim`: how it is filled; "
            "`$finding`: how it is filled>",
            text,
        )

    def test_a_name_both_constant_and_template_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "named both"):
            protocol_result.fill_prompts(PROTOCOL, {"PROMPT": "x"}, {"PROMPT": "y"})


class Scenario(unittest.TestCase):
    """A two-stage area: generate, then judge from the generated answers."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name)
        (self.area / "prompts").mkdir()
        # the file names differ from the names the pipeline registers
        (self.area / "prompts" / "gen.txt").write_text(GENERATE, encoding="utf-8")
        (self.area / "prompts" / "jud.txt").write_text(JUDGE, encoding="utf-8")
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(PROTOCOL, encoding="utf-8")
        self.sent: list[str] = []

    def fill(self) -> None:
        rc, out = run_main(
            protocol_fill.main,
            [
                str(self.protocol),
                "--prompts",
                "--prompt-file",
                f"generate_context={self.area / 'prompts' / 'gen.txt'}",
                "--prompt-file",
                f"judge={self.area / 'prompts' / 'jud.txt'}",
            ],
        )
        self.assertEqual(rc, 0, out)

    def templates(self) -> dict[str, str]:
        """What the pipeline's registry holds, read once — as stagekit's
        `register_prompt_dir` reads each file at registration."""
        return {
            "generate_context": (self.area / "prompts" / "gen.txt").read_text(),
            "judge": (self.area / "prompts" / "jud.txt").read_text(),
        }

    def model(self, prompt: str) -> str:
        """The stand-in: records the prompt it is handed, answers fixed."""
        self.sent.append(prompt)
        return "1. too small\n2. no control" if prompt.startswith("A claim") else "1"

    ITEM = {"claim": "Coffee cures colds", "finding": "fewer colds", "gap": "sample"}

    def run_area(self) -> None:
        """The area's start: every template the run uses checked first, then
        the two stages, each prompt filled from the checked texts."""
        templates = self.templates()
        prompt_check.require_registered_templates(self.protocol, templates)
        answer = self.model(
            Template(templates["generate_context"]).substitute(self.ITEM)
        )
        self.model(
            Template(templates["judge"]).substitute(self.ITEM, candidates=answer)
        )

    def test_every_prompt_sent_is_its_registered_block_filled(self) -> None:
        self.fill()
        self.run_area()
        blocks = protocol_check.named_prompt_blocks(self.protocol.read_text())
        expected = [
            Template(blocks["generate_context"]).substitute(self.ITEM),
            Template(blocks["judge"]).substitute(
                self.ITEM, candidates="1. too small\n2. no control"
            ),
        ]
        # a block cannot show the template's final line ending, so the sent
        # prompt is compared without it (`protocol_check.as_compared`)
        self.assertEqual([protocol_check.as_compared(p) for p in self.sent], expected)

    def test_a_changed_block_refuses_the_start_before_any_call(self) -> None:
        self.fill()
        text = self.protocol.read_text()
        self.protocol.write_text(text.replace("Candidates:", "Candidate:"))
        with self.assertRaises(SystemExit) as cm:
            self.run_area()
        told = str(cm.exception.code)
        self.assertIn("judge: line 1 differs", told)
        self.assertIn("refused before any model call", told)
        self.assertEqual(self.sent, [])

    def test_a_template_the_protocol_does_not_register_refuses_the_start(self) -> None:
        self.fill()
        templates = {**self.templates(), "generate_no_context": "Claim: $claim\n"}
        with self.assertRaises(SystemExit) as cm:
            prompt_check.require_registered_templates(self.protocol, templates)
        self.assertIn("generate_no_context: not covered", str(cm.exception.code))

    def test_prompt_file_without_prompts_is_a_usage_error(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            run_main(
                protocol_fill.main,
                [str(self.protocol), "--prompt-file", "g=prompts/gen.txt"],
            )
        self.assertEqual(cm.exception.code, 2)

    def test_a_prompt_file_without_a_name_is_refused(self) -> None:
        rc, out = run_main(
            protocol_fill.main,
            [str(self.protocol), "--prompts", "--prompt-file", "prompts/gen.txt"],
        )
        self.assertEqual(rc, 2)
        self.assertIn("expected NAME=PATH", out)


if __name__ == "__main__":
    unittest.main()
