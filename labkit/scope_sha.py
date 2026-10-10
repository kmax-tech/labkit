"""Stamp WHICH code an audit looked at — the stamp of AS-019 The stamp covers everything that determines the number (preflight and analysis audit).

The audit fields in a protocol claim "this code was audited". A stamp that
covers less than the code determining the number is worse than none: it makes
a stale audit look current. The scope covers exactly: `scripts/*.py` and
`analysis/*.py` of the area, the repo-local `lib/` and `src/` modules they
import (shared anchors and thresholds live there), and the `labkit==` pin
line when one is found. NOT covered: data files, prompt files, models.toml,
the protocol — an unchanged stamp says the CODE is the same, not the
inputs. Sibling: `promises.declared_scope_sha` is the same idea per
promise, over its declared scope.

Why a command and not a shell one-liner: the one-liner in the first draft of
AS-019 The stamp covers everything that determines the number
    { cat "$S"; xargs -a "$S" shasum -a 256; ...; } | shasum -a 256
which on macOS hashed NO file content at all — BSD xargs has no `-a`, and
under zsh's noclobber the `>` that built the list was refused too. It printed
a stable-looking 12-hex stamp while a changed anchor file left it untouched
(2026-09-08). A stamp that cannot go wrong quietly has to be tested code.

The hash covers each file's PATH — relative to the repo root, so the working
directory and the spelling of the area do not move it — and its content
digest, plus the pin line: adding, removing, renaming or editing a scope file
all change the stamp. `area_stamp` is the one home of the scope: `scope-sha`,
`preflight` and `labkit-audit` all call it, so the stamp an audit prints is the
stamp a later check recomputes (review 2026-10-07: four tools and spellings
gave four different stamps for one unchanged area).
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
from pathlib import Path

from labkit.repo import layout_root, no_such_area

DIGEST_CHARS = 12  # enough to spot a mismatch, short enough for a protocol line
AREA_GLOBS = ("scripts/*.py", "analysis/*.py")


def area_files(area: Path, globs: tuple[str, ...] = AREA_GLOBS) -> list[Path]:
    """The area's own code, in a stable order."""
    out: list[Path] = []
    for pat in globs:
        out.extend(area.glob(pat))
    return out


#: The repo-local roots a script reaches by import: `lib/` (the house
#: layout) and `src/` (a repo whose own package is the thing measured —
#: uniagent computes every registered key in src/measure, and with lib/
#: alone neither the audit stamp nor the key search saw it, 2026-10-07).
LOCAL_ROOTS = ("lib", "src")


