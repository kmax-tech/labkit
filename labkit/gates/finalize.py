"""finalize — the gate after a run, before a number is reported.

Sequences the checks that must pass before results are written back into
the protocol.

    finalize <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 clean, 1 findings (at least one blocker), 2 usage error.

What it runs, in order (the same numbers as `finalize_area`, which shows
each step's condition):
  0. protocol       the named PROTOCOL-*.md or the area's only one, and its
                    settings block — the only early end (exit 2)
  1. answering run  the run that answers — the adopted run once the head's
                    `[result] run` names one, else the newest completed bound
                    run reporting an intent key, the same choice as
                    intent-check — and every later step checks THAT run.
                    Then its record:
                    the head's `[result] run` names this one or none yet
                    (blocker / note with the command), its
                    JSONL rows come from this run, the runs it continues or
                    its derived_from lineage (blocker), each line of its
                    call log has a record naming its alias — its own, or
                    the storing run's for a stored answer — and a derived
                    run asked no model and read no answer stored outside
                    any run (blocker), else
                    a model record stands in its lineage where its metrics
                    show calls (warning), stand-in answers in its call log
                    (warning, `stand_in_findings`), the arm lines match
                    (warning),
                    it is a full run — `run_kind='measurement'`, not acknowledged unfrozen
                    (warning here, `runs.unreportable`; report-check blocks)
  2. registration   the answering run's promise block is the one the first
                    measurement registered — a blocker naming every change
                    (sentences, keys, constants, scopes) and the way back;
                    first measurements that recorded different blocks, a
                    blocker (`registration_changes`, LAB-003 No run without
                    an intent paragraph); a run without a record that
                    reads which may have been the first measurement, a
                    blocker in place of the comparison
                    (`registration_hold.lost_record_hold`), any other
                    such run a warning (`lost_record_warnings`); a
                    history git could not list, a blocker before all of
                    these (`registration_hold.unread_history_hold`) —
                    like them only with an answering run: without one
                    this station is skipped, and report-check's report
                    duty tells that history
  3. intent-check   every registered promise has a metrics key (and vice
                    versa), and prose and promise block name the same ids;
                    skipped only when neither registers an id
  4. run code and declared scopes  the script and the helpers it imports,
                    the run's and its lineage's, are the code here now
                    (blocker, `check_run_code`; a module in another
                    repository warns), and every declared promise scope is
                    unchanged since the run
  5. open fields    protocol fields still holding a placeholder — a
                    warning, a must field's too (preflight blocks that
                    before the freeze); a bound field written twice and
                    generated data counts typed by hand or stale block;
                    README placeholders and route block findings warn; with
                    a route block, a `scripts/01_measure.py` that does not
                    parse blocks
  6. provenance     at protocol `repeat_cost = "low"` only: the run froze its source
                    (`data=` in config.json), each source matches its recorded
                    checksum and is tracked or ignored by a rule (a directory
                    source: each visible file under it); untracked outputs warn
                    — the two of the three questions the
                    agent audit asks that a machine can answer (LAB-017 The number of audits follows the cost tier);
                    the third, the counted unit, is the protocol's `Unit` field
  7. input origins  on every repeat cost: each input whose record names an
                    origin run is that run's registered output, the bytes
                    both records hold — the first part that fails (origin
                    gone or unreadable, not completed, no such output, other
                    bytes registered, the file changed) is a blocker whose
                    way out restores evidence, never rewrites it
                    (`origin_check`); a plain input and the runs the lookup
                    skipped are notes. An origin run bound to a protocol
                    whose text as it started (commit and patch) cannot be
                    read back blocks; one bound to none owes none and is
                    a note. A bound origin is held to the promises of
                    that text, except a preparation, which reports no
                    result; its text is still read back. At low repeat cost
                    changed bytes are station 6's blocker, told here as a
                    note
  8. area tests     tests/test_<NN>_<name>.py via the repo's interpreter, on
                    every tier: a failing test is a blocker (evaluate() lost
                    its resolution check), a missing one no finding here
  9. registered outputs  every output the run registered is the file it
                    recorded — path and sha256 from outputs.json; gone or
                    other bytes is a blocker (`check_registered_outputs`)
     criterion n    every `criterion_<i>_n` key in metrics.json equals some input
                    count the run recorded (rows of a data= file, lines of
                    an output) — a warning, not a blocker, until the false
                    alarm rate is known
     null lane      an output the run kept with a registered and a null
                    lane: the null answers otherwise on some item, gold
                    included — a warning, static evidence
                    (`null_lane_findings`, LAB-034 Null condition in the
                    same run); without both lanes, a note
     kept number    the kept number, at every kind: the answering run's
                    metrics.json holds the key the head's `[kept]` names as a
                    finite number — a blocker naming the key, the run and
                    what it holds instead (`kept_number_gaps`); a `[kept]`
                    missing or unfilled blocks too (`kept_gaps`). The key,
                    not its meaning: a wrong computation under the right
                    key passes
     reference      a computation's comparison with the stated value its
                    head registers (`[reference]`): the run recorded the
                    verdict and it reads; `not comparable` — the key absent
                    from metrics.json or no finite number — is a blocker
                    naming the key and the way out (write the key, measure
                    anew), so no "met" can be reported; a `ref_*` key
                    without a registered reference, and a reference changed
                    after the run, block too (`reference.comparison_gaps`);
                    `not met` is a valid outcome, a note
 10. audit findings every finding still `open` in an audit record of this
                    protocol (any mode), with its file: a BLOCKER is a
                    blocker, a WARNING a warning — a finding nobody decided
                    is an ignored finding (LAB-015 Preflight audit before
                    freezing); a finding on another protocol of the area
                    holds nothing here. And every
                    analysis record names a run the area still holds: a
                    deleted run directory behind a record is a blocker

Three grades, decided where each finding is made and summed at the end:
`Findings.block` (exit 1), `Findings.warn` (counted, exit 0), a plain
print (a note, uncounted). "0 blockers, N warnings" sums the warnings of
every station, not the open fields alone.

What it does NOT do: fill fields, edit the protocol, or commit. It is a
read-only gate that reports findings.
"""

from __future__ import annotations

from functools import partial
from dataclasses import replace
from pathlib import Path

