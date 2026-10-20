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
                    the run the answer cites is this one (blocker), the
                    `Answering run` field names it (blocker/warning), its
                    JSONL rows come from this run, the runs it continues or
                    its derived_from lineage (blocker), a model record stands
                    in its lineage (warning), the arm lines match (warning),
                    it is a full run — `run_kind='measurement'`, not acknowledged unfrozen
                    (warning here, `runs.unreportable`; report-check blocks)
  2. intent-check   every registered promise has a metrics key (and vice
                    versa); skipped when the protocol registers no id
  3. declared scopes  every declared promise scope unchanged since the run
  4. open fields    protocol fields still holding a placeholder
  5. frozen source  at protocol `cost = "seconds"` only: the run froze its source
                    (`data=` in config.json) and every source and output file
                    is tracked in git — the two of the three questions the
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
  8. audit findings every finding still `open` in `audits/` (any mode), with
                    its file: a BLOCKER is a blocker, a WARNING a warning — a
                    finding nobody decided is an ignored finding
                    (LAB-015 Preflight audit before freezing); the benchmark
                    rounds reported numbers past undecided BLOCKERs (plan
                    2026-10-17, A3)

Three grades, decided where each finding is made and summed at the end:
`Findings.block` (exit 1), `Findings.warn` (counted, exit 0), a plain
print (a note, uncounted). "0 blockers, N warnings" sums the warnings of
every station, not the open fields alone.

What it does NOT do: fill fields, edit the protocol, or commit. It is a
read-only gate that reports findings.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from labkit.formats import console, findings as audit_findings, promises, protocol_block
from labkit.formats.standard_contract import lane
from labkit.formats.gate import Findings
from labkit.formats.runs import (
    RUN_ID,
    unreportable,
    read_run_config,
)
from labkit.formats.answering_run import (
    bound_answering_run,
)
from labkit.formats.repo import (
    ProtocolChoiceError,
    area_path,
    layout_root,
    no_such_area,
    the_protocol,
)
from labkit.checks.intent_check import main as intent_check_main, ids_in_prose
from labkit.gates.preflight import area_tests
from labkit.formats.protocol_check import (
    answer_field,
    answering_run_field,
    answering_run_open,
    open_holes,
)
from labkit.checks.run_record_check import (
    arm_findings,
    criterion_n_input_mismatches,
    model_provenance_gap,
    provenance_findings,
    row_provenance_findings,
    single_draw,
)
from labkit.checks.readme_check import readme_placeholders, readme_route


def answering_run(
    findings: Findings, area: Path, pid: str | None, ids_registered: bool
) -> Path | None:
    """The run every station holds the protocol to — `answering_run.bound_answering_run`,
    ONE choice for every station: intent-check skips newer runs without
    intent keys (a probe), so checking scopes or provenance on the newest
    run judged the probe while the numbers came from the measurement
    (review 2026-10-07). A blocker here is the finding; the exclusions are
    printed for the operator."""
    if pid is None:
        findings.block("no stamped protocol id ([protocol] id) — no run is bound to it")
        return None
    choice = bound_answering_run(area, pid)
    blocker, lines = choice.explain(ids_registered)
    if choice.run_dir is None:
        findings.block(blocker or f"no completed run bound to {pid}")
        for line in lines:
            findings.note(f"    {line}")
        return None
    if blocker:
        findings.block(blocker)
    findings.note(
        f"  {choice.run_dir.name}: completed" + "".join(f" ({ln})" for ln in lines)
    )
    return choice.run_dir


def cited_run_mismatch(text: str, measurement_run: Path) -> str | None:
    """A blocker when the protocol's answer cites runs and not the one the
    checks hold; None when it cites that run or none."""
    cited = cited_runs(text)
    if cited and measurement_run.name not in cited:
        return (
            f'"Answer to the question" cites {", ".join(cited)}, '
            f"but the run that answers is {measurement_run.name} — cite the run "
            f"the checks hold, or rerun"
        )
    return None


def answering_run_field_mismatch(
    text: str, measurement_run: Path
) -> tuple[str, str] | None:
    """("block" | "warn", message): the `Answering run` line names another
    run than the one the checks hold (block), or is still "none yet"
    (warn: write it with protocol-fill). None when it names that run or
    the protocol has no such line. The field is a readable projection of
    `answering_run.bound_answering_run`, never a second binding — so it is held to
    the choice, not consulted for it."""
    value = answering_run_field(text)
    if value is None or measurement_run.name in value:
        return None
    if answering_run_open(value):
        return (
            "warn",
            f'"Answering run" not written yet — `protocol-fill --from-run '
            f"{measurement_run.name}` writes it with the number once this finalize is clean",
        )
    return (
        "block",
        f'"Answering run" names {value.split()[0]}, but the run that answers is '
        f"{measurement_run.name} — the field is a projection of the binding; "
        f"protocol-fill it with the run the checks hold",
    )


