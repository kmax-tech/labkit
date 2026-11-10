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
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from labkit.formats.gate import BLOCKER
from labkit import PACKAGE_DIR
from labkit.checks.audit_binding import AuditError, RunShown, audited_run, run_shown
from labkit.formats.area_state import state_of
from labkit.checks.prompt_check import prompt_constants
from labkit.formats.protocol_check import prompt_blocks
from labkit.formats import (
    findings,
    followup,
    promises,
    protocol_block,
    protocol_check,
    rules,
    scope_sha,
)
from labkit.formats.runs import recorded_models
from labkit.formats.prompts import prompt_body
from labkit.formats.protocol_block import repo_protocol_ids
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
from labkit.formats.runs import metrics_path, run_path
from labkit.formats.scope_sha import (
    area_files,
    area_snapshot,
    repo_imports,
)
from labkit.formats.standard_contract import (
    ANALYSIS_AUDIT,
    COMPUTE_KIND,
)
from labkit.gates import ways_out
from labkit.gates.ways_out import (
    AUDIT_AGAIN,
    PROTOCOL_NAMED,
)
from labkit.run.llm import model_entry

AGENT = PACKAGE_DIR / "agents" / "experiment-preflight.agent.md"
CLARITY_AGENT = PACKAGE_DIR / "agents" / "code-clarity.agent.md"
REVIEW_AGENT = PACKAGE_DIR / "agents" / "decision-review.agent.md"
REPORT_AGENT = PACKAGE_DIR / "agents" / "report-review.agent.md"
CLARITY = "clarity"
ANALYSIS = ANALYSIS_AUDIT  # its one spelling is standard_contract's
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
    "`<line>: <row>`, and for a computation over a model's annotations the "
    "evidence that the annotator suits under `===== EVIDENCE: … =====` lines "
    "(the bound apply protocol and its result as FILE lines), and the area's "
    "earlier decided BLOCKERs and corrections under one `===== EARLIER DECIDED "
    "BLOCKERS AND CORRECTIONS =====` line. Nothing else is in scope."
)


def instructions(mode: str = "preflight") -> str:
    """The agent's instructions as shipped, without the provenance comment —
    the preflight agent for preflight and analysis, the clarity agent for
    clarity, the decision-review agent for `--review` (`decision_review`),
    the report-review agent for `--report-review` (`report_review`)."""
    agent = {
        CLARITY: CLARITY_AGENT,
        "review": REVIEW_AGENT,
        "report": REPORT_AGENT,
    }.get(mode, AGENT)
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
    label, rules_text = standard_excerpt("report")
    return [("BRIEF", instructions("report")), (f"FILE: {label}", rules_text)]


def cited_rules(mode: str = "preflight") -> list[str]:
    """The `LAB-nnn` ids the instructions for MODE cite, in order of first
    mention — the part of the standard the auditor gets to read."""
    seen: list[str] = []
    for m in rules.CODE_RE.finditer(instructions(mode)):
        if m.group(1).startswith("LAB-") and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def standard_excerpt(mode: str = "preflight") -> tuple[str, str]:
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
        raise AuditError(
            no_such_area(area), fix="name the area by its path or numbered name"
        )
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
        raise AuditError(
            f"{chosen.name}: a promise declares scope `{os.path.relpath(gone[0], chosen.parent.resolve())}`, and it is not a file",
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
    script = area / "scripts" / "01_measure.py"
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
    validation stales the record — a DOI by its string only)."""

    protocol_text: str
    read: Callable[[Path], str]
    run: tuple[tuple[str, str], ...] = ()
    evidence: tuple[tuple[str, str], ...] = ()  # `validity_evidence`
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
        return (
            (
                "EVIDENCE: annotation_validity",
                f"protocol = {m.annotation_validity.value} — NOT BOUND: {bound}. "
                "No validation is shown; nothing here supports the annotator.",
            ),
        )
    return _bound_pieces(bound, repo)


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
    prompts = prompt_blocks(bound.protocol) + [
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


class FieldChange(NamedTuple):
    """A corrected field as the follow-up shows it: its LABEL, its value as
    the first measurement registered it — REGISTERED, None when that text
    cannot be read back, WHERE saying which text it is or why not — and its
    value NOW."""

    label: str
    registered: str | None
    where: str
    now: str


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
    (a `file:` check: where the dependency is shown whole), or that it is
    missing; "" when F requires none. METRICS is the snapshot the prompt
    renders (`RunShown.evidence`), never the file read again. The one
    wording of the follow-up piece (`earlier_piece`) and the decision
    review (`decision_review.decisions_text`)."""
    if not f.check:
        return ""
    note = f" ({f.check_note})" if f.check_note else ""
    present = metrics is not None and f.check in metrics
    if present and f.check.startswith(findings.FILE_CHECK):
        return f"required check `{f.check}`{note}: shown above under `{(metrics or {})[f.check]}`"
    if present:
        value = json.dumps((metrics or {})[f.check], ensure_ascii=False)
        return f"required check `{f.check}`{note} = {value}"
    if f.check.startswith(findings.FILE_CHECK):
        return (
            f"required check `{f.check}`: not among the answering run's "
            f"dependencies shown whole"
        )
    return f"required check `{f.check}`: missing in the answering run's metrics.json"


