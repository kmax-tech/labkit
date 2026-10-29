"""reference — a computation's kept number held to a stated value.

    ref = protocol_block.reference(text)                 # None: a pure computation
    metrics = reference.with_verdict(evaluate_rows(…), ref)   # the compute skeleton, and its --check
    reference.phrase(metrics, ref)                       # "reference 0.62 ± 0.01 (within): not met, distance 0.145"
    reference.comparison_gaps(ref, metrics)              # finalize's blockers, as data

The one home of the verdict (`reference_verdict`): the compute skeleton
writes it to the run's metrics after `evaluate_rows`, `02_analyze.py
--check` recomputes it from the kept rows, `result_render` renders it
into the Recorded results line, and finalize holds the run to it. A
reference is registered in the head (`[reference]`,
docs/notes/2026-10-29-reference-comparison.md) and compared by the run:
the verdict is generated, never typed, like every other number
(LAB-041 Generate numbers, don't retype them).

Three states, each its own: no `[reference]` — no `ref_*` key is written
and nothing is owed; `compared` — `ref_met` true or false, a miss is a
valid outcome with the distance; `not comparable` — the registered key is
absent from the metrics or no finite number, a blocker, and no "met" can
be rendered. Pure: nothing here reads or writes a file.
"""

from __future__ import annotations

from labkit.formats.gate import GateFinding, blocker
from labkit.formats.protocol_block import (
    AT_LEAST,
    AT_MOST,
    WITHIN,
    Reference,
    finite_number,
)
from labkit.formats.runs import as_stored

#: the keys the verdict writes into metrics.json, beside the kept number's
STATE_KEY = "ref_state"
MET_KEY = "ref_met"
DISTANCE_KEY = "ref_distance"
VALUE_KEY = "ref_value"
TOLERANCE_KEY = "ref_tolerance"
RELATION_KEY = "ref_relation"
VERDICT_KEYS = frozenset(
    {STATE_KEY, MET_KEY, DISTANCE_KEY, VALUE_KEY, TOLERANCE_KEY, RELATION_KEY}
)
#: the two states of `ref_state`
COMPARED = "compared"
NOT_COMPARABLE = "not comparable"


def reference_verdict(measured: object, ref: Reference) -> dict[str, object]:
    """The verdict of MEASURED, the metrics value under REF's key, against
    REF, as the run records it: `ref_state` COMPARED with `ref_met` (bool)
    and `ref_distance` (`|measured - value|`, in the key's unit, for every
    relation), or NOT_COMPARABLE with both None when MEASURED is None (the
    key absent) or no finite number (a string, a bool, NaN, an infinity);
    with `ref_value`, `ref_tolerance` (the absolute tolerance the
    comparison used, `Reference.absolute_tolerance`; None for `at_least`
    and `at_most`) and `ref_relation` as compared. `within` is met when
    the distance is at most the tolerance; `at_least` when `measured >=
    value`; `at_most` when `measured <= value`. Exact float arithmetic,
    no rounding and no closeness band: the distance is the raw difference,
    the rendered line carries it as the run recorded it, and a measured
    value at the very edge of the tolerance falls where the floats put it
    (0.63 against 0.62 ± 0.01 is not met by 9e-18) — the distance beside
    the verdict shows a reader how close it was."""
    tolerance = ref.absolute_tolerance
    stated = {
        VALUE_KEY: ref.value,
        TOLERANCE_KEY: tolerance,
        RELATION_KEY: ref.relation,
    }
    if not finite_number(measured):
        return {STATE_KEY: NOT_COMPARABLE, MET_KEY: None, DISTANCE_KEY: None, **stated}
    assert isinstance(measured, (int, float))  # finite_number said so
    distance = abs(measured - ref.value)
    if ref.relation == WITHIN:
        assert tolerance is not None, "`within` reads with a tolerance"
        met = distance <= tolerance
    elif ref.relation == AT_LEAST:
        met = measured >= ref.value
    else:
        assert ref.relation == AT_MOST, f"relation {ref.relation!r} outside RELATIONS"
        met = measured <= ref.value
    return {STATE_KEY: COMPARED, MET_KEY: met, DISTANCE_KEY: distance, **stated}


def with_verdict(metrics: dict, ref: Reference | None) -> dict:
    """METRICS with the verdict against REF added (`reference_verdict` on
    `metrics[ref.key]`, None when absent); METRICS itself, unchanged,
    without a reference. Raises ValueError when METRICS already carries a
    verdict key: the comparison is the head's, never computed beside it
    in `evaluate_rows`, and without a `[reference]` no `ref_*` key may
    stand in the run."""
    typed = sorted(VERDICT_KEYS & set(metrics))
    if typed:
        raise ValueError(
            f"metrics carry {typed} — the reference verdict is written from the "
            f"head's [reference] (`reference.with_verdict`), never by evaluate_rows"
            + ("" if ref is not None else "; and no [reference] is registered")
        )
    if ref is None:
        return metrics
    return {**metrics, **reference_verdict(metrics.get(ref.key), ref)}