from labkit.formats import evidence
from labkit.formats.area_state import AreaState, state_of
from labkit.formats.repo import area_args
from labkit.formats.answer_reading import read_answer_reading
from labkit.formats.protocol_then import as_measured
from labkit.formats.commands import gate_command, measure_anew
from labkit.formats.gate import (
    GUARANTEED,
    NOTE,
    NOT_EXECUTABLE,
    OPEN_RULE,
    STATIC_EVIDENCE,
    TECHNICAL_RULE,
    WARNING,
    GateFinding,
    RuleAssignment,
    blocker,
    cited_rule,
    outcome_of_failed_read,
    with_rule,
    withdrawn_first,
)
from labkit.formats.runs import (
    metrics_path,
    metrics_text,
    read_data,
    read_metrics,
    runs_path,
)
from labkit.formats import (
    console,
    findings as audit_findings,
    followup,
    promises,
    protocol_block,
    reference,
)
from labkit.formats.standard_contract import lane
from labkit.formats.gate import EXIT_CONTRACT, Findings
from labkit.formats.runs import (
    NO_MEASUREMENT,
    UNFROZEN_ACK,
    ArtefactError,
    MetricsError,
    kept_jsonl_rows,
    lineage,
    outputs_now,
    read_outputs,
    read_run_dir,
    unreportable,
    read_run_config,
)
from labkit.formats.repo import (
    git_root,
    layout_root,
    ProtocolChoiceError,
    the_protocol,
)
from labkit.formats.commands import (
    adopt_command,
    area_slots,
    contract_command,
    data_counts_command,
    fill_command,
    measure_command,
    withdraw_command,
)
from labkit.gates.registration_hold import standing_adoption
from labkit.gates.registration_station import check_registration
from labkit.gates.ways_out import PROTOCOL_NAMED
from labkit.formats.commands import register_anew
from labkit.checks.intent_check import NoRunChosen
from labkit.checks.intent_check import origin_intent_findings
from labkit.checks.intent_check import hold as intent_hold
from labkit.gates.preflight import area_tests, tell_test_run
from labkit.formats.protocol_fields import PROMPT_LABEL, field_name
from labkit.formats.protocol_check import (
    REPEATED_WAY_OUT,
    field_values,
    head_rule,
    kept_gaps,
    must_and_soft_holes,
    named_field,
    reference_gap,
    repeated_findings,
)
from labkit.checks import data_counts
from labkit.checks.origin_check import (
    BYTES_CHANGED,
    LOOKED_UP_WITHIN_AREA,
    origin_finding,
    origin_held,
    origin_state,
)
from labkit.checks.result_render import kept_phrase
from labkit.checks.run_record_check import (
    answer_reading_gaps,
    arm_findings,
    code_since_run,
    criterion_n_input_mismatches,
    criterion_ns,
    kept_number_gaps,
    null_lane_findings,
    model_provenance_findings,
    output_record_findings,
    provenance_findings,
    row_provenance_findings,
    single_draw,
)
from labkit.checks.audit_binding import (
    UNDECIDED,
    UNDECIDED_RULE,
    check_audit_findings_decided,
    check_audit_records_read,
    check_audited_runs_kept,
    source_protocol_finding,
    source_protocol_then,
)
from labkit.checks.readme_check import readme_placeholders, readme_route
from labkit.checks.code_scan import unreadable_source
from labkit.formats.files import ReadError
from labkit.formats.scope_sha import SourceError

CODE_003 = cited_rule("CODE-003 Test the functions that produce numbers")
CODE_016 = cited_rule("CODE-016 The experiment area reconstructs itself")
LAB_004 = cited_rule("LAB-004 Identifiers make the intent addressable")
LAB_011 = cited_rule("LAB-011 Required-field check")
LAB_041 = cited_rule("LAB-041 Generate numbers, don't retype them")
LAB_043 = cited_rule("LAB-043 Runs go through `runlog`")
LAB_104 = cited_rule("LAB-104 A number leaves the area only through its adoption")


def choose_answering_run(
    findings: Findings, protocol: Path, pid: str | None, text: str, state: AreaState
) -> Path | None:
    """The run every station holds PROTOCOL (its TEXT) to —
    `answering_run.bound_answering_run`, ONE choice for every station: the
    adopted run once `[result]` names one, else the newest bound run that
    reports an intent key (intent-check skips a probe, so checking scopes
    or provenance on the newest run would judge the probe while the numbers
    come from the measurement). A blocker here is the
    finding, and it carries the runs that were looked at and why none
    answers: a note beside it reaches no caller that collects the findings
    as data. A blocker beside a chosen run is told and the run returned:
    the later stations go on with it (`labkit-params` refuses such a
    choice instead). Bound runs newer by name than the
    adopted one are a static-evidence warning, never a blocker: a run id is
    local time without a zone, so the name orders the runs of one machine
    only — yet on one machine a newer run left out is what choosing among
    seeds looks like."""
    if pid is None:
        findings.block(
            "no stamped protocol id ([protocol] id) — no run is bound to it",
            fix="stamp the area with `labkit-init exp <name> --kind …`, which "
            "writes a fresh id, and carry the protocol's text over",
            rule=LAB_043,
        )
        return None
    choice, blocker, lines = state.measured_of(pid).told(text)
    if choice.run_dir is None:
        assert blocker is not None, "explain() names a blocker whenever no run stands"
        looked_at = "".join(f"; {line}" for line in lines)
        fix = (
            f"withdraw the adoption (`{withdraw_command(protocol)}`), audit the "
            f"run that answers, then `{adopt_command(protocol, '<run_id>')}` adopts it"
            if choice.adopted
            else blocker.fix
        )
        findings.take(
            replace(
                blocker,
                text=blocker.text + looked_at,
                fix=fix,
                step=withdraw_command(protocol) if choice.adopted else blocker.step,
            )
        )
        return None

    if blocker:
        findings.take(blocker)
    findings.note(
        f"  {choice.run_dir.name}: completed" + "".join(f" ({ln})" for ln in lines)
    )
    if choice.newer_by_name:
        findings.warn(
            f"{', '.join(choice.newer_by_name)}: bound to this protocol and newer "
            f"by name than the adopted run {choice.run_dir.name} — if one of them "
            f"answers, withdraw the adoption (`{withdraw_command(protocol)}`), "
            f"audit it and adopt it; a run left out of the report is named in it",
            evidence_kind=STATIC_EVIDENCE,
            rule=OPEN_RULE,
        )
    return choice.run_dir


def undeclared_note(text: str, protocol: Path) -> str | None:
    """A note while the protocol declares no result yet — the normal state
    before adoption, so no warning: it names `labkit-next AREA` and no step
    of its own. finalize is a station of `next`'s chain
    (`report_check.chain_gaps` → `finalize_findings`), so it cannot print
    `next`'s step without calling itself; the one explainer stays `next`.
    None once a run is declared."""
    if protocol_block.declared_run(text) is not None:
        return None
    return (
        "no result adopted yet ([result]): "
        f"`{gate_command('labkit-next', protocol.parent)}` names the step"
    )


