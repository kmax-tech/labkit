"""decision_history — the decisions on an audit finding that a later one replaced.

`labkit-audit AREA --decide N STATUS --why REASON` sets a finding's
decision (`findings.write_decision`). A decision it replaces is kept in the
finding's table, oldest first, one entry per line:

    [[finding]]
    grade = "BLOCKER"
    text = "…"
    replaced_decisions = [
      { status = "fixed", reason = "seed now set", effect = "", until = "2026-11-24T14:02" },
    ]
    status = "open"
    reason = "the seed is set after the split; the fix does not hold"

An entry is the decision as it stood — `status`, `reason`, `effect` — and
`until`, the minute a later decision replaced it (as the record's `[audit]
date`). The key is absent while no decision was replaced: a new record
holds none, and a present key holds at least one entry.

Which decisions are kept (`after_replacing`): every decision another one
replaces — a status taken back, a reason corrected. The undecided start
(`open` without a reason) is no decision and leaves no entry; a decision
given again unchanged leaves none either.

A commit holds the history: a later version of the record may only add
entries after the committed ones, and a committed decision that was
replaced is the first entry added (`history_kept`, held by
`evidence.record_changed`). Entries a decision added and replaced again
between two commits have no witness and are taken as written.

The history is part of the decision a review confirms
(`findings.decision_digest`, through `digest_fields`): a decision taken
back and given again word for word has a longer history, so it is another
decision, and a review or a fix verdict of the earlier one says nothing
about it. A finding without history has the digest it had before the
history existed.

Kept for the findings of an audit record only. The claims of a report
review (`report_reviews.write_claim_decision`) keep no history. The
history is not shown to the decision reviewer or the follow-up auditor;
`labkit-audit --findings` shows each entry on one line.
Why: docs/notes/2026-11-25-keep-decisions-taken-back.md.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Protocol

from labkit.formats.protocol_block import toml_string
from labkit.formats.runs import DATE_MINUTE

#: the key of a `[[finding]]` table that holds its replaced decisions
KEY = "replaced_decisions"
#: the line that opens the array as labkit writes it, and the one that closes
#: it: each entry stands on a line of its own between them, so a line that
#: is `]` alone is never part of a value (`toml_string` writes one line)
ARRAY_OPENING = re.compile(rf"^\s*{KEY}\s*=\s*\[\s*$")
ARRAY_CLOSING = re.compile(r"^\s*\]\s*$")
_ENTRY_KEYS = ("status", "reason", "effect", "until")


class DecisionHistoryError(ValueError):
    """A `replaced_decisions` value that is not the form labkit writes; the
    message names what is wrong, the caller the file and the finding."""


@dataclass(frozen=True)
class ReplacedDecision:
    """One decision on a finding that a later decision replaced."""

    status: str
    reason: str
    effect: str
    # the minute the later decision was stored, as `runs.date_minute` writes it
    until: str


class DecidedFinding(Protocol):
    """What this module reads of a finding (`findings.Finding`): its decision
    as it stands, whether it is the undecided start, and its history."""

    @property
    def status(self) -> str:
        """The status as it stands."""
        ...

    @property
    def reason(self) -> str:
        """The reason given with it."""
        ...

    @property
    def effect(self) -> str:
        """A limit's effect, else ""."""
        ...

    @property
    def undecided(self) -> bool:
        """Is this the state a finding is written in, before any decision?"""
        ...

    @property
    def replaced_decisions(self) -> tuple[ReplacedDecision, ...]:
        """The decisions a later one replaced, oldest first."""
        ...


