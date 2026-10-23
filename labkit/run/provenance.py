"""provenance — what a run records about where it came from.

The git state at start and end, the environment and its lock (pins, VCS
refs, drift between the lock and what is installed), the models resolved,
the data files described (path, digest, rows, ids) with the leakage check
across splits and control roles, and the script and untracked sources
snapshotted into the run directory. `runlog.Run` calls these when it
creates a run; they read the repo and the files and write only into the
run directory they are handed.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
import json
import re
import sys
from pathlib import Path

from labkit.formats import jsonl, repo
from labkit.formats.files import write_atomic_bytes
from labkit.formats.scope_sha import (
    DIGEST_CHARS,
    digest,
    file_digest,
    tree_digest,
)
from labkit.formats.runs import (
    DIRTY_MARK,
    NO_GIT,
    RECORD_SHA_CHARS,
    recorded_path,
)


SPLIT_KEYS = ("train", "dev", "test")


#: Roles for the leakage check beyond splits (2026-10-05, three audits in
#: three repos): a control set — anchors, gates, placebos — must share no id
#: with the measured set, or the gate and the measured arm hold the same
#: data point. Matched on the first `_`/`-` segment of the data key.
CONTROL_ROLES = (
    "anchor",
    "anchors",
    "gate",
    "gates",
    "placebo",
    "placebos",
    "control",
    "controls",
    "calibration",
)


MEASURED_ROLES = (
    *SPLIT_KEYS,
    "items",
    "measured",
    "cases",
    "prepared",
    "pairs",
    "pool",
)


def git_head(cwd: Path, short: bool = False) -> str:
    """HEAD's commit, "" outside a repo or before the first commit (an
    unborn HEAD is a state, not an error)."""
    if repo.git_root(cwd) is None:
        return ""
    r = repo.git_run(["rev-parse", *(["--short"] if short else []), "HEAD"], cwd)
    return r.stdout.strip() if r.returncode == 0 else ""


def git_state(cwd: Path, untracked: bool = True) -> str:
    """HEAD's short commit, `+dirty` when the tree differs from it.

    `untracked=True` (the state at start) counts untracked files too: a file
    git does not know may have been run. `untracked=False` (the state at the
    end) counts tracked files only — the run's own products (`runs/<id>/`,
    `output/`, `runs.tsv`) are untracked until committed, so every finished
    run read `+dirty` and the index column said nothing (74 of 74 rows in
    one lab repo; a cloud agent reported "beae3bf+dirty but the patch is
    empty", 2026-10-13)."""
    rev = git_head(cwd, short=True)
    if not rev:
        return NO_GIT
    args = ["status", "--porcelain"] + ([] if untracked else ["--untracked-files=no"])
    dirty = repo.git(args, cwd)
    return f"{rev}{DIRTY_MARK if dirty else ''}"


def parse_lock(lock: Path) -> dict[str, str | None]:
    """requirements.lock -> {package: version}. None = pinned without a version.

    URL pins (`name @ https://...`, e.g. spaCy models) carry no `==` version;
    they count as pinned-any rather than as drift. Git pins with an explicit
    ref are the exception: `parse_vcs_pins` reads them and `lock_drift`
    compares them by commit.
    """
    out: dict[str, str | None] = {}
    for raw in lock.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        name = repo.requirement_name(line)  # the one grammar of a pin line
        if name is None:
            continue
        if _EDITABLE_PIN.match(line) or "==" not in line:
            out[name] = None  # a VCS, editable or URL pin: no version to compare
        else:
            out[name] = line.partition("==")[2].strip()
    return out


# A VCS pin names a ref, not a version — `labkit @ git+file:///...@v0.14.0`.
# The version comparison in `lock_drift` cannot see it, and counting it as
# pinned-any hid exactly the package that changes most often (2026-09-15:
# installed labkit was two minor versions behind the lock, drift said 0 —
# and the pinned tag did not even exist in the source repo).
_VCS_PIN = repo.VCS_REQUIREMENT


# An editable install freezes as `-e git+<url>@<commit>#egg=<name>`: pip
# reads the commit from the source checkout. Unread, it counted as "installed
# but not in the lock" — a lock written by `pip freeze` seconds earlier in the
# same venv reported drift on every run (usability probe 2026-10-07, 6 of 6).
_EDITABLE_PIN = repo.EDITABLE_REQUIREMENT


_HEX_REF = re.compile(r"^[0-9a-f]{7,40}$")


def parse_vcs_pins(lock: Path) -> dict[str, tuple[str, str]]:
    """Git pins that carry an explicit ref: {package: (url, ref)}."""
    out: dict[str, tuple[str, str]] = {}
    for raw in lock.read_text(encoding="utf-8").splitlines():
        m = _VCS_PIN.match(raw.strip()) or _EDITABLE_PIN.match(raw.strip())
        if m and m.group("ref"):
            out[repo.pip_name(m.group("name"))] = (
                m.group("url"),
                m.group("ref"),
            )
    return out


def resolve_ref(url: str, ref: str) -> str | None:
    """The commit a lock ref points at — None when unknowable offline.

    A hex ref is its own answer. A tag/branch on a file:// URL is resolved
    against the local repo; an unresolvable ref returns "" — a lock that
    names a ref which does not exist is uninstallable, and that IS drift
    (2026-09-15: the lock pinned v0.15.0, the repo's tags stopped at
    v0.14.0). Remote URLs are not fetched: a check that needs the network
    would fire on every offline run, and a check that always fires is a
    check nobody reads.
    """
    if _HEX_REF.match(ref.lower()):
        return ref.lower()
    if url.startswith("file://"):
        # --verify: without it, rev-parse ECHOES an unknown ref back on
        # stdout instead of failing empty.
        r = repo.git_run(
            ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], Path(url[7:])
        )
        return r.stdout.strip().lower() if r.returncode == 0 else ""
    return None


