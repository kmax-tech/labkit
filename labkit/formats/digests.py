"""digests — the one sha256 of labkit: of bytes that are not a file
(`digest`), of a file (`file_digest`) and over named contents
(`tree_digest`), the shape of every stamp. Pure; below every format that
stamps, so a stamp's reader and its writer share it without importing
each other (`scope_sha` stamps the area, `promises` a promise's scope).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path


DIGEST_CHARS = 12  # enough to spot a mismatch, short enough for a protocol line


def digest(data: bytes, chars: int | None = DIGEST_CHARS) -> str:
    """sha256 of DATA, cut to CHARS (None: full) — the one digest of bytes
    that are not a file: a promise block's canonical JSON, a lease
    endpoint's canonical URL."""
    h = hashlib.sha256(data).hexdigest()
    return h if chars is None else h[:chars]


def file_bytes(path: Path) -> bytes:
    """The bytes of the file at PATH — the one reader a check calls when it
    shows a dependency's content beside its digest. Raises OSError."""
    return path.read_bytes()


def file_digest(path: Path) -> str:
    """sha256 of a file's bytes, full hex, read in chunks. The one file
    digest: the stamp, the run record, the hooks and recheck read it; a
    caller that records a prefix cuts it itself, so the recorded width
    stays where the format is."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_digest(
    entries: Iterable[tuple[str, bytes]],
    trailer: Iterable[str] = (),
    chars: int | None = DIGEST_CHARS,
) -> str:
    """One digest over named contents: per entry its name and the sha256 of
    its bytes, one line each, then the trailer lines — so adding, dropping,
    renaming or editing an entry moves it. The caller orders the entries
    (sorted, for a stamp). `chars=None` keeps the full hex. The shape of the
    area stamp, a promise's declared scope, a run's directory source and the
    usability probe's scaffold sha."""
    h = hashlib.sha256()
    for name, content in entries:
        h.update(name.encode("utf-8") + b"\n")
        h.update(hashlib.sha256(content).hexdigest().encode() + b"\n")
    for line in trailer:
        h.update(line.encode("utf-8") + b"\n")
    digest = h.hexdigest()
    return digest if chars is None else digest[:chars]
