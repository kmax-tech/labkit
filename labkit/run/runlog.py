"""runlog — minimal per-experiment run tracking (stdlib-only, no service).

Convention (LAB-043 Runs go through `runlog`, LAB-079 Self-contained experiment areas): every run — pilots included — goes through
`with runlog.run(...)`. Each run gets a self-contained dir and one append-only
run-index row; PROTOCOL-<task>.md cites run_ids instead of pasting numbers.

    runs/<run_id>/config.json      the record at start: config, data, git state,
                                   env, models resolved, the binding (protocol id),
                                   `run_kind` (preparation, probe or measurement), `unfrozen_ack`
                                   and the failed audit attempt it rests on
    runs/<run_id>/metrics.json     the numbers reported via r.metrics()
    runs/<run_id>/outputs.json     the files registered via r.output(), as the
                                   run left them (sha, lines, rows_from, continues)
    runs/<run_id>/completion.json  confirmed completion: finish time, end git
                                   state, note, the runs this one continues
    runs/<run_id>/script-source.py  the script AS IT RAN (untracked or dirty
                                   code is in no commit and in no diff)
    runs/<run_id>/uncommitted.patch  the diff, IF the repo was dirty (tracked files only)
    runs/<run_id>/source-untracked/  untracked files next to the script, verbatim
    runs/<run_id>/<raw files>      verbatim model output etc. (save_raw)
    runs.tsv                       run index, one row per completed run
                                   (columns: RUN_INDEX_COLS) — derived, never a source

Three ways a run depends on another run's rows — not one:

    _prov          per row; the SCRIPT sets it (`batch.Store(prov=...)`), it
                   names the run and model that wrote the row; read by
                   `batch.row_runs`, held by `finalize`
    continues      per run; runlog RECORDS it at finalize from the rows a
                   .jsonl output held when `r.output()` registered it (outputs.json per
                   file, completion.json as the union) — a resumed file;
                   the earlier run need not be completed; carries no model
    derived_from   per run; the SCRIPT declares it (`runlog.run(...,
                   derived_from=ID)`), config.json holds it; the parent must
                   be completed and no repeat (else the best draw could
                   answer through it); the run makes no model call and records no
                   model — `answering_run.model_provenance_run` walks this key alone
    repeat_of      per run; `runlog.run(..., repeat_of=ID)`: the same measurement
                   asked again — new model calls, its own model record, the
                   same protocol, block, config and inputs as ID or a
                   refusal (`answering_run.repeat_mismatch`); `draw` numbers it (2,
                   3, …). With `reseed=True` (a fit's spread over seeds) runlog
                   sets the config's `seed` to `answering_run.repeat_seed` of
                   ID and the draw and records that value — the seed the
                   script passed is not used, every other key stays ID's;
                   the script measures with `Run.config` and writes to
                   `Run.draw_output`. Supporting evidence: it never answers the protocol

Usage:
    import runlog
    with runlog.run("bt-oracle",
                    config={"model": "haiku", "seed": 42},
                    data={"train": TRAIN, "dev": DEV, "test": TEST}) as r:
        ...
        r.save_raw("responses.jsonl", raw_text)   # raw output, verbatim
        r.metrics(acc=0.83, n=100)
        r.note("pilot: threshold 0.5 too strict")  # optional

`data` uses the standard split keys "train" / "dev" / "test" (any other key is
recorded too, just not split-checked). For each file runlog records path,
sha256 and row count, and it checks the three splits for overlapping `id`s —
a leak raises before the run starts, rather than inflating a score nobody can
explain later. Recording the files is what makes "which data was that?"
answerable six weeks on; the split keys are what make it answerable by a tool.

A run directory exists only with its config.json (0.74.0: everything that
can fail is read before mkdir, a failure while writing the record removes
the directory). An incomplete run leaves its dir with config.json but
without the required completion markers — visible, not silent. The run-index row is written on
clean exit only. States: completed · running · unknown · crashed ·
unfinalized · corrupt · unreadable (config.json damaged, or written before
schema 4 — read with its pinned labkit).
"""

