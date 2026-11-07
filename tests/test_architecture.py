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


#: the doctrine cell of a row whose every module is doctrine (gates, probes)
WHOLE_ROW = "all"


def doctrine_marks(modules_cell: str, doctrine_cell: str) -> set[str]:
    """The modules one row of the layer table marks doctrine: every module of
    MODULES_CELL when DOCTRINE_CELL is `WHOLE_ROW`, else the modules
    DOCTRINE_CELL names, each one its row lists."""
    listed = set(re.findall(r"`(\w+)`", modules_cell))
    if doctrine_cell.strip() == WHOLE_ROW:
        return listed
    marked = set(re.findall(r"`(\w+)`", doctrine_cell))
    if not marked <= listed:
        raise AssertionError(f"doctrine marks {marked - listed} not in its row")
    return marked


def doctrine_modules() -> set[str]:
    """The modules the layer table marks doctrine; every other module is core."""
    doc = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    out: set[str] = set()
    for m in re.finditer(r"^\| (?:\d|tools)[^|]*\| ([^|]+)\| ([^|]+)\|", doc, re.M):
        out |= doctrine_marks(m.group(1), m.group(2))
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
    ("start_check", "findings"),  # findings.open_findings, findings.area_records
    ("start_check", "audit_gaps"),  # audit_gaps.audit_record_gap
    ("start_check", "failed_attempts"),  # failed_attempts.audit_unavailable
    ("start_check", "protocol_check"),  # protocol_check.low_registration_missing
    # the same registration, as HEAD holds it, for a first measurement:
    # report-check holds that commit, and a start on an uncommitted one could
    # never be adopted (audit 2026-10-27, third, I1) — a deliberate, bounded
    # exception: it leaves with the doctrine checks at a run's start as a
    # whole (docs/architecture.md, "The import rule"), and licenses no other
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


def on_a_cycle(graph: dict[str, set[str]]) -> list[str]:
    """The modules of GRAPH (module → the modules it imports) that reach
    themselves through their imports, sorted."""

    def reaches(start: str) -> set[str]:
        seen: set[str] = set()
        todo = list(graph.get(start, ()))
        while todo:
            m = todo.pop()
            if m not in seen:
                seen.add(m)
                todo.extend(graph.get(m, ()))
        return seen

    return sorted(m for m in graph if m in reaches(m))


#: an import back along a cycle that stands on purpose: a name kept where
#: stamped lab code imports it, forwarding to its one implementation —
#: listed by name until a release announces its end (CHANGELOG)
FORWARDING_EDGES = {
    # the stamped measure scripts' `from labkit.formats.repo import
    # next_after_run`, since the step commands moved to commands (2026-11-07)
    ("repo", "commands"),
}
#: public names defined twice on purpose: the forwarders of FORWARDING_EDGES
FORWARDED_NAMES = {"next_after_run"}


