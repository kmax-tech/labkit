"""test_inventory — which test of labkit's suite reaches which finding site,
and through which layer it entered labkit.

    python -m labkit.tools.test_inventory [--out FILE]

The basis for a clear test model: whether a rule's check is tested on its
own or only inside a scenario that runs whole commands, and how many tests
reach the same check. Runs the suite of the checkout labkit is installed
from (`tests/`, `pytest -n auto`) once with every gate finding built and
every `SystemExit` raised with a string message traced, and tells per rule
and per finding site
(`check_inventory.finding_sites`) the tests that reached it — their count,
how many of them carry the mark `rule`, and the test files they stand in —
by the layer through which each test entered:

  - `command` — a console script's `main` or `cli` (`[project.scripts]`),
    called in the test's process or run in a subprocess it started
  - `gate`, `check`, `format`, `run`, `tool`, `probe`, `other` — else the
    package folder of the outermost labkit function the test called
    (`labkit/gates/…` is `gate`)

How it traces: a `sitecustomize` on PYTHONPATH (`install_trace`) wraps
`GateFinding.__init__` in every Python process of the run that inherits its
environment and registers a `sys.monitoring` callback for raised
exceptions; each finding built, and each `SystemExit` raised in the package
with a message, appends the test (`PYTEST_CURRENT_TEST`), the site (for a
finding the first labkit frame outside `formats/gate.py`, for an exit the
raising frame) and the outermost labkit frame (the entry) to one file per
process. The tests marked `rule` are the ones pytest collects under
`-m rule`, collected once before the run.

Its limits, which the output repeats: reaching a site is not asserting it —
a test may build a finding and check something else; the mark `rule` holds
that a test starts no process and enters no command, not that it holds one
condition; a site's `printed` channel is not traced; of the exits only a
`SystemExit` itself with a string code is — not a subclass
(`recheck.NotVerifiable`) and not `console.Refused`, which the scan counts
as no site either, and an exit site whose message is a name that holds an
integer at run time is never reached; a subprocess started with an
environment of its own carries no test name and is not traced; a process in
which another tool holds the monitoring id traces no exit, and the output
counts those processes; a finding rebuilt where no site stands
(`dataclasses.replace` in a gate), or an exit raised where the scan counts
none (`sys.exit("…")`), counts as unmapped. Computed at every call,
committed nowhere: line numbers move with every edit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import CodeType, FrameType
from typing import TYPE_CHECKING, Any

from labkit import PACKAGE_DIR

if TYPE_CHECKING:
    # the trace runs at every Python start of the suite: it loads no more than it needs
    from labkit.tools.check_inventory import FindingSite

#: the folder each traced process writes its findings into; unset, nothing is traced
TRACE_ENV = "LABKIT_FINDING_TRACE"
#: the constructors' module, whose frames are no site
GATE_MODULE = "labkit/formats/gate.py"
#: the package folders that name a layer; any other is `other`
LAYERS = {
    "gates": "gate",
    "checks": "check",
    "formats": "format",
    "run": "run",
    "tools": "tool",
    "probes": "probe",
}
COMMAND = "command"
#: the channels the trace follows (`check_inventory.FindingSite.channel`);
#: a `printed` site is not traced
FINDING, EXIT = "finding", "exit"
#: the `sys.monitoring` tool id the trace of exits takes — one of the ids
#: Python leaves to tools, apart from the debugger's, coverage's and the
#: profiler's
MONITOR_TOOL = 4
#: the name's end of the marker a process leaves in the trace folder when it
#: could not trace its exits
EXITS_UNTRACED_SUFFIX = ".exits-untraced"
USAGE = "usage: python -m labkit.tools.test_inventory [--out FILE]"


@dataclass(frozen=True)
class Event:
    """One finding told during a test: the TEST (pytest's node id), the
    site's PATH (relative to the package's parent) and LINE, the ENTRY
    (`module.qualname` of the outermost labkit frame), whether it was told
    in a SUBPROCESS the test started, and its CHANNEL — FINDING for a gate
    finding built, EXIT for a `SystemExit` raised with a message."""

    test: str
    path: str
    line: int
    entry: str
    subprocess: bool
    channel: str


# -- the trace, in every process of the run ----------------------------------

_out: list = []  # [pid, open file] of this process, opened at the first finding
_rel_cache: dict[str, str | None] = {}


def _package_rel(filename: str) -> str | None:
    """FILENAME relative to the package's parent when it lies in the
    package, else None; cached per name."""
    if filename not in _rel_cache:
        try:
            rel = Path(filename).resolve().relative_to(PACKAGE_DIR.parent.resolve())
            _rel_cache[filename] = rel.as_posix() if rel.parts[0] == "labkit" else None
        except ValueError:
            _rel_cache[filename] = None
    return _rel_cache[filename]


def _module_of(rel: str) -> str:
    """`labkit/gates/finalize.py` → `labkit.gates.finalize`."""
    return rel.removesuffix(".py").removesuffix("/__init__").replace("/", ".")


def _record(folder: str, frame: FrameType | None, channel: str) -> None:
    """Append what is told now as one JSON line to this process's file in
    FOLDER: a gate finding being built (CHANNEL FINDING; FRAME the
    constructor's caller, the site the first labkit frame outside
    `formats/gate.py`) or a `SystemExit` being raised (CHANNEL EXIT; FRAME
    the raising frame, which is the site). Nothing outside a test, and
    nothing for an exit raised outside the package."""
    test = os.environ.get("PYTEST_CURRENT_TEST")
    if not test:
        return
    site: tuple[str, int] | None = None
    entry: tuple[str, str] | None = None
    raised_here = channel == EXIT
    while frame is not None:
        rel = _package_rel(frame.f_code.co_filename)
        if raised_here and rel is None:
            return
        if rel is not None:
            if site is None and (raised_here or rel != GATE_MODULE):
                site = (rel, frame.f_lineno)
            entry = (rel, frame.f_code.co_qualname)
        raised_here = False
        frame = frame.f_back
    if site is None or entry is None:
        return
    if not _out or _out[0] != os.getpid():
        _out[:] = [os.getpid(), open(Path(folder) / f"{os.getpid()}.jsonl", "a")]
    line = {
        "test": test.rsplit(" (", 1)[0],
        "path": site[0],
        "line": site[1],
        "entry": f"{_module_of(entry[0])}.{entry[1]}",
        "subprocess": "pytest" not in sys.modules,
        "channel": channel,
    }
    _out[1].write(json.dumps(line) + "\n")
    _out[1].flush()


def install_trace() -> None:
    """Record each gate finding built and each `SystemExit` raised with a
    message, when TRACE_ENV names a folder; else do nothing. Called by the
    `sitecustomize` `run_suite` puts on PYTHONPATH. Wraps
    `GateFinding.__init__` and registers a `sys.monitoring` callback for
    raised exceptions (`trace_exits`)."""
    folder = os.environ.get(TRACE_ENV)
    if not folder:
        return
    from labkit.formats.gate import GateFinding

    built = GateFinding.__init__

    def traced(self: GateFinding, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401 — GateFinding's own signature
        built(self, *args, **kwargs)
        _record(folder, sys._getframe(1), FINDING)

    GateFinding.__init__ = traced  # type: ignore[method-assign]
    try:
        trace_exits(folder)
    except ValueError as exc:
        # an error here would end in Python's one-line sitecustomize warning
        # and leave the exits of this process silently uncounted: the
        # marker makes the inventory say so (`exits_untraced`)
        marker = Path(folder) / f"{os.getpid()}{EXITS_UNTRACED_SUFFIX}"
        marker.write_text(f"{exc}\n", encoding="utf-8")


def trace_exits(folder: str) -> None:
    """Record into FOLDER each `SystemExit` raised with a message — the
    exception class itself, not a subclass, its code a string: what the
    inventory counts as an `exit` site (`raise SystemExit(<message>)`).
    Python reports a raised exception once in every frame it passes; only
    the first report, in the raising frame, is recorded.

    Raises:
        ValueError: Another tool holds MONITOR_TOOL in this process.
    """
    monitoring = sys.monitoring
    monitoring.use_tool_id(MONITOR_TOOL, "labkit-test-inventory")
    last: list[BaseException] = []  # the exit reported last, to tell its later frames

    def raised(code: CodeType, offset: int, exc: BaseException) -> None:
        if type(exc) is not SystemExit or not isinstance(exc.code, str):
            return
        if last and last[0] is exc:
            return
        last[:] = [exc]
        _record(folder, sys._getframe(1), EXIT)

    monitoring.register_callback(MONITOR_TOOL, monitoring.events.RAISE, raised)
    monitoring.set_events(MONITOR_TOOL, monitoring.events.RAISE)


SITECUSTOMIZE = """\
# written by labkit.tools.test_inventory: trace findings and exits in this process
try:
    from labkit.tools import test_inventory
