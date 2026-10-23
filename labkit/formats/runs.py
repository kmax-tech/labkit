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
import time
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal, cast

from labkit.formats.files import write_atomic
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


#: a JSON object as a run's record files hold it (config.json, completion.json):
#: labkit's own keys are checked when the file is read (`read_run_config`),
#: the experiment's config and metrics keys stay free — Any, not a schema
JsonObject = dict[str, Any]

#: Current run-record format; the writer and reader use the same version.
RUN_SCHEMA = 3

RunKind = Literal["preparation", "probe", "measurement"]


def parse_run_kind(value: object) -> RunKind:
    """Validate the declared purpose of a run, naming the field on failure."""
    if value == "preparation":
        return "preparation"
    if value == "probe":
        return "probe"
    if value == "measurement":
        return "measurement"
    raise ValueError(
        f"run_kind = {value!r}; expected 'preparation', 'probe' or 'measurement'"
    )


#: what a run directory is — the closed set every reader compares to:
#: `run_state` gives the first six, `unreadable` is a run whose config.json
#: cannot be read (`RunDir.error`)
RunState = Literal[
    "completed", "running", "unknown", "crashed", "unfinalized", "corrupt", "unreadable"
]


def run_state(run_dir: Path, alive: bool | None) -> RunState:
    """One of: completed · running · unknown · crashed · unfinalized · corrupt
    (a run whose config.json cannot be read — damaged, or written before
    schema 3 — is `unreadable`: `run_facts`, `runlog.active`; this function
    never sees one, its caller has read the config).

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
    has_metrics = metrics_path(run_dir).is_file()
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
COMPLETED: Final = "completed"
UNREADABLE: Final = "unreadable"
#: the width of every digest a run RECORDS (a data file, an output) — the
#: area stamp and a promise's scope hash keep `scope_sha.DIGEST_CHARS`;
#: `recheck.pin` compares by prefix, so the width is part of the format
RECORD_SHA_CHARS = 16

#: a run id is its start time plus four hex: `2026-10-13T14-00-57_071a`.
#: runlog writes it with RUN_ID_TIME; RUN_ID finds one in prose (a cited
#: run) and names a run directory (`fullmatch`); `run_started` reads the time.
RUN_ID_TIME = "%Y-%m-%dT%H-%M-%S"
#: the local time a record states (`started`, `finished`, a lock's holder,
#: a staged probe): `2026-10-13T14:00:57`, read back by `fromisoformat`.
RECORD_TIME = "%Y-%m-%dT%H:%M:%S"


def now_stamp() -> str:
    """The local time now in RECORD_TIME — the one spelling of a record's time."""
    return time.strftime(RECORD_TIME)


#: why a run broke off, written by `runlog.run` when the block raises — the
#: exception's type and message; without it a crashed run showed only that
#: it crashed (a claude-cli answer another model wrote ends a run loudly,
#: and the reason stood on stderr alone, 2026-10-23)
FAILURE_FILE = "failure.json"
#: the folder under an area that holds its runs, and the file of the values
#: reported through `run.metrics(...)` — the one spelling of each (audit
#: 2026-10-23: about twenty call sites spelled `area / "runs" / id` and
#: `run / "metrics.json"` by hand)
RUNS_DIR = "runs"
METRICS_FILE = "metrics.json"


def runs_path(area: Path) -> Path:
    """AREA's `runs/` — every run directory lies directly in it."""
    return area / RUNS_DIR


def run_path(area: Path, run_id: str) -> Path:
    """`runs/<RUN_ID>/` of AREA: the run's directory (`run_dir` in every
    signature that takes one)."""
    return area / RUNS_DIR / run_id


def metrics_path(run_dir: Path) -> Path:
    """RUN_DIR's `metrics.json`."""
    return run_dir / METRICS_FILE


