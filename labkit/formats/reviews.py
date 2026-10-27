"""reviews — a second auditor's verdicts on accepted findings, as data.

An accepted finding with the effect `stands` says: the verdicts hold, read
within this limit (`findings.EFFECT_STANDS`). Whether the reason given
bears that out was nobody's question (labkit-paper area 09, fifth haiku
round, 2026-10-22: 28 findings, 15 accepted with no action; t5 accepted
three BLOCKERs and six WARNINGs with `stands`, six of them with the reason
"Finding noted"). `labkit-audit AREA --review` hands every such decision of
one record to a cold reviewer with the finding, the reason, the protocol
(the registered intent and the reported claim), the files the findings
name and what the audit was shown of the run, and writes the verdicts
next to the records:

    audits/2026-10-22T09-40-review.toml

    [review]
    date = "2026-10-22T09:40"
    model = "opus"
    record = "2026-10-22T09-15-analysis.toml"   # whose decisions were reviewed
    scope_sha = "597fafd525d3"   # the code the reviewer read (= the record's)
    shown_sha = "15b62aeeac1f"   # what it was shown of the run (= the record's)
    claim_sha = "0a9c3d7e5b21"   # the claim it judged: the Conclusion (`claim_digest`)
    again = false                # an `--again` draw: its verdicts count, it releases nothing
    upheld = 1
    rejected = 2
    insufficient = 0

    [[decision]]
    finding = 2                      # as `--decide` numbers it
    decision_sha = "3c1f9a0b2d4e"    # the decision as reviewed (`findings.decision_digest`)
    verdict = "rejected"             # upheld | rejected | insufficient
    why = "…"

A review upholds decision N of a record when it names that record, saw
the code and the run the record saw (`scope_sha`, `shown_sha`), judged the
claim the protocol makes now (`claim_sha`: the Conclusion,
`protocol_check.reported_claim` — the Recorded results and Limit lines
are generated from the record and the run and bound through them),
carries a `[[decision]]` for N whose `decision_sha` is the digest of the
finding as it stands now, says `upheld`, and is no `--again` draw — at
least one review on that state must be one (`upholding`). A changed
reason, effect or status makes the review stale, and so does a rewritten
claim — the wording of the claim is what separates upheld from rejected
(replay 2026-10-22: the two upheld decisions were the two whose
Conclusion said no more than what the number is). `rejected` and
`insufficient` never release: the question is whether the reported
claim stands within the limit, and "the context does not show" is not a
yes. Every draw on one state counts: once a review of the decision as
decided and claimed now said anything but `upheld`, no later draw
releases it (`contested`) — the way out is deciding again, with the
evidence in the reason, or limiting the claim; `labkit-audit --review`
refuses another draw on such a state unless asked for one (`--again`):
its verdicts count like any draw's, and it releases nothing — an `upheld`
from `--again` alone never releases a decision, contested or not. Deciding again does not mean closing: once a
review of this record did not uphold a decision on a finding
(`once_not_upheld`), a `dismissed`, `fixed` or `deferred` on it owes an
upholding review of the new decision as well — the reviewer is asked
whether the reason shows the finding inapplicable, the fault gone in the
files as audited, or the task truly somebody else's (sixth haiku round,
2026-10-23, t5: `dismissed` with "insufficient evidence withdrawn" after
`insufficient` released the state; a filled-in reason is not evidence).
What is guaranteed is the release condition; whether the verdict is
right stays the reviewer's judgement, as with every agent audit.
report-check blocks on an accepted BLOCKER's `stands` nobody upheld and
warns on an accepted WARNING's, and grades a closed contested finding the
same way (`report_check.review_findings`; decided 2026-10-22 after the
fifth round's replay, two passes, and the assessment of its fifteen
decisions from their sources, `docs/usability/2026-10-22-decision-review-*.md`).

Reading is loud: a file without its `[review]` table, a verdict outside
VERDICTS, counts that are not the decisions' raise ReviewError naming the
file and the field. `findings.area_records` skips these files by their
name (REVIEW_NAME).
"""

from __future__ import annotations