def earlier_piece(shown: Followup) -> tuple[tuple[str, str], ...]:
    """What MODE analysis shows of the earlier decisions: one `(label,
    text)` piece with every earlier decided BLOCKER and correction as
    `<record>#<n>`, its text, its recorded subject, its
    decision (status, reason, effect), for a
    correction the field as first registered and as it reads now, and, when
    the finding requires a check, that metrics.json key with its note and
    its whole value as shown, or that it is missing — or one piece saying
    there is none."""
    if not shown.entries:
        return (
            (
                EARLIER_LABEL,
                "none: no earlier decided BLOCKER or correction in this area",
            ),
        )
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
            then = (
                f"\n  {change.label} registered ({change.where}): {change.registered}"
                if change.registered is not None
                else f"\n  {change.label} registered: cannot be read back — {change.where}"
            )
            entry += f"{then}\n  {change.label} now: {change.now}"
        line = required_check_line(f, shown.metrics)
        if line:
            entry += f"\n  {line}"
        entries.append(entry)
    text = "\n".join(entries)
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
        ref: findings.decision_digest(m.finding)
        for ref, m in followup.chain(findings.area_records(area)).members.items()
    }
    return [
        e.ref for e in earlier if now.get(e.ref) != findings.decision_digest(e.finding)
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
) -> Followup:
    """The follow-up of PROTOCOL (stamped id PID) in AREA: the earlier
    decided BLOCKERs and corrections of a field of PROTOCOL
    (`followup.earlier_corrections`, `findings.corrected_field`) of the
    area's records that name PID — those of a record that CURRENT does not
    tell as the state now audited — with the origin of each, each
    correction's change — a BLOCKER's too — (`FieldChange`: the field as
    the first measurement registered it, `protocol_history.
    registrations_as_first_measured`, and as it reads now), and METRICS as
    shown. A record of another protocol of the area is not followed up
    here: it judged another question. Raises AuditError when the records
    do not read (`findings.FindingsError`) or a finding's place names no
    single field."""
    records = followup.protocol_records(area, pid)
    text = protocol.read_text(encoding="utf-8")

    def field_of(f: findings.Finding) -> str | None:
        """The field F corrects in PROTOCOL, or None. Raises AuditError
        when F's place begins several fields or means one written twice
        (`findings.corrected_field`)."""
        try:
            return findings.corrected_field(f, protocol, text)
        except protocol_check.FieldPlaceError as exc:
            raise ways_out.unclear_correction(f.one_line, protocol.name, exc) from exc

    try:
        c = followup.chain(records)
        blockers = followup.earlier_blockers(records, current)
        corrections = followup.earlier_corrections(records, current, field_of)
    except findings.FindingsError as exc:
        raise AuditError(str(exc), fix=findings.record_way(area)) from exc
    shown = blockers + corrections
    origins = {e.ref: c.members[c.origin[e.ref]].finding for e in shown}
    changes = {
        e.ref: _field_change(protocol, text, e.finding)
        for e in shown
        if field_of(e.finding) is not None
    }
    return Followup(shown, metrics, origins, changes)


def _field_change(protocol: Path, text: str, f: findings.Finding) -> FieldChange:
    """The change of the field F corrects in PROTOCOL (TEXT now): its value
    as the first measurement registered it and as it reads now. Raises
    RuntimeError when git fails."""
    at = f.place
    if at is None:
        raise ValueError(f"{f.one_line}: names no field of {protocol.name}")
    # called only for a field `corrected_field` named, so any unclear place
    # here is a fault of the caller and raises
    hit = protocol_check.field_at(text, at[1])
    pid = protocol_block.head(text).id
    if pid is None:
        return FieldChange(hit.label, None, "the protocol has no id", hit.value)
    groups = state_of(protocol.parent).measured_of(pid).first_groups
    texts, why = registrations_as_first_measured(protocol, groups, git_root(protocol))
    if not texts:
        return FieldChange(hit.label, None, why, hit.value)
    then, where = texts[0]
    old = protocol_check.named_field(then, hit.label)
    return FieldChange(
        hit.label, old.value if old is not None else ABSENT, where, hit.value
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
    SHOWN_NOW, the earlier repairs shown (`Followup`); and PROTOCOL_ID, the
    stamped id of the protocol read, which the record names."""

    prompt: str
    stamp: Stamp
    state: findings.AuditedState
    indexed: list[Path]
    earlier_repairs: Followup
    protocol_id: str


def bound_prompt(mode: str, area: Path, reading: AuditInputs) -> BoundPrompt:
    """The prompt and what its record binds (`BoundPrompt`) from ONE
    reading:
    the record binds what the prompt shows. The code is one snapshot: its
    bytes render the prompt, its sha goes in the record, and every stamped
    file the reading does not take in full is indexed — so the prompt shows
    each file the stamp covers, no more and no fewer. The promise block and
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
        protocol_check.registration_stamp(text),
        run_id,
        shown.sha if shown else None,
    )

    def current(r: findings.Record) -> bool:
        """Is R a record of the state this prompt shows?"""
        return r.mode == ANALYSIS and r.state == state

    earlier_repairs = (
        earlier_of(area, protocol, pid, current, shown.evidence() if shown else None)
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
                validity_evidence(area, text),
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
        prompt, Stamp(snap.sha, list(snap.files)), state, indexed, earlier_repairs, pid
    )
