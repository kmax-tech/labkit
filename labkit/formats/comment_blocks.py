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
scanner and one in-place writer for both, so the two kinds cannot drift
apart. A block inside a closed fenced code block outside every block
(`example_lines`) is an example the document shows and is not read; a
fence no closing line follows hides nothing.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from labkit.formats.markdown import fence_end

HEAD_END = "-->"

#: the opening line of any labkit block — a result block
#: (`<!-- labkit result: …`) as well as a comment block of every KIND
BLOCK_OPEN = re.compile(r"^<!-- labkit (?P<kind>[\w-]+)")


class CommentBlockError(ValueError):
    """A block of a report that does not read; the message names the line."""


def opener(kind: str) -> str:
    """The line that opens a block of KIND."""
    return f"<!-- labkit {kind}"


def closer(kind: str) -> str:
    """The line that closes a block of KIND."""
    return f"<!-- /labkit {kind} -->"


def block_end(lines: list[str], i: int) -> int | None:
    """The index of the line closing the labkit block LINES[I] opens
    (`BLOCK_OPEN`, closed by `closer` of its kind), or None when LINES[I]
    opens none or no closing line follows. A block reader decides whether
    an opening line reads; this walk only needs where a block ends."""
    m = BLOCK_OPEN.match(lines[i].strip())
    if not m:
        return None
    close = closer(m.group("kind"))
    j = i + 1
    while j < len(lines) and lines[j].strip() != close:
        j += 1
    return j if j < len(lines) else None


def example_fences(lines: list[str]) -> list[tuple[int, int]]:
    """(opening, closing) line, 0-based, of every closed fenced code block
    of LINES that stands outside every labkit block — where a document
    shows an example. The one walk that tells an example from a block, for
    every block reader. Inside a block a fence line is body: a ``` left
    open in a block's body opens no fence that would run past its closing
    line and hide the real blocks after it. An opening line no closing
    line follows starts no block here, so it hides no example after it
    (the block readers refuse it). A fence no closing line follows hides
    nothing: by Markdown's rule it runs to the end, and a reader that
    skipped it would lose every block after it. A stray fence line that a
    later bare fence line closes does make what lies between an example,
    real blocks too, as Markdown renders it — without a message. A fence inside a blockquote (`> ````) is
    not seen; the lines shown in it carry `> ` too, so no block reader
    takes one of them for a block line."""
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        end = block_end(lines, i)
        if end is None:
            end = fence_end(lines, i)
            if end is not None:
                out.append((i, end))
        i = (end if end is not None else i) + 1
    return out


def refuse_misread_openers(
    lines: list[str], shown: set[int], kind: str, name: str
) -> None:
    """Raise CommentBlockError at the first line of LINES outside the
    examples SHOWN (`example_lines`) that starts a block of KIND
    (`BLOCK_OPEN`) but is not its opening line alone: the walk for
    examples takes it for a block, the reader would pass it by. NAME is
    how the sentence calls the block."""
    for i, raw in enumerate(lines):
        line = raw.strip()
        m = BLOCK_OPEN.match(line)
        if i not in shown and m and m.group("kind") == kind and line != opener(kind):
            raise CommentBlockError(
                f"line {i + 1}: a {name} opens with {opener(kind)} alone on its line"
            )


def example_lines(lines: list[str]) -> set[int]:
    """The 0-based indexes of every line of an example code block of LINES
    (`example_fences`), its fence lines included."""
    return {i for first, last in example_fences(lines) for i in range(first, last + 1)}


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
    it ("discussion block"). An opening or closing line inside a closed
    fenced code block outside every block is no marker (an example shown,
    `example_lines`).
    CHECK_HEAD(head lines, opening line) runs on each head as soon as it is
    read, before the body — its own error then comes first.

    Raises CommentBlockError naming the line on an opening line of KIND
    with more on it, a closing line without an opening one, a head never closed by `-->` on a line of its
    own, a block opening inside another, a block never closed."""
    open_, close = opener(kind), closer(kind)
    out: list[CommentBlock] = []
    lines = text.split("\n")
    shown = example_lines(lines)
    refuse_misread_openers(lines, shown, kind, name)
    n = 0
    while n < len(lines):
        line = lines[n].strip()
        n += 1
        if n - 1 in shown or line not in (open_, close):
            continue
        if line == close:
            raise CommentBlockError(f"line {n}: {close} closes no {name}")
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
