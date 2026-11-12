"""report_reviews — a cold reader's claims on a finished report, as data
bound to what the reader saw.

`labkit-audit AREA --report-review REPORT` (`gates/report_review`) reads a
report that discusses a run of AREA (a discussion block,
`report_blocks.discussions`) against that run's numbers and the area's
audit records, and writes what it found here:

    audits/report-reviews/2026-10-26T11-05-review.toml

    [report_review]
    date = "2026-10-26T11:05"
    model = "opus"
    report = "REPORT.md"                              # relative to the repo
    protocol = "experiments/01-x/PROTOCOL-x.md"       # relative to the repo
    fingerprint = "5e0c…"     # over the parts below (`fingerprint`)
    again = false             # an `--again` draw: its claims count, it releases nothing
    claims = 1

    [report_review.parts]     # one digest per input the reader saw
    "REPORT REPORT.md" = "…"
    DISCUSSED = "…"
    "FILE: experiments/01-x/PROTOCOL-x.md" = "…"
    "FILE: experiments/01-x/runs/<id>/metrics.json" = "…"
    AUDITS = "…"

    [[claim]]
    line = 11
    kind = "result"           # result | contradiction
    why = "…"
    status = "open"           # open | false-positive (`--decide`)
    reason = ""               # the counter-evidence, owed for false-positive

The fingerprint covers exactly the inputs the reader was given — the
report, its discussion blocks, the protocol, each discussed run's
`metrics.json`, the area's audit records with their decisions and failed
attempts — and nothing it was not: not this folder, not the attempt
journal, so writing the record leaves its own state as it was. The
reader's instructions and the standard's rules are labkit's and change
with the version, not with the report.

The release rule (`standing`, pure): a report is released for a protocol
when at least one review that is no `--again` draw saw this very state
(the fingerprint now) and every claim a review of this state named is
decided `false-positive` and upheld by a second reviewer (`upheld`). A
claim holds the state, an `--again` draw's as well; a later clean review
of the same state does not outvote it. Two ways out: a changed input —
the report, or a source the reader read (a protocol, a decision) — and a
review of that state; or, when the reader misread, the decision
`false-positive` with the counter-evidence as its reason
(`write_claim_decision`) and its confirmation. Why: a review that is only
a hint at the commit is passed over, and the discussed run's numbers stay
in the report as results; and a false claim that can only be evaded by
rewording a correct text is never answered.

A claim takes one decision besides `open` (`claim_refusal`): no limit
line makes an unadopted number a result or a contradicted statement
true, and a repair changes the state, which a review of the new state
judges. A decision is bound to its record, the claim's number, the state
the record saw and its own digest (`claim_decision_digest`); the record's
folder is outside the fingerprint, so deciding leaves the judged state as
it was, and a decision is never carried into another state's review.

The confirmation (`labkit-audit AREA --review --record <this file>`,
`gates/claim_review`) is written beside the review it judges:

    audits/report-reviews/2026-10-26T11-40-claim-review.toml

    [claim_review]
    date = "2026-10-26T11:40"
    model = "opus"
    record = "2026-10-26T11-05-review.toml"   # whose decisions were reviewed
    fingerprint = "5e0c…"     # the state the reviewer saw (= the record's)
    again = false             # an `--again` draw: its verdicts count, it releases nothing
    upheld = 0
    rejected = 1
    insufficient = 0

    [[verdict]]
    claim = 1                 # as `--decide` numbers it
    decision_sha = "3c1f…"    # the decision as reviewed (`claim_decision_digest`)
    verdict = "rejected"      # upheld | rejected | insufficient
    why = "…"

Only `upheld` releases, and every draw on one decision counts: once a
review did not uphold a decision as it stands, no later draw releases it.
The way on is a decision with a revised reason — a new digest, which owes
a confirmation of its own; the earlier verdict stays in its file and
`held_by` names it.

Reading is loud: a file without its table, a kind outside CLAIM_KINDS, a count
that is not the claims' raise ReportReviewError naming the file and the
field. A record whose claims carry no `status` — written by labkit
LAST_UNDECIDED_RELEASE or earlier — is not read; its refusal names the move
that keeps it (`SUPERSEDED`, a folder no reader lists). The folder is
beside the records, not among them: the readers of
`audits/*.toml` (`findings.area_records`, `reviews.area_reviews`) do not
descend into it.
"""

