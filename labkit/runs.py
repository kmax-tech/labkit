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
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from labkit import promises


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


def is_alive(pid: object, script: object) -> bool | None:
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
    if cmd is None or not isinstance(script, str) or not script:
        return None  # a script name that is not text cannot be matched — undecidable
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


class ArtefactError(ValueError):
    """A run's artefact (metrics.json, outputs.json, completion.json) that is
    unreadable or not the shape its writer gives it."""


class MetricsError(ArtefactError):
    """A run's metrics.json that cannot be read as a JSON object."""


def _json_of(path: Path, what: str) -> object:
    """The JSON in a run artefact. Raises ArtefactError naming the file and
    what it holds ("metrics", "outputs", "completion")."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtefactError(
            f"{path}: unreadable {what} ({exc}) — repair the run or move it aside"
        ) from exc


@dataclass(frozen=True)
class OutputEntry:
    """One file a run registered as its output (`run.output`)."""

    path: Path
    sha256: str | None  # the content's first 16 hex digits; None: absent at the end
    lines: int | None  # lines of a text file; None: absent or not text
    note: str = ""
    rows_from: dict[str, int] = field(
        default_factory=dict
    )  # run_id -> rows (JSONL, 0.72.3)
    continues: tuple[str, ...] = ()  # runs whose rows this file already held


def read_outputs(run_dir: Path) -> list[OutputEntry] | None:
    """The outputs a run registered, from its outputs.json; None when the run
    registered none (no file). Raises ArtefactError when an entry is not the
    shape `runlog` writes — a path as text, sha256 text or null, lines an
    integer or null."""
    path = run_dir / "outputs.json"
    if not path.is_file():
        return None
    data = _json_of(path, "outputs")
    if not isinstance(data, list):
        raise ArtefactError(
            f"{path}: must be a list of entries, not {type(data).__name__}"
        )
    out: list[OutputEntry] = []
    for n, entry in enumerate(cast(list[object], data), 1):
        if not isinstance(entry, dict):
            raise ArtefactError(f"{path}: entry {n} is not an object")
        e = cast(dict[str, object], entry)
        p, sha, lines, note = (
            e.get("path"),
            e.get("sha256"),
            e.get("lines"),
            e.get("note", ""),
        )
        if not isinstance(p, str) or not p:
            raise ArtefactError(f"{path}: entry {n} has no path")
        if sha is not None and not isinstance(sha, str):
            raise ArtefactError(f"{path}: entry {n}: sha256 is {sha!r}")
        if lines is not None and (
            isinstance(lines, bool) or not isinstance(lines, int)
        ):
            raise ArtefactError(f"{path}: entry {n}: lines is {lines!r}")
        rows_from = e.get("rows_from", {})
        cont = e.get("continues", [])
        if not isinstance(rows_from, dict) or not isinstance(cont, list):
            raise ArtefactError(f"{path}: entry {n}: rows_from/continues malformed")
        out.append(
            OutputEntry(
                Path(p),
                sha,
                lines,
                str(note),
                {str(k): int(v) for k, v in cast(dict[str, object], rows_from).items()},  # type: ignore[arg-type]
                tuple(str(c) for c in cast(list[object], cont)),
            )
        )
    return out


def read_completion(run_dir: Path) -> dict[str, object]:
    """A run's completion.json as a JSON object. Raises ArtefactError when it
    is missing, unreadable or not an object — the caller asks a completed
    run, whose marker this is (`completion_state` decides that, by markers)."""
    path = run_dir / "completion.json"
    data = _json_of(path, "completion")
    if not isinstance(data, dict):
        raise ArtefactError(f"{path}: must be a JSON object, not {type(data).__name__}")
    return cast(dict[str, object], data)


def read_metrics(path: Path) -> dict[str, object]:
    """A run's metrics.json as a JSON object. Raises MetricsError naming the
    file when it is unreadable, not JSON, or not an object — a list such as
    `["c1_pass"]` read as metrics once satisfied the guaranteed intent check
    (review 2026-10-08). Skipping an unreadable file chose the next older run
    as if the newer had reported no intent keys (review 2026-10-06)."""
    try:
        data = _json_of(path, "metrics")
    except ArtefactError as exc:
        raise MetricsError(str(exc)) from exc
    if not isinstance(data, dict):
        raise MetricsError(
            f"{path}: metrics must be a JSON object, not {type(data).__name__}"
        )
    return cast(dict[str, object], data)


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


@dataclass(frozen=True)
class RunSummary:
    """What a run is, for someone who returns to the area months later —
    the facts a reader otherwise collects from config.json keys and the
    patch file (a person with an assistant got 1 of 8 such questions right,
    code-navigation round 11, 2026-10-08)."""

    run_id: str
    state: str  # completion_state: completed | unfinalized | corrupt | …
    derived_from: str | None  # the run whose rows this one re-evaluated
    models: tuple[str, ...]  # model aliases the run resolved; () when none
    git: str  # the commit, "+dirty" when the tree was not clean
    uncommitted_bytes: int  # size of uncommitted.patch; 0 when the tree was clean
    command: str | None  # the command line that started it; None: not recorded


def run_summary(run_dir: Path) -> RunSummary:
    """Read one run folder into a RunSummary. Raises RunConfigError when its
    config.json is unreadable, ValueError when the folder has none."""
    cfg = read_run_config(run_dir)
    if cfg is None:
        raise ValueError(f"{run_dir}: no config.json — not a run folder")
    models = cfg.get("models_resolved")
    aliases = tuple(sorted(models)) if isinstance(models, dict) else ()
    patch = run_dir / "uncommitted.patch"
    argv = cfg.get("command")
    command = (
        " ".join(str(a) for a in argv) if isinstance(argv, list) and argv else None
    )
    derived = cfg.get("derived_from")
    return RunSummary(
        run_id=run_dir.name,
        state=completion_state(run_dir),
        derived_from=str(derived) if derived else None,
        models=aliases,
        git=str(cfg.get("git") or "?"),
        uncommitted_bytes=patch.stat().st_size if patch.is_file() else 0,
        command=command,
    )


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


# ---- which run answers for a protocol — one choice for intent-check,
# finalize and labkit-params (2026-10-08: it stood in intent_check and
# finalize alike; a third copy for the parameter view was the line)


def run_facts(run_dir: Path) -> dict | None:
    """What a run directory says about itself: state and binding.

    `None` for a directory without config.json — not a run. An unreadable
    config.json is a run in state `corrupt` with the reason in `why`: it
    stays in the listing the operator reads instead of vanishing, and it is
    never chosen (review 2026-10-06).
    """
    try:
        cfg = read_run_config(run_dir)
    except RunConfigError as exc:
        return {
            "dir": run_dir,
            "metrics": run_dir / "metrics.json",
            "state": "corrupt",
            "protocol_id": None,
            "why": str(exc),
        }
    if cfg is None:
        return None
    binding = cfg.get("protocol") or {}
    return {
        "dir": run_dir,
        "metrics": run_dir / "metrics.json",
        "state": run_state(run_dir, cfg, alive=False),
        "protocol_id": binding.get("id"),
    }


def bound_runs(area: Path, pid: str) -> tuple[list[dict], list[dict]]:
    """(runs bound to `pid` and completed, everything else), oldest first.

    Only the first list may feed an automatic choice. The second carries
    the reason it was left out, for the operator who has to look. The
    binding is the id and nothing else — `protocol.path` is a hint for
    humans, never a selection criterion: it goes stale by design.
    """
    taken, left = [], []
    for d in sorted((area / "runs").glob("*")):
        facts = run_facts(d)
        if facts is None:
            continue
        if facts["state"] != "completed":
            facts.setdefault("why", facts["state"])
        elif facts["protocol_id"] == pid:
            taken.append(facts)
            continue
        elif facts["protocol_id"]:
            facts["why"] = f"bound to {facts['protocol_id']}"
        else:
            facts["why"] = "unbound (no protocol id at run time)"
        left.append(facts)
    return taken, left


def newest_with_intent_keys(cands: list[dict]) -> tuple[Path | None, int]:
    """Among already-eligible runs: the newest reporting any intent key,
    plus how many newer ones were skipped for reporting none.

    The rule from 2026-09-09 (area 71) unchanged, only its input narrowed:
    a producer or probe run writes a metrics.json too, and holding the
    promises against THAT file reports every promise as unimplemented.
    """
    skipped = 0
    for facts in reversed(cands):
        if promises.reported_ids(read_metrics(facts["metrics"])):
            return facts["metrics"], skipped
        skipped += 1
    return (cands[-1]["metrics"], 0) if cands else (None, 0)


def newer_unreadable(chosen: Path, rest: list[dict]) -> str | None:
    """Why the choice must not stand: a run NEWER than the chosen one whose
    config.json cannot be read. Its binding is unknowable, so it may be the
    run that answers — choosing an older one past it is what
    `runs.read_run_config` says must not happen (review 2026-10-07)."""
    bad = [
        f
        for f in rest
        if f["state"] == "corrupt"
        and f["protocol_id"] is None
        and f["dir"].name > chosen.name
    ]
    if not bad:
        return None
    return (
        f"{len(bad)} newer run(s) cannot say which protocol they belong to — "
        + "; ".join(f["why"] for f in bad)
        + f". Repair or move them aside before {chosen.name} may answer."
    )


@dataclass(frozen=True)
class RunExclusion:
    """A run that could not answer, and why (for the operator who has to look)."""

    run_dir: Path
    why: str


@dataclass(frozen=True)
class AnsweringRun:
    """The outcome of choosing the run that answers for a protocol.

    Attributes:
        run_dir: The chosen run, or None when none may answer.
        skipped_newer: Newer bound runs passed over for reporting no intent
            key (a probe or producer run).
        exclusions: Every run left out, with its reason.
        blocker: Why no choice stands — no completed bound run, or a newer
            run whose binding cannot be read — or None.
    """

    run_dir: Path | None
    skipped_newer: int
    exclusions: tuple[RunExclusion, ...]
    blocker: str | None


def bound_answering_run(area: Path, pid: str) -> AnsweringRun:
    """The run every check holds the protocol to: the newest COMPLETED run
    bound to `pid` that reports an intent key. The binding is the run's own
    record, so the choice is a filter, not a guess; an unfinalized or corrupt
    run has numbers and no finish, a run bound elsewhere answers another
    question. A newer run whose config.json cannot be read blocks the
    choice: it may be the one that answers."""
    if not (area / "runs").is_dir():
        return AnsweringRun(None, 0, (), f"no runs/ directory in {area}")
    taken, rest = bound_runs(area, pid)
    exclusions = tuple(RunExclusion(f["dir"], f["why"]) for f in rest)
    if not taken:
        return AnsweringRun(None, 0, exclusions, f"no completed run bound to {pid}")
    mpath, skipped = newest_with_intent_keys(taken)
    assert mpath is not None, "taken is non-empty, so a metrics file exists"
    return AnsweringRun(
        mpath.parent, skipped, exclusions, newer_unreadable(mpath.parent, rest)
    )


def model_provenance_run(run_dir: Path) -> Path | None:
    """The run whose `models_resolved` says which model answered the rows
    `run_dir` reads: the run itself when it recorded one, else the nearest
    ancestor along `derived_from` that did (a derived run records none —
    its rows are the parent's, and resolving the alias anew would be
    provenance the rows never had). None when no run in the chain recorded
    a model.

    Raises:
        ValueError: If an ancestor is missing or the chain loops.
    """
    seen: list[str] = []
    here = run_dir
    while True:
        cfg = read_run_config(here)
        if cfg is None:
            raise ValueError(
                f"{here}: no config.json — the lineage of {run_dir.name} breaks here"
            )
        if cfg.get("models_resolved"):
            return here
        parent = cfg.get("derived_from")
        if parent is None:
            return None
        if not isinstance(parent, str) or not parent:
            raise ValueError(
                f"{here.name}: derived_from must name a run, not {parent!r}"
            )
        if parent in seen or parent == here.name:
            raise ValueError(
                f"{run_dir.name}: derived_from loops: {' -> '.join([*seen, here.name, parent])}"
            )
        seen.append(here.name)
        here = here.parent / parent
        if not here.is_dir():
            raise ValueError(
                f"{run_dir.name}: derived_from names {parent}, which is not under {run_dir.parent}"
            )


#: States that mean "this run is not a clean finish" — `--wait` exits 2 on
#: any of them, `reindex` rebuilds none of them. `unknown` is NOT in this
#: list: it means "can't tell", and treating it as failed would hide a run
#: that is still going.
FAILED_STATES = ("crashed", "unfinalized", "corrupt")
