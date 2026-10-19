"""import_check — code that determines the number and that no stamp sees.

The audit stamp follows `import` statements into `lib/` and `src/`
(`scope_sha`); it cannot follow a `sys.path` edit, `importlib`, `runpy`
or `exec`, a file the script loads from another area, or an import that
resolves to a repo file outside those roots. `stamp_coverage_findings`
names each such line as a WARNING (static evidence, LAB-019 The stamp
covers everything that determines the number).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from labkit.formats.scope_sha import (
    LOCAL_ROOTS,
    SourceError,
    area_files,
    imported_repo_helpers,
)
from labkit.checks.code_scan import unreadable_source


DYNAMIC_LOADERS = {
    "import_module",
    "spec_from_file_location",
    "run_path",
    "run_module",
    "__import__",
    "exec",
}


def _call_name(node: ast.Call) -> str:
    """The last name of what a call calls: `importlib.import_module(...)` → import_module."""
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def _is_sys_path(node: ast.AST | None) -> bool:
    """True for the expression `sys.path`."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "path"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _outside_roots(name: str, area: Path, repo: Path) -> Path | None:
    """The repo file an import of dotted NAME resolves to when it lies
    outside LOCAL_ROOTS and outside the area's own scripts — None otherwise
    (a stdlib or third-party name resolves to nothing in the repo)."""
    seg = name.split(".")[0]
    if not seg or seg in LOCAL_ROOTS:
        return None
    if (area / "scripts" / f"{seg}.py").is_file() or (
        area / "analysis" / f"{seg}.py"
    ).is_file():
        return None  # a sibling in the area: stamped with it
    for candidate in (repo / f"{seg}.py", repo / seg / "__init__.py"):
        if candidate.is_file():
            return candidate
    if (repo / seg).is_dir() and seg not in ("data", "tests", "notes", "docs", "runs"):
        return (
            repo / seg
        )  # a package without __init__ — a namespace package, or a path import
    return None


#: an area name inside a path string: `14-hotel`, `experiments/14-hotel/scripts/x.py`
#: an area name inside a path literal (`repo.AREA_NAME` is the name itself;
#: here it is searched for in a string, any number of digits)
AREA_IN_PATH = re.compile(r"(?:^|/)(\d+-[a-z0-9][a-z0-9-]*)(?:/|$)")


