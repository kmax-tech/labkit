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
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import cast

from labkit import promises
from labkit.repo import layout_root


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
    return runs_script(cmd, script)


def runs_script(cmd: str, script: str) -> bool:
    """Does the command line CMD run SCRIPT — as a word of its own or the last
    component of a path (`python /a/01_measure.py --x`)? Not as part of
    another name: `not_01_measure.py` held a dead run "running" while a
    substring decided it (review 2026-10-14). A directory with a space in
    its path still matches; the name is bounded, not the path split."""
    return re.search(rf"(?:^|[\s/]){re.escape(script)}(?:\s|$)", cmd) is not None


def run_state(run_dir: Path, cfg: dict, alive: bool | None) -> str:
    """One of: completed · running · unknown · crashed · unfinalized · corrupt
    (a run whose config.json cannot be read — damaged, or written before
    schema 2 — is `unreadable`: `run_facts`, `runlog.active`; this function
    never sees one, it takes a parsed cfg).

    metrics.json without completion.json is decided by liveness: alive →
    running, unknowable → unknown, dead → unfinalized.

    Complete when BOTH metrics.json and completion.json exist. Both, not
    completion.json alone: a completion record must not paper over results
    that were deleted or never landed. Hence `corrupt` — completion without
    metrics — which is a failure like `unfinalized`, not a finish.

    `alive is None` means the liveness check was undecidable (no `ps`, no
    script name). That is `unknown`, not `crashed` — claiming a process is
    dead when the evidence says "can't tell" is a false negative that hides
    a running run. `endpoint_lease` already treats None as conservatively
    alive; `run_state` uses the same contract.
    """
    has_metrics = (run_dir / "metrics.json").is_file()
    has_completion = (run_dir / "completion.json").is_file()
    if has_metrics and has_completion:
        return COMPLETED
    if alive is True:
        return "running"
    if alive is None:
        return "unknown"
    if has_completion:
        return "corrupt"
    return "unfinalized" if has_metrics else "crashed"


#: the one state every consumer that picks or accepts a run compares to
COMPLETED = "completed"
#: the width of every digest a run RECORDS (a data file, an output) — the
#: area stamp and a promise's scope hash keep `scope_sha.DIGEST_CHARS`;
#: `recheck.pin` compares by prefix, so the width is part of the format
RECORD_SHA_CHARS = 16

#: a run id is its start time plus four hex: `2026-10-13T14-00-57_071a`.
#: runlog writes it with RUN_ID_TIME; RUN_ID finds one in prose (a cited
#: run) and names a run directory (`fullmatch`); `run_started` reads the time.
RUN_ID_TIME = "%Y-%m-%dT%H-%M-%S"
RUN_ID = re.compile(
    r"\b(?P<date>\d{4}-\d{2}-\d{2})T(?P<h>\d{2})-(?P<m>\d{2})-(?P<s>\d{2})_[0-9a-f]{2,12}\b"
)


def run_started(run_id: str) -> datetime | None:
    """The start time a run id carries (local time), None for a name of another shape."""
    m = RUN_ID.fullmatch(run_id)
    if m is None:
        return None
    try:
        return datetime.fromisoformat(f"{m['date']}T{m['h']}:{m['m']}:{m['s']}")
    except ValueError:  # the shape of a run id, not a date: 2026-02-30T…
        return None


class RunConfigError(ValueError):
    """A run directory whose config.json exists but cannot be read."""


def acknowledged_unfrozen(run_dir: Path) -> bool:
    """Did RUN_DIR start on LABKIT_UNFROZEN=1 (`unfrozen_ack` in its
    config.json)? The one reading: protocol-fill marks the answer line with
    it, finalize warns, report-check refuses (2026-10-17). False for a run
    without config.json; an unreadable one raises RunConfigError.
    """
    cfg = read_run_config(run_dir)
    return cfg is not None and cfg.get("unfrozen_ack") is True


def run_instrument(run_dir: Path) -> str | None:
    """The instrument RUN_DIR ran under (`instrument` in its config.json,
    written by runlog from the protocol head, standard 0.20): model,
    estimator or count. The one reading for the gates that ask what the
    run did — finalize holds a model run to its `models_resolved` and
    names a one-draw spread with it. None for a run without config.json
    or without the key (a run of a labkit before 0.20); an unreadable
    config raises RunConfigError.
    """
    cfg = read_run_config(run_dir)
    return None if cfg is None else cfg.get("instrument")


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
    sha256: (
        str | None
    )  # the content's first RECORD_SHA_CHARS hex digits; None: absent at the end
    lines: int | None  # lines of a text file; None: absent or not text
    note: str = ""
    rows_from: dict[str, int] = field(
        default_factory=dict
    )  # run_id -> rows (JSONL, 0.72.3)
    continues: tuple[str, ...] = ()  # runs whose rows this file already held