def _lib_names(path: Path, libdir: Path) -> set[str]:  # noqa: C901 complexity baseline 2026-10-08
    """Dotted module paths under `libdir` that `path` may import, read from
    its syntax tree: `import a.b`, `from a.b import c` (c may be a module),
    `from a import b`, the root's own name as a prefix (`from lib import x`)
    and relative imports inside the root. Candidates, not facts: the caller
    keeps those that are files. Raises ValueError naming the file when it
    does not parse — a stamp over code it cannot read would be a guess."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise ValueError(f"{path}: cannot read its imports ({exc})") from exc
    prefix = libdir.name
    package: list[str] = []
    if libdir in path.parents:
        package = list(path.relative_to(libdir).parent.parts)
    names: set[str] = set()

    def strip(parts: list[str]) -> list[str]:
        return parts[1:] if parts and parts[0] == prefix else parts

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = strip(alias.name.split("."))
                if parts:
                    names.add(".".join(parts))
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: only meaningful inside the root
                if libdir not in path.parents:
                    continue
                base = (
                    package[: len(package) - (node.level - 1)]
                    if node.level > 1
                    else package
                )
                parts = base + ((node.module or "").split(".") if node.module else [])
            else:
                parts = strip((node.module or "").split("."))
            if parts:
                names.add(".".join(parts))
            for alias in node.names:  # `from a import b`: b may be a module
                names.add(".".join([*parts, alias.name]))
    return names


def _lib_files(name: str, libdir: Path) -> list[Path]:
    """The files importing dotted `name` executes under `libdir`: the
    module (`a/b.py`, or a package's `a/b/__init__.py`) and the
    `__init__.py` of every package on the way. A name that is no module
    there (a function, a stdlib module) gives nothing. Before 2026-10-07 a
    package import took every file of the package, and an area importing
    `measure.comparison` was charged with `measure/positions.py`."""
    parts = name.split(".")
    if not parts or not parts[0]:
        return []
    target = libdir.joinpath(*parts)
    if target.with_suffix(".py").is_file():
        found = [target.with_suffix(".py")]
    elif (target / "__init__.py").is_file():
        found = [target / "__init__.py"]
    else:
        return []
    for i in range(1, len(parts)):
        init = libdir.joinpath(*parts[:i]) / "__init__.py"
        if init.is_file():
            found.append(init)
    return found


def imported_repo_helpers(area: Path, repo: Path) -> list[Path]:
    """The helper files elsewhere in the repo that the area's scripts import —
    repo-local files (under LOCAL_ROOTS) the area's code reaches by
    import, transitively —
    shared anchors and thresholds live there, so they determine the number
    (AS-019 The stamp covers everything that determines the number). Review 2026-10-07: `from lib import scoring` and `import
    lib.scoring` were read as a module `lib`, and a lib module's own imports
    were not followed; lib/scoring.py changed while the stamp stayed put."""
    roots = [repo / r for r in LOCAL_ROOTS if (repo / r).is_dir()]
    seen: set[Path] = set()
    todo = list(area_files(area))
    while todo:
        path = todo.pop()
        for libdir in roots:
            for name in _lib_names(path, libdir):
                for f in _lib_files(name, libdir):
                    if f not in seen:
                        seen.add(f)
                        todo.append(f)
    return sorted(seen)


def find_pin(start: Path, name: str = "labkit==") -> tuple[str, str] | None:
    """(file, line) of the labkit pin, searched upwards from the area."""
    for d in [start, *start.parents]:
        for fn in ("requirements.lock", "requirements.txt"):
            p = d / fn
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith(name) or s.startswith("labkit @"):
                    return str(p), s
    return None


def _key(f: Path, root: Path) -> str:
    """The path as hashed: relative to the repo root, `/`-separated; a file
    outside the root keeps its absolute path."""
    f = f.resolve()
    try:
        return f.relative_to(root.resolve()).as_posix()
    except ValueError:
        return f.as_posix()


def scope_sha(files: list[Path], pin: str | None, root: Path) -> str:
    """Digest over (repo-relative path, content digest) per file plus the pin line."""
    h = hashlib.sha256()
    for key, f in sorted({_key(f, root): f for f in files}.items()):
        h.update(key.encode("utf-8") + b"\n")
        h.update(hashlib.sha256(Path(f).read_bytes()).hexdigest().encode() + b"\n")
    if pin:
        h.update(pin.encode("utf-8") + b"\n")
    return h.hexdigest()[:DIGEST_CHARS]


def area_stamp(
    area: Path,
    extra: list[Path] | tuple[Path, ...] = (),
    globs: tuple[str, ...] = AREA_GLOBS,
    use_pin: bool = True,
) -> tuple[str, list[Path], tuple[str, str] | None]:
    """(sha, files, pin) of an area: its scripts, the repo-local lib modules
    they import, `extra` files, and the labkit pin. Raises FileNotFoundError
    naming a missing file, ValueError when there is nothing to stamp."""
    root = layout_root(area)
    files = area_files(area, globs) + imported_repo_helpers(area, root) + list(extra)
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        raise FileNotFoundError(f"scope file(s) missing: {', '.join(missing)}")
    if not files:
        raise ValueError(
            f"no scope files under {area} ({', '.join(globs)}) and none named"
        )
    pin = find_pin(area.resolve()) if use_pin else None
    return scope_sha(files, pin[1] if pin else None, root), files, pin


#: the stamp as an audit line carries it (`labkit-audit`, `scope-sha` print it so)
AUDIT_SHA = re.compile(r"scope sha ([0-9a-f]{12})\b")


def audit_stamp_drift(area: Path, audit_line: str) -> str | None:
    """Why `audit_line` (the head's `preflight_audit`) does not cover the
    area's code as it is now, or None when it does.

    The line is written by hand, so nothing showed whether an audit ran or
    saw this code (review 2026-10-07). Its `scope sha` is checkable: it must
    equal the stamp the code has now. An explicit `n/a — <reason>` is a
    visible decision, not a claim, and passes.
    """
    line = audit_line.strip()
    if line.lower().startswith("n/a"):
        return None
    m = AUDIT_SHA.search(line)
    if not m:
        return (
            "the audit line names no `scope sha <12 hex>` — copy the stamp "
            "`labkit-audit` or `scope-sha` printed for the audited code"
        )
    try:
        now = area_stamp(area)[0]
    except (FileNotFoundError, ValueError) as exc:
        return f"the area cannot be stamped now ({exc})"
    if m.group(1) != now:
        return (
            f"the audit saw scope sha {m.group(1)}, the code now stamps {now} — "
            f"it changed after the audit: re-audit, or restamp once the change "
            f"is decided"
        )
    return None


def main(argv: list[str]) -> int:  # noqa: C901 complexity baseline 2026-10-08
    """Command line of `scope-sha`: the stamp over an area's code for an audit line."""
    if argv and argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print(
            "usage: scope-sha [AREA | --area DIR] [--globs PAT,...] [--no-pin] [FILE ...]"
        )
        print("  --area DIR       area directory (default: cwd)")
        print(
            "  --globs PAT,...  comma-separated globs for area scripts "
            "(default: scripts/*.py,analysis/*.py)"
        )
        print(
            "  FILE ...         extra files that determine the number; the "
            "repo-local lib/ modules the scripts import are included already"
        )
        print("  --no-pin         do not include the labkit pin line")
        return 0

    area = Path(".")
    use_pin = True
    globs = AREA_GLOBS
    extra: list[Path] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--area":
            if i + 1 >= len(argv):
                print("--area needs a directory")
                return 2
            area = Path(argv[i + 1])
            i += 2
            continue
        if a == "--globs":
            if i + 1 >= len(argv):
                print("--globs needs a comma-separated pattern list")
                return 2
            globs = tuple(p.strip() for p in argv[i + 1].split(","))
            i += 2
            continue
        if a == "--no-pin":
            use_pin = False
            i += 1
            continue
        if Path(a).is_dir():  # `scope-sha <AREA>`, like every other gate (2026-10-05)
            area = Path(a)
            i += 1
            continue
        extra.append(Path(a))
        i += 1
    if not area.is_dir():
        print(f"scope-sha: {no_such_area(area)}")
        return 2

    try:
        sha, files, pin_found = area_stamp(area, extra, globs, use_pin)
    except (FileNotFoundError, ValueError) as exc:
        print(f"scope-sha: {exc}")
        return 2
    root = layout_root(area)
    for key in sorted({_key(f, root) for f in files}):
        print(key)
    if pin_found:
        print(f"{pin_found[1]}   ({pin_found[0]})")
    elif use_pin:
        print("(no labkit pin found — stamp does not cover the shared helpers)")
    print(f"scope sha {sha}")
    return 0


def cli() -> None:
    """Entry point for the installed `scope-sha` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
