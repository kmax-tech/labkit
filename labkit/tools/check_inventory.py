"""check_inventory — every place labkit tells a finding, with the rule it
cites, and every active rule of the standard with the places that cite it.

    python -m labkit.tools.check_inventory [--records EXPERIMENTS] [--out FILE]

The basis for measuring whether a rule earns its place: a rule no finding
cites is held by an agent audit or by nobody, and a finding that cites no
rule cannot be counted for one. Read from the source (`ast`), never run:

  - a finding site is a call that builds a gate finding (`GateFinding`,
    `blocker`, `coded`, `Findings.block`, `Findings.warn`; channel
    `finding`), a `raise SystemExit(<message>)` (how code a measure script
    reaches ends, `console.Refused` says which; channel `exit`), or a call
    that prints a `WARNING:` or `BLOCKER:` line of its own (channel
    `printed`); a `console.Refused` (exit 2: the command cannot run) is no
    finding and is left out
  - what is scanned: the bodies of top-level functions, classes' methods
    and the functions nested in either; code at module level and the
    methods of a nested class are not, and two sites of one channel on one
    line count once
  - its rule is the assignment the call records as data (`rule=`, a
    `gate.RuleAssignment`: a rule id, an open assignment, a technical
    contract, a new class), read through a local name and a module
    constant; the rule tables count by it. Beside it the scan names the
    rule ids the call's strings cite — its own literals, the module
    constants it names, what is assigned to a local name it passes —, a
    citation in the text, not a record
  - an open cause a site receives is a place the code names `OPEN_RULE`
    that is not the rule argument of a finding site itself: the value of a
    cause's record, a table, a function's result, or one arm of a
    condition in a rule argument. A site whose rule reads `variable` gets
    its assignment from such a place, so the open sites alone undercount
    what is open; the count line and the last table name both. What the
    scan cannot tell: which site receives which cause, and whether every
    cause of a `variable` site carries an assignment
  - its commands are the console scripts (`[project.scripts]`) whose code
    reaches its function by a static call graph: a call or reference by
    name, through an import or a module alias, a method through `self` or
    its class's name. An estimate in both directions, not a trace
    (`labkit-calltree` shows what one run did call); `—` where no command
    reaches it — code an area script calls (`recheck`, `lanes`) or nothing

With `--records EXPERIMENTS` (a lab repo's experiments folder) it adds
what the agent audits found there: the findings per rule the auditor named
(`findings.Finding.rule`), and every `new class` finding — a fault no rule
of the standard names, listed for the author to review. A new class
becomes a rule only by a decision with its grounds, never by this list.

The table is computed at every call and committed nowhere: line
numbers move with every edit. Prints the markdown to stdout, or writes it
to FILE.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import console, findings
from labkit.formats.gate import NEW_CLASS, OPEN_ASSIGNMENT, TECHNICAL_CONTRACT
from labkit.formats.rules import CODE_RE, load_ledger

USAGE = (
    "usage: python -m labkit.tools.check_inventory [--records EXPERIMENTS] [--out FILE]"
)

RULE_ID = CODE_RE  # every rule family; the ledger read here holds LAB
PRINTED_GRADE = re.compile(r"\b(WARNING|BLOCKER):")

#: the finding constructors (`labkit.formats.gate`) and the grade each one
#: sets itself; None where the grade is the call's first argument
CONSTRUCTORS: dict[str, str | None] = {
    "blocker": "BLOCKER",
    "block": "BLOCKER",
    "warn": "WARNING",
    "coded": None,
    "GateFinding": None,
}
#: the constructors that set the evidence kind themselves: a blocker is
#: always exact, static evidence never blocks (`gate.GateFinding`)
GUARANTEED_BY_CONSTRUCTION = {"blocker", "block"}
#: the units that are the constructors themselves, not a check
CONSTRUCTOR_UNITS = {
    "labkit.formats.gate.blocker",
    "labkit.formats.gate.coded",
    "labkit.formats.gate.Findings.block",
    "labkit.formats.gate.Findings.warn",
    "labkit.formats.gate.GateFinding.line",
}
#: `.warn` / `.block` on these names is the stdlib's, not a gate's
NOT_A_COLLECTOR = {"warnings", "logging", "logger", "log"}
#: the shipped texts an agent or an area reads, whose rule ids count as
#: "cited outside the code"
SHIPPED_TEXT_GLOBS = ("agents/*.md", "templates/*.template", "docs/*-guide.md")
WORDING_WIDTH = 90


@dataclass(frozen=True)
class FindingSite:
    """One place in labkit's source that tells a finding.

    Attributes:
        unit: The function or method it stands in, `module.qualname`; a
            nested function counts as part of the function around it.
        path: The source file, relative to the package's parent.
        line: The call's first line.
        end_line: The call's last line.
        channel: `finding` (a gate finding), `exit` (a `SystemExit`
            with a message) or `printed` (a `WARNING:`/`BLOCKER:` line).
        grade: BLOCKER, WARNING, `exit`, or `variable` where the call
            passes one.
        evidence_kind: GUARANTEED, STATIC_EVIDENCE, `variable`, or
            `none` for an exit or a printed line, which carry none.
        rules: The rule ids in the call's strings, sorted — what the
            message cites, not what the finding records.
        wording: The message's constant text, every value as `{…}`.
        assignment: The rule assignment the call records as data
            (`gate.RuleAssignment`, `_call_assignment`): a rule id
            `LAB-nnn`, OPEN_ASSIGNMENT, TECHNICAL_CONTRACT or NEW_CLASS;
            NOT_RECORDED where the call sets none (every `exit` and
            `printed` site, and a gate finding the migration has not
            visited); `variable` where it passes a value the scan cannot
            follow. The rule tables count by it.
    """

    unit: str
    path: str
    line: int
    end_line: int
    channel: str
    grade: str
    evidence_kind: str
    rules: tuple[str, ...]
    wording: str
    assignment: str = ""


#: a site that records no rule assignment as data
NOT_RECORDED = "not recorded"
#: the module constants of `gate` that stand for an assignment without a rule
_RULE_CONSTANTS = {
    "OPEN_RULE": OPEN_ASSIGNMENT,
    "TECHNICAL_RULE": TECHNICAL_CONTRACT,
    "NEW_CLASS_RULE": NEW_CLASS,
}


@dataclass(frozen=True)
class OpenCause:
    """One place the code names `OPEN_RULE` outside a finding site's own
    rule argument (`open_causes`): PATH and LINE, and UNIT, the function
    or method around it, the module's name for code at module level."""

    path: str
    line: int
    unit: str


