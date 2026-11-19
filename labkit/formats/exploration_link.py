"""exploration_link — a confirmation's link to its exploration
(`[explored_in]`, `protocol_block.explored_in`): the exploratory protocol a
confirmatory one builds on and the run that protocol had adopted when the
link was written (docs/notes/2026-11-14-exploratory-workflow-plan.md, "Link
from a confirmation to its exploration").

Is the link valid (`linked_exploration`)? The linking protocol is
confirmatory; the id names exactly one other protocol of the repo, in any
area; that protocol's first measurements registered `type =
"exploratory"`; the named run is a completed measurement of it, no repeat,
and the run it has adopted (`[result] run`). Asked where the link is
written (`protocol-fill --explored-in`) and at the start of the first
confirming measurement (`start_check.require_exploration_link`), never
again: from then on the link is a registration part
(`protocol_history.scope_differences`), and a change of the state it
names makes the confirming audit stale instead (`exploration_state`,
`scope_sha.exploration_basis`).
The link names the basis of a confirmation. It transfers no measurement
value and widens no input-origin lookup; a link into another repository is
not read. Read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from labkit.formats import protocol_block, protocol_history, runs
from labkit.formats.area_state import TREE, FileState, state_of
from labkit.formats.gate import TECHNICAL_RULE, RuleAssignment, cited_rule
from labkit.formats.protocol_block import ExploredIn
from labkit.formats.repo import git_root
from labkit.formats.runs import RunDir

LAB_003 = cited_rule("LAB-003 No run without an intent paragraph")
#: the two types, by name (`protocol_block.TYPES` is their home)
EXPLORATORY, CONFIRMATORY = protocol_block.TYPES


class LinkedExploration(NamedTuple):
    """The exploration `[explored_in]` names, bound: the exploratory
    protocol's path, its text as the file state holds it, and its adopted
    run — the one the link names."""

    protocol: Path
    text: str
    run: RunDir


@dataclass(frozen=True)
class NotLinked:
    """Why `[explored_in]` names no adopted exploratory run.

    Attributes:
        why: The sentence, as a refusal continues it.
        rule: The rule assignment of this cause: an id that names no
            protocol, several or the linking protocol itself, and a
            protocol, run record or table that does not read, the technical
            contract; every condition of the link's own contract (the
            types — also a first measurement's type that cannot be read —,
            the run, the adoption) LAB_003, whose paragraph on the link
            states them.
    """

    why: str
    rule: RuleAssignment


def adopted_link(exploration_text: str) -> ExploredIn | NotLinked:
    """The link to the exploratory protocol EXPLORATION_TEXT as
    `protocol-fill --explored-in` writes it: that protocol's id and the run
    it has adopted (`[result] run`), read once — no later check selects a
    newer adoption. NotLinked for a head that does not read or carries no
    stamped id, and for a protocol that has adopted no run. Whether the
    pair is valid is `linked_exploration`'s. Pure."""
    try:
        pid = protocol_block.head(exploration_text).id
        run = protocol_block.declared_run(exploration_text)
    except protocol_block.BlockError as exc:
        return NotLinked(
            f"the exploratory protocol does not read: {exc}", TECHNICAL_RULE
        )
    if pid is None:
        return NotLinked(
            "the exploratory protocol carries no stamped id", TECHNICAL_RULE
        )
    if run is None:
        return NotLinked(_NOT_ADOPTED, LAB_003)
    return ExploredIn(pid, run)


#: why a protocol without `[result] run` cannot be linked; a withdrawn
#: adoption leaves the same head
_NOT_ADOPTED = (
    "the exploratory protocol has adopted no run ([result] run; a withdrawn "
    "adoption is none) — a confirmation examines the exploration's own "
    "selection, so the link waits for the adoption"
)


