"""gate — what a gate found, told once: the blockers, the warnings, the
summary and the exit code.

Every gate that blocks (preflight, finalize, report-check, code-check,
notes-check) collects its findings here and ends with `report`: one
spelling of the grade (`BLOCKER:` / `WARNING:`), one summary line, one exit
contract — 1 with a blocker, 0 otherwise (`EXIT_CONTRACT`, the line every
gate's `--help` ends with). The one exception is `labkit-audit`, by intent:
it exits 1 on a warning too, because its findings are for a person to
decide, not for a hook to pass (its docstring has the evidence). The order
of the gates and what each holds: docs/architecture.md, "The gates in
order". A gate's verdict is recomputed at every call and logged nowhere,
by design — "Where verdicts are recorded" there says why.

A finding is data first (`GateFinding`: its grade and its text — not
`findings.Finding`, an audit's finding the person decides) and a line on
the console second. `Findings` keeps the data and tells each finding, as it
is found, through one channel — `print` by default, `None` for a gate that
runs inside another gate and only wants the data (report-check's finalize
station). Headers and the notes a station prints beside its findings
(`note`, `header`) go through the same channel, so a silent gate is silent
whole; they are told, never counted. Why one collector and one channel:
docs/notes/2026-10-19-gates-and-run-start.md.

A finding goes in as data: `block` and `warn` for a text the gate words
itself, `take` for a `GateFinding` built where it was found — a protocol
id's, or a code check's (`coded`: grade, where, what, rule, fix as fields,
told as `BLOCKER · <where> · <what> · <rule> · <fix>`). No gate reads a
grade back from a line's words.

Every BLOCKER names its way out (`fix`): the step that closes it, as a
command where one exists, and where the cause may not be fixable, the
handover. A BLOCKER without one is refused here, and
`tests/test_ways_out_data.py` holds every site that builds one. Why: an
agent that sees no admissible next step goes past the gate, and a held step
that names its command is followed
(docs/notes/2026-10-27-standard-way-out.md).
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from labkit.formats.files import ACCESS, read_cause

if TYPE_CHECKING:
    from labkit.formats.commands import Command

BLOCKER = "BLOCKER"
WARNING = "WARNING"
NOTE = "NOTE"  # an auditor's grade below WARNING: printed, never held

#: the exit contract of every mechanical gate, as its `--help` states it
EXIT_CONTRACT = (
    "exit codes: 0 clean (warnings may stand), 1 at least one blocker, "
    "2 no check (usage error, nothing to hold)"
)

#: how a finding is told: the gate prefixes the grade (`BLOCKER: …`), the
#: text says its grade in its own words, or the code checks' ` · ` form
PREFIXED, AS_WRITTEN, DOTTED = "prefixed", "as written", "dotted"

#: what carries a gate finding's sentence (`GateFinding.evidence_kind`): an
#: exact mechanical check, or an indication that warns and never blocks.
#: The third kind AGENTS.md names, the agent audit, is no gate's sentence —
#: it is the nature of `findings.Finding`, the record a person decides.
GUARANTEED = "guaranteed"
STATIC_EVIDENCE = "static evidence"
EVIDENCE_KINDS = (GUARANTEED, STATIC_EVIDENCE)

#: what a finding says about its check (`GateFinding.outcome`,
#: docs/notes/2026-11-09-check-outcomes.md and
#: docs/notes/2026-11-11-check-classification-sample.md): an exact check found
#: a known rule or a technical contract breached — a required input missing
#: or malformed is that too —; an exact check found the deviation it checks
#: for, and its binding basis is not settled; a search found an indication,
#: and no breach is established; or the check could not be executed here (an
#: access refused, a limit of the check). Only the last is for a site to say
#: (`GateFinding.stated_outcome`); the others follow from what carries the
#: sentence and from the rule assignment (`derived_outcome`), and a site that
#: states one of them otherwise is refused — VIOLATED on an open assignment
#: raises. A BLOCKER blocks whatever its outcome, and the line names only a
#: check not executed: VIOLATED, DEVIATION and SUSPECTED read alike there
VIOLATED = "violated"
DEVIATION = "deviation"
SUSPECTED = "suspected"
NOT_EXECUTABLE = "not executable"
OUTCOMES = (VIOLATED, DEVIATION, SUSPECTED, NOT_EXECUTABLE)
#: how a line names a check not executed: `BLOCKER (check not executable): …`
NOT_EXECUTABLE_MARK = "check not executable"


def outcome_of_failed_read(exc: BaseException) -> str | None:
    """What a site states (`GateFinding.stated_outcome`) for a failed read
    EXC: NOT_EXECUTABLE when the access was refused (the input may be
    sound), else None — nothing. A missing or malformed input is a defect
    found, so the finding's outcome is the derived one (`derived_outcome`):
    VIOLATED where the site records a technical contract or a known rule,
    DEVIATION where its assignment is open. Not the cause, which
    `files.read_cause` names. Any exception a site catches around a read
    goes in; only an OSError other than a missing file gives
    NOT_EXECUTABLE."""
    return NOT_EXECUTABLE if read_cause(exc) == ACCESS else None


#: how every line joins its fix to its text — `<what is refused and why>.
#: Next: <fix>`, the fix a command where one exists; a dotted line gives it
#: its own ` · Next: ` part
WAY_OUT = ". Next: "
#: what a hold names first while a declared run's code has changed
#: (`GateFinding.withdraw_first`): why in each hold, not in one note — a
#: hold that says only "measure anew" leads past a note below it
WITHDRAW_FIRST = "withdraw the adoption first (`{command}`), then "


def with_way_out(why: str, fix: str | None) -> str:
    """WHY with its way out FIX joined as every line tells it (`WAY_OUT`,
    WHY's own closing full stop dropped first); WHY alone without one — the
    one spelling of a sentence and its step, for a finding's line and for a
    refusal's message (`AuditError`, `AttemptError`, runlog's start
    refusals)."""
    if not fix:
        return why
    return why.rstrip().removesuffix(".") + WAY_OUT + fix


#: the four kinds of a finding's rule assignment (`RuleAssignment`), the one
#: home of their words: a rule of the standard the finding cites; a rule not
#: decided yet; a technical condition no rule of the standard covers; a fault
#: the agent audit found that no rule names (`findings.Finding.rule`)
KNOWN_RULE = "known rule"
OPEN_ASSIGNMENT = "open assignment"
TECHNICAL_CONTRACT = "technical contract"
NEW_CLASS = "new class"
RULE_KINDS = (KNOWN_RULE, OPEN_ASSIGNMENT, TECHNICAL_CONTRACT, NEW_CLASS)
#: a rule id a finding site records: a rule of the lab standard (`LAB-nnn`) or
#: of the code standard (`CODE-nnn`, docs/coding-style.md)
_RULE_ID = r"(?:LAB|CODE)-\d{3}"
#: how a cited rule reads: `LAB-nnn <its name>`, `CODE-nnn <its name>`
_CITED_RULE = re.compile(rf"^({_RULE_ID}) (\S.*)$")


@dataclass(frozen=True)
class RuleAssignment:
    """Which rule a finding holds, as data: KIND, one of RULE_KINDS; for a
    KNOWN_RULE its RULE_ID (`LAB-nnn` of the lab standard, `CODE-nnn` of the
    code standard) and NAME as cited,
    for every other kind neither — an open assignment names no rule, not
    even a proposed one, and recording it decides nothing. Raises ValueError
    for another kind, a malformed id, a known rule without its name, or an
    id beside another kind. Whether the id and the name are an active rule
    of the ledger, or a head of the code standard, is held over the source,
    where they are written (`rules.check_refs`, `tests/test_rules.py`): this
    module is core and reads neither.

    Attributes:
        kind: KNOWN_RULE, OPEN_ASSIGNMENT, TECHNICAL_CONTRACT or NEW_CLASS.
        rule_id: `LAB-nnn` or `CODE-nnn` for KNOWN_RULE, else None.
        name: The rule's name as cited for KNOWN_RULE, else None.
    """

    kind: str
    rule_id: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in RULE_KINDS:
            raise ValueError(
                f"a rule assignment is one of {RULE_KINDS}, not {self.kind!r}"
            )
        if self.kind == KNOWN_RULE:
            if self.rule_id is None or not re.fullmatch(_RULE_ID, self.rule_id):
                raise ValueError(
                    f"a known rule carries its id `LAB-nnn` or `CODE-nnn`, not "
                    f"{self.rule_id!r}"
                )
            if not (self.name or "").strip():
                raise ValueError(f"a known rule carries its name: {self.rule_id}")
        elif self.rule_id is not None or self.name is not None:
            raise ValueError(
                f"a rule assignment of kind {self.kind!r} names no rule, and this "
                f"one names {self.rule_id!r} {self.name!r}"
            )

    @property
    def line_part(self) -> str | None:
        """What a finding's line tells of it: `LAB-nnn <name>` for a known
        rule, NEW_CLASS for a new class, None (nothing told) for an open
        assignment and a technical contract — they are data for the
        inventory, not words for the reader."""
        if self.kind == KNOWN_RULE:
            return f"{self.rule_id} {self.name}"
        return NEW_CLASS if self.kind == NEW_CLASS else None


def cited_rule(rule: str) -> RuleAssignment:
    """The KNOWN_RULE assignment of RULE as a site cites it, `LAB-nnn <its
    name>` or `CODE-nnn <its name>` — the spelling `rules.check_refs` holds to the ledger. Raises
    ValueError for any other shape."""
    m = _CITED_RULE.match(rule)
    if m is None:
        raise ValueError(
            f"a cited rule reads `LAB-nnn <its name>` or `CODE-nnn <its name>`, "
            f"not {rule!r}"
        )
    return RuleAssignment(KNOWN_RULE, m.group(1), m.group(2))


#: the assignments without a rule, one value each
OPEN_RULE = RuleAssignment(OPEN_ASSIGNMENT)
TECHNICAL_RULE = RuleAssignment(TECHNICAL_CONTRACT)
NEW_CLASS_RULE = RuleAssignment(NEW_CLASS)


#: the outcome of an exact check that found its condition, by the kind of
#: its rule assignment (`derived_outcome`); None is a site that records no
#: assignment. VIOLATED needs a decided basis; an open assignment may be a
#: duty not decided or only a rule not yet entered, so DEVIATION claims
#: neither. A new class and a site without an assignment name no decided
#: basis either
_EXACT_OUTCOME_BY_BASIS: dict[str | None, str] = {
    KNOWN_RULE: VIOLATED,
    TECHNICAL_CONTRACT: VIOLATED,
    OPEN_ASSIGNMENT: DEVIATION,
    NEW_CLASS: DEVIATION,
    None: DEVIATION,
}


def derived_outcome(evidence_kind: str, basis: str | None) -> str:
    """The outcome of a check that ran and found its condition, from what
    carries the sentence (EVIDENCE_KIND) and the kind of the finding's rule
    assignment (BASIS, one of RULE_KINDS, None without an assignment) —
    the one home of the derivation, for a finding and for the inventory
    that reads a site from the source; NOT_EXECUTABLE is never derived, the
    site says it. STATIC_EVIDENCE gives SUSPECTED whatever the basis;
    GUARANTEED gives VIOLATED for a known rule or a technical contract and
    DEVIATION for an open assignment, a new class and no assignment
    (`_EXACT_OUTCOME_BY_BASIS`). Raises ValueError for an evidence kind or a
    rule kind it does not name, so a new one is decided here before any
    finding is told as a breach. Pure."""
    if evidence_kind == STATIC_EVIDENCE:
        return SUSPECTED
    if evidence_kind != GUARANTEED or basis not in _EXACT_OUTCOME_BY_BASIS:
        raise ValueError(
            f"no check outcome is defined for evidence kind {evidence_kind!r} "
            f"with rule kind {basis!r} (`gate.derived_outcome`)"
        )
    return _EXACT_OUTCOME_BY_BASIS[basis]


@dataclass(frozen=True)
class GateFinding:
    """One finding of a gate. The grade field decides what counts, never the
    words; FORM decides how it is told (`line`); EVIDENCE_KIND says what
    carries the sentence.

    Two axes, two questions. `grade` answers "what follows" — a BLOCKER
    stops, a WARNING is read. `evidence_kind` answers "what carries the
    sentence in `text`" — GUARANTEED, an exact mechanical check that is
    silent on a correct input, or STATIC_EVIDENCE, an indication that may
    be wrong and so warns and never blocks (a static-evidence BLOCKER is
    refused here). The kind classifies the sentence, not the thing it is
    about: "record X holds an undecided BLOCKER" is a register fact and
    GUARANTEED, although the finding it names is an agent audit's
    judgement — that judgement keeps its own grade in the record
    (`findings.Finding`). The kind is given at every site, never defaulted:
    the author of a check says what the check is.

    Attributes:
        grade: BLOCKER or WARNING.
        text: What was found — for a DOTTED finding the part between where
            and rule (`<what> · <consequence>`), else the whole message.
        form: PREFIXED (`<grade>: <text>`), AS_WRITTEN (the text says its
            grade itself, `DUPLICATE protocol id`), DOTTED (`coded`).
        where: The file or `file:line` the finding points at, when it has one.
        rule: The rule assignment (`RuleAssignment`). None: the site has not
            been visited by the migration yet (docs/notes/2026-11-10-test-model.md,
            step 3), so nothing is recorded; OPEN_RULE: visited, and the
            rule is recorded as not decided. Neither is told in the line.
            A plain string is refused.
        fix: The way out — what closes the finding, a command where one
            exists. Required for a BLOCKER (refused without one), optional
            for a WARNING; told in every form (`line`).
        step: The command the way out names, as data (`commands.Command`),
            where it names one of labkit's own; code that decides on a
            finding's way — `next_step`, `report_check.adoption_order_note`
            — reads its `name`, never the words of `fix`.
        withdraw_first: The withdrawal (`commands.withdraw_command`) a hold
            names before its own way out while the declared run's code
            changed since it ran (`withdrawn_first`); told
            as `WITHDRAW_FIRST` before `fix` in every form (`way`).
        evidence_kind: GUARANTEED or STATIC_EVIDENCE, keyword, required.
        stated_outcome: The outcome the site states, or None (the default)
            where it states none — not the finding's outcome, which `outcome`
            gives. A site states NOT_EXECUTABLE for a check that could not
            run; another value of OUTCOMES is accepted only where it is the
            derived one (`derived_outcome`), and refused otherwise.
        changed_since: The run whose code or declared scope this blocker
            found changed since it ran — set where the comparison found the
            difference (`run_record_check.code_since_run`,
            `finalize.check_declared_scopes`); None for every other finding,
            also for code that could not be compared. Callers order their
            advice by it, never by the words
            (`report_check.held_declaration`).
    """

    grade: str
    text: str
    form: str = PREFIXED
    where: str | None = None
    rule: RuleAssignment | None = None
    fix: str | None = None
    evidence_kind: str = field(kw_only=True)
    changed_since: str | None = field(default=None, kw_only=True)
    step: Command | None = field(default=None, kw_only=True)
    withdraw_first: Command | None = field(default=None, kw_only=True)
    stated_outcome: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if self.grade not in (BLOCKER, WARNING):
            raise ValueError(
                f"a gate finding's grade is BLOCKER or WARNING, not {self.grade!r}"
            )
        if self.rule is not None and not isinstance(self.rule, RuleAssignment):
            raise ValueError(
                f"a gate finding's rule is a RuleAssignment (`cited_rule`, "
                f"OPEN_RULE, TECHNICAL_RULE), not {self.rule!r}"
            )
        if self.form not in (PREFIXED, AS_WRITTEN, DOTTED):
            raise ValueError(f"a gate finding's form is not {self.form!r}")
        if self.evidence_kind not in EVIDENCE_KINDS:
            raise ValueError(
                f"a gate finding's evidence kind is one of {EVIDENCE_KINDS}, "
                f"not {self.evidence_kind!r}"
            )
        if self.stated_outcome is not None and self.stated_outcome not in OUTCOMES:
            raise ValueError(
                f"a gate finding's outcome is one of {OUTCOMES}, not {self.stated_outcome!r}"
            )
        derived = derived_outcome(self.evidence_kind, self._basis)
        if self.stated_outcome not in (None, NOT_EXECUTABLE, derived):
            raise ValueError(
                f"a gate finding states the outcome {self.stated_outcome!r}, and "
                f"its evidence kind and rule assignment give {derived!r}: "
                f"{self.text!r}"
            )
        if self.evidence_kind == STATIC_EVIDENCE and self.grade == BLOCKER:
            raise ValueError(
                f"static evidence warns, never blocks (AGENTS.md): {self.text!r}"
            )
        if self.grade == BLOCKER and not (self.fix or "").strip():
            raise ValueError(
                f"a BLOCKER names its way out (fix), and this one has none: "
                f"{self.text!r}"
            )

    @property
    def outcome(self) -> str:
        """What the finding says about its check, one of OUTCOMES:
        NOT_EXECUTABLE where the site states it — it comes first, a check
        that did not run found nothing —, else the outcome derived from the
        evidence kind and the rule assignment (`derived_outcome`)."""
        if self.stated_outcome == NOT_EXECUTABLE:
            return NOT_EXECUTABLE
        return derived_outcome(self.evidence_kind, self._basis)

    @property
    def _basis(self) -> str | None:
        """The kind of the rule assignment, None without one."""
        return self.rule.kind if self.rule is not None else None

    @property
    def way(self) -> str | None:
        """The way out as told: `fix`, after the withdrawal first where
        `withdraw_first` is set (`WITHDRAW_FIRST`); None without a fix."""
        if self.fix is None or self.withdraw_first is None:
            return self.fix
        return WITHDRAW_FIRST.format(command=self.withdraw_first) + self.fix

    @property
    def line(self) -> str:
        """The finding as a gate tells it, without the indent. The dotted
        form names static evidence (`WARNING · static evidence · …`) so a
        reader of a code check's line sees it is an indication; a prefixed
        line stays `WARNING: …`, and the summary counts the kind. The way
        out (`way`) ends the line in every form: its own dotted part
        (`Next: …`), else after `WAY_OUT`. Of the outcomes only
        NOT_EXECUTABLE is named; a DEVIATION reads like a VIOLATED finding."""
        unrun = NOT_EXECUTABLE_MARK if self.outcome == NOT_EXECUTABLE else None
        if self.form == DOTTED:
            kind = STATIC_EVIDENCE if self.evidence_kind == STATIC_EVIDENCE else None
            fix = f"Next: {self.way}" if self.way else None
            rule = self.rule.line_part if self.rule is not None else None
            parts = (self.grade, kind, unrun, self.where, self.text, rule, fix)
            return " · ".join(p for p in parts if p)
        if self.form == AS_WRITTEN:
            told = f"{self.text} ({unrun})" if unrun else self.text
        else:
            told = (
                f"{self.grade} ({unrun}): {self.text}"
                if unrun
                else f"{self.grade}: {self.text}"
            )
        return with_way_out(told, self.way)

    @property
    def message(self) -> str:
        """What the summary repeats: the text with its way out, and for a
        DOTTED finding the whole line — its text alone would lose where it
        points and the fix."""
        if self.form == DOTTED:
            return self.line
        return with_way_out(self.text, self.way)


def withdrawn_first(
    found: list[GateFinding], withdrawal: Command | None
) -> list[GateFinding]:
    """FOUND, each BLOCKER with a way out naming WITHDRAWAL first
    (`GateFinding.withdraw_first`) when one is given; a warning, a blocker
    without a way out, or None come back as they are. The one place the
    rule becomes a datum; who decides it is `report_check.held_declaration`
    and `registration_hold.declaring_protocol`."""
    if withdrawal is None:
        return found
    return [
        replace(f, withdraw_first=withdrawal)
        if f.grade == BLOCKER and f.fix is not None
        else f
        for f in found
    ]


def blocker(
    text: str,
    *,
    fix: str,
    step: Command | None = None,
    stated_outcome: str | None = None,
    rule: RuleAssignment | None = None,
) -> GateFinding:
    """A GUARANTEED BLOCKER with its way out FIX, told prefixed — what a pure
    check returns as data for the gate that takes it (`Findings.take`).
    STATED_OUTCOME: NOT_EXECUTABLE for a check that could not run, else None
    (`GateFinding.stated_outcome`); RULE: its rule assignment
    (`GateFinding.rule`)."""
    return GateFinding(
        BLOCKER,
        text,
        rule=rule,
        fix=fix,
        evidence_kind=GUARANTEED,
        step=step,
        stated_outcome=stated_outcome,
    )


def coded(
    grade: str,
    where: str | None,
    text: str,
    *,
    evidence_kind: str,
    rule: RuleAssignment | None = None,
    fix: str | None = None,
    stated_outcome: str | None = None,
) -> GateFinding:
    """A code check's finding (code-check, preflight's code station, the
    audit's tier note), told as `<grade> · <where> · <text> · <rule> · <fix>`
    with the parts it has (static evidence, a check not executable, named
    after the grade)."""
    return GateFinding(
        grade,
        text,
        DOTTED,
        where=where,
        rule=rule,
        fix=fix,
        evidence_kind=evidence_kind,
        stated_outcome=stated_outcome,
    )


#: the slot a check that does not know the working directory leaves for the
#: area in a command it names (`labkit-audit <area> --mode analysis`); the
#: gate that knows the area fills it (`Findings(area=…)`)
AREA_SLOT = "<area>"
#: the slot as it opens an audit command — filled with the gate's audit head,
#: which names `--protocol` where the area holds several (`commands.audit_command`)
AUDIT_SLOT = f"labkit-audit {AREA_SLOT}"


class Findings:
    """What the stations found, as data, and the channel they are told through.

    Every blocker is told as one line and repeated in the summary, so it is
    found at the end of a long hook output too.

    Args:
        tell: Where each line goes as it is found — `print` by default;
            `None` collects silently, for a gate run inside another gate
            (report-check's finalize station).
        area: The area as the reader types it; every `AREA_SLOT` in a
            finding taken is replaced by it, shell-quoted, so a named
            command runs as printed (a step naming `<area>` is not
            taken).
        audit: The audit command's head for that area (`commands.audit_command`
            with no step: the area quoted, `--protocol` where the area holds
            several); every `AUDIT_SLOT` is replaced by it before the plain
            slot is filled. Without it the plain area stands there.
    """

    def __init__(
        self,
        tell: Callable[[str], None] | None = print,
        *,
        area: str | None = None,
        audit: str | None = None,
    ) -> None:
        self.found: list[GateFinding] = []
        self._tell = tell
        self._area = area
        self._audit = audit

    @property
    def blocked(self) -> list[str]:
        """The blockers' messages (`GateFinding.message`), in the order found."""
        return [f.message for f in self.found if f.grade == BLOCKER]

    @property
    def warned(self) -> list[str]:
        """The warnings' messages (`GateFinding.message`), in the order found."""
        return [f.message for f in self.found if f.grade == WARNING]

    @property
    def warnings(self) -> int:
        """How many warnings stand."""
        return len(self.warned)

    @property
    def static_evidence(self) -> int:
        """How many of the warnings are static evidence — indications, not
        proofs (a blocker never is)."""
        return sum(1 for f in self.found if f.evidence_kind == STATIC_EVIDENCE)

    @property
    def exit_code(self) -> int:
        """The exit contract: 1 with a blocker, 0 with warnings only or all clear."""
        return 1 if self.blocked else 0

    def note(self, text: str) -> None:
        """A line told beside the findings and counted as nothing — a station
        header, an `ok`, a reminder."""
        if self._tell is not None:
            self._tell(text)

    def header(self, title: str) -> None:
        """A station's header line, told like a note."""
        self.note(f"── {title} ──")

    def take(self, finding: GateFinding) -> None:
        """Keep a finding, its area slot filled, and tell it."""
        if self._area is not None and AREA_SLOT in finding.line:
            area, audit = shlex.quote(self._area), self._audit

            def filled(s: str) -> str:
                s = s.replace(AUDIT_SLOT, audit) if audit is not None else s
                return s.replace(AREA_SLOT, area)

            finding = replace(
                finding,
                text=filled(finding.text),
                fix=filled(finding.fix) if finding.fix else None,
            )
        self.found.append(finding)
        self.note(f"  {finding.line}")

    def take_all(self, findings: Iterable[GateFinding]) -> None:
        """Keep and tell findings in order through this collector's channel."""
        for finding in findings:
            self.take(finding)

    def block(
        self,
        msg: str,
        *,
        fix: str,
        step: Command | None = None,
        stated_outcome: str | None = None,
        rule: RuleAssignment | None = None,
    ) -> None:
        """A blocker: told as `BLOCKER: msg. Next: fix`, repeated in the
        summary, exit 1. Always GUARANTEED — static evidence never blocks.
        FIX is the way out (`GateFinding.fix`), required; STEP the command
        it names, as data (`GateFinding.step`); STATED_OUTCOME and RULE as
        `blocker`'s."""
        self.take(
            blocker(msg, fix=fix, step=step, stated_outcome=stated_outcome, rule=rule)
        )

    def warn(
        self,
        msg: str,
        *,
        evidence_kind: str,
        fix: str | None = None,
        stated_outcome: str | None = None,
        rule: RuleAssignment | None = None,
    ) -> None:
        """A warning: told as `WARNING: msg`, counted, exit 0 on its own.
        EVIDENCE_KIND says what carries it (`GateFinding`); FIX, when given,
        is told after it as for a blocker; STATED_OUTCOME and RULE as
        `blocker`'s."""
        self.take(
            GateFinding(
                WARNING,
                msg,
                rule=rule,
                fix=fix,
                evidence_kind=evidence_kind,
                stated_outcome=stated_outcome,
            )
        )

    def _kinds(self) -> str:
        """` (K static evidence)` when K warnings are indications, else ``."""
        k = self.static_evidence
        return f" ({k} static evidence)" if k else ""

    def summary(self, tool: str, before: str) -> list[str]:
        """The summary lines: with a blocker the count and every blocker named
        again, with warnings only the count, else `all clear`."""
        if self.blocked:
            return [
                f"{tool}: {len(self.blocked)} blocker(s), {self.warnings} warning(s)"
                f"{self._kinds()} "
                f"— fix the blockers before {before}:",
                *(f"  - {msg}" for msg in self.blocked),
            ]
        if self.warned:
            return [
                f"{tool}: 0 blockers, {self.warnings} warning(s){self._kinds()} — review the "
                f"warnings above before {before}."
            ]
        return [f"{tool}: all clear."]

    def report(self, tool: str, before: str) -> int:
        """Tell the summary (`summary`, after a blank line) and return the
        exit code (`exit_code`): 1 with a blocker, 0 otherwise."""
        self.note("")
        for line in self.summary(tool, before):
            self.note(line)
        return self.exit_code