def _hold_declaration(
    findings: Findings, protocol: Path, text: str, run: Path | None
) -> None:
    """The head's `[result]`: a table that does not read blocks
    (`declared_run_gaps`); none yet is a note naming `labkit-next`
    (`undeclared_note`). An adopted run is the run the checks hold
    (`answering_run.bound_answering_run`), so it cannot name another."""
    gaps = declared_run_gaps(text, protocol)
    findings.take_all(gaps)
    if run is None or gaps:
        return
    note = undeclared_note(text, protocol)
    if note:
        # the normal state before adoption: a note, finalize stays clear
        findings.note(f"  {note}")


def check_answering_run(
    findings: Findings,
    area: Path,
    protocol: Path,
    text: str,
    pid: str | None,
    state: AreaState,
) -> Path | None:
    """Station 1: the run every later station holds the protocol to — chosen
    from STATE (the area's state, `area_state.Measured.answering`), shown,
    and held to the run the head declares (`[result] run`). Returns it, or
    None."""
    answering_run = choose_answering_run(findings, protocol, pid, text, state)
    _hold_declaration(findings, protocol, text, answering_run)
    if answering_run is not None:
        # findings from the call log first; the metrics-based warning only
        # when the call log gives none (`model_provenance_findings`)
        findings.take_all(model_provenance_findings(area, answering_run))
        for warning in (
            single_draw(area, answering_run),
            *unreportable_warnings(answering_run),
        ):
            if warning:
                findings.take(warning)
        blockers, notes = row_provenance_findings(answering_run)
        findings.take_all(blockers)
        for n in notes:
            findings.note(f"  {n}")
        findings.take_all(arm_findings(text, area, answering_run))
    return answering_run


#: the rule assignment of each cause that makes a run's number unreportable
#: (`runs.Unreportable.cause`): a run that is no measurement breaks LAB-104
#: A number leaves the area only through its adoption ("that run is a full
#: run"); for a run acknowledged over an unfrozen protocol no sentence
#: states it for every such run
UNREPORTABLE_RULES = {
    NO_MEASUREMENT: LAB_104,
    UNFROZEN_ACK: OPEN_RULE,
}


#: the names of the two findings of finalize whose cause report-check's
#: chain holds at a station of its own (`GateFinding.known_as`): the chain
#: leaves finalize's finding out by this name
#: (`report_check.without_unreportable_warnings`,
#: `report_check.without_declaration_blocker`)
UNREPORTABLE_NUMBER = "unreportable number"
UNREADABLE_RESULT_TABLE = "unreadable result table"


def unreportable_warnings(answering_run: Path) -> list[GateFinding]:
    """Why the answering run's number cannot be reported (`runs.unreportable`),
    each a warning here with the rule of its cause, known as
    UNREPORTABLE_NUMBER: finalize holds the run, report-check refuses the
    report."""
    cfg = read_run_config(answering_run)
    if cfg is None:
        return []
    return [
        GateFinding(
            WARNING,
            f"the answering run {answering_run.name}: {mark.why} — its number "
            f"cannot be reported (report-check refuses it)",
            rule=UNREPORTABLE_RULES[mark.cause],
            evidence_kind=GUARANTEED,
            known_as=UNREPORTABLE_NUMBER,
        )
        for mark in unreportable(cfg)
    ]


def check_open_audit_findings(
    findings: Findings,
    area: Path,
    state: AreaState,
    held: evidence.AreaEvidence,
    protocol: Path,
    protocol_id: str | None,
) -> None:
    """Station 10: every finding still `open` in the audit records of
    PROTOCOL (those that name PROTOCOL_ID, `followup.records_of`), any
    mode (`findings.open_findings`, with the table of the gates' rules) — a
    BLOCKER blocks, a WARNING warns, a NOTE is printed — each with
    its file; a finding on another protocol of the area holds nothing here,
    and a head without an id (PROTOCOL_ID None) has no record to hold it.
    And every analysis record of the area names a run the area still holds
    (`audit_binding.check_audited_runs_kept`): a run an audit read is a kept run,
    and its deleted directory is a blocker where the record stands. A
    record nobody can read is a blocker, not "no findings" — and while one
    does not read, neither the gone runs nor the open findings are checked.
    An undecided NOTE is no gate finding: it is told after the blockers and
    warnings, not in its record's order. STATE and HELD are the area's
    state and audit evidence, read once at the entry."""
    if held.unreadable:
        findings.take_all(check_audit_records_read(state, evidence=held))
        return
    # the runs: every record of the area; the findings: this protocol's
    gone = check_audited_runs_kept(state, evidence=held)
    undecided = check_audit_findings_decided(
        held,
        protocol_id=protocol_id,
        # the line names PROTOCOL only where the area holds several
        # (`commands.audit_command`)
        way_out_of=partial(audit_findings.decide_way, area, protocol=protocol),
    )
    findings.take_all([*gone, *undecided])
    own = followup.records_of(held.records, protocol_id)
    notes = 0
    for u in audit_findings.open_findings(own):
        if u.grade == NOTE:  # no gate finding: told, never counted
            notes += 1
            findings.note("  " + with_rule(f"{u.line} — {UNDECIDED}", UNDECIDED_RULE))
    if not gone and not undecided and not notes:
        findings.note(
            f"  every finding decided ({len(own)} audit record(s) on {protocol.name})"
            if own
            else f"  no audit record on {protocol.name} in audits/"
        )


def check_intent_keys_in_metrics(
    findings: Findings,
    protocol: Path,
    text: str,
    answering_run: Path | None,
    state: AreaState,
) -> None:
    """Station 3: every registered intent id reports as a key of the answering
    run's metrics.json, a branch as one of its registered outcomes
    (intent-check). Not code_check.check_intent_ids, which
    holds the promises to the code before any run."""
    if not promises.registers_promises(text):
        findings.note("  no intent ids registered — nothing to check")
        return
    try:
        held = intent_hold(
            protocol,
            metrics_path(answering_run) if answering_run is not None else None,
            state,
        )
    except NoRunChosen:
        # without an answering run intent-check makes the same run choice
        # (`bound_answering_run`, the same text) after reading the block:
        # station 1 holds it, one cause one blocker
        assert answering_run is None, "intent-check chose no run beside station 1's"
        findings.note(NO_RUN)
        return
    except console.Refused as exc:  # nothing to hold: a blocker, as its exit 2
        findings.block(
            f"intent-check: {exc.why}",
            fix=f"repair what the sentence names; "
            f"`{gate_command('intent-check', protocol)}` holds it alone",
            rule=TECHNICAL_RULE,
        )
        return
    # Its findings as data, each a blocker; its notes — which run, on what
    # proof — stay notes.
    for line in held.notes:
        findings.note(f"  {line}")
    for finding in held.findings:
        findings.take(replace(finding, text=f"intent-check: {finding.text}"))
    if not held.findings:
        findings.note(f"  {held.summary}")


