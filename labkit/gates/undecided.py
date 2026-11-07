"""undecided — what the stop and the commit hold of an area's audit
evidence, beside report-check: an audit BLOCKER nobody decided, a record
or the attempt journal lost or unreadable, evidence changed against HEAD
or ignored by git (`undecided_state`), and what a current handover lets
pass. The hooks (`agent_hooks.stop`, `agent_hooks.commit_gates`) hold on
it, and `next_step` names its step; it prints nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labkit.formats import attempts, evidence, findings, handovers
from labkit.formats.scope_sha import areas_touched


#: what the stop and the pre-commit hold, and what a handover let pass
@dataclass(frozen=True)
class Undecided:
    """What the stop and the commit hold (BLOCKERS) and what a current
    handover let pass (ACKNOWLEDGED: one line per area, the losses it
    acknowledges) — a pass that names no loss would read as "nothing
    wrong"."""

    blockers: list[str]
    acknowledged: list[str]


def undecided_blockers(
    repo: Path, paths: list[Path], *, staged: bool = False
) -> list[str]:
    """The blockers of `undecided_state`."""
    return undecided_state(repo, paths, staged=staged).blockers


def undecided_state(
    repo: Path, paths: list[Path], *, staged: bool = False
) -> Undecided:
    """Every audit BLOCKER still `open` in an area one of PATHS lies in — as
    `<area>: <file>: <text>`, each area once —, every audit record gone
    that the area's attempt journal or HEAD names (`attempts.area_gaps`),
    or the sentence of a record or journal nobody can read. BLOCKERs only, by intent (`findings.open_findings` has the
    table): the hook says what the commit would be refused for. The area is the nearest directory above the path with a
    PROTOCOL-*.md, inside REPO, and every area whose promises declare a
    changed path in their scope or whose code imports a changed shared
    helper (`scope_sha.areas_touched`, the stop's answer too), and every
    area deleted whole — its protocol with it, so no area to the tree or
    the index — whose journal copy on the branch still names its evidence
    (`attempts.copied_areas`) and whose directory holds a changed path —
    an area never committed and gone whole leaves no such path, and only
    its copy knows it. A
    path outside every area contributes nothing, and so does an area with
    no audit record and no journal in the state checked or at HEAD — an
    audits/ gone from the tree but committed is a gap: this holds the areas
    the session worked in, not the whole repo
    (a repo's old areas must not block every stop).
    STAGED (the pre-commit): the audit records with their decisions and
    the attempt journal as the index holds them (`attempts.area_integrity`)
    — what the commit carries, not the tree.
    A current handover acknowledges integrity gaps and the open BLOCKERs it
    records for this stop/commit alone (`handovers.acknowledgement`): it
    binds the audit files by blob, so a finding changed or added after it
    is held again. It decides nothing — the findings stay `open`. At commit, its audit evidence must also match the working
    tree, so new unstaged evidence cannot borrow an earlier
    acknowledgement. Where the gaps stand and a handover record of the area
    does not count, a line per record says why (`handovers.mismatch`).
    Evidence changed against HEAD in that state, or ignored by git
    (`evidence.changes`, `evidence.ignored`), holds as well, and no
    handover acknowledges it: a restore from git undoes it."""
    out: list[str] = []
    acknowledged: list[str] = []
    areas = areas_touched(paths, repo)
    changed = {p.resolve() for p in paths}
    # an area removed with its protocol is found by no protocol walk; its
    # journal copy is the one thing left that names what it held
    areas += [
        area
        for area in attempts.copied_areas(repo)
        if area not in areas and any(area in p.parents for p in changed)
    ]
    for area in areas:
        shown = area.relative_to(repo.resolve()).as_posix()
        # Only a current handover can acknowledge integrity gaps.
        # Open readable BLOCKERs remain owed independently below.
        handed_over = handovers.acknowledgement(area, staged=staged)
        state = attempts.area_integrity(area, staged=staged)
        if handed_over.valid and state.problems:
            acknowledged.append(
                f"{shown}: a handover acknowledges this loss — not restored, and "
                f"no audit or adoption passes on it: " + "; ".join(state.problems)
            )
        if not handed_over.valid and state.problems:
            out += [f"{shown}: {problem}" for problem in state.problems]
            # a handover written for this area that no longer counts says why
            out += [
                f"{shown}: the handover {name} no longer acknowledges this: {why}"
                for name, why in handed_over.refused.items()
            ]
        open_lines = [
            f"{shown}: {u.line}" for u in findings.open_blockers(state.records)
        ]
        if handed_over.valid and open_lines:
            acknowledged.append(
                f"{shown}: a handover records these open BLOCKERs — the protocol "
                f"ends without a result: " + "; ".join(open_lines)
            )
        else:
            out += open_lines
        # undone from git, so never a handover's to acknowledge
        changed = evidence.changes(area, staged=staged) + evidence.ignored(area)
        out += [f"{shown}: {line}" for line in changed]
    return Undecided(out, acknowledged)
