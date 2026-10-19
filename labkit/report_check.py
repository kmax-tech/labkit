"""report-check — the gate after the last step, before a number leaves the area.

    report-check <AREA> [--protocol PROTOCOL-*.md]
    report-check --if-reported [--staged] PATH ...  every protocol of an area
                                                    a path touches whose answer
                                                    cites a run (the stop hook;
                                                    with --staged the pre-commit:
                                                    the answer as the index
                                                    holds it, and the area's
                                                    tree must equal the index)

Exit codes: 0 clean, 1 a blocker, 2 usage error.

`finalize` holds the run before the number is written back; what follows it
— the analysis audit, the result written into its note, the note held to the
run by `02_analyze.py --check` — had no gate. In the cloud judge probe at
`minutes` (2026-10-14, draw 3) the agent skipped the check and the result
note, and finalize was green. A gate there cannot be finalize itself: finalize
comes before the analysis audit, so it cannot ask for what follows the audit.
report-check comes last and holds the whole chain, at every cost tier:

  0. protocol      the named PROTOCOL-*.md or the area's only one
  1. frozen        at `minutes`/`hours`: `frozen = true`, and the freeze
                   holds: no must gap `protocol-check` names
                   (`check_fields`) — the [[promise]] tables written, not
                   the stamp's `<…>` sentences. At `cost = "seconds"` no
                   freeze and no preflight audit are owed
                   (LAB-017 The number of audits follows the cost tier), so
                   this station is skipped and says so; until 0.99.0 the whole
                   command exited 0 there, and a probe's number passed as
                   a reported one (TODO 1, 2026-10-19)
  2. finalize      `finalize_area` clean — its blockers are named here —
                   so the answering run is bound to this protocol and the
                   answer cites it; and that run is a full run: `long=True`,
                   not acknowledged unfrozen (`runs.unreportable`) — a
                   reported number owes a full run (frozen at
                   minutes/hours); a probe's or an acknowledged run's number
                   cannot be reported (second haiku round on 0.98.0: t3 and
                   t18 reported a probe, t5 an acknowledged run; plan
                   2026-10-17, A3)
  3. analysis audit  a record `audits/*-analysis.toml` whose `scope_sha` is
                   the area's stamp now, whose `block_sha` is the promise
                   block now and whose `run_id` is the answering run, every
                   finding decided (`findings.audit_coverage`) — code or
                   promises changed after the analysis audit, or a later
                   run, owe a new one (LAB-050 Analysis audit before
                   reporting)
  4. the check     `scripts/02_analyze.py --check` exits 0 under the repo's
                   interpreter: the rows recompute to the run's metrics and
                   the note it names carries every number and the run_id
                   (`recheck.holds`; LAB-041 Generate numbers, don't retype
                   them). One command for every skeleton: the count stamps
                   its own `02_analyze.py` too (until 0.99.0 it carried the
                   check inside `01_measure.py`, and this station asked for
                   a file the skeleton never wrote, audit 2026-10-19)

Every station runs; the blockers are summed at the end. It reads and runs,
never writes.

`--if-reported` is the gate the agent cannot choose: `claude-hook stop`
runs it on every changed path, the stamped pre-commit on every staged one,
and it holds every protocol of every area one of those paths lies in
(`reported_protocols`) whose "Answer to the question" cites a run
(`finalize.cited_runs`) — the one line that declares a result reported,
written by `protocol-fill --from-run`. The area, not the protocol alone:
a script edited after the answer was written back changes what the
analysis audit saw and what `--check` recomputes, and with the protocol
untouched both hooks passed it (audit 2026-10-19). A protocol whose
answer is still open owes nothing here: an exploration ends with no
reported result, probes or not (third haiku round on 0.99.0: t3 and t5
reported a probe's number and never called report-check; TODO 2,
2026-10-19). finalize stays the check before the analysis audit; this is
the check after it.

`--staged` is the pre-commit's form. The commit holds the index, the
stations read the working tree: so the declaration is read from the index
(`index_text` — an answer only the tree carries is not in the commit), and
an area whose tree differs from the index (`tree_differs`: a file modified
and not staged, or untracked) is a blocker before any station runs, since
the check would judge a state the commit does not hold. Until 0.99.0 the
hook read the tree: a reported answer staged, then reopened in the tree,
passed the commit (audit 2026-10-19).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import subprocess
from pathlib import Path

from labkit.gate import Findings
from labkit import console, findings, promises, protocol_block
from labkit.audit import AuditError, audited_run
from labkit.finalize import cited_runs, finalize_area
from labkit.preflight import area_test_python
from labkit.protocol_check import check_fields
from labkit.repo import (
    area_protocols,
    choose_protocol,
    find_area,
    git_root,
    git_run,
    layout_root,
    status_entries,
)
from labkit.runs import read_run_config, unreportable
from labkit.scope_sha import area_stamp
from labkit.standard_contract import CHECK_SCRIPT, check_command, release

#: how long `--check` may take inside the gate (audit 2026-10-15: no limit)
CHECK_TIMEOUT_S = 300.0


def check_analysis_script(area: Path, repo: Path) -> str | None:
    """Why the area's check (`standard_contract.check_command`: the analysis
    script's `--check`, stamped by every skeleton) does not pass, or None:
    no script, or a nonzero exit with the last lines it printed."""
    script = CHECK_SCRIPT
    if not (area / script).is_file():
        return (
            f"no {script} — the check that holds the note to the run is owed; "
            f"every skeleton stamps it (an area stamped at seconds before 0.100.0 "
            f"carried the check inside 01_measure.py: stamp "
            f"labkit/templates/analyze-quick-script.py.template beside it)"
        )
    try:
        r = subprocess.run(
            [area_test_python(repo), *check_command(area)],
            cwd=repo,
            capture_output=True,
            text=True,
            errors="replace",  # the tail is quoted, not parsed: a byte no
            # codec reads must not raise out of the gate (audit 2026-10-19)
            timeout=CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"{script} --check did not finish in {CHECK_TIMEOUT_S:g} s"
    if r.returncode == 0:
        return None
    tail = (r.stderr.strip() or r.stdout.strip() or "no output").splitlines()[-3:]
    return f"{script} --check exits {r.returncode}: " + " | ".join(tail)


def freeze_gaps(protocol: Path, frozen: bool) -> list[str]:
    """Station 1: why the freeze does not hold — the flag unset, or a must
    gap protocol-check names (the stamp's `<…>` promise sentences among them)."""
    gaps = [] if frozen else ["not `frozen = true` — a reported number owes the freeze"]
    report = check_fields(protocol.read_text(encoding="utf-8"))
    gaps += report.missing_must
    # a must field still holding its `<…>` placeholder passed here while
    # protocol-check and preflight refused it (audit 2026-10-15)
    gaps += [f"line {n}: {label} still a placeholder" for n, label in report.must_holes]
    return [f"{protocol.name}: {g}" for g in gaps]


def analysis_audit_gap(area: Path, protocol: Path) -> str | None:
    """Station 3: why no decided analysis record covers the code, the promise
    block and the answering run as they are now, or None. Without an
    answering run there is nothing the audit could be held to."""
    try:
        run_dir, why = audited_run(area, protocol)
        if run_dir is None:
            return f"no answering run to hold it to — {why}"
        return findings.audit_coverage(
            area,
            area_stamp(area)[0],
            "analysis",
            promises.block_stamp(protocol.read_text(encoding="utf-8")),
            run_dir.name,
        )
    except (FileNotFoundError, ValueError, AuditError) as exc:
        # ValueError: nothing to stamp, a findings file or the promise block
        # unreadable (FindingsError, PromiseError); AuditError: the head
        return f"the analysis audit cannot be held to the area: {exc}"


def unreportable_gaps(area: Path, protocol: Path, freeze_owed: bool) -> list[str]:
    """Station 2, the run: why the answering run's number cannot be reported
    (`runs.unreportable`), each a blocker. Without an answering run there is
    nothing to hold — finalize says so. FREEZE_OWED names the freeze in the
    sentence (minutes/hours); at seconds a full run is owed, no freeze."""
    try:
        run_dir, _ = audited_run(area, protocol)
    except AuditError as exc:
        return [f"the answering run cannot be chosen: {exc}"]
    if run_dir is None:
        return []
    cfg = read_run_config(run_dir)
    if cfg is None:
        return [f"{run_dir.name}: no config.json — not a run"]
    owed = "a full run (long=True)" + (" on a frozen protocol" if freeze_owed else "")
    return [
        f"the answering run {run_dir.name}: {mark} — its number cannot be "
        f"reported; a reported number owes {owed}"
        for mark in unreportable(cfg)
    ]


def finalize_gaps(area: Path, protocol: Path) -> list[str]:
    """Station 2, the gate before: finalize's blockers, each named here with
    its prefix — inside the stop hook "run it to see them" was a round trip
    the agent did not take. Exit 2 (no protocol to hold) is one blocker."""
    collected = Findings()
    with contextlib.redirect_stdout(io.StringIO()):
        finalized = finalize_area(area, protocol, collected)
    if finalized == 0:
        return []
    if collected.blocked:
        return [f"finalize: {b}" for b in collected.blocked]
    return [f"finalize {area} exits {finalized} — run it to see why"]


def later_gaps(area: Path, protocol: Path, freeze_owed: bool = True) -> list[str]:
    """Stations 2–4: finalize clean and its run a full run, an analysis audit
    of the area now, the check."""
    out = finalize_gaps(area, protocol)
    out += unreportable_gaps(area, protocol, freeze_owed)
    gap = analysis_audit_gap(area, protocol)
    if gap:
        out.append(f"analysis audit: {gap} (LAB-050 Analysis audit before reporting)")
    failed = check_analysis_script(area, layout_root(area))
    if failed:
        out.append(f"{failed} (LAB-041 Generate numbers, don't retype them)")
    return out


def report_check(area: Path, protocol: Path | None = None) -> int:
    """Run the stations on AREA; 0 clean, 1 a blocker, 2 no protocol to hold."""
    chosen = choose_protocol(area, protocol, "report-check")
    if chosen is None:
        return 2
    try:
        head = protocol_block.head(chosen.read_text(encoding="utf-8"))
    except protocol_block.BlockError as exc:
        print(f"report-check: {chosen.name}: {exc}")
        return 2
    # what the release owes at this tier is the contract's answer: the freeze
    # follows the lane, the rest is owed everywhere (`standard_contract.release`)
    freeze_owed = release(head.cost).freeze
    findings = Findings()
    if freeze_owed:
        gaps = freeze_gaps(chosen, head.frozen)
    else:
        gaps = []
        print(
            f'  {chosen.name}: cost = "{head.cost}" — no freeze and no preflight audit '
            f"owed (LAB-017 The number of audits follows the cost tier); the full "
            f"run, the analysis audit and the check are"
        )
    for b in gaps + later_gaps(area, chosen, freeze_owed):
        findings.block(b)
    if not findings.blocked:
        held = ("frozen, " if freeze_owed else "") + "finalized, audited, checked"
        print(f"  {chosen.name}: {held}")
    return findings.report("report-check", "reporting")


def reported_protocols(paths: list[Path], repo: Path) -> list[Path]:
    """Every protocol of every area one of PATHS lies in, each once, in
    path order: a changed script, run or audit record reopens the area's
    reported numbers as a changed protocol does. A path under no area
    (`repo.find_area`, stopping at REPO) contributes nothing."""
    areas: list[Path] = []
    for path in paths:
        area = find_area(path, stop=repo)
        if area is not None and area not in areas:
            areas.append(area)
    return [p for area in sorted(areas) for p in area_protocols(area)]


def index_text(repo: Path, path: Path) -> str | None:
    """PATH's content as git's index holds it — what a commit now would
    carry — or None when the index does not hold it (untracked, or staged
    as deleted). PATH must lie under REPO."""
    rel = path.resolve().relative_to(repo.resolve()).as_posix()
    r = git_run(["show", f":{rel}"], repo)
    return r.stdout if r.returncode == 0 else None


def tree_differs(repo: Path, area: Path) -> list[str]:
    """The paths under AREA whose working tree differs from the index — a
    tracked file modified or deleted and not staged, an untracked file —
    relative to REPO. Empty when the tree under AREA is what the commit
    would hold."""
    rel = area.resolve().relative_to(repo.resolve()).as_posix()
    return [path for xy, path in status_entries(repo, (rel,)) if xy[1] != " "]


def if_reported(paths: list[Path], repo: Path, *, staged: bool) -> int:
    """`report-check` for every protocol of an area one of PATHS touches
    whose "Answer to the question" cites a run — the gate at the stop and
    the commit: a result declared reported is held to the whole chain, a
    protocol whose answer is still open is skipped (an exploration may end
    with no reported result). STAGED (the pre-commit): the answer is read
    from the index, and an area whose tree differs from the index is a
    blocker — the stations read the tree, the commit holds the index.
    Returns the worst exit code."""
    worst = 0
    for protocol in reported_protocols(paths, repo):
        if staged:
            text = index_text(repo, protocol)
            if text is None:
                continue  # not in the commit: nothing declared there
        else:
            try:
                text = protocol.read_text(encoding="utf-8")
            except OSError as exc:
                print(f"report-check: {protocol}: {exc}")
                worst = max(worst, 2)
                continue
        cited = cited_runs(text)
        if not cited:
            continue
        print(f"═══ report-check {protocol} (its answer cites {', '.join(cited)}) ═══")
        area = protocol.parent.resolve()
        if staged:
            differs = tree_differs(repo, area)
            if differs:
                print(
                    f"  {area.relative_to(repo.resolve()).as_posix()}: the working "
                    f"tree differs from the index ({', '.join(differs)}) — the "
                    f"stations read the tree, the commit holds the index; stage "
                    f"these too, or stash them, so the commit holds what the "
                    f"check sees"
                )
                worst = max(worst, 1)
                continue
        worst = max(worst, report_check(area, protocol))
    return worst


def main(argv: list[str]) -> int:
    """Command line of `report-check`."""
    if argv and argv[0] == "--if-reported":
        cwd = Path.cwd()
        rest = argv[1:]
        staged = bool(rest) and rest[0] == "--staged"
        paths = [Path(a) for a in (rest[1:] if staged else rest)]
        return if_reported(paths, git_root(cwd) or cwd, staged=staged)
    ap = argparse.ArgumentParser(
        prog="report-check", description=(__doc__ or "").split("\n\n")[0]
    )
    ap.add_argument("area", type=Path)
    ap.add_argument("--protocol", type=Path, default=None)
    a = ap.parse_args(argv)
    if not a.area.is_dir():
        print(f"report-check: {a.area} is not a directory")
        return 2
    return report_check(a.area.resolve(), a.protocol)


def cli() -> None:
    """Console entry point `report-check`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
