"""files — writing a file safely, for every format that writes one.

The formats know their own records (`runs`, `findings`, `promises`); how a
file is put on disk so that no reader sees half of it is one technique
they share, and it lives here rather than with one of them.
"""

from __future__ import annotations

import os
from pathlib import Path


def write_atomic(path: Path, text: str) -> None:
    """Write `text` whole or not at all: a temp file beside `path`, then
    rename — a reader sees the old file or the new one, never half of
    either. Every record file of a run (config, outputs, metrics,
    completion), the lease and a filled protocol write through it; the run
    index is appended under its lock instead. Staged beside the target, not outside its directory
    (CODE-013): the same filesystem is certain there, and every reader asks
    for a record by name or lists directories — a `.config.json.tmp<pid>`
    next to it is never read as one."""
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
