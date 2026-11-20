"""What `report_check` finds for a confirmation that names its exploration
(`[explored_in]`): two findings of two kinds, told at two stations of its
chain (`report_check.chain_gaps`).

- At the registration station (2), the link itself (`link_gaps`, which
  reads a context; `unresolved_link_hold`, the rule on data): an id that
  names no protocol of the repo, or several, is a BLOCKER — guaranteed, a
  check not executable. The link names the basis of the confirmation;
  while it resolves to no one protocol, nothing of that basis was read,
  and the result that names it is not released. Where no file carries
  the id, the way out names the restore the history gives (`last_held`,
  which asks it; `LastHeld`, the answer as data).
- At the analysis station (5), under a covering audit: the runs of the
  exploration's area that recorded an input digest a run of the
  confirmation recorded too and that the audit was not shown, because
  they started after it began (`use_after_audit_findings`, which reads a
  context; `later_use_findings`, the search): warnings only. A
  shared digest is static evidence: an equal digest is byte-identical
  content, never a proof that the confirmation depends on the run — and
  no shared digest is no proof that it does not.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from labkit.formats import attempts, findings, protocol_block
from labkit.formats.area_state import (
    CLOCKS_ASSUMED,
    AreaState,
    HistoryUnread,
    state_of,
)
from labkit.formats.commands import (
    audit_command,
    checkout_command,
    explored_in_command,
    gate_command,
    register_anew,
    stamp_command,
)
from labkit.formats.exploration_state import (
    SharedInput,
    basis_closure,
    not_shown_since,
    shared_inputs,
)
from labkit.formats.gate import (
    NOT_EXECUTABLE,
    STATIC_EVIDENCE,
    TECHNICAL_RULE,
    WARNING,
    GateFinding,
    blocker,
    cited_rule,
)
from labkit.formats.protocol_block import ExploredIn
from labkit.formats.protocol_then import last_held_with_id
from labkit.formats.repo import git_root, shown
from labkit.checks.audit_binding import covering_analysis
from labkit.gates import ways_out
from labkit.gates.report_context import Checked


LAB_050 = cited_rule("LAB-050 Analysis audit before reporting")


def audit_began(
    records: Sequence[findings.Record], journal: Sequence[attempts.Attempt]
) -> datetime | None:
    """When the latest of RECORDS' audits began (local time): the start of
    the attempt of JOURNAL whose end names the record's file, the latest
    over RECORDS. None when JOURNAL names no attempt for any of them, or
    names one whose start does not read as a time. An audit's attempt
    states the time its command began reading the area, before the prompt
    was built (`audit.main`), so a run started at or after it is taken as
    not shown — also one the prompt happened to hold. The bound is a time,
    not the audit's documents: a run takes its id's time before runlog
    writes its record, and an audit that begins reading between the two
    was not shown the run although the run's time lies before. Pure."""
    by_file = {a.file: a.started for a in journal if a.file}
    began: list[datetime] = []
    for r in records:
        started = by_file.get(r.path.name)
        if started is None:
            continue
        try:
            began.append(datetime.fromisoformat(started))
        except ValueError:
            return None
    return max(began, default=None)


def use_after_audit_findings(ctx: Checked) -> list[GateFinding]:
    """`later_use_findings` for CTX, a protocol whose result an analysis
    audit covers: against the start of the latest covering record's
    attempt (`audit_began`; a journal that does not read gives none, and
    then no run is taken as shown). [] without `[explored_in]` or an
    answering run. Raises BlockError on an `[explored_in]` that does not
    read, what `covering_analysis` raises, RuntimeError when git fails."""
    if ctx.run is None or protocol_block.explored_in(ctx.text) is None:
        return []
    covering = covering_analysis(ctx.area, ctx.text, ctx.run)
    try:
        journal = attempts.read_journal(ctx.area)
    except attempts.AttemptError:
        journal = []  # no start reads: `audit_began` gives None
    began = audit_began(covering, journal)
    return later_use_findings(ctx.area, ctx.protocol, ctx.text, ctx.area_state, began)


