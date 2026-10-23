"""Stamp WHICH code an audit looked at — the stamp of LAB-019 The stamp covers everything that determines the number (preflight and analysis audit).

The audit fields in a protocol claim "this code was audited". A stamp that
covers less than the code determining the number is worse than none: it makes
a stale audit look current. The scope covers exactly: `scripts/*.py` and
`analysis/*.py` of the area, the files its protocols' promises declare as
scope, the repo-local `lib/` and `src/` modules all of these import (shared
anchors and thresholds live there), and the `labkit==` pin line when one is
found — at least what `labkit-audit` reads in full — and, where a protocol
of the area names `[model] annotation_validity`, the evidence the audit is
shown of it (`validation_basis`: the bound apply protocol, its result, its
scripts and its `models.toml` entry; of a DOI only its string — the cited
content is bound by nothing). NOT covered otherwise: data files, prompt
files, models.toml, the protocol — an unchanged stamp says the CODE is the
same, not the inputs. Sibling: `promises.declared_scope_sha` is the same idea per
promise, over its declared scope.

Why a command and not a shell one-liner: the one-liner in the first draft of
LAB-019 The stamp covers everything that determines the number
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
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from labkit.formats.runs import metrics_path, run_path
from labkit.formats import console, protocol_block
from pathlib import Path

from labkit.formats.repo import (
    area_protocols,
    areas_of,
    layout_root,
    no_such_area,
    repo_protocols,
    requirement_lines,
)

DIGEST_CHARS = 12  # enough to spot a mismatch, short enough for a protocol line


class SourceError(ValueError):
    """A file in the stamp's scope that cannot be read as Python; the message
    names it. A gate reports it as a blocker — until 0.94.0 it was a
    traceback in preflight and code-check, exit 1 and so not blocking in the
    pre-run hook (audit 2026-10-15)."""


AREA_GLOBS = ("scripts/*.py", "analysis/*.py")


def area_files(area: Path, globs: tuple[str, ...] = AREA_GLOBS) -> list[Path]:
    """The area's own code: scripts, then analysis, each sorted by name
    (the order every check and the audit prompt list them in)."""
    out: list[Path] = []
    for pat in globs:
        out.extend(sorted(area.glob(pat)))
    return out


#: The repo-local roots a script reaches by import: `lib/` (the house
#: layout) and `src/` (a repo whose own package is the thing measured —
#: uniagent computes every registered key in src/measure, and with lib/
#: alone neither the audit stamp nor the key search saw it, 2026-10-07).
LOCAL_ROOTS = ("lib", "src")


def parse_source(path: Path) -> ast.Module:
    """The syntax tree of a scope file, or SourceError naming the file. The
    one parse behind every gate that reads code: until the audit of
    2026-10-18 only the import walk raised SourceError, so without a `lib/`
    in the repo a broken script reached a bare `ast.parse` in code-check's
    constant check — a traceback in preflight, exit 1, not blocking."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise SourceError(f"{path}: cannot be read as Python ({exc})") from exc


def _lib_names(path: Path, libdir: Path) -> set[str]:  # noqa: C901 complexity baseline 2026-10-08
    """Dotted module paths under `libdir` that `path` may import, read from
    its syntax tree: `import a.b`, `from a.b import c` (c may be a module),
    `from a import b`, the root's own name as a prefix (`from lib import x`)
    and relative imports inside the root. Candidates, not facts: the caller
    keeps those that are files. Raises SourceError naming the file when it
    does not parse — a stamp over code it cannot read would be a guess."""
    tree = parse_source(path)
    prefix = libdir.name
    package: list[str] = []
    if libdir in path.parents:
        package = list(path.relative_to(libdir).parent.parts)
    names: set[str] = set()

    def strip(parts: list[str]) -> list[str]:
        if parts and parts[0] == prefix:
            # `import lib.x` runs lib/__init__.py first: it is code too
            names.add(ROOT_INIT)
            return parts[1:]
        return parts

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


#: The name `_lib_names` gives the root's own `__init__.py`, which an import
#: through the root's name (`from lib import x`) executes; `_lib_files`
#: resolves it to `<root>/__init__.py` when that file exists.
ROOT_INIT = "__init__"


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


