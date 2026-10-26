"""labkit-audit — the agent audits of an area, through any llm backend.

    labkit-audit <AREA> --mode preflight|analysis|clarity [--protocol FILE]
                 [--model ALIAS] [--timeout S] [--out FILE]
    labkit-audit <AREA> --decide N STATUS REASON [--effect E] [--record FILE]
    labkit-audit <AREA> --findings [--record FILE]
    labkit-audit <AREA> --review [--record FILE]      (`gates/decision_review`)
    labkit-audit <AREA> --report-review REPORT        (`gates/report_review`)

The agent audit of LAB-015 Preflight audit before freezing (preflight, before freezing) and LAB-050 Analysis audit before reporting
(analysis, before a number leaves) as one command — the only runner since
0.79.0; the Claude subagent copy of the instructions is gone. The
instructions ship with the package (`experiment-preflight.agent.md`); the
files they tell the auditor to read are gathered here and inlined — the
area's protocol, `scripts/*.py`, `analysis/*.py`, the repo-local `lib/`
modules they import, and from the lab standard that ships with labkit
exactly the rules the instructions cite (`cited_rules`):
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
contract, made from one audit result: the LAST verdict
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
       (`findings.write_failed`): the evidence an acknowledged full run's
       LABKIT_UNFROZEN=1 rests on, since 0.99.0

The report is printed (and written to --out), and its findings are written
as data into the area — `audits/<date>-<mode>.toml`, one `[[finding]]` per
line, every one `open` (`labkit.formats.findings`); deciding each (fixed / accepted
/ deferred / dismissed, with reason) and stamping the protocol field stays
with the human (LAB-015 Preflight audit before freezing), and `preflight`
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
import json
import ast
import os
import re
import shlex
import sys
import time
from pathlib import Path
from collections.abc import Callable
from typing import NamedTuple

from labkit import PACKAGE_DIR
from labkit.formats.gate import GUARANTEED
from labkit.formats.runs import metrics_path, run_path
from labkit.run import llm, llm_backends
from labkit.run.llm import model_entry
from labkit.formats import (
    attempts,
    console,
    findings,
    followup,
    promises,
    protocol_block,
    protocol_check,
    rules,
    scope_sha,
)
from labkit.formats.gate import WARNING, GateFinding, coded
from labkit.formats.standard_contract import COMPUTE_KIND, lane
from labkit.formats.repo import (
    ProtocolChoiceError,
    area_path,
    area_protocols,
    layout_root,
    no_such_area,
    shown,
    the_protocol,
)
from labkit.formats.runs import completed_runs
from labkit.formats.protocol_history import (
    BoundValidation,
    bound_validation,
)
from labkit.formats.protocol_block import repo_protocol_ids
from labkit.formats.answering_run import recorded_models
from labkit.checks.prompt_check import prompt_blocks, prompt_constants
from labkit.checks.audit_binding import AuditError, RunShown, audited_run, run_shown
from labkit.formats.scope_sha import (
    area_files,
    area_snapshot,
    area_stamp,
    repo_imports,
    validation_note,
)

AGENT = PACKAGE_DIR / "agents" / "experiment-preflight.agent.md"
CLARITY_AGENT = PACKAGE_DIR / "agents" / "code-clarity.agent.md"
REVIEW_AGENT = PACKAGE_DIR / "agents" / "decision-review.agent.md"
REPORT_AGENT = PACKAGE_DIR / "agents" / "report-review.agent.md"
DEFAULT_MODEL = "opus"  # the agent's model; any alias of models.toml works
REPORT_TOKENS = 4096  # room for a report of many findings, where a backend caps
DEFAULT_TIMEOUT_S = (
    findings.ATTEMPT_TIMEOUT_S
)  # one call reads the area, the rules, the rows
MODES = ("preflight", "analysis", "clarity")
#: the audit's exit contract — not `gate.EXIT_CONTRACT`: a warning is a
#: finding to decide here, so it exits 1 too (the module docstring says why)
AUDIT_EXIT_CONTRACT = (
    "exit codes: 0 no blocker and no warning, 1 findings to decide (a blocker "
    "OR a warning), 2 no audit (missing file, unreadable report, backend failure); "
    "--review: 0 every decision upheld, 1 at least one not upheld, 2 no review; "
    "--report-review: 0 no claim (or this state reviewed clean), 1 a claim (the commit holds), 2 no review"
)
CLARITY = "clarity"
ANALYSIS = "analysis"
STANDARD_LABEL = (
    "labkit/docs/standard.md"  # the shipped standard, wherever labkit is installed
)

#: a finding line: the grade, then the ` · ` the instructions ask for — or
#: a dash or colon, which auditors write too (audit 2026-10-15: two blockers
#: written as `BLOCKER — …` parsed as none, and the record read as covered)
FINDING = re.compile(r"^[\s>*`-]*\**(BLOCKER|WARNING|NOTE)\**\s*(?:·|—|–|:)", re.M)
VERDICT = re.compile(
    r"verdict:\s*(\d+)\s*blockers?(?:\(s\))?,\s*(\d+)\s*warnings?(?:\(s\))?"
    r"(?:,\s*(\d+)\s*notes?(?:\(s\))?)?",
    re.I,
)
CLARITY_FINDING = re.compile(r"^[\s>*`-]*RULE\s*(\d+)\**\s*·", re.M)
CLARITY_VERDICT = re.compile(
    r"verdict:\s*(\d+)\s*findings?(?:\s*\((\d+)\s*would be answered wrong\))?", re.I
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
    "earlier decided BLOCKERs under one `===== EARLIER DECIDED BLOCKERS =====` "
    "line. Nothing else is in scope."
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


class Reading(NamedTuple):
    """What the auditor reads in full: the protocol, the code, the standard
    (its cited rules). Every other stamped file comes as an index, taken
    from the snapshot (`bound_prompt`)."""

    protocol: Path
    code: list[Path]  # scripts, analysis files, declared scopes, direct imports
    standard: Path


def gather(area: Path, protocol: Path | None) -> Reading:
    """What the agent reads, by LAB-103 The audit reads by declared scope,
    not by import graph: the area's scripts and analysis files, the files
    the promises declare as scope, the repo-local modules those import
    directly — in full (every other stamped file is indexed from the
    snapshot, `bound_prompt`). Refuses what is missing."""
    if not area.is_dir():
        raise AuditError(no_such_area(area))
    try:
        chosen = the_protocol(area, protocol)
    except ProtocolChoiceError as exc:
        raise AuditError(str(exc)) from exc
    repo = layout_root(area)
    scripts = area_files(area)
    if not scripts:
        raise AuditError(f"{area}: no scripts/*.py or analysis/*.py — nothing to audit")
    code = [p.resolve() for p in scripts]
    declared = scope_sha.declared_scope_files([chosen])
    gone = [f for f in declared if not f.is_file()]
    if gone:
        # a promise resting on a missing file is not audited around
        raise AuditError(
            f"{chosen.name}: a promise declares scope `{os.path.relpath(gone[0], chosen.parent.resolve())}`, and it is not a file"
        )
    code += [f for f in declared if f not in code]
    code += [f for f in repo_imports(code, repo) if f.resolve() not in code]
    standard = rules.STANDARD
    if not standard.is_file():
        raise AuditError(
            f"{standard} is missing — labkit was installed without its standard "
            f"(scar table, severity legend); reinstall labkit"
        )
    return Reading(chosen, code, standard)


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
            raise AuditError(f"{rel}: cannot index it ({exc})") from exc
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
            f"{area}: no {', '.join(missing)} — the clarity reading starts there"
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
    fixes: tuple[tuple[str, str], ...] = ()  # `fixed_piece`, MODE analysis


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
    model its run recorded (`answering_run.recorded_models`), and today's
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
                f"run {bound.run} declared, but {shown(metrics, repo)} does not read",
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
    body = "".join(f"===== {label} =====\n{text}\n" for label, text in pieces)
    return (
        f"{instructions(mode)}\n\nMODE: {mode} · AREA: {rel(area)}\n\n"
        f"{INLINE_NOTE}\n\n{body}"
    )


#: the label of the piece that shows the earlier decided BLOCKERs
EARLIER_LABEL = "EARLIER DECIDED BLOCKERS"
#: operating limits of that piece, not thresholds of meaning: past either
#: the audit refuses, loudly, rather than show a cut list (decided
#: 2026-10-26 after the follow-up pilots, whose pieces held one entry of
#: under 2 kB; revisit with the sizes records keep under `followup`)
EARLIER_MAX_ENTRIES = 40
EARLIER_MAX_BYTES = 60_000
#: a line that opens as a fix verdict — read whole or refused, never skipped
FIX_OPEN = re.compile(r"^[\s>*`-]*\**FIX\**\s*(?:·|—|–|:)", re.M)
#: a fix verdict line: `FIX · <record>#<n> · <verdict> · <why>`
FIX = re.compile(
    r"^[\s>*`-]*\**FIX\**\s*(?:·|—|–|:)\s*`?(?P<record>[^\s`#]+)#(?P<n>\d+)`?\s*"
    r"(?:·|—|–|:)\s*`?(?P<verdict>[a-z_]+)`?\s*(?:·|—|–|:)\s*(?P<why>\S.*)$"
)


class Followup(NamedTuple):
    """What an analysis audit is shown to judge earlier decisions, taken
    once: the area's earlier decided BLOCKERs (`followup.earlier_blockers`),
    the answering run's metrics.json as the prompt shows it
    (`RunShown.metrics`; None when it shows none), and the origin of each
    shown finding's chain (its ref → the origin's finding)."""

    blockers: list[followup.Member]
    metrics: dict | None
    origins: dict[str, findings.Finding]

    def check_present(self, e: followup.Member) -> bool | None:
        """Whether E's required check key stands in the metrics shown —
        None when E requires no check. From the snapshot the prompt
        renders, never from the file read again."""
        if not e.finding.check:
            return None
        return self.metrics is not None and e.finding.check in self.metrics


def earlier_piece(shown: Followup) -> tuple[tuple[str, str], ...]:
    """What MODE analysis shows of the earlier decisions: one `(label,
    text)` piece with every earlier decided BLOCKER as `<record>#<n>`, its
    text, its decision (status, reason, effect) and, when the finding
    requires a check, that metrics.json key with its note and its whole
    value as shown, or that it is missing — or one piece saying there is
    none."""
    if not shown.blockers:
        return ((EARLIER_LABEL, "none: no earlier decided BLOCKER in this area"),)
    entries = []
    for e in shown.blockers:
        f = e.finding
        effect = f" (effect: {f.effect})" if f.effect else ""
        entry = (
            f"{e.ref}\n  finding: {f.text}\n  decided: {f.status}{effect} — "
            f"{f.reason or '(no reason given)'}"
        )
        present = shown.check_present(e)
        if present is True:
            value = json.dumps((shown.metrics or {})[f.check], ensure_ascii=False)
            note = f" ({f.check_note})" if f.check_note else ""
            entry += f"\n  required check `{f.check}`{note} = {value}"
        elif present is False:
            entry += (
                f"\n  required check `{f.check}`: missing in the answering "
                f"run's metrics.json"
            )
        entries.append(entry)
    text = "\n".join(entries)
    size = len(text.encode("utf-8"))
    if len(entries) > EARLIER_MAX_ENTRIES or size > EARLIER_MAX_BYTES:
        raise AuditError(
            f"{len(entries)} earlier decided BLOCKERs, {size} bytes — past the "
            f"follow-up's operating limit ({EARLIER_MAX_ENTRIES} entries, "
            f"{EARLIER_MAX_BYTES} bytes); none is cut from what the auditor must "
            f"judge, so the audit does not run. Settle earlier findings, or raise "
            f"the limit in labkit with the measured sizes"
        )
    return ((EARLIER_LABEL, text),)


def parse_fixes(text: str, shown_now: Followup) -> list[findings.FixVerdict]:
    """The report's `FIX · <record>#<n> · <verdict> · <why>` entries before
    the last verdict line, each bound to the decision EARLIER showed for
    that finding (`findings.decision_digest`) — labkit attaches the digest,
    the auditor names the finding. The why is the FIX line's text and the
    lines right below it (`fix_block`), kept whole: the evidence an auditor
    lists under the line is the verdict's ground (pilot B-2, 2026-10-26:
    five lines, the record held the first). Raises AuditError on a FIX line
    that does not read whole, a block that also names another shown
    finding, a finding the prompt did not show, a verdict outside
    `findings.FIX_VERDICTS`, and a second verdict on one finding: none of
    them may release a repair, and a guess at what was meant would. A
    shown finding without a line gets no verdict — unchecked, never
    resolved. Each verdict carries the finding's required check and
    whether its key stood in the metrics shown (`Followup.check_present`);
    a `resolved` on a missing key is kept as the auditor wrote it."""
    m = list(VERDICT.finditer(text or ""))
    lines = ((text or "")[: m[-1].start()] if m else (text or "")).splitlines()
    shown = {e.ref: e for e in shown_now.blockers}
    out: list[findings.FixVerdict] = []
    for i, line in enumerate(lines):
        if not FIX_OPEN.match(line):
            continue
        f = FIX.match(line.strip())
        if f is None:
            raise AuditError(
                f"a FIX line that does not read: {line.strip()[:160]!r} — the form "
                f"is `FIX · <record>#<n> · resolved|unresolved|not_assessable · <why>`"
            )
        ref = f"{f['record']}#{f['n']}"
        e = shown.get(ref)
        if e is None:
            raise AuditError(
                f"a FIX verdict on {ref}, which the prompt did not show — the shown "
                f"ones: {', '.join(shown) or 'none'}"
            )
        more = fix_block(lines, i)
        others = sorted({r for r in shown if r != ref and any(r in x for x in more)})
        if others:
            raise AuditError(
                f"the FIX entry on {ref} also names {', '.join(others)} below its "
                f"line — which finding its verdict judges is not clear; one entry "
                f"per finding, separated by a blank line"
            )
        out.append(
            findings.FixVerdict(
                e.record.path.name,
                e.n,
                findings.decision_digest(e.finding),
                f["verdict"],
                "\n".join([f["why"].strip(), *(x.strip() for x in more)]),
                e.finding.check,
                shown_now.check_present(e),
            )
        )
    problem = findings.fix_verdict_problem(out)
    if problem:
        raise AuditError(problem)
    return out


def fix_block(lines: list[str], at: int) -> list[str]:
    """The lines that continue the FIX entry at LINES[AT]: every line right
    below it up to the first blank line or the first line that opens
    another entry — a FIX, a finding, a READ, the verdict or scope line, a
    code fence."""
    out: list[str] = []
    for line in lines[at + 1 :]:
        if (
            not line.strip()
            or FIX_OPEN.match(line)
            or FINDING.match(line)
            or READ_HINT.match(line)
            or VERDICT.search(line)
            or line.strip().startswith("scope:")
            or protocol_block.FENCE.match(line)
        ):
            break
        out.append(line)
    return out


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
    return len(shown.blockers), len(text.encode("utf-8")) if shown.blockers else 0


def carried_of(
    shown: Followup, fixes: list[findings.FixVerdict]
) -> list[findings.Finding]:
    """The findings the new record carries: one per shown BLOCKER whose
    verdict is not `resolved` (`followup.carried_finding`). A shown one
    without a verdict is not carried — unchecked, it stays where it is."""
    by_ref = {e.ref: e for e in shown.blockers}
    return [
        followup.carried_finding(by_ref[v.ref], v, shown.origins[v.ref])
        for v in fixes
        if v.verdict != "resolved"
    ]


def earlier_of(
    area: Path, current: Callable[[findings.Record], bool], metrics: dict | None
) -> Followup:
    """The follow-up of AREA: its earlier decided BLOCKERs — those of a
    record that CURRENT does not tell as the state now audited — with the
    origin of each, and METRICS as shown. Raises AuditError when there are
    earlier BLOCKERs and the area holds more than one protocol: the records
    carry no protocol id, so whose question an earlier finding judged is
    not certain."""
    records = findings.area_records(area)
    try:
        c = followup.chain(records)
        shown = followup.earlier_blockers(records, current)
    except findings.FindingsError as exc:
        raise AuditError(str(exc)) from exc
    if shown and len(area_protocols(area)) > 1:
        raise AuditError(
            f"{len(shown)} earlier decided BLOCKER(s) and {len(area_protocols(area))} "
            f"protocols in {area.name}: the records name no protocol, so which "
            f"question an earlier finding judged is not certain — the follow-up "
            f"does not guess; one protocol per area, or settle the earlier findings"
        )
    origins = {e.ref: c.members[c.origin[e.ref]].finding for e in shown}
    return Followup(shown, metrics, origins)


def parse_clarity(text: str) -> dict:
    """{"findings": N, "wrong": M, "lines": [(rule, line)]} from the LAST
    `verdict: N findings (M would be answered wrong)` line. Raises AuditError
    when no verdict line is readable."""
    matches = list(CLARITY_VERDICT.finditer(text or ""))
    if not matches:
        raise AuditError("the report has no readable `verdict:` line — not a reading")
    m = matches[-1]
    body = (text or "")[: m.start()]
    lines = [
        (int(f.group(1)), line.strip())
        for line in body.splitlines()
        if (f := CLARITY_FINDING.match(line))
    ]
    return {
        "findings": int(m.group(1)),
        "wrong": int(m.group(2) or 0),
        "lines": lines,
    }


def parse(text: str) -> dict:
    """{"verdict": (blockers, warnings, notes), "findings": [(grade, line)]} from
    the LAST verdict line, findings from the text before it (that the two
    agree is the writer's check, `findings.verdict_disagrees`). Raises AuditError when no verdict line is readable."""
    matches = list(VERDICT.finditer(text or ""))
    if not matches:
        raise AuditError("the report has no readable `verdict:` line — not an audit")
    m = matches[-1]
    body = (text or "")[: m.start()]
    findings = [
        (f.group(1), line.strip())
        for line in body.splitlines()
        if (f := FINDING.match(line))
    ]
    return {
        "verdict": (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)),
        "findings": findings,
        "scope": scope_list((text or "")[m.end() :]),
    }


