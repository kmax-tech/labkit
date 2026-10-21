"""labkit-audit — the agent audits of an area, through any llm backend.

    labkit-audit <AREA> --mode preflight|analysis|clarity [--protocol FILE]
                 [--model ALIAS] [--timeout S] [--out FILE]

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

Exit codes are the contract, made from one audit result: the LAST verdict
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
from labkit.run import llm, llm_backends
from labkit.formats import (
    console,
    findings,
    promises,
    protocol_block,
    rules,
    runs,
    scope_sha,
)
from labkit.formats.standard_contract import lane
from labkit.formats.repo import (
    ProtocolChoiceError,
    area_path,
    layout_root,
    no_such_area,
    shown,
    the_protocol,
)
from labkit.formats.runs import completed_runs, read_outputs
from labkit.formats.answering_run import bound_answering_run
from labkit.formats.scope_sha import (
    area_files,
    area_snapshot,
    area_stamp,
    repo_imports,
)

AGENT = PACKAGE_DIR / "agents" / "experiment-preflight.agent.md"
CLARITY_AGENT = PACKAGE_DIR / "agents" / "code-clarity.agent.md"
DEFAULT_MODEL = "opus"  # the agent's model; any alias of models.toml works
REPORT_TOKENS = 4096  # room for a report of many findings, where a backend caps
DEFAULT_TIMEOUT_S = (
    findings.ATTEMPT_TIMEOUT_S
)  # one call reads the area, the rules, the rows
MODES = ("preflight", "analysis", "clarity")
CLARITY = "clarity"
ANALYSIS = "analysis"
STANDARD_LABEL = (
    "labkit/docs/standard.md"  # the shipped standard, wherever labkit is installed
)
ROWS_HEAD, ROWS_TAIL = 50, 20  # what the instructions tell the auditor to read
ROW_WIDTH = 2000  # a longer row (a trace) is cut, marked, never dropped

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
    "`<line>: <row>`. Nothing else is in scope."
)


class AuditError(RuntimeError):
    """No audit could be made — the cause is in the message."""


def instructions(mode: str = "preflight") -> str:
    """The agent's instructions as shipped, without the provenance comment —
    the preflight agent for preflight and analysis, the clarity agent for clarity."""
    agent = CLARITY_AGENT if mode == CLARITY else AGENT
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


def audited_run(
    area: Path, protocol: Path, text: str | None = None
) -> tuple[Path | None, str]:
    """The run an analysis audit reads and its record is bound to — the
    answering run (`answering_run.bound_answering_run`, the one choice every gate
    holds the protocol to) read off the protocol file (or TEXT, the
    protocol as the caller's file state holds it), or `(None, why)`: no
    protocol id, no completed bound run, a blocker of the choice. Raises
    AuditError on a head it cannot read. report-check holds the record to
    the same choice (`report_check.checked`)."""
    if text is None:
        text = protocol.read_text(encoding="utf-8")
    try:
        pid = protocol_block.head(text).id
    except protocol_block.BlockError as exc:
        raise AuditError(f"{protocol.name}: head unreadable — {exc}") from exc
    if pid is None:
        return None, "the protocol id is still a placeholder"
    choice = bound_answering_run(area, pid)
    blocker, _ = choice.explain(promises.registers_ids(text))
    if blocker or choice.run_dir is None:
        return None, blocker or "no completed bound run"
    return choice.run_dir, ""


def run_rows(area: Path, run_dir: Path | None, why: str) -> list[tuple[str, str]]:
    """What MODE analysis is told to read of RUN_DIR, the answering run as
    `audited_run` chose it ONCE for both the prompt and the record: `(label,
    text)` per piece — the first ROWS_HEAD and last ROWS_TAIL lines of every
    output the run registered, numbered as `<n>: <row>`, and its
    metrics.json. One `(label, note)` pair says why there is nothing: WHY
    (no protocol id, no completed bound run), or no registered output."""
    repo = layout_root(area)
    if run_dir is None:
        return [("ROWS", f"no rows: {why}")]
    registered = read_outputs(run_dir)
    out: list[tuple[str, str]] = []
    rel_run = run_dir.resolve().relative_to(repo.resolve()).as_posix()
    if not registered:
        out.append((f"ROWS {rel_run}", "no rows: the run registered no output file"))
    for entry in registered or []:
        path = Path(entry.path)
        path = path if path.is_absolute() else repo / path
        if not path.is_file():
            raise AuditError(f"{run_dir.name} registered {entry.path}, which is gone")
        name = shown(path, repo)
        out.append(rows_excerpt(path, name))
    metrics = run_dir / "metrics.json"
    if metrics.is_file():
        out.append(
            (f"FILE: {rel_run}/metrics.json", metrics.read_text(encoding="utf-8"))
        )
    return out


class RunShown(NamedTuple):
    """What MODE analysis shows of the answering run, taken once: the
    pieces the prompt renders (`run_rows`) and their digest, which the record
    carries as `shown_sha` and report-check recomputes — a metrics.json or
    output rows changed after the audit owe a new one (review 2026-10-20:
    the run id alone could not tell)."""

    pieces: tuple[tuple[str, str], ...]
    sha: str


def run_shown(area: Path, run_dir: Path | None, why: str) -> RunShown:
    """`run_rows` of RUN_DIR as one snapshot with its digest."""
    pieces = tuple(run_rows(area, run_dir, why))
    return RunShown(pieces, scope_sha.digest(runs.as_stored(pieces).encode("utf-8")))


def rows_excerpt(path: Path, name: str) -> tuple[str, str]:
    """`(label, text)` of one output file: its first ROWS_HEAD and last
    ROWS_TAIL lines as `<line>: <row>`, a gap marked by its size, a row
    longer than ROW_WIDTH cut and marked — never silently dropped."""
    lines = path.read_text(encoding="utf-8").splitlines()
    n = len(lines)
    shown = (
        range(n)
        if n <= ROWS_HEAD + ROWS_TAIL
        else [*range(ROWS_HEAD), *range(n - ROWS_TAIL, n)]
    )
    body: list[str] = []
    last = -1
    for i in shown:
        if i != last + 1:
            body.append(f"… {i - last - 1} line(s) not shown …")
        row = lines[i]
        if len(row) > ROW_WIDTH:
            row = row[:ROW_WIDTH] + f" … [{len(lines[i]) - ROW_WIDTH} more chars]"
        body.append(f"{i + 1}: {row}")
        last = i
    label = f"ROWS {name} ({n} line(s); the first {ROWS_HEAD} and last {ROWS_TAIL} are shown)"
    return label, "\n".join(body)


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
    audit, so the prompt shows the bytes the record's sha names), and in
    MODE analysis what it shows of the answering run (`run_shown`, the same
    pieces whose digest the record carries)."""

    protocol_text: str
    read: Callable[[Path], str]
    run: tuple[tuple[str, str], ...] = ()


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
        if mode == ANALYSIS:
            pieces += source.run
    body = "".join(f"===== {label} =====\n{text}\n" for label, text in pieces)
    return (
        f"{instructions(mode)}\n\nMODE: {mode} · AREA: {rel(area)}\n\n"
        f"{INLINE_NOTE}\n\n{body}"
    )


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


def early_for_tier(area: Path, protocol: Path, mode: str) -> list[str]:
    """One WARNING line when a preflight audit comes before the cost tier
    asks for it: at `cost = "seconds"` the first run is the cheaper probe
    and ONE audit in mode analysis after it covers the preflight rows
    (LAB-017 The number of audits follows the cost tier). uniagent area 01,
    2026-10-05: two preflight audits and an analysis audit at seconds, and
    the protocol itself says one after the first run would have done. A
    head this labkit cannot read says nothing here — protocol-check does."""
    if mode != "preflight":
        return []
    try:
        head = protocol_block.head(protocol.read_text(encoding="utf-8"))
    except protocol_block.BlockError:
        return []
    if mode in lane(head.cost).audits or completed_runs(area, with_repeats=True):
        return []
    return [
        'WARNING · cost = "seconds" and no completed run · the first run is the '
        "cheaper probe; one audit in --mode analysis after it covers the preflight "
        "rows too · LAB-017 The number of audits follows the cost tier · run first, "
        "audit once"
    ]


class Stamp(NamedTuple):
    """The area's stamp as the auditor saw it: taken ONCE, before the call.
    Until 0.95.0 it was taken after the model answered (up to 900 s later),
    so a lib module edited meanwhile gave a record whose sha no auditor had
    read, and the freeze gate took it as covered (audit 2026-10-15)."""

    sha: str
    files: list[Path]


def stamp_facts(stamp: Stamp, verdict: tuple[int, int, int]) -> str:
    """The facts of the protocol's audit field — the human adds the decisions.
    The sha is `scope_sha.area_stamp`, the same a later `scope-sha` recomputes."""
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
) -> str:
    """The auditor's report. When the backend does not answer (the CLI died,
    the server was down, the retries ran out) there is no audit, and the
    evidence that one was tried — on this code, these promises, with this
    much time — goes next to the records (`findings.write_failed`) before
    the AuditError that ends the command with exit 2. That file is what a
    LABKIT_UNFROZEN=1 rests on (second haiku round on 0.98.0:
    no agent started an audit, and the hatch asked for nothing). A usage
    error (an alias models.toml does not know) is not an unavailable audit
    and propagates as it is, so none is written for it."""
    try:
        return llm.complete(
            args.model,
            prompt,
            timeout=args.timeout,
            max_tokens=_report_room(args.model),
        )
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
        )
        raise AuditError(
            f"{exc}\nlabkit-audit: no audit — the backend did not answer; recorded "
            f"as {tried}. A full run at minutes/hours may acknowledge it with "
            f"LABKIT_UNFROZEN=1; its number cannot be reported (report-check "
            f"refuses it). Run the audit again when the backend answers."
        ) from exc


