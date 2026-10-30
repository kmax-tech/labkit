"""report_blocks — a report outside the protocol: its report result blocks,
its discussion blocks, the runs it cites, the numbers it states without a
source.

A separate report (`REPORT.md`, a results note) carries a reported number
in a report result block, written by `protocol-fill <PROTOCOL> --into <FILE>`:

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
- `blocks_owed` (guaranteed): a report that cites a run some protocol
  declares as its result carries that protocol's block — the number the
  report shows of it is the generated one, not a retyped one. A cited run
  no protocol declares owes no block (the gate warns: nothing is declared
  there).
- `cited_gaps` (guaranteed): every token that reads as a run id
  (`runs.RUN_ID_LIKE`) names a run directory of the repo.
- `discussions`, `discussion_gaps` (guaranteed): a run the report looks
  at without reporting it stands in a discussion block, written by
  `protocol-fill <PROTOCOL> --discuss RUN --why "…" --into <FILE>` — its
  head holds the protocol, the run and the why as TOML, its line says
  `Run <id> — discussed, not reported: <why>`. A block without its why,
  one whose line differs from its head, and a second block of the same
  protocol and run are blockers. The gate (`report_hold.promotions`)
  holds the undiscussed citation of a protocol's answering run that
  declares no result: at `low` such a report is the promotion without the
  adoption (sixth haiku round, 2026-10-23, t3 and t18: `--from-run`
  refused, REPORT.md written from metrics.json by hand, the hook warned and
  let it pass).
- A protocol handed over unresolved stands in a handover block, written
  by `protocol-fill <PROTOCOL> --handover`; its format and its check live
  in `handovers` (the stop and the commit read it), here its lines count
  as generated (`generated_lines`).
- `numbers_beside_discussed` (static evidence, never blocks): the numbers
  in a discussion block and the paragraphs around it — a discussed run's
  number in a report is a reported number unless the sentence says what
  it is.
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

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from labkit.checks.result_render import Rendering
from labkit.formats import handovers, runs
from labkit.formats.comment_blocks import (
    HEAD_END,
    CommentBlockError,
    closer,
    comment_blocks,
    opener,
    with_comment_block,
)
from labkit.formats.gate import GateFinding, blocker
from labkit.formats.protocol_block import toml_string
from labkit.formats.repo import into_command

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
    """One report result block: the protocol it belongs to (its path
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


def path_from_report(protocol: Path, report: Path) -> str:
    """PROTOCOL's path as REPORT names it: relative to the report's
    directory, `/`-separated — the block's owner as `--into` writes it and
    as the gate names it when a block is owed. Raises ValueError on a path
    with whitespace: the block's opening line holds it as one word."""
    rel = Path(os.path.relpath(protocol.resolve(), report.resolve().parent)).as_posix()
    if any(c.isspace() for c in rel):
        raise ValueError(
            f"{rel}: a protocol path with whitespace cannot name a result block"
        )
    return rel


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


def with_block(text: str, protocol: str, run_id: str, body: str) -> str:
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


def withdraw_result_blocks(text: str, protocol: Path, report: Path) -> str:
    """TEXT without the result blocks belonging to PROTOCOL in REPORT.

    Resolve each block's owner relative to REPORT, so equivalent path
    spellings name the same protocol. Preserve every line outside those
    blocks, including other protocols' blocks and prose. This transforms
    text only; it reads and writes no report. Raises ReportBlockError when
    any result block does not read.
    """
    owner = protocol.resolve()
    found = [b for b in blocks(text) if (report.parent / b.protocol).resolve() == owner]
    lines = text.split("\n")
    for b in reversed(found):
        del lines[b.first - 1 : b.last]
    return "\n".join(lines)


@dataclass(frozen=True)
class BlockSource:
    """What a block's protocol says now: the run it declares (None: no
    result declared, or no protocol there — WHY says which) and the body it
    renders for that run (None when it cannot be rendered — WHY says why)."""

    run_id: str | None
    body: str | None
    why: str = ""


def block_gaps(
    found: list[Block], sources: dict[str, BlockSource], report: Path
) -> list[GateFinding]:
    """Why a block of FOUND (in REPORT) does not show what its protocol says
    now, one blocker each with its way out, or []: SOURCES maps each block's protocol (as
    written) to its `BlockSource`; the command that writes it again names
    protocol and report as the working directory reaches them
    (`repo.into_command`). Exact: the declared run and equality of the
    body, no reading of what the body says."""
    gaps: list[GateFinding] = []
    for b in found:
        s = sources[b.protocol]
        at = f"line {b.first}: the result block of {b.protocol} (run {b.run_id})"
        into = f"`{into_command(report.parent / b.protocol, report)}`"
        if s.run_id is None:
            gaps.append(
                blocker(
                    f"{at}: {s.why} — a block shows an adopted result only",
                    fix="remove it, or adopt a run in the protocol (`--from-run`) "
                    "and write it again",
                )
            )
        elif s.run_id != b.run_id:
            gaps.append(
                blocker(
                    f"{at}: the protocol has adopted run {s.run_id} now",
                    fix=f"{into} replaces the block",
                )
            )
        elif s.body is None:
            gaps.append(
                blocker(
                    f"{at}: {s.why}",
                    fix=f"repair what the sentence names in the protocol, then "
                    f"{into} writes the block again",
                )
            )
        elif b.body != s.body:
            gaps.append(
                blocker(
                    f"{at} differs from the protocol's rendering",
                    fix=f"{into} writes it again",
                )
            )
    return gaps


def blocks_owed(
    cited: list[tuple[int, str]],
    declaring: dict[str, list[str]],
    present: set[str],
) -> list[tuple[int, str, str]]:
    """(line, run id, protocol) for every cited run (CITED: `cited_run_ids`)
    that a protocol declares as its result (DECLARING: run id → the
    protocols, each as the report names it) and whose block the report
    does not carry (PRESENT: the protocols of its blocks, as written) —
    each protocol once, at the first line citing one of its runs. Why
    (fifth haiku round, 2026-10-22): all three labkit reports retyped the
    declared number in prose, and 0.103.0 only warned."""
    out: list[tuple[int, str, str]] = []
    named: set[str] = set()
    for n, run_id in cited:
        for protocol in declaring.get(run_id, []):
            if protocol in present or protocol in named:
                continue
            named.add(protocol)
            out.append((n, run_id, protocol))
    return out


def cited_run_ids(text: str) -> list[tuple[int, str]]:
    """(line, token) of every token in TEXT that reads as a run id."""
    return [
        (n, m.group(0))
        for n, line in enumerate(text.split("\n"), 1)
        for m in runs.RUN_ID_LIKE.finditer(line)
    ]


def cited_gaps(cited: list[tuple[int, str]], known: set[str]) -> list[GateFinding]:
    """Why a cited token names no run, one blocker each with its way out: not
    in the shape runlog writes, or no `runs/<id>/` among KNOWN (the run ids
    of the repo)."""
    gaps: list[GateFinding] = []
    for n, token in cited:
        if not runs.RUN_ID.fullmatch(token):
            gaps.append(
                blocker(
                    f"line {n}: {token} reads as a run id but is not one runlog writes",
                    fix="cite a run by the id runlog wrote (its `runs/<id>/`), "
                    "or reword the token",
                )
            )
        elif token not in known:
            gaps.append(
                blocker(
                    f"line {n}: cites run {token} — no runs/{token}/ in the repo",
                    fix="cite a run the repo holds: a run that is gone reports no number",
                )
            )
    return gaps


#: a run the report discusses without reporting it: a generated block whose
#: head is TOML inside the opening comment — the one place the protocol,
#: the run and the why are kept — and whose body is the line the reader
#: sees, written from the head (`discussion_body`):
#:
#:     <!-- labkit discussed
#:     protocol = "experiments/01-x/PROTOCOL-x.md"
#:     run = "2026-10-26T08-18-33_7392"
#:     why = "adoption refused — target leakage through G_VRH"
#:     -->
#:     Run 2026-10-26T08-18-33_7392 — discussed, not reported: adoption refused — target leakage through G_VRH
#:     <!-- /labkit discussed -->
#:
#: The why is the report of what stopped the number, on the page beside it.
#: A false one ("not reported" beside a number read as the result) is a
#: sentence the report review reads — the gate's blind spot moved onto the
#: page. Not a prose pattern: a marker the gate reads out of prose fell
#: apart on the first backtick around the id (eighth haiku round, t3;
#: docs/notes/2026-10-26-report-run-citations.md).
DISCUSSED = "discussed"
DISCUSS_OPEN = opener(DISCUSSED)
DISCUSS_HEAD_END = HEAD_END
DISCUSS_CLOSE = closer(DISCUSSED)
DISCUSS_KEYS = ("protocol", "run", "why")


def discuss_command(protocol: str, run_id: str, report: str) -> str:
    """The `protocol-fill … --discuss` line that writes the block
    discussing RUN_ID of PROTOCOL into REPORT, each path as the caller
    names it."""
    return (
        f'protocol-fill {protocol} --discuss {run_id} --why "<what refused the '
        f'adoption, what you found>" --into {report}'
    )


@dataclass(frozen=True)
class Discussion:
    """One discussion block: the PROTOCOL (its path relative to the report,
    as written), the RUN_ID, the WHY as written, where it stands (FIRST the
    opening line, LAST the closing one, 1-based), its BODY as written."""

    protocol: str
    run_id: str
    why: str
    first: int
    last: int
    body: str


def discussion_body(run_id: str, why: str) -> str:
    """The line a discussion block of RUN_ID with WHY shows."""
    return f"Run {run_id} — {DISCUSSED}, not reported: {why}"


def discussion_lines(protocol: str, run_id: str, why: str) -> list[str]:
    """The block discussing RUN_ID of PROTOCOL with WHY, line by line; the
    head's strings written by `protocol_block.toml_string`. Raises
    ValueError on a why that cannot stand in the block — empty, more than
    one line (`\\n` or `\\r`), holding `-->` (it would close the comment) —
    and on a lone surrogate in any of the three (no TOML string holds one),
    the message naming the field."""
    why = why.strip()
    if not why:
        raise ValueError(
            "--why is empty — say what refused the adoption and what was found"
        )
    # the why stands raw in the block's line; a report read in text mode
    # turns a lone \r into a line break, and the line no longer equals its head
    if "\n" in why or "\r" in why or DISCUSS_HEAD_END in why:
        raise ValueError(
            f"--why {why!r}: one line, without {DISCUSS_HEAD_END!r} (it closes the "
            f"block's head)"
        )
    head = [DISCUSS_OPEN]
    for key, value, field in (
        ("protocol", protocol, "the protocol path"),
        ("run", run_id, "the run id"),
        ("why", why, "--why"),
    ):
        try:
            head.append(f"{key} = {toml_string(value)}")
        except ValueError as exc:
            raise ValueError(f"{field}: {exc}") from exc
    return [*head, DISCUSS_HEAD_END, discussion_body(run_id, why), DISCUSS_CLOSE]


def _discussion_head(head: list[str], at: int) -> tuple[str, str, str]:
    """(protocol, run, why) of the TOML HEAD of the block opened at line AT.
    Raises ReportBlockError on TOML that does not read, a missing or
    unknown key, or a value that is not a string."""
    try:
        data = tomllib.loads("\n".join(head))
    except tomllib.TOMLDecodeError as exc:
        raise ReportBlockError(
            f"line {at}: the discussion block's head is not TOML: {exc}"
        ) from exc
    missing = [k for k in DISCUSS_KEYS if k not in data]
    unknown = sorted(set(data) - set(DISCUSS_KEYS))
    if missing or unknown:
        raise ReportBlockError(
            f"line {at}: the discussion block's head holds "
            f"{', '.join(DISCUSS_KEYS)}"
            + (f" — missing {', '.join(missing)}" if missing else "")
            + (f" — unknown {', '.join(unknown)}" if unknown else "")
        )
    bad = [k for k in DISCUSS_KEYS if not isinstance(data[k], str)]
    if bad:
        raise ReportBlockError(
            f"line {at}: the discussion block's {', '.join(bad)} must be a string"
        )
    return data["protocol"], data["run"], data["why"]


def discussions(text: str) -> list[Discussion]:
    """Every discussion block of TEXT in order (`comment_blocks`). Raises
    ReportBlockError on a block that does not read: never closed, closed
    without opening, nested, or a head that is not the three keys."""
    try:
        found = comment_blocks(
            text, DISCUSSED, "discussion block", check_head=_discussion_head
        )
    except CommentBlockError as exc:
        raise ReportBlockError(str(exc)) from exc
    return [
        Discussion(
            *_discussion_head(b.head, b.first),
            b.first,
            b.last,
            "\n".join(b.body).strip(),
        )
        for b in found
    ]


def with_discussion(text: str, protocol: str, run_id: str, why: str) -> str:
    """TEXT with the block discussing RUN_ID of PROTOCOL with WHY: the one
    block of that protocol and run replaced in place, or one appended at
    the end; other discussions stay (`with_comment_block`). Raises
    ReportBlockError on a block that does not read or on two blocks of the
    same protocol and run (the gate names that too), ValueError on a why
    that cannot stand (`discussion_lines`)."""
    new = discussion_lines(protocol, run_id, why)
    matching = {
        d.first
        for d in discussions(text)
        if (d.protocol, d.run_id) == (protocol, run_id)
    }
    try:
        return with_comment_block(
            text,
            new,
            comment_blocks(text, DISCUSSED, "discussion block"),
            lambda b: b.first in matching,
            lambda same: (
                f"run {run_id} of {protocol} is discussed in {len(same)} blocks "
                f"(lines {', '.join(str(b.first) for b in same)}) — remove all "
                f"but one, then write it again"
            ),
        )
    except CommentBlockError as exc:
        raise ReportBlockError(str(exc)) from exc


def discussion_gaps(found: list[Discussion]) -> list[GateFinding]:
    """Why a block of FOUND does not say what it holds, one blocker each with
    its way out:
    an empty why (it is the report of what stopped the number), a body
    that differs from the line its head writes, two blocks of the same
    protocol and run. Exact, on the text alone."""
    gaps: list[GateFinding] = []
    seen: dict[tuple[str, str], int] = {}
    for d in found:
        at = f"line {d.first}: the discussion of run {d.run_id} ({d.protocol})"
        key = (d.protocol, d.run_id)
        if key in seen:
            gaps.append(
                blocker(
                    f"{at} repeats the block at line {seen[key]} — one block per "
                    f"protocol and run",
                    fix="remove one",
                )
            )
        else:
            seen[key] = d.first
        if not d.why.strip():
            gaps.append(
                blocker(
                    f"{at} has no why",
                    fix=f"say what refused the adoption and what was found: "
                    f"`{discuss_command('<PROTOCOL>', d.run_id, '<FILE>')}`",
                )
            )
        elif d.body != discussion_body(d.run_id, d.why.strip()):
            gaps.append(
                blocker(
                    f"{at}: its line differs from its head",
                    fix=f"edit the head with `protocol-fill … --discuss {d.run_id} "
                    f"--why … --into <FILE>`, not the line",
                )
            )
    return gaps


def numbers_beside_discussed(
    text: str, found: list[Discussion]
) -> list[tuple[int, list[str]]]:
    """(line, numbers) of every line that states a number in a discussion
    block of FOUND (its line, the why included) or in the paragraph right
    above or below it — the non-blank lines up to a blank line or another
    generated block. Static evidence: a hint at a discussed run's number
    presented in a report, never a blocker."""
    lines = text.split("\n")
    inside = generated_lines(text)

    def in_paragraph(n: int) -> bool:
        return 1 <= n <= len(lines) and bool(lines[n - 1].strip()) and n not in inside

    wanted: set[int] = set()
    for d in found:
        wanted.update(range(d.first, d.last + 1))
        lo = d.first
        while in_paragraph(lo - 1):
            lo -= 1
        hi = d.last
        while in_paragraph(hi + 1):
            hi += 1
        wanted.update(range(lo, hi + 1))
    out: list[tuple[int, list[str]]] = []
    for n in sorted(wanted):
        numbers = _numbers_in(lines[n - 1])
        if numbers and not _discussion_head_line(lines[n - 1]):
            out.append((n, numbers))
    return out


def generated_lines(text: str) -> set[int]:
    """The line numbers of TEXT inside a result block, a discussion block or
    a handover block (`handovers.blocks`), the opening and closing lines
    included. Raises ReportBlockError on a block that does not read."""
    spans = [(b.first, b.last) for b in blocks(text)]
    spans += [(d.first, d.last) for d in discussions(text)]
    try:
        spans += [(h.first, h.last) for h in handovers.handover_blocks(text)]
    except handovers.HandoverError as exc:
        raise ReportBlockError(str(exc)) from exc
    return {n for first, last in spans for n in range(first, last + 1)}


def _discussion_head_line(line: str) -> bool:
    """Is LINE a key of a discussion block's head (its numbers are the
    block's data, shown again on its line)?"""
    return line.split("=", 1)[0].strip() in DISCUSS_KEYS and "=" in line


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


def _numbers_in(line: str) -> list[str]:
    """The stated numbers of LINE (`_NUMBER` after `_NOT_A_NUMBER`)."""
    return _NUMBER.findall(_NOT_A_NUMBER.sub(" ", line))


def unsourced_numbers(text: str) -> list[tuple[int, list[str]]]:
    """(line, numbers) of every line of TEXT outside the generated blocks
    (result and discussion blocks) that states a number. Static evidence: a
    hint, never a blocker. Raises ReportBlockError on a block that does not
    read."""
    inside = generated_lines(text)
    out: list[tuple[int, list[str]]] = []
    for n, line in enumerate(text.split("\n"), 1):
        if n in inside:
            continue
        found = _numbers_in(line)
        if found:
            out.append((n, found))
    return out
