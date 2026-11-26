"""finding_limits — a limitation's effect on the verdicts and the Limitation
line the protocol carries it in.

A finding decided `limitation` records its effect: `stands` (the verdicts
hold, read within the limit) or `<ID>[, <ID>] not assessable` (the run does
not judge the named promises; `leaves_unjudged`, `effect_ids`). The protocol
carries each limit as a `Limitation (audit <record> #N)` line (`limit_label`,
`limit_line`) and a note in Recorded results (`answer_note`). An effect of
another form raises ValueError.
"""

from __future__ import annotations

import re

from labkit.formats import promises
from labkit.formats.findings import Finding, Record


#: a limit's effect on the verdicts: they stand with the limit, or the run
#: judges the named promises not at all (`--not-assessable`)
EFFECT_STANDS = "stands"
_EFFECT_NOT = re.compile(r"^(\S+(?:\s*,\s*\S+)*)\s+not assessable$")
EFFECT_FORM = (
    '`stands` or `<ID>[, <ID>] not assessable` (e.g. "criterion-1 not assessable")'
)


def leaves_unjudged(effect: str) -> bool:
    """Whether the limitation's EFFECT is `<ID>[, <ID>] not assessable` — it
    voids the verdicts of what it names —, not `stands` and not none. The
    one test of the form: rendering lifts such an effect a review did not
    uphold, and the way after a rejection is its own."""
    return bool(effect) and effect != EFFECT_STANDS


def effect_ids(effect: str) -> tuple[str, ...]:
    """The promise ids EFFECT leaves not assessable, in its order — () for
    `stands`. Raises ValueError on any other text or an id that is no
    promise id (`promises.is_block_id`)."""
    if effect == EFFECT_STANDS:
        return ()
    m = _EFFECT_NOT.match(effect.strip())
    ids = tuple(i.strip() for i in m.group(1).split(",")) if m else ()
    if not ids or not all(promises.is_block_id(i) for i in ids):
        # an id in the letters of 0.103.0 names the version that reads it
        earlier = any(promises.EARLIER_ID.match(f"[{i}]") for i in ids)
        help_ = f"; {promises.EARLIER_IDS_HELP}" if earlier else ""
        raise ValueError(f"effect {effect!r} — {EFFECT_FORM}{help_}")
    return ids


def effect_sentence(effect: str) -> str:
    """EFFECT as the protocol's Limitation line opens with it."""
    ids = effect_ids(effect)
    if not ids:
        return "the verdicts stand, read within this limit"
    return f"{', '.join(ids)} not assessable with this run"


#: how every Limitation line's label opens
LIMIT_PREFIX = "Limitation (audit "


def limit_label(record: Record, n: int) -> str:
    """The protocol label that carries finding N of RECORD as a limit."""
    return f"{LIMIT_PREFIX}{record.path.stem} #{n})"


#: the Limitation line's opening for a `stands` a decision review did not
#: confirm: it claims neither that the verdicts stand nor that they fall
UNCONFIRMED = "a limit proposed, not confirmed by a second auditor — unresolved"


def limit_line(finding: Finding, *, contested: bool) -> str:
    """The value of a Limitation line: FINDING's effect, then the person's reason
    (`limit_label` is the label beside it). CONTESTED: a decision review of
    the decision as it stands said other than `upheld`
    (`reviews.contested`) — the line then opens with UNCONFIRMED in place
    of the effect."""
    reason = " ".join(finding.reason.split())
    opening = UNCONFIRMED if contested else effect_sentence(finding.effect)
    return f"{opening} — {reason}"


def answer_note(limits: list[tuple[str, str]]) -> str:
    """What the Recorded results line says of LIMITS, (label, effect) each:
    one note counting them; the Limitation lines below carry each one whole, and
    which promise one leaves not assessable stands in the line's verdicts
    (`result_render.verdicts`). Empty for no limits. One note for all, so
    the line does not grow a "read within" tail per limit."""
    if not limits:
        return ""
    n = len(limits)
    return f"; subject to {n} recorded limitation{'s' if n > 1 else ''} (the Limitation lines below)"