from __future__ import annotations

import re
import shlex
import time
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import findings
from labkit.formats.files import write_atomic
from labkit.formats.runs import as_stored, date_minute, name_minute
from labkit.formats.findings import create_file, written_order
from labkit.formats.protocol_block import toml_string as _s
from labkit.formats.digests import digest
from labkit.formats.reviews import UPHELD, VERDICTS

FOLDER = "report-reviews"
#: the mode of a report review's attempts in the area's journal (`attempts`):
#: its ids and answer files carry it (`<minute>-report-review-<hex>`)
ATTEMPT_MODE = "report-review"
#: what a claim says of a report line: a discussed run's number stated as a
#: result, or a statement the audit records contradict
CLAIM_KINDS = ("result", "contradiction")
RESULT, CONTRADICTION = CLAIM_KINDS
#: the statuses a claim takes, of `findings.STATUSES`: undecided, or the
#: reader misread — every other status is refused (`claim_refusal`)
OPEN, FALSE_POSITIVE = "open", "false-positive"
CLAIM_STATUSES = (OPEN, FALSE_POSITIVE)
#: the line that opens a claim's table, for the decision lines' rewrite
CLAIM_HEADER = findings.array_header("claim")
#: the last release that reads a record whose claims carry no decision
LAST_UNDECIDED_RELEASE = "0.112.0"
#: the folder under FOLDER that keeps such a record once moved there
#: (`git mv`); no reader lists it
SUPERSEDED = "superseded"
#: a claim review's file name (`<minute>-claim-review[-n].toml`), beside
#: the reviews whose decisions it judges
CLAIM_REVIEW_NAME = re.compile(r"-claim-review(?:-\d+)?\.toml$")
#: the mode of a claim review's attempts in the area's journal; it names
#: ATTEMPT_MODE, so a handover leaves its lines out as it does the report
#: review's (`handovers.journal_digest`)
CLAIM_ATTEMPT_MODE = f"{ATTEMPT_MODE}-claim"


class ReportReviewError(ValueError):
    """A report review file that cannot be read as such; the message names
    the file and the field."""


class UndecidedFormat(ReportReviewError):
    """A report review whose claims carry no `status`: written before a
    claim could be decided, and no longer read."""


@dataclass(frozen=True)
class ReportClaim:
    """One line the reader names: the report's LINE, the KIND (`CLAIM_KINDS`),
    WHY in its sentence; the person's decision on it, STATUS
    (`CLAIM_STATUSES`) with its REASON."""

    line: int
    kind: str
    why: str
    status: str = OPEN
    reason: str = ""


def claim_refusal(kind: str, status: str) -> str | None:
    """Why STATUS cannot decide a claim of KIND, or None: a claim is never
    a `limitation` — no limit line makes an unadopted number a result
    (`result`) or a contradicted statement true (`contradiction`) — and
    never `fixed` — a repair changes the report or a source, so the record
    no longer covers the state and a review of the new state judges it.
    As `findings.subject_refusal` refuses a limitation on an
    implementation finding. Pure."""
    if status == "fixed":
        return (
            "a claim is not decided `fixed`: a repair changes the report or a "
            "source the reader read, so this record no longer covers the state "
            "— review the repaired state (`labkit-audit <AREA> --report-review "
            "<REPORT>`), which judges the repair"
        )
    if status != "limitation":
        return None
    if kind == RESULT:
        return (
            "a `result` claim is no limitation: the line shows as a result a "
            "number the protocol has not adopted, and no limit line around it "
            "makes it one (LAB-104 A number leaves the area only through its "
            "adoption) — adopt the run, mark the line as not reported, or decide "
            "`false-positive` when the reader misread"
        )
    return (
        "a `contradiction` claim is no limitation: the report states what the "
        "records contradict, and a limit line does not make the statement true "
        "— change the statement or the decision it goes against, or decide "
        "`false-positive` when the reader misread"
    )


