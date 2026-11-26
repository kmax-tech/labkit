"""audit_records — an audit's findings file: written by labkit-audit, read
loudly, a decision rewritten in place, and the records an area holds.

`labkit-audit` (MODE preflight or analysis) writes what it found into the
area, one file per audit:

    experiments/<NN>-<name>/audits/2026-10-12T15-33-preflight.toml

    [audit]
    date = "2026-10-12T15:33"
    mode = "preflight"
    model = "opus"
    scope_sha = "fa45c7618423"   # the code the auditor read (scope_sha.area_stamp)
    block_sha = "0c1d2e3f4a5b"   # the promises it read (promises.block_stamp)
    registration = { "kind" = "compute", "Question / hypothesis" = "9a8b7c6d5e4f" }
                                 # what it judged (protocol_check.registration_stamp)
    # run_id = "2026-10-12T15-01-07_a1b2"  — mode analysis only: the run whose rows it read
    blockers = 1
    warnings = 2
    notes = 1

    [[finding]]
    grade = "BLOCKER"
    text = "BLOCKER · scripts/01_measure.py:42 · … · LAB-038 What the prompt demands · …"
                         # the finding whole: its grade line and the lines the
                         # auditor wrote below it, joined by line breaks (\n)
    status = "open"      # open | fixed | limitation | false-positive
    reason = ""          # owed for limitation and false-positive
    # effect = "stands"  — a BLOCKER or WARNING decided limitation: see EFFECT
    # replaced_decisions = [ … ]  — before `status`, once a decision replaced
    #                      another: each earlier decision, kept (`decision_history`)

The person decides each finding with `labkit-audit AREA --decide N STATUS
--why REASON`, which validates the decision the person typed and stores it
(`write_decision`) — the one supported way to write a decision; a record
changed by hand is not one labkit wrote, whatever its fields say, and a
check of the file cannot tell who wrote them. labkit never decides.

Reading is loud: an unknown status, a decided status without a reason, a
file without its `[audit]` table raise `findings.FindingsError` naming the file and
the field — a findings file nobody can read is not "no findings".
"""

from __future__ import annotations

import re
import time
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import decision_history, protocol_block
from labkit.formats.commands import audit_command, checkout_command, stage_command
from labkit.formats.decision_history import ReplacedDecision
from labkit.formats.gate import BLOCKER, NEW_CLASS_RULE, RuleAssignment
from labkit.formats.protocol_block import toml_string as _s
from labkit.formats.repo import INDEX_REV, files_at, git_root, shown, text_at
from labkit.formats.runs import date_minute, name_minute
from labkit.formats.standard_contract import ANALYSIS_AUDIT, PREFLIGHT_AUDIT
from labkit.formats.audit_files import DIR, create_file, is_record_name, written_order
from labkit.formats.finding_decisions import subject_refusal
from labkit.formats.finding_limits import EFFECT_FORM, effect_ids
from labkit.formats.finding_line import (
    GRADES,
    SUBJECTS,
    active_rule_of,
    recorded_rule,
    recorded_rule_problem,
    stored_rule,
    subject_of,
)
from labkit.formats.findings import (
    CARRIES_REF,
    DECIDED,
    EffectFormError,
    Finding,
    FindingsError,
    FixVerdict,
    MODES,
    NO_RUN,
    OPEN,
    REASON_OWED,
    Record,
    STATUSES,
    count_problem,
    counts_outrun,
    fix_verdict_problem,
    undetermined_finding_problem,
    verdict_disagrees,
)
from labkit.formats.required_check import (
    CHECK_KEY,
    REQUEST_CHECKS,
    check_of,
    evidence_request,
)


#: why a record changed by hand may not parse — told in the refusal of a
#: file that does not (an unescaped quote in a reason makes it unreadable)
REASON_FORM = (
    'a reason is a TOML string: "double quotes" escape a quote as \\" and a '
    "backslash as \\\\; 'single quotes' take one line of text without a ' "
    "or a control character"
)


def _head_problem(
    mode: str, protocol_id: str, run_id: str | None, shown_sha: str | None
) -> str | None:
    """What is wrong with the `[audit]` head `write` is handed, or None: a
    PROTOCOL_ID not of `protocol_block.ID_SHAPE`, a MODE outside MODES, a
    RUN_ID or SHOWN_SHA given in preflight or missing in analysis."""
    if not protocol_block.ID_SHAPE.match(protocol_id):
        return (
            f"protocol_id {protocol_id!r}: the stamped id of the audited protocol "
            f"(`labkit-init exp` stamps it)"
        )
    if mode not in MODES:
        return f"mode {mode!r} — one of {', '.join(MODES)}"
    if (mode == ANALYSIS_AUDIT) != (run_id is not None):
        return (
            f"mode {mode!r} with run_id {run_id!r}: an analysis audit names the "
            f"run it read (NO_RUN for none), a preflight audit names none"
        )
    if (mode == ANALYSIS_AUDIT) != (shown_sha is not None):
        return (
            f"mode {mode!r} with shown_sha {shown_sha!r}: an analysis audit names "
            f"what it was shown of the run, a preflight audit is shown none"
        )
    return None