@dataclass(frozen=True)
class RuleUse:
    """One active rule and every place that cites it.

    Attributes:
        rule: `LAB-nnn Title`, as the ledger names it.
        sites: The finding sites citing it.
        code_modules: Modules whose other (non-docstring) strings cite it,
            sites left out — a check's message a gate passes on, a constant.
        shipped_texts: Agent definitions, templates and guides citing it.
    """

    rule: str
    sites: tuple[FindingSite, ...]
    code_modules: tuple[str, ...]
    shipped_texts: tuple[str, ...]


@dataclass(frozen=True)
class Module:
    """One parsed source module of the package."""

    name: str
    path: str
    tree: ast.Module


def read_modules(package_dir: Path) -> list[Module]:
    """Every `.py` file under PACKAGE_DIR, parsed; a file that does not
    parse raises SyntaxError naming it."""
    root = package_dir.parent
    out = []
    for path in sorted(package_dir.rglob("*.py")):
        rel = path.relative_to(root)
        parts = rel.with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        out.append(Module(name, str(rel), tree))
    return out


def docstring_nodes(tree: ast.Module) -> set[int]:
    """The ids of the string constants that are documentation, not
    messages: every string standing alone as a statement (the docstrings
    and attribute notes)."""
    return {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def strings_in(node: ast.AST, skip: set[int]) -> list[str]:
    """Every string constant under NODE, f-string parts included, leaving
    out the ids in SKIP (`docstring_nodes`)."""
    return [
        n.value
        for n in ast.walk(node)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and id(n) not in skip
    ]


def wording(node: ast.AST | None, assigned: dict[str, list[ast.AST]]) -> str:
    """The constant text of a message expression, every value as `{…}`; a
    local name assigned once reads through to its value."""
    if node is None:
        return ""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            v.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str)
            else "{…}"
            for v in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return wording(node.left, assigned) + wording(node.right, assigned)
    if isinstance(node, ast.Name) and len(assigned.get(node.id, [])) == 1:
        return wording(assigned[node.id][0], assigned)
    return "{…}"


