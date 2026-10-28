"""repo — where things are: repo root, an area's protocols, git.

Small questions every gate asks, answered once. Before 2026-10-06 they were
answered five times: each module globbed `PROTOCOL-*.md` itself, three
functions found the repo root by three different rules, and two private
`_git` helpers turned EVERY git failure into an empty string — so a git that
failed to run read as "working tree clean".

Two git calls, by what a non-zero exit means:

    git(args, cwd)      the output; None outside a repo; GitError otherwise
    git_run(args, cwd)  the completed process, for commands whose exit code
                        IS the answer (`ls-files --error-unmatch`,
                        `rev-parse --verify`, `show HEAD:path`)
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from labkit.formats import console

GIT_TIMEOUT_S = 20

# --- requirement lines: the one grammar of a pin (four spellings before, audit 2026-10-13)
_PKG = r"(?P<name>[A-Za-z0-9][A-Za-z0-9._\-]*)"
#: `name @ git+<url>@<ref>` — a VCS pin; the ref is optional, a trailing `# comment` allowed
VCS_REQUIREMENT = re.compile(
    rf"^{_PKG}\s*@\s*git\+(?P<url>[^@\s#]+)(?:@(?P<ref>[^#\s]+))?\s*(?:#.*)?$"
)
#: `-e git+<url>@<ref>#egg=<name>` — how pip freezes an editable VCS install;
#: in a git worktree pip appends `&subdirectory=<path to the worktree>`
#: (2026-10-27: every probe staged from a worktree found no labkit line)
EDITABLE_REQUIREMENT = re.compile(
    rf"^-e\s+git\+(?P<url>[^@\s#]+)@(?P<ref>[^#\s]+)#egg={_PKG}(?:&\S*)?\s*$"
)
#: `-e /path/to/<name>` — how pip freezes an editable path install
EDITABLE_PATH_REQUIREMENT = re.compile(rf"^-e\s+(?P<path>\S*/{_PKG})/?\s*$")
#: `name==X.Y.Z` — a version pin
VERSION_REQUIREMENT = re.compile(rf"^{_PKG}\s*==\s*(?P<version>\d+\.\d+\.\d+)\s*$")


def pip_name(name: str) -> str:
    """A package name as pip normalises it: lowercase, `_` to `-`. Spelled
    seven times before (audit 2026-10-15)."""
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


class GitError(RuntimeError):
    """git could not be run, or failed inside a repository."""


class AmbiguousArea(argparse.ArgumentTypeError):
    """A bare area name more than one area carries (`x` for `01-x` and
    `02-x`). An ArgumentTypeError, so argparse prints its sentence where a
    command parses the area with `type=area_path`; a command that calls
    `area_path` itself refuses with it."""


def area_path(arg: str) -> Path:
    """The area a command argument names: a directory as given, else the
    bare name as `labkit-init exp` prints it — `01-<name>` or `<name>`
    (`areas_named`) — under `experiments/` of the working directory or of
    its repository. Returns the argument unchanged when nothing matches,
    so the caller's "no such area" still speaks (2026-10-07: two agents
    passed `01-docs-per-case` to code-check and were refused). Raises
    AmbiguousArea naming every candidate when more than one area matches:
    "no such area" for a name that exists twice sent the reader looking
    for a missing one (review, 2026-10-20)."""
    given = Path(arg)
    if given.is_dir() or given.is_absolute() or "/" in arg:
        return given
    hits: set[Path] = set()
    for base in {Path.cwd(), git_root(Path.cwd()) or Path.cwd()}:
        hits.update(p.resolve() for p in areas_named(base / EXPERIMENTS, arg))
    if len(hits) > 1:
        names = ", ".join(sorted(shown(h, Path.cwd()) for h in hits))
        raise AmbiguousArea(
            f"area name {arg!r} matches {len(hits)} areas: {names} — give the "
            f"one you mean by its path or its numbered name"
        )
    return hits.pop() if hits else given


def adopt_command(protocol: Path, run_id: str = "<run_id>") -> str:
    """The `protocol-fill … --from-run` line that adopts RUN_ID into PROTOCOL,
    the protocol named as the working directory reaches it (`shown`): a bare
    file name failed from the repo root, where agents run the scripts
    (count probe, 2026-10-20)."""
    return f"protocol-fill {shown(protocol, Path.cwd())} --from-run {run_id}"


def withdraw_command(protocol: Path) -> str:
    """The `protocol-fill … --withdraw` line that withdraws PROTOCOL's result
    declaration, the protocol named as the working directory reaches it —
    the way to replace a declaration: withdraw, audit, adopt."""
    return f'protocol-fill {shown(protocol, Path.cwd())} --withdraw --why "<why>"'


def measure_command(area: Path) -> str:
    """The line that measures AREA: its stamped `scripts/01_measure.py` (every
    skeleton has one) with the repo's interpreter, the script as the working
    directory reaches it; the script opens its run through runlog."""
    script = shown(area / "scripts" / "01_measure.py", Path.cwd())
    return f".venv/bin/python {shlex.quote(script)}"


def next_after_run(protocol: Path, run_id: str) -> str:
    """The steps after a measurement of PROTOCOL, in the order the gates
    accept them: finalize, the analysis audit and its decisions, the
    Conclusion, then the adoption of RUN_ID — what every skeleton prints
    at the end of a run. Printing the adoption alone sent agents into its
    refusal (audit 2026-10-27, third, I3)."""
    area = protocol.parent
    return (
        f"next: finalize {shlex.quote(shown(area, Path.cwd()))} · "
        f"{audit_command(area, '--mode', 'analysis', protocol=protocol)}, then "
        f"decide its findings · write the Conclusion · then "
        f"{adopt_command(protocol, run_id)} (writes Recorded results, [result] run "
        f"and the run entry from metrics.json)"
    )


def report_review_command(area: Path, report: Path, protocol: Path) -> str:
    """The command that reviews REPORT on AREA, paths as seen from the
    working directory; `--protocol` only when the area has more than one."""
    return audit_command(
        area, "--report-review", shown(report, Path.cwd()), protocol=protocol
    )


def into_command(protocol: Path, report: Path) -> str:
    """The `protocol-fill PROTOCOL --into REPORT` line that writes PROTOCOL's
    result block into REPORT, both as the working directory reaches them
    (`shown`), shell-quoted: a protocol named relative to the report and a
    report relative to the repo ran from neither (audit 2026-10-27, S2)."""
    here = Path.cwd()
    return shlex.join(
        ["protocol-fill", shown(protocol, here), "--into", shown(report, here)]
    )


def handover_command(protocol: Path, report: str = "REPORT.md") -> str:
    """The `protocol-fill … --handover` line for PROTOCOL into REPORT, its
    why and tried as placeholders; it runs no model."""
    return (
        f"protocol-fill {shlex.quote(shown(protocol, Path.cwd()))} --handover "
        f'--why "<what blocks>" --tried "<what you tried>" --into {shlex.quote(report)}'
    )


def audit_command(
    area: Path, *step: str, protocol: Path | None = None, base: Path | None = None
) -> str:
    """The `labkit-audit` line for STEP on AREA, paths as BASE (the working
    directory by default) reaches them, every word shell-quoted, and
    `--protocol PROTOCOL` when the area holds more than one protocol — the
    command refuses to choose there (`the_protocol`). The one builder of
    every printed audit step; STEP's words are given as BASE reaches them.
    Without PROTOCOL in such an area the line names none, and the command
    as printed refuses with the choice it needs."""
    here = base or Path.cwd()
    words = ["labkit-audit", shown(area, here), *step]
    if protocol is not None and len(area_protocols(area)) > 1:
        words += ["--protocol", shown(protocol, here)]
    return shlex.join(words)


def decide_command(
    area: Path,
    n: int,
    status: str,
    reason: str,
    record: str,
    *,
    effect: str | None = None,
    protocol: Path | None = None,
    base: Path | None = None,
) -> str:
    """The `labkit-audit … --decide N STATUS "REASON" [--effect EFFECT]
    --record RECORD` line (`audit_command`): REASON in double quotes as
    given — a placeholder the reader replaces (`<why>`), never a ready-made
    reason —, EFFECT as given, RECORD as the caller shows it. The one
    builder of a printed decision."""
    effect_words = f" --effect {effect}" if effect is not None else ""
    return (
        f"{audit_command(area, protocol=protocol, base=base)} --decide {n} "
        f'{status} "{reason}"{effect_words} --record {shlex.quote(record)}'
    )


def shown(path: Path, base: Path) -> str:
    """PATH as a report line, a bundle header or a refusal names it: relative
    to BASE when it lies below it, else absolute; both resolved first (on
    macOS /var is /private/var, and a comparison of one resolved and one
    unresolved path found nothing below), `/`-separated. The key a stamp
    hashes is its own rule (`scope_sha._key`), not a display."""
    p, b = path.resolve(), base.resolve()
    return p.relative_to(b).as_posix() if p.is_relative_to(b) else p.as_posix()


def no_such_area(area: Path) -> str:
    """The sentence for an area path that is not a directory. A relative
    path resolves against the working directory, so the sentence names it
    (2026-10-07: an agent called code-check from inside the area with the
    repo-relative path and tried four spellings)."""
    where = "" if area.is_absolute() else f" (relative to {Path.cwd()})"
    return (
        f"no such area: {area}{where} — give the area's path or its name "
        f"as `labkit-init exp` printed it (01-<name>)"
    )


#: an area's directory name as `labkit-init exp` prints it: `NN-<slug>`
AREA_NAME = re.compile(r"^(\d+)-(.+)$")


def split_area_name(name: str) -> tuple[str | None, str]:
    """(number, slug) of an area directory name; (None, name) when it
    carries no `NN-` prefix. Four regexes said this before (audit 2026-10-15)."""
    m = AREA_NAME.match(name)
    return (m.group(1), m.group(2)) if m else (None, name)


#: the folder of a lab repo that holds its experiment areas
EXPERIMENTS = "experiments"


def file_url_path(url: str) -> Path | None:
    """The local path a `file://` URL names — also after `git+`, as pip and
    a requirement pin write it —; None for any other URL. One reading for a
    lock's ref, an editable install and a pin's source (audit 2026-10-28,
    H8)."""
    plain = url.removeprefix("git+")
    return Path(plain.removeprefix("file://")) if plain.startswith("file://") else None


def areas_named(experiments: Path, name: str) -> list[Path]:
    """Every area directory under EXPERIMENTS that the bare NAME names,
    sorted: the one called NAME and every `NN-<NAME>` (`AREA_NAME`) — the
    one rule of which areas a name matches, for a command's argument
    (`area_path`, NAME as given) and for the area `labkit-init exp` stamps,
    promotes or restamps (`scaffold.existing_area`, NAME spelled as its
    slug first). [] when EXPERIMENTS is no directory. Read by the grammar,
    not a glob: `[0-9]*-<name>` also took `02-count-docs` for `docs`
    (audit 2026-10-27)."""
    if not experiments.is_dir():
        return []
    return sorted(
        p
        for p in experiments.iterdir()
        if p.is_dir() and name in (p.name, split_area_name(p.name)[1])
    )


#: the one name shape of a protocol file, as a glob and as a pattern
PROTOCOL_GLOB = "PROTOCOL-*.md"
PROTOCOL_NAME = re.compile(r"^PROTOCOL-[^/]+\.md$")
#: directories a repo-wide scan never reads: nothing under them is a living
#: file of the lab — a protocol copied into `runs/<id>/` or shipped in
#: `.venv/` is a record or a package, not a second protocol (audit
#: 2026-10-15: four scans, one of them skipped these, three did not)
SKIP_DIRS = frozenset({".git", ".venv", "node_modules", "__pycache__", "runs", "data"})


def repo_protocols(root: Path) -> list[Path]:
    """Every protocol anywhere under ROOT, outside SKIP_DIRS, sorted — the
    repo-wide form of `area_protocols`."""
    return sorted(
        p
        for p in root.rglob(PROTOCOL_GLOB)
        if not SKIP_DIRS & set(p.relative_to(root).parts)
    )


def lab_root(start: Path) -> Path | None:
    """The nearest directory, START or above, holding `models.toml` — where
    a lab repo's layout starts for the scaffolder and the model backend;
    None when none does. One rule: `labkit-init exp` asked for
    `experiments/` too and `llm` for `models.toml` alone (audit 2026-10-15)."""
    here = start.resolve()
    for d in (here, *here.parents):
        if (d / "models.toml").is_file():
            return d
    return None


def area_protocols(area: Path) -> list[Path]:
    """Every protocol in the area (`PROTOCOL-*.md` directly in it),
    lexicographic — a list, not a first hit.

    The series rule gives every follow-up its own `PROTOCOL-s<N>-<slug>.md`,
    so an area legitimately holds many. Returning `sorted(...)[0]` picked
    one of them wordlessly, and lexicographic order is not temporal order:
    in an area running s1..s13 the pick was always s1. A green check against
    the wrong protocol is worse than no check, so the caller must choose
    (2026-09-26).
    """
    return sorted(area.glob(PROTOCOL_GLOB))


def indexed_files(repo: Path) -> list[Path]:
    """Every file git's index holds under REPO, outside SKIP_DIRS, sorted,
    as resolved paths — what the next commit carries (`git ls-files
    --cached`): a file deleted only in the working tree is still here, one
    only in the tree is not. Raises RuntimeError when git fails."""
    r = git_run(["ls-files", "-z", "--cached"], repo)
    if r.returncode != 0:
        raise RuntimeError(f"git ls-files failed in {repo}: {r.stderr.strip()}")
    root = repo.resolve()
    return sorted(
        root / rel
        for rel in r.stdout.split("\0")
        if rel and not SKIP_DIRS & set(Path(rel).parts)
    )


def indexed_protocols(repo: Path) -> list[Path]:
    """Every protocol git's index holds under REPO (`indexed_files`),
    sorted, as resolved paths — the commit's form of `repo_protocols`."""
    return [p for p in indexed_files(repo) if PROTOCOL_NAME.match(p.name)]


