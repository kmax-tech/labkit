"""Every BLOCKER names its way out, as data (`gate.GateFinding.fix`), and so
does every refusal an agent meets outside the gates' findings — an
`AuditError` (labkit-audit, the reviews), an `AttemptError` (the attempt
journal) and runlog's start refusals: the ways past the gates came where an
agent saw no admissible next step, and a held step that named its command
was followed (docs/notes/2026-10-27-standard-way-out.md). Held twice:
`GateFinding` refuses a BLOCKER without a fix when it is built, and this
test reads every site in labkit/ that builds one or raises one of those
refusals — so a site no other test reaches is held too. What stays exempt
is listed with its reason. Whether a fix fits its cause is a reader's
judgement; this holds that there is one."""

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


#: the refusals that carry their way out as `fix=` (`AuditError`,
#: `AttemptError`: a required keyword, None only where exempt)
REFUSALS = ("AuditError", "AttemptError")
#: the modules whose start refusals are `SystemExit(with_way_out(…))`
START_REFUSALS = ("labkit/run/runlog.py", "labkit/run/start_check.py")
#: (module, function) → why a refusal there names no way out
EXEMPT = {
    ("labkit/formats/attempts.py", "keep_answer"): (
        "a second answer for one attempt is a call labkit's own code makes "
        "wrong, never a state an agent reaches"
    ),
    ("labkit/formats/attempts.py", "end"): (
        "an outcome outside OUTCOMES is a call labkit's own code makes wrong, "
        "never a state an agent reaches"
    ),
}


def _functions(tree: ast.AST) -> dict[ast.AST, str]:
    """Every node of TREE → the name of the function it stands in."""
    out: dict[ast.AST, str] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(fn):
                out.setdefault(node, fn.name)
    return out


def refusals_without_way_out(rel: str, tree: ast.AST) -> list[tuple[int, str]]:
    """(line, function) of every refusal in TREE (the module REL) that names
    no way out: an AuditError or AttemptError built without `fix=` or with
    None or "", and — in START_REFUSALS — a `SystemExit` of a sentence not
    joined with its way out (`gate.with_way_out`). An int exit code is no
    refusal."""
    where = _functions(tree)
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _name(node.func)
        if name in REFUSALS:
            fix = next((k.value for k in node.keywords if k.arg == "fix"), None)
            if fix is None or _empty(fix):
                out.append((node.lineno, where.get(node, "<module>")))
        elif name == "SystemExit" and rel in START_REFUSALS and node.args:
            arg = node.args[0]
            sentence = isinstance(arg, (ast.JoinedStr, ast.BinOp)) or (
                isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            )
            if sentence:
                out.append((node.lineno, where.get(node, "<module>")))
            elif isinstance(arg, ast.Call) and _name(arg.func) == "with_way_out":
                if len(arg.args) < 2 or _empty(arg.args[1]):
                    out.append((node.lineno, where.get(node, "<module>")))
    return out


class EveryRefusal(unittest.TestCase):
    def test_every_refusal_an_agent_meets_names_its_way_out(self):
        missing, exempted = [], set()
        for path in sorted((ROOT / "labkit").rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), rel)
            for n, fn in refusals_without_way_out(rel, tree):
                if (rel, fn) in EXEMPT:
                    exempted.add((rel, fn))
                else:
                    missing.append(f"{rel}:{n} ({fn})")
        self.assertEqual(missing, [], "a refusal without its way out")
        # an exemption that no longer matches a site is stale: drop it
        self.assertEqual(exempted, set(EXEMPT))

    def test_the_reader_finds_a_refusal_without_a_way_out(self):
        tree = ast.parse(
            "def f():\n"
            "    raise AuditError('x', fix=None)\n"
            "    raise AttemptError('x', fix='do y')\n"
            "    raise SystemExit(f'runlog: {x}')\n"
            "    raise SystemExit(with_way_out('runlog: x', 'do y'))\n"
            "    raise SystemExit(2)\n"
        )
        self.assertEqual(
            refusals_without_way_out("labkit/run/runlog.py", tree),
            [(2, "f"), (4, "f")],
        )

    def test_a_refusal_tells_its_way_out_and_keeps_its_parts(self):
        from labkit.checks.audit_binding import AuditError
        from labkit.formats.attempts import AttemptError

        for cls in (AuditError, AttemptError):
            exc = cls("x is gone", fix="restore x")
            self.assertEqual(str(exc), "x is gone — way out: restore x")
            self.assertEqual((exc.why, exc.fix), ("x is gone", "restore x"))
        self.assertEqual(gate.with_way_out("x", None), "x")


class TheHooks(unittest.TestCase):
    """The pre-run hook's notes name their step too; its block and the stop's
    tell the findings above, each with its fix, and the undecided way
    (`agent_hooks.UNDECIDED_WAY`) names `--findings`, `--decide` and the
    handover."""

    def test_a_run_outside_an_area_is_told_its_way_out(self):
        import tempfile

        from labkit.gates import agent_hooks

        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "01_measure.py"
            script.write_text("from labkit.run import runlog\n", encoding="utf-8")
            blocks, line = agent_hooks.before_run(script, Path(d))
        self.assertFalse(blocks)
        self.assertIn("no PROTOCOL-*.md above it", line)
        self.assertIn(f"{gate.WAY_OUT}stamp an area for it with `labkit-init exp", line)

    def test_the_undecided_way_names_the_commands(self):
        from labkit.gates import agent_hooks

        for step in ("--findings", "--decide", "--handover"):
            self.assertIn(step, agent_hooks.UNDECIDED_WAY)


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