def scope_list(tail: str) -> list[str]:
    """The auditor's closing `scope:` list — the files it says determine the
    number, one per line (also accepted on the `scope:` line itself)."""
    lines = tail.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("scope:"):
            first = line.strip().removeprefix("scope:").strip()
            rest = [
                ln.strip().lstrip("-*• ").strip("`")
                for ln in lines[i + 1 :]
                if not protocol_block.FENCE.match(ln)  # a marker is no entry
            ]
            return [s for s in ([first.strip("`")] if first else []) + rest if s]
    return []


def scope_mismatch(area: Path, listed: list[str], files: list[Path]) -> list[str]:
    """Where the auditor's scope and the stamp disagree — FILES are the
    stamp's, taken before the call (`Stamp`). The stamp is what a later
    check recomputes, so a file the auditor read as part of the number but
    the stamp misses can change unnoticed (review 2026-10-07: the list was
    asked for and then dropped)."""
    root = layout_root(area)
    # home: sets compared to each other, not a display (repo.shown)
    stamped = {
        f.resolve().relative_to(root.resolve()).as_posix()
        for f in files
        # home: only the stamp's files below the root take part
        if f.resolve().is_relative_to(root.resolve())
    }
    named = set()
    for s in listed:
        q = Path(s)
        q = q if q.is_absolute() else root / q
        named.add(
            q.resolve().relative_to(root.resolve()).as_posix()
            # home: compared with `stamped`; outside the root, as the auditor wrote it
            if q.resolve().is_relative_to(root.resolve())
            else s
        )
    out = [
        f"the auditor read {n} as part of the number, the stamp does not cover it"
        for n in sorted(named - stamped)
    ]
    out += [
        f"the stamp covers {s}, the auditor did not list it as read"
        for s in sorted(stamped - named)
    ]
    return out


