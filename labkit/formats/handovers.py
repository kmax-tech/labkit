"""Write and validate a terminal handover, never an approval of evidence.

Each immutable JSON record in audits/handovers binds one unresolved report,
its protocol without a result, and every available audit file by blob id.
Only the stop/commit's integrity refusal may use this acknowledgement.
Normal audits and result release continue to hold missing evidence.
Rationale: docs/notes/2026-10-27-handover-recovery.md.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from labkit.formats import files, findings, protocol_block, runs, scope_sha
from labkit.formats.repo import (
    area_protocols,
    blobs_now,
    git_root,
    indexed_blobs,
    indexed_protocols,
    state_text,
    under_root,
)

DIRECTORY = "handovers"
SCHEMA = 1


class HandoverError(ValueError):
    """A handover's fields or referenced state do not establish an unresolved end."""


@dataclass(frozen=True)
class Handover:
    """One unresolved end and its exact evidence state; no finding is resolved."""

    schema: int
    protocol: str
    protocol_sha: str
    report: str
    why: str
    tried: str
    evidence: dict[str, str]
    expected: list[str]
    problems: list[str]


def protocol_fingerprint(text: str) -> str:
    """SHA256 of normalized UTF-8 text for the protocol projection."""
    return scope_sha.digest(text.encode("utf-8"), chars=None)


def evidence(
    area: Path, *, staged: bool = False, omit: Path | None = None
) -> dict[str, str]:
    """Audit paths and blob ids in tree/index, including malformed bytes.

    Omit only the handover being validated to avoid self-reference.
    Raise HandoverError outside git or for symbolic-link evidence.
    """
    area = area.resolve()
    root = git_root(area)
    if root is None:
        raise HandoverError(f"{area}: handover evidence requires a git repository")
    folder = area / findings.DIR
    if staged:
        held = indexed_blobs(root, folder)
    else:
        all_paths = list(folder.rglob("*"))
        paths = [p for p in all_paths if p.is_file()]
        if any(p.is_symlink() for p in [folder, *all_paths]):
            raise HandoverError(
                f"{folder}: handover evidence must not be symbolic links"
            )
        held = blobs_now(root, paths)
    return {
        p.relative_to(folder).as_posix(): sha
        for p, sha in sorted(held.items())
        if p != omit
    }


def _relative(value: object, field: str) -> str:
    """Validate a nonempty normalized relative path, raising HandoverError."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise HandoverError(f"handover {field}: a relative path is required")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise HandoverError(f"handover {field}: {value!r} is not a safe relative path")
    return value


def read_handover(path: Path, text: str | None = None) -> Handover:
    """Read a strict handover record; raise HandoverError on malformed data."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8") if text is None else text)
    except (ValueError, UnicodeError) as exc:
        raise HandoverError(f"{path}: handover is not UTF-8 JSON: {exc}") from exc
    keys = set(Handover.__dataclass_fields__)
    if (
        not isinstance(raw, dict)
        or set(raw) != keys
        or type(raw.get("schema")) is not int
        or raw["schema"] != SCHEMA
    ):
        raise HandoverError(f"{path}: handover fields must match schema {SCHEMA}")
    return Handover(
        SCHEMA,
        _relative(raw["protocol"], "protocol"),
        _string(raw["protocol_sha"], "protocol_sha"),
        _relative(raw["report"], "report"),
        _message(raw["why"], "why"),
        _message(raw["tried"], "tried"),
        _evidence_table(raw["evidence"]),
        [
            _relative(v, "expected evidence")
            for v in _strings(raw["expected"], "expected")
        ],
        _strings(raw["problems"], "problems"),
    )


def read_record(root: Path, path: Path, *, staged: bool = False) -> Handover:
    """The handover record at PATH as the tree or, STAGED, the index holds
    it. Raises HandoverError naming PATH when it is absent there, not UTF-8
    or not a record."""
    try:
        text = state_text(root, path, staged=staged)
    except UnicodeError as exc:
        raise HandoverError(f"{path}: handover is not UTF-8 JSON: {exc}") from exc
    if text is None:
        raise HandoverError(f"{path}: no handover record in the {_state(staged)}")
    return read_handover(path, text)


def _state(staged: bool) -> str:
    """The state a check reads, as its sentences name it."""
    return "index" if staged else "tree"


def _string(value: object, field: str) -> str:
    """A nonempty handover string, or HandoverError naming FIELD."""
    if not isinstance(value, str) or not value.strip():
        raise HandoverError(f"handover {field} must be a nonempty string")
    return value


def _message(value: object, field: str) -> str:
    """A reportable one-line explanation that cites no run as a result."""
    text = _string(value, field)
    if "\n" in text or "\r" in text or runs.RUN_ID_LIKE.search(text):
        raise HandoverError(
            f"handover {field}: use one line naming the protocol, not run ids"
        )
    return text


def _strings(value: object, field: str) -> list[str]:
    """A list of explicit strings, or HandoverError naming FIELD."""
    if not isinstance(value, list):
        raise HandoverError(f"handover {field} must be a list of strings")
    return [_string(v, field) for v in value]