#: the suffix of a report the gates hold (`report_hold.report_files`) and
#: a handover may write: exactly `.md`, so a handover never writes where
#: report-check would not look (audit 2026-10-27, third, S3)
REPORT_SUFFIX = ".md"


def protocol_link(path: Path, state: str) -> str:
    """The refusal of PATH, a protocol that is a symbolic link in STATE
    ("tree" or "index"). A protocol is a regular file: the tree's reader
    followed a link and the index's read the name it stores, so the stop
    and the commit judged different text."""
    return (
        f"{path}: a protocol must be a regular file, not a symbolic link (in the "
        f"{state}) — the stop would read the file it names and the commit the "
        "link itself; put the file there instead of the link"
    )


def protocol_links(
    repo: Path, protocols: list[Path], *, staged: bool
) -> dict[Path, str]:
    """Each of PROTOCOLS that is a symbolic link in the tree or, STAGED, in
    git's index (`indexed_links`, one listing), broken or not, → its refusal
    (`protocol_link`). Raises RuntimeError when git fails."""
    if staged:
        held = set(indexed_links(repo))
        return {p: protocol_link(p, "index") for p in protocols if own_path(p) in held}
    return {p: protocol_link(p, "tree") for p in protocols if p.is_symlink()}


def under_root(root: Path, path: Path) -> bool:
    """Does ROOT hold PATH (ROOT resolved, PATH at its own path,
    `own_path`)? A membership test for a gate that is given paths from
    anywhere — the stop hook's changed paths, a test's temporary area —
    and reads only those of its repo. A symbolic link is where it lies: a
    link in the repo to a file outside is held, a link outside to a file
    in the repo is not."""
    return own_path(path).is_relative_to(root.resolve())


