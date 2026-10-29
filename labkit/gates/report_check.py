"""report-check — the gate after the last step, before a number leaves the area.

    report-check <AREA> [--protocol PROTOCOL-*.md]
    report-check --if-reported [--staged] PATH ...  every protocol of an area
                                                    a path touches whose head
                                                    declares a result, and every
                                                    report among PATHS citing a
                                                    run (the stop hook; with
                                                    --staged the pre-commit: the
                                                    head and the report as the
                                                    index holds them, and the
                                                    area's tree must equal the
                                                    index)

Exit codes: 0 clean, 1 a blocker, 2 usage error.

This module holds the protocol's release stations and the entry points
(`if_reported`, `hold_declared`, `main`): the order and the conditions of
what runs stand here. Finding the reports a change reaches and what holds
each lives in `report_hold`, which `if_reported` calls after the protocols.

`finalize` holds the run before the number is written back and comes
before the analysis audit; report-check comes last and holds the whole
chain, at every repeat cost (why each station holds what it holds:
docs/notes/2026-10-19-hooks-and-report-check.md):

  0. protocol       choose the protocol; read its head, declaration and
                    answering run into Checked. No protocol or unreadable
                    context ends with exit 2.
  1. declaration    report an unreadable `[result]` as a blocker.
  2. registration   where the lane freezes: the flag, required fields and
                    promise tables must hold. Otherwise, where the lane
                    owes registration: check the commit of the first
                    measurement. At low repeat cost no freeze or preflight audit
                    is owed (LAB-017 The number of audits follows the cost tier).
  3. finalize       run finalize and name its blockers.
  4. full run       with an answering run: require a measurement without
                    an unfrozen acknowledgement (`runs.unreportable`).
  5. analysis       where the lane owes an analysis audit: a decided record
                    must cover the current code, promises, answering run
                    and shown evidence; while the area's audit evidence is
                    gone the blocker names the loss and its restore, since
                    labkit-audit starts no audit then. Check the generated
                    Recorded results and Limit lines against that run and
                    those records.
  6. recomputation  always run `scripts/02_analyze.py --check` under the
                    repo's interpreter: its outputs, metrics and cited
                    result must agree (LAB-041 Generate numbers, don't retype them).
  7. decisions      where the lane owes an analysis audit: check reviews
                    of accepted `stands` decisions. An unconfirmed BLOCKER
                    blocks; an unconfirmed WARNING warns.
  8. report         where the head registers a report file (`report`) and
                    that file is delivered: it carries the result block of
                    the declared run or the protocol's handover block
                    (`report_hold.report_owed`).
  9. summary        1 if any stage found a blocker, otherwise 0.

`report_check` lists the stages and their conditions in this order. A
blocker does not stop later applicable stages. It reads and runs checks;
it does not itself write the protocol or run records. Checked supplies
this gate's protocol text, head, declaration and selected answering run.
The nested finalize gate and the analysis script read their own inputs;
this is not a single file snapshot across all stages. The output names
the file state whose declaration was checked.

`--if-reported` is the gate that runs unasked: `claude-hook stop` runs it
on every changed path and sends the agent back once per stop (a hook that
never let a session end would trap it — `stop_hook_active`), the stamped
pre-commit runs it on every staged path and holds. So the commit is the
gate the agent cannot pass; the stop is the one it hears first. Both
select every protocol of every area one of those paths lies in
(`affected_protocols`). It checks those whose head declares a result
(`[result] run`, `protocol_block.declared_run`), written by
`protocol-fill --from-run`. The area, not the protocol
alone: a script edited after the answer was written back changes what the
analysis audit saw and what `--check` recomputes. A protocol declaring no
result owes nothing here but its registered report: an exploration ends
with no reported result, probes or not; a `[result]` that does not read
is held and blocks. A protocol whose head registers a report file
(`report = "REPORT.md"`) owes that file its result once the file is
delivered — in the tree at the stop, in the index at the commit —: the
result block of the declared run or the protocol's handover block,
declared or not (`report_hold.report_owed`, `hold_registered`); a
report with the run id removed, a run id typed in, or a discussion block
releases nothing (pressure pilot 2026-10-29: three of six agents deleted
the run id after the hook refused the citation, and the commit passed).
The protocols registering a file among the paths are selected too
(`report_hold.registering_protocols`): the report at the repository root
lies in no area.

A report outside the protocol — a Markdown file among the paths that
cites a run, not a protocol, not under `runs/` or `data/`, tested at its
own path (`report_files`) — is held too (`hold_report`): a report that is
a symbolic link, wherever it points, is refused alone, one blocker naming
the copy that replaces it (`link_gap`: the file a link points to can lie
where no report is held), and its other checks wait for that copy; else
each generated result block equals what the
protocol it names declares now — the block's run — and renders for it
(`report_blocks.block_gaps`, written by
`protocol-fill --into`), each token that reads as a run id names a run of
the repo (`report_blocks.cited_gaps`) — blockers; the protocol declaring a
cited run joins the protocols the stations hold (`held_by_reports`); a
number outside every block is a warning, no source being assigned to it
(`report_blocks.unsourced_numbers`, static evidence). The paths given,
and what a changed declaration reaches: a protocol among them whose
declaration differs from HEAD's (`newly_declared`) holds every committed
report citing that run (`committed_reports`, `reached_reports`) — the
number such a report shows became a declared result in this state, so it
owes its block now (the two-step commit of the sixth haiku round, t5,
2026-10-23). An old citation of a run whose declaration did not change
reopens nothing.

`--staged` is the pre-commit's form. The commit holds the index, the
stations read the working tree: so the declaration is read from the index
(`repo.state_text` — an answer only the tree carries is not in the commit), and
an area whose tree differs from the index (`tree_differs`: a file modified
and not staged, or untracked) is a blocker before any station runs, since
the check would judge a state the commit does not hold.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from labkit.formats.gate import GUARANTEED
from labkit.formats.runs import RunDir
from labkit.formats.gate import (
    BLOCKER,
    EXIT_CONTRACT,
    WARNING,
    Findings,
    GateFinding,
    blocker,
)
from labkit.formats.answering_run import first_measurements
from labkit.formats.protocol_history import (
    registration_differences,
    registrations_as_first_measured,
    registration_in_commit,
)
from labkit.formats import (
    attempts,
    console,
    findings,
    followup,
    promises,
    protocol_block,
    reviews,
    runs,
)
from labkit.checks.audit_binding import (
    AuditError,
    analysis_now,
    audited_run,
    check_evidence,
    covering_analysis,
    dependency_pieces,
)
from labkit.checks.result_render import render_gaps, rendering
from labkit.gates.finalize import finalize_area
from labkit.gates.preflight import area_test_python, contract_hint
from labkit.gates import ways_out
from labkit.gates.report_hold import (
    Sources,
    discussing_reports,
    held_by_reports,
    hold_report,
    reached_reports,
    registering_protocols,
    repo_sources,
    report_files,
    report_owed,
    tree_differs,
)
from labkit.formats.protocol_check import check_fields, conclusion_written
from labkit.formats.repo import (
    adopt_command,
    area_path,
    area_protocols,
    audit_command,
    choose_protocol,
    commit_known,
    decide_command,
    git_root,
    indexed_protocols,
    layout_root,
    measure_command,
    no_such_area,
    protocol_links,
    shown,
    state_text,
    withdraw_command,
)
from labkit.formats.runs import read_run_config, recorded_commit, unreportable
from labkit.formats.scope_sha import areas_touched
from labkit.formats.standard_contract import (
    ANALYSIS_AUDIT,
    CHECK_FLAG,
    CHECK_SCRIPT,
    check_command,
    lane,
)

#: which file state the declaration (the answer line) is read from — named
#: in the output, so a reader knows what was held. The stations read the
#: working tree in every case; the caller makes the tree that state: the
#: pre-commit holds the area's tree equal to the index (`tree_differs`), the
#: adoption writes the proposal into the tree and puts it back on refusal
#: (`protocol_fill.adopt`)
TREE = "working tree"
INDEX = "index"
PROPOSED = "proposed protocol"


@dataclass(frozen=True)
class Checked:
    """The context of one check, built once (`checked`) and read by every
    station: one protocol text, one head, one answering run, one named file
    state. This gate's checks use the same declaration and run choice.
    The nested finalize gate and analysis script read their own inputs.

    Attributes:
        area: The area, resolved.
        repo: Where the area's layout starts (`repo.layout_root`).
        protocol: The protocol file.
        text: The protocol as STATE holds it — the declaration is read here.
        head: Its TOML head.
        state: TREE, INDEX or PROPOSED.
        declared: The run the head declares as the reported result
            (`protocol_block.declared_run`, `[result] run`), None for an
            exploration — or for a `[result]` that does not read, which
            `declaration_gap` then names (a blocker: the commit must not
            carry it).
        declaration_gap: Why the declaration does not read, or None.
        run: The answering run (`audit_binding.audited_run`, through
            `answering_run.bound_answering_run`: the one choice every gate holds the
            protocol to), or None.
        why: Why there is no answering run, when RUN is None.
    """

    area: Path
    repo: Path
    protocol: Path
    text: str
    head: protocol_block.Head
    state: str
    declared: str | None
    declaration_gap: str | None
    run: Path | None
    why: str


def checked(
    area: Path, protocol: Path, *, state: str = TREE, text: str | None = None
) -> Checked:
    """The context of one check: TEXT is the protocol as STATE holds it
    (the working tree when None). Raises `protocol_block.BlockError` on an
    unreadable head, `AuditError` out of the run choice."""
    if text is None:
        text = protocol.read_text(encoding="utf-8")
    head = protocol_block.head(text)
    declared, declaration_gap = _declaration(text)
    run, why = audited_run(area, protocol, text)
    return Checked(
        area=area.resolve(),
        repo=layout_root(area),
        protocol=protocol,
        text=text,
        head=head,
        state=state,
        declared=declared,
        declaration_gap=declaration_gap,
        run=run,
        why=why,
    )


#: how long `--check` may take inside the gate (audit 2026-10-15: no limit)
CHECK_TIMEOUT_S = 300.0


def check_analysis_script(area: Path, repo: Path) -> str | None:
    """Why the area's check (`standard_contract.check_command`: the analysis
    script's `--check`, stamped by every skeleton) does not pass, or None:
    no script, or a nonzero exit with the last lines it printed."""
    script = CHECK_SCRIPT
    if not (area / script).is_file():
        return (
            f"no {script} — the check that holds the note to the run is owed; "
            f"every skeleton stamps it (an area stamped at low repeat cost before 0.100.0 "
            f"carried the check inside 01_measure.py: stamp "
            f"labkit/templates/analyze-quick-script.py.template beside it)"
        )
    try:
        r = subprocess.run(
            [area_test_python(repo), *check_command(area)],
            cwd=repo,
            capture_output=True,
            text=True,
            errors="replace",  # the tail is quoted, not parsed: a byte no
            # codec reads must not raise out of the gate (audit 2026-10-19)
            timeout=CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"{script} --check did not finish in {CHECK_TIMEOUT_S:g} s"
    if r.returncode == 0:
        return None
    tail = (r.stderr.strip() or r.stdout.strip() or "no output").splitlines()[-3:]
    return f"{script} --check exits {r.returncode}: " + " | ".join(tail)


def _declaration(text: str) -> tuple[str | None, str | None]:
    """(the declared run, None) or (None, why the `[result]` table does not read)."""
    try:
        return protocol_block.declared_run(text), None
    except protocol_block.BlockError as exc:
        return None, str(exc)


def freeze_gaps(ctx: Checked) -> list[GateFinding]:
    """Why the freeze does not hold — the flag unset, or a must
    gap protocol-check names (the stamp's `<…>` promise sentences among them)."""
    name = ctx.protocol.name
    fields = contract_hint(ctx.protocol)
    gaps = (
        []
        if ctx.head.frozen
        else [
            blocker(
                f"{name}: not `frozen = true` — a reported number owes the freeze",
                fix=f"freeze it: `preflight {shlex.quote(shown(ctx.area, Path.cwd()))}` "
                f"clean, the preflight audit run and decided "
                f"(`{audit_command(ctx.area, '--mode', 'preflight', protocol=ctx.protocol)}`), "
                f"then `frozen = true`",
            )
        ]
    )
    report = check_fields(ctx.text)
    gaps += [
        blocker(f"{name}: {label}", fix=f"write the field; {fields}")
        for label in report.missing_must
    ]
    # a must field still holding its `<…>` placeholder passed here while
    # protocol-check and preflight refused it (audit 2026-10-15)
    gaps += [
        blocker(
            f"{name}: line {n}: {label} still a placeholder",
            fix=f"replace it with this protocol's own text; {fields}",
        )
        for n, label in report.must_holes
    ]
    return gaps


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
            fix="name the protocol it replaces",
        )
    hits = protocol_block.repo_protocol_ids(ctx.protocol).get(pid, [])
    if len(hits) != 1:
        return blocker(
            f"[replaces] protocol = {pid} names "
            + ("no protocol of this repo" if not hits else f"{len(hits)} protocols"),
            fix="name the one protocol of this repo it replaces, kept as it is",
        )
    circle = _replacement_circle(str(ctx.head.id), hits[0])
    if circle:
        return blocker(
            f"the replacements run in a circle ({circle})",
            fix="let each name the one before it",
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
            f'{s(x)}, to = {s(y)}, why = "…"',
        )
        for (what, x, y), old_where in computed.items()
        if (what, x, y) not in listed
    ]
    against = "; ".join(where for _, where in olds)
    out += [
        blocker(
            f"declares a change the registrations do not show: {what} {x} → {y} "
            f"(the predecessor {against}, this protocol {new_where})",
            fix="remove that [[replaces.change]]",
        )
        for what, x, y in sorted(listed - set(computed))
    ]
    return out


