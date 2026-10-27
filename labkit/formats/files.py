"""files — writing a file safely, for every format that writes one.

The formats know their own records (`runs`, `findings`, `promises`); how a
file is put on disk so that no reader sees half of it is one technique
they share, and it lives here rather than with one of them.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from pathlib import Path


def write_atomic(path: Path, text: str) -> None:
    """Write `text` whole or not at all: a temp file beside `path`, then
    rename — a reader sees the old file or the new one, never half of
    either. Every file a run leaves (config, outputs, metrics, completion,
    failure, the patch of uncommitted changes, raw artefacts, the source
    snapshots through `write_atomic_bytes`), the lease, a filled protocol,
    a protocol `labkit-init` promotes or restamps and the stamp files it
    writes go through it; the run index is appended under its lock
    instead. Staged beside the target, not outside its directory
    (CODE-013): the same filesystem is certain there, and every reader asks
    for a record by name or lists directories — a `.config.json.tmp<pid>`
    next to it is never read as one. An existing file keeps its mode, one
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
