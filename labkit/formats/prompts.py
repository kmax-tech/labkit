"""prompts — the text an agent is given, joined one way.

Every part an agent reads stands under a `===== <label> =====` line: the
audit's prompt, both reviewers', the code-check bundle. The join lived in
`gates/audit.py`, a layer above `checks/code_check.py`, which spelled its
own (audit 2026-10-28, H3).
"""

from __future__ import annotations


def prompt_body(pieces: list[tuple[str, str]]) -> str:
    """PIECES as an agent reads them: each text under a `===== label =====`
    line of its own."""
    return "".join(f"===== {label} =====\n{text}\n" for label, text in pieces)
