"""gate — what a gate found, told once: the blockers, the warnings, the
summary and the exit code.

Every gate that blocks (preflight, finalize, report-check, code-check,
notes-check) collects its findings here and ends with `report`: one
spelling of the grade (`BLOCKER:` / `WARNING:`), one summary line, one exit
contract — 1 with a blocker, 0 otherwise. Until 0.96.0 five gates spelled
this five ways (a dataclass, two counters with inline prints, graded
strings counted by `startswith` — and preflight counted code-check's
strings a second time), and three spellings of the grade (audit 2026-10-15).

A finding that already carries its grade as a word (code-check's
`BLOCKER · <where> · …`, protocol-check's `…: WARNING: …`) goes in through
`add`, printed as written and counted by that word; `block` and `warn`
print the grade themselves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: the grade a line carries as a word — the first one wins
GRADE = re.compile(r"\b(BLOCKER|WARNING)\b")


def grade_of(line: str) -> str:
    """`BLOCKER` or `WARNING`, read from the line; a line naming neither is a
    blocker — a finding nobody graded must not pass as a warning."""
    m = GRADE.search(line)
    return m.group(1) if m else "BLOCKER"


@dataclass
class Findings:
    """What the stations found: every blocker as one line, repeated in the
    summary — inside a commit hook the sections run to 20 lines and the one
    blocker drowned in the middle (usability probe 2026-10-07)."""

    blocked: list[str] = field(default_factory=list)
    warned: list[str] = field(default_factory=list)

    @property
    def warnings(self) -> int:
        """How many warnings stand."""
        return len(self.warned)

    def block(self, msg: str) -> None:
        """Print a blocker and keep it for the summary."""
        print(f"  BLOCKER: {msg}")
        self.blocked.append(msg)

    def warn(self, msg: str) -> None:
        """Print a warning and keep it for the summary."""
        print(f"  WARNING: {msg}")
        self.warned.append(msg)

    def add(self, line: str) -> None:
        """A finding graded by its own words (`grade_of`): printed as written."""
        print(f"  {line}")
        (self.blocked if grade_of(line) == "BLOCKER" else self.warned).append(line)

    def report(self, tool: str, before: str) -> int:
        """The summary line and the exit code: 1 with a blocker (each one
        named again), 0 with warnings only or all clear."""
        print()
        if self.blocked:
            print(
                f"{tool}: {len(self.blocked)} blocker(s), {self.warnings} warning(s) "
                f"— fix the blockers before {before}:"
            )
            for msg in self.blocked:
                print(f"  - {msg}")
            return 1
        if self.warned:
            print(
                f"{tool}: 0 blockers, {self.warnings} warning(s) — review the "
                f"warnings above before {before}."
            )
            return 0
        print(f"{tool}: all clear.")
        return 0