def check_run_code(
    findings: Findings, area: Path, answering_run: Path, held_by: Path | None
) -> None:
    """Station 4, first half: the code that produced the answering run's
    number, and that of every run it derives from, is the code here now
    (`run_record_check.code_since_run`), for every kind — a fix after the
    run with no new run would leave the old code's number standing. A module in
    another repository is a warning. HELD_BY, the protocol that declares the
    answering run (None: none does), puts the withdrawal first in each
    blocker's way out (`gate.withdrawn_first`)."""
    changed, apart = code_since_run(area, answering_run)
    findings.take_all(
        withdrawn_first(changed, withdraw_command(held_by) if held_by else None)
    )
    for line in apart:
        findings.warn(line, evidence_kind=GUARANTEED, rule=TECHNICAL_RULE)
    if not changed and not apart:
        findings.note(
            f"  the script and the helpers it imports are as {answering_run.name} ran them"
        )


def check_answer_reading(
    findings: Findings, area: Path, protocol: Path, answering_run: Path
) -> None:
    """Station 4, third part: each run of the answering run's lineage that
    declares its answer reading (`answer_reading`) is held to its parent
    beyond the code (`run_record_check.answer_reading_gaps`): the prompts
    field of PROTOCOL as each run started under it, and the answer file
    both registered. A protocol text that cannot be read back blocks, as
    does an outputs.json that does not read. A note names the declaration
    and what of the parent's code was compared (`code_since_run`). Says
    nothing where no run declares one; a broken lineage and a declaration
    that does not read are `check_run_code`'s blockers."""
    try:
        chain = lineage(answering_run)
    except ValueError:
        return
    root = git_root(area)
    for child, parent in zip(chain, chain[1:]):
        try:
            declared = read_answer_reading(child)
        except ArtefactError:
            continue  # `check_run_code` blocks on it, and compares the parent whole
        if declared is None:
            continue
        findings.note(
            f"  {child.name} declares its answer reading {declared.module}: the "
            f"code of {parent.name} is compared in that module and the modules it "
            f"imports, not in its whole script"
        )
        # the prompts field as each run started under it: prose, read here
        prompts: list[str | None] = []
        for run in (parent, child):
            text, where = as_measured(protocol, read_run_dir(run), root, role="run")
            if text is None:
                findings.block(
                    f"the prompts {child.name} re-reads with cannot be held to "
                    f"{parent.name}'s: {where}",
                    fix=f"restore what the sentence names, or {measure_anew(area)}",
                    rule=TECHNICAL_RULE,
                )
                break
            prompts.append(
                field_values(text, normalise=str).get(field_name(PROMPT_LABEL))
            )
        try:
            outputs = (read_outputs(parent) or [], read_outputs(child) or [])
        except ArtefactError as exc:
            findings.take(run_file_unread(str(exc), exc, child))
            continue
        if len(prompts) == 2:
            findings.take_all(
                answer_reading_gaps(
                    parent.name,
                    child.name,
                    (prompts[0], prompts[1]),
                    outputs,
                    measure_anew(area),
                )
            )


def check_declared_scopes(
    findings: Findings,
    area: Path,
    answering_run: Path,
    text: str = "",
    held_by: Path | None = None,
) -> None:
    """Station 4, second half: a promise's declared scope edited after the run: today's code is not
    the code that produced the number. An answering run that recorded no block is a blocker
    (`promises.promise_tables_owed`: every reportable run is held to
    a registration that is data) — it came from a labkit that let it pass,
    or the block was added after the run."""
    cfg = read_run_config(answering_run)
    recorded = cfg.promises if cfg else None
    if recorded is None and text and not promises.registers_promises(text):
        findings.note(
            "  n/a — the protocol registers no promise id (a computation), nothing to hold"
        )
        return
    if recorded is None:
        owed = promises.promise_tables_owed(None, frozen=False, full_run=True)
        findings.block(
            f"{answering_run.name} recorded no promise block: {owed} — a run "
            f"records the block it was measured under, so this one cannot "
            f"answer; reproduce it with the labkit version its repo pins",
            fix=f"a block added after the run is a new registration: "
            f"{register_anew(per='per change, the promise block among them')}",
            rule=LAB_004,
        )
        return
    drift = promises.scope_drift(recorded, area)
    for d in drift:
        if d.unread is not None:
            # no digest now, so nothing is compared: the cause of that,
            # told with its rule and outcome — no change is shown, and a new
            # run would be refused over the same scope
            findings.block(
                f"declared scope cannot be compared with what "
                f"{answering_run.name} recorded: {d.told}",
                fix=f"{promises.scope_way_out(d.promise_id, d.unread)}, then "
                f"`{gate_command('finalize', area)}`",
                stated_outcome=d.unread.site_outcome,
                rule=d.unread.rule,
            )
            continue
        drifted = replace(
            blocker(
                f"declared scope changed since {answering_run.name}: {d.told}",
                fix=f"rerun before reporting: `{measure_command(area)}`, then audit that run",
                step=measure_command(area),
                rule=LAB_041,
            ),
            changed_since=answering_run.name,
        )
        findings.take(
            withdrawn_first([drifted], withdraw_command(held_by) if held_by else None)[
                0
            ]
        )
    if not drift:
        findings.note(
            f"  {len(recorded['ids'])} declared scope(s) unchanged since {answering_run.name}"
        )