def write(
    area: Path,
    mode: str,
    model: str,
    scope_sha: str,
    block_sha: str,
    verdict: tuple[int, int, int],
    findings: list[tuple[str, str]],
    *,
    registration: Mapping[str, str],
    protocol_id: str,
    run_id: str | None = None,
    shown_sha: str | None = None,
    fix_verdicts: Iterable[FixVerdict] = (),
    carried: Iterable[Finding] = (),
    followup_size: tuple[int, int] | None = None,
    now: float | None = None,
) -> Path:
    """Write the audit's findings file into AREA/audits/ and return its path.
    SCOPE_SHA is the code the auditor read, BLOCK_SHA the promise block
    (`promises.block_stamp`), REGISTRATION the registration it judged
    (`protocol_check.registration_stamp`), PROTOCOL_ID the stamped id of the
    protocol it read (refused when not `protocol_block.ID_SHAPE`), RUN_ID the run whose rows it read and SHOWN_SHA
    the digest of what the prompt showed of it (`audit_binding.run_shown`) — both
    owed in mode analysis (RUN_ID NO_RUN when there was none), refused in
    mode preflight.
    Every finding starts `open`. Never overwrites: the name carries the minute,
    and a second record of that minute takes the next number (`create_file`).
    Refuses (ValueError) a count that is not a non-negative integer
    (`count_problem`) and a verdict whose blockers and warnings are not
    exactly the BLOCKER and WARNING lines of FINDINGS (`verdict_disagrees`):
    a finding line is never withdrawn by prose below it.
    FIX_VERDICTS are written as `[[fix_verdict]]` tables after the
    findings, in mode analysis only; a verdict outside FIX_VERDICTS, one
    without its why and a second one on the same finding are refused
    (`fix_verdict_problem`). CARRIED are the earlier findings a follow-up
    did not find resolved, as `followup.carried_finding` built them: each
    is written open after the auditor's findings, counted in `blockers`
    and in `carried_blockers` — the counts are the record's whole, the
    auditor's own verdict is FINDINGS'. FOLLOWUP_SIZE (entries, bytes) is
    what the follow-up piece measured, written as `followup`.
    """
    carried = tuple(carried)
    problem = _head_problem(mode, protocol_id, run_id, shown_sha)
    if problem:
        raise ValueError(problem)
    for key, value in zip(("blockers", "warnings", "notes"), verdict, strict=True):
        problem = count_problem(key, value)
        if problem:
            raise ValueError(f"verdict: {problem}")
    fix_lines = _fix_verdict_lines(mode, fix_verdicts)
    carried_lines = _carried_lines(mode, carried)
    disagree = verdict_disagrees(verdict, [grade for grade, _ in findings])
    if disagree:
        raise ValueError(
            f"{disagree} — nothing is recorded: every finding is one "
            f"`BLOCKER · <where> · …` line, the verdict counts exactly those, and "
            f"no line is withdrawn below it; run the audit again"
        )
    when = time.localtime(now)
    stamp = name_minute(when)
    b, w, k = verdict
    lines = [
        "# written by labkit-audit — decide each finding with "
        "`labkit-audit <area> --decide N STATUS --why REASON`; a record changed by hand is not one labkit wrote",
        "[audit]",
        f"date = {_s(date_minute(when))}",
        f"mode = {_s(mode)}",
        f"protocol = {_s(protocol_id)}",
        f"model = {_s(model)}",
        f"scope_sha = {_s(scope_sha)}",
        f"block_sha = {_s(block_sha)}",
        "registration = { "
        + ", ".join(f"{_s(k)} = {_s(v)}" for k, v in registration.items())
        + " }",
        *([f"run_id = {_s(run_id)}"] if run_id is not None else []),
        *([f"shown_sha = {_s(shown_sha)}"] if shown_sha is not None else []),
        f"blockers = {b + len(carried)}",
        f"warnings = {w}",
        f"notes = {k}",
        *([f"carried_blockers = {len(carried)}"] if carried else []),
        *(
            [
                f"followup = {{ entries = {followup_size[0]}, bytes = {followup_size[1]} }}"
            ]
            if followup_size is not None
            else []
        ),
    ]
    for grade, text in findings:
        check, note = check_of(text)
        if grade not in GRADES:
            raise ValueError(f"grade {grade!r} — one of {', '.join(GRADES)}")
        subject = subject_of(text)
        rule = active_rule_of(text)
        problem = undetermined_finding_problem(grade, subject, check, note)
        if problem:
            raise ValueError(f"{problem}: {text.splitlines()[0][:160]!r}")
        lines += [
            "",
            "[[finding]]",
            f"grade = {_s(grade)}",
            f"text = {_s(text)}",
            f"subject = {_s(subject)}",
            f"rule = {_s(rule)}",
            *([f"check = {_s(check)}"] if check else []),
            *([f"check_note = {_s(note)}"] if note else []),
            'status = "open"',
            'reason = ""',
        ]
    lines += carried_lines + fix_lines
    return create_file(area / DIR, f"{stamp}-{mode}", ".toml", "\n".join(lines) + "\n")


