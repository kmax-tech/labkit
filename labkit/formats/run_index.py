"""run_index — the run index of an area, `runs.tsv`: a local view of the
completed runs, one row per run (`RUN_INDEX_COLS`), rebuilt from the run
records by `runlog reindex` and kept out of the repository by the lab
stamp. The one home of its name, its columns, its lock and its reading:
the run's end appends through `append_row` under `index_lock`, every
reader goes through `read_index` (the header as written, every row whole)
and an index that does not read raises `RunIndexError` naming the line —
a short row is never read as no measurement, since the index may be the
only trace of a run whose directory is gone. Who reads it: the area state
(`area_state`, the lost measurements), the run's start (`runlog`).
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import time
from collections.abc import Iterator
from pathlib import Path

from labkit.formats import console
from labkit.formats.runs import as_stored

#: the run index of an area, a local view rebuilt from runs/ (`runlog reindex`)
RUN_INDEX = "runs.tsv"

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

#: how long an append or reindex waits for the index lock before it is
#: called hung
INDEX_LOCK_TIMEOUT_S = 30.0


class RunIndexError(console.Refused, ValueError):
    """A run index that does not read as written (`read_index`): old
    columns or a row without all of them. WHY names the file, the line
    where there is one, and the way out; a command ends on it as runlog's
    refusal (`console.exit_with`), exit 2."""

    def __init__(self, why: str) -> None:
        super().__init__("runlog", why)

    def __str__(self) -> str:
        return self.why


@contextlib.contextmanager
def index_lock(base_dir: Path, shared: bool = False) -> Iterator[None]:
    """Exclusive lock for every change to runs.tsv — append, reindex; SHARED
    for a reading (`read_index_now`), so no reader sees a row half appended.

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
                fcntl.flock(
                    fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB
                )
                break
            except OSError:
                if time.monotonic() - t0 >= INDEX_LOCK_TIMEOUT_S:
                    raise RuntimeError(
                        f"runlog: runs.tsv locked for over {int(INDEX_LOCK_TIMEOUT_S)}s "
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
    for a run's end (`runlog.Run.finish`) and `runlog.reindex`, which each
    built it."""
    return [
        run_id,
        git,
        script,
        as_stored(data),
        as_stored(config),
        as_stored(metrics),
        note,
        protocol_id,
    ]


def append_row(index: Path, row: list[str]) -> None:
    """One row onto the run index, header created if absent. Callers hold
    the index lock — header creation reads the file too."""
    if not index.exists() or index.stat().st_size == 0:
        index.write_text("\t".join(RUN_INDEX_COLS) + "\n", encoding="utf-8")
    with index.open("a", encoding="utf-8") as f:
        f.write("\t".join(c.replace("\t", " ").replace("\n", " ") for c in row) + "\n")


def header_refusal(header: list[str]) -> str | None:
    """Why a run index with HEADER may not be read or appended to, or None:
    columns other than RUN_INDEX_COLS — appended to, an old-format index
    would not error, its columns would shift silently; read, its runs would
    be taken from the wrong column. The sentence `read_index` raises for
    every reader and writer."""
    if not header or header == RUN_INDEX_COLS:
        return None
    return (
        f"{RUN_INDEX} columns {header} don't match this runlog "
        f"({RUN_INDEX_COLS}) — an index written by labkit before 0.21, or a "
        f"damaged first line. "
        "Migrate it with labkit 0.47 (`runlog migrate-index <area>`, which "
        "keeps every row verbatim), then come back; appending without it "
        "would shift columns silently."
    )


def read_index(index: Path) -> tuple[list[str], list[list[str]]]:
    """(header, rows) of the run index INDEX, checked as written: the
    header RUN_INDEX_COLS (`header_refusal`), every row all of its columns;
    blank lines are skipped. The one check its readers (`indexed_runs`) and
    writers (the run's start, `runlog.reindex`) share. ([], []) without a
    file or with an empty one. Raises RunIndexError naming the line. A
    writer holds the lock."""
    if not index.exists():
        return [], []
    lines = index.read_text(encoding="utf-8").splitlines()
    if not lines:
        return [], []
    header = lines[0].split("\t")
    why = header_refusal(header)
    if why is not None:
        raise RunIndexError(why)
    rows: list[list[str]] = []
    for n, line in enumerate(lines[1:], start=2):
        if not line:
            continue
        row = line.split("\t")
        if len(row) != len(RUN_INDEX_COLS):
            # the index may be the only trace of a run whose folder is gone
            # (`indexed_runs`): read short, it would hide a measurement;
            # dropped, the trace is lost
            raise RunIndexError(
                f"{index}:{n}: {len(row)} of {len(RUN_INDEX_COLS)} tab-separated "
                f"columns ({', '.join(RUN_INDEX_COLS)}) — a row cut short or run "
                f"together. Repair the line by hand: run_id and protocol_id say "
                f"which protocol was measured; the other columns may be `{{}}` "
                f"(data, config, metrics) or empty, or copied from runs/<run_id>/ "
                f"where that folder still stands. Never delete a row that names a "
                f"run: it may be the only trace of a run whose folder is gone "
                f"(`runlog reindex` rebuilds rows only for folders that stand)"
            )
        rows.append(row)
    return header, rows


def read_index_now(index: Path) -> tuple[list[str], list[list[str]]]:
    """`read_index` of INDEX under the shared lock, for a reader that holds
    no lock: a row a finishing run appends is read whole or not at all.
    ([], []) without a file, and then no lock file is made."""
    if not index.exists():
        return [], []
    with index_lock(index.parent, shared=True):
        return read_index(index)


def indexed_runs(base_dir: str | Path, protocol_id: str | None = None) -> list[str]:
    """The run ids the area's run index lists for PROTOCOL_ID (every one when
    None), in index order — the runs measured to the end, whether or not
    their directories still stand. Reads under the shared lock
    (`read_index_now`); [] without an index. Raises RunIndexError on an
    index that does not read (`read_index`): a short row is no evidence of
    no measurement."""
    _, rows = read_index_now(Path(base_dir) / RUN_INDEX)
    run_at, pid_at = RUN_INDEX_COLS.index("run_id"), RUN_INDEX_COLS.index("protocol_id")
    return [r[run_at] for r in rows if protocol_id is None or r[pid_at] == protocol_id]


def indexed_bindings(base_dir: str | Path) -> dict[str, str]:
    """Run id → protocol id ("" for a run recorded unbound) of every run the
    area's run index lists, in index order — what the area state reads the
    index for: the runs only the index knows (`area_state.AreaState.lost`).
    Reads under the shared lock; {} without an index. Raises RunIndexError
    on an index that does not read, as `indexed_runs`."""
    _, rows = read_index_now(Path(base_dir) / RUN_INDEX)
    run_at, pid_at = RUN_INDEX_COLS.index("run_id"), RUN_INDEX_COLS.index("protocol_id")
    return {r[run_at]: r[pid_at] for r in rows}


def index_refusal(index: Path, rows: list[list[str]]) -> str | None:
    """Why the run index INDEX (its ROWS, as `read_index` checked them)
    may not be appended to, or None: a run id listed more than once."""
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