def later_use_findings(
    area: Path,
    protocol: Path,
    text: str,
    state: AreaState,
    began: datetime | None,
) -> list[GateFinding]:
    """One warning per run of the exploration's area that shares an input
    digest with a run of the confirmation PROTOCOL of AREA (its text TEXT,
    the area's state STATE) and that an audit begun at BEGAN was not shown
    (`exploration_state.not_shown_since`; BEGAN None: no run is taken as
    seen). The search is the audit's own (`exploration_state.shared_inputs`
    over the runs of the exploration's area, read from the working tree),
    so a new analysis audit is shown every run named here — the way out.
    [] without `[explored_in]` and without a stamped id. [] too for a link
    whose id names no protocol of the repo, or several: the search did not
    run then, and that is not this function's finding — report-check's
    registration station (2) holds the release for it (`link_gaps`, asked
    for every protocol, before this function), so "no warning" never
    stands alone there.
    Raises BlockError on an `[explored_in]` that does not read,
    RuntimeError when git fails."""
    link = protocol_block.explored_in(text)
    pid = protocol_block.head(text).id
    if link is None or pid is None:
        return []
    hits = protocol_block.repo_protocol_ids(area).get(link.protocol, [])
    if len(hits) != 1:
        return []  # no search ran: `unresolved_link_hold` is its blocker
    theirs = hits[0].parent
    shared = shared_inputs(
        state.measured_of(pid).runs,
        state_of(theirs).runs,
        {m.run_id for m in basis_closure(theirs, link.run)},
    )
    by_run: dict[str, list[SharedInput]] = {}
    for s in not_shown_since(shared, began):
        by_run.setdefault(s.exploring_run, []).append(s)
    audit = audit_command(area, "--mode", "analysis", protocol=protocol)
    since = (
        f"started after the analysis audit that covers this result began "
        f"({began.isoformat(timespec='seconds')}; {CLOCKS_ASSUMED})"
        if began is not None
        else "the attempt journal gives no start of the analysis audit that "
        "covers this result (no entry names its record, or the journal or the "
        "time does not read), so no run is taken as shown to it"
    )
    return [
        GateFinding(
            WARNING,
            f"data use after the audit: run {run} of {theirs.name} recorded "
            f"{_same_files(pairs)} — {since}. The run is taken as not shown to that audit. "
            f"An equal sha256 is byte-identical content, not necessarily the same "
            f"file or origin; whether the confirmation is "
            f"independent of that run is not decided here, either way",
            fix=f"have the auditor judge it: `{audit}` shows every input digest "
            f"a run of that area shares with a run of this protocol",
            evidence_kind=STATIC_EVIDENCE,
            rule=LAB_050,
        )
        for run, pairs in by_run.items()
    ]


@dataclass(frozen=True)
class LastHeld:
    """What the history tells of an id no protocol of the repo carries
    (`last_held` asks; `unresolved_link_hold` words the restore from it):
    FILES, each protocol file the working tree lacks that carried the id
    in the last commit that held it, with that commit; UNKNOWN, "" when
    the history was read, else why it was not — no repository, or git's
    words on a history it could not list. Empty FILES with UNKNOWN "" is
    an answer: no commit holds a restore."""

    files: tuple[tuple[Path, str], ...] = ()
    unknown: str = ""


def last_held(area: Path, pid: str) -> LastHeld:
    """`LastHeld` for PID in the repository AREA lies in
    (`protocol_then.last_held_with_id`). A history git cannot list is not
    read as "no commit holds it": its words are the answer's UNKNOWN, told
    in the blocker. Raises GitError when git cannot run."""
    root = git_root(area)
    if root is None:
        return LastHeld(unknown=f"{shown(area, Path.cwd())} lies in no git repository")
    try:
        return LastHeld(tuple(last_held_with_id(root, pid)))
    except HistoryUnread as exc:
        return LastHeld(unknown=str(exc))


def link_gaps(ctx: Checked) -> list[GateFinding]:
    """The hold on a link that names no one protocol, read from CTX: the
    rule `unresolved_link_hold` over CTX's `[explored_in]`, the protocol
    ids of the repository as the working tree holds them
    (`protocol_block.repo_protocol_ids`), whether the area holds a
    measurement of the protocol (`Measured.has_measured`) and, for an id
    no file carries, what the history holds of it (`last_held`; not asked
    otherwise). Asked in every lane, with or without an answering run or
    a covering audit. Raises BlockError on an `[explored_in]` that does
    not read, GitError when git cannot run."""
    link = protocol_block.explored_in(ctx.text)
    if link is None:
        return []
    ids = protocol_block.repo_protocol_ids(ctx.area)
    gone = LastHeld()
    if not ids.get(link.protocol):
        gone = last_held(ctx.area, link.protocol)
    return unresolved_link_hold(
        link,
        ids,
        ctx.area,
        ctx.protocol,
        ctx.head.id,
        ways_out.handover(ctx.protocol),
        has_measured=ctx.area_state.measured_of(ctx.head.id).has_measured,
        gone=gone,
    )