def write_failure(
    run_dir: Path, exc_type: type[BaseException], exc: BaseException | None
) -> Path:
    """Write RUN_DIR/failure.json: the exception's type, its message and the
    time; return its path. Raises OSError when it cannot be written."""
    path = run_dir / FAILURE_FILE
    write_atomic(
        path,
        json.dumps(
            {"error": exc_type.__name__, "message": str(exc or ""), "at": now_stamp()},
            indent=1,
        ),
    )
    return path


def read_failure(run_dir: Path) -> str | None:
    """`<Type>: <message>` from RUN_DIR/failure.json, None when the run left
    none; RunConfigError when it is there and cannot be read."""
    path = run_dir / FAILURE_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return f"{data['error']}: {data['message']}"
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
        raise RunConfigError(f"{path}: unreadable ({exc})") from exc


RUN_ID = re.compile(
    r"\b(?P<date>\d{4}-\d{2}-\d{2})T(?P<h>\d{2})-(?P<m>\d{2})-(?P<s>\d{2})_[0-9a-f]{2,12}\b"
)
#: what reads as a run id in prose: RUN_ID's time with any suffix. A cited
#: token of this shape that is not a RUN_ID names no run runlog wrote —
#: an agent typed `…T12-48-00_final` into the Answer, and a gate that saw
#: only RUN_ID saw no citation and let it through (labkit-paper area 08,
#: 2026-10-21)
RUN_ID_LIKE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_[\w-]+")


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


def read_run_config(run_dir: Path) -> RunConfig | None:
    """A run's metadata, read and checked once (`parse_run_config`), None
    when the directory has no config.json.

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
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise RunConfigError(
            f"{cfg_file}: unreadable run metadata ({exc}) — the run cannot "
            f"say what it is; repair or move it aside"
        ) from exc
    try:
        return parse_run_config(cfg)
    except RunConfigError as exc:
        raise RunConfigError(
            f"{cfg_file}: unreadable run metadata ({exc}) — repair or move it aside"
        ) from exc


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
        default_factory=dict[str, int]
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


def _schema_problem(sv: object) -> str | None:
    """Why a record's schema version cannot be read by this package."""
    # written before labkit 0.21 (when metrics.json alone marked a finish):
    # 0.89.0 dropped the `legacy` state that listed such a run (CHANGELOG)
    before_schema = "a run of labkit before 0.21 — read it with labkit 0.47"
    if sv is None:
        return f"no schema_version: {before_schema}"
    if not isinstance(sv, int) or isinstance(sv, bool):
        return f"schema_version = {sv!r}, not an integer"
    if sv < 2:
        return f"schema_version = {sv}, below 2: {before_schema}"
    if sv < RUN_SCHEMA:
        return "schema_version = 2; read this record with labkit 0.99.0"
    if sv != RUN_SCHEMA:
        return f"schema_version = {sv}; expected {RUN_SCHEMA}"
    return None


#: labkit's own tables in config.json: each an object or null (`promises`
#: is null for a protocol without a block). Held on read — a damaged one
#: read as an empty table let a repeat with an empty config pass as
#: comparable (review 2026-10-20).
RECORD_TABLES = ("config", "data", "models_resolved", "promises")


def _derived_shape_problem(cfg: JsonObject) -> str | None:
    """`derived_from` null or a run id: the parent is a run of the same
    runs/ directory, named, never a path — `./<own run>` looped the walk
    forever and `../../<elsewhere>` left the area (review 2026-10-20)."""
    parent = cfg.get("derived_from")
    if parent is None or (isinstance(parent, str) and RUN_ID.fullmatch(parent)):
        return None
    return (
        f"derived_from = {parent!r} must name a run of this runs/ directory (a run id)"
    )


def _repeat_shape_problem(cfg: JsonObject) -> str | None:
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


