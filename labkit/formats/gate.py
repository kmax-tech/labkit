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
`tests/test_ways_out_data.py` holds every site that builds one. Why: the
ways past the gates came where an agent saw no admissible next step, and a
held step that named its command was followed
(docs/notes/2026-10-27-standard-way-out.md).
"""

from __future__ import annotations

import shlex
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace

BLOCKER = "BLOCKER"
WARNING = "WARNING"

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

#: how a prefixed or as-written line joins its fix to its text; a dotted
#: line gives the fix its own ` · ` part
WAY_OUT = " — way out: "


def with_way_out(why: str, fix: str | None) -> str:
    """WHY with its way out FIX joined as every line tells it (`WAY_OUT`); WHY
    alone without one — the one spelling of a sentence and its step, for a
    finding's line and for a refusal's message (`AuditError`,
    `AttemptError`, runlog's start refusals)."""
    return why + (WAY_OUT + fix if fix else "")


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
    the author of a check says what the check is (audit 2026-10-23, C5).

    Attributes:
        grade: BLOCKER or WARNING.
        text: What was found — for a DOTTED finding the part between where
            and rule (`<what> · <consequence>`), else the whole message.
        form: PREFIXED (`<grade>: <text>`), AS_WRITTEN (the text says its
            grade itself, `DUPLICATE protocol id`), DOTTED (`coded`).
        where: The file or `file:line` the finding points at, when it has one.
        rule: The standard's rule it cites (`LAB-nnn Name`), when it cites one.
        fix: The way out — what closes the finding, a command where one
            exists. Required for a BLOCKER (refused without one), optional
            for a WARNING; told in every form (`line`).
        evidence_kind: GUARANTEED or STATIC_EVIDENCE, keyword, required.
    """

    grade: str
    text: str
    form: str = PREFIXED
    where: str | None = None
    rule: str | None = None
    fix: str | None = None
    evidence_kind: str = field(kw_only=True)

    def __post_init__(self) -> None:
        if self.grade not in (BLOCKER, WARNING):
            raise ValueError(
                f"a gate finding's grade is BLOCKER or WARNING, not {self.grade!r}"
            )
        if self.form not in (PREFIXED, AS_WRITTEN, DOTTED):
            raise ValueError(f"a gate finding's form is not {self.form!r}")
        if self.evidence_kind not in EVIDENCE_KINDS:
            raise ValueError(
                f"a gate finding's evidence kind is one of {EVIDENCE_KINDS}, "
                f"not {self.evidence_kind!r}"
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
    def line(self) -> str:
        """The finding as a gate tells it, without the indent. The dotted
        form names static evidence (`WARNING · static evidence · …`) so a
        reader of a code check's line sees it is an indication; a prefixed
        line stays `WARNING: …`, and the summary counts the kind. The fix
        ends the line in every form: its own dotted part, else after
        `WAY_OUT`."""
        if self.form == DOTTED:
            kind = STATIC_EVIDENCE if self.evidence_kind == STATIC_EVIDENCE else None
            parts = (self.grade, kind, self.where, self.text, self.rule, self.fix)
            return " · ".join(p for p in parts if p)
        told = self.text if self.form == AS_WRITTEN else f"{self.grade}: {self.text}"
        return with_way_out(told, self.fix)

    @property
    def message(self) -> str:
        """What the summary repeats: the text with its fix, and for a DOTTED
        finding the whole line — its text alone would lose where it points
        and the fix."""
        if self.form == DOTTED:
            return self.line
        return with_way_out(self.text, self.fix)


def blocker(text: str, *, fix: str) -> GateFinding:
    """A GUARANTEED BLOCKER with its way out FIX, told prefixed — what a pure
    check returns as data for the gate that takes it (`Findings.take`)."""
    return GateFinding(BLOCKER, text, fix=fix, evidence_kind=GUARANTEED)


def coded(
    grade: str,
    where: str | None,
    text: str,
    *,
    evidence_kind: str,
    rule: str | None = None,
    fix: str | None = None,
) -> GateFinding:
    """A code check's finding (code-check, preflight's code station, the
    audit's tier note), told as `<grade> · <where> · <text> · <rule> · <fix>`
    with the parts it has (static evidence named after the grade)."""
    return GateFinding(
        grade,
        text,
        DOTTED,
        where=where,
        rule=rule,
        fix=fix,
        evidence_kind=evidence_kind,
    )


#: the slot a check that does not know the working directory leaves for the
#: area in a command it names (`labkit-audit <area> --mode analysis`); the
#: gate that knows the area fills it (`Findings(area=…)`)
AREA_SLOT = "<area>"
#: the slot as it opens an audit command — filled with the gate's audit head,
#: which names `--protocol` where the area holds several (`repo.audit_command`)
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
            command runs as printed (ninth haiku round: a step naming
            `<area>` was not taken).
        audit: The audit command's head for that area (`repo.audit_command`
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

    def block(self, msg: str, *, fix: str) -> None:
        """A blocker: told as `BLOCKER: msg — way out: fix`, repeated in the
        summary, exit 1. Always GUARANTEED — static evidence never blocks.
        FIX is the way out (`GateFinding.fix`), required."""
        self.take(GateFinding(BLOCKER, msg, fix=fix, evidence_kind=GUARANTEED))

    def warn(self, msg: str, *, evidence_kind: str, fix: str | None = None) -> None:
        """A warning: told as `WARNING: msg`, counted, exit 0 on its own.
        EVIDENCE_KIND says what carries it (`GateFinding`); FIX, when given,
        is told after it as for a blocker."""
        self.take(GateFinding(WARNING, msg, fix=fix, evidence_kind=evidence_kind))

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
