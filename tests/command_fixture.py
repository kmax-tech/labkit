"""A console command called in-process for test fixtures: the one main-runner.

One home for "call a command's `main(argv)` and take what it printed", so a
test file states the command and its arguments and not how the streams are
caught (`tests/test_one_home.py` holds a second runner out). What a test adds
around the call — a working directory, a patched model — it wraps around
`run_main`; a helper that returns the two streams apart stays in its file.
"""

from __future__ import annotations

import contextlib
import io
from collections.abc import Callable


def run_main(
    main: Callable[[list[str]], int], argv: list[str], *, capture_stderr: bool = True
) -> tuple[int, str]:
    """Call MAIN with ARGV; its exit code and what it printed.

    Args:
        main: a command's `main`, which takes the argument list and returns
            the exit code.
        argv: the arguments after the command's name.
        capture_stderr: True takes stdout and stderr together, in the order
            printed (a refusal is on stderr); False takes stdout alone and
            leaves stderr where it points.

    Returns:
        (exit code, the captured text).

    Raises:
        SystemExit: MAIN left through `sys.exit` (argparse's refusal); what
            it printed until then is lost to the caller.
    """
    out = io.StringIO()
    with contextlib.ExitStack() as caught:
        caught.enter_context(contextlib.redirect_stdout(out))
        if capture_stderr:
            caught.enter_context(contextlib.redirect_stderr(out))
        code = main(argv)
    return code, out.getvalue()