def short(text: str) -> str:
    """TEXT on one line, cut to `WORDING_WIDTH`, safe in a table cell."""
    one = " ".join(text.split()).replace("|", "\\|")
    return one if len(one) <= WORDING_WIDTH else one[: WORDING_WIDTH - 1] + "…"


def module_constants(modules: list[Module]) -> dict[str, list[str]]:
    """`module.NAME` → the strings of a module-level assignment to NAME."""
    out: dict[str, list[str]] = {}
    for m in modules:
        skip = docstring_nodes(m.tree)
        for stmt in m.tree.body:
            targets = (
                stmt.targets
                if isinstance(stmt, ast.Assign)
                else [stmt.target]
                if isinstance(stmt, ast.AnnAssign) and stmt.value is not None
                else []
            )
            for t in targets:
                if isinstance(t, ast.Name):
                    out[f"{m.name}.{t.id}"] = strings_in(stmt, skip)
    return out


def imported_names(m: Module, known_modules: set[str]) -> dict[str, str]:
    """Local name → what it stands for, fully qualified: a module
    (`gate` → `labkit.formats.gate`) or a module's attribute
    (`blocker` → `labkit.formats.gate.blocker`)."""
    out: dict[str, str] = {}
    for node in ast.walk(m.tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    out[a.asname] = a.name
                else:
                    out[a.name.split(".")[0]] = a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                out[a.asname or a.name] = f"{node.module}.{a.name}"
    # a plain `import os` names no package module and leads nowhere
    return {k: v for k, v in out.items() if v in known_modules or "." in v}


def units(m: Module) -> dict[str, ast.AST]:
    """`module.qualname` → its node: every top-level function, class and
    method; a nested function stays inside the unit around it."""
    out: dict[str, ast.AST] = {}
    for stmt in m.tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[f"{m.name}.{stmt.name}"] = stmt
        elif isinstance(stmt, ast.ClassDef):
            out[f"{m.name}.{stmt.name}"] = stmt
            for item in stmt.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[f"{m.name}.{stmt.name}.{item.name}"] = item
    return out


def local_assignments(node: ast.AST) -> dict[str, list[ast.AST]]:
    """Local name → the values assigned to it under NODE."""
    out: dict[str, list[ast.AST]] = defaultdict(list)
    for n in ast.walk(node):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out[t.id].append(n.value)
        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)) and n.value is not None:
            if isinstance(n.target, ast.Name):
                out[n.target.id].append(n.value)
    return out


def _constructor(call: ast.Call) -> str | None:
    """The finding constructor CALL calls, or None."""
    f = call.func
    if (
        isinstance(f, ast.Name)
        and f.id in CONSTRUCTORS
        # `block` and `warn` are `Findings` methods: they count only as
        # `<collector>.block(...)`, never as a bare name
        and f.id not in {"block", "warn"}
    ):
        return f.id
    if isinstance(f, ast.Attribute) and f.attr in CONSTRUCTORS:
        if isinstance(f.value, ast.Name) and f.value.id in NOT_A_COLLECTOR:
            return None
        return f.attr
    return None


def _grade_name(node: ast.AST | None) -> str:
    """BLOCKER / WARNING / GUARANTEED / STATIC_EVIDENCE when NODE names
    one of them, else `variable`."""
    name = (
        node.id
        if isinstance(node, ast.Name)
        else node.attr
        if isinstance(node, ast.Attribute)
        else None
    )
    known = {"BLOCKER", "WARNING", "GUARANTEED", "STATIC_EVIDENCE"}
    return name if name in known else "variable"