def own_path(path: Path) -> Path:
    """PATH with its directory resolved and its own name kept: a symbolic
    link stays the link, where `resolve()` would give the file it names.
    The path git keeps an entry under, and the one a gate tests before it
    reads through a link (`report_hold.report_files`)."""
    return path.parent.resolve() / path.name


#: the revision `text_at` reads the index as
INDEX_REV = ""


def text_at(repo: Path, path: Path, rev: str = INDEX_REV) -> str | None:
    """PATH's content as git holds it at REV under REPO — the index when
    REV is INDEX_REV (`git show :path`, what a commit now would carry),
    else that revision's (`HEAD:path`: the last commit's). None when that
    state does not hold the file (untracked, staged as deleted, new since
    HEAD) or there is no such revision (an unborn branch). PATH must lie
    under REPO. The entry at PATH's own path (`own_path`): a link in the
    working tree is not followed, and a symbolic link git holds reads as
    the target it stores (`indexed_links` names those). The one reading of
    a file at a git state: the pre-commit's declaration, the citing report
    as the index holds it, the protocol as HEAD last committed it. Raises
    UnicodeDecodeError naming `REV:path` when the bytes are not UTF-8."""
    rel = own_path(path).relative_to(repo.resolve()).as_posix()
    try:
        r = git_run(["show", f"{rev}:{rel}"], repo)
    except UnicodeDecodeError as exc:
        raise not_text(exc, f"{rev}:{rel}") from exc
    return r.stdout if r.returncode == 0 else None


