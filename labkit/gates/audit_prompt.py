"""What the agent audit is shown: its instructions, the area's files and the
evidence it reads, rendered into one prompt and bound to the area's stamp
before the call.

The instructions ship with the package (`labkit/agents/*.agent.md`);
`render` inlines the files they tell the auditor to read, the rules of the
standard they cite (`cited_rules`) and, in a follow-up, the earlier decided
blockers and corrections (`earlier_piece`). `bound_prompt` takes the stamp once, before the
call, so the record names the sha the auditor read. Nothing here calls a
model or writes a file; `gates.audit` does.
"""

from __future__ import annotations

import ast
import difflib
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from labkit.formats.gate import BLOCKER
from labkit import PACKAGE_DIR
from labkit.checks.audit_binding import AuditError, RunShown, audited_run, run_shown
from labkit.formats.area_state import state_of
from labkit.checks.prompt_check import prompt_constants
from labkit.formats.protocol_check import prompt_blocks, unread_prompt_field
from labkit.formats import (
    digests,
    findings,
    finding_decisions,
    audit_records,
    required_check,
    followup,
    promises,
    protocol_block,
    protocol_check,
    rules,
    scope_sha,
)
from labkit.formats.exploration_state import (
    ClosureRun,
    SharedInput,
    named_state,
    shared_inputs,
)
from labkit.formats.runs import ArtefactError, read_data, recorded_models
from labkit.formats.prompts import prompt_body
from labkit.formats.protocol_block import CONFIRMATORY, repo_protocol_ids
from labkit.formats.protocol_then import FIRST_MEASUREMENT, as_measured
from labkit.formats.protocol_history import (
    ABSENT,
    BoundValidation,
    bound_validation,
    registrations_as_first_measured,
)
from labkit.formats.repo import (
    ProtocolChoiceError,
    git_root,
    layout_root,
    no_such_area,
    shown,
    the_protocol,
)
from labkit.formats.runs import MEASURE_SCRIPT, metrics_path, read_run_dir, run_path
from labkit.formats.scope_sha import (
    area_files,
    area_snapshot,
    repo_imports,
)
from labkit.formats.standard_contract import (
    ANALYSIS_AUDIT,
    CLARITY,
    COMPUTE_KIND,
    PREFLIGHT_AUDIT,
)
from labkit.gates import ways_out
from labkit.gates.registration_hold import (
    run_compared_with,
    workflow,
    workflow_of_first_texts,
)
from labkit.gates.ways_out import (
    AUDIT_AGAIN,
    PROTOCOL_NAMED,
)
from labkit.run.llm import model_entry

AGENT = PACKAGE_DIR / "agents" / "experiment-preflight.agent.md"
CLARITY_AGENT = PACKAGE_DIR / "agents" / "code-clarity.agent.md"
REVIEW_AGENT = PACKAGE_DIR / "agents" / "decision-review.agent.md"
REPORT_AGENT = PACKAGE_DIR / "agents" / "report-review.agent.md"
CLAIM_AGENT = PACKAGE_DIR / "agents" / "claim-review.agent.md"
ANALYSIS = ANALYSIS_AUDIT  # its one spelling is standard_contract's
#: the modes of the three reviews, spelled here where their instructions are
#: looked up; `decision_review`, `report_review` and `claim_review` import them
REVIEW = "review"
REPORT_REVIEW = "report"
CLAIM_REVIEW = "claim"
#: the instructions each prompt mode is given — every mode stands here; a
#: mode that does not is refused, never read as the preflight agent's
AGENT_OF_MODE = {
    PREFLIGHT_AUDIT: AGENT,
    ANALYSIS_AUDIT: AGENT,
    CLARITY: CLARITY_AGENT,
    REVIEW: REVIEW_AGENT,
    REPORT_REVIEW: REPORT_AGENT,
    CLAIM_REVIEW: CLAIM_AGENT,
}
STANDARD_LABEL = (
    "labkit/docs/standard.md"  # the shipped standard, wherever labkit is installed
)
INLINE_NOTE = (
    "The files you are told to read are inlined below instead of read with "
    "tools; each starts with a `===== FILE: <path> =====` line, the rules of "
    "the standard under one such line, modules further down the import graph "
    "as signatures under one `===== INDEX: … =====` line (not read — name one "
    "in an assignment to have it supplied), and in MODE analysis the answering "
    "run's output rows under `===== ROWS <path> … =====` lines, each row as "
    "`<line>: <row>`, the origin run of each input under one `===== INPUT "
    "ORIGINS =====` line and the protocol each origin run was bound to, "
    "as it stood when that run started, under `===== SOURCE PROTOCOL <run> "
    "=====` lines, every run of the protocol audited and of each source's "
    "protocol, with its state, result, registration and code then, under "
    "`===== RUNS OF THIS PROTOCOL <id> =====` and `===== RUNS OF SOURCE "
    "PROTOCOL <id> =====` lines and each run's whole code diff under "
    "`===== RUN DIFF <compared> → <run> =====` lines, a diff an earlier "
    "finding asked for under `===== REQUESTED DIFF <old> → <new>[, <path>] "
    "=====` lines and a file of a run's code then under `===== REQUESTED "
    "CODE <run>, <path> =====` lines, and for a computation over a model's annotations the "
    "evidence that the annotator suits under `===== EVIDENCE: … =====` lines "
    "(the bound apply protocol and its result as FILE lines), for a "
    "confirmatory protocol that replaces another the predecessor's "
    "registration and the inputs both protocols' runs recorded under "
    "`===== PREDECESSOR: … =====` lines, for a confirmatory protocol that "
    "names its exploration (`[explored_in]`) that exploration's registration, "
    "its adopted run and Conclusion, the runs the adopted run rests on and "
    "the inputs both protocols' runs recorded under `===== EXPLORATION: … "
    "=====` lines, every data or output file the protocol declares in "
    "`[[evidence_file]]`, in full, under an `===== EVIDENCE FILE: <path> (sha256 "
    "<hex>) =====` line, and the area's "
    "earlier decided BLOCKERs and corrections under one `===== EARLIER DECIDED "
    "BLOCKERS AND CORRECTIONS =====` line. Nothing else is in scope."
)


def instructions(mode: str = PREFLIGHT_AUDIT) -> str:
    """The agent's instructions as shipped, without the provenance comment —
    the preflight agent for preflight and analysis, the clarity agent for
    clarity, the decision-review agent for `--review` (`decision_review`),
    the report-review agent for `--report-review` (`report_review`), the
    claim-review agent for `--review` on a report review (`claim_review`):
    AGENT_OF_MODE. Raises ValueError naming MODE when it is none of these —
    a misspelled mode would otherwise be given the preflight agent's
    instructions."""
    if mode not in AGENT_OF_MODE:
        raise ValueError(
            f"no instructions for mode {mode!r} — the modes are "
            f"{', '.join(sorted(AGENT_OF_MODE))}"
        )
    agent = AGENT_OF_MODE[mode]
    return re.sub(
        r"^<!--.*?-->\n", "", agent.read_text(encoding="utf-8"), count=1, flags=re.S
    )


def review_brief() -> list[tuple[str, str]]:
    """What the report reviewer reads besides the bundle, as (label, text)
    pieces: its instructions (`REPORT_AGENT`, "BRIEF") and the standard's
    excerpt they cite (`standard_excerpt`). The part of a review's
    fingerprint that is the brief, not the state
    (`report_hold.review_fingerprint`): a corrected brief makes every
    earlier review stale, so a claim an old rule raised no longer holds
    the report."""
    label, rules_text = standard_excerpt(REPORT_REVIEW)
    return [("BRIEF", instructions(REPORT_REVIEW)), (f"FILE: {label}", rules_text)]


def cited_rules(mode: str = PREFLIGHT_AUDIT) -> list[str]:
    """The `LAB-nnn` ids the instructions for MODE cite, in order of first
    mention — the part of the standard the auditor gets to read."""
    seen: list[str] = []
    for m in rules.CODE_RE.finditer(instructions(mode)):
        if m.group(1).startswith("LAB-") and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def standard_excerpt(mode: str = PREFLIGHT_AUDIT) -> tuple[str, str]:
    """(label, text): the cited rules' blocks from the shipped standard, each
    from its head to the next. An id the ledger does not know, or whose text
    does not ship, raises — a missing rule must not pass as an audit without it."""
    ids = cited_rules(mode)
    text = "\n".join(rules.rule_text(rid) for rid in ids)
    return f"{STANDARD_LABEL} ({', '.join(ids)} — the rules this audit cites)", text