def check_completion(
    findings: Findings, area: Path, text: str, pid: str | None
) -> Path | None:
    """Station 1: the run every later station holds the protocol to — chosen,
    shown, and held to the run the answer cites. Returns it, or None."""
    measurement_run = answering_run(findings, area, pid, bool(ids_in_prose(text)))
    if measurement_run is not None:
        mismatch = cited_run_mismatch(text, measurement_run)
        if mismatch:
            findings.block(mismatch)
        graded = answering_run_field_mismatch(text, measurement_run)  # (grade, message)
        if graded is not None:
            grade, message = graded
            (findings.block if grade == "block" else findings.warn)(message)
        for warning in (
            model_provenance_gap(measurement_run),
            single_draw(area, measurement_run),
            *unreportable_warnings(measurement_run),
        ):
            if warning:
                findings.warn(warning)
        blockers, notes = row_provenance_findings(measurement_run)
        for b in blockers:
            findings.block(b)
        for n in notes:
            findings.note(f"  {n}")
        for w in arm_findings(text, area, measurement_run):
            findings.warn(w)
    return measurement_run


def unreportable_warnings(measurement_run: Path) -> list[str]:
    """Why the answering run's number cannot be reported (`runs.unreportable`),
    each a warning here: finalize holds the run, report-check refuses the report."""
    cfg = read_run_config(measurement_run)
    if cfg is None:
        return []
    return [
        f"the answering run {measurement_run.name}: {mark} — its number cannot "
        f"be reported (report-check refuses it)"
        for mark in unreportable(cfg)
    ]


def check_open_audit_findings(findings: Findings, area: Path) -> None:
    """Station 8: every finding still `open` in the area's audit records, any
    mode — a BLOCKER blocks, a WARNING warns, a NOTE is printed — each with
    its file. A record nobody can read is a blocker, not "no findings"."""
    try:
        records = audit_findings.area_records(area)
    except audit_findings.FindingsError as exc:
        findings.block(str(exc))
        return
    seen = 0
    for rec in records:
        for f in rec.open:
            seen += 1
            line = f"{rec.path.name}: {f.text} — undecided (LAB-015 Preflight audit before freezing)"
            if f.grade == "BLOCKER":
                findings.block(line)
            elif f.grade == "WARNING":
                findings.warn(line)
            else:
                findings.note(f"  {line}")
    if not seen:
        findings.note(
            f"  every finding decided ({len(records)} record(s))"
            if records
            else "  no audit record in audits/"
        )