def early_for_tier(area: Path, protocol: Path, mode: str) -> list[GateFinding]:
    """One WARNING line when a preflight audit comes before the repeat cost
    asks for it: at `repeat_cost = "low"` the first run is the cheaper probe
    and ONE audit in mode analysis after it covers the preflight rows
    (LAB-017 The number of audits follows the cost tier). uniagent area 01,
    2026-10-05: two preflight audits and an analysis audit at low repeat cost, and
    the protocol itself says one after the first run would have done. A
    head this labkit cannot read says nothing here — protocol-check does."""
    if mode != "preflight":
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


class Stamp(NamedTuple):
    """The area's stamp as the auditor saw it: taken ONCE, before the call.
    Until 0.95.0 it was taken after the model answered (up to 900 s later),
    so a lib module edited meanwhile gave a record whose sha no auditor had
    read, and the freeze gate took it as covered (audit 2026-10-15)."""

    sha: str
    files: list[Path]


def stamp_facts(stamp: Stamp, verdict: tuple[int, int, int]) -> str:
    """The stamp's facts, for the person reading the report beside the
    record: the sha is `scope_sha.area_stamp`, the same a later `scope-sha`
    recomputes and the record carries as `scope_sha`."""
    sha = stamp.sha
    b, w, n = verdict
    return (
        f"{time.strftime('%Y-%m-%d')} · scope sha {sha} · {b + w + n} findings "
        f"({b} blockers, {w} warnings, {n} notes — decide each: fixed / accepted / deferred / dismissed)"
    )


