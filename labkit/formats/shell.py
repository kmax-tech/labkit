"""shell — a shell line as its simple commands, one reading for every reader.

The pre-run hook decides per command whether a line opens a run (a `cd` is
followed, a throwaway flag frees only its own command); the transcript
reader counts the labkit commands and file reads an agent made. Both read
the same line the same way here: quote-aware (`shlex`), cut at `&&`, `||`,
`;`, `|`, `&`, `(`, `)` and line breaks, heredoc bodies removed — their
lines are input data, not commands. Static evidence: a line shlex cannot
read (an unbalanced quote) is split at whitespace instead of being skipped,
so a reader still sees its commands, more crudely.
"""

from __future__ import annotations

import re
import shlex

HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
SEPARATORS = frozenset({"&&", "||", ";", "|", "&", "(", ")"})


def strip_heredocs(command: str) -> str:
    """The command without heredoc bodies: their lines are input data (a
    Python script, a file's text), not shell — `from labkit.checks import recheck`
    in a body is no run of `recheck`."""
    lines = command.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        tags = [m.group(2) for m in HEREDOC.finditer(lines[i])]
        i += 1
        for tag in tags:
            while i < len(lines) and lines[i].strip() != tag:
                i += 1
            i += 1  # the terminator
    return "\n".join(out)


def pieces(command: str) -> list[tuple[list[str], str]]:
    """(words, the separator after them) for each simple command."""
    text = strip_heredocs(command).replace("\n", " ; ")
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:  # an unbalanced quote: whitespace, see the module docstring
        tokens = text.split()
    out: list[tuple[list[str], str]] = [([], "")]
    for tok in tokens:
        if tok in SEPARATORS:
            out[-1] = (out[-1][0], tok)
            out.append(([], ""))
        else:
            out[-1][0].append(tok)
    return [(w, op) for w, op in out if w]


def segments(command: str) -> list[list[str]]:
    """The simple commands of a shell line, as word lists."""
    return [w for w, _ in pieces(command)]
