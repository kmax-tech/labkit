#!/usr/bin/env python3
"""code-check — the mechanical half of the preflight, before the model looks.

The preflight audit (Arbeitsstandard §2.A12) used to do three jobs in one
pass: mechanics, compliance, judgement. The mechanics are the cheap half and
they do not need a model — an id that no script mentions, a field the
analysis reads and no producer writes, a protocol still full of placeholders
are all decidable from the source. Deciding them here leaves the model the
one question worth its cost: does the code MEAN what the registration says.

Three automated checks; the rest are extracted as facts for the
code-check agent (via ``--bundle``), not verified by this command:

  1. **intent ids against the code** (§2.A1a, AUTOMATED). Every registered
     [K1]/[S1]/[W1]/[N1] must appear as a key literal in the area's scripts.
     Report time has `intent-check` for the metrics; before the run the same
     promise goes unchecked exactly when repairing it is still cheap.
  1b. **parser fixtures** (AUTOMATED, 2026-10-05). Every `parse_*` function in
     the area's scripts is exercised by a test under the repo's tests/ — five
     audit findings in three repos were "this parser has no fixture test on
     real raw answers", and a parser fails silently into a wrong number.
  1c. **prompt drift** (AUTOMATED, 2026-10-05). The protocol's prompt block
     is the `PROMPT` constant, not a transcript of it: every line of the
     constant without a `{placeholder}` must appear in the block. The most
     frequent provenance blocker in the audit corpus.

The following are extracted into the audit bundle but NOT checked by this
command — the code-check agent judges them:

  2. **schema contract** (§2.A12, preflight scope). Every field the analysis
     READS must be written somewhere — in the materialized data if it exists,
     otherwise as a write site in the producer's source.
  3. **gate labels** (§2). String comparisons in evaluation code — both
     resolved literals and named constants — extracted as facts for the agent.
  4. **protocol placeholders**. Delegated to `protocol-check`, which owns the
     template contract.

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

# --- gate-label extraction ------------------------------------------------

INFRA_VARS = frozenset({
    "mode", "ext", "suffix", "key", "status", "encoding", "sep",
    "format", "lang", "language", "scheme", "protocol", "method",
    "dtype", "compression", "engine", "__name__",
})

_NOISE_LITERAL = re.compile(
    r"^(\.[a-z]{1,6}"       # file extensions: .json, .csv, .jsonl
    r"|--?"                  # CLI flags: -v, --dry-run
    r"|.*/"                  # paths: data/prepared/x
    r"|https?:)"             # URLs
)


class _ComparisonVisitor(ast.NodeVisitor):
    """String comparisons in evaluation code — facts for the agent.

    Collects both resolved string literals (``answer == "yes"``) and named
    constants (``answer in VALID_ANSWERS``), so the agent can distinguish
    "gate via shared constant" from "gate via hardcoded literals".
    """

    def __init__(self, filename: str, source: str) -> None:
        self.filename = filename
        self._source = source
        self.entries: list[tuple[int, str, str, str]] = []
        self._filtered: list[str] = []
        self._const_defs: dict[str, tuple[int, set[str]]] = {}
        self._imports: dict[str, str] = {}
        self._prepass(source)

    def _prepass(self, source: str) -> None:
        """Collect module-level constant definitions and imports."""
        try:
            tree = ast.parse(source, filename=self.filename)
        except SyntaxError:
            return
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    vals = self._literal_strings(node.value)
                    if vals is not None:
                        self._const_defs[target.id] = (node.lineno, vals)
            elif isinstance(node, ast.ImportFrom) and node.module:
                for alias in (node.names or []):
                    name = alias.asname or alias.name
                    self._imports[name] = node.module

    @staticmethod
    def _literal_strings(node: ast.expr) -> set[str] | None:
        """Extract string elements from a set/list/tuple/dict literal."""
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            out = set()
            for elt in node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    out.add(elt.value)
            return out if out else None
        if isinstance(node, ast.Dict):
            out = set()
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    out.add(k.value)
            return out if out else None
        return None

    @staticmethod
    def _node_label(node: ast.expr) -> str | None:
        """Human-readable label: ``Name`` or ``Name.attr``."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        return None

    @staticmethod
    def _var_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        return None

    def _add(self, lineno: int, var: str, op: str, value_desc: str) -> None:
        if var.lower() in INFRA_VARS:
            self._filtered.append(var)
            return
        self.entries.append((lineno, var, op, value_desc))

    def _add_literal(self, lineno: int, var: str, op: str, val: str) -> None:
        if not val or _NOISE_LITERAL.match(val):
            self._filtered.append(var)
            return
        self._add(lineno, var, op, repr(val))

    def _resolve(self, name: str) -> str:
        """Annotate a named operand with its definition or import source."""
        base = name.split(".")[0]
        if base in self._const_defs:
            defline, vals = self._const_defs[base]
            resolved = ", ".join(repr(v) for v in sorted(vals))
            return f"{name} [Name, resolved: {{{resolved}}}, def. line {defline}]"
        if base in self._imports:
            return f"{name} [Name, imported from {self._imports[base]}]"
        return f"{name} [Name, unresolved]"

    def visit_Compare(self, node: ast.Compare) -> None:
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)):
                op_str = "==" if isinstance(op, ast.Eq) else "!="
                left_var = self._var_name(node.left) or "?"
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                    self._add_literal(node.lineno, left_var, op_str, comparator.value)
                else:
                    label = self._node_label(comparator)
                    if label:
                        self._add(node.lineno, left_var, op_str, self._resolve(label))
                right_var = self._var_name(comparator) or "?"
                if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                    self._add_literal(node.lineno, right_var, op_str, node.left.value)

            elif isinstance(op, (ast.In, ast.NotIn)):
                op_str = "in" if isinstance(op, ast.In) else "not in"
                left_var = self._var_name(node.left) or "?"
                if isinstance(comparator, (ast.Set, ast.List, ast.Tuple)):
                    strs = []
                    for elt in comparator.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            strs.append(elt.value)
                    if strs:
                        if all(_NOISE_LITERAL.match(s) for s in strs):
                            self._filtered.append(left_var)
                        else:
                            vals = ", ".join(repr(s) for s in strs)
                            self._add(node.lineno, left_var, op_str, f"{{{vals}}}")
                else:
                    label = self._node_label(comparator)
                    if label:
                        self._add(node.lineno, left_var, op_str, self._resolve(label))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == "get"
                and len(node.args) >= 2):
            default = node.args[1]
            if isinstance(default, ast.Constant) and isinstance(default.value, str):
                holder = self._var_name(func.value) or "?"
                self._add_literal(node.lineno, holder, ".get default", default.value)
        self.generic_visit(node)


