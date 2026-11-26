"""console — the one exit of every labkit command line, and its one refusal.

`exit_with(main)` calls `main(sys.argv[1:])` and exits with its code.
When a reader closes the pipe early, stdout is redirected to /dev/null
and the command exits 0; this also prevents a broken pipe on final flush.
Usage errors and progress go to stderr; findings and results go to stdout.

While `exit_with` runs a command's main, answers that cannot change are
kept for that command (`once_per_command`); with no command running
nothing is kept.

"""

from __future__ import annotations

import contextlib
import functools
import os
import sys
from collections.abc import Callable, Hashable, Iterator
from importlib.metadata import PackageNotFoundError, distribution, version
from typing import TypeVar, cast

T = TypeVar("T")

#: the answers kept for the command now running, by key; None while no
#: command runs — `once_per_command` then keeps nothing
_kept_answers: dict[Hashable, object] | None = None


@contextlib.contextmanager
def one_command() -> Iterator[None]:
    """The span of one command: inside it `once_per_command` keeps answers,
    starting from none; at its end, also by an exception, they are dropped
    and nothing is kept. `exit_with` runs a command's main in it.

    Side effects:
        Sets and clears this module's kept answers.

    Raises:
        RuntimeError: a command is already running — the inner span's end
            would drop the outer one's answers.
    """
    global _kept_answers
    if _kept_answers is not None:
        raise RuntimeError("one_command inside one_command: a command is running")
    _kept_answers = {}
    try:
        yield
    finally:
        _kept_answers = None


def once_per_command(
    key: Hashable, ask: Callable[[], T], *, keep: Callable[[T], bool] | None = None
) -> T:
    """ASK's answer, asked at most once per command for KEY.

    For a question whose answer cannot change while the command runs — an
    object read by its full hash — and whose answer is immutable. The
    caller owes both; KEY names the question whole (what is asked, where,
    of what), since two questions under one key get the first one's answer.

    With no command running (`one_command`) ASK is called every time: in a
    measure script — a run's start, its own call of `recheck` — and in a
    main called directly, without `exit_with`. An exception out of ASK
    passes through and nothing is kept. KEEP, when given, decides for an
    answer whether it is one of those that cannot change; an answer it
    refuses is returned and asked again next time.

    Side effects:
        Inside a command, keeps the answer until the command ends.
    """
    if _kept_answers is None:
        return ask()
    if key in _kept_answers:
        return cast(T, _kept_answers[key])
    answer = ask()
    if keep is None or keep(answer):
        _kept_answers[key] = answer
    return answer


def refuse(tool: str, why: str) -> None:
    """Print `TOOL: WHY` to stderr for a command that could not run.

    Returns None; does not exit or choose an exit code. The caller supplies
    the reason, such as an invalid argument, missing file or ambiguous
    protocol. Findings go to stdout through the gate's collector.

    """
    print(f"{tool}: {why}", file=sys.stderr)


def progress(tool: str, text: str) -> None:
    """A line about the command's own doing — what it reads, the tokens a
    call cost, an early note — on STDERR like a refusal, so stdout stays
    the result (labkit-audit's report). Neither a finding nor a refusal:
    exit codes do not change because of it."""
    print(f"{tool}: {text}", file=sys.stderr)


def usage(tool: str, text: str, asked: bool) -> int:
    """TEXT, the command's usage: on stdout with exit 0 when ASKED (`-h`,
    `--help`); else the command ran with nothing to work on, a refusal on
    stderr with exit 2 (`refuse`)."""
    if asked:
        print(text)
        return 0
    refuse(tool, f"no arguments\n{text}")
    return 2


def asks_help(argv: list[str]) -> bool:
    """Whether ARGV asks for the usage: `-h` or `--help` anywhere on a
    hand-read command line, not only first — `CMD SUB --help` and
    `CMD AREA --help` print the usage and do nothing else, where reading
    the flag as a value or a path made a command run (labkit-hooks
    installed). Not for a command line that hands words after its target
    to another command (labkit-calltree)."""
    return "-h" in argv or "--help" in argv


class Refused(Exception):
    """A command that cannot run, raised where the reason is known: TOOL is
    the command that refuses (named, not read off sys.argv, which `-m` and
    a caller's own command change), WHY the reason. `exit_with` prints it
    through `refuse` and exits 2; a main that runs as another gate's station
    catches it itself. A caller gets a result or this exception, never an
    exit code beside a result (`Path | int`) that means "already
    printed". The rule goes by the caller, not by the directory: code a
    measure script reaches with no main of labkit's around it — the
    start checks of a run (`run/start_check`, `runlog.run`'s own
    refusals, `batch`, `lanes`) and `recheck` — ends with `SystemExit` and
    the sentence, the loud end without a traceback that script needs;
    code a labkit main reaches raises this — `runlog.busy`, `detached`,
    the runlog command, intent-check, code-check, every gate."""

    def __init__(self, tool: str, why: str) -> None:
        super().__init__(f"{tool}: {why}")
        self.tool = tool
        self.why = why


def exit_with(main: Callable[[list[str]], int]) -> None:
    """Exit with `main(argv)`'s code; a `Refused` raised out of it is printed
    through `refuse` and exits 2; a pipe closed by the reader is exit 0.
    MAIN runs as one command (`one_command`)."""
    try:
        with one_command():
            code = main(sys.argv[1:])
    except Refused as exc:
        refuse(exc.tool, exc.why)
        code = 2
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        code = 0
    sys.exit(code)


@functools.cache
def command_names() -> frozenset[str]:
    """The console commands labkit installs: `[project.scripts]` as the
    installed metadata hold it. Raises PackageNotFoundError when labkit is
    not installed (`pip install -e '.[dev]'`); a stale editable install
    lacks a command added since — reinstall."""
    return frozenset(
        ep.name
        for ep in distribution("labkit").entry_points
        if ep.group == "console_scripts"
    )


def installed_version() -> str | None:
    """The installed labkit's version, None where labkit runs from a source
    tree that is not installed (on `PYTHONPATH` only). The one reading of
    it: a caller that needs the version says itself what its absence
    means — a refusal, or the word "unknown"."""
    try:
        return version("labkit")
    except PackageNotFoundError:
        return None


def split_command(argv: list[str]) -> tuple[list[str], list[str] | None]:
    """(the words before the first `--`, the command after it) of a command
    line that runs another command; the command is None when ARGV holds no
    `--`, and every word after the cut stays untouched — `--log` included.

    The cut happens before argparse: a trailing REMAINDER positional takes
    an option that follows the other positionals (`--log FILE -- CMD`) as
    part of the command."""
    if "--" not in argv:
        return argv, None
    cut = argv.index("--")
    return argv[:cut], argv[cut + 1 :]
