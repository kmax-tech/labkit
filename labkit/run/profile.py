"""profile — what a prepared dataset shows per gold class before any model call.

A gold class that a surface cue tells apart answers the question without
the model: the item count and word count per class, each marker the area
names (a word or phrase) counted per class, each further numeric confound
column the area names averaged per class. `00_prepare.py --audit` prints
it; the person reads it and writes the judgement into the protocol's Data
profile field before the measuring run. A marker found in one class only
is a shortcut candidate — a cue the model could use, not proof it does.

Which markers and confounds matter is the area's decision, and an open
decision stays visible: `None` is "not decided yet", `()` is "decided:
none applies", and a named marker found in no item is "checked, no hit".

    p = profile.profile(items, markers=MARKERS, confounds=CONFOUNDS)
    print("\\n".join(profile.lines(p)))
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClassProfile:
    """One gold class: its item count, mean word count and mean of each named confound."""

    gold: str
    n: int
    mean_words: float
    confounds: dict[str, float]


@dataclass(frozen=True)
class MarkerCount:
    """One marker: in how many items of each gold class it occurs."""

    marker: str
    per_class: dict[str, int]

    @property
    def only_in(self) -> str | None:
        """The one class it occurs in when every other class has none of it."""
        present = [g for g, k in self.per_class.items() if k > 0]
        return present[0] if len(present) == 1 and len(self.per_class) > 1 else None


@dataclass(frozen=True)
class Profile:
    """The data profile; `markers`/`confounds` None when the area has not decided them."""

    classes: tuple[ClassProfile, ...]
    markers: tuple[MarkerCount, ...] | None
    any_marker: dict[str, int] | None  # items holding at least one marker, per class
    confounds: tuple[str, ...] | None


def _pattern(marker: str) -> re.Pattern[str]:
    """MARKER as a whole word or phrase, case ignored."""
    return re.compile(rf"(?<!\w){re.escape(marker)}(?!\w)", re.I)


def _by_class(
    items: list[dict],
    markers: tuple[str, ...] | None,
    confounds: tuple[str, ...] | None,
    text_field: str,
    gold_field: str,
) -> dict[str, list[dict]]:
    """ITEMS grouped by gold value, held to `profile`'s rules (ValueError)."""
    if not items:
        raise ValueError("no items to profile")
    for name in (*(markers or ()), *(confounds or ())):
        if not name.strip():
            raise ValueError("an empty marker or confound name")
    by_class: dict[str, list[dict]] = {}
    for n, it in enumerate(items, 1):
        for key in (text_field, gold_field):
            if key not in it:
                raise ValueError(f"item {it.get('id', n)} has no {key!r}")
        for c in confounds or ():
            v = it.get(c)
            if not isinstance(v, int | float) or isinstance(v, bool):
                raise ValueError(
                    f"item {it.get('id', n)}: confound {c!r} is {v!r}, not a number"
                )
        by_class.setdefault(str(it[gold_field]), []).append(it)
    return by_class


def profile(
    items: list[dict],
    *,
    markers: tuple[str, ...] | None,
    confounds: tuple[str, ...] | None,
    text_field: str = "text",
    gold_field: str = "gold",
) -> Profile:
    """The profile of ITEMS per gold class, classes in order of first
    appearance. Raises ValueError on an item without the text or gold
    field, a confound that is not a number, an empty marker or confound
    name, or no items."""
    by_class = _by_class(items, markers, confounds, text_field, gold_field)
    classes = tuple(
        ClassProfile(
            gold,
            len(rows),
            sum(len(str(r[text_field]).split()) for r in rows) / len(rows),
            {c: sum(r[c] for r in rows) / len(rows) for c in confounds or ()},
        )
        for gold, rows in by_class.items()
    )
    if markers is None:
        return Profile(classes, None, None, confounds)
    pats = {m: _pattern(m) for m in markers}

    def holds(r: dict, m: str) -> bool:
        return bool(pats[m].search(str(r[text_field])))

    counted = tuple(
        MarkerCount(
            m, {g: sum(holds(r, m) for r in rows) for g, rows in by_class.items()}
        )
        for m in markers
    )
    any_marker = {
        g: sum(any(holds(r, m) for m in markers) for r in rows)
        for g, rows in by_class.items()
    }
    return Profile(classes, counted, any_marker, confounds)


def lines(p: Profile) -> list[str]:
    """P as `--audit` prints it: the classes, the markers, the confounds —
    an undecided one said so, never shown as an empty table."""
    out = ["== data profile per gold class ==", f"  {'gold':<16} {'n':>4}  mean words"]
    out += [f"  {c.gold:<16} {c.n:>4}  {c.mean_words:.1f}" for c in p.classes]
    out.append("== markers (MARKERS) ==")
    if p.markers is None:
        out.append(
            "  not decided — MARKERS is None: name the words or phrases that could "
            "answer the question without the model, or () when none applies"
        )
    elif not p.markers:
        out.append("  decided: none applies (MARKERS = ())")
    else:
        for m in p.markers:
            counts = " · ".join(f"{g} {k}" for g, k in m.per_class.items())
            note = (
                f"only in {m.only_in} — a shortcut candidate"
                if m.only_in
                else "checked: in no item"
                if not any(m.per_class.values())
                else ""
            )
            out.append(f"  {m.marker:<16} {counts}   {note}".rstrip())
        assert p.any_marker is not None
        sizes = {c.gold: c.n for c in p.classes}
        union = " · ".join(f"{g} {k}/{sizes[g]}" for g, k in p.any_marker.items())
        out.append(f"  {'any of them':<16} {union}")
    out.append("== further confounds (CONFOUNDS) ==")
    if p.confounds is None:
        out.append(
            "  not decided — CONFOUNDS is None: name the numeric item fields beside "
            "the word count that could differ by class, or () when none applies"
        )
    elif not p.confounds:
        out.append("  decided: none beyond the word count (CONFOUNDS = ())")
    else:
        for name in p.confounds:
            means = " · ".join(f"{c.gold} {c.confounds[name]:.3g}" for c in p.classes)
            out.append(f"  {name:<16} {means}")
    return out
