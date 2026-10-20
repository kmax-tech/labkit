"""findings — an audit's findings as data the person decides, not as prose.

`labkit-audit` (MODE preflight or analysis) writes what it found into the
area, one file per audit:

    experiments/<NN>-<name>/audits/2026-10-12T15-33-preflight.toml

    [audit]
    date = "2026-10-12T15:33"
    mode = "preflight"
    model = "opus"
    scope_sha = "fa45c7618423"   # the code the auditor read (scope_sha.area_stamp)
    block_sha = "0c1d2e3f4a5b"   # the promises it read (promises.block_stamp)
    # run_id = "2026-10-12T15-01-07_a1b2"  — mode analysis only: the run whose rows it read
    blockers = 1
    warnings = 2
    notes = 1

    [[finding]]
    grade = "BLOCKER"
    text = "BLOCKER · scripts/01_measure.py:42 · … · LAB-038 What the prompt demands · …"
    status = "open"      # open | fixed | accepted | deferred | dismissed
    reason = ""          # owed for accepted, deferred and dismissed

The person edits `status` and `reason`; nothing else writes the file.

When the backend does not answer (`llm_backends.BackendError`: the CLI died, the
server was down, every retry ran out), `labkit-audit` writes no findings
but the evidence that it tried, next to them:

    audits/2026-10-12T15-33-preflight-failed.toml

    [failed]
    date = "2026-10-12T15:33"
    mode = "preflight"
    model = "opus"
    scope_sha = "fa45c7618423"   # the code it would have read
    block_sha = "0c1d2e3f4a5b"   # the promises it would have read
    timeout_s = 900              # the time the call was given
    error = "claude-cli exit 1: …"
    command = "labkit-audit experiments/09-x --mode preflight"

That file is what `LABKIT_UNFROZEN=1` acknowledges at `minutes`/`hours`:
an audit that could not run, not one nobody ran (`audit_unavailable`, held
by runlog's freeze gate since 0.99.0). labkit writes it, with the error the
backend gave; a usage error (an unknown alias, an area that cannot be
stamped) is not an unavailable audit and leaves none. A record of findings
and a failed attempt never share a name; `area_records` reads the records
only.
A record binds what the auditor read: the code (`scope_sha`), the promise
block (`block_sha`) and, in mode analysis, the answering run (`run_id`).
A full run at `minutes`/`hours` needs a preflight record of the code and
the promises as they are now, every finding decided (`audit_coverage`,
held by runlog's freeze gate and by `preflight`); a reported number needs
an analysis record of code, promises and the answering run as they are
now (`report-check`). Until 0.97.1 a record named the code only, so a
promise rewritten after the audit, or a later run under the same code,
kept the old audit valid (review 2026-10-18). `preflight` reads every
findings file of the area: a finding still `open`
is a warning before the freeze and a blocker once `frozen = true`
(LAB-015 Preflight audit before freezing: every finding is decided), a `deferred`
finding anywhere in the repo is printed as a reminder and never counted.

Why (uniagent, 2026-10-12, 23 preflight and 21 analysis audits read by
hand): a finding deferred in area 16 as "its own task" bit in area 17; the
same finding was accepted three times in three areas; 13 of 44 audit lines
end in "accepted/dismissed" and what they decided is lost in a 400-character
protocol line. With the findings as data the deferred ones stay visible and
an audit's yield (fixed / accepted / dismissed per class) can be counted
instead of read.

Reading is loud: an unknown status, a decided status without a reason, a
file without its `[audit]` table raise FindingsError naming the file and
the field — a findings file nobody can read is not "no findings".
"""

from __future__ import annotations

import json
import re
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import promises
from labkit.formats.scope_sha import AUDIT_SHA, audit_stamp_drift

DIR = "audits"
#: the suffix of a failed attempt's file, never of a record of findings
FAILED_SUFFIX = "-failed.toml"
#: the seconds `labkit-audit` gives its one call by default, and the least a
#: failed attempt must have been given to count as one (`audit_unavailable`):
#: an attempt given less time than the audit takes is not an attempt
ATTEMPT_TIMEOUT_S = 900
STATUSES = ("open", "fixed", "accepted", "deferred", "dismissed")
REASON_OWED = ("accepted", "deferred", "dismissed")
GRADES = ("BLOCKER", "WARNING", "NOTE")
MODES = ("preflight", "analysis")
#: what an analysis record names as its run when no completed run was
#: bound to the protocol while the auditor read — it saw no rows
NO_RUN = "none"