def _report_room(alias: str) -> int | None:
    """The token cap an audit report is given: REPORT_TOKENS where the
    backend takes a cap, none where it has none (claude-cli, whose own limit
    is far above a report)."""
    return REPORT_TOKENS if llm.takes_max_tokens(alias) else None


def bound_prompt(
    mode: str, area: Path, reading: Reading
) -> tuple[str, Stamp, str, str | None, str | None, list[Path]]:
    """(prompt, stamp, block sha, run id, shown sha, indexed files) from ONE
    reading:
    the record binds what the prompt shows. The code is one snapshot: its
    bytes render the prompt, its sha goes in the record, and every stamped
    file the reading does not take in full is indexed — so the prompt shows
    each file the stamp covers, no more and no fewer. The promise block
    comes from the one protocol text the prompt carries; in MODE analysis
    the run is chosen once, and what the prompt shows of it is one snapshot
    whose digest goes in the record (NO_RUN when none answers).

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
    changed = "the area changed while it was read; run the audit again"
    try:
        prompt = render(
            mode,
            area,
            protocol,
            reading.code,
            reading.standard,
            indexed,
            source=Source(text, snap.text, shown.pieces if shown else ()),
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
    return prompt, stamp, promises.block_stamp(text), run_id, shown_sha, indexed


def main(argv: list[str]) -> int:
    """Command line of `labkit-audit`: audit one area in one mode, or store
    a decision the person gives on one of its findings (`--decide`)."""
    ap = argparse.ArgumentParser(
        prog="labkit-audit", description=(__doc__ or "").splitlines()[0]
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
        "--record", type=Path, help="with --decide: this record, not the newest"
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
    if args.decide is not None:
        return _decide(args.area, args.decide, args.record)
    if args.mode == CLARITY:
        return _clarity(args)
    try:
        reading = gather(args.area, args.protocol)
        protocol, code = reading.protocol, reading.code
        for line in early_for_tier(args.area, protocol, args.mode):
            print(f"labkit-audit: {line}", file=sys.stderr)
        prompt, stamp, block_sha, run_id, shown_sha, indexed = bound_prompt(
            args.mode, args.area, reading
        )
        print(
            f"labkit-audit: {args.mode} · {protocol.name} · {len(code)} code file(s) "
            f"in full, {len(indexed)} indexed · "
            f"{args.model} · {len(prompt) // 1000} kB",
            file=sys.stderr,
        )
        report = _answer_or_record(args, argv, prompt, stamp, block_sha)
        print(f"labkit-audit: tokens · {llm.last_usage().describe()}", file=sys.stderr)
        result = parse(report)
    except (
        AuditError,
        llm_backends.PromptTruncated,
        KeyError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        # KeyError: llm.resolve on an alias models.toml does not know;
        # FileNotFoundError, ValueError: the area cannot be stamped;
        # ValueError also: the promise block cannot be read (PromiseError)
        print(f"labkit-audit: {str(exc).strip(chr(39))}", file=sys.stderr)
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
            run_id=run_id,
            shown_sha=shown_sha,
        )
    except ValueError as exc:  # verdict and finding lines disagree
        print(f"labkit-audit: {exc}", file=sys.stderr)
        return 2
    print(f"\nstamp: {stamp_facts(stamp, result['verdict'])}", file=sys.stderr)
    now = area_stamp(args.area)[0]
    if now != stamp.sha:
        print(
            f"stamp NOTE: the code changed while the auditor read it — it saw scope "
            f"sha {stamp.sha}, the code now stamps {now}; the record names {stamp.sha}, "
            f"and the change owes its own audit",
            file=sys.stderr,
        )
    for line in decision_lines(findings.read(recorded), args.area, report):
        print(line, file=sys.stderr)
    # the auditor lists what it read in full; the indexed modules are the
    # caller's to add before the list is held to the stamp (LAB-103 The audit reads by declared scope)
    listed_scope = result["scope"] + [str(p) for p in indexed]
    for gap in scope_mismatch(args.area, listed_scope, stamp.files):
        print(f"scope WARNING: {gap}", file=sys.stderr)
    return 1 if b or w else 0


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
    hints = [ln.strip() for ln in report.splitlines() if READ_HINT.match(ln)]
    if hints:
        out.append("reading hints — not recorded, nothing to decide:")
        out += [f"  {h}" for h in hints]
    return out


def _check_args(ap: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Exactly one of --mode (audit) and --decide (store a decision); --record
    only with --decide. A usage error exits 2 through argparse."""
    if (args.mode is None) == (args.decide is None):
        ap.error("give --mode to audit, or --decide N STATUS REASON — one of them")
    if args.record is not None and args.decide is None:
        ap.error("--record goes with --decide")