def _direct_url_commit(dist: importlib.metadata.Distribution) -> str | None:
    """The commit the installed code stands at, if knowable.

    A VCS install: the commit pip recorded (direct_url.json). An editable
    install from a local checkout: that checkout's HEAD now — its code is the
    working tree, so the install-time commit says nothing. Uncommitted edits
    in that checkout are not seen.
    """
    try:
        raw = dist.read_text("direct_url.json")
        info = json.loads(raw) if raw else None
    except (AttributeError, TypeError, ValueError, OSError):
        return None
    if not isinstance(info, dict):
        return None
    vcs = info.get("vcs_info")
    if isinstance(vcs, dict) and isinstance(vcs.get("commit_id"), str):
        return vcs["commit_id"].lower()
    url = info.get("url")
    editable = isinstance(info.get("dir_info"), dict) and info["dir_info"].get(
        "editable"
    )
    if editable and isinstance(url, str) and url.startswith("file://"):
        return checkout_head(Path(url.removeprefix("file://")))
    return None


def checkout_head(path: Path) -> str | None:
    """HEAD of the git checkout at `path`; None when it is none."""
    try:
        r = repo.git_run(["rev-parse", "HEAD"], path)
    except repo.GitError:
        return None
    return r.stdout.strip().lower() if r.returncode == 0 else None


def vcs_mismatch(url: str, ref: str, installed_commit: str | None) -> bool:
    """Does the installed commit disagree with the lock's git ref?"""
    want = resolve_ref(url, ref)
    if want is None:
        return False  # remote tag/branch: unverifiable offline, pinned-any
    if not want:
        return True  # ref does not resolve locally: lock is uninstallable
    if not installed_commit:
        return True  # pinned to a commit, installed from something else
    return not (installed_commit.startswith(want) or want.startswith(installed_commit))


# `pip freeze` omits its own bootstrapping packages, so they are never in the
# lock. Counting them would make drift permanently >= 1 — and a check that
# always fires is a check nobody reads. The exclusion must apply to BOTH sides:
# some pip versions do write setuptools into the freeze, and filtering it only
# out of the installed set would report it as "pinned but missing" forever.
FREEZE_OMITS = {"pip", "setuptools", "wheel", "distribute", "pkg-resources"}


