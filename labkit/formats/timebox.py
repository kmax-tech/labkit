"""The protocol's Timebox as a number, and a measurement's projection against it.

The field `Timebox` is prose for a person ("4h — then record and ask"). A
measurement script can hold itself to it when the value starts with a
duration, `<number> <unit>` with the unit one of s, min, h (`seconds_of`):
the fit skeleton times its first fold, projects the whole run
(`projected_seconds`) and refuses to go on when the projection exceeds the
budget (`over_budget`), before the budget is spent — a refusal with the
numbers instead of a container killed at its limit. A Timebox that does
not start with a duration is no error: the field stays prose, and the
caller says that no projection is made. Pure functions; no file is read
here. Why and the incident: docs/notes/2026-10-31-fit-budget.md.
"""

from __future__ import annotations

import re

from labkit.formats import protocol_check

#: the units a Timebox may start with, in seconds
UNITS = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
}
GRAMMAR = "a duration first: <number> <unit>, the unit one of s, min, h (e.g. `45 min — then record and ask`)"
_LEAD = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)\b")
FIELD = "Timebox"


def parse_seconds(value: str) -> int:
    """The seconds a Timebox value names at its start; ValueError naming the
    grammar when it starts with anything else (a zero or negative duration
    included)."""
    m = _LEAD.match(value)
    if not m or m.group(2).lower() not in UNITS:
        raise ValueError(f"Timebox {value.strip()!r}: {GRAMMAR}")
    seconds = float(m.group(1).replace(",", ".")) * UNITS[m.group(2).lower()]
    if seconds <= 0:
        raise ValueError(f"Timebox {value.strip()!r}: a duration above zero")
    return int(round(seconds))


def seconds_of(protocol_text: str) -> tuple[int | None, str]:
    """(seconds, note) for the protocol's Timebox: the seconds when the field
    starts with a duration, else None — the note says which case holds
    (no field, a placeholder, or prose without a leading duration), for the
    caller to print, since a run without a budget check should say so."""
    found = [
        f
        for f in protocol_check.fields(protocol_text)
        if f.name == protocol_check.field_name(FIELD)
    ]
    if not found:
        return None, f"no {FIELD} field — no budget projection"
    value = found[0].value
    if found[0].placeholder:
        return None, f"{FIELD} not filled — no budget projection"
    try:
        return parse_seconds(value), f"{FIELD}: {value.strip().splitlines()[0]}"
    except ValueError:
        return (
            None,
            f"{FIELD} {value.strip().splitlines()[0]!r} names no duration first ({GRAMMAR}) — no budget projection",
        )


def projected_seconds(
    first_fold_s: float, n_folds: int, fits_per_fold: int, test_fit: bool
) -> float:
    """The whole measurement from its first fold: FIRST_FOLD_S for each of
    N_FOLDS folds, plus one fit's share of the fold (`first_fold_s /
    fits_per_fold`) for the final fit on every labelled item when TEST_FIT.
    A projection, not a bound: later folds run on the same amount of data,
    the final fit on more."""
    if n_folds < 1 or fits_per_fold < 1:
        raise ValueError(
            f"projected_seconds(): n_folds {n_folds} and fits_per_fold {fits_per_fold} must be at least 1"
        )
    if first_fold_s < 0:
        raise ValueError(
            f"projected_seconds(): first fold took {first_fold_s} s — a negative duration"
        )
    return first_fold_s * n_folds + (first_fold_s / fits_per_fold if test_fit else 0.0)


def over_budget(
    projected_s: float,
    budget_s: int,
    first_fold_s: float,
    n_folds: int,
    fits_per_fold: int,
) -> str | None:
    """The refusal when PROJECTED_S exceeds BUDGET_S, with the numbers and
    the way out; None when the projection fits. The way out names what a
    protocol may change before its first measurement: fewer folds or
    refits in the plan, or a larger Timebox — never a shorter run of the
    same plan."""
    if projected_s <= budget_s:
        return None
    return (
        f"the first fold took {first_fold_s:.0f} s; {n_folds} folds of {fits_per_fold} fits project to "
        f"{projected_s / 60:.1f} min against a Timebox of {budget_s / 60:.1f} min — stopped before the budget. "
        f"Next: register fewer folds or refits (the plan in the measurement script's head, before the first "
        f"measurement) or a larger Timebox in the protocol, then measure again"
    )