def _carried_lines(mode: str, carried: tuple[Finding, ...]) -> list[str]:
    """CARRIED as open `[[finding]]` tables. Raises ValueError outside mode
    analysis and on one that is no BLOCKER or names no finding it carries."""
    if carried and mode != ANALYSIS_AUDIT:
        raise ValueError(
            f"mode {mode!r} with carried findings: only a follow-up carries"
        )
    lines: list[str] = []
    for f in carried:
        if f.grade != BLOCKER or not CARRIES_REF.match(f.carries):
            raise ValueError(
                f"a carried finding is a BLOCKER naming `<record>#<n>`: "
                f"{f.grade} carries {f.carries!r}"
            )
        if f.subject not in SUBJECTS:
            raise ValueError(
                f"a carried finding names its subject, one of "
                f"{', '.join(SUBJECTS)}: {f.carries} carries {f.subject!r}"
            )
        try:
            stored = stored_rule(f.rule)
        except ValueError as exc:
            raise ValueError(
                f"a carried finding names its rule: {f.carries}: {exc}"
            ) from exc
        lines += [
            "",
            "[[finding]]",
            f"grade = {_s(f.grade)}",
            f"text = {_s(f.text)}",
            f"subject = {_s(f.subject)}",
            f"rule = {_s(stored)}",
            *([f"check = {_s(f.check)}"] if f.check else []),
            *([f"check_note = {_s(f.check_note)}"] if f.check_note else []),
            f"carries = {_s(f.carries)}",
            'status = "open"',
            'reason = ""',
        ]
    return lines


def _fix_verdict_lines(mode: str, verdicts: Iterable[FixVerdict]) -> list[str]:
    """VERDICTS as the `[[fix_verdict]]` tables a record ends with. Raises
    ValueError on verdicts outside mode analysis and on what
    `fix_verdict_problem` refuses."""
    verdicts = tuple(verdicts)
    if verdicts and mode != ANALYSIS_AUDIT:
        raise ValueError(
            f"mode {mode!r} with fix verdicts: only an analysis audit judges "
            f"earlier repairs"
        )
    problem = fix_verdict_problem(verdicts)
    if problem:
        raise ValueError(problem)
    lines: list[str] = []
    for v in verdicts:
        lines += [
            "",
            "[[fix_verdict]]",
            f"record = {_s(v.record)}",
            f"n = {v.n}",
            f"decision_sha = {_s(v.decision_sha)}",
            f"verdict = {_s(v.verdict)}",
            f"why = {_s(v.why)}",
            *(
                [
                    f"check = {_s(v.check)}",
                    f"check_present = {str(v.check_present).lower()}",
                ]
                if v.check
                else []
            ),
            *([f"subject = {_s(v.subject)}"] if v.subject else []),
        ]
    return lines


def _audit_table(path: Path, data: dict) -> dict:
    """The `[audit]` table of a findings file, held to its shape."""
    audit = data.get("audit")
    if not isinstance(audit, dict):
        raise FindingsError(f"{path}: no [audit] table")
    for key in ("date", "mode", "model", "scope_sha", "block_sha"):
        if not isinstance(audit.get(key), str):
            raise FindingsError(f"{path}: [audit] {key} is missing or not a string")
    for key in ("blockers", "warnings", "notes"):
        problem = count_problem(key, audit.get(key))
        if problem:
            raise FindingsError(f"{path}: [audit] {problem}")
    if audit["mode"] not in MODES:
        raise FindingsError(
            f"{path}: [audit] mode {audit['mode']!r} — one of {', '.join(MODES)}"
        )
    pid = audit.get("protocol")
    if not isinstance(pid, str) or not protocol_block.ID_SHAPE.match(pid):
        raise FindingsError(
            f"{path}: [audit] protocol {pid!r} — a record names the id of the protocol "
            f"it audited; a record without it was written by labkit 0.112.0 or "
            f"earlier and is read with that version"
        )
    problem = _run_fields_problem(audit)
    if problem:
        raise FindingsError(f"{path}: [audit] {problem}")
    reg = audit.get("registration")
    if not (
        isinstance(reg, dict) and reg and all(isinstance(v, str) for v in reg.values())
    ):
        raise FindingsError(
            f"{path}: [audit] registration is missing or not a table of strings — "
            f"a record names the registration it judged (the question and the "
            f"other fields the kind owes); a record written before labkit bound "
            f"it is no longer read: run the audit again"
        )
    return audit


def _run_fields_problem(audit: dict) -> str | None:
    """Why the run fields do not fit the record's mode, or None: an analysis
    record names the run it read (`run_id`, NO_RUN for none) and what it was
    shown of it (`shown_sha`); a preflight record reads no run and names
    neither."""
    if audit["mode"] == PREFLIGHT_AUDIT:
        extra = [k for k in ("run_id", "shown_sha") if k in audit]
        return (
            f"{', '.join(extra)} in a preflight audit, which reads no run"
            if extra
            else None
        )
    if not isinstance(audit.get("run_id"), str):
        return (
            f"run_id is missing or not a string — an analysis audit names the "
            f"run it read ({NO_RUN!r} for none)"
        )
    if not isinstance(audit.get("shown_sha"), str):
        return (
            "shown_sha is missing or not a string — an analysis record names what "
            "it was shown of the run; a record written before labkit bound it is "
            "no longer read: run the analysis audit again"
        )
    return None


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
    effect = row.get("effect", "")
    if not isinstance(effect, str):
        raise FindingsError(f"{path}: finding {i}: effect is not a string")
    check, note, subject, rule = _auditor_fields(path, i, row)
    carries = row.get("carries", "")
    if not isinstance(carries, str) or (carries and not CARRIES_REF.match(carries)):
        raise FindingsError(
            f"{path}: finding {i}: carries {carries!r} — `<record file>#<n>` or absent"
        )
    found = Finding(
        row["grade"],
        row["text"],
        row["status"],
        row["reason"].strip(),
        effect.strip(),
        check,
        note,
        carries,
        subject,
        rule,
        _replaced_decisions(path, i, row),
    )
    problem = _effect_problem(found)
    if problem:
        raise FindingsError(f"{path}: finding {i}: {problem}")
    return found


