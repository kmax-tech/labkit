"""Values a stamped template repeats from another place stay equal to it.

Each pair below is a declared copy no reader would compare by hand: the
editor's search exclusions are "the same list as pyrightconfig.json's
exclude", and `models.toml` must define the alias `labkit-audit` calls by
default. Audit 2026-10-27 (second), D: neither was tied.

    .venv/bin/python -m pytest tests/test_template_ties.py
"""

from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

from labkit.gates import audit

TEMPLATES = Path(__file__).resolve().parents[1] / "labkit" / "templates"


def jsonc(name: str) -> dict:
    """The template NAME read as JSON with `//` comment lines dropped."""
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    return json.loads(re.sub(r"(?m)^\s*//.*$", "", text))


class TemplateTies(unittest.TestCase):
    def test_the_editor_excludes_what_pyright_excludes(self):
        pyright = set(jsonc("pyrightconfig.json.template")["exclude"])
        search = jsonc("vscode-settings.json.template")["search.exclude"]
        self.assertEqual({k for k, v in search.items() if v}, pyright)

    def test_the_guide_states_a_required_check_as_the_decision_list_does(self):
        """The work order of a finding's `check:` is one wording: the
        decision list and the follow-up's holds print `findings.check_order`,
        the agent guide states it (repair case, 2026-10-28: "its requested
        diagnostic run and assessed" left the check unwritten)."""
        from labkit.formats import findings

        guide = TEMPLATES.parent / "docs" / "agent-guide.md"
        agents = " ".join(guide.read_text(encoding="utf-8").split())
        self.assertIn(findings.check_order("<key>", "what it must show"), agents)

    def test_models_toml_defines_the_audit_default_alias(self):
        text = (TEMPLATES / "models.toml.template").read_text(encoding="utf-8")
        self.assertIn(audit.DEFAULT_MODEL, tomllib.loads(text)["models"])


if __name__ == "__main__":
    unittest.main()
