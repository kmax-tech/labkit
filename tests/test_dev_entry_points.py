"""The editor's command list and the justfile's timeline example name modules
that are console commands: a module that lost its CLI in a split runs under
`python -m` without a word and exits 0."""

import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def command_modules() -> set[str]:
    with (ROOT / "pyproject.toml").open("rb") as f:
        scripts = tomllib.load(f)["project"]["scripts"]
    return {target.split(":")[0] for target in scripts.values()}


class DevEntryPoints(unittest.TestCase):
    def test_every_launch_option_is_a_command_module(self):
        text = (ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8")
        # VS Code reads JSON with comments; the file keeps them on lines of their own
        launch = json.loads(re.sub(r"(?m)^\s*//.*$", "", text))
        (pick,) = [i for i in launch["inputs"] if i["id"] == "command"]
        self.assertEqual(set(pick["options"]) - command_modules(), set())

    def test_the_timeline_example_names_a_command_module(self):
        text = (ROOT / "justfile").read_text(encoding="utf-8")
        examples = re.findall(r"just timeline ([a-z_.]+)", text)
        self.assertTrue(examples, "no `just timeline` example in the justfile")
        for module in examples:
            self.assertIn(f"labkit.{module}", command_modules())


if __name__ == "__main__":
    unittest.main()
