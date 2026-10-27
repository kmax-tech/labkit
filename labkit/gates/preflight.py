"""preflight — the gate before freezing a protocol.

Sequences the checks that must pass before `frozen = true`. Each station
tells what it found through the gate's one channel (`gate.Findings`);
preflight adds a summary line and an exit code that reflects the worst
finding.

    preflight <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 no blocker (warnings may stand), 1 at least one blocker,
2 usage error. One early end: a protocol head that does not parse ends
station 1 with exit 1 and nothing after it runs. Any other blocker lets
the later stations run; the summary names every blocker again.

What it runs, in order (`preflight_area` shows each station's condition):
  0. protocol        the named PROTOCOL-*.md or the area's only one
  1. protocol-check  mandatory fields, placeholders, the stamped id, a repeat_cost
                     tier lowered since the first commit; an unparseable
                     head ends here
  2. repeat cost       what the lane (`standard_contract.lane`) owes before the
                     freeze: at `low` the agent audit is OPTIONAL (one
                     audit after the first run suffices,
                     LAB-017 The number of audits follows the cost tier);
                     `high` ask for it here; an unfilled repeat cost
                     counts as `high`. Told, never counted — "audit due" is
                     a reminder, not a blocker; so is the cold-reader line
                     (LAB-102 Cold reader before freezing)
  3. audit findings  the records `labkit-audit` wrote (`audits/*.toml`,
                     `labkit.formats.findings`): a finding still `open` is a
                     warning, a blocker once frozen = true; an unreadable
                     record is a blocker. Where the lane owes the freeze and
                     the head names a preflight record, that record must be
                     one of the code and the promise block as they are now,
                     decided (`findings.audit_record_gap`, the same answer
                     runlog's freeze gate gives). A `deferred` finding in another
                     area of the repo is told as a reminder, never counted
  4. code-check      its automated checks (`code_check.code_findings`):
                     intent ids against the code, parser fixtures, prompt
                     drift, and the code the stamp cannot follow (sys.path
                     edits, dynamic loaders, imports outside lib/ and src/
                     — static evidence, warnings); each finding carries
                     its grade as data
  5. scope-sha       audit stamp over the input scope; told
  6. working tree    uncommitted changes (warning, not a blocker)
  7. hooks           the installed labkit hooks match this labkit (warning);
                     outside a git repo there is nothing to check
  8. area tests      tests/test_<NN>_<name>.py via pytest — the resolution
                     check and the parser cases as a permanent test
                     (LAB-016 Resolution check before freezing); a failing
                     test is a blocker, a missing file a warning — a
                     blocker once frozen = true
  9. summary         1 with a blocker, else 0

What it does NOT do: commit, freeze, or change any file. It is a
read-only gate.
"""

from __future__ import annotations

from collections.abc import Callable

from dataclasses import dataclass
import subprocess
import sys
from pathlib import Path

from labkit.formats.gate import GUARANTEED, STATIC_EVIDENCE
from labkit.checks.code_check import code_findings
from labkit.formats import (
    console,
    handovers,
    promises,
    protocol_block,
    protocol_check,
    standard_contract,
)
from labkit.gates import install_hooks
from labkit.formats import findings as audit_findings
from labkit.formats.gate import EXIT_CONTRACT, Findings
from labkit.formats.repo import (
    AmbiguousArea,
    area_path,
    choose_protocol,
    git_root,
    tree_dirty,
    layout_root,
    no_such_area,
    split_area_name,
)
from labkit.formats.protocol_check import check_fields
from labkit.formats.protocol_history import (
    check_annotation_validity,
    check_protocol_id,
    repeat_cost_lowered,
)
from labkit.formats.protocol_block import repo_protocol_ids
from labkit.formats.scope_sha import AREA_GLOBS, area_stamp


@dataclass(frozen=True)
class AreaTests:
    """What running an area's own tests found."""

    pattern: str  # what was looked for, for the message
    files: list[Path]
    state: str  # "none" | "ok" | "failed" | "no-pytest"
    tail: list[str]  # the last lines of a failing run


def area_test_python(repo: Path) -> str:
    """The Python installation that runs an area's tests: the repo's own
    `.venv`, else the one running labkit. The repo's, not the caller's — the
    tests import the repo's dependencies, and a gate run from another venv
    failed them on a missing package (uniagent, 2026-10-07)."""
    own = repo / ".venv" / "bin" / "python"
    return str(own) if own.is_file() else sys.executable


