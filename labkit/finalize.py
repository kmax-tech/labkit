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


def run(area: Path, protocol: Path | None = None) -> int:
    """Run all finalize checks. Returns 0 (clean) or 1 (findings)."""
    # Every blocker as one line, repeated in the summary: inside a commit
    # hook the sections run to 20 lines and the one blocker drowned in the
    # middle (usability probe 2026-10-07).
    blocked: list[str] = []
    warnings = 0

    # -- resolve protocol -------------------------------------------------
    if protocol is not None:
        if not protocol.is_file():
            print(f"finalize: no such protocol: {protocol}")
            return 2
    else:
        protocols = area_protocols(area)
        if not protocols:
            print(f"finalize: no PROTOCOL-*.md in {area}")
            return 2
        if len(protocols) > 1:
            print(
                f"finalize: {len(protocols)} protocols in {area} — name "
                f"one with --protocol FILE:"
            )
            for p in protocols:
                print(f"  {p}")
            return 2
        protocol = protocols[0]

    text = protocol.read_text(encoding="utf-8")
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        print(f"finalize: {protocol.name}: {exc}")
        return 2
    pid = head.id
    newest_dir: Path | None = None

    # -- 1. completion check -----------------------------------------------
    print(f"── completion: {protocol.name} ──")
    if pid is None:
        print("  no stamped protocol id ([protocol] id) — no run is bound to it")
        blocked.append("no stamped protocol id")
    else:
        runs_dir = area / "runs"
        if not runs_dir.is_dir():
            print(f"  no runs/ directory in {area}")
            blocked.append(f"no runs/ directory in {area}")
        else:
            taken, rest = bound_runs(area, pid)
            if not taken:
                print(f"  no completed run bound to {pid}")
                if rest:
                    for f in rest:
                        print(f"    {f['dir'].name}: {f['why']}")
                blocked.append(f"no completed run bound to {pid}")
            else:
                # ONE choice for every station: intent-check skips newer
                # runs without intent keys (a probe), so checking scopes or
                # provenance on taken[-1] judged the probe while the
                # numbers came from the measurement (review 2026-10-07).
                mpath, skipped = newest_with_intent_keys(taken)
                assert mpath is not None, "taken is non-empty"
                blocking = newer_unreadable(mpath.parent, rest)
                if blocking:
                    print(f"  BLOCKER: {blocking}")
                    blocked.append(blocking)
                newest_dir = mpath.parent
                note = (
                    f" (skipped {skipped} newer bound run(s) without intent keys)"
                    if skipped
                    else ""
                )
                print(f"  {newest_dir.name}: completed{note}")
                cited = cited_runs(text)
                if cited and newest_dir.name not in cited:
                    msg = (
                        f'"Answer to the question" cites {", ".join(cited)}, '
                        f"but the run that answers is {newest_dir.name} — cite the run "
                        f"the checks hold, or rerun"
                    )
                    print(f"  BLOCKER: {msg}")
                    blocked.append(msg)

    # -- 2. intent-check ---------------------------------------------------
    print("── intent-check ──")
    reg = registered_ids(text)
    if not reg:
        print("  no intent ids registered — nothing to check")
    else:
        ic_args = [str(protocol)] + (
            ["--metrics", str(newest_dir / "metrics.json")]
            if newest_dir is not None
            else []
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = intent_check_main(ic_args)
        for line in buf.getvalue().splitlines():
            print(f"  {line}")
        if rc != 0:
            blocked.append("intent-check failed (see its lines above)")

    # -- 2b. declared scopes ------------------------------------------------
    # The run recorded a hash per promise over its declared scope. A scope
    # edited after the run means today's code is not the code that produced
    # the number; until 2026-10-06 only recheck saw it (Durchstich).
    print("── declared scopes ──")
    if newest_dir is None:
        print("  no completed run to check")
    else:
        recorded = (read_run_config(newest_dir) or {}).get("promises")
        if recorded is None:
            print("  no promise block recorded — nothing to compare")
        else:
            drift = promises.scope_drift(recorded, area)
            for d in drift:
                msg = (
                    f"declared scope changed since {newest_dir.name}: "
                    f"{d} — rerun before reporting"
                )
                print(f"  BLOCKER: {msg}")
                blocked.append(msg)
            if not drift:
                print(
                    f"  {len(recorded['ids'])} declared scope(s) unchanged "
                    f"since {newest_dir.name}"
                )

    # -- 3. open fields ----------------------------------------------------
    print(f"── open fields: {protocol.name} ──")
    holes = open_holes(text, head)
    if holes:
        for lineno, label in holes:
            print(f"  {protocol.name}:{lineno}: {label}")
        warnings += len(holes)
    else:
        print("  all fields filled")

    # -- 4. provenance (runs of seconds) ------------------------------------
    print("── provenance ──")
    short = head.cost == "seconds"
    if not short:
        print("  n/a — not a run of seconds (the agent audit covers provenance there)")
    elif newest_dir is None:
        print("  no completed run to check")
    else:
        b, w = provenance_findings(area, newest_dir)
        for line in b:
            print(f"  BLOCKER: {line}")
        for line in w:
            print(f"  warning: {line}")
        if not b and not w:
            print("  source frozen in the run; source and output tracked in git")
        blocked += b
        warnings += len(w)

    # -- 4b. area tests ----------------------------------------------------
    # The resolution check runs again before a number leaves: a later edit
    # of evaluate() that mutes the criterion is caught here too — on every
    # tier, seconds included, where preflight is not owed (2026-10-07). A
    # missing test is no finding here; preflight owes it at the freeze.
    print("── area tests ──")
    tests = area_tests(area, git_root(area) or area)
    if tests.state == "none":
        print(f"  none ({tests.pattern})")
    elif tests.state == "ok":
        print(f"  ok — {', '.join(t.name for t in tests.files)}")
    elif tests.state == "no-pytest":
        print("  warning: pytest is not installed in this interpreter — tests not run")
        warnings += 1
    else:
        for ln in tests.tail:
            print(f"  {ln}")
        msg = f"{', '.join(t.name for t in tests.files)} failed — evaluate() no longer holds its resolution check"
        print(f"  BLOCKER: {msg}")
        blocked.append(msg)

    # -- 5. criterion n ------------------------------------------------------
    print("── criterion n ──")
    if newest_dir is None:
        print("  no completed run to check")
    else:
        w = criterion_n_input_mismatches(newest_dir)
        for line in w:
            print(f"  warning: {line}")
        if not w:
            print("  every c<i>_n equals a recorded input count (or there is none)")
        warnings += len(w)

    # -- summary -----------------------------------------------------------
    print()
    if blocked:
        print(
            f"finalize: {len(blocked)} blocker(s), {warnings} warning(s) "
            f"— fix the blockers before reporting:"
        )
        for msg in blocked:
            print(f"  - {msg}")
        return 1
    if warnings:
        print(
            f"finalize: 0 blockers, {warnings} warning(s) — review "
            f"the open fields before reporting."
        )
        return 0
    print("finalize: all clear.")
    return 0


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