def _call_rules(
    call: ast.AST,
    skip: set[int],
    assigned: dict[str, list[ast.AST]],
    constants: dict[str, list[str]],
    module: str,
    imports: dict[str, str],
) -> tuple[str, ...]:
    """The rule ids in CALL's strings and in the values assigned to the
    local names it passes, and in the module constants either names."""
    nodes = [call] + [
        value
        for n in ast.walk(call)
        if isinstance(n, ast.Name)
        for value in assigned.get(n.id, [])
    ]
    texts = [s for node in nodes for s in strings_in(node, skip)]
    for node in nodes:
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                texts += constants.get(f"{module}.{n.id}", [])
                texts += constants.get(imports.get(n.id, ""), [])
    return tuple(sorted({r for t in texts for r in RULE_ID.findall(t)}))


#: the one spelling of a refusal with its way out (`gate.with_way_out`): a
#: `SystemExit` around it is a refusal, its first argument the message
WAY_OUT_WRAPPER = "with_way_out"


def _rule_argument(call: ast.Call, ctor: str) -> ast.AST | None:
    """The expression CALL to the finding constructor CTOR passes as its
    rule: the `rule=` keyword, or a GateFinding's fifth positional argument
    (grade, text, form, where, rule)."""
    for k in call.keywords:
        if k.arg == "rule":
            return k.value
    if ctor == "GateFinding" and len(call.args) > 4:
        return call.args[4]
    return None


def _call_assignment(
    expr: ast.AST | None,
    assigned: dict[str, list[ast.AST]],
    constants: dict[str, list[str]],
    module: str,
    imports: dict[str, str],
) -> str:
    """The rule assignment EXPR records (`FindingSite.assignment`): a
    gate constant by its name, `cited_rule("LAB-nnn …")` by its id, read
    through a local name assigned once and through a module constant;
    NOT_RECORDED without EXPR or for a literal None, `variable` for
    anything else."""
    if expr is None or (isinstance(expr, ast.Constant) and expr.value is None):
        return NOT_RECORDED
    name = (
        expr.id
        if isinstance(expr, ast.Name)
        else expr.attr
        if isinstance(expr, ast.Attribute)
        else None
    )
    if name in _RULE_CONSTANTS:
        return _RULE_CONSTANTS[name]
    if isinstance(expr, ast.Name) and len(assigned.get(expr.id, [])) == 1:
        return _call_assignment(
            assigned[expr.id][0], assigned, constants, module, imports
        )
    texts: list[str] = []
    if isinstance(expr, ast.Call) and getattr(expr.func, "id", None) == "cited_rule":
        texts = [
            a.value
            for a in expr.args
            if isinstance(a, ast.Constant) and isinstance(a.value, str)
        ]
    elif isinstance(expr, ast.Name):
        texts = constants.get(f"{module}.{expr.id}", []) or constants.get(
            imports.get(expr.id, ""), []
        )
    ids = sorted({r for t in texts for r in RULE_ID.findall(t)})
    return ids[0] if len(ids) == 1 else "variable"


def _refusal_message(n: ast.AST) -> ast.AST | None:
    """The message of a `raise SystemExit(<message>)` — for
    `SystemExit(with_way_out(<message>, <fix>))` its first argument; None
    for any other node, and for an exit code or a main's result passed
    through (`SystemExit(main(argv))`)."""
    if not (isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)):
        return None
    exc = n.exc
    if not (
        isinstance(exc.func, ast.Name) and exc.func.id == "SystemExit" and exc.args
    ):
        return None
    arg = exc.args[0]
    if isinstance(arg, ast.Call):
        wrapped = isinstance(arg.func, ast.Name) and arg.func.id == WAY_OUT_WRAPPER
        return arg.args[0] if wrapped and arg.args else None
    if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
        return None
    return arg


def _finding_parts(call: ast.Call, ctor: str) -> tuple[str, str, ast.AST | None]:
    """Grade, evidence kind and message of a call to the finding
    constructor CTOR."""
    args = call.args
    keyword = {k.arg: k.value for k in call.keywords}
    grade = CONSTRUCTORS[ctor] or _grade_name(args[0] if args else None)
    if ctor in GUARANTEED_BY_CONSTRUCTION:
        kind = "GUARANTEED"
    else:
        kind = _grade_name(keyword.get("evidence_kind"))
    # the message: blocker/block/warn take it first, a GateFinding second
    # (after the grade), coded third (after grade and where)
    at = {"coded": 2, "GateFinding": 1}.get(ctor, 0)
    return grade, kind, args[at] if len(args) > at else keyword.get("text")