def check_open_fields(
    findings: Findings,
    protocol: Path,
    text: str,
    head: protocol_block.Head,
    state: AreaState,
) -> None:
    """Station 5: fields of the protocol still empty or a placeholder — in
    a field owed as a must under LAB_011, in any other as an open
    assignment —, a bound field written twice (a blocker), the README's
    placeholders (CODE-016 The experiment area reconstructs itself) and
    route block, and the generated data counts (`check_data_counts`). The
    note "all fields filled, README and data counts clean" stands only when
    every one of these found nothing."""
    must_holes, soft_holes = must_and_soft_holes(text, head)
    holes = sorted(must_holes + soft_holes)
    for lineno, label in holes:
        findings.warn(
            f"{protocol.name}:{lineno}: {label}",
            evidence_kind=GUARANTEED,
            # LAB_011 names the required fields, no rule the others
            rule=LAB_011 if (lineno, label) in must_holes else OPEN_RULE,
        )
    repeated = repeated_findings(text)
    for twice in repeated:
        findings.block(
            f"{protocol.name}: {twice}",
            fix=f"{REPEATED_WAY_OUT}; then `{gate_command('finalize', protocol.parent)}`",
            rule=TECHNICAL_RULE,
        )
    try:
        stale = readme_placeholders(protocol.parent)
    except ReadError as exc:
        # one cause, one blocker: the route check would read the same file
        findings.block(
            str(exc),
            fix=f"repair README.md as UTF-8 text or remove it, then "
            f"`{gate_command('finalize', protocol.parent)}`",
            stated_outcome=outcome_of_failed_read(exc),
            rule=TECHNICAL_RULE,
        )
        readme_clean = False
    else:
        for line in stale:
            # a pattern over prose: an `<…>` the author meant is matched too
            findings.warn(
                f"{line} — a stamped placeholder, fill or delete the line",
                evidence_kind=STATIC_EVIDENCE,
                rule=CODE_016,
            )
        try:
            route = readme_route(protocol.parent, protocol.name)
        except SourceError as exc:
            findings.take(unreadable_source(exc))
            route_clean = False
        else:
            findings.take_all(route)
            route_clean = not route
        readme_clean = not stale and route_clean
    counted = check_data_counts(findings, protocol, text, state)
    if not holes and not repeated and readme_clean and counted:
        findings.note("  all fields filled, README and data counts clean")


def check_data_counts(
    findings: Findings, protocol: Path, text: str, state: AreaState
) -> bool:
    """Station 5, the generated counts of Data / scope: where the field
    holds them (`counts (prepare run <id>): …`), they are what that run
    recorded (`data_counts.counts_gap`) — a part typed by hand or left
    stale blocks, with the command that writes it again. True when they
    hold or there are none."""
    # one copy or none: a Data / scope written twice is refused at station 5
    hit = named_field(text, data_counts.FIELD)
    gap = data_counts.counts_gap(protocol.parent, hit.value if hit else "", state)
    if gap is None:
        return True
    findings.block(
        gap.why,
        fix=f"`{data_counts_command(protocol, gap.run_id)}` writes them from the run "
        "— never typed",
        rule=gap.rule,
    )
    return False


def check_provenance(findings: Findings, area: Path, answering_run: Path) -> None:
    """Station 6: every source the run read frozen in its record, its bytes
    the ones the record names, and tracked in git or kept outside it — by
    an ignore rule, or lying outside the repository; the outputs tracked,
    an untracked one a warning (`provenance_findings`)."""
    b, w, outside = provenance_findings(area, answering_run)
    findings.take_all(b)
    findings.take_all(w)
    for line in outside:
        findings.note(f"  {line}")
    if not b and not w:
        findings.note(
            "  source frozen in the run; source tracked in git"
            + (" or kept outside it" if outside else "")
            + "; output tracked in git; each source's bytes as the run recorded them"
        )


def check_input_origins(
    findings: Findings,
    area: Path,
    answering_run: Path,
    *,
    provenance_holds_bytes: bool,
) -> None:
    """Station 7: each input of the answering run whose record names an
    origin run is that run's registered output, its bytes as both records
    hold them (`origin_check.origin_gap`) — the first part that fails is a
    blocker naming the input, the origin and the condition, with the way
    out that restores evidence (`origin_finding`). A plain input and the
    runs the lookup skipped are notes (`origin_notes`). Then, for each
    origin run whose origin check holds, the protocol it was bound to as
    it saw it when it started (`audit_binding.source_protocol_then`): when
    the run was bound to a protocol and that text cannot be read back, a
    blocker (`source_protocol_finding`) — the audit of this run cannot be
    shown the text its source was bound to; a run bound to no protocol
    owes none and is a note (`check_source_protocols` holds a bound one to
    its text's promises, a preparation to none). PROVENANCE_HOLDS_BYTES:
    station 6 ran and holds every input's bytes, so changed bytes and a
    record that does not read are its blockers, told here as a note — one
    cause, one blocker."""
    try:
        entries = read_data(answering_run) or []
    except ArtefactError as exc:
        if provenance_holds_bytes:
            findings.note("  not read — the provenance station names the record")
            return
        findings.take(
            run_file_unread(
                f"the record of {answering_run.name} does not read: {exc}",
                exc,
                answering_run,
            )
        )
        return
    if not entries:
        findings.note("  n/a — the run recorded no input file")
        return
    findings.note(f"  {LOOKED_UP_WITHIN_AREA}")
    held: list[str] = []  # origin runs whose origin check holds, in the inputs' order
    for entry in entries:
        state = origin_state(area, entry)
        for line in state.notes:
            findings.note(f"  {line}")
        if state.now is None:
            continue  # a plain input: a note, never a finding
        if state.gap is None:
            findings.note(f"  {origin_held(entry)}")
            assert entry.origin_run is not None  # state.now is set
            held.append(entry.origin_run)  # only a held origin's protocol is read
        elif state.gap.part == BYTES_CHANGED and provenance_holds_bytes:
            findings.note(f"  {state.gap.told} — the provenance station names it")
        else:
            findings.take(origin_finding(state.gap, area))
    # an origin whose promise fails is named above, once; its protocol is
    # read back only where the run itself stands
    check_source_protocols(findings, area, held)


def check_source_protocols(findings: Findings, area: Path, held: list[str]) -> None:
    """Station 7, second part, only for the origin runs of HELD — those
    whose origin check holds; one that fails is named by its origin
    blocker and not read here. For each (repeats allowed), the protocol it was bound
    to as it started (`audit_binding.source_protocol_then`) — a blocker
    when the run was bound to one and that text cannot be read back
    (`source_protocol_finding`), a note when it reads or when the run was
    bound to none. A text that reads is the one the origin run is held to:
    it reports every promise that text registered, as intent-check holds
    an answering run (`intent_check.origin_intent_findings`) — a blocker
    each where its metrics and that text disagree; the protocol as it reads now is not asked.
    A preparation origin (`run_kind` "preparation",
    `SourceProtocolThen.preparation`) reports no result and is held to none
    of its text's promises, bound or not — a run without `protocol=` binds
    to the area's only protocol at its start
    (`start_check.protocol_binding`), and the standard states the exception
    (LAB-043 Runs go through `runlog`, "An input's origin run is recorded
    and held"); its text is still read back, and its bytes held in the
    first part."""
    root = git_root(area)
    for run_id in dict.fromkeys(held):
        then = source_protocol_then(area, run_id, root)
        finding = source_protocol_finding(then, area)
        if finding is not None:
            findings.take(finding)
        elif then.bound is False:
            findings.note(f"  {then.where}; none is owed")
        else:
            # no finding and bound: `source_protocol_finding` left only a text that reads
            assert then.text is not None
            findings.note(f"  its protocol then: {then.where}")
            if then.preparation:
                findings.note(
                    f"  {run_id} is a preparation: it reports no result, so it "
                    f"owes none of that text's promises"
                )
                continue
            origin_blockers = origin_intent_findings(
                runs_path(area) / run_id, then.text, area
            )
            findings.take_all(origin_blockers)
            if not origin_blockers:
                findings.note(f"  {run_id}, held to that text: no mismatch")


