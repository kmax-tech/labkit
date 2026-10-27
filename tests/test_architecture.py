"""The architecture map in docs/architecture.md, held to the code.

The layer table is the one home of the map; this test reads it, so the doc
cannot drift from the imports unnoticed (review 2026-10-08: three new
modules were missing from it, and a gate imported a tool).
"""

import ast
import re
import tomllib
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


def folder_map() -> dict[str, str]:
    """Module → the package folder its row of the layer table names."""
    doc = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(r"^\| ((?:\d|tools)[^|]*)\| ([^|]+)\|", doc, re.M):
        folder = re.search(r"`labkit/(\w+)/`", m.group(1))
        if folder is None:
            raise AssertionError(f"layer row {m.group(1).strip()!r} names no folder")
        for name in re.findall(r"`(\w+)`", m.group(2)):
            out[name] = folder.group(1)
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
#: rule the core had copied (`cost == "low"`) becoming a visible import
#: of `standard_contract` is the same crossing made explicit, not a new one.
KNOWN_CROSSINGS = {
    # the freeze gate at a run's start: audit coverage (LAB-015), the low lane's
    # registration and which lane owes the freeze, the audit or the foreground
    # — doctrine that refuses a run, sitting in the run writer's start check
    # (moved with it out of runlog; the same crossings, not new ones)
    ("start_check", "findings"),  # findings.audit_coverage
    ("start_check", "protocol_check"),  # protocol_check.low_registration_missing
    # the same registration, as HEAD holds it, for a first measurement:
    # report-check holds that commit, and a start on an uncommitted one could
    # never be adopted (audit 2026-10-27, third, I1) — added deliberately, the
    # same doctrine as the line above; moving it would split protocol_history
    ("start_check", "protocol_history"),  # protocol_history.registration_in_commit
    ("start_check", "standard_contract"),  # standard_contract.lane
    ("runlog", "standard_contract"),  # standard_contract.lane (was a copied rule)
    # the field catalogue and a rule's text in the code check — the boundary
    # case: the TOML head is core, the prose fields are doctrine
    ("prompt_check", "protocol_check"),  # protocol_check.fields (moved from code_check)
    ("code_check", "rules"),  # rules.paragraph
    ("code_check", "standard_contract"),  # standard_contract.lane (was a copied rule)
    # the pin check is core; checking rule references and hooks is doctrine
    ("repo_check", "rules"),  # rules.check_refs, rules.load_ledger
    ("repo_check", "install_hooks"),  # install_hooks.check, .labkit_version
}


def module_paths() -> dict[str, Path]:
    """Module name → its file, in whichever layer package it sits."""
    return {f.stem: f for f in sorted(PACKAGE.rglob("*.py")) if f.stem != "__init__"}


def modules() -> list[str]:
    return sorted(module_paths())


def imports_of(module: str) -> set[str]:
    """The labkit modules a module imports, lazy imports inside functions
    included: `from labkit.run import runlog`, `from labkit.run.runlog import
    Run` and `import labkit.run.runlog` all name `runlog`."""
    known = set(modules())
    tree = ast.parse(module_paths()[module].read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            if n.module == "labkit" or n.module.startswith("labkit."):
                out.update(p for p in n.module.split(".")[1:] if p in known)
                out.update(a.name for a in n.names if a.name in known)
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("labkit."):
                    out.update(p for p in a.name.split(".")[1:] if p in known)
    return out


class Layers(unittest.TestCase):
    def test_every_module_stands_in_the_map(self):
        layers = layer_map()
        self.assertEqual([m for m in modules() if m not in layers], [])
        self.assertEqual([m for m in layers if m not in modules()], [])

    def test_every_module_sits_in_its_rows_folder(self):
        folders, paths = folder_map(), module_paths()
        astray = {
            m: f"labkit/{paths[m].parent.name}/, its row says labkit/{f}/"
            for m, f in folders.items()
            if m in paths and paths[m].parent.name != f
        }
        self.assertEqual(astray, {})

    def test_imports_point_downward(self):
        layers = layer_map()
        up = [
            f"{m} (layer {layers[m]}) imports {t} (layer {layers[t]})"
            for m in modules()
            for t in sorted(imports_of(m))
            if t in layers and layers[t] > layers[m]
        ]
        self.assertEqual(up, [])


class Packaging(unittest.TestCase):
    def test_every_package_ships(self):
        """pyproject names every folder holding an `__init__.py`: a package
        left out is missing from the wheel while the editable install of
        this repo still finds it."""
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        listed = set(data["tool"]["setuptools"]["packages"])
        on_disk = {
            ".".join(i.parent.relative_to(ROOT).parts)
            for i in PACKAGE.rglob("__init__.py")
        }
        self.assertEqual(listed, on_disk)


class CoreAndDoctrine(unittest.TestCase):
    """The core (which run made this number, from what) imports nothing of
    the doctrine (how a lab chooses to work): docs/architecture.md, "Core
    and doctrine"."""

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
            for n in ast.parse(module_paths()[m].read_text(encoding="utf-8")).body:
                if isinstance(
                    n, (ast.FunctionDef, ast.ClassDef)
                ) and not n.name.startswith("_"):
                    where[n.name].append(m)
        twice = {k: v for k, v in where.items() if len(v) > 1 and k not in ENTRY_POINTS}
        self.assertEqual(twice, {}, "one public name, one thing (CODE-015)")


if __name__ == "__main__":
    unittest.main()