def claim_status_problem(kind: str, status: object, reason: str) -> str | None:
    """Why STATUS with REASON cannot stand on a claim of KIND, or None: a
    status outside CLAIM_STATUSES (`claim_refusal`'s sentence where it has
    one), or `false-positive` without its reason. One rule for the writer
    and the reader. Pure."""
    if not isinstance(status, str) or status not in CLAIM_STATUSES:
        refused = claim_refusal(kind, status) if isinstance(status, str) else None
        return refused or f"status {status!r} — one of {', '.join(CLAIM_STATUSES)}"
    if status == FALSE_POSITIVE and not reason.strip():
        return (
            f"status {status!r} owes a reason — the counter-evidence: the line, "
            "the record, the number the reader misread"
        )
    return None


def claim_decision_digest(claim: ReportClaim) -> str:
    """The digest of CLAIM as decided — line, kind, why, status, reason —
    which a claim review binds to (`ClaimVerdict.decision_sha`): a changed
    reason is another decision, and a verdict on the old one says nothing
    about it. As `findings.decision_digest`."""
    fields = [claim.line, claim.kind, claim.why, claim.status, claim.reason]
    return digest(as_stored(fields).encode("utf-8"))


@dataclass(frozen=True)
class ReportReview:
    """One review file: which report, under which protocol, of which state,
    with which claims."""

    path: Path
    date: str
    model: str
    report: str
    protocol: str
    fingerprint: str
    parts: dict[str, str]
    again: bool
    claims: tuple[ReportClaim, ...]


def folder(area: Path) -> Path:
    """`AREA/audits/report-reviews/`."""
    return area / findings.DIR / FOLDER


def fingerprint(parts: list[tuple[str, str]]) -> tuple[str, dict[str, str]]:
    """(the digest of the whole, the digest of each part) of PARTS, each a
    (label, text) the reader was given, in the order given."""
    each = {label: digest(text.encode("utf-8")) for label, text in parts}
    whole = digest("".join(f"{k}\0{v}\n" for k, v in each.items()).encode("utf-8"))
    return whole, each


def write_report_review(
    area: Path,
    *,
    model: str,
    report: str,
    protocol: str,
    whole: str,
    parts: dict[str, str],
    claims: list[ReportClaim],
    again: bool,
    now: float | None = None,
) -> Path:
    """Write the review of REPORT under PROTOCOL (both relative to the
    repo) into `AREA/audits/report-reviews/` and return its path
    (`<minute>-review[-n].toml`, the name `findings.written_order` sorts,
    never overwriting), every claim `open`. Refuses (ValueError) a claim
    of a kind outside CLAIM_KINDS, and one already decided: a review names
    claims, the person decides them (`write_claim_decision`)."""
    for c in claims:
        if c.kind not in CLAIM_KINDS:
            raise ValueError(f"claim kind {c.kind!r} — one of {', '.join(CLAIM_KINDS)}")
        if c.status != OPEN or c.reason:
            raise ValueError(
                f"a review writes its claims open, not {c.status!r} with a reason"
            )
    when = time.localtime(now)
    lines = [
        "# written by labkit-audit --report-review — a cold reader's claims on "
        "the report named below, bound to the inputs it read; not edited by hand",
        "[report_review]",
        f"date = {_s(date_minute(when))}",
        f"model = {_s(model)}",
        f"report = {_s(report)}",
        f"protocol = {_s(protocol)}",
        f"fingerprint = {_s(whole)}",
        f"again = {'true' if again else 'false'}",
        f"claims = {len(claims)}",
        "",
        "[report_review.parts]",
        *(f"{_s(k)} = {_s(v)}" for k, v in parts.items()),
    ]
    for c in claims:
        lines += [
            "",
            "[[claim]]",
            f"line = {c.line}",
            f"kind = {_s(c.kind)}",
            f"why = {_s(c.why)}",
            f"status = {_s(c.status)}",
            f"reason = {_s(c.reason)}",
        ]
    target = folder(area)
    target.parent.mkdir(exist_ok=True)
    return create_file(
        target,
        name_minute(when) + "-review",
        ".toml",
        "\n".join(lines) + "\n",
    )