def check_area_tests(findings: Findings, area: Path) -> None:
    """Station 8: the area's own tests. The resolution check runs again before a number leaves: a later edit
    of evaluate() that mutes the criterion is caught here too — on every
    tier, low included, where preflight is not owed. A
    missing test is no finding here; preflight owes it at the freeze."""
    # the same place preflight looks: a stamped tree before `git init` has
    # tests/ under its layout root, where git_root finds none
    tests = area_tests(area, layout_root(area))
    if tests.state == "none":
        findings.note(f"  none ({tests.pattern})")
    else:
        tell_test_run(
            findings,
            tests,
            "the area's own checks of evaluate() (its resolution check, where "
            "it has a criterion) do not hold",
            CODE_003,
        )


def run_file_unread(text: str, exc: BaseException, answering_run: Path) -> GateFinding:
    """The blocker TEXT for a run file that did not read with EXC: a file
    that could not be opened leaves the check not executed — made readable,
    then finalized again; a file missing or malformed is a defect of the
    run — measured anew and audited, its own files staying as they are
    (`gate.outcome_of_failed_read`). The area is the run directory's
    grandparent (`<area>/runs/<id>`), as every finalize station takes it."""
    area = answering_run.parent.parent
    if outcome_of_failed_read(exc) == NOT_EXECUTABLE:
        return blocker(
            text,
            fix=f"make the run's files readable (path and permissions), then "
            f"`{gate_command('finalize', area)}`",
            stated_outcome=NOT_EXECUTABLE,
            rule=TECHNICAL_RULE,
        )
    return blocker(
        text,
        fix=f"measure anew (`{measure_command(area)}`) and audit that run; "
        f"the run's own files stay as they are",
        step=measure_command(area),
        rule=TECHNICAL_RULE,
    )


def check_null_lane(findings: Findings, answering_run: Path) -> None:
    """Station 9: the kept rows' null lane moved (`null_lane_findings`) —
    a gate over the run's own output, not the editable script's guard."""
    try:
        kept = kept_jsonl_rows(answering_run)
    except (ValueError, OSError) as exc:
        findings.take(
            run_file_unread(
                f"the outputs of {answering_run.name} do not read: {exc}",
                exc,
                answering_run,
            )
        )
        return
    held = null_lane_findings(kept, answering_run.parent.parent)
    findings.take_all(held.unmoved)
    if held.examined == 0:
        findings.note("  n/a — no kept output holds a registered and a null lane")
    elif not held.unmoved:
        findings.note(f"  the null lane moved in {held.examined} kept output(s)")


def check_registered_outputs(findings: Findings, answering_run: Path) -> None:
    """Station 9: every output the run registered is the file the run
    recorded (`output_record_findings`) — the number's rows and the
    deliverable of an external task, held by path and sha256 from
    outputs.json, on every lane."""
    try:
        registered = outputs_now(answering_run)
    except ArtefactError as exc:
        findings.take(
            run_file_unread(
                f"the outputs of {answering_run.name} do not read: {exc}",
                exc,
                answering_run,
            )
        )
        return
    drifted = output_record_findings(
        registered or [], answering_run.name, answering_run.parent.parent
    )
    findings.take_all(drifted)
    if registered is None:
        findings.note("  n/a — the run registered no output file (run.output)")
    elif not drifted:
        findings.note(
            f"  {len(registered)} registered output(s) as the run recorded them"
        )


def check_reference(
    findings: Findings,
    protocol: Path,
    text: str,
    head: protocol_block.Head,
    answering_run: Path,
) -> None:
    """Station 9: the comparison with the stated value the head registers
    (`[reference]`, a computation's), held to the answering run's
    metrics.json (`reference.comparison_gaps`, each a guaranteed blocker):
    a table that does not read, or one on a kind with a bar
    (`reference_gap`), blocks too; metrics that do not read block as the
    other stations' do. Once the kind is decided the kept-number station
    holds the same metrics and key: metrics that do not read, and a
    verdict not comparable for want of a finite kept number, are its
    blockers, told here as a note — one cause, one blocker. Without a
    table: a note, nothing owed — unless the run wrote `ref_*` keys. `not
    met` is a valid outcome, told as a note."""
    gap = reference_gap(text, head)
    if gap:
        findings.block(
            f"{protocol.name}: {gap}",
            fix=f"repair the head as the sentence says, then "
            f"`{gate_command('finalize', protocol.parent)}`",
            rule=TECHNICAL_RULE,
        )
        return
    if kept_gaps(text, head):
        # the kept-number station names the [kept] gap; a second blocker on
        # the same cause would read as a second fault
        findings.note("  not read — the kept-number station names the [kept] gap")
        return
    try:
        ref = protocol_block.reference(text)
        key = protocol_block.kept_key(text) if ref is not None else None
    except protocol_block.BlockError as exc:
        findings.block(
            f"{protocol.name}: {exc}",
            fix=f"repair the [reference] and [kept] tables as the sentence says; "
            f"`{gate_command('protocol-check', protocol)}` shows them",
            rule=TECHNICAL_RULE,
        )
        return
    # with the kind decided the kept-number station reads the same
    # metrics.json and holds the same key: a cause it names is not told a
    # second time
    kept_station_holds = head.kind is not None
    try:
        metrics = runs_metrics(answering_run)
    except MetricsError as exc:
        if kept_station_holds:
            findings.note("  not read — the kept-number station names the metrics")
            return
        findings.take(
            run_file_unread(
                f"the metrics of {answering_run.name} do not read: {exc}",
                exc,
                answering_run,
            )
        )
        return
    if (
        kept_station_holds
        and metrics.get(reference.STATE_KEY) == reference.NOT_COMPARABLE
    ):
        findings.note(
            "  not compared — the kept-number station names the kept key it lacks"
        )
        return
    held = reference.comparison_gaps(ref, key, metrics)
    findings.take_all(held)
    if held:
        return
    if ref is None or key is None:
        findings.note("  n/a — no [reference] registered")
    else:
        findings.note(
            f"  {reference.phrase(metrics, ref, key)} — as the run recorded it"
        )


