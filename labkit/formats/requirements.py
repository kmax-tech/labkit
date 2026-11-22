"""requirements — the one grammar of a requirements line (a pin).

What a `requirements.txt`, a `requirements.lock` or `pip freeze` says
about a package: a VCS pin (`name @ git+<url>@<ref>`), an editable VCS or
path install as pip freezes it, a version pin (`name==X.Y.Z`), and the
package name as pip normalises it — and which files of a repository
say it (`PIN_FILES`, `requirements_files`). Read by provenance (the run's
environment), the repo check and the stamp (the labkit pin), the
declared-scope hash and the usability probe. The grammar is pure: lines
in, matches out; `requirements_files` reads only whether files exist
and where the git root is.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import re

from labkit.formats.repo import git_root

#: what pip froze: the environment a run records
REQUIREMENTS_LOCK = "requirements.lock"
#: what the repository declares: the stamped pin of labkit at its tag
REQUIREMENTS_TXT = "requirements.txt"
#: the files that pin a repository's environment, the lock first: in one
#: directory, a search takes the lock before the declared list
PIN_FILES = (REQUIREMENTS_LOCK, REQUIREMENTS_TXT)

_PKG = r"(?P<name>[A-Za-z0-9][A-Za-z0-9._\-]*)"
#: `name @ git+<url>@<ref>` — a VCS pin; the ref is optional, a trailing `# comment` allowed
VCS_REQUIREMENT = re.compile(
    rf"^{_PKG}\s*@\s*git\+(?P<url>[^@\s#]+)(?:@(?P<ref>[^#\s]+))?\s*(?:#.*)?$"
)
#: `-e git+<url>@<ref>#egg=<name>` — how pip freezes an editable VCS install;
#: in a git worktree pip appends `&subdirectory=<path to the worktree>`
EDITABLE_REQUIREMENT = re.compile(
    rf"^-e\s+git\+(?P<url>[^@\s#]+)@(?P<ref>[^#\s]+)#egg={_PKG}(?:&\S*)?\s*$"
)
#: `-e /path/to/<name>` — how pip freezes an editable path install
EDITABLE_PATH_REQUIREMENT = re.compile(rf"^-e\s+(?P<path>\S*/{_PKG})/?\s*$")
#: `name==X.Y.Z` — a version pin
VERSION_REQUIREMENT = re.compile(rf"^{_PKG}\s*==\s*(?P<version>\d+\.\d+\.\d+)\s*$")


def pip_name(name: str) -> str:
    """A package name as pip normalises it: lowercase, `_` to `-`."""
    return name.lower().replace("_", "-")


def requirement_name(line: str) -> str | None:
    """The package a requirements line names, as pip normalises it
    (lowercase, `_` to `-`): a VCS or editable pin, `name==…`, `name @ <url>`.
    None for a blank, a comment or a line of another shape."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    for pat in (VCS_REQUIREMENT, EDITABLE_REQUIREMENT, EDITABLE_PATH_REQUIREMENT):
        if (m := pat.match(s)) is not None:
            return pip_name(m.group("name"))
    for sep in ("==", " @ "):
        if sep in s:
            return pip_name(s.split(sep, 1)[0].strip())
    return None


def requirement_lines(text: str, name: str) -> list[str]:
    """The lines of a requirements file (or `pip freeze` output) that name `name`."""
    return [ln.strip() for ln in text.splitlines() if requirement_name(ln) == name]


def requirements_files(
    start: Path, names: tuple[str, ...] = PIN_FILES
) -> Iterator[Path]:
    """Every file named in NAMES that exists in START or above it, nearest
    directory first and, within one directory, in the order of NAMES.

    The search stops at the root of START's git repository
    (`repo.git_root`), that root included: a requirements file above the
    repository is not the repository's, and taking it would record one
    commit differently on two machines. Outside a repository it goes on to
    the filesystem root. START is made absolute, not resolved: a yielded
    path keeps the spelling the caller gave. Lazy — a caller that takes
    the first match looks into no further directory.
    """
    start = start.absolute()
    top = git_root(start)
    for d in [start, *start.parents]:
        for name in names:
            if (d / name).exists():
                yield d / name
        if top is not None and d.resolve() == top:
            return
