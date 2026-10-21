"""A protocol head for test fixtures: the ```toml block with its [protocol] table.

One home for the shape, so a fixture states only what it varies:
`head(cost="seconds", frozen=True)`.
"""

from __future__ import annotations

from labkit.formats.runs import RunKind

import json
from pathlib import Path

from labkit.formats import promises, runs

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


def run_record(
    fields: dict | None = None, /, *, drop: tuple[str, ...] = (), **more: object
) -> dict:
    """A complete config.json as runlog writes it — schema 3, every field of
    `runs.RUN_CONFIG_KEYS`: a measurement, unbound, no parent, no repeat, no
    data, an empty config. FIELDS and MORE replace what a test varies; a
    test of a damaged record breaks a field explicitly: DROP leaves fields
    out (a record from before the schema), or it deletes one from the
    result (`del record["unfrozen_ack"]`). The one home for the record's shape in
    the tests: a fixture that wrote a part of it read, until 2026-10-20, as
    a record with defaults."""
    record: dict = {
        "schema_version": 3,
        "experiment": "x",
        "script": "01_measure.py",
        "protocol": {"id": None, "path": None},
        "derived_from": None,
        "repeat_of": None,
        "draw": None,
        "run_kind": "measurement",
        "unfrozen_ack": False,
        "audit_failed": None,
        "cost_tier": None,
        "promises": None,
        "script_sha": "no-script",
        "untracked_sources": [],
        "pid": 1,
        "git": "g",
        "git_full": "g",
        "python": "3.12",
        "env": "unpinned",
        "models_resolved": {},
        "started": "2026-01-01T00:00:00",
        "command": [],
        "data": {},
        "config": {},
    }
    assert tuple(record) == runs.RUN_CONFIG_KEYS, "run_record lags runs.RUN_CONFIG_KEYS"
    out = {**record, **(fields or {}), **more}
    for key in drop:
        del out[key]
    return out


def completed_run(
    area: Path,
    name: str,
    *,
    pid: str = PID,
    metrics: dict | None = None,
    completion: bool = True,
    run_kind: RunKind = "measurement",
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
    cfg = run_record(
        protocol={"id": pid, "path": "PROTOCOL-x.md"},
        run_kind=run_kind,
        unfrozen_ack=unfrozen_ack,
        promises=promises.snapshot(block, area) if block is not None else None,
    )
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    if metrics is not None:
        (d / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    if completion:
        (d / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 3,
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
    result: str | None = None,
) -> str:
    """The fenced TOML block; `promises` is appended inside it verbatim. A
    frozen or seconds head without an explicit block carries `DEFAULT_BLOCK`;
    `None` means no block even then (the mutant of standard 0.19's rule).
    RESULT is the run id a `[result]` table declares (phase 3, 2026-10-21)."""
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
    if result is not None:
        lines += ["", "[result]", f'run = "{result}"']
    body = "\n".join(lines) + "\n"
    if promises:
        body += "\n" + promises.strip() + "\n"
    return body + "```\n"