def recorded_path(path: Path, inside: Path) -> str:
    """How a run's record (outputs.json, config.json `data`) writes PATH:
    relative to the root of the repo INSIDE lies in, when PATH lies in that
    repo, so a clone elsewhere reads the same record; absolute only for a file
    outside the repo. `resolve_recorded` reads it back. Absolute paths broke
    `02_analyze.py --check` and finalize's source check on every machine but
    the one that measured (a cloud run's `/home/user/...`, 2026-10-14); a
    relative `data=` path was kept relative to whatever the working directory
    was."""
    root = layout_root(inside).resolve()
    resolved = path.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return str(resolved)


def resolve_recorded(recorded: str, inside: Path) -> Path:
    """A path as `recorded_path` wrote it, made absolute against the root of
    the repo INSIDE lies in; an absolute record stays as it is."""
    p = Path(recorded)
    return p if p.is_absolute() else layout_root(inside) / p


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
    return [
        _output_entry(path, n, entry, run_dir)
        for n, entry in enumerate(cast(list[object], data), 1)
    ]


def _is_count(value: object) -> bool:
    """An integer that is not a bool — JSON `true` is no line or row count."""
    return isinstance(value, int) and not isinstance(value, bool)


def _output_entry(path: Path, n: int, entry: object, run_dir: Path) -> OutputEntry:
    """Entry N of outputs.json PATH, or ArtefactError naming what is wrong; a
    relative path is resolved against the repo RUN_DIR lives in."""
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
    if lines is not None and not _is_count(lines):
        raise ArtefactError(f"{path}: entry {n}: lines is {lines!r}")
    rows_from = e.get("rows_from", {})
    cont = e.get("continues", [])
    if not isinstance(rows_from, dict) or not isinstance(cont, list):
        raise ArtefactError(f"{path}: entry {n}: rows_from/continues malformed")
    rows = cast(dict[str, object], rows_from)
    for run_id, count in rows.items():
        if not _is_count(count):
            raise ArtefactError(
                f"{path}: entry {n}: rows_from[{run_id!r}] is {count!r}, not a row count"
            )
    return OutputEntry(
        resolve_recorded(p, run_dir),
        sha,
        cast(int | None, lines),
        str(note),
        {str(k): cast(int, v) for k, v in rows.items()},
        tuple(str(c) for c in cast(list[object], cont)),
    )


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
    # written before labkit 0.21 (when metrics.json alone marked a finish):
    # 0.89.0 dropped the `legacy` state that listed such a run (CHANGELOG)
    before_schema = "a run of labkit before 0.21 — read it with labkit 0.47"
    sv = cfg.get("schema_version")
    if sv is None:
        return f"no schema_version: {before_schema}"
    if not isinstance(sv, int) or isinstance(sv, bool):
        return f"schema_version = {sv!r}, not an integer"
    if sv < 2:
        return f"schema_version = {sv}, below 2: {before_schema}"
    binding = cfg.get("protocol")
    if binding is not None:
        if not isinstance(binding, dict):
            return f"protocol = {binding!r}, not an object"
        for key in ("id", "path"):
            if binding.get(key) is not None and not isinstance(binding[key], str):
                return f"protocol.{key} = {binding[key]!r}, not a string"
    return _repeat_shape_problem(cfg)


def _repeat_shape_problem(cfg: dict) -> str | None:
    """`repeat_of` null or a run id; `draw` null without it, an integer >= 2
    with it. A damaged value read as "no repeat" put a repeat back into the
    answering choice — loud instead (review 2026-10-15)."""
    parent, draw = cfg.get("repeat_of"), cfg.get("draw")
    if parent is None:
        return None if draw is None else f"draw = {draw!r} without repeat_of"
    if not isinstance(parent, str) or RUN_ID.fullmatch(parent) is None:
        return f"repeat_of = {parent!r}, not a run id"
    if not isinstance(draw, int) or isinstance(draw, bool) or draw < 2:
        return f"draw = {draw!r} for a repeat, not an integer >= 2"
    return None


