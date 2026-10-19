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
never writes. The stations read one context (`Checked`, built once by
`checked`): the protocol text as the named file state holds it, its head,
the run ids the answer cites, and the answering run chosen once
(`audit.audited_run`, through `runs.bound_answering_run`, the one choice
every gate holds a protocol to) — no station reads the file or chooses the
run for itself, and the output names the state that was held.

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
import subprocess
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.gate import Findings
from labkit.formats import console, findings, promises, protocol_block
from labkit.gates.audit import AuditError, audited_run
from labkit.gates.finalize import cited_runs, finalize_area
from labkit.gates.preflight import area_test_python
from labkit.formats.protocol_check import check_fields
from labkit.formats.repo import (
    area_protocols,
    areas_of,
    choose_protocol,
    git_root,
    git_run,
    layout_root,
    status_entries,
)
from labkit.formats.runs import read_run_config, unreportable
from labkit.formats.scope_sha import area_stamp
from labkit.formats.standard_contract import (
    ANALYSIS_AUDIT,
    CHECK_SCRIPT,
    Lane,
    check_command,
    lane,
)

#: which file state the declaration (the answer line) is read from — named
#: in the output, so a reader knows what was held. The stations read the
#: working tree in every case; the caller makes the tree that state: the
#: pre-commit holds the area's tree equal to the index (`tree_differs`), the
#: adoption writes the proposal into the tree and puts it back on refusal
#: (`protocol_fill.adopt`)
TREE = "working tree"
INDEX = "index"
PROPOSED = "proposed protocol"


@dataclass(frozen=True)
class Checked:
    """The context of one check, built once (`checked`) and read by every
    station: one protocol text, one head, one answering run, one named file
    state — so the declaration, the audit record and the check are held to
    the same run and the same text, and no station chooses for itself.

    Attributes:
        area: The area, resolved.
        repo: Where the area's layout starts (`repo.layout_root`).
        protocol: The protocol file.
        text: The protocol as STATE holds it — the declaration is read here.
        head: Its TOML head.
        state: TREE, INDEX or PROPOSED.
        cited: The run ids the answer cites (`finalize.cited_runs`) — the
            declaration that a result is reported.
        run: The answering run (`audit.audited_run`, through
            `runs.bound_answering_run`: the one choice every gate holds the
            protocol to), or None.
        why: Why there is no answering run, when RUN is None.
    """

    area: Path
    repo: Path
    protocol: Path
    text: str
    head: protocol_block.Head
    state: str
    cited: tuple[str, ...]
    run: Path | None
    why: str


def checked(
    area: Path, protocol: Path, *, state: str = TREE, text: str | None = None
) -> Checked:
    """The context of one check: TEXT is the protocol as STATE holds it
    (the working tree when None). Raises `protocol_block.BlockError` on an
    unreadable head, `AuditError` out of the run choice."""
    if text is None:
        text = protocol.read_text(encoding="utf-8")
    head = protocol_block.head(text)
    run, why = audited_run(area, protocol, text)
    return Checked(
        area=area.resolve(),
        repo=layout_root(area),
        protocol=protocol,
        text=text,
        head=head,
        state=state,
        cited=tuple(cited_runs(text)),
        run=run,
        why=why,
    )


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


def freeze_gaps(ctx: Checked) -> list[str]:
    """Station 1: why the freeze does not hold — the flag unset, or a must
    gap protocol-check names (the stamp's `<…>` promise sentences among them)."""
    gaps = (
        []
        if ctx.head.frozen
        else ["not `frozen = true` — a reported number owes the freeze"]
    )
    report = check_fields(ctx.text)
    gaps += report.missing_must
    # a must field still holding its `<…>` placeholder passed here while
    # protocol-check and preflight refused it (audit 2026-10-15)
    gaps += [f"line {n}: {label} still a placeholder" for n, label in report.must_holes]
    return [f"{ctx.protocol.name}: {g}" for g in gaps]


def analysis_audit_gap(ctx: Checked) -> str | None:
    """Station 3: why no decided analysis record covers the code, the promise
    block and the answering run as they are now, or None. Without an
    answering run there is nothing the audit could be held to."""
    if ctx.run is None:
        return f"no answering run to hold it to — {ctx.why}"
    try:
        return findings.audit_coverage(
            ctx.area,
            area_stamp(ctx.area)[0],
            ANALYSIS_AUDIT,
            promises.block_stamp(ctx.text),
            ctx.run.name,
        )
    except (FileNotFoundError, ValueError) as exc:
        # ValueError: nothing to stamp, a findings file or the promise block
        # unreadable (FindingsError, PromiseError)
        return f"the analysis audit cannot be held to the area: {exc}"


