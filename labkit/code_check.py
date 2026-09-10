#!/usr/bin/env python3
"""code-check — the mechanical half of the preflight, before the model looks.

The preflight audit (Arbeitsstandard §2.A12) used to do three jobs in one
pass: mechanics, compliance, judgement. The mechanics are the cheap half and
they do not need a model — an id that no script mentions, a field the
analysis reads and no producer writes, a protocol still full of placeholders
are all decidable from the source. Deciding them here leaves the model the
one question worth its cost: does the code MEAN what the registration says.

Three checks, all decidable, none of them a judgement:

  1. **intent ids against the code** (§2.A1a). Every registered [K1]/[S1]/
     [W1]/[N1] must appear as a key literal in the area's scripts. Report
     time has `intent-check` for the ledger; before the run the same promise
     goes unchecked exactly when repairing it is still cheap.
  2. **schema contract** (§2.A12, preflight scope). Every field the analysis
     READS must be written somewhere — in the materialized data if it exists,
     otherwise as a write site in the producer's source. A field that is read
     and never written is a KeyError at evaluation time, after the tokens
     were spent.
  3. **protocol placeholders**. Delegated to `protocol-check`, which owns the
     template contract; code-check only reports that it ran and what it said.

Reads and writes are told apart with `ast`, not with a regex: `row["x"]` in
a Load context is a read, in a Store context it is a write, and no pattern
over text gets that right reliably.

Usage:
    code-check <AREA>                    # run the mechanical checks
    code-check <AREA> --bundle FILE      # additionally write the audit bundle
                                         # (protocol + scripts + imported
                                         #  repo-local lib modules) for the
                                         #  code-check agent to read in one go

Exit code 1 if any check reports a finding, 2 on usage errors.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

try:
    from labkit.intent_check import ID_IN_PROTOCOL, code_ids
except ImportError:  # vendored flat copies (student repos)
    from intent_check import ID_IN_PROTOCOL, code_ids  # type: ignore


# --- source analysis ------------------------------------------------------

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

    @staticmethod
    def _name_of(node: ast.expr) -> str | None:
        return node.id if isinstance(node, ast.Name) else None

    def visit_Assign(self, node: ast.Assign) -> None:
        """`R = {}` / `R = defaultdict(list)` marks R as locally built."""
        val = node.value
        builds = isinstance(val, (ast.Dict, ast.DictComp)) or (
            isinstance(val, ast.Call)
            and isinstance(val.func, ast.Name)
            and val.func.id in self.BUILDERS)
        if builds:
            for target in node.targets:
                name = self._name_of(target)
                if name:
                    self.built.add(name)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            holder = self._name_of(node.value)
            if isinstance(node.ctx, ast.Load):
                self.reads.setdefault(
                    key.value, (self._site(node.lineno), holder))
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
                        (self._site(node.lineno), self._name_of(func.value)))
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
    for pattern in ("data/**/*.jsonl", "data/**/*.json",
                    "output/**/*.jsonl", "output/**/*.json"):
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
                                _harvest(json.loads(line), keys)
            except (OSError, json.JSONDecodeError, RecursionError):
                continue
            if len(keys) > before:
                seen.append(f.name)
    return keys, seen


CONSUMER = re.compile(r"^(0[23]_|analysis)")


def split_stages(area: Path) -> tuple[list[Path], list[Path]]:
    """(producers, consumers) — the numbering IS the pipeline order."""
    scripts = sorted(area.glob("scripts/*.py"))
    analysis = sorted(area.glob("analysis/*.py"))
    consumers = [p for p in scripts if CONSUMER.match(p.name)] + analysis
    producers = [p for p in scripts if p not in consumers]
    return producers, consumers


def check_intent_ids(area: Path, protocol: Path) -> list[str]:
    """Registered promises against the code, before any run exists.

    `intent-check` asks the same question of the ledger at report time, when
    the tokens are already spent. Here the answer is still cheap.
    """
    registered = {m.group(1).lower()
                  for m in ID_IN_PROTOCOL.finditer(
                      protocol.read_text(encoding="utf-8"))}
    if not registered:
        return []
    in_code = code_ids(area)
    unmistakable = code_ids(area, suffixed_only=True)
    findings = []
    for i in sorted(registered - set(in_code)):
        findings.append(
            f"BLOCKER · {protocol.name} · [{i.upper()}] is registered, but no "
            f"script mentions a '{i}'/'{i}_*' key · the run reports nothing "
            f"for this promise and the ledger check fails after the tokens "
            f"are spent · §2.A1a · implement the key or drop the id")
    for i in sorted(set(unmistakable) - registered):
        findings.append(
            f"WARNING · {unmistakable[i][0]} · key '{i}_*' is in the intent-id "
            f"namespace, but the protocol registers no [{i.upper()}] · a "
            f"number gets reported that nobody registered · §2.A1a · register "
            f"it or rename the key")
    return findings


def schema_facts(area: Path) -> str:
    """The field table — facts for the agent, not findings of our own.

    Three calibration rounds (2026-09-10, areas 60-73) failed to make this a
    checker. Every narrowing removed one false-blocker class and left the
    next: fields staged into files a later step writes, a `fan_v1.jsonl` that
    is simply not on disk any more, a consumer that reads across area
    boundaries (72 reads 71's prepared data). Deciding whether a read is
    satisfied needs the data FLOW, and that is exactly what a model reads
    well and a parser does not.

    So the mechanics stop at the facts: which fields the analysis reads, and
    which keys the area's data rows actually carry. The agent holds them
    against each other — with the lookup work already done, which is the part
    that used to cost it minutes of grepping.
    """
    producers, consumers = split_stages(area)
    known, files = data_keys(area)
    lines = ["## Schema facts (mechanically extracted — judge them, they are "
             "not findings)", ""]
    lines.append(f"Data keys present in the area's own JSON(L) rows "
                 f"({', '.join(files) if files else 'no data materialized yet'}):")
    lines.append("  " + (", ".join(sorted(known)) if known else "—"))
    lines.append("")
    lines.append("Fields read by the analysis stage, with the variable read "
                 "from — a name absent from the list above is either staged "
                 "by an earlier step, read from another area, or a defect:")
    for c in consumers:
        v = scan(c)
        if v is None:
            lines.append(f"  {c.name}: DOES NOT PARSE")
            continue
        unexplained = sorted(
            f for f, (_, holder) in v.reads.items()
            if f not in known and f not in v.writes
            and FIELDISH.match(f) and holder and holder not in v.built)
        if unexplained:
            for f in unexplained:
                site, holder = v.reads[f]
                lines.append(f"  {site}: '{f}' from `{holder}` — not in the "
                             f"area's data")
        else:
            lines.append(f"  {c.name}: every read field is present in the "
                         f"area's data")
    return "\n".join(lines) + "\n"


# --- the bundle -----------------------------------------------------------

LIB_IMPORT = re.compile(r"^\s*(?:from|import)\s+(\w+)", re.M)


def imported_lib(area: Path, repo: Path) -> list[Path]:
    """Repo-local lib modules the area's code imports (§2.A12 scope)."""
    libdir = repo / "lib"
    if not libdir.is_dir():
        return []
    names = set()
    for p in sorted(area.glob("scripts/*.py")) + sorted(area.glob("analysis/*.py")):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        names |= {m.group(1) for m in LIB_IMPORT.finditer(text)}
    return [libdir / f"{n}.py" for n in sorted(names)
            if (libdir / f"{n}.py").is_file()]


def write_bundle(area: Path, repo: Path, protocol: Path, out: Path) -> int:
    parts = [f"# AUDIT BUNDLE · area {area.name}\n\n",
             schema_facts(area), "\n"]
    files = [protocol]
    files += sorted(area.glob("scripts/*.py")) + sorted(area.glob("analysis/*.py"))
    files += imported_lib(area, repo)
    for f in files:
        try:
            body = f.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            label = f.relative_to(repo)
        except ValueError:
            label = f
        parts.append(f"\n===== FILE: {label} =====\n{body}")
    out.write_text("".join(parts), encoding="utf-8")
    return len(files)


# --- cli ------------------------------------------------------------------

def find_protocol(area: Path) -> Path | None:
    hits = sorted(area.glob("PROTOCOL-*.md"))
    return hits[0] if hits else None


def find_repo(area: Path) -> Path:
    for parent in [area] + list(area.parents):
        if (parent / ".git").exists():
            return parent
    return area


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: code-check <AREA> [--bundle FILE]")
        return 0 if argv else 2

    area = Path(argv[0])
    bundle_to = None
    if len(argv) >= 3 and argv[1] == "--bundle":
        bundle_to = Path(argv[2])
    elif len(argv) > 1:
        print(f"code-check: unexpected argument {argv[1]!r}")
        return 2
    if not area.is_dir():
        print(f"code-check: no such area: {area}")
        return 2
    protocol = find_protocol(area)
    if protocol is None:
        print(f"code-check: no PROTOCOL-*.md in {area}")
        return 2

    findings = check_intent_ids(area, protocol)
    for f in findings:
        print(f)

    if bundle_to is not None:
        n = write_bundle(area, find_repo(area), protocol, bundle_to)
        print(f"bundle: {n} file(s) -> {bundle_to} "
              f"({bundle_to.stat().st_size // 1024} KB)")

    blockers = sum(1 for f in findings if f.startswith("BLOCKER"))
    warnings = sum(1 for f in findings if f.startswith("WARNING"))
    print(f"mechanics: {blockers} blocker(s), {warnings} warning(s) "
          f"— judgement (does the code MEAN the registration?) is the "
          f"agent's half")
    return 1 if findings else 0


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