def _printed_grade(call: ast.Call, skip: set[int]) -> str | None:
    """WARNING or BLOCKER when CALL prints a line of that grade itself —
    a string of its own says `WARNING:` or `BLOCKER:` and no finding
    constructor stands inside it; else None."""
    if any(isinstance(a, ast.Call) and _constructor(a) for a in ast.walk(call)):
        return None
    for s in strings_in(call, skip):
        hit = PRINTED_GRADE.search(s)
        if hit:
            return hit.group(1)
    return None


def site_kind(
    n: ast.AST, skip: set[int]
) -> tuple[str, str, str, ast.AST | None] | None:
    """Channel, grade, evidence kind and message when node N is a finding
    site (the module docstring says what counts), else None."""
    refused = _refusal_message(n)
    if refused is not None:
        return "exit", "exit", "none", refused
    if not isinstance(n, ast.Call):
        return None
    ctor = _constructor(n)
    if ctor is not None:
        return ("finding", *_finding_parts(n, ctor))
    printed = _printed_grade(n, skip)
    if printed is not None:
        return "printed", printed, "none", n.args[0] if n.args else None
    return None


def finding_sites(modules: list[Module]) -> list[FindingSite]:
    """Every finding site of MODULES, in source order; a printed line
    inside another printed call is one site, the outer."""
    constants = module_constants(modules)
    known = {m.name for m in modules}
    out: list[FindingSite] = []
    seen: set[tuple[str, int, str]] = set()
    for m in modules:
        skip = docstring_nodes(m.tree)
        imports = imported_names(m, known)
        for unit, node in units(m).items():
            if isinstance(node, ast.ClassDef) or unit in CONSTRUCTOR_UNITS:
                continue
            assigned = local_assignments(node)
            for n in ast.walk(node):
                kind = site_kind(n, skip)
                if kind is None:
                    continue
                channel, grade, evidence_kind, msg = kind
                line = n.lineno  # type: ignore[attr-defined] — a call and a raise have one
                if (m.path, line, channel) in seen:
                    continue
                seen.add((m.path, line, channel))
                out.append(
                    FindingSite(
                        unit=unit,
                        path=m.path,
                        line=line,
                        end_line=n.end_lineno or line,  # type: ignore[attr-defined]
                        channel=channel,
                        grade=grade,
                        evidence_kind=evidence_kind,
                        rules=_call_rules(
                            n, skip, assigned, constants, m.name, imports
                        ),
                        wording=short(wording(msg, assigned)),
                        assignment=(
                            _call_assignment(
                                _rule_argument(n, ctor),
                                assigned,
                                constants,
                                m.name,
                                imports,
                            )
                            if channel == "finding"
                            and isinstance(n, ast.Call)
                            and (ctor := _constructor(n)) is not None
                            else NOT_RECORDED
                        ),
                    )
                )
    return out


def _names_open_rule(n: ast.AST) -> bool:
    """Is N the name `OPEN_RULE`, bare or through a module, where it is read?"""
    if isinstance(n, ast.Name):
        return n.id == "OPEN_RULE" and isinstance(n.ctx, ast.Load)
    return isinstance(n, ast.Attribute) and n.attr == "OPEN_RULE"


def _site_rule_names(node: ast.AST, skip: set[int]) -> set[int]:
    """The ids of the `OPEN_RULE` names under the unit NODE that a finding
    site of it records as its own rule: its rule argument, read through a
    local name assigned once as `_call_assignment` reads it."""
    assigned = local_assignments(node)
    out: set[int] = set()
    for n in ast.walk(node):
        kind = site_kind(n, skip)
        if kind is None or kind[0] != "finding" or not isinstance(n, ast.Call):
            continue
        ctor = _constructor(n)
        expr = _rule_argument(n, ctor) if ctor is not None else None
        while isinstance(expr, ast.Name) and len(assigned.get(expr.id, [])) == 1:
            expr = assigned[expr.id][0]
        if expr is not None and _names_open_rule(expr):
            out.add(id(expr))
    return out