def unreportable_gaps(ctx: Checked, freeze_owed: bool) -> list[str]:
    """Station 2, the run: why the answering run's number cannot be reported
    (`runs.unreportable`), each a blocker. Without an answering run there is
    nothing to hold — finalize says so. FREEZE_OWED names the freeze in the
    sentence (minutes/hours); at seconds a full run is owed, no freeze."""
    if ctx.run is None:
        return []
    cfg = read_run_config(ctx.run)
    if cfg is None:
        return [f"{ctx.run.name}: no config.json — not a run"]
    owed = "a full run (long=True)" + (" on a frozen protocol" if freeze_owed else "")
    return [
        f"the answering run {ctx.run.name}: {mark} — its number cannot be "
        f"reported; a reported number owes {owed}"
        for mark in unreportable(cfg)
    ]


def finalize_gaps(area: Path, protocol: Path) -> list[str]:
    """Station 2, the gate before: finalize's blockers, each named here with
    its prefix — a hook that says "run it to see them" asks for a round
    trip the agent does not take. finalize runs on a silent collector
    (`Findings(tell=None)`): its findings arrive as data and nothing of its
    output reaches this gate's. Exit 2 (no protocol to hold) is one blocker."""
    collected = Findings(tell=None)  # the data, not the console
    finalized = finalize_area(area, protocol, collected)
    if finalized == 0:
        return []
    if collected.blocked:
        return [f"finalize: {b}" for b in collected.blocked]
    return [f"finalize {area} exits {finalized} — run it to see why"]


def later_gaps(ctx: Checked, ln: Lane) -> list[str]:
    """Stations 2–4: finalize clean and its run a full run, the analysis
    audit where the lane LN owes it (`Lane.audits`; every lane of the
    standard does), the check. The freeze names itself in station 2's
    sentence where the lane owes it."""
    out = finalize_gaps(ctx.area, ctx.protocol)
    out += unreportable_gaps(ctx, ln.freeze)
    if ANALYSIS_AUDIT in ln.audits:
        gap = analysis_audit_gap(ctx)
        if gap:
            out.append(
                f"analysis audit: {gap} (LAB-050 Analysis audit before reporting)"
            )
    failed = check_analysis_script(ctx.area, ctx.repo)
    if failed:
        out.append(f"{failed} (LAB-041 Generate numbers, don't retype them)")
    return out


def report_check(
    area: Path,
    protocol: Path | None = None,
    *,
    state: str = TREE,
    text: str | None = None,
) -> int:
    """Run the stations on AREA; 0 clean, 1 a blocker, 2 no protocol to hold.
    STATE and TEXT name the file state the declaration is read from
    (`checked`): the tree by default, the index for the pre-commit, the
    written proposal for the adoption."""
    chosen = choose_protocol(area, protocol, "report-check")
    if chosen is None:
        return 2
    try:
        ctx = checked(area, chosen, state=state, text=text)
    except (protocol_block.BlockError, AuditError) as exc:
        print(f"report-check: {chosen.name}: {exc}")
        return 2
    print(
        f"  {chosen.name}: read from the {ctx.state}; the answer cites "
        f"{', '.join(ctx.cited) or 'no run'}; the answering run is "
        f"{ctx.run.name if ctx.run is not None else 'none — ' + ctx.why}"
    )
    # what the release owes at this tier is the contract's answer: the freeze
    # (station 1) and the audits follow the lane; finalize, the full run and
    # the check are owed at every tier
    ln = lane(ctx.head.cost)
    findings = Findings()
    if ln.freeze:
        gaps = freeze_gaps(ctx)
    else:
        gaps = []
        print(
            f'  {chosen.name}: cost = "{ctx.head.cost}" — no freeze and no preflight audit '
            f"owed (LAB-017 The number of audits follows the cost tier); the full "
            f"run, the analysis audit and the check are"
        )
    for b in gaps + later_gaps(ctx, ln):
        findings.block(b)
    if not findings.blocked:
        held = ("frozen, " if ln.freeze else "") + "finalized, audited, checked"
        print(f"  {chosen.name}: {held}")
    return findings.report("report-check", "reporting")


def reported_protocols(paths: list[Path], repo: Path) -> list[Path]:
    """Every protocol of every area one of PATHS lies in, each once, in
    path order: a changed script, run or audit record reopens the area's
    reported numbers as a changed protocol does. A path under no area
    contributes nothing (`repo.areas_of`, the commit's undecided gate reads
    the same answer)."""
    return [p for area in sorted(areas_of(paths, repo)) for p in area_protocols(area)]


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
        worst = max(
            worst,
            report_check(area, protocol, state=INDEX if staged else TREE, text=text),
        )
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