def completion_state(run_dir: Path) -> str:
    """`run_state` of a run directory read from disk, liveness not asked.

    The one question every consumer that picks or accepts a run must ask —
    recheck, a derived run's parent, intent-check's choice, the usability
    scorer. Asking `metrics.json` alone let an unfinalized v2 run (metrics,
    no completion record) be rechecked as a kept number and accepted as a
    parent (review 2026-10-06). A directory without config.json is not a
    run, and an unreadable config.json is a damaged one: both raise
    RunConfigError — neither may vanish and let an older run be chosen in
    its place.
    """
    cfg = read_run_config(run_dir)
    if cfg is None:
        raise RunConfigError(f"{run_dir}: no config.json — not a run directory")
    return run_state(run_dir, cfg, alive=False)


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
    git: str  # the commit at start, "+dirty" when the tree was not clean (untracked files count)
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


@dataclass(frozen=True)
class RunDir:
    """One directory under `runs/` and what its config.json says: `config`
    None and `error` None is no run (no config.json); `error` set is a run
    whose metadata cannot be read (the RunConfigError's sentence)."""

    dir: Path
    config: dict | None
    error: str | None


def _run_dir(d: Path) -> RunDir:
    try:
        return RunDir(d, read_run_config(d), None)
    except RunConfigError as exc:
        return RunDir(d, None, str(exc))


def run_dirs(area: Path) -> list[RunDir]:
    """Every directory under the area's `runs/`, oldest first (run_ids start
    with the timestamp, so name order is start order), each with its
    metadata read once. The one walk: listing, index, choice and completion
    used to walk `runs/` six times and each decided for itself what an
    unreadable run means (audit 2026-10-13). Here it is data — the caller
    says whether it refuses, reports or skips."""
    runs = area / "runs"
    if not runs.is_dir():
        return []
    return [_run_dir(d) for d in sorted(runs.glob("*")) if d.is_dir()]


def completed_runs(area: Path, *, with_repeats: bool) -> list[Path]:
    """The area's completed run directories, oldest first; WITH_REPEATS says
    whether a repeat draw (`repeat_of`) counts — every caller decides it in
    sight, since a "newest run" that is a repeat would displace the run that
    answers. An unreadable run raises RunConfigError: it may be the newest
    and must not vanish."""
    out = []
    for rd in run_dirs(area):
        if rd.error is not None:
            raise RunConfigError(rd.error)
        if (
            rd.config is not None
            and run_state(rd.dir, rd.config, alive=False) == COMPLETED
            and (with_repeats or repeat_parent(rd.config) is None)
        ):
            out.append(rd.dir)
    return out


def write_atomic(path: Path, text: str) -> None:
    """Write `text` whole or not at all: a temp file beside `path`, then
    rename — a reader sees the old file or the new one, never half of
    either. Every record file of a run (config, outputs, metrics,
    completion) and the lease write through it; the index is appended
    under its lock. Staged beside the target, not outside its directory
    (CODE-013): the same filesystem is certain there, and every reader asks
    for a record by name or lists directories — a `.config.json.tmp<pid>`
    next to it is never read as one."""
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---- which run answers for a protocol — one choice for intent-check,
# finalize and labkit-params (2026-10-08: it stood in intent_check and
# finalize alike; a third copy for the parameter view was the line)


def run_facts(run_dir: Path) -> dict | None:
    """What a run directory says about itself: state and binding.

    `None` for a directory without config.json — not a run. An unreadable
    config.json is a run in state `unreadable` with the reason in `why`: it
    stays in the listing the operator reads instead of vanishing, and it is
    never chosen (review 2026-10-06). Not `corrupt` — that word is
    completion.json without metrics.json (0.74.0).

    Liveness is not asked here (`alive=False`): a run still finalizing in
    another process reads as `unfinalized`; `runlog.active` asks.
    """
    return _facts(_run_dir(run_dir))


def _facts(rd: RunDir) -> dict | None:
    if rd.error is not None:
        return {
            "dir": rd.dir,
            "metrics": rd.dir / "metrics.json",
            "state": "unreadable",
            "protocol_id": None,
            "why": rd.error,
        }
    if rd.config is None:
        return None
    binding = rd.config.get("protocol") or {}
    return {
        "dir": rd.dir,
        "metrics": rd.dir / "metrics.json",
        "state": run_state(rd.dir, rd.config, alive=False),
        "protocol_id": binding.get("id"),
    }