def _answer_or_record(
    args: argparse.Namespace,
    argv: list[str],
    prompt: str,
    stamp: Stamp,
    block_sha: str,
) -> tuple[str, attempts.Running]:
    """(the auditor's report, its attempt in the area's journal — the
    caller ends it with the record). The attempt is begun right before the
    call (`attempts.begin`: refused while another audit of the area runs
    or a record the journal or HEAD names is gone; an earlier attempt
    without an end is marked interrupted and named). When the backend does not answer (the CLI died,
    the server was down, the retries ran out) there is no audit, and the
    evidence that one was tried — on this code, these promises, with this
    much time — goes next to the records (`findings.write_failed`) before
    the AuditError that ends the command with exit 2. That file is what a
    LABKIT_UNFROZEN=1 rests on (second haiku round on 0.98.0:
    no agent started an audit, and the hatch asked for nothing). A usage
    error (an alias models.toml does not know) is not an unavailable audit
    and propagates as it is, so none is written for it.

    An answer the model did not write whole (`llm_backends.UnprovenAnswer`)
    is recorded with cause `unproven`, and from then on this state is not
    sent to this model again (`findings.stopped_attempt`): the next try is
    refused before any call."""
    stopped = findings.stopped_attempt(
        args.area, args.mode, args.model, stamp.sha, block_sha
    )
    if stopped is not None:
        raise AuditError(
            f"{stopped.path}: {args.model} did not write its {args.mode} audit of "
            f"this state whole — {stopped.error}\nlabkit-audit: no further try on "
            f"the same code, promises and model; each costs as much and was stopped "
            f"again. Audit with another alias (--model), or leave the number "
            f"unreported (report-check refuses it without an audit)."
        )
    # the alias is resolved before the attempt begins: an alias models.toml
    # does not know is a usage error (KeyError), not an attempt
    room = _report_room(args.model)
    running = attempts.begin(args.area, args.mode, args.model, stamp.sha)
    for note in running.notes:
        console.progress("labkit-audit", note)
    try:
        answer = llm.complete(args.model, prompt, timeout=args.timeout, max_tokens=room)
        # kept before anything reads it: an answer that does not read is
        # evidence of what the auditor said, and the end names it
        running.keep_answer(answer)
        return answer, running
    except llm_backends.UnprovenAnswer as exc:
        tried = findings.write_failed(
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
            f"next try with {args.model} is refused. Audit with another alias "
            f"(--model), or leave the number unreported."
        ) from exc
    except llm_backends.BackendError as exc:
        tried = findings.write_failed(
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
            f"refuses it). Run the audit again when the backend answers."
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


def bound_prompt(
    mode: str, area: Path, reading: Reading
) -> tuple[
    str,
    Stamp,
    str,
    str | None,
    str | None,
    list[Path],
    dict[str, str],
    Followup,
]:
    """(prompt, stamp, block sha, run id, shown sha, indexed files,
    registration, what is shown of the earlier repairs — `Followup`) from
    ONE reading:
    the record binds what the prompt shows. The code is one snapshot: its
    bytes render the prompt, its sha goes in the record, and every stamped
    file the reading does not take in full is indexed — so the prompt shows
    each file the stamp covers, no more and no fewer. The promise block and
    the registration (`protocol_check.registration_stamp`) come from the one
    protocol text the prompt carries; in MODE analysis
    the run is chosen once, and what the prompt shows of it is one snapshot
    whose digest goes in the record (NO_RUN when none answers), and the
    area's `fixed` BLOCKERs are read once: the prompt shows them, and each
    verdict on one is bound to the decision shown (`parse_fixes`).

    The reading's file list was taken before the snapshot. After rendering,
    the list, the snapshot and the protocol are taken again; any change
    means the prompt rests on a list or bytes the area no longer has, and
    the audit is refused (AuditError) — a file added in between stood in
    the stamp and not in the prompt (review 2026-10-20)."""
    protocol = reading.protocol
    text = protocol.read_text(encoding="utf-8")
    snap = area_snapshot(area)
    full = {c.resolve() for c in reading.code}
    indexed = [f for f in snap.files if f.resolve() not in full]
    run_id: str | None = None
    shown: RunShown | None = None
    if mode == ANALYSIS:
        run_dir, why = audited_run(area, protocol, text)
        run_id = run_dir.name if run_dir is not None else findings.NO_RUN
        shown = run_shown(area, run_dir, why)
    block = promises.block_stamp(text)
    registration = protocol_check.registration_stamp(text)

    def current(r: findings.Record) -> bool:
        """Is R a record of the state this prompt shows?"""
        return (
            r.mode == ANALYSIS
            and r.scope_sha == snap.sha
            and r.block_sha == block
            and r.run_id == run_id
            and r.shown_sha == (shown.sha if shown else None)
            and dict(r.registration) == registration
        )

    shown_now = (
        earlier_of(area, current, shown.metrics() if shown else None)
        if mode == ANALYSIS
        else Followup([], None, {})
    )
    changed = "the area changed while it was read; run the audit again"
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
                earlier_piece(shown_now) if mode == ANALYSIS else (),
            ),
        )
    except KeyError as exc:
        raise AuditError(f"{exc.args[0]} — {changed}") from exc
    again = gather(area, protocol)
    if (
        [c.resolve() for c in again.code] != [c.resolve() for c in reading.code]
        or area_snapshot(area).sha != snap.sha
        or protocol.read_text(encoding="utf-8") != text
    ):
        raise AuditError(f"{area}: {changed}")
    stamp = Stamp(snap.sha, list(snap.files))
    shown_sha = shown.sha if shown else None
    return (
        prompt,
        stamp,
        promises.block_stamp(text),
        run_id,
        shown_sha,
        indexed,
        protocol_check.registration_stamp(text),
        shown_now,
    )


