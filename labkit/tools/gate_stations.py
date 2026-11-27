"""gate_stations — one checked-in page of every gate that numbers its
stations: per station the functions it calls, the finding sites they can
tell, and the way out each site names.

    python -m labkit.tools.gate_stations [--check]

Writes `docs/gate-stations.md` of the checkout labkit is installed from, or
with `--check` compares the file with what it would write and exits 1 on a
difference. The page is read from the source (`ast` and the comments, as
`tokenize` finds them — a numbered line inside a string is none), never
run, and adds nothing to it:

  - a gate is a function whose body numbers its stations in comments
    (`# 3. intent-check — always`, at least two of them): `finalize_area`,
    `preflight_area`, report-check's `protocol_verdict` and `chain_gaps`,
    the start of a run. A gate that numbers no stations (`protocol-check`,
    `code-check`, `labkit-audit`) is not on the page;
    `docs/checks-overview.md` lists its sites by module
  - a station is one such comment with the comment lines directly below it
    (its title, which states when the station runs) and the code up to the
    next station
  - the functions of a station are the units its code calls or names
    (`check_inventory.unit_references`), in the order of the source; the
    page shows those that tell a finding or reach one, each with the first
    sentence of its docstring
  - the sites of a station are those in its own code and in the functions
    it calls (`at this station`), and those these functions reach through
    the static call graph (`further down`) — the search stops at another
    gate of the page, which the station names instead, and does not pass
    through the gate's own function
  - a site reads as `check_inventory.finding_sites` scans it: grade,
    evidence kind, recorded rule, the constant text of its message and its
    way out (`FindingSite.way_out`)

Its limits, which the page repeats: the call graph resolves names, not
values, so `further down` names sites the station cannot reach at run time
(a function named is followed whether or not the branch that calls it
runs; a class named counts for each of its `__dunder__` methods; a name
given two classes in one function reaches the methods of both). A method
called on an object is followed where annotations tell the object's class
(`method_receivers`); a method called on any other object is missed, and
so are a subclass's override of a method its annotated base has and a
function found by a computed name. A site under
several stations is listed under each; which condition a site holds is
established by reading its function.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import console
from labkit.formats.gate import OPEN_ASSIGNMENT, TECHNICAL_CONTRACT
from labkit.tools.check_inventory import (
    NOT_RECORDED,
    WORDING_WIDTH,
    FindingSite,
    Module,
    UnitReference,
    call_graph,
    entry_points,
    finding_sites,
    one_line,
    reaching_commands,
    read_modules,
    rule_names,
    unit_references,
    units,
)
from labkit.tools.check_overview import write_or_compare

USAGE = "usage: python -m labkit.tools.gate_stations [--check]"
#: the page, relative to the checkout
STATIONS = Path("docs") / "gate-stations.md"
#: a comment that opens a station: its number and the first line of its title
STATION_COMMENT = re.compile(r"# (\d+)\. (.*)")
#: how many station comments make a function a gate of the page: one
#: numbered comment alone is a remark, not a sequence
MIN_STATIONS = 2


@dataclass(frozen=True)
class Station:
    """One numbered station of a gate.

    Attributes:
        number: The number its comment gives it.
        title: The comment's text, its continuation lines joined — what the
            station holds and when it runs.
        line: The comment's line in the gate's source file.
        end_line: The last line of the station's code: the line before the
            next station's comment, or the gate's last line.
    """

    number: int
    title: str
    line: int
    end_line: int


@dataclass(frozen=True)
class Gate:
    """One function that numbers its stations: UNIT (`module.qualname`),
    the source file PATH relative to the package's parent, and its
    STATIONS in source order."""

    unit: str
    path: str
    stations: tuple[Station, ...]


@dataclass(frozen=True)
class StationSites:
    """What one station can tell.

    Attributes:
        own: The sites in the station's own code.
        called: The units the station's code calls or names that tell a
            finding or reach one, in source order.
        called_sites: The sites inside the units of `called`.
        further: The sites the units of `called` reach through the call
            graph, outside themselves — a static estimate.
        gates: The other gates of the page the station reaches; their
            stations are not repeated under it.
    """

    own: tuple[FindingSite, ...]
    called: tuple[str, ...]
    called_sites: tuple[FindingSite, ...]
    further: tuple[FindingSite, ...]
    gates: tuple[str, ...]


def comment_lines(source: str) -> dict[int, str]:
    """Line number → the comment that fills that line of SOURCE, from its
    `#` on: a comment after code on the same line is left out, and so is a
    `#` inside a string.

    Raises:
        tokenize.TokenError, SyntaxError: SOURCE does not tokenize.
    """
    lines = source.splitlines()
    return {
        tok.start[0]: tok.string
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT
        and not lines[tok.start[0] - 1][: tok.start[1]].strip()
    }


def stations_of(node: ast.AST, comments: dict[int, str]) -> tuple[Station, ...]:
    """The stations the function NODE numbers in its comments, COMMENTS
    being its source file's (`comment_lines`); empty when it numbers fewer
    than `MIN_STATIONS`. A station's title runs on through the comment
    lines directly below its number, up to the first line of code or the
    next station."""
    first, last = node.lineno, node.end_lineno  # type: ignore[attr-defined] — a function has both
    opened = [
        (n, m)
        for n in range(first, last + 1)
        if (m := STATION_COMMENT.fullmatch(comments.get(n, "")))
    ]
    if len(opened) < MIN_STATIONS:
        return ()
    numbered = {n for n, _ in opened}
    out = []
    for i, (n, m) in enumerate(opened):
        title = [m.group(2)]
        below = n + 1
        while below in comments and below not in numbered and below <= last:
            title.append(comments[below].removeprefix("#").strip())
            below += 1
        end = opened[i + 1][0] - 1 if i + 1 < len(opened) else last
        out.append(Station(int(m.group(1)), " ".join(title), n, end))
    return tuple(out)


def gates(modules: list[Module], comments: dict[str, dict[int, str]]) -> list[Gate]:
    """Every function of MODULES that numbers its stations, by file and
    line; COMMENTS maps a module's path to its comments (`comment_lines`)."""
    out = []
    for m in modules:
        for unit, node in units(m).items():
            if isinstance(node, ast.ClassDef):
                continue
            stations = stations_of(node, comments[m.path])
            if stations:
                out.append((m.path, stations[0].line, Gate(unit, m.path, stations)))
    return [g for _, _, g in sorted(out, key=lambda t: t[:2])]