def check_kept_number(
    findings: Findings,
    protocol: Path,
    text: str,
    head: protocol_block.Head,
    answering_run: Path,
) -> None:
    """Station 9: the kept number — the key the head's `[kept]` names, at
    every kind — held as a finite number in the answering run's
    metrics.json (`run_record_check.kept_number_gaps`, a guaranteed
    blocker): the check the agent cannot edit away, where the skeleton's
    own check sits in its script. A `[kept]` table missing, unfilled or
    malformed (`protocol_check.kept_gaps`) blocks too; an undecided kind is
    a note. The key binds the name, not the meaning: a wrong computation
    under the right key passes — the tests and the analysis audit judge
    that."""
    gaps = kept_gaps(text, head)
    for gap in gaps:
        # an unfilled value is the stamp's placeholder, which protocol-fill
        # sets; every other gap is a table to add, drop or repair by hand
        unfilled = gap.label in {f"[kept] {f}" for f in protocol_block.KEPT_KEYS}
        findings.block(
            f"{protocol.name}: {gap.label}"
            + (" is still the placeholder" if unfilled else ""),
            fix=(
                f"`{fill_command(protocol, f'kept.{gap.label.removeprefix("[kept] ")}=<value>')}`"
                if unfilled
                else f"repair the head as the sentence says, then "
                f"`{gate_command('finalize', protocol.parent)}`"
            ),
            rule=gap.rule,
        )
    if gaps:
        return
    if head.kind is None:
        findings.note("  n/a — the head's kind is undecided (open fields name it)")
        return
    key = protocol_block.kept_key(text)  # kept_gaps found the table filled
    try:
        metrics = runs_metrics(answering_run)
    except MetricsError as exc:
        findings.take(
            run_file_unread(
                f"the metrics of {answering_run.name} do not read: {exc}",
                exc,
                answering_run,
            )
        )
        return
    held = kept_number_gaps(
        key, metrics, answering_run.name, answering_run.parent.parent, head.kind
    )
    findings.take_all(held)
    if not held:
        kept = protocol_block.kept(text)
        assert kept is not None and kept.unit is not None, "kept_gaps found it filled"
        findings.note(f"  {kept_phrase(key, metrics[key], kept.unit)}")


def runs_metrics(answering_run: Path) -> dict:
    """ANSWERING_RUN's metrics.json (`runs.read_metrics`); raises MetricsError."""
    return read_metrics(metrics_path(answering_run))


def check_criterion_n(findings: Findings, answering_run: Path) -> None:
    """Station 9: a criterion's denominator that matches no recorded input
    count (`run_record_check.criterion_n_input_mismatches`). The run's
    inputs and outputs are read only when metrics.json holds a denominator;
    a record that does not read then blocks — at repeat cost high no other
    station reads the inputs (`runs.read_data`). No metrics.json: nothing
    to hold."""
    try:
        has_metrics = metrics_text(answering_run) is not None
        ns = criterion_ns(runs_metrics(answering_run)) if has_metrics else {}
        if ns:  # the counts a denominator is held to
            inputs = read_data(answering_run) or []
            outputs = read_outputs(answering_run) or []
        else:
            inputs, outputs = [], []
    except ArtefactError as exc:
        findings.take(
            run_file_unread(
                f"the record of {answering_run.name} does not read: {exc}",
                exc,
                answering_run,
            )
        )
        return
    w = criterion_n_input_mismatches(ns, inputs, outputs)
    findings.take_all(w)
    if not w:
        findings.note(
            "  every criterion_<i>_n equals a recorded input count (or there is none)"
        )


def report(findings: Findings) -> int:
    """The summary and the exit code (`gate.Findings.report`)."""
    return findings.report("finalize", "reporting")


NO_RUN = "  no completed run to check"


def _inputs(
    area: Path, state: AreaState | None, held: evidence.AreaEvidence | None
) -> tuple[AreaState, evidence.AreaEvidence]:
    """The area's state and audit evidence for finalize's stations: the
    caller's when it built them for its check run (report-check), else
    built here once — finalize on the console is its own entry."""
    return (
        state if state is not None else state_of(area),
        held if held is not None else evidence.read_evidence(area, staged=False),
    )


def _refuse(
    findings: Findings,
    console_output: bool,
    why: str,
    fix: str,
    rule: RuleAssignment,
) -> None:
    """Step 0's early end told: on the console (CONSOLE_OUTPUT) a refusal
    with WHY; in a passed collector a blocker with its way out FIX and
    RULE, so the caller (report-check) can name it."""
    if console_output:
        console.refuse("finalize", why)
    else:
        findings.block(why, fix=fix, rule=rule)