def main(argv: list[str]) -> int:
    """Command line of `labkit-audit`: audit one area in one mode, store a
    decision the person gives on one of its findings (`--decide`), or show
    what there is to decide (`--findings`)."""
    ap = argparse.ArgumentParser(
        prog="labkit-audit",
        description=(__doc__ or "").splitlines()[0],
        epilog=AUDIT_EXIT_CONTRACT,
    )
    ap.add_argument("area", type=area_path)
    ap.add_argument("--mode", choices=MODES)
    ap.add_argument(
        "--decide",
        nargs=3,
        metavar=("N", "STATUS", "REASON"),
        help="store your decision on finding N of the newest record: STATUS "
        f"({' | '.join(findings.STATUSES)}) and REASON (owed for "
        f"{', '.join(findings.REASON_OWED)}); no audit runs",
    )
    ap.add_argument(
        "--effect",
        default="",
        metavar="EFFECT",
        help="with --decide, owed for an accepted BLOCKER, open to an accepted WARNING: "
        "`stands` (the verdicts hold, "
        'the limit named beside them) or "<ID>[, <ID>] not assessable" (this run '
        "does not judge those promises)",
    )
    ap.add_argument(
        "--findings",
        action="store_true",
        help="show the newest record's findings with their --decide commands; no audit runs",
    )
    ap.add_argument(
        "--review",
        action="store_true",
        help="a second auditor on the accepted findings with effect `stands` of the "
        "newest analysis record (or --record): does the reported claim stand within "
        "each limit? writes audits/<minute>-review.toml",
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
        "reviewed — a measurement of the reviewer's spread; it never releases",
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
    args = ap.parse_args(argv)
    _check_args(ap, args)
    if args.mode is None:
        return _without_audit(args)
    if args.mode == CLARITY:
        return _clarity(args)
    try:
        reading = gather(args.area, args.protocol)
        protocol, code = reading.protocol, reading.code
        for finding in early_for_tier(args.area, protocol, args.mode):
            console.progress("labkit-audit", finding.line)
        (
            prompt,
            stamp,
            block_sha,
            run_id,
            shown_sha,
            indexed,
            registration,
            shown_now,
        ) = bound_prompt(args.mode, args.area, reading)
        console.progress(
            "labkit-audit",
            f"{args.mode} · {protocol.name} · {len(code)} code file(s) "
            f"in full, {len(indexed)} indexed · "
            f"{args.model} · {len(prompt) // 1000} kB",
        )
        report, running = _answer_or_record(args, argv, prompt, stamp, block_sha)
    except (
        AuditError,
        llm_backends.PromptTruncated,
        KeyError,
        FileNotFoundError,
        ValueError,
        RuntimeError,
    ) as exc:
        # KeyError: llm.resolve on an alias models.toml does not know;
        # FileNotFoundError, ValueError: the area cannot be stamped;
        # ValueError also: the promise block cannot be read (PromiseError),
        # an attempt refused (AttemptError); RuntimeError: git failed
        console.refuse("labkit-audit", str(exc).strip(chr(39)))
        return 2
    try:
        return _record(
            args,
            report,
            running,
            stamp,
            block_sha,
            run_id,
            shown_sha,
            indexed,
            registration,
            shown_now,
        )
    finally:
        if not running.ended:
            running.end("none", error="the command ended before the record")


def _record(
    args: argparse.Namespace,
    report: str,
    running: attempts.Running,
    stamp: Stamp,
    block_sha: str,
    run_id: str | None,
    shown_sha: str | None,
    indexed: list[Path],
    registration: dict[str, str],
    shown_now: Followup,
) -> int:
    """Read REPORT, write its record and end RUNNING with it; print what the
    person decides. Exit 1 on a blocker or a warning, 0 on none, 2 when the
    report does not read, its FIX lines do not (`parse_fixes`), or a shown
    decision changed while the auditor read it (`decisions_moved`) — the
    attempt ends without a record, said why."""
    console.progress("labkit-audit", f"tokens · {llm.last_usage().describe()}")
    try:
        result = parse(report)
        fixes = parse_fixes(report, shown_now)
        moved = decisions_moved(shown_now.blockers, args.area)
        if moved:
            raise AuditError(
                f"the decision on {', '.join(moved)} changed while the auditor read "
                f"it — its verdict would judge a decision that no longer stands; "
                f"run the audit again"
            )
    except (AuditError, ValueError) as exc:
        running.end("none", error=str(exc))
        console.refuse("labkit-audit", str(exc).strip(chr(39)))
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
            stamp.sha,
            block_sha,
            result["verdict"],
            result["findings"],
            registration=registration,
            run_id=run_id,
            shown_sha=shown_sha,
            fix_verdicts=fixes,
            carried=carried_of(shown_now, fixes),
            followup_size=followup_size(shown_now) if args.mode == ANALYSIS else None,
        )
    except ValueError as exc:  # verdict and finding lines disagree
        running.end("none", error=str(exc))
        console.refuse("labkit-audit", str(exc))
        return 2
    running.end("record", file=recorded.name)
    _stamp_report(args.area, args.mode, stamp, result["verdict"], recorded)
    # the auditor lists what it read in full; the indexed modules are the
    # caller's to add before the list is held to the stamp (LAB-103 The audit reads by declared scope)
    listed_scope = result["scope"] + [str(p) for p in indexed]
    for gap in scope_mismatch(args.area, listed_scope, stamp.files):
        print(f"scope WARNING: {gap}", file=sys.stderr)
    # last, on stdout after the report: what the person acts on. On stderr
    # it came out before the buffered report in a pipe, and `| tail` cut it
    # off (sandbox judge probes, 2026-10-21)
    print()
    for line in decision_lines(findings.read(recorded), args.area, report):
        print(line)
    for line in fix_lines(shown_now.blockers, fixes):
        print(line)
    return 1 if b or w or carried_of(shown_now, fixes) else 0


