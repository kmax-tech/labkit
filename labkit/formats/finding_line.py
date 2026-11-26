"""finding_line — an auditor's line read by one grammar: its tag and fields,
and the subject and the rule a finding names.

A line reads `<TAG> · <field> · <field> · …` (`tagged_line`); a finding's
grade line names its place first, its subject third (`subject_of`) and its
rule in the field that opens with `LAB-nnn` or says "new class"
(`active_rule_of`). A record stores the rule as `stored_rule` writes it and
`recorded_rule` reads it. A line without its subject or its rule raises
ValueError quoting the line; the rules are read from the shipped ledger.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Sequence
from dataclasses import dataclass

from labkit.formats.gate import (
    BLOCKER,
    KNOWN_RULE,
    NEW_CLASS,
    NEW_CLASS_RULE,
    NOTE,
    WARNING,
    RuleAssignment,
)
from labkit.formats import rules


GRADES = (BLOCKER, WARNING, NOTE)
#: the grammar of an answer line, one home for the audit and both
#: reviewers: what may stand before its keyword
#: (indentation, a quote, a bullet, a code mark, a heading's hashes) and the
#: separator after it — the ` · ` the instructions ask for, or a dash or
#: colon, which agents write too, so a `BLOCKER — …` line is never parsed
#: as none and its record read as covered
LEAD = r"^[\s>*`#-]*"
SEP = r"(?:·|—|–|:)"


def tag_head(tags: Sequence[str]) -> str:
    """The pattern of a tagged line's head: the lead a renderer adds
    (`LEAD`), one of TAGS, bold or not, as group 1, then the separator
    (`SEP`) — the one grammar every reader of an auditor's line starts
    from (`tagged_line`, `audit_reply.FINDING`)."""
    return LEAD + r"\**(" + "|".join(map(re.escape, tags)) + r")\**\s*" + SEP


#: a finding's grade line up to its first field
GRADE_HEAD = tag_head(GRADES)
#: between a tagged line's fields a dot or a dash — never a colon, which
#: `<file>:<line>` holds
_FIELD_SEP = re.compile(r"\s+[·—–]\s+")


@dataclass(frozen=True)
class TaggedLine:
    """An auditor's line read by the one grammar (`tagged_line`): TAG, the
    grade or the tag (`READ`) that opens it; FIELDS, what follows the
    separator, parted at a dot or a dash, each stripped of spaces."""

    tag: str
    fields: tuple[str, ...]

    @property
    def file_place(self) -> tuple[str, str] | None:
        """(file, place) of the first field, `<file>:<place>`: the file as
        written and what follows its first colon, spaces trimmed — inside
        the backticks when the field opens with one (text after the closing
        backtick is no part of the place); None when the field holds no
        colon, no file or no place. Fields part at a dot or a dash
        (`tagged_line`), so a place ends at ` — ` too."""
        if not self.fields:
            return None
        field = self.fields[0]
        if field.startswith("`") and "`" in field[1:]:
            field = field[1 : field.index("`", 1)]
        file, colon, place = field.strip("`").partition(":")
        place = place.strip().strip("`").strip()
        if not colon or not file.strip() or not place:
            return None
        return file.strip(), place


def tagged_line(line: str, tags: Sequence[str] = GRADES) -> TaggedLine | None:
    """LINE read as `<TAG> · <field> · <field> · …` (`TaggedLine`): the lead
    and the separator as `tag_head` takes them, the fields parted at a dot
    or a dash; None for a line that does not open with one of TAGS. The
    one reading of a grade line's fields — its place (`Finding.place`), its
    subject (`subject_of`), the file a review is shown
    (`decision_review.named_files`) — and of a reading hint's place
    (`audit_decisions.read_hints`)."""
    m = re.match(tag_head(tags) + r"\s*", line)
    if m is None:
        return None
    rest = line[m.end() :].strip()
    fields = tuple(f.strip() for f in _FIELD_SEP.split(rest)) if rest else ()
    return TaggedLine(m.group(1), fields)


#: what a finding is about, the auditor's judgement in the third field of
#: its line (`<GRADE> · <file>:<place> · <subject> · …`). `implementation`: the
#: code, the data handling or the run does not do what the registration
#: says or a correct measurement needs — the repair changes them and
#: measures anew, so `limitation` is refused for it (`subject_refusal`).
#: `statement`: the run does what it should, and the finding is about what
#: the registered text, the result or the report says — a limit of the
#: claim (`limitation`) or a description corrected in place (`fixed`).
#: `undetermined`: a concrete suspicion of a fault the auditor cannot settle
#: from what it was shown — the finding requires the check that settles it
#: and says what its value must show (`undetermined_finding_problem`); `limitation`
#: is refused, and the follow-up settles it on the check's value
#: (`undetermined_fix_problem`).
IMPLEMENTATION = "implementation"
STATEMENT = "statement"
UNDETERMINED = "undetermined"
SUBJECTS = (IMPLEMENTATION, STATEMENT, UNDETERMINED)
#: what a follow-up names for the fault it found in an undetermined finding
SETTLED_SUBJECTS = (IMPLEMENTATION, STATEMENT)
SUBJECT_FORM = (
    f"the third field of the finding line names its subject: `{IMPLEMENTATION}` "
    f"(the code, the data handling or the run departs from the registration "
    f"or a correct measurement), `{STATEMENT}` (the run is right; the finding "
    f"is about what the registered text, the result or the report says) or "
    f"`{UNDETERMINED}` (a concrete suspicion what is shown cannot settle; the "
    f"finding names the missing information and closes with the check that "
    f"settles it and what its value must show)"
)


def subject_of(text: str) -> str:
    """The subject (SUBJECTS) a finding names in the third field of its
    grade line, TEXT's first line: `<GRADE> · <file>:<place> · <subject> · …`,
    its fields parted by a dot or a dash as the parser reads them (`LEAD`,
    `SEP`).
    Raises ValueError, quoting the line, when the field is not one of
    SUBJECTS: which decisions a finding allows rests on it (`subject_refusal`),
    and a guess would decide it."""
    first = text.splitlines()[0] if text else ""
    # fields[0] is `<file>:<place>`, fields[1] the subject (`tagged_line`)
    line = tagged_line(first)
    subject = (
        line.fields[1].strip("`*") if line is not None and len(line.fields) > 1 else ""
    )
    if subject not in SUBJECTS:
        raise ValueError(
            f"a finding line without its subject: {first[:160]!r} — {SUBJECT_FORM}"
        )
    return subject


#: NEW_CLASS (`gate.NEW_CLASS`, the one home of the rule kinds' words) is the
#: rule field of a finding the standard has no rule for — collected for the
#: author to review (`new_class_findings`), never a rule of its own until a
#: decision with its grounds makes one. A record stores `LAB-nnn` or
#: NEW_CLASS; `Finding.rule` holds it as the gate's `RuleAssignment`
#: (`recorded_rule`, `stored_rule`)
RULE_FORM = (
    "a finding line names the rule it holds in its sixth field: "
    '`LAB-nnn <rule name>`, an active rule of the standard, or "new class" '
    "when none fits"
)
# a field may open with the separator of a wrapped line (`· LAB-015 …`)
_RULE_FIELD = re.compile(r'^[·—–`*"\'\s]*(LAB-\d{3})\b')
_NEW_CLASS_FIELD = re.compile(r'^[·—–`*"\'\s]*new class\b', re.I)


def active_rule_of(text: str) -> str:
    """The rule a finding names, `LAB-nnn` or NEW_CLASS: the field of its
    lines (parted at a dot or a dash, as `tagged_line` parts them) that
    opens with a rule id or says "new class". Read by what the field says,
    not by its position: the fields before it are free text that may hold a
    dash. Kept apart from the subject (where the fault lies) and the place
    (`file:line`): neither is inferred from the other. Raises ValueError,
    quoting the first line, for no such field, for two different ones, and
    for an id that is no active rule of the shipped ledger."""
    found = []
    for line in text.splitlines():
        for field in _FIELD_SEP.split(line.strip()):
            m = _RULE_FIELD.match(field)
            if m is not None:
                found.append(m.group(1))
            elif _NEW_CLASS_FIELD.match(field):
                found.append(NEW_CLASS)
    named = list(dict.fromkeys(found))
    first = text.splitlines()[0][:160] if text else ""
    if not named:
        raise ValueError(f"a finding line without its rule: {first!r} — {RULE_FORM}")
    if len(named) > 1:
        raise ValueError(
            f"a finding line with {len(named)} rules ({', '.join(named)}): "
            f"{first!r} — one rule per finding; {RULE_FORM}"
        )
    rule = named[0]
    if rule != NEW_CLASS:
        status = {r.id: r.status for r in rules.load_ledger(rules.LEDGER)}.get(rule)
        if status != "active":
            raise ValueError(
                f"a finding line naming {rule}, "
                f"{'not in the ledger' if status is None else status}: {first!r} "
                f"— {RULE_FORM}"
            )
    return rule


@functools.cache
def _ledger_titles() -> dict[str, str]:
    """Rule id → name of every rule of the shipped ledger, active or retired."""
    return {r.id: r.title for r in rules.load_ledger(rules.LEDGER)}


def recorded_rule(stored: str) -> RuleAssignment:
    """The `RuleAssignment` of a record's rule field STORED: NEW_CLASS_RULE,
    or the known rule with the ledger's name (a rule retired since keeps
    its name). Raises ValueError as `recorded_rule_problem` names it."""
    problem = recorded_rule_problem(stored)
    if problem is not None:
        raise ValueError(problem)
    if stored == NEW_CLASS:
        return NEW_CLASS_RULE
    return RuleAssignment(KNOWN_RULE, stored, _ledger_titles()[stored])


def stored_rule(rule: RuleAssignment | None) -> str:
    """How a record stores RULE: its id, or NEW_CLASS. Raises ValueError for
    None and for an assignment an auditor does not give (open, technical)."""
    if rule is not None and rule.kind == KNOWN_RULE and rule.rule_id is not None:
        return rule.rule_id
    if rule == NEW_CLASS_RULE:
        return NEW_CLASS
    raise ValueError(
        f"an audit finding's rule is a rule of the ledger or {NEW_CLASS!r}, not {rule!r}"
    )


def recorded_rule_problem(rule: object) -> str | None:
    """Why a record's RULE cannot stand, or None: NEW_CLASS, or an id the
    shipped ledger holds — active or retired since, so a record outlives
    its rule's retirement."""
    if rule == NEW_CLASS:
        return None
    if isinstance(rule, str) and rule in _ledger_titles():
        return None
    return f"rule {rule!r} — a rule id of the ledger or {NEW_CLASS!r}"
