"""protocol_evidence — declare a file the audit reads in full (`[[evidence_file]]`).

    protocol-fill PROTOCOL --evidence-file PATH [--replace-evidence-file]

PATH (relative to the working directory, or absolute) is written as the
audit resolves it: relative to the protocol's directory, lexically — a
`data/` symlink on the way stays as written, as the stamp names it. The
sha256 is computed from the file's bytes, never typed. Before anything is
written, the protocol as it would be is put through the audit's own
checks (`audit_prompt.checked_evidence_files`: a file, unchanged since
its declaration, UTF-8, within the per-file and the total limit over
every declared file), so a declaration this command writes is one the
audit shows. A path already declared is never overwritten silently: with
the same sha256 nothing changes; with another one the call is refused
unless `--replace-evidence-file` names the replacement. Writes no file:
`declare_evidence_file` returns the protocol text, `protocol-fill`
writes it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath

from labkit.formats import digests, protocol_block
from labkit.formats.protocol_block import EvidenceFile, toml_string
from labkit.formats.repo import rel_posix
from labkit.formats.scope_sha import declared_evidence_bytes
from labkit.gates.audit_prompt import CheckedEvidenceFile, checked_evidence_files

#: the header line of one declared evidence file in the TOML block
_EVIDENCE_HEADER = protocol_block.array_header("evidence_file")
#: the digest line inside one `[[evidence_file]]` table
_SHA256_LINE = re.compile(r"^\s*sha256\s*=")


class Outcome(Enum):
    """What `declare_evidence_file` did to the protocol's declarations."""

    ADDED = "added"
    UNCHANGED = "already declared with this sha256"
    REPLACED = "sha256 replaced"


@dataclass(frozen=True)
class Declaration:
    """The result of `declare_evidence_file`: ENTRY the file as declared,
    OUTCOME what changed, PREVIOUS_SHA256 the digest it replaced (None
    unless REPLACED), TEXT the protocol text holding it, CHECKED every
    declared file as the audit would show it, TOTAL_BYTES their bytes
    together — the sum the total limit was held to."""

    entry: EvidenceFile
    outcome: Outcome
    previous_sha256: str | None
    text: str
    checked: tuple[CheckedEvidenceFile, ...]
    total_bytes: int


def declared_path(protocol: Path, given: Path) -> str:
    """GIVEN as an `[[evidence_file]]` path: relative to PROTOCOL's
    directory, `/`-separated, as git names it (`repo.rel_posix`: the
    directory resolved, GIVEN taken as written while it lies below it, so
    a `data/` link on the way stays as written; else its folders resolved,
    its last component never). Raises ValueError when it does not lie below
    that directory, or is that directory."""
    try:
        rel = rel_posix(given, protocol.parent)
    except ValueError as exc:
        raise ValueError(
            f"{given} is not below {protocol.parent} ({exc}) — an evidence file "
            f"is declared relative to the protocol's directory"
        ) from None
    if rel == ".":
        raise ValueError(f"{given} is the protocol's directory, not a file")
    return rel