def _replaced_decisions(path: Path, i: int, row: dict) -> tuple[ReplacedDecision, ...]:
    """The replaced decisions of the i-th `[[finding]]` table
    (`decision_history.read_entries`), each held to what a decision on this
    finding can be: a status of STATUSES and an effect that fits it
    (`_effect_problem`). Raises FindingsError naming the entry."""
    try:
        entries = decision_history.read_entries(row.get(decision_history.KEY))
    except decision_history.DecisionHistoryError as exc:
        raise FindingsError(f"{path}: finding {i}: {exc}") from exc
    for k, entry in enumerate(entries, start=1):
        where = f"{path}: finding {i}: {decision_history.KEY} entry {k}"
        if entry.status not in STATUSES:
            raise FindingsError(
                f"{where}: status {entry.status!r} — one of {', '.join(STATUSES)}"
            )
        problem = _effect_problem(
            Finding(row["grade"], row["text"], entry.status, entry.reason, entry.effect)
        )
        if problem:
            raise FindingsError(f"{where}: {problem}")
    return entries


def _auditor_fields(
    path: Path, i: int, row: dict
) -> tuple[str, str, str, RuleAssignment]:
    """(check, check_note, subject, rule) of the i-th `[[finding]]` table —
    the fields labkit-audit takes from the auditor's line, never a decision:
    a metrics key or "", a note only beside a check, one of SUBJECTS, and a
    rule id of the ledger or NEW_CLASS (`recorded_rule_problem`) — a record without
    subject or rule is one labkit 0.112.0 or earlier wrote, read with that
    version (the repo's pin), never here. Raises FindingsError
    otherwise (`carries` is read beside them)."""
    check = row.get("check", "")
    if not isinstance(check, str) or (check and not CHECK_KEY.match(check)):
        raise FindingsError(
            f"{path}: finding {i}: check {check!r} is no metrics key (lowercase "
            f"snake_case), no `file:<path>`, no `diff:<run>..<run>[:<path>]` and "
            f"no `code:<run>:<path>` (each with an optional line range)"
        )
    if check.startswith(REQUEST_CHECKS):
        try:
            evidence_request(check)
        except ValueError as exc:
            raise FindingsError(f"{path}: finding {i}: {exc}") from exc
    note = row.get("check_note", "")
    if not isinstance(note, str) or (note and not check):
        raise FindingsError(
            f"{path}: finding {i}: check_note {note!r} — a string, and only with a check"
        )
    subject = row.get("subject")
    if subject not in SUBJECTS:
        raise FindingsError(
            f"{path}: finding {i}: subject {subject!r} — one of {', '.join(SUBJECTS)}; "
            f"a record without subjects was written by labkit 0.112.0 or earlier "
            f"and is read with that version"
        )
    rule = row.get("rule")
    if rule is None:
        raise FindingsError(
            f"{path}: finding {i}: no rule field — a record without rules was "
            f"written by labkit 0.112.0 or earlier and is read with that version"
        )
    rule_refused = recorded_rule_problem(rule)
    if rule_refused is not None:
        raise FindingsError(f"{path}: finding {i}: {rule_refused}")
    problem = undetermined_finding_problem(row["grade"], subject, check, note)
    if problem:
        raise FindingsError(f"{path}: finding {i}: {problem}")
    return check, note, subject, recorded_rule(str(rule))


def read(path: Path) -> Record:
    """The findings file at PATH; raises FindingsError on anything it cannot hold to."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FindingsError(f"{path}: not TOML ({exc}) — {REASON_FORM}") from exc
    return _record_of(path, text)


def _record_of(path: Path, text: str) -> Record:
    """TEXT read as the findings file at PATH (`read`'s check, on text not yet
    written: `write_decision` reads its result back before it writes)."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise FindingsError(f"{path}: not TOML ({exc}) — {REASON_FORM}") from exc
    audit = _audit_table(path, data)
    rows = data.get("finding", [])
    if not isinstance(rows, list):
        raise FindingsError(f"{path}: `finding` must be [[finding]] tables")
    parsed = tuple(_finding(path, i, row) for i, row in enumerate(rows, start=1))
    verdicts = _fix_verdicts(path, data.get("fix_verdict", []))
    if verdicts and audit["mode"] != ANALYSIS_AUDIT:
        raise FindingsError(
            f"{path}: fix_verdict in a {audit['mode']} audit — only an analysis "
            f"audit judges earlier repairs"
        )
    carried_n = audit.get("carried_blockers", 0)
    problem = count_problem("carried_blockers", carried_n)
    if (
        problem
        or carried_n != sum(1 for f in parsed if f.carries)
        or carried_n > audit["blockers"]
    ):
        raise FindingsError(
            f"{path}: [audit] carried_blockers = {carried_n!r}, the record carries "
            f"{sum(1 for f in parsed if f.carries)} finding(s) with `carries` and "
            f"counts blockers = {audit['blockers']} — the counts hold every carried "
            f"BLOCKER; a carried finding was lost, added or uncounted by hand"
        )
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
        tuple(audit["registration"].items()),
        audit.get("run_id"),
        audit.get("shown_sha"),
        (audit["blockers"], audit["warnings"], audit["notes"]),
        parsed,
        audit["protocol"],
        verdicts,
    )


