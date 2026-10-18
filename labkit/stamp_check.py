"""stamp_check — the stamped skeleton, held to its instrument.

    python -m labkit.stamp_check <AREA> [--protocol FILE]

Two exact facts of a stamped area, read from its code (plan II, the stamp
check, 2026-10-17); what the code MEANS stays with the agent audit:

  1. The measure script asks a model exactly when the head says so.
     `instrument = "apply"`: `scripts/01_measure.py` imports `labkit.llm`
     and calls `llm.complete` or `llm.complete_many` — an apply protocol
     whose script asks no model is a finding. `fit` or `count`: the
     script does not import `labkit.llm` — a model call in a measurement
     the protocol declares model-free is a finding (a model that renders
     features belongs to `00_prepare.py`; a model that answers the rows
     is `instrument = "apply"`).
  2. The stamped contract tests survive. The instrument's test template
     stamps the resolution check as named test functions
     (`skeletons.contract_tests`); every one still stands in the area's
     test file, not under `pytest.mark.skip`, `skipif` or `xfail`. A
     deleted, renamed or skipped contract test is the finding — before it
     is a red one, and before `evaluate_rows` is rewritten past it.

Why: nine of nine pilot attempts were estimators that got the model
skeleton and rebuilt it, and nothing mechanical saw the rebuild
(labkit-paper 09, 2026-10-16). With the instrument in the head (0.20) an
agent that finds no instrument fits stops (AGENTS template, step 1); one
that bends a skeleton instead meets this check. Tier: guaranteed — every
sentence says what the AST says, nothing more. Runs as a station of
`preflight` (a blocker at `frozen = true`, a warning before) and in
`claude-hook post-change` on a changed script or area test.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from labkit import protocol_block
from labkit.repo import area_test_files, choose_protocol, layout_root
from labkit.skeletons import MEASURE_SCRIPT, SKELETONS, contract_tests

LLM_MODULE = "labkit.llm"
#: the functions that ask a model; `llm.provenance` or `llm.retries` ask none
LLM_CALLS = ("complete", "complete_many")
#: a decorator that keeps a test from running
SKIP_MARKS = ("skip", "skipif", "xfail")


@dataclass(frozen=True)
class LlmUse:
    """How a script uses `labkit.llm`: imported at all, and asked."""

    imported: bool
    called: bool


def _dotted(node: ast.AST) -> str | None:
    """`llm.complete` → "llm.complete", `labkit.llm.complete` likewise, a bare
    name as is; None for anything that is not a name chain."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return None if head is None else f"{head}.{node.attr}"
    return None


def _llm_bindings(tree: ast.AST) -> tuple[set[str], set[str], bool]:
    """(local names bound to the module, completion functions imported by
    name, anything else of it imported) — every import form of labkit.llm."""
    modules: set[str] = set()
    functions: set[str] = set()
    other = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and not node.level:
            for a in node.names:
                if node.module == "labkit" and a.name == "llm":
                    modules.add(a.asname or a.name)
                elif node.module == LLM_MODULE and a.name in LLM_CALLS:
                    functions.add(a.asname or a.name)
                elif node.module == LLM_MODULE:
                    other = True
        elif isinstance(node, ast.Import):
            modules.update(
                a.asname or a.name for a in node.names if a.name == LLM_MODULE
            )
    return modules, functions, other


def _asks_a_model(tree: ast.AST, modules: set[str], functions: set[str]) -> bool:
    """Is a completion function called through one of the bound names?"""
    for node in ast.walk(tree):
        target = _dotted(node.func) if isinstance(node, ast.Call) else None
        if target is None:
            continue
        head, _, func = target.rpartition(".")
        if (func in LLM_CALLS and head in modules) or (
            not head and target in functions
        ):
            return True
    return False


def llm_use(source: str) -> LlmUse:
    """Does SOURCE import `labkit.llm` — `from labkit import llm`, `import
    labkit.llm`, `from labkit.llm import complete`, aliases included — and
    call one of its completion functions? Raises SyntaxError; the caller
    names the file."""
    tree = ast.parse(source)
    modules, functions, other = _llm_bindings(tree)
    return LlmUse(
        bool(modules or functions or other), _asks_a_model(tree, modules, functions)
    )


def test_functions(source: str) -> dict[str, list[str]]:
    """Every test function in SOURCE (at module level or in a class) → its
    decorators as dotted names (`pytest.mark.skip`, `pytest.mark.skipif`)."""
    out: dict[str, list[str]] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name.startswith("test_")
        ):
            out[node.name] = [
                _dotted(d.func if isinstance(d, ast.Call) else d) or ""
                for d in node.decorator_list
            ]
    return out


