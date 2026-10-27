"""Write and validate a handover — a protocol's end without a result —,
never an approval of evidence.

Each immutable JSON record in audits/handovers binds one unresolved end:
its protocol without a result, the findings left open or deferred, and
every available audit file by blob id. The report carries the record's
projection as a handover block, one per protocol, beside any other prose
or block:

    <!-- labkit handover
    protocol = "experiments/01-x/PROTOCOL-x.md"
    record = "experiments/01-x/audits/handovers/handover-….json"
    -->
    Unresolved: `experiments/01-x/PROTOCOL-x.md` — no result is reported; …

    - Why: …
    - Tried: …
    - Findings left open or deferred (in `experiments/01-x/audits`): …
    - Evidence and recorded losses: [handover record](<…>)
    <!-- /labkit handover -->

Only the stop/commit's integrity refusal may use this acknowledgement, and
only while the block, the protocol and the audit files match the record
(`acknowledgement`). Normal audits and result release continue to hold
missing evidence. Rationale: docs/notes/2026-10-27-handover-recovery.md.
"""

from __future__ import annotations

import json
import os
import secrets
import tomllib
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from labkit.formats import files, findings, protocol_block, runs, scope_sha
from labkit.formats.comment_blocks import (
    HEAD_END,
    CommentBlockError,
    closer,
    comment_blocks,
    opener,
    write_comment_block,
)
from labkit.formats.repo import (
    PROTOCOL_NAME,
    REPORT_SUFFIX,
    SKIP_DIRS,
    GitError,
    area_protocols,
    blobs_now,
    git_root,
    indexed_blobs,
    indexed_protocols,
    protocol_links,
    state_text,
    under_root,
)

DIRECTORY = "handovers"
SCHEMA = 1

KIND = "handover"
OPEN = opener(KIND)
CLOSE = closer(KIND)
HEAD_KEYS = ("protocol", "record")
#: the decisions a handover lists as left over: nothing settled them
UNSETTLED = ("open", "deferred")


class HandoverError(ValueError):
    """A handover's fields or referenced state do not establish an unresolved end."""


@dataclass(frozen=True)
class Handover:
    """One unresolved end and its exact evidence state; no finding is resolved.
    REMAINING names each finding left open or deferred as `<record file>
    #<n> (<grade>, <status>)`."""

    schema: int
    protocol: str
    protocol_sha: str
    report: str
    why: str
    tried: str
    evidence: dict[str, str]
    expected: list[str]
    remaining: list[str]
    problems: list[str]


def protocol_fingerprint(text: str) -> str:
    """SHA256 of normalized UTF-8 text for the protocol projection."""
    return scope_sha.digest(text.encode("utf-8"), chars=None)


def evidence(
    area: Path, *, staged: bool = False, omit: Path | None = None
) -> dict[str, str]:
    """Audit paths and blob ids in tree/index, including malformed bytes.

    Omit only the handover being validated to avoid self-reference.
    Raise HandoverError outside git, for symbolic-link evidence and when
    git cannot list it (an unmerged or link entry in the index).
    """
    area = area.resolve()
    root = git_root(area)
    if root is None:
        raise HandoverError(f"{area}: handover evidence requires a git repository")
    folder = area / findings.DIR
    try:
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
    except GitError as exc:
        # an unmerged or link entry in the index: a sentence, not a
        # traceback at the commit (audit 2026-10-27, third, K3)
        raise HandoverError(f"{folder}: {exc}") from exc
    return {
        p.relative_to(folder).as_posix(): sha
        for p, sha in sorted(held.items())
        if p != omit
    }


def entry(record: findings.Record, n: int) -> str:
    """Finding N of RECORD as a handover names it: `<record file> #<n>
    (<grade>, <status>)` — never its text, which may cite a run. The one
    spelling `remaining` writes and `handed_over` is matched against."""
    f = record.findings[n - 1]
    return f"{record.path.name} #{n} ({f.grade}, {f.status})"


def remaining(records: Iterable[findings.Record]) -> list[str]:
    """Every finding of RECORDS no decision settled (`UNSETTLED`), by
    record file and number (`entry`)."""
    return [
        entry(r, n)
        for r in records
        for n, f in enumerate(r.findings, 1)
        if f.status in UNSETTLED
    ]


