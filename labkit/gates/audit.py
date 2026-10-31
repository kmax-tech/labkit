"""labkit-audit — the agent audits of an area, through any llm backend.

    labkit-audit <AREA> --mode preflight|analysis|clarity [--protocol FILE]
                 [--model ALIAS] [--timeout S] [--out FILE]
    labkit-audit <AREA> --decide N STATUS --why REASON [--not-assessable IDS] [--record FILE]
    labkit-audit <AREA> --findings [--record FILE]
    labkit-audit <AREA> --review [--record FILE] [--again]   (`gates/decision_review`)
    labkit-audit <AREA> --report-review REPORT [--again] [--protocol FILE]
                                                     (`gates/report_review`)

The agent audit of LAB-015 Preflight audit before freezing (preflight, before freezing) and LAB-050 Analysis audit before reporting
(analysis, before a number leaves) as one command — the only runner since
0.79.0; the Claude subagent copy of the instructions is gone. The
instructions ship with the package (`experiment-preflight.agent.md`); the
files they tell the auditor to read are gathered and inlined
(`audit_prompt`) — the
area's protocol, `scripts/*.py`, `analysis/*.py`, the repo-local `lib/`
modules they import, and from the lab standard that ships with labkit
exactly the rules the instructions cite (`audit_prompt.cited_rules`):
LAB-103 The audit reads by declared scope, not by import graph,
LAB-015 Preflight audit before freezing (the scar table, the severity legend),
LAB-017 The number of audits follows the cost tier,
LAB-004 Identifiers make the intent addressable,
LAB-050 Analysis audit before reporting
— not the whole standard, which cost ~30k tokens per read and was read twice
per audit in uniagent, 2026-10-10. In MODE analysis the answering run's rows come too:
the first 50 and the last 20 lines of every output it registered, numbered,
and its `metrics.json` — the auditor has no tools, so what it is told to
look at must be on the page. One call goes through `labkit.run.llm` to the alias
the lab's `models.toml` names (`opus` by default, stamped as `claude-cli`).
Synchronous, with a timeout: on expiry the command fails, it never waits on
in the background.

Exit codes (`AUDIT_EXIT_CONTRACT`, the line --help ends with) are the
contract, made from one audit result (`audit_reply.parse`): the LAST verdict
line and the finding lines above it must count the same blockers and
warnings, else nothing is recorded and the exit is 2 — a finding withdrawn
in prose below its line left an open blocker in the record behind exit 0
(review 2026-10-20):
    0  no blocker and no warning
    1  findings to decide — a blocker OR a warning (labkit-paper benchmark,
       2026-10-06: the table-led audit found the positional-join fault only
       as a WARNING; an audit that passed on warnings would have let it by)
    2  no audit: a missing file, an unreadable report, a backend failure —
       a backend that did not answer leaves `audits/<date>-<mode>-failed.toml`
       (`failed_attempts.write_failed`): the evidence an acknowledged full run's
       LABKIT_UNFROZEN=1 rests on, since 0.99.0

The report is printed (and written to --out), and its findings are written
as data into the area — `audits/<date>-<mode>.toml`, one `[[finding]]` per
line, every one `open` (`labkit.formats.findings`); deciding each (fixed / accepted
/ false-positive, with reason; `audit_decisions`) and stamping the protocol
field stays with the human (LAB-015 Preflight audit before freezing), and `preflight`
holds the file to that. The command prints the stamp's facts — date, scope
sha, counts — to copy from, and what the call cost (`llm.last_usage()`:
prompt and output tokens, USD where the backend prices it) beside the
prompt size on stderr.

Mode `clarity` is the other reader (2026-10-09): the code-clarity agent's
area mode (`code-clarity.agent.md`) reads README, protocol and the measure
script the way a newcomer opens them and reports what that reader would
get wrong — template residue, a term before its definition, a docstring
that omits a conjunct. Static evidence: exit 1 means findings to read, it
stamps nothing and it is no proof the area is clear. Before freezing, while
the prose can still change.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
import time
from collections.abc import Generator, Sequence
from pathlib import Path

from labkit.checks.audit_binding import AuditError
from labkit.formats import (
    attempts,
    console,
    failed_attempts,
    findings,
    followup,
    protocol_block,
)
from labkit.formats.gate import GUARANTEED, WARNING, GateFinding, coded, with_way_out
from labkit.formats.repo import (
    area_path,
    audit_command,
    no_such_area,
    shown,
)
from labkit.formats.runs import completed_runs
from labkit.formats.scope_sha import (
    area_stamp,
    validation_note,
)
from labkit.formats.standard_contract import (
    PREFLIGHT_AUDIT,
    lane,
)
from labkit.gates.audit_decisions import (
    decide,
    decide_shape,
    decision_lines,
    show_findings,
)
from labkit.gates.audit_prompt import (
    ANALYSIS,
    CLARITY,
    BoundPrompt,
    Source,
    Stamp,
    bound_prompt,
    carried_of,
    decisions_moved,
    followup_size,
    gather,
    gather_clarity,
    render,
)
from labkit.gates.audit_reply import parse, parse_clarity, parse_fixes, scope_mismatch
from labkit.gates.ways_out import (
    ANSWER_AGAIN,
    AUDIT_AGAIN,
)
from labkit.run import llm, llm_backends

DEFAULT_MODEL = "opus"  # the agent's model; any alias of models.toml works
REPORT_TOKENS = 4096  # room for a report of many findings, where a backend caps
DEFAULT_TIMEOUT_S = (
    failed_attempts.ATTEMPT_TIMEOUT_S
)  # one call reads the area, the rules, the rows
MODES = (*findings.MODES, "clarity")  # the recorded modes and the readability read
#: the audit's exit contract — not `gate.EXIT_CONTRACT`: a warning is a
#: finding to decide here, so it exits 1 too (the module docstring says why)
AUDIT_EXIT_CONTRACT = (
    "exit codes: 0 no blocker and no warning, 1 findings to decide (a blocker "
    "OR a warning), 2 no audit (missing file, unreadable report, backend failure); "
    "--review (the state's, with --again too): 0 every decision reviewed is "
    "released, 1 after a draw at least one is held (a verdict other than upheld, "
    "this draw's or an earlier one's, or only --again draws said upheld), 2 no "
    "review; --report-review (the state's, with --again too): 0 the state is released "
    "(the commit counts the record once it is staged), 1 after a draw the commit "
    "holds it (a claim on it, this draw's or an earlier one's, or only --again "
    "draws saw it), 2 no review (a claimed state without --again is refused "
    "with no call)"
)


def early_for_tier(area: Path, protocol: Path, mode: str) -> list[GateFinding]:
    """One WARNING line when a preflight audit comes before the repeat cost
    asks for it: at `repeat_cost = "low"` the first run is the cheaper probe
    and ONE audit in mode analysis after it covers the preflight rows
    (LAB-017 The number of audits follows the cost tier). uniagent area 01,
    2026-10-05: two preflight audits and an analysis audit at low repeat cost, and
    the protocol itself says one after the first run would have done. A
    head this labkit cannot read says nothing here — protocol-check does."""
    if mode != PREFLIGHT_AUDIT:
        return []
    try:
        head = protocol_block.head(protocol.read_text(encoding="utf-8"))
    except protocol_block.BlockError:
        return []
    if mode in lane(head.repeat_cost).audits or completed_runs(area, with_repeats=True):
        return []
    return [
        coded(
            WARNING,
            None,
            'repeat_cost = "low" and no completed run · the first run is the cheaper '
            "probe; one audit in --mode analysis after it covers the preflight rows too",
            rule="LAB-017 The number of audits follows the cost tier",
            fix="run first, audit once",
            evidence_kind=GUARANTEED,
        )
    ]


def stamp_facts(stamp: Stamp, grades: Sequence[str], counted_notes: int) -> str:
    """The stamp summary line: date, scope sha, the findings to decide as
    the record lists them, and the notes the auditor tallied but did not
    list. The sha is `scope_sha.area_stamp`, the same a later `scope-sha`
    recomputes and the record carries as `scope_sha`. GRADES are the
    record's findings' grades in the order `--decide` numbers them (carried
    ones included); COUNTED_NOTES the notes of the auditor's verdict line —
    at repeat cost low a tally only, never listed or recorded
    (`experiment-preflight.agent.md`, LAB-017 The number of audits follows
    the cost tier), so nothing to decide."""
    b, w, n = (sum(1 for g in grades if g == grade) for grade in findings.GRADES)
    # the auditor counts notes loosely and no gate holds the tally
    # (`findings.verdict_disagrees`): fewer tallied than listed adds nothing
    unlisted = counted_notes - n
    return (
        f"{time.strftime('%Y-%m-%d')} · scope sha {stamp.sha} · {len(grades)} "
        f"findings to decide ({b} blockers, {w} warnings, {n} notes — decide "
        f"each: {findings.DECIDED_LIST})"
        + (
            f" · {unlisted} more note(s) tallied by the auditor, not listed or "
            "recorded — nothing to decide"
            if unlisted > 0
            else ""
        )
    )


def _answer_or_record(
    args: argparse.Namespace,
    argv: list[str],
    prompt: str,
    stamp: Stamp,
    block_sha: str,
    protocol: Path,
) -> tuple[str, attempts.Running]:
    """(the auditor's report, its attempt in the area's journal — the
    caller ends it with the record). The attempt, on BLOCK_SHA and the
    PROTOCOL audited (its start names both), is begun right before the
    call (`attempts.begin`: refused while another audit of the area runs
    or a record the journal or HEAD names is gone; an earlier attempt
    without an end is marked interrupted and named). When the backend does not answer (the CLI died,
    the server was down, the retries ran out) there is no audit, and the
    evidence that one was tried — on this code, these promises, with this
    much time — goes next to the records (`failed_attempts.write_failed`) before
    the AuditError that ends the command with exit 2. That file is what a
    LABKIT_UNFROZEN=1 rests on (second haiku round on 0.98.0:
    no agent started an audit, and the hatch asked for nothing). A usage
    error (an alias models.toml does not know) is not an unavailable audit
    and propagates as it is, so none is written for it.

    An answer the model did not write whole (`llm_backends.UnprovenAnswer`)
    is recorded with cause `unproven`, and from then on this state is not
    sent to this model again (`failed_attempts.stopped_attempt`): the next try is
    refused before any call."""
    stopped = failed_attempts.stopped_attempt(
        args.area, args.mode, args.model, stamp.sha, block_sha
    )
    if stopped is not None:
        raise AuditError(
            f"{stopped.path}: {args.model} did not write its {args.mode} audit of "
            f"this state whole — {stopped.error}\nlabkit-audit: no further try on "
            f"the same code, promises and model; each costs as much and was stopped "
            f"again",
            fix="audit with another alias (--model), or leave the number "
            "unreported (report-check refuses it without an audit)",
        )
    # the alias is resolved before the attempt begins: an alias models.toml
    # does not know is a usage error (KeyError), not an attempt
    room = _report_room(args.model)
    running = attempts.begin(
        args.area,
        args.mode,
        args.model,
        stamp.sha,
        block_sha=block_sha,
        protocol=protocol.name,
    )
    for note in running.notes:
        console.progress("labkit-audit", note)
    try:
        answer = llm.complete(args.model, prompt, timeout=args.timeout, max_tokens=room)
        # kept before anything reads it: an answer that does not read is
        # evidence of what the auditor said, and the end names it
        running.keep_answer(answer)
        return answer, running
    except llm_backends.UnprovenAnswer as exc:
        tried = failed_attempts.write_failed(
            args.area,
            args.mode,
            args.model,
            stamp.sha,
            block_sha,
            args.timeout,
            str(exc),
            " ".join(["labkit-audit", *argv]),
            cause="unproven",
        )
        running.end("failed", file=tried.name)
        raise AuditError(
            f"{exc}\nlabkit-audit: no audit — {args.model} did not write the answer "
            f"whole; recorded as {tried}. Do not run it again on this state: the "
            f"next try with {args.model} is refused",
            fix="audit with another alias (--model), or leave the number unreported",
        ) from exc
    except llm_backends.BackendError as exc:
        tried = failed_attempts.write_failed(
            args.area,
            args.mode,
            args.model,
            stamp.sha,
            block_sha,
            args.timeout,
            str(exc),
            " ".join(["labkit-audit", *argv]),
            cause="unavailable",
        )
        running.end("failed", file=tried.name)
        raise AuditError(
            f"{exc}\nlabkit-audit: no audit — the backend did not answer; recorded "
            f"as {tried}. A full run at high repeat cost may acknowledge it with "
            f"LABKIT_UNFROZEN=1; its number cannot be reported (report-check "
            f"refuses it)",
            fix="run the audit again when the backend answers",
        ) from exc
    except BaseException as exc:
        running.end("none", error=f"{type(exc).__name__}: {exc}")
        raise


def _report_room(alias: str) -> int | None:
    """The token cap an audit report is given: REPORT_TOKENS where the
    backend takes a cap, none where it has none (claude-cli: it sends the
    model's own output cap, 128000 for opus 5.5 on CLI 2.1.285; an answer
    past it comes back cut and resumed — `llm_backends.UnprovenAnswer`)."""
    return REPORT_TOKENS if llm.takes_max_tokens(alias) else None


#: what the audit and both reviewers refuse with exit 2 and a sentence
#: instead of a traceback: their own errors (AuditError, BackendError,
#: PromptTruncated are RuntimeErrors; FindingsError, ReviewError,
#: ReportReviewError, AttemptError, ProtocolChoiceError, PromiseError are
#: ValueErrors), git failing (RuntimeError), an alias models.toml does not
#: know (KeyError), a file gone. Each command listed its own; the report
#: review's lacked ValueError (audit 2026-10-27, third, M7).
REFUSAL_ERRORS = (ValueError, RuntimeError, KeyError, FileNotFoundError)


@contextlib.contextmanager
def journaled_answer(
    area: Path, mode: str, model: str, fingerprint: str, prompt: str, timeout: int
) -> Generator[tuple[attempts.Running, str]]:
    """A reviewer's model call as an attempt of MODE on AREA started on
    FINGERPRINT (`attempts.attempt`): the alias resolved first (an unknown
    one is a usage error, not an attempt), the attempt's notes told, the
    answer kept before anything reads it, its tokens told. The block reads
    and records the answer and ends the attempt (`Running.end`); a block
    that raises ends it `none`. The decision and the report review use it —
    the call was written twice; the audit ends its attempt across two steps
    itself (`_answer_or_record`)."""
    room = _report_room(model)
    with attempts.attempt(area, mode, model, fingerprint) as running:
        for note in running.notes:
            console.progress("labkit-audit", note)
        answer = llm.complete(model, prompt, timeout=timeout, max_tokens=room)
        running.keep_answer(answer)
        console.progress("labkit-audit", f"tokens · {llm.last_usage().describe()}")
        yield running, answer


def main(argv: list[str]) -> int:
    """Command line of `labkit-audit`: audit one area in one mode, store a
    decision the person gives on one of its findings (`--decide`), or show
    what there is to decide (`--findings`). An area path that is no
    directory is refused first, with exit 2 and the sentence every command
    uses (`repo.no_such_area`), whatever the step."""
    ap = argparse.ArgumentParser(
        prog="labkit-audit",
        description=(__doc__ or "").splitlines()[0],
        epilog=AUDIT_EXIT_CONTRACT,
    )
    ap.add_argument("area", type=area_path)
    ap.add_argument("--mode", choices=MODES)
    ap.add_argument(
        "--decide",
        nargs=2,
        metavar=("N", "STATUS"),
        help="store your decision on finding N of the newest record: STATUS "
        f"({' | '.join(s for s in findings.STATUSES if s != 'open')}), its reason "
        f"with --why (owed for {', '.join(findings.REASON_OWED)}); no audit runs",
    )
    ap.add_argument(
        "--why",
        default="",
        metavar="REASON",
        help="with --decide: why — the change for fixed, the limit for limit, the "
        "counter-evidence (file, line, value) for false-positive",
    )
    ap.add_argument(
        "--not-assessable",
        default="",
        metavar="IDS",
        help="with --decide N limitation: the promises this run does not judge, "
        "comma-separated (`quality-check-2`); without it a limit's verdicts "
        "stand, read within it",
    )
    ap.add_argument(
        "--findings",
        action="store_true",
        help="show what there is to decide: every record with an open BLOCKER and "
        "the newest, the evidence problems, and where a BLOCKER or a problem "
        "stands the --decide and handover commands; a failed audit call — a "
        "-failed.toml, or an attempt that ended without a record, with its kept "
        "answer — is named with its error and the handover until a later "
        "completed audit of its mode, protocol and promise block supersedes it, "
        "also after a code change (then it is shown as superseded; a historical "
        "call, of labkit 0.103.0 or earlier, with the audit that supersedes it); "
        "no audit runs; exit 2 on such a call, on evidence that does not read, or "
        "with no record at all",
    )
    ap.add_argument(
        "--review",
        action="store_true",
        help="a second auditor on the decisions of the newest analysis record (or "
        "--record) that owe one — a finding decided `limitation` with effect `stands`, a finding "
        "closed after a review did not uphold a decision on it, a carried finding "
        "closed false-positive: does the reported claim stand? writes "
        "audits/<minute>-review.toml",
    )
    ap.add_argument(
        "--report-review",
        type=Path,
        metavar="REPORT",
        help="a cold reader on REPORT, which discusses a run of the area (a "
        "discussion block): does it state such a run's numbers as results, or what "
        "the audits contradict? writes audits/report-reviews/<minute>-review.toml, "
        "bound to the inputs it read; report-check holds the report until a review "
        "of its state names no claim",
    )
    ap.add_argument(
        "--again",
        action="store_true",
        help="with --review or --report-review: draw once more on a state already "
        "reviewed, to see the reviewer's spread; the draw is recorded and counts — "
        "a verdict other than upheld, or a claim, holds the state like any review's "
        "— and it releases nothing: it lifts no hold an earlier review placed, and "
        "its upheld or clean verdict alone releases no decision and no report; "
        "exit: the state's, with or without --again",
    )
    ap.add_argument(
        "--record",
        type=Path,
        help="with --decide, --findings or --review: this record, not the newest",
    )
    ap.add_argument(
        "--protocol", type=Path, help="the protocol, in an area holding several"
    )
    ap.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"models.toml alias (default {DEFAULT_MODEL})",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help="seconds for the one call",
    )
    ap.add_argument("--out", type=Path, help="also write the report here")
    # before argparse: with two values it took `--effect` for the reason and
    # refused "unrecognized arguments: stands", never naming the reason
    shape = decide_shape(argv)
    if shape is not None:
        ap.error(shape)
    args = ap.parse_args(argv)
    _check_args(ap, args)
    if not args.area.is_dir():
        # before any step: `--findings` from a subdirectory with the
        # repo-relative path read "no audit record yet", `--review` a
        # traceback (SAB round 1, 2026-10-29)
        console.refuse("labkit-audit", no_such_area(args.area))
        return 2
    if args.mode is None:
        return _without_audit(args)
    if args.mode == CLARITY:
        return _clarity(args)
    try:
        reading = gather(args.area, args.protocol)
        protocol, code = reading.protocol, reading.code
        for finding in early_for_tier(args.area, protocol, args.mode):
            console.progress("labkit-audit", finding.line)
        bound = bound_prompt(args.mode, args.area, reading)
        console.progress(
            "labkit-audit",
            f"{args.mode} · {protocol.name} · {len(code)} code file(s) "
            f"in full, {len(bound.indexed)} indexed · "
            f"{args.model} · {len(bound.prompt) // 1000} kB",
        )
        report, running = _answer_or_record(
            args, argv, bound.prompt, bound.stamp, bound.state.block_sha, protocol
        )
    except REFUSAL_ERRORS as exc:
        console.refuse("labkit-audit", str(exc).strip(chr(39)))
        return 2
    try:
        return _record(args, report, running, bound)
    finally:
        if not running.ended:
            running.end("none", error="the command ended before the record")


def _record(
    args: argparse.Namespace,
    report: str,
    running: attempts.Running,
    bound: BoundPrompt,
) -> int:
    """Read REPORT, written to BOUND's prompt, write its record (bound to
    what BOUND shows) and end RUNNING with it; print what the
    person decides. Exit 1 on a blocker or a warning, 0 on none, 2 when the
    report does not read, its FIX lines do not (`audit_reply.parse_fixes`), or a shown
    decision changed while the auditor read it (`audit_prompt.decisions_moved`) — the
    attempt ends without a record, said why and with the way on
    (`_refusal_without_record`)."""
    console.progress("labkit-audit", f"tokens · {llm.last_usage().describe()}")
    try:
        result = parse(report)
        fixes = parse_fixes(report, bound.earlier_repairs)
        moved = decisions_moved(bound.earlier_repairs.blockers, args.area)
        if moved:
            raise AuditError(
                f"the decision on {', '.join(moved)} changed while the auditor read "
                f"it — its verdict would judge a decision that no longer stands",
                fix=AUDIT_AGAIN,
            )
    except (AuditError, ValueError) as exc:
        running.end("none", error=str(exc))
        console.refuse("labkit-audit", _refusal_without_record(exc, args, running))
        return 2
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    b, w, _ = result["verdict"]
    try:
        recorded = findings.write(
            args.area,
            args.mode,
            args.model,
            bound.state.scope_sha,
            bound.state.block_sha,
            result["verdict"],
            result["findings"],
            registration=bound.state.registration,
            run_id=bound.state.run_id,
            shown_sha=bound.state.shown_sha,
            fix_verdicts=fixes,
            carried=carried_of(bound.earlier_repairs, fixes),
            followup_size=followup_size(bound.earlier_repairs)
            if args.mode == ANALYSIS
            else None,
        )
    # verdict and finding lines disagree, or a finding's field does not read
    except ValueError as exc:
        running.end("none", error=str(exc))
        console.refuse("labkit-audit", _refusal_without_record(exc, args, running))
        return 2
    running.end("record", file=recorded.name)
    _stamp_report(args.area, args.mode, bound.stamp, result["verdict"], recorded)
    # the auditor lists what it read in full; the indexed modules are the
    # caller's to add before the list is held to the stamp (LAB-103 The audit reads by declared scope)
    listed_scope = result["scope"] + [str(p) for p in bound.indexed]
    for gap in scope_mismatch(args.area, listed_scope, bound.stamp.files):
        print(f"scope WARNING: {gap}", file=sys.stderr)
    # last, on stdout after the report: what the person acts on. On stderr
    # it came out before the buffered report in a pipe, and `| tail` cut it
    # off (sandbox judge probes, 2026-10-21)
    print()
    for line in decision_lines(
        findings.read(recorded), args.area, report, args.protocol
    ):
        print(line)
    for line in fix_lines(bound.earlier_repairs.blockers, fixes):
        print(line)
    return 1 if b or w or carried_of(bound.earlier_repairs, fixes) else 0


def _refusal_without_record(
    exc: AuditError | ValueError, args: argparse.Namespace, running: attempts.Running
) -> str:
    """The refusal `_record` prints when it writes no record (RUNNING ends
    `none`): EXC's cause and the ways on — the first by the cause, then the
    answer RUNNING kept, then `labkit-audit <area> --findings`, which names
    the call and offers the handover. The first way by the cause: an
    AuditError's own fix (each raised in `_record` carries one); for an
    area record that does not read (FindingsError, from `audit_prompt.decisions_moved`)
    `findings.record_way`, which names `--findings` itself; for any other
    ValueError — the answer's lines, refused by `findings.write`: the
    verdict count, a finding's field — ANSWER_AGAIN. ARGS gives the area
    and the protocol the command was run with."""
    answer = args.area / findings.DIR / running.answer
    kept = f"the answer is kept in {shown(answer, Path.cwd())}"
    listing = (
        f"`{audit_command(args.area, '--findings', protocol=args.protocol)}` "
        "names this call and offers the handover"
    )
    if isinstance(exc, AuditError):
        ways = [exc.fix, kept, listing] if exc.fix else [kept, listing]
        return with_way_out(exc.why, "; ".join(ways))
    if isinstance(exc, findings.FindingsError):
        return with_way_out(
            str(exc), f"{findings.record_way(args.area, args.protocol)}; {kept}"
        )
    return with_way_out(str(exc), f"{ANSWER_AGAIN}; {kept}; {listing}")


def fix_lines(
    earlier: list[followup.Member], fixes: list[findings.FixVerdict]
) -> list[str]:
    """One line per earlier decided BLOCKER the audit was shown: its
    verdict, or that it has none and its follow-up stays unchecked."""
    given = {v.ref: v for v in fixes}
    out = []
    for e in earlier:
        v = given.get(e.ref)
        out.append(
            f"  fix {e.ref}: {v.verdict} — {v.why}"
            if v
            else f"  fix {e.ref}: no verdict — its follow-up stays unchecked"
        )
    return out


def _stamp_report(
    area: Path, mode: str, stamp: Stamp, verdict: tuple[int, int, int], recorded: Path
) -> None:
    """What the person copies and watches, on stderr after the report: the
    stamp's facts, counted from the record written (RECORDED); in mode
    preflight the head field that names the record
    (`preflight_audit = "<record>"`, once every finding is decided); and a
    NOTE when the code changed while the auditor read it."""
    grades = [f.grade for f in findings.read(recorded).findings]
    print(f"\nstamp: {stamp_facts(stamp, grades, verdict[2])}", file=sys.stderr)
    if mode == PREFLIGHT_AUDIT:
        print(
            f'head: preflight_audit = "{recorded.name}" — once every finding is '
            f"decided, name this record in [protocol] and freeze "
            f"(LAB-015 Preflight audit before freezing)",
            file=sys.stderr,
        )
    now = area_stamp(area)[0]
    if now != stamp.sha:
        print(
            f"stamp NOTE: the code changed while the auditor read it — it saw scope "
            f"sha {stamp.sha}, the code now stamps {now}; the record names {stamp.sha}, "
            f"and the change owes its own audit{validation_note(area)}",
            file=sys.stderr,
        )


def _check_args(ap: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Exactly one of --mode (audit), --decide (store a decision), --findings
    (show what there is to decide), --review (a second auditor on the
    decisions) and --report-review (a cold reader on a report); --record
    never with --mode or --report-review. A usage error exits 2 through
    argparse."""
    chosen = [
        args.mode is not None,
        args.decide is not None,
        args.findings,
        args.review,
        args.report_review is not None,
    ]
    if sum(chosen) != 1:
        ap.error(
            "give --mode to audit, --decide N STATUS --why REASON to decide, --findings "
            "to show what there is to decide, --review to review the decisions, or "
            "--report-review REPORT to read a finished report — one of them"
        )
    if args.record is not None and (
        args.mode is not None or args.report_review is not None
    ):
        ap.error("--record goes with --decide, --findings or --review")
    if (args.why or args.not_assessable) and args.decide is None:
        ap.error("--why and --not-assessable go with --decide")
    if args.again and not (args.review or args.report_review is not None):
        ap.error("--again goes with --review or --report-review")