def _decide(area: Path, decide: list[str], record: Path | None) -> int:
    """`--decide`: store the person's decision on one finding of RECORD (the
    area's newest record without it) through `findings.write_decision`;
    print what was written and how many findings stay open. Exit 2 on a
    decision that cannot be stored, the file untouched."""
    n_text, status, reason = decide
    try:
        if not n_text.isdigit():
            raise findings.FindingsError(f"N must be a finding number, not {n_text!r}")
        if record is None:
            records = findings.area_records(area)
            if not records:
                raise findings.FindingsError(
                    f"{area}: no findings record to decide in — run the audit first"
                )
            record = records[-1].path
        rec = findings.write_decision(record, int(n_text), status, reason)
    except findings.FindingsError as exc:
        console.refuse("labkit-audit", str(exc))
        return 2
    print(
        f"decided: {record.name} finding {n_text}: {status}"
        + (f" — {reason.strip()}" if reason.strip() else "")
        + f" · {len(rec.open)} open"
    )
    return 0


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
        print(
            f"labkit-audit: clarity · {protocol.name} · README + {files[1].name} · "
            f"{args.model} · {len(prompt) // 1000} kB",
            file=sys.stderr,
        )
        report = llm.complete(
            args.model,
            prompt,
            timeout=args.timeout,
            max_tokens=_report_room(args.model),
        )
        print(f"labkit-audit: tokens · {llm.last_usage().describe()}", file=sys.stderr)
        result = parse_clarity(report)
    except (
        AuditError,
        llm_backends.BackendError,
        llm_backends.PromptTruncated,
        KeyError,
    ) as exc:
        # KeyError: llm.resolve on an alias models.toml does not know
        print(f"labkit-audit: {str(exc).strip(chr(39))}", file=sys.stderr)
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
