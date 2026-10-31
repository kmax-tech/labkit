"""protocol-fill — fill protocol fields, adopt a run or render recorded results.

Filling protocol fields by full-text replacement fails in rounds: the quoted
placeholder block never matches exactly (2026-09-09, twice in one day on the
same protocol — three attempts each until a regex sat). The template stamps
every field as `- **Label †:** <placeholder>`, so the LABEL is the stable
handle; this tool matches it, replaces the `<...>` value (multi-line
placeholders included) and leaves everything else byte-identical. The text
edits stand in `protocol_edit`, the writers of the result section in
`protocol_result`; this module reads and writes the files and holds the
command line.

    protocol-fill PROTOCOL-x.md --list
    protocol-fill PROTOCOL-x.md "Meaning of the gold label=positive = ..."   the form AGENTS.md shows; several fields in one call
    protocol-fill PROTOCOL-x.md "Meaning of the gold label" "positive = ..."   the same, one field
    protocol-fill PROTOCOL-x.md --line 27 Question "does Y move X?"
    protocol-fill PROTOCOL-x.md "criterion-1 sentence=<the promise>"   a [[promise]]'s sentence, as a TOML string
    protocol-fill PROTOCOL-x.md type=exploratory repeat_cost=low kind=fit "model alias=haiku"   the TOML head's stamped placeholders
    protocol-fill PROTOCOL-x.md --prompts      the Prompt block from the scripts' PROMPT constants
    protocol-fill PROTOCOL-x.md --render       the result section written again from its sources:
                                               Recorded results, Limitation lines (stray ones dropped), Prompt block
    protocol-fill PROTOCOL-x.md --into REPORT.md  the declared result as a generated block in a
                                               report outside the protocol (replaced in place,
                                               or appended); report-check holds the block to
                                               the protocol's rendering
    protocol-fill PROTOCOL-x.md --discuss RUN_ID --why "…" --into REPORT.md
                                               a run the report looks at without
                                               reporting it, as a discussion block
                                               (head: protocol, run, why; its line
                                               written from them)
    protocol-fill PROTOCOL-x.md --handover --why "…" --tried "…" --into REPORT.md
                                               the protocol's end without a result:
                                               `[result]` withdrawn, a handover record
                                               under audits/handovers/, its handover
                                               block in the report (`handovers`)
    protocol-fill PROTOCOL-x.md --withdraw --why "…" [--into REPORT.md]
                                               the declaration withdrawn: `[result]`
                                               gone, Recorded results and Limitation lines
                                               reset, the run's Runs entry marked
                                               `withdrawn <date>: <why>`, its result
                                               blocks in REPORT withdrawn; audit
                                               records and findings untouched, no
                                               result released
    protocol-fill PROTOCOL-x.md --data-counts [RUN_ID]
                                               the counts a preparation run recorded
                                               (the newest by default) as the
                                               generated end of Data / scope —
                                               the files it read, its items:
                                               labelled, unlabelled, per gold value
    protocol-fill PROTOCOL-x.md --from-run [RUN_ID]   adopt the run as the result: `[result] run`
                                               in the TOML head (the declaration), Recorded results and
                                               Runs lines from its metrics.json (by default the
                                               protocol's answering run, the one every gate
                                               holds it to), written only when report-check
                                               passes on them; the Summary's Conclusion — the
                                               question's answer in two sentences, within the
                                               Limitations — stays yours

A field that is already filled is refused without --force — overwriting an
answer silently is how two truths happen.

`--from-run` is the write-back LAB-041 Generate numbers, don't retype them
asks for: twelve cold agents (cloud probes 2026-10-12) typed the number into
three protocol lines by hand, and one `--check` failed on the retyping. The
lines carry every metric key and value as the run recorded them, and the
run_id — exactly what `--check` (`recheck.cited`) holds the protocol to. Labels are matched with the †
marker and case ignored; an ambiguous label (same label in Summary and a
section) is refused with the line numbers, disambiguate with --line.

`--from-run` is also the one path by which a number becomes the result
(`adopt`): `[result].run` in the TOML head declares it reported, and
the declaration is not what makes it sound — the checks are. So the lines
are written, `report-check` runs on the written protocol (finalize clean, a
full run — no probe, no acknowledged run — a decided analysis audit of code,
promises and that run, `02_analyze.py --check` holding the written numbers;
frozen at high repeat cost), and a blocker puts the file back as it was. A
result adopted this way has passed every check labkit prescribes; the stop
hook and the pre-commit (`report-check --if-reported`) hold a hand-written or
later-changed answer to the same. A provisional number stays a sketch in
`runs/` and `output/`, never in Recorded results.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from labkit.formats import (
    attempts,
    console,
    files,
    handovers,
    promises,
    protocol_block,
    runs,
)
from labkit.checks.result_render import rendering
from labkit.formats.gate import with_way_out
from labkit.formats.repo import (
    GitError,
    adopt_command,
    audit_command,
    git_root,
    shown,
    state_text,
)
from labkit.checks import data_counts, recheck, report_blocks
from labkit.gates import report_check, report_hold
from labkit.gates import report_context
from labkit.checks.prompt_check import prompt_constants, unreadable_prompt_constants
from labkit.formats.protocol_check import (
    field_name,
    fields,
    not_owed,
    placeholder_fields,
)
from labkit.tools.protocol_edit import (
    HEAD_KEYS,
    as_filled,
    assignments_of,
    fill,
    fill_many,
    head_open,
    open_sentences,
)
from labkit.tools.protocol_result import (
    WRITTEN_AFTER_RUN,
    WRITTEN_BY_RUN,
    declared_run_dir,
    fill_prompts,
    from_run,
    render_result,
    withdraw,
    without_result,
)


def adopt(protocol: Path, before: str, after: str) -> int:
    """Adopt the result AFTER writes into PROTOCOL: write it, run report-check
    on the written protocol, and on a blocker put BEFORE back and return 1.
    The one path by which a number becomes the result: whatever stands in
    Recorded results through here has passed every check (the write-back is the
    declaration, the check is what makes it hold; a declaration the check
    refuses is no weaker kind of result, it is none). The gates at the stop
    and the commit (`report-check --if-reported`) hold the same line to a
    hand-written or later-changed answer. A check that ends in an exception
    puts BEFORE back too and re-raises: until 0.99.0 only a blocker exit
    restored the file, and the unchecked declaration stayed (audit
    2026-10-19, a check script printing a byte no codec reads). Both writes
    go whole or not at all (`files.write_atomic`): a reader, or the next
    check, sees the protocol as it was or as proposed, never half of
    either; the check is told it holds the proposal (`report_context.PROPOSED`)."""
    files.write_atomic(protocol, after)
    try:
        rc = report_check.report_check(
            protocol.parent, protocol, state=report_context.PROPOSED, text=after
        )
    except BaseException:
        files.write_atomic(protocol, before)
        raise
    if rc == 0:
        return 0
    files.write_atomic(protocol, before)
    # the discussion owes a report review, which `attempts.begin` refuses
    # while the area's evidence is gone (pilot t60)
    lost = report_hold.lost_evidence(protocol)
    mention = (
        f"a report cannot discuss this run now — {lost.fix}"
        if lost is not None
        else f"a report that mentions this run without adopting it discusses it "
        f"— `{report_blocks.discuss_command(shown(protocol, Path.cwd()), '<run_id>', '<REPORT>')}` "
        f"— and leaves the question open; the run's numbers are not the result"
    )
    print(
        f"protocol-fill: not adopted — report-check refuses the written result "
        f"(above); {protocol.name} is as it was. Pass the checks first, or leave "
        f"the number a sketch in runs/ (an exploration reports no result). A "
        f"refusal is a finding to report, not an obstacle to route around: "
        f"{mention}."
    )
    return 1


def _write_back(args: argparse.Namespace, text: str) -> int:
    """`--from-run`: the number from the run's metrics.json into the protocol,
    adopted as the result only when report-check passes on it (`adopt`)."""
    protocol = args.protocol.resolve()
    try:
        new, filled, run_id = from_run(
            text,
            protocol.parent,
            None if args.from_run == "newest" else args.from_run,
            force=args.force,
        )
    except ValueError as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    print(
        f"filled from run {run_id}: {', '.join(filled) or 'nothing (all written already)'}"
        f" — adopting as the result:"
    )
    rc = adopt(protocol, text, new)
    if rc == 0:
        _name_yours(
            new, protocol.parent, recheck.chosen_run(protocol.parent, new, run_id)
        )
    return rc


def _name_yours(text: str, area: Path, run: Path) -> None:
    """After an adopted write-back: the after-run fields still open, which
    the author writes (Conclusion: the question's answer in two sentences within
    the Limitations; Raw output from the rows), and the run's output files — the
    post hook asked for Raw output only after the commit, and two of three
    cold agents filled it in a second round (sandbox, 2026-10-21). A field
    this protocol does not owe (`not_owed`: Raw output without a model) is
    not named."""
    spared = not_owed(text)
    open_ = [
        (n, label)
        for n, label in placeholder_fields(text)
        if label in WRITTEN_AFTER_RUN and label not in spared
    ]
    if not open_:
        return
    outputs = runs.read_outputs(run) or []
    where = ", ".join(shown(o.path, area) for o in outputs) or f"{shown(run, area)}/"
    print(f"still yours, after the run (its rows: {where}):")
    for n, label in open_:
        print(f"{n:4d}  {label}")


def _list_open(text: str) -> int:
    """`--list`: every open field, the TOML head's placeholders (`HEAD_KEYS`)
    and open promise sentences first; then, each under its own line, the fields `--from-run`
    writes and the after-run fields the author writes. Listed among the rest
    they read as owed before the run: cold agents filled them with "pending
    run" or "filled after the run", and the write after the run was then
    refused without --force (cloud 2026-10-14, sandbox 2026-10-21)."""
    sentences: list[tuple[int | None, str]] = [
        (n, f"{label}  (TOML head: this promise in one sentence)")
        for n, label in open_sentences(text)
    ]
    head: list[tuple[int | None, str]] = [
        (
            n,
            f"{label}  (TOML head: "
            f"{' | '.join(choices) if choices else 'the alias from models.toml'})",
        )
        for label, (key, choices) in HEAD_KEYS.items()
        if (n := head_open(text, key)) is not None
    ]
    spared = not_owed(text)
    holes = (
        head
        + sentences
        + [(n, label) for n, label in placeholder_fields(text) if label not in spared]
    )
    spare = [(n, label) for n, label in placeholder_fields(text) if label in spared]
    if not holes:
        print("no placeholder fields left")
    after = WRITTEN_BY_RUN + WRITTEN_AFTER_RUN
    groups = (
        (None, [(n, label) for n, label in holes if label not in after]),
        (
            "after the run — `protocol-fill <PROTOCOL> --from-run` writes these; leave them:",
            [(n, label) for n, label in holes if label in WRITTEN_BY_RUN],
        ),
        (
            "after the run — yours, once its rows exist (`--from-run` names them); leave them now:",
            [(n, label) for n, label in holes if label in WRITTEN_AFTER_RUN],
        ),
        (
            "not owed by this protocol (its kind and model) — leave or delete them:",
            spare,
        ),
    )
    for title, group in groups:
        if title is not None and group:
            print(title)
        for n, label in group:
            # a sentence the table walk cannot place is named all the same
            print(f"{n:4d}  {label}" if n is not None else f"   ?  {label}")
    return 0


def _prompts_file(protocol: Path, text: str) -> int:
    """`--prompts` on PROTOCOL: the Prompt block from the PROMPT constants
    of the area's scripts that parse — all of them or none. A constant the
    static reader cannot compute to a string (`unreadable_prompt_constants`)
    is named and nothing is written (exit 2): a block with one variant of
    two reads as filled to every gate."""
    area = protocol.resolve().parent
    unreadable = unreadable_prompt_constants(area)
    if unreadable:
        console.refuse(
            "protocol-fill",
            f"{', '.join(unreadable)} not statically readable as a string — "
            "nothing written; write the Prompt block by hand from the "
            "script's `--show`",
        )
        return 2
    try:
        new = fill_prompts(text, prompt_constants(area))
    except ValueError as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    files.write_atomic(protocol, new)
    print("filled: Prompt (from the scripts' PROMPT constants)")
    return 0


def into_report(text: str, area: Path, report: str, protocol: str) -> tuple[str, str]:
    """`--into`: REPORT with the declared result as a generated block — the
    protocol's Recorded results and Limitation lines as rendered (`report_blocks.block_body`),
    replaced in place or appended (`report_blocks.with_block`).
    PROTOCOL is the protocol's path relative to the report, the block's
    owner: its blocks are replaced whichever run they showed. (report text,
    run id). Raises ValueError without a declared run or its metrics.json,
    and on a block in REPORT that does not read."""
    run = declared_run_dir(text, area, "a report shows an adopted result only")
    body = report_blocks.block_body(rendering(area, text, run))
    return report_blocks.with_block(report, protocol, run.name, body), run.name


def _into_file(protocol: Path, text: str, report: Path) -> int:
    """`--into` on PROTOCOL: write REPORT's block when it differs, say so."""
    before = report.read_text(encoding="utf-8") if report.is_file() else ""
    try:
        new, run_id = into_report(
            text,
            protocol.resolve().parent,
            before,
            report_blocks.path_from_report(protocol, report),
        )
    except (ValueError, protocol_block.BlockError) as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    if new != before:
        files.write_atomic(report, new)
    print(
        f"{report}: the result block for run {run_id} "
        + ("written" if new != before else "unchanged — it says what its sources say")
    )
    return 0


