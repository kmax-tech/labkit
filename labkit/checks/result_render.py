"""result_render — the result section as its bound sources render it.

The Recorded results line and the Limit lines are generated. Recorded
results opens with the reportable verdict of every registered promise
(`verdicts`, one derivation for every reader): an admissibility condition
not assessable — an accepted limit names it — or not met leaves every
criterion not assessable, so a criterion's own `True` never reads as a
pass beside it (the repair case, 2026-10-27, K2). The declared run's other
reported keys follow as recorded values — descriptive; the registered
promises' keys stay in `metrics.json`, unchanged, and are not repeated as
values —, then the run id and one note on the limits. Each Limit line comes
from an accepted finding with an effect in the analysis records covering
that run (`audit_binding.covering_analysis`). `protocol-fill --from-run`
writes them, `--render` writes them again, and report-check holds the
protocol to exactly this rendering (`render_gaps`): a generated line that
differs from its sources is a blocker, whatever it says — exact, and
silent on whether a limit is enough (the audit's question). The Summary's
Conclusion and the rest of the prose stay the author's.

    r = result_render.rendering(area, text, run)     # what the text should say
    result_render.render_gaps(text, r)              # [] when it says exactly that
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labkit.checks.audit_binding import AuditError, covering_analysis
from labkit.checks.recheck import LABKIT_KEYS
from labkit.formats import findings, promises, runs
from labkit.formats.protocol_check import (
    RECORDED_RESULTS_LABEL,
    fields,
    recorded_results_field,
)


@dataclass(frozen=True)
class Rendering:
    """What the result section says when it says what its sources say."""

    recorded_results: str  # the Recorded results line's value
    limits: tuple[tuple[str, str], ...]  # (label, value) per limit, in record order


def recorded_results_line(
    metrics: dict, run_id: str, verdict_keys: frozenset[str] = frozenset()
) -> str:
    """`key = value, … (run <id>)` — every reported key and value as the run
    recorded them but the registered promises' keys (VERDICT_KEYS, read as
    `verdicts`), so `recheck.cited` finds each number and the run id."""
    kept = {
        k: v
        for k, v in metrics.items()
        if k not in LABKIT_KEYS and k not in verdict_keys
    }
    body = ", ".join(f"{k} = {v}" for k, v in kept.items())
    return f"{body} (run {run_id})" if body else f"(run {run_id})"


def verdicts(
    block: promises.PromiseTables, metrics: dict, unjudged: dict[str, str]
) -> list[str]:
    """The reportable verdict of every promise of BLOCK, in its order, one
    phrase each, from the run's METRICS read through each promise's key and
    UNJUDGED (an id an accepted limit leaves not assessable → that limit's
    label). Every admissibility condition conditions every criterion (each
    `[A…]` says why its failure voids the verdict): one not assessable or
    not met makes each criterion `not assessable`, with why; a criterion
    otherwise `met` or `missed` as recorded, `not assessable` when a limit
    names it. A key not recorded as true or false gives no verdict and says
    so — intent-check holds that run. A branch reads as recorded. Pure; the
    run's metrics are never changed."""
    blocked = [
        f"{p.id} not assessable ({unjudged[p.id]})"
        if p.id in unjudged
        else f"{p.id} not met"
        for p in block.promises
        if p.kind == "admissibility"
        and (p.id in unjudged or metrics.get(p.key) is False)
    ]
    return [_verdict(p, metrics.get(p.key), unjudged, blocked) for p in block.promises]


def _verdict(
    p: promises.Promise, value: object, unjudged: dict[str, str], blocked: list[str]
) -> str:
    """`verdicts` for one promise P, its recorded VALUE; BLOCKED the
    admissibility conditions that leave a criterion unjudged."""
    if p.kind == "branch":
        return f"{p.id} {value}"
    if p.id in unjudged:
        return f"{p.id} not assessable ({unjudged[p.id]})"
    if p.kind == "criterion" and blocked:
        return f"{p.id} not assessable — {', '.join(blocked)}"
    if value is True:
        return f"{p.id} met"
    if value is False:
        return f"{p.id} {'missed' if p.kind == 'criterion' else 'not met'}"
    return f"{p.id}: no verdict — `{p.key}` not recorded as true or false"


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
        (findings.limit_label(r, n), findings.limit_line(f), f.effect)
        for r in records
        for n, f in r.limits()
        if f.effect
    ]


def rendering(area: Path, text: str, run: Path) -> Rendering:
    """The result section of TEXT as RUN's `metrics.json` and the covering
    records render it. Raises what `runs.read_metrics` raises on a run
    without readable metrics."""
    metrics = runs.read_metrics(runs.metrics_path(run))
    limits = limits_of(area, text, run)
    note = findings.answer_note([(label, effect) for label, _, effect in limits])
    try:
        block = promises.parse_block(text)
    except promises.PromiseError:
        block = None  # the head station names an unreadable block
    if block is None:
        recorded_results = recorded_results_line(metrics, run.name) + note
    else:
        unjudged: dict[str, str] = {}
        for label, _, effect in limits:
            for pid in findings.effect_ids(effect):
                unjudged.setdefault(pid, label)
        said = "; ".join(verdicts(block, metrics, unjudged))
        keys = frozenset(p.key for p in block.promises)
        recorded_results = (
            f"{said} · recorded: {recorded_results_line(metrics, run.name, keys)}{note}"
        )
    return Rendering(
        recorded_results, tuple((label, value) for label, value, _ in limits)
    )


def render_gaps(text: str, expected: Rendering) -> list[str]:
    """Why TEXT's result section is not EXPECTED, one sentence each, or []:
    the Recorded results line missing or differing, a Limit line missing or differing,
    a Limit line no covering record decides, a generated label written more
    than once (every line of a label is held, not the last one). Exact:
    the comparison is equality of the rendered values, no reading of what
    they say."""
    gaps: list[str] = []
    recorded_results = recorded_results_field(text)
    if recorded_results is None:
        gaps.append(
            "the Recorded results line is not written — `protocol-fill <PROTOCOL> --from-run` "
            "writes it from the run"
        )
    elif recorded_results != expected.recorded_results:
        gaps.append(
            "the Recorded results line differs from its rendering (the run's metrics.json and "
            "the records' limits) — `protocol-fill <PROTOCOL> --render` writes it again"
        )
    labels = [f.label.replace("†", "").strip() for f in fields(text)]
    generated = [
        label
        for label in dict.fromkeys(labels)
        if label == RECORDED_RESULTS_LABEL or label.startswith(findings.LIMIT_PREFIX)
    ]
    for label in generated:
        n = labels.count(label)
        if n > 1:
            # a dict of the fields kept the last line only, and a first line
            # saying anything passed beside a correct second one (review
            # 2026-10-22: "no restriction applies" above the record's line)
            gaps.append(
                f'"{label}" is written {n} times — one generated line per label; '
                f"remove the extra line(s) by hand (`--render` rewrites one and "
                f"leaves the others)"
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
