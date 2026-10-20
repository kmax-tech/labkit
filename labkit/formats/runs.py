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

from labkit.formats.repo import layout_root


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


def as_stored(value: object) -> str:
    """VALUE as a run's JSON files store it, keys sorted: the one equality
    of stored values — two are the same only when their texts are, so `1`
    is not `true`, `1` is not `1.0`, a tuple is its list and NaN is NaN.
    Python's `==` takes `True == 1` and `1 == 1.0`, and a checker built on
    it passed a recomputation of another type (review 2026-10-20). Raises
    TypeError for a value JSON cannot hold."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


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


def unreportable(cfg: dict) -> list[str]:
    """Why the number of the run CFG records cannot be reported — empty when
    it is a full run on a protocol the freeze gate let through.

    A full run declares `long=True`; its record carries `long` (since
    0.99.0) and `unfrozen_ack` (a full run acknowledged over an unfrozen
    protocol with `LABKIT_UNFROZEN=1`). Both are the run's own words at
    start, so the question is a read, not a guess. The marks are one telling
    for finalize (a warning) and report-check (a blocker): in the second
    haiku round on labkit 0.98.0 (labkit-paper area 09, t3 and t18) the
    agents measured without `long=True` and reported the probe's number;
    neither gate asked whether the answering run was a full run. A record
    without `long` was written by labkit before 0.99.0 and cannot say — that
    is a mark too, not a pass (no legacy reading). The word is "probe", not
    "pilot": the agents of those rounds called their shortcut a pilot, and
    labkit's own messages had offered them the word (review 2026-10-18).
    """
    marks = []
    long = cfg.get("long")
    if not isinstance(long, bool):
        marks.append(
            "the record does not say whether it was a full run (`long`, "
            "recorded since 0.99.0) — a run of an earlier labkit, or a damaged record"
        )
    elif not long:
        marks.append("a probe (long=False), not a full run")
    if cfg.get("unfrozen_ack") is True:
        marks.append(
            "a full run acknowledged over an unfrozen protocol with LABKIT_UNFROZEN=1"
        )
    return marks


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


def read_run_dir(d: Path) -> RunDir:
    """The `RunDir` of directory D, its config.json read once; an unreadable
    one is carried in `error`, never raised."""
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
    return [read_run_dir(d) for d in sorted(runs.glob("*")) if d.is_dir()]


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


#: States that mean "this run is not a clean finish" — `--wait` exits 2 on
#: any of them, `reindex` rebuilds none of them. `unknown` is NOT in this
#: list: it means "can't tell", and treating it as failed would hide a run
#: that is still going.
FAILED_STATES = ("crashed", "unfinalized", "corrupt", "unreadable")
