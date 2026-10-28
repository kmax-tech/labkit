"""data_counts — the counts a preparation run recorded, as `protocol-fill
--data-counts` writes them into the protocol's Data / scope and the gates
hold them there.

The counts come from the run, never from the author: the files it read
(`data=`, non-empty lines as runlog counts them, a CSV header included)
and its prepared items — labelled, unlabelled, per gold value — as its
metrics record them (`item_counts`, written by the estimator skeleton's
`00_prepare.py`). The generated part of Data / scope opens with `counts
(prepare run <run_id>):` and stands at the field's end; the author's own
words stand before it.

Why: two cold agents registered counts the data did not hold — 108
labelled persons for 92, 118/60/60 compounds for 240/80/80 — after a
prepare script that printed the total alone (fifth SAB-like draw,
2026-10-28).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from labkit.formats import runs

#: the label of the field the counts stand in
FIELD = "Data / scope"
#: the metrics keys of a preparation run's counts (`item_counts`)
COUNT_KEYS = ("n_items", "n_labelled", "n_unlabelled", "gold_counts")
#: a gold that takes at most this many values is a class label and is
#: counted per value; more values are a measured quantity, not counted so
CLASS_LIMIT = 20
#: the generated part of Data / scope: its run, then its text to the end
COUNTS = re.compile(r"counts \(prepare run (?P<run>[^\s)]+)\): .*$")


def item_counts(items: list[dict], gold: str = "gold") -> dict:
    """The counts of prepared ITEMS by their GOLD field: `n_items`;
    `n_labelled` and `n_unlabelled` (gold None); `gold_counts`, the
    labelled items per gold value (as text) when the gold takes at most
    CLASS_LIMIT values, else None. Raises KeyError for an item without
    the GOLD field — a missing gold is None, never an absent key."""
    golds = [it[gold] for it in items]
    labelled = [g for g in golds if g is not None]
    values = Counter(str(g) for g in labelled)
    return {
        "n_items": len(items),
        "n_labelled": len(labelled),
        "n_unlabelled": len(golds) - len(labelled),
        "gold_counts": dict(sorted(values.items()))
        if len(values) <= CLASS_LIMIT
        else None,
    }


def counts_text(run_dir: Path) -> str:
    """What RUN_DIR, a completed preparation run, recorded of its data, as
    one sentence: `counts (prepare run <id>): read <file> <n> lines, …;
    <n> items prepared — <n> labelled (<value> <n>, …), <n> unlabelled`.
    The items' split stands only where the run's metrics hold
    `item_counts`. Raises ValueError for a run that is no completed
    preparation run, or holds no `n_items`."""
    cfg = runs.read_run_config(run_dir)
    if cfg is None or cfg.run_kind != "preparation":
        raise ValueError(f"{run_dir.name} is no preparation run (run_kind)")
    if runs.run_state(run_dir, alive=False) != runs.COMPLETED:
        raise ValueError(f"{run_dir.name} did not complete")
    metrics = runs.read_metrics(runs.metrics_path(run_dir))
    if "n_items" not in metrics:
        raise ValueError(f"{run_dir.name} records no n_items in metrics.json")
    read = [
        f"{Path(str(e['path'])).name} {e['rows']} lines"
        for _, e in sorted(cfg.data.items())
        if isinstance(e, dict) and isinstance(e.get("rows"), int)
    ]
    items = f"{metrics['n_items']} items prepared"
    if "n_labelled" in metrics:
        by_value = metrics.get("gold_counts")
        if not isinstance(by_value, dict):
            by_value = {}
        values = (
            " (" + ", ".join(f"{k} {v}" for k, v in by_value.items()) + ")"
            if by_value
            else ""
        )
        items += (
            f" — {metrics['n_labelled']} labelled{values}, "
            f"{metrics['n_unlabelled']} unlabelled"
        )
    head = f"counts (prepare run {run_dir.name}): "
    return head + (f"read {', '.join(read)}; " if read else "") + items


def with_counts(value: str, counts: str) -> str:
    """The Data / scope VALUE with its generated part replaced by COUNTS,
    or COUNTS added after the author's words — or COUNTS alone for a value
    still a placeholder (`<…>`)."""
    flat = " ".join(value.split())
    m = COUNTS.search(flat)
    if m:
        return (flat[: m.start()] + counts).strip()
    if not flat or (flat.startswith("<") and flat.endswith(">")):
        return counts
    return f"{flat.rstrip(' .;')} · {counts}"


def counts_gap(area: Path, value: str) -> tuple[str, str] | None:
    """Why the generated counts in Data / scope VALUE do not hold, with the
    command that writes them again: (sentence, run id) — the run the part
    names is not a completed preparation run of AREA, or the part differs
    from what that run recorded (`counts_text`): typed or stale. None when
    VALUE holds no generated part, or it holds."""
    m = COUNTS.search(" ".join(value.split()))
    if m is None:
        return None
    run_id = m.group("run")
    run_dir = runs.run_path(area, run_id)
    if not run_dir.is_dir():
        return (
            f"{FIELD} names prepare run {run_id}, which the area does not have",
            run_id,
        )
    try:
        expected = counts_text(run_dir)
    except ValueError as exc:
        return f"{FIELD} names prepare run {run_id}: {exc}", run_id
    if m.group(0) != expected:
        return (
            f"{FIELD}: the counts differ from what prepare run {run_id} recorded "
            f"— typed or stale (it records: {expected})",
            run_id,
        )
    return None
