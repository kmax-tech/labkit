"""ways_out — what a BLOCKER is, the ways out of one by its cause, and the
handover sentence: the texts `labkit-audit` prints with every decision
list and report-check prints in its holds. Model-free, so the release gate
reads them without loading a model backend (audit 2026-10-27, third, M1);
the stamped AGENTS.md states the same ways ("When you are stuck") and
`tests/test_ways_out.py` holds both to the same names and every command to
a real one.
"""

from __future__ import annotations

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
        UNJUDGED_PROMISE,
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
        "a wrong declaration",
        "the measurement stands and the protocol's head declares another run "
        "than the one the finding judged: withdraw the declaration "
        '(`protocol-fill <PROTOCOL> --withdraw --why "<why>"`), decide `fixed` '
        "naming that, run the analysis audit again — the follow-up judges the "
        "finding —, then adopt the run that answers (`--from-run`); no new "
        "measurement",
    ),
    (
        "none of these",
        f"stop and {HANDOVER} — decide each readable open BLOCKER first "
        "(deferred, with why it stays unresolved). Never hand-edit audit or "
        "run evidence; decisions use --decide, generated report blocks use "
        "protocol-fill; never --no-verify",
    ),
)
#: the unjudged-promise cause's way out where the protocol registers no
#: promise — a computation has no [[promise]] table, and `--decide` refuses
#: every id an effect names there (`audit._registered`); the routes left
#: are the ones that work: limit the claim, fix the fault, defer and hand over
NO_PROMISE_ROUTE = (
    "this protocol registers no promise, so no effect leaves one not "
    "assessable (`--decide` refuses every id): a fault you cannot fix limits "
    "the claim — accept it with `--effect stands`, the limit named in the "
    "Conclusion (a second auditor must uphold it) — or decide it `deferred` "
    "and hand over"
)


def blocker_routes(promised: bool) -> tuple[str, ...]:
    """The ways out of a BLOCKER by its cause (WAYS_OUT), as printed with a
    decision list and shown to the analysis auditor — for a protocol that
    registers promises (PROMISED) as WAYS_OUT states them, else with the
    unjudged-promise route as NO_PROMISE_ROUTE."""
    return (
        "  before deciding a BLOCKER, name which of these it is:",
        *(
            f"    {name}: "
            f"{NO_PROMISE_ROUTE if name == UNJUDGED_PROMISE and not promised else what}"
            for name, what in WAYS_OUT
        ),
    )


#: how long a finding's text stands in the decision list