import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import findings
from labkit.formats.findings import REVIEW_NAME, create_file, written_order
from labkit.formats.protocol_block import toml_string as _s
from labkit.formats.protocol_check import reported_claim
from labkit.formats.runs import as_stored, date_minute, name_minute
from labkit.formats.scope_sha import digest

VERDICTS = ("upheld", "rejected", "insufficient")
UPHELD, REJECTED, INSUFFICIENT = VERDICTS
NOT_REVIEWED = "not reviewed"


class ReviewError(ValueError):
    """A review file that cannot be read as such; the message names file and field."""


def claim_digest(text: str) -> str:
    """The digest of the claim the protocol TEXT makes
    (`protocol_check.reported_claim`): what a review binds to as
    `claim_sha`."""
    return digest(as_stored(reported_claim(text)).encode("utf-8"))


@dataclass(frozen=True)
class Decision:
    """One reviewed decision: the finding's number in its record, the
    decision as reviewed (`findings.decision_digest`), the verdict, the
    reviewer's sentence."""

    finding: int
    decision_sha: str
    verdict: str
    why: str


@dataclass(frozen=True)
class Review:
    """One review file: which record's decisions, what the reviewer saw, the
    verdicts."""

    path: Path
    date: str
    model: str
    record: str  # the findings record's file name
    scope_sha: str
    shown_sha: str
    claim_sha: str  # the claim judged (`claim_digest`: the Conclusion then)
    again: bool  # an `--again` draw: its verdicts count, it releases nothing
    counts: tuple[int, int, int]  # upheld, rejected, insufficient
    decisions: tuple[Decision, ...]

    def of(self, n: int) -> Decision | None:
        """The decision on finding N, or None."""
        return next((d for d in self.decisions if d.finding == n), None)


def counts_of(decisions: list[Decision] | tuple[Decision, ...]) -> tuple[int, int, int]:
    """(upheld, rejected, insufficient) over DECISIONS."""
    return tuple(sum(1 for d in decisions if d.verdict == v) for v in VERDICTS)  # type: ignore[return-value]


def write_review(
    area: Path,
    model: str,
    record: str,
    scope_sha: str,
    shown_sha: str,
    claim_sha: str,
    decisions: list[Decision],
    *,
    again: bool,
    now: float | None = None,
) -> Path:
    """Write the review of RECORD's decisions into AREA/audits/ — AGAIN when
    the draw was asked for with `--again` — and return its path (`<minute>-review[-n].toml`, never overwriting). Refuses
    (ValueError) a verdict outside VERDICTS, an empty review and a finding
    number reviewed twice."""
    if not decisions:
        raise ValueError("a review without decisions is not written")
    seen: set[int] = set()
    for d in decisions:
        if d.verdict not in VERDICTS:
            raise ValueError(f"verdict {d.verdict!r} — one of {', '.join(VERDICTS)}")
        if d.finding in seen:
            raise ValueError(f"finding {d.finding} reviewed twice")
        seen.add(d.finding)
    when = time.localtime(now)
    stamp = name_minute(when)
    u, r, i = counts_of(decisions)
    lines = [
        "# written by labkit-audit --review — a second auditor's verdicts on the "
        "accepted findings of the record named below; not edited by hand",
        "[review]",
        f"date = {_s(date_minute(when))}",
        f"model = {_s(model)}",
        f"record = {_s(record)}",
        f"scope_sha = {_s(scope_sha)}",
        f"shown_sha = {_s(shown_sha)}",
        f"claim_sha = {_s(claim_sha)}",
        f"again = {'true' if again else 'false'}",
        f"upheld = {u}",
        f"rejected = {r}",
        f"insufficient = {i}",
    ]
    for d in decisions:
        lines += [
            "",
            "[[decision]]",
            f"finding = {d.finding}",
            f"decision_sha = {_s(d.decision_sha)}",
            f"verdict = {_s(d.verdict)}",
            f"why = {_s(d.why)}",
        ]
    return create_file(
        area / findings.DIR, f"{stamp}-review", ".toml", "\n".join(lines) + "\n"
    )