class AuditInputs(NamedTuple):
    """What the auditor reads in full: the protocol, the code, the standard
    (its cited rules). Every other stamped file comes as an index, taken
    from the snapshot (`bound_prompt`)."""

    protocol: Path
    code: list[Path]  # scripts, analysis files, declared scopes, direct imports
    standard: Path


def gather(area: Path, protocol: Path | None) -> AuditInputs:
    """What the agent reads, by LAB-103 The audit reads by declared scope,
    not by import graph: the area's scripts and analysis files, the files
    the promises declare as scope, the repo-local modules those import
    directly — in full (every other stamped file is indexed from the
    snapshot, `bound_prompt`). Refuses what is missing."""
    if not area.is_dir():
        # not a command line: the audit's own refusal of a path a caller
        # passed, with its way out — home: repo.resolve_area
        missing = no_such_area(area)
        raise AuditError(missing, fix="name the area by its path or numbered name")
    try:
        chosen = the_protocol(area, protocol)
    except ProtocolChoiceError as exc:
        raise AuditError(str(exc), fix=PROTOCOL_NAMED) from exc
    repo = layout_root(area)
    scripts = area_files(area)
    if not scripts:
        raise AuditError(
            f"{area}: no scripts/*.py or analysis/*.py — nothing to audit",
            fix="write the area's scripts first (`labkit-init exp` stamps them)",
        )
    code = [p.resolve() for p in scripts]
    declared = scope_sha.declared_scope_files([chosen])
    gone = [f for f in declared if not f.is_file()]
    if gone:
        # a promise resting on a missing file is not audited around
        scope = os.path.relpath(gone[0], chosen.parent.resolve())
        raise AuditError(
            f"{chosen.name}: a promise declares scope `{scope}`, and it is not a file",
            fix="name a file of the area in the promise's `scope`, or write that file",
        )
    code += [f for f in declared if f not in code]
    code += [f for f in repo_imports(code, repo) if f.resolve() not in code]
    standard = rules.STANDARD
    if not standard.is_file():
        raise AuditError(
            f"{standard} is missing — labkit was installed without its standard "
            f"(scar table, severity legend)",
            fix="reinstall labkit from the repo's pinned `requirements.txt`",
        )
    return AuditInputs(chosen, code, standard)


def module_index(files: list[Path], repo: Path, read: Callable[[Path], str]) -> str:
    """One line per file — path and line count — then its top-level
    `def`/`class` signatures with the first docstring line: what the auditor
    gets instead of the text of a module further down the import graph.
    READ gives a file's text (the snapshot's, for an audit)."""
    out: list[str] = []
    for f in files:
        rel = shown(f, repo)
        source = read(f)
        try:
            tree = ast.parse(source, filename=str(f))
        except SyntaxError as exc:
            raise AuditError(
                f"{rel}: cannot index it ({exc})",
                fix="fix the syntax error it names, then run the audit again",
            ) from exc
        out.append(f"{rel} ({len(source.splitlines())} lines)")
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = f"def {node.name}({ast.unparse(node.args)})"
            elif isinstance(node, ast.ClassDef):
                sig = f"class {node.name}"
            else:
                continue
            doc = (ast.get_docstring(node) or "").strip().splitlines()
            out.append(f"  {sig}" + (f"  — {doc[0]}" if doc else ""))
    return "\n".join(out)


def gather_clarity(area: Path, protocol: Path | None) -> tuple[Path, list[Path]]:
    """(protocol, [README, the measure script]) the clarity reader gets — its
    reading scope and nothing else: no lib modules, no standard."""
    chosen = gather(area, protocol).protocol
    readme = area / "README.md"
    script = area / MEASURE_SCRIPT
    missing = [p.name for p in (readme, script) if not p.is_file()]
    if missing:
        raise AuditError(
            f"{area}: no {', '.join(missing)} — the clarity reading starts there",
            fix="write them first (`labkit-init exp` stamps both)",
        )
    return chosen, [readme, script]


INDEX_LABEL = (
    "INDEX: repo-local modules further down the import graph — not inlined; "
    "name one in a finding's assignment to have it read (LAB-103 The audit "
    "reads by declared scope, not by import graph)"
)


class Source(NamedTuple):
    """What a prompt is rendered from, each read once by the caller: the
    protocol's text, a reader for every other file (`Snapshot.text` for an
    audit, so the prompt shows the bytes the record's sha names), in MODE
    analysis what it shows of the answering run (`run_shown`, the same
    pieces whose digest the record carries), and the evidence an annotator
    suits (`validity_evidence`; read from outside the area, covered by the
    record's `scope_sha` through `scope_sha.validation_basis`, so a changed
    validation stales the record — a DOI by its string only) and, for a
    confirmatory successor, its predecessor (`predecessor_evidence`), and
    for a confirmation that names its exploration, that state
    (`exploration_evidence`), and the files the protocol declares in
    `[[evidence_file]]` (`evidence_file_pieces`; covered through
    `scope_sha.evidence_file_basis`)."""

    protocol_text: str
    read: Callable[[Path], str]
    run: tuple[tuple[str, str], ...] = ()
    # validity, predecessor, exploration, declared evidence files
    evidence: tuple[tuple[str, str], ...] = ()
    fixes: tuple[tuple[str, str], ...] = ()  # `earlier_piece`, MODE analysis


DOI_ONLY = (
    "checked for its form only; what the publication shows is not in scope "
    "of this audit and was not read"
)
#: the head of a piece showing today's settings of a bound validation
CURRENT_ONLY = (
    "Today's setting, not necessarily what the validation ran with — the "
    "run's record above says which model answered."
)


def validity_evidence(area: Path, text: str) -> tuple[tuple[str, str], ...]:
    """What the audit is shown of `[model] annotation_validity` for a
    computation whose number claims a property of the data
    (`number_describes = "target_property"`): the bound apply protocol in
    full, its declared run's `metrics.json` (the validation result), the
    model its run recorded (`runs.recorded_models`), and today's
    models.toml entry and prompt sources (the protocol's `Prompt` blocks and
    the area's `PROMPT*` constants, `prompt_check`) marked as today's —
    a reference alone gives the audit nothing to judge. Not bound
    (`protocol_history.bound_validation`): one line saying why, never part
    of the evidence. A DOI: the DOI and that its content is not in scope.
    () for every other protocol."""
    try:
        m = protocol_block.model(text)
        kind = protocol_block.head(text).kind
    except protocol_block.BlockError:
        return ()
    if (
        m is None
        or kind != COMPUTE_KIND
        or m.number_describes != protocol_block.TARGET_PROPERTY
        or m.annotation_validity is None
    ):
        return ()
    if m.annotation_validity.key == "doi":
        return (
            (
                "EVIDENCE: annotation_validity",
                f"doi = {m.annotation_validity.value} — {DOI_ONLY}",
            ),
        )
    repo = layout_root(area)
    bound = bound_validation(text, repo_protocol_ids(area))
    if not isinstance(bound, BoundValidation):
        assert bound is not None  # a computation naming a protocol, as checked above
        return (
            (
                "EVIDENCE: annotation_validity",
                f"protocol = {m.annotation_validity.value} — NOT BOUND: {bound.why}. "
                "No validation is shown; nothing here supports the annotator.",
            ),
        )
    return _bound_pieces(bound, repo)


#: what the listed inputs do and do not show, the head of their piece
INPUTS_SHOW = (
    "Each line: protocol, run, key, recorded path, sha256 as recorded, rows; "
    "every run of each protocol, probes and repeats included. An equal "
    "sha256 is the same bytes. It does not show whether those data were "
    "evaluated for the changed question, and another sha256 can hold the "
    "same observations in another form."
)


def _recorded_inputs(area: Path, pid: str, role: str, repo: Path) -> list[str]:
    """One line per input every run of AREA bound to PID recorded
    (`runs.read_data`), oldest run first — every run of it, probes and
    repeats included (`area_state.Measured.runs`); each line names ROLE
    (predecessor or successor) and PID, since both protocols may share an
    area. A run whose record does not read, or that named no input, is
    said, never skipped."""
    lines = []
    for rd in state_of(area).measured_of(pid).runs:
        run = f"{role} {pid}, {shown(area, repo)} run {rd.dir.name}"
        try:
            entries = read_data(rd.dir)
        except ArtefactError as exc:
            lines.append(f"{run}: its inputs do not read ({exc})")
            continue
        if entries is None:
            lines.append(f"{run}: no readable record")
        elif not entries:
            lines.append(f"{run}: recorded no input")
        for e in entries or []:
            lines.append(
                f"{run}: {e.key} = {e.recorded} · sha256 {e.sha256} · rows {e.rows}"
            )
    return lines


