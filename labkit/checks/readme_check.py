"""readme_check — whether an area's README can lead a reader.

Lines still holding a stamped `<…>` placeholder (`readme_placeholders`),
and the route block between its markers: present, naming the protocol
and every station a reader takes after it (`readme_route`). The README
points; it copies no number, and nothing here writes it — the stamp
does. Read-only.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from labkit.formats.gate import (
    GUARANTEED,
    OPEN_RULE,
    WARNING,
    GateFinding,
    RuleAssignment,
    cited_rule,
)
from labkit.formats.scope_sha import SCRIPT_GLOB, area_files, readme_text, parse_source


# the stamp's blanks may wrap lines; an HTML comment (`<!-- labkit:route -->`)
# is a marker, not a blank
_PLACEHOLDER = re.compile(r"<(?!!--)[^<>]{3,}>")


def readme_placeholders(area: Path) -> list[str]:
    """Lines of the area's README.md still holding a stamped `<…>` placeholder.
    A README that still carries the stamp's blanks tells a reader nothing and
    looks as if it did. No README: nothing.
    Static evidence: the pattern also matches an `<…>` the author wrote in
    prose outside a code span."""
    text = readme_text(area)
    if text is None:
        return []
    # a `<path>/<id>` inside a code span or a fenced block is an example, not a
    # blank
    scan = re.sub(
        r"```.*?```|`[^`\n]*`",
        lambda m: " " * len(m.group()),
        text,
        flags=re.S,
    )
    out = []
    for m in _PLACEHOLDER.finditer(scan):
        line = text.count("\n", 0, m.start()) + 1
        out.append(f"README.md:{line}: {' '.join(m.group(0).split())[:70]}")
    return out


ROUTE_START = "<!-- labkit:route -->"


ROUTE_END = "<!-- /labkit:route -->"


#: What the README's route must point to: the stations a reader takes after
#: the protocol — which run (`runlog`), which values (`labkit-params`), where
#: the ids are decided, the proof (CODE-016 The experiment area reconstructs
#: itself). The README points; it copies no question, answer, run id or
#: threshold — each has its one home, and a copy goes stale.
ROUTE_STATIONS = (
    "runlog",
    "labkit-params",
    "scripts/01_measure.py:evaluate_rows",
    "config.json",
)


CODE_016 = cited_rule("CODE-016 The experiment area reconstructs itself")


def _route_warning(text: str, rule: RuleAssignment) -> GateFinding:
    return GateFinding(WARNING, text, rule=rule, evidence_kind=GUARANTEED)


def readme_route(area: Path, protocol_name: str) -> list[GateFinding]:
    """Why the README's route block cannot lead a reader, each a warning:
    no block between the markers, the protocol or a station not named, or
    `scripts/01_measure.py` without an `evaluate_rows`. No README: nothing.
    The block is checked, never written — finalize reads only; the stamp
    writes it. A script that is missing or defines no `evaluate_rows`
    records CODE-016 The experiment area reconstructs itself; the block and
    its stations record an open assignment — no rule names them.

    Raises:
        SourceError: `scripts/01_measure.py` does not parse — the gate
            reports it as a blocker (`code_scan.unreadable_source`).
    """
    text = readme_text(area)
    if text is None:
        return []
    start, end = text.find(ROUTE_START), text.find(ROUTE_END)
    if start < 0 or end < start:
        return [
            _route_warning(
                f"README.md: no {ROUTE_START} … {ROUTE_END} block — the route "
                f"(protocol · runlog · labkit-params · evaluate_rows · config.json) "
                f"is what a reader opens first",
                OPEN_RULE,
            )
        ]
    block = text[start:end]
    out = []
    if protocol_name not in block:
        out.append(
            _route_warning(f"README.md route: does not name {protocol_name}", OPEN_RULE)
        )
    for station in ROUTE_STATIONS:
        if station not in block:
            out.append(
                _route_warning(f"README.md route: does not name {station}", OPEN_RULE)
            )
    script = area / "scripts" / "01_measure.py"
    if script not in area_files(area, (SCRIPT_GLOB,)):
        out.append(
            _route_warning(
                "README.md route: scripts/01_measure.py does not exist", CODE_016
            )
        )
    elif not any(
        isinstance(n, ast.FunctionDef) and n.name == "evaluate_rows"
        for n in parse_source(script).body
    ):
        out.append(
            _route_warning(
                "README.md route: scripts/01_measure.py defines no evaluate_rows",
                CODE_016,
            )
        )
    return out
