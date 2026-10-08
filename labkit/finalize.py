"""finalize — the gate after a run, before a number is reported.

Sequences the checks that must pass before results are written back into
the protocol.

    finalize <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 clean, 1 findings (at least one blocker), 2 usage error.

What it runs, in order (the same numbers as `finalize_area`, which shows
each step's condition):
  0. protocol       the named PROTOCOL-*.md or the area's only one, and its
                    settings block — the only early end (exit 2)
  1. completion     the measurement run that answers — the newest completed
                    bound run reporting intent keys, the same choice as
                    intent-check — and every later step checks THAT run
  2. intent-check   every registered promise has a metrics key (and vice versa)
  3. declared scopes  every declared promise scope unchanged since the run
  4. open fields    protocol fields still holding a placeholder
  5. provenance     at protocol `cost = "seconds"`: the run froze its source
                    (`data=` in config.json) and every source and output file
                    is tracked in git — the two of the three questions the
                    agent audit kept asking that a machine can answer (AS-017
                    Die Zahl der Audits folgt der Kostenstufe, 2026-10-05);
                    the third, the counted unit, is the protocol's `Unit` field
  6. area tests     tests/test_<NN>_<name>.py via the repo's interpreter, on
                    every tier: a failing test is a blocker (evaluate() lost
                    its resolution check), a missing one no finding here
  7. criterion n    every `c<i>_n` key in metrics.json equals some input
                    count the run recorded (rows of a data= file, lines of
                    an output) — a warning, not a blocker, until the false
                    alarm rate is known (2026-10-05; the denominator class
                    was 31 of 171 audit findings)

What it does NOT do: fill fields, edit the protocol, or commit. It is a
read-only findings.
"""

from __future__ import annotations

import contextlib
import io
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from labkit import promises, protocol_block
from labkit.runs import bound_answering_run, read_metrics, read_outputs, read_run_config
from labkit.repo import (
    area_path,
    choose_protocol,
    git_root,
    git_run,
    no_such_area,
)
from labkit.intent_check import main as intent_check_main, registered_ids
from labkit.preflight import area_tests
from labkit.protocol_check import RUN_ID, fields, open_holes


def _tracked(repo: Path, path: Path) -> bool:
    """Is `path` tracked in `repo`? The exit code is the answer."""
    return git_run(["ls-files", "--error-unmatch", str(path)], repo).returncode == 0


CRITERION_N = promises.CRITERION_N_KEY


def criterion_n_input_mismatches(measurement_run: Path) -> list[str]:  # noqa: C901 complexity baseline 2026-10-08
    """Warnings: a criterion's denominator (`c<i>_n` in metrics.json) that
    matches no input count the run recorded — the size of what was counted,
    not a promised constant (that is `intent_check.promised_constant_mismatches`)."""
    metrics_file = measurement_run / "metrics.json"
    if not metrics_file.is_file():
        return []
    metrics = read_metrics(metrics_file)
    ns = {
        k: v
        for k, v in metrics.items()
        if CRITERION_N.match(k) and isinstance(v, int) and not isinstance(v, bool)
    }
    if not ns:
        return []
    cfg = read_run_config(measurement_run) or {}
    counts: dict[str, int] = {}
    for key, d in (cfg.get("data") or {}).items():
        if isinstance(d, dict) and isinstance(d.get("rows"), int):
            counts[f"data[{key}].rows"] = d["rows"]
    for o in read_outputs(measurement_run) or []:
        if o.lines is not None:
            counts[f"{o.path.name} lines"] = o.lines
    if not counts:
        return [
            f"{', '.join(sorted(ns))} present, but the run recorded no input count "
            f"(no data= rows, no output lines) to hold them to"
        ]
    out = []
    for k, n in sorted(ns.items()):
        if n not in counts.values():
            out.append(
                f"{k} = {n} matches no recorded count "
                f"({', '.join(f'{a} = {b}' for a, b in sorted(counts.items()))}) — "
                f"a denominator that is not the input is the audits' most "
                f"frequent real finding"
            )
    return out