def repeat_parent(config: dict) -> str | None:
    """The run a repeat draws again (config.json `repeat_of`), or None.

    `derived_from` re-reads the parent's rows and makes no model call;
    `repeat_of` asks the model again with the same instrument on the same
    items — a full measurement with its own model record, recorded so the
    spread of the number is visible (TODO item 4, 2026-10-14). A repeat is
    supporting evidence: it never answers the protocol (`bound_runs`)."""
    v = config.get("repeat_of")
    if v is None:
        return None
    if not isinstance(v, str) or RUN_ID.fullmatch(v) is None:
        raise RunConfigError(f"repeat_of = {v!r}, not a run id")
    return v


def repeats_of(area: Path, run_id: str) -> list[Path]:
    """The completed repeats of RUN_ID in draw order (2, 3, …) — by the
    recorded `draw`, not by name: run ids carry the start second and a random
    suffix, so two repeats started in one second sort by chance."""
    return [d for _, d in _numbered_repeats(area, run_id)]


def _repeats(area: Path, run_id: str) -> list[tuple[int, RunDir]]:
    """(recorded draw, run) of every repeat of RUN_ID ever started.

    Raises RunConfigError for a run whose config.json cannot be read — it
    cannot say whether it is a draw of RUN_ID, and dropping it would show a
    spread over fewer draws than were taken, or hand its number out again —
    and for a repeat without an integer `draw` (2026-10-15)."""
    found: list[tuple[int, RunDir]] = []
    for rd in run_dirs(area):
        if rd.error is not None:
            raise RunConfigError(rd.error)
        if rd.config is None or repeat_parent(rd.config) != run_id:
            continue
        draw = rd.config.get("draw")
        if not isinstance(draw, int) or isinstance(draw, bool):
            raise RunConfigError(
                f"{rd.dir}/config.json: a repeat without an integer `draw`"
            )
        found.append((draw, rd))
    return found


def _numbered_repeats(area: Path, run_id: str) -> list[tuple[int, Path]]:
    """(recorded draw, run dir) of RUN_ID's completed repeats, by draw. Two
    completed repeats with one draw number raise: the lock reserves each
    number once, so a second holder was copied or written by hand."""
    found = sorted(
        (draw, rd.dir)
        for draw, rd in _repeats(area, run_id)
        if rd.config is not None
        and run_state(rd.dir, rd.config, alive=False) == COMPLETED
    )
    for (a, da), (b, db) in zip(found, found[1:]):
        if a == b:
            raise RunConfigError(
                f"{da.name} and {db.name} both record draw {a} of {run_id}"
            )
    return found


def next_draw(area: Path, run_id: str) -> int:
    """The draw number a new repeat of RUN_ID gets: the run itself is draw 1,
    every repeat ever started — completed, running or crashed — holds its
    number, so the next is one past the highest. runlog counts it under its
    index lock (Run.draw); a crashed draw leaves a gap, never a reuse."""
    return 1 + max([1, *(draw for draw, _ in _repeats(area, run_id))])


def draws(area: Path, run_id: str) -> list[tuple[int, Path]]:
    """(draw, run dir) for RUN_ID and its completed repeats, draw 1 first —
    what an analysis reads to show the spread of the number."""
    return [(1, area / "runs" / run_id), *_numbered_repeats(area, run_id)]


def repeat_mismatch(
    parent: dict, new: dict, draw_keys: tuple[str, ...] = ()
) -> list[str]:
    """Why a run whose config.json would be NEW is no comparable repeat of
    PARENT (both config.json dicts), [] when it is: the same protocol, the
    same promise snapshot (block and every declared scope's digest), the same
    measure script, the same resolved model, the same experiment config
    (prompt digest, model alias, constants, sampling) and the same inputs
    (data= digests and rows) — the job set follows from these. A
    repeat that differs in any of these measures something else, and its
    spread would be noise of the change, not of the model. DRAW_KEYS are
    the config keys a draw may differ in by declaration — an estimator's
    `seed`: its spread over seeds is its draws (2026-10-17)."""
    out: list[str] = []
    pid = (parent.get("protocol") or {}).get("id")
    if pid != (new.get("protocol") or {}).get("id"):
        out.append(f"protocol {(new.get('protocol') or {}).get('id')} is not {pid}")
    pp, np_ = parent.get("promises") or {}, new.get("promises") or {}
    if pp.get("block_sha") != np_.get("block_sha"):
        out.append("the promise block changed")
    elif pp != np_:
        # same block, other code: a declared scope's digest moved
        out.append("the code a promise rests on changed (declared_scope_sha)")
    if parent.get("script_sha") != new.get("script_sha"):
        out.append("the measure script changed (script_sha)")
    if (parent.get("models_resolved") or {}) != (new.get("models_resolved") or {}):
        out.append("the model resolved differently (models_resolved)")
    pc, nc = parent.get("config") or {}, new.get("config") or {}
    for key in sorted(set(pc) | set(nc)):
        if key not in draw_keys and pc.get(key) != nc.get(key):
            out.append(f"config {key}: {pc.get(key)!r} → {nc.get(key)!r}")

    def digests(cfg: dict) -> dict:
        return {
            k: (v.get("sha256"), v.get("rows"))
            for k, v in (cfg.get("data") or {}).items()
            if isinstance(v, dict)
        }

    if digests(parent) != digests(new):
        out.append("the inputs (data=) differ")
    return out