def state_text(repo: Path, path: Path, *, staged: bool) -> str | None:
    """PATH's own entry as a gate's state holds it: the index when STAGED
    (`text_at`), else the working tree — in both a file's content, and for
    a symbolic link the target it stores, not the file it points to; None
    when that state does not hold the file. The one reading of a file in
    "the tree or the index" (report-check, the handover, the hooks). Raises
    UnicodeDecodeError naming PATH when the bytes are not UTF-8."""
    if staged:
        return text_at(repo, path)
    if path.is_symlink():
        return os.readlink(path)
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise not_text(exc, str(path)) from exc


def not_text(exc: UnicodeDecodeError, where: str) -> UnicodeDecodeError:
    """EXC with "in WHERE" appended to its reason: still a UnicodeError for
    every caller that catches one, and its sentence names the file that did
    not decode. WHERE is that file's name, or a sentence that locates it
    and may carry the way out (`provenance.describe_data`)."""
    return UnicodeDecodeError(
        exc.encoding, exc.object, exc.start, exc.end, f"{exc.reason} in {where}"
    )


#: git's mode of a symbolic link (`git ls-files --stage`)
LINK_MODE = "120000"


def indexed_links(repo: Path) -> dict[Path, str]:
    """Every symbolic link git's index holds under REPO, as its own path
    (under REPO resolved) → the target it stores, as stored (`../x.md`, an
    absolute path) — what a commit now would carry where `indexed_files`
    names a file. One listing of the index and one read per link. Raises
    RuntimeError when git fails."""
    r = git_run(["ls-files", "--stage", "-z"], repo)
    if r.returncode != 0:
        raise RuntimeError(f"git ls-files --stage failed in {repo}: {r.stderr.strip()}")
    root = repo.resolve()
    out: dict[Path, str] = {}
    for entry in r.stdout.split("\0"):
        meta, _, rel = entry.partition("\t")
        if not rel or meta.split(" ")[0] != LINK_MODE:
            continue
        out[root / rel] = blob_text(repo, meta.split(" ")[1])
    return out


def indexed_blobs(repo: Path, folder: Path) -> dict[Path, str]:
    """Index files below FOLDER and their blob ids, without decoding bytes.

    Raise GitError for an unmerged entry or a failed listing. Binary or
    malformed evidence can therefore be fingerprinted without parsing it.
    """
    rel = own_path(folder).relative_to(repo.resolve()).as_posix()
    result = git_run(["ls-files", "--stage", "-z", "--", rel], repo)
    if result.returncode:
        raise GitError(f"git ls-files in {repo}: {result.stderr.strip()}")
    out: dict[Path, str] = {}
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        meta, name = entry.split("\t", 1)
        mode, sha, stage = meta.split()
        if stage != "0" or mode == LINK_MODE:
            raise GitError(f"{name}: evidence must be a regular, merged index file")
        out[repo.resolve() / name] = sha
    return out


def blob_text(repo: Path, sha: str) -> str:
    """The text of blob SHA in REPO's object store (`git cat-file blob`).
    Raises RuntimeError when git cannot read it."""
    blob = git_run(["cat-file", "blob", sha], repo)
    if blob.returncode != 0:
        raise RuntimeError(
            f"git cat-file blob {sha} failed in {repo}: {blob.stderr.strip()}"
        )
    return blob.stdout