def open_causes(modules: list[Module]) -> list[OpenCause]:
    """Every place MODULES name `OPEN_RULE` that is not a finding site's
    own rule argument, in source order — the open assignments a site
    receives from its cause. Code at module level counts (a table of
    rules); an import and the constant's definition name no cause."""
    out: list[OpenCause] = []
    for m in modules:
        skip = docstring_nodes(m.tree)
        at_site: set[int] = set()
        unit_of: dict[int, str] = {}
        for unit, node in units(m).items():
            if isinstance(node, ast.ClassDef):
                continue
            if unit not in CONSTRUCTOR_UNITS:
                at_site |= _site_rule_names(node, skip)
            for n in ast.walk(node):
                unit_of[id(n)] = unit
        out += sorted(
            (
                OpenCause(m.path, n.lineno, unit_of.get(id(n), m.name))  # type: ignore[attr-defined] — a name has a line
                for n in ast.walk(m.tree)
                if _names_open_rule(n) and id(n) not in at_site
            ),
            key=lambda c: c.line,
        )
    return out


@dataclass(frozen=True)
class _Scope:
    """What a name in one unit can resolve to (`call_graph`)."""

    module: str
    imports: dict[str, str]
    known_modules: set[str]
    all_units: dict[str, ast.AST]
    methods: dict[str, set[str]]
    cls: str | None  # the class around a method, else None


def _referenced_unit(n: ast.AST, scope: _Scope) -> str | None:
    """The unit node N names — a local or imported name, `module.attr`
    through an imported module, `self.attr` in a method, `Class.attr` —
    or None."""
    target = None
    if isinstance(n, ast.Name):
        local = f"{scope.module}.{n.id}"
        target = local if local in scope.all_units else scope.imports.get(n.id)
    elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
        base, imported = n.value.id, scope.imports.get(n.value.id)
        if base in {"self", "cls"} and scope.cls is not None:
            target = f"{scope.cls}.{n.attr}"
        elif imported in scope.known_modules or imported in scope.methods:
            target = f"{imported}.{n.attr}"
        elif f"{scope.module}.{base}" in scope.methods:
            target = f"{scope.module}.{base}.{n.attr}"
    return target if target in scope.all_units else None


def call_graph(modules: list[Module]) -> dict[str, set[str]]:
    """Unit → the units it calls or names (the module docstring says how
    far the estimate reaches). A class named stands for all its methods."""
    known = {m.name for m in modules}
    all_units: dict[str, ast.AST] = {}
    for m in modules:
        all_units.update(units(m))
    methods: dict[str, set[str]] = defaultdict(set)
    for u in all_units:
        parent = u.rsplit(".", 1)[0]
        if isinstance(all_units.get(parent), ast.ClassDef):
            methods[parent].add(u)
    graph: dict[str, set[str]] = defaultdict(set)
    for m in modules:
        imports = imported_names(m, known)
        for unit, node in units(m).items():
            parent = unit.rsplit(".", 1)[0]
            scope = _Scope(
                m.name,
                imports,
                known,
                all_units,
                methods,
                parent if parent in methods else None,
            )
            for n in ast.walk(node):
                target = _referenced_unit(n, scope)
                if target is not None and target != unit:
                    graph[unit].add(target)
                    graph[unit] |= methods.get(target, set())
    return graph


def entry_points(pyproject: str) -> dict[str, str]:
    """Console script → its unit, from `[project.scripts]`
    (`labkit.gates.finalize:cli` → `labkit.gates.finalize.cli`)."""
    scripts = tomllib.loads(pyproject)["project"]["scripts"]
    return {name: target.replace(":", ".") for name, target in scripts.items()}


