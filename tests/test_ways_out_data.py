"""Every BLOCKER names its way out, as data (`gate.GateFinding.fix`): the
ways past the gates came where an agent saw no admissible next step, and a
held step that named its command was followed
(docs/notes/2026-10-27-standard-way-out.md). Held twice: `GateFinding`
refuses a BLOCKER without a fix when it is built, and this test reads every
site in labkit/ that builds one — so a site no other test reaches is held
too. Whether a fix fits its cause is a reader's judgement; this holds that
there is one."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labkit.formats import gate  # noqa: E402

#: the calls that build a gate finding: (name, index of the grade argument,
#: or None when the call is a blocker by itself)
BUILDERS = {"GateFinding": 0, "coded": 0, "blocker": None, "block": None}


def _name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_warning(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "WARNING"


def _empty(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value in (None, "")


def blocker_sites_without_fix(tree: ast.AST) -> list[int]:
    """The lines of TREE that build a finding that may be a BLOCKER (its grade
    not the name WARNING) without a `fix=` keyword, or with an empty one."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _name(node.func)
        if name not in BUILDERS:
            continue
        if name == "block" and not (isinstance(node.func, ast.Attribute) and node.args):
            continue
        grade_at = BUILDERS[name]
        if grade_at is not None:
            grade = node.args[grade_at] if len(node.args) > grade_at else None
            if grade is None or _is_warning(grade):
                continue
        fix = next((k.value for k in node.keywords if k.arg == "fix"), None)
        if fix is None or _empty(fix):
            lines.append(node.lineno)
    return lines


class EverySite(unittest.TestCase):
    def test_every_blocker_site_in_labkit_passes_a_fix(self):
        missing = []
        for path in sorted((ROOT / "labkit").rglob("*.py")):
            if path.name == "gate.py" and path.parent.name == "formats":
                continue  # the builders themselves pass their caller's fix on
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
            missing += [
                f"{path.relative_to(ROOT)}:{n}" for n in blocker_sites_without_fix(tree)
            ]
        self.assertEqual(missing, [], "a BLOCKER built without its way out")

    def test_the_reader_finds_a_site_without_a_fix(self):
        """The negative is a claim: the reader sees the cases it must."""
        tree = ast.parse(
            "GateFinding(BLOCKER, 'x', evidence_kind=GUARANTEED)\n"
            "coded(BLOCKER, None, 'x', evidence_kind=GUARANTEED, fix=None)\n"
            "findings.block('x', fix='')\n"
            "GateFinding(grade, 'x', evidence_kind=GUARANTEED)\n"
            "GateFinding(WARNING, 'x', evidence_kind=GUARANTEED)\n"
            "blocker('x', fix='do y')\n"
        )
        self.assertEqual(blocker_sites_without_fix(tree), [1, 2, 3, 4])


class TheFinding(unittest.TestCase):
    def test_a_blocker_without_a_fix_is_refused_and_a_warning_is_not(self):
        for fix in (None, "", "  "):
            with self.assertRaisesRegex(ValueError, "names its way out"):
                gate.GateFinding(
                    gate.BLOCKER, "x", fix=fix, evidence_kind=gate.GUARANTEED
                )
        warning = gate.GateFinding(gate.WARNING, "x", evidence_kind=gate.GUARANTEED)
        self.assertEqual(warning.line, "WARNING: x")

    def test_every_form_tells_the_fix(self):
        fix = "run `y`"
        for form, line in (
            (gate.PREFIXED, "BLOCKER: x — way out: run `y`"),
            (gate.AS_WRITTEN, "x — way out: run `y`"),
            (gate.DOTTED, "BLOCKER · a.py:1 · x · run `y`"),
        ):
            f = gate.GateFinding(
                gate.BLOCKER,
                "x",
                form,
                where="a.py:1" if form == gate.DOTTED else None,
                fix=fix,
                evidence_kind=gate.GUARANTEED,
            )
            self.assertEqual(f.line, line)
            self.assertIn(fix, f.message)

    def test_the_summary_repeats_the_fix_and_the_area_slot_is_filled(self):
        told: list[str] = []
        out = gate.Findings(told.append, area="experiments/01-x")
        out.block("x", fix=f"run `labkit-audit {gate.AREA_SLOT} --findings`")
        out.report("tool", "reporting")
        want = "x — way out: run `labkit-audit experiments/01-x --findings`"
        self.assertIn(f"  BLOCKER: {want}", told)
        self.assertIn(f"  - {want}", told)


if __name__ == "__main__":
    unittest.main()
