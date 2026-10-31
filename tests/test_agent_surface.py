"""The stamped AGENTS.md: short, dated nowhere, every command a real one.

The prose did not carry (agent-surface plan, docs/notes/2026-10-30-agent-
surface.md): agents followed the gate messages at the point of use, not
4,774 words read once. AGENTS.md keeps the loop, six words, the kinds
table and the stop rule under WORD_LIMIT; the workflow in full is the
agent guide (`labkit-next --guide`). A date or an incident in either is
history for a note, not an instruction.
"""

from __future__ import annotations

import contextlib
import io
import re
import shlex
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labkit.gates import audit_decisions  # noqa: E402
from labkit.tools import next_step  # noqa: E402

AGENTS = ROOT / "labkit" / "templates" / "AGENTS.md.template"
GUIDE = ROOT / "labkit" / "docs" / "agent-guide.md"
WORD_LIMIT = 1200
DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


def words(text: str) -> int:
    """The words of TEXT: whitespace-separated tokens holding a letter or a
    digit (a table's `|` and `---` are none)."""
    return sum(1 for t in text.split() if re.search(r"[A-Za-z0-9]", t))


class Agents(unittest.TestCase):
    text = AGENTS.read_text(encoding="utf-8")

    def test_it_stays_under_the_word_limit(self):
        self.assertLessEqual(words(self.text), WORD_LIMIT)

    def test_the_count_reads_words_not_table_rules(self):
        self.assertEqual(words("| a | b |\n|---|---|\n`x --y` 0.5"), 5)

    def test_agent_facing_text_carries_no_date(self):
        for path in (AGENTS, GUIDE):
            with self.subTest(path.name):
                found = DATE.findall(path.read_text(encoding="utf-8"))
                self.assertEqual(found, [], f"{path.name}: history goes to a note")

    def test_the_date_reader_finds_a_date(self):
        self.assertEqual(DATE.findall("as of 2026-10-27, not v0.104.0"), ["2026-10-27"])

    def test_it_names_six_words(self):
        section = self.text[self.text.index("## Six words") :]
        section = section[: section.index("\n## ", 1)]
        rows = re.findall(r"^\| (\w+) \|", section, re.M)
        self.assertEqual(
            rows,
            ["Word", "protocol", "run", "criterion", "audit", "decision", "adoption"],
        )

    def test_every_labkit_command_it_names_is_installed(self):
        scripts = set(
            tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
                "project"
            ]["scripts"]
        )
        named = {
            span.split()[0].removeprefix(".venv/bin/")
            for span in re.findall(r"`([^`]+)`", self.text)
            if " " in span
        }
        ours = {
            c
            for c in named
            if c.startswith(("labkit-", "protocol-", "code-", "report-", "runlog"))
        }
        self.assertTrue({"labkit-next", "labkit-adopt", "labkit-audit"} <= ours)
        self.assertEqual(ours - scripts, set())

    def test_it_points_at_the_next_step_and_the_guide(self):
        self.assertIn("`labkit-next <area>`", self.text)
        self.assertIn("`labkit-next --guide`", self.text)


#: every text an agent reads that may show an example command or branch
AGENT_TEXTS = (
    AGENTS,
    GUIDE,
    ROOT / "labkit" / "docs" / "protocol-field-guide.md",
    ROOT / "labkit" / "templates" / "experiment-protocol.md.template",
)


def spans(text: str) -> list[str]:
    """The code spans and double-quoted spans of TEXT, whitespace collapsed."""
    flat = " ".join(text.split())
    return re.findall(r"`([^`]+)`", flat) + re.findall(r'"([^"]+)"', flat)


class Examples(unittest.TestCase):
    """An example an agent copies must be one labkit takes: a review ran a
    shown `--decide` call (refused, no `--why`) and a shown branch (refused,
    no consequences)."""

    def test_every_decide_call_shown_is_one_the_parser_takes(self):

        seen = 0
        for path in AGENT_TEXTS:
            for span in spans(path.read_text(encoding="utf-8")):
                if not span.startswith("labkit-audit") or "--decide" not in span:
                    continue
                seen += 1
                with self.subTest(path=path.name, span=span):
                    self.assertIsNone(audit_decisions.decide_shape(shlex.split(span)))
        self.assertGreater(seen, 0, "the reader finds the decide calls")

    def test_every_branch_example_shown_parses(self):
        from labkit.formats import promises

        seen = 0
        for path in AGENT_TEXTS:
            for span in spans(path.read_text(encoding="utf-8")):
                if "→" not in span or ";" not in span or "<outcome>" in span:
                    continue
                seen += 1
                example = promises.ID_PREFIX.sub("", span)
                with self.subTest(path=path.name, span=span):
                    self.assertGreaterEqual(len(promises.parse_outcomes(example)), 2)
        self.assertGreater(seen, 0, "the reader finds the branch examples")

    def test_the_reader_refuses_the_reviewed_faults(self):
        from labkit.formats import promises

        self.assertIsNotNone(
            audit_decisions.decide_shape(
                shlex.split('labkit-audit a --decide 1 fixed "x"')
            )
        )
        with self.assertRaises(promises.PromiseError):
            promises.parse_outcomes(
                "criterion-1 met → generalises; otherwise → no-verdict"
            )


class Guide(unittest.TestCase):
    def test_the_flag_prints_the_guide(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = next_step.main(["--guide"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), GUIDE.read_text(encoding="utf-8"))

    def test_no_area_and_no_guide_is_a_usage_error(self):
        with (
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as cm,
        ):
            next_step.main([])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
