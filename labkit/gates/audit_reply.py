"""Reading the auditor's answer: its finding lines, the verdict line, the FIX
lines of a follow-up and the scope it says it read.

Pure functions from the report text to data; an `AuditError` names the line
that cannot be read. The line forms are the agent instructions'
(`experiment-preflight.agent.md`); `LEAD` and `SEP` are the pieces the
review gates build their own line patterns from.
"""

from __future__ import annotations

import re
from pathlib import Path

from labkit.checks.audit_binding import AuditError
from labkit.formats import (
    findings,
    protocol_block,
)
from labkit.formats.repo import (
    layout_root,
)
from labkit.gates.audit_prompt import Followup
from labkit.gates.ways_out import (
    ANSWER_AGAIN,
)

#: the grammar of an answer line, one home for the audit and both
#: reviewers (audit 2026-10-27, third): what may stand before its keyword
#: (indentation, a quote, a bullet, a code mark) and the separator between
#: its fields — the ` · ` the instructions ask for, or a dash or colon,
#: which agents write too (audit 2026-10-15: two blockers written as
#: `BLOCKER — …` parsed as none, and the record read as covered)
LEAD = r"^[\s>*`-]*"
SEP = r"(?:·|—|–|:)"
#: a finding line: the grade, then a separator
FINDING = re.compile(
    LEAD + r"\**(" + "|".join(findings.GRADES) + r")\**\s*" + SEP, re.M
)
VERDICT = re.compile(
    r"verdict:\s*(\d+)\s*blockers?(?:\(s\))?,\s*(\d+)\s*warnings?(?:\(s\))?"
    r"(?:,\s*(\d+)\s*notes?(?:\(s\))?)?",
    re.I,
)
#: a verdict line as a section of a report: VERDICT at the line's start —
#: a finding's bullet that quotes a verdict mid-line does not end it
VERDICT_LINE = re.compile(LEAD + r"\**" + VERDICT.pattern, re.I)
#: the auditor's refusal to audit — the one line its instructions give it for
#: an unfilled protocol (`experiment-preflight.agent.md`); an answer without a
#: verdict line that carries it is shown as that refusal
REFUSED = re.compile(LEAD + r"refused:\s*(.*?)[\s`*]*$", re.M | re.I)
CLARITY_FINDING = re.compile(LEAD + r"RULE\s*(\d+)\**\s*" + SEP, re.M)
CLARITY_VERDICT = re.compile(
    r"verdict:\s*(\d+)\s*findings?(?:\s*\((\d+)\s*would be answered wrong\))?", re.I
)
#: a line that opens as a fix verdict — read whole or refused, never skipped
FIX_OPEN = re.compile(LEAD + r"\**FIX\**\s*" + SEP, re.M)
#: a fix verdict line: `FIX · <record>#<n> · <verdict> · <why>`
FIX = re.compile(
    LEAD
    + r"\**FIX\**\s*"
    + SEP
    + r"\s*`?(?P<record>[^\s`#]+)#(?P<n>\d+)`?\s*"
    + SEP
    + r"\s*`?(?P<verdict>[a-z_]+)`?\s*"
    + SEP
    + r"\s*(?P<why>\S.*)$"
)