def discuss_into(
    text: str, area: Path, report: str, protocol: str, run_id: str, why: str
) -> str:
    """`--discuss RUN_ID --why WHY --into`: REPORT with the block discussing
    RUN_ID of the protocol whose TEXT is given — its head holding PROTOCOL
    (the protocol's path relative to the report), the run and WHY, its
    line written from them (`report_blocks.with_discussion`): the block of
    that protocol and run replaced in place, or one appended; other
    discussions stay. Raises ValueError when the protocol declares RUN_ID
    as its result (the result block shows it: `--into` without
    `--discuss`), when AREA holds no `runs/<RUN_ID>/`, on a why or a head
    string the block cannot hold (`report_blocks.discussion_lines`), and on
    a block in REPORT that does not read or is there twice."""
    if protocol_block.declared_run(text) == run_id:
        raise ValueError(
            f"run {run_id} is the protocol's adopted result — an adopted result "
            f"is reported, not discussed: `--into` without `--discuss` writes its "
            f"result block"
        )
    if not runs.run_path(area, run_id).is_dir():
        raise ValueError(
            f"no runs/{run_id}/ in {area.name} — a discussion names a run of the "
            f"protocol's area"
        )
    return report_blocks.with_discussion(report, protocol, run_id, why)


def _discuss_file(
    protocol: Path, text: str, report: Path, run_id: str, why: str
) -> int:
    """`--discuss … --into` on PROTOCOL: write REPORT's discussion block of
    RUN_ID when it differs, say so."""
    before = report.read_text(encoding="utf-8") if report.is_file() else ""
    try:
        new = discuss_into(
            text,
            protocol.resolve().parent,
            before,
            report_blocks.path_from_report(protocol, report),
            run_id,
            why,
        )
    except (ValueError, protocol_block.BlockError) as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    if new != before:
        files.write_atomic(report, new)
    print(
        f"{report}: the discussion block of run {run_id} "
        + ("written" if new != before else "unchanged")
    )
    return 0