def read_report_review(path: Path) -> ReportReview:
    """The review at PATH; raises ReportReviewError on anything it cannot
    hold to — UndecidedFormat on a record whose claims carry no decision."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ReportReviewError(f"{path}: not TOML ({exc})") from exc
    return _review_of(path, text)


def _review_of(path: Path, text: str) -> ReportReview:
    """The review TEXT holds, as the file at PATH (`read_report_review`)."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ReportReviewError(f"{path}: not TOML ({exc})") from exc
    table = data.get("report_review")
    if not isinstance(table, dict):
        raise ReportReviewError(f"{path}: no [report_review] table")
    for key in ("date", "model", "report", "protocol", "fingerprint"):
        if not isinstance(table.get(key), str):
            raise ReportReviewError(
                f"{path}: [report_review] {key} is missing or not a string"
            )
    if not isinstance(table.get("again"), bool):
        raise ReportReviewError(f"{path}: [report_review] again is not true or false")
    parts = table.get("parts")
    if not isinstance(parts, dict) or not all(
        isinstance(v, str) for v in parts.values()
    ):
        raise ReportReviewError(
            f"{path}: [report_review.parts] is not a table of digests"
        )
    rows = data.get("claim", [])
    if not isinstance(rows, list):
        raise ReportReviewError(f"{path}: `claim` must be [[claim]] tables")
    claims = tuple(_claim(path, i, row) for i, row in enumerate(rows, start=1))
    if table.get("claims") != len(claims):
        raise ReportReviewError(
            f"{path}: [report_review] claims = {table.get('claims')!r}, and "
            f"{len(claims)} [[claim]] table(s) follow"
        )
    return ReportReview(
        path,
        table["date"],
        table["model"],
        table["report"],
        table["protocol"],
        table["fingerprint"],
        dict(parts),
        table["again"],
        claims,
    )


def _claim(path: Path, i: int, row: object) -> ReportClaim:
    """Claim I of the file at PATH from ROW."""
    if not isinstance(row, dict):
        raise ReportReviewError(f"{path}: claim {i} is not a table")
    line = row.get("line")
    if not isinstance(line, int) or isinstance(line, bool) or line < 1:
        raise ReportReviewError(f"{path}: claim {i}: line is not a line number")
    for key in ("kind", "why"):
        if not isinstance(row.get(key), str):
            raise ReportReviewError(
                f"{path}: claim {i}: {key} is missing or not a string"
            )
    if row["kind"] not in CLAIM_KINDS:
        raise ReportReviewError(
            f"{path}: claim {i}: kind {row['kind']!r} — one of {', '.join(CLAIM_KINDS)}"
        )
    if "status" not in row:
        raise UndecidedFormat(
            f"{path}: claim {i} carries no `status` — a report review written by "
            f"labkit {LAST_UNDECIDED_RELEASE} or earlier is no longer read "
            f"({LAST_UNDECIDED_RELEASE} is the last release that reads it): keep it "
            f"out of the way with `git mv {shlex.quote(str(path))} "
            f"{shlex.quote(str(path.parent / SUPERSEDED / path.name))}` (make the "
            f"folder first), then review the report again — one call"
        )
    reason = row.get("reason")
    if not isinstance(reason, str):
        raise ReportReviewError(f"{path}: claim {i}: reason is missing or not a string")
    problem = claim_status_problem(row["kind"], row["status"], reason)
    if problem:
        raise ReportReviewError(f"{path}: claim {i}: {problem}")
    return ReportClaim(
        line, row["kind"], row["why"].strip(), row["status"], reason.strip()
    )