def first_added(repo: Path, path: Path) -> tuple[str, Path] | None:
    """(commit, path then): the one commit under REPO that added PATH,
    followed back through renames (`git log --follow`), and the path PATH
    had there. None when that is not one commit: PATH never committed,
    deleted and added again (its history holds two beginnings), or a
    shallow clone (its oldest commit shows every file as added). PATH must
    lie under REPO. Raises RuntimeError when git fails."""
    if not head_sha(repo):
        return None
    shallow = git_run(["rev-parse", "--is-shallow-repository"], repo)
    if shallow.returncode != 0 or shallow.stdout.strip() != "false":
        return None
    rel = path.resolve().relative_to(repo.resolve()).as_posix()
    args = ["log", "--follow", "--name-status", "--format=%x00%H", "--", rel]
    r = git_run(args, repo)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {r.stderr.strip()}")
    # one entry per commit, newest first: its hash, then the status line
    # of the followed file, tab-separated (`A\tpath`, `R100\told\tnew`);
    # a path git quotes (unusual characters) reads nowhere — no evidence
    entries = []
    for chunk in r.stdout.split("\0"):
        lines = [ln for ln in chunk.splitlines() if ln]
        if lines:
            entries.append((lines[0], lines[1].split("\t") if len(lines) > 1 else []))
    statuses = [fields[0][:1] for _, fields in entries if fields]
    if not entries or statuses.count("A") != 1 or "D" in statuses:
        return None
    commit, fields = entries[-1]
    if len(fields) != 2 or fields[0] != "A":
        return None
    return commit, repo / fields[1]


#: the options a run's patch is written with: every file in full (binary
#: ones too), whatever the user's diff settings say — so it applies again
TREE_PATCH_ARGS = (
    "diff",
    "--binary",
    "--full-index",
    "--no-color",
    "--no-ext-diff",
    "--no-textconv",
    "--no-relative",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "HEAD",
)
_COLOR = re.compile(r"\x1b\[[0-9;]*m")
_PREFIXED = re.compile(r"^diff --git [a-z]/", re.M)


def tree_patch(cwd: Path) -> str:
    """The working tree's tracked changes against HEAD as a patch that
    applies again (TREE_PATCH_ARGS), unstripped — what a run keeps as its
    `uncommitted.patch`. Raises GitError when git fails."""
    r = git_run(list(TREE_PATCH_ARGS), cwd)
    if r.returncode != 0:
        raise GitError(f"git diff HEAD in {cwd}: {r.stderr.strip()}")
    return r.stdout


def blobs_then(
    repo: Path, commit: str, patch: str, paths: list[Path]
) -> dict[Path, str | None]:
    """The blob id each of PATHS had in the working tree a run started
    from: COMMIT's tree with the part of PATCH (the run's `git diff HEAD`,
    "" when its tree was clean) that touches PATHS applied — read in a
    temporary index, the repository's own index untouched; the blobs land
    in the object store, so `git cat-file blob <id>` restores one. A patch
    written before TREE_PATCH_ARGS is read as far as it can be: colour
    codes dropped, hunk lengths recounted and a hunk not held to the file's
    end (stripping cut its last blank context lines), its path prefix taken
    as written; a last added line's trailing whitespace the stripping took
    is lost and reads as a change. None for a path that tree
    lacks: untracked when the run started, or not yet there. PATHS lie in
    REPO's own tree. Raises GitError when COMMIT is no commit of REPO or
    the part of PATCH for PATHS does not apply to it."""
    rels = {p.resolve().relative_to(repo.resolve()).as_posix(): p for p in paths}
    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        steps: list[tuple[list[str], str | None]] = [(["read-tree", commit], None)]
        if patch.strip():
            plain = _COLOR.sub("", patch).rstrip("\n") + "\n"
            strip = "-p1" if _PREFIXED.search(plain) else "-p0"
            includes = [f"--include={rel}" for rel in rels]
            steps.append(
                (
                    [
                        "-c",
                        "apply.whitespace=nowarn",
                        "apply",
                        "--cached",
                        "--recount",
                        "--unidiff-zero",
                        strip,
                        *includes,
                        "-",
                    ],
                    plain,
                )
            )
        steps.append((["ls-files", "-s", "-z", "--", *rels], None))
        listed = ""
        for args, stdin in steps:
            r = git_run(args, repo, env=env, stdin=stdin)
            if r.returncode != 0:
                step = args[2] if args[0] == "-c" else args[0]
                raise GitError(f"git {step} at {commit[:12]}: {r.stderr.strip()}")
            listed = r.stdout
    found: dict[Path, str | None] = dict.fromkeys(rels.values())
    for entry in listed.split("\0"):
        if entry:
            meta, _, rel = entry.partition("\t")
            if rel in rels:
                found[rels[rel]] = meta.split()[1]
    return found


