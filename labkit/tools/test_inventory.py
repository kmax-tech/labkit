"""test_inventory — which test of labkit's suite reaches which finding site,
and through which layer it entered labkit.

    python -m labkit.tools.test_inventory [--out FILE]

The basis for a clear test model: whether a rule's check is tested on its
own or only inside a scenario that runs whole commands, and how many tests
reach the same check. Runs the suite of the checkout labkit is installed
from (`tests/`, `pytest -n auto`) once with every gate finding traced, and
tells per rule and per finding site (`check_inventory.finding_sites`) the
tests that reached it, by the layer through which each test entered:

  - `command` — a console script's `main` or `cli` (`[project.scripts]`),
    called in the test's process or run in a subprocess it started
  - `gate`, `check`, `format`, `run`, `tool`, `probe`, `other` — else the
    package folder of the outermost labkit function the test called
    (`labkit/gates/…` is `gate`)

How it traces: a `sitecustomize` on PYTHONPATH (`install_trace`) wraps
`GateFinding.__init__` in every Python process of the run that inherits its
environment; each finding built appends the test (`PYTEST_CURRENT_TEST`),
the first labkit frame outside `formats/gate.py` (the site) and the
outermost labkit frame (the entry) to one file per process.

Its limits, which the output repeats: reaching a site is not asserting it —
a test may build a finding and check something else; only gate findings
are traced, not a site's `exit` or `printed` channel; a subprocess started
with an environment of its own carries no test name and is not traced; a
finding rebuilt where no site stands (`dataclasses.replace` in a gate)
counts as unmapped. Computed at every call, committed nowhere: line
numbers move with every edit.
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
USAGE = "usage: python -m labkit.tools.test_inventory [--out FILE]"


@dataclass(frozen=True)
class Event:
    """One gate finding built during a test: the TEST (pytest's node id),
    the site's PATH (relative to the package's parent) and LINE, the ENTRY
    (`module.qualname` of the outermost labkit frame) and whether it was
    built in a SUBPROCESS the test started."""

    test: str
    path: str
    line: int
    entry: str
    subprocess: bool


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


def _record(folder: str) -> None:
    """Append the finding being built now as one JSON line to this
    process's file in FOLDER; nothing outside a test."""
    test = os.environ.get("PYTEST_CURRENT_TEST")
    if not test:
        return
    site: tuple[str, int] | None = None
    entry: tuple[str, str] | None = None
    frame = sys._getframe(2)  # past _record and the wrapper
    while frame is not None:
        rel = _package_rel(frame.f_code.co_filename)
        if rel is not None:
            if site is None and rel != GATE_MODULE:
                site = (rel, frame.f_lineno)
            entry = (rel, frame.f_code.co_qualname)
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
    }
    _out[1].write(json.dumps(line) + "\n")
    _out[1].flush()


def install_trace() -> None:
    """Wrap `GateFinding.__init__` so that each finding built is recorded,
    when TRACE_ENV names a folder; else do nothing. Called by the
    `sitecustomize` `run_suite` puts on PYTHONPATH."""
    folder = os.environ.get(TRACE_ENV)
    if not folder:
        return
    from labkit.formats.gate import GateFinding

    built = GateFinding.__init__

    def traced(self: GateFinding, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401 — GateFinding's own signature
        built(self, *args, **kwargs)
        _record(folder)

    GateFinding.__init__ = traced  # type: ignore[method-assign]


SITECUSTOMIZE = """\
# written by labkit.tools.test_inventory: trace gate findings in this process
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
                    Event(d["test"], d["path"], d["line"], d["entry"], d["subprocess"])
                )
            except KeyError as exc:
                raise ValueError(f"{f}:{n}: not a trace line (no {exc})") from exc
    return out


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


@dataclass(frozen=True)
class Reach:
    """Which tests reached which site: BY_SITE maps a site's (path, line)
    to {layer: the tests that entered through it}; UNMAPPED are the events
    whose place is no finding site."""

    by_site: dict[tuple[str, int], dict[str, set[str]]]
    unmapped: list[Event]


def reach(events: list[Event], sites: list[FindingSite], commands: set[str]) -> Reach:
    """The reach of EVENTS over the finding-channel SITES (`Reach`). Pure."""
    traced = [s for s in sites if s.channel == "finding"]
    by_site: dict[tuple[str, int], dict[str, set[str]]] = {
        (s.path, s.line): defaultdict(set) for s in traced
    }
    unmapped = []
    for e in events:
        s = site_at(e.path, e.line, traced)
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
    suite_line: str,
    failed: list[str],
) -> str:
    """The inventory as markdown: the run, the standing of the sites, per
    rule, the sites no test reaches below a command, the unreached, the
    sites most tests reach, and per test file."""
    traced = [s for s in sites if s.channel == "finding"]
    key = {(s.path, s.line): s for s in traced}
    stand = {k: site_standing(v) for k, v in r.by_site.items()}
    out = [
        "# Test inventory — which test reaches which finding site",
        "",
        f"Suite: {suite_line}. Gate-finding sites: {len(traced)} of "
        f"{len(sites)} finding sites (the `exit` and `printed` channels are not "
        f"traced). Unmapped findings (built where no site stands): {len(r.unmapped)}.",
        "",
        "Reaching a site is not asserting it; a subprocess with an environment "
        "of its own is not traced. `direct`: some test entered below a "
        "command (a gate, check, format … function); `only through commands`: "
        "every test that reached it ran a whole command.",
        "",
        "| standing | sites |",
        "|---|---|",
    ]
    for name in STANDINGS:
        out.append(f"| {name} | {sum(1 for v in stand.values() if v == name)} |")
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
    out += _per_rule(key, stand, r)
    out += _site_lists(key, stand, r)
    out += _most_reached(key, r)
    out += _per_file(r, slow_files)
    out += _unmapped_and_failed(r, failed)
    return "\n".join(out) + "\n"


def _per_rule(
    key: dict[tuple[str, int], FindingSite], stand: dict[tuple[str, int], str], r: Reach
) -> list[str]:
    """The table per rule: its sites by standing and the tests reaching them."""
    out: list[str] = []
    rules: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for k, s in key.items():
        for rule in s.rules or ("(no rule)",):
            rules[rule].append(k)
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
                f"{', '.join(s.rules) or '—'} | {len(_tests(r.by_site[k]))} |"
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


def _unmapped_and_failed(r: Reach, failed: list[str]) -> list[str]:
    """The places that built a finding where no site stands, most first,
    and the tests that failed under the trace."""
    places: dict[str, int] = defaultdict(int)
    for e in r.unmapped:
        places[f"{e.path}:{e.line}"] += 1
    out = [
        "",
        "## Findings built where no site stands",
        "",
        "| place | findings |",
        "|---|---|",
    ]
    out += [
        f"| `{p}` | {n} |" for p, n in sorted(places.items(), key=lambda x: -x[1])[:15]
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
    with tempfile.TemporaryDirectory(prefix="labkit-test-inventory-") as d:
        folder = Path(d)
        log = folder / "pytest.log"
        print("test_inventory: running the suite with the trace on (several minutes)")
        code = run_suite(repo, folder, log)
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        suite_line = lines[-1] if lines else "no output"
        failed = [ln.split(" ", 1)[1] for ln in lines if ln.startswith("FAILED ")]
        events = read_events(folder / "trace")
    if code != 0:
        suite_line = f"NOT GREEN (pytest exit {code}): {suite_line}"
    text = render_test_inventory(
        sites,
        reach(events, sites, commands),
        slow_files(repo / "tests"),
        suite_line,
        failed,
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