def predecessor_evidence(area: Path, text: str) -> tuple[tuple[str, str], ...]:
    """What the audit is shown to judge a successor that calls itself
    confirmatory (`[replaces]` with `type = "confirmatory"`; no gate holds
    the type, `report_replacement.replacement_gaps`): the predecessor's
    registration as each of its first measurements saw it — one piece per
    distinct text, or its text as it stands when it has not measured, the
    label saying which (`registrations_as_first_measured`) —, and the
    inputs every run of both protocols recorded, under INPUTS_SHOW. The pieces let the auditor judge
    whether the changed question meets data already evaluated; they prove
    neither. A predecessor that is not exactly one protocol of the repo, or
    whose registration cannot be read back: one line saying so. The record's
    `scope_sha` covers the predecessor's run records
    (`scope_sha.predecessor_basis`): a new or changed run of the
    predecessor stales the record, the successor's own later runs do so
    through the run the record binds. () for every other protocol,
    and for a head that does not read or carries no id — `bound_prompt`
    refuses both before it renders. Raises RuntimeError when git fails."""
    try:
        rep = protocol_block.replaces(text)
        head = protocol_block.head(text)
    except protocol_block.BlockError:
        return ()
    if rep is None or head.type != CONFIRMATORY or head.id is None:
        return ()
    repo = layout_root(area)
    hits = repo_protocol_ids(area).get(rep.protocol, [])
    if len(hits) != 1:
        return (
            (
                f"PREDECESSOR: {rep.protocol}",
                f"NOT SHOWN: {len(hits)} protocols of this repo carry that id. "
                "Nothing here supports that the data are unseen.",
            ),
        )
    pred = hits[0]
    theirs = state_of(pred.parent).measured_of(rep.protocol)
    texts, missing = registrations_as_first_measured(
        pred, theirs.first_groups, git_root(pred)
    )
    pieces = [
        (f"PREDECESSOR: {shown(pred, repo)}, its registration {where}", then)
        for then, where in texts
    ] or [
        (
            f"PREDECESSOR: {shown(pred, repo)}",
            f"NOT SHOWN: its registration cannot be read back — {missing}",
        )
    ]
    inputs = _recorded_inputs(pred.parent, rep.protocol, "predecessor", repo)
    inputs += _recorded_inputs(area, head.id, "successor", repo)
    pieces.append(
        (
            "PREDECESSOR: inputs the runs of both protocols recorded",
            f"{INPUTS_SHOW}\n" + ("\n".join(inputs) or "no run of either protocol"),
        )
    )
    return tuple(pieces)


#: what equal input digests do and do not show, the head of their piece
SHARED_SHOW = (
    "Each line: a run of the exploration's area and a run of this "
    "confirmation that recorded an input with the same sha256 — the same "
    "bytes. `outside the named state` marks a run the link does not rest "
    "on: this audit's record does not go stale when such a run appears, so "
    "judge it here. No line does not show the data unseen: a subset, a "
    "re-encoded file or the same items under another name carry another "
    "sha256."
)


def exploration_evidence(area: Path, text: str) -> tuple[tuple[str, str], ...]:
    """What the audit is shown to judge a confirmation that names its
    exploration (`[explored_in]`), in either mode:

    1. the exploratory protocol's registration as each of its first
       measurements saw it (`registrations_as_first_measured`);
    2. the selection and the conclusion: the run the link names, the run
       that protocol adopts now and its Conclusion as it stands;
    3. the basis: the named run and every run it rests on
       (`exploration_state.named_state`), how the closure reached it, the
       text it started under and its step with every declared change;
       each such text not shown under 1 in full, once;
    4. the inputs every run of both protocols recorded, under INPUTS_SHOW,
       and every input digest a run of the exploration's area shares with
       a run of the confirmation (`exploration_state.shared_inputs`), under
       SHARED_SHOW — static evidence of further data use.

    The pieces let the auditor judge whether the confirming data were
    already evaluated; they prove neither. The record's `scope_sha` covers
    the parts under 2 and 3 (`scope_sha.exploration_basis`): a change
    there stales the record, a run outside the closure does not. An
    exploration that is not exactly one protocol of the repo: one line
    saying so. () without the table, and for a head that does not read or
    carries no id — `bound_prompt` refuses both before it renders. Raises
    RuntimeError when git fails."""
    try:
        link = protocol_block.explored_in(text)
        head = protocol_block.head(text)
    except protocol_block.BlockError:
        return ()
    if link is None or head.id is None:
        return ()
    repo = layout_root(area)
    hits = repo_protocol_ids(area).get(link.protocol, [])
    if len(hits) != 1:
        return (
            (
                f"EXPLORATION: {link.protocol}",
                f"NOT SHOWN: {len(hits)} protocols of this repo carry that id. "
                "Nothing here says what this confirmation builds on.",
            ),
        )
    theirs = hits[0]
    their_state = state_of(theirs.parent)
    texts, missing = registrations_as_first_measured(
        theirs,
        their_state.measured_of(link.protocol).first_groups,
        git_root(theirs),
    )
    pieces = [
        (f"EXPLORATION: {shown(theirs, repo)}, its registration {where}", then)
        for then, where in texts
    ] or [
        (
            f"EXPLORATION: {shown(theirs, repo)}",
            f"NOT SHOWN: its registration cannot be read back — {missing}",
        )
    ]
    named = named_state(theirs, link)
    pieces.append(
        (
            "EXPLORATION: the selection and the conclusion",
            f"[explored_in] names run {link.run}.\n"
            f"The exploratory protocol adopts now: "
            f"{named.adopted or 'no run (never adopted, or the adoption withdrawn)'}.\n"
            f"Its Conclusion as it stands: {named.conclusion or ABSENT}",
        )
    )
    pieces.append(
        (
            "EXPLORATION: the named run and the runs it rests on",
            "\n".join(line for m in named.closure for line in _closure_lines(m)),
        )
    )
    shown_texts = {then for then, _ in texts}
    for member in named.closure:
        then = member.then
        if then is not None and then.text is not None and then.text not in shown_texts:
            shown_texts.add(then.text)
            pieces.append((f"EXPLORATION: its protocol {then.where}", then.text))
    confirming = state_of(area).measured_of(head.id).runs
    inputs = _recorded_inputs(theirs.parent, link.protocol, "exploration", repo)
    inputs += _recorded_inputs(area, head.id, "confirmation", repo)
    shared = shared_inputs(
        confirming, their_state.runs, {m.run_id for m in named.closure}
    )
    pieces.append(
        (
            "EXPLORATION: inputs the runs of both protocols recorded",
            f"{INPUTS_SHOW}\n" + ("\n".join(inputs) or "no run of either protocol"),
        )
    )
    pieces.append(
        (
            "EXPLORATION: input digests shared with this confirmation",
            f"{SHARED_SHOW}\n"
            + (
                "\n".join(_shared_line(s) for s in shared)
                or "no run of the exploration's area recorded an input with a "
                "sha256 a run of this confirmation recorded"
            ),
        )
    )
    return tuple(pieces)


def _closure_lines(member: ClosureRun) -> list[str]:
    """One run of an exploration's closure as the audit reads it: how it
    was reached, the text it started under, its step with every declared
    change, and what of it does not read."""
    lines = [f"- run {member.run_id} ({member.reached})"]
    then = member.then
    if then is None:
        if not member.unread:
            # binding is the protocol a run started under, not what the run
            # was for: a preparation can be bound, an unbound run need not be one
            lines.append("  bound to no protocol: it owes no text")
    elif then.text is not None:
        lines.append(f"  its protocol {then.where}")
        step = then.step
        if step is None and then.unknown is None:
            lines.append("  no step: it stands by that text")
        elif step is not None:
            lines.append(
                f'  step "{step.id}" on {step.run} ({step.occasion}): {step.why}'
            )
            lines += [
                f'    {c.what}: "{c.from_}" → "{c.to}"'
                + (f" — {c.why}" if c.why else "")
                for c in step.changes
            ] or ["    no change of the registration declared"]
    lines += [f"  NOT READ: {why}" for why in member.unread]
    return lines


def _shared_line(s: SharedInput) -> str:
    """One shared input digest as the audit reads it."""
    where = "within the named state" if s.in_closure else "outside the named state"
    return (
        f"exploration run {s.exploring_run} ({where}): {s.exploring_key} · "
        f"confirmation run {s.confirming_run}: {s.confirming_key} · sha256 {s.sha256}"
    )