def _evidence_table(value: object) -> dict[str, str]:
    """A checked mapping of relative evidence paths to blob ids."""
    if not isinstance(value, dict):
        raise HandoverError("handover evidence must map paths to blob ids")
    return {
        _relative(k, "evidence path"): _string(v, "blob id") for k, v in value.items()
    }


def report_destination(root: Path, path: Path) -> Path:
    """A regular Markdown report inside ROOT, never an evidence file.

    Raise HandoverError rather than overwrite protocols or files in the
    repository's excluded evidence/environment directories.
    """
    from labkit.formats.repo import PROTOCOL_NAME, SKIP_DIRS

    report = path.resolve()
    if (
        path.is_symlink()
        or not under_root(root, report)
        or report.suffix.lower() != ".md"
    ):
        raise HandoverError(
            "handover report must be a regular Markdown file inside the repository"
        )
    protected = SKIP_DIRS | {findings.DIR}
    if protected & set(report.relative_to(root).parts) or PROTOCOL_NAME.match(
        report.name
    ):
        raise HandoverError("handover report must not replace a protocol or evidence")
    return report


def report_text(record: Handover, root: Path, path: Path) -> str:
    """Render the unresolved report; raw evidence details stay in the linked record."""
    report = root / record.report
    protocol = Path(os.path.relpath(root / record.protocol, report.parent)).as_posix()
    link = Path(os.path.relpath(path, report.parent)).as_posix()
    return (
        f"# Unresolved experiment\n\nProtocol: `{protocol}`.\n\n"
        f"Reason: {record.why}\n\nTried: {record.tried}\n\n"
        f"Evidence and recorded losses: [handover record](<{link}>).\n\n"
        "No result is reported. Open questions are handed over for review.\n"
    )


def write_record(path: Path, record: Handover) -> None:
    """Create PATH atomically; refuse an existing record instead of replacing evidence."""
    if path.exists():
        raise HandoverError(f"{path}: a handover record already exists")
    text = json.dumps(asdict(record), ensure_ascii=False, indent=2) + "\n"
    read_handover(path, text)
    path.parent.mkdir(parents=True, exist_ok=True)
    files.write_atomic(path, text)


def new_path(area: Path) -> Path:
    """A fresh handover filename; it cannot be confused with a run id."""
    return area / findings.DIR / DIRECTORY / f"handover-{secrets.token_hex(12)}.json"


def record_paths(area: Path, *, staged: bool = False) -> list[Path]:
    """Handover records in tree/index; no file content is parsed or changed."""
    area = area.resolve()
    folder = area / findings.DIR / DIRECTORY
    if staged:
        root = git_root(area)
        if root is None:
            return []
        return sorted(p for p in indexed_blobs(root, folder) if p.suffix == ".json")
    return sorted(folder.glob("*.json"))


def missing_evidence(
    area: Path, present: set[str], *, staged: bool = False
) -> list[str]:
    """Losses acknowledged by retained handovers still block normal audits.

    This preserves a lost committed path even after the handover commit
    itself becomes HEAD. Restoring the original evidence removes the gap.
    Malformed handover records raise HandoverError instead of hiding loss.
    """
    area = area.resolve()
    root = git_root(area)
    missing: set[str] = set()
    for path in record_paths(area, staged=staged):
        record = read_record(root, path, staged=staged) if root else read_handover(path)
        missing.update(set(record.expected) - present)
    return [
        f"{findings.DIR}/{name}: recorded evidence loss — restore it or hand over unresolved"
        for name in sorted(missing)
    ]


def valid(area: Path, *, staged: bool = False) -> bool:
    """Whether an exact, current handover permits an unresolved stop/commit.

    Every protocol in the area must declare no result. The chosen protocol,
    the complete audit snapshot and generated report must match the same
    state. Open readable findings remain a separate hook obligation.
    Invalid candidates give no permission; normal checks report the errors.
    """
    area = area.resolve()
    root = git_root(area)
    if root is None:
        return False
    protocols = (
        [p for p in indexed_protocols(root) if p.parent == area]
        if staged
        else area_protocols(area)
    )
    for path in record_paths(area, staged=staged):
        try:
            record = read_record(root, path, staged=staged)
            protocol = root / record.protocol
            report = report_destination(root, root / record.report)
            if protocol not in protocols or protocol.is_symlink():
                continue
            protocol_text = state_text(root, protocol, staged=staged)
            report_value = state_text(root, report, staged=staged)
            if (
                protocol_text is None
                or protocol_fingerprint(protocol_text) != record.protocol_sha
            ):
                continue
            texts = [state_text(root, p, staged=staged) for p in protocols]
            if any(
                t is None or protocol_block.declared_run(t) is not None for t in texts
            ):
                continue
            if report_value != report_text(record, root, path):
                continue
            current = evidence(area, staged=staged, omit=path)
            if staged and evidence(area, omit=path) != current:
                continue  # a commit must not leave new or changed audit evidence behind
            if current == record.evidence:
                return True
        except (HandoverError, OSError, UnicodeError, protocol_block.BlockError):
            continue
    return False