def declared_scope_files(protocols: list[Path]) -> list[Path]:
    """The files the `[[promise]]` tables of `protocols` declare as scope
    (`file` or `file:function`, relative to the protocol's directory), each
    once, resolved, in order; no tables, none. A missing file is returned
    as it is — the caller names it; a malformed block raises
    `promises.PromiseError` (a ValueError). The audit reads these in full
    for its protocol; the stamp covers them for every protocol of the area."""
    from labkit.formats import promises  # layer 1 both; promises imports this module

    out: list[Path] = []
    for protocol in protocols:
        block = promises.parse_block(protocol.read_text(encoding="utf-8"))
        if block is None:
            continue
        for p in block.promises:
            for entry in p.scope:
                f = (protocol.parent / entry.split(":", 1)[0]).resolve()
                if f not in out:
                    out.append(f)
    return out


def imported_repo_helpers(area: Path, repo: Path) -> list[Path]:
    """The helper files elsewhere in the repo that the area's scripts import —
    repo-local files (under LOCAL_ROOTS) the area's code reaches by
    import, transitively —
    shared anchors and thresholds live there, so they determine the number
    (LAB-019 The stamp covers everything that determines the number). Review 2026-10-07: `from lib import scoring` and `import
    lib.scoring` were read as a module `lib`, and a lib module's own imports
    were not followed; lib/scoring.py changed while the stamp stayed put."""
    return _import_closure(list(area_files(area)), repo)


def _import_closure(start: list[Path], repo: Path) -> list[Path]:
    """The repo-local files START reach by import, transitively, sorted."""
    roots = [repo / r for r in LOCAL_ROOTS if (repo / r).is_dir()]
    seen: set[Path] = set()
    todo = list(start)
    while todo:
        path = todo.pop()
        for libdir in roots:
            for name in _lib_names(path, libdir):
                for f in _lib_files(name, libdir):
                    if f not in seen:
                        seen.add(f)
                        todo.append(f)
    return sorted(seen)


def import_reach(area: Path, repo: Path) -> set[Path]:
    """Every repo-local path the area's code reaches by import, transitively:
    the files `imported_repo_helpers` stamps, and the paths an import names
    that do not exist (`a.py`, `a/__init__.py`) — a helper deleted under
    the area is still one it depends on. Raises SourceError like the stamp."""
    reach = {f.resolve() for f in imported_repo_helpers(area, repo)}
    roots = [repo / r for r in LOCAL_ROOTS if (repo / r).is_dir()]
    for path in [*area_files(area), *imported_repo_helpers(area, repo)]:
        for libdir in roots:
            for name in _lib_names(path, libdir):
                target = libdir.joinpath(*name.split("."))
                reach.add(target.with_suffix(".py").resolve())
                reach.add((target / "__init__.py").resolve())
    return reach


def areas_touched(
    paths: list[Path], repo: Path, protocols: list[Path] | None = None
) -> list[Path]:
    """The areas PATHS touch: the area each path lies in (`repo.areas_of`),
    every area whose promises declare a path in their scope
    (`declared_scope_files`) — a rubric or a label file read at run time
    determines the number though no code imports it — every area whose
    stamp covers the path as bound validation evidence
    (`validation_sources`: a changed validation stales the audit of the
    computation resting on it), and for a path under
    a LOCAL_ROOT every area whose code imports it (`import_reach`): a
    shared helper changed or deleted reopens the numbers that rest on it as
    a script in the area does. PROTOCOLS as in `repo.find_area` (the
    index's at the commit), else the working tree's; their text is read
    from the working tree, as the area's code is. An area whose protocol
    or code cannot be read counts as touched: whether it rests on the path
    cannot be told, and the gate is the safer answer; the other areas
    answer as if it were not there. The one answer for the stop, the
    commit's undecided gate and report-check."""
    root = repo.resolve()
    out = areas_of(paths, root, protocols)
    changed = {p.resolve() for p in paths}
    shared = [p for p in changed if any((root / r) in p.parents for r in LOCAL_ROOTS)]
    every = protocols if protocols is not None else repo_protocols(root)
    for area in sorted({p.parent for p in every}):
        if area in out:
            continue
        try:
            declared = declared_scope_files([p for p in every if p.parent == area])
        except (ValueError, OSError):
            out.append(area)
            continue
        if changed.intersection(declared):
            out.append(area)
            continue
        if changed.intersection(f.resolve() for f in validation_sources(area)):
            out.append(area)
            continue
        if not shared:
            continue
        try:
            reach = import_reach(area, root)
        except SourceError:
            out.append(area)
            continue
        if any(p in reach for p in shared):
            out.append(area)
    return out