def parse_fixes(text: str, earlier_repairs: Followup) -> list[findings.FixVerdict]:
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
    shown = {e.ref: e for e in earlier_repairs.blockers}
    out: list[findings.FixVerdict] = []
    for i, line in enumerate(lines):
        if not FIX_OPEN.match(line):
            continue
        f = FIX.match(line.strip())
        if f is None:
            raise AuditError(
                f"a FIX line that does not read: {line.strip()[:160]!r} — the form "
                f"is `FIX · <record>#<n> · resolved|unresolved|not_assessable · <why>`",
                fix=ANSWER_AGAIN,
            )
        ref = f"{f['record']}#{f['n']}"
        e = shown.get(ref)
        if e is None:
            raise AuditError(
                f"a FIX verdict on {ref}, which the prompt did not show — the shown "
                f"ones: {', '.join(shown) or 'none'}",
                fix=ANSWER_AGAIN,
            )
        more = fix_block(lines, i)
        others = sorted({r for r in shown if r != ref and any(r in x for x in more)})
        if others:
            raise AuditError(
                f"the FIX entry on {ref} also names {', '.join(others)} below its "
                f"line — which finding its verdict judges is not clear; one entry "
                f"per finding, separated by a blank line",
                fix=ANSWER_AGAIN,
            )
        out.append(
            findings.FixVerdict(
                e.record.path.name,
                e.n,
                findings.decision_digest(e.finding),
                f["verdict"],
                "\n".join([f["why"].strip(), *(x.strip() for x in more)]),
                e.finding.check,
                earlier_repairs.check_present(e),
            )
        )
    problem = findings.fix_verdict_problem(out)
    if problem:
        raise AuditError(problem, fix=ANSWER_AGAIN)
    return out


#: the FIX section said to be empty — `FIX lines: none — …`, `FIX: none`:
#: the auditor's own words for an area without an earlier decided BLOCKER
#: (the prompt shows it "none: no earlier decided BLOCKER in this area");
#: a section line, not a FIX entry and not a remark after the last finding
#: (task 21, 2026-10-29: two paid audits refused for it, the agent then
#: changed code and measured again instead of adopting the audited run)
FIX_NONE = re.compile(LEAD + r"\**FIX(\s+lines?)?\**\s*:\**\s*none\b", re.I)


def section_line(line: str) -> bool:
    """Does LINE open a section of a report — a FIX or READ line, the
    verdict or scope line, a code fence, the FIX section said to be empty
    (`FIX_NONE`)? Such a line ends a finding (`finding_entries`) and a FIX
    entry (`fix_block`)."""
    return bool(
        FIX_OPEN.match(line)
        or FIX_NONE.match(line)
        or READ_HINT.match(line)
        or VERDICT_LINE.match(line)
        or line.strip().startswith("scope:")
        or protocol_block.FENCE.match(line)
    )


#: the closing tally of the notes not listed at repeat cost low
#: (`notes: K (not listed — repeat cost low)`, `experiment-preflight.agent.md`):
#: a section of the report too, which ends the finding above it
NOTES_TALLY = re.compile(LEAD + r"\**notes\**\s*:\s*\d+", re.I)


def fix_block(lines: list[str], at: int) -> list[str]:
    """The lines that continue the FIX entry at LINES[AT]: every line right
    below it up to the first blank line, finding line or section line
    (`section_line`)."""
    out: list[str] = []
    for line in lines[at + 1 :]:
        if not line.strip() or FINDING.match(line) or section_line(line):
            break
        out.append(line)
    return out


def last_verdict(
    pattern: re.Pattern[str], text: str | None, said: str, kind: str
) -> re.Match[str]:
    """The LAST match of the verdict PATTERN in TEXT — the closing line an
    agent's answer is held to. Raises AuditError naming SAID ("the
    report", "the reply") and KIND ("an audit", "a review") when there is
    none. The one reading of a closing line for the audit and both
    reviewers."""
    matches = list(pattern.finditer(text or ""))
    if not matches:
        raise AuditError(
            f"{said} has no readable `verdict:` line — not {kind}", fix=ANSWER_AGAIN
        )
    return matches[-1]