def _render_file(protocol: Path, text: str) -> int:
    """`--render` on PROTOCOL: write the rendering when it differs, say what changed."""
    try:
        new, written = render_result(text, protocol.resolve().parent)
    except (ValueError, protocol_block.BlockError) as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    if new != text:
        files.write_atomic(protocol, new)
    print(
        "rendered: "
        + (
            ", ".join(written)
            or "nothing changed — the result says what its sources say"
        )
    )
    return 0


def _list_file(text: str) -> int:
    """`--list`: the open fields, or a refusal naming an unreadable block."""
    try:
        return _list_open(text)
    except promises.PromiseError as exc:
        console.refuse("protocol-fill", str(exc))
        return 2


def _run_mode(args: argparse.Namespace, text: str) -> int | None:
    """The exit code of the mode ARGS name (--withdraw, --data-counts,
    --handover, --list, --prompts, --render, --discuss, --into, --from-run),
    or None when they name none: a field fill."""
    if args.withdraw:
        return _withdraw_file(args, text)
    if args.data_counts is not None:
        return _data_counts_file(args, text)
    if args.handover:
        return _handover_file(args, text)
    if args.list:
        return _list_file(text)
    if args.prompts:
        return _prompts_file(args.protocol, text)
    if args.render:
        return _render_file(args.protocol, text)
    if args.discuss is not None:
        return _discuss_file(args.protocol, text, args.into, args.discuss, args.why)
    if args.into is not None:
        return _into_file(args.protocol, text, args.into)
    if args.from_run is not None:
        return _write_back(args, text)
    return None


