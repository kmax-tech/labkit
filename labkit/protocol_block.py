"""protocol_block — the one TOML block of a protocol, and its head.

A protocol carries exactly one fenced ```toml block. Its `[protocol]` table
holds the fields a machine reads — the head — and its optional
`[[promise]]` tables hold the promises (`promises.py`):

    [protocol]
    standard = "0.20"
    id = "p-0123456789abcdef"       # stamped by `labkit-init exp`, never typed
    type = "exploratory"            # exploratory | confirmatory
    cost = "seconds"                # seconds | minutes | hours
    instrument = "apply"            # apply | fit | count — what happens to this run's labels
    frozen = false
    preflight_audit = ""            # one line once the audit is decided

The instrument is the kind of the experiment, as data (standard 0.20,
2026-10-17; named 2026-10-18): what happens to this run's labels. *apply*
asks a fixed model per item and never sees them (a prompt, a parser, a
placebo or anchor null lane; today a model through `labkit.llm`); *fit*
learns from them in the run (an estimator fitted out of fold, a
permuted-label null lane, a seed); *count* has none (deterministic, no bar
to clear). The pretraining of a model is no difference here — it happened
outside the run. Until 0.20 the kind was inferred at six places from the
prose of "Model / tool" and from `labkit-init`'s flags; the field cut, the
stamped skeleton, the promise block and the gates read this key. A mixed
form names what produces the row's answer; a model that renders features
belongs to the prepare step.

One parser (`tomllib`), exact keys, typed values: a typo is a loud error
naming the field, never a silent "not found" — `Cost: second` used to read
as an undeclared tier and so as `hours` (TODO 8). The prose fields a human
writes and reads stay Markdown; `protocol_check` holds them by their exact
template label.

A value still in angle brackets (`"<seconds | minutes | hours>"`) is a
placeholder: the head reads it as None, and the checker reports it as an
unfilled field instead of a malformed one.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

#: the head format this labkit reads; a protocol of another standard is
#: read with the labkit release it was written for
STANDARD = "0.20"
TYPES = ("exploratory", "confirmatory")
COST_TIERS = ("seconds", "minutes", "hours")
#: what happens to this run's labels — the kind of the experiment, as data
INSTRUMENTS = ("apply", "fit", "count")
#: `p-` plus 16 lowercase hex: not derived from name or path, so renaming
#: and moving a protocol leave its identity intact
ID_SHAPE = re.compile(r"^p-[0-9a-f]{16}$")

FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w+-]*)")
_TOP_LEVEL = {"protocol", "promise"}
#: the settings every protocol carries in its ```toml head (the block at the
#: end of the protocol), in the template's order — not the run's config.json,
#: which runlog writes per run
PROTOCOL_HEAD_KEYS = (
    "standard",
    "id",
    "type",
    "cost",
    "instrument",
    "frozen",
    "preflight_audit",
)


class BlockError(ValueError):
    """The protocol's TOML block is missing or malformed; the message names the field."""


@dataclass(frozen=True)
class Head:
    """The `[protocol]` table. None marks a field still holding its placeholder."""

    standard: str
    id: str | None
    type: str | None
    cost: str | None
    instrument: str | None  # apply | fit | count
    frozen: bool
    preflight_audit: str  # "" until the audit is decided

    @property
    def placeholders(self) -> list[str]:
        """The head fields still holding a template placeholder."""
        return [
            f for f in ("id", "type", "cost", "instrument") if getattr(self, f) is None
        ]


def fence_spans(lines: list[str]) -> list[tuple[str, int, int]]:
    """(info string, first body line, line after the body) of every
    top-level fenced block, as 0-based indexes into LINES — the one fence
    walker; `fenced_blocks` is its text form, and the readers that need a
    place (the head's line, the Prompt block to replace) use the spans.
    A fence inside another fence is body, not a block: a verbatim prompt
    that asks the model for ```toml output is no second head (review
    2026-10-07). A fence closes with the same character, at least as long,
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


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    """(info string, body) of every top-level fenced block (`fence_spans`)."""
    lines = text.splitlines()
    return [
        (info, "\n".join(lines[start:end]) + "\n")
        for info, start, end in fence_spans(lines)
    ]


def toml_block_span(text: str) -> tuple[int, int] | None:
    """(first body line, line after the body) of the protocol's one TOML
    block, 0-based, or None without one; raises BlockError when there are
    two — where a writer edits the head in place."""
    spans = [(s, e) for info, s, e in fence_spans(text.splitlines()) if info == "toml"]
    if len(spans) > 1:
        raise BlockError(
            f"{len(spans)} ```toml blocks — a protocol has exactly "
            f"one, holding [protocol] and its [[promise]] tables"
        )
    return spans[0] if spans else None


def closes(line: str, marker: str) -> bool:
    """Does `line` close a fence opened with `marker`?"""
    s = line.strip()
    return bool(s) and set(s) == {marker[0]} and len(s) >= len(marker)


def block_text(text: str) -> str | None:
    """The raw text of the protocol's TOML block, None if it has none.

    Raises BlockError when there are two: a protocol has exactly one."""
    blocks = [body for info, body in fenced_blocks(text) if info == "toml"]
    if len(blocks) > 1:
        raise BlockError(
            f"{len(blocks)} ```toml blocks — a protocol has exactly "
            f"one, holding [protocol] and its [[promise]] tables"
        )
    return blocks[0] if blocks else None


def parse_toml_block(text: str) -> dict:
    """The parsed TOML block; an empty dict when the protocol has none."""
    raw = block_text(text)
    if raw is None:
        return {}
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise BlockError(
            f"the protocol's ```toml block is not valid TOML: {exc}"
        ) from exc
    extra = set(data) - _TOP_LEVEL
    if extra:
        raise BlockError(
            f"top-level keys {sorted(extra)} in the ```toml block — "
            f"only [protocol] and [[promise]] belong there"
        )
    return data


def _placeholder(value: object) -> bool:
    """The template's `"<…>"`; a value merely starting with `<` is content."""
    return (
        isinstance(value, str)
        and value.strip().startswith("<")
        and value.strip().endswith(">")
    )