def fix_lines(
    earlier: list[followup.Member], fixes: list[findings.FixVerdict]
) -> list[str]:
    """One line per earlier `fixed` BLOCKER the audit was shown: its
    verdict, or that it has none and its repair stays unchecked."""
    given = {v.ref: v for v in fixes}
    out = []
    for e in earlier:
        v = given.get(e.ref)
        out.append(
            f"  fix {e.ref}: {v.verdict} — {v.why}"
            if v
            else f"  fix {e.ref}: no verdict — its repair stays unchecked"
        )
    return out


def _stamp_report(
    area: Path, mode: str, stamp: Stamp, verdict: tuple[int, int, int], recorded: Path
) -> None:
    """What the person copies and watches, on stderr after the report: the
    stamp's facts; in mode preflight the head field that names the record
    (`preflight_audit = "<record>"`, once every finding is decided); and a
    NOTE when the code changed while the auditor read it."""
    print(f"\nstamp: {stamp_facts(stamp, verdict)}", file=sys.stderr)
    if mode == "preflight":
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


#: a READ line of the auditor's report: a reading hint, printed and never
#: recorded (the record keeps what FINDING matches)
READ_HINT = re.compile(r"^[\s>*`-]*\**READ\**\s*(?:·|—|–|:)")
#: how long a finding's text stands in the decision list
DECISION_TEXT_WIDTH = 160