def blobs_now(repo: Path, paths: list[Path]) -> dict[Path, str]:
    """The blob id each of PATHS (existing files under REPO) would have if
    added now (`git hash-object`, the repository's filters applied as
    `git add` applies them). Raises GitError when git fails."""
    if not paths:
        return {}
    r = git_run(["hash-object", "--", *(str(p) for p in paths)], repo)
    if r.returncode != 0:
        raise GitError(f"git hash-object in {repo}: {r.stderr.strip()}")
    return dict(zip(paths, r.stdout.split(), strict=True))


def find_area(
    path: Path, stop: Path | None = None, protocols: list[Path] | None = None
) -> Path | None:
    """The nearest directory above PATH holding a PROTOCOL-*.md, or None;
    the walk ends at STOP (the repo root) without leaving it. PROTOCOLS,
    when given (resolved paths, such as `indexed_protocols`), are the
    protocols that make a directory an area instead of the working tree's."""
    homes = None if protocols is None else {p.parent for p in protocols}
    for d in path.resolve().parents:
        if (d in homes) if homes is not None else area_protocols(d):
            return d
        if stop is not None and d == stop.resolve():
            return None
    return None


def areas_of(
    paths: list[Path], stop: Path, protocols: list[Path] | None = None
) -> list[Path]:
    """The areas PATHS touch, each once, in path order: the nearest area
    above each path (`find_area`, the walk ends at STOP without leaving it);
    a path under no area contributes nothing. The one answer for every gate
    that holds "the areas this session worked in" — the stop's reported
    numbers and the commit's undecided findings — so the two cannot drift
    apart in what they call an area. PROTOCOLS as in `find_area`."""
    out: list[Path] = []
    for path in paths:
        area = find_area(path, stop=stop, protocols=protocols)
        if area is not None and area not in out:
            out.append(area)
    return out


def git_root(path: Path) -> Path | None:
    """The nearest ancestor (or `path`) holding `.git`; None outside a repo."""
    base = path if path.is_dir() else path.parent
    for parent in [base.resolve(), *base.resolve().parents]:
        if (parent / ".git").exists():
            return parent
    return None


def layout_root(path: Path) -> Path:
    """Where an area's repo layout starts: the git root, else the nearest
    ancestor with `CLAUDE.md` or `tests/` (a freshly stamped tree before
    `git init`), else `path` itself."""
    root = git_root(path)
    if root is not None:
        return root
    base = (path if path.is_dir() else path.parent).resolve()  # "." has no parents
    for parent in [base, *base.parents]:
        if (parent / "CLAUDE.md").is_file() or (parent / "tests").is_dir():
            return parent
    return base


def git_run(
    args: list[str],
    cwd: Path,
    timeout: float = GIT_TIMEOUT_S,
    env: Mapping[str, str] | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run git, ENV added to the environment and STDIN given; the caller
    reads the exit code. Raises GitError only when git itself cannot run
    (missing binary, timeout)."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **env} if env else None,
            input=stdin,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError(f"git {' '.join(args)} in {cwd}: {exc}") from exc


def status_entries(repo: Path, pathspec: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    """`git status --porcelain` under REPO (PATHSPEC narrows it), untracked
    files included, as (XY, path) — NUL-separated (`-z`): the text form
    quotes a name with a non-ASCII character
    (`"notes/messung/gr\303\266\303\237e.md"`), which was then no file and
    never checked (audit 2026-10-15). A rename or copy comes as its new path
    with the old one dropped. Raises RuntimeError when git fails."""
    return [(xy, path) for xy, path, _ in _status_records(repo, pathspec)]


def touched_paths(repo: Path) -> list[Path]:
    """Every path `git status` names under REPO: modified, added, untracked,
    deleted, and both sides of a rename — what a gate holding "the areas
    this work touched" reads, since a file removed from an area changes it
    as an edit does. Raises RuntimeError when git fails."""
    out: list[Path] = []
    for _, path, source in _status_records(repo, ()):
        out.append(repo / path)
        if source is not None:
            out.append(repo / source)
    return out


def head_sha(repo: Path, *, short: bool = False) -> str:
    """HEAD's commit under REPO — git's short form with SHORT —, "" outside
    a repository and before the first commit (an unborn HEAD is a state,
    not an error). Raises GitError only when git cannot run."""
    if git_root(repo) is None:
        return ""
    r = git_run(
        ["rev-parse", "--verify", "-q", *(["--short"] if short else []), "HEAD"], repo
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def tree_dirty(repo: Path, *, untracked: bool = True) -> bool:
    """Does the working tree under REPO differ from HEAD (`git status
    --porcelain` names anything)? UNTRACKED counts files git does not know
    — a file nobody committed may have been run —, False counts tracked
    files only. False outside a repository; a git that fails inside one
    raises GitError (it used to read as clean)."""
    args = ["status", "--porcelain", *([] if untracked else ["--untracked-files=no"])]
    return bool(git(args, repo))


def git_dir_path(repo: Path, name: str, *, common: bool = False) -> Path | None:
    """NAME inside REPO's git directory — this worktree's own (each worktree
    has its own HEAD), or with COMMON the main repository's, which every
    worktree shares —; None outside a repository git takes. Local, never
    committed: where labkit keeps the audit locks, the stop base, the
    session log, the attempt journals' copies (`attempts.journal_copy`) and
    the evidence copies beside them (`attempts.evidence_copy`)."""
    r = git_run(["rev-parse", "--git-common-dir" if common else "--git-dir"], repo)
    if r.returncode != 0:
        return None
    d = Path(r.stdout.strip())
    return (d if d.is_absolute() else repo / d) / name


def files_at(repo: Path, folder: Path, rev: str = INDEX_REV) -> set[str] | None:
    """The files REV holds under FOLDER (inside REPO), relative to FOLDER,
    `/`-separated — the index when REV is INDEX_REV (`ls-files --cached`,
    what a commit now would carry), else that revision's tree (`ls-tree
    -r`). None when there is no such state: REPO is no repository git takes
    (a bare `.git` directory), or REV names no revision (an unborn HEAD) —
    told by git's exit codes, not its words. Raises RuntimeError when git
    fails otherwise."""
    if git_run(["rev-parse", "--git-dir"], repo).returncode != 0:
        return None
    if (
        rev != INDEX_REV
        and git_run(["rev-parse", "--verify", "-q", f"{rev}^{{tree}}"], repo).returncode
        != 0
    ):
        return None
    rel = folder.resolve().relative_to(repo.resolve()).as_posix()
    args = (
        ["ls-files", "-z", "--cached", "--", rel]
        if rev == INDEX_REV
        else ["ls-tree", "-r", "-z", "--name-only", rev, "--", rel]
    )
    r = git_run(args, repo)
    if r.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args[:2])} failed in {repo}: {r.stderr.strip()}"
        )
    return {p[len(rel) + 1 :] for p in r.stdout.split("\0") if p.startswith(rel + "/")}