except ImportError:
    # a Python without this labkit (a probe's own venv) builds none of its findings
    pass
else:
    test_inventory.install_trace()
"""


def run_suite(repo: Path, folder: Path, log: Path) -> int:
    """Run REPO's suite once with the trace on, its findings into FOLDER
    and pytest's output into LOG; pytest's exit code."""
    hook = folder / "sitecustomize"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    trace = folder / "trace"
    trace.mkdir()
    env = {
        **os.environ,
        TRACE_ENV: str(trace),
        "PYTHONPATH": os.pathsep.join(
            p for p in (str(hook), os.environ.get("PYTHONPATH", "")) if p
        ),
    }
    with open(log, "w", encoding="utf-8") as out:
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-n",
                "auto",
                "tests",
            ],
            cwd=repo,
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
    return r.returncode


def read_events(trace: Path) -> list[Event]:
    """Every event the processes wrote into TRACE; a line that does not
    read raises ValueError naming its file and line (`jsonl.objects`)."""
    from labkit.formats import jsonl

    out = []
    for f in sorted(trace.glob("*.jsonl")):
        for n, d in jsonl.objects(f.read_text(encoding="utf-8"), str(f)):
            if not isinstance(d, dict):
                raise ValueError(f"{f}:{n}: not a trace line (no object)")
            try:
                out.append(
                    Event(
                        d["test"],
                        d["path"],
                        d["line"],
                        d["entry"],
                        d["subprocess"],
                        d["channel"],
                    )
                )
            except KeyError as exc:
                raise ValueError(f"{f}:{n}: not a trace line (no {exc})") from exc
    return out


def exits_untraced(trace: Path) -> int:
    """How many processes of the run left a marker in TRACE that they could
    not trace their exits (`install_trace`)."""
    return len(list(trace.glob(f"*{EXITS_UNTRACED_SUFFIX}")))


# -- the inventory, from the events ------------------------------------------


def entry_layer(entry: str, commands: set[str]) -> str:
    """The layer through which a test entered labkit at ENTRY
    (`module.qualname`): COMMAND for the `main` or `cli` of a module in
    COMMANDS (the console scripts' modules) or a module run as a script
    (`<module>`), else the layer of its package folder (LAYERS)."""
    module, _, name = entry.rpartition(".")
    if name == "<module>" or (module in commands and name in ("main", "cli")):
        return COMMAND
    parts = entry.split(".")
    return LAYERS.get(parts[1], "other") if len(parts) > 2 else "other"


def site_at(path: str, line: int, sites: list[FindingSite]) -> FindingSite | None:
    """The finding site of SITES at PATH whose call spans LINE — the
    innermost where calls nest —, or None."""
    hits = [s for s in sites if s.path == path and s.line <= line <= s.end_line]
    return min(hits, key=lambda s: s.end_line - s.line) if hits else None


def traced_sites(sites: list[FindingSite]) -> list[FindingSite]:
    """Of SITES, those the trace follows: the gate findings and the exits."""
    return [s for s in sites if s.channel in (FINDING, EXIT)]


def require_one_site_per_line(traced: list[FindingSite]) -> None:
    """Refuse TRACED sites of which two start on one line of one file: a
    site is known by its file and line (`Reach.by_site`). `main` asks
    before the suite runs, `reach` again for any other caller.

    Raises:
        ValueError: Naming the file and line two sites share.
    """
    seen: set[tuple[str, int]] = set()
    for s in traced:
        if (s.path, s.line) in seen:
            raise ValueError(
                f"{s.path}:{s.line}: two traced finding sites start on this line"
            )
        seen.add((s.path, s.line))


@dataclass(frozen=True)
class Reach:
    """Which tests reached which site: BY_SITE maps a traced site's (path,
    line) to {layer: the tests that entered through it}; UNMAPPED are the
    events whose place is no site of their channel."""

    by_site: dict[tuple[str, int], dict[str, set[str]]]
    unmapped: list[Event]


def reach(events: list[Event], sites: list[FindingSite], commands: set[str]) -> Reach:
    """The reach of EVENTS over the traced SITES (`traced_sites`), each
    event held to the sites of its own channel (`Reach`). Pure.

    Raises:
        ValueError: Two traced sites start on one line of one file — the
            key of `Reach.by_site` would stand for both.
    """
    traced = traced_sites(sites)
    require_one_site_per_line(traced)
    by_site: dict[tuple[str, int], dict[str, set[str]]] = {
        (s.path, s.line): defaultdict(set) for s in traced
    }
    unmapped = []
    for e in events:
        s = site_at(e.path, e.line, [s for s in traced if s.channel == e.channel])
        if s is None:
            unmapped.append(e)
            continue
        by_site[(s.path, s.line)][entry_layer(e.entry, commands)].add(e.test)
    return Reach(by_site, unmapped)


def site_standing(layers: dict[str, set[str]]) -> str:
    """A site's standing by the layers that reached it: `unreached`, `only
    through commands`, or `direct` — some test entered below a command."""
    if not any(layers.values()):
        return "unreached"
    if set(k for k, v in layers.items() if v) == {COMMAND}:
        return "only through commands"
    return "direct"


STANDINGS = ("direct", "only through commands", "unreached")
#: the layers from the narrowest entry to the widest: a site's lowest is
#: the narrowest any test reached it through
DEPTH = ("format", "check", "run", "tool", "probe", "other", "gate", COMMAND)


def lowest_layer(layers: dict[str, set[str]]) -> str | None:
    """The narrowest layer (DEPTH) through which some test reached a site,
    or None when none did."""
    reached = [layer for layer in DEPTH if layers.get(layer)]
    return reached[0] if reached else None


def _tests(layers: dict[str, set[str]]) -> set[str]:
    return set().union(*layers.values()) if layers else set()


def render_test_inventory(
    sites: list[FindingSite],
    r: Reach,
    slow_files: set[str],
    rule_tests: set[str],
    suite_line: str,
    failed: list[str],
    *,
    exits_untraced: int = 0,
) -> str:
    """The inventory as markdown: the run, the standing of the traced sites
    by channel, the sites a test marked `rule` (RULE_TESTS, node ids)
    reaches, per rule, the sites no test reaches below a command, the
    unreached, the sites most tests reach, per test file, per scenario
    test, per site with its test files, and the events no site stands
    for. EXITS_UNTRACED is the number of processes that traced no exit
    (`exits_untraced`); the head names it."""
    traced = traced_sites(sites)
    key = {(s.path, s.line): s for s in traced}
    stand = {k: site_standing(v) for k, v in r.by_site.items()}
    channels = (FINDING, EXIT)
    n = {c: sum(1 for s in traced if s.channel == c) for c in channels}
    printed = len(sites) - len(traced)
    out = [
        "# Test inventory — which test reaches which finding site",
        "",
        f"Suite: {suite_line}. Traced sites: {n[FINDING]} gate findings and "
        f"{n[EXIT]} exits of {len(sites)} finding sites; the {printed} `printed` "
        f"sites are not traced. Unmapped findings and exits (told where no site "
        f"stands): {len(r.unmapped)}. Processes that traced no exit (another "
        f"tool held the monitoring id): {exits_untraced}.",
        "",
        "An exit is a `SystemExit` itself raised in the package with a string "
        "message; a subclass and `console.Refused` are no site and not traced.",
        "",
        "Reaching a site is not asserting it; a subprocess with an environment "
        "of its own is not traced. `direct`: some test entered below a "
        "command (a gate, check, format … function); `only through commands`: "
        "every test that reached it ran a whole command.",
        "",
        "| standing | gate findings | exits |",
        "|---|---|---|",
    ]
    for name in STANDINGS:
        counts = [
            sum(1 for k, v in stand.items() if v == name and key[k].channel == c)
            for c in channels
        ]
        out.append(f"| {name} | {counts[0]} | {counts[1]} |")
    lowest = [lowest_layer(v) for v in r.by_site.values()]
    out += [
        "",
        "The narrowest layer through which some test reaches each site:",
        "",
        "| lowest layer | sites |",
        "|---|---|",
    ]
    out += [
        f"| {layer} | {lowest.count(layer)} |" for layer in DEPTH if layer in lowest
    ]
    out += _rule_marked(key, r, rule_tests)
    findings = {k: s for k, s in key.items() if s.channel == FINDING}
    out += _per_rule(findings, stand, r)
    out += _site_lists(key, stand, r)
    out += _most_reached(key, r)
    out += _per_file(r, slow_files)
    out += _per_scenario(r, slow_files)
    out += _per_site(key, stand, r, rule_tests)
    out += _unmapped_and_failed(r, failed)
    return "\n".join(out) + "\n"


def _rule_marked(
    key: dict[tuple[str, int], FindingSite], r: Reach, rule_tests: set[str]
) -> list[str]:
    """The count of sites a test marked `rule` reaches, by channel, and
    what the mark does and does not establish."""
    counts = {
        c: (
            sum(
                1
                for k, s in key.items()
                if s.channel == c and _tests(r.by_site[k]) & rule_tests
            ),
            sum(1 for s in key.values() if s.channel == c),
        )
        for c in (FINDING, EXIT)
    }
    return [
        "",
        "## Sites a test marked `rule` reaches",
        "",
        f"{len(rule_tests)} tests carry the mark `rule`. They reach "
        f"{counts[FINDING][0]} of {counts[FINDING][1]} gate-finding sites and "
        f"{counts[EXIT][0]} of {counts[EXIT][1]} exit sites; the table per site "
        "names the count for each. The mark's guard refuses a test that "
        "starts a process or enters a console command, and `pure_call` a "
        "check that opens a file, each within the limits "
        "`tests/check_guards.py` names. That a test holds "
        "one condition, with its violation and its valid twin, is not "
        "established by the mark: a reader of the test establishes it.",
    ]


def _per_site(
    key: dict[tuple[str, int], FindingSite],
    stand: dict[tuple[str, int], str],
    r: Reach,
    rule_tests: set[str],
) -> list[str]:
    """One row per traced site: its standing, its tests, how many of them
    carry the mark `rule`, and the test files they stand in, most tests
    first."""
    out = [
        "",
        "## Per site (the test files that reach it)",
        "",
        "| site | unit | channel | standing | tests | rule tests | test files |",
        "|---|---|---|---|---|---|---|",
    ]
    for k in sorted(key):
        s, tests = key[k], _tests(r.by_site[k])
        per_file: dict[str, int] = defaultdict(int)
        for test in tests:
            per_file[test.split("::", 1)[0]] += 1
        files = ", ".join(
            f"`{f}` {count}"
            for f, count in sorted(per_file.items(), key=lambda x: (-x[1], x[0]))
        )
        out.append(
            f"| `{s.path}:{s.line}` | `{s.unit}` | {s.channel} | {stand[k]} | "
            f"{len(tests)} | {len(tests & rule_tests)} | {files or '—'} |"
        )
    return out


def _per_rule(
    key: dict[tuple[str, int], FindingSite], stand: dict[tuple[str, int], str], r: Reach
) -> list[str]:
    """The table per rule, by the assignment each site records as data
    (`FindingSite.assignment`): its sites by standing and the tests
    reaching them."""
    out: list[str] = []
    rules: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for k, s in key.items():
        rules[s.assignment].append(k)
    out += [
        "",
        "## Per rule",
        "",
        "| rule | sites | direct | only through commands | unreached | tests |",
        "|---|---|---|---|---|---|",
    ]
    for rule in sorted(rules):
        ks = rules[rule]
        counts = [sum(1 for k in ks if stand[k] == name) for name in STANDINGS]
        tests = set().union(*(_tests(r.by_site[k]) for k in ks))
        out.append(
            f"| {rule} | {len(ks)} | "
            + " | ".join(map(str, counts))
            + f" | {len(tests)} |"
        )
    return out


def _site_lists(
    key: dict[tuple[str, int], FindingSite], stand: dict[tuple[str, int], str], r: Reach
) -> list[str]:
    """The sites reached only through whole commands, and the unreached."""
    out: list[str] = []
    for name, title in (
        ("only through commands", "Sites reached only through whole commands"),
        ("unreached", "Sites no test reaches"),
    ):
        out += [
            "",
            f"## {title}",
            "",
            "| site | unit | grade | rules | tests |",
            "|---|---|---|---|---|",
        ]
        for k in sorted(k for k, v in stand.items() if v == name):
            s = key[k]
            out.append(
                f"| `{s.path}:{s.line}` | `{s.unit}` | {s.grade} | "
                f"{s.assignment} | {len(_tests(r.by_site[k]))} |"
            )
    return out


def _most_reached(key: dict[tuple[str, int], FindingSite], r: Reach) -> list[str]:
    """The twenty sites most tests reach, by layer."""
    out: list[str] = []
    out += [
        "",
        "## Sites most tests reach",
        "",
        "| site | tests | by layer |",
        "|---|---|---|",
    ]
    top = sorted(key, key=lambda k: -len(_tests(r.by_site[k])))[:20]
    for k in top:
        layers = ", ".join(
            f"{layer} {len(t)}" for layer, t in sorted(r.by_site[k].items()) if t
        )
        out.append(f"| `{k[0]}:{k[1]}` | {len(_tests(r.by_site[k]))} | {layers} |")
    return out


def _per_file(r: Reach, slow_files: set[str]) -> list[str]:
    """Per test file: its tests and its test × site pairs by layer."""
    out: list[str] = []
    per_file: dict[str, dict[str, set[tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for k, layers in r.by_site.items():
        for layer, tests in layers.items():
            for t in tests:
                per_file[t.split("::", 1)[0]][layer].add((t, f"{k[0]}:{k[1]}"))
    all_layers = sorted({layer for f in per_file.values() for layer in f})
    out += [
        "",
        "## Per test file (test × site pairs by layer)",
        "",
        "| file | slow | tests | " + " | ".join(all_layers) + " |",
        "|---|---|---|" + "---|" * len(all_layers),
    ]
    for f in sorted(per_file, key=lambda f: -sum(len(v) for v in per_file[f].values())):
        layers = per_file[f]
        tests = {t for pairs in layers.values() for t, _ in pairs}
        cells = " | ".join(str(len(layers.get(layer, ()))) for layer in all_layers)
        out.append(
            f"| `{f}` | {'yes' if f in slow_files else ''} | {len(tests)} | {cells} |"
        )
    return out


#: a scenario test's standing in step 4 of the test model
#: (docs/notes/2026-11-10-test-model.md): every site it reaches is reached
#: by a faster test too; a site only it (or another scenario) reaches; no
#: traced site, so nothing is known — never read as redundant
COVERED, HOLDS_A_SITE, UNKNOWN = "covered", "holds a site", "unknown"


@dataclass(frozen=True)
class ScenarioTest:
    """One test of a scenario file (`slow_files`) and what reach says of it.

    Attributes:
        test: Its pytest node id.
        sites: The finding sites it reaches, as `path:line`.
        held: Of SITES, those no test outside the scenario files reaches
            below a whole command — what only a scenario reaches.
        standing: COVERED, HOLDS_A_SITE or UNKNOWN.
    """

    test: str
    sites: tuple[str, ...]
    held: tuple[str, ...]
    standing: str


def scenario_tests(r: Reach, slow: set[str]) -> list[ScenarioTest]:
    """Every test of the SLOW files that reached a traced site, with
    its sites and the sites no faster test reaches below a command
    (`ScenarioTest`), sorted by test id. Reach is not an assertion: COVERED
    says only that each site it reaches has a faster test too, never that
    the scenario's assertions — what one command passes to the next — are
    held elsewhere. A scenario test reaching no traced site is not listed;
    its standing is UNKNOWN (`scenario_standing`). Pure."""

    def scenario(t: str) -> bool:
        return t.split("::", 1)[0] in slow

    by_test: dict[str, set[str]] = defaultdict(set)
    faster: dict[str, bool] = {}
    for (path, line), layers in r.by_site.items():
        key = f"{path}:{line}"
        faster[key] = any(
            not scenario(t)
            for layer, ts in layers.items()
            if layer != COMMAND
            for t in ts
        )
        for ts in layers.values():
            for t in ts:
                if scenario(t):
                    by_test[t].add(key)
    out = []
    for t in sorted(by_test):
        sites = tuple(sorted(by_test[t]))
        held = tuple(k for k in sites if not faster[k])
        out.append(ScenarioTest(t, sites, held, HOLDS_A_SITE if held else COVERED))
    return out


def scenario_standing(test: str, listed: list[ScenarioTest]) -> str:
    """The standing of TEST: its entry's in LISTED (`scenario_tests`), else
    UNKNOWN — a scenario test whose findings were not traced (it reached no
    traced site, only printed lines or exits that are none, or its
    subprocess carried no test name) says nothing about redundancy."""
    return next((s.standing for s in listed if s.test == test), UNKNOWN)


def _per_scenario(r: Reach, slow: set[str]) -> list[str]:
    """The table per scenario test (`scenario_tests`)."""
    listed = scenario_tests(r, slow)
    counts = {
        k: sum(1 for s in listed if s.standing == k) for k in (COVERED, HOLDS_A_SITE)
    }
    out = [
        "",
        "## Per scenario test (step 4: reach only, not assertions)",
        "",
        f"{len(listed)} scenario tests reached a traced site: "
        f"{counts[COVERED]} {COVERED} (every site has a faster test too), "
        f"{counts[HOLDS_A_SITE]} {HOLDS_A_SITE}. A scenario test not listed is "
        f"{UNKNOWN}. Reach never establishes a replacement: its assertions are "
        "reviewed one by one before any removal.",
        "",
        "| test | sites | held only by scenarios |",
        "|---|---|---|",
    ]
    for s in listed:
        held = ", ".join(f"`{k}`" for k in s.held) or "—"
        out.append(f"| `{s.test}` | {len(s.sites)} | {held} |")
    return out


def _unmapped_and_failed(r: Reach, failed: list[str]) -> list[str]:
    """The places that built a finding or raised an exit where no site of
    that channel stands, most first, and the tests that failed under the
    trace."""
    places: dict[tuple[str, str], int] = defaultdict(int)
    for e in r.unmapped:
        places[(f"{e.path}:{e.line}", e.channel)] += 1
    out = [
        "",
        "## Findings and exits told where no site stands",
        "",
        "| place | channel | told |",
        "|---|---|---|",
    ]
    out += [
        f"| `{p}` | {channel} | {n} |"
        for (p, channel), n in sorted(places.items(), key=lambda x: -x[1])[:15]
    ]
    if failed:
        out += ["", "## Tests that failed under the trace", ""]
        out += [f"- `{t}`" for t in failed]
    return out


def slow_files(tests_dir: Path) -> set[str]:
    """The test files under TESTS_DIR that carry the `slow` mark, as
    `tests/<name>.py`."""
    return {
        f"tests/{p.name}"
        for p in tests_dir.glob("test_*.py")
        if "pytestmark = pytest.mark.slow" in p.read_text(encoding="utf-8")
    }


def rule_tests(repo: Path) -> set[str]:
    """The node ids of the tests of REPO's suite that carry the mark
    `rule`, as pytest collects them (`--collect-only -m rule`); runs no
    test.

    Raises:
        RuntimeError: The collection did not end with exit 0 — pytest's
            output is in the message.
    """
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-m",
            "rule",
            "-p",
            "no:cacheprovider",
            "tests",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"collecting the tests marked `rule` ended with exit {r.returncode}:\n"
            f"{r.stdout}{r.stderr}"
        )
    return collected_ids(r.stdout)


def collected_ids(output: str) -> set[str]:
    """The node ids in OUTPUT, what `pytest --collect-only -q` printed: its
    lines that name a test (`file::…`), without the summary and blank
    lines. Pure."""
    return {ln.strip() for ln in output.splitlines() if "::" in ln}


def main(argv: list[str]) -> int:
    """Run the traced suite and print the inventory, or write it to `--out
    FILE`; 0, or 1 when the suite is not green (the inventory is still
    written, its first line says so)."""
    from labkit.formats import console
    from labkit.tools.check_inventory import entry_points, finding_sites, read_modules

    if argv in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    out: Path | None = None
    if argv:
        if len(argv) != 2 or argv[0] != "--out":
            raise console.Refused("test_inventory", USAGE)
        out = Path(argv[1])
    repo = PACKAGE_DIR.parent
    if not (repo / "tests").is_dir() or not (repo / "pyproject.toml").is_file():
        raise console.Refused(
            "test_inventory",
            f"{repo}: no tests/ beside the package — labkit's own checkout runs it",
        )
    commands = {
        e.rpartition(".")[0]
        for e in entry_points(
            (repo / "pyproject.toml").read_text(encoding="utf-8")
        ).values()
    }
    sites = finding_sites(read_modules(PACKAGE_DIR))
    require_one_site_per_line(traced_sites(sites))
    marked = rule_tests(repo)
    with tempfile.TemporaryDirectory(prefix="labkit-test-inventory-") as d:
        folder = Path(d)
        log = folder / "pytest.log"
        print("test_inventory: running the suite with the trace on (several minutes)")
        code = run_suite(repo, folder, log)
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        suite_line = lines[-1] if lines else "no output"
        failed = [ln.split(" ", 1)[1] for ln in lines if ln.startswith("FAILED ")]
        events = read_events(folder / "trace")
        untraced = exits_untraced(folder / "trace")
    if code != 0:
        suite_line = f"NOT GREEN (pytest exit {code}): {suite_line}"
    text = render_test_inventory(
        sites,
        reach(events, sites, commands),
        slow_files(repo / "tests"),
        marked,
        suite_line,
        failed,
        exits_untraced=untraced,
    )
    if out is None:
        sys.stdout.write(text)
    else:
        out.write_text(text, encoding="utf-8")
        print(f"test_inventory: wrote {out}")
    return 0 if code == 0 else 1


def cli() -> None:
    """Console entry: `main` with the process's arguments."""
    from labkit.formats import console

    console.exit_with(main)


if __name__ == "__main__":
    cli()