def _choice(table: dict, field: str, allowed: tuple[str, ...]) -> str | None:
    value = table[field]
    if _placeholder(value):
        return None
    if value not in allowed:
        raise BlockError(
            f"[protocol] {field} = {value!r} — one of {', '.join(allowed)}"
        )
    return value


def id_of(text: str) -> str | None:
    """The head's id; None when the head is missing, malformed or unstamped.
    For readers that index or count protocols — a broken head is reported
    where that protocol itself is checked, not by every scan that meets it."""
    try:
        return head(text).id
    except BlockError:
        return None


def head(text: str) -> Head:  # noqa: C901 complexity baseline 2026-10-08
    """The protocol's head. Raises BlockError when the block or the
    `[protocol]` table is missing, a field is missing or unknown, or a
    value has the wrong type or is outside its choices."""
    data = parse_toml_block(text)
    if "protocol" not in data:
        raise BlockError(
            f"no [protocol] table — the head ({', '.join(PROTOCOL_HEAD_KEYS)}) "
            f"lives in the ```toml block; protocols with a prose head "
            f"are read by labkit 0.47"
        )
    table = data["protocol"]
    if not isinstance(table, dict):
        raise BlockError("`protocol` must be a table: [protocol]")
    unknown = set(table) - set(PROTOCOL_HEAD_KEYS)
    if unknown:
        raise BlockError(
            f"[protocol]: unknown field(s) {sorted(unknown)}; "
            f"allowed: {', '.join(PROTOCOL_HEAD_KEYS)}"
        )
    missing = [f for f in PROTOCOL_HEAD_KEYS if f not in table]
    if missing:
        raise BlockError(f"[protocol]: missing {', '.join(missing)}")
    standard = table["standard"]
    if not isinstance(standard, str):
        raise BlockError(f'[protocol] standard = {standard!r} — a string, "{STANDARD}"')
    if standard != STANDARD:
        raise BlockError(
            f"[protocol] standard = {standard!r}, this labkit reads "
            f"{STANDARD!r} — use the labkit release the protocol was "
            f"written for, or update the protocol"
        )
    pid = table["id"]
    if not isinstance(pid, str):
        raise BlockError(f"[protocol] id = {pid!r} — a string")
    if _placeholder(pid):
        pid = None
    elif not ID_SHAPE.match(pid):
        raise BlockError(
            f"[protocol] id = {pid!r} — expected `p-` plus 16 lowercase "
            f"hex digits, stamped by `labkit-init exp`"
        )
    frozen = table["frozen"]
    if not isinstance(frozen, bool):
        raise BlockError(f"[protocol] frozen = {frozen!r} — true or false")
    audit = table["preflight_audit"]
    if not isinstance(audit, str):
        raise BlockError(f"[protocol] preflight_audit = {audit!r} — a string")
    if _placeholder(audit):
        audit = ""
    return Head(
        standard=standard,
        id=pid,
        type=_choice(table, "type", TYPES),
        cost=_choice(table, "cost", COST_TIERS),
        instrument=_choice(table, "instrument", INSTRUMENTS),
        frozen=frozen,
        preflight_audit=audit.strip(),
    )


def find_by_id(area: Path, pid: str) -> Path:
    """The one protocol in `area` whose head carries `pid` — the binding a
    run recorded. A run's recorded path goes stale by design (renaming keeps
    the id); raises BlockError when no protocol or several carry it."""
    from labkit.repo import area_protocols  # layer 1 both; imported late, no cycle

    hits = []
    for p in area_protocols(area):
        try:
            if head(p.read_text(encoding="utf-8")).id == pid:
                hits.append(p)
        except BlockError:
            continue
    if len(hits) != 1:
        raise BlockError(
            f"{len(hits)} protocol(s) in {area} carry id {pid}"
            + (
                ": " + ", ".join(h.name for h in hits)
                if hits
                else " — renamed, moved or re-stamped since the run?"
            )
        )
    return hits[0]