def _bound_pieces(bound: BoundValidation, repo: Path) -> tuple[tuple[str, str], ...]:
    """The bound apply protocol, its result, its recorded model, and today's
    model entry and prompt as prompt pieces; what is missing is said, never
    skipped."""
    area = bound.protocol.parent
    pieces = [(f"FILE: {shown(bound.protocol, repo)}", bound.text)]
    metrics = metrics_path(run_path(area, bound.run))
    try:
        pieces.append(
            (f"FILE: {shown(metrics, repo)}", metrics.read_text(encoding="utf-8"))
        )
    except OSError:
        pieces.append(
            (
                "EVIDENCE: validation result",
                f"run {bound.run} adopted, but {shown(metrics, repo)} does not read",
            )
        )
    pieces.append(
        (
            "EVIDENCE: validation model, as its run recorded it",
            recorded_models(run_path(area, bound.run)),
        )
    )
    # today's settings, for comparing with the computation's own model and
    # prompt — labelled, since they may have changed after the validation
    bound_model = protocol_block.model(bound.text)
    alias = bound_model.alias if bound_model is not None else None
    pieces.append(
        (
            "EVIDENCE: current configuration of the validation's alias",
            f"{CURRENT_ONLY}\n{model_entry(alias, area)}",
        )
    )
    try:
        registered = prompt_blocks(bound.protocol)
    except ValueError as exc:  # shown to the auditor, not a crash of the bundle
        registered = [f"UNREADABLE: {unread_prompt_field(bound.protocol.name, exc)}"]
    prompts = registered + [
        f"{name} = {value!r}" for name, value in sorted(prompt_constants(area).items())
    ]
    pieces.append(
        (
            "EVIDENCE: current prompt sources of the validation",
            f"{CURRENT_ONLY}\n"
            + ("\n\n".join(prompts) or "no Prompt block and no PROMPT constant found"),
        )
    )
    return tuple(pieces)


#: how a declared evidence file's piece opens: `EVIDENCE FILE: <path> (sha256 <hex>)`
EVIDENCE_FILE_LABEL = "EVIDENCE FILE: "
#: operating limits of the declared evidence files, not thresholds of
#: meaning: past either the audit refuses before the call, naming each file
#: and its size, rather than show a cut file (set 2026-11-25 above the
#: largest file the motivating area declares, 135 kB, and its 160 kB total)
EVIDENCE_FILE_MAX_BYTES = 200_000
EVIDENCE_FILES_MAX_BYTES = 400_000


@dataclass(frozen=True)
class CheckedEvidenceFile:
    """A declared evidence file that passed `checked_evidence_files`: NAME
    its path as the prompt shows it (from the repository root), SHA256 the
    declared digest (its bytes' digest), TEXT its whole content."""

    name: str
    sha256: str
    text: str


def evidence_file_pieces(
    protocol: Path, text: str, snap: scope_sha.Snapshot
) -> tuple[tuple[str, str], ...]:
    """The files TEXT (the text of PROTOCOL) declares in `[[evidence_file]]`
    as prompt pieces, in the order declared, each in full under
    `EVIDENCE FILE: <path> (sha256 <hex>)` — the bytes of SNAP, the ones the
    record's sha covers (`scope_sha.evidence_file_basis`). () without a
    declaration. Raises AuditError, before any model call, as
    `checked_evidence_files` does."""
    return tuple(
        (f"{EVIDENCE_FILE_LABEL}{ef.name} (sha256 {ef.sha256})", ef.text)
        for ef in checked_evidence_files(protocol, text, snap.evidence_files)
    )


def checked_evidence_files(
    protocol: Path, text: str, contents: Mapping[Path, bytes]
) -> tuple[CheckedEvidenceFile, ...]:
    """The files TEXT (the text of PROTOCOL) declares in `[[evidence_file]]`,
    in the order declared, checked as the audit shows them — the one home
    of these checks, for the audit (`evidence_file_pieces`) and for
    `protocol-fill --evidence-file`, which runs them on the protocol as it
    would be written. CONTENTS maps each declared file that is a file,
    resolved, to its bytes (`scope_sha.evidence_file_basis`,
    `scope_sha.declared_evidence_bytes`); a declared file missing from it
    is not a file, or — while the path is a file — one that does not read.
    () without a declaration.

    Raises AuditError naming each file it holds: a declared file whose
    path leads out of the repository (`evidence_outside_repo_refusal`),
    before anything else is asked of it; one that is
    not a file; one that does not read (`evidence_unreadable_refusal`);
    one whose sha256 is no longer the declared one; one over
    EVIDENCE_FILE_MAX_BYTES, or all together over EVIDENCE_FILES_MAX_BYTES
    (`evidence_size_refusal`); one that is not UTF-8 text. Nothing is
    dropped or cut. BlockError on a malformed table."""
    declared = protocol_block.evidence_files(text)
    if not declared:
        return ()
    outside = [
        (evidence_file_name(protocol, ef.path), target)
        for ef in declared
        if (target := scope_sha.evidence_target_outside_repo(protocol, ef.path))
        is not None
    ]
    if outside:
        raise evidence_outside_repo_refusal(protocol.name, outside)
    # (path as the prompt names it, declared sha256, the snapshot's bytes)
    found: list[tuple[str, str, bytes | None]] = [
        (
            evidence_file_name(protocol, ef.path),
            ef.sha256,
            contents.get((protocol.parent / ef.path).resolve()),
        )
        for ef in declared
    ]
    unread = [
        evidence_file_name(protocol, ef.path)
        for ef, (_, _, data) in zip(declared, found)
        if data is None and (protocol.parent / ef.path).is_file()
    ]
    if unread:
        raise evidence_unreadable_refusal(protocol.name, unread)
    gone = [name for name, _, data in found if data is None]
    if gone:
        raise AuditError(
            f"{protocol.name} declares evidence file(s) that are not a file: "
            f"{', '.join(gone)}",
            fix="write the file, or remove its [[evidence_file]] table",
        )
    held = [(name, sha, data) for name, sha, data in found if data is not None]
    changed = [
        f"{name} (declared sha256 {sha}, now {digests.digest(data, None)})"
        for name, sha, data in held
        if digests.digest(data, None) != sha
    ]
    if changed:
        raise AuditError(
            f"{protocol.name}: evidence file(s) changed after their declaration: "
            f"{'; '.join(changed)} — the auditor would read other bytes than "
            f"the ones declared",
            fix="restore the declared file, or check that the file as it stands "
            "is the one the audit is to read and write its sha256 into the "
            "table's `sha256`",
        )
    too_large = evidence_size_refusal(
        protocol.name, [(name, len(data)) for name, _, data in held]
    )
    if too_large is not None:
        raise too_large
    checked: list[CheckedEvidenceFile] = []
    unreadable: list[str] = []
    for name, sha, data in held:
        try:
            checked.append(CheckedEvidenceFile(name, sha, data.decode("utf-8")))
        except UnicodeDecodeError:
            unreadable.append(name)
    if unreadable:
        raise AuditError(
            f"{protocol.name}: evidence file(s) not UTF-8 text: "
            f"{', '.join(unreadable)} — the prompt shows text only",
            fix="declare a text form of the file (JSON, CSV, Markdown)",
        )
    return tuple(checked)


def evidence_file_name(protocol: Path, path: str) -> str:
    """The declared PATH of PROTOCOL as the prompt and every refusal name
    it: from the repository root."""
    where = shown(protocol.parent, layout_root(protocol.parent))
    return path if where == "." else f"{where}/{path}"


def evidence_outside_repo_refusal(
    protocol_name: str, outside: list[tuple[str, Path]]
) -> AuditError:
    """The refusal of declared evidence files whose path leads out of the
    repository through a symlink (OUTSIDE: the file as `evidence_file_name`
    gives it, and where it leads) — for the audit and for `protocol-fill
    --evidence-file` alike. A link that stays inside the repository, as one
    to another area's data, is not refused."""
    return AuditError(
        f"{protocol_name}: evidence file(s) that lead out of the repository: "
        + ", ".join(f"{name} (leads to {target})" for name, target in outside)
        + " — another clone of the repository does not hold the file, so the "
        "audit does not read it",
        fix="copy the file into the repository and declare the copy, or remove "
        "its [[evidence_file]] table",
    )


def evidence_unreadable_refusal(protocol_name: str, names: list[str]) -> AuditError:
    """The refusal of declared evidence files (NAMES, as
    `evidence_file_name` gives them) that are files and do not read — a
    permission, an I/O error — for the audit and for `protocol-fill
    --evidence-file` alike."""
    return AuditError(
        f"{protocol_name}: evidence file(s) that cannot be read: "
        f"{', '.join(names)} — the auditor would be shown nothing of them",
        fix="make the file readable (its permissions), or remove its "
        "[[evidence_file]] table",
    )