def handed_over(area: Path) -> set[str]:
    """The findings any handover record of AREA in the tree lists as left
    over (`Handover.remaining`, as `entry` spells them) — the binding a
    reader uses to tell a finding handed over unresolved from one set
    aside for later. A handover settles nothing: the findings stay listed.
    Raises HandoverError on a record that does not read."""
    return {
        name for path in record_paths(area) for name in read_handover(path).remaining
    }


def build(
    root: Path,
    protocol: Path,
    protocol_text: str,
    report: Path,
    path: Path,
    *,
    why: str,
    tried: str,
    records: list[findings.Record],
    expected: Iterable[str],
    problems: Iterable[str],
) -> Handover:
    """The record a handover at PATH writes: PROTOCOL as PROTOCOL_TEXT
    will stand (no result), REPORT, WHY and TRIED, the findings RECORDS
    leave unsettled, the area's audit files as the tree holds them now,
    the EXPECTED paths and the PROBLEMS found. Raises HandoverError on a
    field the record cannot hold (`read_handover`)."""
    record = Handover(
        SCHEMA,
        protocol.relative_to(root).as_posix(),
        protocol_fingerprint(protocol_text),
        report.relative_to(root).as_posix(),
        why.strip(),
        tried.strip(),
        evidence(protocol.parent, omit=path),
        sorted(expected),
        remaining(records),
        list(dict.fromkeys(problems)),
    )
    read_handover(path, _json(record))
    return record


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
        _strings(raw["remaining"], "remaining"),
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

    Raise HandoverError rather than write into a protocol or a file in the
    repository's excluded evidence/environment directories.
    """
    report = path.resolve()
    if (
        path.is_symlink()
        or not under_root(root, report)
        or report.suffix != REPORT_SUFFIX
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


@dataclass(frozen=True)
class HandoverBlock:
    """One handover block of a report: the PROTOCOL and the RECORD its head
    names (paths relative to the report, as written), where it stands
    (FIRST the opening line, LAST the closing one, 1-based) and its LINES
    from opening to closing."""

    protocol: str
    record: str
    first: int
    last: int
    lines: list[str]


def _shown(record: Handover, root: Path, path: Path) -> tuple[str, str, str]:
    """(protocol, record file, audits folder) of RECORD kept at PATH, each
    relative to RECORD's report — as its block names them."""
    base = (root / record.report).parent

    def rel(target: Path) -> str:
        return Path(os.path.relpath(target, base)).as_posix()

    return rel(root / record.protocol), rel(path), rel(path.parents[1])


def handover_lines(record: Handover, root: Path, path: Path) -> list[str]:
    """The handover block of RECORD (kept at PATH) as its report shows it:
    the head names protocol and record relative to the report, the body is
    written from the record alone. Raises HandoverError on a path no TOML
    string holds."""
    protocol, link, audits = _shown(record, root, path)
    try:
        head = [
            f"{k} = {protocol_block.toml_string(v)}"
            for k, v in (("protocol", protocol), ("record", link))
        ]
    except ValueError as exc:
        raise HandoverError(f"handover block head: {exc}") from exc
    left = "; ".join(record.remaining) or "none"
    return [
        OPEN,
        *head,
        HEAD_END,
        f"Unresolved: `{protocol}` — no result is reported; its open questions "
        "are handed over for review.",
        "",
        f"- Why: {record.why}",
        f"- Tried: {record.tried}",
        f"- Findings left open or deferred (in `{audits}`): {left}",
        f"- Evidence and recorded losses: [handover record](<{link}>)",
        CLOSE,
    ]


def handover_blocks(text: str) -> list[HandoverBlock]:
    """Every handover block of TEXT in order (`comment_blocks`). Raises
    HandoverError naming the line on a block that does not read: never
    closed, closed without opening, nested, or a head that is not protocol
    and record."""
    try:
        found = comment_blocks(text, KIND, "handover block", check_head=_block_head)
    except CommentBlockError as exc:
        raise HandoverError(str(exc)) from exc
    return [
        HandoverBlock(*_block_head(b.head, b.first), b.first, b.last, b.lines)
        for b in found
    ]