def reaching_commands(
    graph: dict[str, set[str]], entries: dict[str, str]
) -> dict[str, set[str]]:
    """Unit → the commands whose entry reaches it through GRAPH."""
    out: dict[str, set[str]] = defaultdict(set)
    for command, entry in entries.items():
        stack, seen = [entry], {entry}
        while stack:
            u = stack.pop()
            out[u].add(command)
            for v in graph.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    return out


def rule_uses(
    ledger_rows: list[tuple[str, str]],
    sites: list[FindingSite],
    modules: list[Module],
    shipped: dict[str, str],
) -> list[RuleUse]:
    """Every rule of LEDGER_ROWS (`(id, title)`, the active ones) with the
    SITES citing it, the other modules whose message strings cite it, and
    the SHIPPED texts (name → text) citing it."""
    spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for s in sites:
        spans[s.path].append((s.line, s.end_line))
    in_code: dict[str, set[str]] = defaultdict(set)
    for m in modules:
        skip = docstring_nodes(m.tree)
        for n in ast.walk(m.tree):
            if (
                isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and id(n) not in skip
                and not any(a <= n.lineno <= b for a, b in spans[m.path])
            ):
                for r in RULE_ID.findall(n.value):
                    in_code[r].add(m.name)
    out = []
    for rid, title in ledger_rows:
        out.append(
            RuleUse(
                rule=f"{rid} {title}",
                sites=tuple(s for s in sites if s.assignment == rid),
                code_modules=tuple(sorted(in_code.get(rid, set()))),
                shipped_texts=tuple(
                    sorted(name for name, text in shipped.items() if rid in text)
                ),
            )
        )
    return out