def unresolved_link_hold(
    link: ExploredIn | None,
    ids: Mapping[str, Sequence[Path]],
    area: Path,
    protocol: Path,
    pid: str | None,
    handover_way: str,
    *,
    has_measured: bool,
    gone: LastHeld,
) -> list[GateFinding]:
    """The BLOCKER for a LINK (the `[explored_in]` of PROTOCOL in AREA,
    whose own stamped id is PID, the one a new registration replaces)
    whose id names no protocol among IDS (the repo's protocol ids, each
    with the files that carry it) or several; [] for an id that names
    exactly one, and without a link (None).

    The link names the basis of the confirmation. While it resolves to no
    one protocol, nothing of that basis is read: neither the state the
    audit follows nor the inputs the exploration's runs share with this
    protocol's (`later_use_findings`). That is a check that did not run,
    not a check that found nothing, so the result that names the
    exploration is not released over it — unlike a shared input, which is
    a hint and warns. The condition is exact (guaranteed).

    The ways out make the id name exactly one protocol: the exploratory
    protocol restored where none carries the id; where several do, the
    copy removed, or kept under a fresh id — a step by hand the sentence
    names, since no command gives an existing protocol a new id. The restore is worded from GONE (`LastHeld`, read only
    where no file carries the id): the checkout of each file the history
    holds under the id, from the last commit that held it; where the
    history holds none, or was not read, a sentence saying what is not
    known — never a command with open slots. The link itself is written anew only while HAS_MEASURED is
    False (`Measured.has_measured`: no run of PROTOCOL that measured or
    may have, a lost one included); with one, the link is a registration
    part and stays as registered, and the alternatives are a new
    registration or the handover (HANDOVER_WAY, `ways_out.handover`).
    Pure."""
    if link is None:
        return []
    hits = ids.get(link.protocol, [])
    if len(hits) == 1:
        return []
    if not hits:
        named = "no protocol of this repo"
        restores = ", ".join(
            f"`{checkout_command(shown(path, Path.cwd()), commit)}`"
            for path, commit in gone.files
        )
        if gone.unknown:
            resolve = (
                f"bring the exploratory protocol back from the commit that "
                f"holds it — which commit and which path is not known here: "
                f"{gone.unknown}"
            )
        elif not gone.files:
            resolve = (
                "put the exploratory protocol back in its place — git names "
                "no restore: no commit of this repository holds a protocol "
                "file with that id that the working tree lacks (it was never "
                "committed, or its id was changed in a file that still stands)"
            )
        elif len(gone.files) == 1:
            resolve = (
                f"bring the exploratory protocol back from the last commit "
                f"that held it ({restores})"
            )
        else:
            resolve = (
                f"bring the exploratory protocol back — {len(gone.files)} files "
                f"carried the id, each in the last commit that held it; restore "
                f"the one the link means ({restores})"
            )
    else:
        named = f"{len(hits)} protocols ({', '.join(str(h) for h in hits)})"
        checks = ", ".join(f"`{gate_command('protocol-check', h)}`" for h in hits)
        # no command gives an existing protocol a fresh id: the step is by
        # hand, and the sentence names it and the file it acts on
        resolve = (
            f"one of these files is the exploration the link means — the one "
            f"whose area holds its run, runs/{link.run}/ —; each other file "
            f"is a copy, and no command gives it a fresh id. Remove the copy "
            f"from the repo; or, to keep it as a protocol of its own, stamp "
            f"one (`{stamp_command()}` writes a fresh id), carry the copy's "
            f"text into the new PROTOCOL-*.md by hand — every line but the "
            f"`id` in its head —, and then remove the copy ({checks} name "
            f"the duplicate id)"
        )
    if has_measured:
        other = (
            f"the link itself is registered and stays as written; where the "
            f"exploration cannot be named again, either "
            f"{register_anew(pid or '<id>')}; or {handover_way}"
        )
    else:
        other = (
            f"or, as this protocol has no measurement yet, write the "
            f"link anew (`{explored_in_command(protocol)}`)"
        )
    return [
        blocker(
            f"exploration link: [explored_in] protocol = {link.protocol} names "
            f"{named} — the exploration this confirmation names as its basis "
            f"was not read: neither the state its audit follows nor the inputs "
            f"its runs share with this protocol's were checked. That is no "
            f"check, not a check that found nothing; the result is not "
            f"released over it",
            fix=f"make the id name exactly one protocol of the repo: {resolve}, "
            f"then `{gate_command('report-check', area)}`; {other}",
            stated_outcome=NOT_EXECUTABLE,
            rule=TECHNICAL_RULE,
        )
    ]


def _same_files(pairs: Sequence[SharedInput]) -> str:
    """The inputs of one exploring run that PAIRS name, each with the
    confirming run's input holding the same bytes."""
    return "; ".join(
        f"its input {s.exploring_key} with the sha256 of {s.confirming_key} "
        f"of run {s.confirming_run} ({s.sha256[:12]})"
        for s in pairs
    )