def decision_lines(record: findings.Record, area: Path, report: str) -> list[str]:
    """What the person decides, as printed after an audit is recorded: the
    record's path, its findings numbered as `--decide` takes them — from
    the stored record, never counted in the model's text — each with the
    command that decides it (`--record` named, so a later audit cannot
    shift it), then the READ lines of REPORT apart: printed, not recorded,
    nothing to decide. Five of six sandbox probes (2026-10-21) numbered the
    printed lines and decided findings the record does not hold."""
    here = Path.cwd()
    where = shown(record.path, here)
    out: list[str] = []
    if not record.findings:
        out.append(f"findings: {where} — no findings to decide")
    else:
        owed = ", ".join(findings.REASON_OWED)
        out.append(
            f"findings: {where} — {len(record.findings)} to decide "
            f"({' / '.join(s for s in findings.STATUSES if s != 'open')}; a reason "
            f"owed for {owed}):"
        )
        for n, f in enumerate(record.findings, 1):
            text = (
                f.text
                if len(f.text) <= DECISION_TEXT_WIDTH
                else f.text[: DECISION_TEXT_WIDTH - 1] + "…"
            )
            out.append(f"  {n} · {text}")
            out.append(
                f"      labkit-audit {shlex.quote(shown(area, here))} --decide {n} "
                f'STATUS "REASON" --record {shlex.quote(where)}'
            )
            if f.grade == "BLOCKER":
                out.append(
                    "      accepted owes its effect: --effect stands (the verdicts "
                    "hold, read within it; a second auditor must uphold it before the "
                    "number leaves: `labkit-audit <area> --review`) or "
                    '--effect "<ID> not assessable"'
                )
            elif f.grade == "WARNING":
                out.append(
                    "      accepted may name its effect when it limits what the "
                    'result allows: --effect stands | --effect "<ID> not assessable"'
                )
    hints = [ln.strip() for ln in report.splitlines() if READ_HINT.match(ln)]
    if hints:
        out.append("reading hints — not recorded, nothing to decide:")
        out += [f"  {h}" for h in hints]
    return out