def bound_runs(area: Path, pid: str) -> tuple[list[dict], list[dict]]:
    """(runs bound to `pid` and completed, everything else), oldest first.

    Only the first list may feed an automatic choice. The second carries
    the reason it was left out, for the operator who has to look. The
    binding is the id and nothing else — `protocol.path` is a hint for
    humans, never a selection criterion: it goes stale by design.
    """
    taken, left = [], []
    for rd in run_dirs(area):
        facts = _facts(rd)
        if facts is None:
            continue
        parent = repeat_parent(rd.config) if rd.config is not None else None
        if facts["state"] != COMPLETED:
            facts.setdefault("why", facts["state"])
        elif parent is not None:
            facts["why"] = (
                f"a repeat of {parent} — supporting evidence, never the answer"
            )
        elif facts["protocol_id"] == pid:
            taken.append(facts)
            continue
        elif facts["protocol_id"]:
            facts["why"] = f"bound to {facts['protocol_id']}"
        else:
            facts["why"] = "unbound (no protocol id at run time)"
        left.append(facts)
    return taken, left


def newest_with_intent_keys(cands: list[dict]) -> tuple[Path | None, int, bool]:
    """Among already-eligible runs: (metrics path, newer runs skipped for
    reporting no intent key, whether the chosen one reports any).

    The rule from 2026-09-09 (area 71) unchanged, only its input narrowed:
    a producer or probe run writes a metrics.json too, and holding the
    promises against THAT file reports every promise as unimplemented.
    When NO candidate reports an intent key, the newest is returned with
    skipped = 0 and reports_intent_keys = False — the caller says so,
    instead of a probe run passing as the answer (2026-10-09).
    """
    skipped = 0
    for facts in reversed(cands):
        if promises.reported_ids(read_metrics(facts["metrics"])):
            return facts["metrics"], skipped, True
        skipped += 1
    return (cands[-1]["metrics"], 0, False) if cands else (None, 0, False)


def start_second(run_dir: Path) -> str:
    """The start second a run id carries (everything before the suffix):
    two runs that share it sort by their random suffix, not by start."""
    return run_dir.name.rsplit("_", 1)[0]


def same_second(a: Path, b: Path) -> bool:
    """Whether two DIFFERENT runs started in the same second — the one rule
    for a tie the run ids cannot break: the answering choice, its
    unreadable-run guard and `newest_completed` all ask here (until 0.97.1
    the scorer compared the seconds itself, audit 2026-10-15)."""
    return a != b and start_second(a) == start_second(b)


def _not_older(run_dir: Path, chosen: Path) -> bool:
    """Whether RUN_DIR may have started after CHOSEN: newer by name, or
    started in the same second — the random suffix orders those by chance
    (2026-10-15)."""
    return run_dir.name > chosen.name or same_second(run_dir, chosen)


def newest_completed(area: Path, *, with_repeats: bool) -> Path | None:
    """The newest completed run of the area (`completed_runs`), None without
    one — refusing a tie: when the last two started in the same second the
    run ids cannot say which is newest. The scorer's run and runlog's
    "last finished" line read here; the answering choice adds the binding
    and the intent keys (`bound_answering_run`).

    Raises:
        RunConfigError: An unreadable run, or two newest runs in one second.
    """
    done = completed_runs(area, with_repeats=with_repeats)
    if len(done) >= 2 and same_second(done[-1], done[-2]):
        raise RunConfigError(
            f"{done[-2].name} and {done[-1].name} started in the same second — "
            f"the run ids cannot say which is newest; move the one that does "
            f"not count out of runs/"
        )
    return done[-1] if done else None