def newest_preparation(area: Path) -> Path:
    """AREA's newest completed preparation run. Raises ValueError when it
    has none."""
    prepared = [
        r
        for r in runs.completed_runs(area, with_repeats=False)
        if (cfg := runs.read_run_config(r)) is not None
        and cfg.run_kind == "preparation"
    ]
    if not prepared:
        raise ValueError(
            f"{area.name} has no completed preparation run — run scripts/00_prepare.py first"
        )
    return prepared[-1]


def _data_counts_file(args: argparse.Namespace, text: str) -> int:
    """`--data-counts`: the counts of a preparation run (ARGS.data_counts, the
    newest by default) written as the generated end of Data / scope
    (`data_counts.with_counts`), the author's words before it kept."""
    protocol = args.protocol.resolve()
    area = protocol.parent
    try:
        run = (
            newest_preparation(area)
            if args.data_counts == "newest"
            else runs.run_path(area, args.data_counts)
        )
        counts = data_counts.counts_text(run)
        value = next(
            (f.value for f in fields(text) if f.name == field_name(data_counts.FIELD)),
            None,
        )
        if value is None:
            raise ValueError(f"{protocol.name} has no `{data_counts.FIELD}` field")
        new = fill(
            text, data_counts.FIELD, data_counts.with_counts(value, counts), force=True
        )
    except ValueError as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    files.write_atomic(protocol, new)
    print(f"{data_counts.FIELD}: {counts}")
    return 0


