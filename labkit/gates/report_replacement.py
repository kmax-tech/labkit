"""The replacement station of `report_check`: a protocol that declares
`[replaces]` answers a new, post-hoc question, and the declaration binds
it to one predecessor of the repo (`replacement_gaps`).
"""

from __future__ import annotations


from dataclasses import replace
from pathlib import Path

from labkit.formats.repo import gate_command
from labkit.formats.gate import (
    GateFinding,
    blocker,
)
from labkit.formats.protocol_history import (
    registration_differences,
    registrations_as_first_measured,
)
from labkit.formats import (
    findings,
    handovers,
    protocol_block,
)
from labkit.gates import ways_out
from labkit.formats.repo import (
    decide_command,
    git_root,
    handover_command,
)
from labkit.gates.report_context import Checked


def replacement_gaps(ctx: Checked) -> list[GateFinding]:
    """A protocol that declares `[replaces]` (K1,
    docs/notes/2026-10-27-new-registration-contracts.md) answers a new,
    post-hoc question, and the declaration binds it, exactly: the
    predecessor is one protocol of the repo, not itself, and the chain of
    replacements has no circle; the protocol is `type = "exploratory"`;
    every difference of its registration against the predecessor's — each
    as its first measurements saw it (`protocol_history.
    registrations_as_first_measured`; against each when they saw several,
    the way out of K3's registration that cannot be told) — is a
    `[[replaces.change]]`, and every
    declared change is one (`registration_differences`); the predecessor's
    open BLOCKERs are decided first. Blockers, each with the line or command
    that clears it. Nothing without `[replaces]`: an undeclared successor is
    indicated at the report (`replacement_hints`), never held here."""
    name = ctx.protocol.name
    try:
        rep = protocol_block.replaces(ctx.text)
    except protocol_block.BlockError as exc:
        return [
            blocker(
                f"{name}: {exc}",
                fix='write `[replaces]` as the head reads it: `protocol = "<id>"` '
                "and one `[[replaces.change]]` (what, from, to, why) per change",
            )
        ]
    if rep is None or ctx.head.id is None:
        return []
    pred = _predecessor(ctx, rep.protocol)
    if isinstance(pred, GateFinding):
        return [replace(pred, text=f"{name}: {pred.text}")]
    out = []
    if ctx.head.type != "exploratory":
        out.append(
            blocker(
                f'{name}: [protocol] type = "{ctx.head.type}" — a protocol that replaces '
                f"another answers a new, post-hoc question",
                fix='set `type = "exploratory"` in its head',
            )
        )
    out += [
        replace(f, text=f"{name}: {f.text}")
        for f in _undeclared_changes(ctx, rep, pred)
    ]
    out += [replace(f, text=f"{name}: {f.text}") for f in _predecessor_open(ctx, pred)]
    return out


def _predecessor(ctx: Checked, pid: str) -> Path | GateFinding:
    """The predecessor's protocol for `[replaces] protocol = PID`, or why it
    is none, as a blocker with its way out: its own id, no or several
    protocols of the repo carrying PID, or a circle of replacements."""
    if pid == ctx.head.id:
        return blocker(
            "[replaces] protocol is its own id",
            fix=f"name the protocol it replaces in [replaces] protocol, then "
            f"`{gate_command('report-check', ctx.area)}`",
        )
    hits = protocol_block.repo_protocol_ids(ctx.protocol).get(pid, [])
    if len(hits) != 1:
        return blocker(
            f"[replaces] protocol = {pid} names "
            + ("no protocol of this repo" if not hits else f"{len(hits)} protocols"),
            fix="name the one protocol of this repo it replaces, kept as it "
            f"is, then `{gate_command('report-check', ctx.area)}`",
        )
    circle = _replacement_circle(str(ctx.head.id), hits[0])
    if circle:
        return blocker(
            f"the replacements run in a circle ({circle})",
            fix=f"let each name the one before it, then "
            f"`{gate_command('report-check', ctx.area)}`",
        )
    return hits[0]