def _block_head(head: list[str], at: int) -> tuple[str, str]:
    """(protocol, record) of the TOML HEAD of the block opened at line AT.
    Raises HandoverError on TOML that does not read or other keys than
    protocol and record, each a string."""
    try:
        data = tomllib.loads("\n".join(head))
    except tomllib.TOMLDecodeError as exc:
        raise HandoverError(
            f"line {at}: the handover block's head is not TOML: {exc}"
        ) from exc
    if sorted(data) != sorted(HEAD_KEYS) or not all(
        isinstance(data[k], str) for k in HEAD_KEYS
    ):
        raise HandoverError(
            f"line {at}: the handover block's head holds protocol and record, "
            "each a string"
        )
    return data["protocol"], data["record"]


def write_handover_block(text: str, record: Handover, root: Path, path: Path) -> str:
    """TEXT with RECORD's handover block: the one block of its protocol
    replaced in place, or one appended at the end; everything else stays
    (`write_comment_block`). Raises HandoverError on a block that does not
    read or on two blocks of the same protocol."""
    protocol = _shown(record, root, path)[0]
    matching = {b.first for b in handover_blocks(text) if b.protocol == protocol}
    try:
        return write_comment_block(
            text,
            handover_lines(record, root, path),
            comment_blocks(text, KIND, "handover block"),
            lambda b: b.first in matching,
            lambda same: (
                f"{protocol} is handed over in {len(same)} blocks (lines "
                f"{', '.join(str(b.first) for b in same)}) — remove all but one, "
                "then write it again"
            ),
        )
    except CommentBlockError as exc:
        raise HandoverError(str(exc)) from exc


def _json(record: Handover) -> str:
    """RECORD as the file holds it."""
    return json.dumps(asdict(record), ensure_ascii=False, indent=2) + "\n"


def write_record(path: Path, record: Handover) -> None:
    """Create PATH atomically; refuse an existing record instead of replacing evidence."""
    if path.exists():
        raise HandoverError(f"{path}: a handover record already exists")
    text = _json(record)
    read_handover(path, text)
    path.parent.mkdir(parents=True, exist_ok=True)
    files.write_atomic(path, text)


def new_path(area: Path) -> Path:
    """A fresh handover filename; it cannot be confused with a run id."""
    return area / findings.DIR / DIRECTORY / f"handover-{secrets.token_hex(12)}.json"


def record_paths(area: Path, *, staged: bool = False) -> list[Path]:
    """Handover records in tree/index; no file content is parsed or changed.
    Raises HandoverError when git cannot list the index."""
    area = area.resolve()
    folder = area / findings.DIR / DIRECTORY
    if staged:
        root = git_root(area)
        if root is None:
            return []
        try:
            held = indexed_blobs(root, folder)
        except GitError as exc:
            raise HandoverError(f"{folder}: {exc}") from exc
        return sorted(p for p in held if p.suffix == ".json")
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
        f"{findings.DIR}/{name}: lost, as a handover recorded — restore it; until "
        "then audits and adoption stay refused (a current handover lets only the "
        "stop and the commit pass)"
        for name in sorted(missing)
    ]


def _protocols(area: Path, root: Path, *, staged: bool) -> list[Path]:
    """AREA's protocols in the tree or, STAGED, the index."""
    if staged:
        return [p for p in indexed_protocols(root) if p.parent == area]
    return area_protocols(area)


def declared_results(area: Path, root: Path, *, staged: bool = False) -> list[Path]:
    """The protocols of AREA, in the tree or STAGED the index, that declare
    a result: none may, while the area is handed over. Raises HandoverError
    on a protocol that does not read or is a symbolic link there
    (`repo.protocol_links`)."""
    protocols = _protocols(area.resolve(), root, staged=staged)
    links = protocol_links(root, protocols, staged=staged)
    if links:
        raise HandoverError(next(iter(links.values())))
    out = []
    for p in protocols:
        try:
            text = state_text(root, p, staged=staged)
            if text is not None and protocol_block.declared_run(text) is not None:
                out.append(p)
        except (UnicodeError, protocol_block.BlockError) as exc:
            raise HandoverError(f"{p}: the protocol does not read: {exc}") from exc
    return out


