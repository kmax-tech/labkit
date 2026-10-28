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
                    (`data=` in config.json) and every source and output file
                    is tracked in git (a directory source: each visible file
                    under it) — the two of the three questions the
                    agent audit kept asking that a machine can answer (LAB-017 The number of audits follows the cost tier, 2026-10-05);
                    the third, the counted unit, is the protocol's `Unit` field
  6. area tests     tests/test_<NN>_<name>.py via the repo's interpreter, on
                    every tier: a failing test is a blocker (evaluate() lost
                    its resolution check), a missing one no finding here
  7. criterion n    every `c<i>_n` key in metrics.json equals some input
                    count the run recorded (rows of a data= file, lines of
                    an output) — a warning, not a blocker, until the false
                    alarm rate is known (2026-10-05; the denominator class
                    was 31 of 171 audit findings)
     null lane      an output the run kept with a registered and a null
                    lane: the null answers otherwise on some item, gold
                    included — a blocker (`null_lane_findings`, LAB-034
                    Null condition in the same run); without both lanes, a
                    note
  8. audit findings every finding still `open` in `audits/` (any mode), with
                    its file: a BLOCKER is a blocker, a WARNING a warning — a
                    finding nobody decided is an ignored finding
                    (LAB-015 Preflight audit before freezing); the benchmark
                    rounds reported numbers past undecided BLOCKERs (plan
                    2026-10-17, A3). And every analysis record names a run
                    the area still holds: a deleted run directory behind a
                    record is a blocker (fifth haiku round, `rm -rf runs/…`)

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

from labkit.formats.gate import GUARANTEED, STATIC_EVIDENCE, GateFinding, blocker
from labkit.formats.runs import metrics_path, run_path
from labkit.formats import console, findings as audit_findings, promises, protocol_block
from labkit.formats.standard_contract import lane
from labkit.formats.gate import EXIT_CONTRACT, Findings
from labkit.formats.runs import (
    RunDir,
    patch_path,
    read_run_dir,
    recorded_commit,
    run_dirs,
    unreportable,
    read_run_config,
)
from labkit.formats.answering_run import (
    bound_answering_run,
    first_registrations,
)
from labkit.formats import protocol_history
from labkit.formats.repo import (
    adopt_command,
    AmbiguousArea,
    area_path,
    audit_command,
    git_root,
    layout_root,
    measure_command,
    no_such_area,
    ProtocolChoiceError,
    shown,
    the_protocol,
    withdraw_command,
)
from labkit.gates.ways_out import (
    HANDOVER,
    PROTOCOL_NAMED,
    declared_first,
    register_anew,
)
from labkit.checks.intent_check import hold as intent_hold
from labkit.gates.preflight import area_tests, tell_test_run
from labkit.formats.protocol_check import (
    field_name,
    fields,
    open_holes,
)
from labkit.checks import data_counts
from labkit.checks.run_record_check import (
    arm_findings,
    code_since_run,
    criterion_n_input_mismatches,
    null_lane_findings,
    model_provenance_gap,
    provenance_findings,
    row_provenance_findings,
    single_draw,
)
from labkit.checks.readme_check import readme_placeholders, readme_route


def choose_answering_run(
    findings: Findings, area: Path, pid: str | None, ids_registered: bool
) -> Path | None:
    """The run every station holds the protocol to — `answering_run.bound_answering_run`,
    ONE choice for every station: intent-check skips newer runs without
    intent keys (a probe), so checking scopes or provenance on the newest
    run judged the probe while the numbers came from the measurement
    (review 2026-10-07). A blocker here is the finding, and it carries the
    runs that were looked at and why none answers: a note beside it
    reaches no caller that collects the findings as data (audit
    2026-10-23, B1)."""
    if pid is None:
        findings.block(
            "no stamped protocol id ([protocol] id) — no run is bound to it",
            fix="stamp the area with `labkit-init exp <name> --kind …`, which "
            "writes a fresh id, and carry the protocol's text over",
        )
        return None
    choice = bound_answering_run(area, pid)
    blocker, lines = choice.explain(ids_registered)
    if choice.run_dir is None:
        assert blocker is not None, "explain() names a blocker whenever no run stands"
        looked_at = "".join(f"; {line}" for line in lines)
        findings.take(replace(blocker, text=blocker.text + looked_at))
        return None
    if blocker:
        findings.take(blocker)
    findings.note(
        f"  {choice.run_dir.name}: completed" + "".join(f" ({ln})" for ln in lines)
    )
    return choice.run_dir


