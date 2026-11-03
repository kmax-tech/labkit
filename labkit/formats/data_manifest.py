"""data_manifest — a sha256 manifest naming data kept outside git.

A lab keeps large data (an LLM cache, dataset archives) on disk beside the
experiment, ignored by git, and names each file in git by a tracked
`MANIFEST.sha256`: one line per file, `<sha256 hex>  <path>` as `shasum -a
256` writes it (a `*` before the path, binary mode, reads the same), the
path relative to the repository root, so `shasum -a 256 -c <manifest>` run
there checks every file. Blank lines are skipped; any other line is
refused, as is a path listed twice with two digests.

Which manifests hold a source, and what finalize does with them:
`run_record_check.provenance_findings`.
"""

from __future__ import annotations

import re

#: the manifest's file name; finalize reads the ones git tracks in a
#: source's directory and above it
MANIFEST_NAME = "MANIFEST.sha256"

_LINE = re.compile(r"([0-9a-f]{64}) [ *](.+)")


class ManifestError(ValueError):
    """A manifest line that is not `<sha256 hex>  <path>`, or a path
    listed twice with two digests."""


def parse_manifest(text: str, name: str) -> dict[str, str]:
    """TEXT, a manifest's content, as path (relative to the repository
    root, as written) → sha256 hex. Raises ManifestError naming NAME and
    the line number for a line that is not an entry, and for a path
    listed twice with two digests."""
    entries: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        m = _LINE.fullmatch(line)
        if m is None:
            raise ManifestError(
                f"{name}:{number}: not `<sha256 hex>  <path>` as `shasum -a 256` "
                f"writes it: {line[:80]!r}"
            )
        digest, path = m.groups()
        if entries.setdefault(path, digest) != digest:
            raise ManifestError(
                f"{name}:{number}: {path} is listed twice with two digests"
            )
    return entries
