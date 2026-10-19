"""gate — what a gate found, told once: the blockers, the warnings, the
summary and the exit code.

Every gate that blocks (preflight, finalize, report-check, code-check,
notes-check) collects its findings here and ends with `report`: one
spelling of the grade (`BLOCKER:` / `WARNING:`), one summary line, one exit
contract — 1 with a blocker, 0 otherwise.

A finding is data first (`GateFinding`: its grade and its text — not
`findings.Finding`, an audit's finding the person decides) and a line on
the console second. `Findings` keeps the data and tells each finding, as it
is found, through one channel — `print` by default, `None` for a gate that
runs inside another gate and only wants the data (report-check's finalize
station). Headers and the notes a station prints beside its findings
(`note`, `header`) go through the same channel, so a silent gate is silent
whole; they are told, never counted. Why one collector and one channel:
docs/notes/2026-10-19-gates-and-run-start.md.

A finding that already carries its grade as a word (code-check's
`BLOCKER · <where> · …`, protocol-check's `…: WARNING: …`) goes in through
`add`, told as written and counted by that word; `block` and `warn` tell
the grade themselves.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

#: the grade a line carries as a word — the first one wins
GRADE = re.compile(r"\b(BLOCKER|WARNING)\b")
BLOCKER = "BLOCKER"
WARNING = "WARNING"


def grade_of(line: str) -> str:
    """`BLOCKER` or `WARNING`, read from the line; a line naming neither is a
    blocker — a finding nobody graded must not pass as a warning."""
    m = GRADE.search(line)
    return m.group(1) if m else BLOCKER


@dataclass(frozen=True)
class GateFinding:
    """One finding of a gate: its grade, its text (what the summary repeats),
    and whether the text already spells the grade (`add`) or the gate spells
    it (`block`, `warn`)."""

    grade: str
    text: str
    graded_by_text: bool = False

    @property
    def line(self) -> str:
        """The finding as a gate tells it, without the indent."""
        return self.text if self.graded_by_text else f"{self.grade}: {self.text}"


class Findings:
    """What the stations found, as data, and the channel they are told through.

    Every blocker is told as one line and repeated in the summary, so it is
    found at the end of a long hook output too.

    Args:
        tell: Where each line goes as it is found — `print` by default;
            `None` collects silently, for a gate run inside another gate
            (report-check's finalize station).
    """

    def __init__(self, tell: Callable[[str], None] | None = print) -> None:
        self.found: list[GateFinding] = []
        self._tell = tell

    @property
    def blocked(self) -> list[str]:
        """The blockers' texts, in the order found."""
        return [f.text for f in self.found if f.grade == BLOCKER]

    @property
    def warned(self) -> list[str]:
        """The warnings' texts, in the order found."""
        return [f.text for f in self.found if f.grade == WARNING]

    @property
    def warnings(self) -> int:
        """How many warnings stand."""
        return len(self.warned)

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
        """Keep a finding and tell it."""
        self.found.append(finding)
        self.note(f"  {finding.line}")

    def block(self, msg: str) -> None:
        """A blocker: told as `BLOCKER: msg`, repeated in the summary, exit 1."""
        self.take(GateFinding(BLOCKER, msg))

    def warn(self, msg: str) -> None:
        """A warning: told as `WARNING: msg`, counted, exit 0 on its own."""
        self.take(GateFinding(WARNING, msg))

    def add(self, line: str) -> None:
        """A finding graded by its own words (`grade_of`): told as written."""
        self.take(GateFinding(grade_of(line), line, graded_by_text=True))

    def summary(self, tool: str, before: str) -> list[str]:
        """The summary lines: with a blocker the count and every blocker named
        again, with warnings only the count, else `all clear`."""
        if self.blocked:
            return [
                f"{tool}: {len(self.blocked)} blocker(s), {self.warnings} warning(s) "
                f"— fix the blockers before {before}:",
                *(f"  - {msg}" for msg in self.blocked),
            ]
        if self.warned:
            return [
                f"{tool}: 0 blockers, {self.warnings} warning(s) — review the "
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
