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

The fingerprint covers exactly the inputs the reader was given — the
report, its discussion blocks, the protocol, each discussed run's
`metrics.json`, the area's audit records with their decisions and failed
attempts — and nothing it was not: not this folder, not the attempt
journal, so writing the record leaves its own state as it was. The
reader's instructions and the standard's rules are labkit's and change
with the version, not with the report.

The release rule (`standing`, pure): a report is released for a protocol
when at least one review that is no `--again` draw saw this very state
(the fingerprint now) and no review of this state named a claim. A claim
holds the state, an `--again` draw's as well; a later clean review of the
same state does not outvote it. The way out is a changed input — the
report, or a source the reader read (a protocol, a decision) — and a
review of that state. Why (eighth
haiku round, 2026-10-26, t18): the review was a hint at the commit, the
agent passed it over, and the discussed run's numbers stayed in the
report as results.

Reading is loud: a file without its table, a kind outside KINDS, a count
that is not the claims' raise ReportReviewError naming the file and the
field. The folder is beside the records, not among them: the readers of
`audits/*.toml` (`findings.area_records`, `reviews.area_reviews`) do not
descend into it.
"""

from __future__ import annotations

import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import findings
from labkit.formats.findings import create_file, written_order
from labkit.formats.protocol_block import toml_string as _s
from labkit.formats.scope_sha import digest

FOLDER = "report-reviews"
#: what a claim says of a report line: a discussed run's number stated as a
#: result, or a statement the audit records contradict
KINDS = ("result", "contradiction")


class ReportReviewError(ValueError):
    """A report review file that cannot be read as such; the message names
    the file and the field."""


@dataclass(frozen=True)
class ReportClaim:
    """One line the reader names: the report's LINE, the KIND (`KINDS`),
    WHY in its sentence."""

    line: int
    kind: str
    why: str


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
    never overwriting). Refuses (ValueError) a claim
    of a kind outside KINDS."""
    for c in claims:
        if c.kind not in KINDS:
            raise ValueError(f"claim kind {c.kind!r} — one of {', '.join(KINDS)}")
    when = time.localtime(now)
    lines = [
        "# written by labkit-audit --report-review — a cold reader's claims on "
        "the report named below, bound to the inputs it read; not edited by hand",
        "[report_review]",
        f"date = {_s(time.strftime('%Y-%m-%dT%H:%M', when))}",
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
        ]
    target = folder(area)
    target.parent.mkdir(exist_ok=True)
    return create_file(
        target,
        time.strftime("%Y-%m-%dT%H-%M", when) + "-review",
        ".toml",
        "\n".join(lines) + "\n",
    )


def read_report_review(path: Path) -> ReportReview:
    """The review at PATH; raises ReportReviewError on anything it cannot
    hold to."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
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
    if row["kind"] not in KINDS:
        raise ReportReviewError(
            f"{path}: claim {i}: kind {row['kind']!r} — one of {', '.join(KINDS)}"
        )
    return ReportClaim(line, row["kind"], row["why"].strip())


def area_report_reviews(area: Path) -> list[ReportReview]:
    """Every report review of AREA, oldest first (`findings.written_order`);
    a file that cannot be read raises."""
    where = folder(area)
    if not where.is_dir():
        return []
    paths = sorted(where.glob("*.toml"), key=written_order)
    return [read_report_review(p) for p in paths]


@dataclass(frozen=True)
class Standing:
    """Where REPORT stands under a protocol: RELEASED or not, the CLAIMS
    reviews of this state named (each with its file), and the newest
    review of an EARLIER state, if any — what changed since is in its
    parts."""

    released: bool
    claims: list[tuple[ReportReview, ReportClaim]]
    on_state: list[ReportReview]
    earlier: ReportReview | None


def standing(
    reviews: list[ReportReview], report: str, protocol: str, whole: str
) -> Standing:
    """The release of REPORT under PROTOCOL in the state whose fingerprint
    is WHOLE, from REVIEWS (oldest first). Released only when a review
    that is no `--again` draw saw this state and no review of this state
    named a claim. Pure."""
    mine = [r for r in reviews if (r.report, r.protocol) == (report, protocol)]
    on_state = [r for r in mine if r.fingerprint == whole]
    claims = [(r, c) for r in on_state for c in r.claims]
    released = not claims and any(not r.again for r in on_state)
    earlier = next((r for r in reversed(mine) if r.fingerprint != whole), None)
    return Standing(released, claims, on_state, earlier)


def changed_parts(earlier: ReportReview, now: dict[str, str]) -> list[str]:
    """The labels of the inputs that differ between EARLIER's parts and
    NOW's — added, removed or changed — in NOW's order, then the removed."""
    out = [k for k, v in now.items() if earlier.parts.get(k) != v]
    return out + [k for k in earlier.parts if k not in now]


def held_by(standing: Standing) -> str:
    """The claims that hold a state, each with its record, line, kind and
    why — what a refusal names so the next step can answer it."""
    return "; ".join(
        f"CLAIM in {r.path.name}, line {c.line} ({c.kind}): {c.why}"
        for r, c in standing.claims
    )