def repo_imports(files: list[Path], repo: Path) -> list[Path]:
    """The repo-local files (under LOCAL_ROOTS) that `files` import DIRECTLY —
    one step of the graph `imported_repo_helpers` walks to the end. The
    audit reads these in full and the rest as an index (LAB-103 The audit
    reads by declared scope, not by import graph); the stamp keeps the
    whole graph."""
    roots = [repo / r for r in LOCAL_ROOTS if (repo / r).is_dir()]
    seen: set[Path] = set()
    for path in files:
        for libdir in roots:
            for name in _lib_names(path, libdir):
                seen.update(_lib_files(name, libdir))
    return sorted(seen)


def find_pin(start: Path, name: str = "labkit") -> tuple[str, str] | None:
    """(file, line) of the pin of `name`, searched upwards from the area."""
    for d in [start, *start.parents]:
        for fn in ("requirements.lock", "requirements.txt"):
            p = d / fn
            if not p.exists():
                continue
            lines = requirement_lines(p.read_text(encoding="utf-8"), name)
            if lines:
                return str(p), lines[0]
    return None


def _key(f: Path, root: Path) -> str:
    """The path as hashed: relative to the repo root, `/`-separated; a file
    outside the root keeps its absolute path."""
    f = f.resolve()
    try:
        return f.relative_to(root.resolve()).as_posix()
    except ValueError:
        return f.as_posix()


def digest(data: bytes, chars: int | None = DIGEST_CHARS) -> str:
    """sha256 of DATA, cut to CHARS (None: full) — the one digest of bytes
    that are not a file: a promise block's canonical JSON, a lease
    endpoint's canonical URL (audit 2026-10-15: each spelled hashlib itself)."""
    h = hashlib.sha256(data).hexdigest()
    return h if chars is None else h[:chars]


def file_digest(path: Path) -> str:
    """sha256 of a file's bytes, full hex, read in chunks. The one file
    digest: the stamp, the run record, the hooks and recheck used to spell
    it four times (audit 2026-10-13); a caller that records a prefix cuts
    it itself, so the recorded width stays where the format is."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_digest(
    entries: Iterable[tuple[str, bytes]],
    trailer: Iterable[str] = (),
    chars: int | None = DIGEST_CHARS,
) -> str:
    """One digest over named contents: per entry its name and the sha256 of
    its bytes, one line each, then the trailer lines — so adding, dropping,
    renaming or editing an entry moves it. The caller orders the entries
    (sorted, for a stamp). `chars=None` keeps the full hex. The shape of the
    area stamp, a promise's declared scope, a run's directory source and the
    usability probe's scaffold sha."""
    h = hashlib.sha256()
    for name, content in entries:
        h.update(name.encode("utf-8") + b"\n")
        h.update(hashlib.sha256(content).hexdigest().encode() + b"\n")
    for line in trailer:
        h.update(line.encode("utf-8") + b"\n")
    digest = h.hexdigest()
    return digest if chars is None else digest[:chars]


@dataclass(frozen=True)
class Snapshot:
    """An area's stamped code as read ONCE: every file's bytes, and the sha
    over exactly these bytes. A reader that renders from `contents` shows
    what `sha` names; reading the paths again may see other bytes.

    Attributes:
        sha: The stamp (`DIGEST_CHARS` hex) over `contents`, the pin line and
            the `validation` evidence.
        files: The stamped files in the order the scope lists them, each once.
        contents: Resolved path → the bytes the sha covers.
        pin: (file, line) of the labkit pin, or None.
        validation: One sentence per `annotation_validity` the area's
            protocols declare, naming what of it the sha covers
            (`validation_basis`); () when none does.
    """

    sha: str
    files: tuple[Path, ...]
    contents: Mapping[Path, bytes]
    pin: tuple[str, str] | None
    validation: tuple[str, ...] = ()

    def text(self, path: Path) -> str:
        """The snapshot's text of PATH. Raises KeyError naming a path the
        snapshot does not hold — a reader asking for one would show bytes
        no sha covers."""
        key = path.resolve()
        if key not in self.contents:
            raise KeyError(f"{path} is not in the snapshot of the stamped code")
        return self.contents[key].decode("utf-8")