def _protocol_mismatch(
    area: Path, root: Path, record: Handover, *, staged: bool
) -> str | None:
    """Why RECORD's protocol no longer stands as handed over in the tree
    or, STAGED, the index — not one of AREA's, a symbolic link, changed
    since, or a protocol of the area declaring a result — or None."""
    protocol = root / record.protocol
    if protocol not in _protocols(area, root, staged=staged):
        return (
            f"its protocol {record.protocol} is not a protocol of the area in "
            f"the {_state(staged)}"
        )
    link = protocol_links(root, [protocol], staged=staged)
    if link:
        return link[protocol]
    text = state_text(root, protocol, staged=staged)
    if text is None or protocol_fingerprint(text) != record.protocol_sha:
        return f"{record.protocol} changed since the handover"
    declaring = declared_results(area, root, staged=staged)
    if declaring:
        return f"{declaring[0].relative_to(root).as_posix()} declares a result"
    return None


def mismatch(area: Path, root: Path, path: Path, *, staged: bool) -> str | None:
    """Why the handover record at PATH does not acknowledge AREA as the tree
    or, STAGED, the index holds it — the first condition that fails, one
    sentence — or None when it does: its protocol unchanged since, no
    protocol of the area declaring a result, its block in the report as
    written, the audit files as bound (at the commit also the tree's equal
    to the index's, so unstaged evidence cannot borrow it)."""
    state = _state(staged)
    try:
        record = read_record(root, path, staged=staged)
        changed = _protocol_mismatch(area, root, record, staged=staged)
        if changed:
            return changed
        report = report_destination(root, root / record.report)
        written = state_text(root, report, staged=staged)
        if written is None:
            return f"its report {record.report} is not in the {state}"
        wanted = handover_lines(record, root, path)
        link = _shown(record, root, path)[1]
        found = [b for b in handover_blocks(written) if b.record == link]
        if not found:
            return f"{record.report} holds no handover block of this record"
        if [b.lines for b in found] != [wanted]:
            return (
                f"its block in {record.report} differs from the record — write it "
                "again with protocol-fill --handover (prose outside the block is free)"
            )
        current = evidence(area, staged=staged, omit=path)
        if staged and evidence(area, omit=path) != current:
            return "the tree's audits/ differs from the index's — stage all of it"
        if current != record.evidence:
            return (
                "audits/ changed since the handover (a file added, changed or "
                "removed) — a new handover binds the new state"
            )
    except (
        HandoverError,
        GitError,
        OSError,
        UnicodeError,
        protocol_block.BlockError,
    ) as exc:
        return str(exc)
    return None


@dataclass(frozen=True)
class Acknowledgement:
    """Whether a handover acknowledges an area's integrity gaps (VALID),
    and for each record that does not, why (RECORD file name → sentence)."""

    valid: bool
    refused: dict[str, str]


def acknowledgement(area: Path, *, staged: bool = False) -> Acknowledgement:
    """Whether an exact, current handover permits an unresolved stop/commit
    of AREA (`mismatch` names each condition), and why each other record
    does not. Every protocol in the area must declare no result. Open
    readable findings remain a separate hook obligation."""
    area = area.resolve()
    root = git_root(area)
    if root is None:
        return Acknowledgement(False, {})
    refused: dict[str, str] = {}
    try:
        paths = record_paths(area, staged=staged)
    except HandoverError as exc:
        return Acknowledgement(False, {DIRECTORY: str(exc)})
    for path in paths:
        why = mismatch(area, root, path, staged=staged)
        if why is None:
            return Acknowledgement(True, {})
        refused[path.name] = why
    return Acknowledgement(False, refused)


def valid(area: Path, *, staged: bool = False) -> bool:
    """Whether an exact, current handover permits an unresolved stop/commit
    of AREA (`acknowledgement`)."""
    return acknowledgement(area, staged=staged).valid