from __future__ import annotations

import contextlib
import fcntl
from dataclasses import dataclass
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import TracebackType
from collections.abc import Iterator

from labkit.formats.runs import metrics_path, patch_path, run_path
from labkit.run import batch
from labkit.formats import console, repo
from labkit.formats.files import write_atomic
from labkit.formats.gate import with_way_out
from labkit.formats.standard_contract import lane
from labkit.formats.runs import (
    COMPLETION_FILE,
    CONFIG_FILE,
    OUTPUTS_FILE,
    COMPLETED,
    RunKind,
    RUN_SCHEMA,
    RECORD_SHA_CHARS,
    RUN_ID_TIME,
    UNREADABLE,
    RunConfig,
    RunConfigError,
    RunState,
    is_alive,
    now_stamp,
    read_completion,
    write_failure,
    read_metrics,
    recorded_path,
    run_dirs,
    run_state,
)
from labkit.formats.answering_run import (
    REPEAT_SEED_KEY,
    next_draw,
    repeat_mismatch,
    repeat_seed,
)
from labkit.run.provenance import (
    Provenance,
    describe_data,
    git_state,
    record_provenance,
    script_sha,
    source_digest,
    snapshot_script,
    snapshot_untracked_sources,
)
from labkit.run.start_check import (
    Prepared,
    completed_parent,
    require_detached,
    freeze_gate,
    prepare,
    require_registration,
    require_valid_reseed,
    foreground_timeout,
)

RUN_INDEX_COLS = [
    "run_id",
    "git",
    "script",
    "data",
    "config",
    "metrics",
    "note",
    "protocol_id",
]


def notify_desktop(title: str, body: str) -> None:
    """Best-effort macOS notification — session-independent, never raises.

    The monitor of record for an overnight run must not be tomorrow's status
    question (2026-08-17: a run finished at night and sat unnoticed for ~9 h).
    Opt-out with LABKIT_NOTIFY=0; anything else leaves it on.
    """
    if os.environ.get("LABKIT_NOTIFY") == "0" or sys.platform != "darwin":
        return
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                'display notification "{}" with title "{}"'.format(
                    body.replace('"', "'")[:200], title.replace('"', "'")[:60]
                ),
            ],
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        pass


_NOTIFY_MIN_S = 120  # a pilot finishing under 2 min needs no banner


#: how long an append or reindex waits for the index lock before it is
#: called hung
_INDEX_LOCK_TIMEOUT_S = 30.0


@contextlib.contextmanager
def _index_lock(base_dir: Path) -> Iterator[None]:
    """Exclusive lock for every change to runs.tsv — append, reindex.

    Without it a reindex and a finishing run race: one appends while the
    other reads, and a row lands twice or not at all. flock, not a lock
    FILE: the kernel drops it when the process dies, so a crashed run leaves
    no stale lock for the next one to trip over. Header creation and the
    duplicate check run inside it too — they read the same file.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(base_dir / f".{RUN_INDEX}.lock", os.O_CREAT | os.O_RDWR, 0o644)
    t0 = time.monotonic()
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() - t0 >= _INDEX_LOCK_TIMEOUT_S:
                    raise RuntimeError(
                        f"runlog: runs.tsv locked for over {int(_INDEX_LOCK_TIMEOUT_S)}s "
                        f"({base_dir}) — another append or reindex "
                        f"is running, or one hung."
                    )
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def index_row(
    run_id: str,
    git: str,
    script: str,
    data: object,
    config: object,
    metrics: object,
    note: str,
    protocol_id: str,
) -> list[str]:
    """One row of the run index in RUN_INDEX_COLS order — the one layout
    for a run's end (`Run.finish`) and `reindex`, which each built it."""
    return [
        run_id,
        git,
        script,
        json.dumps(data, ensure_ascii=False, sort_keys=True),
        json.dumps(config, ensure_ascii=False, sort_keys=True),
        json.dumps(metrics, ensure_ascii=False, sort_keys=True),
        note,
        protocol_id,
    ]


