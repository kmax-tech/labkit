"""protocol_block — the one TOML block of a protocol, and its head.

A protocol carries exactly one fenced ```toml block. Its `[protocol]` table
holds the fields a machine reads — the head — and its optional
`[[promise]]` tables hold the promises (`promises.py`):

    [protocol]
    standard = "0.18"
    id = "p-0123456789abcdef"       # stamped by `lib exp`, never typed
    type = "exploratory"            # exploratory | confirmatory
    cost = "seconds"                # seconds | minutes | hours
    frozen = false
    preflight_audit = ""            # one line once the audit is decided

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

#: the head format this labkit reads; a protocol of another standard is
#: read with the labkit release it was written for
STANDARD = "0.18"
TYPES = ("exploratory", "confirmatory")
COST_TIERS = ("seconds", "minutes", "hours")
#: `p-` plus 16 lowercase hex: not derived from name or path, so renaming
#: and moving a protocol leave its identity intact
ID_SHAPE = re.compile(r"^p-[0-9a-f]{16}$")

_FENCED_TOML = re.compile(r"^```toml[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
_TOP_LEVEL = {"protocol", "promise"}
_HEAD_FIELDS = ("standard", "id", "type", "cost", "frozen", "preflight_audit")


class BlockError(ValueError):
    """The protocol's TOML block is missing or malformed; the message names the field."""


@dataclass(frozen=True)
class Head:
    """The `[protocol]` table. None marks a field still holding its placeholder."""
    standard: str
    id: str | None
    type: str | None
    cost: str | None
    frozen: bool
    preflight_audit: str            # "" until the audit is decided

    @property
    def placeholders(self) -> list[str]:
        return [f for f in ("id", "type", "cost") if getattr(self, f) is None]


def block_text(text: str) -> str | None:
    """The raw text of the protocol's TOML block, None if it has none.

    Raises BlockError when there are two: a protocol has exactly one."""
    blocks = [m.group(1) for m in _FENCED_TOML.finditer(text)]
    if len(blocks) > 1:
        raise BlockError(f"{len(blocks)} ```toml blocks — a protocol has exactly "
                         f"one, holding [protocol] and its [[promise]] tables")
    return blocks[0] if blocks else None


def load(text: str) -> dict:
    """The parsed TOML block; an empty dict when the protocol has none."""
    raw = block_text(text)
    if raw is None:
        return {}
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise BlockError(f"the protocol's ```toml block is not valid TOML: {exc}") from exc
    extra = set(data) - _TOP_LEVEL
    if extra:
        raise BlockError(f"top-level keys {sorted(extra)} in the ```toml block — "
                         f"only [protocol] and [[promise]] belong there")
    return data


def _placeholder(value: object) -> bool:
    """The template's `"<…>"`; a value merely starting with `<` is content."""
    return isinstance(value, str) and value.strip().startswith("<") and value.strip().endswith(">")


def _choice(table: dict, field: str, allowed: tuple[str, ...]) -> str | None:
    value = table[field]
    if _placeholder(value):
        return None
    if value not in allowed:
        raise BlockError(f"[protocol] {field} = {value!r} — one of {', '.join(allowed)}")
    return value


def head(text: str) -> Head:
    """The protocol's head. Raises BlockError when the block or the
    `[protocol]` table is missing, a field is missing or unknown, or a
    value has the wrong type or is outside its choices."""
    data = load(text)
    if "protocol" not in data:
        raise BlockError("no [protocol] table — the head (standard, id, type, cost, "
                         "frozen, preflight_audit) lives in the ```toml block; "
                         "protocols with a prose head are read by labkit 0.47")
    table = data["protocol"]
    if not isinstance(table, dict):
        raise BlockError("`protocol` must be a table: [protocol]")
    unknown = set(table) - set(_HEAD_FIELDS)
    if unknown:
        raise BlockError(f"[protocol]: unknown field(s) {sorted(unknown)}; "
                         f"allowed: {', '.join(_HEAD_FIELDS)}")
    missing = [f for f in _HEAD_FIELDS if f not in table]
    if missing:
        raise BlockError(f"[protocol]: missing {', '.join(missing)}")
    standard = table["standard"]
    if standard != STANDARD:
        raise BlockError(f"[protocol] standard = {standard!r}, this labkit reads "
                         f"{STANDARD!r} — use the labkit release the protocol was "
                         f"written for, or update the protocol")
    pid = table["id"]
    if not isinstance(pid, str):
        raise BlockError(f"[protocol] id = {pid!r} — a string")
    if _placeholder(pid):
        pid = None
    elif not ID_SHAPE.match(pid):
        raise BlockError(f"[protocol] id = {pid!r} — expected `p-` plus 16 lowercase "
                         f"hex digits, stamped by `lib exp`")
    frozen = table["frozen"]
    if not isinstance(frozen, bool):
        raise BlockError(f"[protocol] frozen = {frozen!r} — true or false")
    audit = table["preflight_audit"]
    if not isinstance(audit, str):
        raise BlockError(f"[protocol] preflight_audit = {audit!r} — a string")
    if _placeholder(audit):
        audit = ""
    return Head(standard=standard, id=pid, type=_choice(table, "type", TYPES),
                cost=_choice(table, "cost", COST_TIERS), frozen=frozen,
                preflight_audit=audit.strip())