def _withdraw_file(args: argparse.Namespace, text: str) -> int:
    """`--withdraw`: the protocol's declaration withdrawn (`protocol_result.withdraw`) and,
    with --into, the protocol's result blocks in that report
    (`report_blocks.withdraw_result_blocks`); the protocol is written last,
    so a report that does not read leaves both as they were. Names the
    steps that remain and every report still citing the run."""
    protocol = args.protocol.resolve()
    try:
        new, run_id = withdraw(text, args.why, date.today().isoformat())
        report_after: tuple[Path, str] | None = None
        if args.into is not None:
            report = args.into.resolve()
            if not report.is_file():
                raise ValueError(f"no such report: {args.into}")
            before = report.read_text(encoding="utf-8")
            after = report_blocks.withdraw_result_blocks(before, protocol, report)
            if after != before:
                report_after = (report, after)
    except (ValueError, report_blocks.ReportBlockError) as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    if report_after is not None:
        files.write_atomic(*report_after)
    files.write_atomic(protocol, new)
    area = protocol.parent
    print(
        f"withdrawn: run {run_id} is no longer the result of {protocol.name} — its "
        f"Runs entry keeps why; audit records and findings are as they were, and "
        f"nothing is released"
        + (
            f"; its result blocks left {shown(report_after[0], Path.cwd())}"
            if report_after
            else ""
        )
    )
    # the order of the way out "a wrong declaration" (ways_out.WAYS_OUT), one
    # step a line, so the decision is not skipped
    print("next, in this order:")
    print(
        f"  1. a BLOCKER that named this adoption: decide it `fixed`, naming the "
        f"withdrawal — `{audit_command(area, '--findings', protocol=protocol)}` "
        f"prints its --decide command"
    )
    print(
        f"  2. `{audit_command(area, '--mode', 'analysis', protocol=protocol)}` — the "
        f"state moved, so it audits the run that answers and follows earlier decided "
        f"BLOCKERs up; decide its findings"
    )
    print(f"  3. `{adopt_command(protocol)}` adopts the run that answers")
    root = git_root(area)
    if root is not None:
        _print_still_citing(protocol, run_id, root)
    return 0