def declared_run_mismatch(
    text: str, answering_run: Path, protocol: Path
) -> GateFinding | None:
    """A blocker when the head's `[result] run` of PROTOCOL (its TEXT) names
    another run than the one the checks hold, with the command that
    declares that one; None when it names that run or the protocol
    declares none (an exploration). The declaration is a projection of
    `answering_run.bound_answering_run`, never a second binding — held to the
    choice, not consulted for it."""
    declared = protocol_block.declared_run(text)
    if declared is None or declared == answering_run.name:
        return None
    # the command is the last step, not the fix: printed bare beside an open
    # BLOCKER on that very run, three of three Haiku readers were told to
    # adopt the faulty run (stuck-state probe 2026-10-28)
    return blocker(
        f"[result] declares {declared}, but the run that answers is "
        f"{answering_run.name}",
        fix=f"withdraw the declaration (`{withdraw_command(protocol)}`), audit the "
        f"run that answers and decide its findings, then "
        f"`{adopt_command(protocol, answering_run.name)}` declares it — an audit "
        f"made while another run is declared does not cover it; if the fault is "
        f"in that run, fix the code and measure again first",
    )


def undeclared_hint(text: str, answering_run: Path, protocol: Path) -> str | None:
    """A note while the protocol declares no result yet — the normal state
    before adoption, so no warning: the command that declares
    MEASUREMENT_RUN and writes its number (`repo.adopt_command`, naming
    PROTOCOL — `--from-run <run>` alone exits 2, review 2026-10-20). None
    once a run is declared."""
    if protocol_block.declared_run(text) is not None:
        return None
    return (
        f"no [result] declared yet — after the analysis audit "
        f"(`{audit_command(protocol.parent, '--mode', 'analysis', protocol=protocol)}`), "
        f"its decisions and the Conclusion, "
        f"`{adopt_command(protocol, answering_run.name)}` declares the run and "
        f"writes the number"
    )


def _hold_declaration(
    findings: Findings, area: Path, protocol: Path, text: str, run: Path | None
) -> None:
    """The head's `[result]` against RUN, the run the checks hold: a table
    that does not read or names no run of AREA blocks (`declared_run_gaps`),
    one naming another run blocks (`declared_run_mismatch`), none yet is a
    note with the command (`undeclared_hint`)."""
    gaps = declared_run_gaps(area, text, protocol)
    findings.take_all(gaps)
    if run is None:
        return
    try:
        protocol_block.declared_run(text)
    except protocol_block.BlockError:
        return  # named in GAPS; nothing to hold to the run
    mismatch = declared_run_mismatch(text, run, protocol)
    if mismatch:
        findings.take(mismatch)
    hint = undeclared_hint(text, run, protocol)
    if hint:
        findings.note(
            f"  {hint}"
        )  # the normal state before adoption: a note, finalize stays clear


def check_answering_run(
    findings: Findings, area: Path, protocol: Path, text: str, pid: str | None
) -> Path | None:
    """Station 1: the run every later station holds the protocol to — chosen,
    shown, and held to the run the head declares (`[result] run`). Returns
    it, or None."""
    answering_run = choose_answering_run(findings, area, pid, _registers(text))
    _hold_declaration(findings, area, protocol, text, answering_run)
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