class FindingsError(ValueError):
    """A findings file that cannot be read as such; the message names file and field."""


@dataclass(frozen=True)
class Finding:
    """One finding of one audit and what the person decided about it."""

    grade: str
    text: str
    status: str
    reason: str


@dataclass(frozen=True)
class Record:
    """One audit's findings file."""

    path: Path
    date: str
    mode: str
    model: str
    scope_sha: str  # the code the auditor read
    block_sha: str  # the promise block it read (promises.NO_BLOCK: none declared)
    run_id: (
        str | None
    )  # mode analysis: the run whose rows it read (NO_RUN: none); preflight: None
    verdict: tuple[int, int, int]
    findings: tuple[Finding, ...]

    @property
    def open(self) -> list[Finding]:
        """The findings nobody has decided yet."""
        return [f for f in self.findings if f.status == "open"]

    @property
    def deferred(self) -> list[Finding]:
        """The findings put off as somebody's later task."""
        return [f for f in self.findings if f.status == "deferred"]


def counts_outrun(verdict: tuple[int, int, int], grades: list[str]) -> str | None:
    """Why VERDICT counts more blockers or warnings than GRADES lists, or
    None: a record whose counts outrun its tables reads as "nothing open"
    — covered, decided, frozen (audit 2026-10-15). Notes are not held; an
    auditor counts them loosely. One answer for the writer and the reader:
    a person edits the files, so the reader holds the same line (review
    2026-10-18: `blockers = 2` without a table read as covered)."""
    b, w, _ = verdict
    listed = {g: sum(1 for grade in grades if grade == g) for g in GRADES}
    if b > listed["BLOCKER"] or w > listed["WARNING"]:
        return (
            f"the verdict counts {b} blocker(s) and {w} warning(s), the record "
            f"carries {listed['BLOCKER']} BLOCKER and {listed['WARNING']} WARNING "
            f"line(s)"
        )
    return None


def verdict_disagrees(verdict: tuple[int, int, int], grades: list[str]) -> str | None:
    """Why VERDICT's blockers and warnings are not exactly the BLOCKER and
    WARNING lines GRADES lists, or None — the one audit result a record and
    an exit code are made from. More lines than counted is a withdrawn
    finding ("Correction: no finding" under a BLOCKER line): exit 0 while the
    record kept the blocker open, and the next gate refused the coverage
    (review 2026-10-20). Notes are not held; an auditor counts them loosely."""
    b, w, _ = verdict
    listed = {g: sum(1 for grade in grades if grade == g) for g in GRADES}
    if b != listed["BLOCKER"] or w != listed["WARNING"]:
        return (
            f"the verdict counts {b} blocker(s) and {w} warning(s), the report "
            f"lists {listed['BLOCKER']} BLOCKER and {listed['WARNING']} WARNING "
            f"line(s)"
        )
    return None


def _s(value: str) -> str:
    """A TOML basic string: json's escaping is a subset of TOML's."""
    return json.dumps(value, ensure_ascii=False)