def _append_row(index: Path, row: list[str]) -> None:
    """One row onto the run index, header created if absent. Callers hold
    the index lock — header creation reads the file too."""
    if not index.exists():
        index.write_text("\t".join(RUN_INDEX_COLS) + "\n", encoding="utf-8")
    with index.open("a", encoding="utf-8") as f:
        f.write("\t".join(c.replace("\t", " ").replace("\n", " ") for c in row) + "\n")


#: the run index of an area, a local view rebuilt from runs/ (`reindex`)
RUN_INDEX = "runs.tsv"


def header_refusal(header: list[str]) -> str | None:
    """Why a run index with HEADER may not be appended to, or None: columns
    other than RUN_INDEX_COLS — appended to, an old-format index would not
    error, its columns would shift silently. One sentence for the run's
    start (`_check_run_index`) and `reindex` (`index_refusal`)."""
    if not header or header == RUN_INDEX_COLS:
        return None
    return (
        f"{RUN_INDEX} columns {header} don't match this runlog "
        f"({RUN_INDEX_COLS}) — an index written by labkit before 0.21. "
        "Migrate it with labkit 0.47 (`runlog migrate-index <area>`, which "
        "keeps every row verbatim), then come back; appending without it "
        "would shift columns silently."
    )


def _check_run_index(base_dir: Path) -> None:
    """Refuse to run against a run index of other columns (`header_refusal`),
    before the run, with the migration spelled out. Reads the header line
    only. Raises RuntimeError."""
    index = base_dir / RUN_INDEX
    if not index.exists():
        return
    with index.open(encoding="utf-8") as f:
        why = header_refusal(f.readline().rstrip("\n").split("\t"))
    if why is not None:
        raise RuntimeError(why)


def _runs_held(path: Path) -> set[str] | None:
    """The runs whose rows PATH holds now (`batch.row_runs`): empty for a
    file not yet there, None when its rows cannot be read."""
    if not path.exists():
        return set()
    try:
        return set(batch.row_runs(path).runs)
    except ValueError:
        return None


def _repeat_parent(base_dir: Path, repeat_of: str) -> RunConfig:
    """The config of REPEAT_OF, a completed primary run of this area, or a
    refusal: missing, not completed, unreadable, or itself a repeat."""
    pcfg = completed_parent(base_dir, "repeat_of", repeat_of)
    if pcfg.repeat_of is not None:
        raise SystemExit(
            with_way_out(
                f"runlog: {repeat_of} is itself a repeat of {pcfg.repeat_of}",
                f"repeat the primary run: `repeat_of={pcfg.repeat_of!r}`",
            )
        )
    return pcfg


def _repeat_draw(
    base_dir: Path,
    repeat_of: str | None,
    reseed: bool,
    prepared: Prepared,
    data: dict,
    models: dict,
) -> tuple[str | None, int | None, dict]:
    """(repeat_of, draw, config) for config.json, before mkdir and under the
    index lock the caller holds: a repeat draws a completed primary run of
    this area again, comparable in protocol, promise block, config and
    inputs (`answering_run.repeat_mismatch`) — else a refusal. Draw 1 is the
    run itself; its repeats count on from 2. RESEED (its conditions held
    before, `start_check.require_valid_reseed`) sets the config's REPEAT_SEED_KEY
    to `repeat_seed(repeat_of, draw)`, and the comparison holds it to that
    value. (None, None, the config) for a run that repeats none."""
    if repeat_of is None:
        return None, None, prepared.config
    if prepared.derived_from is not None:
        raise SystemExit(
            with_way_out(
                "runlog: repeat_of and derived_from exclude each other — a repeat "
                "asks the model again, a derived run re-reads old rows",
                "pass the one this run is: `repeat_of=` to ask again, "
                "`derived_from=` to re-read",
            )
        )
    pcfg = _repeat_parent(base_dir, repeat_of)
    try:
        draw = next_draw(base_dir, repeat_of)
    except RunConfigError as exc:
        raise SystemExit(
            with_way_out(
                f"runlog: repeat_of={repeat_of!r}: the next draw number cannot be "
                f"counted — {exc}",
                "restore the run record the sentence names as runlog wrote it "
                "(`git checkout HEAD -- <path>` where git holds it)",
            )
        ) from exc
    config = prepared.config
    if reseed:
        config = {**config, REPEAT_SEED_KEY: repeat_seed(repeat_of, draw)}
    mine = {
        "protocol": prepared.bound.binding,
        "promises": prepared.promises,
        "config": config,
        "data": data,
        "script_sha": script_sha(),
        "models_resolved": models,
    }
    try:
        differs = repeat_mismatch(
            pcfg, mine, reseed_of=(repeat_of, draw) if reseed else None
        )
    except RunConfigError as exc:
        raise SystemExit(
            with_way_out(
                f"runlog: repeat_of={repeat_of!r}: {exc}",
                "restore the run record the sentence names as runlog wrote it "
                "(`git checkout HEAD -- <path>` where git holds it)",
            )
        ) from exc
    if differs:
        raise SystemExit(
            with_way_out(
                f"runlog: this run is no repeat of {repeat_of} — it measures "
                f"something else:\n  " + "\n  ".join(differs),
                "run it as the same measurement, or as a run of its own "
                "without `repeat_of`",
            )
        )
    return repeat_of, draw, config