def registration_changes(
    area: Path, protocol: Path, pid: str | None, run: Path | None
) -> list[GateFinding]:
    """The answering RUN holds the registration its protocol's first
    measurement recorded (K3, docs/notes/2026-10-27-new-registration-contracts.md):
    the promise block in each run's record (`promises.snapshot`: ids, keys,
    sentences through the block's digest, scopes, constants — not the code
    the scopes name, so a repair measured again under the same promises
    passes). A run whose block differs from the first measurement's is held,
    each change named — sentences, keys, constants and scopes together,
    from the protocol texts both runs saw (`named_changes`) — with the way
    out: restore what was registered and measure again, or register anew.
    Every lane: a bar moved after a result was seen answers no registered
    question at any repeat cost. Run here, after every measurement, and not
    first at the adoption: three runs and an audit went into a changed
    registration before report-check named it (fourth SAB-like draw,
    2026-10-28). The first measurements are every run at each first
    position (`answering_run.first_registrations`), not one chosen by name;
    when they recorded different blocks, which one stood cannot be told and
    no run answers a registered question: held too, the ways out a new
    registration that declares its changes against each (K1,
    `report_check.replacement_gaps`) or a handover without a declared
    result. Empty without an answering run, a stamped id PID, or a block in
    the records. Raises RuntimeError when git fails."""
    if pid is None or run is None:
        return []
    cfg = read_run_config(run)
    now = cfg.promises if cfg is not None else None
    if now is None:
        return []
    root = git_root(protocol)
    registered = first_registrations(area, pid, root)
    if len(registered) > 1:
        named = ", ".join(
            f"{rd.dir.name} (block {sha})" for sha, (rd, _) in registered.items()
        )
        return [
            blocker(
                f"the first measurements recorded different registrations: {named} — "
                f"which one stood before the number cannot be told, so no run of "
                f"this protocol answers a registered question",
                fix="either "
                + register_anew(
                    pid,
                    "per change against each of these registrations (report-check "
                    "of the new protocol lists them)",
                )
                + f"; or {HANDOVER}",
            )
        ]
    if not registered:
        return []
    ((sha, (first, snap)),) = registered.items()
    if now["block_sha"] == sha:
        return []
    changes, restores = named_changes(
        protocol, first, read_run_dir(run), snap, now, root
    )
    commit = recorded_commit(first.config) if first.config is not None else None
    shown_then = ""
    if commit and root is not None:
        rel = protocol.resolve().relative_to(root.resolve()).as_posix()
        shown_then = (
            f" — `git show {commit[:12]}:{rel}` shows them as committed then"
            + (
                f", runs/{first.dir.name}/uncommitted.patch what its tree changed"
                if patch_path(first.dir).is_file()
                else ""
            )
        )
    return [
        blocker(
            f"the registration changed after the first measurement {first.dir.name}: "
            f"{'; '.join(changes)} (recorded by the answering run {run.name}) — a "
            f"bar set after a result was seen does not answer the registered "
            f"question",
            fix=f"restore the [[promise]] tables as {first.dir.name} "
            f"registered them ({'; '.join(restores)}){shown_then}, "
            f"and measure again, then audit that run (the earlier runs stay); or, "
            f"when the registration cannot be answered as written, "
            + register_anew(pid)
            + " — the earlier protocol, its runs and their verdict stay",
        )
    ]


def named_changes(
    protocol: Path,
    first: RunDir,
    answering: RunDir,
    was: dict,
    now: dict,
    root: Path | None,
) -> tuple[list[str], list[str]]:
    """(changes, restores): every change of the promise block from the
    first measurement FIRST to the ANSWERING run, and what undoes each. From
    the protocol texts both runs saw (`protocol_history.as_measured`,
    `promise_differences`): sentences, keys, constants and scopes together —
    the run records keep sentences only through the block's digest, and a
    restore told only the constants left a changed sentence that held the
    next run again (fourth SAB-like draw). Where a text cannot be read back,
    what the records WAS and NOW hold (`promises.snapshot_changes`) and why
    the sentences go unnamed. Raises RuntimeError when git fails."""
    then, why_then = protocol_history.as_measured(protocol, first, root)
    current, why_now = protocol_history.as_measured(protocol, answering, root)
    if then is not None and current is not None:
        diffs = protocol_history.promise_differences(then, current)
        if diffs:
            return (
                [change_phrase(*d) for d in diffs],
                [restore_phrase(*d) for d in diffs],
            )
    changes = promises.snapshot_changes(was, now)
    restores = [_restored(c) for c in changes]
    if then is None or current is None:
        why = why_then if then is None else why_now
        changes.append(f"the sentences unread ({why})")
    return changes, restores


