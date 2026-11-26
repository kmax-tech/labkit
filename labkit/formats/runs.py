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

from labkit.formats.digests import DIGEST_CHARS, digest, file_digest
from labkit.formats.files import (
    ACCESS,
    MALFORMED,
    MISSING,
    READ_CAUSES,
    ReadError,
    read_cause,
    write_atomic,
)
from labkit.formats import jsonl
from labkit.formats.repo import (
    commit_known,
    experiment_areas,
    lab_root,
    layout_root,
    rel_posix,
)


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

    The PID alone is not enough: the OS recycles PIDs, and a dead run's PID
    can belong to another process days later. So the command line is
    checked for the recorded script name as well. If that cannot be
    decided (no `ps`, no script name), the answer is **None**, not `True`:
    an "unknown" is usable, a false "running" is not. A PID that is no
    integer, or one the system cannot hold as a process id, is undecidable
    too: the record does not say which process it meant.
    """
    if not isinstance(pid, int):
        return None
    try:
        os.kill(pid, 0)  # signal 0: existence check only
    except ProcessLookupError:
        return False
    except OverflowError:
        return None  # larger than any process id: not a PID the record can mean
    except PermissionError:
        pass  # exists, belongs to someone else
    cmd = _command_of(pid)
    if cmd is None or not isinstance(script, str) or not script:
        return None  # a script name that is not text cannot be matched — undecidable
    return runs_script(cmd, script)


def runs_script(cmd: str, script: str) -> bool:
    """Does the command line CMD run SCRIPT — as a word of its own or the last
    component of a path (`python /a/01_measure.py --x`)? Not as part of
    another name: a substring match would hold a dead run "running" under
    `not_01_measure.py`. A directory with a space in its path still
    matches; the name is bounded, not the path split."""
    return re.search(rf"(?:^|[\s/]){re.escape(script)}(?:\s|$)", cmd) is not None


#: a JSON object as a run's record files hold it (config.json, completion.json):
#: labkit's own keys are checked when the file is read (`read_run_config`),
#: the experiment's config and metrics keys stay free — Any, not a schema
JsonObject = dict[str, Any]

#: Current run-record format; the writer and reader use the same version.
RUN_SCHEMA = 5
#: the last release that writes and reads schema 4, the format before input
#: origins (checked against the tags, tests/test_release_tags.py)
SCHEMA_4_READ_BY = "0.113.0"

RunKind = Literal["preparation", "probe", "measurement"]
#: the run kind that measures the registered question — the one spelling
#: every reader compares a readable record's `run_kind` with
MEASUREMENT: RunKind = "measurement"
#: the two kinds that answer no registered question: a run that builds the
#: data, and a small run that tries the instrument
PREPARATION: RunKind = "preparation"
PROBE: RunKind = "probe"
#: what a derived run is, as the README defines the term: it re-reads a
#: completed run's rows and makes no new model calls — the sentence the
#: call-log check and runlog's call refusal name
DERIVED_RUN_CONTRACT = (
    "a derived run re-reads its parent's rows and makes no model calls"
)
#: the measurement script every skeleton stamps (`standard_contract`): the
#: one script that opens the full run and carries the `DELIVERABLES`
#: constant the stamp fills; `params` reads its constants
MEASURE_SCRIPT = Path("scripts") / "01_measure.py"


def parse_run_kind(value: object) -> RunKind:
    """Validate the declared purpose of a run, naming the field on failure."""
    if value == PREPARATION:
        return PREPARATION
    if value == PROBE:
        return PROBE
    if value == MEASUREMENT:
        return MEASUREMENT
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
    """One of: completed · running · unknown · crashed · unfinalized · corrupt.
    A run whose config.json cannot be read — damaged, or of another schema
    than RUN_SCHEMA — is `unreadable` (`run_facts`, `runlog.active`); this
    function never sees one, its caller has read the config.

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
    has_completion = (run_dir / COMPLETION_FILE).is_file()
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
#: area stamp and a promise's scope hash keep `digests.DIGEST_CHARS`;
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


#: the minute an audit file's name starts with (`2026-10-27T14-05`) and
#: the minute its `date` field states (`2026-10-27T14:05`): one spelling
#: each for the records labkit-audit, the reviews and the attempt journal
#: write
NAME_MINUTE = "%Y-%m-%dT%H-%M"
DATE_MINUTE = "%Y-%m-%dT%H:%M"


def name_minute(when: time.struct_time | None = None) -> str:
    """WHEN (local time now when None) as an audit file's name begins."""
    return time.strftime(NAME_MINUTE, when or time.localtime())


def date_minute(when: time.struct_time | None = None) -> str:
    """WHEN (local time now when None) as an audit file's `date` states it."""
    return time.strftime(DATE_MINUTE, when or time.localtime())


#: why a run broke off, written by `runlog.run` when the block raises — the
#: exception's type and message; without it a crashed run shows only that
#: it crashed, the reason on stderr alone
FAILURE_FILE = "failure.json"
#: the folder under an area that holds its runs, and the file of the values
#: reported through `run.metrics(...)` — the one spelling of each
RUNS_DIR = "runs"
METRICS_FILE = "metrics.json"
#: the run record's other files, one spelling each
CONFIG_FILE = "config.json"
COMPLETION_FILE = "completion.json"
OUTPUTS_FILE = "outputs.json"
#: the code a run imported, per git repository, and the folder of its
#: patches and copies (`code_repos.write_code`)
CODE_FILE = "code.json"
CODE_DIR = "code"
#: the cache a run read its model answers from — version, mode, directory —
#: and one line per model call through it (`llm_cache.Cache`)
LLM_CACHE_FILE = "llm-cache.json"
LLM_CALLS_FILE = "llm-calls.jsonl"


@dataclass(frozen=True)
class ModelCall:
    """One line of a run's `llm-calls.jsonl` as `read_model_calls` returns
    it: the ALIAS the run called, HIT whether the answer came from the
    cache, ORIGIN_RUN the run that stored a hit's answer, STAND_IN whether
    a hit's answer is a stand-in (`llm_cache.store_stand_in`), and the
    USAGE by field (for a hit the original call's; `llm_backends.Usage`
    names the fields).

    ORIGIN_RUN None means three things: without HIT, a call that asked the
    model; with HIT and STAND_IN, a stand-in, a fixed answer that is no
    model's; with HIT alone, an answer stored outside any run and not
    marked as a stand-in (a hand-written entry, or a stand-in stored before
    0.115.0)."""

    alias: str
    hit: bool
    origin_run: str | None
    stand_in: bool
    usage: dict[str, int | float | None]