def write(
    area: Path,
    mode: str,
    model: str,
    scope_sha: str,
    block_sha: str,
    verdict: tuple[int, int, int],
    findings: list[tuple[str, str]],
    *,
    run_id: str | None = None,
    now: float | None = None,
) -> Path:
    """Write the audit's findings file into AREA/audits/ and return its path.
    SCOPE_SHA is the code the auditor read, BLOCK_SHA the promise block
    (`promises.block_stamp`), RUN_ID the run whose rows it read — owed in
    mode analysis (NO_RUN when there was none), refused in mode preflight.
    Every finding starts `open`. Never overwrites: the name carries the minute,
    and a second record of that minute takes the next number (`_create`).
    Refuses (ValueError) a verdict whose blockers and warnings are not
    exactly the BLOCKER and WARNING lines of FINDINGS (`verdict_disagrees`):
    a finding line is never withdrawn by prose below it.
    """
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} — one of {', '.join(MODES)}")
    if (mode == "analysis") != (run_id is not None):
        raise ValueError(
            f"mode {mode!r} with run_id {run_id!r}: an analysis audit names the "
            f"run it read (NO_RUN for none), a preflight audit names none"
        )
    disagree = verdict_disagrees(verdict, [grade for grade, _ in findings])
    if disagree:
        raise ValueError(
            f"{disagree} — nothing is recorded: every finding is one "
            f"`BLOCKER · <where> · …` line, the verdict counts exactly those, and "
            f"no line is withdrawn below it; run the audit again"
        )
    when = time.localtime(now)
    stamp = time.strftime("%Y-%m-%dT%H-%M", when)
    b, w, k = verdict
    lines = [
        "# written by labkit-audit — decide each finding: set status and reason",
        "[audit]",
        f"date = {_s(time.strftime('%Y-%m-%dT%H:%M', when))}",
        f"mode = {_s(mode)}",
        f"model = {_s(model)}",
        f"scope_sha = {_s(scope_sha)}",
        f"block_sha = {_s(block_sha)}",
        *([f"run_id = {_s(run_id)}"] if run_id is not None else []),
        f"blockers = {b}",
        f"warnings = {w}",
        f"notes = {k}",
    ]
    for grade, text in findings:
        if grade not in GRADES:
            raise ValueError(f"grade {grade!r} — one of {', '.join(GRADES)}")
        lines += [
            "",
            "[[finding]]",
            f"grade = {_s(grade)}",
            f"text = {_s(text)}",
            'status = "open"',
            'reason = ""',
        ]
    return _create(area / DIR, f"{stamp}-{mode}", ".toml", "\n".join(lines) + "\n")


def _create(folder: Path, name: str, suffix: str, text: str) -> Path:
    """Write TEXT to `FOLDER/<name><suffix>`, else `<name>-2<suffix>`, … —
    the first name no file holds, taken by exclusive create, so two audits
    finishing in one minute get two files: a check for a free name before
    a plain write let both take the same one, and one record was lost
    (review 2026-10-20). Creates FOLDER."""
    folder.mkdir(exist_ok=True)
    n = 1
    while True:
        path = folder / f"{name}{'' if n == 1 else f'-{n}'}{suffix}"
        try:
            with path.open("x", encoding="utf-8") as f:
                f.write(text)
        except FileExistsError:
            n += 1
            continue
        return path


def _audit_table(path: Path, data: dict) -> dict:
    """The `[audit]` table of a findings file, held to its shape."""
    audit = data.get("audit")
    if not isinstance(audit, dict):
        raise FindingsError(f"{path}: no [audit] table")
    for key in ("date", "mode", "model", "scope_sha", "block_sha"):
        if not isinstance(audit.get(key), str):
            raise FindingsError(f"{path}: [audit] {key} is missing or not a string")
    for key in ("blockers", "warnings", "notes"):
        if not isinstance(audit.get(key), int) or isinstance(audit.get(key), bool):
            raise FindingsError(f"{path}: [audit] {key} is missing or not an integer")
    if audit["mode"] not in MODES:
        raise FindingsError(
            f"{path}: [audit] mode {audit['mode']!r} — one of {', '.join(MODES)}"
        )
    if audit["mode"] == "analysis" and not isinstance(audit.get("run_id"), str):
        raise FindingsError(
            f"{path}: [audit] run_id is missing or not a string — an analysis "
            f"audit names the run it read ({NO_RUN!r} for none)"
        )
    if audit["mode"] == "preflight" and "run_id" in audit:
        raise FindingsError(
            f"{path}: [audit] run_id {audit['run_id']!r} in a preflight audit, "
            f"which reads no run"
        )
    return audit


def _finding(path: Path, i: int, row: object) -> Finding:
    """The i-th `[[finding]]` table, held to grade, status and the owed reason."""
    if not isinstance(row, dict):
        raise FindingsError(f"{path}: finding {i} is not a table")
    for key in ("grade", "text", "status", "reason"):
        if not isinstance(row.get(key), str):
            raise FindingsError(
                f"{path}: finding {i}: {key} is missing or not a string"
            )
    if row["grade"] not in GRADES:
        raise FindingsError(
            f"{path}: finding {i}: grade {row['grade']!r} — one of {', '.join(GRADES)}"
        )
    if row["status"] not in STATUSES:
        raise FindingsError(
            f"{path}: finding {i}: status {row['status']!r} — one of {', '.join(STATUSES)}"
        )
    if row["status"] in REASON_OWED and not row["reason"].strip():
        raise FindingsError(
            f"{path}: finding {i}: status {row['status']!r} owes a reason"
        )
    return Finding(row["grade"], row["text"], row["status"], row["reason"].strip())


