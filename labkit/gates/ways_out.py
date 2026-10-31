"""ways_out — what a BLOCKER is, the ways out of one by its cause, and the
handover sentence: the texts `labkit-audit` prints with every decision
list and report-check prints in its holds. Model-free, so the release gate
reads them without loading a model backend (audit 2026-10-27, third, M1);
the stamped AGENTS.md states the same ways ("When you are stuck") and
`tests/test_ways_out.py` holds both to the same names and every command to
a real one.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from labkit.formats.gate import BLOCKER, GateFinding
from labkit.formats.repo import withdraw_command

#: what a BLOCKER is and what closes it, printed above the decisions: an
#: agent whose code missed the registered bar moved the bar to the score
#: (ninth haiku round, t5: 0.75 registered, 0.65 written after the audit).
#: A route promises only what a gate checks: report-check holds the fields
#: the kind owes and the kind to the first measurement's commit
#: (`report_check.registration_gaps`), and the promise block to the
#: registration the first measurements recorded
#: (`finalize.registration_changes`) — a bar lowered after it and
#: measured again is held
#: the ways out of a BLOCKER, by its cause: (name, what to do). Printed with
#: every decision list (`blocker_routes`) and stated in the stamped AGENTS.md
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


def report_way_while_lost(findings_command: str) -> str:
    """The way out of a report that cites or discusses a run of an area
    whose audit evidence is gone (`attempts.evidence_gaps`): labkit-audit
    starts no attempt there (`attempts.begin`), so neither the audit an
    adoption owes nor the report review a discussion owes can run — bring
    the evidence back (FINDINGS_COMMAND lists each loss with its restore),
    or the report cites no run of the area. The one wording report-check's
    report holds, `--report-review`'s refusal, the adoption's refusal and
    the handover print."""
    return (
        "while the area's audit evidence is gone labkit-audit starts no audit "
        "and no review, so neither the audit an adoption owes nor the report "
        "review a discussion owes can run: (a) bring the evidence back "
        f"(`{findings_command}` lists each loss with its restore); (b) where "
        "nothing restores it, the report cites no run of the area — remove "
        "the run ids and the discussion block, keep its handover block (it "
        "names the protocol, not its runs)"
    )


#: the way out of a protocol choice a command cannot make for itself
PROTOCOL_NAMED = "name the protocol: `--protocol PROTOCOL-<name>.md`"
#: the way out of a model answer that did not keep the form labkit reads
ANSWER_AGAIN = (
    "run the same command again: the answer did not keep the form, and another draw may"
)
#: the way out of an audit whose inputs moved while it read them
AUDIT_AGAIN = "run the audit again on the state as it stands"


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


#: the cause whose way out is an effect `<ID> not assessable` — WAYS_OUT
#: states it for a protocol with promises; for one without (a computation)
#: `blocker_routes` prints NO_PROMISE_ROUTE in its place
UNJUDGED_PROMISE = "an unjudged promise"
WAYS_OUT = (
    (
        "an implementation error",
        "the code does not do what the registration says: fix the code (where "
        "the protocol has adopted a result, withdraw it first — `protocol-fill "
        '<PROTOCOL> --withdraw --why "<why>"`), decide `fixed` naming the change, '
        "measure again under the unchanged registration, audit the new run",
    ),
    (
        "a missed criterion",
        "the code does what it says and the criterion is missed: that is the "
        "result — report the miss first (LAB-042 Log the outcome — failures "
        "too); a bar set after a result is seen answers no registered question, "
        "and report-check holds a registration changed after the first measurement",
    ),
    (
        UNJUDGED_PROMISE,
        "a fault you cannot fix leaves a promise unjudged: decide it `limitation` "
        "with `--not-assessable <ID>`; the criterion then reads not "
        "assessable — report the measured numbers as description, no verdict",
    ),
    (
        "an invalid registration",
        "the registration cannot be answered as written: it is not repaired in "
        f"place — {register_anew()}; hand the earlier protocol over "
        "(`--handover`), its open BLOCKERs stay open in that record. The "
        "earlier verdict is rendered first; a new approach never turns an "
        "earlier miss into a pass",
    ),
    (
        "an incomplete registration",
        "the commit of the first measurement lacked a choice that steers the "
        "result or its judgement (report-check names the field): that "
        "measurement is exploratory, and a new run on the same data does not "
        "restore what stood before the number. When the missing choice can be "
        f"made on grounds the new registration states, {register_anew()}; else "
        f"{HANDOVER}. A pure typo in a prose field is corrected in the protocol "
        "itself",
    ),
    (
        "a wrong adoption",
        "the measurement stands and the protocol's head has adopted a run that "
        "does not answer — the finding names the one that does: withdraw the "
        "adoption "
        '(`protocol-fill <PROTOCOL> --withdraw --why "<why>"`), decide `fixed` '
        "naming that, run the analysis audit again — the follow-up judges the "
        "finding —, then adopt the run that answers (`labkit-adopt`); no new "
        "measurement",
    ),
    (
        "none of these",
        "a way out above cannot be taken because a prerequisite it names is "
        "missing — name which; a refusal alone is no reason, it names its next "
        f"step: stop and {HANDOVER} — the open BLOCKERs stay open and the "
        "handover records them, with why it stops. Never hand-edit audit or "
        "run evidence; decisions use --decide, generated report blocks use "
        "protocol-fill; never --no-verify",
    ),
)
#: each way out in one line, as the decision list prints it: when it is
#: the cause, and the next step — the whole text stands in WAYS_OUT and
#: AGENTS.md ("When you are stuck"); the cold agent of the declared-run case
#: found the full list hard to filter
WAYS_OUT_SHORT = {
    "an implementation error": (
        "the code does not do what the registration says → fix it (an adopted "
        "result: `--withdraw` first), decide `fixed`, measure again, audit"
    ),
    "a missed criterion": (
        "the code is right and the criterion is missed: that is the result → "
        "report the miss first (LAB-042 Log the outcome — failures too); never "
        "move the bar"
    ),
    UNJUDGED_PROMISE: (
        "a fault you cannot fix → `limitation` with `--not-assessable <ID>`; the "
        "numbers stay description"
    ),
    "an invalid registration": (
        "the question cannot be answered as written: it is not repaired in place "
        '→ register anew, naming the earlier one in `[replaces] protocol = "<id>"`, '
        "exploratory; a new approach never turns an earlier miss into a pass"
    ),
    "an incomplete registration": (
        "report-check names a field missing at the first measurement → "
        "register anew with `[replaces]`, or hand over"
    ),
    "a wrong adoption": (
        "the measurement stands, the head adopted a run that does not answer → "
        "`--withdraw`, decide `fixed`, audit again, then `labkit-adopt`; no new "
        "measurement"
    ),
    "none of these": (
        "a way out cannot be taken for a missing prerequisite you can name → "
        "`--handover`, which records the open BLOCKERs; never `--no-verify`"
    ),
}
#: the one-line form of NO_PROMISE_ROUTE
NO_PROMISE_SHORT = (
    "a fault you cannot fix, no promise registered → `limitation` with the limit "
    "named, or hand over"
)
#: where every way out stands in full
WAYS_OUT_IN_FULL = 'each in full: AGENTS.md, "When you are stuck"'


#: the unjudged-promise cause's way out where the protocol registers no
#: promise — a computation has no [[promise]] table, and `--decide` refuses
#: every id an effect names there (`audit_decisions._registered`); the routes left
#: are the ones that work: limit the claim, fix the fault, defer and hand over
NO_PROMISE_ROUTE = (
    "this protocol registers no promise, so no effect leaves one not "
    "assessable (`--decide` refuses every id): a fault you cannot fix limits "
    "the claim — decide it `limitation`, the limit named in the Conclusion (a "
    "second auditor must uphold it) — or hand over"
)


def blocker_routes(promised: bool, *, full: bool) -> tuple[str, ...]:
    """The ways out of a BLOCKER by its cause — FULL as WAYS_OUT states them
    (shown to the analysis auditor), else one line each (WAYS_OUT_SHORT,
    printed with a decision list) and where they stand in full; for a
    protocol that registers no promise (not PROMISED) the unjudged-promise
    route as NO_PROMISE_ROUTE or NO_PROMISE_SHORT."""

    def what(name: str, text: str) -> str:
        if name == UNJUDGED_PROMISE and not promised:
            return NO_PROMISE_ROUTE if full else NO_PROMISE_SHORT
        return text if full else WAYS_OUT_SHORT[name]

    return (
        "  before deciding a BLOCKER, name which of these it is:",
        *(f"    {name}: {what(name, text)}" for name, text in WAYS_OUT),
        *(() if full else (f"    ({WAYS_OUT_IN_FULL})",)),
    )


#: how long a finding's text stands in the decision list


#: what every hold names first while a declared run's code has changed
WITHDRAW_FIRST = "withdraw the adoption first (`{command}`), then "


def declared_first(finding: GateFinding, protocol: Path) -> GateFinding:
    """FINDING with the withdrawal of PROTOCOL's declaration before its way
    out — for a blocker of a state whose declared run's code changed since
    it ran: the commit hook holds the code to that run, and an audit made
    while it stands declared does not cover the next run. A warning, or a
    blocker without a way out, comes back as it is. Why in each hold, not
    in one note: six holds that said "measure anew" led past a note below
    them (decision-reading probe and file-check case, 2026-10-28)."""
    if finding.grade != BLOCKER or finding.fix is None:
        return finding
    first = WITHDRAW_FIRST.format(command=withdraw_command(protocol))
    return replace(finding, fix=first + finding.fix)
