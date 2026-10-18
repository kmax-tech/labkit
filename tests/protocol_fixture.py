"""A protocol head for test fixtures: the ```toml block with its [protocol] table.

One home for the shape, so a fixture states only what it varies:
`head(cost="seconds", frozen=True)`.
"""

from __future__ import annotations

from pathlib import Path

PID = "p-0123456789abcdef"

#: The tables a frozen fixture carries unless it says otherwise — the stamp's
#: shape (0.71.0: frozen = true owes a promise block); the scope is the
#: script `scope_file` writes.
DEFAULT_BLOCK = """\
[[promise]]
id = "C1"
key = "c1_pass"
sentence = "the criterion holds"
scope = ["scripts/01_measure.py"]

[[promise]]
id = "A1"
key = "a1_pass"
sentence = "the yield suffices"
scope = ["scripts/01_measure.py"]

[[promise]]
id = "A2"
key = "a2_pass"
sentence = "the null lane sits at chance"
scope = ["scripts/01_measure.py"]
"""


def scope_file(area: Path) -> Path:
    """The script the default block's scopes name, written if absent."""
    script = area / "scripts" / "01_measure.py"
    if not script.is_file():
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            'def evaluate_rows(rows):\n    return {"c1_pass": True, "a1_pass": True, "a2_pass": True}\n',
            encoding="utf-8",
        )
    return script


def head(
    *,
    id: str = PID,
    type: str = "exploratory",
    cost: str = "minutes",
    instrument: str = "apply",
    frozen: bool = False,
    preflight_audit: str = "",
    promises: str | None = "",
) -> str:
    """The fenced TOML block; `promises` is appended inside it verbatim. A
    frozen or seconds head without an explicit block carries `DEFAULT_BLOCK`;
    `None` means no block even then (the mutant of standard 0.19's rule)."""
    if promises == "" and (frozen or cost == "seconds"):
        promises = DEFAULT_BLOCK  # frozen, or at seconds every run is the full run
    promises = promises or ""
    lines = [
        "```toml",
        "[protocol]",
        'standard = "0.20"',
        f'id = "{id}"',
        f'type = "{type}"',
        f'cost = "{cost}"',
        f'instrument = "{instrument}"',
        f"frozen = {'true' if frozen else 'false'}",
        f'preflight_audit = "{preflight_audit}"',
    ]
    body = "\n".join(lines) + "\n"
    if promises:
        body += "\n" + promises.strip() + "\n"
    return body + "```\n"