def area_snapshot(
    area: Path,
    extra: list[Path] | tuple[Path, ...] = (),
    globs: tuple[str, ...] = AREA_GLOBS,
    use_pin: bool = True,
) -> Snapshot:
    """The area's stamped code, read once: its scripts, the files its
    protocols' promises declare as scope, the repo-local lib modules all of
    these import, `extra` files, and the labkit pin — at least every file
    `labkit-audit` reads in full. The sha is a digest over (repo-relative
    path, content digest) per file plus the pin line, taken from the bytes
    the snapshot holds. Raises FileNotFoundError naming a missing file,
    ValueError when there is nothing to stamp or a promise block is
    malformed."""
    root = layout_root(area)
    # the audit reads a declared file and its direct imports in full, so the
    # stamp walks from it too — every protocol's, so it needs no choice and
    # covers at least what any audit of the area reads
    declared = declared_scope_files(area_protocols(area))
    listed = (
        area_files(area, globs)
        + declared
        + _import_closure(
            [*area_files(area), *(f for f in declared if f.is_file())], root
        )
        + list(extra)
    )
    missing = [str(f) for f in listed if not f.is_file()]
    if missing:
        raise FileNotFoundError(f"scope file(s) missing: {', '.join(missing)}")
    if not listed:
        raise ValueError(
            f"no scope files under {area} ({', '.join(globs)}) and none named"
        )
    files: list[Path] = []
    contents: dict[Path, bytes] = {}
    for f in listed:
        if f.resolve() not in contents:
            files.append(f)
            contents[f.resolve()] = f.read_bytes()
    pin = find_pin(area.resolve()) if use_pin else None
    entries = sorted((_key(f, root), contents[f]) for f in contents)
    basis, told = validation_basis(area)
    # appended after the files and only when declared: an area without an
    # `annotation_validity` keeps the stamp it had
    sha = tree_digest([*entries, *basis], trailer=[pin[1]] if pin else [])
    return Snapshot(sha, tuple(files), MappingProxyType(contents), pin, told)


#: entry names of the validation basis start so, apart from every file key
VALIDATION_KEY = "annotation_validity"


def validation_basis(
    area: Path,
) -> tuple[list[tuple[str, bytes]], tuple[str, ...]]:
    """(entries, sentences): what the area stamp covers of the evidence its
    protocols name in `[model] annotation_validity`, so an audit that was
    shown that evidence (`audit.validity_evidence`) goes stale when it
    changes. Per declaring protocol: the reference as written; for a
    protocol id that resolves to exactly one protocol of the repo
    (`protocol_block.repo_protocol_ids`), that protocol's bytes, its
    declared run's `metrics.json` (a marker while it is missing), the run
    records that say which model answered (`config.json`,
    `answering_run.recorded_runs`) and its area's `scripts/*.py` (where its
    `PROMPT` constants live; its `Prompt` blocks stand in the protocol).
    Today's models.toml is not stamped: it can change after the validation
    without changing what was validated. A DOI binds no document bytes: only its string
    is stamped. Whether the reference is a valid binding (an apply with a
    result) is the gate's (`protocol_history.bound_validation`), not the
    stamp's. Never raises for a protocol it cannot read — the head check
    names that."""
    root = layout_root(area)
    entries: list[tuple[str, bytes]] = []
    told: list[str] = []
    for p, ref, bound in _validation_refs(area):
        name = f"{VALIDATION_KEY} of {_key(p, root)}"
        entries.append((name, f"{ref.key} = {ref.value}".encode("utf-8")))
        if ref.key != "protocol":
            told.append(f"{_key(p, root)} names doi {ref.value} (its string only)")
            continue
        if bound is None:
            told.append(f"{_key(p, root)} names {ref.value}, bound to no one protocol")
            continue
        entries += _bound_entries(name, bound, root)
        told.append(
            f"{_key(p, root)} names {_key(bound, root)} (the protocol, its "
            f"declared result, the run record of its model and its scripts)"
        )
    return entries, tuple(told)


def validation_sources(area: Path) -> list[Path]:
    """The files outside AREA's own code that its stamp covers through
    `[model] annotation_validity` (`validation_basis`): per bound protocol,
    the protocol, its declared run's `metrics.json`, the run records of its
    model (`config.json`) and its area's `scripts/*.py`. A path may not exist (a
    result not written yet). A DOI ties the area to no file. What
    `areas_touched` follows, so a change to the evidence reopens the area
    that rests on it."""
    out: list[Path] = []
    for _, _, bound in _validation_refs(area):
        if bound is not None:
            out += _bound_files(bound)
    return out