def read_review(path: Path) -> Review:
    """The review at PATH; raises ReviewError on anything it cannot hold to."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ReviewError(f"{path}: not TOML ({exc})") from exc
    table = data.get("review")
    if not isinstance(table, dict):
        raise ReviewError(f"{path}: no [review] table")
    for key in ("date", "model", "record", "scope_sha", "shown_sha", "claim_sha"):
        if not isinstance(table.get(key), str):
            raise ReviewError(
                f"{path}: [review] {key} is missing or not a string"
                + (
                    " — a review written before labkit bound the claim is no longer "
                    "read: review again"
                    if key == "claim_sha"
                    else ""
                )
            )
    if not isinstance(table.get("again"), bool):
        raise ReviewError(
            f"{path}: [review] again is missing or not true or false — a review "
            f"written by labkit 0.103.0 or earlier is not read (whether it was an "
            f"`--again` draw is not recorded): review again"
        )
    rows = data.get("decision", [])
    if not isinstance(rows, list) or not rows:
        raise ReviewError(f"{path}: `decision` must be one or more [[decision]] tables")
    decisions = tuple(_decision(path, i, row) for i, row in enumerate(rows, start=1))
    counts = tuple(table.get(v) for v in VERDICTS)
    if counts != counts_of(decisions):
        raise ReviewError(
            f"{path}: [review] counts {counts} are not the decisions' "
            f"{counts_of(decisions)} (upheld, rejected, insufficient)"
        )
    return Review(
        path,
        table["date"],
        table["model"],
        table["record"],
        table["scope_sha"],
        table["shown_sha"],
        table["claim_sha"],
        table["again"],
        counts_of(decisions),
        decisions,
    )


def _decision(path: Path, i: int, row: object) -> Decision:
    if not isinstance(row, dict):
        raise ReviewError(f"{path}: decision {i} is not a table")
    n = row.get("finding")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ReviewError(f"{path}: decision {i}: finding is not a finding number")
    for key in ("decision_sha", "verdict", "why"):
        if not isinstance(row.get(key), str):
            raise ReviewError(f"{path}: decision {i}: {key} is missing or not a string")
    if row["verdict"] not in VERDICTS:
        raise ReviewError(
            f"{path}: decision {i}: verdict {row['verdict']!r} — one of {', '.join(VERDICTS)}"
        )
    return Decision(n, row["decision_sha"], row["verdict"], row["why"].strip())


def area_reviews(area: Path) -> list[Review]:
    """Every review of AREA, oldest first (`findings.written_order`); a file
    that cannot be read raises."""
    folder = area / findings.DIR
    if not folder.is_dir():
        return []
    paths = sorted(
        (p for p in folder.glob("*.toml") if REVIEW_NAME.search(p.name)),
        key=written_order,
    )
    return [read_review(p) for p in paths]


def drawn_on(record: findings.Record, reviews: list[Review]) -> list[Review]:
    """The REVIEWS of RECORD that saw what its auditor saw — its name, its
    code and its run as shown — under whatever claim, oldest first."""
    return [
        r
        for r in reviews
        if r.record == record.path.name
        and r.scope_sha == record.scope_sha
        and r.shown_sha == record.shown_sha
    ]


def reviews_of(
    record: findings.Record, reviews: list[Review], text: str
) -> list[Review]:
    """The REVIEWS of RECORD that saw what its auditor saw (`drawn_on`)
    and judged the claim the protocol TEXT makes now, oldest first."""
    claim = claim_digest(text)
    return [r for r in drawn_on(record, reviews) if r.claim_sha == claim]


def once_not_upheld(
    record: findings.Record, n: int, reviews: list[Review]
) -> Decision | None:
    """The oldest verdict on finding N of RECORD that was not `upheld` —
    from any review that saw the record's code and run (`drawn_on`), at
    whatever decision and under whatever claim it was drawn — or None.
    Such a finding is contested: a decision made on it since owes an
    upholding review of its own (`upholding`), whatever its status —
    `dismissed`, `fixed` or `deferred` close nothing by themselves
    (sixth haiku round, 2026-10-23, t5: after `insufficient` the finding
    was dismissed with "insufficient evidence withdrawn" and the state
    released; `report_check.review_findings` holds it now)."""
    for r in drawn_on(record, reviews):
        d = r.of(n)
        if d is not None and d.verdict != UPHELD:
            return d
    return None


def verdicts_on_state(
    record: findings.Record, n: int, reviews: list[Review], text: str
) -> list[Decision]:
    """Every review's decision on finding N of RECORD as it is decided now,
    under the claim the protocol TEXT makes now — the decisions whose
    `decision_sha` is the digest of the finding as it stands
    (`findings.decision_digest`) — oldest first; [] when never reviewed,
    reviewed as a different decision (a changed reason, effect or status)
    or under another claim. Every draw on one state counts, not the
    newest: a contested decision is settled by deciding again (the reason
    names the evidence, the effect changes, the claim is limited), never
    by another draw (review 2026-10-22: the newest matching review won,
    so an unchanged `rejected` could be re-reviewed until an `upheld`
    came — the borderline baseline decision came back rejected, upheld,
    upheld and insufficient over four draws)."""
    return [d for _, d in _on_state(record, n, reviews, text)]


def _on_state(
    record: findings.Record, n: int, reviews: list[Review], text: str
) -> list[tuple[Review, Decision]]:
    """`verdicts_on_state` with the review each verdict came from."""
    now = findings.decision_digest(record.findings[n - 1])
    out: list[tuple[Review, Decision]] = []
    for r in reviews_of(record, reviews, text):
        d = r.of(n)
        if d is not None and d.decision_sha == now:
            out.append((r, d))
    return out


def upholding(
    record: findings.Record, n: int, reviews: list[Review], text: str
) -> bool:
    """Does the review uphold finding N of RECORD as decided now, under the
    claim TEXT makes now? Yes only when at least one review that is no
    `--again` draw judged this state and every review of it said `upheld`:
    `rejected` and `insufficient` do not release, a later draw does not
    outvote them, an `--again` draw's `upheld` releases nothing, and a
    review of a decision or a claim since changed says nothing."""
    pairs = _on_state(record, n, reviews, text)
    return any(not r.again for r, _ in pairs) and all(
        d.verdict == UPHELD for _, d in pairs
    )


def contested(
    record: findings.Record, n: int, reviews: list[Review], text: str
) -> bool:
    """Has a review of finding N as decided and claimed now said anything
    but `upheld`? Then another draw on this state settles nothing
    (`decision_review` refuses one unless asked for a measurement)."""
    return any(d.verdict != UPHELD for d in verdicts_on_state(record, n, reviews, text))


def state(record: findings.Record, n: int, reviews: list[Review], text: str) -> str:
    """The review state of finding N of RECORD in words, for a gate's
    sentence: `upheld`, `rejected: <why>`, `insufficient: <why>`,
    `contested (<counts>): <the first sentence that did not uphold>` when
    draws on this state disagree, or NOT_REVIEWED (never, or not as
    decided and claimed now) — followed, when a review of the record once
    did not uphold the finding at another decision or claim
    (`once_not_upheld`), by that verdict: a changed Conclusion or decision
    asks for a new review, and the reader still sees what the last one
    said (eighth haiku round, t5: after a Conclusion edit a rejected
    decision showed as plain "not reviewed"). The grade a gate gives it
    does not change."""
    verdicts = verdicts_on_state(record, n, reviews, text)
    if not verdicts:
        was = once_not_upheld(record, n, reviews)
        if was is None:
            return NOT_REVIEWED
        return (
            f"{NOT_REVIEWED} as decided and claimed now; earlier "
            f"{was.verdict}: {was.why}"
        )
    kinds = {d.verdict for d in verdicts}
    if kinds == {UPHELD}:
        if not upholding(record, n, reviews, text):
            return f"{NOT_REVIEWED} — only `--again` draws said upheld, and they release nothing"
        return UPHELD
    first = next(d for d in verdicts if d.verdict != UPHELD)
    if len(kinds) == 1 and len(verdicts) == 1:
        return f"{first.verdict}: {first.why}"
    u, r, i = counts_of(verdicts)
    return (
        f"contested over {len(verdicts)} draws ({u} upheld, {r} rejected, "
        f"{i} insufficient) — another draw settles nothing, deciding again does; "
        f"{first.verdict}: {first.why}"
    )