_FIX_VERDICT_KEYS = {"record", "n", "decision_sha", "verdict", "why"}
_FIX_CHECK_KEYS = {"check", "check_present"}
_FIX_SUBJECT_KEY = {"subject"}


def _fix_verdicts(path: Path, rows: object) -> tuple[FixVerdict, ...]:
    """The `[[fix_verdict]]` tables, each held to its five fields and their
    types, together to `fix_verdict_problem`."""
    if not isinstance(rows, list):
        raise FindingsError(f"{path}: `fix_verdict` must be [[fix_verdict]] tables")
    out: list[FixVerdict] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or set(row) - _FIX_SUBJECT_KEY not in (
            _FIX_VERDICT_KEYS,
            _FIX_VERDICT_KEYS | _FIX_CHECK_KEYS,
        ):
            raise FindingsError(
                f"{path}: fix_verdict {i}: the fields are exactly "
                f"{', '.join(sorted(_FIX_VERDICT_KEYS))}, with a required "
                f"check also {', '.join(sorted(_FIX_CHECK_KEYS))}, and on a "
                f"settled undetermined finding also subject"
            )
        check, present = row.get("check", ""), row.get("check_present")
        if not isinstance(check, str) or not (
            present is None or isinstance(present, bool)
        ):
            raise FindingsError(
                f"{path}: fix_verdict {i}: check is a string, check_present true or false"
            )
        n = row["n"]
        if not isinstance(n, int) or isinstance(n, bool):
            raise FindingsError(f"{path}: fix_verdict {i}: n = {n!r} is not an integer")
        for key in ("record", "decision_sha", "verdict", "why"):
            if not isinstance(row[key], str):
                raise FindingsError(f"{path}: fix_verdict {i}: {key} is not a string")
        subject = row.get("subject", "")
        if not isinstance(subject, str):
            raise FindingsError(f"{path}: fix_verdict {i}: subject is not a string")
        out.append(
            FixVerdict(
                row["record"],
                n,
                row["decision_sha"],
                row["verdict"],
                row["why"],
                check,
                present,
                subject,
            )
        )
    problem = fix_verdict_problem(out)
    if problem:
        raise FindingsError(f"{path}: {problem}")
    return tuple(out)


#: the line that opens a `[[finding]]` table: what tells the tables whose
#: decision lines are rewritten (`[[claim]]` in a report review)
_FINDING_HEADER = protocol_block.array_header("finding")
#: a one-line `status = …`, `reason = …` or `effect = …` — the lines a
#: decision rewrites
_DECISION_LINE = re.compile(
    r"""^(\s*(status|reason|effect)\s*=\s*)(?:"(?:[^"\\]|\\.)*"|'[^']*')(\s*(?:#.*)?)$"""
)


#: the opening of a multi-line decision value (`reason = """…"""` or `'''…'''`)
_DECISION_OPEN = re.compile(r"""^(\s*(status|reason|effect)\s*=\s*)(\"\"\"|''')""")


def _closing(rest: str, delim: str) -> int | None:
    """Where the multi-line string opened by DELIM ends in REST (one line of
    it, without its line break): the index after its closing delimiter, or
    None when it does not close there. As TOML reads it: a basic string
    (`\"\"\"`) skips an escaped character, and up to two quotes of the
    delimiter's kind right before the closing three belong to the value."""
    quote, i = delim[0], 0
    while i < len(rest):
        if quote == '"' and rest[i] == "\\":
            i += 2
            continue
        if rest.startswith(delim, i):
            end = i + 3
            while end < len(rest) and rest[end] == quote and end - i < 5:
                end += 1
            return end
        i += 1
    return None


def _multi_line_end(
    lines: list[str], i: int, opened: re.Match[str]
) -> tuple[int, str] | None:
    """Where the multi-line decision value OPENED on lines[i] ends: the
    index of its last line and the text after its closing delimiter there
    (a comment); None when it never closes."""
    delim, j = opened.group(3), i
    rest = lines[i].splitlines()[0][opened.end() :]
    while (end := _closing(rest, delim)) is None:
        j += 1
        if j == len(lines):
            return None
        rest = lines[j].splitlines()[0] if lines[j].strip("\r\n") else ""
    return j, rest[end:]