def gate_labels(area: Path) -> str:
    """String comparisons in evaluation code — facts, not findings.

    The prompt↔gate scar (§2, "Was der Prompt verlangt, prüft das Gate —
    aus derselben Konstante") was the most frequent error class (4× in one
    area). The mechanics extract what the gate compares against; the agent
    judges whether it matches the prompt.
    """
    _producers, consumers = split_stages(area)
    all_entries: list[tuple[str, int, str, str, str]] = []
    all_filtered: list[str] = []
    for c in consumers:
        try:
            source = c.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=c.name)
        except (OSError, SyntaxError):
            continue
        v = _ComparisonVisitor(c.name, source)
        v.visit(tree)
        for lineno, var, op, value_desc in v.entries:
            all_entries.append((c.name, lineno, var, op, value_desc))
        all_filtered.extend(v._filtered)

    lines = ["## Gate labels (mechanically extracted — judge them against "
             "the prompt)", ""]
    if all_entries:
        lines.append("Comparisons in evaluation code "
                      "(variable · operator · value · source):")
        for fname, lineno, var, op, value_desc in all_entries:
            lines.append(f"  {fname}:{lineno}  {var} {op} {value_desc}")
    else:
        lines.append("No string comparisons found in evaluation code.")

    if all_filtered:
        vars_summary = ", ".join(sorted(set(all_filtered)))
        lines.append(f"\n({len(all_filtered)} comparison(s) filtered as "
                     f"infrastructure: {vars_summary})")
    lines.append("")
    return "\n".join(lines) + "\n"


def split_stages(area: Path) -> tuple[list[Path], list[Path]]:
    """(producers, consumers) — the numbering IS the pipeline order."""
    scripts = sorted(area.glob("scripts/*.py"))
    analysis = sorted(area.glob("analysis/*.py"))
    consumers = [p for p in scripts if CONSUMER.match(p.name)] + analysis
    producers = [p for p in scripts if p not in consumers]
    return producers, consumers