def evidence_size_refusal(
    protocol_name: str, sizes: list[tuple[str, int]]
) -> AuditError | None:
    """The refusal of declared evidence files past the operating limits —
    one of SIZES (file as shown, bytes) over EVIDENCE_FILE_MAX_BYTES, or
    their sum over EVIDENCE_FILES_MAX_BYTES — naming each file over the
    limit and every file's size; None within both."""
    large = [f"{name} ({n} bytes)" for name, n in sizes if n > EVIDENCE_FILE_MAX_BYTES]
    total = sum(n for _, n in sizes)
    if not large and total <= EVIDENCE_FILES_MAX_BYTES:
        return None
    return AuditError(
        f"{protocol_name}: evidence past the audit's operating limit "
        f"({EVIDENCE_FILE_MAX_BYTES} bytes a file, {EVIDENCE_FILES_MAX_BYTES} "
        f"in all): "
        + (f"{', '.join(large)}; " if large else "")
        + f"{total} bytes in all ("
        + ", ".join(f"{name} {n}" for name, n in sizes)
        + ") — no evidence is cut from what the auditor reads, so the audit "
        "does not run",
        fix="declare a smaller file that holds what the audit must read, or "
        "raise the limit in labkit with the measured sizes",
    )


def render(
    mode: str,
    area: Path,
    protocol: Path,
    code: list[Path],
    standard: Path | None,
    indexed: list[Path] | None = None,
    *,
    source: Source,
) -> str:
    """The one prompt: instructions, MODE line, then every piece verbatim
    under a `===== <label> =====` line — the files, the cited rules of the
    standard (when `standard` is given), the index of the deeper modules
    (when `indexed` is given), in MODE analysis the answering run's rows.
    Clarity: README and script around the protocol, no standard, no index.
    Every file's text comes from SOURCE, never from the disk again."""
    repo = layout_root(area)

    def rel(p: Path) -> str:
        return shown(p, repo)

    def file(p: Path) -> tuple[str, str]:
        text = source.protocol_text if p == protocol else source.read(p)
        return f"FILE: {rel(p)}", text

    if mode == CLARITY:
        pieces = [file(p) for p in (code[0], protocol, *code[1:])]
    else:
        pieces = [file(p) for p in (protocol, *code)]
        if standard is not None:
            label, text = standard_excerpt(mode)
            pieces.append((f"FILE: {label}", text))
        if indexed:
            pieces.append((INDEX_LABEL, module_index(indexed, repo, source.read)))
        pieces += source.evidence
        if mode == ANALYSIS:
            pieces += source.run
            pieces += source.fixes
            # the ways out by cause, so a finding's repair names one of
            # them: a repair proposing a new constant after the first
            # measurement leads into report-check's refusal
            # the protocol as shown: its block read when the audit stamped
            # it (`promises.block_stamp` raises first), so no PromiseError
            # here; the audit holds one protocol, as `--decide` does
            routes = ways_out.blocker_routes(
                bool(promises.table_ids(source.protocol_text))
            )
            pieces.append((WAYS_OUT_LABEL, "\n".join(routes)))
    body = prompt_body(pieces)
    return (
        f"{instructions(mode)}\n\nMODE: {mode} · AREA: {rel(area)}\n\n"
        f"{INLINE_NOTE}\n\n{body}"
    )


#: the label of the piece that shows the earlier decided BLOCKERs
EARLIER_LABEL = "EARLIER DECIDED BLOCKERS AND CORRECTIONS"
#: the label of the piece that shows the ways out of a BLOCKER (MODE analysis)
WAYS_OUT_LABEL = "WAYS OUT OF A BLOCKER"
#: operating limits of that piece, not thresholds of meaning: past either
#: the audit refuses, loudly, rather than show a cut list (revisit with
#: the sizes records keep under `followup`)
EARLIER_MAX_ENTRIES = 40
EARLIER_MAX_BYTES = 60_000


class ValueThen(NamedTuple):
    """A field's value in one earlier text of the protocol: its VALUE there
    (`protocol_history.ABSENT` where that text does not hold the field),
    None when the text cannot be read back; WHERE naming the text (the run
    that saw it, its commit), or saying why it cannot be read."""

    value: str | None
    where: str


class FieldChange(NamedTuple):
    """A corrected field as the follow-up shows it, each value under the
    name of the text it comes from; no text stands in for another.

    Attributes:
        label: The field's label.
        first_measured: The field in the text of the protocol's first
            measurement (`registrations_as_first_measured`) — the first
            registration while `first_untold` is "". With `first_untold`
            filled it is the first measurement that reads: evidence, not
            established as the first registration, and None where no
            measurement is listed at all.
        run_audited: The field in the own text of the run audited
            (`as_measured`); None without a run audited.
        now: The field as the protocol stands.
        first_untold: Why the first measurement of the protocol is not
            told (the sentences of `registration_hold.untold_first_holds`);
            "" when it is told. Filled, the first registration and the
            workflow that binds the runs are undetermined.
        compared_with_run_audited: True where the change to judge is taken
            against `run_audited` (an exploratory workflow with a run
            audited, `registration_hold.run_compared_with`); False where
            against the first registration — a confirmatory or undecided
            workflow, and every protocol without a run audited.
    """

    label: str
    first_measured: ValueThen | None
    run_audited: ValueThen | None
    now: str
    first_untold: str
    compared_with_run_audited: bool


class Followup(NamedTuple):
    """What an analysis audit is shown to judge earlier decisions, taken
    once: the ENTRIES — the area's earlier decided BLOCKERs
    (`followup.earlier_blockers`), then its earlier corrections of a
    protocol field (`followup.earlier_corrections`) —, the answering run's
    metrics.json as the prompt shows it (`RunShown.metrics`; None when it
    shows none), the origin of each shown finding's chain (its ref → the
    origin's finding), and for each correction the change it is judged on
    (its ref → `FieldChange`)."""

    entries: list[followup.Member]
    metrics: dict | None
    origins: dict[str, findings.Finding]
    changes: dict[str, FieldChange]

    def check_present(self, e: followup.Member) -> bool | None:
        """Whether E's required check key stands in the metrics shown —
        None when E requires no check. From the snapshot the prompt
        renders, never from the file read again."""
        if not e.finding.check:
            return None
        return self.metrics is not None and e.finding.check in self.metrics


def required_check_line(f: findings.Finding, metrics: dict | None) -> str:
    """The line a prompt shows under F when F requires a check: the
    metrics.json key with its note and its whole value as METRICS shows it
    (a `file:` check: where the dependency is shown whole; a `diff:` check:
    where the requested diff is), or that it is
    missing; "" when F requires none. METRICS is the snapshot the prompt
    renders (`RunShown.evidence`), never the file read again. The one
    wording of the follow-up piece (`earlier_piece`) and the decision
    review (`decision_review.decisions_text`)."""
    if not f.check:
        return ""
    note = f" ({f.check_note})" if f.check_note else ""
    present = metrics is not None and f.check in metrics
    if present and f.check.startswith(
        (required_check.FILE_CHECK, *required_check.REQUEST_CHECKS)
    ):
        return f"required check `{f.check}`{note}: shown above under `{(metrics or {})[f.check]}`"
    if present:
        value = json.dumps((metrics or {})[f.check], ensure_ascii=False)
        return f"required check `{f.check}`{note} = {value}"
    if f.check.startswith(required_check.REQUEST_CHECKS):
        return (
            f"required check `{f.check}`: not shown — its `REQUESTED` "
            f"piece above says why"
        )
    if f.check.startswith(required_check.FILE_CHECK):
        return (
            f"required check `{f.check}`: not among the answering run's "
            f"dependencies shown whole"
        )
    return f"required check `{f.check}`: missing in the answering run's metrics.json"


#: the names under which the follow-up prints a corrected field's values,
#: one per text (`field_change_lines`)
AS_FIRST_REGISTERED = "as first registered"
FIRST_THAT_READS = (
    "in the first measurement whose text can be read back — evidence, not "
    "established as the "
    "first registration"
)
IN_RUN_AUDITED = "in the audited run's own text"


#: the name of the section of the follow-up piece that shows each field
#: text once (`field_texts_lines`), and how an entry points into it
FIELD_TEXTS = "FIELD TEXTS"
#: unchanged words a word diff keeps on each side of a change
#: (`word_diff`); a longer unchanged run is cut to its ends around `…` —
#: both texts stand in full above the diff, so the cut hides nothing
DIFF_CONTEXT_WORDS = 8
#: the size from which a field text printed twice moves all the piece's
#: texts, short ones included, under `FIELD TEXTS` (`field_text_numbers`):
#: a shorter repeated one ("3 documents") reads better at each entry than
#: as a number, and its repetition costs less than the section's head; a
#: protocol field of a long area (7 kB, argmining27 experiment 15) is far
#: above it
FIELD_TEXT_ONCE_MIN = 500