def finalize_area(
    area: Path,
    protocol: Path | None = None,
    findings: Findings | None = None,
    *,
    state: AreaState | None = None,
    held: evidence.AreaEvidence | None = None,
) -> int:
    """Run finalize on an area. Returns 0 (clean or warnings only),
    1 (a blocker) or 2 (no protocol to hold the area to). FINDINGS, when
    given, collects what the stations found and is the channel every line
    goes through (`gate.Findings`): a gate that runs finalize as one of its
    stations (report-check) hands over a silent one (`Findings(tell=None)`)
    and names the blockers instead of "run it to see them". STATE, the
    area's state (`area_state.state_of`), and HELD, its audit evidence
    (`evidence.read_evidence`), are the caller's when it built them for its
    check run, else built here once.

    The flow — every condition that decides whether a step runs is in this
    function; one level down is how a step works, not whether it runs. A
    run is one execution of the experiment's script, a folder
    under `runs/` bound to this protocol — not this function, and not the
    protocol itself.

    0. Choose the protocol and read its settings block. Ends at once with 2
       when the named file is missing, the folder holds several protocols
       and none is named, or the settings block cannot be read. On the
       console the reason is a refusal; in a passed collector it is kept as
       a blocker, so the caller (report-check) can name it.
    1. answering run — choose the run the later steps examine
       (`answering_run`); none bound is a blocker, and steps 2, 4, 6, 7
       and 9 then skip.
    2. registration — only with a run: the type the first measurement
       registered decides the workflow (`registration_station`); a
       confirmatory or undecided one holds the promise block as the first
       measurement registered it (`registration_changes`), an exploratory
       one each step of the answering run against its basis and, once the
       protocol adopts that run, the protocol as it stands against the
       run's own text (`exploration_hold`); a blocker names every change.
    3. intent-check — always; with an answering run it reads its metrics,
       without one it holds the promise block alone (step 1 names the run).
    4. the run's code and the declared scopes — only with a run: the code
       that produced the number is the code here now (`check_run_code`),
       each declared scope as the run saw it (`check_declared_scopes`), and
       a derived run that declares its answer reading holds its parent's
       prompts and answer file (`check_answer_reading`).
    5. open fields — always: protocol placeholders and stamped `<…>`
       placeholders left in the area's README warn; a bound field written
       twice and data counts typed by hand or stale block.
    6. provenance — only for repeat_cost = low, and only with a run.
    7. input origins — on every repeat cost, only with a run: an input
       that is no longer the recorded output of its origin run blocks, and
       so does an origin run bound to a protocol whose text as it started
       cannot be read back; at repeat_cost = low changed bytes are step 6's
       blocker and a note here.
    8. area tests — always.
    9. registered outputs, criterion n, the null lane, the kept number and
       the reference comparison — only with a run; an output that is not
       the file the run recorded (gone, or another sha256 than outputs.json)
       blocks, criterion n warns, a null lane that did not move warns, a
       computation's run without its `[kept] key` as a finite number blocks, a
       registered reference the run cannot compare (the key absent or no
       finite number) blocks — a missed one is a result.
    10. audit findings — always: an `open` BLOCKER in a record of this
       protocol blocks; one on another protocol of the area does not.

    A blocker never stops a step: all of them run, then the summary lists
    every blocker again. Warnings alone end with 0.
    """
    console_output = findings is None
    # alone, finalize fills the slots its ways out leave (`<area>`); a caller
    # that hands FINDINGS over fills them as it takes them (report-check)
    if findings is None:
        findings = Findings(**area_slots(area, protocol))
    # 0. protocol and settings — the only early end
    try:
        chosen = the_protocol(area, protocol)
    except ProtocolChoiceError as exc:
        _refuse(findings, console_output, str(exc), PROTOCOL_NAMED, TECHNICAL_RULE)
        return 2
    state, held = _inputs(area, state, held)
    text = state.text_of(chosen)
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        _refuse(
            findings,
            console_output,
            f"{chosen.name}: {exc}",
            f"repair the head as the sentence says: "
            f"`{contract_command(chosen)}` shows its fields",
            head_rule(exc),
        )
        return 2

    # 1. answering run — the run every later step examines
    findings.header(f"answering run: {chosen.name}")
    answering_run = check_answering_run(findings, area, chosen, text, head.id, state)

    # 2. the registration as the first measurement recorded it — with a run
    findings.header("registration since the first measurement")
    if answering_run is None:
        findings.note(NO_RUN)
    else:
        check_registration(findings, area, chosen, head.id, answering_run, state, held)

    # 3. intent-check — always
    findings.header("intent-check")
    check_intent_keys_in_metrics(findings, chosen, text, answering_run, state)

    # 4. the run's code and the declared scopes — only with a run
    findings.header("the run's code and declared scopes")
    if answering_run is None:
        findings.note(NO_RUN)
    else:
        # the protocol that declares this very run: its holds withdraw first
        held_by = standing_adoption(chosen, text, answering_run, state)
        check_run_code(findings, area, answering_run, held_by)
        check_declared_scopes(findings, area, answering_run, text, held_by)
        check_answer_reading(findings, area, chosen, answering_run)

    # 5. open fields — always
    findings.header(f"open fields: {chosen.name}")
    check_open_fields(findings, chosen, text, head, state)

    # 6. provenance — at low repeat cost, and only with a run
    findings.header("provenance")
    if not lane(head.repeat_cost).provenance:
        findings.note(
            f"  n/a — protocol repeat cost is {head.repeat_cost!r} (the agent audit covers provenance there)"
        )
    elif answering_run is None:
        findings.note(NO_RUN)
    else:
        check_provenance(findings, area, answering_run)

    # 7. input origins — on every repeat cost, only with a run
    findings.header("input origins")
    if answering_run is None:
        findings.note(NO_RUN)
    else:
        # an input that is no longer its origin's recorded output blocks;
        # at repeat_cost = low station 6 holds every input's bytes and the
        # `data=` record, so changed bytes and an unreadable record are
        # notes here (`check_input_origins`)
        check_input_origins(
            findings,
            area,
            answering_run,
            provenance_holds_bytes=lane(head.repeat_cost).provenance,
        )

    # 8. area tests — always
    findings.header("area tests")
    check_area_tests(findings, area)

    # 9. registered outputs, criterion n, the null lane and the reference
    #    comparison — only with a run
    findings.header("registered outputs")
    if answering_run is None:
        findings.note(NO_RUN)
    else:
        check_registered_outputs(findings, answering_run)
        findings.header("criterion n")
        check_criterion_n(findings, answering_run)
        findings.header("null lane")
        check_null_lane(findings, answering_run)
        findings.header("kept number")
        check_kept_number(findings, chosen, text, head, answering_run)
        findings.header("reference comparison")
        check_reference(findings, chosen, text, head, answering_run)

    # 10. audit findings — always; a head without an id has no record
    findings.header("audit findings")
    check_open_audit_findings(findings, area, state, held, chosen, head.id)

    return report(findings)  # 1 if any step found a blocker, else 0


def declared_run_gaps(text: str, protocol: Path) -> list[GateFinding]:
    """A blocker when the head's `[result]` table does not read (a typed
    id, a stray key: `protocol_block.declared_run`'s sentence). An adopted
    run that is no completed run of the protocol — no `runs/<id>/` among
    them — is the run choice's blocker (`choose_answering_run`). Empty
    without a declaration or with one that reads. The blocker is known as
    UNREADABLE_RESULT_TABLE."""
    written = (
        f"`{withdraw_command(protocol)}` removes it; audit the run that answers, "
        f"then `{adopt_command(protocol, '<run_id>')}` writes the table for it"
    )
    try:
        protocol_block.declared_run(text)
    except protocol_block.BlockError as exc:
        return [
            blocker(
                str(exc),
                fix=written,
                step=withdraw_command(protocol),
                rule=TECHNICAL_RULE,
                known_as=UNREADABLE_RESULT_TABLE,
            )
        ]
    return []


def main(argv: list[str]) -> int:
    """Command line of `finalize`: check one area."""
    got = area_args(
        "finalize",
        argv,
        [
            (__doc__ or "").strip().splitlines()[0],
            "usage: finalize <AREA> [--protocol PROTOCOL-*.md]",
            "       (the gate at the stop and the commit is `report-check --if-reported`, "
            "which runs finalize as one station)",
            EXIT_CONTRACT,
        ],
    )
    if isinstance(got, int):  # --help, or a refusal told
        return got
    return finalize_area(got.area, got.protocol)


def cli() -> None:
    """Console entry point of `finalize`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