def read(path: Path) -> Record:
    """The findings file at PATH; raises FindingsError on anything it cannot hold to."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise FindingsError(f"{path}: not TOML ({exc})") from exc
    audit = _audit_table(path, data)
    rows = data.get("finding", [])
    if not isinstance(rows, list):
        raise FindingsError(f"{path}: `finding` must be [[finding]] tables")
    parsed = tuple(_finding(path, i, row) for i, row in enumerate(rows, start=1))
    outrun = counts_outrun(
        (audit["blockers"], audit["warnings"], audit["notes"]),
        [f.grade for f in parsed],
    )
    if outrun:
        raise FindingsError(f"{path}: {outrun} — a finding was lost or a count edited")
    return Record(
        path,
        audit["date"],
        audit["mode"],
        audit["model"],
        audit["scope_sha"],
        audit["block_sha"],
        audit.get("run_id"),
        (audit["blockers"], audit["warnings"], audit["notes"]),
        parsed,
    )


#: the name `_create` gives a record or a failed attempt:
#: `<minute>-<mode>[-<n>]` and its suffix, n counting the files of one minute
_WRITTEN_NAME = re.compile(
    rf"^(\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}-\d{{2}})-(?:{'|'.join(MODES)})(?:-(\d+))?"
    rf"(?:{re.escape(FAILED_SUFFIX)}|\.toml)$"
)


def written_order(path: Path) -> tuple[str, int, str]:
    """The sort key of a file `_create` wrote, oldest first: its minute, then
    its number within the minute as a number. By name, `-2` and `-3` sorted
    before the minute's first file, and the newest failed attempt read as
    the oldest (review 2026-10-20). Raises FindingsError for a name of
    another shape: its age cannot be told."""
    m = _WRITTEN_NAME.match(path.name)
    if m is None:
        raise FindingsError(
            f"{path}: not a name labkit-audit writes (<minute>-<mode>[-<n>].toml) "
            f"— its place among the records cannot be told; rename or move it"
        )
    return (m.group(1), int(m.group(2) or 1), path.name)


def area_records(area: Path) -> list[Record]:
    """Every findings file of AREA, oldest first (`written_order`); a file
    that cannot be read raises."""
    folder = area / DIR
    if not folder.is_dir():
        return []
    paths = [p for p in folder.glob("*.toml") if not p.name.endswith(FAILED_SUFFIX)]
    return [read(p) for p in sorted(paths, key=written_order)]


def _bound(sha: str, block_sha: str, run_id: str | None) -> str:
    """What a record binds, in words: `code <sha>, promises <block>[, run <id>]`."""
    return f"code {sha}, promises {block_sha}" + (
        f", run {run_id}" if run_id is not None else ""
    )


def audit_coverage(
    area: Path, sha: str, mode: str, block_sha: str, run_id: str | None = None
) -> str | None:
    """Why no audit of MODE covers the area as it is now, or None: a record
    with that `mode` whose `scope_sha` is SHA (the code), whose `block_sha`
    is BLOCK_SHA (the promises, `promises.block_stamp`) and — mode analysis
    — whose `run_id` is RUN_ID (the answering run), every finding of it
    decided. The head's audit line is written by hand; this is what makes
    "the frozen code was audited" a fact instead of a line (2026-10-14: after
    fixing the audit's findings a cold agent stamped the new sha, and no
    audit had seen that code). `preflight` for the freeze (runlog, preflight),
    `analysis` for the report (report-check). Until 0.97.1 only the code was
    held: a promise rewritten after the audit, or a later run under the same
    code, kept the old record valid (review 2026-10-18).

    Raises:
        FindingsError: A findings file of AREA cannot be read.
        ValueError: MODE is not one of MODES, or RUN_ID is given for
            `preflight` or missing for `analysis`.
    """
    if mode not in MODES:
        raise ValueError(f"audit mode {mode!r} is not one of {', '.join(MODES)}")
    if (mode == "analysis") != (run_id is not None):
        raise ValueError(
            f"audit mode {mode!r} with run_id {run_id!r}: an analysis audit is "
            f"held to the answering run, a preflight audit to none"
        )
    records = [r for r in area_records(area) if r.mode == mode]
    covering = [
        r
        for r in records
        if (r.scope_sha, r.block_sha, r.run_id) == (sha, block_sha, run_id)
    ]
    if not covering:
        seen = (
            "; ".join(
                sorted({_bound(r.scope_sha, r.block_sha, r.run_id) for r in records})
            )
            or "none"
        )
        return (
            f"no {mode} audit saw the area as it is now "
            f"({_bound(sha, block_sha, run_id)}; audited: {seen}) — a change after "
            f"the audit owes a new one: `labkit-audit <area> --mode {mode}`"
        )
    undecided = [f for r in covering for f in r.open]
    if undecided:
        return (
            f"{len(undecided)} finding(s) of the {mode} audit of {sha} still "
            f"`open` — decide each (fixed / accepted / deferred / dismissed)"
        )
    return None


@dataclass(frozen=True)
class Failed:
    """One attempt at an audit whose backend did not answer — written by
    `labkit-audit`, never by hand (the evidence an acknowledged full run
    rests on)."""

    path: Path
    date: str
    mode: str
    model: str
    scope_sha: str  # the code it would have read
    block_sha: str  # the promise block it would have read
    timeout_s: int  # the seconds the one call was given
    error: str  # what the backend said
    command: str  # the command line that tried


def write_failed(
    area: Path,
    mode: str,
    model: str,
    scope_sha: str,
    block_sha: str,
    timeout_s: int,
    error: str,
    command: str,
    *,
    now: float | None = None,
) -> Path:
    """Write the evidence of an audit that could not run into AREA/audits/
    and return its path: `<stamp>-<mode>-failed.toml`, never overwriting.
    SCOPE_SHA and BLOCK_SHA name what the auditor would have read, so the
    freeze gate can hold the acknowledgement to the code and promises as
    they are now; TIMEOUT_S what the call was given; ERROR the backend's
    words; COMMAND the line that tried."""
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} — one of {', '.join(MODES)}")
    when = time.localtime(now)
    stamp = time.strftime("%Y-%m-%dT%H-%M", when)
    lines = [
        "# written by labkit-audit — the audit did not run; this is the evidence, "
        "not a record of findings",
        "[failed]",
        f"date = {_s(time.strftime('%Y-%m-%dT%H:%M', when))}",
        f"mode = {_s(mode)}",
        f"model = {_s(model)}",
        f"scope_sha = {_s(scope_sha)}",
        f"block_sha = {_s(block_sha)}",
        f"timeout_s = {int(timeout_s)}",
        f"error = {_s(error)}",
        f"command = {_s(command)}",
    ]
    return _create(
        area / DIR, f"{stamp}-{mode}", FAILED_SUFFIX, "\n".join(lines) + "\n"
    )


def read_failed(path: Path) -> Failed:
    """The failed attempt at PATH; raises FindingsError on anything it
    cannot hold to — a file nobody can read is not evidence."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise FindingsError(f"{path}: not TOML ({exc})") from exc
    table = data.get("failed")
    if not isinstance(table, dict):
        raise FindingsError(f"{path}: no [failed] table")
    for key in ("date", "mode", "model", "scope_sha", "block_sha", "error", "command"):
        if not isinstance(table.get(key), str):
            raise FindingsError(f"{path}: [failed] {key} is missing or not a string")
    timeout = table.get("timeout_s")
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        raise FindingsError(f"{path}: [failed] timeout_s is missing or not an integer")
    if table["mode"] not in MODES:
        raise FindingsError(
            f"{path}: [failed] mode {table['mode']!r} — one of {', '.join(MODES)}"
        )
    return Failed(
        path,
        table["date"],
        table["mode"],
        table["model"],
        table["scope_sha"],
        table["block_sha"],
        timeout,
        table["error"],
        table["command"],
    )


