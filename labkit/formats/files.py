"""files — writing a file safely, for every format that writes one.

The formats know their own records (`runs`, `findings`, `promises`); how a
file is put on disk so that no reader sees half of it is one technique
they share, and it lives here rather than with one of them — as does
asking whether a file's `flock` is held (`lock_held`: a detached start,
an output lock).
"""

from __future__ import annotations

import fcntl
import os
import stat
import threading
from collections.abc import Callable
from pathlib import Path

#: why a reader could not give its file, carried with the error so that the
#: check that called it decides what it means for its question
#: (docs/notes/2026-11-09-check-outcomes.md): the file is not there; it is
#: there and cannot be opened (a permission, a directory in its place); it
#: was read and is not what its writer gives (not UTF-8, not JSON, not
#: Python, not the shape)
MISSING = "missing"
ACCESS = "access"
MALFORMED = "malformed"
READ_CAUSES = (MISSING, ACCESS, MALFORMED)


class ReadError(ValueError):
    """A file a reader could not give, and why: CAUSE, one of READ_CAUSES,
    MALFORMED by default — every shape error is one. The readers' own errors
    derive from it (`runs.ArtefactError`, `scope_sha.SourceError`)."""

    def __init__(self, message: str, *, cause: str = MALFORMED) -> None:
        if cause not in READ_CAUSES:
            raise ValueError(f"a read cause is one of {READ_CAUSES}, not {cause!r}")
        super().__init__(message)
        self.cause = cause


def read_cause(exc: BaseException) -> str:
    """The cause of a failed read EXC: a ReadError's own, MISSING for
    FileNotFoundError, ACCESS for any other OSError, MALFORMED for anything
    else (a decode, a parse, a shape)."""
    if isinstance(exc, ReadError):
        return exc.cause
    if isinstance(exc, FileNotFoundError):
        return MISSING
    if isinstance(exc, OSError):
        return ACCESS
    return MALFORMED


def write_atomic(path: Path, text: str) -> None:
    """Write `text` whole or not at all: a temp file beside `path`, then
    rename — a reader sees the old file or the new one, never half of
    either. Every file a run leaves (config, outputs, metrics, completion,
    failure, the patch of uncommitted changes, raw artefacts, the source
    snapshots through `write_atomic_bytes`), the lease, a filled protocol,
    a protocol `labkit-init` promotes or restamps and the stamp files it
    writes go through it; the run index is appended under its lock
    instead. Staged beside the target, not outside its directory
    (CODE-013 Publish state atomically): the same filesystem is certain
    there, and every reader asks for a record by name or lists directories
    — a `.config.json.tmp<pid>` next to it is never read as one. An existing file keeps its mode, one
    not writable is refused as a write in place would be (PermissionError),
    and a failed write leaves no temp file. A symlink at `path` is replaced
    by the file, not written through."""
    _replace(path, lambda tmp: tmp.write_text(text, encoding="utf-8"))


def write_atomic_bytes(path: Path, data: bytes) -> None:
    """`write_atomic` for bytes — the source snapshots a run keeps
    (`provenance`), copied as they are, not decoded."""
    _replace(path, lambda tmp: tmp.write_bytes(data))


def write_all(texts: dict[Path, str]) -> None:
    """Write every file of TEXTS (path to text) as `write_atomic` does, and
    none when one cannot be staged: all temp files are written first, then
    renamed in turn. A failed stage removes the staged ones, every target
    as it was; a rename failing after the first leaves the files renamed
    before it new (renames beside their targets do not fail but for a
    vanished directory or a changed permission)."""
    staged: list[tuple[Path, Path]] = []
    try:
        for path, text in texts.items():
            staged.append(
                (
                    _stage(
                        path, lambda tmp, t=text: tmp.write_text(t, encoding="utf-8")
                    ),
                    path,
                )
            )
    except BaseException:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)
        raise
    for tmp, path in staged:
        os.replace(tmp, path)


def _replace(path: Path, write: Callable[[Path], object]) -> None:
    """Stage PATH through WRITE (`_stage`) and rename the temp file over it."""
    os.replace(_stage(path, write), path)


def _stage(path: Path, write: Callable[[Path], object]) -> Path:
    """The temp file beside PATH, written by WRITE and given PATH's mode
    when PATH exists; removed again when a step fails. PermissionError,
    nothing written, when PATH exists and is not writable."""
    mode = None
    if path.exists():
        if not os.access(path, os.W_OK):
            raise PermissionError(f"{path}: not writable — nothing written")
        mode = stat.S_IMODE(path.stat().st_mode)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    try:
        write(tmp)
        if mode is not None:
            os.chmod(tmp, mode)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp


def write_once(path: Path, text: str) -> bool:
    """Write TEXT to PATH whole, unless PATH exists: True when this call
    wrote it, False when another writer was first — that file stays as it
    is. A temp file beside PATH, named for this process and thread, is
    hard-linked to PATH (the link fails when PATH exists) and removed
    again; a reader sees no file or the whole one. The record a cache
    keeps per key goes through it (`llm_cache`): the first answer under a
    key is the one every later read gets."""
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}-{threading.get_ident()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.link(tmp, path)
    except FileExistsError:
        return False
    finally:
        tmp.unlink(missing_ok=True)
    return True


def lock_held(path: Path) -> bool:
    """Is the `fcntl.flock` lock on PATH held, by any process? A shared,
    non-blocking probe, so two readers never see each other as the holder;
    the kernel releases a holder's lock when its last descriptor closes,
    a killed process included — never a pid, which the system reuses.
    Raises FileNotFoundError when PATH is gone."""
    with path.open("rb") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
        return False
