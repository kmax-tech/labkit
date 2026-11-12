"""The architecture map in docs/architecture.md, held to the code.

The layer table is the one home of the map; this test reads it, so the doc
cannot drift from the imports unnoticed.
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
#: the core, listed by name until it moves. The test asks for
#: exactly this set: a new crossing fails, and so does a removed one left
#: standing here — the list only shrinks, with one kind of exception: a
#: rule the core had copied (`cost == "low"`) becoming a visible import
#: of `standard_contract` is the same crossing made explicit, not a new one.
KNOWN_CROSSINGS = {
    # the freeze gate at a run's start: audit coverage (LAB-015), the low lane's
    # registration and which lane owes the freeze, the audit or the foreground
    # — doctrine that refuses a run, sitting in the run writer's start check
    ("start_check", "findings"),  # findings.open_findings
    (
        "start_check",
        "evidence",
    ),  # evidence.read_evidence: the records the freeze gate reads
    ("start_check", "audit_gaps"),  # audit_gaps.audit_record_gap
    ("start_check", "failed_attempts"),  # failed_attempts.audit_unavailable
    ("start_check", "protocol_check"),  # protocol_check.low_registration_missing
    # the same registration, as HEAD holds it, for a first measurement:
    # report-check holds that commit, and a start on an uncommitted one could
    # never be adopted — a deliberate, bounded
    # exception: it leaves with the doctrine checks at a run's start as a
    # whole (docs/architecture.md, "The import rule"), and licenses no other
    ("start_check", "protocol_history"),  # protocol_history.registration_in_commit
    ("start_check", "standard_contract"),  # standard_contract.lane
    ("runlog", "standard_contract"),  # standard_contract.lane (the exception above)
    # the field catalogue and a rule's text in the code check — the boundary
    # case: the TOML head is core, the prose fields are doctrine
    ("prompt_check", "protocol_check"),  # protocol_check.fields
    ("code_check", "rules"),  # rules.paragraph
    ("code_check", "standard_contract"),  # standard_contract.lane (the exception above)
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
    # next_after_run`, which forwards to commands
    ("repo", "commands"),
}
#: public names defined twice on purpose: the forwarders of FORWARDING_EDGES
FORWARDED_NAMES = {"next_after_run"}


class NoImportCycle(unittest.TestCase):
    """The downward rule forbids an upward import but not a cycle inside a
    layer; this test forbids the cycle too, FORWARDING_EDGES aside. Lazy
    imports count."""

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


#: the readers of what an area measured (plan Phase 4, M1): outside
#: `labkit/formats` only the area state calls them, by name as data — a
#: module importing or naming one of them derives the field anew
FIELD_READERS = {
    "first_measurement_groups",  # answering_run, the first positions
    "indexed_runs",  # run_index, the index's run ids
    "indexed_bindings",  # run_index, the index's run id → protocol id
    "committed_runs",  # area_state, the runs git holds back
    "indexed_run_dirs",  # area_state, the runs git's index holds
    "bound_answering_run",  # answering_run, the choice over the run facts
    "bound_runs",  # answering_run, the completed bound runs and the rest
    "facts_of",  # answering_run, a record's state, binding and repeat
    "record_status",  # findings, the audit records and their errors
    "evidence_gaps",  # attempts, the records and attempts gone
    "change_findings",  # evidence, the committed evidence changed
    "area_reviews",  # reviews, the decision reviews
    "area_report_reviews",  # report_reviews, the report reviews
    "handed_over",  # handovers, the findings the records list as left over
}


def field_reader_uses(source: str) -> set[str]:
    """The names of FIELD_READERS SOURCE imports or reads as an attribute
    (`module.name`), docstrings and comments left out (an `ast` walk)."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            found |= {a.name for a in node.names if a.name in FIELD_READERS}
        elif isinstance(node, ast.Attribute) and node.attr in FIELD_READERS:
            found.add(node.attr)
        elif isinstance(node, ast.Name) and node.id in FIELD_READERS:
            found.add(node.id)
    return found


class OneAnswerPerStateQuestion(unittest.TestCase):
    """M1 of the plan's Phase 4: has a protocol measured, and which
    measurements were first, is answered by `area_state.Measured` alone —
    no gate, check, tool or run module calls the readers it is built from."""

    def test_only_the_area_state_calls_the_field_readers(self):
        paths = module_paths()
        offenders = {
            m: sorted(used)
            for m, p in sorted(paths.items())
            if p.parent.name != "formats"
            and (used := field_reader_uses(p.read_text(encoding="utf-8")))
        }
        self.assertEqual(offenders, {})

    def test_the_check_bites(self):
        self.assertEqual(
            field_reader_uses(
                "from labkit.formats.run_index import indexed_runs\n"
                "x = run_index.indexed_bindings(a)\n"
                '"""indexed_runs in a docstring"""\n'
            ),
            {"indexed_runs", "indexed_bindings"},
        )