def failed_attempts(area: Path) -> list[Failed]:
    """Every failed attempt of AREA, oldest first (`written_order`); a file
    that cannot be read raises."""
    folder = area / DIR
    if not folder.is_dir():
        return []
    return [
        read_failed(p)
        for p in sorted(folder.glob(f"*{FAILED_SUFFIX}"), key=written_order)
    ]


def audit_unavailable(
    area: Path, sha: str, mode: str, block_sha: str | None
) -> Failed | None:
    """The newest failed attempt of MODE at the area as it is now — code SHA
    and, when given, promises BLOCK_SHA — whose call was given at least
    ATTEMPT_TIMEOUT_S seconds; None when none is. This is what a full run's
    acknowledgement rests on: an audit that could not run. An attempt at
    other code or other promises says nothing about these; an attempt given
    less time than the audit takes (`--timeout 1`) is not an attempt. Both
    are mechanical, and both are said in the refusal.

    Raises:
        FindingsError: A failed-attempt file of AREA cannot be read.
    """
    if mode not in MODES:
        raise ValueError(f"audit mode {mode!r} is not one of {', '.join(MODES)}")
    fitting = [
        f
        for f in failed_attempts(area)
        if f.mode == mode
        and f.scope_sha == sha
        and (block_sha is None or f.block_sha == block_sha)
        and f.timeout_s >= ATTEMPT_TIMEOUT_S
    ]
    return fitting[-1] if fitting else None


