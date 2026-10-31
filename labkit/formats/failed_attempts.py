"""failed_attempts — the evidence that an audit was tried and could not run.

When the backend does not answer (`llm_backends.BackendError`: the CLI died, the
server was down, every retry ran out), `labkit-audit` writes no findings
but the evidence that it tried, next to them:

    audits/2026-10-12T15-33-preflight-failed.toml

    [failed]
    date = "2026-10-12T15:33"
    mode = "preflight"
    model = "opus"
    scope_sha = "fa45c7618423"   # the code it would have read
    block_sha = "0c1d2e3f4a5b"   # the promises it would have read
    timeout_s = 900              # the time the call was given
    error = "claude-cli exit 1: …"
    command = "labkit-audit experiments/09-x --mode preflight"

That file is what `LABKIT_UNFROZEN=1` acknowledges at `high`:
an audit that could not run, not one nobody ran (`audit_unavailable`, held
by runlog's freeze gate since 0.99.0). labkit writes it, with the error the
backend gave; a usage error (an unknown alias, an area that cannot be
stamped) is not an unavailable audit and leaves none. A record of findings
and a failed attempt never share a name (`findings.FAILED_SUFFIX`);
`findings.area_records` reads the records only.
"""

from __future__ import annotations


import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.protocol_block import toml_string as _s
from labkit.formats.runs import date_minute, name_minute
from labkit.formats.findings import (
    DIR,
    FAILED_SUFFIX,
    FindingsError,
    MODES,
    create_file,
    written_order,
)

#: the low lane's `labkit-audit` gives its one call by default, and the least a
#: failed attempt must have been given to count as one (`audit_unavailable`):
#: an attempt given less time than the audit takes is not an attempt
ATTEMPT_TIMEOUT_S = 900
#: why an audit attempt failed: the backend gave no answer (`unavailable`),
#: or an answer the requested model did not write whole (`unproven`,
#: `llm_backends.UnprovenAnswer` — a safety stop, another model). An
#: unproven attempt ends the auditing of that state with that model
#: (`stopped_attempt`): each further try costs the same and was stopped
#: again in the fit probes
FAILED_CAUSES = ("unavailable", "unproven")


@dataclass(frozen=True)
class Failed:
    """One attempt at an audit whose backend did not answer — written by
    `labkit-audit`, never by hand (the evidence an acknowledged full run
    rests on)."""

    path: Path
    date: str
    mode: str
    model: str
    scope_sha: str  # the code it would have read
    block_sha: str  # the promise block it would have read
    timeout_s: int  # the seconds the one call was given
    error: str  # what the backend said
    command: str  # the command line that tried
    cause: str  # one of FAILED_CAUSES


def write_failed(
    area: Path,
    mode: str,
    model: str,
    scope_sha: str,
    block_sha: str,
    timeout_s: int,
    error: str,
    command: str,
    *,
    cause: str,
    now: float | None = None,
) -> Path:
    """Write the evidence of an audit that could not run into AREA/audits/
    and return its path: `<stamp>-<mode>-failed.toml`, never overwriting.
    SCOPE_SHA and BLOCK_SHA name what the auditor would have read, so the
    freeze gate can hold the acknowledgement to the code and promises as
    they are now; TIMEOUT_S what the call was given; ERROR the backend's
    words; COMMAND the line that tried; CAUSE one of FAILED_CAUSES."""
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} — one of {', '.join(MODES)}")
    if cause not in FAILED_CAUSES:
        raise ValueError(f"cause {cause!r} — one of {', '.join(FAILED_CAUSES)}")
    when = time.localtime(now)
    stamp = name_minute(when)
    lines = [
        "# written by labkit-audit — the audit did not run; this is the evidence, "
        "not a record of findings",
        "[failed]",
        f"date = {_s(date_minute(when))}",
        f"mode = {_s(mode)}",
        f"model = {_s(model)}",
        f"scope_sha = {_s(scope_sha)}",
        f"block_sha = {_s(block_sha)}",
        f"timeout_s = {int(timeout_s)}",
        f"error = {_s(error)}",
        f"command = {_s(command)}",
        f"cause = {_s(cause)}",
    ]
    return create_file(
        area / DIR, f"{stamp}-{mode}", FAILED_SUFFIX, "\n".join(lines) + "\n"
    )