#: the field texts of a follow-up piece, each (label, value) → its number
FieldTextNumbers = dict[tuple[str, str], int]


def field_text_ref(label: str, value: str, numbers: FieldTextNumbers) -> str:
    """VALUE of field LABEL as an entry prints it: the value itself, or,
    when NUMBERS shows it under `FIELD TEXTS`, the number it stands under
    there."""
    n = numbers.get((label, value))
    if n is None:
        return value
    return f"field text {n}, under {FIELD_TEXTS} below"


def value_then_line(
    label: str, name: str, then: ValueThen, numbers: FieldTextNumbers | None = None
) -> str:
    """The line that shows field LABEL in one earlier text, under NAME, the
    name of that text: the text's place and the value (or the number it
    stands under in NUMBERS, `field_text_ref`), or that the text cannot be
    read back and why."""
    if then.value is None:
        return f"{label} {name}: cannot be read back — {then.where}"
    return f"{label} {name} ({then.where}): {field_text_ref(label, then.value, numbers or {})}"


def shown_values(change: FieldChange) -> list[str]:
    """The field texts `field_change_lines` prints for CHANGE, in the order
    printed: each value that can be read back and is not `ABSENT` (a text
    that does not hold the field, printed as the marker itself)."""
    then = [t.value for t in (change.first_measured, change.run_audited) if t]
    return [v for v in [*then, change.now] if v is not None and v != ABSENT]


def judged_pair(change: FieldChange) -> tuple[str, str] | None:
    """The two texts of CHANGE's change to judge, (from, to), as its
    `change to judge` line names them: from the audited run's own text
    where the change is taken against it, else from the first
    registration. None where there is nothing to diff: the first
    registration is the benchmark and undetermined, a text cannot be read
    back or does not hold the field, or both texts are equal."""
    if change.compared_with_run_audited:
        before = change.run_audited
    elif change.first_untold:
        return None
    else:
        before = change.first_measured
    if before is None or before.value in (None, ABSENT) or change.now == ABSENT:
        return None
    if before.value == change.now:
        return None
    return before.value, change.now


def field_text_numbers(changes: Sequence[FieldChange]) -> FieldTextNumbers:
    """The number of each field text CHANGES print (`shown_values`),
    numbered from 1 in the order first printed — or {} when no text of
    `FIELD_TEXT_ONCE_MIN` bytes or more would be printed twice: then each
    value stands at its entry, as for a single correction with distinct
    texts or a short text repeated. One such repeated text numbers them
    all, so a piece has one layout: every field text at its entry, or
    every one once under `FIELD TEXTS`."""
    printed = [(c.label, v) for c in changes for v in shown_values(c)]
    repeated = {key for key in printed if printed.count(key) > 1}
    if not any(len(v.encode("utf-8")) >= FIELD_TEXT_ONCE_MIN for _, v in repeated):
        return {}
    numbers: FieldTextNumbers = {}
    for key in printed:
        numbers.setdefault(key, len(numbers) + 1)
    return numbers


def _unchanged(words: list[str], *, first: bool, last: bool) -> list[str]:
    """The words a word diff keeps of an unchanged run WORDS: up to
    `DIFF_CONTEXT_WORDS` after the change before it (none when FIRST) and
    before the change after it (none when LAST), the cut marked `…`."""
    n = DIFF_CONTEXT_WORDS
    head = [] if first else words[:n]
    tail = [] if last else words[-n:]
    if len(words) <= len(head) + len(tail):
        return words
    return [*head, "…", *tail]


def word_diff(old: str, new: str) -> str:
    """The change from OLD to NEW as one line of words: removed words as
    `[-…-]`, added words as `{+…+}`, unchanged runs cut to their ends
    (`_unchanged`). Whitespace is folded, as the registration compares a
    field; texts equal but for whitespace say so. Words, not lines: a
    protocol field is one paragraph on one line, and a line diff of it
    would repeat both texts whole."""
    a, b = old.split(), new.split()
    if a == b:
        return "the two texts differ in whitespace only"
    # autojunk off: in a field of a thousand words it would treat the
    # common words as junk and diff around them
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    out: list[str] = []
    for k, (tag, i1, i2, j1, j2) in enumerate(ops):
        if tag == "equal":
            out += _unchanged(a[i1:i2], first=k == 0, last=k == len(ops) - 1)
        if tag in ("replace", "delete"):
            out.append("[-" + " ".join(a[i1:i2]) + "-]")
        if tag in ("replace", "insert"):
            out.append("{+" + " ".join(b[j1:j2]) + "+}")
    return " ".join(out)


def field_texts_lines(
    changes: Sequence[FieldChange], numbers: FieldTextNumbers
) -> list[str]:
    """The `FIELD TEXTS` section of the follow-up piece: each field text of
    NUMBERS once in full, indented, under its number, its field's label,
    its digest and its size; then each change to judge of CHANGES
    (`judged_pair`) once, as a word diff (`word_diff`) between the two
    numbered texts. [] when NUMBERS is empty."""
    if not numbers:
        return []
    lines = [
        f"{FIELD_TEXTS} — each field text the entries above name by number, "
        f"once in full (one number per distinct text: entries that show the "
        f"same text name the same number), with the sha256 of its UTF-8 bytes "
        f"and its size; then each change to judge between two texts that read "
        f"and differ, once, as a word diff (whitespace folded): removed words "
        f"as [-…-], added words as {{+…+}}, unchanged words past "
        f"{DIFF_CONTEXT_WORDS} on either side of a change cut to …. The diff "
        f"points to the change; the full texts are the evidence"
    ]
    for (label, value), n in numbers.items():
        data = value.encode("utf-8")
        lines.append(
            f"field text {n} · {label} · sha256 {digests.digest(data)} · "
            f"{len(data)} bytes:"
        )
        lines += [f"  {line}" for line in value.split("\n")]
    pairs = dict.fromkeys(
        (c.label, *pair) for c in changes if (pair := judged_pair(c)) is not None
    )
    for label, old, new in pairs:
        lines.append(
            f"change to judge, field text {numbers[(label, old)]} → field text "
            f"{numbers[(label, new)]} ({label}):"
        )
        lines.append(f"  {word_diff(old, new)}")
    return lines


#: what the follow-up tells the auditor while the first registration is
#: undetermined: the missing evidence is named as missing, no verdict is
#: prescribed, and none lifts finalize's hold (`untold_first_holds`)
NOT_ASSESSABLE_WITHOUT_FIRST = (
    "Whether the first registration was kept cannot be assessed from this "
    "evidence. A verdict does not replace the missing evidence and does not "
    "lift the hold on the release. Judge what the evidence shown does support"
)


def field_change_lines(
    change: FieldChange, numbers: FieldTextNumbers | None = None
) -> list[str]:
    """The lines the follow-up prints for a corrected field, in this order:

    1. first measurement untold (`first_untold`): that the first
       registration is undetermined, and why — and that no verdict
       stands in for it: whether the first registration was kept cannot
       be assessed, and the hold stays (`NOT_ASSESSABLE_WITHOUT_FIRST`);
    2. the field in the first measurement's text — as first registered,
       or, first measurement untold, as evidence that is not established
       as the first registration (no line where no measurement is listed);
    3. with a run audited: the field in that run's own text;
    4. the field now;
    5. which of these the change to judge is taken against;
    6. with NUMBERS, where that change's word diff stands under
       `FIELD TEXTS` (none where `judged_pair` gives none).

    Equal values are printed on their own lines all the same: each line
    names the text its value comes from. A value NUMBERS holds is printed
    as the number it stands under in the piece's `FIELD TEXTS`
    (`field_text_ref`); without NUMBERS every value stands here."""
    numbers = numbers or {}
    lines = []
    if change.first_untold:  # 1
        lines.append(
            f"first registration: undetermined — {change.first_untold}. "
            f"Which workflow binds this protocol's runs is undetermined too. "
            f"No value below is established as the first registration. "
            f"{NOT_ASSESSABLE_WITHOUT_FIRST}"
        )
    if change.first_measured is not None:  # 2
        name = FIRST_THAT_READS if change.first_untold else AS_FIRST_REGISTERED
        lines.append(
            value_then_line(change.label, name, change.first_measured, numbers)
        )
    if change.run_audited is not None:  # 3
        lines.append(
            value_then_line(change.label, IN_RUN_AUDITED, change.run_audited, numbers)
        )
    now = field_text_ref(change.label, change.now, numbers)
    lines.append(f"{change.label} now: {now}")  # 4
    # 5
    if change.compared_with_run_audited and change.first_untold:
        lines.append(
            f"change to judge: from the value {IN_RUN_AUDITED} to the value now — "
            f"the first measurement whose text can be read back registered an "
            f"exploratory protocol, where each run is held to its own text"
        )
    elif change.compared_with_run_audited:
        lines.append(
            f"change to judge: from the value {IN_RUN_AUDITED} to the value now — "
            f"in an exploratory workflow each run is held to its own text; the "
            f"first registration is context"
        )
    elif change.first_untold:
        lines.append(
            "change to judge: from the first registration to the value now — and "
            "the first registration is undetermined: no value shown here is that "
            "benchmark, and a value marked as evidence does not stand in for it"
        )
    elif change.run_audited is not None:
        lines.append(
            f"change to judge: from the value {AS_FIRST_REGISTERED} to the value "
            f"now — the first registration is the benchmark; the audited run's "
            f"own text shows what that run was measured under"
        )
    else:
        lines.append(
            f"change to judge: from the value {AS_FIRST_REGISTERED} to the value now"
        )
    pair = judged_pair(change)
    if numbers and pair is not None:
        old, new = (numbers[(change.label, v)] for v in pair)
        lines.append(
            f"word diff: under {FIELD_TEXTS} below, field text {old} → field text {new}"
        )
    return lines


