"""A protocol head for test fixtures: the ```toml block with its [protocol] table.

One home for the shape, so a fixture states only what it varies:
`head(cost="seconds", frozen=True)`.
"""
from __future__ import annotations

PID = "p-0123456789abcdef"


def head(*, id: str = PID, type: str = "exploratory", cost: str = "minutes",
         frozen: bool = False, preflight_audit: str = "", promises: str = "") -> str:
    """The fenced TOML block; `promises` is appended inside it verbatim."""
    lines = ["```toml", "[protocol]", 'standard = "0.18"', f'id = "{id}"',
             f'type = "{type}"', f'cost = "{cost}"', f"frozen = {'true' if frozen else 'false'}",
             f'preflight_audit = "{preflight_audit}"']
    body = "\n".join(lines) + "\n"
    if promises:
        body += "\n" + promises.strip() + "\n"
    return body + "```\n"