def is_undecided_format(text: str) -> bool:
    """Is TEXT a report review of the format without decisions — a
    `[report_review]` table and a `[[claim]]` without `status`? The one
    kind of record that may lie in SUPERSEDED in place of where it was
    written (`superseded_name`); a record this labkit reads is none. Pure."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return False
    rows = data.get("claim", [])
    return (
        isinstance(data.get("report_review"), dict)
        and isinstance(rows, list)
        and any(isinstance(row, dict) and "status" not in row for row in rows)
    )


def superseded_name(rel: str) -> str | None:
    """Where REL, a path under an area's audits/, was written when it now
    lies in SUPERSEDED (`report-reviews/superseded/<name>` →
    `report-reviews/<name>`); None for any other path. Pure."""
    parts = rel.split("/")
    if len(parts) == 3 and parts[:2] == [FOLDER, SUPERSEDED]:
        return f"{FOLDER}/{parts[2]}"
    return None


def without_claim_decisions(text: str) -> str | None:
    """TEXT, a report review's, without its claims' decision lines
    (`findings.without_decisions` on `[[claim]]`): what
    `write_claim_decision` keeps byte for byte. None when a claim lacks
    them. Pure."""
    return findings.without_decisions(text, CLAIM_HEADER)


def write_claim_decision(path: Path, n: int, status: str, reason: str) -> ReportReview:
    """Set claim N (1-based) of the review at PATH to STATUS with REASON —
    the decision the person gives, stored, never made: the side effect is
    the file. The lines are found by the record's structure (the N-th
    `[[claim]]` table), every other byte kept; the result is read back and
    the file replaced whole (`files.write_atomic`) only when exactly that
    claim changed. As `findings.write_decision`. Raises ReportReviewError
    — the file untouched — on a record that does not read, a number
    outside it, a status a claim cannot take (`claim_status_problem`), or
    a claim without the status and reason lines the review writes."""
    before = read_report_review(path)
    if not 1 <= n <= len(before.claims):
        raise ReportReviewError(
            f"{path}: no claim {n} — the record holds "
            + (f"claim 1..{len(before.claims)}" if before.claims else "no claim")
        )
    old = before.claims[n - 1]
    problem = claim_status_problem(old.kind, status, reason)
    if problem:
        raise ReportReviewError(f"{path}: claim {n}: {problem}")
    decided = ReportClaim(old.line, old.kind, old.why, status, reason.strip())
    # decoded, not read as text: a CRLF record keeps its line endings
    text = findings.with_decision(
        path.read_bytes().decode("utf-8"), n, status, reason.strip(), CLAIM_HEADER
    )
    if text is None:
        raise ReportReviewError(
            f"{path}: claim {n} has no `status` and `reason` lines as the review "
            f"writes them — the record was changed by hand; restore it or review "
            f"the report again"
        )
    after = _review_of(path, text)
    expected = list(before.claims)
    expected[n - 1] = decided
    if list(after.claims) != expected or _head(after) != _head(before):
        raise ReportReviewError(f"{path}: the decision did not read back as written")
    write_atomic(path, text)
    return after


def _head(r: ReportReview) -> tuple:
    """What a decision must leave as it was besides the claims."""
    return (r.date, r.model, r.report, r.protocol, r.fingerprint, r.parts, r.again)


def area_report_reviews(area: Path) -> list[ReportReview]:
    """Every report review of AREA, oldest first (`findings.written_order`);
    a file that cannot be read raises. The claim reviews beside them are
    `area_claim_reviews`'s, the folder SUPERSEDED nobody's."""
    where = folder(area)
    if not where.is_dir():
        return []
    paths = sorted(
        (p for p in where.glob("*.toml") if not CLAIM_REVIEW_NAME.search(p.name)),
        key=written_order,
    )
    return [read_report_review(p) for p in paths]


@dataclass(frozen=True)
class ClaimVerdict:
    """One reviewed decision: the CLAIM's number in its record, the
    decision as reviewed (`claim_decision_digest`), the VERDICT
    (`reviews.VERDICTS`), the reviewer's sentence."""

    claim: int
    decision_sha: str
    verdict: str
    why: str


@dataclass(frozen=True)
class ClaimReview:
    """One claim-review file: which review's decisions, on which state,
    the verdicts."""

    path: Path
    date: str
    model: str
    record: str  # the report review's file name
    fingerprint: str  # the state the reviewer saw (= the record's)
    again: bool  # an `--again` draw: its verdicts count, it releases nothing
    verdicts: tuple[ClaimVerdict, ...]

    def of(self, n: int) -> ClaimVerdict | None:
        """The verdict on claim N, or None."""
        return next((v for v in self.verdicts if v.claim == n), None)