def branch_refs(repo: Path) -> list[str]:
    """Every branch REPO's repository knows, local and remote-tracking, as
    full ref names (`refs/heads/main`, `refs/remotes/origin/x`) — a
    symbolic ref (`refs/remotes/origin/HEAD`) left out, it names one of the
    others. Only what this clone holds: a branch never fetched is not
    there. [] outside a repository; GitError when git fails inside one."""
    out = git(
        [
            "for-each-ref",
            "--format=%(if)%(symref)%(then)%(else)%(refname)%(end)",
            "refs/heads",
            "refs/remotes",
        ],
        repo,
    )
    return [ref for ref in (out or "").splitlines() if ref]


def worktree_roots(repo: Path) -> list[Path]:
    """The working directory of every worktree of REPO's repository, REPO's
    own among them, as `git worktree list` names them — a directory removed
    without `git worktree remove` is still named (git calls it prunable),
    so the caller checks it exists. [] outside a repository; GitError when
    git fails inside one."""
    out = git(["worktree", "list", "--porcelain", "-z"], repo)
    return [
        Path(field.removeprefix("worktree "))
        for field in (out or "").split("\0")
        if field.startswith("worktree ")
    ]


def fork_point(repo: Path, base: str) -> str | None:
    """The newest commit BASE and HEAD share — BASE itself when HEAD grew
    from it — or None when git knows no common one (BASE unknown, or
    unrelated histories)."""
    r = git_run(["merge-base", base, "HEAD"], repo)
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


#: a commit as a record names it: the full sha, SHA-1 or SHA-256
FULL_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def commit_of(repo: Path, ref: str) -> str | None:
    """The commit REF (a tag, a branch, a sha) names under REPO, as its full
    sha; None when it names none. `--verify --quiet`: without them
    rev-parse echoes an unknown ref back on stdout instead of failing
    empty. The one "ref → commit" for the lab-pin check, a lock's ref and a
    pin's tag (audit 2026-10-27, third, S8). Raises GitError when git cannot
    run (REPO missing among them)."""
    r = git_run(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], repo)
    return r.stdout.strip() if r.returncode == 0 else None


def commit_known(repo: Path, commit: str) -> bool:
    """Does REPO hold COMMIT, a full sha, as a commit (`rev-parse --verify
    -q COMMIT^{commit}`)? False for a sha this clone never fetched or has
    pruned (a rewritten history, a shallow clone's cut), and for anything
    that is not a full sha: a branch name or a short sha would resolve to
    what it names now, not to what was recorded. Raises GitError only when
    git cannot run."""
    return (
        FULL_SHA.fullmatch(commit) is not None and commit_of(repo, commit) is not None
    )


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    """Is OLDER an ancestor of NEWER under REPO, or the same commit (`git
    merge-base --is-ancestor`)? Both must be commits REPO holds
    (`commit_known`). Raises RuntimeError when git fails."""
    args = ["merge-base", "--is-ancestor", older, newer]
    r = git_run(args, repo)
    if r.returncode not in (0, 1):
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {r.stderr.strip()}")
    return r.returncode == 0


def earliest_commits(repo: Path, commits: list[str]) -> list[str]:
    """The commits of COMMITS that no other of them precedes — none of the
    others is an ancestor of it (`is_ancestor`) — in COMMITS' order, each
    once. One on a linear history; one per branch where the history
    diverged (a rebase, an amend, a side branch), since git cannot say
    which of two commits came first when neither is an ancestor of the
    other. Every commit must be one REPO holds (`commit_known`). Raises
    RuntimeError when git fails."""
    distinct = list(dict.fromkeys(commits))
    earliest: list[str] = []  # the earliest of the commits seen so far
    for commit in distinct:
        if any(is_ancestor(repo, e, commit) for e in earliest):
            continue
        earliest = [e for e in earliest if not is_ancestor(repo, commit, e)]
        earliest.append(commit)
    return [c for c in distinct if c in earliest]