def _handover_file(args: argparse.Namespace, text: str) -> int:
    """Write a handover without changing any audit or run evidence.

    Refuse open readable BLOCKERs and another protocol of the area that
    declares a result before writing. Bind the available audit bytes, the
    findings left open, known losses and the protocol
    (`handovers.build`); the report gets the record's handover block, the
    one of this protocol replaced in place, its result blocks in that
    report withdrawn, everything else kept (`handovers.with_handover_block`,
    `report_blocks.withdraw_result_blocks`). Other reports are not written.
    Write the immutable record first, protocol
    projection second, report last: interruption cannot grant permission
    before all three agree. No model is called and no decision is made for
    the author.
    """
    protocol = args.protocol.resolve()
    area = protocol.parent
    root = git_root(area)
    done: list[str] = []
    try:
        if root is None:
            raise ValueError("handover requires a git repository")
        report = handovers.report_destination(root, args.into)
        state = attempts.area_integrity(area)
        withdrawn = protocol_block.declared_run(text)
        new = without_result(text)
        others = [p for p in handovers.declared_results(area, root) if p != protocol]
        if others:
            raise ValueError(
                f"{others[0]}: has adopted a result; an area handed over unresolved "
                "cannot also release another protocol's result"
            )
        expected, errors = attempts.expected_evidence(area)
        account = report_check.adoption_state(area, protocol, new)
        path = handovers.new_path(area)
        record = handovers.build(
            root,
            protocol,
            new,
            report,
            path,
            why=args.why,
            tried=args.tried,
            records=state.records,
            expected=expected,
            problems=[*state.problems, *errors],
            account=account,
        )
        before = state_text(root, report, staged=False) or ""
        before = report_blocks.withdraw_result_blocks(before, protocol, report)
        written = handovers.with_handover_block(before, record, root, path)
        handovers.write_record(path, record)
        done.append(shown(path, Path.cwd()))
        if new != text:
            files.write_atomic(protocol, new)
            done.append(shown(protocol, Path.cwd()))
        report.parent.mkdir(parents=True, exist_ok=True)
        files.write_atomic(report, written)
    except (ValueError, OSError, GitError) as exc:
        # what was written before the failure stays and grants nothing until
        # all three agree; said, so a rerun is not a surprise (audit
        # 2026-10-27, third, K8)
        partly = (
            f" — written before it: {', '.join(done)}; they grant nothing until "
            "the report matches, and a rerun writes a new record beside them"
            if done
            else ""
        )
        console.refuse("protocol-fill", f"{exc}{partly}")
        return 2
    print(
        f"handover: its block in {shown(report, Path.cwd())}; "
        f"record: {shown(path, Path.cwd())}"
    )
    print(
        f"run: {account.run or 'none'} — {handovers.RUN_SENTENCE[account.state]}"
        + "".join(f"\n  {why}" for why in account.why)
    )
    if account.state == handovers.ADOPTABLE:
        print(
            "WARNING: "
            + with_way_out(
                f"nothing held the adoption of run {account.run}: a missed "
                "criterion is a result, not a reason to hand over",
                f"`labkit-adopt {shown(area, Path.cwd())} {account.run}` "
                "reports it (the adoption ends this handover)",
            )
        )
    print(
        "stage the report, protocol, handover record and all remaining audit "
        "evidence together; this releases no number and approves no audit"
    )
    if withdrawn is not None:
        _print_still_citing(protocol, withdrawn, root)
    return 0


