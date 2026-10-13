"""The README's command list, held to the code.

Every console script of pyproject.toml and every sub-command of the two
multi-command tools stands in the README's command block; a count written
in prose ("Sixteen") drifted the day the seventeenth command came
(audit 2026-10-13), so the list is held here and the prose carries no number.
"""

import contextlib
import io
import re
import tomllib
import unittest
from pathlib import Path

from labkit import runlog, usability

ROOT = Path(__file__).resolve().parents[1]


def command_block() -> str:
    """The bash block that follows the 'console commands' sentence."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    after = readme[readme.index("**console commands**") :]
    return after.split("```bash\n", 1)[1].split("```", 1)[0]


def usability_subcommands() -> set[str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
        usability.main(["--help"])
    m = re.search(r"\{([a-z,-]+)\}", out.getvalue())
    assert m, out.getvalue()
    return set(m.group(1).split(","))


class ReadmeCommands(unittest.TestCase):
    def test_every_console_script_is_listed(self):
        scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]["scripts"]
        block = command_block()
        for name in scripts:
            with self.subTest(name):
                self.assertRegex(
                    block,
                    rf"(?m)^{re.escape(name)}\b",
                    msg=f"{name} missing from the README block",
                )

    def test_every_subcommand_is_listed(self):
        block = command_block()
        for sub in usability_subcommands():
            with self.subTest(f"usability {sub}"):
                self.assertRegex(block, rf"(?m)^usability [a-z|-]*\b{re.escape(sub)}\b")
        for sub in ("start", "reindex"):
            with self.subTest(f"runlog {sub}"):
                self.assertIn(f"runlog {sub}", block)
        self.assertTrue(hasattr(runlog, "reindex"))

    def test_the_prose_carries_no_count(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        before = readme[: readme.index("**console commands**")]
        sentence = before[before.rfind("\n\n") :]  # the paragraph that opens the list
        self.assertNotRegex(sentence, r"(?i)\b(sixteen|seventeen|eighteen|\d+)\b")


if __name__ == "__main__":
    unittest.main()
