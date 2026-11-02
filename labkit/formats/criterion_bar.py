"""criterion_bar — [criterion-1]'s bar in the estimator and prompt skeletons.

    criterion_bar.require_one_form(cfg.at_least, cfg.margin)   # MeasureConfig.__post_init__
    bar = criterion_bar.bar_of(cfg.at_least, cfg.margin, null_value)   # evaluate_rows
    passed = score >= bar

[criterion-1] registers exactly one of two constants (LAB-035 Thresholds
belong to the run, not to the measure; docs/notes/2026-11-02-absolute-task-bar.md):
`at_least`, a bar the task states, is the bar as written whatever the null
lane scores; `margin` is a lead over the null value the skeleton computes
(the estimator's permutation expectation or refit mean, the prompt
skeleton's null-lane accuracy). The one home of the two forms, their
refusal and the arithmetic, so the two skeletons cannot drift apart. A
registered value is read as written (`Fraction(str(value))`, 0.25 = 1/4):
in floats a lane exactly at the bar failed by one ulp. Pure: nothing here
reads or writes a file.
"""

from __future__ import annotations

from fractions import Fraction

#: the two constants, by their names in the [[promise]] table
AT_LEAST = "at_least"
MARGIN = "margin"


def require_one_form(at_least: float | None, margin: float | None) -> None:
    """Return when exactly one of AT_LEAST and MARGIN is registered (not
    None). Raises ValueError naming both forms otherwise — both would leave
    the verdict to whichever the code reads, neither registers no bar."""
    if (at_least is None) != (margin is None):
        return
    given = (
        f"both `{AT_LEAST}` and `{MARGIN}`"
        if margin is not None
        else f"neither `{AT_LEAST}` nor `{MARGIN}`"
    )
    raise ValueError(
        f"[criterion-1] registers {given} — register one in its constants: "
        f"`{AT_LEAST} = <value>` for a bar the task states (absolute; name its "
        f"source in the sentence), or `{MARGIN} = <value>` for a lead over the "
        "null value"
    )


def bar_of(
    at_least: float | None, margin: float | None, null_value: Fraction | float
) -> Fraction | float:
    """[criterion-1]'s bar: AT_LEAST as written, or NULL_VALUE plus MARGIN as
    written — a Fraction where NULL_VALUE is one, a float where it is a float
    (r2, spearman). Raises ValueError unless exactly one form is registered
    (`require_one_form`)."""
    require_one_form(at_least, margin)
    if at_least is not None:
        return Fraction(str(at_least))
    assert margin is not None  # require_one_form said so
    return null_value + Fraction(str(margin))