def change_phrase(what: str, old: str, new: str) -> str:
    """One `protocol_history.promise_differences` entry as the hold names it:
    `[A2] null_band 0.1 → 0.15`, `[C1] sentence "…" → "…"`, `[A3] added`."""
    pid, _, part = what.partition(" ")
    if not part:
        return (
            f"[{pid}] added" if old == protocol_history.ABSENT else f"[{pid}] dropped"
        )
    if part == "sentence":
        return f'[{pid}] sentence "{old}" → "{new}"'
    return f"[{pid}] {part} {old} → {new}"


def restore_phrase(what: str, old: str, new: str) -> str:
    """What undoes one `promise_differences` entry: a value or a sentence
    back, an added promise out, a dropped one back in."""
    pid, _, part = what.partition(" ")
    if not part:
        return f"[{pid}] out" if old == protocol_history.ABSENT else f"[{pid}] back in"
    if part == "sentence":
        return f'[{pid}] sentence "{old}" back'
    return f"[{pid}] {part} {old} back"


def _restored(change: str) -> str:
    """What undoes CHANGE, a phrase of `promises.snapshot_changes`: a value
    back, an added promise out, a dropped one back in, the sentences as then
    (the snapshot keeps them only through the block's digest)."""
    if " → " in change:
        return change.split(" → ")[0] + " back"
    if change.endswith(" added"):
        return change.removesuffix(" added") + " out"
    if change.endswith(" dropped"):
        return change.removesuffix(" dropped") + " back in"
    return "every sentence as then"


def check_registration(
    findings: Findings, area: Path, protocol: Path, pid: str | None, run: Path
) -> None:
    """Hold the answering RUN to the registration of the first measurement
    (`registration_changes`); a note when it holds."""
    held = registration_changes(area, protocol, pid, run)
    findings.take_all(held)
    if not held:
        findings.note("  the promise block is the one the first measurement registered")


def check_open_audit_findings(findings: Findings, area: Path) -> None:
    """Station 8: every finding still `open` in the area's audit records, any
    mode (`findings.open_findings`, with the table of the gates' rules) — a
    BLOCKER blocks, a WARNING warns, a NOTE is printed — each with
    its file; and every analysis record names a run the area still holds
    (`findings.records_of_gone_runs`): a run an audit read is a kept run,
    and its deleted directory is a blocker where the record stands. A
    record nobody can read is a blocker, not "no findings"."""
    try:
        records = audit_findings.area_records(area)
    except audit_findings.FindingsError as exc:
        findings.block(str(exc), fix=audit_findings.record_way(area))
        return
    known = {rd.dir.name for rd in run_dirs(area)}
    gone = audit_findings.records_of_gone_runs(records, known)
    for rec in gone:
        findings.block(
            f"{rec.path.name}: names {rec.run_id} as the run it read, and there is "
            f"no runs/{rec.run_id}/ in this area — a run an audit read is a kept run, "
            f"and nothing restores its rows (LAB-043 Runs go through `runlog`)",
            fix="measure again under a new run and audit that",
        )
    seen = len(gone)
    for u in audit_findings.open_findings(records):
        seen += 1
        line = f"{u.line} — undecided (LAB-015 Preflight audit before freezing)"
        if u.grade == "BLOCKER":
            findings.block(line, fix=audit_findings.decide_way(area, u))
        elif u.grade == "WARNING":
            findings.warn(line, evidence_kind=GUARANTEED)
        else:
            findings.note(f"  {line}")
    if not seen:
        findings.note(
            f"  every finding decided ({len(records)} record(s))"
            if records
            else "  no audit record in audits/"
        )


