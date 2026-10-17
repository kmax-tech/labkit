"""findings — an audit's findings as data the person decides, not as prose.

`labkit-audit` (MODE preflight or analysis) writes what it found into the
area, one file per audit:

    experiments/<NN>-<name>/audits/2026-10-12T15-33-preflight.toml

    [audit]
    date = "2026-10-12T15:33"
    mode = "preflight"
    model = "opus"
    scope_sha = "fa45c7618423"
    blockers = 1
    warnings = 2
    notes = 1

    [[finding]]
    grade = "BLOCKER"
    text = "BLOCKER · scripts/01_measure.py:42 · … · LAB-038 What the prompt demands · …"
    status = "open"      # open | fixed | accepted | deferred | dismissed
    reason = ""          # owed for accepted, deferred and dismissed

The person edits `status` and `reason`; nothing else writes the file.

Two more records say that an audit was STARTED but has no result yet, or
never got one (2026-10-16, labkit-paper area 09, haiku t3: the agent took
a killed second audit call for a failed audit and ran the full run with
LABKIT_UNFROZEN=1 while the first call's BLOCKER landed in `audits/`
unread; omx' code-review names the state `independent review
unavailable` and never lets it pass as approval):

    2026-10-16T14-55-preflight.running      # written before the model call,
    [audit]                                 # removed when the record is written
    date = "2026-10-16T14:55"
    mode = "preflight"
    model = "opus"
    scope_sha = "fa45c7618423"
    pid = 4711
    script = "labkit-audit"                 # for runs.is_alive: pid alone recycles

    2026-10-16T14-57-preflight.toml         # the call failed: a record without a result
    [audit]
    …
    outcome = "unavailable"
    reason = "claude-cli: not logged in"
    blockers = 0 …                          # and no [[finding]] table

A marker whose pid is dead is an audit that died (SIGTERM, a harness
timeout) — an `unavailable` too, read by `audit_stops`. An audit that did
not run is not passed: a full run waits on a live marker and is refused
on an unavailable one, acknowledgement or not (author's decision
2026-10-17: fail loud instead of marking silently). The way out is a new
`labkit-audit`, whose record replaces the marker — never deleting the file.

A full run at `minutes`/`hours` needs a preflight record WITH A RESULT whose
`scope_sha` is the code's stamp now, every finding decided
(`audit_coverage`, held by runlog's freeze gate and by `preflight`), and
no stop from `audit_stops` (an open BLOCKER in any record, a running or
unavailable audit). `preflight` reads every
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
import os
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from labkit.runs import is_alive

DIR = "audits"
#: the one value `outcome` takes — a record without `outcome` carries a result
UNAVAILABLE = "unavailable"
#: the marker an audit leaves between its stamp and its record
RUNNING_SUFFIX = ".running"
STATUSES = ("open", "fixed", "accepted", "deferred", "dismissed")
REASON_OWED = ("accepted", "deferred", "dismissed")
GRADES = ("BLOCKER", "WARNING", "NOTE")
MODES = ("preflight", "analysis")


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
    scope_sha: str
    verdict: tuple[int, int, int]
    findings: tuple[Finding, ...]
    #: why the audit has no result (`outcome = "unavailable"`); None for a result
    unavailable: str | None = None

    @property
    def open(self) -> list[Finding]:
        """The findings nobody has decided yet."""
        return [f for f in self.findings if f.status == "open"]

    @property
    def deferred(self) -> list[Finding]:
        """The findings put off as somebody's later task."""
        return [f for f in self.findings if f.status == "deferred"]


def _s(value: str) -> str:
    """A TOML basic string: json's escaping is a subset of TOML's."""
    return json.dumps(value, ensure_ascii=False)