def parse_clarity(text: str) -> dict:
    """{"findings": N, "wrong": M, "lines": [(rule, line)]} from the LAST
    `verdict: N findings (M would be answered wrong)` line. Raises AuditError
    when no verdict line is readable."""
    m = last_verdict(CLARITY_VERDICT, text, "the report", "a reading")
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
    """{"verdict": (blockers, warnings, notes), "findings": [(grade, text)]}
    from the LAST verdict line, the findings from the lines before it, each
    whole (`finding_entries`: its grade line and the lines that continue
    it). That the verdict counts exactly the finding lines is the writer's
    check (`findings.verdict_disagrees`). Raises AuditError when no verdict
    line is readable — quoting the auditor's `refused:` line when the
    answer is its refusal (`REFUSED`) — and where the lines after the last
    finding cannot be told apart (`finding_entries`)."""
    refusal = REFUSED.search(text or "")
    if refusal is not None and VERDICT.search(text or "") is None:
        raise AuditError(
            f"no audit — the auditor refused: {refusal.group(1)}. Nothing is recorded",
            fix="answer what it names, then run the audit again",
        )
    m = last_verdict(VERDICT, text, "the report", "an audit")
    # the lines before the verdict's own line: what stands before `verdict:`
    # on that line (a bullet, a bold mark) belongs to no finding
    body = (text or "")[: (text or "").rfind("\n", 0, m.start()) + 1]
    return {
        "verdict": (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)),
        "findings": finding_entries(body.splitlines()),
        "scope": scope_list((text or "")[m.end() :]),
    }


def finding_entries(lines: list[str]) -> list[tuple[str, str]]:
    """(grade, text) of every finding in LINES — a report's lines before its
    verdict line — in order. A finding is its grade line (FINDING) and every
    line below it up to the next finding line or section line
    (`section_line`, or the notes tally NOTES_TALLY); a blank line does not
    end it. Its text is those lines stripped, the blank ones dropped,
    joined by line breaks — the record keeps the finding whole: effect,
    rule, repair and check included (pilot round 2, t21: a WARNING stored
    as its first 136 characters). Lines before the first finding and after
    a section line belong to no finding and are not read, as before.

    Raises AuditError (ANSWER_AGAIN) on the one shape that does not read:
    an unindented line that a blank line separates from the last finding
    before a section line or the verdict — between two findings it can
    only be the first one's, after the last it may be that finding's or a
    remark on the whole audit, and a guess would put a remark in a finding
    or drop part of one. An indented line is the finding's wherever it
    stands: the auditor indented it under the finding, as it indents the
    finding's bullets (2026-10-29: two paid audits, Haiku and Sonnet,
    refused for an indented `Effect:` or `· LAB-nnn` paragraph below a
    blank line inside the last finding's evidence)."""
    entries: list[tuple[str, list[str]]] = []
    after_blank = ""  # the current finding's first line below a blank line
    blank = False
    current: list[str] | None = None
    for line in lines:
        if f := FINDING.match(line):
            current, after_blank, blank = [line.strip()], "", False
            entries.append((f.group(1), current))
        elif section_line(line) or NOTES_TALLY.match(line):
            if after_blank:
                raise _after_the_last(entries[-1][1][0], after_blank)
            current = None
        elif current is None:
            continue  # before the first finding, or after a section line
        elif not line.strip():
            blank = True
        else:
            # an indented line is the finding's, blank line or not
            if blank and not after_blank and not line[0].isspace():
                after_blank = line.strip()
            current.append(line.strip())
    if after_blank:
        raise _after_the_last(entries[-1][1][0], after_blank)
    return [(grade, "\n".join(lines_of)) for grade, lines_of in entries]


def _after_the_last(finding: str, line: str) -> AuditError:
    """The refusal of LINE, which a blank line separates from FINDING, the
    last finding before a section line or the verdict."""
    return AuditError(
        f"after the last finding, below a blank line: {finding[:120]!r} is "
        f"followed by {line[:120]!r} — that reads as the finding's or as a remark "
        f"on the whole audit, and which cannot be told; the last finding goes on "
        f"below its line without a blank line or indented, and nothing else "
        f"stands before the verdict. Nothing is recorded",
        fix=ANSWER_AGAIN,
    )


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
    stamp's, taken before the call (`audit_prompt.Stamp`). The stamp is what a later
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


#: a READ line of the auditor's report: a reading hint, printed and never
#: recorded (the record keeps what FINDING matches)
READ_HINT = re.compile(LEAD + r"\**READ\**\s*" + SEP)