def declare_evidence_file(
    protocol: Path, text: str, given: Path, *, replace: bool
) -> Declaration:
    """TEXT (the text of PROTOCOL) with the file GIVEN declared in
    `[[evidence_file]]` — its path as `declared_path` writes it, its
    sha256 computed from its bytes now — checked as the audit checks it.

    A new path is appended at the end of the TOML block. A path already
    declared with this sha256 leaves TEXT as it is (UNCHANGED); with
    another sha256 it is refused unless REPLACE, which rewrites only that
    table's `sha256` line (REPLACED). Every outcome, UNCHANGED included,
    is held to the audit's checks over every declared file: one stale or
    oversized other declaration refuses the call.

    Raises:
        ValueError: GIVEN not below PROTOCOL's directory, or not a file; a
            path declared with another sha256 and REPLACE not set; a table
            that does not read back as written.
        AuditError: The protocol as it would be fails the audit's checks
            (`checked_evidence_files`) — a declared file missing, changed,
            not UTF-8, over the per-file limit, or all of them over the
            total limit.
        protocol_block.BlockError: TEXT's block or a table is malformed.
        OSError: A declared file does not read."""
    path = declared_path(protocol, given)
    f = protocol.parent / path
    if not f.is_file():
        raise ValueError(f"{given} is not a file")
    entry = EvidenceFile(path, digests.digest(f.read_bytes(), None))
    declared = protocol_block.evidence_files(text)
    # at most one: `evidence_files` refuses a path declared twice
    same = next(
        (
            i
            for i, e in enumerate(declared)
            if PurePosixPath(e.path) == PurePosixPath(path)
        ),
        None,
    )
    previous: str | None = None
    if same is None:
        new, outcome = with_evidence_table(text, entry), Outcome.ADDED
    elif declared[same].sha256 == entry.sha256:
        new, outcome = text, Outcome.UNCHANGED
    elif not replace:
        raise ValueError(
            f"{path} is declared with sha256 {declared[same].sha256}, the "
            f"file now has {entry.sha256} — nothing written; "
            f"--replace-evidence-file writes the new sha256 when the file as "
            f"it stands is the one the audit is to read"
        )
    else:
        previous = declared[same].sha256
        new, outcome = with_replaced_sha256(text, same, entry), Outcome.REPLACED
    contents = {
        found.file: found.data
        for _, found in declared_evidence_bytes(protocol, new)
        if found is not None
    }
    checked = checked_evidence_files(protocol, new, contents)
    total = sum(
        len(contents[(protocol.parent / e.path).resolve()])
        for e in protocol_block.evidence_files(new)
    )
    return Declaration(entry, outcome, previous, new, checked, total)


def evidence_table(entry: EvidenceFile) -> list[str]:
    """ENTRY as the TOML lines of one `[[evidence_file]]` table."""
    return [
        "[[evidence_file]]",
        f"path = {toml_string(entry.path)}",
        f"sha256 = {toml_string(entry.sha256)}",
    ]


def with_evidence_table(text: str, entry: EvidenceFile) -> str:
    """TEXT with ENTRY's table appended at the end of the TOML block,
    every earlier declaration kept. Raises ValueError without a TOML block,
    and when the declarations do not read back as before plus ENTRY."""
    before = protocol_block.evidence_files(text)
    new = protocol_block.with_tables_at_block_end(text, (), evidence_table(entry))
    if protocol_block.evidence_files(new) != (*before, entry):
        raise ValueError("[[evidence_file]] did not read back as written")
    return new


def with_replaced_sha256(text: str, index: int, entry: EvidenceFile) -> str:
    """TEXT with the `sha256` line of its INDEX-th `[[evidence_file]]`
    table (0-based, the order `protocol_block.evidence_files` reads)
    written as ENTRY's; every other byte stays. Raises ValueError without a
    TOML block, and when the declarations do not read back with only that
    digest changed."""
    before = protocol_block.evidence_files(text)
    span = protocol_block.toml_block_span(text)
    if span is None:
        raise ValueError("no ```toml block — the table is written into the head")
    start, end = span
    lines = text.split("\n")
    headers = [i for i in range(start, end) if _EVIDENCE_HEADER.match(lines[i])]
    if len(headers) != len(before):
        raise ValueError(
            f"{len(before)} evidence file(s) declared, {len(headers)} "
            f"`[[evidence_file]]` header line(s) — write each as its own "
            f"`[[evidence_file]]` table to have its sha256 replaced"
        )
    first = headers[index] + 1
    stop = next(
        (j for j in range(first, end) if protocol_block.TABLE_HEADER.match(lines[j])),
        end,
    )
    digest_lines = [j for j in range(first, stop) if _SHA256_LINE.match(lines[j])]
    if len(digest_lines) != 1:
        raise ValueError(
            f"[[evidence_file]] #{index + 1}: {len(digest_lines)} `sha256 =` "
            f"line(s) — write the digest on one line of its own to have it replaced"
        )
    lines[digest_lines[0]] = f"sha256 = {toml_string(entry.sha256)}"
    new = "\n".join(lines)
    expected = tuple(entry if i == index else e for i, e in enumerate(before))
    if protocol_block.evidence_files(new) != expected:
        raise ValueError("[[evidence_file]] did not read back as written")
    return new
