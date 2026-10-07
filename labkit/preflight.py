"""preflight — the gate before freezing a protocol.

Sequences the checks that must pass before `frozen = true`.
Each check prints its own output; preflight adds a summary line and an
exit code that reflects the worst finding.

    preflight <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 clean, 1 findings (at least one blocker), 2 usage error.

What it runs, in order:
  1. protocol-check   mandatory fields, placeholders
  1b. cost tier       `cost` in the protocol head — `seconds` makes the agent
                      audit optional before freezing (one audit after the
                      first run suffices, AS-017 Die Zahl der Audits folgt der Kostenstufe); `minutes`/`hours` ask
                      for it here; an unfilled cost counts as `hours`
  2. code-check       intent ids against the code
  3. scope-sha        audit stamp over the input scope
  4. dirty check      uncommitted changes (warning, not a blocker)
  5. area tests       tests/test_*<area>*.py via pytest — the resolution
                      check and the parser cases as a permanent test
                      (AS-016 Auflösungsprobe vor dem Einfrieren); a failing test is a blocker, a missing
                      file a warning

What it does NOT do: commit, freeze, or change any file. It is a
read-only gate.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from labkit.code_check import check_intent_ids
from labkit import install_hooks
from labkit.repo import area_protocols, git, git_root, layout_root
from labkit.protocol_check import check_fields, check_protocol_id
from labkit.scope_sha import AREA_GLOBS, area_stamp


def _is_dirty(area: Path) -> bool:
    """Uncommitted changes under `area`; False outside a repo. A git that
    fails inside a repo raises (repo.GitError) — it used to read as clean."""
    return bool(git(["status", "--porcelain"], area))


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
        protocols = area_protocols(area)
        if not protocols:
            print(f"preflight: no PROTOCOL-*.md in {area}")
            return 2
        if len(protocols) > 1:
            print(
                f"preflight: {len(protocols)} protocols in {area} — name "
                f"one with --protocol FILE:"
            )
            for p in protocols:
                print(f"  {p}")
            return 2
        protocol = protocols[0]

    text = protocol.read_text(encoding="utf-8")

    # -- 1. protocol-check ------------------------------------------------
    print(f"── protocol-check: {protocol.name} ──")
    # The same field report as protocol-check (one home): the head, the
    # owed fields by cut, and the graduation at frozen = true.
    report = check_fields(text)
    if report.head is None:
        print(f"  HEAD (must): {report.head_error}")
        return 1
    missing_must, missing_should = report.missing_must, report.missing_should
    must_holes, should_holes = report.must_holes, report.soft_holes
    id_findings = check_protocol_id(protocol, report.head)

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
    if should_holes:
        for n, label in should_holes:
            print(f"  {protocol.name}:{n}: placeholder (should): {label}")
        warnings += len(should_holes)
    if not (
        missing_must or must_holes or id_findings or missing_should or should_holes
    ):
        print("  ok")

    # -- 1b. cost tier ------------------------------------------------------
    print("── cost tier ──")
    tier = report.head.cost
    if tier == "seconds":
        print(
            "  seconds — rerunnable at will: the agent audit is OPTIONAL before "
            "freezing; one audit after the first run, on real output, "
            "suffices (AS-017 Die Zahl der Audits folgt der Kostenstufe)"
        )
    elif tier is None:
        print(
            "  not filled — treated as `hours`: the experiment-preflight "
            "audit is due before freezing (AS-015 Preflight-Audit vor dem Einfrieren); set `cost` in the head "
            "to say otherwise"
        )
    else:
        print(
            f"  {tier} — the experiment-preflight audit is due before freezing (AS-015 Preflight-Audit vor dem Einfrieren)"
        )

    # -- 2. code-check (intent ids) ---------------------------------------
    print("── code-check: intent ids ──")
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
    try:
        sha, _, _ = area_stamp(area)
        print(f"  {sha}")
    except ValueError:
        print(f"  no scripts matching {AREA_GLOBS} in {area} (skipped)")

    # -- 4. dirty check ----------------------------------------------------
    print("── working tree ──")
    repo = layout_root(area)
    if _is_dirty(repo):
        print(f"  WARNING: uncommitted changes in {repo}")
        print("  (not a blocker — commit or stash before the run)")
        warnings += 1
    else:
        print("  clean")

    # -- 4b. hooks -----------------------------------------------------------
    # The gates that do not depend on the agent remembering: a repo without
    # them (or with an older labkit's) runs on good intentions only.
    print("── hooks ──")
    git_repo = git_root(area)
    if git_repo is None:
        print("  n/a — not a git repo")
    else:
        gaps = install_hooks.check(git_repo)
        for g in gaps:
            print(f"  WARNING: {g}")
        if gaps:
            print("  fix with  .venv/bin/labkit-hooks install")
            warnings += 1
        else:
            print("  installed (this labkit's pre-commit, core.hooksPath, claude-hook)")

    # -- 5. area tests -----------------------------------------------------
    print("── tests ──")
    slug = re.sub(r"^\d+-", "", area.name).replace("-", "_")
    tests_dir = repo / "tests"
    tests = sorted(tests_dir.glob(f"test_*{slug}*.py")) if tests_dir.is_dir() else []
    if not tests:
        print(
            f"  WARNING: no tests/test_*{slug}*.py — the resolution check has "
            f"no permanent form (AS-016 Auflösungsprobe vor dem Einfrieren)"
        )
        warnings += 1
    else:
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                *map(str, tests),
            ],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            print(f"  ok — {', '.join(t.name for t in tests)}")
        elif "No module named pytest" in (r.stderr or ""):
            print(
                "  WARNING: pytest is not installed in this interpreter — tests not run"
            )
            warnings += 1
        else:
            tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-6:]
            for ln in tail:
                print(f"  {ln}")
            print(
                f"  BLOCKER: {', '.join(t.name for t in tests)} failed — an "
                f"unfilled or broken resolution check must not pass the freeze"
            )
            blockers += 1

    # -- summary -----------------------------------------------------------
    print()
    if blockers:
        print(
            f"preflight: {blockers} blocker(s), {warnings} warning(s) "
            f"— fix the blockers before freezing."
        )
        return 1
    if warnings:
        print(f"preflight: 0 blockers, {warnings} warning(s) — review before freezing.")
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