def unreportable(cfg: RunConfig) -> list[str]:
    """Reasons this run cannot supply a reported result.

    Only a measurement without an unfrozen acknowledgement is eligible;
    the release gate checks completion, audits and recomputation separately.
    """
    marks: list[str] = []
    if cfg.run_kind != "measurement":
        marks.append(f"a {cfg.run_kind} (run_kind={cfg.run_kind!r}), not a measurement")
    if cfg.unfrozen_ack:
        marks.append(
            "a full run acknowledged over an unfrozen protocol with LABKIT_UNFROZEN=1"
        )
    return marks


#: what a run records as its `git` when it started outside a repository
#: (`provenance.git_state` writes it; `recorded_commit` reads it)
NO_GIT: Final = "no-git"
#: the mark `git_state` appends when the tree differed from the commit
DIRTY_MARK: Final = "+dirty"


def recorded_commit(cfg: RunConfig) -> str | None:
    """The commit CFG's run started at (HEAD's short sha as recorded, the
    `+dirty` mark stripped), or None when it started outside a repository
    (NO_GIT). Whether the tree was dirty is `cfg.git.endswith(DIRTY_MARK)`:
    the commit says what stood committed, the mark that more stood in the
    tree."""
    commit = cfg.git.removesuffix(DIRTY_MARK)
    return None if commit in ("", NO_GIT) else commit


def completion_state(run_dir: Path) -> RunState:
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
    return run_state(run_dir, alive=False)


@dataclass(frozen=True)
class RunSummary:
    """What a run is, for someone who returns to the area months later —
    the facts a reader otherwise collects from config.json keys and the
    patch file (a person with an assistant got 1 of 8 such questions right,
    code-navigation round 11, 2026-10-08)."""

    run_id: str
    state: RunState  # run_state, liveness not asked
    run_kind: RunKind  # preparation · probe · measurement, as config.json records it
    derived_from: str | None  # the run whose rows this one re-evaluated
    models: tuple[str, ...]  # model aliases the run resolved; () when none
    git: str  # the commit at start, "+dirty" when the tree was not clean (untracked files count)
    uncommitted_bytes: int  # size of uncommitted.patch; 0 when the tree was clean
    command: str | None  # the command line that started it; None: not recorded


def run_summary(run_dir: Path) -> RunSummary:
    """Read one run folder into a RunSummary, its config.json once. Raises
    RunConfigError when it is unreadable, ValueError when the folder has none."""
    cfg = read_run_config(run_dir)
    if cfg is None:
        raise ValueError(f"{run_dir}: no config.json — not a run folder")
    return summarize(run_dir, cfg)


def summarize(run_dir: Path, cfg: RunConfig) -> RunSummary:
    """The RunSummary of RUN_DIR from CFG, its config.json as already read
    (`run_dirs`) — a listing reads each run once, not once per fact."""
    patch = run_dir / "uncommitted.patch"
    return RunSummary(
        run_id=run_dir.name,
        state=run_state(run_dir, alive=False),
        run_kind=cfg.run_kind,
        derived_from=cfg.derived_from,
        models=tuple(sorted(cfg.models_resolved)),
        git=cfg.git or "?",
        uncommitted_bytes=patch.stat().st_size if patch.is_file() else 0,
        command=" ".join(cfg.command) if cfg.command else None,
    )


@dataclass(frozen=True)
class ProtocolBinding:
    """The protocol a run was started under, as config.json `protocol`
    records it. `id` is the binding — every choice of a run filters by it;
    `path` is a hint for a person and goes stale by design. Both None:
    the run is unbound."""

    id: str | None
    path: str | None


