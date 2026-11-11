"""Guards that hold a rule test and a pure check to their layer
(docs/architecture.md, "Checks and their tests").

- `no_process_or_command`: what the pytest mark `rule` switches on for the
  whole test (`conftest._rule_test_guard`). No process starts — and a
  repository is built only by starting git, so none is built either — and
  no console command is entered through its module (`<module>.main`,
  `<module>.cli` of every `[project.scripts]` entry).
- `pure_call`: one check called with no file opened, read, listed or
  stat'ed and no process started. Resolving a path passes (`Path.resolve`,
  as `repo.shown` calls it): a way out names a path as the working
  directory reaches it.

Each guard replaces module attributes for its duration, so a helper that
reaches the forbidden call through those modules is caught too. Its limits:
a name bound before the guard starts (`from labkit.gates.finalize import
main` at a test module's top) is not replaced; the import system's own file
reads (`posix.stat`) pass; a C extension that opens a file passes. The
guards enforce the boundaries a rule test exercises — not purity for every
possible execution.
"""

from __future__ import annotations

import builtins
import contextlib
import importlib
import io
import os
import subprocess
from collections.abc import Callable, Generator
from importlib.metadata import distribution
from pathlib import Path
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class ForbiddenAccess(AssertionError):
    """A guarded test or check reached a file, a process or a command."""


#: (module, attribute) of every call that reads the file system: open,
#: stat, list — `Path.read_text`, `is_file`, `iterdir` and `glob` end in
#: one of them
FILE_CALLS = (
    (builtins, "open"),
    (io, "open"),
    (os, "open"),
    (os, "stat"),
    (os, "lstat"),
    (os, "listdir"),
    (os, "scandir"),
    (os, "access"),
    (os, "readlink"),
)
#: (module, attribute) of every call that starts a process; `subprocess.run`
#: and git's calls in `repo` end in `subprocess.Popen`
PROCESS_CALLS = (
    (subprocess, "Popen"),
    (os, "system"),
    (os, "posix_spawn"),
    (os, "posix_spawnp"),
    (os, "fork"),
)


@contextlib.contextmanager
def _replaced(
    calls: tuple[tuple[object, str], ...], what: str, allowed: Callable[[], bool]
) -> Generator[None]:
    """Each of CALLS replaced by one that raises ForbiddenAccess naming
    WHAT, unless ALLOWED() says the call is one the guard lets through;
    restored on exit."""
    saved = [(mod, name, getattr(mod, name)) for mod, name in calls]

    def guard(name: str, original: Callable[..., object]) -> Callable[..., object]:
        def refused(*args: object, **kwargs: object) -> object:
            if allowed():
                return original(*args, **kwargs)
            raise ForbiddenAccess(f"{what}: {name}{args!r}")

        return refused

    try:
        for mod, name, original in saved:
            setattr(mod, name, guard(name, original))
        yield
    finally:
        for mod, name, original in saved:
            setattr(mod, name, original)


def command_modules() -> list[object]:
    """The module of every console command labkit installs
    (`[project.scripts]` as the installed metadata hold it)."""
    return [
        importlib.import_module(ep.value.partition(":")[0])
        for ep in distribution("labkit").entry_points
        if ep.group == "console_scripts"
    ]


@contextlib.contextmanager
def no_process_or_command() -> Generator[None]:
    """For the duration: starting a process and entering a console command
    raise ForbiddenAccess."""
    commands = tuple(
        (mod, name)
        for mod in command_modules()
        for name in ("main", "cli")
        if hasattr(mod, name)
    )
    with (
        _replaced(PROCESS_CALLS, "a rule test starts no process", lambda: False),
        _replaced(commands, "a rule test enters no command", lambda: False),
    ):
        yield


def pure_call(check: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """CHECK(*ARGS, **KWARGS) with every file and process call refused
    (ForbiddenAccess), but for the file calls `Path.resolve` makes while
    it resolves a path."""
    resolving = [0]
    resolve = Path.resolve

    def counted(self: Path, strict: bool = False) -> Path:
        resolving[0] += 1
        try:
            return resolve(self, strict=strict)
        finally:
            resolving[0] -= 1

    Path.resolve = counted  # type: ignore[method-assign] — restored below
    try:
        with (
            _replaced(
                FILE_CALLS, "a pure check reads no file", lambda: resolving[0] > 0
            ),
            _replaced(PROCESS_CALLS, "a pure check starts no process", lambda: False),
        ):
            return check(*args, **kwargs)
    finally:
        Path.resolve = resolve  # type: ignore[method-assign] — the original