def _validation_refs(
    area: Path,
) -> Iterator[tuple[Path, protocol_block.Validity, Path | None]]:
    """(protocol, reference, bound protocol or None) per protocol of AREA
    that declares `[model] annotation_validity`; the bound protocol only for
    a protocol id naming exactly one protocol of the repo
    (`protocol_block.repo_protocol_ids`). A protocol that does not read is
    skipped — the head check names it."""
    ids: dict[str, list[Path]] | None = None
    for p in area_protocols(area):
        try:
            m = protocol_block.model(p.read_text(encoding="utf-8"))
        except (OSError, protocol_block.BlockError):
            continue
        if m is None or m.annotation_validity is None:
            continue
        ref = m.annotation_validity
        if ref.key != "protocol":
            yield p, ref, None
            continue
        if ids is None:
            ids = protocol_block.repo_protocol_ids(area)
        hits = ids.get(ref.value, [])
        yield p, ref, hits[0] if len(hits) == 1 else None


def _bound_files(bound: Path) -> list[Path]:
    """The bound protocol, its declared run's `metrics.json`, the
    `config.json` of that run and of the run that recorded its model
    (`answering_run.recorded_runs`: which model answered is a record, not
    today's models.toml), and its area's scripts — paths even while missing,
    the files `_bound_entries` reads."""
    # layer 1 both; answering_run imports promises, which imports this module
    from labkit.formats.answering_run import recorded_runs

    out = [bound]
    try:
        run = protocol_block.declared_run(bound.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, protocol_block.BlockError):
        run = None
    if run is not None:
        run_dir = run_path(bound.parent, run)
        out.append(metrics_path(run_dir))
        out += [r / "config.json" for r in recorded_runs(run_dir)]
    out += sorted((bound.parent / "scripts").glob("*.py"))
    return out


def validation_note(area: Path) -> str:
    """For a refusal of a stale audit: "" when the area stamp covers no
    `annotation_validity` evidence (or the area cannot be stamped — the
    refusal names that), else a clause saying the stamp covers the bound
    validation too, so a change there is why the audit no longer covers.
    The stamp is one digest: it cannot tell the code from the evidence."""
    try:
        told = area_snapshot(area).validation
    except (FileNotFoundError, ValueError):
        return ""
    if not told:
        return ""
    return (
        " — the stamp covers the bound validation too, so a change to it "
        "counts as well: " + "; ".join(told)
    )


def _bound_entries(name: str, bound: Path, root: Path) -> list[tuple[str, bytes]]:
    """The bytes of `_bound_files` as named stamp entries
    (`validation_basis`); a missing file as a marker."""
    try:
        data = bound.read_bytes()
    except OSError as exc:
        return [(f"{name}: {_key(bound, root)}", f"unreadable: {exc}".encode())]
    return [(f"{name}: {_key(bound, root)}", data)] + [
        (f"{name}: {_key(f, root)}", f.read_bytes() if f.is_file() else b"<missing>")
        for f in _bound_files(bound)[1:]
    ]


def area_stamp(
    area: Path,
    extra: list[Path] | tuple[Path, ...] = (),
    globs: tuple[str, ...] = AREA_GLOBS,
    use_pin: bool = True,
) -> tuple[str, list[Path], tuple[str, str] | None]:
    """(sha, files, pin) of `area_snapshot` — for a caller that needs the
    stamp, not the bytes. Raises as `area_snapshot` does."""
    snap = area_snapshot(area, extra, globs, use_pin)
    return snap.sha, list(snap.files), snap.pin


def main(argv: list[str]) -> int:  # noqa: C901 complexity baseline 2026-10-08
    """Command line of `scope-sha`: the stamp over an area's code, as a record's `scope_sha` names it."""
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
                console.refuse("scope-sha", "--area needs a directory")
                return 2
            area = Path(argv[i + 1])
            i += 2
            continue
        if a == "--globs":
            if i + 1 >= len(argv):
                console.refuse(
                    "scope-sha", "--globs needs a comma-separated pattern list"
                )
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
        console.refuse("scope-sha", no_such_area(area))
        return 2

    try:
        sha, files, pin_found = area_stamp(area, extra, globs, use_pin)
    except (FileNotFoundError, ValueError) as exc:
        console.refuse("scope-sha", str(exc))
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
    console.exit_with(main)


if __name__ == "__main__":
    cli()
