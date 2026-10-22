"""report_blocks — a report outside the protocol: its generated result blocks,
the runs it cites, the numbers it states without a source.

A report (`REPORT.md`, a results note) carries a reported number in a
generated block, written by `protocol-fill <PROTOCOL> --into <FILE>`:

    <!-- labkit result: run 2026-10-22T09-13-08_0dc3 (protocol-fill --into; edit the protocol, not this block) -->
    auc = 0.69, n = 12 (run 2026-10-22T09-13-08_0dc3)
    <!-- /labkit result -->

The body is what the protocol that declares that run as its result renders
(`result_render.rendering`): its Answer line, limits note included, and one
line per Limit (`block_body`) — the note's "Limit lines below" stand below
in the report too. What each check
here states, and no more:

- `block_gaps` (guaranteed): a block says exactly what its declaring
  protocol's rendering says. For the prose beside it nothing follows.
- `cited_gaps` (guaranteed): every token that reads as a run id
  (`runs.RUN_ID_LIKE`) names a run directory of the repo.
- `unsourced_numbers` (static evidence, never blocks): numbers outside every
  block — no source is assigned to them. A number that happens to equal a
  value of the run is named too: equal values do not show where a number
  came from, and a count or median the run never stored has no source here
  at all.

Why (labkit-paper area 09, fifth haiku round, 2026-10-22): the protocol's
Answer was held exactly, and REPORT.md at the repository root stated
"28 training samples" (the file has 44) and "median 0.449" (it is 0.284);
no gate read the file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from labkit.checks.result_render import Rendering
from labkit.formats import runs

#: the block's opening and closing lines, each a line of its own
OPEN = re.compile(r"^<!-- labkit result: run (?P<run>\S+) \(.*\) -->$")
CLOSE = "<!-- /labkit result -->"
OPEN_NOTE = "protocol-fill --into; edit the protocol, not this block"


class ReportBlockError(ValueError):
    """A block that does not read: opened and never closed, closed without
    opening, nested. The message names the line."""


@dataclass(frozen=True)
class Block:
    """One generated result block: the run it renders, where it stands (the
    opening and closing line, 1-based) and its body as written."""

    run_id: str
    first: int
    last: int
    body: str


def block_body(r: Rendering) -> str:
    """A block's body as R renders it: the Answer line, then each Limit
    line as the protocol carries it."""
    return "\n".join(
        [r.answer, *(f"- **{label}:** {value}" for label, value in r.limits)]
    )


def block_lines(run_id: str, body: str) -> list[str]:
    """The block for RUN_ID with BODY, line by line."""
    return [
        f"<!-- labkit result: run {run_id} ({OPEN_NOTE}) -->",
        *body.split("\n"),
        CLOSE,
    ]


def blocks(text: str) -> list[Block]:
    """Every generated block of TEXT in order. Raises ReportBlockError on a
    block that does not read."""
    out: list[Block] = []
    opened: tuple[str, int] | None = None
    body: list[str] = []
    for n, line in enumerate(text.split("\n"), 1):
        m = OPEN.match(line.strip())
        if m:
            if opened is not None:
                raise ReportBlockError(
                    f"line {n}: a result block opens inside the one opened at line {opened[1]}"
                )
            opened, body = (m.group("run"), n), []
        elif line.strip() == CLOSE:
            if opened is None:
                raise ReportBlockError(f"line {n}: {CLOSE} closes no result block")
            out.append(Block(opened[0], opened[1], n, "\n".join(body).strip()))
            opened = None
        elif opened is not None:
            body.append(line)
    if opened is not None:
        raise ReportBlockError(
            f"line {opened[1]}: the result block for run {opened[0]} is never closed ({CLOSE})"
        )
    return out


def write_block(text: str, run_id: str, body: str) -> str:
    """TEXT with RUN_ID's block holding BODY (`block_body`): every block of RUN_ID
    replaced in place, or one appended at the end when there is none.
    Raises ReportBlockError on a block that does not read."""
    found = [b for b in blocks(text) if b.run_id == run_id]
    lines = text.split("\n")
    new = block_lines(run_id, body)
    if not found:
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join([*lines, "", *new, ""])
    for b in reversed(found):
        lines[b.first - 1 : b.last] = new
    return "\n".join(lines)


def block_gaps(
    found: list[Block], expected: dict[str, str], why_not: dict[str, str]
) -> list[str]:
    """Why a block of FOUND does not say what its source says, one sentence
    each, or []: EXPECTED maps a run id to the body its declaring protocol
    renders (`block_body`), WHY_NOT a run id without one to the reason. Exact: equality,
    no reading of what the body says."""
    gaps: list[str] = []
    for b in found:
        want = expected.get(b.run_id)
        if want is None:
            why = why_not.get(
                b.run_id, f"no protocol of the repo declares run {b.run_id}"
            )
            gaps.append(f"line {b.first}: the result block for run {b.run_id}: {why}")
        elif b.body != want:
            gaps.append(
                f"line {b.first}: the result block for run {b.run_id} differs from the "
                f"protocol's rendering — `protocol-fill <PROTOCOL> --into <FILE>` writes it again"
            )
    return gaps


def cited_run_ids(text: str) -> list[tuple[int, str]]:
    """(line, token) of every token in TEXT that reads as a run id."""
    return [
        (n, m.group(0))
        for n, line in enumerate(text.split("\n"), 1)
        for m in runs.RUN_ID_LIKE.finditer(line)
    ]


def cited_gaps(cited: list[tuple[int, str]], known: set[str]) -> list[str]:
    """Why a cited token names no run, one sentence each: not in the shape
    runlog writes, or no `runs/<id>/` among KNOWN (the run ids of the repo)."""
    gaps: list[str] = []
    for n, token in cited:
        if not runs.RUN_ID.fullmatch(token):
            gaps.append(
                f"line {n}: {token} reads as a run id but is not one runlog writes"
            )
        elif token not in known:
            gaps.append(f"line {n}: cites run {token} — no runs/{token}/ in the repo")
    return gaps


#: what is not a stated number before the scan: comments (a block's own
#: markers), code spans (a path, a command, a key), run ids, dates, version
#: strings, URLs, hyphen-joined identifiers (a CAS number `2464-18-8`), a
#: list item's number
_NOT_A_NUMBER = re.compile(
    r"<!--.*?-->"
    r"|`[^`]*`"
    rf"|{runs.RUN_ID_LIKE.pattern}"
    r"|\b\d{4}-\d{2}-\d{2}(?:T[\d:-]+)?"
    r"|\bv?\d+\.\d+\.\d+\b"
    r"|https?://\S+"
    r"|\b\d+(?:-\d+){2,}\b"
    r"|^\s*\d+[.)]\s"
)
#: a stated number: a decimal, or an integer of two digits or more — a lone
#: digit is mostly a step, a heading or a fold count, and its hint is noise
_NUMBER = re.compile(r"(?<![\w.])-?(?:\d+[.,]\d+|\d{2,})(?![\w])")


def unsourced_numbers(text: str) -> list[tuple[int, list[str]]]:
    """(line, numbers) of every line of TEXT outside the generated blocks
    that states a number. Static evidence: a hint, never a blocker. Raises
    ReportBlockError on a block that does not read."""
    inside = {n for b in blocks(text) for n in range(b.first, b.last + 1)}
    out: list[tuple[int, list[str]]] = []
    for n, line in enumerate(text.split("\n"), 1):
        if n in inside:
            continue
        found = _NUMBER.findall(_NOT_A_NUMBER.sub(" ", line))
        if found:
            out.append((n, found))
    return out
