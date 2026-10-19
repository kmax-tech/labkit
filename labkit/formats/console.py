"""console — the one exit of every labkit command line, and its one refusal.

`exit_with(main)` calls `main(sys.argv[1:])` and exits with its code. A reader
that closes the pipe early (`protocol-check --contract P | head`) raises
BrokenPipeError inside print or at the interpreter's final flush; Python
then prints a traceback and exits 120, which a cloud agent read as a crash
of the command (Haiku 5.5, 2026-10-13). A closed pipe is the reader's
choice, not an error of ours: stdout is pointed at /dev/null so the final
flush cannot raise, and the exit code is 0.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable


def refuse(tool: str, why: str) -> None:
    """A command that could not run — a bad argument, no such area, no
    protocol to choose, no such file — says so on STDERR; what a gate FOUND
    goes to stdout. The two were mixed (44 refusals on stdout, 25 on stderr,
    audit 2026-10-15), so a caller reading stdout for findings read a usage
    error as one."""
    print(f"{tool}: {why}", file=sys.stderr)


def exit_with(main: Callable[[list[str]], int]) -> None:
    """Exit with `main(argv)`'s code; a pipe closed by the reader is exit 0."""
    try:
        code = main(sys.argv[1:])
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        code = 0
    sys.exit(code)