def _check_args(ap: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Exactly one of --mode (audit), --decide (store a decision), --findings
    (show what there is to decide) and --review (a second auditor on the
    decisions); --record never with --mode. A usage error exits 2 through
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
            "give --mode to audit, --decide N STATUS REASON to decide, --findings "
            "to show what there is to decide, --review to review the decisions, or "
            "--report-review REPORT to read a finished report — one of them"
        )
    if args.record is not None and (
        args.mode is not None or args.report_review is not None
    ):
        ap.error("--record goes with --decide, --findings or --review")
    if args.effect and args.decide is None:
        ap.error("--effect goes with --decide")
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
        return _decide(args.area, args.decide, args.record, args.effect, args.protocol)
    return _findings(args.area, args.record)


def record_path(area: Path, record: Path) -> Path:
    """RECORD as given when it exists, else the file of that name under
    AREA's audits/ — the gates name a record by its file name
    (`Limit (audit <record> #N)`, report-check's `--record <name>`), and
    judge-2 (round on 86e38bc, 2026-10-22) copied the name and was refused
    with "No such file"."""
    if record.exists():
        return record
    named = area / findings.DIR / record.name
    return named if record.parent == Path(".") and named.exists() else record


def _newest_record(area: Path) -> Path:
    """The area's newest findings record; FindingsError when it has none."""
    records = findings.area_records(area)
    if not records:
        raise findings.FindingsError(
            f"{area}: no findings record — run the audit first"
        )
    return records[-1].path


def _findings(area: Path, record: Path | None) -> int:
    """`--findings`: RECORD's (the newest's) findings numbered with their
    `--decide` commands, read from the record — no model call, no new
    record. The auditor's READ hints are not recorded, so none show here.
    Exit 2 when there is no record to read."""
    try:
        rec = findings.read(
            record_path(area, record) if record is not None else _newest_record(area)
        )
    except findings.FindingsError as exc:
        console.refuse("labkit-audit", str(exc))
        return 2
    for line in decision_lines(rec, area, ""):
        print(line)
    return 0


def _decide(
    area: Path,
    decide: list[str],
    record: Path | None,
    effect: str = "",
    protocol: Path | None = None,
) -> int:
    """`--decide`: store the person's decision on one finding of RECORD (the
    area's newest record without it) through `findings.write_decision`,
    with EFFECT for an accepted BLOCKER — its ids held to the promises the
    protocol registers; print what was written and how many findings stay
    open. Exit 2 on a decision that cannot be stored, the file untouched."""
    n_text, status, reason = decide
    try:
        if not n_text.isdigit():
            raise findings.FindingsError(f"N must be a finding number, not {n_text!r}")
        if effect:
            _registered(area, protocol, effect)
        record = _newest_record(area) if record is None else record_path(area, record)
        rec = findings.write_decision(record, int(n_text), status, reason, effect)
    except findings.FindingsError as exc:
        console.refuse("labkit-audit", str(exc))
        return 2
    print(
        f"decided: {record.name} finding {n_text}: {status}"
        + (f" ({effect.strip()})" if effect.strip() else "")
        + (f" — {reason.strip()}" if reason.strip() else "")
        + f" · {len(rec.open)} open"
    )
    return 0


def _registered(area: Path, protocol: Path | None, effect: str) -> None:
    """FindingsError unless every id EFFECT names is a promise of the area's protocol."""
    try:
        ids = findings.effect_ids(effect)
    except ValueError as exc:
        raise findings.FindingsError(str(exc)) from exc
    if not ids:
        return
    try:
        chosen = the_protocol(area, protocol)
    except ProtocolChoiceError as exc:
        raise findings.FindingsError(f"the effect's ids: {exc}") from exc
    block = promises.parse_block(chosen.read_text(encoding="utf-8"))
    known = set(block.by_id()) if block is not None else set()
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise findings.FindingsError(
            f"effect names {', '.join(unknown)} — {chosen.name} registers "
            f"{', '.join(sorted(known)) or 'no promise'}"
        )


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