def _undeclared_changes(
    ctx: Checked, rep: protocol_block.Replaces, pred: Path
) -> list[GateFinding]:
    """Every difference of the registration against PRED's that REP does not
    declare, and every declared change that is none — PRED's registration
    as each of its first measurements saw it (several: the changes are owed
    against each), this protocol's as its first measurement saw it, or as
    it stands before one; or why they cannot be compared."""
    olds, missing = registrations_as_first_measured(pred, rep.protocol, git_root(pred))
    news, own_missing = registrations_as_first_measured(
        ctx.protocol, str(ctx.head.id), git_root(ctx.protocol)
    )
    gaps = [
        f"{p.name}: {why}"
        for p, why in ((pred, missing), (ctx.protocol, own_missing))
        if why
    ]
    if len(news) > 1:
        gaps.append(
            f"{ctx.protocol.name}: its own first measurements saw different "
            f"registrations (the registration station names them)"
        )
    if gaps:
        return [
            blocker(
                f"the registrations cannot be compared — {'; '.join(gaps)}",
                fix=f"until they can, {ways_out.HANDOVER}",
            )
        ]
    ((new, new_where),) = news
    computed: dict[tuple[str, str, str], str] = {}
    for old, old_where in olds:
        for change in registration_differences(old, new):
            computed.setdefault(change, old_where)
    listed = {(c.what, c.from_, c.to) for c in rep.changes}
    s = protocol_block.toml_string
    out = [
        blocker(
            f"changed against {pred.name} ({old_where}) and not declared: {what} {x} → "
            f"{y}",
            fix=f"add under [replaces]: [[replaces.change]] what = {s(what)}, from = "
            f'{s(x)}, to = {s(y)}, why = "…"; then '
            f"`{gate_command('report-check', ctx.area)}`",
        )
        for (what, x, y), old_where in computed.items()
        if (what, x, y) not in listed
    ]
    against = "; ".join(where for _, where in olds)
    out += [
        blocker(
            f"declares a change the registrations do not show: {what} {x} → {y} "
            f"(the predecessor {against}, this protocol {new_where})",
            fix=f"remove that [[replaces.change]], then "
            f"`{gate_command('report-check', ctx.area)}`",
        )
        for what, x, y in sorted(listed - set(computed))
    ]
    return out


def _predecessor_open(ctx: Checked, pred: Path) -> list[GateFinding]:
    """PRED's BLOCKERs still `open` that no handover of PRED's area records
    (`handovers.handed_over`) — each holds the replacement until it is
    decided, or the predecessor is handed over (its open BLOCKERs stay open
    in that record)."""
    try:
        held = findings.open_blockers(findings.area_records(pred.parent))
        recorded = handovers.handed_over(pred.parent) if held else set()
    except (findings.FindingsError, handovers.HandoverError) as exc:
        return [
            blocker(
                f"the predecessor's audit records do not read: {exc}",
                fix=findings.record_way(pred.parent, pred),
            )
        ]
    return [
        blocker(
            f"its predecessor's BLOCKER is still open — {u.line}",
            fix="decide it (`"
            + decide_command(
                pred.parent,
                u.number,
                "STATUS",
                "<why>",
                u.record.path.name,
                protocol=pred,
            )
            + f"`), or hand the predecessor over, replaced by {ctx.head.id}: `"
            + handover_command(pred)
            + "`",
        )
        for u in held
        if handovers.entry(u.record, u.number) not in recorded
    ]


def _replacement_circle(start: str, pred: Path) -> str:
    """The chain of `[replaces]` from PRED back, as ids joined by ` → `,
    when it returns to START or to an id it already passed; "" when it
    ends."""
    seen = [start]
    current: Path | None = pred
    while current is not None:
        try:
            text = current.read_text(encoding="utf-8")
            pid = protocol_block.head(text).id
            nxt = protocol_block.replaces(text)
        except (OSError, protocol_block.BlockError):
            return ""
        if pid in seen:
            return " → ".join([*seen, str(pid)])
        seen.append(str(pid))
        if nxt is None:
            return ""
        hits = protocol_block.repo_protocol_ids(current).get(nxt.protocol, [])
        current = hits[0] if len(hits) == 1 else None
    return ""