def station_sites(
    gate: Gate,
    station: Station,
    references: dict[str, list[UnitReference]],
    graph: dict[str, set[str]],
    sites_in: dict[str, list[FindingSite]],
    gate_units: set[str],
) -> StationSites:
    """What STATION of GATE can tell: REFERENCES and GRAPH are the package's
    (`unit_references`, `call_graph`), SITES_IN maps a unit to its finding
    sites, GATE_UNITS are the units of every gate of the page. Pure."""
    own = tuple(
        s
        for s in sites_in.get(gate.unit, ())
        if station.line <= s.line <= station.end_line
    )
    named: list[str] = []
    for r in sorted(references.get(gate.unit, ()), key=lambda r: r.line):
        if station.line <= r.line <= station.end_line and r.target not in named:
            named.append(r.target)
    # everything a named unit reaches, itself left out; another gate is
    # named, not entered
    reached: dict[str, set[str]] = {}
    for unit in named:
        seen: set[str] = set()
        stack = [] if unit in gate_units else list(graph.get(unit, ()))
        while stack:
            u = stack.pop()
            if u in seen or u == gate.unit:
                continue
            seen.add(u)
            if u not in gate_units:
                stack.extend(graph.get(u, ()))
        reached[unit] = seen
    other_gates = sorted(
        {u for unit in named for u in {unit, *reached[unit]} if u in gate_units}
    )
    called = tuple(
        unit
        for unit in named
        if unit not in gate_units
        and (
            sites_in.get(unit)
            or any(sites_in.get(u) for u in reached[unit] - gate_units)
        )
    )
    further_units = {u for unit in called for u in reached[unit]} - set(called)
    return StationSites(
        own=own,
        called=called,
        called_sites=tuple(s for unit in called for s in sites_in.get(unit, ())),
        further=tuple(
            s for u in sorted(further_units - gate_units) for s in sites_in.get(u, ())
        ),
        gates=tuple(other_gates),
    )


