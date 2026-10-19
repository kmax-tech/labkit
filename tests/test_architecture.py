"""The architecture map in docs/architecture.md, held to the code.

The layer table is the one home of the map; this test reads it, so the doc
cannot drift from the imports unnoticed (review 2026-10-08: three new
modules were missing from it, and a gate imported a tool).
"""

import ast
import re
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "labkit"
TOOLS = 5  # tools stand above every layer
#: public names every command module carries by convention
ENTRY_POINTS = {"main", "cli"}


def layer_map() -> dict[str, int]:
    """Module → layer, read from the doc's layer table."""
    doc = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    out: dict[str, int] = {}
    for m in re.finditer(r"^\| (\d|tools)[^|]*\| ([^|]+)\|", doc, re.M):
        level = TOOLS if m.group(1) == "tools" else int(m.group(1))
        for name in re.findall(r"`(\w+)`", m.group(2)):
            if name in out:
                raise AssertionError(f"{name} stands twice in the layer table")
            out[name] = level
    return out


def doctrine_modules() -> set[str]:
    """The modules the layer table marks doctrine; every other module is core."""
    doc = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    out: set[str] = set()
    for m in re.finditer(r"^\| (?:\d|tools)[^|]*\| ([^|]+)\| ([^|]+)\|", doc, re.M):
        listed = set(re.findall(r"`(\w+)`", m.group(1)))
        marked = set(re.findall(r"`(\w+)`", m.group(2)))
        if not marked <= listed:
            raise AssertionError(f"doctrine marks {marked - listed} not in its row")
        out |= marked
    return out


#: core → doctrine imports that stand today, each a piece of doctrine inside
#: the core, listed by name until it moves (2026-10-15). The test asks for
#: exactly this set: a new crossing fails, and so does a removed one left
#: standing here — the list only shrinks, with one kind of exception: a
#: rule the core had copied (`cost == "seconds"`) becoming a visible import
#: of `standard_contract` is the same crossing made explicit, not a new one.
KNOWN_CROSSINGS = {
    # the freeze gate inside runlog: audit coverage (LAB-015), the seconds
    # registration and which lane owes the freeze, the audit or the foreground
    # — doctrine that refuses a run, sitting in the run writer
    ("runlog", "findings"),  # findings.audit_coverage
    ("runlog", "protocol_check"),  # protocol_check.seconds_registration_missing
    ("runlog", "standard_contract"),  # standard_contract.lane (was a copied rule)
    # the field catalogue and a rule's text in the code check — the boundary
    # case: the TOML head is core, the prose fields are doctrine
    ("code_check", "protocol_check"),  # protocol_check.fields
    ("code_check", "rules"),  # rules.paragraph
    ("code_check", "standard_contract"),  # standard_contract.lane (was a copied rule)
    # the pin check is core; checking rule references and hooks is doctrine
    ("repo_check", "rules"),  # rules.check_refs, rules.load_registry
    ("repo_check", "install_hooks"),  # install_hooks.check, .labkit_version
}


def modules() -> list[str]:
    return sorted(f.stem for f in PACKAGE.glob("*.py") if f.stem != "__init__")


def imports_of(module: str) -> set[str]:
    """The labkit modules a module imports, lazy imports inside functions included."""
    tree = ast.parse((PACKAGE / f"{module}.py").read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            if n.module == "labkit":
                out.update(a.name for a in n.names)
            elif n.module.startswith("labkit."):
                out.add(n.module.split(".")[1])
        elif isinstance(n, ast.Import):
            out.update(
                a.name.split(".")[1] for a in n.names if a.name.startswith("labkit.")
            )
    return out


class Layers(unittest.TestCase):
    def test_every_module_stands_in_the_map(self):
        layers = layer_map()
        self.assertEqual([m for m in modules() if m not in layers], [])
        self.assertEqual([m for m in layers if m not in modules()], [])

    def test_imports_point_downward(self):
        layers = layer_map()
        up = [
            f"{m} (layer {layers[m]}) imports {t} (layer {layers[t]})"
            for m in modules()
            for t in sorted(imports_of(m))
            if t in layers and layers[t] > layers[m]
        ]
        self.assertEqual(up, [])


class CoreAndDoctrine(unittest.TestCase):
    """The core (which run made this number, from what) imports nothing of
    the doctrine (how a lab chooses to work): docs/architecture.md, "Core
    or doctrine"."""

    def test_the_doctrine_column_marks_known_modules(self):
        self.assertLessEqual(doctrine_modules(), set(modules()))

    def test_a_core_module_imports_no_doctrine_module(self):
        doctrine = doctrine_modules()
        crossings = {
            (m, t)
            for m in modules()
            if m not in doctrine
            for t in imports_of(m)
            if t in doctrine
        }
        self.assertEqual(crossings, KNOWN_CROSSINGS)


class OneNameOneThing(unittest.TestCase):
    def test_no_public_name_in_two_modules(self):
        where: dict[str, list[str]] = defaultdict(list)
        for m in modules():
            for n in ast.parse((PACKAGE / f"{m}.py").read_text(encoding="utf-8")).body:
                if isinstance(
                    n, (ast.FunctionDef, ast.ClassDef)
                ) and not n.name.startswith("_"):
                    where[n.name].append(m)
        twice = {k: v for k, v in where.items() if len(v) > 1 and k not in ENTRY_POINTS}
        self.assertEqual(twice, {}, "one public name, one thing (CODE-015)")


if __name__ == "__main__":
    unittest.main()