def script_findings(area: Path, instrument: str) -> list[str]:
    """Fact 1 for AREA's measure script under INSTRUMENT."""
    script = area / MEASURE_SCRIPT
    if not script.is_file():
        return [
            f"no {MEASURE_SCRIPT} — the stamped measure skeleton is gone; "
            f"the stamp check has nothing to hold to the instrument"
        ]
    try:
        use = llm_use(script.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"{MEASURE_SCRIPT}:{exc.lineno}: not valid Python — {exc.msg}"]
    if SKELETONS[instrument].asks_a_model:
        if not use.imported:
            return [
                f'{MEASURE_SCRIPT}: instrument = "apply", but the script never '
                f"imports labkit.llm — an apply protocol whose script asks no model "
                f"(a model is asked through labkit.llm, never through an endpoint "
                f"of the script's own)"
            ]
        if not use.called:
            return [
                f'{MEASURE_SCRIPT}: instrument = "apply", but the script never '
                f"calls llm.complete or llm.complete_many — the import alone asks "
                f"no model"
            ]
        return []
    if use.imported:
        return [
            f"{MEASURE_SCRIPT} imports labkit.llm, but the head says instrument = "
            f'"{instrument}" — a model call in a measurement the protocol declares '
            f"model-free; a model that renders features belongs to "
            f'scripts/00_prepare.py, a model that answers the rows is instrument = "apply"'
        ]
    return []


def contract_findings(files: list[Path], instrument: str) -> list[str]:
    """Fact 2: the stamped contract tests missing or skipped in FILES —
    nothing without a file (preflight names a missing test file itself)."""
    if not files:
        return []
    found: dict[str, list[str]] = {}
    out: list[str] = []
    for f in files:
        try:
            found.update(test_functions(f.read_text(encoding="utf-8")))
        except SyntaxError as exc:
            out.append(f"{f.name}:{exc.lineno}: not valid Python — {exc.msg}")
    if out:
        return out
    where = ", ".join(f.name for f in files)
    for name in contract_tests(instrument):
        if name not in found:
            out.append(
                f"{where}: the stamped contract test `{name}` is gone — renamed or "
                f"deleted; the resolution check the stamp wrote no longer holds "
                f"`evaluate_rows` (restore it, or rename it back)"
            )
            continue
        skipped = [d for d in found[name] if d.rsplit(".", 1)[-1] in SKIP_MARKS]
        if skipped:
            out.append(
                f"{where}: the stamped contract test `{name}` is skipped "
                f"(@{skipped[0]}) — a skipped contract test holds nothing"
            )
    return out


def stamp_findings(
    area: Path, head: protocol_block.Head, repo: Path | None = None
) -> list[str]:
    """Every finding of the stamp check for AREA under HEAD, each a sentence
    naming the file and the fact; empty when the stamp holds. A head whose
    instrument is still the placeholder yields nothing: protocol-check
    names that gap, and there is no instrument to hold the code to."""
    if head.instrument is None:
        return []
    repo = layout_root(area) if repo is None else repo
    _, files = area_test_files(area, repo)
    return script_findings(area, head.instrument) + contract_findings(
        files, head.instrument
    )


def main(argv: list[str]) -> int:
    """`python -m labkit.stamp_check <AREA>`: the findings, one per line;
    exit 1 with any, 2 when no protocol or head can be read."""
    ap = argparse.ArgumentParser(
        prog="python -m labkit.stamp_check",
        description=(__doc__ or "").splitlines()[0],
    )
    ap.add_argument("area", type=Path)
    ap.add_argument(
        "--protocol", type=Path, help="the protocol, in an area holding several"
    )
    args = ap.parse_args(argv)
    area = args.area.resolve()
    protocol = choose_protocol(area, args.protocol, "stamp-check")
    if protocol is None:
        return 2
    try:
        head = protocol_block.head(protocol.read_text(encoding="utf-8"))
    except protocol_block.BlockError as exc:
        print(f"stamp-check: {protocol.name}: {exc}")
        return 2
    found = stamp_findings(area, head)
    for line in found:
        print(f"stamp-check: {line}")
    if not found:
        print(
            f"stamp-check: {area.name}: the stamp holds its instrument"
            + (f" ({head.instrument})" if head.instrument else " — none set yet")
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
