"""kept_number_check — the numbers a finished run reports, held to its record.

A criterion's denominator against an input count the run recorded
(`criterion_n_input_mismatches`, a static-evidence warning) and the kept
number held as the head's `[kept] key` names it (`kept_number_gaps`, a
guaranteed blocker). Each returns findings graded where they are made.
Read-only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from labkit.formats import promises, protocol_block
from labkit.formats.commands import measure_anew, register_anew
from labkit.formats.gate import (
    LAB_041,
    OPEN_RULE,
    STATIC_EVIDENCE,
    WARNING,
    GateFinding,
    blocker,
)
from labkit.formats.runs import DataEntry, OutputEntry

CRITERION_N = promises.CRITERION_N_KEY


def criterion_ns(metrics: Mapping[str, object]) -> dict[str, int]:
    """The criterion denominators of METRICS, a run's metrics.json: every
    `criterion_<i>_n` key that holds an integer — a bool is no count."""
    return {
        k: v
        for k, v in metrics.items()
        if CRITERION_N.match(k) and isinstance(v, int) and not isinstance(v, bool)
    }


def criterion_n_input_mismatches(
    ns: Mapping[str, int],
    inputs: Sequence[DataEntry],
    outputs: Sequence[OutputEntry],
) -> list[GateFinding]:
    """A static-evidence WARNING per criterion denominator of NS
    (`criterion_ns`) that matches no input count the run recorded — the rows
    of its INPUTS (`data=`) and the lines of its OUTPUTS: the size of what
    was counted, not a promised constant (that is
    `intent_check.promised_constant_mismatches`). One WARNING when NS holds
    denominators and the run recorded no count at all; [] when NS is empty
    or every denominator matches. A warning, never a blocker, until its
    false alarm rate is known; the rule is not decided yet (OPEN_RULE)."""
    if not ns:
        return []
    counts: dict[str, int] = {}
    for d in inputs:
        if d.rows is not None:
            counts[f"data[{d.key}].rows"] = d.rows
    for o in outputs:
        if o.lines is not None:
            counts[f"{o.path.name} lines"] = o.lines
    if not counts:
        return [
            _criterion_n_warning(
                f"{', '.join(sorted(ns))} present, but the run recorded no input "
                f"count (no data= rows, no output lines) to hold them to"
            )
        ]
    return [
        _criterion_n_warning(
            f"{k} = {n} matches no recorded count "
            f"({', '.join(f'{a} = {b}' for a, b in sorted(counts.items()))}) — "
            f"a denominator that is not the input is the audits' most "
            f"frequent real finding"
        )
        for k, n in sorted(ns.items())
        if n not in counts.values()
    ]


def _criterion_n_warning(text: str) -> GateFinding:
    """The static-evidence WARNING `criterion_n_input_mismatches` gives."""
    return GateFinding(WARNING, text, rule=OPEN_RULE, evidence_kind=STATIC_EVIDENCE)


#: how many of the run's other metrics a kept-number blocker names
_HELD_SHOWN = 6


def kept_number_gaps(
    key: str, metrics: dict, run: str, area: Path, kind: str
) -> list[GateFinding]:
    """A guaranteed blocker when METRICS, the metrics.json of the run RUN of
    AREA, does not hold KEY — the head's `[kept] key`, at every kind — as a
    finite number (`protocol_block.finite_number`: a bool, a text, None, NaN
    or an infinity is none), naming the key, the run and what it holds
    instead, its way out a new protocol of the head's KIND after the first
    measurement; [] when it does. The skeleton's own check sits in an
    agent-editable script; this one reads the head and the run's record. It
    binds the key, not its meaning: a wrong computation stored under KEY
    passes — the area's tests and the analysis audit judge that
    (docs/notes/2026-11-01-kept-key-in-the-head.md)."""
    if key in metrics and protocol_block.finite_number(metrics[key]):
        return []
    others = [(k, v) for k, v in metrics.items() if k != key]
    held = ", ".join(f"{k} = {v!r}"[:60] for k, v in others[:_HELD_SHOWN]) + (
        f", … ({len(others) - _HELD_SHOWN} more)" if len(others) > _HELD_SHOWN else ""
    )
    what = (
        f"holds `{key}` = {metrics[key]!r}, which is no finite number"
        if key in metrics
        else f"holds no `{key}`"
    )
    return [
        blocker(
            f"the kept number: metrics.json of {run} {what} — the head's [kept] "
            f"names `{key}` as the number this protocol reports"
            + (f"; it holds {held}" if held else "; it holds nothing else"),
            fix=f"write `{key}` as a finite number from evaluate_rows() (the "
            f"skeleton reads the key from the head's [kept]), then "
            f"{measure_anew(area)}; when [kept] names the wrong number, set it "
            f"before the first measurement — after it, "
            + register_anew(per="per change, the [kept] among them", kind=kind),
            rule=LAB_041,
        )
    ]
