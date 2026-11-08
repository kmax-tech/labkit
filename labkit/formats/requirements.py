"""requirements — the one grammar of a requirements line (a pin).

What a `requirements.txt`, a `requirements.lock` or `pip freeze` says
about a package: a VCS pin (`name @ git+<url>@<ref>`), an editable VCS or
path install as pip freezes it, a version pin (`name==X.Y.Z`), and the
package name as pip normalises it. Read by provenance (the run's
environment), the repo check and the stamp (the labkit pin), the
declared-scope hash and the usability probe. Pure: lines in, matches out.
"""

from __future__ import annotations

import re

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
