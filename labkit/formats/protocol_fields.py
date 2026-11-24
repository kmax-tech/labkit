"""protocol_fields — the labelled field lines of a protocol's prose, as
written: `- **<label>:** <value>` with the lines that continue the value.

The line grammar alone (`labelled_fields`, `LabelledField`), the label
normalised for comparison (`field_name`) and the value of the one field a
label names (`named_value`). It reads no template and knows no catalogue:
which fields a protocol owes, whether one is filled or still a stamp's
placeholder, and what stands below a label are `protocol_check`'s
(`protocol_check.fields`, `FieldLine`), built on these lines. Pure.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass

from labkit.formats import markdown

#: a bold field label opening a line: `- **Label (gloss) †:** value`
_BULLET = r"^\s*(?:[-*]\s+|\d+[.)]\s+)?"  # `- `, `* `, `1. `, `1) ` or none
_FIELD_OPEN = re.compile(
    _BULLET + r"\*\*(?P<label>[^*]+?)(?::\*\*|\*\*\s*:)(?P<value>.*)$"
)
#: the lead of a field's label line, its indent and list marker
#: (`protocol_edit` keeps it when it rewrites the line)
FIELD_LEAD = re.compile(_BULLET)
HTML_COMMENT = re.compile(r"<!--.*?-->")

#: the one label a core reader names: the area stamp of a confirmation
#: follows this field of the exploration it names
#: (`exploration_state.named_state`). The catalogue lists it among the
#: fields a protocol owes (`protocol_check.FIELDS`).
CONCLUSION_LABEL = "Conclusion"
#: the field that holds the prompts verbatim: a derived run that declares
#: its answer reading is held to it as its parent's text held it
#: (`run_record_check.answer_reading_gaps`)
PROMPT_LABEL = "Prompt (verbatim, per variant)"


def field_name(label: str) -> str:
    """`Prompt (verbatim, per variant)` → `prompt`; `Free knobs †` → `free knobs`."""
    return label.split("(")[0].replace("†", "").strip().casefold()


@dataclass(frozen=True)
class LabelledField:
    """One labelled field of a protocol's prose as written — not
    `protocol_check.FieldLine`, which adds whether it is filled."""

    line: int  # 1-based line of the label
    name: str  # field_name() of the label
    label: str  # the label as written
    value: str  # the value with its continuation lines, HTML comments removed
    last: int  # 1-based last line of the value


def _continues(line: str, own: int) -> bool:
    """Does LINE, below a field opened at indent OWN, continue its value? A
    plain indented line does; a list item does when it sits deeper than the
    field's own line and opens no field of its own."""
    item = re.match(r"\s*(?:[-*]\s+|\d+[.)]\s)", line)
    if item is None:
        return True
    return len(line) - len(line.lstrip()) > own and not _FIELD_OPEN.match(line)


def _continuation(lines: list[str], start: int, own: int) -> tuple[list[str], int]:
    """(the lines that continue a field's value, the index after the last),
    from the 0-based index START below a label line at indent OWN, each
    without its list marker.

    The value runs on over indented continuation lines: a bare
    `- **Label:**` with the text below is written, not empty (reading the
    first line only, the registration gate would refuse a written
    registration). Sub-bullets deeper than the field's own line are its
    value too, as the placeholder rule already counts them: read as nothing,
    a Data / scope written as a list would compare empty in the scope hold
    and hide its source digest. A deeper line that opens a field of its own
    (`- **registered:**`) ends it."""
    parts: list[str] = []
    nxt = start
    while (
        nxt < len(lines)
        and lines[nxt].startswith((" ", "\t"))
        and lines[nxt].strip()
        and not markdown.FENCE.match(lines[nxt])
        and _continues(lines[nxt], own)
    ):
        parts.append(re.sub(_BULLET, "", lines[nxt]).strip())
        nxt += 1
    return parts, nxt


@functools.lru_cache(maxsize=64)
def labelled_fields(text: str) -> tuple[LabelledField, ...]:
    """Every bold field label in the prose of TEXT with its value, outside
    code fences and multi-line HTML comments, in the order written. A label
    may wrap onto the next line (`- **Resolution check (ZERO calls, …\n
    extremes):** <…>`); it is read whole. Parsed once per text."""
    out: list[LabelledField] = []
    lines = text.splitlines()
    fence: str | None = None  # the open fence's marker; nested fences are body
    comment = False  # inside a multi-line <!-- … --> — not prose
    for i, line in enumerate(lines):
        if comment:
            comment = "-->" not in line
            continue
        if line.strip().startswith("<!--") and "-->" not in line:
            comment = True
            continue
        if fence is not None:
            if markdown.closes(line, fence):
                fence = None
            continue
        opened = markdown.FENCE.match(line)
        if opened:
            fence = opened.group(2)
            continue
        if "**" not in line:
            continue
        joined, nxt = line, i + 1
        if (
            re.match(_BULLET + r"\*\*", line)
            and ":**" not in line
            and i + 1 < len(lines)
        ):
            joined, nxt = line + " " + lines[i + 1].strip(), i + 2
        m = _FIELD_OPEN.match(joined)
        if not m:
            continue
        parts, last = _continuation(lines, nxt, len(line) - len(line.lstrip()))
        label = " ".join(m.group("label").split())
        out.append(
            LabelledField(
                line=i + 1,
                name=field_name(label),
                label=label,
                value=HTML_COMMENT.sub(
                    "", " ".join([m.group("value"), *parts])
                ).strip(),
                last=last,
            )
        )
    return tuple(out)


def named_value(text: str, label: str) -> str | None:
    """The value of the field of TEXT whose label LABEL names —
    `field_name` of both equal, so case, a parenthesised gloss and † aside,
    never a part of a label; None for a label TEXT does not hold, or holds
    more than once. An empty value is "", not None."""
    name = field_name(label)
    hits = [f for f in labelled_fields(text) if f.name == name]
    return hits[0].value if len(hits) == 1 else None