def _decision_lines(
    lines: list[str],
    n: int,
    header: re.Pattern[str] = _FINDING_HEADER,
    *,
    history: bool,
) -> dict[str, tuple[int, int, str, str]] | None:
    """{"status": (first, end, head, tail), "reason": …, "effect": … when it
    stands} of the N-th table HEADER opens in LINES (`[[finding]]` unless
    said otherwise): the value spans
    lines[first:end], HEAD is the text before it (`reason = `), TAIL the
    text after it on its last line (a comment). A value is a one-line TOML
    string or a multi-line one; None when status or reason is missing or a
    multi-line value never closes. The table runs from its header to the
    next table header of any kind. With HISTORY the table's replaced
    decisions join them under `decision_history.KEY` when the array stands
    as labkit writes it — from its opening line to the line that closes it,
    HEAD and TAIL empty. HISTORY is true for a `[[finding]]`; a `[[claim]]`
    keeps no history, so there such lines are no decision lines."""
    seen, inside = 0, False
    at: dict[str, tuple[int, int, str, str]] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if header.match(line):
            seen += 1
            inside = seen == n
        elif protocol_block.TABLE_HEADER.match(line):
            inside = False
        elif (
            inside
            and history
            and decision_history.ARRAY_OPENING.match(line.splitlines()[0])
        ):
            end = decision_history.array_end(lines, i)
            if end is None:
                return None
            at[decision_history.KEY] = (i, end, "", "")
            i = end - 1
        elif inside and line.strip():
            first = line.splitlines()[0]
            one = _DECISION_LINE.match(first)
            opened = None if one else _DECISION_OPEN.match(first)
            if one:
                at[one.group(2)] = (i, i + 1, one.group(1), one.group(3))
            elif opened:
                closed = _multi_line_end(lines, i, opened)
                if closed is None:
                    return None
                at[opened.group(2)] = (i, closed[0] + 1, opened.group(1), closed[1])
                i = closed[0]
        i += 1
    return at if {"status", "reason"} <= set(at) else None


def without_decisions(
    text: str, header: re.Pattern[str] = _FINDING_HEADER, *, history: bool = True
) -> str | None:
    """TEXT, a record's, with every finding's decision lines removed —
    `status`, `reason` and `effect`, a multi-line value whole, and a
    finding's replaced decisions: what
    `write_decision` keeps byte for byte. Two versions of one record whose
    results are equal differ in decisions alone (`evidence.AreaEvidence.change_sentences`). None
    when a finding lacks the status and reason lines labkit-audit writes,
    or a multi-line value never closes. HEADER opens the tables decided:
    `[[finding]]`, or a report review's `[[claim]]`, which keeps no
    replaced decisions and is read with HISTORY false
    (`report_reviews.without_claim_decisions`). Pure."""
    lines = text.splitlines(keepends=True)
    count = sum(1 for line in lines if header.match(line))
    dropped: set[int] = set()
    for n in range(1, count + 1):
        at = _decision_lines(lines, n, header, history=history)
        if at is None:
            return None
        for first, end, _, _ in at.values():
            dropped.update(range(first, end))
    return "".join(line for i, line in enumerate(lines) if i not in dropped)


def findings_in(text: str) -> tuple[Finding, ...] | None:
    """The findings TEXT, a record's, holds, in its order — for a comparison
    of two versions of one record (`evidence.record_changed`); None when
    TEXT does not read as a record, which the record's own reader reports
    (`read`). Pure."""
    try:
        return _record_of(Path("record.toml"), text).findings
    except FindingsError:
        return None


def with_decision(
    text: str, n: int, status: str, reason: str, header: re.Pattern[str]
) -> str | None:
    """TEXT, a record's, with the `status` and `reason` lines of the N-th
    table HEADER opens set to STATUS and REASON — each value on one line
    (`toml_string`), a multi-line one replaced whole, every other byte
    kept. None when that table lacks one of the two lines or a multi-line
    value never closes. The rewrite of a decision without an effect: a
    report review's claim (`report_reviews.write_claim_decision`). Pure."""
    lines = text.splitlines(keepends=True)
    at = _decision_lines(lines, n, header, history=False)
    if at is None:
        return None
    values = {"status": status, "reason": reason}
    for key in sorted(values, key=lambda k: -at[k][0]):
        first, end, head, tail = at[key]
        last = lines[end - 1]
        ending = last[len(last.splitlines()[0]) :] or "\n"
        lines[first:end] = [head + _s(values[key]) + tail + ending]
    return "".join(lines)


def write_decision(
    path: Path,
    n: int,
    status: str,
    reason: str,
    effect: str = "",
    *,
    when: time.struct_time | None = None,
) -> Record:
    """Set finding N (1-based) of the record at PATH to STATUS with REASON —
    and, for a limit, EFFECT (`effect_ids`) — the decision the
    person gives, stored, never made: the side effect is the file. The
    lines are found by the record's structure (the N-th `[[finding]]`
    table), their values written by `toml_string`, every other byte kept;
    an effect line is added after the reason, or dropped when the decision
    no longer owes one. A decision this one replaces is kept: added to the
    finding's replaced decisions with the minute WHEN (local time now when
    None) — not the undecided start, and nothing when the decision is given
    again unchanged (`decision_history.after_replacing`). The result is
    read back and the file replaced whole
    (`files.write_atomic`) only when exactly that finding changed. Raises
    FindingsError — the file untouched — on a record that does not read, a
    number outside it, a status outside STATUSES, a reason owed and empty
    (for `limitation` and `false-positive`, and for `open` when it takes a
    decided status back),
    `limitation` on an implementation finding (`subject_refusal`), a BLOCKER
    limitation without its effect or an effect anywhere else, or a
    finding without the status and reason lines labkit-audit writes (a
    one-line or a multi-line TOML string each)."""
    from labkit.formats.files import write_atomic

    before = read(path)
    if not 1 <= n <= len(before.findings):
        raise FindingsError(
            f"{path}: no finding {n} — the record holds finding 1..{len(before.findings)}"
        )
    if status not in STATUSES:
        raise FindingsError(f"status {status!r} — one of {', '.join(STATUSES)}")
    if status in REASON_OWED and not reason.strip():
        raise FindingsError(f"status {status!r} owes a reason — why it is {status}")
    old = before.findings[n - 1]
    if status == OPEN and old.status in DECIDED and not reason.strip():
        raise FindingsError(
            f"{path}: finding {n}: taking the decision `{old.status}` back owes "
            f"a reason — why it no longer holds"
        )
    refused = subject_refusal(old, status)
    if refused is not None:
        raise FindingsError(f"{path}: finding {n}: {refused}")
    history = decision_history.after_replacing(
        old, status, reason.strip(), effect.strip(), date_minute(when)
    )
    # the check, the subject and the rule stay the auditor's: a decision never sets them
    decided = Finding(
        old.grade,
        old.text,
        status,
        reason.strip(),
        effect.strip(),
        old.check,
        old.check_note,
        old.carries,
        old.subject,
        old.rule,
        history,
    )
    _hold_effect(decided)
    # None when the decision replaced none: the history stays as it stands
    replaced = history[-1] if history != old.replaced_decisions else None
    text = _decided_text(path, n, decided, replaced)
    after = _record_of(path, text)
    expected = list(before.findings)
    expected[n - 1] = decided
    if list(after.findings) != expected or _head(after) != _head(before):
        raise FindingsError(f"{path}: the decision did not read back as written")
    write_atomic(path, text)
    return after


