"""comment_blocks — the generated blocks a report carries as HTML comments.

A block of KIND opens with `<!-- labkit KIND` on a line of its own, holds
a TOML head up to `-->`, then its body, and closes with `<!-- /labkit
KIND -->`:

    <!-- labkit discussed
    protocol = "experiments/01-x/PROTOCOL-x.md"
    run = "2026-10-27T10-00-00_ab12"
    why = "…"
    -->
    Run 2026-10-27T10-00-00_ab12 — discussed, not reported: …
    <!-- /labkit discussed -->

The discussion block (`checks.report_blocks`) and the handover block
(`handovers`) are its kinds; each reads and checks its own head. One
scanner and one in-place writer: the handover block was a near copy of the
discussion block's, and the two had already diverged (audit 2026-10-27,
third, S1).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

HEAD_END = "-->"


class CommentBlockError(ValueError):
    """A block of a report that does not read; the message names the line."""


def opener(kind: str) -> str:
    """The line that opens a block of KIND."""
    return f"<!-- labkit {kind}"


def closer(kind: str) -> str:
    """The line that closes a block of KIND."""
    return f"<!-- /labkit {kind} -->"


@dataclass(frozen=True)
class CommentBlock:
    """One block as it stands: its HEAD lines (between the opening line and
    `-->`), its BODY lines (between `-->` and the closing line), FIRST the
    opening and LAST the closing line (1-based), LINES from opening to
    closing."""

    head: list[str]
    body: list[str]
    first: int
    last: int
    lines: list[str]


def comment_blocks(
    text: str,
    kind: str,
    name: str,
    check_head: Callable[[list[str], int], object] | None = None,
) -> list[CommentBlock]:
    """Every block of KIND in TEXT, in order; NAME is how a sentence calls
    it ("discussion block"). CHECK_HEAD(head lines, opening line) runs on
    each head as soon as it is read, before the body — its own error then
    comes first. Raises CommentBlockError naming the line on a closing line
    without an opening one, a head never closed by `-->` on a line of its
    own, a block opening inside another, a block never closed."""
    open_, close = opener(kind), closer(kind)
    out: list[CommentBlock] = []
    lines = text.split("\n")
    n = 0
    while n < len(lines):
        line = lines[n].strip()
        n += 1
        if line == close:
            raise CommentBlockError(f"line {n}: {close} closes no {name}")
        if line != open_:
            continue
        first = n
        while n < len(lines) and lines[n].strip() not in (HEAD_END, open_, close):
            n += 1
        if n >= len(lines) or lines[n].strip() != HEAD_END:
            raise CommentBlockError(
                f"line {first}: the {name}'s head is never closed "
                f"({HEAD_END} on a line of its own)"
            )
        head = lines[first:n]
        if check_head is not None:
            check_head(head, first)
        n += 1
        start = n
        while n < len(lines) and lines[n].strip() != close:
            if lines[n].strip() == open_:
                raise CommentBlockError(
                    f"line {n + 1}: a {name} opens inside the one opened at line "
                    f"{first}"
                )
            n += 1
        if n >= len(lines):
            raise CommentBlockError(
                f"line {first}: the {name} opened there is never closed ({close})"
            )
        body = lines[start:n]
        n += 1
        out.append(CommentBlock(head, body, first, n, lines[first - 1 : n]))
    return out


def with_comment_block(
    text: str,
    new: list[str],
    found: list[CommentBlock],
    same: Callable[[CommentBlock], bool],
    twice: Callable[[list[CommentBlock]], str],
) -> str:
    """TEXT with the block NEW (its lines, opening to closing): the one of
    FOUND (TEXT's blocks of that kind) for which SAME holds replaced in
    place, or NEW appended at the end after one blank line; every other
    line stays. Raises CommentBlockError with TWICE(the matches) when more
    than one matches."""
    matches = [b for b in found if same(b)]
    if len(matches) > 1:
        raise CommentBlockError(twice(matches))
    lines = text.split("\n")
    if not matches:
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join([*lines, "", *new, ""])
    (b,) = matches
    lines[b.first - 1 : b.last] = new
    return "\n".join(lines)