def paths_committed_since(repo: Path, base: str) -> list[Path]:
    """Every path a commit after BASE up to HEAD touched, under REPO:
    added, modified, deleted, and both sides of a rename (`--no-renames`
    names a rename as its deletion and its addition) — `touched_paths` for
    the commits, not the tree. BASE "" (begun before the first commit):
    every path HEAD holds. [] while HEAD is unborn. Raises RuntimeError
    when git fails."""
    if not head_sha(repo):
        return []
    args = (
        ["diff", "--name-only", "-z", "--no-renames", base, "HEAD"]
        if base
        else ["ls-tree", "-r", "-z", "--name-only", "HEAD"]
    )
    r = git_run(args, repo)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {r.stderr.strip()}")
    return [repo / p for p in r.stdout.split("\0") if p]


def head_before(repo: Path, when: datetime) -> str | None:
    """The commit HEAD's line stood on before WHEN (aware, or naive in
    local time), told by commit dates: the first parent of the oldest
    commit on HEAD's first-parent line whose committer date is at or after
    WHEN in whole seconds (`rev-list --since`) — HEAD itself when none is,
    "" when that oldest commit has no parent (every commit counts). None
    while HEAD is unborn. The date is the commit's own word: an amend or a
    rebase dates a commit anew, a set GIT_COMMITTER_DATE moves it. Raises
    RuntimeError when git fails."""
    head = head_sha(repo)
    if not head:
        return None
    args = ["rev-list", "--first-parent", f"--since=@{int(when.timestamp())}", "HEAD"]
    r = git_run(args, repo)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {r.stderr.strip()}")
    since = r.stdout.split()
    if not since:
        return head
    parent = git_run(["rev-parse", "--verify", "-q", f"{since[-1]}^1"], repo)
    return parent.stdout.strip() if parent.returncode == 0 else ""


def _status_records(
    repo: Path, pathspec: tuple[str, ...]
) -> list[tuple[str, str, str | None]]:
    """(XY, path, source of a rename or copy or None) per `git status`
    entry — the one parse behind `status_entries` and `touched_paths`."""
    r = git_run(
        ["status", "--porcelain", "-z", "--untracked-files=all", "--", *pathspec],
        repo,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git status failed in {repo}: {r.stderr.strip()}")
    entries = r.stdout.split("\0")
    out: list[tuple[str, str, str | None]] = []
    i = 0
    while i < len(entries):
        line = entries[i]
        i += 1
        if len(line) < 4:
            continue
        source = None
        if line[0] in "RC":
            source = entries[i]  # the entry after a rename or copy is its source
            i += 1
        out.append((line[:2], line[3:], source))
    return out


def git(args: list[str], cwd: Path, timeout: float = GIT_TIMEOUT_S) -> str | None:
    """git's stripped output; None when `cwd` is not inside a repository.

    Any other failure raises GitError with git's own message — an empty
    string here used to mean "clean" whether or not git had run.
    """
    if git_root(cwd) is None:
        return None
    r = git_run(args, cwd, timeout)
    if r.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} in {cwd} failed "
            f"(exit {r.returncode}): {r.stderr.strip()}"
        )
    return r.stdout.strip()


class ProtocolChoiceError(ValueError):
    """No protocol to hold the area to: none named and none or several there."""


def the_protocol(area: Path, protocol: Path | None) -> Path:
    """The protocol a command holds the area to: the named one, else the
    area's only one. Raises ProtocolChoiceError (the message says why and
    lists the candidates) when there is none, or several and none is named
    — a gate never guesses, and when the one it holds is a symbolic link
    (`protocol_link`). `choose_protocol` is the printing form."""
    if protocol is not None:
        if protocol.is_symlink():
            raise ProtocolChoiceError(protocol_link(protocol, "tree"))
        if not protocol.is_file():
            raise ProtocolChoiceError(f"no such protocol: {protocol}")
        return protocol
    protocols = area_protocols(area)
    if not protocols:
        raise ProtocolChoiceError(f"no PROTOCOL-*.md in {area}")
    if len(protocols) > 1:
        raise ProtocolChoiceError(
            f"{len(protocols)} protocols in {area} — name one with --protocol FILE:\n"
            + "\n".join(f"  {p}" for p in protocols)
        )
    if protocols[0].is_symlink():
        raise ProtocolChoiceError(protocol_link(protocols[0], "tree"))
    return protocols[0]


def choose_protocol(area: Path, protocol: Path | None, tool: str) -> Path | None:
    """`the_protocol` for a command line: says why on stderr
    (`console.refuse`, prefixed with `tool`) and returns None instead of raising."""
    try:
        return the_protocol(area, protocol)
    except ProtocolChoiceError as exc:
        console.refuse(tool, str(exc))
        return None
