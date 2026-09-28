"""finalize — the gate after a run, before a number is reported.

Sequences the checks that must pass before results are written back into
the protocol.

    finalize <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 clean, 1 findings (at least one blocker), 2 usage error.

What it runs, in order:
  1. completion     the newest bound run is 'completed'
  2. intent-check   every registered promise has a metrics key (and vice versa)
  3. open fields    protocol fields still holding a placeholder

What it does NOT do: fill fields, edit the protocol, or commit. It is a
read-only gate.
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

from labkit.code_check import find_protocols
from labkit.intent_check import (
    bound_runs,
    main as intent_check_main,
    protocol_id_of,
    registered_ids,
)
from labkit.protocol_fill import open_fields


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
                print(f"  {newest['dir'].name}: completed")

    # -- 2. intent-check ---------------------------------------------------
    print(f"── intent-check ──")
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

    # -- 3. open fields ----------------------------------------------------
    print(f"── open fields: {protocol.name} ──")
    holes = open_fields(text)
    if holes:
        for lineno, label in holes:
            print(f"  {protocol.name}:{lineno}: {label}")
        warnings += len(holes)
    else:
        print("  all fields filled")

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