def first_sentence(node: ast.AST | None) -> str:
    """The first sentence of the docstring of the function or class NODE,
    on one line: the text up to the first full stop that ends a sentence
    within the first paragraph, the whole paragraph without one — a colon
    that closes it dropped, since the list it opens is not shown; empty for
    None and for a unit without a docstring."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return ""
    paragraph = " ".join((ast.get_docstring(node) or "").split("\n\n")[0].split())
    end = re.search(r"\.(?= [A-Z`(\[])", paragraph)
    return paragraph[: end.end()] if end else paragraph.removesuffix(":")


def _short_unit(unit: str) -> str:
    """UNIT without the package and layer: `finalize.station_run_code`."""
    return unit.removeprefix("labkit.").split(".", 1)[-1]


def _rows(sites: tuple[FindingSite, ...], rule_names: dict[str, str]) -> list[str]:
    """The table of SITES, by file and line: function, grade, evidence
    kind, rule, message and way out. RULE_NAMES maps a rule id to its
    title."""
    out = [
        "| Function | Grade | Evidence kind | Rule | Tells | Next |",
        "|---|---|---|---|---|---|",
    ]
    for s in sorted(sites, key=lambda s: (s.path, s.line, s.channel)):
        rule = s.assignment
        if rule in rule_names:
            rule = f"{rule} {rule_names[rule]}"
        out.append(
            f"| `{_short_unit(s.unit)}` | {s.grade} | {s.evidence_kind} | {rule} "
            f"| {s.wording or '—'} | {s.way_out or '—'} |"
        )
    return out


def render_stations(
    found: list[Gate],
    told: dict[tuple[str, int], StationSites],
    purposes: dict[str, str],
    commands: dict[str, set[str]],
    rule_names: dict[str, str],
) -> str:
    """The page as markdown: the head with its limits, then per gate of
    FOUND its stations in order. TOLD maps a gate's unit and a station's
    line to what the station can tell, PURPOSES a unit to the first
    sentence of its docstring, COMMANDS a unit to the commands that reach
    it, RULE_NAMES a rule id to its title. Pure."""
    out = [
        "# Gate stations — what each station calls, what it can tell, and the way out",
        "",
        "Generated, do not edit: `python -m labkit.tools.gate_stations` writes "
        "this page from the source, and `tests/test_gate_stations.py` holds it "
        "equal to what the command writes. After a change to a gate's "
        "stations or to a finding site run the command again (`just overview`).",
        "",
        "How to read it. A gate is a function that numbers its stations in "
        "comments; a station's title is that comment, which states when the "
        "station runs. *Calls* are the functions the station's code calls that "
        "tell a finding or reach one, each with the first sentence of its "
        "docstring. *At this station* lists the finding sites in the station's "
        "own code (the *Function* column then names the gate itself) and in "
        "those functions; *further down* lists the sites these functions reach "
        "through the call graph. *Tells* is the constant text of the site's "
        f"message, every value as `{{…}}`, on one line and cut to {WORDING_WIDTH} "
        "characters (`…` marks the cut). *Next* is the way out the site names "
        "as data — its constant text, or in backticks the expression that "
        "builds it; `—` where it names none that way (a BLOCKER always names "
        "one; a warning's message may still say what to do). *Rule* is the "
        "rule assignment the finding records as data: a rule of the standard "
        f"by id and name, `{TECHNICAL_CONTRACT}` (a condition no rule of the "
        f"standard covers), `{OPEN_ASSIGNMENT}` (the rule is not decided yet), "
        "`variable` (the cause passes the assignment in, so the scan cannot "
        f"read it) or `{NOT_RECORDED}` (an exit records none). *Commands "
        "whose code reaches it* counts labkit's console scripts only; a gate "
        "none of them reaches is called by an area's own script.",
        "",
        "Its limits. The call graph resolves names, not values: *further down* "
        "is a static estimate that names sites the station cannot reach at run "
        "time (a function named is followed whether or not the branch that "
        "calls it runs; a class named counts for each of its `__dunder__` "
        "methods; a name given two classes in one function reaches the "
        "methods of both). A method called on an object is followed where "
        "annotations tell the object's class — a parameter, a return value, a "
        "dataclass field; a method called on any other object is missed, and "
        "so are a subclass's override of a method its annotated base has and "
        "a function found by a computed name; a path "
        "back through the gate's own function is not followed. A site under several "
        "stations is listed under each. Which condition a site holds is "
        "established by reading its function; the tests that reach a site "
        "stand in [the checks overview](checks-overview.md). A gate that "
        "numbers no stations (`protocol-check`, `code-check`, `labkit-audit`) "
        "is not on this page. The order of the gates and what each holds: "
        "[The gates in order](architecture.md#the-gates-in-order).",
    ]
    for g in found:
        reached_by = ", ".join(f"`{c}`" for c in sorted(commands.get(g.unit, ())))
        out += [
            "",
            f"## `{_short_unit(g.unit)}` — `{g.path}`",
            "",
            f"{purposes.get(g.unit) or '—'}",
            "",
            f"Commands whose code reaches it: {reached_by or 'no console script'}.",
        ]
        for st in g.stations:
            t = told[(g.unit, st.line)]
            out += [
                "",
                f"### {station_label(g, st)}. {one_line(st.title)}",
            ]
            if t.gates:
                names = ", ".join(f"`{_short_unit(u)}`" for u in t.gates)
                out += ["", f"Runs another gate of this page: {names}."]
            if t.called:
                out += ["", "Calls:", ""]
                out += [
                    f"- `{_short_unit(u)}` — {one_line(purposes.get(u, '')) or '—'}"
                    for u in t.called
                ]
            here = (*t.own, *t.called_sites)
            if here:
                out += ["", "**At this station:**", "", *_rows(here, rule_names)]
            if t.further:
                out += [
                    "",
                    "**Further down (static estimate):**",
                    "",
                    *_rows(t.further, rule_names),
                ]
            if not (here or t.further or t.gates):
                out += ["", "Reaches no finding site."]
    return "\n".join(out) + "\n"


def stations_told(
    modules: list[Module],
    root: Path,
    sites: list[FindingSite],
    graph: dict[str, set[str]],
) -> tuple[list[Gate], dict[tuple[str, int], StationSites]]:
    """The gates of MODULES (their files read under ROOT, the package's
    parent, for the comments) and what each station can tell: TOLD maps a
    gate's unit and a station's line to its `StationSites`. SITES and GRAPH
    are the package's (`finding_sites`, `call_graph`)."""
    comments = {
        m.path: comment_lines((root / m.path).read_text(encoding="utf-8"))
        for m in modules
    }
    found = gates(modules, comments)
    references = unit_references(modules)
    sites_in: dict[str, list[FindingSite]] = defaultdict(list)
    for s in sites:
        sites_in[s.unit].append(s)
    gate_units = {g.unit for g in found}
    told = {
        (g.unit, st.line): station_sites(g, st, references, graph, sites_in, gate_units)
        for g in found
        for st in g.stations
    }
    return found, told