def linked_exploration(
    text: str, ids: dict[str, list[Path]], *, file_state: FileState = TREE
) -> LinkedExploration | NotLinked | None:
    """The one binding of the `[explored_in]` of the protocol TEXT against
    IDS (`protocol_block.repo_protocol_ids` of the repo): the exploration
    bound, why it is not (`NotLinked`, the first condition that fails, in
    the module's order), or None without the table. The exploration's area
    is read as FILE_STATE holds it (`area_state.state_of`), the texts its
    first measurements saw from git (`protocol_history.first_texts`).

    A first measurement known only by a lost record is not seen here: the
    exploration's own release holds it (`registration_hold.lost_record_hold`),
    and a link is written only after that release.

    Raises BlockError on a head or an `[explored_in]` of TEXT that does not
    read, RuntimeError when git fails."""
    link = protocol_block.explored_in(text)
    if link is None:
        return None
    own = protocol_block.head(text)
    if own.type != CONFIRMATORY:
        return NotLinked(
            f"this protocol's type is {own.type or 'not stated'} — [explored_in] is a "
            f"confirmation's link to its exploration; within one exploration a "
            f"run names its basis in [builds_on]",
            LAB_003,
        )
    if link.protocol == own.id:
        return NotLinked(
            "[explored_in] protocol is this protocol's own id — a confirmation "
            "is a protocol of its own",
            TECHNICAL_RULE,
        )
    hits = ids.get(link.protocol, [])
    if len(hits) != 1:
        return NotLinked(
            f"[explored_in] protocol = {link.protocol} names "
            + (
                "no protocol of this repo"
                if not hits
                else f"{len(hits)} protocols ({', '.join(str(h) for h in hits)})"
            ),
            TECHNICAL_RULE,
        )
    protocol = hits[0]
    area = protocol.parent
    state = state_of(area, file_state=file_state)
    try:
        theirs = state.text_of(protocol)
    except ValueError as exc:
        return NotLinked(str(exc), TECHNICAL_RULE)
    measured = state.measured_of(link.protocol)
    firsts = [rd for group in measured.first_groups for rd in group]
    if not firsts:
        return NotLinked(f"{protocol.name} has measured nothing yet", LAB_003)
    seen, unread = protocol_history.first_texts(protocol, firsts, git_root(area))
    if unread:
        return NotLinked(
            f"the type {protocol.name} registered at its first measurement cannot "
            f"be read — {unread[0]}; no exploration is assumed",
            LAB_003,
        )
    types = sorted({protocol_history.type_of(then) or "not stated" for _, then in seen})
    if types != [EXPLORATORY]:
        return NotLinked(
            f"{protocol.name} registered type {' and '.join(types)} at its first "
            f"measurement — [explored_in] names an exploratory protocol",
            LAB_003,
        )
    return _adopted_run(link, protocol, theirs, measured.runs)


def _adopted_run(
    link: ExploredIn, protocol: Path, theirs: str, bound: tuple[RunDir, ...]
) -> LinkedExploration | NotLinked:
    """The last conditions of `linked_exploration`: LINK's run is among
    BOUND (the runs of the exploratory PROTOCOL, its text THEIRS) a
    completed measurement the file state holds, no repeat, and the run
    THEIRS adopts."""
    named = f"[explored_in] run = {link.run}"
    rd = next((r for r in bound if r.dir.name == link.run), None)
    if rd is None:
        return NotLinked(f"{named} is no run of {protocol.name}", LAB_003)
    if rd.config is None:
        return NotLinked(f"{named} does not read: {rd.error}", TECHNICAL_RULE)
    if rd.from_commit is not None:
        return NotLinked(
            f"{named} is deleted (commit {rd.from_commit[:12]} holds it)", LAB_003
        )
    state = runs.completion_state(rd.dir)
    if (
        rd.config.run_kind != runs.MEASUREMENT
        or rd.config.repeat_of is not None
        or state != runs.COMPLETED
    ):
        what = (
            f"a repeat of {rd.config.repeat_of}"
            if rd.config.repeat_of is not None
            else f"a {rd.config.run_kind} run, {state}"
        )
        return NotLinked(
            f"{named} is {what} — the link names a completed measurement, no repeat",
            LAB_003,
        )
    try:
        adopted = protocol_block.declared_run(theirs)
    except protocol_block.BlockError as exc:
        return NotLinked(
            f"the [result] of {protocol.name} does not read: {exc}", TECHNICAL_RULE
        )
    if adopted is None:
        return NotLinked(_NOT_ADOPTED, LAB_003)
    if adopted != link.run:
        return NotLinked(
            f"{protocol.name} has adopted {adopted}, not {link.run} — a "
            f"confirmation examines the exploration's own selection",
            LAB_003,
        )
    return LinkedExploration(protocol, theirs, rd)