def _print_still_citing(protocol: Path, run_id: str, root: Path) -> None:
    """After a handover withdrew RUN_ID: every report that still cites it
    (`report_hold.reports_citing`), each with the `--discuss` command that
    keeps the citation honestly — or remove it; each holds the stop and the
    commit until then. While the area's audit evidence is gone the
    discussion's review cannot run (`attempts.begin`), so the restore or
    the removal is named instead (`report_hold.lost_evidence`). Silent when
    none cites it."""
    held = report_hold.reports_citing(run_id, root)
    if not held:
        return
    here = Path.cwd()
    lost = report_hold.lost_evidence(protocol)
    if lost is not None:
        print(
            f"{len(held)} report(s) still cite the withdrawn run {run_id} and hold "
            f"the commit — {lost.fix}:"
        )
        for path in held:
            print(f"  {shown(path, here)}")
        return
    print(
        f"{len(held)} report(s) still cite the withdrawn run {run_id} and hold "
        "the commit until the citation is removed or discussed:"
    )
    for path in held:
        command = report_blocks.discuss_command(
            shown(protocol, here), run_id, shown(path, here)
        )
        print(f"  {shown(path, here)}: {command}")


def _check_data_counts_args(
    ap: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Refuse --data-counts beside another operation: it writes the end of
    Data / scope and nothing else."""
    if args.data_counts is not None and (
        args.withdraw
        or args.handover
        or args.discuss is not None
        or args.from_run is not None
        or args.list
        or args.prompts
        or args.render
        or args.into is not None
        or args.field is not None
    ):
        ap.error("--data-counts goes alone: it writes the end of Data / scope")


def _check_report_mode_args(
    ap: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Refuse incomplete or conflicting report operations before file access."""
    if args.withdraw:
        if not args.why:
            ap.error(
                "--withdraw requires --why TEXT: why the run is no longer the result"
            )
        if (
            args.handover
            or args.discuss is not None
            or args.from_run is not None
            or args.tried is not None
            or args.force
            or args.list
            or args.prompts
            or args.render
            or args.field is not None
        ):
            ap.error("--withdraw goes with --why and an optional --into REPORT only")
    elif args.handover:
        if not args.why or not args.tried or args.into is None:
            ap.error("--handover requires --why TEXT, --tried TEXT and --into REPORT")
        if args.force:
            ap.error(
                "--handover writes its block in place and keeps the rest of the "
                "report; --force does not go with it"
            )
        if (
            args.discuss is not None
            or args.from_run is not None
            or args.list
            or args.prompts
            or args.render
            or args.field is not None
        ):
            ap.error("--handover cannot be combined with another operation")
    elif args.tried is not None:
        ap.error("--tried goes with --handover")
    elif (args.discuss is None) != (args.why is None) or (
        args.discuss is not None and args.into is None
    ):
        ap.error("--discuss RUN_ID goes with --why TEXT and --into REPORT")


def main(argv: list[str]) -> int:
    """Fill fields, adopt a run, render the protocol or write a report block."""

    ap = argparse.ArgumentParser(
        prog="protocol-fill",
        description="Fill protocol fields, adopt a run or render recorded results "
        "in a protocol or report. Fields in a PROTOCOL-*.md are matched "
        "by label (never by quoting the placeholder text): "
        "`FIELD VALUE...` fills one, `LABEL=VALUE [LABEL=VALUE ...]` "
        "fills several in one call (all or nothing). --list shows what "
        "is still open.",
    )
    ap.add_argument("protocol", type=Path)
    ap.add_argument("field", nargs="?", help="field label († optional), or LABEL=VALUE")
    ap.add_argument(
        "value", nargs="*", help="the field's new value, or further LABEL=VALUE"
    )
    ap.add_argument(
        "--list", action="store_true", help="list open placeholder fields and exit"
    )
    ap.add_argument(
        "--prompts",
        action="store_true",
        help="write the Prompt block from the area scripts' PROMPT constants",
    )
    ap.add_argument(
        "--render",
        action="store_true",
        help="write the result section again from its sources for the adopted run: "
        "the Recorded results line, the Limitation lines (stray ones dropped), the Prompt block",
    )
    ap.add_argument(
        "--into",
        type=Path,
        default=None,
        metavar="REPORT",
        help="the report a block is written into (a report outside the protocol): "
        "alone, the adopted result as a generated block — Recorded results and "
        "Limitation lines as rendered; the protocol's block is replaced (also after a "
        "new run), else one is appended; with --discuss or --handover, that block",
    )
    ap.add_argument(
        "--discuss",
        default=None,
        metavar="RUN_ID",
        help="with --why and --into: write a discussion block of RUN_ID into REPORT — "
        "a run the report looks at without reporting it; the block's head holds the "
        "protocol, the run and the why, its line is written from them (replaced in "
        "place for the same protocol and run, else appended)",
    )
    ap.add_argument(
        "--why",
        default=None,
        help="one line: with --discuss what refused the adoption and what you "
        "found; with --handover what blocks, naming the protocol, no run ids; "
        "with --withdraw why the run is no longer the result",
    )
    ap.add_argument(
        "--handover",
        action="store_true",
        help="with --why, --tried and --into: withdraw the result and its result blocks in REPORT, keep a handover record of the remaining evidence and write its handover block into REPORT (in place, other text kept); other reports are unchanged; no result is released",
    )
    ap.add_argument(
        "--tried", help="with --handover: what was tried — one line, no run ids"
    )
    ap.add_argument(
        "--data-counts",
        nargs="?",
        const="newest",
        default=None,
        metavar="RUN_ID",
        help="write the counts a preparation run recorded (the newest by default) "
        "as the generated end of Data / scope: the files it read and its items — "
        "labelled, unlabelled, per gold value; the words before it stay yours; "
        "finalize holds the part to the run, so it is never typed",
    )
    ap.add_argument(
        "--withdraw",
        action="store_true",
        help="with --why (and --into REPORT): withdraw the result's adoption — "
        "[result] removed, Recorded results and Limitation lines reset, the run's Runs "
        "entry marked withdrawn with the date and why, its result blocks in REPORT "
        "withdrawn; audit records and findings untouched; no result is released, "
        "the next adoption owes a covering audit",
    )
    ap.add_argument(
        "--from-run",
        nargs="?",
        const="newest",
        default=None,
        metavar="RUN_ID",
        help="adopt the run as the result: write it as `[result] run` in the TOML head and write Recorded results and Runs lines from its metrics.json, kept only when report-check passes "
        "(without RUN_ID the protocol's answering run — the one finalize and report-check hold it to: completed, bound to its id, never a repeat); the Summary's Conclusion stays yours — the question's answer in two sentences, within the Limitations",
    )
    ap.add_argument(
        "--line",
        type=int,
        default=None,
        help="line number, when the label is ambiguous",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="overwrite a field that is already filled (with --from-run: the "
        "generated lines of the run adopted); a [result] that names another "
        "run is withdrawn first (--withdraw), never replaced",
    )
    args = ap.parse_args(argv)
    _check_data_counts_args(ap, args)
    _check_report_mode_args(ap, args)
    if not args.protocol.is_file():
        console.refuse("protocol-fill", f"no such file: {args.protocol}")
        return 2
    text = args.protocol.read_text(encoding="utf-8")
    moded = _run_mode(args, text)
    if moded is not None:
        return moded
    assignments = assignments_of(args.field, args.value)
    if not assignments:
        ap.error(
            "need FIELD and VALUE, LABEL=VALUE..., --list, --render, --into or --from-run"
        )
    if args.line is not None and len(assignments) > 1:
        ap.error("--line goes with one FIELD, not with LABEL=VALUE")
    try:
        new = fill_many(text, assignments, line_no=args.line, force=args.force)
    except ValueError as exc:  # all or nothing: the file is untouched
        console.refuse("protocol-fill", str(exc))
        return 2
    files.write_atomic(args.protocol, new)
    print("filled: " + ", ".join(as_filled(text, label) for label, _ in assignments))
    return 0


def cli() -> None:
    """Entry point for the installed `protocol-fill` command."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