def provenance_findings(
    area: Path, measurement_run: Path
) -> tuple[list[str], list[str]]:
    """(blockers, warnings) for a run of seconds: source frozen, files tracked."""
    blockers: list[str] = []
    warnings: list[str] = []
    cfg = read_run_config(measurement_run) or {}
    data = cfg.get("data") or {}
    if not data:
        blockers.append(
            "source not frozen — the run carries no `data=`; pass "
            "data={name: path} to runlog.run so sha and rows are recorded"
        )
    sources = [
        Path(v["path"]) for v in data.values() if isinstance(v, dict) and v.get("path")
    ]
    registered = read_outputs(measurement_run)
    outputs: list[Path] = [o.path for o in registered or []]
    if registered is None:
        warnings.append(
            "no outputs.json — the run registered no output file (run.output)"
        )
    repo = git_root(area)
    if repo is None:
        warnings.append(
            "not a git repository — cannot tell whether source and output are committed"
        )
        return blockers, warnings
    for f in sources:
        if not f.exists():
            blockers.append(f"{f} is gone — the run's rows cannot be re-derived")
        elif not _tracked(repo, f):
            blockers.append(
                f"source {f} is not tracked in git — commit it, or the number "
                f"cannot be re-derived"
            )
    # The output rows are born after the run, so on every first pass they are
    # untracked by construction: a warning that names the command, not a
    # blocker that sends the agent round the loop (2026-10-05, five probes).
    for f in outputs:
        if not f.exists():
            blockers.append(f"{f} is gone — the run's rows cannot be re-derived")
        elif not _tracked(repo, f):
            warnings.append(
                f"output {f.name} is not yet tracked — `git add {f}` before "
                f"the commit that cites the number"
            )
    return blockers, warnings


@dataclass
class Findings:
    """What the stations found: every blocker as one line, repeated in the
    summary — inside a commit hook the sections run to 20 lines and the one
    blocker drowned in the middle (usability probe 2026-10-07)."""

    blocked: list[str] = field(default_factory=list)
    warnings: int = 0

    def block(self, msg: str) -> None:
        """Print a blocker and keep it for the summary."""
        print(f"  BLOCKER: {msg}")
        self.blocked.append(msg)

    def warn(self, msg: str) -> None:
        """Print a warning and count it for the summary."""
        print(f"  warning: {msg}")
        self.warnings += 1


def answering_run(findings: Findings, area: Path, pid: str | None) -> Path | None:
    """The run every station holds the protocol to — `runs.bound_answering_run`,
    ONE choice for every station: intent-check skips newer runs without
    intent keys (a probe), so checking scopes or provenance on the newest
    run judged the probe while the numbers came from the measurement
    (review 2026-10-07). A blocker here is the finding; the exclusions are
    printed for the operator."""
    if pid is None:
        findings.block("no stamped protocol id ([protocol] id) — no run is bound to it")
        return None
    choice = bound_answering_run(area, pid)
    if choice.run_dir is None:
        findings.block(choice.blocker or f"no completed run bound to {pid}")
        for x in choice.exclusions:
            print(f"    {x.run_dir.name}: {x.why}")
        return None
    if choice.blocker:
        findings.block(choice.blocker)
    note = (
        f" (skipped {choice.skipped_newer} newer bound run(s) without intent keys)"
        if choice.skipped_newer
        else ""
    )
    print(f"  {choice.run_dir.name}: completed{note}")
    return choice.run_dir


def cited_run_mismatch(text: str, measurement_run: Path) -> str | None:
    """A blocker when the protocol's answer cites runs and not the one the
    checks hold; None when it cites that run or none."""
    cited = cited_runs(text)
    if cited and measurement_run.name not in cited:
        return (
            f'"Answer to the question" cites {", ".join(cited)}, '
            f"but the run that answers is {measurement_run.name} — cite the run "
            f"the checks hold, or rerun"
        )
    return None


def check_completion(
    findings: Findings, area: Path, text: str, pid: str | None
) -> Path | None:
    """Station 1: the run every later station holds the protocol to — chosen,
    shown, and held to the run the answer cites. Returns it, or None."""
    measurement_run = answering_run(findings, area, pid)
    if measurement_run is not None:
        mismatch = cited_run_mismatch(text, measurement_run)
        if mismatch:
            findings.block(mismatch)
    return measurement_run