def _effect_problem(f: Finding) -> str | None:
    """Why F's effect cannot stand, or None: an effect on anything but a
    BLOCKER or WARNING decided `limitation`, or not in EFFECT_FORM. A limit
    without one reads (a record written by hand); report-check asks for
    it."""
    if not f.effect:
        return None
    if not f.effect_allowed:
        return (
            f"--not-assessable belongs to a BLOCKER or WARNING decided limitation, "
            f"not to a {f.status} {f.grade}"
        )
    try:
        effect_ids(f.effect)
    except ValueError as exc:
        return str(exc)
    return None


def _hold_effect(decided: Finding) -> None:
    """A BLOCKER decided `limitation` carries its effect, a WARNING may, nothing
    else does — or FindingsError: EffectFormError for an effect owed and
    missing or not in EFFECT_FORM."""
    if decided.effect_owed and not decided.effect:
        raise EffectFormError(
            "a BLOCKER decided limitation owes its effect on the verdicts — "
            f"{EFFECT_FORM}: does this run still judge the promise?"
        )
    problem = _effect_problem(decided)
    if problem:
        # where an effect is allowed, the only problem left is its form
        raise (EffectFormError if decided.effect_allowed else FindingsError)(problem)


def _decided_text(
    path: Path, n: int, decided: Finding, replaced: ReplacedDecision | None
) -> str:
    """The record's text with finding N's decision lines set to DECIDED —
    each value written on one line (`toml_string`), a multi-line one
    replaced whole — and REPLACED, the decision this one replaces (None when
    none), added as the last entry of the finding's replaced decisions: on
    a line before the array's closing one, or with a new array before the
    first decision line. Raises FindingsError when the finding's decision
    lines or its array do not stand as labkit-audit writes them."""
    # decoded, not read as text: a CRLF record keeps its line endings
    lines = path.read_bytes().decode("utf-8").splitlines(keepends=True)
    at = _decision_lines(lines, n, history=True)
    if at is None:
        raise FindingsError(
            f"{path}: finding {n} has no `status` and `reason` lines as labkit-audit "
            f"writes them — the record was changed by hand; restore it "
            f"(`{checkout_command(path.name)}` in its audits/) or audit again"
        )
    history_at = at.pop(decision_history.KEY, None)
    earlier = len(decided.replaced_decisions) - (0 if replaced is None else 1)
    # entries TOML read that no line of the array's form shows: an array on one line
    if earlier and history_at is None:
        raise FindingsError(
            f"{path}: finding {n}: its `{decision_history.KEY}` do not stand one "
            f"entry per line as labkit-audit writes them — the record was "
            f"changed by hand; restore it (`{checkout_command(path.name)}` in "
            f"its audits/) or audit again"
        )

    def ending(span: tuple[int, int, str, str]) -> str:
        last = lines[span[1] - 1]
        return last[len(last.splitlines()[0]) :] or "\n"

    def line(span: tuple[int, int, str, str], value: str) -> str:
        _, _, head, tail = span
        return head + _s(value) + tail + ending(span)

    edits = [
        (at["status"], [line(at["status"], decided.status)]),
        (
            at["reason"],
            [line(at["reason"], decided.reason)]
            + (
                [f"effect = {_s(decided.effect)}{ending(at['reason'])}"]
                if decided.effect and "effect" not in at
                else []
            ),
        ),
    ]
    if "effect" in at:
        edits.append(
            (
                at["effect"],
                [line(at["effect"], decided.effect)] if decided.effect else [],
            )
        )
    if replaced is not None and history_at is not None:
        closing = history_at[1] - 1
        entry = decision_history.entry_line(replaced) + ending(history_at)
        edits.append(((closing, closing, "", ""), [entry]))
    if replaced is not None and history_at is None:
        # with the first decision line's edit: an edit of its own at the
        # same line would be applied in no certain order
        first_edit = min(edits, key=lambda e: e[0][0])
        first_edit[1][:0] = [
            text + ending(first_edit[0])
            for text in decision_history.array_lines((replaced,))
        ]
    for (first, end, _, _), new in sorted(edits, key=lambda e: -e[0][0]):
        lines[first:end] = new
    return "".join(lines)