def _str_constants(node: ast.AST) -> set[str]:
    """Every string literal inside NODE."""
    return {
        n.value
        for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


def _sys_path_target(node: ast.AST) -> ast.AST | None:
    """The expression a `sys.path.<method>(…)` call, `sys.path += …` or
    `sys.path[…] = …` adds — None when NODE is none of these."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if _is_sys_path(node.func.value) and node.args:
            return node.args[-1]
    if isinstance(node, ast.AugAssign) and _is_sys_path(node.target):
        return node.value
    if isinstance(node, ast.Assign) and any(
        _is_sys_path(t) or (isinstance(t, ast.Subscript) and _is_sys_path(t.value))
        for t in node.targets
    ):
        return node.value
    return None


def _import_findings(
    node: ast.Import | ast.ImportFrom,
    area: Path,
    repo: Path,
    where: Path,
    rule: str,
    fix: str,
) -> list[tuple[int, str]]:
    """The imports of NODE that resolve outside lib/ and src/."""
    names = (
        [a.name for a in node.names]
        if isinstance(node, ast.Import)
        else ([node.module] if node.module and not node.level else [])
    )
    out = []
    for name in names:
        found = _outside_roots(name, area, repo)
        if found is not None:
            out.append(
                (
                    node.lineno,
                    (
                        f"WARNING · {where}:{node.lineno} · `{name}` resolves to "
                        f"{found.relative_to(repo)}, outside lib/ and src/ · the stamp does "
                        f"not cover it, a change there moves the number unseen · {rule} · {fix}"
                    ),
                )
            )
    return out


def _path_under_area(expr: ast.expr, area: Path) -> Path | None:
    """`AREA / "scripts" / "01_measure.py"` read as that path; None for any
    other expression (only literal parts after the area's own name)."""
    if isinstance(expr, ast.Name) and expr.id == "AREA":
        return area
    if (
        isinstance(expr, ast.BinOp)
        and isinstance(expr.op, ast.Div)
        and isinstance(expr.right, ast.Constant)
        and isinstance(expr.right.value, str)
    ):
        base = _path_under_area(expr.left, area)
        return base / expr.right.value if base is not None else None
    return None


def _loads_area_file(node: ast.Call, area: Path) -> bool:
    """Does this loader call name, as a literal path, a file the area's stamp
    covers already (`scope_sha.area_files`)? The stamped 02_analyze.py loads
    its own 01_measure.py so; warning on it made every fresh area with a
    model start with a WARNING from labkit's own skeleton (cold Sonnet,
    2026-10-14). A computed path stays a finding."""
    covered = {f.resolve() for f in area_files(area)}
    return any(
        (target := _path_under_area(arg, area)) is not None
        and target.resolve() in covered
        for arg in node.args
    )


def _coverage_in(
    path: Path, area: Path, repo: Path, own: bool
) -> list[tuple[int, str]]:
    """(line, finding) for one file — see stamp_coverage_findings. Dynamic
    loaders and foreign-area paths are read in the area's OWN files only: a
    shared helper's loader is parameterised by its caller, and reporting it
    for every area that imports the helper would be the same line forever."""
    rule = "LAB-019 The stamp covers everything that determines the number"
    fix = (
        "declare the file as a promise's scope (its declared_scope_sha then "
        "sees it) or copy it into the area"
    )
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []  # scope_sha raises on this file already; one loud place
    root = repo.resolve()
    where = (
        path.resolve().relative_to(root)
        if path.resolve().is_relative_to(root)
        else path
    )
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        target = _sys_path_target(node)
        if target is not None:
            names = _str_constants(target)
            if names and names <= set(LOCAL_ROOTS):
                continue  # the stamped template's `sys.path.insert(0, REPO / "lib")`
            out.append(
                (
                    line,
                    (
                        f"WARNING · {where}:{line} · `sys.path` gains "
                        f"{', '.join(sorted(names)) or 'a computed path'} · imports after it may "
                        f"resolve outside lib/ and src/, which the stamp does not follow · {rule} · {fix}"
                    ),
                )
            )
        elif own and isinstance(node, ast.Call) and _call_name(node) in DYNAMIC_LOADERS:
            if _loads_area_file(node, area):
                continue  # the stamped analysis skeleton loading its own 01_measure.py
            out.append(
                (
                    node.lineno,
                    (
                        f"WARNING · {where}:{node.lineno} · `{_call_name(node)}(…)` loads code at "
                        f"run time · the stamp follows `import` lines only, so what this loads "
                        f"changes the number unseen · {rule} · {fix}"
                    ),
                )
            )
        elif own and isinstance(node, ast.Constant) and isinstance(node.value, str):
            foreign = sorted(
                {m for m in AREA_IN_PATH.findall(node.value) if m != area.name}
            )
            if foreign:
                out.append(
                    (
                        node.lineno,
                        (
                            f"WARNING · {where}:{node.lineno} · names area `{foreign[0]}` · a file "
                            f"of another area determines this number, and this area's stamp does "
                            f"not cover it (uniagent 15–17: the script of 14) · {rule} · {fix}"
                        ),
                    )
                )
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            out += _import_findings(node, area, repo, where, rule, fix)
    return out


def stamp_coverage_findings(area: Path, repo: Path) -> list[str]:
    """Code the stamp cannot follow (static evidence, WARNING only): a
    `sys.path` edit that does not point at `lib/` or `src/`, a dynamic
    loader, a path naming another area, an import resolving outside
    `lib/` and `src/`. The stamp (`scope_sha.area_stamp`) walks static
    imports into LOCAL_ROOTS and nothing else; what these lines pull in
    determines the number without any stamp seeing a change to it."""
    out: list[tuple[str, int, str]] = []
    try:
        helpers = imported_repo_helpers(area, repo)
    except SourceError as exc:
        return [unreadable_source(exc)]
    for path in area_files(area):
        out += [(str(path), n, f) for n, f in _coverage_in(path, area, repo, own=True)]
    for path in helpers:
        out += [(str(path), n, f) for n, f in _coverage_in(path, area, repo, own=False)]
    return [
        f for _, _, f in sorted(out)
    ]  # ast.walk is breadth-first; the reader wants source order