def read_entries(value: object) -> tuple[ReplacedDecision, ...]:
    """The replaced decisions a `[[finding]]` table holds under KEY, VALUE
    being what TOML read there (None when the key is absent: no history).
    Raises DecisionHistoryError when VALUE is no array, an empty one, or an
    entry is not a table of exactly `status`, `reason`, `effect` and `until`
    as strings, `until` a minute. Whether a status is one a finding can
    have and an effect fits it is the finding's check (`findings._finding`).
    Pure."""
    if value is None:
        return ()
    if not isinstance(value, list) or not value:
        raise DecisionHistoryError(
            f"{KEY} is not an array of at least one entry — the key is absent "
            f"while no decision was replaced"
        )
    entries: list[ReplacedDecision] = []
    for k, row in enumerate(value, start=1):
        if not isinstance(row, dict) or sorted(row) != sorted(_ENTRY_KEYS):
            raise DecisionHistoryError(
                f"{KEY} entry {k} is not a table of exactly {', '.join(_ENTRY_KEYS)}"
            )
        for key in _ENTRY_KEYS:
            if not isinstance(row[key], str):
                raise DecisionHistoryError(f"{KEY} entry {k}: {key} is not a string")
        try:
            time.strptime(row["until"], DATE_MINUTE)
        except ValueError as exc:
            raise DecisionHistoryError(
                f"{KEY} entry {k}: until {row['until']!r} is not a minute "
                f"(YYYY-MM-DDTHH:MM)"
            ) from exc
        entries.append(
            ReplacedDecision(row["status"], row["reason"], row["effect"], row["until"])
        )
    return tuple(entries)


def after_replacing(
    current: DecidedFinding, status: str, reason: str, effect: str, until: str
) -> tuple[ReplacedDecision, ...]:
    """The history of CURRENT once STATUS, REASON and EFFECT are stored as
    its decision at the minute UNTIL: its history, with CURRENT's own
    decision added as the newest entry — unless CURRENT is the undecided
    start, which is no decision, or the new decision equals the one that
    stands. Pure."""
    if current.undecided:
        return current.replaced_decisions
    if (current.status, current.reason, current.effect) == (status, reason, effect):
        return current.replaced_decisions
    replaced = ReplacedDecision(current.status, current.reason, current.effect, until)
    return current.replaced_decisions + (replaced,)


def history_kept(committed: DecidedFinding, now: DecidedFinding) -> bool:
    """Does NOW, a finding as it stands, keep the history of COMMITTED, the
    same finding as a commit holds it? Yes when COMMITTED's entries open
    NOW's unchanged and COMMITTED's decision was not lost: it still stands
    and nothing was added, or it is the first entry added. A COMMITTED that
    is the undecided start owes no entry, so any entries may follow. Entries
    after the first added one are not compared: no commit saw them. Pure."""
    held = committed.replaced_decisions
    if now.replaced_decisions[: len(held)] != held:
        return False
    if committed.undecided:
        return True
    decision = (committed.status, committed.reason, committed.effect)
    added = now.replaced_decisions[len(held) :]
    if not added:
        return (now.status, now.reason, now.effect) == decision
    return (added[0].status, added[0].reason, added[0].effect) == decision


def digest_fields(entries: tuple[ReplacedDecision, ...]) -> list[str]:
    """What ENTRIES add to the digest of a finding's decision
    (`findings.decision_digest`): nothing when there are none — a finding
    without history keeps its digest —, else KEY and every entry's status,
    reason, effect and minute in order. Pure."""
    if not entries:
        return []
    return [KEY] + [getattr(e, key) for e in entries for key in _ENTRY_KEYS]


def array_end(lines: list[str], opening: int) -> int | None:
    """The index after the line that closes the array LINES[OPENING] opens
    (ARRAY_OPENING): the array spans lines[opening:end]. None when no line
    after it closes it (ARRAY_CLOSING). LINES may keep their line breaks."""
    for j in range(opening + 1, len(lines)):
        if ARRAY_CLOSING.match(lines[j].strip("\r\n")):
            return j + 1
    return None


def entry_line(entry: ReplacedDecision) -> str:
    """ENTRY as its line in the array, without a line break: an inline table
    of four one-line strings (`toml_string`), indented, with its comma."""
    fields = ", ".join(
        f"{key} = {toml_string(getattr(entry, key))}" for key in _ENTRY_KEYS
    )
    return f"  {{ {fields} }},"


def array_lines(entries: tuple[ReplacedDecision, ...]) -> list[str]:
    """The array of ENTRIES as the lines a `[[finding]]` table holds it in,
    without line breaks: the opening, one line per entry, the closing."""
    return [f"{KEY} = [", *(entry_line(e) for e in entries), "]"]