def earlier_piece(shown: Followup) -> tuple[tuple[str, str], ...]:
    """What MODE analysis shows of the earlier decisions: one `(label,
    text)` piece with every earlier decided BLOCKER and correction as
    `<record>#<n>`, its text, its recorded subject, its
    decision (status, reason, effect), for a
    correction the field's values, each under the name of the text it
    comes from, and the change to judge (`field_change_lines`), and, when
    the finding requires a check, that metrics.json key with its note and
    its whole value as shown, or that it is missing — or one piece saying
    there is none.

    A field text of `FIELD_TEXT_ONCE_MIN` bytes or more that the
    corrections would print more than once (several corrections of one
    field, or one text equal to another) is printed in full only once: then
    every field text of the piece stands once in full under `FIELD TEXTS`
    after the entries, each entry names the number of its texts, and
    each change to judge follows there once as a word diff
    (`field_text_numbers`, `field_texts_lines`). No field text is dropped
    (the diff folds whitespace and cuts unchanged runs; the texts do not); the
    operating limits are measured on the piece as printed."""
    if not shown.entries:
        return (
            (
                EARLIER_LABEL,
                "none: no earlier decided BLOCKER or correction in this area",
            ),
        )
    changes = [shown.changes[e.ref] for e in shown.entries if e.ref in shown.changes]
    numbers = field_text_numbers(changes)
    entries = []
    for e in shown.entries:
        f = e.finding
        effect = f" (effect: {f.effect})" if f.effect else ""
        # the recorded subject, not the word in the text: a carried finding a
        # follow-up settled keeps its origin's `undetermined` in its text, and
        # a verdict judged by that word is refused
        entry = (
            f"{e.ref}\n  finding: {f.text}\n  subject: {f.subject}\n"
            f"  decided: {f.status}{effect} — "
            f"{f.reason or '(no reason given)'}"
        )
        change = shown.changes.get(e.ref)
        if change is not None:
            entry += "".join(
                f"\n  {line}" for line in field_change_lines(change, numbers)
            )
        line = required_check_line(f, shown.metrics)
        if line:
            entry += f"\n  {line}"
        entries.append(entry)
    text = "\n".join([*entries, *field_texts_lines(changes, numbers)])
    size = len(text.encode("utf-8"))
    if len(entries) > EARLIER_MAX_ENTRIES or size > EARLIER_MAX_BYTES:
        raise AuditError(
            f"{len(entries)} earlier decided BLOCKERs and corrections, {size} bytes — past the "
            f"follow-up's operating limit ({EARLIER_MAX_ENTRIES} entries, "
            f"{EARLIER_MAX_BYTES} bytes); none is cut from what the auditor must "
            f"judge, so the audit does not run",
            fix="settle earlier findings, or raise the limit in labkit with the "
            "measured sizes",
        )
    return ((EARLIER_LABEL, text),)


def decisions_moved(earlier: list[followup.Member], area: Path) -> list[str]:
    """The refs in EARLIER whose decision is no longer the one the prompt
    showed — the record re-read now, gone or another digest. A verdict on a
    decision that changed while the auditor read it judges neither."""
    now = {
        ref: finding_decisions.decision_digest(m.finding)
        for ref, m in followup.chain(audit_records.area_records(area)).members.items()
    }
    return [
        e.ref
        for e in earlier
        if now.get(e.ref) != finding_decisions.decision_digest(e.finding)
    ]


def followup_size(shown: Followup) -> tuple[int, int]:
    """(entries, bytes) of the follow-up piece SHOWN renders — what the
    record keeps to revisit the operating limits."""
    ((_, text),) = earlier_piece(shown)
    return len(shown.entries), len(text.encode("utf-8")) if shown.entries else 0


def carried_of(
    shown: Followup, fixes: list[findings.FixVerdict]
) -> list[findings.Finding]:
    """The findings the new record carries: one per shown BLOCKER whose
    verdict is not `resolved` (`followup.carried_finding`). A shown one
    without a verdict is not carried — unchecked, it stays where it is. A
    correction of another grade is not carried: without its `resolved` the
    field's change stays held where finalize compares it."""
    by_ref = {e.ref: e for e in shown.entries}
    return [
        followup.carried_finding(by_ref[v.ref], v, shown.origins[v.ref])
        for v in fixes
        if v.verdict != "resolved" and by_ref[v.ref].finding.grade == BLOCKER
    ]


def earlier_of(
    area: Path,
    protocol: Path,
    pid: str,
    current: Callable[[findings.Record], bool],
    metrics: dict | None,
    run: Path | None = None,
) -> Followup:
    """The follow-up of PROTOCOL (stamped id PID) in AREA: the earlier
    decided BLOCKERs and corrections of a field of PROTOCOL
    (`followup.earlier_corrections`, `finding_decisions.corrected_field`) of the
    area's records that name PID — those of a record that CURRENT does not
    tell as the state now audited — with the origin of each, each
    correction's change — a BLOCKER's too — (`FieldChange`: the field as
    the text the hold compares with holds it, `_field_change`, and as it
    reads now), and METRICS as shown. RUN is the run audited, None without
    one. A record of another protocol of the area is not followed up
    here: it judged another question. Raises AuditError when the records
    do not read (`findings.FindingsError`) or a finding's place names no
    single field."""
    records = followup.protocol_records(area, pid)
    text = protocol.read_text(encoding="utf-8")

    def field_of(f: findings.Finding) -> str | None:
        """The field F corrects in PROTOCOL, or None. Raises AuditError
        when F's place begins several fields or means one written twice
        (`finding_decisions.corrected_field`)."""
        try:
            return finding_decisions.corrected_field(f, protocol, text)
        except protocol_check.FieldPlaceError as exc:
            raise ways_out.unclear_correction(f.one_line, protocol.name, exc) from exc

    try:
        c = followup.chain(records)
        blockers = followup.earlier_blockers(records, current)
        corrections = followup.earlier_corrections(records, current, field_of)
    except findings.FindingsError as exc:
        raise AuditError(str(exc), fix=audit_records.record_way(area)) from exc
    shown = blockers + corrections
    origins = {e.ref: c.members[c.origin[e.ref]].finding for e in shown}
    changes = {
        e.ref: _field_change(protocol, text, e.finding, run)
        for e in shown
        if field_of(e.finding) is not None
    }
    return Followup(shown, metrics, origins, changes)