def newer_unreadable(chosen: Path, rest: list[dict]) -> str | None:
    """Why the choice must not stand: a run NEWER than the chosen one, or
    started in the same second, whose config.json cannot be read. Its
    binding is unknowable, so it may be the run that answers — choosing an
    older one past it is what `runs.read_run_config` says must not happen
    (review 2026-10-07)."""
    bad = [
        f for f in rest if f["state"] == "unreadable" and _not_older(f["dir"], chosen)
    ]
    if not bad:
        return None
    return (
        f"{len(bad)} newer run(s) cannot say which protocol they belong to — "
        + "; ".join(f["why"] for f in bad)
        + f". Repair or move them aside before {chosen.name} may answer."
    )


def same_second_rival(chosen: Path, taken: list[dict], has_keys: bool) -> str | None:
    """Why the choice must not stand: another bound run of the same standing
    (reporting an intent key, if the chosen one does) started in the same
    second. The run id carries the second and a random suffix, so which of
    the two is newest is chance (2026-10-15)."""
    rivals = [
        f["dir"].name
        for f in taken
        if same_second(f["dir"], chosen)
        and (not has_keys or promises.reported_ids(read_metrics(f["metrics"])))
    ]
    if not rivals:
        return None
    return (
        f"{chosen.name} and {', '.join(rivals)} started in the same second — "
        "the run ids cannot say which is newest. Move the one that does not "
        "answer out of runs/."
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
        run_dir: The chosen run; None whenever `blocker` is set, so a caller
            that reads only run_dir cannot take a run that must not answer.
        skipped_newer: Newer bound runs passed over for reporting no intent
            key (a probe or producer run).
        reports_intent_keys: False when no bound run reports an intent key
            and the newest was taken anyway — a probe or producer run, not
            an answer; the caller names it.
        exclusions: Every run left out, with its reason.
        blocker: Why no choice stands — no completed bound run, or a newer
            run whose binding cannot be read — or None.
    """

    run_dir: Path | None
    skipped_newer: int
    exclusions: tuple[RunExclusion, ...]
    blocker: str | None
    reports_intent_keys: bool = True

    def explain(self, ids_registered: bool) -> tuple[str | None, list[str]]:
        """(why no run may answer, or None; the lines that say what was
        looked at) — ONE telling for finalize, intent-check, recheck, params
        and the audit, which each rendered this four ways with four
        semantics (audit 2026-10-15). A chosen run that reports no intent
        key while the protocol registers ids is a blocker here, everywhere:
        a probe or producer run is not an answer."""
        if self.run_dir is None:
            return self.blocker, [f"{x.run_dir.name}: {x.why}" for x in self.exclusions]
        if ids_registered and not self.reports_intent_keys:
            return (
                f"{self.run_dir.name} is the newest bound run, and no bound run "
                f"reports an intent key — a probe or producer run, not an answer",
                [],
            )
        lines = []
        if self.skipped_newer:
            lines.append(
                f"skipped {self.skipped_newer} newer bound run(s) without intent keys"
            )
        return None, lines


def bound_answering_run(area: Path, pid: str) -> AnsweringRun:
    """The run every check holds the protocol to: the newest COMPLETED run
    bound to `pid` that reports an intent key. The binding is the run's own
    record, so the choice is a filter, not a guess; an unfinalized or corrupt
    run has numbers and no finish, a run bound elsewhere answers another
    question. A newer run whose config.json cannot be read (`unreadable`)
    blocks the choice: it may be the one that answers — then run_dir is
    None and `blocker` says why. So does a rival started in the same
    second, whose order the run ids cannot tell."""
    if not (area / "runs").is_dir():
        return AnsweringRun(
            None,
            0,
            (),
            f"no completed run bound to {pid} — no runs/ directory in {area}",
        )
    taken, rest = bound_runs(area, pid)
    exclusions = tuple(RunExclusion(f["dir"], f["why"]) for f in rest)
    if not taken:
        return AnsweringRun(None, 0, exclusions, f"no completed run bound to {pid}")
    mpath, skipped, has_keys = newest_with_intent_keys(taken)
    assert mpath is not None, "taken is non-empty, so a metrics file exists"
    blocker = newer_unreadable(mpath.parent, rest) or same_second_rival(
        mpath.parent, taken, has_keys
    )
    if blocker:
        return AnsweringRun(None, skipped, exclusions, blocker, has_keys)
    return AnsweringRun(mpath.parent, skipped, exclusions, None, has_keys)


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
FAILED_STATES = ("crashed", "unfinalized", "corrupt", "unreadable")