#: the file accesses a gate or check may not make itself (plan Phase 4, M2):
#: every one is a format's to make, and the state hands the result down
FILE_ACCESS = {
    "read_text",
    "read_bytes",
    "iterdir",
    "glob",
    "rglob",
    "is_dir",
    "is_file",
    "exists",
    "open",
}
#: modules of gates and checks that open files by their nature, named here
#: so a new one cannot pass unseen: the hooks and the installer (they read
#: the harness's event, the session log, the hook files), the audit
#: commands (they read the prompt's pieces and write records), the notes
#: command (it runs over the notes it is given)
FILE_ACCESS_MODULES = {
    "hook_session",
    "hook_post_change",
    "agent_hooks",
    "hook_pre_run",
    "install_hooks",
    "audit",
    "audit_prompt",
    "audit_decisions",
    "decision_review",
    "report_review",
    "claim_review",
    "notes_check",
}
#: functions that run a program or read a command-line argument, which no
#: state can hand them: the area's tests, the analysis script's --check,
#: and the arguments a command checks before any state exists
FILE_ACCESS_FUNCTIONS = {
    ("preflight", "area_test_python"),
    ("preflight", "area_tests"),
    ("report_check", "check_analysis_script"),
    ("code_check", "_arguments"),
    ("intent_check", "_named"),
    ("intent_check", "choose_explicit"),
}


def file_accesses(source: str) -> list[tuple[str, int, str]]:
    """(function, line, access) for every call in SOURCE that opens, reads
    or lists a file — a method of FILE_ACCESS, a bare `open`, `subprocess`,
    `git_run` or `git` — with the top-level function it stands in ("" at
    module level)."""
    out: list[tuple[str, int, str]] = []
    tree = ast.parse(source)
    for node in tree.body:
        name = node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else ""
        for n in ast.walk(node):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in FILE_ACCESS:
                out.append((name, n.lineno, f.attr))
            elif (
                isinstance(f, ast.Attribute)
                and isinstance(f.value, ast.Name)
                and f.value.id == "subprocess"
            ):
                out.append((name, n.lineno, "subprocess." + f.attr))
            elif isinstance(f, ast.Name) and f.id in ("open", "git_run", "git"):
                out.append((name, n.lineno, f.id))
    return out


class NoFileAccessInGates(unittest.TestCase):
    """M2 of the plan's Phase 4: a gate or check reads the area through the
    state and the formats, never a file itself — but for the modules and
    functions named above, each with its reason."""

    def test_gates_and_checks_open_no_file(self):
        paths = module_paths()
        offenders = {}
        for m, p in sorted(paths.items()):
            if p.parent.name not in ("gates", "checks") or m in FILE_ACCESS_MODULES:
                continue
            hits = [
                f"{fn or '<module>'}:{line}: {what}"
                for fn, line, what in file_accesses(p.read_text(encoding="utf-8"))
                if (m, fn) not in FILE_ACCESS_FUNCTIONS
            ]
            if hits:
                offenders[m] = hits
        self.assertEqual(offenders, {})

    def test_every_named_exception_still_opens_a_file(self):
        paths = module_paths()
        for m in FILE_ACCESS_MODULES:
            self.assertTrue(file_accesses(paths[m].read_text(encoding="utf-8")), m)
        for m, fn in FILE_ACCESS_FUNCTIONS:
            found = file_accesses(paths[m].read_text(encoding="utf-8"))
            self.assertTrue(any(f == fn for f, _, _ in found), (m, fn))

    def test_the_check_bites(self):
        found = file_accesses(
            "def f(p):\n    return p.read_text()\n\ndef g(p):\n    with open(p) as fh:\n        return fh.read()\n"
        )
        self.assertEqual(
            [(fn, what) for fn, _, what in found], [("f", "read_text"), ("g", "open")]
        )


#: what a forwarded gate finding keeps: a gate that passes a finding on
#: (`dataclasses.replace(f, text=…)`) adds a prefix or a way out, never
#: another grade, rule assignment, evidence kind or check outcome
KEPT_WHEN_FORWARDED = {"grade", "rule", "evidence_kind", "stated_outcome"}
#: (module, function) of an explicit transformation of one of them, each
#: with its reason; none today
FORWARDING_TRANSFORMATIONS: set[tuple[str, str]] = set()


def forwarding_changes(source: str) -> list[tuple[str, int, list[str]]]:
    """(function, line, fields) of every `replace(...)` in SOURCE that sets
    a field of KEPT_WHEN_FORWARDED."""
    out: list[tuple[str, int, list[str]]] = []
    tree = ast.parse(source)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for n in ast.walk(fn):
            if not isinstance(n, ast.Call):
                continue
            name = (
                n.func.id
                if isinstance(n.func, ast.Name)
                else getattr(n.func, "attr", "")
            )
            changed = sorted({k.arg for k in n.keywords if k.arg} & KEPT_WHEN_FORWARDED)
            if name == "replace" and changed:
                out.append((fn.name, n.lineno, changed))
    return out


