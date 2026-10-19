"""One home per question — held by grep, not by memory.

`docs/architecture.md` names the home of every recurring question and says
a second answer is drift. Three audits (2026-10-06, 2026-10-13,
2026-10-15) removed the same kinds of copies — a hand-spelled sha256, a
`git` run outside `repo`, a `PROTOCOL-*.md` scan, the id letters, a fence
regex — and they came back within two weeks each time. This test greps
`labkit/*.py` for the shapes a copy takes; a match outside the home fails,
naming file and line. A line that must stay says why with a `# home:`
comment naming the home it is not.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "labkit"
#: rules that also hold in the stamped script templates — a stamped area reads
#: its tier off the contract like labkit does (review 2026-10-19)
IN_TEMPLATES = {"a tier rule read off the head"}

#: (what, the shape of a copy, the module(s) where it belongs)
RULES: list[tuple[str, str, set[str]]] = [
    ("sha256 by hand", r"hashlib\.", {"scope_sha"}),
    (
        "git outside repo.git_run",
        r"subprocess\.\w+\(\s*\[\s*\"git\"",
        {"repo"},
    ),
    ("a PROTOCOL-*.md scan", r"r?glob\(\s*\"PROTOCOL-", {"repo"}),
    ("pip's name normalisation", r"\.lower\(\)\.replace\(\"_\", \"-\"\)", {"repo"}),
    ("a fence regex", r"re\.compile\([^\n]*(`\{3|```|~\{3)", {"protocol_block"}),
    ("a fence toggled by hand", r"startswith\(\(?\"(```|~~~)", {"protocol_block"}),
    ("the id letters", r"\[(?:[cab]{2,3}|[CAB]{2,3})\]|\^a\\d", {"promises"}),
    ("the area name NN-slug", r"\^\(\\d\+\)-", {"repo"}),
    ("a temp-and-rename write", r"os\.replace\(", {"runs"}),
    ("the run-id shape", r"\\d\{4\}-\\d\{2\}-\\d\{2\}T", {"runs"}),
    (
        "a run id's start second compared by hand",
        r"start_second\(|rsplit\(\"_\", 1\)",
        {"runs"},
    ),
    (
        "a requirements pin spelled by hand",
        r"startswith\(\"labkit\"\)|\^\\s\*labkit",
        {"repo"},
    ),
    # what a tier owes is read off `standard_contract.lane`, never off the
    # head's word: seven modules compared it by hand and the gate and the
    # skeleton disagreed (audit 2026-10-19)
    ("a tier rule read off the head", r"[=!]=\s*\{?\"seconds\"", {"standard_contract"}),
]


def offenders(what: str, shape: str, homes: set[str]) -> list[str]:
    out = []
    pattern = re.compile(shape)
    paths = sorted(PACKAGE.rglob("*.py"))
    if what in IN_TEMPLATES:
        paths += sorted((PACKAGE / "templates").glob("*.py.template"))
    for path in paths:
        if path.stem in homes:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines, 1):
            said = "# home:" in line or (n > 1 and "# home:" in lines[n - 2])
            if pattern.search(line) and not said:
                out.append(f"{path.name}:{n}: {what} — {line.strip()[:80]}")
    return out


class OneHome(unittest.TestCase):
    def test_no_copy_outside_its_home(self):
        found = [o for rule in RULES for o in offenders(*rule)]
        self.assertEqual(found, [], "\n" + "\n".join(found))

    def test_the_rules_bite(self):
        """Each shape matches what it is written for (a rule that matches
        nothing guards nothing)."""
        samples = {
            "sha256 by hand": "h = hashlib.sha256(data).hexdigest()",
            "git outside repo.git_run": 'subprocess.run(["git", "status"])',
            "a PROTOCOL-*.md scan": 'for f in root.rglob("PROTOCOL-*.md"):',
            "pip's name normalisation": 'name.lower().replace("_", "-")',
            "a fence regex": 'FENCE = re.compile(r"^\\s*```")',
            "a fence toggled by hand": 'if line.strip().startswith("```"):',
            "the id letters": 'KEY = re.compile(r"([ca])\\d+_pass")',
            "the area name NN-slug": 'm = re.match(r"^(\\d+)-(.+)$", name)',
            "a temp-and-rename write": "os.replace(tmp, path)",
            "the run-id shape": 'RUN = re.compile(r"\\d{4}-\\d{2}-\\d{2}T")',
            "a run id's start second compared by hand": "if runs.start_second(a) == runs.start_second(b):",
            "a requirements pin spelled by hand": 'if ln.startswith("labkit"):',
            "a tier rule read off the head": 'if head.cost == "seconds":',
        }
        for what, shape, _ in RULES:
            with self.subTest(what=what):
                self.assertIsNotNone(re.compile(shape).search(samples[what]), shape)


if __name__ == "__main__":
    unittest.main()
