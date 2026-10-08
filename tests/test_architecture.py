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
        self.assertEqual(twice, {}, "one public name, one thing (CS-015)")


if __name__ == "__main__":
    unittest.main()