def binding_of(cfg: JsonObject) -> ProtocolBinding:
    """The run's binding, the one reading of `cfg["protocol"]` — absent or
    null is unbound. `read_run_config` refuses a malformed table on read;
    a config built in memory (a run about to be written) is held to the
    same shape here. Raises RunConfigError naming the field."""
    table = cfg.get("protocol")
    if table is None:
        return ProtocolBinding(None, None)
    if not isinstance(table, dict):
        raise RunConfigError(f"protocol = {table!r}, not an object")
    table = cast(JsonObject, table)
    missing = [key for key in ("id", "path") if key not in table]
    if missing:
        raise RunConfigError(
            f"protocol.{', protocol.'.join(missing)} missing — the binding carries "
            f"both, null where there is none"
        )
    extra = sorted(set(table) - {"id", "path"})
    if extra:
        raise RunConfigError(
            f"protocol.{', protocol.'.join(extra)}: not a field of the binding"
        )
    found: list[str | None] = []
    for key in ("id", "path"):
        value = table.get(key)
        if value is not None and not isinstance(value, str):
            raise RunConfigError(f"protocol.{key} = {value!r}, not a string")
        found.append(value)
    return ProtocolBinding(found[0], found[1])


#: every field of config.json, as `runlog.Run._write_record` writes it: the
#: type it holds, and whether null is a value the writer writes (a run
#: without parent, repeat, draw, failed audit, tier or promise block). A
#: record carries EVERY field — a missing one is no null and no default:
#: dropping `"unfrozen_ack": true` once made an acknowledged run reportable
#: (review 2026-10-20). A key outside the table is refused as well: the
#: writer is the record's only author. The experiment's own settings live
#: inside `config` and stay free.
_FIELDS: dict[str, tuple[type, bool]] = {
    "schema_version": (int, False),
    "experiment": (str, False),
    "script": (str, False),
    "protocol": (dict, False),
    "derived_from": (str, True),
    "repeat_of": (str, True),
    "draw": (int, True),
    "run_kind": (str, False),
    "unfrozen_ack": (bool, False),
    "audit_failed": (str, True),
    "cost_tier": (str, True),
    "promises": (dict, True),
    "script_sha": (str, False),
    "untracked_sources": (list, False),
    "pid": (int, False),
    "git": (str, False),
    "git_full": (str, False),
    "python": (str, False),
    "env": (str, False),
    "models_resolved": (dict, False),
    "started": (str, False),
    "command": (list, False),
    "data": (dict, False),
    "config": (dict, False),
}
RUN_CONFIG_KEYS = tuple(_FIELDS)
#: a field's type as the record's JSON names it, for the refusal
_JSON_NAME = {
    dict: "object",
    list: "list",
    str: "string",
    int: "integer",
    bool: "boolean",
}
#: the nested fields: held as stored JSON text — in the record's own key
#: order, which a printed config shows — and handed out as fresh copies,
#: so no reader can change what another reads (`frozen=True` alone freezes
#: the fields, not the dicts in them). The `protocol` table is kept there
#: too, as written, for `as_record`; readers take `protocol` (the binding).
_NESTED = (
    "promises",
    "untracked_sources",
    "models_resolved",
    "command",
    "data",
    "config",
)


