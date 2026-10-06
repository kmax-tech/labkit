"""finalize — the gate after a run, before a number is reported.

Sequences the checks that must pass before results are written back into
the protocol.

    finalize <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 clean, 1 findings (at least one blocker), 2 usage error.

What it runs, in order:
  1. completion     the newest bound run is 'completed'
  2. intent-check   every registered promise has a metrics key (and vice versa)
  2b. scopes        every declared promise scope unchanged since the run
  3. open fields    protocol fields still holding a placeholder
  5. criterion n    every `c<i>_n` (legacy `k<i>_n`) key in metrics.json equals some input
                    count the run recorded (rows of a data= file, lines of
                    an output) — a warning, not a blocker, until the false
                    alarm rate is known (2026-10-05; the denominator class
                    was 31 of 171 audit findings)
  4. provenance     at `Cost: seconds` / the measurement short form: the
                    run froze its source (`data=` in config.json) and every
                    source and output file is tracked in git — the two of
                    the three questions the agent audit kept asking that a
                    machine can answer (§2.A12, 2026-10-05); the third, the
                    counted unit, is the protocol's `Unit:` field

What it does NOT do: fill fields, edit the protocol, or commit. It is a
read-only gate.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

from labkit import promises
from labkit.runs import read_run_config
from labkit.code_check import find_protocols
from labkit.intent_check import (
    bound_runs,
    main as intent_check_main,
    protocol_id_of,
    registered_ids,
)
from labkit.protocol_check import TYPE_MEASUREMENT, cost_tier_of
from labkit.protocol_fill import open_fields


def _git_root(start: Path) -> Path | None:
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                       capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 else None


def _tracked(repo: Path, path: Path) -> bool:
    r = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)], cwd=repo,
                       capture_output=True, text=True)
    return r.returncode == 0


CRITERION_N = promises.CRITERION_N_KEY


def criterion_n_findings(run_dir: Path) -> list[str]:
    """Warnings: a `c<i>_n` (legacy `k<i>_n`) that matches no input count the run recorded."""
    metrics_file = run_dir / "metrics.json"
    if not metrics_file.is_file():
        return []
    metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
    ns = {k: v for k, v in metrics.items() if CRITERION_N.match(k) and isinstance(v, int)}
    if not ns:
        return []
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
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
        return [f"{', '.join(sorted(ns))} present, but the run recorded no input count "
                f"(no data= rows, no output lines) to hold them to"]
    out = []
    for k, n in sorted(ns.items()):
        if n not in counts.values():
            out.append(f"{k} = {n} matches no recorded count "
                       f"({', '.join(f'{a} = {b}' for a, b in sorted(counts.items()))}) — "
                       f"a denominator that is not the input is the audits' most "
                       f"frequent real finding")
    return out


def provenance_findings(area: Path, run_dir: Path) -> tuple[list[str], list[str]]:
    """(blockers, warnings) for a run of seconds: source frozen, files tracked."""
    blockers: list[str] = []
    warnings: list[str] = []
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    data = cfg.get("data") or {}
    if not data:
        blockers.append("source not frozen — the run carries no `data=`; pass "
                        "data={name: path} to runlog.run so sha and rows are recorded")
    sources = [Path(v["path"]) for v in data.values() if isinstance(v, dict) and v.get("path")]
    outputs: list[Path] = []
    outputs_file = run_dir / "outputs.json"
    if outputs_file.is_file():
        outputs = [Path(o["path"]) for o in json.loads(outputs_file.read_text(encoding="utf-8"))
                   if o.get("path")]
    else:
        warnings.append("no outputs.json — the run registered no output file (run.output)")
    repo = _git_root(area)
    if repo is None:
        warnings.append("not a git repository — cannot tell whether source and output are committed")
        return blockers, warnings
    for f in sources:
        if not f.exists():
            blockers.append(f"{f} is gone — the run's rows cannot be re-derived")
        elif not _tracked(repo, f):
            blockers.append(f"source {f} is not tracked in git — commit it, or the number "
                            f"cannot be re-derived")
    # The output rows are born after the run, so on every first pass they are
    # untracked by construction: a warning that names the command, not a
    # blocker that sends the agent round the loop (2026-10-05, five probes).
    for f in outputs:
        if not f.exists():
            blockers.append(f"{f} is gone — the run's rows cannot be re-derived")
        elif not _tracked(repo, f):
            warnings.append(f"output {f.name} is not yet tracked — `git add {f}` before "
                            f"the commit that cites the number")
    return blockers, warnings


def run(area: Path, protocol: Path | None = None) -> int:
    """Run all finalize checks. Returns 0 (clean) or 1 (findings)."""
    blockers = 0
    warnings = 0

    # -- resolve protocol -------------------------------------------------
    if protocol is not None:
        if not protocol.is_file():
            print(f"finalize: no such protocol: {protocol}")
            return 2
    else:
        protocols = find_protocols(area)
        if not protocols:
            print(f"finalize: no PROTOCOL-*.md in {area}")
            return 2
        if len(protocols) > 1:
            print(f"finalize: {len(protocols)} protocols in {area} — name "
                  f"one with --protocol FILE:")
            for p in protocols:
                print(f"  {p}")
            return 2
        protocol = protocols[0]

    text = protocol.read_text(encoding="utf-8")
    pid = protocol_id_of(text)
    newest_dir: Path | None = None

    # -- 1. completion check -----------------------------------------------
    print(f"── completion: {protocol.name} ──")
    if pid is None:
        print("  no protocol id — completion check skipped (below Standard 0.16)")
    else:
        runs_dir = area / "runs"
        if not runs_dir.is_dir():
            print(f"  no runs/ directory in {area}")
            blockers += 1
        else:
            taken, rest = bound_runs(area, pid)
            if not taken:
                print(f"  no completed run bound to {pid}")
                if rest:
                    for f in rest:
                        print(f"    {f['dir'].name}: {f['why']}")
                blockers += 1
            else:
                newest = taken[-1]
                newest_dir = newest["dir"]
                print(f"  {newest_dir.name}: completed")

    # -- 2. intent-check ---------------------------------------------------
    print("── intent-check ──")
    reg = registered_ids(text)
    if not reg:
        print("  no intent ids registered — nothing to check")
    else:
        ic_args = [str(protocol)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = intent_check_main(ic_args)
        for line in buf.getvalue().splitlines():
            print(f"  {line}")
        if rc == 0:
            pass
        elif rc == 2:
            blockers += 1
        else:
            blockers += 1

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
                print(f"  BLOCKER: declared scope changed since {newest_dir.name}: "
                      f"{d} — rerun before reporting")
            if not drift:
                print(f"  {len(recorded['ids'])} declared scope(s) unchanged "
                      f"since {newest_dir.name}")
            blockers += len(drift)

    # -- 3. open fields ----------------------------------------------------
    print(f"── open fields: {protocol.name} ──")
    holes = open_fields(text)
    if holes:
        for lineno, label in holes:
            print(f"  {protocol.name}:{lineno}: {label}")
        warnings += len(holes)
    else:
        print("  all fields filled")

    # -- 4. provenance (runs of seconds) ------------------------------------
    print("── provenance ──")
    short = cost_tier_of(text) == "seconds" or bool(TYPE_MEASUREMENT.search(text))
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
        blockers += len(b)
        warnings += len(w)

    # -- 5. criterion n ------------------------------------------------------
    print("── criterion n ──")
    if newest_dir is None:
        print("  no completed run to check")
    else:
        w = criterion_n_findings(newest_dir)
        for line in w:
            print(f"  warning: {line}")
        if not w:
            print("  every c<i>_n / k<i>_n equals a recorded input count (or there is none)")
        warnings += len(w)

    # -- summary -----------------------------------------------------------
    print()
    if blockers:
        print(f"finalize: {blockers} blocker(s), {warnings} warning(s) "
              f"— fix the blockers before reporting.")
        return 1
    if warnings:
        print(f"finalize: 0 blockers, {warnings} warning(s) — review "
              f"the open fields before reporting.")
        return 0
    print("finalize: all clear.")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: finalize <AREA> [--protocol PROTOCOL-*.md]")
        return 0 if argv else 2

    area = Path(argv[0])
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
        print(f"finalize: no such area: {area}")
        return 2

    return run(area, protocol)


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