def check_intent_keys_in_metrics(
    findings: Findings, protocol: Path, text: str, measurement_run: Path | None
) -> None:
    """Station 2: every registered intent id reports as a key of the answering
    run's metrics.json (intent-check). Not code_check.check_intent_ids, which
    holds the promises to the code before any run."""
    if not ids_in_prose(text):
        findings.note("  no intent ids registered — nothing to check")
        return
    args = [str(protocol)] + (
        ["--metrics", str(measurement_run / "metrics.json")]
        if measurement_run is not None
        else []
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = intent_check_main(args)
    for line in buf.getvalue().splitlines():
        findings.note(f"  {line}")
    if rc != 0:
        findings.block("intent-check failed (see its lines above)")


def check_declared_scopes(
    findings: Findings, area: Path, measurement_run: Path, text: str = ""
) -> None:
    """Station 3: a promise's declared scope edited after the run: today's code is not
    the code that produced the number; until 2026-10-06 only recheck saw it
    (Durchstich). An answering run that recorded no block is a blocker
    (standard 0.19, `promises.promise_tables_owed`: every reportable run is held to
    a registration that is data) — it came from a labkit that let it pass,
    or the block was added after the run."""
    recorded = (read_run_config(measurement_run) or {}).get("promises")
    if recorded is None and text and not promises.registers_ids(text):
        findings.note(
            "  n/a — the protocol registers no promise id (a count), nothing to hold"
        )
        return
    if recorded is None:
        owed = promises.promise_tables_owed(None, frozen=False, full_run=True)
        findings.block(
            f"{measurement_run.name} recorded no promise block: {owed} — a run "
            f"under labkit 0.70.0 or earlier is checked and reproduced with "
            f"its pinned version; a block added after the run is a new registration"
        )
        return
    drift = promises.scope_drift(recorded, area)
    for d in drift:
        findings.block(
            f"declared scope changed since {measurement_run.name}: {d} — rerun before reporting"
        )
    if not drift:
        findings.note(
            f"  {len(recorded['ids'])} declared scope(s) unchanged since {measurement_run.name}"
        )


def check_open_fields(
    findings: Findings, protocol: Path, text: str, head: protocol_block.Head
) -> None:
    """Station 4: fields of the protocol still empty or a placeholder, and
    the README's route block (CODE-016)."""
    holes = open_holes(text, head)
    for lineno, label in holes:
        findings.warn(f"{protocol.name}:{lineno}: {label}")
    stale = readme_placeholders(protocol.parent)
    for line in stale:
        findings.warn(f"{line} — a stamped placeholder, fill or delete the line")
    route = readme_route(protocol.parent, protocol.name)
    for line in route:
        findings.warn(line)
    if not holes and not stale and not route:
        findings.note("  all fields filled")


def check_provenance(findings: Findings, area: Path, measurement_run: Path) -> None:
    """Station 5: the run's source frozen in the run, source and output
    tracked in git."""
    b, w = provenance_findings(area, measurement_run)
    for line in b:
        findings.block(line)
    for line in w:
        findings.warn(line)
    if not b and not w:
        findings.note("  source frozen in the run; source and output tracked in git")


def check_area_tests(findings: Findings, area: Path) -> None:
    """Station 6: the area's own tests. The resolution check runs again before a number leaves: a later edit
    of evaluate() that mutes the criterion is caught here too — on every
    tier, seconds included, where preflight is not owed (2026-10-07). A
    missing test is no finding here; preflight owes it at the freeze."""
    # the same place preflight looks: a stamped tree before `git init` has
    # tests/ under its layout root, and git_root found "none" (audit 2026-10-15)
    tests = area_tests(area, layout_root(area))
    if tests.state == "none":
        findings.note(f"  none ({tests.pattern})")
    elif tests.state == "ok":
        findings.note(f"  ok — {', '.join(t.name for t in tests.files)}")
    elif tests.state == "no-pytest":
        findings.warn("pytest is not installed in this interpreter — tests not run")
    else:
        for ln in tests.tail:
            findings.note(f"  {ln}")
        findings.block(
            f"{', '.join(t.name for t in tests.files)} failed — evaluate() no longer holds its resolution check"
        )


def check_criterion_n(findings: Findings, measurement_run: Path) -> None:
    """Station 7: a criterion's denominator that matches no recorded input count."""
    w = criterion_n_input_mismatches(measurement_run)
    for line in w:
        findings.warn(line)
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
    measurement run is one execution of the experiment's script, a folder
    under `runs/` bound to this protocol — not this function, and not the
    protocol itself.

    0. Choose the protocol and read its settings block. Ends at once with 2
       when the named file is missing, the folder holds several protocols
       and none is named, or the settings block cannot be read.
    1. completion — choose the measurement run the later steps examine
       (`measurement_run`); none bound is a blocker, and steps 3, 5 and 7
       then skip.
    2. intent-check — always; with a measurement run it reads its metrics.
    3. declared scopes — only with a run.
    4. open fields — always; warnings only: protocol placeholders and
       stamped `<…>` placeholders left in the area's README.
    5. provenance — only for cost = seconds, and only with a run.
    6. area tests — always.
    7. criterion n — only with a run; warnings only.
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
            findings.note(f"finalize: {exc}")
        return 2
    text = chosen.read_text(encoding="utf-8")
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        findings.note(f"finalize: {chosen.name}: {exc}")
        return 2

    # 1. completion — the run every later step examines
    findings.header(f"completion: {chosen.name}")
    measurement_run = check_completion(findings, area, text, head.id)

    # 2. intent-check — always
    findings.header("intent-check")
    check_intent_keys_in_metrics(findings, chosen, text, measurement_run)

    # 3. declared scopes — only with a run
    findings.header("declared scopes")
    if measurement_run is None:
        findings.note(NO_RUN)
    else:
        check_declared_scopes(findings, area, measurement_run, text)

    # 4. open fields — always
    findings.header(f"open fields: {chosen.name}")
    check_open_fields(findings, chosen, text, head)

    # 5. provenance — where the lane owes it (seconds), and only with a run
    findings.header("frozen source and tracked files")
    if not lane(head.cost).provenance:
        findings.note(
            f"  n/a — protocol cost is {head.cost!r} (the agent audit covers provenance there)"
        )
    elif measurement_run is None:
        findings.note(NO_RUN)
    else:
        check_provenance(findings, area, measurement_run)

    # 6. area tests — always
    findings.header("area tests")
    check_area_tests(findings, area)

    # 7. criterion n — only with a run
    findings.header("criterion n")
    if measurement_run is None:
        findings.note(NO_RUN)
    else:
        check_criterion_n(findings, measurement_run)

    # 8. audit findings — always
    findings.header("audit findings")
    check_open_audit_findings(findings, area)

    return report(findings)  # 1 if any step found a blocker, else 0


def cited_runs(text: str) -> list[str]:
    """The run ids the protocol's "Answer to the question" cites — a number
    written back, the one declaration that a result is reported
    (`protocol_check.answer_field`; report-check holds it at the stop and
    the commit). Empty while the field is a placeholder or cites none."""
    value = answer_field(text)
    return sorted({m.group(0) for m in RUN_ID.finditer(value)}) if value else []


def main(argv: list[str]) -> int:
    """Command line of `finalize`: check one area."""
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: finalize <AREA> [--protocol PROTOCOL-*.md]")
        print(
            "       (the gate at the stop and the commit is `report-check --if-reported`, "
            "which runs finalize as one station)"
        )
        return 0 if argv else 2

    area = area_path(argv[0])
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
