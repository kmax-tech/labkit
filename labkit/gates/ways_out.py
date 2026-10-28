"""ways_out — what a BLOCKER is, the ways out of one by its cause, and the
handover sentence: the texts `labkit-audit` prints with every decision
list and report-check prints in its holds. Model-free, so the release gate
reads them without loading a model backend (audit 2026-10-27, third, M1);
the stamped AGENTS.md states the same ways ("When you are stuck") and
`tests/test_ways_out.py` holds both to the same names and every command to
a real one.
"""

from __future__ import annotations

from pathlib import Path

from labkit.formats import findings
from labkit.formats.repo import audit_command, decide_command

#: what a BLOCKER is and what closes it, printed above the decisions: an
#: agent whose code missed the registered bar moved the bar to the score
#: (ninth haiku round, t5: 0.75 registered, 0.65 written after the audit).
#: A route promises only what a gate checks: report-check holds the fields
#: the kind owes and the kind to the first measurement's commit
#: (`report_check.registration_gaps`), and the promise block to the
#: registration the first measurements recorded
#: (`report_check.registration_changes`) — a bar lowered after it and
#: measured again is held
#: the ways out of a BLOCKER, by its cause: (name, what to do). Printed with
#: every decision list (BLOCKER_ROUTES) and stated in the stamped AGENTS.md
#: ("When you are stuck"); tests/test_ways_out.py holds both to the same
#: names and every command to a real one. The repair case (2026-10-27)
#: took the invalid-registration route for a missed criterion and moved
#: its bars inside it: the miss comes first, a new registration declares
#: what it changes (K1–K3, docs/notes/2026-10-27-new-registration-contracts.md).
#: how a question that cannot be answered leaves the session — the one
#: sentence the ways out and report-check's holds (K1, K3) print. A run id
#: in a report reads as that run's number: report-check holds the answering
#: run of a protocol that declares no result, so a handover names the
#: protocol (the counter-case of 2026-10-27, tests/test_counter_cases.py)
HANDOVER = (
    "hand over: `labkit-audit <area> --findings` prints the --decide and "
    "`protocol-fill <PROTOCOL> --handover` commands — the handover leaves no "
    "[result] table in the protocol's head, and its block in the report names "
    "the protocol, not its runs (a cited run id reads as a reported number), "
    "what stands in the way and what was tried; no number"
)


def register_anew(pid: str = "<id>", per: str = "per change") -> str:
    """The way out of a registration that cannot be answered as written
    (K1): a new exploratory protocol naming the earlier one PID, its
    changes declared PER what the caller names — the one wording the ways
    out and report-check's holds (K3) print."""
    return (
        "register anew: a new protocol (`labkit-init exp <new-name> --kind …`), "
        '`type = "exploratory"`, committed before its own first run, naming the '
        f'earlier one in `[replaces] protocol = "{pid}"` with one '
        f"`[[replaces.change]]` (what, from, to, why) {per}"
    )


WAYS_OUT = (
    (
        "an implementation error",
        "the code does not do what the registration says: fix the code, measure "
        "again under the unchanged registration, audit the new run; `fixed` names "
        "the change",
    ),
    (
        "a missed criterion",
        "the code does what it says and the criterion is missed: that is the "
        "result — report the miss first (LAB-042 Log the outcome — failures "
        "too); a bar set after a result is seen answers no registered question, "
        "and report-check holds a registration changed after the first measurement",
    ),
    (
        "an unjudged promise",
        "a fault you cannot fix leaves a promise unjudged: decide it accepted "
        'with `--effect "<ID> not assessable"`; the criterion then reads not '
        "assessable — report the measured numbers as description, no verdict",
    ),
    (
        "an invalid registration",
        "the registration cannot be answered as written: it is not repaired in "
        f"place — {register_anew()}; decide the "
        "earlier protocol's open BLOCKERs `deferred`, naming the new one. The "
        "earlier verdict is rendered first; a new approach never turns an "
        "earlier miss into a pass",
    ),
    (
        "none of these",
        f"stop and {HANDOVER} — decide each readable open BLOCKER first "
        "(deferred, with why it stays unresolved). Never hand-edit audit or "
        "run evidence; decisions use --decide, generated report blocks use "
        "protocol-fill; never --no-verify",
    ),
)
BLOCKER_ROUTES = (
    "  before deciding a BLOCKER, name which of these it is:",
    *(f"    {name}: {what}" for name, what in WAYS_OUT),
)
#: how long a finding's text stands in the decision list


def decide_way(
    area: Path, open_finding: findings.OpenFinding, protocol: Path | None = None
) -> str:
    """The way out of OPEN_FINDING, an audit finding nobody decided in AREA:
    its `--decide` command (`repo.decide_command`, STATUS and the reason
    left for the person), and for a BLOCKER the `--findings` command that
    prints the ways out by cause beside it — the fix the gates that hold an
    undecided finding name."""
    cmd = decide_command(
        area,
        open_finding.number,
        "STATUS",
        "<why>",
        open_finding.record.path.name,
        protocol=protocol,
    )
    way = f"decide it ({findings.DECIDED_LIST}): `{cmd}`"
    if open_finding.grade != "BLOCKER":
        return way
    return (
        f"{way} — `{audit_command(area, '--findings', protocol=protocol)}` "
        f"prints the ways out of a BLOCKER by its cause"
    )


def record_way(area: Path, protocol: Path | None = None) -> str:
    """The way out of an audit record in AREA that does not read: restore it
    as labkit-audit wrote it or audit again, and the recovery entry
    (`--findings`) that names what stands and the handover — never a
    record rewritten by hand."""
    return (
        "restore the record as labkit-audit wrote it (`git checkout HEAD -- "
        "<record>` where git holds it) or audit again; "
        f"`{audit_command(area, '--findings', protocol=protocol)}` names what "
        "stands and the handover"
    )