def check_intent_ids(area: Path, protocol: Path) -> list[str]:
    """Registered promises against the code, before any run exists.

    `intent-check` asks the same question of the metrics at report time, when
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
            f"for this promise and the metrics check fails after the tokens "
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

# Inherited from the severity legend in Arbeitsstandard §2.A12 — the German
# legend there is the minting site; this is its English rendering, stamped
# into every bundle so BOTH audit agents grade findings by the same
# definitions (the code-check agent reads only the bundle and cannot look
# the legend up). Change it there first, then mirror it here.
SEVERITY_LEGEND = (
    "## Severity legend (inherited from Arbeitsstandard §2.A12)\n"
    "\n"
    "- BLOCKER: materially changes a reported number or the validity of\n"
    "  the frozen criterion.\n"
    "- WARNING: a real problem without demonstrated influence on the\n"
    "  current number.\n"
    "- NOTE: failure scenario only under a condition (\"if X is changed,\n"
    "  then ...\") — not triggerable on the code as it stands.\n"
    "\n"
    "The grade says how close the failure scenario sits to the current\n"
    "run; a finding WITHOUT a scenario (which reported number goes wrong,\n"
    "with which input) exists at no grade.\n")

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
             SEVERITY_LEGEND, "\n",
             schema_facts(area), "\n",
             gate_labels(area), "\n"]
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

def find_protocols(area: Path) -> list[Path]:
    """Every protocol in the area, lexicographic — a list, not a first hit.

    The series rule (§2.F, Regel 2) gives every follow-up its own
    `PROTOCOL-s<N>-<slug>.md`, so an area legitimately holds many. Returning
    `sorted(...)[0]` picked one of them wordlessly, and lexicographic order
    is not temporal order: in an area running s1..s13 the pick was always
    s1, never the protocol just built. A green check against the wrong
    protocol is worse than no check, so the caller must choose (2026-09-26).
    """
    return sorted(area.glob("PROTOCOL-*.md"))


def find_repo(area: Path) -> Path:
    for parent in [area] + list(area.parents):
        if (parent / ".git").exists():
            return parent
    return area


PARSE_DEF = re.compile(r"^\s*def (parse_\w+)\s*\(", re.M)
PROMPT_NAME = re.compile(r"^PROMPT(_[A-Z0-9_]+)?$")
PROMPT_FIELD = re.compile(r"^\s*[-*]\s*\*{0,2}prompt\b", re.I)
FENCE = re.compile(r"^\s*```")
PLACEHOLDER_IN_PROMPT = re.compile(r"\{[^{}]*\}")


def check_parser_fixtures(area: Path, repo: Path) -> list[str]:
    """Every `parse_*` in the area's scripts is named in some test file."""
    scripts = sorted((area / "scripts").glob("*.py")) if (area / "scripts").is_dir() else []
    parsers: dict[str, Path] = {}
    for sp in scripts:
        for m in PARSE_DEF.finditer(sp.read_text(encoding="utf-8")):
            parsers.setdefault(m.group(1), sp)
    if not parsers:
        return []
    tests_dir = repo / "tests"
    test_text = "\n".join(t.read_text(encoding="utf-8")
                          for t in sorted(tests_dir.glob("test_*.py"))) if tests_dir.is_dir() else ""
    findings = []
    for name, sp in sorted(parsers.items()):
        if not re.search(rf"\b{re.escape(name)}\b", test_text):
            findings.append(
                f"BLOCKER · {sp.name} · {name}() has no test under {tests_dir.name}/ · "
                f"a parser fails silently into a wrong number · give it a fixture "
                f"with real raw answers (§2.A13, 2026-10-05)")
    return findings


