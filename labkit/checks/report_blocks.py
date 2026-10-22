"""report_blocks — a report outside the protocol: its generated result blocks,
the runs it cites, the numbers it states without a source.

A report (`REPORT.md`, a results note) carries a reported number in a
generated block, written by `protocol-fill <PROTOCOL> --into <FILE>`:

    <!-- labkit result: experiments/01-x/PROTOCOL-x.md run 2026-10-22T09-13-08_0dc3 (protocol-fill --into; edit the protocol, not this block) -->
    auc = 0.69, n = 12 (run 2026-10-22T09-13-08_0dc3)
    <!-- /labkit result -->

The opening line names the protocol the block belongs to — its path
relative to the report, without spaces — and the run it shows. The body is
what that protocol, declaring that run as its result, renders
(`result_render.rendering`): its Recorded results line, limits note included, and one
line per Limit (`block_body`) — the note's "Limit lines below" stand below
in the report too. What each check
here states, and no more:

- `block_gaps` (guaranteed): a block shows the run its protocol declares
  now and says exactly what the protocol renders for it. For the prose
  beside it nothing follows. A new run adopted by the protocol makes the
  block stale, and `--into` replaces every block of that protocol.
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
OPEN = re.compile(
    r"^<!-- labkit result: (?P<protocol>\S+) run (?P<run>\S+) \(.*\) -->$"
)
CLOSE = "<!-- /labkit result -->"
OPEN_NOTE = "protocol-fill --into; edit the protocol, not this block"


class ReportBlockError(ValueError):
    """A block that does not read: opened and never closed, closed without
    opening, nested. The message names the line."""


@dataclass(frozen=True)
class Block:
    """One generated result block: the protocol it belongs to (its path
    relative to the report, as written), the run it shows, where it stands
    (the opening and closing line, 1-based) and its body as written."""

    protocol: str
    run_id: str
    first: int
    last: int
    body: str


def block_body(r: Rendering) -> str:
    """A block's body as R renders it: the Recorded results line, then each Limit
    line as the protocol carries it."""
    return "\n".join(
        [r.recorded_results, *(f"- **{label}:** {value}" for label, value in r.limits)]
    )


def block_lines(protocol: str, run_id: str, body: str) -> list[str]:
    """PROTOCOL's block showing RUN_ID with BODY, line by line."""
    return [
        f"<!-- labkit result: {protocol} run {run_id} ({OPEN_NOTE}) -->",
        *body.split("\n"),
        CLOSE,
    ]


def blocks(text: str) -> list[Block]:
    """Every generated block of TEXT in order. Raises ReportBlockError on a
    block that does not read."""
    out: list[Block] = []
    opened: tuple[str, str, int] | None = None
    body: list[str] = []
    for n, line in enumerate(text.split("\n"), 1):
        m = OPEN.match(line.strip())
        if m:
            if opened is not None:
                raise ReportBlockError(
                    f"line {n}: a result block opens inside the one opened at line {opened[2]}"
                )
            opened, body = (m.group("protocol"), m.group("run"), n), []
        elif line.strip() == CLOSE:
            if opened is None:
                raise ReportBlockError(f"line {n}: {CLOSE} closes no result block")
            out.append(Block(*opened, n, "\n".join(body).strip()))
            opened = None
        elif opened is not None:
            body.append(line)
    if opened is not None:
        raise ReportBlockError(
            f"line {opened[2]}: the result block for run {opened[1]} is never closed ({CLOSE})"
        )
    return out


def write_block(text: str, protocol: str, run_id: str, body: str) -> str:
    """TEXT with PROTOCOL's block showing RUN_ID with BODY (`block_body`):
    every block of PROTOCOL replaced in place, whichever run it showed — a
    newly adopted run replaces the old one —, or one appended at the end
    when there is none. Raises ReportBlockError on a block that does not
    read."""
    found = [b for b in blocks(text) if b.protocol == protocol]
    lines = text.split("\n")
    new = block_lines(protocol, run_id, body)
    if not found:
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join([*lines, "", *new, ""])
    for b in reversed(found):
        lines[b.first - 1 : b.last] = new
    return "\n".join(lines)


@dataclass(frozen=True)
class BlockSource:
    """What a block's protocol says now: the run it declares (None: no
    result declared, or no protocol there — WHY says which) and the body it
    renders for that run (None when it cannot be rendered — WHY says why)."""

    run_id: str | None
    body: str | None
    why: str = ""


def block_gaps(found: list[Block], sources: dict[str, BlockSource]) -> list[str]:
    """Why a block of FOUND does not show what its protocol says now, one
    sentence each, or []: SOURCES maps each block's protocol (as written)
    to its `BlockSource`. Exact: the declared run and equality of the body, no
    reading of what the body says."""
    gaps: list[str] = []
    for b in found:
        s = sources[b.protocol]
        at = f"line {b.first}: the result block of {b.protocol} (run {b.run_id})"
        if s.run_id is None:
            gaps.append(
                f"{at}: {s.why} — a block shows a declared result only; remove it, "
                f"or adopt a run in the protocol (`--from-run`) and write it again"
            )
        elif s.run_id != b.run_id:
            gaps.append(
                f"{at}: the protocol declares run {s.run_id} now — "
                f"`protocol-fill {b.protocol} --into <FILE>` replaces the block"
            )
        elif s.body is None:
            gaps.append(f"{at}: {s.why}")
        elif b.body != s.body:
            gaps.append(
                f"{at} differs from the protocol's rendering — "
                f"`protocol-fill {b.protocol} --into <FILE>` writes it again"
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