def write(
    area: Path,
    mode: str,
    model: str,
    scope_sha: str,
    verdict: tuple[int, int, int],
    findings: list[tuple[str, str]],
    now: float | None = None,
) -> Path:
    """Write the audit's findings file into AREA/audits/ and return its path.
    Every finding starts `open`. Never overwrites: the name carries the minute.
    Refuses (ValueError) a verdict that counts more blockers or warnings than
    FINDINGS lists of that grade — notes are not held, an auditor counts
    them loosely.
    """
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} — one of {', '.join(MODES)}")
    b, w, _ = verdict
    listed = {g: sum(1 for grade, _ in findings if grade == g) for g in GRADES}
    if b > listed["BLOCKER"] or w > listed["WARNING"]:
        # a record whose counts outrun its tables read as "nothing open" —
        # covered, decided, frozen (audit 2026-10-15)
        raise ValueError(
            f"the verdict counts {b} blocker(s) and {w} warning(s), the report "
            f"carries {listed['BLOCKER']} BLOCKER and {listed['WARNING']} WARNING "
            f"line(s) readable as findings (`BLOCKER · <where> · …`) — nothing is "
            f"recorded; have the auditor write each finding as one such line"
        )
    when = time.localtime(now)
    path = _fresh_path(area, mode, when, ".toml")
    b, w, k = verdict
    lines = [
        "# written by labkit-audit — decide each finding: set status and reason",
        "[audit]",
        f"date = {_s(time.strftime('%Y-%m-%dT%H:%M', when))}",
        f"mode = {_s(mode)}",
        f"model = {_s(model)}",
        f"scope_sha = {_s(scope_sha)}",
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_unavailable(
    area: Path,
    mode: str,
    model: str,
    scope_sha: str,
    reason: str,
    now: float | None = None,
) -> Path:
    """Write the record of an audit that got no result — backend error,
    timeout, a truncated prompt — into AREA/audits/ and return its path:
    `outcome = "unavailable"` with the reason, the stamp the auditor would
    have read, no findings. Refuses (ValueError) an empty reason: a record
    that cannot say why is the silent failure it is meant to replace."""
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} — one of {', '.join(MODES)}")
    if not reason.strip():
        raise ValueError("an unavailable audit owes its reason")
    when = time.localtime(now)
    path = _fresh_path(area, mode, when, ".toml")
    lines = [
        "# written by labkit-audit — this audit got NO result; rerun it, do not delete this",
        "[audit]",
        f"date = {_s(time.strftime('%Y-%m-%dT%H:%M', when))}",
        f"mode = {_s(mode)}",
        f"model = {_s(model)}",
        f"scope_sha = {_s(scope_sha)}",
        f"outcome = {_s(UNAVAILABLE)}",
        f"reason = {_s(reason.strip())}",
        "blockers = 0",
        "warnings = 0",
        "notes = 0",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _fresh_path(area: Path, mode: str, when: time.struct_time, suffix: str) -> Path:
    """`audits/<minute>-<mode><suffix>`, never an existing file: a second
    audit in the same minute gets `-2`, `-3`, …"""
    stamp = time.strftime("%Y-%m-%dT%H-%M", when)
    folder = area / DIR
    folder.mkdir(exist_ok=True)
    path = folder / f"{stamp}-{mode}{suffix}"
    n = 2
    while path.exists():
        path = folder / f"{stamp}-{mode}-{n}{suffix}"
        n += 1
    return path


def _audit_table(path: Path, data: dict) -> dict:
    """The `[audit]` table of a findings file, held to its shape; `outcome`,
    when present, is `unavailable` and owes a `reason`."""
    audit = data.get("audit")
    if not isinstance(audit, dict):
        raise FindingsError(f"{path}: no [audit] table")
    for key in ("date", "mode", "model", "scope_sha"):
        if not isinstance(audit.get(key), str):
            raise FindingsError(f"{path}: [audit] {key} is missing or not a string")
    for key in ("blockers", "warnings", "notes"):
        if not isinstance(audit.get(key), int) or isinstance(audit.get(key), bool):
            raise FindingsError(f"{path}: [audit] {key} is missing or not an integer")
    if audit["mode"] not in MODES:
        raise FindingsError(
            f"{path}: [audit] mode {audit['mode']!r} — one of {', '.join(MODES)}"
        )
    if "outcome" in audit:
        if audit["outcome"] != UNAVAILABLE:
            raise FindingsError(
                f"{path}: [audit] outcome {audit['outcome']!r} — the one value is "
                f"{UNAVAILABLE!r}; a record with a result has no outcome key"
            )
        if not isinstance(audit.get("reason"), str) or not audit["reason"].strip():
            raise FindingsError(f"{path}: [audit] outcome unavailable owes a reason")
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
    unavailable = audit["reason"].strip() if "outcome" in audit else None
    if unavailable is not None and rows:
        raise FindingsError(
            f"{path}: an unavailable audit carries {len(rows)} [[finding]] table(s) — "
            f"it has no result, so it has no findings"
        )
    return Record(
        path,
        audit["date"],
        audit["mode"],
        audit["model"],
        audit["scope_sha"],
        (audit["blockers"], audit["warnings"], audit["notes"]),
        tuple(_finding(path, i, row) for i, row in enumerate(rows, start=1)),
        unavailable,
    )


def area_records(area: Path) -> list[Record]:
    """Every findings file of AREA, oldest first; a file that cannot be read raises."""
    folder = area / DIR
    if not folder.is_dir():
        return []
    return [read(p) for p in sorted(folder.glob("*.toml"))]


def audit_coverage(area: Path, sha: str, mode: str) -> str | None:
    """Why no audit of MODE covers the area's code stamped SHA, or None: a
    record with that `mode` whose `scope_sha` is SHA, every finding of it
    decided. The head's audit line is written by hand; this is what makes
    "the frozen code was audited" a fact instead of a line (2026-10-14: after
    fixing the audit's findings a cold agent stamped the new sha, and no
    audit had seen that code). `preflight` for the freeze (runlog, preflight),
    `analysis` for the report (report-check).

    Raises:
        FindingsError: A findings file of AREA cannot be read.
        ValueError: MODE is not one of MODES.
    """
    if mode not in MODES:
        raise ValueError(f"audit mode {mode!r} is not one of {', '.join(MODES)}")
    records = [r for r in area_records(area) if r.mode == mode]
    covering = [r for r in records if r.scope_sha == sha and r.unavailable is None]
    if not covering:
        failed = [r for r in records if r.scope_sha == sha and r.unavailable]
        if failed:
            last = failed[-1]
            return (
                f"the {mode} audit of {sha} got no result ({last.path.name}: "
                f"{last.unavailable}) — an audit that did not run is not passed: "
                f"rerun `labkit-audit <area> --mode {mode}`"
            )
        seen = ", ".join(sorted({r.scope_sha for r in records})) or "none"
        return (
            f"no {mode} audit saw the code as it is now (scope sha {sha}; "
            f"audited: {seen}) — a change after the audit owes a new one: "
            f"`labkit-audit <area> --mode {mode}`"
        )
    undecided = [f for r in covering for f in r.open]
    if undecided:
        return (
            f"{len(undecided)} finding(s) of the {mode} audit of {sha} still "
            f"`open` — decide each (fixed / accepted / deferred / dismissed)"
        )
    return None


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


# -------------------------------------------------------------- running audits


@dataclass(frozen=True)
class Running:
    """The marker an audit left before its model call: who runs it, since when."""

    path: Path
    date: str
    mode: str
    model: str
    scope_sha: str
    pid: int
    script: str


def mark_running(
    area: Path,
    mode: str,
    model: str,
    scope_sha: str,
    pid: int | None = None,
    script: str | None = None,
    now: float | None = None,
) -> Path:
    """Leave `audits/<minute>-<mode>.running` before the model call and return
    its path; the caller removes it once the record is written (`write` or
    `write_unavailable`). PID and SCRIPT default to this process, as
    `runs.is_alive` needs them: a pid alone is recycled by the OS."""
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} — one of {', '.join(MODES)}")
    when = time.localtime(now)
    path = _fresh_path(area, mode, when, RUNNING_SUFFIX)
    lines = [
        "# written by labkit-audit before its model call — removed with the record;",
        "# still here with a dead pid: the audit died, rerun it (never delete this)",
        "[audit]",
        f"date = {_s(time.strftime('%Y-%m-%dT%H:%M', when))}",
        f"mode = {_s(mode)}",
        f"model = {_s(model)}",
        f"scope_sha = {_s(scope_sha)}",
        f"pid = {os.getpid() if pid is None else pid}",
        f"script = {_s(Path(sys.argv[0]).name if script is None else script)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def read_running(path: Path) -> Running:
    """The marker at PATH; raises FindingsError on anything it cannot hold to."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise FindingsError(f"{path}: not TOML ({exc})") from exc
    audit = data.get("audit")
    if not isinstance(audit, dict):
        raise FindingsError(f"{path}: no [audit] table")
    for key in ("date", "mode", "model", "scope_sha", "script"):
        if not isinstance(audit.get(key), str):
            raise FindingsError(f"{path}: [audit] {key} is missing or not a string")
    if not isinstance(audit.get("pid"), int) or isinstance(audit["pid"], bool):
        raise FindingsError(f"{path}: [audit] pid is missing or not an integer")
    if audit["mode"] not in MODES:
        raise FindingsError(
            f"{path}: [audit] mode {audit['mode']!r} — one of {', '.join(MODES)}"
        )
    return Running(
        path,
        audit["date"],
        audit["mode"],
        audit["model"],
        audit["scope_sha"],
        audit["pid"],
        audit["script"],
    )


def area_running(area: Path) -> list[Running]:
    """Every running marker of AREA, oldest first; one that cannot be read raises."""
    folder = area / DIR
    if not folder.is_dir():
        return []
    return [read_running(p) for p in sorted(folder.glob(f"*{RUNNING_SUFFIX}"))]


def audit_stops(
    area: Path, alive: Callable[[object, object], bool | None] | None = None
) -> list[str]:
    """Why no FULL run may start in AREA whatever the acknowledgement says —
    one line each, in the order omx' review table combines verdicts: an open
    BLOCKER in any record beats everything; then an audit without a result
    (a marker whose pid is dead, or the newest record of a mode unavailable);
    then an audit still running (a marker with a live pid: wait). Open
    WARNINGs are no stop — `open_warnings` lists them for the acknowledgement
    line. ALIVE defaults to `runs.is_alive` (pid, script) → True / False / None;
    None (undecidable: no `ps`) counts as not known to run, so the marker
    reads as an audit that died — loud, and a rerun resolves it. Empty when
    nothing stands in the way, including an area without `audits/` (the pilot
    whose audit nobody could start).

    Raises:
        FindingsError: A record or marker of AREA cannot be read.
    """
    alive = is_alive if alive is None else alive  # resolved here: tests fake it
    out = []
    records = area_records(area)
    for r in records:
        for f in r.findings:
            if f.grade == "BLOCKER" and f.status == "open":
                out.append(
                    f"audit BLOCKER still `open` in {r.path.name}: {f.text} — decide "
                    f"it (fixed / accepted / deferred / dismissed); LABKIT_UNFROZEN=1 "
                    f"does not pass an undecided BLOCKER"
                )
    for mode in MODES:
        of_mode = [r for r in records if r.mode == mode]
        if of_mode and of_mode[-1].unavailable:
            last = of_mode[-1]
            out.append(
                f"audit unavailable since {last.date} ({last.path.name}): "
                f"{last.unavailable} — an audit that did not run is not passed; "
                f"rerun `labkit-audit <area> --mode {mode}`"
            )
    waiting = []
    for m in area_running(area):
        if alive(m.pid, m.script) is True:
            waiting.append(
                f"audit running since {m.date} ({m.path.name}, pid {m.pid}, "
                f"{m.model}) — wait for its record, then decide its findings"
            )
        else:
            out.append(
                f"audit died since {m.date} ({m.path.name}, pid {m.pid} gone): no "
                f"result — rerun `labkit-audit <area> --mode {m.mode}`; the new "
                f"record replaces the marker, deleting it does not"
            )
    return out + waiting


def open_warnings(area: Path) -> list[str]:
    """The WARNING findings still `open` in any record of AREA, one line each —
    no stop, but named in the acknowledgement line of an unfrozen full run."""
    return [
        f"audit WARNING still `open` in {r.path.name}: {f.text}"
        for r in area_records(area)
        for f in r.findings
        if f.grade == "WARNING" and f.status == "open"
    ]
