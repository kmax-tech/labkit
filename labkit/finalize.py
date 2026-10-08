"""finalize — the gate after a run, before a number is reported.

Sequences the checks that must pass before results are written back into
the protocol.

    finalize <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 clean, 1 findings (at least one blocker), 2 usage error.

What it runs, in order:
  1. completion     the run that answers — the newest completed bound run
                    reporting intent keys, the same choice as intent-check —
                    and every later station checks THAT run
  2. intent-check   every registered promise has a metrics key (and vice versa)
  2b. scopes        every declared promise scope unchanged since the run
  3. open fields    protocol fields still holding a placeholder
  4. provenance     at `cost = "seconds"`: the
                    run froze its source (`data=` in config.json) and every
                    source and output file is tracked in git — the two of
                    the three questions the agent audit kept asking that a
                    machine can answer (AS-017 Die Zahl der Audits folgt der Kostenstufe, 2026-10-05); the third, the
                    counted unit, is the protocol's `Unit` field
  4b. area tests    tests/test_<NN>_<name>.py via the repo's interpreter, on
                    every tier: a failing test is a blocker (evaluate() lost
                    its resolution check), a missing one no finding here
  5. criterion n    every `c<i>_n` key in metrics.json equals some input
                    count the run recorded (rows of a data= file, lines of
                    an output) — a warning, not a blocker, until the false
                    alarm rate is known (2026-10-05; the denominator class
                    was 31 of 171 audit findings)

What it does NOT do: fill fields, edit the protocol, or commit. It is a
read-only gate.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from labkit import promises, protocol_block
from labkit.runs import read_run_config
from labkit.repo import area_path, area_protocols, git_root, git_run, no_such_area
from labkit.intent_check import (
    bound_runs,
    main as intent_check_main,
    newer_unreadable,
    newest_with_intent_keys,
    registered_ids,
)
from labkit.preflight import area_tests
from labkit.protocol_check import RUN_ID, fields, open_holes


def _tracked(repo: Path, path: Path) -> bool:
    """Is `path` tracked in `repo`? The exit code is the answer."""
    return git_run(["ls-files", "--error-unmatch", str(path)], repo).returncode == 0


CRITERION_N = promises.CRITERION_N_KEY


def criterion_n_input_mismatches(run_dir: Path) -> list[str]:
    """Warnings: a criterion's denominator (`c<i>_n` in metrics.json) that
    matches no input count the run recorded — the size of what was counted,
    not a promised constant (that is `intent_check.promised_constant_mismatches`)."""
    metrics_file = run_dir / "metrics.json"
    if not metrics_file.is_file():
        return []
    metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
    ns = {
        k: v for k, v in metrics.items() if CRITERION_N.match(k) and isinstance(v, int)
    }
    if not ns:
        return []
    cfg = read_run_config(run_dir) or {}
    counts: dict[str, int] = {}
    for key, d in (cfg.get("data") or {}).items():
        if isinstance(d, dict) and isinstance(d.get("rows"), int):
            counts[f"data[{key}].rows"] = d["rows"]
    outputs_file = run_dir / "outputs.json"
    if outputs_file.is_file():
        for o in json.loads(outputs_file.read_text(encoding="utf-8")):
            if isinstance(o.get("lines"), int):
                counts[f"{Path(o['path']).name} lines"] = o["lines"]
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


def provenance_findings(area: Path, run_dir: Path) -> tuple[list[str], list[str]]:
    """(blockers, warnings) for a run of seconds: source frozen, files tracked."""
    blockers: list[str] = []
    warnings: list[str] = []
    cfg = read_run_config(run_dir) or {}
    data = cfg.get("data") or {}
    if not data:
        blockers.append(
            "source not frozen — the run carries no `data=`; pass "
            "data={name: path} to runlog.run so sha and rows are recorded"
        )
    sources = [
        Path(v["path"]) for v in data.values() if isinstance(v, dict) and v.get("path")
    ]
    outputs: list[Path] = []
    outputs_file = run_dir / "outputs.json"
    if outputs_file.is_file():
        outputs = [
            Path(o["path"])
            for o in json.loads(outputs_file.read_text(encoding="utf-8"))
            if o.get("path")
        ]
    else:
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
class Gate:
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


def choose_protocol(area: Path, protocol: Path | None) -> Path | None:
    """The protocol finalize holds the area to: the named one, else the
    area's only one. Prints why and returns None when there is none, or
    several and none is named — finalize refuses to guess."""
    if protocol is not None:
        if not protocol.is_file():
            print(f"finalize: no such protocol: {protocol}")
            return None
        return protocol
    protocols = area_protocols(area)
    if not protocols:
        print(f"finalize: no PROTOCOL-*.md in {area}")
        return None
    if len(protocols) > 1:
        print(
            f"finalize: {len(protocols)} protocols in {area} — name one with --protocol FILE:"
        )
        for p in protocols:
            print(f"  {p}")
        return None
    return protocols[0]


def answering_run(gate: Gate, area: Path, pid: str | None) -> Path | None:
    """The run every station holds the protocol to: the newest completed run
    bound to it that reports intent keys. ONE choice for every station:
    intent-check skips newer runs without intent keys (a probe), so checking
    scopes or provenance on the newest run judged the probe while the
    numbers came from the measurement (review 2026-10-07)."""
    if pid is None:
        gate.block("no stamped protocol id ([protocol] id) — no run is bound to it")
        return None
    if not (area / "runs").is_dir():
        gate.block(f"no runs/ directory in {area}")
        return None
    taken, rest = bound_runs(area, pid)
    if not taken:
        gate.block(f"no completed run bound to {pid}")
        for f in rest:
            print(f"    {f['dir'].name}: {f['why']}")
        return None
    mpath, skipped = newest_with_intent_keys(taken)
    assert mpath is not None, "taken is non-empty"
    blocking = newer_unreadable(mpath.parent, rest)
    if blocking:
        gate.block(blocking)
    note = (
        f" (skipped {skipped} newer bound run(s) without intent keys)"
        if skipped
        else ""
    )
    print(f"  {mpath.parent.name}: completed{note}")
    return mpath.parent


def cited_run_mismatch(text: str, run_dir: Path) -> str | None:
    """A blocker when the protocol's answer cites runs and not the one the
    checks hold; None when it cites that run or none."""
    cited = cited_runs(text)
    if cited and run_dir.name not in cited:
        return (
            f'"Answer to the question" cites {", ".join(cited)}, '
            f"but the run that answers is {run_dir.name} — cite the run "
            f"the checks hold, or rerun"
        )
    return None


def check_completion(gate: Gate, area: Path, text: str, pid: str | None) -> Path | None:
    """Station 1: the run every later station holds the protocol to — chosen,
    shown, and held to the run the answer cites. Returns it, or None."""
    run_dir = answering_run(gate, area, pid)
    if run_dir is not None:
        mismatch = cited_run_mismatch(text, run_dir)
        if mismatch:
            gate.block(mismatch)
    return run_dir


def check_intent_keys_in_metrics(
    gate: Gate, protocol: Path, text: str, run_dir: Path | None
) -> None:
    """Station 2: every registered intent id reports as a key of the answering
    run's metrics.json (intent-check). Not code_check.check_intent_ids, which
    holds the promises to the code before any run."""
    if not registered_ids(text):
        print("  no intent ids registered — nothing to check")
        return
    args = [str(protocol)] + (
        ["--metrics", str(run_dir / "metrics.json")] if run_dir is not None else []
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = intent_check_main(args)
    for line in buf.getvalue().splitlines():
        print(f"  {line}")
    if rc != 0:
        gate.block("intent-check failed (see its lines above)")


def check_declared_scopes(gate: Gate, area: Path, run_dir: Path) -> None:
    """Station 3: a promise's declared scope edited after the run: today's code is not
    the code that produced the number; until 2026-10-06 only recheck saw it
    (Durchstich)."""
    recorded = (read_run_config(run_dir) or {}).get("promises")
    if recorded is None:
        print("  no promise block recorded — nothing to compare")
        return
    drift = promises.scope_drift(recorded, area)
    for d in drift:
        gate.block(
            f"declared scope changed since {run_dir.name}: {d} — rerun before reporting"
        )
    if not drift:
        print(
            f"  {len(recorded['ids'])} declared scope(s) unchanged since {run_dir.name}"
        )


def check_open_fields(
    gate: Gate, protocol: Path, text: str, head: protocol_block.Head
) -> None:
    """Station 4: fields of the protocol still empty or a placeholder."""
    holes = open_holes(text, head)
    for lineno, label in holes:
        gate.warn(f"{protocol.name}:{lineno}: {label}")
    if not holes:
        print("  all fields filled")


def provenance_owed(head: protocol_block.Head) -> bool:
    """Whether finalize checks provenance (source frozen in the run, source
    and output tracked in git): only for runs of seconds — above that tier
    the agent audit covers provenance."""
    return head.cost == "seconds"


def check_provenance(gate: Gate, area: Path, run_dir: Path) -> None:
    """Station 5: the run's source frozen in the run, source and output
    tracked in git."""
    b, w = provenance_findings(area, run_dir)
    for line in b:
        gate.block(line)
    for line in w:
        gate.warn(line)
    if not b and not w:
        print("  source frozen in the run; source and output tracked in git")


def check_area_tests(gate: Gate, area: Path) -> None:
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
        gate.warn("pytest is not installed in this interpreter — tests not run")
    else:
        for ln in tests.tail:
            print(f"  {ln}")
        gate.block(
            f"{', '.join(t.name for t in tests.files)} failed — evaluate() no longer holds its resolution check"
        )


def check_criterion_n(gate: Gate, run_dir: Path) -> None:
    """Station 7: a criterion's denominator that matches no recorded input count."""
    w = criterion_n_input_mismatches(run_dir)
    for line in w:
        gate.warn(line)
    if not w:
        print("  every c<i>_n equals a recorded input count (or there is none)")


