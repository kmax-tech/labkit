"""gate_label_scan — the string comparisons in evaluation code, as facts.

Every comparison against a string — a resolved literal or a named
constant — in the area's evaluation scripts, with its line, minus the
infrastructure variables and noise literals that are no gate label. The
code-check agent holds them against the prompt (LAB-038 What the prompt
demands); this module extracts and never judges.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from labkit.checks.code_scan import name_of, string_constants, split_stages


INFRA_VARS = frozenset(
    {
        "mode",
        "ext",
        "suffix",
        "key",
        "status",
        "encoding",
        "sep",
        "format",
        "lang",
        "language",
        "scheme",
        "protocol",
        "method",
        "dtype",
        "compression",
        "engine",
        "__name__",
    }
)


_NOISE_LITERAL = re.compile(
    r"^(\.[a-z]{1,6}"  # file extensions: .json, .csv, .jsonl
    r"|--?"  # CLI flags: -v, --dry-run
    r"|.*/"  # paths: data/prepared/x
    r"|https?:)"  # URLs
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
                for alias in node.names or []:
                    name = alias.asname or alias.name
                    self._imports[name] = node.module

    @staticmethod
    def _literal_strings(node: ast.expr) -> set[str] | None:
        """The string elements of a set/list/tuple literal, or a dict's string keys."""
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            return set(string_constants(node.elts)) or None
        if isinstance(node, ast.Dict):
            return set(string_constants(node.keys)) or None
        return None

    @staticmethod
    def _node_label(node: ast.expr) -> str | None:
        """Human-readable label: ``Name`` or ``Name.attr``."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
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

    def visit_Compare(self, node: ast.Compare) -> None:  # noqa: C901 complexity baseline 2026-10-08
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)):
                op_str = "==" if isinstance(op, ast.Eq) else "!="
                left_var = name_of(node.left) or "?"
                if isinstance(comparator, ast.Constant) and isinstance(
                    comparator.value, str
                ):
                    self._add_literal(node.lineno, left_var, op_str, comparator.value)
                else:
                    label = self._node_label(comparator)
                    if label:
                        self._add(node.lineno, left_var, op_str, self._resolve(label))
                right_var = name_of(comparator) or "?"
                if isinstance(node.left, ast.Constant) and isinstance(
                    node.left.value, str
                ):
                    self._add_literal(node.lineno, right_var, op_str, node.left.value)

            elif isinstance(op, (ast.In, ast.NotIn)):
                op_str = "in" if isinstance(op, ast.In) else "not in"
                left_var = name_of(node.left) or "?"
                if isinstance(comparator, (ast.Set, ast.List, ast.Tuple)):
                    strs = string_constants(comparator.elts)
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
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and len(node.args) >= 2
        ):
            default = node.args[1]
            if isinstance(default, ast.Constant) and isinstance(default.value, str):
                holder = name_of(func.value) or "?"
                self._add_literal(node.lineno, holder, ".get default", default.value)
        self.generic_visit(node)


def gate_labels(area: Path) -> str:
    """String comparisons in evaluation code — facts, not findings.

    The prompt↔gate scar (LAB-038 What the prompt demands) was the most frequent error class (4× in one
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

    lines = [
        "## Gate labels (mechanically extracted — judge them against the prompt)",
        "",
    ]
    if all_entries:
        lines.append(
            "Comparisons in evaluation code (variable · operator · value · source):"
        )
        for fname, lineno, var, op, value_desc in all_entries:
            lines.append(f"  {fname}:{lineno}  {var} {op} {value_desc}")
    else:
        lines.append("No string comparisons found in evaluation code.")

    if all_filtered:
        vars_summary = ", ".join(sorted(set(all_filtered)))
        lines.append(
            f"\n({len(all_filtered)} comparison(s) filtered as "
            f"infrastructure: {vars_summary})"
        )
    lines.append("")
    return "\n".join(lines) + "\n"
