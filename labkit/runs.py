"""runs — read what a run directory says about itself.

The read side of a run, apart from `runlog`, which writes one: liveness of
the recording process, the run's state from its markers, its metadata, and
which runs of an area are complete. Every module that picks, accepts or
lists a run asks here — recheck, intent-check, finalize, the usability
scorer, the endpoint lease — without importing the writer (and, through it,
the LLM backend). Contract: docs/protocol-run-binding.md, "Run completion".
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _command_of(pid: int) -> str | None:
    """Command line of a process, or None if unreadable."""
    try:
        r = subprocess.run(
            ["ps", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None


def is_alive(pid, script) -> bool | None:
    """Is THIS run still going? True / False / None (undecidable).

    The PID alone is not enough, and that is no theoretical concern: on
    2026-08-15 `runlog` reported a run from August 13 as running because the
    OS had meanwhile recycled the PID to a macOS service
    (`RemoteManagement`). Anyone following the working standard's "look,
    don't ask" got a wrong answer — and would not have restarted a run that
    was long dead.

    So the command line is additionally checked for the recorded script
    name. If that cannot be decided (no `ps`, no script name), the answer
    is **None**, not `True`: an "unknown" is usable, a false "running" is
    not.
    """
    if not isinstance(pid, int):
        return None
    try:
        os.kill(pid, 0)  # signal 0: existence check only
    except ProcessLookupError:
        return False
    except PermissionError:
        pass  # exists, belongs to someone else
    cmd = _command_of(pid)
    if cmd is None or not script:
        return None
    return script in cmd


def run_state(run_dir: Path, cfg: dict, alive: bool | None) -> str:
    """One of: completed · running · unknown · crashed · unfinalized · corrupt · legacy.

    Complete when BOTH metrics.json and completion.json exist. Both, not
    completion.json alone: a completion record must not paper over results
    that were deleted or never landed. Hence `corrupt` — completion without
    metrics — which is a failure like `unfinalized`, not a finish.

    `legacy`: config.json carries no `schema_version` >= 2 (written before
    labkit 0.21, when metrics.json alone marked a finish). Such a run is
    read with labkit 0.47; here it is never `completed`.

    `alive is None` means the liveness check was undecidable (no `ps`, no
    script name). That is `unknown`, not `crashed` — claiming a process is
    dead when the evidence says "can't tell" is a false negative that hides
    a running run. `endpoint_lease` already treats None as conservatively
    alive; `run_state` uses the same contract.
    """
    if cfg.get("schema_version", 0) < 2:
        return "legacy"
    has_metrics = (run_dir / "metrics.json").is_file()
    has_completion = (run_dir / "completion.json").is_file()
    if has_metrics and has_completion:
        return "completed"
    if alive is True:
        return "running"
    if alive is None:
        return "unknown"
    if has_completion:
        return "corrupt"
    return "unfinalized" if has_metrics else "crashed"


class RunConfigError(ValueError):
    """A run directory whose config.json exists but cannot be read."""


def read_run_config(run_dir: Path) -> dict | None:
    """A run's metadata, None when the directory has no config.json.

    Unreadable is not absent: a damaged config.json raises RunConfigError
    naming the file. Skipping it silently made a broken newer run vanish
    and let an older one be chosen or reported in its place (review
    2026-10-06) — listings show it as `corrupt`, choices refuse.
    """
    cfg_file = run_dir / "config.json"
    if not cfg_file.is_file():
        return None
    try:
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunConfigError(
            f"{cfg_file}: unreadable run metadata ({exc}) — the run cannot "
            f"say what it is; repair or move it aside"
        ) from exc
    problem = _shape_problem(cfg)
    if problem:
        raise RunConfigError(
            f"{cfg_file}: unreadable run metadata ({problem}) — repair or move it aside"
        )
    return cfg


def _shape_problem(cfg: object) -> str | None:
    """The minimal shape every reader relies on, checked in one place:
    valid JSON that is a list, or a binding that is a string, used to fail
    later as an AttributeError far from the file (review 2026-10-07)."""
    if not isinstance(cfg, dict):
        return f"a JSON {type(cfg).__name__}, not an object"
    sv = cfg.get("schema_version")
    if sv is not None and (not isinstance(sv, int) or isinstance(sv, bool)):
        return f"schema_version = {sv!r}, not an integer"
    binding = cfg.get("protocol")
    if binding is not None:
        if not isinstance(binding, dict):
            return f"protocol = {binding!r}, not an object"
        for key in ("id", "path"):
            if binding.get(key) is not None and not isinstance(binding[key], str):
                return f"protocol.{key} = {binding[key]!r}, not a string"
    return None


def completion_state(run_dir: Path) -> str:
    """`run_state` of a run directory read from disk, liveness not asked.

    The one question every consumer that picks or accepts a run must ask —
    recheck, a derived run's parent, intent-check's choice, the usability
    scorer. Asking `metrics.json` alone let an unfinalized v2 run (metrics,
    no completion record) be rechecked as a kept number and accepted as a
    parent (review 2026-10-06). A directory without config.json predates
    run metadata and is `legacy`; an unreadable config.json raises
    RunConfigError — a damaged run must
    not vanish and let an older one be chosen in its place.
    """
    return run_state(run_dir, read_run_config(run_dir) or {}, alive=False)


def completed_runs(area: Path) -> list[Path]:
    """The area's completed run directories, oldest first (run_ids start
    with the timestamp, so name order is start order)."""
    runs = area / "runs"
    if not runs.is_dir():
        return []
    return [
        d
        for d in sorted(runs.iterdir())
        if d.is_dir() and completion_state(d) == "completed"
    ]


#: States that mean "this run is not a clean finish" — `--wait` exits 2 on
#: any of them, `reindex` rebuilds none of them. `unknown` is NOT in this
#: list: it means "can't tell", and treating it as failed would hide a run
#: that is still going.
FAILED_STATES = ("crashed", "unfinalized", "corrupt")