def _predecessor_open(ctx: Checked, pred: Path) -> list[GateFinding]:
    """PRED's BLOCKERs still `open`, each with the `--decide` that defers it
    to this protocol — they are decided before the replacement reports."""
    try:
        held = findings.open_blockers(findings.area_records(pred.parent))
    except findings.FindingsError as exc:
        return [
            blocker(
                f"the predecessor's audit records do not read: {exc}",
                fix=findings.record_way(pred.parent, pred),
            )
        ]
    return [
        blocker(
            f"its predecessor's BLOCKER is still open — {u.line}",
            fix="decide it first: `"
            + decide_command(
                pred.parent,
                u.number,
                "deferred",
                f"replaced by {ctx.head.id}: <why>",
                u.record.path.name,
                protocol=pred,
            )
            + "`",
        )
        for u in held
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


def registration_gaps(ctx: Checked) -> list[GateFinding]:
    """The committed registration where the lane owes it instead of the freeze
    (seconds): the registration stood in the protocol as committed at the
    first measurement — the commit its record names (`runs.recorded_commit`)
    — at each run `answering_run.first_measurements` names: git's history
    orders the measurements, a run id (local time) only those at one
    commit; on diverged history, or for a run whose commit cannot be
    placed, more than one is first and each is held. Blockers per run: it
    recorded no commit, the repository does not hold that commit, the
    commit does not hold the protocol (nothing stood before the number),
    the fields the lane owes were not written there
    (`protocol_history.registration_in_commit`). runlog's start gate holds
    a first measurement to the same registration at HEAD
    (`start_check._committed_registration`), so this station catches what
    got past it — a commit rewritten after the run, a run started outside
    runlog; what stood before the number is what the commit holds. Outside a repository
    a warning, as the provenance station's (`run_record_check.provenance_findings`).
    Empty without a measurement (finalize names the missing run) and
    without a stamped id. Why (labkit-paper area 09, fifth haiku round,
    2026-10-22): none of the three labkit agents had committed criterion
    and admissibility condition before the first measurement."""
    if ctx.head.id is None:
        return []
    root = git_root(ctx.protocol)
    first = first_measurements(ctx.area, ctx.head.id, root)
    if not first:
        return []
    if root is None:
        return [
            GateFinding(
                WARNING,
                "not a git repository — the registration cannot be held to the "
                "commit of the first measurement",
                evidence_kind=GUARANTEED,
            )
        ]
    return [gap for rd in first for gap in _registration_at(ctx, root, rd, len(first))]


def _registration_at(
    ctx: Checked, root: Path, rd: RunDir, held: int
) -> list[GateFinding]:
    """`registration_gaps` for RD, one of HELD first measurements, in the
    repository ROOT."""
    cfg = rd.config
    assert cfg is not None, "first_measurements names read runs only"
    at = f"the first measurement {rd.dir.name}"
    # several are first on diverged history or beside a run git cannot
    # place: without the why, a reader takes the second blocker for a bug
    among = "" if held == 1 else f"; one of {held} that git's history does not order"
    commit = recorded_commit(cfg)
    # what stood before the number cannot be repaired afterwards: a new
    # registration, committed before its own first run, or the handover
    anew = (
        "when the missing choices can be made on grounds the new registration "
        f"states, {ways_out.register_anew(str(ctx.head.id))}; else "
        f"{ways_out.HANDOVER}"
    )
    if commit is None:
        return [
            blocker(
                f"{at} recorded no commit ({cfg.git!r}{among}) — the registration "
                f"cannot be held to what stood before the number (LAB-003 No run "
                f"without an intent paragraph)",
                fix=anew,
            )
        ]
    if not commit_known(root, commit):
        return [
            blocker(
                f"{at} ({commit}{among}) recorded a commit this repository does not "
                f"hold (a rewritten history, a shallow clone) — neither its place "
                f"among the measurements nor the registration it stood on can be "
                f"read (LAB-003 No run without an intent paragraph)",
                fix="fetch that commit from a clone that has it (`git fetch "
                "--unshallow` in a shallow clone)",
            )
        ]
    missing = registration_in_commit(ctx.protocol, commit, ctx.head.kind)
    if missing is None:
        return [
            blocker(
                f"{ctx.protocol.name} was not committed at {at} ({commit[:12]}{among}) "
                f"— nothing stood before the number; the registration is what the "
                f"commit of the first measurement holds (LAB-003 No run without an "
                f"intent paragraph)",
                fix=anew,
            )
        ]
    if missing:
        return [
            blocker(
                f"the registration as committed at {at} ({commit[:12]}{among}) lacks "
                f"{', '.join(missing)} — the registration is what the commit of "
                f"the first measurement holds, not what the tree says now, so "
                f"that measurement is exploratory; a new run on the same data does "
                f"not restore what stood before the number (LAB-003 No run without "
                f"an intent paragraph)",
                fix=anew,
            )
        ]
    return []


def analysis_audit_gap(ctx: Checked) -> GateFinding | None:
    """Why no decided analysis record covers the code, the promise
    block, the answering run and what the audit was shown of it as they are
    now, as a blocker with its way out, or None. Without an answering run
    there is nothing the audit could be held to. When no record covers and
    the area's audit evidence is gone (`attempts.evidence_gaps`: a file an
    attempt of any mode ended with deleted, a journal cut), labkit-audit
    starts no audit (`attempts.begin`), so the blocker names the loss and
    its restore, or the handover, instead of an audit command; a covering
    record with findings open is decided, which needs no attempt."""
    audit = (
        f"audit the answering run as it stands: "
        f"`{audit_command(ctx.area, '--mode', 'analysis', protocol=ctx.protocol)}`, "
        f"then decide its findings"
    )
    if ctx.run is None:
        return blocker(
            f"no answering run to hold it to — {ctx.why}",
            fix=f"measure: `{measure_command(ctx.area)}`, then audit that run",
        )
    try:
        gap = findings.audit_coverage(
            ctx.area, ANALYSIS_AUDIT, analysis_now(ctx.area, ctx.text, ctx.run)
        )
        covering = covering_analysis(ctx.area, ctx.text, ctx.run)
    except AuditError as exc:  # a registered output is gone
        return blocker(
            f"the analysis audit cannot be held to the run: {exc.why}",
            fix=exc.fix or audit,
        )
    except (FileNotFoundError, ValueError) as exc:
        # ValueError: nothing to stamp, a findings file or the promise block
        # unreadable (FindingsError, PromiseError)
        return blocker(
            f"the analysis audit cannot be held to the area: {exc}",
            fix=f"repair what the sentence names, then {audit}",
        )
    if gap is None:
        return None
    # the way out is a new audit, and `attempts.begin` refuses every attempt
    # while one of these stands: "none has run yet" and `--mode analysis`
    # were printed after an audit's record was deleted (pilot t60)
    lost = attempts.evidence_gaps(ctx.area) if not covering else []
    if lost:
        findings_command = audit_command(ctx.area, "--findings", protocol=ctx.protocol)
        return blocker(
            f"no analysis audit covers the area as it is now, and none can run — "
            f"{attempts.gone_line(lost)}",
            fix=f"(a) bring the evidence back — the line names the first "
            f"restore, `{findings_command}` lists every loss with its restore —, "
            f"then {audit}; (b) where nothing restores it, no audit covers the "
            f"area and no number leaves it: {ways_out.HANDOVER}",
        )
    return blocker(gap, fix=audit)


def limit_gaps(ctx: Checked) -> list[GateFinding]:
    """The generated results and limits: every accepted BLOCKER of the covering analysis
    records has its effect decided, and the result section says exactly
    what those records and the run render (`result_render.render_gaps`):
    the Recorded results line with its note, one Limit line per decided limit, none
    that no record decides. Exact in what it holds — equality with the
    rendering — and silent on whether a limit is enough: that is the
    audit's question. Empty when no covering record exists
    (`analysis_audit_gap` names that), and the rendering is not owed while
    the head declares no result."""
    if ctx.run is None:
        return []
    try:
        records = covering_analysis(ctx.area, ctx.text, ctx.run)
    except (AuditError, FileNotFoundError, ValueError):
        return []
    gaps: list[GateFinding] = []
    # `<ID> not assessable` only where the protocol registers a promise: a
    # computation has none, and `--decide` refuses every id there. The block
    # reads here: `covering_analysis` above stamped it (PromiseError → [])
    effects = (
        'stands|"<ID> not assessable"' if promises.table_ids(ctx.text) else "stands"
    )
    for r in records:
        for n, f in r.limits():
            if not f.effect:
                gaps.append(
                    blocker(
                        f"{findings.limit_label(r, n)}: an accepted BLOCKER owes its "
                        "effect on the verdicts",
                        fix="`"
                        + decide_command(
                            ctx.area,
                            n,
                            "accepted",
                            "REASON",
                            r.path.name,
                            effect=effects,
                            protocol=ctx.protocol,
                        )
                        + "`",
                    )
                )
    if ctx.declared is None:
        return gaps  # nothing reported: the result section is not owed yet
    try:
        expected = rendering(ctx.area, ctx.text, ctx.run)
    except (OSError, ValueError) as exc:
        return gaps + [
            blocker(
                f"the result cannot be rendered from {ctx.run.name}: {exc}",
                fix=f"repair what the sentence names, then "
                f"`protocol-fill {shlex.quote(shown(ctx.protocol, Path.cwd()))} "
                f"--render` writes the result section",
            )
        ]
    return gaps + render_gaps(ctx.text, expected)


def review_findings(ctx: Checked) -> list[GateFinding]:
    """The decision reviews: every `stands` among the limits of the
    covering analysis records is upheld by a decision review
    (`reviews.upholding`: a review of that record, its code and its run as
    shown, under the claim the protocol makes now, of the decision as it
    stands now, every draw saying `upheld`). The grade follows the
    finding's: an accepted BLOCKER's `stands` no review upholds — never
    reviewed, rejected, insufficient, contested, or reviewed as another
    decision or claim — is a BLOCKER (a severe finding is not settled by
    a reason alone; decided 2026-10-22 after the fifth round's replay and
    the assessment of its fifteen decisions from their sources), an
    accepted WARNING's a WARNING for now (the release does not yet hang
    on every lesser limit). A finding a review of the record once did not
    uphold (`reviews.once_not_upheld`) and that is now `dismissed`, `fixed`
    or `deferred` (`findings.CLOSING`) is held the same way until a review
    upholds the new decision: closing it is not settling it (sixth haiku
    round, 2026-10-23, t5). Empty when no record covers the run
    (`analysis_audit_gap` names that), and silent on whether the verdict is
    right: that is the reviewer's judgement."""
    if ctx.run is None:
        return []
    try:
        records = covering_analysis(ctx.area, ctx.text, ctx.run)
    except (AuditError, FileNotFoundError, ValueError):
        return []  # ValueError: FindingsError — analysis_audit_gap names them
    out: list[GateFinding] = []
    try:
        found = reviews.area_reviews(ctx.area)
    except reviews.ReviewError as exc:
        # named, and the decisions are judged as unreviewed: a file nobody
        # can read must not hide a BLOCKER's unupheld `stands`
        out.append(
            GateFinding(
                WARNING, f"a review nobody can read: {exc}", evidence_kind=GUARANTEED
            )
        )
        found = []
    for r in records:
        for n, f in r.limits():
            if f.effect != findings.EFFECT_STANDS or reviews.upholding(
                r, n, found, ctx.text
            ):
                continue
            out.append(
                GateFinding(
                    BLOCKER if f.grade == "BLOCKER" else WARNING,
                    f"{findings.limit_label(r, n)}: `stands` on an accepted {f.grade} "
                    f"{reviews.state(r, n, found, ctx.text)} — no decision review "
                    f"upholds that the reported claim stands within this limit "
                    f"(LAB-015 Preflight audit before freezing)",
                    fix=f"{_review_step(ctx, r)} asks a second auditor; after a "
                    f"rejection, decide again",
                    evidence_kind=GUARANTEED,
                )
            )
        for n, f in enumerate(r.findings, 1):
            if f.status not in findings.CLOSING:
                continue
            was = reviews.once_not_upheld(r, n, found)
            if was is None or reviews.upholding(r, n, found, ctx.text):
                continue
            out.append(
                GateFinding(
                    BLOCKER if f.grade == "BLOCKER" else WARNING,
                    f"audit {r.path.stem} #{n}: `{f.status}` on a {f.grade} a "
                    f"review said {was.verdict} on ({was.why}) — closing a finding "
                    f"a reviewer did not uphold settles nothing by itself; the new "
                    f"decision is {reviews.state(r, n, found, ctx.text)} "
                    f"(LAB-015 Preflight audit before freezing)",
                    fix=f"{_review_step(ctx, r)} asks a second auditor whether the "
                    f"reason shows it {_closing_question(f.status)}",
                    evidence_kind=GUARANTEED,
                )
            )
        out += first_dismissals(ctx, r, found)
    return out


def first_dismissals(
    ctx: Checked, r: findings.Record, found: list[reviews.Review]
) -> list[GateFinding]:
    """A BLOCKER of record R decided `dismissed` (`findings.dismissed_blocker`)
    that no review among FOUND upholds — held as a BLOCKER: the deciding
    agent's own decision would release a blocking finding. A carried one is
    the follow-up's (`followup_findings`), one a review once did not uphold
    the closing rule's (`review_findings`); each is held once."""
    out: list[GateFinding] = []
    for n, f in enumerate(r.findings, 1):
        if (
            not findings.dismissed_blocker(f)
            or f.carries
            or reviews.once_not_upheld(r, n, found) is not None
            or reviews.upholding(r, n, found, ctx.text)
        ):
            continue
        out.append(
            GateFinding(
                BLOCKER,
                f"audit {r.path.stem} #{n}: `dismissed` on a BLOCKER "
                f"{reviews.state(r, n, found, ctx.text)} — a blocking finding is not "
                f"released by the deciding agent's own decision (LAB-015 Preflight "
                f"audit before freezing)",
                fix=f"{_review_step(ctx, r)} asks a second auditor whether the reason "
                f"shows it {_closing_question('dismissed')}",
                evidence_kind=GUARANTEED,
            )
        )
    return out


def followup_findings(ctx: Checked) -> list[GateFinding]:
    """The follow-up of earlier decided BLOCKERs (`followup.release_holds`): each
    one not released by a valid `resolved` of the state reported now, and a
    BLOCKER `fixed` in that state itself, is a BLOCKER naming the missing
    step. A carried finding (`carries`) closed in a covering record as
    `dismissed` or `deferred` is held until a decision review of that
    record upholds the new decision — the follow-up did not find the fault
    gone, so closing it is not settling it (the rule of
    `reviews.once_not_upheld`, for a verdict of the follow-up). A chain
    that does not read is a BLOCKER. Without a covering record every
    earlier decided BLOCKER is held — no follow-up saw it. Empty without an
    answering run, or when the covering records or the area's records do
    not read (`analysis_audit_gap` names those); silent on whether a verdict
    is right: that is the auditor's judgement. Why: the fixed-followup
    pilots, 2026-10-26."""
    if ctx.run is None:
        return []
    try:
        covering = covering_analysis(ctx.area, ctx.text, ctx.run)
        records = findings.area_records(ctx.area)
    except (AuditError, FileNotFoundError, ValueError):
        return []  # analysis_audit_gap names them
    try:
        metrics: dict | None = runs.read_metrics(runs.metrics_path(ctx.run))
    except (OSError, ValueError):
        metrics = None
    evidence = check_evidence(metrics, dependency_pieces(ctx.run))
    try:
        held = followup.release_holds(records, covering, evidence)
    except findings.FindingsError as exc:
        return [
            blocker(
                f"the carried findings of {ctx.area.name} do not form a chain: {exc}",
                fix=findings.record_way(ctx.area, ctx.protocol),
            )
        ]
    # the follow-up refuses an area with several protocols (`audit.earlier_of`):
    # no step there may name it
    several = len(area_protocols(ctx.area)) > 1
    out = [
        blocker(
            f"audit {h.ref}: {h.why} (LAB-015 Preflight audit before freezing)",
            fix=followup.STEP_NONE_SEVERAL
            if several and h.needs_followup_audit
            else h.step,
        )
        for h in held
    ]
    try:
        found = reviews.area_reviews(ctx.area)
    except reviews.ReviewError:
        found = []  # review_findings names the file; unreviewed holds here
    for r in covering:
        for n, f in enumerate(r.findings, 1):
            if findings.carried_and_closed(f) and not reviews.upholding(
                r, n, found, ctx.text
            ):
                out.append(
                    blocker(
                        f"audit {r.path.stem} #{n}: a carried finding (from {f.carries}) "
                        f"`{f.status}` — the follow-up did not find the fault gone, so "
                        f"closing it settles nothing by itself "
                        f"(LAB-015 Preflight audit before freezing)",
                        fix=f"{_review_step(ctx, r)} asks a second auditor whether "
                        f"the reason shows it {_closing_question(f.status)}",
                    )
                )
    return out


def _review_step(ctx: Checked, record: findings.Record) -> str:
    """The decision review of RECORD as the next step: the whole command
    with the area as seen from here, and — while the protocol's Conclusion
    is unwritten — the step `--review` refuses without (it judges the
    claim). A refusal naming `<area>` and no precondition was not followed
    (ninth haiku round, t3)."""
    command = f"`{audit_command(ctx.area, '--review', '--record', record.path.name, protocol=ctx.protocol)}`"
    if conclusion_written(ctx.text):
        return command
    return (
        f"write the Conclusion in {ctx.protocol.name} first (the review judges "
        f"that claim, and refuses without it), then {command}"
    )


def _closing_question(status: str) -> str:
    """What the reviewer is asked of a closed contested finding, by status."""
    return {
        "dismissed": "does not apply to the code and run as audited",
        "fixed": "gone in the files as audited",
        "deferred": "somebody else's task, not this result's limit",
    }[status]


def unreportable_gaps(ctx: Checked, freeze_owed: bool) -> list[GateFinding]:
    """Why the answering run's number cannot be reported
    (`runs.unreportable`), each a blocker. Without an answering run there is
    nothing to hold — finalize says so. FREEZE_OWED names the freeze in the
    sentence (high repeat cost); at low repeat cost a full run is owed, no freeze."""
    if ctx.run is None:
        return []
    measure = f"`{measure_command(ctx.area)}`"
    cfg = read_run_config(ctx.run)
    if cfg is None:
        return [
            blocker(
                f"{ctx.run.name}: no config.json — not a run",
                fix=f"measure through runlog: {measure}",
            )
        ]
    owed = "a full run (run_kind='measurement')" + (
        " on a frozen protocol" if freeze_owed else ""
    )
    return [
        blocker(
            f"the answering run {ctx.run.name}: {mark} — its number cannot be "
            f"reported; a reported number owes {owed}",
            fix=f"measure in full{' after the freeze' if freeze_owed else ''}: "
            f"{measure}, then audit that run",
        )
        for mark in unreportable(cfg)
    ]


def finalize_gaps(area: Path, protocol: Path) -> list[GateFinding]:
    """Finalize's blockers, each named here with
    its prefix — a hook that says "run it to see them" asks for a round
    trip the agent does not take. finalize runs on a silent collector
    (`Findings(tell=None)`): its findings arrive as data and nothing of its
    output reaches this gate's, so finalize puts every reason into the
    blocker itself (the runs it looked at, intent-check's lines, the test
    counts) and keeps its exit-2 reason (no protocol to hold) as a blocker
    too. A non-zero exit without a blocker is a bug in finalize, not a
    state to report around."""
    collected = Findings(tell=None)  # the data, not the console
    finalized = finalize_area(area, protocol, collected)
    if finalized == 0:
        return []
    if not collected.blocked:
        raise RuntimeError(
            f"finalize {area} exits {finalized} and kept no blocker — every "
            f"reason finalize has must be a finding"
        )
    return [
        replace(f, text=f"finalize: {f.text}")
        for f in collected.found
        if f.grade == BLOCKER
    ]


def analysis_findings(ctx: Checked, rule: str) -> list[GateFinding]:
    """Coverage and rendered-result blockers for an analysis stage already due.

    RULE is the lane's analysis-audit rule; the entry point decides whether
    this stage runs. Missing coverage and result differences are all kept.
    """
    out: list[GateFinding] = []
    gap = analysis_audit_gap(ctx)
    if gap:
        out.append(replace(gap, text=f"analysis audit: {gap.text} ({rule})"))
    # the rendered result section is held here too, named as what it is:
    # a cold reader took "analysis audit:" on a retyped Recorded results
    # line for a record problem (reading probe 2026-10-22)
    out.extend(
        replace(gap, text=f"result section: {gap.text}") for gap in limit_gaps(ctx)
    )
    return out


def recomputation_findings(area: Path, repo: Path) -> list[GateFinding]:
    """Run the analysis script's check and return its failure as a blocker."""
    failed = check_analysis_script(area, repo)
    return (
        [
            blocker(
                f"{failed} (LAB-041 Generate numbers, don't retype them)",
                fix=f"fix what the check names until `.venv/bin/python "
                f"{shlex.quote(shown(area / CHECK_SCRIPT, Path.cwd()))} {CHECK_FLAG}` "
                f"exits 0; a number in the protocol comes from `protocol-fill`, "
                f"never typed",
            )
        ]
        if failed
        else []
    )


def report_check(
    area: Path,
    protocol: Path | None = None,
    *,
    state: str = TREE,
    text: str | None = None,
) -> int:
    """Check AREA before reporting; 0 clean or warnings, 1 blocked, 2 no context.

    0. Choose the protocol and read Checked; missing or unreadable ends with 2.
    1. Declaration: an unreadable `[result]` blocks, later stages continue.
    2. Registration: check the freeze where the lane owes it; otherwise check
       the first measurement's committed registration where owed.
    3. Finalize: always collect its blockers.
    4. Full run: check reportability only when an answering run exists.
    5. Analysis: coverage and rendered results only where the lane owes it.
    6. Recomputation: always run the analysis script's `--check`.
    7. Decisions: review accepted `stands` only where analysis is owed.
    8. Report: the registered report, only when the head names one and the
       file is delivered in STATE, carries the result block or the handover.
    9. Summary: return 1 with any blocker, otherwise 0.

    Every applicable stage runs despite earlier blockers. STATE and TEXT
    name the declaration's file state: the tree by default, the index for
    the pre-commit, the written proposal for adoption. The nested finalize
    gate and analysis script read their own inputs.
    """
    # 0. protocol and context — the only early end
    chosen = choose_protocol(area, protocol, "report-check")
    if chosen is None:
        return 2
    try:
        ctx = checked(area, chosen, state=state, text=text)
    except (protocol_block.BlockError, AuditError) as exc:
        console.refuse("report-check", f"{chosen.name}: {exc}")
        return 2
    print(
        f"  {chosen.name}: read from the {ctx.state}; the head declares "
        f"{ctx.declared or 'no run'}; the answering run is "
        f"{ctx.run.name if ctx.run is not None else 'none — ' + ctx.why}"
    )
    ln = lane(ctx.head.repeat_cost)
    findings = Findings(
        area=shown(ctx.area, Path.cwd()),
        audit=audit_command(ctx.area, protocol=ctx.protocol),
    )

    # 1. declaration — a blocker does not stop the remaining stages
    if ctx.declaration_gap:
        findings.block(
            f"{chosen.name}: {ctx.declaration_gap}",
            fix=f"`{withdraw_command(ctx.protocol)}` removes it; audit the run "
            f"that answers, then `{adopt_command(ctx.protocol)}` writes the "
            f"`[result]` table for it",
        )

    # 2. registration — freeze or committed registration, as the lane owes
    if ln.freeze:
        findings.take_all(freeze_gaps(ctx))
    else:
        print(
            f'  {ctx.protocol.name}: repeat_cost = "{ctx.head.repeat_cost}" — no freeze and no preflight '
            f"audit owed (LAB-017 The number of audits follows the cost tier); the "
            f"registration as committed at the first measurement, the full run, "
            f"the analysis audit and the check are owed instead"
        )
        if ln.registration:
            findings.take_all(registration_gaps(ctx))
    # a declared replacement binds its changes (K1)
    findings.take_all(replacement_gaps(ctx))

    # 3. finalize — always, with its blockers named
    finalized = finalize_gaps(ctx.area, ctx.protocol)
    findings.take_all(finalized)
    # a declared run whose code changed: every later hold withdraws first
    held_by = held_declaration(ctx, finalized)

    # 4. full run — only with an answering run; finalize names its absence
    if ctx.run is not None:
        findings.take_all(withdrawn_first(unreportable_gaps(ctx, ln.freeze), held_by))

    # 5. analysis — coverage and rendering where the lane owes the audit
    if ANALYSIS_AUDIT in ln.audits:
        findings.take_all(
            withdrawn_first(analysis_findings(ctx, ln.analysis_rule), held_by)
        )

    # 6. recomputation — always, including after a failed earlier stage
    findings.take_all(
        withdrawn_first(recomputation_findings(ctx.area, ctx.repo), held_by)
    )

    # 7. decisions — reviews and follow-ups where the lane owes the analysis audit
    if ANALYSIS_AUDIT in ln.audits:
        findings.take_all(withdrawn_first(review_findings(ctx), held_by))
        findings.take_all(withdrawn_first(followup_findings(ctx), held_by))

    # 7b. adoption last — a `--from-run` line beside other blockers is the last
    # step, not the fix (stuck-state probe 2026-10-28)
    tell_adoption_order(findings)

    # 8. report — the file the head registers, once delivered in this state
    findings.take_all(report_findings(ctx))

    # 9. summary — 1 with a blocker, otherwise 0
    if not findings.blocked:
        held = ("frozen, " if ln.freeze else "") + "finalized, audited, checked"
        print(f"  {chosen.name}: {held}")
    return findings.report("report-check", "reporting")


def report_findings(ctx: Checked) -> list[GateFinding]:
    """The registered report's obligation (`report_hold.report_owed`): the
    file the head's `report` names, as the state holds it, carries the
    result block of the declared run or the protocol's handover block —
    else one blocker; nothing registered or not delivered: []. The file
    is read relative to the area's layout root (`Checked.repo`: the git
    repository where there is one), from the index when the state is the
    index."""
    gap = report_owed(
        ctx.protocol, ctx.text, ctx.declared, ctx.repo, staged=ctx.state == INDEX
    )
    return [] if gap is None else [gap]


def adoption_order_note(blocked: list[str]) -> str | None:
    """The order to tell when BLOCKED (the blocker messages) names an adoption
    (`--from-run`) beside blockers that are not themselves projections of
    one (`--from-run`, `--render`): adoption runs this check and is refused
    while any of them stands, so they come first. None otherwise — then the
    adoption line is the way out as printed. Why: printed bare, `--from-run
    <run> --force` beside an open BLOCKER on that run read as the fix to
    three of three Haiku readers (docs/usability/2026-10-28-haiku-stuck-reading.md)."""
    adoption = [m for m in blocked if "--from-run" in m]
    other = [m for m in blocked if "--from-run" not in m and "--render" not in m]
    if not adoption or not other:
        return None
    return (
        f"  adoption comes last: `--from-run` runs report-check itself and is "
        f"refused while any of the {len(other)} other blocker(s) above stands — "
        f"clear them first, or hand the area over; the `--from-run` line names "
        f"the last step, not the fix"
    )


def held_declaration(ctx: Checked, finalized: list[GateFinding]) -> Path | None:
    """The protocol of CTX when it declares the run that answers and
    finalize's blockers (FINALIZED) found that run's code changed since it
    ran (`changed since <run>`); None otherwise. While so, every later hold
    names the withdrawal first (`ways_out.declared_first`): the declared
    number no longer holds for the code, the commit hook holds the code to
    it, and an audit made while it stands declared does not cover the next
    run."""
    if ctx.run is None or ctx.declared != ctx.run.name:
        return None
    mark = f"changed since {ctx.declared}"
    return ctx.protocol if any(mark in f.text for f in finalized) else None


def withdrawn_first(
    found: list[GateFinding], held_by: Path | None
) -> list[GateFinding]:
    """FOUND, each blocker's way out after the withdrawal of HELD_BY's
    declaration when there is one (`held_declaration`)."""
    if held_by is None:
        return found
    return [ways_out.declared_first(f, held_by) for f in found]


def tell_adoption_order(findings: Findings) -> None:
    """Tell `adoption_order_note` through FINDINGS when it applies."""
    order = adoption_order_note(findings.blocked)
    if order:
        findings.note(order)


def affected_protocols(
    paths: list[Path], repo: Path, *, staged: bool = False
) -> list[Path]:
    """Every protocol of every area PATHS touch, each once, by area: a
    changed script, run or audit record reopens the area's reported numbers
    as a changed protocol does, and so does a file its promises declare in
    scope, a shared helper its code imports, or the validation its
    `annotation_validity` binds (`scope_sha.areas_touched`,
    the stop and the commit's undecided gate read the same answer). STAGED:
    areas and protocols are the index's (`repo.indexed_protocols`) — a
    protocol deleted only in the tree is still in the commit."""
    if not staged:
        return [
            p
            for area in sorted(areas_touched(paths, repo))
            for p in area_protocols(area)
        ]
    indexed = indexed_protocols(repo)
    areas = areas_touched(paths, repo, indexed)
    return [p for area in sorted(areas) for p in indexed if p.parent == area]


def if_reported(paths: list[Path], repo: Path, *, staged: bool) -> int:
    """`report-check` for every protocol of an area one of PATHS touches
    whose head declares a result, and for every report among PATHS
    (`report_files`): the gate at the stop and the commit. A result declared
    reported is held to the whole chain, a protocol declaring none is
    skipped (an exploration may end with no reported result). A report
    that is a symbolic link is refused alone, naming the copy that replaces
    it; its other checks wait for that copy. A report's generated blocks
    are held to the protocols they name, which the stations hold too, its
    cited run ids to the repo's runs; its other numbers are hints. STAGED
    (the pre-commit): declarations and reports are
    read from the index, and an area whose tree differs from the index is a
    blocker — the stations read the tree, the commit holds the index.
    A protocol among them whose declaration differs from HEAD's
    (`newly_declared`) reaches the committed reports citing that run
    (`committed_reports`): they are held as if changed, since the number
    they show became a declared result in this very state (the two-step
    commit of the sixth haiku round, 2026-10-23). A committed report that
    discusses a run of an area PATHS touch is held too
    (`discussing_reports`): its review read that area. A protocol whose
    head registers a file among PATHS as its report is held too
    (`registering_protocols`): the report lies in no area, and a change
    of it reaches the protocol that owes it its result
    (`report_hold.report_owed`, through `hold_declared`). Returns the worst
    exit code."""
    protocols = affected_protocols(paths, repo, staged=staged)
    for p in registering_protocols(paths, repo, staged=staged):
        if p not in protocols:
            protocols.append(p)
    reports = report_files(paths, repo, staged=staged)
    reached = reached_reports(protocols, reports, repo, staged=staged)
    held = {p for p, _ in reports} | {p for p, _, _ in reached}
    reached += discussing_reports(paths, held, repo, staged=staged)
    sources = (
        repo_sources(repo, staged=staged)
        if reports or reached
        else Sources(repo.resolve(), set(), {}, {}, {})
    )
    for p in held_by_reports(reports + [(p, t) for p, t, _ in reached], sources):
        if p not in protocols:
            protocols.append(p)
    worst = 0
    for protocol in protocols:
        worst = max(worst, hold_declared(protocol, repo, staged=staged))
    for path, text in reports:
        worst = max(worst, hold_report(path, text, repo, sources, staged=staged))
    for path, text, held_as in reached:
        worst = max(
            worst,
            hold_report(path, text, repo, sources, held_as=held_as, staged=staged),
        )
    return worst


def hold_declared(protocol: Path, repo: Path, *, staged: bool) -> int:
    """`report-check` on PROTOCOL when its head declares a result, as the
    state holds it (the index when STAGED); for an exploration only its
    registered report's obligation (`hold_registered`); 0 for a protocol
    the commit does not hold, 2 for one that cannot be read or is a
    symbolic link in that state (`repo.protocol_links`)."""
    link = protocol_links(repo, [protocol], staged=staged)
    if link:
        console.refuse("report-check", link[protocol])
        return 2
    try:
        text = state_text(repo, protocol, staged=staged)
    except (OSError, UnicodeError) as exc:  # a refusal, never a traceback
        console.refuse("report-check", f"{protocol}: {exc}")
        return 2
    if text is None:
        if staged:
            return 0  # not in the commit: nothing declared there
        console.refuse("report-check", f"{protocol}: no such file")
        return 2
    declared, gap = _declaration(text)
    if declared is None and gap is None:
        # an exploration: nothing declared; its registered report, once
        # delivered, is owed the handover or the result all the same
        return hold_registered(protocol, text, repo, staged=staged)
    print(
        f"═══ report-check {protocol} (its head declares "
        f"{declared or 'a result that does not read'}) ═══"
    )
    area = protocol.parent.resolve()
    if staged:
        differs = tree_differs(repo, area)
        if differs:
            print(
                f"  {area.relative_to(repo.resolve()).as_posix()}: the working "
                f"tree differs from the index ({', '.join(differs)}) — the "
                f"stations read the tree, the commit holds the index; stage "
                f"these too, or stash them, so the commit holds what the "
                f"check sees"
            )
            return 1
    return report_check(area, protocol, state=INDEX if staged else TREE, text=text)


def hold_registered(protocol: Path, text: str, repo: Path, *, staged: bool) -> int:
    """The registered report's obligation of PROTOCOL, a protocol that
    declares no result (`report_hold.report_owed` with no declared run):
    0 when the head registers no report, the file is not delivered in the
    state, or it carries the protocol's handover block; 1 held, the
    blocker told under its own heading. Raises `protocol_block.BlockError`
    on a head that does not read — the caller read the declaration off
    the same text first."""
    gap = report_owed(protocol, text, None, repo, staged=staged)
    if gap is None:
        return 0
    print(
        f"═══ report-check {protocol} (its head declares no result; its "
        f"registered report is delivered) ═══"
    )
    out = Findings()
    out.take(gap)
    return out.report("report-check", "reporting")


def main(argv: list[str]) -> int:
    """Command line of `report-check`."""
    if argv and argv[0] == "--if-reported":
        cwd = Path.cwd()
        rest = argv[1:]
        staged = bool(rest) and rest[0] == "--staged"
        paths = [Path(a) for a in (rest[1:] if staged else rest)]
        return if_reported(paths, git_root(cwd) or cwd, staged=staged)
    ap = argparse.ArgumentParser(
        prog="report-check",
        description=(__doc__ or "").split("\n\n")[0],
        # the hooks' form is parsed above, before argparse; it is still part
        # of this command's contract and stands in its --help (audit 2026-10-23, C2)
        epilog=(
            "report-check --if-reported [--staged] PATH ...\n"
            "    every protocol of an area a path touches whose head declares a\n"
            "    result, and every report among PATHS citing a run (the stop\n"
            "    hook; with --staged the pre-commit: the head and the report as\n"
            "    the index holds them, and the area's tree must equal the index)\n"
            f"{EXIT_CONTRACT}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("area", type=area_path)
    ap.add_argument("--protocol", type=Path, default=None)
    a = ap.parse_args(argv)
    if not a.area.is_dir():
        console.refuse("report-check", no_such_area(a.area))
        return 2
    return report_check(a.area.resolve(), a.protocol)


def cli() -> None:
    """Console entry point `report-check`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
