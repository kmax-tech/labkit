"""result_render — the result section as its bound sources render it.

The Answer line and the Limit lines are generated, never written by hand:
the Answer from the declared run's `metrics.json` (every reported key and
value as recorded, the run id, one note on the limits), each Limit line
from an accepted finding with an effect in the analysis records covering
that run (`audit_binding.covering_analysis`). `protocol-fill --from-run`
writes them, `--render` writes them again, and report-check holds the
protocol to exactly this rendering (`render_gaps`): a generated line that
differs from its sources is a blocker, whatever it says — exact, and
silent on whether a limit is enough (the audit's question). The Result
sentence and the rest of the prose stay the author's. Phase 5 of the 1.0
line (2026-10-21); until 0.101.0 report-check read the Limit lines and the
Answer's note with patterns, and the writers lived in the tool.

    r = result_render.rendering(area, text, run)     # what the text should say
    result_render.render_gaps(text, r)              # [] when it says exactly that
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labkit.checks.audit_binding import AuditError, covering_analysis
from labkit.checks.recheck import LABKIT_KEYS
from labkit.formats import findings, runs
from labkit.formats.protocol_check import answer_field, fields

#: the Answer line's label, as the template writes it
ANSWER_LABEL = "Answer to the question"


@dataclass(frozen=True)
class Rendering:
    """What the result section says when it says what its sources say."""

    answer: str  # the Answer line's value
    limits: tuple[tuple[str, str], ...]  # (label, value) per limit, in record order


def answer_line(metrics: dict, run_id: str) -> str:
    """`key = value, … (run <id>)` — every reported key and value as the run
    recorded them, so `recheck.cited` finds each number and the run id."""
    kept = {k: v for k, v in metrics.items() if k not in LABKIT_KEYS}
    body = ", ".join(f"{k} = {v}" for k, v in kept.items())
    return f"{body} (run {run_id})"


def limits_of(area: Path, text: str, run: Path) -> list[tuple[str, str, str]]:
    """(label, value, effect) of every limit with its effect decided — an
    accepted BLOCKER, an accepted WARNING that names one — in the analysis
    records covering RUN. An area the gate cannot hold to that run gives
    none here: report-check names why (`analysis_audit_gap`)."""
    try:
        records = covering_analysis(area, text, run)
    except (AuditError, FileNotFoundError, ValueError):
        return []
    return [
        (findings.limit_label(r, n), findings.limit_line(r, n, f), f.effect)
        for r in records
        for n, f in r.limits()
        if f.effect
    ]


def rendering(area: Path, text: str, run: Path) -> Rendering:
    """The result section of TEXT as RUN's `metrics.json` and the covering
    records render it. Raises what `runs.read_metrics` raises on a run
    without readable metrics."""
    metrics = runs.read_metrics(run / "metrics.json")
    limits = limits_of(area, text, run)
    answer = answer_line(metrics, run.name) + findings.answer_note(
        [(label, effect) for label, _, effect in limits]
    )
    return Rendering(answer, tuple((label, value) for label, value, _ in limits))


def render_gaps(text: str, expected: Rendering) -> list[str]:
    """Why TEXT's result section is not EXPECTED, one sentence each, or []:
    the Answer line missing or differing, a Limit line missing or differing,
    a Limit line no covering record decides. Exact: the comparison is
    equality of the rendered values, no reading of what they say."""
    gaps: list[str] = []
    answer = answer_field(text)
    if answer is None:
        gaps.append(
            "the Answer line is not written — `protocol-fill <PROTOCOL> --from-run` "
            "writes it from the run"
        )
    elif answer != expected.answer:
        gaps.append(
            "the Answer line differs from its rendering (the run's metrics.json and "
            "the records' limits) — `protocol-fill <PROTOCOL> --render` writes it again"
        )
    have = {f.label.replace("†", "").strip(): f.value for f in fields(text)}
    for label, value in expected.limits:
        got = have.get(label)
        if got is None:
            gaps.append(
                f'no "{label}" line — the accepted finding\'s limit belongs in the '
                f"protocol; `protocol-fill <PROTOCOL> --render` writes it from the record"
            )
        elif got != value:
            gaps.append(
                f'"{label}" differs from the record — `protocol-fill <PROTOCOL> '
                f"--render` writes the record's line"
            )
    expected_labels = {label for label, _ in expected.limits}
    for label in have:
        if label.startswith(findings.LIMIT_PREFIX) and label not in expected_labels:
            gaps.append(
                f'"{label}" names a limit no covering record decides — written by '
                f"hand or from an older record; `protocol-fill <PROTOCOL> --render` "
                f"drops it"
            )
    return gaps