def check_intent_keys_in_metrics(
    findings: Findings, protocol: Path, text: str, measurement_run: Path | None
) -> None:
    """Station 2: every registered intent id reports as a key of the answering
    run's metrics.json (intent-check). Not code_check.check_intent_ids, which
    holds the promises to the code before any run."""
    if not registered_ids(text):
        print("  no intent ids registered — nothing to check")
        return
    args = [str(protocol)] + (
        ["--metrics", str(measurement_run / "metrics.json")]
        if measurement_run is not None
        else []
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = intent_check_main(args)
    for line in buf.getvalue().splitlines():
        print(f"  {line}")
    if rc != 0:
        findings.block("intent-check failed (see its lines above)")


def check_declared_scopes(
    findings: Findings, area: Path, measurement_run: Path, frozen: bool
) -> None:
    """Station 3: a promise's declared scope edited after the run: today's code is not
    the code that produced the number; until 2026-10-06 only recheck saw it
    (Durchstich). A frozen protocol whose run recorded no block is a
    blocker since 0.71.0 (`promises.block_owed`): the run came from a labkit
    that let it pass, or the block was added after the run."""
    recorded = (read_run_config(measurement_run) or {}).get("promises")
    if recorded is None:
        owed = promises.block_owed(frozen, None)
        if owed:
            findings.block(
                f"{measurement_run.name} recorded no promise block: {owed} — a run "
                f"under labkit 0.70.0 or earlier is checked and reproduced with "
                f"its pinned version; a block added after the run is a new registration"
            )
        else:
            print("  no promise block recorded — nothing to compare")
        return
    drift = promises.scope_drift(recorded, area)
    for d in drift:
        findings.block(
            f"declared scope changed since {measurement_run.name}: {d} — rerun before reporting"
        )
    if not drift:
        print(
            f"  {len(recorded['ids'])} declared scope(s) unchanged since {measurement_run.name}"
        )


# the stamp's blanks may wrap lines; an HTML comment (`<!-- labkit:route -->`)
# is a marker, not a blank
_PLACEHOLDER = re.compile(r"<(?!!--)[^<>]{3,}>")


def readme_placeholders(area: Path) -> list[str]:
    """Lines of the area's README.md still holding a stamped `<…>` placeholder.
    A README that still carries the stamp's blanks tells a reader nothing and
    looks as if it did (code-navigation round 11). No README: nothing."""
    readme = area / "README.md"
    if not readme.is_file():
        return []
    text = readme.read_text(encoding="utf-8")
    out = []
    for m in _PLACEHOLDER.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        out.append(f"README.md:{line}: {' '.join(m.group(0).split())[:70]}")
    return out


ROUTE_START = "<!-- labkit:route -->"
ROUTE_END = "<!-- /labkit:route -->"
#: What the README's route must point to: the stations a reader takes after
#: the protocol — which run (`runlog`), which values (`labkit-params`), where
#: the ids are decided, the proof (CS-016 The experiment area reconstructs
#: itself). The README points; it copies no question, answer, run id or
#: threshold — each has its one home, and a copy went stale within a day
#: (area 08, 2026-10-08).
ROUTE_STATIONS = (
    "runlog",
    "labkit-params",
    "scripts/01_measure.py:evaluate_rows",
    "config.json",
)


def readme_route(area: Path, protocol_name: str) -> list[str]:
    """Why the README's route block cannot lead a reader: no block between
    the markers, the protocol or a station not named, or
    `scripts/01_measure.py` without an `evaluate_rows`. No README: nothing.
    The block is checked, never written — finalize reads only; the stamp
    writes it."""
    readme = area / "README.md"
    if not readme.is_file():
        return []
    text = readme.read_text(encoding="utf-8")
    start, end = text.find(ROUTE_START), text.find(ROUTE_END)
    if start < 0 or end < start:
        return [
            f"README.md: no {ROUTE_START} … {ROUTE_END} block — the route "
            f"(protocol · runlog · labkit-params · evaluate_rows · config.json) "
            f"is what a reader opens first"
        ]
    block = text[start:end]
    out = []
    if protocol_name not in block:
        out.append(f"README.md route: does not name {protocol_name}")
    for station in ROUTE_STATIONS:
        if station not in block:
            out.append(f"README.md route: does not name {station}")
    script = area / "scripts" / "01_measure.py"
    if not script.is_file():
        out.append("README.md route: scripts/01_measure.py does not exist")
    elif not any(
        isinstance(n, ast.FunctionDef) and n.name == "evaluate_rows"
        for n in ast.parse(script.read_text(encoding="utf-8")).body
    ):
        out.append("README.md route: scripts/01_measure.py defines no evaluate_rows")
    return out


def check_open_fields(
    findings: Findings, protocol: Path, text: str, head: protocol_block.Head
) -> None:
    """Station 4: fields of the protocol still empty or a placeholder, and
    the README's route block (CS-016)."""
    holes = open_holes(text, head)
    for lineno, label in holes:
        findings.warn(f"{protocol.name}:{lineno}: {label}")
    stale = readme_placeholders(protocol.parent)
    for line in stale:
        findings.warn(f"{line} — a stamped placeholder, fill or delete the line")
    route = readme_route(protocol.parent, protocol.name)
    for line in route:
        findings.warn(line)
    if not holes and not stale and not route:
        print("  all fields filled")


def check_provenance(findings: Findings, area: Path, measurement_run: Path) -> None:
    """Station 5: the run's source frozen in the run, source and output
    tracked in git."""
    b, w = provenance_findings(area, measurement_run)
    for line in b:
        findings.block(line)
    for line in w:
        findings.warn(line)
    if not b and not w:
        print("  source frozen in the run; source and output tracked in git")


def check_area_tests(findings: Findings, area: Path) -> None:
    """Station 6: the area's own tests. The resolution check runs again before a number leaves: a later edit
    of evaluate() that mutes the criterion is caught here too — on every
    tier, seconds included, where preflight is not owed (2026-10-07). A
    missing test is no finding here; preflight owes it at the freeze."""
    tests = area_tests(area, git_root(area) or area)
    if tests.state == "none":
        print(f"  none ({tests.pattern})")
    elif tests.state == "ok":
        print(f"  ok — {', '.join(t.name for t in tests.files)}")
    elif tests.state == "no-pytest":
        findings.warn("pytest is not installed in this interpreter — tests not run")
    else:
        for ln in tests.tail:
            print(f"  {ln}")
        findings.block(
            f"{', '.join(t.name for t in tests.files)} failed — evaluate() no longer holds its resolution check"
        )


def check_criterion_n(findings: Findings, measurement_run: Path) -> None:
    """Station 7: a criterion's denominator that matches no recorded input count."""
    w = criterion_n_input_mismatches(measurement_run)
    for line in w:
        findings.warn(line)
    if not w:
        print("  every c<i>_n equals a recorded input count (or there is none)")


def report(findings: Findings) -> int:
    """The summary: every blocker once more, then the exit code (0 clean, 1
    findings)."""
    print()
    if findings.blocked:
        print(
            f"finalize: {len(findings.blocked)} blocker(s), {findings.warnings} warning(s) — fix the blockers before reporting:"
        )
        for msg in findings.blocked:
            print(f"  - {msg}")
        return 1
    if findings.warnings:
        print(
            f"finalize: 0 blockers, {findings.warnings} warning(s) — review the open fields before reporting."
        )
        return 0
    print("finalize: all clear.")
    return 0


NO_RUN = "  no completed run to check"


def header(title: str) -> None:
    """Print a station's header line."""
    print(f"── {title} ──")


def finalize_area(area: Path, protocol: Path | None = None) -> int:
    """Run finalize on an area. Returns 0 (clean or warnings only),
    1 (a blocker) or 2 (no protocol to hold the area to).

    The flow — every condition that decides whether a step runs is in this
    function; one level down is how a step works, not whether it runs. A
    measurement run is one execution of the experiment's script, a folder
    under `runs/` bound to this protocol — not this function, and not the
    protocol itself.

    0. Choose the protocol and read its settings block. Ends at once with 2
       when the named file is missing, the folder holds several protocols
       and none is named, or the settings block cannot be read.
    1. completion — choose the measurement run the later steps examine
       (`measurement_run`); none bound is a blocker, and steps 3, 5 and 7
       then skip.
    2. intent-check — always; with a measurement run it reads its metrics.
    3. declared scopes — only with a run.
    4. open fields — always; warnings only: protocol placeholders and
       stamped `<…>` placeholders left in the area's README.
    5. provenance — only for cost = seconds, and only with a run.
    6. area tests — always.
    7. criterion n — only with a run; warnings only.

    A blocker never stops a step: all of them run, then the summary lists
    every blocker again. Warnings alone end with 0.
    """
    # 0. protocol and settings — the only early end
    chosen = choose_protocol(area, protocol, "finalize")
    if chosen is None:
        return 2
    text = chosen.read_text(encoding="utf-8")
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        print(f"finalize: {chosen.name}: {exc}")
        return 2
    findings = Findings()

    # 1. completion — the run every later step examines
    header(f"completion: {chosen.name}")
    measurement_run = check_completion(findings, area, text, head.id)

    # 2. intent-check — always
    header("intent-check")
    check_intent_keys_in_metrics(findings, chosen, text, measurement_run)

    # 3. declared scopes — only with a run
    header("declared scopes")
    if measurement_run is None:
        print(NO_RUN)
    else:
        check_declared_scopes(findings, area, measurement_run, head.frozen)

    # 4. open fields — always
    header(f"open fields: {chosen.name}")
    check_open_fields(findings, chosen, text, head)

    # 5. provenance — only for cost = seconds, and only with a run
    header("provenance")
    if head.cost != "seconds":
        print(
            "  n/a — protocol cost is not 'seconds' (the agent audit covers provenance there)"
        )
    elif measurement_run is None:
        print(NO_RUN)
    else:
        check_provenance(findings, area, measurement_run)

    # 6. area tests — always
    header("area tests")
    check_area_tests(findings, area)

    # 7. criterion n — only with a run
    header("criterion n")
    if measurement_run is None:
        print(NO_RUN)
    else:
        check_criterion_n(findings, measurement_run)

    return report(findings)  # 1 if any step found a blocker, else 0


def cited_runs(text: str) -> list[str]:
    """The run ids the protocol's "Answer to the question" cites — a number
    written back. Empty while the field is a placeholder or cites none."""
    for f in fields(text):
        if f.name == "answer to the question" and not f.placeholder:
            return sorted(set(RUN_ID.findall(f.value)))
    return []


def if_reported(protocols: list[Path]) -> int:
    """`finalize` for every protocol whose answer cites a run — the commit
    gate: a number written back does not enter the history unchecked
    (review 2026-10-07: nothing showed whether finalize ever ran). Returns
    the worst exit code; protocols without a cited run are skipped."""
    worst = 0
    for protocol in protocols:
        try:
            text = protocol.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"finalize: {protocol}: {exc}")
            worst = max(worst, 2)
            continue
        if not cited_runs(text):
            continue
        print(f"═══ finalize {protocol} (its answer cites a run) ═══")
        worst = max(worst, finalize_area(protocol.parent, protocol))
    return worst


def main(argv: list[str]) -> int:
    """Command line of `finalize`: check one area, or every protocol whose answer cites a run (`--if-reported`)."""
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: finalize <AREA> [--protocol PROTOCOL-*.md]")
        print(
            "       finalize --if-reported PROTOCOL-*.md ...   (the commit gate: only "
            "protocols whose answer cites a run)"
        )
        return 0 if argv else 2
    if argv[0] == "--if-reported":
        return if_reported([Path(a) for a in argv[1:]])

    area = area_path(argv[0])
    protocol = None
    rest = argv[1:]
    while rest:
        if rest[0] == "--protocol" and len(rest) >= 2:
            protocol = Path(rest[1])
            rest = rest[2:]
            continue
        print(f"finalize: unexpected argument {rest[0]!r}")
        return 2

    if not area.is_dir():
        print(f"finalize: {no_such_area(area)}")
        return 2

    return finalize_area(area, protocol)


def cli() -> None:
    """Console entry point of `finalize`."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