def phrase(metrics: dict, ref: Reference) -> str:
    """The comparison as the Recorded results line carries it, from the
    verdict METRICS recorded (not recomputed) and REF's key for the way a
    comparison failed: `reference 0.62 ± 0.01 (within): met, distance
    0.003`, `… not met, distance 0.145`, or `… not comparable:
    deforestation_rate absent` / `… = nan is no finite number`. The value,
    the tolerance and the distance are written as `recheck.plain_numbers`
    writes them, so the check finds each in the note. Raises ValueError
    when METRICS holds no verdict or one in neither state."""
    if STATE_KEY not in metrics:
        raise ValueError(f"metrics record no `{STATE_KEY}` — no verdict to render")
    stated = f"reference {metrics[VALUE_KEY]}"
    if metrics.get(TOLERANCE_KEY) is not None:
        stated += f" ± {metrics[TOLERANCE_KEY]}"
    stated += f" ({metrics[RELATION_KEY]})"
    state = metrics[STATE_KEY]
    if state == COMPARED:
        met = metrics[MET_KEY]
        if met is not True and met is not False:
            raise ValueError(f"`{MET_KEY}` = {met!r} is not true or false")
        return (
            f"{stated}: {'met' if met else 'not met'}, distance {metrics[DISTANCE_KEY]}"
        )
    if state == NOT_COMPARABLE:
        why = (
            f"{ref.key} absent"
            if ref.key not in metrics
            else f"{ref.key} = {metrics[ref.key]} is no finite number"
        )
        return f"{stated}: not comparable: {why}"
    raise ValueError(
        f"`{STATE_KEY}` = {state!r} is neither compared nor not comparable"
    )


def comparison_gaps(ref: Reference | None, metrics: dict) -> list[GateFinding]:
    """Why the run's METRICS cannot report the comparison REF registers, one
    guaranteed blocker each, or []: a `ref_*` key without a registered
    reference (a comparison typed beside the number); a registered
    reference the run recorded no verdict for (the script does not read
    the head); a verdict NOT_COMPARABLE — the key absent or no finite
    number, with the way out: write the key, measure anew; a verdict in
    neither state or with a `ref_met` that is not true or false (written
    beside the number); or a verdict compared against another value,
    tolerance or relation than the head registers now (the registration
    changed after the run). A missed reference is no finding: `ref_met =
    false` is a valid outcome."""
    if ref is None:
        typed = sorted(VERDICT_KEYS & set(metrics))
        if not typed:
            return []
        return [
            blocker(
                f"metrics.json carries {typed} and the head registers no [reference] "
                f"— a comparison is registered before the run, never written beside "
                f"the number",
                fix="register the stated value in the head's [reference] table "
                "(key, value, tolerance, relation, source) and measure anew; or "
                "drop the keys from evaluate_rows()",
            )
        ]
    if STATE_KEY not in metrics:
        return [
            blocker(
                f"the head registers [reference] on `{ref.key}`, and the run recorded "
                f"no verdict (no `{STATE_KEY}` in metrics.json) — the script does "
                f"not read the head's reference",
                fix="write the verdict from the head after evaluate_rows() — the "
                "compute skeleton's `metrics_of()` does (`reference.with_verdict`) "
                "— then measure anew and audit that run",
            )
        ]
    if metrics[STATE_KEY] == NOT_COMPARABLE:
        why = (
            "is absent from metrics.json"
            if ref.key not in metrics
            else f"= {metrics[ref.key]!r} in metrics.json is no finite number"
        )
        return [
            blocker(
                f"`{ref.key}` {why}, so the registered reference ({phrase(metrics, ref)}) "
                f"cannot be compared and no verdict can be reported",
                fix=f"write `{ref.key}` as a finite number from evaluate_rows() (the "
                f"key the head's [reference] names — the compute skeleton's "
                f"METRIC_KEY), measure anew and audit that run; a reference that "
                f"names the wrong key is a new registration",
            )
        ]
    if metrics[STATE_KEY] != COMPARED or metrics.get(MET_KEY) not in (True, False):
        return [
            blocker(
                f"the verdict in metrics.json does not read: `{STATE_KEY}` = "
                f"{metrics[STATE_KEY]!r}, `{MET_KEY}` = {metrics.get(MET_KEY)!r} — "
                f"written beside the number, not by `reference.with_verdict`",
                fix="let the compute skeleton's `metrics_of()` write the verdict, "
                "measure anew and audit that run",
            )
        ]
    now = reference_verdict(0, ref)
    moved = [
        k
        for k in (VALUE_KEY, TOLERANCE_KEY, RELATION_KEY)
        if as_stored(metrics.get(k)) != as_stored(now[k])
    ]
    if moved:
        return [
            blocker(
                f"the run compared with {', '.join(f'{k} = {metrics.get(k)!r}' for k in moved)}, "
                f"the head registers {', '.join(f'{k} = {now[k]!r}' for k in moved)} — "
                f"the reference changed after the run, and a value set after a "
                f"result was seen does not answer the registered question",
                fix="restore the [reference] the run compared with, or register anew "
                "and measure again",
            )
        ]
    return []