def _registers(text: str) -> bool:
    """Does the protocol register a promise id, in its prose or its block
    (`promises.registered_ids`)? A malformed block counts as registered:
    intent-check then refuses it by name — a blocker — where this question
    would otherwise read "nothing to check"."""
    try:
        return bool(promises.registered_ids(text))
    except promises.PromiseError:
        return True


#: the way out of an intent-check finding: the registration and the run name
#: different promises
INTENT_FIX = (
    "make the protocol's ids, its promise block and the run's metrics.json name "
    "the same promises: fix the code and measure again; after the first "
    "measurement a changed registration is registered anew"
)


def check_intent_keys_in_metrics(
    findings: Findings, protocol: Path, text: str, answering_run: Path | None
) -> None:
    """Station 2: every registered intent id reports as a key of the answering
    run's metrics.json (intent-check). Not code_check.check_intent_ids, which
    holds the promises to the code before any run."""
    if not _registers(text):
        findings.note("  no intent ids registered — nothing to check")
        return
    try:
        held = intent_hold(
            protocol, metrics_path(answering_run) if answering_run is not None else None
        )
    except console.Refused as exc:  # nothing to hold: a blocker, as its exit 2
        findings.block(
            f"intent-check: {exc.why}",
            fix=f"repair what the sentence names; `intent-check "
            f"{shlex.quote(shown(protocol, Path.cwd()))}` holds it alone",
        )
        return
    # Its findings as data, each a blocker (audit 2026-10-23, B1); its
    # notes — which run, on what proof — stay notes (follow-up F4).
    for line in held.notes:
        findings.note(f"  {line}")
    for line in held.findings:
        findings.block(f"intent-check: {line}", fix=INTENT_FIX)
    if not held.findings:
        findings.note(f"  {held.summary}")


def check_run_code(
    findings: Findings, area: Path, answering_run: Path, held_by: Path | None
) -> None:
    """Station 3, first half: the code that produced the answering run's
    number, and that of every run it derives from, is the code here now
    (`run_record_check.code_since_run`), for every kind — a fix after the
    run with no new run left the old code's number standing (audit
    2026-10-27, A1). A module in another repository is a warning. HELD_BY,
    the protocol that declares the answering run (None: none does), puts
    the withdrawal first in each blocker's way out (`declared_first`)."""
    changed, apart = code_since_run(area, answering_run)
    findings.take_all(declared_first(f, held_by) if held_by else f for f in changed)
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
    the code that produced the number; until 2026-10-06 only recheck saw it
    (Durchstich). An answering run that recorded no block is a blocker
    (standard 0.19, `promises.promise_tables_owed`: every reportable run is held to
    a registration that is data) — it came from a labkit that let it pass,
    or the block was added after the run."""
    cfg = read_run_config(answering_run)
    recorded = cfg.promises if cfg else None
    if recorded is None and text and not _registers(text):
        findings.note(
            "  n/a — the protocol registers no promise id (a computation), nothing to hold"
        )
        return
    if recorded is None:
        owed = promises.promise_tables_owed(None, frozen=False, full_run=True)
        findings.block(
            f"{answering_run.name} recorded no promise block: {owed} — a run "
            f"under labkit 0.70.0 or earlier is held and reproduced with "
            f"its pinned version",
            fix=f"a block added after the run is a new registration: "
            f"{register_anew(per='per change, the promise block among them')}",
        )
        return
    drift = promises.scope_drift(recorded, area)
    for d in drift:
        drifted = blocker(
            f"declared scope changed since {answering_run.name}: {d}",
            fix=f"rerun before reporting: `{measure_command(area)}`, then audit that run",
        )
        findings.take(declared_first(drifted, held_by) if held_by else drifted)
    if not drift:
        findings.note(
            f"  {len(recorded['ids'])} declared scope(s) unchanged since {answering_run.name}"
        )


def check_open_fields(
    findings: Findings, protocol: Path, text: str, head: protocol_block.Head
) -> None:
    """Station 4: fields of the protocol still empty or a placeholder, and
    the README's route block (CODE-016)."""
    holes = open_holes(text, head)
    for lineno, label in holes:
        findings.warn(f"{protocol.name}:{lineno}: {label}", evidence_kind=GUARANTEED)
    stale = readme_placeholders(protocol.parent)
    for line in stale:
        findings.warn(
            f"{line} — a stamped placeholder, fill or delete the line",
            evidence_kind=GUARANTEED,
        )
    route = readme_route(protocol.parent, protocol.name)
    for line in route:
        findings.warn(line, evidence_kind=GUARANTEED)
    counted = check_data_counts(findings, protocol, text)
    if not holes and not stale and not route and counted:
        findings.note("  all fields filled")


