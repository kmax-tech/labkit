"""prompts — the text an agent is given, joined one way.

Every part an agent reads stands under a `===== <label> =====` line: the
audit's prompt, both reviewers', the code-check bundle. The join lives
here, below the gates and the checks that both use it, so neither spells
its own.
"""

from __future__ import annotations


def prompt_body(pieces: list[tuple[str, str]]) -> str:
    """PIECES as an agent reads them: each text under a `===== label =====`
    line of its own."""
    return "".join(f"===== {label} =====\n{text}\n" for label, text in pieces)
