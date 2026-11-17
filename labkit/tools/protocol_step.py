"""protocol_step — write the step the next runs make (`[builds_on]`).

    protocol-fill PROTOCOL --builds-on RUN_ID --id STEP --occasion OCCASION --why "…"

The step names its basis run, why it is taken and every change of the
registration against the basis run's own text — computed here from that
text (`protocol_history.as_measured_patch_checked`) and the protocol as it stands
(`protocol_history.registration_differences`), never typed. A run id is
written by this command, never by hand. The basis is held as the start
holds it (`start_check.require_step_basis`): a completed run of this
protocol, no repeat. One current step: an earlier `[builds_on]` is
replaced, since each run keeps the step it ran under in its own text.
Writes the protocol file and nothing else.
"""

from __future__ import annotations

import re
from pathlib import Path

from labkit.formats import protocol_block, runs
from labkit.formats.protocol_block import BuildsOn, StepChange, toml_string
from labkit.formats.protocol_history import (
    registration_differences,
    as_measured_patch_checked,
)
from labkit.formats.repo import git_root
from labkit.run.start_check import require_step_basis

#: the header lines of a step in the TOML block: its table and its changes
_STEP_HEADER = protocol_block.table_header("builds_on")
_CHANGE_HEADER = re.compile(r"^\s*\[\[\s*builds_on\.change\s*\]\]\s*(?:#.*)?$")


def step_with_changes(
    protocol: Path, text: str, basis: str, step_id: str, occasion: str, why: str
) -> BuildsOn:
    """The step on BASIS that PROTOCOL (its text TEXT) makes: STEP_ID,
    OCCASION and WHY as given, its changes the differences of the
    registration from BASIS's own text to TEXT, each without a reason of
    its own (the step's WHY covers them; add one by hand where it does
    not). Raises ValueError when BASIS cannot be built on — the start's
    refusal, told without runlog's prefix — or its own text cannot be read
    back, and BlockError on a head that does not read."""
    area = protocol.resolve().parent
    pid = protocol_block.head(text).id
    if pid is None:
        raise ValueError(f"{protocol.name} has no stamped id — a step is a protocol's")
    probe = BuildsOn(step_id, basis, occasion, why, ())
    try:
        require_step_basis(area, pid, with_step(text, probe))
    except SystemExit as exc:  # the start's rule, held before the file is written
        raise ValueError(str(exc.code).removeprefix("runlog: ")) from exc
    rd = runs.read_run_dir(runs.run_path(area, basis))
    then, where = as_measured_patch_checked(
        protocol.resolve(), rd, git_root(area), role="basis run"
    )
    if then is None:
        raise ValueError(
            f"the basis's own text cannot be read back — {where}; a step's "
            f"changes are computed from it, never from today's text"
        )
    changes = tuple(
        StepChange(what, x, y, None)
        for what, x, y in registration_differences(then, text)
    )
    return BuildsOn(step_id, basis, occasion, why, changes)


def step_toml(step: BuildsOn) -> list[str]:
    """STEP as the TOML lines of `[builds_on]` and its `[[builds_on.change]]`
    tables, each string one line (`toml_string`)."""
    lines = [
        "[builds_on]",
        f"id = {toml_string(step.id)}",
        f"run = {toml_string(step.run)}",
        f"occasion = {toml_string(step.occasion)}",
        f"why = {toml_string(step.why)}",
    ]
    for c in step.changes:
        lines += [
            "[[builds_on.change]]",
            f"what = {toml_string(c.what)}",
            f"from = {toml_string(c.from_)}",
            f"to = {toml_string(c.to)}",
        ]
        if c.why is not None:
            lines.append(f"why = {toml_string(c.why)}")
    return lines


def with_step(text: str, step: BuildsOn) -> str:
    """TEXT with STEP as its one `[builds_on]`: an earlier step's table and
    change tables removed, STEP's written at the end of the TOML block.
    Every other byte stays. Raises ValueError without a TOML block, and
    when the block does not read back with STEP."""
    span = protocol_block.toml_block_span(text)
    if span is None:
        raise ValueError("no ```toml block — the step is written into the head")
    start, end = span
    lines = text.split("\n")
    kept: list[str] = []
    in_step = False
    for line in lines[start:end]:
        if _STEP_HEADER.match(line) or _CHANGE_HEADER.match(line):
            in_step = True
        elif protocol_block.TABLE_HEADER.match(line):
            in_step = False
        if not in_step:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    body = [*kept, "", *step_toml(step)]
    new = "\n".join([*lines[:start], *body, *lines[end:]])
    if protocol_block.builds_on(new) != step:
        raise ValueError("[builds_on] did not read back as written")
    return new