def render_inventory(
    sites: list[FindingSite],
    uses: list[RuleUse],
    commands: dict[str, set[str]],
    causes: list[OpenCause],
) -> str:
    """The inventory as markdown: a count line, the rules, the sites, the
    open causes a site receives (CAUSES)."""

    def cmds(unit: str) -> str:
        return ", ".join(sorted(commands.get(unit, set()))) or "—"

    def short_unit(unit: str) -> str:
        return unit.removeprefix("labkit.")

    cited = sum(1 for s in sites if RULE_ID.fullmatch(s.assignment))
    by_kind = Counter(s.assignment for s in sites)
    held = [u for u in uses if u.sites]
    lines = [
        "# Check inventory",
        "",
        f"{len(sites)} finding sites, {cited} of them record a rule as data "
        f"(`GateFinding.rule`); {len(held)} of {len(uses)} active rules are "
        "recorded by a finding site. "
        f"Of the others: {by_kind[TECHNICAL_CONTRACT]} a technical contract, "
        f"{by_kind[OPEN_ASSIGNMENT]} an open assignment, {by_kind[NEW_CLASS]} a "
        f"new class, {by_kind['variable']} a rule the cause passes in "
        f"(`variable`), {by_kind[NOT_RECORDED]} none. Open assignments in all: "
        f"{by_kind[OPEN_ASSIGNMENT] + len(causes)} — at the "
        f"{by_kind[OPEN_ASSIGNMENT]} open sites and at {len(causes)} causes a "
        "site receives (last table). "
        "Read from the source, not run: `python -m labkit.tools.check_inventory` "
        "(its docstring says what counts and how far the estimate reaches).",
        "",
        "## Rules",
        "",
        "| Rule | Finding sites | Other code strings | Shipped texts |",
        "|---|---|---|---|",
    ]
    for u in uses:
        where = ", ".join(f"`{s.path}:{s.line}`" for s in u.sites) or "—"
        lines.append(
            f"| {u.rule} | {where} | {', '.join(short_unit(m) for m in u.code_modules) or '—'} "
            f"| {', '.join(u.shipped_texts) or '—'} |"
        )
    lines += [
        "",
        "## Finding sites",
        "",
        "| Site | Function | Channel | Grade | Evidence kind | Rule (data) | Cited in the text | Commands | Wording |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in sites:
        lines.append(
            f"| `{s.path}:{s.line}` | `{short_unit(s.unit)}` | {s.channel} | {s.grade} "
            f"| {s.evidence_kind} | {s.assignment} | {', '.join(s.rules) or '—'} | {cmds(s.unit)} "
            f"| {s.wording} |"
        )
    lines += [
        "",
        "## Open causes a site receives",
        "",
        "| Place | Function |",
        "|---|---|",
        *(f"| `{c.path}:{c.line}` | `{short_unit(c.unit)}` |" for c in causes),
    ]
    return "\n".join(lines) + "\n"


def inventory(package_dir: Path) -> str:
    """The inventory of the package at PACKAGE_DIR, as markdown: reads its
    sources, its ledger, its shipped texts and the `pyproject.toml` beside
    it."""
    modules = read_modules(package_dir)
    sites = finding_sites(modules)
    ledger = [
        (r.id, r.title)
        for r in load_ledger(package_dir / "docs" / "rules.tsv")
        if r.status == "active"
    ]
    shipped = {
        str(p.relative_to(package_dir)): p.read_text(encoding="utf-8")
        for pattern in SHIPPED_TEXT_GLOBS
        for p in sorted(package_dir.glob(pattern))
    }
    pyproject = (package_dir.parent / "pyproject.toml").read_text(encoding="utf-8")
    commands = reaching_commands(call_graph(modules), entry_points(pyproject))
    return render_inventory(
        sites,
        rule_uses(ledger, sites, modules, shipped),
        commands,
        open_causes(modules),
    )


def render_audit_rules(
    experiments: Path, records: list[tuple[Path, findings.Record]]
) -> str:
    """What the agent audits under EXPERIMENTS found, as markdown: the
    findings per rule the auditor named, then every `new class` finding
    with its record and number, for the author to review."""
    per_rule: dict[str, int] = defaultdict(int)
    for _, record in records:
        for f in record.findings:
            per_rule[findings.stored_rule(f.rule)] += 1
    new = findings.new_class_findings(records)
    lines = [
        "",
        f"## Audit findings in {experiments}",
        "",
        f"{sum(per_rule.values())} findings in {len(records)} audit records, "
        f"{len(new)} of them `{findings.NEW_CLASS}`.",
        "",
        "| Rule | Findings |",
        "|---|---|",
        *(f"| {rule} | {n} |" for rule, n in sorted(per_rule.items())),
        "",
        f"## `{findings.NEW_CLASS}` — for the author to review",
        "",
        "A fault no rule of the standard names. It becomes a rule only by a "
        "decision with its grounds, never by this list.",
        "",
        "| Finding | Grade | Subject | Status | Text |",
        "|---|---|---|---|---|",
        *(
            f"| `{record.path.relative_to(experiments)}#{n}` | {f.grade} | {f.subject} "
            f"| {f.status} | {short(f.one_line)} |"
            for _, record, n, f in new
        ),
    ]
    return "\n".join(lines) + "\n"


def _options(argv: list[str]) -> dict[str, Path]:
    """ARGV's options, each with its path. Raises console.Refused for an
    unknown option, one given twice and one without its value."""
    options: dict[str, Path] = {}
    rest = list(argv)
    while rest:
        option = rest[0]
        if option not in ("--out", "--records"):
            raise console.Refused(
                "check_inventory", f"{option!r} is no option; {USAGE}"
            )
        if option in options:
            raise console.Refused("check_inventory", f"{option} given twice; {USAGE}")
        if len(rest) < 2:
            raise console.Refused(
                "check_inventory", f"{option} without its value; {USAGE}"
            )
        options[option] = Path(rest[1])
        rest = rest[2:]
    return options


def main(argv: list[str]) -> int:
    """Print the inventory, with `--records EXPERIMENTS` the audit findings
    there by rule; to stdout, or to `--out FILE`. 0."""
    if argv in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    options = _options(argv)
    out = options.get("--out")
    text = inventory(PACKAGE_DIR)
    experiments = options.get("--records")
    if experiments is not None:
        if not experiments.is_dir():
            raise console.Refused("check_inventory", f"{experiments}: no such folder")
        text += render_audit_rules(experiments, findings.repo_records(experiments))
    if out is None:
        sys.stdout.write(text)
    else:
        out.write_text(text, encoding="utf-8")
        print(f"check_inventory: wrote {out}")
    return 0


def cli() -> None:
    """Console entry: `main` with the process's arguments."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