def _head(r: Record) -> tuple:
    """What a decision must leave as it was besides the findings."""
    return (
        r.date, r.mode, r.model, r.scope_sha, r.block_sha, r.registration, r.run_id,
        r.shown_sha, r.verdict,
    )  # fmt: skip


@dataclass(frozen=True)
class RecordStatus:
    """Readable records and explicit errors; a broken file hides no other finding."""

    records: list[Record]
    errors: list[str]


def record_status(area: Path, *, staged: bool = False) -> RecordStatus:
    """Read every findings record of AREA in the requested state.

    Return readable records and errors separately for recovery guidance.
    `area_records` is the strict view, which refuses any error; the
    stop/commit, `--findings` and the handover read this one through
    `evidence.AreaEvidence`, the errors kept beside. At the index,
    an unstaged record is an error too; decisions are never read from the
    tree in place of the index. No writes or console output.
    """
    folder = area / DIR
    root = git_root(area) if staged else None
    errors: list[str] = []
    if staged:
        held = None if root is None else files_at(root, folder, INDEX_REV)
        if root is None or held is None:
            return RecordStatus([], [f"{folder}: no git repository holds its index"])
        paths = [folder / rel for rel in held if "/" not in rel and is_record_name(rel)]
        names = {p.name for p in paths}
        left = sorted(
            p
            for p in folder.glob("*.toml")
            if is_record_name(p.name) and p.name not in names
        )
        if left:
            errors.append(
                f"{', '.join(shown(p, Path.cwd()) for p in left)}: in the tree, not in the "
                f"index — the commit would leave the audit record behind; stage it "
                f"(`{stage_command(*left)}`)"
                f" — a record a later change made outdated is staged too, its "
                f"BLOCKERs decided (`fixed`, naming the change, where it repaired "
                f"them), never deleted"
            )
    else:
        paths = [p for p in folder.glob("*.toml") if is_record_name(p.name)]
    records: list[Record] = []
    order: dict[Path, tuple[str, int, str]] = {}
    for path in sorted(paths):
        order[path], problem = _recovery_record_order(path)
        if problem:
            errors.append(problem)
        try:
            if staged:
                assert root is not None
                text = text_at(root, path, INDEX_REV)
                if text is None:
                    raise FindingsError(
                        f"{path}: listed in git's index, but not readable there"
                    )
                record = _record_of(path, text)
            else:
                record = read(path)
        except (FindingsError, UnicodeError) as exc:
            errors.append(str(exc) + (" (as git's index holds it)" if staged else ""))
        else:
            records.append(record)
    return RecordStatus(sorted(records, key=lambda r: order[r.path]), errors)


def _recovery_record_order(path: Path) -> tuple[tuple[str, int, str], str | None]:
    """Order a record while retaining a naming error separately from its
    findings. A record whose name gives no time sorts first, so the newest
    `--findings` names is the one `--decide` takes as the newest."""
    try:
        return written_order(path), None
    except FindingsError as exc:
        return ("0000", 0, path.name), str(exc)


def area_records(area: Path) -> list[Record]:
    """Every findings record of AREA in the working tree, oldest first.

    Raise FindingsError on a malformed or unreadable record. The index's
    records and the readers that keep the errors beside the readable
    records use `record_status` (`evidence.AreaEvidence`).
    """
    status = record_status(area)
    if status.errors:
        raise FindingsError(status.errors[0])
    return status.records


def repo_records(experiments: Path) -> list[tuple[Path, Record]]:
    """(area, record) for every findings file under EXPERIMENTS, by area then date."""
    out = []
    for folder in sorted(experiments.glob(f"*/{DIR}")):
        if folder.is_dir():
            out += [(folder.parent, r) for r in area_records(folder.parent)]
    return out


def new_class_findings(
    records: Iterable[tuple[Path, Record]],
) -> list[tuple[Path, Record, int, Finding]]:
    """Every finding of RECORDS (`repo_records`: area and record) whose rule
    the auditor gave as NEW_CLASS, with its area and number — what the
    author reviews for a gap in the standard. A new class becomes a rule
    only by a decision with its grounds, never by this list."""
    return [
        (area, record, n, f)
        for area, record in records
        for n, f in enumerate(record.findings, 1)
        if f.rule == NEW_CLASS_RULE
    ]


def open_elsewhere(area: Path, experiments: Path) -> list[tuple[Path, Record, Finding]]:
    """Open findings in other areas of the repo — a finding left there as
    "its own task" may be this area's."""
    return [
        (other, rec, f)
        for other, rec in repo_records(experiments)
        if other.resolve() != area.resolve()
        for f in rec.open
    ]


def record_way(area: Path, protocol: Path | None = None) -> str:
    """The way out of an audit record in AREA that does not read: restore it
    as labkit-audit wrote it or audit again, and the recovery entry
    (`--findings`) that names what stands and the handover — never a
    record rewritten by hand."""
    return (
        f"restore the record as labkit-audit wrote it "
        f"(`{checkout_command('<record>')}` where git holds it) or audit again; "
        f"`{audit_command(area, '--findings', protocol=protocol)}` names what "
        "stands and the handover"
    )