def station_label(gate: Gate, station: Station) -> str:
    """How a page names STATION of GATE: `finalize.finalize_area · 6`."""
    return f"{_short_unit(gate.unit)} · {station.number}"


def stations_page(package_dir: Path) -> str:
    """The page for the package at PACKAGE_DIR, read from its sources, its
    ledger, and the `pyproject.toml` and the code standard beside it."""
    modules = read_modules(package_dir)
    root = package_dir.parent
    graph = call_graph(modules)
    found, told = stations_told(modules, root, finding_sites(modules), graph)
    gate_units = {g.unit for g in found}
    nodes: dict[str, ast.AST] = {}
    for m in modules:
        nodes.update(units(m))
    shown = gate_units | {u for t in told.values() for u in t.called}
    purposes = {u: first_sentence(nodes.get(u)) for u in shown}
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    names = rule_names(package_dir)
    return render_stations(
        found, told, purposes, reaching_commands(graph, entry_points(pyproject)), names
    )


def main(argv: list[str]) -> int:
    """Write the page, or with `--check` compare it: 0, or 1 when the page
    on disk is not what would be written.

    Side effects:
        Without `--check`, creates or overwrites `docs/gate-stations.md`
        of the checkout.
    """
    if argv in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    if argv not in ([], ["--check"]):
        raise console.Refused("gate_stations", USAGE)
    return write_or_compare(
        "gate_stations",
        STATIONS,
        stations_page(PACKAGE_DIR),
        check=argv == ["--check"],
        sources="the source gives",
    )


def cli() -> None:
    """Console entry: `main` with the process's arguments."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