class NoImportCycle(unittest.TestCase):
    """The downward rule forbids an upward import but not a cycle inside a
    layer; five stood until 2026-11-07, each a helper kept in the module of
    its first caller (architecture audit, L1). Lazy imports count."""

    def test_no_module_reaches_itself_through_its_imports(self):
        graph = {m: imports_of(m) - {m} for m in modules()}
        for m, t in FORWARDING_EDGES:
            graph[m].discard(t)
        self.assertEqual(on_a_cycle(graph), [])

    def test_a_forwarding_edge_is_still_needed(self):
        # an edge listed here that no longer stands is listed in vain
        for m, t in FORWARDING_EDGES:
            self.assertIn(t, imports_of(m), (m, t))

    def test_the_check_bites(self):
        self.assertEqual(
            on_a_cycle({"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"a"}}),
            ["a", "b", "c"],
        )


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

    def test_all_marks_the_whole_row_and_a_list_only_its_names(self):
        row = "`audit`, `next_step` "
        self.assertEqual(doctrine_marks(row, " all "), {"audit", "next_step"})
        self.assertEqual(doctrine_marks(row, " `audit` "), {"audit"})
        with self.assertRaises(AssertionError):
            doctrine_marks(row, " `params` ")

    def test_every_gate_and_probe_is_doctrine_and_two_tools_are_core(self):
        doctrine, paths = doctrine_modules(), module_paths()
        for m, f in paths.items():
            if f.parent.name in ("gates", "probes"):
                self.assertIn(m, doctrine)
        self.assertNotIn("repo_check", doctrine)
        self.assertNotIn("params", doctrine)

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


class TheReleaseGateCallsNoModel(unittest.TestCase):
    def test_importing_report_check_loads_no_model_backend(self):
        # the pre-commit and the stop import it; through audit, the reviewers
        # and their texts it loaded llm and llm_backends (audit 2026-10-27,
        # third, M1). A fresh process: this one has them loaded already.
        import subprocess
        import sys

        code = (
            "import sys, labkit.gates.report_check; "
            "print(sorted(m for m in ('labkit.run.llm', 'labkit.run.llm_backends') "
            "if m in sys.modules))"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        self.assertEqual(out.stdout.strip(), "[]", out.stderr)


#: what follows the dot of a backticked file name (`runs.tsv`, `metrics.json`):
#: such a reference names a file, not a module's attribute
FILE_SUFFIXES = {"csv", "json", "jsonl", "lock", "log", "md", "patch", "py"}
FILE_SUFFIXES |= {"sh", "sha256", "toml", "tsv", "txt"}


def top_level_names(module: str) -> set[str]:
    """The names MODULE binds at its top level — functions, classes,
    assignments and imports: what `module.name` in the doc can mean."""
    tree = ast.parse(module_paths()[module].read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            out.update(t.id for t in n.targets if isinstance(t, ast.Name))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split(".")[0] for a in n.names)
    return out


def doc_references() -> list[tuple[int, str, str]]:
    """(line, module, name) for every backticked span of the doc that starts
    with `module.name`, module a labkit module; a longer chain
    (`gate.GateFinding.evidence_kind`) counts by its first two parts."""
    doc = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    known = set(modules())
    out: list[tuple[int, str, str]] = []
    for number, line in enumerate(doc.splitlines(), 1):
        for span in re.findall(r"`([^`]+)`", line):
            m = re.match(r"([a-z_][a-z0-9_]*)\.([A-Za-z_]\w*)", span)
            if m and m.group(1) in known and m.group(2) not in FILE_SUFFIXES:
                out.append((number, m.group(1), m.group(2)))
    return out


class EveryNamedHomeExists(unittest.TestCase):
    """Every `module.name` the doc names is defined in that module: a rename
    without the doc's line fails here instead of leaving the map naming a
    home that is gone (the gates in order, the chain and the one-home table
    are prose; 2026-11-06)."""

    def test_every_reference_resolves(self):
        names: dict[str, set[str]] = {}
        gone = [
            f"docs/architecture.md:{number}: {module}.{name}"
            for number, module, name in doc_references()
            if name not in names.setdefault(module, top_level_names(module))
        ]
        self.assertEqual(gone, [])

    def test_the_check_bites(self):
        # the twin: the reader finds references at all, and a name the module
        # does not define is not among its names
        refs = doc_references()
        self.assertGreater(len(refs), 100)
        self.assertIn(("report_check", "chain_gaps"), {(m, n) for _, m, n in refs})
        self.assertNotIn("chain_gapz", top_level_names("report_check"))


def literal_decisions(source: str) -> list[int]:
    """The lines of SOURCE where a `decide_command` call is given its STATUS
    (the third argument, or `status=`) as a string literal — a decision the
    caller chose itself rather than one taken from a recorded finding."""
    out: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name != "decide_command":
            continue
        status = node.args[2] if len(node.args) > 2 else None
        for kw in node.keywords:
            if kw.arg == "status":
                status = kw.value
        if isinstance(status, ast.Constant) and isinstance(status.value, str):
            out.append(node.lineno)
    return out


class NextComposesNoDecision(unittest.TestCase):
    """`labkit-next` names steps and chooses no scientific decision: a status
    in a `--decide` line it prints comes from the recorded finding — its
    subject, through `findings.decision_after_restore` — never from the place
    or file name of a finding (docs/architecture.md, "Who does what";
    until 2026-11-06 `_finding_on_the_field` offered `limitation` for any
    open finding on the protocol)."""

    def test_next_step_passes_no_literal_status(self):
        source = (PACKAGE / "gates" / "next_step.py").read_text(encoding="utf-8")
        self.assertEqual(literal_decisions(source), [])

    def test_the_check_bites(self):
        chosen = 'decide_command(a, 1, "limitation", "why", "r.toml")\n'
        named = 'decide_command(a, 1, status="fixed", reason="", record="r")\n'
        taken = "decide_command(a, 1, findings.decision_after_restore(f), '', 'r')\n"
        self.assertEqual(literal_decisions(chosen + named + taken), [1, 2])


class OneNameOneThing(unittest.TestCase):
    def test_no_public_name_in_two_modules(self):
        where: dict[str, list[str]] = defaultdict(list)
        for m in modules():
            for n in ast.parse(module_paths()[m].read_text(encoding="utf-8")).body:
                if isinstance(
                    n, (ast.FunctionDef, ast.ClassDef)
                ) and not n.name.startswith("_"):
                    where[n.name].append(m)
        twice = {
            k: v
            for k, v in where.items()
            if len(v) > 1 and k not in ENTRY_POINTS | FORWARDED_NAMES
        }
        self.assertEqual(twice, {}, "one public name, one thing (CODE-015)")


if __name__ == "__main__":
    unittest.main()