def check_data_counts(findings: Findings, protocol: Path, text: str) -> bool:
    """Station 4, the generated counts of Data / scope: where the field
    holds them (`counts (prepare run <id>): …`), they are what that run
    recorded (`data_counts.counts_gap`) — a part typed by hand or left
    stale blocks, with the command that writes it again. True when they
    hold or there are none."""
    value = next(
        (f.value for f in fields(text) if f.name == field_name(data_counts.FIELD)),
        "",
    )
    gap = data_counts.counts_gap(protocol.parent, value)
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
    """Station 5: the run's source frozen in the run, source and output
    tracked in git."""
    b, w = provenance_findings(area, answering_run)
    findings.take_all(b)
    for line in w:
        findings.warn(line, evidence_kind=GUARANTEED)
    if not b and not w:
        findings.note("  source frozen in the run; source and output tracked in git")


def check_area_tests(findings: Findings, area: Path) -> None:
    """Station 6: the area's own tests. The resolution check runs again before a number leaves: a later edit
    of evaluate() that mutes the criterion is caught here too — on every
    tier, low included, where preflight is not owed (2026-10-07). A
    missing test is no finding here; preflight owes it at the freeze."""
    # the same place preflight looks: a stamped tree before `git init` has
    # tests/ under its layout root, and git_root found "none" (audit 2026-10-15)
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
        )
        return
    findings.take_all(held.unmoved)
    if held.examined == 0:
        findings.note("  n/a — no kept output holds a registered and a null lane")
    elif not held.unmoved:
        findings.note(f"  the null lane moved in {held.examined} kept output(s)")


def check_criterion_n(findings: Findings, answering_run: Path) -> None:
    """Station 7: a criterion's denominator that matches no recorded input count."""
    w = criterion_n_input_mismatches(answering_run)
    for line in w:
        findings.warn(line, evidence_kind=STATIC_EVIDENCE)
    if not w:
        findings.note("  every c<i>_n equals a recorded input count (or there is none)")


def report(findings: Findings) -> int:
    """The summary and the exit code (`gate.Findings.report`)."""
    return findings.report("finalize", "reporting")


NO_RUN = "  no completed run to check"