@dataclass(frozen=True)
class RunConfig:
    """A run's metadata as labkit wrote it, every field present, read once
    and checked once (`parse_run_config`). Scalars are typed fields, None
    only where the writer writes null; the nested tables come from the
    attributes below as fresh copies of the stored JSON, never a shared
    dict. The experiment's own settings are `config`, free JSON."""

    schema_version: int
    run_kind: RunKind
    protocol: ProtocolBinding
    # the run whose rows this one re-reads, making no model call
    derived_from: str | None
    # the run a repeat draws again: the model asked once more with the same
    # instrument on the same items, its own model record, so the spread of
    # the number is visible — supporting evidence that never answers the
    # protocol (`answering_run.bound_runs`)
    repeat_of: str | None
    draw: int | None  # a repeat's draw number, >= 2 (the run itself is 1)
    unfrozen_ack: bool
    experiment: str
    script: str
    audit_failed: str | None
    cost_tier: str | None
    script_sha: str
    pid: int
    git: str
    git_full: str
    python: str
    env: str
    started: str
    _nested: str = field(repr=False)

    def _get(self, key: str) -> Any:
        return json.loads(self._nested)[key]

    @property
    def config(self) -> JsonObject:
        """The experiment's settings, free JSON."""
        return cast(JsonObject, self._get("config"))

    @property
    def data(self) -> JsonObject:
        """The described inputs (`data=`), {} when none were given."""
        return cast(JsonObject, self._get("data"))

    @property
    def models_resolved(self) -> JsonObject:
        """The model aliases the run resolved (`llm` records), {} when none."""
        return cast(JsonObject, self._get("models_resolved"))

    @property
    def promises(self) -> JsonObject | None:
        """The promise snapshot (`promises.snapshot`), None for a protocol
        without a block."""
        return cast("JsonObject | None", self._get("promises"))

    @property
    def command(self) -> list[str]:
        """The command line that started the run."""
        return cast(list[str], self._get("command"))

    @property
    def untracked_sources(self) -> list[str]:
        """The untracked sources the run snapshot beside its script."""
        return cast(list[str], self._get("untracked_sources"))

    def as_record(self) -> JsonObject:
        """The record as config.json stores it, a fresh copy: for a reader
        that prints or searches it whole (the index row, an arm line's
        fingerprint), never for reading one field."""
        nested = json.loads(self._nested)
        return {
            key: nested[key] if key in nested else getattr(self, key)
            for key in RUN_CONFIG_KEYS
        }

    def repeat_basis(self) -> JsonObject:
        """What makes two runs comparable as draws of one measurement
        (`answering_run.repeat_mismatch`): binding, promise snapshot, the
        script's digest, the resolved model, the config and the inputs — as
        config.json stores them. A run about to start builds the same keys."""
        return {
            "protocol": {"id": self.protocol.id, "path": self.protocol.path},
            "promises": self.promises,
            "config": self._get("config"),
            "data": self._get("data"),
            "script_sha": self.script_sha,
            "models_resolved": self._get("models_resolved"),
        }


def _field_problem(cfg: JsonObject) -> str | None:
    """Why CFG's fields are not the record's, or None: a field missing, a
    null where the writer never writes one, a value of another type (a bool
    is no int), `command` or `untracked_sources` not a list of strings."""
    missing = [key for key in RUN_CONFIG_KEYS if key not in cfg]
    if missing:
        return (
            f"{', '.join(missing)} missing — a labkit record carries every field "
            f"its writer writes; missing is no null and no default"
        )
    for key, (kind, nullable) in _FIELDS.items():
        value = cfg[key]
        name = _JSON_NAME[kind]
        expected = f"{'an' if name[0] in 'aeiou' else 'a'} {name}"
        if value is None:
            if not nullable:
                return f"{key} = null, not {expected}"
            continue
        if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
            return f"{key} = {value!r}, not {expected}"
    for key in ("command", "untracked_sources"):
        if not all(isinstance(v, str) for v in cast(list[object], cfg[key])):
            return f"{key} = {cfg[key]!r}, not a list of strings"
    return None