def lock_drift(lock: Path) -> int:
    """How many installed packages disagree with the lock?

    "Re-freeze after every install" is a rule that gets violated SILENTLY: the
    lock falls behind, and every run keeps recording a hash that describes an
    environment which does not exist. A rule that fails without a sound has to
    become a check. Git pins are compared by commit (direct_url.json vs the
    lock's ref), not skipped as pinned-any.
    """
    from importlib.metadata import distributions

    pinned = {n: v for n, v in parse_lock(lock).items() if n not in FREEZE_OMITS}
    vcs = {n: uv for n, uv in parse_vcs_pins(lock).items() if n not in FREEZE_OMITS}
    installed: dict[str, str] = {}
    vcs_commit: dict[str, str | None] = {}
    for dist in distributions():
        name = repo.pip_name(dist.metadata["Name"] or "")
        if name and name not in FREEZE_OMITS:
            installed[name] = dist.version
            if name in vcs:
                vcs_commit[name] = _direct_url_commit(dist)
    drift = sum(
        1
        for n, v in installed.items()
        if n not in pinned or (pinned[n] is not None and pinned[n] != v)
    )
    drift += sum(1 for n in pinned if n not in installed)
    drift += sum(
        1
        for n, (url, ref) in vcs.items()
        if n in installed and vcs_mismatch(url, ref, vcs_commit.get(n))
    )
    return drift


def env_state(cwd: Path) -> str:
    """Interpreter + fingerprint of the nearest requirements.lock, plus drift.

    Ties a run to an *environment*, not just a Python version: a changed lock
    changes the hash, so runs from different environments stay distinguishable
    in the run index. Records "unpinned" when no lock exists — visible, not silent.

    `drift:n` says how far the live environment has moved away from the lock.
    Only `drift:0` makes the hash a truthful description of what ran.
    """
    # NEVER .resolve() sys.executable: a venv's python is a symlink to the
    # base interpreter, so resolving it erases the very identity this field
    # records — every venv on the same pyenv base would look identical.
    # (Same trap that broke accessio's venv switch, 2026-08: it compared
    # resolved paths and concluded "already inside" for any caller sharing
    # the base. Use sys.prefix if you need to *test* for a venv.)
    exe = sys.executable
    for d in [cwd.resolve(), *cwd.resolve().parents]:
        lock = d / "requirements.lock"
        if lock.exists():
            h = file_digest(lock)[:DIGEST_CHARS]
            try:
                drift = lock_drift(lock)
            except Exception:  # never let bookkeeping break a run
                return f"{exe} | requirements.lock:{h} | drift:unknown"
            if drift:
                print(
                    f"runlog: WARNING — {drift} package(s) deviate from "
                    f"requirements.lock. `pip freeze > requirements.lock`, "
                    f"or this run's lock hash describes an environment "
                    f"that does not exist.",
                    file=sys.stderr,
                )
            return f"{exe} | requirements.lock:{h} | drift:{drift}"
    print(
        "runlog: WARNING — no requirements.lock found; env recorded as "
        "'unpinned'. `pip freeze > requirements.lock` to pin, or this run "
        "cannot claim the environment it ran in.",
        file=sys.stderr,
    )
    return f"{exe} | unpinned"


def resolve_models(config: dict) -> dict:
    """Alias -> resolved backend spec, for every model-naming config key.

    The alias is a pointer, the config must carry what it pointed to
    (2026-09-09, logic-epistemic-pairs: 25 run configs recorded only
    "model": "sonnet"; which weights answered was reconstructable solely by
    checking models.toml out at the run's commit). Keys considered: "model"
    and *_model, string values only. Best-effort: a failed resolution is
    recorded as a string, never raised — bookkeeping must not break a run.
    """
    out: dict[str, object] = {}
    for key, val in config.items():
        if (key == "model" or key.endswith("_model")) and isinstance(val, str):
            try:
                from labkit.run import llm

                out[val] = llm.resolve(val)
            except Exception as e:
                out[val] = f"unresolved: {e}"
    return out


def _visible_files(directory: Path) -> list[Path]:
    """Every regular file below `directory` that no hidden path component
    hides — `.DS_Store` once moved a mean by a whole document (2026-10-05)."""
    return sorted(
        p
        for p in directory.rglob("*")
        if p.is_file()
        and not any(part.startswith(".") for part in p.relative_to(directory).parts)
    )


def source_digest(path: Path) -> str:
    """The digest of a frozen source (`scope_sha.file_digest` for a file;
    until 2026-10-23 `sha256_file`, the one name in the digest family that
    said the algorithm, not the thing). Of a directory, over each visible file's
    relative path and content — so adding, removing, renaming or editing a
    file below it moves it (a directory source used to be unfreezable, and
    `finalize` then refused every run of the stamped compute skeleton)."""
    if path.is_dir():
        return tree_digest(
            (
                (f.relative_to(path).as_posix(), f.read_bytes())
                for f in _visible_files(path)
            ),
            chars=None,
        )
    return file_digest(path)


