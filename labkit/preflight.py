"""preflight — the gate before freezing a protocol.

Sequences the checks that must pass before `Frozen before run: yes`.
Each check prints its own output; preflight adds a summary line and an
exit code that reflects the worst finding.

    preflight <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 clean, 1 findings (at least one blocker), 2 usage error.

What it runs, in order:
  1. protocol-check   mandatory fields, placeholders
  2. code-check       intent ids against the code
  3. scope-sha        audit stamp over the input scope
  4. dirty check      uncommitted changes (warning, not a blocker)
  5. area tests       tests/test_*<area>*.py via pytest — the resolution
                      check and the parser cases as a permanent test
                      (§2.A13); a failing test is a blocker, a missing
                      file a warning

What it does NOT do: commit, freeze, or change any file. It is a
read-only gate.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from labkit.code_check import check_intent_ids, find_protocols, find_repo
from labkit.protocol_check import (
    DEFAULT_STANDARD,
    STANDARD_VERSION,
    TYPE_MEASUREMENT,
    check_protocol_id,
    check_text,
    placeholder_fields,
    severity_of,
)
from labkit.scope_sha import scope_sha, find_pin, AREA_GLOBS


def _git(args: list[str], cwd: Path) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _is_dirty(area: Path) -> bool:
    return bool(_git(["status", "--porcelain"], area))


def run(area: Path, protocol: Path | None = None) -> int:
    """Run all preflight checks. Returns 0 (clean) or 1 (findings)."""
    blockers = 0
    warnings = 0

    # -- resolve protocol -------------------------------------------------
    if protocol is not None:
        if not protocol.is_file():
            print(f"preflight: no such protocol: {protocol}")
            return 2
    else:
        protocols = find_protocols(area)
        if not protocols:
            print(f"preflight: no PROTOCOL-*.md in {area}")
            return 2
        if len(protocols) > 1:
            print(f"preflight: {len(protocols)} protocols in {area} — name "
                  f"one with --protocol FILE:")
            for p in protocols:
                print(f"  {p}")
            return 2
        protocol = protocols[0]

    text = protocol.read_text(encoding="utf-8")
    std_m = STANDARD_VERSION.search(text)
    standard = std_m.group(1) if std_m else DEFAULT_STANDARD

    # -- 1. protocol-check ------------------------------------------------
    print(f"── protocol-check: {protocol.name} ──")
    is_measurement = bool(TYPE_MEASUREMENT.search(text))
    missing_must, missing_should = check_text(
        text, measurement=is_measurement, standard=standard)
    holes = placeholder_fields(text)
    must_holes = [(n, l) for n, l in holes if severity_of(l) == "must"]
    id_findings = check_protocol_id(protocol, text, standard)

    if missing_must:
        for label in missing_must:
            print(f"  MISSING (must): {label}")
        blockers += len(missing_must)
    if must_holes:
        for n, label in must_holes:
            print(f"  {protocol.name}:{n}: PLACEHOLDER (must): {label}")
        blockers += len(must_holes)
    if id_findings:
        for f in id_findings:
            print(f"  {f}")
        blockers += len(id_findings)
    if missing_should:
        for label in missing_should:
            print(f"  missing (should): {label}")
        warnings += len(missing_should)
    should_holes = [(n, l) for n, l in holes if severity_of(l) == "should"]
    if should_holes:
        for n, label in should_holes:
            print(f"  {protocol.name}:{n}: placeholder (should): {label}")
        warnings += len(should_holes)
    if not (missing_must or must_holes or id_findings or missing_should
            or should_holes):
        print("  ok")

    # -- 2. code-check (intent ids) ---------------------------------------
    print(f"── code-check: intent ids ──")
    findings = check_intent_ids(area, protocol)
    for f in findings:
        print(f"  {f}")
    code_blockers = sum(1 for f in findings if f.startswith("BLOCKER"))
    code_warnings = sum(1 for f in findings if f.startswith("WARNING"))
    blockers += code_blockers
    warnings += code_warnings
    if not findings:
        print("  ok")

    # -- 3. scope-sha ------------------------------------------------------
    print("── scope-sha ──")
    scripts = [p for g in AREA_GLOBS for p in sorted(area.glob(g))]
    if scripts:
        try:
            pin_info = find_pin(find_repo(area))
            pin = pin_info[1] if pin_info else None
            sha = scope_sha(scripts, pin)
            print(f"  {sha}")
        except Exception as e:
            print(f"  ERROR: {e}")
            blockers += 1
    else:
        print(f"  no scripts matching {AREA_GLOBS} in {area} (skipped)")

    # -- 4. dirty check ----------------------------------------------------
    print(f"── working tree ──")
    repo = find_repo(area)
    if _is_dirty(repo):
        print(f"  WARNING: uncommitted changes in {repo}")
        print(f"  (not a blocker — commit or stash before the run)")
        warnings += 1
    else:
        print("  clean")

    # -- 5. area tests -----------------------------------------------------
    print("── tests ──")
    slug = re.sub(r"^\d+-", "", area.name).replace("-", "_")
    tests_dir = repo / "tests"
    tests = sorted(tests_dir.glob(f"test_*{slug}*.py")) if tests_dir.is_dir() else []
    if not tests:
        print(f"  WARNING: no tests/test_*{slug}*.py — the resolution check has "
              f"no permanent form (§2.A13)")
        warnings += 1
    else:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            *map(str, tests)], cwd=repo, capture_output=True, text=True)
        if r.returncode == 0:
            print(f"  ok — {', '.join(t.name for t in tests)}")
        elif "No module named pytest" in (r.stderr or ""):
            print("  WARNING: pytest is not installed in this interpreter — tests not run")
            warnings += 1
        else:
            tail = [l for l in (r.stdout or "").splitlines() if l.strip()][-6:]
            for l in tail:
                print(f"  {l}")
            print(f"  BLOCKER: {', '.join(t.name for t in tests)} failed — an "
                  f"unfilled or broken resolution check must not pass the freeze")
            blockers += 1

    # -- summary -----------------------------------------------------------
    print()
    if blockers:
        print(f"preflight: {blockers} blocker(s), {warnings} warning(s) "
              f"— fix the blockers before freezing.")
        return 1
    if warnings:
        print(f"preflight: 0 blockers, {warnings} warning(s) — review "
              f"before freezing.")
        return 0
    print("preflight: all clear.")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: preflight <AREA> [--protocol PROTOCOL-*.md]")
        return 0 if argv else 2

    area = Path(argv[0])
    protocol = None
    rest = argv[1:]
    while rest:
        if rest[0] == "--protocol" and len(rest) >= 2:
            protocol = Path(rest[1])
            rest = rest[2:]
            continue
        print(f"preflight: unexpected argument {rest[0]!r}")
        return 2

    if not area.is_dir():
        print(f"preflight: no such area: {area}")
        return 2

    return run(area, protocol)


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