def read_model_calls(run_dir: Path) -> list[ModelCall]:
    """The model calls RUN_DIR's `llm-calls.jsonl` records, in order — the
    lines `llm_cache.Cache` writes; [] when the run has no such file (it
    opened no cache, or called nothing through it).

    The lines are read by `jsonl.objects`: split at "\\n" only (a U+2028
    inside a string stays in its line), numbered as an editor numbers them,
    a blank line skipped as for every reader of `jsonl.objects` (the cache
    writes none).

    Raises:
        ValueError: A line that is not one the cache writes — not JSON, or
            `alias`, `hit`, `origin` or `usage` missing or of another
            type — naming the file, the line and the field; a file that is
            not UTF-8 (UnicodeDecodeError).
        OSError: The file stands and does not read.
    """
    path = run_dir / LLM_CALLS_FILE
    if not path.exists():
        return []
    return [
        _parse_model_call(parsed, f"{path}:{n}")
        for n, parsed in jsonl.objects(path.read_text(encoding="utf-8"), str(path))
    ]


def _parse_model_call(parsed: object, where: str) -> ModelCall:
    """One call-log line, already parsed, read at WHERE
    (`read_model_calls`); raises ValueError naming WHERE and the field that
    is not what the cache writes."""
    if not isinstance(parsed, dict):
        raise ValueError(f"{where}: not a JSON object")
    line = cast(JsonObject, parsed)
    alias, hit, origin, usage = (
        line.get(k) for k in ("alias", "hit", "origin", "usage")
    )
    if not isinstance(alias, str):
        raise ValueError(f"{where}: `alias` is not a string")
    if not isinstance(hit, bool):
        raise ValueError(f"{where}: `hit` is not true or false")
    return ModelCall(
        alias,
        hit,
        _origin_run(hit, origin, where),
        _stand_in(hit, origin, where),
        _usage_counts(usage, where),
    )


def _origin_run(hit: bool, origin: object, where: str) -> str | None:
    """The run that stored a hit's answer, None when it was stored outside
    any run or the call asked the model. A hit carries its origin (the run
    may be null), a call that asked the model none — the shape the cache
    writes; anything else raises ValueError naming WHERE."""
    if not hit:
        if origin is not None:
            raise ValueError(
                f"{where}: `origin` of a call that asked the model is not null"
            )
        return None
    if not (isinstance(origin, dict) and "run" in origin):
        raise ValueError(f"{where}: `origin` of a hit is not an object with `run`")
    stored_by: object = cast(JsonObject, origin)["run"]
    if stored_by is not None and not isinstance(stored_by, str):
        raise ValueError(f"{where}: `origin.run` is not a run id or null")
    return stored_by


def _stand_in(hit: bool, origin: object, where: str) -> bool:
    """Whether a hit's answer is a stand-in: its origin's `stand_in`, which
    a line written before 0.115.0 lacks (not marked as a stand-in — no
    evidence that a model gave the answer). A stand-in has no
    run (`origin.run` null); one naming a run, or a `stand_in` that is not
    true or false, raises ValueError naming WHERE. False for a call that
    asked the model. Call after `_origin_run`, which checks the shape."""
    if not hit:
        return False
    fields = cast(JsonObject, origin)
    stand_in: object = fields.get("stand_in", False)
    if not isinstance(stand_in, bool):
        raise ValueError(f"{where}: `origin.stand_in` is not true or false")
    if stand_in and fields["run"] is not None:
        raise ValueError(f"{where}: `origin` of a stand-in names a run")
    return stand_in


def _usage_counts(usage: object, where: str) -> dict[str, int | float | None]:
    """A call-log line's `usage`: an object of counts or nulls, else
    ValueError naming WHERE."""
    if not isinstance(usage, dict):
        raise ValueError(f"{where}: `usage` is not an object of counts or nulls")
    counts = cast(dict[str, object], usage)
    for value in counts.values():
        if isinstance(value, bool) or not isinstance(value, (int, float, type(None))):
            raise ValueError(f"{where}: `usage` is not an object of counts or nulls")
    return cast(dict[str, int | float | None], counts)


def runs_path(area: Path) -> Path:
    """AREA's `runs/` — every run directory lies directly in it."""
    return area / RUNS_DIR


def run_dir_in_lab(area: Path, run_id: str) -> Path | None:
    """The directory of run RUN_ID: AREA's `runs/<RUN_ID>` when it is
    there, else the first experiment area of AREA's lab (`repo.lab_root`,
    the directory holding `models.toml`) that holds one; None when no
    area does, or AREA has no lab root and not the run. The lab's cache of
    model answers (`llm_cache`) is shared by its areas, so the run that
    stored an answer may sit in another area. Looks only at directories;
    whether the record reads is the caller's."""
    own = run_path(area, run_id)
    if own.is_dir():
        return own
    root = lab_root(area)
    if root is None:
        return None
    for other in experiment_areas(root):
        found = run_path(other, run_id)
        if found.is_dir():
            return found
    return None


def run_path(area: Path, run_id: str) -> Path:
    """`runs/<RUN_ID>/` of AREA: the run's directory (`run_dir` in every
    signature that takes one)."""
    return area / RUNS_DIR / run_id


def metrics_path(run_dir: Path) -> Path:
    """RUN_DIR's `metrics.json`."""
    return run_dir / METRICS_FILE


#: what a run records as `script_sha` when it ran no script file
NO_SCRIPT = "no-script"


def script_digest(script: Path | bytes) -> str:
    """The digest a run records as `script_sha`: of SCRIPT, a script file
    or the bytes of one. The one home of its width and method, for the
    writer (`provenance.snapshot_script`, `provenance.script_sha`) and
    every check that compares a script with a record. A run without a
    script file records `NO_SCRIPT` instead. Raises OSError when a file
    does not read."""
    if isinstance(script, bytes):
        return digest(script, DIGEST_CHARS)
    return file_digest(script)[:DIGEST_CHARS]


def script_copy_path(run_dir: Path, suffix: str) -> Path:
    """RUN_DIR's copy of the script as it ran (`script-source<SUFFIX>`;
    `.txt` for a script without one)."""
    return run_dir / f"script-source{suffix or '.txt'}"


def patch_path(run_dir: Path) -> Path:
    """RUN_DIR's `uncommitted.patch`: the tracked files' `git diff HEAD` at
    the start. runlog writes it whenever the tree differs from the commit
    then, untracked files counted — the run's own new directory is one, so
    nearly every run keeps the file, empty where no tracked file differed."""
    return run_dir / "uncommitted.patch"


def untracked_copy_path(run_dir: Path, rel: str) -> Path:
    """RUN_DIR's copy of REL, an untracked file beside an untracked script
    (`source-untracked/<REL>`, REL relative to the script's directory)."""
    return run_dir / "source-untracked" / rel


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