def verdict_counts(verdicts: Sequence[ClaimVerdict]) -> tuple[int, ...]:
    """(upheld, rejected, insufficient) over VERDICTS."""
    return tuple(sum(1 for v in verdicts if v.verdict == kind) for kind in VERDICTS)


def write_claim_review(
    area: Path,
    *,
    model: str,
    record: str,
    whole: str,
    verdicts: list[ClaimVerdict],
    again: bool,
    now: float | None = None,
) -> Path:
    """Write the review of RECORD's claim decisions, made on the state
    WHOLE, into `AREA/audits/report-reviews/` — AGAIN when the draw was
    asked for with `--again` — and return its path
    (`<minute>-claim-review[-n].toml`, never overwriting). Refuses
    (ValueError) a verdict outside `reviews.VERDICTS`, an empty review and
    a claim reviewed twice."""
    if not verdicts:
        raise ValueError("a claim review without verdicts is not written")
    seen: set[int] = set()
    for v in verdicts:
        if v.verdict not in VERDICTS:
            raise ValueError(f"verdict {v.verdict!r} — one of {', '.join(VERDICTS)}")
        if v.claim in seen:
            raise ValueError(f"claim {v.claim} reviewed twice")
        seen.add(v.claim)
    when = time.localtime(now)
    lines = [
        "# written by labkit-audit --review — a second reviewer's verdicts on the "
        "decided claims of the report review named below; not edited by hand",
        "[claim_review]",
        f"date = {_s(date_minute(when))}",
        f"model = {_s(model)}",
        f"record = {_s(record)}",
        f"fingerprint = {_s(whole)}",
        f"again = {'true' if again else 'false'}",
        *(
            f"{kind} = {count}"
            for kind, count in zip(VERDICTS, verdict_counts(verdicts))
        ),
    ]
    for v in verdicts:
        lines += [
            "",
            "[[verdict]]",
            f"claim = {v.claim}",
            f"decision_sha = {_s(v.decision_sha)}",
            f"verdict = {_s(v.verdict)}",
            f"why = {_s(v.why)}",
        ]
    target = folder(area)
    target.parent.mkdir(exist_ok=True)
    return create_file(
        target, name_minute(when) + "-claim-review", ".toml", "\n".join(lines) + "\n"
    )


