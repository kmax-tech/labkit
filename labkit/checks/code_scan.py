"""code_scan — what an area's script source says, read with `ast`.

The fields a script writes and reads (`scan`, a Load or Store context
told apart, never a regex over text), the keys of the materialized data
(`data_keys`), the producer and consumer stages of an area
(`split_stages`), and the one sentence for a script that does not parse
(`unreadable_source`). The base the code checks read; it imports none of
them.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterable
from pathlib import Path

from labkit.formats.gate import AREA_SLOT
from labkit.formats.gate import GUARANTEED
from labkit.formats.gate import BLOCKER, GateFinding, coded
from labkit.formats.scope_sha import (
    ANALYSIS_GLOB,
    SCRIPT_GLOB,
    area_files,
    SourceError,
)


def name_of(node: ast.expr) -> str | None:
    """A bare name's identifier, None for any other expression — the one
    reader both visitors used to carry (`name_of`, `_var_name`)."""
    return node.id if isinstance(node, ast.Name) else None


def string_constants(nodes: Iterable[ast.expr | None]) -> list[str]:
    """The string literals among `nodes`, in order (a dict's `**spread` key is None)."""
    return [
        n.value
        for n in nodes
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


class _FieldVisitor(ast.NodeVisitor):
    """Reads, writes, and which names this file builds as dicts itself.

    `reads` maps field -> (site, holder): the holder is the variable the
    field was read from, so a read out of a dict the same file assembles can
    be told from a read out of a data row.
    """

    BUILDERS = {"dict", "defaultdict", "Counter", "OrderedDict"}

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.reads: dict[str, tuple[str, str | None]] = {}
        self.writes: set[str] = set()
        self.built: set[str] = set()

    def _site(self, lineno: int) -> str:
        return f"{self.filename}:{lineno}"

    def visit_Assign(self, node: ast.Assign) -> None:
        """`R = {}` / `R = defaultdict(list)` marks R as locally built."""
        val = node.value
        builds = isinstance(val, (ast.Dict, ast.DictComp)) or (
            isinstance(val, ast.Call)
            and isinstance(val.func, ast.Name)
            and val.func.id in self.BUILDERS
        )
        if builds:
            for target in node.targets:
                name = name_of(target)
                if name:
                    self.built.add(name)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            holder = name_of(node.value)
            if isinstance(node.ctx, ast.Load):
                self.reads.setdefault(key.value, (self._site(node.lineno), holder))
            else:  # Store / Del — the field is being produced here
                self.writes.add(key.value)
                if holder:
                    self.built.add(holder)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for k in node.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                self.writes.add(k.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                if func.attr == "get":
                    self.reads.setdefault(
                        first.value,
                        (self._site(node.lineno), name_of(func.value)),
                    )
                elif func.attr in ("setdefault", "pop"):
                    self.writes.add(first.value)
        for kw in node.keywords:  # dict(alpha=1) / Row(alpha=1) build fields
            if kw.arg:
                self.writes.add(kw.arg)
        self.generic_visit(node)


def scan(path: Path) -> _FieldVisitor | None:
    """Parse one file; None if it does not parse (never fail the whole run)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return None
    v = _FieldVisitor(path.name)
    v.visit(tree)
    return v


FIELDISH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _harvest(obj: object, out: set[str], depth: int = 0) -> None:
    """Every dict key at every level, lists included.

    Flat top-level harvesting missed both real shapes in the areas: the
    anchors file keeps its fields inside a `pairs: [...]` list, and reading
    only the outer keys reported `must_contradict` as unwritten (2026-09-10).
    Over-approximating the known set is the safe direction — a field too many
    costs a missed finding the model still catches, a field too few costs a
    false blocker that gets the whole check switched off.
    """
    if depth > 6:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(str(k))
            _harvest(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:20]:
            _harvest(v, out, depth + 1)


def data_keys(area: Path) -> tuple[set[str], list[str]]:
    """Keys of every data row the area has on disk, at every nesting level.

    Every JSON(L) file, not just `data/prepared`: the pipeline is staged, so
    `03_evaluate` legitimately reads fields that `01_generate` invented and
    that never existed in the prepared data. Holding a consumer against the
    prepared file alone reported eight blockers in area 64 and found no
    defect (2026-09-10).

    Several lines per file, not one: a producer may write a `_meta` header
    line first, and harvesting only that reports every real field as missing
    (2026-09-10, area 68).
    """
    keys: set[str] = set()
    seen: list[str] = []
    for pattern in (
        "data/**/*.jsonl",
        "data/**/*.json",
        "output/**/*.jsonl",
        "output/**/*.json",
    ):
        for f in sorted(area.glob(pattern)):
            before = len(keys)
            try:
                with f.open(encoding="utf-8") as fh:
                    if f.suffix == ".json":
                        _harvest(json.load(fh), keys)
                    else:
                        for i, line in enumerate(fh):
                            if i >= 5:
                                break
                            line = line.strip()
                            if line:
                                # a peek at the first five lines of a data
                                # file, never the whole; home: jsonl.objects
                                _harvest(json.loads(line), keys)
            except (OSError, json.JSONDecodeError, RecursionError):
                continue
            if len(keys) > before:
                seen.append(f.name)
    return keys, seen


CONSUMER = re.compile(r"^(0[23]_|analysis)")


def split_stages(area: Path) -> tuple[list[Path], list[Path]]:
    """(producers, consumers) — the numbering IS the pipeline order."""
    scripts = area_files(area, (SCRIPT_GLOB,))
    analysis = area_files(area, (ANALYSIS_GLOB,))
    consumers = [p for p in scripts if CONSUMER.match(p.name)] + analysis
    producers = [p for p in scripts if p not in consumers]
    return producers, consumers


def unreadable_source(exc: SourceError) -> GateFinding:
    """The blocker for a file in the area's scope that is not Python: the
    scan cannot say what the code mentions, so nothing is waved through."""
    return coded(
        BLOCKER,
        None,
        f"{exc} · the code cannot be read, so no check over it holds",
        fix=f"repair or remove the file, then `code-check {AREA_SLOT}`",
        evidence_kind=GUARANTEED,
    )
