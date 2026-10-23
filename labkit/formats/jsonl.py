"""jsonl — the one line reader for JSON Lines files.

JSON Lines separates records by "\\n" and nothing else. `str.splitlines()`
also breaks at U+2028, U+2029 and U+0085, which `json.dumps(...,
ensure_ascii=False)` and JavaScript's `JSON.stringify` leave raw inside a
string: a record holding one was read as two torn lines, and the reader
called the file damaged (2026-10-23). Every reader of a JSONL text splits
here; iterating an open file (`for line in fh`) breaks at "\\n" only and
needs no help.
"""

from __future__ import annotations


def record_lines(text: str) -> list[str]:
    """TEXT's lines, split at "\\n" only, each without its "\\n" and a "\\r"
    before it (a file written with CRLF). A final "\\n" ends the last line
    and adds no empty one — the line numbers match an editor's."""
    out = text.split("\n")
    if out and out[-1] == "":
        out.pop()
    return [ln[:-1] if ln.endswith("\r") else ln for ln in out]