def parse_run_config(obj: object) -> RunConfig:
    """The RunConfig of OBJ, a parsed config.json — or RunConfigError naming
    the field: not an object, the schema, a key labkit does not write, a
    field missing, null where it may not be or of another type, the run
    kind, the binding, `derived_from` or the repeat fields of a wrong shape."""
    if not isinstance(obj, dict):
        raise RunConfigError(f"a JSON {type(obj).__name__}, not an object")
    cfg = cast(JsonObject, obj)
    # the schema first: a record of another labkit names the version that
    # reads it, rather than its unfamiliar or missing keys
    problem = _schema_problem(cfg.get("schema_version"))
    if problem:
        raise RunConfigError(problem)
    unknown = sorted(set(cfg) - set(RUN_CONFIG_KEYS))
    if unknown:
        raise RunConfigError(
            f"{', '.join(unknown)}: not a field labkit writes into config.json — "
            f"an experiment's own settings belong in `config`"
        )
    problem = _field_problem(cfg)
    if problem:
        raise RunConfigError(problem)
    try:
        kind = parse_run_kind(cfg["run_kind"])
    except ValueError as exc:
        raise RunConfigError(str(exc)) from exc
    binding = binding_of(cfg)
    problem = _derived_shape_problem(cfg) or _repeat_shape_problem(cfg)
    if problem:
        raise RunConfigError(problem)
    return RunConfig(
        schema_version=cfg["schema_version"],
        run_kind=kind,
        protocol=binding,
        derived_from=cfg["derived_from"],
        repeat_of=cfg["repeat_of"],
        draw=cfg["draw"],
        unfrozen_ack=cfg["unfrozen_ack"],
        experiment=cfg["experiment"],
        script=cfg["script"],
        audit_failed=cfg["audit_failed"],
        cost_tier=cfg["cost_tier"],
        script_sha=cfg["script_sha"],
        pid=cfg["pid"],
        git=cfg["git"],
        git_full=cfg["git_full"],
        python=cfg["python"],
        env=cfg["env"],
        started=cfg["started"],
        _nested=json.dumps(
            {key: cfg[key] for key in (*_NESTED, "protocol")}, ensure_ascii=False
        ),
    )


@dataclass(frozen=True)
class RunDir:
    """One directory under `runs/` and what its config.json says: `config`
    None and `error` None is no run (no config.json); `error` set is a run
    whose metadata cannot be read (the RunConfigError's sentence)."""

    dir: Path
    config: RunConfig | None
    error: str | None

    def __post_init__(self) -> None:
        if self.config is not None and self.error is not None:
            raise ValueError(
                f"{self.dir}: a RunDir is a read run or an unreadable one, not both"
            )


def read_run_dir(d: Path) -> RunDir:
    """The `RunDir` of directory D, its config.json read once; an unreadable
    one is carried in `error`, never raised."""
    try:
        return RunDir(d, read_run_config(d), None)
    except RunConfigError as exc:
        return RunDir(d, None, str(exc))


def run_dirs(area: Path) -> list[RunDir]:
    """Every directory under the area's `runs/`, oldest first by name (run_ids
    start with the timestamp; two runs of one second differ only in their
    random suffix, and their order among themselves is not their start
    order — no record holds a finer time; the answering-run choice refuses
    such a pair, `answering_run.same_second_rival`), each with its
    metadata read once. The one walk: listing, index, choice and completion
    used to walk `runs/` six times and each decided for itself what an
    unreadable run means (audit 2026-10-13). Here it is data — the caller
    says whether it refuses, reports or skips."""
    runs = runs_path(area)
    if not runs.is_dir():
        return []
    return [read_run_dir(d) for d in sorted(runs.glob("*")) if d.is_dir()]


def completed_runs(area: Path, *, with_repeats: bool) -> list[Path]:
    """The area's completed run directories, oldest first; WITH_REPEATS says
    whether a repeat draw (`repeat_of`) counts — every caller decides it in
    sight, since a "newest run" that is a repeat would displace the run that
    answers. An unreadable run raises RunConfigError: it may be the newest
    and must not vanish."""
    out: list[Path] = []
    for rd in run_dirs(area):
        if rd.error is not None:
            raise RunConfigError(rd.error)
        if (
            rd.config is not None
            and run_state(rd.dir, alive=False) == COMPLETED
            and (with_repeats or rd.config.repeat_of is None)
        ):
            out.append(rd.dir)
    return out


# ---- which run answers for a protocol — one choice for intent-check,
# finalize and labkit-params (2026-10-08: it stood in intent_check and
# finalize alike; a third copy for the parameter view was the line)


#: States that mean "this run is not a clean finish" — `--wait` exits 2 on
#: any of them, `reindex` rebuilds none of them. `unknown` is NOT in this
#: list: it means "can't tell", and treating it as failed would hide a run
#: that is still going.
FAILED_STATES = ("crashed", "unfinalized", "corrupt", "unreadable")