def _field_change(
    protocol: Path, text: str, f: findings.Finding, run: Path | None
) -> FieldChange:
    """The change of the field F corrects in PROTOCOL (TEXT now), each
    value from its own text (`FieldChange`):

    1. the field in the first measurement's text
       (`registrations_as_first_measured`) — the first registration;
    2. with RUN, the run audited: the field in RUN's own text
       (`as_measured`);
    3. the field now;
    4. which of 1 and 2 the change is taken against: the hold's own answer
       (`registration_hold.run_compared_with` over the protocol's workflow,
       `registration_hold.workflow`). In an exploratory workflow RUN's own
       text — there the hold compares the protocol as it stands with the
       answering run, and a verdict releases only the change it judged.
       Else, and without a RUN, the first registration: a field changed
       after it stays visible as a change, whatever a later run saw.

    While something leaves the first measurement untold, the workflow that
    binds is UNDECIDED and finalize holds the release. The change then
    says why (`FieldChange.first_untold`), 1 is the first measurement that
    reads, as evidence only (none where no measurement is listed), and 4
    is answered as the first measurements whose text reads registered
    (`registration_hold.workflow_of_first_texts`), so RUN's own text is
    not exchanged for another. Where a text cannot be read back, its
    value is None with the reason; no other text stands in.
    Raises RuntimeError when git fails."""
    at = f.place
    if at is None:
        raise ValueError(f"{f.one_line}: names no field of {protocol.name}")
    # called only for a field `corrected_field` named, so any unclear place
    # here is a fault of the caller and raises
    hit = protocol_check.field_at(text, at[1])

    def value_in(then: str | None, where: str) -> ValueThen:
        """The field in the earlier text THEN, read from WHERE."""
        if then is None:
            return ValueThen(None, where)
        old = protocol_check.named_field(then, hit.label)
        return ValueThen(old.value if old is not None else ABSENT, where)

    pid = protocol_block.head(text).id
    if pid is None:
        no_id = ValueThen(None, "the protocol has no id")
        return FieldChange(
            hit.label, no_id, no_id if run is not None else None, hit.value, "", False
        )
    state = state_of(protocol.parent)
    measured = state.measured_of(pid)
    root = git_root(protocol)
    binding = workflow(
        protocol.parent,
        protocol,
        pid,
        root,
        measured,
        history_unread=state.history_unread,
    )
    first_untold = "; ".join(hold.text for hold in binding.untold)
    # 1
    if first_untold and not measured.first_groups:
        # untold with no measurement listed: no text to show as evidence
        first_measured = None
    else:
        # told with no measurement yet: the protocol as it stands is the
        # registration, and `registrations_as_first_measured` says so
        # an untold first measurement: the run that reads is named as a
        # run, not as "its first measurement"
        texts, why = registrations_as_first_measured(
            protocol,
            measured.first_groups,
            root,
            role="run" if first_untold else FIRST_MEASUREMENT,
        )
        first_measured = value_in(*texts[0]) if texts else ValueThen(None, why)
    # 2
    run_audited = (
        value_in(
            *as_measured(protocol, read_run_dir(run), root, role="the run audited")
        )
        if run is not None
        else None
    )
    # 4
    shown_by = (
        workflow_of_first_texts(protocol, root, measured)
        if first_untold
        else binding.workflow
    )
    return FieldChange(
        hit.label,
        first_measured,
        run_audited,
        hit.value,
        first_untold,
        compared_with_run_audited=run_compared_with(shown_by, run) is not None,
    )


class Stamp(NamedTuple):
    """The area's stamp as the auditor saw it: taken ONCE, before the call.
    Taken after the model answered (up to 900 s later), a lib module edited
    meanwhile would give a record whose sha no auditor had read."""

    sha: str
    files: list[Path]


@dataclass(frozen=True)
class BoundPrompt:
    """An audit prompt and what its record binds, from one reading
    (`bound_prompt`): the PROMPT; the code STAMP with the files it covers;
    the STATE the record binds (`findings.AuditedState`: code, promises,
    registration and, in MODE analysis, the run shown and the digest of
    what is shown of it); the INDEXED files (stamped, not read in full);
    SHOWN_NOW, the earlier repairs shown (`Followup`); PROTOCOL_ID, the
    stamped id of the protocol read, which the record names; in MODE
    analysis the RUN_DIR shown (None: none) and the protocol TEXT read,
    from which `shown_after` takes the state again."""

    prompt: str
    stamp: Stamp
    state: findings.AuditedState
    indexed: list[Path]
    earlier_repairs: Followup
    protocol_id: str
    run_dir: Path | None = None
    text: str = ""


def shown_after(
    area: Path, bound: BoundPrompt, fixes: Sequence[findings.FixVerdict]
) -> str | None:
    """The `shown_sha` the record of BOUND writes, given its verdicts FIXES:
    BOUND's own, unless FIXES judge a requested diff (`followup.JUDGING`)
    — then the digest of the state after them (`run_shown` with ALSO), in
    which that request is no longer shown whole, so the record still
    covers the state once it stands. Only when the state is still the one
    the prompt showed: had the area moved while the auditor read, the
    record binds what it was shown and covers nothing newer."""
    judging = [
        v
        for v in fixes
        if v.verdict in followup.JUDGING
        and v.check_present
        and v.check.startswith(required_check.REQUEST_CHECKS)
    ]
    if not judging or bound.state.shown_sha is None:
        return bound.state.shown_sha
    run_dir = bound.run_dir
    if run_shown(area, run_dir, "", bound.text).sha != bound.state.shown_sha:
        return bound.state.shown_sha
    return run_shown(area, run_dir, "", bound.text, judging).sha


def bound_prompt(mode: str, area: Path, reading: AuditInputs) -> BoundPrompt:
    """The prompt and what its record binds (`BoundPrompt`) from ONE
    reading:
    the record binds what the prompt shows. The code is one snapshot: its
    bytes render the prompt, its sha goes in the record, and every stamped
    file the reading does not take in full is indexed — so the prompt shows
    each file the stamp covers, no more and no fewer (an `[[evidence_file]]`
    another protocol of the area declares is stamped, not shown:
    `scope_sha.evidence_file_basis`). The promise block and
    the registration (`protocol_check.registration_stamp`) come from the one
    protocol text the prompt carries; in MODE analysis
    the run is chosen once, and what the prompt shows of it is one snapshot
    whose digest goes in the record (NO_RUN when none answers), and the
    area's earlier decided BLOCKERs (`followup.earlier_blockers`) are read
    once: the prompt shows them, and each
    verdict on one is bound to the decision shown (`audit_reply.parse_fixes`).

    The reading's file list was taken before the snapshot. After rendering,
    the list, the snapshot and the protocol are taken again; any change
    means the prompt rests on a list or bytes the area no longer has, and
    the audit is refused (AuditError) — a file added in between would stand
    in the stamp and not in the prompt."""
    protocol = reading.protocol
    text = protocol.read_text(encoding="utf-8")
    snap = area_snapshot(area)
    full = {c.resolve() for c in reading.code}
    indexed = [f for f in snap.files if f.resolve() not in full]
    run_id: str | None = None
    run_dir: Path | None = None
    shown: RunShown | None = None
    if mode == ANALYSIS:
        run_dir, why = audited_run(state_of(area), protocol, text)
        run_id = run_dir.name if run_dir is not None else findings.NO_RUN
        shown = run_shown(area, run_dir, why, text)
    # after the run's choice, which names a head that does not read
    pid = protocol_block.id_of(text)
    if pid is None:
        raise AuditError(
            f"{protocol.name} carries no stamped id ([protocol] id): a record names "
            f"the protocol it audited",
            fix="stamp it: `labkit-init exp <name> --kind …` writes a fresh id",
        )
    state = findings.AuditedState(
        snap.sha,
        promises.block_stamp(text),
        protocol_check.registration_stamp(text, audited=mode != ANALYSIS),
        run_id,
        shown.sha if shown else None,
    )

    def current(r: findings.Record) -> bool:
        """Is R a record of the state this prompt shows?"""
        return r.mode == ANALYSIS and r.state == state

    earlier_repairs = (
        earlier_of(
            area,
            protocol,
            pid,
            current,
            shown.evidence() if shown else None,
            run_dir,
        )
        if mode == ANALYSIS
        else Followup([], None, {}, {})
    )
    changed = "the area changed while it was read"
    try:
        prompt = render(
            mode,
            area,
            protocol,
            reading.code,
            reading.standard,
            indexed,
            source=Source(
                text,
                snap.text,
                shown.pieces if shown else (),
                validity_evidence(area, text)
                + predecessor_evidence(area, text)
                + exploration_evidence(area, text)
                + evidence_file_pieces(protocol, text, snap),
                earlier_piece(earlier_repairs) if mode == ANALYSIS else (),
            ),
        )
    except KeyError as exc:
        raise AuditError(f"{exc.args[0]} — {changed}", fix=AUDIT_AGAIN) from exc
    again = gather(area, protocol)
    if (
        [c.resolve() for c in again.code] != [c.resolve() for c in reading.code]
        or area_snapshot(area).sha != snap.sha
        or protocol.read_text(encoding="utf-8") != text
    ):
        raise AuditError(f"{area}: {changed}", fix=AUDIT_AGAIN)
    return BoundPrompt(
        prompt,
        Stamp(snap.sha, list(snap.files)),
        state,
        indexed,
        earlier_repairs,
        pid,
        run_dir,
        text,
    )
