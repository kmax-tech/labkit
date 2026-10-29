"""deliverable — the file an external task names, written by the answering run.

A task that names its output (`pred_results/<name>.csv`) is answered by
that file, not by the metrics in the area. The stamped measurement script
names it in `DELIVERABLES`, writes it from the kept rows through
`write_csv` and registers it with `run.output(...)` before the run closes,
so outputs.json pins it by path and sha256 and `finalize` holds the file
in the tree to that record (`run_record_check.output_record_findings`).
Until then the deliverable was bound to nothing: an injection benchmark
swapped `pred_results/*.csv` in seven delivered states and no gate
noticed (docs/usability/2026-10-29-injection-ab4ce6d.md, M7).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from labkit.formats.files import write_atomic


class DeliverableError(ValueError):
    """Rows that cannot be written as the deliverable: no rows, or a row
    whose keys are not the first row's."""


def render_csv(rows: list[dict[str, object]]) -> str:
    """ROWS as CSV text, the first row's keys as the header in their order;
    every row must carry exactly those keys (DeliverableError naming the
    odd row), and an empty list is refused — an empty deliverable answers
    nothing. Pure: writes nothing."""
    if not rows:
        raise DeliverableError("no rows — an empty deliverable answers nothing")
    header = list(rows[0])
    for n, row in enumerate(rows, 1):
        if list(row) != header:
            raise DeliverableError(
                f"row {n} has the columns {', '.join(row)}, the header "
                f"{', '.join(header)} — every row carries the header's columns, "
                f"in its order"
            )
    out = io.StringIO()
    w = csv.DictWriter(out, header, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def write_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    """Write ROWS as CSV at PATH (`render_csv`) and return PATH, for
    `run.output(...)`. Side effects: creates the parent directory, writes
    the file atomically. Raises DeliverableError as `render_csv` does."""
    text = render_csv(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, text)
    return path