def _without_audit(args: argparse.Namespace) -> int:
    """`--decide`, `--findings`, `--review` or `--report-review`: the calls
    that run no audit of the area (the reviews are one model call each: on a
    record's decisions, `decision_review.review`; on a finished report,
    `report_review.review_report`)."""
    if args.report_review is not None:
        from labkit.gates.report_review import review_report

        return review_report(
            args.area,
            args.report_review,
            args.protocol,
            args.model,
            args.timeout,
            args.out,
            again=args.again,
        )
    if args.review:
        from labkit.gates.decision_review import review

        return review(
            args.area,
            args.protocol,
            args.record,
            args.model,
            args.timeout,
            args.out,
            again=args.again,
        )
    if args.decide is not None:
        return decide(
            args.area,
            args.decide,
            args.why,
            args.record,
            args.not_assessable,
            args.protocol,
        )
    return show_findings(args.area, args.record, args.protocol)


def _clarity(args: argparse.Namespace) -> int:
    """The clarity reading: README, protocol, measure script → findings to
    read. Exit 1 on any finding, 0 on none, 2 on no reading; no stamp, no
    scope — static evidence, not a gate."""
    try:
        protocol, files = gather_clarity(args.area, args.protocol)
        prompt = render(
            CLARITY,
            args.area,
            protocol,
            files,
            None,
            source=Source(
                protocol.read_text(encoding="utf-8"),
                lambda p: p.read_text(encoding="utf-8"),
            ),
        )
        console.progress(
            "labkit-audit",
            f"clarity · {protocol.name} · README + {files[1].name} · "
            f"{args.model} · {len(prompt) // 1000} kB",
        )
        report = llm.complete(
            args.model,
            prompt,
            timeout=args.timeout,
            max_tokens=_report_room(args.model),
        )
        console.progress("labkit-audit", f"tokens · {llm.last_usage().describe()}")
        result = parse_clarity(report)
    except (
        AuditError,
        llm_backends.BackendError,
        llm_backends.PromptTruncated,
        KeyError,
    ) as exc:
        # KeyError: llm.resolve on an alias models.toml does not know
        console.refuse("labkit-audit", str(exc).strip(chr(39)))
        return 2
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    n, m = result["findings"], result["wrong"]
    print(
        f"\nclarity: {n} finding(s), {m} would be answered wrong — a reading, "
        f"not a gate; fix what a newcomer would get wrong before freezing",
        file=sys.stderr,
    )
    return 1 if n else 0


def cli() -> None:
    """Entry point for the installed `labkit-audit` command."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