def _data_rows(path: Path) -> int:
    """Count non-empty lines, excluding the ``_meta`` header in .jsonl files;
    for a directory, its visible files.

    Uses a context manager (the old bare ``p.open()`` leaked file handles in
    tests).
    """
    if path.is_dir():
        return len(_visible_files(path))
    count = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            if path.suffix == ".jsonl":
                try:
                    # streamed: a count that must not refuse a file the
                    # leakage check (`_ids`) will name; home: jsonl.objects
                    if jsonl.is_meta(json.loads(line)):
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass
            count += 1
    return count


def _ids(path: Path) -> set | None:
    """Row ids of a .jsonl file, or None if they can't be read.

    None means "not checkable", never "no overlap" — the caller records the
    reason so a skipped leakage check stays visible.  The ``_meta`` header
    written by write_dataset() is not a data row and is skipped — without it,
    every standard-generated dataset would bail out on a missing "id" key and
    the leakage check would be silently skipped for exactly the files it is
    meant to protect.
    """
    if path.suffix != ".jsonl":
        return None
    ids = set()
    # a line that is not JSON names file and line (audit 2026-10-15), through
    # the one reader
    for _, row in jsonl.objects(path.read_text(encoding="utf-8"), str(path)):
        if jsonl.is_meta(row):
            continue
        if not isinstance(row, dict) or "id" not in row:
            return None
        ids.add(row["id"])
    return ids


def describe_data(paths: dict, base_dir: Path) -> dict:  # noqa: C901 complexity baseline 2026-10-08
    """path (as `runs.recorded_path` writes it, against BASE_DIR's repo) +
    sha256 + rows per split, and the leakage verdict across splits."""
    out: dict = {}
    for key, p in paths.items():
        p = Path(p)
        if not p.exists():
            raise FileNotFoundError(f"data[{key!r}] does not exist: {p}")
        out[key] = {
            "path": recorded_path(p, base_dir),
            "sha256": source_digest(p)[:RECORD_SHA_CHARS],
            "rows": _data_rows(p),
        }

    def role(key: str) -> str:
        return re.split(r"[_-]", key, maxsplit=1)[0].lower()

    known = {k: _ids(Path(p)) for k, p in paths.items() if k in SPLIT_KEYS}
    checkable = {k: v for k, v in known.items() if v is not None}
    verdicts: list[str] = []
    if len(checkable) >= 2:
        for a, b in ((x, y) for x in checkable for y in checkable if x < y):
            shared = checkable[a] & checkable[b]
            if shared:
                raise RuntimeError(
                    f"split leakage: {len(shared)} id(s) in both {a!r} and {b!r}, "
                    f"e.g. {sorted(shared)[:5]}. Fix the split before running."
                )
        verdicts.append(f"no shared ids across {sorted(checkable)}")
    controls = {k: _ids(Path(p)) for k, p in paths.items() if role(k) in CONTROL_ROLES}
    measured = {k: _ids(Path(p)) for k, p in paths.items() if role(k) in MEASURED_ROLES}
    controls = {k: v for k, v in controls.items() if v is not None}
    measured = {k: v for k, v in measured.items() if v is not None}
    for c, cids in controls.items():
        for m, mids in measured.items():
            shared = cids & mids
            if shared:
                raise RuntimeError(
                    f"control leakage: {len(shared)} id(s) in both {c!r} and {m!r}, "
                    f"e.g. {sorted(shared)[:5]} — the gate and the measured arm hold "
                    f"the same data point. Fix the sets before running."
                )
    if controls and measured:
        verdicts.append(
            f"no shared ids between {sorted(controls)} and {sorted(measured)}"
        )
    out["leakage_check"] = (
        ("ok: " + "; ".join(verdicts))
        if verdicts
        else (
            "skipped: need >=2 of train/dev/test, or a control (anchor/gate/placebo) "
            "and a measured set, as .jsonl with an 'id' field per row"
        )
    )
    return out


def snapshot_script(run_dir: Path) -> str:
    """Copy the running script into the run dir; return the content hash of
    the bytes copied (`script_sha`'s width), so record and copy agree.

    Not a nicety: a run's result belongs to the CODE that produced it, and
    neither the commit hash nor `git diff` pins that down. A dirty tree makes
    the hash a lie, and an UNTRACKED script (a fresh experiment area is always
    untracked) appears in no diff at all. Worse, editing a script does not
    reach an already-running process — so "the fix was in by then" can be false
    for a run that finished after it.
    """
    try:
        src = Path(sys.argv[0]).resolve()
        if not src.is_file():
            return "no-script"
        body = src.read_bytes()
        write_atomic_bytes(run_dir / f"script-source{src.suffix or '.txt'}", body)
        # the hash of the bytes copied, not of a second read: a save in
        # between left a record whose hash matched no stored script
        return digest(body)
    except OSError:
        return "no-script"


