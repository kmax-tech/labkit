"""finalize — the gate after a run, before a number is reported.

Sequences the checks that must pass before results are written back into
the protocol.

    finalize <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 clean, 1 findings (at least one blocker), 2 usage error.

What it runs, in order (the same numbers as `finalize_area`, which shows
each step's condition):
  0. protocol       the named PROTOCOL-*.md or the area's only one, and its
                    settings block — the only early end (exit 2)
  1. answering run  the run that answers — the newest completed bound run
                    reporting an intent key, the same choice as intent-check
                    — and every later step checks THAT run. Then its record:
                    the head's `[result] run` names this one or none yet
                    (blocker / note with the command), its
                    JSONL rows come from this run, the runs it continues or
                    its derived_from lineage (blocker), a model record stands
                    in its lineage (warning), the arm lines match (warning),
                    it is a full run — `run_kind='measurement'`, not acknowledged unfrozen
                    (warning here, `runs.unreportable`; report-check blocks)
  1b. registration  the answering run's promise block is the one the first
                    measurement registered — a blocker naming every change
                    (sentences, keys, constants, scopes) and the way back;
                    first measurements that recorded different blocks, a
                    blocker (`registration_changes`, LAB-003 No run without
                    an intent paragraph)
  2. intent-check   every registered promise has a metrics key (and vice
                    versa), and prose and promise block name the same ids;
                    skipped only when neither registers an id
  3. declared scopes  every declared promise scope unchanged since the run
  4. open fields    protocol fields still holding a placeholder
  5. provenance     at protocol `repeat_cost = "low"` only: the run froze its source
                    (`data=` in config.json), each source matches its recorded
                    checksum and is tracked or ignored by a rule (a directory
                    source: each visible file under it); untracked outputs warn
                    — the two of the three questions the
                    agent audit asks that a machine can answer (LAB-017 The number of audits follows the cost tier);
                    the third, the counted unit, is the protocol's `Unit` field
  6. area tests     tests/test_<NN>_<name>.py via the repo's interpreter, on
                    every tier: a failing test is a blocker (evaluate() lost
                    its resolution check), a missing one no finding here
  7. criterion n    every `criterion_<i>_n` key in metrics.json equals some input
                    count the run recorded (rows of a data= file, lines of
                    an output) — a warning, not a blocker, until the false
                    alarm rate is known
     null lane      an output the run kept with a registered and a null
                    lane: the null answers otherwise on some item, gold
                    included — a blocker (`null_lane_findings`, LAB-034
                    Null condition in the same run); without both lanes, a
                    note
     kept number    a computation's kept number: the answering run's
                    metrics.json holds the key the head's `[kept]` names as a
                    finite number — a blocker naming the key, the run and
                    what it holds instead (`kept_number_gaps`); a `[kept]`
                    missing, unfilled or on a fit or an apply blocks too
                    (`kept_gaps`). The key, not its meaning: a wrong
                    computation under the right key passes
     reference      a computation's comparison with the stated value its
                    head registers (`[reference]`): the run recorded the
                    verdict and it reads; `not comparable` — the key absent
                    from metrics.json or no finite number — is a blocker
                    naming the key and the way out (write the key, measure
                    anew), so no "met" can be reported; a `ref_*` key
                    without a registered reference, and a reference changed
                    after the run, block too (`reference.comparison_gaps`);
                    `not met` is a valid outcome, a note
  8. audit findings every finding still `open` in `audits/` (any mode), with
                    its file: a BLOCKER is a blocker, a WARNING a warning — a
                    finding nobody decided is an ignored finding
                    (LAB-015 Preflight audit before freezing). And every
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

import shlex
from dataclasses import replace
from pathlib import Path

from labkit.formats import evidence
from labkit.formats.area_state import AreaState, gone_run_restore, state_of
from labkit.formats.repo import area_args
from labkit.formats.commands import gate_command
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    GateFinding,
    STATIC_EVIDENCE,
    WARNING,
    blocker,
    withdrawn_first,
)
from labkit.formats.runs import metrics_path, read_metrics
from labkit.formats import (
    audit_gaps,
    console,
    findings as audit_findings,
    promises,
    protocol_block,
    reference,
)
from labkit.formats.standard_contract import COMPUTE_KIND, lane
from labkit.formats.gate import EXIT_CONTRACT, Findings
from labkit.formats.runs import (
    ArtefactError,
    MetricsError,
    read_outputs,
    unreportable,
    read_run_config,
)
from labkit.formats.repo import (
    layout_root,
    ProtocolChoiceError,
    shown,
    the_protocol,
)
from labkit.formats.commands import (
    Command,
    adopt_command,
    fill_command,
    handover_command,
    measure_command,
    withdraw_command,
)
from labkit.gates.registration_hold import (
    check_registration,
    declaring_protocol,
)
from labkit.gates.ways_out import PROTOCOL_NAMED
from labkit.formats.commands import register_anew
from labkit.checks.intent_check import NoRunChosen
from labkit.checks.intent_check import hold as intent_hold
from labkit.gates.preflight import area_tests, tell_test_run
from labkit.formats.protocol_check import (
    REPEATED_WAY_OUT,
    kept_gaps,
    named_field,
    open_holes,
    reference_gap,
    repeated_findings,
)
from labkit.checks import data_counts
from labkit.checks.result_render import kept_phrase
from labkit.checks.run_record_check import (
    arm_findings,
    code_since_run,
    criterion_n_input_mismatches,
    kept_number_gaps,
    null_lane_findings,
    model_provenance_gap,
    output_record_findings,
    provenance_findings,
    row_provenance_findings,
    single_draw,
)
from labkit.checks.readme_check import readme_placeholders, readme_route
from labkit.checks.code_scan import unreadable_source
from labkit.formats.scope_sha import SourceError


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
    as data. Bound runs newer by name than the
    adopted one are a static-evidence warning, never a blocker: a run id is
    local time without a zone, so the name orders the runs of one machine
    only — yet on one machine a newer run left out is what choosing among
    seeds looks like."""
    if pid is None:
        findings.block(
            "no stamped protocol id ([protocol] id) — no run is bound to it",
            fix="stamp the area with `labkit-init exp <name> --kind …`, which "
            "writes a fresh id, and carry the protocol's text over",
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
        for warning in (
            model_provenance_gap(answering_run),
            single_draw(area, answering_run),
            *unreportable_warnings(answering_run),
        ):
            if warning:
                findings.warn(warning, evidence_kind=GUARANTEED)
        blockers, notes = row_provenance_findings(answering_run)
        findings.take_all(blockers)
        for n in notes:
            findings.note(f"  {n}")
        for w in arm_findings(text, area, answering_run):
            findings.warn(w, evidence_kind=GUARANTEED)
    return answering_run


def unreportable_warnings(answering_run: Path) -> list[str]:
    """Why the answering run's number cannot be reported (`runs.unreportable`),
    each a warning here: finalize holds the run, report-check refuses the report."""
    cfg = read_run_config(answering_run)
    if cfg is None:
        return []
    return [
        f"the answering run {answering_run.name}: {mark} — its number cannot "
        f"be reported (report-check refuses it)"
        for mark in unreportable(cfg)
    ]


def gone_run_way(area: Path, run_id: str, state: AreaState) -> tuple[str, Command]:
    """The way out of an audit record whose run RUN_ID is gone from AREA,
    and the handover it names as the finding's step: put it back where
    git holds it (STATE's `deleted`: the commit that held it last,
    `area_state.gone_run_restore`), else hand the area over naming the
    loss, or register anew. Measuring again lifts nothing — the record
    stays and names the gone run —, so the way out never offers it."""
    protocols = state.protocols
    protocol = protocols[0] if len(protocols) == 1 else area / "PROTOCOL-<name>.md"
    handover = handover_command(protocol)
    held_back = next((rd for rd in state.deleted if rd.dir.name == run_id), None)
    put_back = (
        f"put it back where git holds it ({gone_run_restore(held_back)}); else"
        if held_back is not None
        else "no commit holds it:"
    )
    return (
        f"{put_back} it is lost, and a new run "
        f"does not lift this — hand the area over naming the loss "
        f"(`{handover}`), or {register_anew()}"
    ), handover


def check_open_audit_findings(
    findings: Findings, area: Path, state: AreaState, held: evidence.AreaEvidence
) -> None:
    """Station 8: every finding still `open` in the area's audit records, any
    mode (`findings.open_findings`, with the table of the gates' rules) — a
    BLOCKER blocks, a WARNING warns, a NOTE is printed — each with
    its file; and every analysis record names a run the area still holds
    (`audit_gaps.records_of_gone_runs`): a run an audit read is a kept run,
    and its deleted directory is a blocker where the record stands. A
    record nobody can read is a blocker, not "no findings". STATE and HELD
    are the area's state and audit evidence, read once at the entry."""
    if held.unreadable:
        for why in held.unreadable:
            findings.block(why, fix=audit_findings.record_way(area))
        return
    records = list(held.records)
    known = {rd.dir.name for rd in state.runs}
    gone = audit_gaps.records_of_gone_runs(records, known)
    for rec in gone:
        assert rec.run_id is not None  # records_of_gone_runs keeps only named runs
        way, handover = gone_run_way(area, rec.run_id, state)
        findings.block(
            f"{rec.path.name}: names {rec.run_id} as the run it read, and there is "
            f"no runs/{rec.run_id}/ in this area — a run an audit read is a kept run, "
            f"and nothing restores its rows (LAB-043 Runs go through `runlog`)",
            fix=way,
            step=handover,
        )
    seen = len(gone)
    for u in audit_findings.open_findings(records):
        seen += 1
        line = f"{u.line} — undecided (LAB-015 Preflight audit before freezing)"
        if u.grade == BLOCKER:
            findings.block(line, fix=audit_findings.decide_way(area, u))
        elif u.grade == WARNING:
            findings.warn(line, evidence_kind=GUARANTEED)
        else:
            findings.note(f"  {line}")
    if not seen:
        findings.note(
            f"  every finding decided ({len(records)} record(s))"
            if records
            else "  no audit record in audits/"
        )


def check_intent_keys_in_metrics(
    findings: Findings,
    protocol: Path,
    text: str,
    answering_run: Path | None,
    state: AreaState,
) -> None:
    """Station 2: every registered intent id reports as a key of the answering
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
            fix=f"repair what the sentence names; `intent-check "
            f"{shlex.quote(shown(protocol, Path.cwd()))}` holds it alone",
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
    """Station 3, first half: the code that produced the answering run's
    number, and that of every run it derives from, is the code here now
    (`run_record_check.code_since_run`), for every kind — a fix after the
    run with no new run would leave the old code's number standing. A module in another repository is a warning. HELD_BY,
    the protocol that declares the answering run (None: none does), puts
    the withdrawal first in each blocker's way out (`gate.withdrawn_first`)."""
    changed, apart = code_since_run(area, answering_run)
    findings.take_all(
        withdrawn_first(changed, withdraw_command(held_by) if held_by else None)
    )
    for line in apart:
        findings.warn(line, evidence_kind=GUARANTEED)
    if not changed and not apart:
        findings.note(
            f"  the script and the helpers it imports are as {answering_run.name} ran them"
        )


def check_declared_scopes(
    findings: Findings,
    area: Path,
    answering_run: Path,
    text: str = "",
    held_by: Path | None = None,
) -> None:
    """Station 3, second half: a promise's declared scope edited after the run: today's code is not
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
        )
        return
    drift = promises.scope_drift(recorded, area)
    for d in drift:
        drifted = replace(
            blocker(
                f"declared scope changed since {answering_run.name}: {d}",
                fix=f"rerun before reporting: `{measure_command(area)}`, then audit that run",
                step=measure_command(area),
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
    """Station 4: fields of the protocol still empty or a placeholder, and
    the README's route block (CODE-016)."""
    holes = open_holes(text, head)
    for lineno, label in holes:
        findings.warn(f"{protocol.name}:{lineno}: {label}", evidence_kind=GUARANTEED)
    repeated = repeated_findings(text)
    for twice in repeated:
        findings.block(
            f"{protocol.name}: {twice}",
            fix=f"{REPEATED_WAY_OUT}; then `finalize {shown(protocol.parent, Path.cwd())}`",
        )
    stale = readme_placeholders(protocol.parent)
    for line in stale:
        # a pattern over prose: an `<…>` the author meant is matched too
        findings.warn(
            f"{line} — a stamped placeholder, fill or delete the line",
            evidence_kind=STATIC_EVIDENCE,
        )
    try:
        route = readme_route(protocol.parent, protocol.name)
    except SourceError as exc:
        findings.take(unreadable_source(exc))
        route = [str(exc)]
    else:
        for line in route:
            findings.warn(line, evidence_kind=GUARANTEED)
    counted = check_data_counts(findings, protocol, text, state)
    if not holes and not repeated and not stale and not route and counted:
        findings.note("  all fields filled")


def check_data_counts(
    findings: Findings, protocol: Path, text: str, state: AreaState
) -> bool:
    """Station 4, the generated counts of Data / scope: where the field
    holds them (`counts (prepare run <id>): …`), they are what that run
    recorded (`data_counts.counts_gap`) — a part typed by hand or left
    stale blocks, with the command that writes it again. True when they
    hold or there are none."""
    # one copy or none: a Data / scope written twice is refused at station 4
    hit = named_field(text, data_counts.FIELD)
    gap = data_counts.counts_gap(protocol.parent, hit.value if hit else "", state)
    if gap is None:
        return True
    why, run_id = gap
    findings.block(
        why,
        fix=f"`protocol-fill {shown(protocol, Path.cwd())} --data-counts {run_id}` "
        f"writes them from the run — never typed",
    )
    return False


def check_provenance(findings: Findings, area: Path, answering_run: Path) -> None:
    """Station 5: every source the run read frozen in its record, its bytes
    the ones the record names, and tracked in git or kept outside it — by
    an ignore rule, or lying outside the repository; the outputs tracked,
    an untracked one a warning (`provenance_findings`)."""
    b, w, outside = provenance_findings(area, answering_run)
    findings.take_all(b)
    for line in w:
        findings.warn(line, evidence_kind=GUARANTEED)
    for line in outside:
        findings.note(f"  {line}")
    if not b and not w:
        findings.note(
            "  source frozen in the run; source tracked in git"
            + (" or kept outside it" if outside else "")
            + "; output tracked in git; each source's bytes as the run recorded them"
        )


def check_area_tests(findings: Findings, area: Path) -> None:
    """Station 6: the area's own tests. The resolution check runs again before a number leaves: a later edit
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
            "it has a criterion) no longer hold",
        )


def check_null_lane(findings: Findings, answering_run: Path) -> None:
    """Station 7b: the kept rows' null lane moved (`null_lane_findings`) —
    a gate over the run's own output, not the editable script's guard."""
    try:
        held = null_lane_findings(answering_run)
    except (ValueError, OSError) as exc:
        findings.block(
            f"the outputs of {answering_run.name} do not read: {exc}",
            fix=f"measure anew (`{measure_command(answering_run.parent.parent)}`) "
            f"and audit that run; the run's own files stay as they are",
            step=measure_command(answering_run.parent.parent),
        )
        return
    findings.take_all(held.unmoved)
    if held.examined == 0:
        findings.note("  n/a — no kept output holds a registered and a null lane")
    elif not held.unmoved:
        findings.note(f"  the null lane moved in {held.examined} kept output(s)")


def check_registered_outputs(findings: Findings, answering_run: Path) -> None:
    """Station 7: every output the run registered is the file the run
    recorded (`output_record_findings`) — the number's rows and the
    deliverable of an external task, held by path and sha256 from
    outputs.json, on every lane."""
    try:
        drifted = output_record_findings(answering_run)
    except ArtefactError as exc:
        findings.block(
            f"the outputs of {answering_run.name} do not read: {exc}",
            fix=f"measure anew (`{measure_command(answering_run.parent.parent)}`) "
            f"and audit that run; the run's own files stay as they are",
            step=measure_command(answering_run.parent.parent),
        )
        return
    findings.take_all(drifted)
    registered = read_outputs(answering_run)
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
    """Station 7: the comparison with the stated value the head registers
    (`[reference]`, a computation's), held to the answering run's
    metrics.json (`reference.comparison_gaps`, each a guaranteed blocker):
    a table that does not read, or one on a kind with a bar
    (`reference_gap`), blocks too; metrics that do not read block as the
    other stations' do. Without a table: a note, nothing owed — unless the
    run wrote `ref_*` keys. `not met` is a valid outcome, told as a note."""
    gap = reference_gap(text, head)
    if gap:
        findings.block(
            f"{protocol.name}: {gap}",
            fix=f"repair the head as the sentence says, then "
            f"`{gate_command('finalize', protocol.parent)}`",
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
        )
        return
    try:
        metrics = runs_metrics(answering_run)
    except MetricsError as exc:
        findings.block(
            f"the metrics of {answering_run.name} do not read: {exc}",
            fix=f"measure anew (`{measure_command(answering_run.parent.parent)}`) "
            f"and audit that run; the run's own files stay as they are",
            step=measure_command(answering_run.parent.parent),
        )
        return
    held = reference.comparison_gaps(ref, key, metrics)
    findings.take_all(held)
    if held:
        return
    if ref is None or key is None:
        findings.note("  n/a — no [reference] registered: a pure computation")
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
    """Station 7: a computation's kept number — the key the head's `[kept]`
    names — held as a finite number in the answering run's metrics.json
    (`run_record_check.kept_number_gaps`, a guaranteed blocker): the check
    the agent cannot edit away, where the skeleton's own `kept_number()`
    sits in its script. A `[kept]` table missing, unfilled, malformed or on
    a fit or an apply (`protocol_check.kept_gaps`) blocks too. A fit or an
    apply binds its answer through its promise keys: a note. The key binds
    the name, not the meaning: a wrong computation under the right key
    passes — the tests and the analysis audit judge that."""
    gaps = kept_gaps(text, head)
    for gap in gaps:
        # an unfilled value is the stamp's placeholder, which protocol-fill
        # sets; every other gap is a table to add, drop or repair by hand
        unfilled = gap in {f"[kept] {f}" for f in protocol_block.KEPT_KEYS}
        findings.block(
            f"{protocol.name}: {gap}"
            + (" is still the placeholder" if unfilled else ""),
            fix=(
                f"`{fill_command(protocol, f'kept.{gap.removeprefix("[kept] ")}=<value>')}`"
                if unfilled
                else f"repair the head as the sentence says, then "
                f"`{gate_command('finalize', protocol.parent)}`"
            ),
        )
    if gaps:
        return
    if head.kind is None:
        findings.note("  n/a — the head's kind is undecided (open fields name it)")
        return
    if head.kind != COMPUTE_KIND:
        findings.note(
            f"  n/a — kind = {head.kind!r} binds its answer through its promise keys"
        )
        return
    key = protocol_block.kept_key(text)  # kept_gaps found the table filled
    try:
        metrics = runs_metrics(answering_run)
    except MetricsError as exc:
        findings.block(
            f"the metrics of {answering_run.name} do not read: {exc}",
            fix=f"measure anew (`{measure_command(answering_run.parent.parent)}`) "
            f"and audit that run; the run's own files stay as they are",
            step=measure_command(answering_run.parent.parent),
        )
        return
    held = kept_number_gaps(
        key, metrics, answering_run.name, answering_run.parent.parent
    )
    findings.take_all(held)
    if not held:
        kept = protocol_block.kept(text)
        assert kept is not None and kept.unit is not None, "kept_gaps found it filled"
        findings.note(f"  {kept_phrase(key, metrics[key], kept.unit)}")


def runs_metrics(answering_run: Path) -> dict:
    """RUN's metrics.json (`runs.read_metrics`); raises MetricsError."""
    return read_metrics(metrics_path(answering_run))


def check_criterion_n(findings: Findings, answering_run: Path) -> None:
    """Station 7: a criterion's denominator that matches no recorded input
    count; a record whose inputs or outputs do not read blocks — at repeat
    cost high no other station reads the inputs (`runs.read_data`)."""
    try:
        w = criterion_n_input_mismatches(answering_run)
    except ArtefactError as exc:
        findings.block(
            f"the record of {answering_run.name} does not read: {exc}",
            fix=f"measure anew (`{measure_command(answering_run.parent.parent)}`) "
            f"and audit that run; the run's own files stay as they are",
            step=measure_command(answering_run.parent.parent),
        )
        return
    for line in w:
        findings.warn(line, evidence_kind=STATIC_EVIDENCE)
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
       (`answering_run`); none bound is a blocker, and steps 1b, 3, 5 and 7
       then skip.
    1b. registration — only with a run: its promise block as the first
       measurement registered it (`registration_changes`), a blocker
       naming every change.
    2. intent-check — always; with an answering run it reads its metrics,
       without one it holds the promise block alone (step 1 names the run).
    3. the run's code and the declared scopes — only with a run: the code
       that produced the number is the code here now (`check_run_code`),
       each declared scope as the run saw it (`check_declared_scopes`).
    4. open fields — always: protocol placeholders and stamped `<…>`
       placeholders left in the area's README warn; a bound field written
       twice and data counts typed by hand or stale block.
    5. provenance — only for repeat_cost = low, and only with a run.
    6. area tests — always.
    7. registered outputs, criterion n, the null lane, the kept number and
       the reference comparison — only with a run; an output that is not
       the file the run recorded (gone, or another sha256 than outputs.json)
       blocks, criterion n warns, a null lane that did not move blocks, a
       computation's run without its `[kept] key` as a finite number blocks, a
       registered reference the run cannot compare (the key absent or no
       finite number) blocks — a missed one is a result.
    8. audit findings — always: an `open` BLOCKER in `audits/` blocks.

    A blocker never stops a step: all of them run, then the summary lists
    every blocker again. Warnings alone end with 0.
    """
    console_output = findings is None
    findings = Findings() if findings is None else findings
    # 0. protocol and settings — the only early end
    try:
        chosen = the_protocol(area, protocol)
    except ProtocolChoiceError as exc:
        if console_output:
            console.refuse("finalize", str(exc))
        else:
            findings.block(str(exc), fix=PROTOCOL_NAMED)
        return 2
    state, held = _inputs(area, state, held)
    text = state.text_of(chosen)
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        if console_output:
            console.refuse("finalize", f"{chosen.name}: {exc}")
        else:
            findings.block(
                f"{chosen.name}: {exc}",
                fix=f"repair the head as the sentence says: `protocol-check "
                f"{shlex.quote(shown(chosen, Path.cwd()))} --contract` shows its fields",
            )
        return 2

    # 1. answering run — the run every later step examines
    findings.header(f"answering run: {chosen.name}")
    answering_run = check_answering_run(findings, area, chosen, text, head.id, state)

    # 1b. the registration as the first measurement recorded it — with a run
    findings.header("registration since the first measurement")
    if answering_run is None:
        findings.note(NO_RUN)
    else:
        check_registration(findings, area, chosen, head.id, answering_run, state, held)

    # 2. intent-check — always
    findings.header("intent-check")
    check_intent_keys_in_metrics(findings, chosen, text, answering_run, state)

    # 3. the run's code and the declared scopes — only with a run
    findings.header("the run's code and declared scopes")
    if answering_run is None:
        findings.note(NO_RUN)
    else:
        # the protocol that declares this very run: its holds withdraw first
        held_by = declaring_protocol(chosen, text, answering_run, state)
        check_run_code(findings, area, answering_run, held_by)
        check_declared_scopes(findings, area, answering_run, text, held_by)

    # 4. open fields — always
    findings.header(f"open fields: {chosen.name}")
    check_open_fields(findings, chosen, text, head, state)

    # 5. provenance — at low repeat cost, and only with a run
    findings.header("provenance")
    if not lane(head.repeat_cost).provenance:
        findings.note(
            f"  n/a — protocol repeat cost is {head.repeat_cost!r} (the agent audit covers provenance there)"
        )
    elif answering_run is None:
        findings.note(NO_RUN)
    else:
        check_provenance(findings, area, answering_run)

    # 6. area tests — always
    findings.header("area tests")
    check_area_tests(findings, area)

    # 7. registered outputs, criterion n, the null lane and the reference
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

    # 8. audit findings — always
    findings.header("audit findings")
    check_open_audit_findings(findings, area, state, held)

    return report(findings)  # 1 if any step found a blocker, else 0


def declared_run_gaps(text: str, protocol: Path) -> list[GateFinding]:
    """A blocker when the head's `[result]` table does not read (a typed
    id, a stray key: `protocol_block.declared_run`'s sentence). An adopted
    run that is no completed run of the protocol — no `runs/<id>/` among
    them — is the run choice's blocker (`choose_answering_run`). Empty
    without a declaration or with one that reads."""
    written = (
        f"`{withdraw_command(protocol)}` removes it; audit the run that answers, "
        f"then `{adopt_command(protocol, '<run_id>')}` writes the table for it"
    )
    try:
        protocol_block.declared_run(text)
    except protocol_block.BlockError as exc:
        return [blocker(str(exc), fix=written, step=withdraw_command(protocol))]
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