#: how often a run id is drawn when the drawn one is taken — 16^4 suffixes
#: per second make a third collision in a row a sign of something else
RUN_ID_DRAWS = 8


def _make_run_dir(base_dir: Path) -> tuple[str, Path]:
    """A new run's id and its directory, created: `<second>_<4 hex>`
    (`RUN_ID_TIME`). The suffix is drawn again when the directory exists —
    two starts in the same second drew the same four hex digits once and
    `mkdir` failed the second run (test_repeats, 2026-10-21). More than
    `RUN_ID_DRAWS` taken in a row is an error, not a loop."""
    for _ in range(RUN_ID_DRAWS):
        run_id = time.strftime(RUN_ID_TIME) + "_" + uuid.uuid4().hex[:4]
        run_dir = run_path(base_dir, run_id)
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return run_id, run_dir
    raise RuntimeError(
        f"{base_dir}: {RUN_ID_DRAWS} run ids drawn this second and every one taken"
    )


class Run:
    """One measure run: its directory, its frozen config, the outputs it
    registers and the metrics it reports.

    `__init__` is three phases, every refusal BEFORE the directory exists:

      1. preparation (`prepare`): the parent a derived run names, the
         protocol binding, the promise snapshot, the config frozen
      2. the start check, in this order: the registration
         (tables owed, constants unchanged), the detach gate only for a
         declared long run whose lane forbids the foreground, whose
         harness sets a limit and which is not already detached; the run
         index header; data leakage when data is supplied; and for a full
         run the freeze gate
         (undecided blockers, the freeze or the registration, the
         acknowledgement over a failed audit)
      3. creation: git, environment and models read (`record_provenance` — a
         derived run resolves no model anew), then under one lock for a
         repeat: the draw counted and, with RESEED, its seed derived
         (`_repeat_draw`), mkdir, the record written (`_write_record`); a
         failure there removes the directory

    A refusal in 1 or 2 is a SystemExit (a RuntimeError for the index
    header and a leak), and leaves no run directory behind. `class run` is
    the context manager around this."""

    def __init__(
        self,
        experiment: str,
        config: dict,
        base_dir: Path,
        data: dict | None = None,
        run_kind: RunKind = "probe",
        protocol: str | Path | None = None,
        derived_from: str | None = None,
        repeat_of: str | None = None,
        reseed: bool = False,
    ) -> None:
        # 1. preparation — what the run is held to, read once
        prepared = prepare(base_dir, config, run_kind, protocol, derived_from)
        # 2. the start check — the order and every skip are visible here;
        #    helpers check the facts without reading a partly built Run
        require_registration(
            prepared.bound,
            prepared.block,
            prepared.config,
            prepared.run_kind == "measurement",
        )
        require_valid_reseed(prepared, repeat_of, reseed)
        obligations = lane(prepared.repeat_cost)
        if prepared.run_kind == "measurement" and not obligations.foreground:
            limit = foreground_timeout()
            if limit is not None and os.environ.get("LABKIT_DETACHED") != "1":
                require_detached(base_dir, limit)
        _check_run_index(base_dir)
        described = describe_data(data, base_dir) if data else {}
        unfrozen_ack, audit_failed = False, None
        if prepared.run_kind == "measurement":
            unfrozen_ack, audit_failed = freeze_gate(base_dir, prepared)
        # 3. creation — the record, whole or not at all; the id and the
        # directory are drawn together under the guard below
        self.experiment = experiment
        self.script = Path(sys.argv[0]).name if sys.argv[0] else "<interactive>"
        self.base = base_dir
        self._protocol = prepared.bound.binding
        self._repeat_cost = prepared.repeat_cost
        self._promises = prepared.promises
        self._derived_from = prepared.derived_from
        self._run_kind = prepared.run_kind
        self._data = described
        self._unfrozen_ack = unfrozen_ack
        self._audit_failed = audit_failed
        self._outputs: list[Path] = []
        # per .jsonl output: the runs its rows named at registration, None
        # when they could not be read
        self._held_before: dict[Path, set[str] | None] = {}
        self._metrics: dict = {}
        self._note = ""
        self._t0 = time.monotonic()
        provenance = record_provenance(
            base_dir, prepared.config, derived=prepared.derived_from is not None
        )
        # Count a repeat's draw and write its record under the same lock:
        # concurrent starts must not receive the same number, and `self.draw`
        # is the one number the script names its file by.
        guard = (
            _index_lock(base_dir) if repeat_of is not None else contextlib.nullcontext()
        )
        with guard:
            self._repeat_of, self.draw, self._config = _repeat_draw(
                base_dir, repeat_of, reseed, prepared, described, provenance.models
            )
            self.run_id, self.dir = _make_run_dir(base_dir)
            try:
                self._write_record(provenance)
            except BaseException:
                shutil.rmtree(self.dir, ignore_errors=True)  # no half-made run
                raise

    @property
    def config(self) -> dict:
        """The config as config.json records it — in its stored form (a
        tuple as a list), a reseeded repeat's derived seed included: what
        the script measures with. A new object each time; the record is not
        changed through it."""
        return json.loads(json.dumps(self._config, ensure_ascii=False))

    def draw_output(self, out: Path) -> Path:
        """OUT for a run that repeats none, else the repeat's own file
        `<stem>_draw<N><suffix>` beside it — the one name of a draw's
        output (`lanes`, the estimator skeleton)."""
        return (
            out
            if self.draw is None
            else out.with_name(f"{out.stem}_draw{self.draw}{out.suffix}")
        )

    def _write_record(self, provenance: Provenance) -> None:
        """config.json — what this run was, written once at start — plus the
        script snapshot and the dirty-tree patch. Not the protocol's settings
        head (protocol_block.PROTOCOL_HEAD_KEYS). Every field but the two
        snapshots is set on the run before this is called."""
        frozen = {
            "schema_version": RUN_SCHEMA,
            "experiment": self.experiment,
            "script": self.script,
            "protocol": self._protocol,
            "derived_from": self._derived_from,
            "repeat_of": self._repeat_of,
            "draw": self.draw,
            "run_kind": self._run_kind,
            "unfrozen_ack": self._unfrozen_ack,
            "audit_failed": self._audit_failed,
            "repeat_cost": self._repeat_cost,
            "promises": self._promises,
            "script_sha": snapshot_script(self.dir),
            "untracked_sources": snapshot_untracked_sources(self.dir),
            "pid": os.getpid(),  # lets `active()` tell running from crashed
            "git": provenance.git,
            "git_full": provenance.git_full,
            "python": sys.version.split()[0],
            "env": provenance.env,
            "models_resolved": provenance.models,
            "started": now_stamp(),
            "command": list(sys.argv),  # how to start this run again
            "data": self._data,
            "config": self._config,
        }
        # whole or not at all, like every record file: a listing that read
        # config.json mid-write saw a damaged run (CODE-013; audit 2026-10-15)
        write_atomic(
            self.dir / CONFIG_FILE, json.dumps(frozen, ensure_ascii=False, indent=2)
        )
        # A dirty tree makes the commit hash a lie: save what it doesn't cover.
        if repo.head_sha(self.base) and repo.tree_dirty(self.base):
            write_atomic(patch_path(self.dir), repo.tree_patch(self.base))

    def output(self, *paths: str | Path) -> None:
        """Register the files this run WRITES (2026-08-18).

        config.json freezes the inputs, but where a run wrote its data lived
        only in the script's code — whoever stood inside runs/<id>/ could not
        answer "where did the data go?" without reading source. Registered
        paths land in `outputs.json` at finalize, with sha256 and line count
        taken AFTER the run, so the record describes the file as the run left
        it. Register the batch.Store target right next to opening it.

        A .jsonl output's rows of other runs are read HERE, at registration:
        those are the rows the run continues (`continues`). A foreign row
        that appears later was written during the run by something else,
        and stays foreign for finalize to hold.
        """
        for p in map(Path, paths):
            self._outputs.append(p)
            if p.suffix == ".jsonl":
                self._held_before[p] = _runs_held(p)

    def save_raw(self, name: str, content: str) -> Path:
        """Write a raw text artefact into the run's directory and return its path."""
        p = self.dir / name
        write_atomic(p, content)
        return p

    def metrics(self, **kv: object) -> None:
        """Add numbers to the run's metrics.json (written when the run finishes)."""
        self._metrics.update(kv)

    def note(self, text: str) -> None:
        """Set the run's one-line note for the run index."""
        self._note = text

    def _finalize(self) -> None:
        """outputs.json, metrics.json, completion.json, the index row — in that
        order (a break after metrics leaves `unfinalized`). An output problem
        (file absent at the end, a damaged row) is a NOTE in outputs.json and
        does not stop completion: `completed` vouches for the run's record,
        not for its outputs — `finalize` reads outputs.json and holds them."""
        self._metrics.setdefault("duration_s", round(time.monotonic() - self._t0, 1))
        continues: set[str] = set()
        if self._outputs:
            rows = []
            for p in self._outputs:
                if p.exists():
                    with p.open("rb") as fh:
                        text_lines = sum(1 for _ in fh)
                    entry: dict = {
                        "path": recorded_path(p, self.dir),
                        "sha256": source_digest(p)[:RECORD_SHA_CHARS],
                        "lines": text_lines,
                    }
                    # A resumed file holds rows of the run that broke off:
                    # name it, so "this run continues that one" is in the
                    # record — the runs the file held when it was
                    # registered, never one whose rows came in meanwhile.
                    if p.suffix == ".jsonl":
                        held = self._held_before.get(p, set())
                        try:
                            rr = batch.row_runs(p)
                        except ValueError as exc:
                            entry["note"] = f"rows unreadable: {exc}"
                        else:
                            entry["rows_from"] = dict(sorted(rr.runs.items()))
                            entry["continues"] = sorted(
                                r
                                for r in rr.runs
                                if r != self.run_id and held is not None and r in held
                            )
                            if held is None:
                                entry["note"] = (
                                    "rows unreadable at registration: no run "
                                    "is continued"
                                )
                            continues.update(entry["continues"])
                    rows.append(entry)
                else:
                    rows.append(
                        {
                            "path": recorded_path(p, self.dir),
                            "sha256": None,
                            "lines": None,
                            "note": "registered, but absent at end of run",
                        }
                    )
            write_atomic(
                self.dir / OUTPUTS_FILE,
                json.dumps(rows, ensure_ascii=False, indent=2),
            )
        write_atomic(
            metrics_path(self.dir),
            json.dumps(self._metrics, ensure_ascii=False, indent=2),
        )
        # Order matters, and this is the reason for it: results first, then
        # the confirmed completion, then the index. A break after metrics
        # leaves `unfinalized` (numbers on disk, run not finished); a break
        # after completion.json leaves a run the index missed but `reindex`
        # can rebuild in full. Before this file the two looked the same.
        # tracked files only: the run's own untracked products are not drift
        git_end = git_state(self.base, untracked=False)
        write_atomic(
            self.dir / COMPLETION_FILE,
            json.dumps(
                {
                    "schema_version": RUN_SCHEMA,
                    "finished": now_stamp(),
                    "git": git_end,
                    "git_full": repo.head_sha(self.base),
                    "note": self._note,
                    "continues": sorted(continues),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        row = index_row(
            self.run_id,
            git_end,
            self.script,
            self._data,
            self._config,
            self._metrics,
            self._note,
            self._protocol.get("id") or "",
        )
        with _index_lock(self.base):
            _append_row(self.base / RUN_INDEX, row)
        dur = self._metrics.get("duration_s", 0)
        if os.environ.get("LABKIT_NOTIFY") == "1" or dur >= _NOTIFY_MIN_S:
            notify_desktop(
                f"run finished: {self.experiment}",
                f"{self.run_id} · {dur}s · {len(self._metrics)} metric(s)",
            )


@dataclass(frozen=True)
class ActiveRun:
    """A run of the area that is not completed, as `active` sees it: what it
    is (`state`, `alive` from the recorded pid) beside what it recorded
    (`config`). An unreadable record has no config and says why (`error`).
    The two are kept apart — merged into one dict, a record key named like
    a computed one would have overwritten it."""

    run_id: str
    dir: Path
    state: RunState
    alive: bool | None  # None: unreadable, or liveness undecidable
    config: RunConfig | None  # None exactly when `error` is set
    error: str | None

    def __post_init__(self) -> None:
        if (self.config is None) == (self.error is None):
            raise ValueError(
                f"{self.dir}: an ActiveRun has a config or an error, exactly one"
            )


def active(base_dir: str | Path) -> list[ActiveRun]:
    """Runs in this area that are not completed, each with its `state`.

    This is what makes parallel work cheap — before starting an experiment you
    LOOK instead of asking: which runs are live, and which files do they read
    and write (their config). `alive` distinguishes a running process from a
    crashed one by checking the recorded pid; `state` says what the run
    directory is (see `run_state`).

        runlog <area>        (the installed console command)
    """
    out: list[ActiveRun] = []
    for rd in run_dirs(Path(base_dir)):
        d, cfg = rd.dir, rd.config
        if rd.error is not None:
            out.append(ActiveRun(d.name, d, UNREADABLE, None, None, rd.error))
            continue
        if cfg is None:
            continue
        alive = is_alive(cfg.pid, cfg.script)
        state = run_state(d, alive)
        if state == COMPLETED:
            continue
        out.append(ActiveRun(d.name, d, state, alive, cfg, None))
    return out


class run:
    """Context manager: `with runlog.run("name", config={...}, data={...}) as r:`
    — every refusal and every record is `Run.__init__` (see its docstring);
    `__exit__` finalizes on a clean exit, a crash leaves the dir without
    metrics.json (visible)."""

    def __init__(
        self,
        experiment: str,
        config: dict,
        base_dir: str | Path | None = None,
        data: dict | None = None,
        run_kind: RunKind = "probe",
        protocol: str | Path | None = None,
        derived_from: str | None = None,
        repeat_of: str | None = None,
        reseed: bool = False,
    ) -> None:
        # `protocol`, `derived_from`, `repeat_of`, `reseed` last: no existing
        # positional call shifts.
        base = Path(base_dir) if base_dir else Path(sys.argv[0]).resolve().parent
        self._run = Run(
            experiment,
            config,
            base,
            data,
            run_kind=run_kind,
            protocol=protocol,
            derived_from=derived_from,
            repeat_of=repeat_of,
            reseed=reseed,
        )

    def __enter__(self) -> Run:
        return self._run

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> bool:
        if exc_type is None:
            self._run._finalize()  # crash -> dir stays without metrics.json (visible)
            return False
        try:
            write_failure(self._run.dir, exc_type, exc)  # the reason stays with the run
        except OSError as err:  # never mask the exception that ended the run
            print(
                f"runlog: could not record why {self._run.run_id} broke off: {err}",
                file=sys.stderr,
            )
        return False


def _read_index(index: Path) -> tuple[list[str], list[list[str]]]:
    """(header, rows) of the run index. Callers hold the lock."""
    if not index.exists():
        return [], []
    lines = index.read_text(encoding="utf-8").splitlines()
    if not lines:
        return [], []
    return lines[0].split("\t"), [ln.split("\t") for ln in lines[1:] if ln]


@dataclass(frozen=True)
class Unindexed:
    """What the run folders hold that the run index does not
    (`unindexed`): the ROWS of completed runs without one, the INCOMPLETE
    runs' ids, the UNREADABLE runs' errors (damaged, or written before
    schema 4), and NO_RECORD, folders that hold no config.json."""

    rows: list[list[str]]
    incomplete: list[str]
    unreadable: list[str]
    no_record: list[str]  # folders under runs/ without config.json: no run


def index_refusal(index: Path, header: list[str], rows: list[list[str]]) -> str | None:
    """Why the run index INDEX (its HEADER and ROWS) may not be appended to,
    or None: old columns (`header_refusal`), or a run id listed more than
    once."""
    why = header_refusal(header)
    if why is not None:
        return why
    seen: dict[str, int] = {}
    for row in rows:
        if row:
            seen[row[0]] = seen.get(row[0], 0) + 1
    dupes = sorted(rid for rid, n in seen.items() if n > 1)
    if dupes:
        return (
            f"{index} lists {len(dupes)} run_id(s) more than "
            f"once: {', '.join(dupes[:5])} — repair by hand; a run "
            f"belongs in the index exactly once."
        )
    return None


def unindexed(base_dir: Path, indexed: set[str]) -> Unindexed:
    """The runs of BASE_DIR not among INDEXED (`Unindexed`): a completed one
    as its index row, read from its record; reads, writes nothing."""
    rows: list[list[str]] = []
    incomplete: list[str] = []
    unreadable: list[str] = []
    no_record: list[str] = []
    for rd in run_dirs(base_dir):
        d, cfg = rd.dir, rd.config
        if d.name in indexed:
            continue
        if rd.error is not None:
            unreadable.append(rd.error)
            continue
        if cfg is None:
            no_record.append(d.name)
            continue
        if run_state(d, alive=False) != COMPLETED:
            incomplete.append(d.name)
            continue
        comp = read_completion(d)
        rows.append(
            index_row(
                d.name,
                str(comp.get("git", "")),
                cfg.script or "",
                cfg.data,
                cfg.config,
                read_metrics(metrics_path(d)),
                str(comp.get("note", "")),
                cfg.protocol.id or "",
            )
        )
    return Unindexed(rows, incomplete, unreadable, no_record)


def reindex(base_dir: Path) -> int:
    """Rebuild the run index (runs.tsv) from the run folders: append a row for
    every completed run that has none (`unindexed`). Never rewrites.

    A row that exists stays untouched. Only runs with both completion
    markers are indexed; a run whose metadata cannot be read (damaged, or
    written before schema 4) is reported, never indexed — exit 2. An index
    with old columns or a run listed twice is refused (`index_refusal`),
    exit 2.
    """
    index = base_dir / RUN_INDEX
    with _index_lock(base_dir):
        header, rows = _read_index(index)
        why = index_refusal(index, header, rows)
        if why is not None:
            console.refuse("runlog", why)
            return 2
        found = unindexed(base_dir, {row[0] for row in rows if row})
        for row in found.rows:
            _append_row(index, row)
    print(f"runlog: {len(found.rows)} row(s) appended to {index}.")
    for name in found.incomplete:
        print(f"  {name}: not completed — nothing to index.")
    for err in found.unreadable:
        print(f"  NOT INDEXED: {err}")
    for name in found.no_record:
        print(f"  {name}: no config.json — no run record, nothing to index.")
    return 2 if found.unreadable else 0