def _string_of(node: ast.AST) -> str | None:
    """The text of a string constant, incl. implicit and `+` concatenation."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _string_of(node.left), _string_of(node.right)
        return a + b if a is not None and b is not None else None
    if isinstance(node, ast.JoinedStr):
        return None   # an f-string renders at run time; nothing to hold the block to
    return None


def prompt_constants(area: Path) -> dict[str, str]:
    """`PROMPT` / `PROMPT_<VARIANT>` string constants across the area's scripts."""
    out: dict[str, str] = {}
    scripts = sorted((area / "scripts").glob("*.py")) if (area / "scripts").is_dir() else []
    for sp in scripts:
        try:
            tree = ast.parse(sp.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and PROMPT_NAME.match(node.targets[0].id):
                text = _string_of(node.value)
                if text is not None:
                    out[node.targets[0].id] = text
    return out


def prompt_blocks(protocol: Path) -> list[str]:
    """The fenced blocks that follow a `Prompt` field in the protocol."""
    lines = protocol.read_text(encoding="utf-8").splitlines()
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        if PROMPT_FIELD.match(lines[i]):
            j = i + 1
            while j < len(lines) and j <= i + 3 and not FENCE.match(lines[j]):
                j += 1
            if j < len(lines) and FENCE.match(lines[j]):
                k = j + 1
                while k < len(lines) and not FENCE.match(lines[k]):
                    k += 1
                blocks.append("\n".join(lines[j + 1:k]))
                i = k
        i += 1
    return blocks


def check_prompt_drift(area: Path, protocol: Path) -> list[str]:
    """The protocol's prompt block against the PROMPT constant(s).

    Compared line by line: every non-empty line of the constant that carries
    no `{placeholder}` must appear, stripped, in some prompt block. A block
    rendered with real data passes; a transcript that drifted does not."""
    consts = prompt_constants(area)
    blocks = [b for b in prompt_blocks(protocol) if "<" not in b.splitlines()[0][:1]] \
        if consts else []
    blocks = [b for b in blocks if not b.strip().startswith("<")]
    if not consts or not blocks:
        return []
    have = {ln.strip() for b in blocks for ln in b.splitlines() if ln.strip()}
    findings = []
    for name, text in sorted(consts.items()):
        fixed = [ln.strip() for ln in text.splitlines()
                 if ln.strip() and not PLACEHOLDER_IN_PROMPT.search(ln)]
        missing = [ln for ln in fixed if ln not in have]
        if fixed and missing:
            findings.append(
                f"BLOCKER · {protocol.name} · prompt block drifted from {name}: "
                f"{len(missing)} of {len(fixed)} fixed line(s) missing, e.g. "
                f"{missing[0][:60]!r} · paste the rendered `--show` output, not a "
                f"transcript (§2.A4, 2026-10-05)")
    return findings


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: code-check <AREA> [--protocol FILE] [--bundle FILE]")
        print("  --protocol FILE  the PROTOCOL-*.md to check against "
              "(required once the area holds more than one)")
        print("  --bundle FILE    pack sources + schema facts + gate labels "
              "for the audit agent")
        return 0 if argv else 2

    area = Path(argv[0])
    bundle_to = None
    protocol_arg = None
    rest = argv[1:]
    while rest:
        if rest[0] in ("--bundle", "--protocol") and len(rest) >= 2:
            if rest[0] == "--bundle":
                bundle_to = Path(rest[1])
            else:
                protocol_arg = Path(rest[1])
            rest = rest[2:]
            continue
        print(f"code-check: unexpected argument {rest[0]!r}")
        return 2

    if not area.is_dir():
        print(f"code-check: no such area: {area}")
        return 2

    protocols = find_protocols(area)
    if protocol_arg is not None:
        if not protocol_arg.is_file():
            print(f"code-check: no such protocol: {protocol_arg}")
            return 2
        protocol = protocol_arg
    elif not protocols:
        print(f"code-check: no PROTOCOL-*.md in {area}")
        return 2
    elif len(protocols) > 1:
        # Fail closed, never pick: see find_protocols.
        print(f"code-check: {len(protocols)} protocols in {area} — name one "
              f"with --protocol FILE:")
        for p in protocols:
            print(f"  {p}")
        return 2
    else:
        protocol = protocols[0]

    repo = find_repo(area)
    findings = (check_intent_ids(area, protocol)
                + check_parser_fixtures(area, repo)
                + check_prompt_drift(area, protocol))
    for f in findings:
        print(f)

    if bundle_to is not None:
        n = write_bundle(area, find_repo(area), protocol, bundle_to)
        print(f"bundle: {n} file(s) -> {bundle_to} "
              f"({bundle_to.stat().st_size // 1024} KB)")

    blockers = sum(1 for f in findings if f.startswith("BLOCKER"))
    warnings = sum(1 for f in findings if f.startswith("WARNING"))
    parts = [f"intent-ids: {blockers} blocker(s), {warnings} warning(s) "
             f"(incl. parser fixtures, prompt drift)"]
    if bundle_to is not None:
        parts.append("schema + gate labels + placeholders extracted into "
                     "the bundle for the code-check agent")
    else:
        parts.append("schema, gate labels, placeholders: not checked "
                     "(need --bundle for the code-check agent)")
    print(" — ".join(parts))
    return 1 if findings else 0


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