def read_failed(path: Path) -> Failed:
    """The failed attempt at PATH; raises FindingsError on anything it
    cannot hold to — a file nobody can read is not evidence."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise FindingsError(f"{path}: not TOML ({exc})") from exc
    table = data.get("failed")
    if not isinstance(table, dict):
        raise FindingsError(f"{path}: no [failed] table")
    for key in (
        "date",
        "mode",
        "model",
        "scope_sha",
        "block_sha",
        "error",
        "command",
        "cause",
    ):
        if not isinstance(table.get(key), str):
            raise FindingsError(f"{path}: [failed] {key} is missing or not a string")
    timeout = table.get("timeout_s")
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        raise FindingsError(f"{path}: [failed] timeout_s is missing or not an integer")
    if table["mode"] not in MODES:
        raise FindingsError(
            f"{path}: [failed] mode {table['mode']!r} — one of {', '.join(MODES)}"
        )
    if table["cause"] not in FAILED_CAUSES:
        raise FindingsError(
            f"{path}: [failed] cause {table['cause']!r} — one of "
            f"{', '.join(FAILED_CAUSES)}"
        )
    return Failed(
        path,
        table["date"],
        table["mode"],
        table["model"],
        table["scope_sha"],
        table["block_sha"],
        timeout,
        table["error"],
        table["command"],
        table["cause"],
    )


def failed_attempts(area: Path) -> list[Failed]:
    """Every failed attempt of AREA, oldest first (`findings.written_order`); a file
    that cannot be read raises."""
    folder = area / DIR
    if not folder.is_dir():
        return []
    return [
        read_failed(p)
        for p in sorted(folder.glob(f"*{FAILED_SUFFIX}"), key=written_order)
    ]


def unproven_attempts(area: Path, mode: str, sha: str, block_sha: str) -> list[Failed]:
    """The `unproven` failed attempts of MODE at the area as it is now —
    code SHA and promises BLOCK_SHA — with any model, oldest first.

    Raises:
        FindingsError: A failed-attempt file of AREA cannot be read.
    """
    return [
        f
        for f in failed_attempts(area)
        if f.cause == "unproven"
        and f.mode == mode
        and f.scope_sha == sha
        and f.block_sha == block_sha
    ]


def stopped_attempt(
    area: Path, mode: str, model: str, sha: str, block_sha: str
) -> Failed | None:
    """The newest `unproven` attempt of MODE with MODEL at the area as it is
    now (`unproven_attempts`); None when there is none. `labkit-audit`
    refuses another try on that state with that model.

    Raises:
        FindingsError: A failed-attempt file of AREA cannot be read.
    """
    fitting = [
        f for f in unproven_attempts(area, mode, sha, block_sha) if f.model == model
    ]
    return fitting[-1] if fitting else None


def audit_unavailable(
    area: Path, sha: str, mode: str, block_sha: str | None
) -> Failed | None:
    """The newest failed attempt of MODE at the area as it is now — code SHA
    and, when given, promises BLOCK_SHA — whose call was given at least
    ATTEMPT_TIMEOUT_S seconds; None when none is. This is what a full run's
    acknowledgement rests on: an audit that could not run. An attempt at
    other code or other promises says nothing about these; an attempt given
    less time than the audit takes (`--timeout 1`) is not an attempt. Both
    are mechanical, and both are said in the refusal.

    Raises:
        FindingsError: A failed-attempt file of AREA cannot be read.
    """
    if mode not in MODES:
        raise ValueError(f"audit mode {mode!r} is not one of {', '.join(MODES)}")
    fitting = [
        f
        for f in failed_attempts(area)
        if f.mode == mode
        and f.scope_sha == sha
        and (block_sha is None or f.block_sha == block_sha)
        and f.timeout_s >= ATTEMPT_TIMEOUT_S
    ]
    return fitting[-1] if fitting else None