@dataclass(frozen=True)
class NumberWritten:
    """Whether a run wrote its number (metrics.json), as far as the file
    state shows it (`number_written`). The four states:

    - `answer` "yes": the run directory holds a metrics.json.
    - `answer` "cannot tell": only a commit holds the run
      (`RunDir.from_commit`), so its files are not here to read.
    - `answer` "no", `failure` None: no metrics.json and no failure.json —
      the run stopped without a failure record, or it still runs.
    - `answer` "no", `failure` set: no metrics.json, and failure.json says
      why (`<Type>: <message>`, `read_failure`).

    Raises ValueError for a failure beside another answer than "no"."""

    answer: Literal["yes", "no", "cannot tell"]
    failure: str | None = None

    def __post_init__(self) -> None:
        if self.failure is not None and self.answer != "no":
            raise ValueError(
                f"NumberWritten: failure = {self.failure!r} beside answer = "
                f"{self.answer!r}; a failure says why no number was written"
            )


def number_written(rd: RunDir) -> NumberWritten:
    """Did run RD write its number (metrics.json), as the file state holds
    it — and when not, the failure it recorded (`read_failure`)? "cannot
    tell" when only a commit holds RD (`RunDir.from_commit`): its files are
    not here to read. Reads RD's directory. RunConfigError when failure.json
    cannot be read."""
    if rd.from_commit is not None:
        return NumberWritten("cannot tell")
    if metrics_path(rd.dir).is_file():
        return NumberWritten("yes")
    return NumberWritten("no", read_failure(rd.dir))