class ForwardingKeepsWhatAFindingIs(unittest.TestCase):
    """The forwarding guard (docs/architecture.md, "Checks and their
    tests"): a finding passed on keeps its grade, rule assignment, evidence kind and
    check outcome, but for a named transformation."""

    def test_no_forwarding_changes_what_a_finding_is(self):
        offenders = {
            (m, fn, line, tuple(fields))
            for m, p in sorted(module_paths().items())
            for fn, line, fields in forwarding_changes(p.read_text(encoding="utf-8"))
            if (m, fn) not in FORWARDING_TRANSFORMATIONS
        }
        self.assertEqual(offenders, set())

    def test_the_guard_bites_and_lets_a_prefix_pass(self):
        forbidden = (
            "def forward(f):\n"
            "    return dataclasses.replace(f, text='x' + f.text, rule=OPEN_RULE)\n"
        )
        self.assertEqual(forwarding_changes(forbidden), [("forward", 2, ["rule"])])
        allowed = "def forward(f):\n    return replace(f, text='finalize: ' + f.text)\n"
        self.assertEqual(forwarding_changes(allowed), [])


def stated_outcome_reads(source: str) -> list[int]:
    """The lines of SOURCE that read a finding's `stated_outcome` — what the
    site stated, None at most sites — where `outcome` is what the finding
    says."""
    return [
        n.lineno
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Attribute)
        and n.attr == "stated_outcome"
        and isinstance(n.ctx, ast.Load)
    ]


class TheOutcomeIsReadDerived(unittest.TestCase):
    """A finding's outcome has one reader's name, `GateFinding.outcome`
    (`gate.derived_outcome`); `stated_outcome` is the site's statement and is
    read only where the two are reconciled, in `gate`."""

    def test_no_module_but_gate_reads_the_stated_outcome(self):
        offenders = {
            (m, line)
            for m, p in sorted(module_paths().items())
            if m != "gate"
            for line in stated_outcome_reads(p.read_text(encoding="utf-8"))
        }
        self.assertEqual(offenders, set())

    def test_the_guard_bites_and_lets_the_keyword_pass(self):
        self.assertEqual(
            stated_outcome_reads("def f(x):\n    return x.stated_outcome\n"), [2]
        )
        self.assertEqual(
            stated_outcome_reads(
                "def f(x):\n    return blocker(x, stated_outcome=NOT_EXECUTABLE)\n"
            ),
            [],
        )
        gate_reads = stated_outcome_reads(
            module_paths()["gate"].read_text(encoding="utf-8")
        )
        self.assertTrue(gate_reads)  # the search finds the reads that exist


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
        # the pre-commit and the stop import it, so no path through audit,
        # the reviewers or their texts may load llm and llm_backends. A fresh
        # process: this one has them loaded already.
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
            # `A, B = …` binds each name of the tuple
            out.update(
                x.id for t in n.targets for x in ast.walk(t) if isinstance(x, ast.Name)
            )
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split(".")[0] for a in n.names)
    return out


def doc_references(path: Path | None = None) -> list[tuple[int, str, str]]:
    """(line, module, name) for every backticked span of PATH (the
    architecture doc when None) that starts with `module.name`, module a
    labkit module; a longer chain (`gate.GateFinding.evidence_kind`) counts
    by its first two parts."""
    path = path or ROOT / "docs" / "architecture.md"
    doc = path.read_text(encoding="utf-8")
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
    are prose)."""

    def test_every_reference_resolves(self):
        names: dict[str, set[str]] = {}
        gone = [
            f"docs/architecture.md:{number}: {module}.{name}"
            for number, module, name in doc_references()
            if name not in names.setdefault(module, top_level_names(module))
        ]
        self.assertEqual(gone, [])

    def test_every_reference_in_code_tests_and_docs_resolves(self):
        """A docstring or comment naming `module.name` names a home that
        exists. The dated audits and notes record a former state and are not
        read."""
        files = [
            *sorted(PACKAGE.rglob("*.py")),
            *sorted((ROOT / "tests").glob("*.py")),
            *sorted(
                p
                for p in (ROOT / "docs").glob("*.md")
                if not p.name.startswith("audit-")
            ),
            ROOT / "README.md",
            *sorted((PACKAGE / "docs").glob("*.md")),
            *sorted((PACKAGE / "agents").glob("*.md")),
            *sorted((PACKAGE / "templates").glob("*.template")),
        ]
        names: dict[str, set[str]] = {}
        gone = [
            f"{path.relative_to(ROOT)}:{number}: {module}.{name}"
            for path in files
            for number, module, name in doc_references(path)
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
        self.assertIn("RESTORE", top_level_names("commands"))  # `A, B = …`


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
    or file name of a finding (docs/architecture.md, "Who does what")."""

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