def read_claim_review(path: Path) -> ClaimReview:
    """The claim review at PATH; raises ReportReviewError on anything it
    cannot hold to."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ReportReviewError(f"{path}: not TOML ({exc})") from exc
    table = data.get("claim_review")
    if not isinstance(table, dict):
        raise ReportReviewError(f"{path}: no [claim_review] table")
    for key in ("date", "model", "record", "fingerprint"):
        if not isinstance(table.get(key), str):
            raise ReportReviewError(
                f"{path}: [claim_review] {key} is missing or not a string"
            )
    if not isinstance(table.get("again"), bool):
        raise ReportReviewError(f"{path}: [claim_review] again is not true or false")
    rows = data.get("verdict", [])
    if not isinstance(rows, list) or not rows:
        raise ReportReviewError(
            f"{path}: `verdict` must be one or more [[verdict]] tables"
        )
    verdicts = tuple(_verdict(path, i, row) for i, row in enumerate(rows, start=1))
    counts = tuple(table.get(kind) for kind in VERDICTS)
    if counts != verdict_counts(verdicts):
        raise ReportReviewError(
            f"{path}: [claim_review] counts {counts} are not the verdicts' "
            f"{verdict_counts(verdicts)} (upheld, rejected, insufficient)"
        )
    return ClaimReview(
        path,
        table["date"],
        table["model"],
        table["record"],
        table["fingerprint"],
        table["again"],
        verdicts,
    )


def _verdict(path: Path, i: int, row: object) -> ClaimVerdict:
    """Verdict I of the claim review at PATH from ROW."""
    if not isinstance(row, dict):
        raise ReportReviewError(f"{path}: verdict {i} is not a table")
    n = row.get("claim")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ReportReviewError(f"{path}: verdict {i}: claim is not a claim number")
    for key in ("decision_sha", "verdict", "why"):
        if not isinstance(row.get(key), str):
            raise ReportReviewError(
                f"{path}: verdict {i}: {key} is missing or not a string"
            )
    if row["verdict"] not in VERDICTS:
        raise ReportReviewError(
            f"{path}: verdict {i}: verdict {row['verdict']!r} — one of "
            f"{', '.join(VERDICTS)}"
        )
    return ClaimVerdict(n, row["decision_sha"], row["verdict"], row["why"].strip())


def area_claim_reviews(area: Path) -> list[ClaimReview]:
    """Every claim review of AREA, oldest first (`findings.written_order`);
    a file that cannot be read raises."""
    where = folder(area)
    if not where.is_dir():
        return []
    paths = sorted(
        (p for p in where.glob("*.toml") if CLAIM_REVIEW_NAME.search(p.name)),
        key=written_order,
    )
    return [read_claim_review(p) for p in paths]


def claim_reviews_on(
    review: ReportReview, claim_reviews: Sequence[ClaimReview]
) -> list[ClaimReview]:
    """The CLAIM_REVIEWS of REVIEW that saw the state it saw — its file
    name and its fingerprint — oldest first."""
    return [
        cr
        for cr in claim_reviews
        if cr.record == review.path.name and cr.fingerprint == review.fingerprint
    ]


def verdicts_on_decision(
    review: ReportReview, n: int, claim_reviews: Sequence[ClaimReview]
) -> list[tuple[ClaimReview, ClaimVerdict]]:
    """Every verdict on claim N of REVIEW as it is decided now — those
    whose `decision_sha` is the claim's digest as it stands
    (`claim_decision_digest`) — each with its claim review, oldest first;
    [] when never reviewed or reviewed as another decision. Every draw on
    one decision counts, not the newest."""
    now = claim_decision_digest(review.claims[n - 1])
    return [
        (cr, v)
        for cr in claim_reviews_on(review, claim_reviews)
        if (v := cr.of(n)) is not None and v.decision_sha == now
    ]


def upheld(review: ReportReview, n: int, claim_reviews: Sequence[ClaimReview]) -> bool:
    """Is claim N of REVIEW decided `false-positive` and that decision
    upheld? Yes only when at least one claim review that is no `--again`
    draw judged the decision as it stands and every review of it said
    `upheld`: `rejected` and `insufficient` do not release, a later draw
    does not outvote them, an `--again` draw's `upheld` releases nothing,
    and a verdict on a decision since changed says nothing. As
    `reviews.upholding`. Pure."""
    if review.claims[n - 1].status != FALSE_POSITIVE:
        return False
    pairs = verdicts_on_decision(review, n, claim_reviews)
    return any(not cr.again for cr, _ in pairs) and all(
        v.verdict == UPHELD for _, v in pairs
    )


def not_upheld(
    review: ReportReview, n: int, claim_reviews: Sequence[ClaimReview]
) -> tuple[ClaimReview, ClaimVerdict] | None:
    """The oldest verdict other than `upheld` on claim N of REVIEW as it is
    decided now, with its claim review, or None. Then another draw on this
    decision settles nothing: the way on is a decision with a revised
    reason (`gates/claim_review` refuses a draw unless asked for one)."""
    return next(
        (
            (cr, v)
            for cr, v in verdicts_on_decision(review, n, claim_reviews)
            if v.verdict != UPHELD
        ),
        None,
    )


def verdict_on_revised_decision(
    review: ReportReview, n: int, claim_reviews: Sequence[ClaimReview]
) -> tuple[ClaimReview, ClaimVerdict] | None:
    """The newest verdict other than `upheld` on claim N of REVIEW at a
    decision that no longer stands (another digest), with its claim
    review, or None: what an earlier reviewer said of the reason since
    revised."""
    now = claim_decision_digest(review.claims[n - 1])
    return next(
        (
            (cr, v)
            for cr in reversed(claim_reviews_on(review, claim_reviews))
            if (v := cr.of(n)) is not None
            and v.decision_sha != now
            and v.verdict != UPHELD
        ),
        None,
    )


def decision_state(
    review: ReportReview, n: int, claim_reviews: Sequence[ClaimReview]
) -> str:
    """Where claim N of REVIEW stands, in words, for a gate's sentence:
    `open`; decided and not yet judged; decided and not upheld, with the
    reviewer's verdict, sentence and file; upheld only by `--again` draws;
    `upheld` — and, while the decision as it stands is not upheld, the
    verdict an earlier reviewer gave a decision since revised
    (`verdict_on_revised_decision`). Pure."""
    claim = review.claims[n - 1]
    if claim.status == OPEN:
        return "open"
    if upheld(review, n, claim_reviews):
        return f"decided {claim.status}, upheld"
    against = not_upheld(review, n, claim_reviews)
    if against is not None:
        cr, v = against
        return (
            f"decided {claim.status}, {v.verdict} by the second reviewer "
            f"({cr.path.name}): {v.why}"
        )
    if verdicts_on_decision(review, n, claim_reviews):
        state = (
            f"decided {claim.status}, upheld only by `--again` draws, which "
            f"release nothing"
        )
    else:
        state = f"decided {claim.status}, not yet judged by a second reviewer"
    was = verdict_on_revised_decision(review, n, claim_reviews)
    if was is None:
        return state
    cr, v = was
    return (
        f"{state}; an earlier decision on it was {v.verdict} ({cr.path.name}): {v.why}"
    )


@dataclass(frozen=True)
class HeldClaim:
    """A claim that holds a state: its REVIEW, its number N there, the
    CLAIM, and where its decision stands (`decision_state`)."""

    review: ReportReview
    n: int
    claim: ReportClaim
    state: str


@dataclass(frozen=True)
class Standing:
    """Where REPORT stands under a protocol: RELEASED or not, the claims
    named on this state that still hold it, HOLDING (every one not decided
    `false-positive` and upheld), the reviews ON_STATE, and the newest
    review of an EARLIER state, if any — what changed since is in its
    parts."""

    released: bool
    holding: list[HeldClaim]
    on_state: list[ReportReview]
    earlier: ReportReview | None


def standing(
    reviews: Sequence[ReportReview],
    report: str,
    protocol: str,
    whole: str,
    claim_reviews: Sequence[ClaimReview],
) -> Standing:
    """The release of REPORT under PROTOCOL in the state whose fingerprint
    is WHOLE, from REVIEWS and CLAIM_REVIEWS (oldest first). Released only
    when a review that is no `--again` draw saw this state and every claim
    a review of this state named — an `--again` draw's included — is
    decided `false-positive` and upheld (`upheld`). Pure."""
    mine = [r for r in reviews if (r.report, r.protocol) == (report, protocol)]
    on_state = [r for r in mine if r.fingerprint == whole]
    holding = [
        HeldClaim(r, n, c, decision_state(r, n, claim_reviews))
        for r in on_state
        for n, c in enumerate(r.claims, start=1)
        if not upheld(r, n, claim_reviews)
    ]
    released = not holding and any(not r.again for r in on_state)
    earlier = next((r for r in reversed(mine) if r.fingerprint != whole), None)
    return Standing(released, holding, on_state, earlier)


def changed_parts(earlier: ReportReview, now: dict[str, str]) -> list[str]:
    """The labels of the inputs that differ between EARLIER's parts and
    NOW's — added, removed or changed — in NOW's order, then the removed."""
    out = [k for k, v in now.items() if earlier.parts.get(k) != v]
    return out + [k for k in earlier.parts if k not in now]


def held_by(standing: Standing) -> str:
    """The claims that hold a state, each with its record, number, line,
    kind, why and where its decision stands — what a refusal names so the
    next step can answer it."""
    return "; ".join(
        f"CLAIM #{h.n} in {h.review.path.name}, line {h.claim.line} "
        f"({h.claim.kind}): {h.claim.why} — {h.state}"
        for h in standing.holding
    )