def read_failure(run_dir: Path) -> str | None:
    """`<Type>: <message>` from RUN_DIR/failure.json, None when the run left
    none; RunConfigError when it is there and cannot be opened or read."""
    path = run_dir / FAILURE_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return f"{data['error']}: {data['message']}"
    except (
        OSError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        raise RunConfigError(f"{path}: unreadable ({exc})") from exc


#: the repeat costs a protocol head declares (`[protocol] repeat_cost`) and
#: a run records as it ran under — here, below protocol_block, which reads
#: the head and imports the run id from this module
REPEAT_COSTS = ("low", "high")

RUN_ID = re.compile(
    r"\b(?P<date>\d{4}-\d{2}-\d{2})T(?P<h>\d{2})-(?P<m>\d{2})-(?P<s>\d{2})_[0-9a-f]{2,12}\b"
)
#: what reads as a run id in prose: RUN_ID's time with any suffix. A cited
#: token of this shape that is not a RUN_ID names no run runlog wrote —
#: a gate that sees only RUN_ID sees no citation in `…T12-48-00_final` and
#: lets it through
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


#: a run record of a schema version this labkit does not read — older,
#: newer or none; `_schema_problem` names the version, not its age
OTHER_SCHEMA = "other_schema"
#: why a run record does not read: the file causes (`files.READ_CAUSES`:
#: missing, access, malformed) and OTHER_SCHEMA
RECORD_CAUSES = (*READ_CAUSES, OTHER_SCHEMA)
#: each record cause as a sentence tells it — an access failure is not
#: damage, and a schema version is named neither older nor newer
RECORD_CAUSE_TOLD = {
    MISSING: "a record file not found",
    ACCESS: "could not be opened (permissions or I/O)",
    MALFORMED: "its record or outputs file is not what labkit writes "
    "(damaged or hand-edited)",
    OTHER_SCHEMA: "of a schema version this labkit does not read",
}


class RunConfigError(ValueError):
    """A run directory whose config.json exists but cannot be read. CAUSE,
    one of RECORD_CAUSES, says which kind: the file could not be opened
    (missing, access), its content is not the record labkit writes
    (malformed, the default), or it is a record of another schema version
    (OTHER_SCHEMA)."""

    def __init__(self, message: str, *, cause: str = MALFORMED) -> None:
        if cause not in RECORD_CAUSES:
            raise ValueError(f"a record cause is one of {RECORD_CAUSES}, not {cause!r}")
        super().__init__(message)
        self.cause = cause


def read_run_config(run_dir: Path) -> RunConfig | None:
    """A run's metadata, read and checked once (`parse_run_config`), None
    when the directory has no config.json.

    Unreadable is not absent: a damaged config.json raises RunConfigError
    naming the file. Skipping it silently would make a broken newer run
    vanish and let an older one be chosen or reported in its place — listings
    show it as `corrupt`, choices refuse.
    """
    cfg_file = run_dir / CONFIG_FILE
    if not cfg_file.is_file():
        return None
    try:
        text = cfg_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RunConfigError(
            f"{cfg_file}: unreadable run metadata ({exc}) — the run cannot "
            f"say what it is; repair or move it aside",
            cause=read_cause(exc),
        ) from exc
    return parse_run_record(text, cfg_file)


def parse_run_record(text: str, where: Path) -> RunConfig:
    """The RunConfig of TEXT, a config.json's content read from WHERE — the
    file, or the same path as git holds it in the index or at a commit
    (`run_dir_from_text`): its JSON through `parse_run_config`. The one
    wording of an unreadable record. Raises RunConfigError naming WHERE."""
    try:
        cfg = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise RunConfigError(
            f"{where}: unreadable run metadata ({exc}) — the run cannot "
            f"say what it is; repair or move it aside"
        ) from exc
    try:
        return parse_run_config(cfg)
    except RunConfigError as exc:
        raise RunConfigError(
            f"{where}: unreadable run metadata ({exc}) — repair or move it aside",
            cause=exc.cause,
        ) from exc


class ArtefactError(ReadError):
    """A run's artefact (metrics.json, outputs.json, completion.json) that is
    unreadable or not the shape its writer gives it. CAUSE (`files.READ_CAUSES`)
    says which: MISSING, ACCESS, or MALFORMED — the default, every shape error
    is one."""


class MetricsError(ArtefactError):
    """A run's metrics.json that cannot be read as a JSON object."""


def _json_of(path: Path, what: str) -> object:
    """The JSON in a run artefact. Raises ArtefactError naming the file and
    what it holds ("metrics", "outputs", "completion")."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtefactError(
            f"{path}: unreadable {what} ({exc}) — repair the run or move it aside",
            cause=read_cause(exc),
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
    )  # run_id -> rows (JSONL)
    continues: tuple[str, ...] = ()  # runs whose rows this file already held


#: the one `data=` key of a run's record that holds no input but the
#: leakage verdict across splits, a sentence (`provenance.describe_data`)
LEAKAGE_CHECK_KEY = "leakage_check"
#: the other: the author's declaration that the run reads no input file
#: (`runlog.run(data=runlog.NO_INPUTS)`), so a record without inputs is told
#: apart from one whose `data=` was left out — the author's word, not a
#: check that the script reads no file
NO_INPUTS_KEY = "no_input_files"
NO_INPUTS_DECLARED = "declared by the author: the run reads no input file"
#: the `data=` keys that hold no input
RESERVED_DATA_KEYS = (LEAKAGE_CHECK_KEY, NO_INPUTS_KEY)
#: an input entry's origin, decided at start (`input_origins`): the run
#: that wrote the file, or null for a plain input without origin
ORIGIN_RUN_KEY = "origin_run"
#: true when the script chose that run (`RunOutput`) — chosen by the
#: script, not confirmed by an auditor
ORIGIN_CHOSEN_KEY = "origin_chosen"
#: the area's runs whose record did not read when the origin was decided
#: without a choice, each `{"run": id, "cause": one of RECORD_CAUSES}`
#: (`UnreadableRun`): skipped records, not known to have written the file,
#: only not ruled out
ORIGIN_UNREADABLE_KEY = "origin_unreadable_runs"


@dataclass(frozen=True)
class UnreadableRun:
    """A run of the area the origin lookup could not look into: RUN its id,
    CAUSE why its record did not read, one of RECORD_CAUSES — the file was
    gone or could not be opened (missing, access), its content is not the
    record labkit writes (malformed), or it is of a schema version this
    labkit does not read (OTHER_SCHEMA). Not a source of the file: a record
    that was skipped."""

    run: str
    cause: str


@dataclass(frozen=True)
class DataEntry:
    """One input a run read (`data=` in its record), as `runlog` writes it:
    KEY as given, the path as the record holds it (`resolve_recorded` reads
    it back), its sha256 cut to RECORD_SHA_CHARS, the rows of a text
    input — None for a binary one (`provenance.BinaryInput`) — and its
    origin as decided at start (ORIGIN_RUN_KEY, ORIGIN_CHOSEN_KEY,
    ORIGIN_UNREADABLE_KEY). Not the outputs (`OutputEntry`)."""

    key: str
    recorded: str
    sha256: str
    rows: int | None
    origin_run: str | None
    origin_chosen: bool
    origin_unreadable_runs: tuple[UnreadableRun, ...]


def data_entries(data: JsonObject, where: str) -> list[DataEntry]:
    """The inputs of a run record's `data=` table DATA, in its order, each
    held to the shape `runlog` writes — a path as nonempty text, sha256 as
    text, rows a count or null (present), and the origin (`_entry_origin`);
    the leakage verdict (LEAKAGE_CHECK_KEY) is no input. Raises
    ArtefactError naming WHERE (the record) and the key on any other
    shape: whether an entry reads is decided here once, which of
    its fields a check needs stays with that check, so no reader turns a
    missing path into the text "None"."""
    out: list[DataEntry] = []
    for key, value in data.items():
        if key in RESERVED_DATA_KEYS:
            continue
        if not isinstance(value, dict):
            raise ArtefactError(f"{where}: data[{key!r}] is no entry ({value!r})")
        e = cast(dict[str, object], value)
        if "rows" not in e:
            raise ArtefactError(
                f"{where}: data[{key!r}] has no rows field (a count, or null "
                f"for a binary input)"
            )
        path, sha, rows = e.get("path"), e.get("sha256"), e["rows"]
        if not isinstance(path, str) or not path:
            raise ArtefactError(
                f"{where}: data[{key!r}] in the run's record names no path — "
                f"nothing says which bytes the run read"
            )
        if not isinstance(sha, str):
            raise ArtefactError(
                f"{where}: data[{key!r}] in the run's record: the run recorded "
                f"no sha256 for it — nothing holds the bytes the number came from"
            )
        if rows is not None and not _is_count(rows):
            raise ArtefactError(f"{where}: data[{key!r}]: rows is {rows!r}")
        run, chosen, unreadable = _entry_origin(e, f"{where}: data[{key!r}]")
        out.append(
            DataEntry(key, path, sha, cast("int | None", rows), run, chosen, unreadable)
        )
    return out


def _entry_origin(
    e: dict[str, object], where: str
) -> tuple[str | None, bool, tuple[UnreadableRun, ...]]:
    """The origin fields of input entry E, each present and of the shape
    `runlog` writes: ORIGIN_RUN_KEY a run id or null, ORIGIN_CHOSEN_KEY a
    boolean, true only with a run, ORIGIN_UNREADABLE_KEY a list of
    `{"run", "cause"}` objects (`UnreadableRun`), empty for a chosen origin
    (a choice looks into no other run). Raises
    ArtefactError naming WHERE: a record that lost its origin must not
    read as a plain input."""
    missing = [
        k
        for k in (ORIGIN_RUN_KEY, ORIGIN_CHOSEN_KEY, ORIGIN_UNREADABLE_KEY)
        if k not in e
    ]
    if missing:
        raise ArtefactError(
            f"{where} has no {', '.join(missing)} — the record does not say "
            f"where the file came from"
        )
    run, chosen, unreadable = (
        e[ORIGIN_RUN_KEY],
        e[ORIGIN_CHOSEN_KEY],
        e[ORIGIN_UNREADABLE_KEY],
    )
    if run is not None and (not isinstance(run, str) or not run):
        raise ArtefactError(f"{where}: {ORIGIN_RUN_KEY} is {run!r}, not a run id")
    if not isinstance(chosen, bool):
        raise ArtefactError(
            f"{where}: {ORIGIN_CHOSEN_KEY} is {chosen!r}, not a boolean"
        )
    if chosen and run is None:
        raise ArtefactError(
            f"{where}: {ORIGIN_CHOSEN_KEY} is true without an origin run"
        )
    if not isinstance(unreadable, list):
        raise ArtefactError(
            f"{where}: {ORIGIN_UNREADABLE_KEY} is {unreadable!r}, not a list"
        )
    skipped = tuple(
        _unreadable_run(u, f"{where}: {ORIGIN_UNREADABLE_KEY}")
        for u in cast(list[object], unreadable)
    )
    if chosen and skipped:
        raise ArtefactError(
            f"{where}: a chosen origin names {ORIGIN_UNREADABLE_KEY} — a choice "
            f"looks into no other run"
        )
    return run, chosen, skipped


def _unreadable_run(u: object, where: str) -> UnreadableRun:
    """U as `{"run": id, "cause": one of RECORD_CAUSES}`, nothing else.
    Raises ArtefactError naming WHERE."""
    if not isinstance(u, dict) or set(cast(dict[str, object], u)) != {"run", "cause"}:
        raise ArtefactError(f'{where}: {u!r} is not {{"run", "cause"}}')
    run, cause = cast(dict[str, object], u)["run"], cast(dict[str, object], u)["cause"]
    if not isinstance(run, str) or not run:
        raise ArtefactError(f"{where}: run is {run!r}, not a run id")
    if cause not in RECORD_CAUSES:
        raise ArtefactError(
            f"{where}: cause is {cause!r}, not one of {', '.join(RECORD_CAUSES)}"
        )
    return UnreadableRun(run, cast(str, cause))


def declares_no_inputs(data: JsonObject, where: str) -> bool:
    """Does a run record's `data=` table DATA carry the author's declaration
    that the run reads no input file (NO_INPUTS_KEY)? Raises ArtefactError
    naming WHERE when the key holds anything but NO_INPUTS_DECLARED, or
    stands beside an input."""
    if NO_INPUTS_KEY not in data:
        return False
    if data[NO_INPUTS_KEY] != NO_INPUTS_DECLARED:
        raise ArtefactError(
            f"{where}: data[{NO_INPUTS_KEY!r}] = {data[NO_INPUTS_KEY]!r}, not "
            f"{NO_INPUTS_DECLARED!r}"
        )
    if set(data) - set(RESERVED_DATA_KEYS):
        raise ArtefactError(
            f"{where}: data declares no input file and names inputs beside it"
        )
    return True


def read_data(run_dir: Path) -> list[DataEntry] | None:
    """The inputs RUN_DIR's record names (`data_entries`), [] when it gave
    none; None when the run has no readable record (`read_run_config`).
    Raises ArtefactError as `data_entries` does."""
    cfg = read_run_config(run_dir)
    if cfg is None:
        return None
    return data_entries(cfg.data, str(run_dir / CONFIG_FILE))


def recorded_path(path: Path, inside: Path) -> str:
    """How a run's record (outputs.json, config.json `data`) writes PATH:
    relative to the root of the repo INSIDE lies in, when PATH lies in that
    repo, so a clone elsewhere reads the same record; absolute only for a file
    outside the repo. `resolve_recorded` reads it back. An absolute path
    would break `02_analyze.py --check` and finalize's source check on every
    machine but the one that measured, a path relative to the working
    directory in every other directory."""
    root = layout_root(inside).resolve()
    resolved = path.resolve()
    if resolved.is_relative_to(root):
        return rel_posix(resolved, root)
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
    path = run_dir / OUTPUTS_FILE
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
    path = run_dir / COMPLETION_FILE
    data = _json_of(path, "completion")
    if not isinstance(data, dict):
        raise ArtefactError(f"{path}: must be a JSON object, not {type(data).__name__}")
    return cast(dict[str, object], data)


def as_stored(value: object) -> str:
    """VALUE as a run's JSON files store it, keys sorted: the one equality
    of stored values — two are the same only when their texts are, so `1`
    is not `true`, `1` is not `1.0`, a tuple is its list and NaN is NaN.
    Python's `==` takes `True == 1` and `1 == 1.0`, and a checker built on
    it would pass a recomputation of another type. Raises TypeError for a value
    JSON cannot hold."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def patch_text(run_dir: Path) -> str:
    """The run's `uncommitted.patch` as text, "" when it kept none — the
    tree's diff against the commit at the run's start (`patch_path`)."""
    path = patch_path(run_dir)
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def kept_script(run_dir: Path, suffix: str, sha: str) -> Path | None:
    """The script's copy the run kept (`script_copy_path`) when it stands
    and its digest begins with SHA, the digest the run recorded; None
    otherwise (no copy, or one whose bytes are not the run's)."""
    kept = script_copy_path(run_dir, suffix)
    if kept.is_file() and script_digest(kept) == sha:
        return kept
    return None


def untracked_copy_differs(run_dir: Path, rel: str, now: Path) -> bool:
    """Do the bytes of NOW, an untracked source the run copied as REL
    (`untracked_copy_path`), differ from the copy — or is the copy gone?"""
    copy = untracked_copy_path(run_dir, rel)
    return not copy.is_file() or copy.read_bytes() != now.read_bytes()


def output_file(entry: OutputEntry) -> Path | None:
    """The file ENTRY registered when it stands in the tree, None when it is
    gone — the one test every reader of a registered output makes."""
    return entry.path if entry.path.is_file() else None


@dataclass(frozen=True)
class OutputNow:
    """One output a run registered (ENTRY) as the tree holds its file now —
    what a check of the recorded outputs compares (`outputs_now`), so the
    check opens no file.

    Attributes:
        entry: The output as outputs.json records it.
        stands: Its file stands in the tree (`output_file`).
        sha256: The file's sha256 now, full hex — None when it is gone, and
            None unread when outputs.json records none to compare with.
    """

    entry: OutputEntry
    stands: bool
    sha256: str | None


def output_now(entry: OutputEntry) -> OutputNow:
    """ENTRY with its file as it stands now: whether it stands, and its
    sha256 (`digests.file_digest`) only when it stands and the record holds
    one to compare with. Raises OSError when that file does not read."""
    stands = output_file(entry) is not None
    compared = stands and entry.sha256 is not None
    return OutputNow(entry, stands, file_digest(entry.path) if compared else None)


def outputs_now(run_dir: Path) -> list[OutputNow] | None:
    """Every output RUN_DIR registered (`read_outputs`) as the tree holds it
    now (`output_now`), in outputs.json's order; None when the run
    registered none. Raises ArtefactError when outputs.json does not read,
    OSError when a registered file stands and does not read."""
    registered = read_outputs(run_dir)
    return None if registered is None else [output_now(e) for e in registered]


@dataclass(frozen=True)
class KeptRows:
    """The data rows of one JSONL output a run registered (ENTRY), as the
    tree holds the file now — what a check of the kept rows judges
    (`kept_jsonl_rows`), so the check opens no file."""

    entry: OutputEntry
    rows: list[dict[str, object]]


def kept_jsonl_rows(run_dir: Path) -> list[KeptRows]:
    """Every `.jsonl` output RUN_DIR registered (`read_outputs`) that stands
    in the tree (`output_file`), with its data rows (`jsonl.data_rows_of`),
    in the order outputs.json names them; [] when the run registered none.
    A gone output is left out — `run_record_check.output_record_findings`
    names it. Raises ArtefactError when outputs.json does not read, OSError
    or ValueError when a kept file does not."""
    return [
        KeptRows(entry, jsonl.data_rows_of(entry.path))
        for entry in read_outputs(run_dir) or []
        if entry.path.suffix == ".jsonl" and output_file(entry) is not None
    ]


def metrics_text(run_dir: Path) -> str | None:
    """The run's metrics.json as text, for a prompt that shows it as the
    file stands; None without one. Raises OSError when the file cannot be
    read."""
    path = metrics_path(run_dir)
    return path.read_text(encoding="utf-8") if path.is_file() else None


def read_metrics(path: Path) -> dict[str, object]:
    """A run's metrics.json as a JSON object. Raises MetricsError naming the
    file when it is unreadable, not JSON, or not an object — a list such as
    `["criterion_1_pass"]` read as metrics would satisfy the guaranteed
    intent check. Skipping an unreadable file would choose the next older
    run as if the newer had reported no intent keys."""
    try:
        data = _json_of(path, "metrics")
    except ArtefactError as exc:
        raise MetricsError(str(exc), cause=exc.cause) from exc
    if not isinstance(data, dict):
        raise MetricsError(
            f"{path}: metrics must be a JSON object, not {type(data).__name__}"
        )
    return cast(dict[str, object], data)


def _schema_problem(sv: object) -> str | None:
    """Why a record's schema version cannot be read by this package."""
    # no schema_version, or one below 2: a record from when metrics.json
    # alone marked a finish
    before_schema = "a run of labkit before 0.21 — read it with labkit 0.47"
    if sv is None:
        return f"no schema_version: {before_schema}"
    if not isinstance(sv, int) or isinstance(sv, bool):
        return f"schema_version = {sv!r}, not an integer"
    if sv < 2:
        return f"schema_version = {sv}, below 2: {before_schema}"
    if sv == 2:
        return "schema_version = 2; read this record with labkit 0.99.0"
    if sv == 3:
        return (
            "schema_version = 3; read this record with labkit 0.103.0 "
            "(`cost_tier` became `repeat_cost` in 0.104.0)"
        )
    if sv == 4:
        return (
            f"schema_version = 4; read this record with labkit {SCHEMA_4_READ_BY} "
            f"(input origins are recorded from schema 5 on)"
        )
    if sv != RUN_SCHEMA:
        return f"schema_version = {sv}; expected {RUN_SCHEMA}"
    return None


#: labkit's own tables in config.json: each an object or null (`promises`
#: is null for a protocol without a block). Held on read — a damaged one
#: read as an empty table would let a repeat with an empty config pass as
#: comparable.
RECORD_TABLES = ("config", "data", "models_resolved", "promises")


def _derived_shape_problem(cfg: JsonObject) -> str | None:
    """`derived_from` null or a run id: the parent is a run of the same
    runs/ directory, named, never a path — `./<own run>` would loop the
    walk forever and `../../<elsewhere>` would leave the area."""
    parent = cfg.get("derived_from")
    if parent is None or (isinstance(parent, str) and RUN_ID.fullmatch(parent)):
        return None
    return (
        f"derived_from = {parent!r} must name a run of this runs/ directory (a run id)"
    )


def _repeat_shape_problem(cfg: JsonObject) -> str | None:
    """`repeat_of` null or a run id; `draw` null without it, an integer >= 2
    with it. A damaged value read as "no repeat" would put a repeat back
    into the answering choice — loud instead."""
    parent, draw = cfg.get("repeat_of"), cfg.get("draw")
    if parent is None:
        return None if draw is None else f"draw = {draw!r} without repeat_of"
    if not isinstance(parent, str) or RUN_ID.fullmatch(parent) is None:
        return f"repeat_of = {parent!r}, not a run id"
    if not isinstance(draw, int) or isinstance(draw, bool) or draw < 2:
        return f"draw = {draw!r} for a repeat, not an integer >= 2"
    return None


#: why a run cannot supply a reported result (`Unreportable.cause`)
NO_MEASUREMENT = "no measurement"
UNFROZEN_ACK = "unfrozen acknowledgement"


@dataclass(frozen=True)
class Unreportable:
    """One reason a run cannot supply a reported result.

    Attributes:
        cause: NO_MEASUREMENT or UNFROZEN_ACK — what a gate reads its rule
            assignment from (`finalize.UNREPORTABLE_RULES`), never the words.
        why: The mark, as a gate's sentence continues it.
    """

    cause: str
    why: str


def unreportable(cfg: RunConfig) -> list[Unreportable]:
    """Reasons this run cannot supply a reported result, each with its
    cause as data.

    Only a measurement without an unfrozen acknowledgement is eligible;
    the release gate checks completion, audits and recomputation separately.
    """
    marks: list[Unreportable] = []
    if cfg.run_kind != MEASUREMENT:
        marks.append(
            Unreportable(
                NO_MEASUREMENT,
                f"a {cfg.run_kind} (run_kind={cfg.run_kind!r}), not a measurement",
            )
        )
    if cfg.unfrozen_ack:
        marks.append(
            Unreportable(
                UNFROZEN_ACK,
                "a full run acknowledged over an unfrozen protocol with "
                "LABKIT_UNFROZEN=1",
            )
        )
    return marks


#: what a run records as its `git` when it started outside a repository or
#: before the first commit (`provenance.git_state` writes it; its
#: `git_full` is "" then, which `recorded_commit` reads)
NO_GIT: Final = "no-git"
#: the mark `git_state` appends when the tree differed from the commit
DIRTY_MARK: Final = "+dirty"


def recorded_commit(cfg: RunConfig) -> str | None:
    """The commit CFG's run started at — HEAD's full sha as the record names
    it (`git_full`) —, or None when it started outside a repository or
    before the first commit (`git_full` "", `git` NO_GIT). The one commit
    of a run: what its measurement is ordered by
    (`area_state.Measured.firsts`) and what the registration is held
    to. `git` carries the short form and whether the tree was dirty
    (`cfg.git.endswith(DIRTY_MARK)`): the commit says what stood committed,
    the mark that more stood in the tree."""
    return cfg.git_full or None


def next_output_name(path: Path) -> str:
    """The name a new measurement's own output takes beside PATH:
    `<stem>_v<N+1>` after a `_v<N>` stem, else `<stem>_v2` — the name the
    refusal of a continued finished run and finalize's hold suggest."""
    m = re.fullmatch(r"(.*_v)(\d+)", path.stem)
    stem = f"{m.group(1)}{int(m.group(2)) + 1}" if m else f"{path.stem}_v2"
    return f"{stem}{path.suffix}"


def completion_state(run_dir: Path) -> RunState:
    """`run_state` of a run directory read from disk, liveness not asked.

    The one question every consumer that picks or accepts a run must ask —
    recheck, a derived run's parent, intent-check's choice, the usability
    scorer. Asking `metrics.json` alone would let an unfinalized run
    (metrics, no completion record) be rechecked as a kept number and
    accepted as a parent. A directory without config.json is not a
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
    patch file, and often gets wrong."""

    run_id: str
    state: RunState  # run_state, liveness not asked
    run_kind: RunKind  # preparation · probe · measurement, as config.json records it
    derived_from: str | None  # the run whose rows this one re-evaluated
    models: tuple[str, ...]  # model aliases the run resolved; () when none
    git: str  # the commit at start, "+dirty" when the tree was not clean (untracked files count)
    uncommitted_bytes: int  # size of uncommitted.patch; 0: no tracked file differed
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
    patch = patch_path(run_dir)
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
#: a dropped `"unfrozen_ack": true` would make an acknowledged run reportable.
#: A key outside the table is refused as well: the
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
    "repeat_cost": (str, True),
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
    repeat_cost: str | None
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
    sv = cfg.get("schema_version")
    problem = _schema_problem(sv)
    if problem:
        # a version this labkit does not read is OTHER_SCHEMA; a value that
        # is no version at all is a malformed record
        named = sv is None or (isinstance(sv, int) and not isinstance(sv, bool))
        raise RunConfigError(problem, cause=OTHER_SCHEMA if named else MALFORMED)
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
        if cfg["repeat_cost"] is not None and cfg["repeat_cost"] not in REPEAT_COSTS:
            raise RunConfigError(
                f"repeat_cost = {cfg['repeat_cost']!r}; expected "
                f"{' | '.join(repr(c) for c in REPEAT_COSTS)} or null (unbound or unfilled head)"
            )
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
        repeat_cost=cfg["repeat_cost"],
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
    whose metadata cannot be read (the RunConfigError's sentence), and
    `error_cause` its kind (`RunConfigError.cause`), set exactly then.
    `from_commit` names the commit the record was read back from
    (`run_dir_from_text`) for a run the file state lacks and a commit
    holds — the commit a checkout restores it from; None for a directory
    the state holds (`area_state.committed_runs`)."""

    dir: Path
    config: RunConfig | None
    error: str | None
    from_commit: str | None = None
    error_cause: str | None = None

    def __post_init__(self) -> None:
        if self.config is not None and self.error is not None:
            raise ValueError(
                f"{self.dir}: a RunDir is a read run or an unreadable one, not both"
            )
        if (self.error is None) != (self.error_cause is None):
            raise ValueError(
                f"{self.dir}: an unreadable RunDir carries its error and its "
                f"cause, a readable one neither"
            )


def read_run_dir(d: Path) -> RunDir:
    """The `RunDir` of directory D, its config.json read once; an unreadable
    one is carried in `error`, never raised."""
    try:
        return RunDir(d, read_run_config(d), None)
    except RunConfigError as exc:
        return RunDir(d, None, str(exc), error_cause=exc.cause)


def patch_lost(rd: RunDir) -> bool:
    """Whether run RD started from a changed tree and its uncommitted.patch
    is gone: runlog writes the patch whenever the tree was not clean (its
    `git` ends in DIRTY_MARK), so without the file the commit alone is not
    what the run saw — neither its protocol text nor its code reads back
    (`start_point`). RD's config must read."""
    assert rd.config is not None, "a run whose config reads"
    return rd.config.git.endswith(DIRTY_MARK) and not patch_path(rd.dir).is_file()


#: the way out of a patch with content beside a record of a clean tree
#: (`patch_contradicts_record`): the person finds out which of the two
#: holds; no command removes the patch or rewrites the mark
PATCH_CONTRADICTION_WAY: Final = (
    "find out which of the two holds, and change nothing before: a patch "
    "left over from elsewhere is moved out of the run's directory, a record "
    "changed by hand is restored from git or a backup; where neither can be "
    "told, the run's start stays unknown and only a new measurement holds"
)


def patch_contradicts_record(rd: RunDir) -> str | None:
    """The clause saying that run RD keeps changes in its
    `uncommitted.patch` although its record says the tree was clean (its
    `git` does not end in DIRTY_MARK), naming both files — or None where
    the two agree. A run that starts from a clean tree leaves no patch or
    an empty one (runlog reads the mark before the run's directory exists
    and writes the patch after, when that directory alone makes the tree
    differ), so a patch with content beside such a record is a
    contradiction: a file left by something else, or a record changed
    since. Which of the two is what the run started from is not known, so
    no reader of a run's start picks one (`start_point`,
    `run_record_check.code_since_run`); the way out is
    PATCH_CONTRADICTION_WAY. RD's config must read."""
    assert rd.config is not None, "a run whose config reads"
    if rd.config.git.endswith(DIRTY_MARK) or not patch_text(rd.dir).strip():
        return None
    name, patch = rd.dir.name, patch_path(rd.dir).name
    return (
        f"keeps changes in {RUNS_DIR}/{name}/{patch} beside a record that says "
        f"its tree was clean ({RUNS_DIR}/{name}/{CONFIG_FILE}: git "
        f"{rd.config.git}, without {DIRTY_MARK}), and a run that starts from a "
        f"clean tree keeps none: which of the two is what it started from is "
        f"not known"
    )


@dataclass(frozen=True)
class StartPoint:
    """What a run started from, readable in ROOT: COMMIT, the full sha its
    record names, and CHANGED_TREE, whether the record says the tree had
    changes then (`git` ends in DIRTY_MARK) — where it did, the run's
    `uncommitted.patch` stands (`start_point` refused otherwise)."""

    root: Path
    commit: str
    changed_tree: bool


def start_point(rd: RunDir, root: Path | None, *, subject: str) -> StartPoint | str:
    """Where run RD started, as a `StartPoint` — or a str: the sentence
    saying why its start cannot be read back, opened by SUBJECT (how the
    caller names the run: "run <id>", "its first measurement <id>"). The
    one home of the preconditions the protocol text a run saw
    (`protocol_then.as_measured`) and the code it ran
    (`run_code.code_then`) share; what each reads from the start point is
    its own. In this order:

    1. RD's record does not read.
    2. The record names no commit (`recorded_commit`).
    3. ROOT is None: no repository to read the commit from.
    4. It started from a tree with changes and its patch is gone
       (`patch_lost`): the commit alone is not what it started from.
    5. It keeps a patch with content beside a record of a clean tree
       (`patch_contradicts_record`): which of the two holds is not known;
       the sentence carries the way out (PATCH_CONTRADICTION_WAY), since
       the callers' own ways out restore what is missing and here nothing
       is.
    6. This clone does not hold the commit.

    Steps 4 and 5 are also the helpers comparison's own blockers
    (`run_record_check.code_since_run`), which reads the same patch.

    A run gone from the tree (`from_commit`) that started from a changed
    tree is `code_then`'s own refusal, made before it asks here. A caller
    that gets a `StartPoint` reads the patch exactly where CHANGED_TREE
    says so: without the mark the patch is absent or empty."""
    if rd.config is None:
        return f"{subject} has no readable record"
    commit = recorded_commit(rd.config)
    if commit is None:
        return f"{subject} recorded no commit"
    if root is None:
        return f"{subject}: no repository to read the commit from"
    if patch_lost(rd):
        return (
            f"{subject} started from a tree with changes ({rd.config.git}), "
            f"and its uncommitted.patch is gone: the commit alone is not what "
            f"it started from"
        )
    contradiction = patch_contradicts_record(rd)
    if contradiction is not None:
        return f"{subject} {contradiction} — {PATCH_CONTRADICTION_WAY}"
    if not commit_known(root, commit):
        return (
            f"{subject} started at {commit[:12]}, a commit this clone does "
            f"not hold — `git fetch` brings it"
        )
    return StartPoint(root, commit, rd.config.git.endswith(DIRTY_MARK))


def run_dir_from_text(d: Path, text: str, *, from_commit: str | None = None) -> RunDir:
    """The `RunDir` of run directory D whose config.json git holds as TEXT:
    in its index (FROM_COMMIT None), or at FROM_COMMIT for a run the file
    state lacks — the run is then read as that commit recorded it. An
    unreadable record is carried in `error`, never raised (`read_run_dir`)."""
    try:
        return RunDir(d, parse_run_record(text, d / CONFIG_FILE), None, from_commit)
    except RunConfigError as exc:
        return RunDir(d, None, str(exc), from_commit, exc.cause)


def run_dirs(area: Path) -> list[RunDir]:
    """Every directory under the area's `runs/`, oldest first by name (run_ids
    start with the timestamp; two runs of one second differ only in their
    random suffix, and their order among themselves is not their start
    order — no record holds a finer time; the answering-run choice refuses
    such a pair, `answering_run.same_second_rival`), each with its
    metadata read once. The one walk for listing, index, choice and
    completion, so none decides for itself what an unreadable run means:
    here it is data — the caller says whether it refuses, reports or
    skips."""
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
# finalize and labkit-params


#: States that mean "this run is not a clean finish" — `--wait` exits 2 on
#: any of them, `reindex` rebuilds none of them. `unknown` is NOT in this
#: list: it means "can't tell", and treating it as failed would hide a run
#: that is still going.
FAILED_STATES = ("crashed", "unfinalized", "corrupt", "unreadable")


def lineage(run_dir: Path) -> list[Path]:
    """The run and its ancestors along `derived_from`, the run first. The
    whole chain is checked, not only up to the run a reader needs: every
    run has a config.json, every `derived_from` is a run id (held where the
    config is read, `runs.read_run_config`) naming a run directory beside
    it, and no run comes twice — compared as resolved paths, not names.

    Raises:
        ValueError: A run without config.json, a `derived_from` that is not
            a run name, a parent that is not under run_dir's parent, or a
            loop — wherever in the chain it sits. RunConfigError (a
            ValueError) for a damaged config.json.
    """
    chain: list[Path] = []
    here = run_dir
    while True:
        cfg = read_run_config(here)
        if cfg is None:
            raise ValueError(
                f"{here}: no config.json — the lineage of {run_dir.name} breaks here"
            )
        chain.append(here)
        parent = cfg.derived_from  # a run id, held where the config is read
        if parent is None:
            return chain
        nxt = run_dir.parent / parent
        if nxt.resolve() in (run.resolve() for run in chain):
            names = " -> ".join([*(run.name for run in chain), parent])
            raise ValueError(f"{run_dir.name}: derived_from loops: {names}")
        here = nxt
        if not here.is_dir():
            raise ValueError(
                f"{run_dir.name}: derived_from names {parent}, which is not under {run_dir.parent}"
            )


def source_runs(run_dir: Path) -> list[Path]:
    """RUN_DIR and every run its rows and inputs rest on, each once,
    RUN_DIR first, then in the order found: the parent along
    `derived_from` (config.json), the runs whose rows its JSONL outputs
    continued (outputs.json `continues`), the origin runs of its inputs
    (config.json `data`) — each followed the same way. All are looked up
    beside RUN_DIR, in the same `runs/` directory.

    Not followed: the run that stored an answer RUN_DIR replayed from the
    cache — the entry holds that run's model answer, and a stand-in is
    never stored under a run (`llm_cache.store_stand_in`); and `repeat_of`
    — a repeat asks the model anew.

    Raises:
        ValueError: A run on the way without config.json, a source run that
            is not a directory beside RUN_DIR; RunConfigError and
            ArtefactError (both ValueError) for a config.json, input record
            or outputs.json that does not read.
    """
    found: list[Path] = [run_dir]
    i = 0
    while i < len(found):
        here = found[i]
        i += 1
        cfg = read_run_config(here)
        if cfg is None:
            raise ValueError(f"{here}: no config.json — its source runs are not known")
        outputs = read_outputs(here) or []
        named = [
            *([cfg.derived_from] if cfg.derived_from is not None else []),
            *(r for entry in outputs for r in entry.continues),
            *(e.origin_run for e in data_entries(cfg.data, str(here / CONFIG_FILE))),
        ]
        for run_id in named:
            if run_id is None:
                continue
            source = run_dir.parent / run_id
            if not source.is_dir():
                raise ValueError(
                    f"{here.name} rests on run {run_id}, which is not under "
                    f"{run_dir.parent}"
                )
            # compared as resolved paths, as `lineage` does: one run once
            if source.resolve() not in (r.resolve() for r in found):
                found.append(source)
    return found


def model_provenance_run(run_dir: Path) -> Path | None:
    """The run whose `models_resolved` says which model answered the rows
    `run_dir` reads: the run itself when it recorded one, else the nearest
    ancestor along `derived_from` that did (a derived run records none —
    its rows are the parent's, and resolving the alias anew would be
    provenance the rows never had). None when no run in the chain recorded
    a model.

    Raises:
        ValueError: From `lineage` — a broken chain, also above the run
            that recorded the model.
    """
    for run in lineage(run_dir):
        cfg = read_run_config(run)
        if cfg is not None and cfg.models_resolved:
            return run
    return None


def recorded_models(run_dir: Path) -> str:
    """Which model answered RUN_DIR's rows, as the run records say
    (`model_provenance_run`): its `models_resolved` as stored, keys sorted,
    under the run that recorded it — or a sentence that no run in the chain
    recorded one, or that the chain does not read. What an audit is shown
    of a bound validation, never today's models.toml."""
    try:
        source = model_provenance_run(run_dir)
        cfg = read_run_config(source) if source is not None else None
    except ValueError as exc:  # RunConfigError too
        return f"run {run_dir.name}: its record does not read ({exc}); which model answered is not known"
    if source is None or cfg is None:
        return (
            f"run {run_dir.name} recorded no model (no models_resolved, nor any "
            "run it derives from); which model answered is not recorded"
        )
    via = "" if source == run_dir else f", the run {run_dir.name} derives from"
    return f"models_resolved recorded by run {source.name}{via}:\n" + json.dumps(
        cfg.models_resolved, ensure_ascii=False, sort_keys=True, indent=2
    )


def recorded_runs(run_dir: Path) -> list[Path]:
    """RUN_DIR and, when another run recorded its model
    (`model_provenance_run`), that run — the records `recorded_models`
    reads, so a stamp over their `config.json` moves with the recorded
    model. RUN_DIR alone when the chain does not read."""
    try:
        source = model_provenance_run(run_dir)
    except ValueError:
        return [run_dir]
    return [run_dir] if source in (None, run_dir) else [run_dir, source]