def waived_audit_gap(line: str) -> str | None:
    """Why an audit line reading `n/a — <reason>` does not cover a full run
    at `minutes`/`hours`, or None when the line says something else. Until
    0.99.0 `n/a` passed every gate as "a visible decision"; third haiku round
    on 0.99.0 (labkit-paper area 09, t18): the agent wrote `frozen = true`
    with `preflight_audit = "n/a — RF model training does not require
    external audit"`, and runlog took it. Nobody waives their own audit;
    the line names the honest ways and offers no word to write instead."""
    if not line.strip().lower().startswith("n/a"):
        return None
    return (
        "`preflight_audit` says n/a — at minutes/hours a full run owes the "
        "preflight audit, and nobody waives their own: run `labkit-audit <area> "
        "--mode preflight` and stamp the scope sha it prints; when the backend "
        "does not answer, labkit-audit records the failed attempt and a full run "
        "acknowledges it with LABKIT_UNFROZEN=1 (its number stays unreportable). "
        "If no audit is owed at all, the cost tier is wrong, not the line — and "
        "a tier lowered after the protocol's first commit is reported "
        "(LAB-015 Preflight audit before freezing, LAB-017 The number of audits follows the cost tier)"
    )


def audit_line_gap(area: Path, line: str, text: str) -> str | None:
    """Why the head's non-empty `preflight_audit` LINE does not cover a full
    run of AREA under the protocol TEXT, or None: it waives the audit
    (`waived_audit_gap`), its `scope sha` is not the code's stamp now
    (`scope_sha.audit_stamp_drift`), or no decided preflight record saw that
    code and the promise block TEXT carries now (`audit_coverage`). One
    answer for runlog's freeze gate and `preflight` (they had two copies
    until 0.99.0); the caller decides what an empty line and `seconds` mean."""
    waived = waived_audit_gap(line)
    if waived:
        return waived
    drift = audit_stamp_drift(area, line)
    if drift:
        return drift
    m = AUDIT_SHA.search(line)
    assert m is not None, "audit_stamp_drift passes a line only with a sha"
    try:
        return audit_coverage(area, m.group(1), "preflight", promises.block_stamp(text))
    except (FindingsError, promises.PromiseError) as exc:
        return str(exc)


def repo_records(experiments: Path) -> list[tuple[Path, Record]]:
    """(area, record) for every findings file under EXPERIMENTS, by area then date."""
    out = []
    for folder in sorted(experiments.glob(f"*/{DIR}")):
        if folder.is_dir():
            out += [(folder.parent, r) for r in area_records(folder.parent)]
    return out


def deferred_elsewhere(
    area: Path, experiments: Path
) -> list[tuple[Path, Record, Finding]]:
    """Deferred findings in other areas of the repo — "its own task" that
    nobody picked up (uniagent 16 → 17, 2026-10-08)."""
    return [
        (other, rec, f)
        for other, rec in repo_records(experiments)
        if other.resolve() != area.resolve()
        for f in rec.deferred
    ]