def script_sha() -> str:
    """The running script's content hash (config.json `script_sha`), or
    "no-script" — read before mkdir too, for a repeat's comparison."""
    try:
        src = Path(sys.argv[0]).resolve()
        return file_digest(src)[:DIGEST_CHARS] if src.is_file() else "no-script"
    except OSError:
        return "no-script"


_SNAPSHOT_CAP = 2 * 1024 * 1024  # a "source file" above 2 MB is data


def snapshot_untracked_sources(run_dir: Path) -> list[str]:
    """Copy untracked *.py next to an UNTRACKED entry script into the run dir.

    Closes the hole the single-file snapshot left (2026-08-18, Einwand MH):
    the entry script imports siblings — helper modules in the same scripts/
    folder — and on the FIRST run of a fresh area all of them are untracked:
    in no commit, in no diff, and (before this) in no copy either.

        uncommitted.patch          tracked drift — what git can see
        source-untracked/          what git cannot see, copied verbatim

    Deliberately narrow (the first draft hoovered output/ and old runs/ into
    the snapshot the moment the script dir was an area root):

      * fires ONLY when the entry script itself is untracked — the fresh-area
        case. A tracked entry means the area was committed once; from there,
        "commit before you run" is the practice, not a copy.
      * copies *.py only, skips output/ runs/ data/ __pycache__/, caps size.

    Committing the area empties this snapshot naturally. Cross-area untracked
    imports remain the documented gap — commit an area before others load it.
    """
    script_dir = Path(sys.argv[0]).resolve().parent
    if repo.git_root(script_dir) is None:
        return []
    r = repo.git_run(["ls-files", "--others", "--exclude-standard", "."], script_dir)
    if r.returncode != 0:
        return []
    untracked = set(r.stdout.splitlines())
    entry = Path(sys.argv[0]).resolve().name
    if entry not in untracked:
        return []
    skip_dirs = {"output", "runs", "data", "__pycache__"}
    copied = []
    for rel in sorted(untracked):
        relp = Path(rel)
        if relp.suffix != ".py" or skip_dirs.intersection(relp.parts):
            continue
        srcf = script_dir / relp
        try:
            if not srcf.is_file() or srcf.stat().st_size > _SNAPSHOT_CAP:
                continue
            dest = run_dir / "source-untracked" / relp
            dest.parent.mkdir(parents=True, exist_ok=True)
            write_atomic_bytes(dest, srcf.read_bytes())
            copied.append(rel)
        except OSError:
            continue
    if copied:
        print(
            f"runlog: entry script is UNTRACKED — copied {len(copied)} source "
            f"file(s) to source-untracked/. Best practice: commit BEFORE the "
            f"run, then the diff carries the provenance. ({', '.join(copied[:5])}"
            + (" ...)" if len(copied) > 5 else ")")
        )
    return copied


@dataclass(frozen=True)
class Provenance:
    """Phase 3's first step: what the record says about where the run
    started — git state and commit, the environment, the models resolved.

    Attributes:
        git: HEAD's short commit, `+dirty` when the tree differs (`git_state`).
        git_full: HEAD's full commit, "" outside a repo.
        env: Interpreter, lock fingerprint and drift (`env_state`).
        models: Alias → resolved spec (`resolve_models`); {} for a derived run.
    """

    git: str
    git_full: str
    env: str
    models: dict


def record_provenance(base_dir: Path, config: dict, derived: bool) -> Provenance:
    """Phase 3, first step: everything the record says about where the run
    started, read BEFORE the directory exists — a failure here must leave
    no directory without config.json. A DERIVED run records no models: its
    rows were answered by its parent's model, and today's models.toml would
    record a provenance the rows never had (`answering_run.model_provenance_run`
    walks derived_from to the run that did)."""
    return Provenance(
        git=git_state(base_dir),
        git_full=git_head(base_dir),
        env=env_state(base_dir),
        models={} if derived else resolve_models(config),
    )
