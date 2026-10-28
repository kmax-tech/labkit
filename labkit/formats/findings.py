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
    registration = { "kind" = "compute", "Question / hypothesis" = "9a8b7c6d5e4f" }
                                 # what it judged (protocol_check.registration_stamp)
    # run_id = "2026-10-12T15-01-07_a1b2"  — mode analysis only: the run whose rows it read
    blockers = 1
    warnings = 2
    notes = 1

    [[finding]]
    grade = "BLOCKER"
    text = "BLOCKER · scripts/01_measure.py:42 · … · LAB-038 What the prompt demands · …"
    status = "open"      # open | fixed | accepted | deferred | dismissed
    reason = ""          # owed for accepted, deferred and dismissed
    # effect = "C1 not assessable"  — an accepted BLOCKER or WARNING: see EFFECT

The person decides each finding with `labkit-audit AREA --decide N STATUS
REASON`, which validates the decision the person typed and stores it
(`write_decision`) — the one supported way to write a decision; a record
changed by hand is not one labkit wrote, whatever its fields say, and a
check of the file cannot tell who wrote them. labkit never decides.

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

That file is what `LABKIT_UNFROZEN=1` acknowledges at `high`:
an audit that could not run, not one nobody ran (`audit_unavailable`, held
by runlog's freeze gate since 0.99.0). labkit writes it, with the error the
backend gave; a usage error (an unknown alias, an area that cannot be
stamped) is not an unavailable audit and leaves none. A record of findings
and a failed attempt never share a name; `area_records` reads the records
only.
A record binds what the auditor read: the code (`scope_sha`), the promise
block (`block_sha`), the registration it judged — the kind and the
question with the other fields the kind owes (`registration`), not the
report fields written after the run — and, in mode analysis, the
answering run (`run_id`).
A full run at `high` needs the preflight record the head names
(`preflight_audit = "<minute>-preflight.toml"`) to be one of the code and
the promises as they are now, every finding decided (`audit_record_gap`,
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

An accepted finding is a fault the person keeps: the number may still be
reported, read within the fault, but a fault in the instrument can leave
a promise unjudged by the run. The decision says which (`effect`):
`stands` — the verdicts hold, read within the limit — or `C1 not
assessable` (ids comma-separated) — this run does not judge them. How
severe a finding is and what the result still allows are two questions:
an accepted BLOCKER owes its effect, an accepted WARNING may name one
(a cue that limits how the number reads), and either way a named effect
reaches the result. Which effect follows from what the promise's sentence
claims — a threshold on these items, or a capability — not from the
grade. The protocol carries each as a `Limit (audit <record> #N)` line
and a note in Recorded results (`protocol-fill --from-run` writes both from the
record), and report-check holds them to it (`limit_line`, `answer_note`). Whether the
named limit is enough stays the audit's question, not this check's
(judge probe, 2026-10-21: a prompt broader than the gold, accepted, and
"C1 not met" reported with the limit in the record only).

Reading is loud: an unknown status, a decided status without a reason, a
file without its `[audit]` table raise FindingsError naming the file and
the field — a findings file nobody can read is not "no findings".
"""

from __future__ import annotations

import re
import shlex
import time
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import promises
from labkit.formats.protocol_block import toml_string as _s
from labkit.formats.protocol_check import registration_drift, registration_stamp
from labkit.formats.repo import (
    INDEX_REV,
    audit_command,
    decide_command,
    files_at,
    git_root,
    shown,
    text_at,
)
from labkit.formats.runs import as_stored, date_minute, name_minute
from labkit.formats.scope_sha import area_stamp, digest, validation_note
from labkit.formats.standard_contract import ANALYSIS_AUDIT, PREFLIGHT_AUDIT

DIR = "audits"
#: the suffix of a failed attempt's file, never of a record of findings
FAILED_SUFFIX = "-failed.toml"
#: the name of a decision review (`reviews`), written beside the records
#: and never read as one: `<minute>-review[-<n>].toml` (`create_file`
#: numbers a second file of the minute before the suffix)
REVIEW_NAME = re.compile(r"-review(?:-\d+)?\.toml$")
#: the low lane's `labkit-audit` gives its one call by default, and the least a
#: failed attempt must have been given to count as one (`audit_unavailable`):
#: an attempt given less time than the audit takes is not an attempt
ATTEMPT_TIMEOUT_S = 900
#: why an audit attempt failed: the backend gave no answer (`unavailable`),
#: or an answer the requested model did not write whole (`unproven`,
#: `llm_backends.UnprovenAnswer` — a safety stop, another model). An
#: unproven attempt ends the auditing of that state with that model
#: (`stopped_attempt`): each further try costs the same and was stopped
#: again in the fit probes
FAILED_CAUSES = ("unavailable", "unproven")
STATUSES = ("open", "fixed", "accepted", "deferred", "dismissed")
REASON_OWED = ("accepted", "deferred", "dismissed")
#: the statuses under which a finding leaves the result's limits without
#: a Limit line — the fault removed, put off, or not a fault. After a
#: review did not uphold a decision on the finding, none of them settles
#: it alone (`reviews.once_not_upheld`, `report_check.review_findings`)
CLOSING = ("fixed", "deferred", "dismissed")
#: every status but `open`: what deciding a finding sets
DECIDED = tuple(s for s in STATUSES if s != "open")
#: the decided statuses as a step names them: "fixed / accepted / deferred / dismissed"
DECIDED_LIST = " / ".join(DECIDED)
#: a carried finding (`carries`: a follow-up did not find its fault gone)
#: closed with one of these owes a decision review before the number leaves
CARRIED_CLOSING = ("dismissed", "deferred")
#: an accepted BLOCKER's effect on the verdicts: they stand with the limit,
#: or the run judges the named promises not at all
EFFECT_STANDS = "stands"
EFFECT_GRADES = ("BLOCKER", "WARNING")
_EFFECT_NOT = re.compile(r"^(\S+(?:\s*,\s*\S+)*)\s+not assessable$")
EFFECT_FORM = '`stands` or `<ID>[, <ID>] not assessable` (e.g. "C1 not assessable")'
GRADES = ("BLOCKER", "WARNING", "NOTE")
MODES = (PREFLIGHT_AUDIT, ANALYSIS_AUDIT)
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
    effect: str = ""  # accepted: EFFECT_STANDS or "<ids> not assessable"
    # the diagnostic the auditor requires to show a repair: a metrics.json
    # key, set from the finding line when the record is written, never by
    # a decision ("" when none is required)
    check: str = ""
    # what the check's value must show, as the auditor wrote it after the
    # key ("" when it wrote none); bound with the check
    check_note: str = ""
    # a carried finding: the earlier finding it continues, `<record file>#<n>`
    # — written by labkit-audit when a follow-up did not find it resolved,
    # never by a person ("" for the auditor's own findings); its origin is
    # found by following the chain (`followup.origin_of`)
    carries: str = ""

    @property
    def effect_owed(self) -> bool:
        """An accepted BLOCKER owes the effect it has on the verdicts."""
        return self.grade == "BLOCKER" and self.status == "accepted"

    @property
    def effect_allowed(self) -> bool:
        """An accepted BLOCKER or WARNING may name an effect; nothing else."""
        return self.grade in EFFECT_GRADES and self.status == "accepted"


#: an analysis audit's verdict on an earlier decided BLOCKER (fixed,
#: accepted, deferred or dismissed):
#: the fault is gone in the files and rows it was shown, still there, or
#: not to be judged from them (no diagnostic shown that could tell)
FIX_VERDICTS = ("resolved", "unresolved", "not_assessable")


@dataclass(frozen=True)
class FixVerdict:
    """An analysis audit's verdict on one earlier decided BLOCKER: the
    record and number it stands in, the decision as it was shown
    (`decision_digest`), the verdict and its why. Bound to that decision:
    a changed status or reason is another decision, which this verdict
    says nothing about."""

    record: str  # the earlier record's file name
    n: int  # the finding's number in it, as `--decide` takes it
    decision_sha: str
    verdict: str  # one of FIX_VERDICTS
    why: str
    # the check the finding required ("" for none) and whether its key stood
    # in the metrics.json the prompt showed — computed by labkit from that
    # snapshot, never by the model; None when no check was required. A
    # `resolved` with check_present False is kept as written: the verdict
    # is the measure, the missing key the gap.
    check: str = ""
    check_present: bool | None = None

    @property
    def ref(self) -> str:
        """`<record>#<n>` — how the auditor names the finding."""
        return f"{self.record}#{self.n}"


#: a finding line's closing field naming the diagnostic a repair must show:
#: `· check: <metrics key>` — the auditor's, fixed when the finding is written
CHECK_FIELD = re.compile(r"·\s*check\s*:")
#: the whole field: the key, then nothing, or a note in one of two forms
#: running to the end of the line — `(<note>)` or `— <note>`
_CHECK = re.compile(
    r"·\s*check\s*:\s*`?(?P<key>[a-z][a-z0-9_]*|file:[^\s`()]+)`?"
    r"(?:\s*\((?P<paren>.*\S.*)\)|\s+[—–]\s+(?P<dash>\S.*))?\s*$"
)
CHECK_KEY = re.compile(r"^(?:[a-z][a-z0-9_]*|file:[^\s`()]+)$")
#: a check that asks for a file's content, not a computed value: the run
#: declares the file as a dependency, so the follow-up is shown it
FILE_CHECK = "file:"
#: how a carried finding names the one it continues: `<record file>#<n>`
CARRIES_REF = re.compile(r"^[^\s#/]+\.toml#[1-9]\d*$")
CHECK_FORM = (
    "a closing `· check: <metrics key>` (lowercase snake_case) or `· check: "
    "file:<repository path>`, optionally followed by ` (<what it must show>)` "
    "or ` — <what it must show>` to the end of the line"
)


def check_of(text: str) -> tuple[str, str]:
    """(key, note) of the diagnostic a finding line requires for its repair
    — its closing `· check: <key>` field, the note what the auditor wrote
    after the key in one of the two forms of CHECK_FORM — or ("", "") when
    it requires none. Only the key is machine-read; the note is kept whole.
    Raises ValueError on a field that does not read and on two check
    fields in one line: a requirement half-read, or one of two, would be
    one nobody can be held to (second fixed-followup pilot: six records
    lost to `check: <key> (<note>)` while only the bare key was read)."""
    if not CHECK_FIELD.search(text):
        return "", ""
    if len(CHECK_FIELD.findall(text)) > 1:
        raise ValueError(
            f"two check fields in one finding: {text.strip()[-160:]!r} — one "
            f"finding requires one diagnostic; {CHECK_FORM}"
        )
    m = _CHECK.search(text.rstrip())
    if m is None:
        raise ValueError(
            f"a check field that does not read: {text.strip()[-160:]!r} — the form "
            f"is {CHECK_FORM}"
        )
    return m["key"], (m["paren"] or m["dash"] or "").strip()


def check_order(check: str, note: str = "") -> str:
    """What a finding's required CHECK asks of the measuring code — the one
    wording of the decision list, the follow-up's holds and AGENTS.md: the
    script computes the value while it measures and writes it to
    metrics.json under CHECK; NOTE, what it must show. A `file:<path>`
    check asks for the file declared as the run's dependency instead. A key alone shows
    nothing: the follow-up judges the computed value. In the repair case
    (2026-10-28) the check went unwritten, and every follow-up judged the
    repair not assessable."""
    shows = f" ({note})" if note else ""
    if check.startswith(FILE_CHECK):
        # a file's content, not a computed value: shown once the run declares
        # it (the repair case's model.json, which no audit piece showed)
        path = check.removeprefix(FILE_CHECK)
        return (
            f"declare `{path}`{shows} among the files the run reads as a dependency "
            f"— in the estimator skeleton `PREDICTOR_FILES`, else runlog's `data=` "
            f"with `provenance.BinaryInput` — so that the run records its digest "
            f"and the analysis audit is shown its content"
        )
    return (
        f"extend the measuring script so that it computes `{check}`{shows} from "
        f"what the run measures and writes the computed value to metrics.json "
        f"under that key — a key written as a constant shows nothing"
    )


def decision_digest(f: Finding) -> str:
    """The digest of F as decided — grade, text, status, reason, effect, and
    the required check and its note and the finding a carried one continues
    when there are — which a review and a fix verdict
    bind to (`reviews.Decision.decision_sha`, `FixVerdict.decision_sha`): a
    changed reason, effect or check is another decision, and a verdict on
    the old one says nothing about it. A finding without a check has the
    digest it had before checks existed."""
    fields = [f.grade, f.text, f.status, f.reason, f.effect]
    if f.check:
        fields += [f.check] + ([f.check_note] if f.check_note else [])
    if f.carries:
        fields += ["carries", f.carries]
    return digest(as_stored(fields).encode("utf-8"))


def effect_ids(effect: str) -> tuple[str, ...]:
    """The promise ids EFFECT leaves not assessable, in its order — () for
    `stands`. Raises ValueError on any other text or an id that is no
    promise id (`promises.is_block_id`)."""
    if effect == EFFECT_STANDS:
        return ()
    m = _EFFECT_NOT.match(effect.strip())
    ids = tuple(i.strip() for i in m.group(1).split(",")) if m else ()
    if not ids or not all(promises.is_block_id(i) for i in ids):
        raise ValueError(f"effect {effect!r} — {EFFECT_FORM}")
    return ids


def effect_sentence(effect: str) -> str:
    """EFFECT as the protocol's Limit line opens with it."""
    ids = effect_ids(effect)
    if not ids:
        return "the verdicts stand, read within this limit"
    return f"{', '.join(ids)} not assessable with this run"


@dataclass(frozen=True)
class AuditedState:
    """The state of an area an audit saw and its record binds: the code
    (SCOPE_SHA, `scope_sha.area_stamp`), the promise block (BLOCK_SHA,
    `promises.block_stamp`), the REGISTRATION it judged
    (`protocol_check.registration_stamp`, compared as a mapping) and, mode
    analysis, the RUN_ID it read (NO_RUN: none) and the SHOWN_SHA of what
    it was shown of that run; both None for preflight. One type for the
    prompt that binds it (`audit.bound_prompt`), the record (`Record.state`)
    and every match of the two (`covering_records`) — the audit matched a
    record field by field beside `covering_records` (audit 2026-10-27,
    third, plan 2)."""

    scope_sha: str
    block_sha: str
    registration: Mapping[str, str]
    run_id: str | None = None
    shown_sha: str | None = None

    def __eq__(self, other: object) -> bool:
        # the registration as a mapping: a record keeps it in the order written
        if not isinstance(other, AuditedState):
            return NotImplemented
        return self.bound == other.bound and dict(self.registration) == dict(
            other.registration
        )

    def __hash__(self) -> int:
        # what __eq__ compares, the registration as sorted pairs
        return hash((self.bound, tuple(sorted(dict(self.registration).items()))))

    @property
    def bound(self) -> tuple[str, str, str | None, str | None]:
        """(code, promises, run, shown) — the state, its registration aside."""
        return (self.scope_sha, self.block_sha, self.run_id, self.shown_sha)

    def words(self) -> str:
        """What the state binds, in words: `code <sha>, promises <block>[,
        run <id>, shown <sha>]`."""
        return (
            f"code {self.scope_sha}, promises {self.block_sha}"
            + (f", run {self.run_id}" if self.run_id is not None else "")
            + (f", shown {self.shown_sha}" if self.shown_sha is not None else "")
        )


@dataclass(frozen=True)
class Record:
    """One audit's findings file."""

    path: Path
    date: str
    mode: str
    model: str
    scope_sha: str  # the code the auditor read
    block_sha: str  # the promise block it read (promises.NO_BLOCK: none declared)
    # the registration it judged: the kind and a digest per owed field
    # (`protocol_check.registration_stamp`), in the order written
    registration: tuple[tuple[str, str], ...]
    run_id: (
        str | None
    )  # mode analysis: the run whose rows it read (NO_RUN: none); preflight: None
    # mode analysis: the digest of what the prompt showed of that run (its
    # rows' excerpts and metrics.json, `audit_binding.run_shown`); preflight: None
    shown_sha: str | None
    verdict: tuple[int, int, int]
    findings: tuple[Finding, ...]
    # mode analysis: its verdicts on earlier decided BLOCKERs, one per
    # finding at most; a finding shown without one is unchecked
    fix_verdicts: tuple[FixVerdict, ...] = ()

    @property
    def state(self) -> AuditedState:
        """The state this record binds (`AuditedState`)."""
        return AuditedState(
            self.scope_sha,
            self.block_sha,
            dict(self.registration),
            self.run_id,
            self.shown_sha,
        )

    @property
    def open(self) -> list[Finding]:
        """The findings nobody has decided yet."""
        return [f for f in self.findings if f.status == "open"]

    @property
    def deferred(self) -> list[Finding]:
        """The findings put off as somebody's later task."""
        return [f for f in self.findings if f.status == "deferred"]

    def limits(self) -> list[tuple[int, Finding]]:
        """(number, finding) of every finding that is a limit of the result:
        an accepted BLOCKER (its effect owed) and an accepted WARNING that
        names an effect — numbered as `--decide` takes them."""
        return [
            (n, f)
            for n, f in enumerate(self.findings, 1)
            if f.effect_owed or (f.effect_allowed and f.effect)
        ]


#: how every Limit line's label opens
LIMIT_PREFIX = "Limit (audit "


@dataclass(frozen=True)
class OpenFinding:
    """One finding still `open`, with the record it stands in."""

    record: Record
    finding: Finding

    @property
    def number(self) -> int:
        """The finding's number in its record, as `--decide` takes it
        (`number_of`)."""
        return number_of(self.record, self.finding)

    @property
    def grade(self) -> str:
        """The finding's grade — BLOCKER, WARNING or NOTE."""
        return self.finding.grade

    @property
    def line(self) -> str:
        """`<record file>: <text>` — how every gate names it."""
        return f"{self.record.path.name}: {self.finding.text}"


def number_of(record: Record, finding: Finding) -> int:
    """FINDING's 1-based number in RECORD, found by identity: two equal
    findings in one record took the first's number by `list.index`, and a
    printed `--decide` named the wrong one (audit 2026-10-27, third, K5).
    Raises ValueError when FINDING is not one of RECORD's."""
    for n, f in enumerate(record.findings, 1):
        if f is finding:
            return n
    raise ValueError(f"{record.path.name}: the finding is not one of its own")


def open_findings(
    records: Iterable[Record], *, mode: str | None = None
) -> list[OpenFinding]:
    """Every finding still `open` in RECORDS, in record order — of MODE's
    records only when MODE is given. The one home of the question "is an
    audit finding still undecided" (audit 2026-10-23, C1: four gates
    walked the records themselves, each grading differently, and nothing
    said whether that was meant). What a gate makes of an undecided
    finding is that gate's rule; the rules stand side by side here:

        gate                         records            an undecided finding is
        preflight, unfrozen          every mode         a WARNING — the decision is owed at the freeze, not before
        preflight, frozen            every mode         a BLOCKER — frozen = true owes every decision
                                                        (LAB-015 Preflight audit before freezing)
        runlog start, full run       preflight only     a BLOCKER refuses the run; a WARNING or NOTE is told
                                                        only with the run acknowledged (LABKIT_UNFROZEN=1),
                                                        a clean start says nothing of it — the run rests on
                                                        the preflight audit; an analysis record judges a
                                                        run, and finalize holds it
        the record the head names    that record only   any grade is a gap (`audit_record_gap`): the freeze
        (runlog, preflight,                             refuses, preflight warns unfrozen and blocks frozen,
        protocol-check)                                 protocol-check reports — the named record stands
                                                        for the frozen state, decided whole
        finalize                     every mode         its grade: BLOCKER blocks, WARNING warns, NOTE is told
        claude-hook stop / undecided every mode, the    a BLOCKER only — the hook says what the commit would be
                                     areas the session  refused for and nags for nothing less (`open_blockers`)
                                     touched
        protocol-fill --handover     every mode         a BLOCKER refuses the handover: decided first, `deferred`
                                                        when it stays unresolved (`open_blockers`)
        labkit-audit --findings      every mode         a BLOCKER selects its record for the listing and prints
                                                        its `deferred` command (`open_blockers`)
        report-check, replacement    the predecessor's  a BLOCKER holds the replacement until it is decided
                                     area               (`open_blockers`)
        audit_coverage (report-check) the covering record  any grade: the record is not decided

    The differences are intended. A change to one row is a change to that
    gate's rule: say so in its docstring and in this table. `audit_record_gap`
    reads `Record.open` of the one named record itself; every walk over
    records goes through here.
    """
    return [
        OpenFinding(r, f)
        for r in records
        if mode is None or r.mode == mode
        for f in r.open
    ]


def open_blockers(records: Iterable[Record]) -> list[OpenFinding]:
    """The open findings of RECORDS graded BLOCKER (`open_findings`): what
    the stop and the commit hold, what a handover owes decided first, what
    `labkit-audit --findings` leads with."""
    return [u for u in open_findings(records) if u.grade == "BLOCKER"]


def limit_label(record: Record, n: int) -> str:
    """The protocol label that carries finding N of RECORD as a limit."""
    return f"{LIMIT_PREFIX}{record.path.stem} #{n})"


def limit_line(finding: Finding) -> str:
    """The value of a Limit line: FINDING's effect, then the person's reason
    (`limit_label` is the label beside it)."""
    reason = " ".join(finding.reason.split())
    return f"{effect_sentence(finding.effect)} — {reason}"


def answer_note(limits: list[tuple[str, str]]) -> str:
    """What the Recorded results line says of LIMITS, (label, effect) each:
    one note counting them; the Limit lines below carry each one whole, and
    which promise one leaves not assessable stands in the line's verdicts
    (`result_render.verdicts`). Empty for no limits. One note per limit
    grew the line to three "read within" tails (sandbox, 2026-10-21)."""
    if not limits:
        return ""
    n = len(limits)
    return f"; subject to {n} recorded limitation{'s' if n > 1 else ''} (the Limit lines below)"


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


def count_problem(name: str, value: object) -> str | None:
    """Why VALUE is no count of NAME (blockers, warnings, notes), or None: a
    count is a non-negative integer. One rule for the writer and the reader
    — `blockers = -1` was written, read and passed the coverage check
    (review 2026-10-20)."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return f"{name} = {value!r} is not a non-negative integer"
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


def carried_and_closed(f: Finding) -> bool:
    """Is F a carried finding (`carries`: a follow-up did not find its fault
    gone) closed `dismissed` or `deferred` (CARRIED_CLOSING)? Such a
    decision owes a decision review before the number leaves — the one rule
    the gate (`report_check.followup_findings`) and the review
    (`decision_review.reviewable`) both read."""
    return bool(f.carries) and f.status in CARRIED_CLOSING


#: why a record changed by hand may not parse — told in the refusal of a
#: file that does not (an unescaped quote in a reason makes it unreadable)
REASON_FORM = (
    'a reason is a TOML string: "double quotes" escape a quote as \\" and a '
    "backslash as \\\\; 'single quotes' take one line of text without a ' "
    "or a control character"
)


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
    (`protocol_check.registration_stamp`), RUN_ID the run whose rows it read and SHOWN_SHA
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
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} — one of {', '.join(MODES)}")
    if (mode == ANALYSIS_AUDIT) != (run_id is not None):
        raise ValueError(
            f"mode {mode!r} with run_id {run_id!r}: an analysis audit names the "
            f"run it read (NO_RUN for none), a preflight audit names none"
        )
    if (mode == ANALYSIS_AUDIT) != (shown_sha is not None):
        raise ValueError(
            f"mode {mode!r} with shown_sha {shown_sha!r}: an analysis audit names "
            f"what it was shown of the run, a preflight audit is shown none"
        )
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
        "`labkit-audit <area> --decide N STATUS REASON`; a record changed by hand is not one labkit wrote",
        "[audit]",
        f"date = {_s(date_minute(when))}",
        f"mode = {_s(mode)}",
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
        lines += [
            "",
            "[[finding]]",
            f"grade = {_s(grade)}",
            f"text = {_s(text)}",
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
        if f.grade != "BLOCKER" or not CARRIES_REF.match(f.carries):
            raise ValueError(
                f"a carried finding is a BLOCKER naming `<record>#<n>`: "
                f"{f.grade} carries {f.carries!r}"
            )
        lines += [
            "",
            "[[finding]]",
            f"grade = {_s(f.grade)}",
            f"text = {_s(f.text)}",
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
        ]
    return lines


def fix_verdict_problem(verdicts: Iterable[FixVerdict]) -> str | None:
    """Why VERDICTS cannot stand in one record, or None: a verdict outside
    FIX_VERDICTS, an empty why, a number below 1, or two verdicts on one
    finding — which of two would count is no question a gate should answer.
    One rule for the writer and the reader."""
    seen: set[str] = set()
    for v in verdicts:
        if v.verdict not in FIX_VERDICTS:
            return f"fix verdict on {v.ref}: {v.verdict!r} — one of {', '.join(FIX_VERDICTS)}"
        if not v.why.strip():
            return f"fix verdict on {v.ref}: no why"
        if v.n < 1:
            return f"fix verdict on {v.ref}: finding numbers start at 1"
        if v.ref in seen:
            return f"fix verdict on {v.ref}: a second verdict on the same finding"
        if bool(v.check) != (v.check_present is not None):
            return (
                f"fix verdict on {v.ref}: check {v.check!r} with check_present "
                f"{v.check_present!r} — a required check names whether its key was shown"
            )
        seen.add(v.ref)
    return None


def create_file(folder: Path, name: str, suffix: str, text: str) -> Path:
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
        problem = count_problem(key, audit.get(key))
        if problem:
            raise FindingsError(f"{path}: [audit] {problem}")
    if audit["mode"] not in MODES:
        raise FindingsError(
            f"{path}: [audit] mode {audit['mode']!r} — one of {', '.join(MODES)}"
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
    check, note = _check_fields(path, i, row)
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
    )
    problem = _effect_problem(found)
    if problem:
        raise FindingsError(f"{path}: finding {i}: {problem}")
    return found


def _check_fields(path: Path, i: int, row: dict) -> tuple[str, str]:
    """(check, check_note) of the i-th `[[finding]]` table: a metrics key or
    "", and a note only beside a check. Raises FindingsError otherwise
    (`carries` is read beside it, `_carries_field`)."""
    check = row.get("check", "")
    if not isinstance(check, str) or (check and not CHECK_KEY.match(check)):
        raise FindingsError(
            f"{path}: finding {i}: check {check!r} is no metrics key (lowercase "
            f"snake_case) and no `file:<path>`"
        )
    note = row.get("check_note", "")
    if not isinstance(note, str) or (note and not check):
        raise FindingsError(
            f"{path}: finding {i}: check_note {note!r} — a string, and only with a check"
        )
    return check, note


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
        verdicts,
    )


_FIX_VERDICT_KEYS = {"record", "n", "decision_sha", "verdict", "why"}
_FIX_CHECK_KEYS = {"check", "check_present"}


def _fix_verdicts(path: Path, rows: object) -> tuple[FixVerdict, ...]:
    """The `[[fix_verdict]]` tables, each held to its five fields and their
    types, together to `fix_verdict_problem`."""
    if not isinstance(rows, list):
        raise FindingsError(f"{path}: `fix_verdict` must be [[fix_verdict]] tables")
    out: list[FixVerdict] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or set(row) not in (
            _FIX_VERDICT_KEYS,
            _FIX_VERDICT_KEYS | _FIX_CHECK_KEYS,
        ):
            raise FindingsError(
                f"{path}: fix_verdict {i}: the fields are exactly "
                f"{', '.join(sorted(_FIX_VERDICT_KEYS))}, and with a required "
                f"check also {', '.join(sorted(_FIX_CHECK_KEYS))}"
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
        out.append(
            FixVerdict(
                row["record"],
                n,
                row["decision_sha"],
                row["verdict"],
                row["why"],
                check,
                present,
            )
        )
    problem = fix_verdict_problem(out)
    if problem:
        raise FindingsError(f"{path}: {problem}")
    return tuple(out)


_FINDING_HEADER = re.compile(r"^\s*\[\[\s*finding\s*\]\]\s*(?:#.*)?$")
_TABLE_HEADER = re.compile(r"^\s*\[")
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


def _decision_lines(
    lines: list[str], n: int
) -> dict[str, tuple[int, int, str, str]] | None:
    """{"status": (first, end, head, tail), "reason": …, "effect": … when it
    stands} of the N-th `[[finding]]` table in LINES: the value spans
    lines[first:end], HEAD is the text before it (`reason = `), TAIL the
    text after it on its last line (a comment). A value is a one-line TOML
    string or a multi-line one; None when status or reason is missing or a
    multi-line value never closes. The table runs from its header to the
    next table header of any kind."""
    seen, inside = 0, False
    at: dict[str, tuple[int, int, str, str]] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if _FINDING_HEADER.match(line):
            seen += 1
            inside = seen == n
        elif _TABLE_HEADER.match(line):
            inside = False
        elif inside and line.strip():
            first = line.splitlines()[0]
            one = _DECISION_LINE.match(first)
            opened = None if one else _DECISION_OPEN.match(first)
            if one:
                at[one.group(2)] = (i, i + 1, one.group(1), one.group(3))
            elif opened:
                delim, j = opened.group(3), i
                rest = first[opened.end() :]
                while (end := _closing(rest, delim)) is None:
                    j += 1
                    if j == len(lines):
                        return None
                    rest = lines[j].splitlines()[0] if lines[j].strip("\r\n") else ""
                at[opened.group(2)] = (i, j + 1, opened.group(1), rest[end:])
                i = j
        i += 1
    return at if {"status", "reason"} <= set(at) else None


def without_decisions(text: str) -> str | None:
    """TEXT, a record's, with every finding's decision lines removed —
    `status`, `reason` and `effect`, a multi-line value whole: what
    `write_decision` keeps byte for byte. Two versions of one record whose
    results are equal differ in decisions alone (`evidence.changes`). None
    when a finding lacks the status and reason lines labkit-audit writes,
    or a multi-line value never closes. Pure."""
    lines = text.splitlines(keepends=True)
    count = sum(1 for line in lines if _FINDING_HEADER.match(line))
    dropped: set[int] = set()
    for n in range(1, count + 1):
        at = _decision_lines(lines, n)
        if at is None:
            return None
        for first, end, _, _ in at.values():
            dropped.update(range(first, end))
    return "".join(line for i, line in enumerate(lines) if i not in dropped)


def write_decision(
    path: Path, n: int, status: str, reason: str, effect: str = ""
) -> Record:
    """Set finding N (1-based) of the record at PATH to STATUS with REASON —
    and, for an accepted BLOCKER, EFFECT (`effect_ids`) — the decision the
    person gives, stored, never made: the side effect is the file. The
    lines are found by the record's structure (the N-th `[[finding]]`
    table), their values written by `toml_string`, every other byte kept;
    an effect line is added after the reason, or dropped when the decision
    no longer owes one. The result is read back and the file replaced whole
    (`files.write_atomic`) only when exactly that finding changed. Raises
    FindingsError — the file untouched — on a record that does not read, a
    number outside it, a status outside STATUSES, a reason owed and empty,
    an accepted BLOCKER without its effect or an effect anywhere else, or a
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
    # the check stays the auditor's: a decision never sets or drops it
    decided = Finding(
        old.grade,
        old.text,
        status,
        reason.strip(),
        effect.strip(),
        old.check,
        old.check_note,
        old.carries,
    )
    _hold_effect(decided)
    text = _decided_text(path, n, decided)
    after = _record_of(path, text)
    expected = list(before.findings)
    expected[n - 1] = decided
    if list(after.findings) != expected or _head(after) != _head(before):
        raise FindingsError(f"{path}: the decision did not read back as written")
    write_atomic(path, text)
    return after


def _effect_problem(f: Finding) -> str | None:
    """Why F's effect cannot stand, or None: an effect on anything but an
    accepted BLOCKER or WARNING, or not in EFFECT_FORM. An accepted BLOCKER
    without one reads (a record decided before effects were owed);
    report-check asks for it."""
    if not f.effect:
        return None
    if not f.effect_allowed:
        return (
            f"an effect belongs to an accepted BLOCKER or WARNING, not to a "
            f"{f.status} {f.grade}"
        )
    try:
        effect_ids(f.effect)
    except ValueError as exc:
        return str(exc)
    return None


def _hold_effect(decided: Finding) -> None:
    """An accepted BLOCKER names its effect, an accepted WARNING may, nothing else does — or FindingsError."""
    if decided.effect_owed and not decided.effect:
        raise FindingsError(
            "an accepted BLOCKER owes its effect on the verdicts — "
            f"--effect {EFFECT_FORM}: does this run still judge the promise?"
        )
    problem = _effect_problem(decided)
    if problem:
        raise FindingsError(problem)


def _decided_text(path: Path, n: int, decided: Finding) -> str:
    """The record's text with finding N's decision lines set to DECIDED —
    each value written on one line (`toml_string`), a multi-line one
    replaced whole."""
    # decoded, not read as text: a CRLF record keeps its line endings
    lines = path.read_bytes().decode("utf-8").splitlines(keepends=True)
    at = _decision_lines(lines, n)
    if at is None:
        raise FindingsError(
            f"{path}: finding {n} has no `status` and `reason` lines as labkit-audit "
            f"writes them — the record was changed by hand; restore it "
            f"(`git checkout HEAD -- {path.name}` in its audits/) or audit again"
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
    for (first, end, _, _), new in sorted(edits, key=lambda e: -e[0][0]):
        lines[first:end] = new
    return "".join(lines)


def _head(r: Record) -> tuple:
    """What a decision must leave as it was besides the findings."""
    return (
        r.date, r.mode, r.model, r.scope_sha, r.block_sha, r.registration, r.run_id,
        r.shown_sha, r.verdict,
    )  # fmt: skip


#: the name `create_file` gives a record, a failed attempt or a review:
#: `<minute>-<mode>[-<n>]` and its suffix, n counting the files of one minute
_WRITTEN_NAME = re.compile(
    rf"^(\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}-\d{{2}})-(?P<mode>{'|'.join(MODES)}|review)(?:-(?P<n>\d+))?"
    rf"(?P<failed>{re.escape(FAILED_SUFFIX)})?(?(failed)|\.toml)$"
)


def written_order(path: Path) -> tuple[str, int, str]:
    """The sort key of a file `create_file` wrote, oldest first: its minute, then
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
    return (m.group(1), int(m.group("n") or 1), path.name)


def is_record_name(name: str) -> bool:
    """Whether a file directly in `audits/` named NAME is a record of
    findings: TOML, neither a failed attempt nor a decision review."""
    return (
        name.endswith(".toml")
        and not name.endswith(FAILED_SUFFIX)
        and not REVIEW_NAME.search(name)
    )


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
    `attempts.area_integrity`, the errors kept beside. At the index,
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
                f"(`git add {' '.join(shlex.quote(shown(p, Path.cwd())) for p in left)}`)"
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
    records use `record_status` (`attempts.area_integrity`).
    """
    status = record_status(area)
    if status.errors:
        raise FindingsError(status.errors[0])
    return status.records


def covering_records(records: list[Record], now: AuditedState) -> list[Record]:
    """The RECORDS that saw the area as it is NOW: that code, that promise
    block, that registration and — mode analysis — that run and what was
    shown of it (`AuditedState`)."""
    return [r for r in records if r.state == now]


def registration_note(records: list[Record], registration: Mapping[str, str]) -> str:
    """For a refusal: "" unless the newest of RECORDS judged another
    registration than REGISTRATION, else a clause naming what changed
    (`protocol_check.registration_drift`) — the question or another field
    the kind owes, rewritten after the audit, owes a new one."""
    if not records:
        return ""
    changed = registration_drift(dict(records[-1].registration), registration)
    if not changed:
        return ""
    return (
        f" — the registration changed after the audit ({', '.join(changed)}): "
        f"the audit judged another question than the protocol asks now"
    )


def records_of_gone_runs(records: list[Record], known: set[str]) -> list[Record]:
    """The analysis RECORDS whose run is not among KNOWN (the run ids the
    area holds now). A record is evidence that the run existed and was
    read; the directory it names is gone. A record of NO_RUN names none.
    Why (labkit-paper area 09, fifth haiku round, 2026-10-22): t18 deleted
    two measured runs with `rm -rf runs/…` after their audits, and finalize
    read the three records left behind as "every finding decided"."""
    return [
        r
        for r in records
        if r.run_id is not None and r.run_id != NO_RUN and r.run_id not in known
    ]


def audit_coverage(area: Path, mode: str, now: AuditedState) -> str | None:
    """Why no audit of MODE covers the area as it is NOW, or None: a record
    with that `mode` that binds NOW (`AuditedState`: the code, the
    promises, the registration and — mode analysis — the answering run and
    what the prompt showed of it, recomputed now: a metrics.json or output
    rows changed after the audit owe a new one), every finding of it
    decided. The head names a record by hand; this is what makes
    "the frozen code was audited" a fact instead of a line (2026-10-14: after
    fixing the audit's findings a cold agent stamped the new sha, and no
    audit had seen that code). Its caller is report-check, mode `analysis`;
    the freeze holds the record its head names instead
    (`audit_record_gap`: runlog, preflight). Until 0.97.1 only the code was
    held: a promise rewritten after the audit, or a later run under the same
    code, kept the old record valid (review 2026-10-18).

    Raises:
        FindingsError: A findings file of AREA cannot be read.
        ValueError: MODE is not one of MODES, or NOW's run and shown sha
            are given for `preflight` or missing for `analysis`.
    """
    if mode not in MODES:
        raise ValueError(f"audit mode {mode!r} is not one of {', '.join(MODES)}")
    analysis = mode == ANALYSIS_AUDIT
    if analysis != (now.run_id is not None) or analysis != (now.shown_sha is not None):
        raise ValueError(
            f"audit mode {mode!r} with run_id {now.run_id!r}, shown_sha "
            f"{now.shown_sha!r}: "
            f"an analysis audit is held to the answering run and what it was "
            f"shown of it, a preflight audit to neither"
        )
    records = [r for r in area_records(area) if r.mode == mode]
    covering = covering_records(records, now)
    if not covering:
        # the code, promises and run as audited, the registration rewritten
        same_state = [r for r in records if r.state.bound == now.bound]
        if same_state:
            return (
                f"no {mode} audit saw the area as it is now"
                f"{registration_note(same_state, now.registration)} — "
                f"`labkit-audit <area> --mode {mode}`"
            )
        seen = "; ".join(sorted({r.state.words() for r in records})) or "none"
        stopped = unproven_attempts(area, mode, now.scope_sha, now.block_sha)
        if stopped:
            models = ", ".join(sorted({f.model for f in stopped}))
            return (
                f"no {mode} audit saw the area as it is now ({now.words()}): "
                f"{len(stopped)} attempt(s) unproven — {models} did not write the "
                f"answer whole (a safety stop or another model; "
                f"{stopped[-1].path.name}); the same model is not tried again on "
                f"this state: `labkit-audit <area> --mode {mode} --model <alias>`"
            )
        # before any audit "a change after the audit" spoke of one that
        # never ran (audit 2026-10-27, third, I12)
        why = (
            "a change after the audit owes a new one" if records else "none has run yet"
        )
        return (
            f"no {mode} audit saw the area as it is now "
            f"({now.words()}; audited: {seen}) — {why}: "
            f"`labkit-audit <area> --mode {mode}`"
            f"{validation_note(area)}"
        )
    still_open = open_findings(covering)
    if still_open:
        return (
            f"{len(still_open)} finding(s) of the {mode} audit of {now.scope_sha} still "
            f"`open` — decide each ({DECIDED_LIST})"
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
    cause: str  # one of FAILED_CAUSES


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
    cause: str,
    now: float | None = None,
) -> Path:
    """Write the evidence of an audit that could not run into AREA/audits/
    and return its path: `<stamp>-<mode>-failed.toml`, never overwriting.
    SCOPE_SHA and BLOCK_SHA name what the auditor would have read, so the
    freeze gate can hold the acknowledgement to the code and promises as
    they are now; TIMEOUT_S what the call was given; ERROR the backend's
    words; COMMAND the line that tried; CAUSE one of FAILED_CAUSES."""
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} — one of {', '.join(MODES)}")
    if cause not in FAILED_CAUSES:
        raise ValueError(f"cause {cause!r} — one of {', '.join(FAILED_CAUSES)}")
    when = time.localtime(now)
    stamp = name_minute(when)
    lines = [
        "# written by labkit-audit — the audit did not run; this is the evidence, "
        "not a record of findings",
        "[failed]",
        f"date = {_s(date_minute(when))}",
        f"mode = {_s(mode)}",
        f"model = {_s(model)}",
        f"scope_sha = {_s(scope_sha)}",
        f"block_sha = {_s(block_sha)}",
        f"timeout_s = {int(timeout_s)}",
        f"error = {_s(error)}",
        f"command = {_s(command)}",
        f"cause = {_s(cause)}",
    ]
    return create_file(
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
    for key in (
        "date",
        "mode",
        "model",
        "scope_sha",
        "block_sha",
        "error",
        "command",
        "cause",
    ):
        if not isinstance(table.get(key), str):
            raise FindingsError(f"{path}: [failed] {key} is missing or not a string")
    timeout = table.get("timeout_s")
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        raise FindingsError(f"{path}: [failed] timeout_s is missing or not an integer")
    if table["mode"] not in MODES:
        raise FindingsError(
            f"{path}: [failed] mode {table['mode']!r} — one of {', '.join(MODES)}"
        )
    if table["cause"] not in FAILED_CAUSES:
        raise FindingsError(
            f"{path}: [failed] cause {table['cause']!r} — one of "
            f"{', '.join(FAILED_CAUSES)}"
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
        table["cause"],
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


def unproven_attempts(area: Path, mode: str, sha: str, block_sha: str) -> list[Failed]:
    """The `unproven` failed attempts of MODE at the area as it is now —
    code SHA and promises BLOCK_SHA — with any model, oldest first.

    Raises:
        FindingsError: A failed-attempt file of AREA cannot be read.
    """
    return [
        f
        for f in failed_attempts(area)
        if f.cause == "unproven"
        and f.mode == mode
        and f.scope_sha == sha
        and f.block_sha == block_sha
    ]


def stopped_attempt(
    area: Path, mode: str, model: str, sha: str, block_sha: str
) -> Failed | None:
    """The newest `unproven` attempt of MODE with MODEL at the area as it is
    now (`unproven_attempts`); None when there is none. `labkit-audit`
    refuses another try on that state with that model.

    Raises:
        FindingsError: A failed-attempt file of AREA cannot be read.
    """
    fitting = [
        f for f in unproven_attempts(area, mode, sha, block_sha) if f.model == model
    ]
    return fitting[-1] if fitting else None


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


def names_preflight_record(name: str) -> bool:
    """Does NAME read as a preflight record's file name — the name
    `create_file` gave it under audits/ (`<minute>-preflight[-n].toml`),
    not a failed attempt's?"""
    m = _WRITTEN_NAME.match(name)
    return (
        m is not None and m.group("mode") == PREFLIGHT_AUDIT and not m.group("failed")
    )


def audit_record_gap(area: Path, name: str, text: str) -> str | None:
    """Why the head's non-empty `preflight_audit` NAME does not cover a full
    run of AREA under the protocol TEXT, or None: it names no record (an
    `n/a`, a sentence, a path — the field is the file name of the decided
    preflight record under audits/, and nobody waives their own audit),
    there is no such record in the area, the record is of another mode,
    it saw other code than the area stamps now (`scope_sha`) or another
    promise block than TEXT carries (`block_sha`), or a finding of it is
    still open. One answer for runlog's freeze gate, `preflight` and
    `protocol-check`; the caller decides what an empty field and `low`
    mean. Until 0.103.0 the field was a hand-written line (`<date> · scope
    sha <12 hex> · N findings`) whose sha a regex read and whose record the
    sha then had to find — the record names its sha itself, so the head
    names the record (review 2026-10-22). `n/a` passed every gate until
    0.99.0 (third haiku round, t18: "RF model training does not require
    external audit"); the refusal names the honest ways and offers no
    word to write instead."""
    name = name.strip()
    if not names_preflight_record(name):
        return (
            "`preflight_audit` names no record — the field is the file name of the "
            "decided preflight record under audits/ (`<minute>-preflight.toml`, "
            "printed by `labkit-audit <area> --mode preflight` when it writes one); "
            "at high repeat cost a full run owes that audit, and nobody waives their "
            "own: run it and name its record; when the backend does not answer, "
            "labkit-audit records the failed attempt and a full run acknowledges "
            "it with LABKIT_UNFROZEN=1 (its number stays unreportable). If no "
            "audit is owed at all, the repeat cost is wrong, not the field — and a "
            "tier lowered after the protocol's first commit is reported "
            "(LAB-015 Preflight audit before freezing, LAB-017 The number of audits follows the cost tier)"
        )
    path = area / DIR / name
    if not path.is_file():
        return (
            f"`preflight_audit` names {DIR}/{name}, and there is no such record in "
            f"this area — name the one `labkit-audit <area> --mode preflight` wrote"
        )
    try:
        record = read(path)
    except FindingsError as exc:
        return str(exc)
    if record.mode != PREFLIGHT_AUDIT:
        return f"{name} is a {record.mode} record — `preflight_audit` names the preflight audit"
    try:
        now = area_stamp(area)[0]
    except (FileNotFoundError, ValueError) as exc:
        return f"the area cannot be stamped now ({exc})"
    if record.scope_sha != now:
        return (
            f"the record {name} saw scope sha {record.scope_sha}, the code now stamps "
            f"{now} — it changed after the audit, so the change owes a new audit "
            f"(`labkit-audit <area> --mode preflight`); naming another record "
            f"without one is refused too{validation_note(area)}"
        )
    judged = _protocol_gap(record, name, text)
    if judged:
        return judged
    if record.open:
        return (
            f"{len(record.open)} finding(s) of {name} still `open` — decide each "
            f"({DECIDED_LIST})"
        )
    return None


def _protocol_gap(record: Record, name: str, text: str) -> str | None:
    """Why RECORD (named NAME) judged another protocol than TEXT, or None:
    another promise block (`block_sha`) or another registration — the kind,
    the question or another field the kind owes (`registration`)."""
    try:
        block = promises.block_stamp(text)
    except promises.PromiseError as exc:
        return str(exc)
    if record.block_sha != block:
        return (
            f"the record {name} saw the promise block {record.block_sha}, the protocol "
            f"carries {block} now — a promise rewritten after the audit owes a new one"
        )
    changed = registration_note([record], registration_stamp(text))
    return (
        f"the record {name} no longer covers the protocol{changed}" if changed else None
    )


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


def decide_way(
    area: Path, open_finding: OpenFinding, protocol: Path | None = None
) -> str:
    """The way out of OPEN_FINDING, an audit finding nobody decided in AREA:
    its `--decide` command (`repo.decide_command`, STATUS and the reason
    left for the person), and for a BLOCKER the `--findings` command that
    prints the ways out by cause beside it — the fix the gates that hold an
    undecided finding name."""
    cmd = decide_command(
        area,
        open_finding.number,
        "STATUS",
        "<why>",
        open_finding.record.path.name,
        protocol=protocol,
    )
    way = f"decide it ({DECIDED_LIST}): `{cmd}`"
    if open_finding.grade != "BLOCKER":
        return way
    return (
        f"{way} — `{audit_command(area, '--findings', protocol=protocol)}` "
        f"prints the ways out of a BLOCKER by its cause"
    )


def record_way(area: Path, protocol: Path | None = None) -> str:
    """The way out of an audit record in AREA that does not read: restore it
    as labkit-audit wrote it or audit again, and the recovery entry
    (`--findings`) that names what stands and the handover — never a
    record rewritten by hand."""
    return (
        "restore the record as labkit-audit wrote it (`git checkout HEAD -- "
        "<record>` where git holds it) or audit again; "
        f"`{audit_command(area, '--findings', protocol=protocol)}` names what "
        "stands and the handover"
    )