#: how long an area's tests may run inside a gate; a hanging test hung the
#: gate until the hook's own timeout killed it, wordless (audit 2026-10-15)
AREA_TEST_TIMEOUT_S = 300.0


def area_tests(area: Path, repo: Path) -> AreaTests:
    """Run the area's tests (`tests/test_*<slug>*.py`) — the resolution
    check and the parser cases in their permanent form. One home for
    preflight (before the freeze) and finalize (before a number is
    reported)."""
    # The name the scaffolder stamps: test_<NN>_<name>.py (or test_<name>.py
    # for an unnumbered area), split files as test_<NN>_<name>_<part>.py.
    # A bare *<name>* glob ran area 09's test for area 08, whose name is a
    # prefix of 09's (uniagent, 2026-10-07).
    # `preflight .` passes a relative path whose .name is "" — resolved first,
    # or the pattern read `tests/test_.py` and the area's test was "none"
    # (fallacy-dataset-generation, 2026-10-09)
    area = area.resolve()
    nn, name = split_area_name(area.name)
    stem = (f"test_{nn}_" if nn else "test_") + name.replace("-", "_")
    pattern = f"tests/{stem}.py"
    tests_dir = repo / "tests"
    files = (
        sorted({*tests_dir.glob(f"{stem}.py"), *tests_dir.glob(f"{stem}_*.py")})
        if tests_dir.is_dir()
        else []
    )
    if not files:
        return AreaTests(pattern, [], "none", [])
    try:
        r = subprocess.run(
            [
                area_test_python(repo),
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                *map(str, files),
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=AREA_TEST_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return AreaTests(
            pattern,
            files,
            "failed",
            [
                f"timed out after {AREA_TEST_TIMEOUT_S:g} s — a test that hangs is a failing test"
            ],
        )
    if r.returncode == 0:
        return AreaTests(pattern, files, "ok", [])
    if "No module named pytest" in (r.stderr or ""):
        return AreaTests(pattern, files, "no-pytest", [])
    tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-6:]
    return AreaTests(pattern, files, "failed", tail)


def preflight_area(
    area: Path, protocol: Path | None = None, findings: Findings | None = None
) -> int:
    """The gate before the freeze, on AREA. Returns 0 (clean or warnings
    only), 1 (a blocker) or 2 (no protocol to hold the area to). FINDINGS,
    when given, collects what the stations found and is the channel every
    line goes through (`gate.Findings`), as for `finalize_area`: the pre-run
    hook hands over a silent one and reads the blockers as data instead of
    the printed report (audit 2026-10-27, third, M4).

    The flow — every condition that decides whether a station runs is in
    this function; one level down is how a station checks, not whether it
    runs:

    0. Choose the protocol and read it. Ends at once with 2 when the named
       file is missing or the folder holds several protocols and none is
       named.
    1. protocol-check — fields, placeholders, id, repeat_cost. A head that does
       not parse is the one early end: the blocker is told, the summary
       follows, exit 1 — the later stations would read a head that is not
       there.
    2. repeat cost — what the lane owes before the freeze; told, never
       counted.
    3. audit findings — every record of the area, always; the audit
       line's coverage only where the lane owes the freeze and the head
       carries the line; the deferred findings elsewhere in the repo
       always, as a reminder.
    4. code-check — always.
    5. scope-sha — always; told.
    6. working tree — always.
    7. hooks — only inside a git repo.
    8. area tests — always; frozen = true grades a missing test a blocker.
    9. summary — 1 if any station found a blocker, else 0.

    A blocker never stops a later station (the head aside): every station
    runs, then the summary names every blocker again. Warnings alone end
    with 0.
    """
    findings = findings if findings is not None else Findings()

    # 0. protocol — the only exit 2
    protocol = choose_protocol(area, protocol, "preflight")
    if protocol is None:
        return 2
    text = protocol.read_text(encoding="utf-8")

    # 1. protocol-check — the one early end: a head nobody can read
    findings.header(f"protocol-check: {protocol.name}")
    report = check_fields(text)  # the same field report as protocol-check
    if report.head is None:
        findings.block(f"HEAD (must): {report.head_error}")
        return findings.report("preflight", "freezing")  # exit 1, nothing after
    head = report.head
    check_protocol_fields(findings, protocol, report, head)

    # the facts every later station reads, read once
    lane = standard_contract.lane(head.repeat_cost)
    frozen = head.frozen
    repo = layout_root(area)
    git_repo = git_root(area)

    # 2. repeat cost — told, never counted
    findings.header("repeat cost")
    for line in repeat_cost_lines(head.repeat_cost, lane):
        findings.note(line)

    # 3. audit findings — the records always; the line's coverage where the
    #    lane owes the freeze and a line is stamped; deferred elsewhere always
    findings.header("audit findings")
    records = check_audit_records(findings, area, frozen=frozen)
    if lane.freeze and head.preflight_audit:
        check_audit_coverage(findings, area, head.preflight_audit, text, frozen=frozen)
    check_deferred_elsewhere(findings, area, records)

    # 4. code-check — always
    findings.header("code-check: intent ids, stamp coverage")
    check_code(findings, area, protocol, repo)

    # 5. scope-sha — always; told
    findings.header("scope-sha")
    findings.note(scope_stamp_line(area))

    # 6. working tree — always
    findings.header("working tree")
    check_working_tree(findings, repo)

    # 7. hooks — only inside a git repo
    findings.header("hooks")
    if git_repo is None:
        findings.note("  n/a — not a git repo")
    else:
        check_hooks(findings, git_repo)

    # 8. area tests — always; frozen = true owes the file
    findings.header("tests")
    check_tests_owed(findings, area_tests(area, repo), frozen=frozen)

    # 9. summary
    return findings.report("preflight", "freezing")  # 1 with a blocker, else 0


def check_protocol_fields(
    findings: Findings,
    protocol: Path,
    report: "protocol_check.FieldReport",
    head: "protocol_block.Head",
) -> None:
    """Station 1: the field report of protocol-check (REPORT: the owed
    fields by cut, the graduation at frozen = true), the stamped id against
    the repo's others and the bound annotation evidence
    (`check_annotation_validity`), a repeat cost lowered since the first commit. A must
    gap or a must placeholder blocks; a should gap, a should placeholder
    and a lowered tier warn; an id finding carries its grade (a changed id
    warns, a doubled one blocks)."""
    ids = repo_protocol_ids(protocol)
    id_findings = check_protocol_id(protocol, head, ids) + check_annotation_validity(
        protocol, protocol.read_text(encoding="utf-8"), ids
    )
    lowered = repeat_cost_lowered(protocol, head)
    for label in report.missing_must:
        findings.block(f"MISSING (must): {label}")
    for n, label in report.must_holes:
        findings.block(f"{protocol.name}:{n}: PLACEHOLDER (must): {label}")
    for finding in id_findings:
        findings.take(finding)
    if lowered:
        findings.warn(lowered, evidence_kind=STATIC_EVIDENCE)
    for label in report.missing_should:
        findings.warn(f"missing (should): {label}", evidence_kind=GUARANTEED)
    for n, label in report.soft_holes:
        findings.warn(
            f"{protocol.name}:{n}: placeholder (should): {label}",
            evidence_kind=GUARANTEED,
        )
    if not (
        report.missing_must
        or report.must_holes
        or id_findings
        or lowered
        or report.missing_should
        or report.soft_holes
    ):
        findings.note("  ok")


def repeat_cost_lines(
    repeat_cost: str | None, lane: "standard_contract.Lane"
) -> list[str]:
    """Station 2: what the lane owes before the freeze, in sentences — the
    audit where LANE owes the freeze (an unfilled COST reads as high), the
    cold reader always. Told by the caller, counted by nobody."""
    if not lane.freeze:
        audit = (
            f"  {lane.repeat_cost} — rerunnable at will: the agent audit is OPTIONAL before "
            "freezing; one audit after the first run, on real output, "
            "suffices (LAB-017 The number of audits follows the cost tier)"
        )
    elif repeat_cost is None:
        audit = (
            "  not filled — treated as `high`: the experiment-preflight "
            "audit is due before freezing (LAB-015 Preflight audit before freezing); set `repeat_cost` in the head "
            "to say otherwise"
        )
    else:
        audit = f"  {repeat_cost} — the experiment-preflight audit is due before freezing (LAB-015 Preflight audit before freezing)"
    return [
        audit,
        "  a cold reader is due while the prose can still change (LAB-102 Cold reader before freezing): `labkit-audit <AREA> --mode clarity` — static "
        "evidence, never blocks",
    ]


def _owed(findings: Findings, frozen: bool) -> Callable[[str], None]:
    """How a gap the freeze owes is told: a blocker once FROZEN, else a
    warning — a mechanical fact either way (GUARANTEED)."""
    if frozen:
        return findings.block
    return lambda msg: findings.warn(msg, evidence_kind=GUARANTEED)


def check_audit_records(
    findings: Findings, area: Path, *, frozen: bool
) -> list[audit_findings.Record]:
    """Station 3, the records: every finding still `open` in the area's
    audit records, each with its file — a warning before the freeze, a
    blocker once FROZEN (frozen = true owes every decision,
    LAB-015 Preflight audit before freezing). A record nobody can read is
    a blocker. Returns the records read (none after an unreadable one), for
    the station's closing line."""
    try:
        records = audit_findings.area_records(area)
    except audit_findings.FindingsError as exc:
        findings.block(str(exc))
        return []
    undecided = audit_findings.open_findings(records)  # the table of the gates' rules
    for u in undecided:
        _owed(findings, frozen)(f"undecided in {u.line}")
    if undecided:
        findings.note(
            f"  {len(undecided)} finding(s) still `open` — decide each ({audit_findings.DECIDED_LIST}) "
            f"with `labkit-audit <area> --decide` before freezing (LAB-015 Preflight audit before freezing)"
            + (" — frozen = true owes it" if frozen else "")
        )
    return records


def check_audit_coverage(
    findings: Findings, area: Path, audit_line: str, text: str, *, frozen: bool
) -> None:
    """Station 3, the record: why the record the head's AUDIT_LINE names
    does not cover a full run of this code and the promise block TEXT
    carries now (`findings.audit_record_gap`, the same answer runlog's
    freeze gate gives — preflight must not pass a state the run refuses).
    A gap warns, and blocks once FROZEN."""
    gap = audit_findings.audit_record_gap(area, audit_line, text)
    if gap:
        _owed(findings, frozen)(
            f"preflight_audit: {gap} (LAB-015 Preflight audit before freezing)"
        )


def check_deferred_elsewhere(
    findings: Findings, area: Path, records: list[audit_findings.Record]
) -> None:
    """Station 3, the reminder: every `deferred` finding in another area of
    the repo, told and never counted — a finding deferred there as "its own
    task" may be this area's; one a handover of that area lists
    (`handovers.handed_over`) is told as handed over unresolved, no result
    released, the rest as set aside for later; a record elsewhere nobody
    can read warns.
    Closes the station with what RECORDS (this area's) say when nothing is
    open."""
    experiments = area.resolve().parent
    try:
        elsewhere = audit_findings.deferred_elsewhere(area, experiments)
    except audit_findings.FindingsError as exc:
        findings.warn(str(exc), evidence_kind=GUARANTEED)
        elsewhere = []
    handed: dict[Path, set[str] | None] = {}
    over = 0
    for other, r, f in elsewhere:
        if other not in handed:
            try:
                handed[other] = handovers.handed_over(other)
            except handovers.HandoverError as exc:
                findings.warn(str(exc), evidence_kind=GUARANTEED)
                handed[other] = None  # cannot tell; "set aside" would claim it
        n = audit_findings.number_of(r, f)
        names = handed[other]
        if names is None:
            how = "handed over or set aside cannot be told — its handover record does not read"
        elif handovers.entry(r, n) in names:
            over += 1
            how = "handed over unresolved — no result released"
        else:
            how = "set aside for later work"
        findings.note(
            f"  deferred in {other.name} ({r.date}), {how}: {f.text} — {f.reason}"
        )
    if elsewhere:
        findings.note(
            f"  {len(elsewhere)} deferred finding(s) elsewhere in the repo "
            f"({len(elsewhere) - over} set aside for later, {over} handed over "
            "unresolved) — a reminder, not counted"
        )
    undecided = bool(audit_findings.open_findings(records))
    if not records and not elsewhere:
        findings.note("  none recorded")
    elif not undecided and not elsewhere:
        findings.note(f"  all decided ({len(records)} audit(s) recorded)")


def check_code(findings: Findings, area: Path, protocol: Path, repo: Path) -> None:
    """Station 4: code-check's automated checks (`code_check.code_findings`:
    intent ids, parser fixtures, prompt drift, stamp coverage), each with
    its grade as data and counted once — here, not again by code-check."""
    found = code_findings(area, protocol, repo)
    for finding in found:
        findings.take(finding)
    if not found:
        findings.note("  ok")


def scope_stamp_line(area: Path) -> str:
    """Station 5: the audit stamp of the area's input scope
    (`scope_sha.area_stamp`), or that there is nothing to stamp — told,
    never counted."""
    try:
        sha, _, _ = area_stamp(area)
    except promises.PromiseError as exc:  # a ValueError too, but not "nothing to stamp"
        return f"  cannot stamp: {exc}"
    except ValueError:
        return f"  no scripts matching {AREA_GLOBS} in {area} (skipped)"
    return f"  {sha}"


def check_working_tree(findings: Findings, repo: Path) -> None:
    """Station 6: uncommitted changes under REPO warn — the number would
    rest on code no commit holds."""
    if tree_dirty(repo):
        findings.warn(
            f"uncommitted changes in {repo} (commit or stash before the run)",
            evidence_kind=GUARANTEED,
        )
    else:
        findings.note("  clean")


def check_hooks(findings: Findings, git_repo: Path) -> None:
    """Station 7: the gates that do not depend on the agent remembering —
    every gap `install_hooks.check` names in GIT_REPO warns: a repo without
    the hooks (or with an older labkit's) runs on good intentions only."""
    gaps = install_hooks.check(git_repo)
    for g in gaps:
        findings.warn(g, evidence_kind=GUARANTEED)
    if gaps:
        findings.note("  fix with  .venv/bin/labkit-hooks install")
    else:
        findings.note(
            "  installed (this labkit's pre-commit, core.hooksPath, claude-hook)"
        )


def check_tests_owed(findings: Findings, tests: AreaTests, *, frozen: bool) -> None:
    """Station 8: what running the area's tests found (TESTS, from
    `area_tests`). No file: a warning, a blocker once FROZEN — frozen means
    every gap is owed (protocol-check's graduation), and the permanent
    resolution check is such a gap. A failing run blocks, with its last
    lines told; a missing pytest warns."""
    names = ", ".join(f.name for f in tests.files)
    if not tests.files:
        _owed(findings, frozen)(
            f"no {tests.pattern} — the resolution check has no "
            f"permanent form (LAB-016 Resolution check before freezing)"
            + (" and frozen = true owes it" if frozen else "")
        )
    elif tests.state == "ok":
        findings.note(f"  ok — {names}")
    elif tests.state == "no-pytest":
        findings.warn(
            "pytest is not installed in this interpreter — tests not run",
            evidence_kind=GUARANTEED,
        )
    else:
        for ln in tests.tail:
            findings.note(f"  {ln}")
        findings.block(
            f"{names} failed — an unfilled or broken resolution check must not pass the freeze"
        )


def main(argv: list[str]) -> int:
    """Command line of `preflight`: the mechanical gate before an area is frozen."""
    if not argv or argv[0] in ("-h", "--help"):
        lines = [
            (__doc__ or "").strip().splitlines()[0],
            "usage: preflight <AREA> [--protocol PROTOCOL-*.md]",
            EXIT_CONTRACT,
        ]
        return console.usage("preflight", "\n".join(lines), asked=bool(argv))

    try:
        area = area_path(argv[0])
    except AmbiguousArea as exc:
        console.refuse("preflight", str(exc))
        return 2
    protocol = None
    rest = argv[1:]
    while rest:
        if rest[0] == "--protocol" and len(rest) >= 2:
            protocol = Path(rest[1])
            rest = rest[2:]
            continue
        console.refuse("preflight", f"unexpected argument {rest[0]!r}")
        return 2

    if not area.is_dir():
        console.refuse("preflight", no_such_area(area))
        return 2

    return preflight_area(area, protocol)


def cli() -> None:
    """Console entry point of `preflight`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
