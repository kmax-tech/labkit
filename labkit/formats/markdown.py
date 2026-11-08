"""markdown — the structure of a Markdown file labkit reads: its fenced
blocks and its `## ` sections.

The one fence walker (`fence_spans`) and the one cut into sections
(`section_starts`), outside every fence: a `## ` line or a ``` inside a
fence is body. Protocols (`protocol_block`), reports, rules and the
stamped skeletons are read through them. Pure: text in, indexes out.
"""

from __future__ import annotations

import re

#: the opening line of a fenced block: indent, the marker (``` or ~~~, at
#: least three), the info string
FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w+-]*)")


def fence_spans(lines: list[str]) -> list[tuple[str, int, int]]:
    """(info string, first body line, line after the body) of every
    top-level fenced block, as 0-based indexes into LINES — the one fence
    walker; `fenced_blocks` is its text form, and the readers that need a
    place (the head's line, the Prompt block to replace) use the spans.
    A fence inside another fence is body, not a block: a verbatim prompt
    that asks the model for ```toml output is no second head. A fence
    closes with the same character, at least as long,
    and nothing after it; an unclosed fence runs to the end."""
    out: list[tuple[str, int, int]] = []
    i = 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m:
            i += 1
            continue
        marker, info = m.group(2), m.group(3).lower()
        start = i + 1
        i = start
        while i < len(lines) and not closes(lines[i], marker):
            i += 1
        out.append((info, start, i))
        i += 1
    return out


def closes(line: str, marker: str) -> bool:
    """Does `line` close a fence opened with `marker`?"""
    s = line.strip()
    return bool(s) and set(s) == {marker[0]} and len(s) >= len(marker)


def section_starts(lines: list[str]) -> list[int]:
    """The 0-based indexes of the `## ` headings of LINES — outside
    every fence (`fenced_lines`), in order. The one cut into sections for
    the prose count, the Runs list, the low cut and the stamp's blank-line
    pass: a `## ` line inside a fence is no heading."""
    fenced = fenced_lines(lines)
    return [
        i
        for i, line in enumerate(lines)
        if i not in fenced and line.lstrip().startswith("## ")
    ]


def section_end(lines: list[str], start: int) -> int:
    """The index of the first line after the section opening at START: the
    next heading's, or `len(lines)`."""
    return next((i for i in section_starts(lines) if i > start), len(lines))


def fenced_lines(lines: list[str]) -> set[int]:
    """The 0-based indexes of every line a fence takes — its markers and its
    body, by `fence_spans`. For a reader that walks lines and must skip the
    fenced ones (a prose count, a label search, a rule scan). A flag
    toggled on ``` by hand would turn prose into code at a `~~~` fence or a
    ``` nested in a fence, where the protocol parser reads it right."""
    out: set[int] = set()
    for _, start, end in fence_spans(lines):
        out.update(range(start - 1, min(end + 1, len(lines))))
    return out


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    """(info string, body) of every top-level fenced block (`fence_spans`)."""
    lines = text.splitlines()
    return [
        (info, "\n".join(lines[start:end]) + "\n")
        for info, start, end in fence_spans(lines)
    ]
