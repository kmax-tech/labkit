"""jsonl — the one reader for JSON Lines files: lines, records, data rows.

JSON Lines separates records by "\\n" and nothing else. `str.splitlines()`
also breaks at U+2028, U+2029 and U+0085, which `json.dumps(...,
ensure_ascii=False)` and JavaScript's `JSON.stringify` leave raw inside a
string: a record holding one was read as two torn lines, and the reader
called the file damaged (2026-10-23). Every reader of a JSONL text splits
here; iterating an open file (`for line in fh`) breaks at "\\n" only and
needs no help.

`objects` turns the lines into objects, each with its line number, and
names file and line for one that is not JSON; `data_rows` drops the
`_meta` header `batch.write_dataset` puts first. Six readers did this
themselves, each with its own error sentence (audit 2026-10-23); `batch`
keeps its own loop for the one case that is its own — a torn last line of
an interrupted write is cut, not refused.
"""

from __future__ import annotations

import json


def is_meta(obj: object) -> bool:
    """The `_meta` header `batch.write_dataset` puts first in a data file —
    not a data row."""
    return isinstance(obj, dict) and "_meta" in obj


def objects(text: str, where: str) -> list[tuple[int, object]]:
    """(line number, object) for every non-empty line of TEXT, in order.
    Raises ValueError naming WHERE (the file, as the caller shows it) and
    the line for one that is not JSON."""
    out: list[tuple[int, object]] = []
    for n, line in enumerate(record_lines(text), 1):
        if not line.strip():
            continue
        try:
            out.append((n, json.loads(line)))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{where}:{n}: not JSON ({exc.msg}) — one JSON object per line; "
                f"repair the line"
            ) from exc
    return out


def data_rows(text: str, where: str) -> list[dict]:
    """The records of TEXT as data rows: objects, the `_meta` header left
    out. Raises ValueError naming WHERE and the line for a line that is not
    JSON or not an object."""
    rows: list[dict] = []
    for n, obj in objects(text, where):
        if is_meta(obj):
            continue
        if not isinstance(obj, dict):
            raise ValueError(f"{where}:{n}: a data row is a JSON object, not {obj!r}")
        rows.append(obj)
    return rows


def record_lines(text: str) -> list[str]:
    """TEXT's lines, split at "\\n" only, each without its "\\n" and a "\\r"
    before it (a file written with CRLF). A final "\\n" ends the last line
    and adds no empty one — the line numbers match an editor's."""
    out = text.split("\n")
    if out and out[-1] == "":
        out.pop()
    return [ln[:-1] if ln.endswith("\r") else ln for ln in out]