def finalize_area(
    area: Path, protocol: Path | None = None, findings: Findings | None = None
) -> int:
    """Run finalize on an area. Returns 0 (clean or warnings only),
    1 (a blocker) or 2 (no protocol to hold the area to). FINDINGS, when
    given, collects what the stations found and is the channel every line
    goes through (`gate.Findings`): a gate that runs finalize as one of its
    stations (report-check) hands over a silent one (`Findings(tell=None)`)
    and names the blockers instead of "run it to see them".

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
    2. intent-check — always; with an answering run it reads its metrics.
    3. declared scopes — only with a run.
    4. open fields — always; warnings only: protocol placeholders and
       stamped `<…>` placeholders left in the area's README.
    5. provenance — only for repeat_cost = low, and only with a run.
    6. area tests — always.
    7. criterion n and the null lane — only with a run; criterion n
       warns, a null lane that did not move blocks.
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
    text = chosen.read_text(encoding="utf-8")
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
    answering_run = check_answering_run(findings, area, chosen, text, head.id)

    # 1b. the registration as the first measurement recorded it — with a run
    findings.header("registration since the first measurement")
    if answering_run is None:
        findings.note(NO_RUN)
    else:
        check_registration(findings, area, chosen, head.id, answering_run)

    # 2. intent-check — always
    findings.header("intent-check")
    check_intent_keys_in_metrics(findings, chosen, text, answering_run)

    # 3. the run's code and the declared scopes — only with a run
    findings.header("the run's code and declared scopes")
    if answering_run is None:
        findings.note(NO_RUN)
    else:
        # the protocol that declares this very run: its holds withdraw first
        held_by = (
            chosen
            if protocol_block.declared_run_shown(text) == answering_run.name
            else None
        )
        check_run_code(findings, area, answering_run, held_by)
        check_declared_scopes(findings, area, answering_run, text, held_by)

    # 4. open fields — always
    findings.header(f"open fields: {chosen.name}")
    check_open_fields(findings, chosen, text, head)

    # 5. provenance — where the lane owes it (seconds), and only with a run
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

    # 7. criterion n and the null lane — only with a run
    findings.header("criterion n")
    if answering_run is None:
        findings.note(NO_RUN)
    else:
        check_criterion_n(findings, answering_run)
        findings.header("null lane")
        check_null_lane(findings, answering_run)

    # 8. audit findings — always
    findings.header("audit findings")
    check_open_audit_findings(findings, area)

    return report(findings)  # 1 if any step found a blocker, else 0


def declared_run_gaps(area: Path, text: str, protocol: Path) -> list[GateFinding]:
    """A blocker when the head's `[result] run` names no run of AREA (no
    `runs/<id>/` there), or when the table does not read (a typed id, a
    stray key: `protocol_block.declared_run`'s sentence). A run id is
    written by runlog and copied by `protocol-fill --from-run`, never
    typed — a typed one claims a run that may not exist. Empty without a
    declaration."""
    written = (
        f"`{withdraw_command(protocol)}` removes it; audit the run that answers, "
        f"then `{adopt_command(protocol, '<run_id>')}` writes the table for it"
    )
    try:
        declared = protocol_block.declared_run(text)
    except protocol_block.BlockError as exc:
        return [blocker(str(exc), fix=written)]
    if declared is None or run_path(area, declared).is_dir():
        return []
    return [
        blocker(
            f"[result] declares {declared}, but there is no runs/{declared}/ in this "
            f"area — a run id is runlog's, never typed",
            fix=written,
        )
    ]


def main(argv: list[str]) -> int:
    """Command line of `finalize`: check one area."""
    if not argv or argv[0] in ("-h", "--help"):
        lines = [
            (__doc__ or "").strip().splitlines()[0],
            "usage: finalize <AREA> [--protocol PROTOCOL-*.md]",
            "       (the gate at the stop and the commit is `report-check --if-reported`, "
            "which runs finalize as one station)",
            EXIT_CONTRACT,
        ]
        return console.usage("finalize", "\n".join(lines), asked=bool(argv))

    try:
        area = area_path(argv[0])
    except AmbiguousArea as exc:
        console.refuse("finalize", str(exc))
        return 2
    protocol = None
    rest = argv[1:]
    while rest:
        if rest[0] == "--protocol" and len(rest) >= 2:
            protocol = Path(rest[1])
            rest = rest[2:]
            continue
        console.refuse("finalize", f"unexpected argument {rest[0]!r}")
        return 2

    if not area.is_dir():
        console.refuse("finalize", no_such_area(area))
        return 2

    return finalize_area(area, protocol)


def cli() -> None:
    """Console entry point of `finalize`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