def report(gate: Gate) -> int:
    """The summary: every blocker once more, then the exit code (0 clean, 1
    findings)."""
    print()
    if gate.blocked:
        print(
            f"finalize: {len(gate.blocked)} blocker(s), {gate.warnings} warning(s) — fix the blockers before reporting:"
        )
        for msg in gate.blocked:
            print(f"  - {msg}")
        return 1
    if gate.warnings:
        print(
            f"finalize: 0 blockers, {gate.warnings} warning(s) — review the open fields before reporting."
        )
        return 0
    print("finalize: all clear.")
    return 0


NO_RUN = "  no completed run to check"


def header(title: str) -> None:
    """Print a station's header line."""
    print(f"── {title} ──")


def run(area: Path, protocol: Path | None = None) -> int:
    """Run finalize on an area. Returns 0 (clean or warnings only),
    1 (a blocker) or 2 (no protocol to hold the area to).

    The flow — every condition that decides whether a step runs is in this
    function; one level down is how a step works, not whether it runs:

    0. Choose the protocol and read its settings block. Ends at once with 2
       when the named file is missing, the folder holds several protocols
       and none is named, or the settings block cannot be read.
    1. completion — choose the run the later steps examine (`run_dir`);
       none bound is a blocker, and steps 3, 5 and 7 then skip.
    2. intent-check — always; with a run it reads that run's metrics.
    3. declared scopes — only with a run.
    4. open fields — always; warnings only.
    5. provenance — only for cost = seconds, and only with a run.
    6. area tests — always.
    7. criterion n — only with a run; warnings only.

    A blocker never stops a step: all of them run, then the summary lists
    every blocker again. Warnings alone end with 0.
    """
    # 0. protocol and settings — the only early end
    chosen = choose_protocol(area, protocol)
    if chosen is None:
        return 2
    text = chosen.read_text(encoding="utf-8")
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        print(f"finalize: {chosen.name}: {exc}")
        return 2
    gate = Gate()

    # 1. completion — the run every later step examines
    header(f"completion: {chosen.name}")
    run_dir = check_completion(gate, area, text, head.id)

    # 2. intent-check — always
    header("intent-check")
    check_intent_keys_in_metrics(gate, chosen, text, run_dir)

    # 3. declared scopes — only with a run
    header("declared scopes")
    if run_dir is None:
        print(NO_RUN)
    else:
        check_declared_scopes(gate, area, run_dir)

    # 4. open fields — always
    header(f"open fields: {chosen.name}")
    check_open_fields(gate, chosen, text, head)

    # 5. provenance — only for cost = seconds, and only with a run
    header("provenance")
    if not provenance_owed(head):
        print("  n/a — not a run of seconds (the agent audit covers provenance there)")
    elif run_dir is None:
        print(NO_RUN)
    else:
        check_provenance(gate, area, run_dir)

    # 6. area tests — always
    header("area tests")
    check_area_tests(gate, area)

    # 7. criterion n — only with a run
    header("criterion n")
    if run_dir is None:
        print(NO_RUN)
    else:
        check_criterion_n(gate, run_dir)

    return report(gate)


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
        worst = max(worst, run(protocol.parent, protocol))
    return worst


def main(argv: list[str]) -> int:
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

    return run(area, protocol)


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
