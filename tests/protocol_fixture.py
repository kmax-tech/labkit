"""A protocol head for test fixtures: the ```toml block with its [protocol] table.

One home for the shape, so a fixture states only what it varies:
`head(cost="seconds", frozen=True)`.
"""

from __future__ import annotations

import json
from pathlib import Path

from labkit.formats import promises

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


def completed_run(
    area: Path,
    name: str,
    *,
    pid: str = PID,
    metrics: dict | None = None,
    completion: bool = True,
    long: bool = True,
    unfrozen_ack: bool = False,
) -> Path:
    """A run directory as runlog leaves one: bound to PID, its promise
    snapshot taken from the area's PROTOCOL-x.md (0.71: a run under a frozen
    protocol recorded its block), a full run unless LONG says a probe, not
    acknowledged unless UNFROZEN_ACK (0.99.0: both recorded, `runs.unreportable`),
    METRICS written when given, finished when COMPLETION. The one home for the
    shape (finalize, report-check)."""
    d = area / "runs" / name
    d.mkdir(parents=True, exist_ok=True)
    scope_file(area)  # the block's scopes name the fixture's script
    block = promises.parse_block((area / "PROTOCOL-x.md").read_text(encoding="utf-8"))
    cfg = {
        "script": "01_measure.py",
        "pid": 1,
        "schema_version": 2,
        "protocol": {"id": pid, "path": "PROTOCOL-x.md"},
        "long": long,
        "unfrozen_ack": unfrozen_ack,
        "promises": promises.snapshot(block, area) if block is not None else None,
    }
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    if metrics is not None:
        (d / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    if completion:
        (d / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "finished": "x",
                    "git": "g",
                    "git_full": "g",
                    "note": "",
                }
            ),
            encoding="utf-8",
        )
    return d


def head(
    *,
    id: str = PID,
    type: str = "exploratory",
    cost: str = "minutes",
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
        'standard = "0.19"',
        f'id = "{id}"',
        f'type = "{type}"',
        f'cost = "{cost}"',
        f"frozen = {'true' if frozen else 'false'}",
        f'preflight_audit = "{preflight_audit}"',
    ]
    body = "\n".join(lines) + "\n"
    if promises:
        body += "\n" + promises.strip() + "\n"
    return body + "```\n"
