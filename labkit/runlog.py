"""runlog — minimal per-experiment run tracking (stdlib-only, no service).

Convention (AS-043 Runs go through `runlog`, AS-079 Self-contained experiment areas): every run — pilots included — goes through
`with runlog.run(...)`. Each run gets a self-contained dir and one append-only
run-index row; PROTOCOL-<task>.md cites run_ids instead of pasting numbers.

    runs/<run_id>/config.json      the record at start: config, data, git state,
                                   env, models resolved, the binding (protocol id)
    runs/<run_id>/metrics.json     the numbers reported via r.metrics()
    runs/<run_id>/outputs.json     the files registered via r.output(), as the
                                   run left them (sha, lines, rows_from, continues)
    runs/<run_id>/completion.json  confirmed completion: finish time, end git
                                   state, note, the runs this one continues
    runs/<run_id>/script-source.py  the script AS IT RAN (untracked or dirty
                                   code is in no commit and in no diff)
    runs/<run_id>/uncommitted.patch  the diff, IF the repo was dirty (tracked files only)
    runs/<run_id>/source-untracked/  untracked files next to the script, verbatim
    runs/<run_id>/<raw files>      verbatim model output etc. (save_raw)
    runs.tsv                       run index, one row per completed run
                                   (columns: RUN_INDEX_COLS) — derived, never a source

Three ways a run depends on another run's rows — not one:

    _prov          per row; the SCRIPT sets it (`batch.Store(prov=...)`), it
                   names the run and model that wrote the row; read by
                   `batch.row_runs`, held by `finalize`
    continues      per run; runlog RECORDS it at finalize from the rows a
                   registered .jsonl output already held (outputs.json per
                   file, completion.json as the union) — a resumed file;
                   the earlier run need not be completed; carries no model
    derived_from   per run; the SCRIPT declares it (`runlog.run(...,
                   derived_from=ID)`), config.json holds it; the parent must
                   be completed; the run makes no model call and records no
                   model — `runs.model_provenance_run` walks this key alone

Usage:
    import runlog
    with runlog.run("bt-oracle",
                    config={"model": "haiku", "seed": 42},
                    data={"train": TRAIN, "dev": DEV, "test": TEST}) as r:
        ...
        r.save_raw("responses.jsonl", raw_text)   # raw output, verbatim
        r.metrics(acc=0.83, n=100)
        r.note("pilot: threshold 0.5 too strict")  # optional

`data` uses the standard split keys "train" / "dev" / "test" (any other key is
recorded too, just not split-checked). For each file runlog records path,
sha256 and row count, and it checks the three splits for overlapping `id`s —
a leak raises before the run starts, rather than inflating a score nobody can
explain later. Recording the files is what makes "which data was that?"
answerable six weeks on; the split keys are what make it answerable by a tool.

A run directory exists only with its config.json (0.74.0: everything that
can fail is read before mkdir, a failure while writing the record removes
the directory). An incomplete run leaves its dir with config.json but
without the required completion markers — visible, not silent. The run-index row is written on
clean exit only. States: completed · running · unknown · crashed ·
unfinalized · corrupt · unreadable (config.json damaged) · legacy (written
before labkit 0.21).
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import TracebackType
from collections.abc import Iterator

from labkit import batch, promises, protocol_block, repo
from labkit.scope_sha import audit_stamp_drift
from labkit.runs import (
    FAILED_STATES,
    RunConfigError,
    completed_runs,
    completion_state,
    is_alive,
    read_completion,
    read_metrics,
    read_run_config,
    run_state,
    run_summary,
)

RUN_INDEX_COLS = [
    "run_id",
    "git",
    "script",
    "data",
    "config",
    "metrics",
    "note",
    "protocol_id",
]

# Bumped when a run directory's SHAPE changes, stamped into config.json at the
# START of the run. It has to be readable before the run ends, because the
# question it settles — did a run without completion.json break off? — is
# asked exactly when that file is absent (2026-09-26). A run without it was
# written before schema 2 and is read by labkit 0.47 only.
RUN_SCHEMA = 2
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


def _head(cwd: Path, short: bool = False) -> str:
    """HEAD's commit, "" outside a repo or before the first commit (an
    unborn HEAD is a state, not an error)."""
    if repo.git_root(cwd) is None:
        return ""
    r = repo.git_run(["rev-parse", *(["--short"] if short else []), "HEAD"], cwd)
    return r.stdout.strip() if r.returncode == 0 else ""


def _git_state(cwd: Path) -> str:
    rev = _head(cwd, short=True)
    if not rev:
        return "no-git"
    dirty = repo.git(["status", "--porcelain"], cwd)
    return f"{rev}{'+dirty' if dirty else ''}"


def _parse_lock(lock: Path) -> dict[str, str | None]:
    """requirements.lock -> {package: version}. None = pinned without a version.

    URL pins (`name @ https://...`, e.g. spaCy models) carry no `==` version;
    they count as pinned-any rather than as drift. Git pins with an explicit
    ref are the exception: `_parse_vcs_pins` reads them and `_lock_drift`
    compares them by commit.
    """
    out: dict[str, str | None] = {}
    for raw in lock.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        editable = _EDITABLE_PIN.match(line)
        if editable:
            out[editable.group("name").lower().replace("_", "-")] = None
        elif "==" in line:
            name, _, ver = line.partition("==")
            out[name.strip().lower().replace("_", "-")] = ver.strip()
        elif " @ " in line:
            out[line.split(" @ ")[0].strip().lower().replace("_", "-")] = None
    return out


# A VCS pin names a ref, not a version — `labkit @ git+file:///...@v0.14.0`.
# The version comparison in `_lock_drift` cannot see it, and counting it as
# pinned-any hid exactly the package that changes most often (2026-09-15:
# installed labkit was two minor versions behind the lock, drift said 0 —
# and the pinned tag did not even exist in the source repo).
_VCS_PIN = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._\-]*)\s*@\s*"
    r"git\+(?P<url>[^@\s#]+)(?:@(?P<ref>[^#\s]+))?\s*(?:#.*)?$"
)
# An editable install freezes as `-e git+<url>@<commit>#egg=<name>`: pip
# reads the commit from the source checkout. Unread, it counted as "installed
# but not in the lock" — a lock written by `pip freeze` seconds earlier in the
# same venv reported drift on every run (usability probe 2026-10-07, 6 of 6).
_EDITABLE_PIN = re.compile(
    r"^-e\s+git\+(?P<url>[^@\s#]+)@(?P<ref>[^#\s]+)"
    r"#egg=(?P<name>[A-Za-z0-9][A-Za-z0-9._\-]*)\s*$"
)
_HEX_REF = re.compile(r"^[0-9a-f]{7,40}$")


def _parse_vcs_pins(lock: Path) -> dict[str, tuple[str, str]]:
    """Git pins that carry an explicit ref: {package: (url, ref)}."""
    out: dict[str, tuple[str, str]] = {}
    for raw in lock.read_text(encoding="utf-8").splitlines():
        m = _VCS_PIN.match(raw.strip()) or _EDITABLE_PIN.match(raw.strip())
        if m and m.group("ref"):
            out[m.group("name").lower().replace("_", "-")] = (
                m.group("url"),
                m.group("ref"),
            )
    return out


def _resolve_ref(url: str, ref: str) -> str | None:
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
        return _checkout_head(Path(url.removeprefix("file://")))
    return None


def _checkout_head(path: Path) -> str | None:
    """HEAD of the git checkout at `path`; None when it is none."""
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip().lower() if proc.returncode == 0 else None


def _vcs_mismatch(url: str, ref: str, installed_commit: str | None) -> bool:
    """Does the installed commit disagree with the lock's git ref?"""
    want = _resolve_ref(url, ref)
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
_FREEZE_OMITS = {"pip", "setuptools", "wheel", "distribute", "pkg-resources"}


def _lock_drift(lock: Path) -> int:
    """How many installed packages disagree with the lock?

    "Re-freeze after every install" is a rule that gets violated SILENTLY: the
    lock falls behind, and every run keeps recording a hash that describes an
    environment which does not exist. A rule that fails without a sound has to
    become a check. Git pins are compared by commit (direct_url.json vs the
    lock's ref), not skipped as pinned-any.
    """
    from importlib.metadata import distributions

    pinned = {n: v for n, v in _parse_lock(lock).items() if n not in _FREEZE_OMITS}
    vcs = {n: uv for n, uv in _parse_vcs_pins(lock).items() if n not in _FREEZE_OMITS}
    installed: dict[str, str] = {}
    vcs_commit: dict[str, str | None] = {}
    for dist in distributions():
        name = (dist.metadata["Name"] or "").lower().replace("_", "-")
        if name and name not in _FREEZE_OMITS:
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
        if n in installed and _vcs_mismatch(url, ref, vcs_commit.get(n))
    )
    return drift


def _env_state(cwd: Path) -> str:
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
            h = hashlib.sha256(lock.read_bytes()).hexdigest()[:12]
            try:
                drift = _lock_drift(lock)
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


def _notify(title: str, body: str) -> None:
    """Best-effort macOS notification — session-independent, never raises.

    The monitor of record for an overnight run must not be tomorrow's status
    question (2026-08-17: a run finished at night and sat unnoticed for ~9 h).
    Opt-out with LABKIT_NOTIFY=0; anything else leaves it on.
    """
    if os.environ.get("LABKIT_NOTIFY") == "0" or sys.platform != "darwin":
        return
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                'display notification "{}" with title "{}"'.format(
                    body.replace('"', "'")[:200], title.replace('"', "'")[:60]
                ),
            ],
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        pass


_NOTIFY_MIN_S = 120  # a pilot finishing under 2 min needs no banner


def _resolve_models(config: dict) -> dict:
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
                from labkit import llm

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


def _sha256(path: Path) -> str:
    """Content digest of a file; of a directory, over each visible file's
    relative path and content — so adding, removing, renaming or editing a
    file below it moves it (a directory source used to be unfreezable, and
    `finalize` then refused every run of the stamped count skeleton)."""
    h = hashlib.sha256()
    if path.is_dir():
        for f in _visible_files(path):
            h.update(f.relative_to(path).as_posix().encode("utf-8") + b"\n")
            h.update(_sha256(f).encode() + b"\n")
        return h.hexdigest()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_meta(row: object) -> bool:
    """True for the ``_meta`` header that write_dataset() puts first."""
    return isinstance(row, dict) and "_meta" in row


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
                    if _is_meta(json.loads(line)):
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
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if _is_meta(row):
            continue
        if "id" not in row:
            return None
        ids.add(row["id"])
    return ids


def _describe(paths: dict) -> dict:  # noqa: C901 complexity baseline 2026-10-08
    """path + sha256 + rows per split, and the leakage verdict across splits."""
    out: dict = {}
    for key, p in paths.items():
        p = Path(p)
        if not p.exists():
            raise FileNotFoundError(f"data[{key!r}] does not exist: {p}")
        out[key] = {"path": str(p), "sha256": _sha256(p)[:16], "rows": _data_rows(p)}

    def role(key: str) -> str:
        return re.split(r"[_-]", key, 1)[0].lower()

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


@contextlib.contextmanager
def _index_lock(base_dir: Path, timeout: float = 30.0) -> Iterator[None]:
    """Exclusive lock for every change to runs.tsv — append, reindex.

    Without it a reindex and a finishing run race: one appends while the
    other reads, and a row lands twice or not at all. flock, not a lock
    FILE: the kernel drops it when the process dies, so a crashed run leaves
    no stale lock for the next one to trip over. Header creation and the
    duplicate check run inside it too — they read the same file.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(base_dir / ".runs.tsv.lock", os.O_CREAT | os.O_RDWR, 0o644)
    t0 = time.monotonic()
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() - t0 >= timeout:
                    raise RuntimeError(
                        f"runlog: runs.tsv locked for over {int(timeout)}s "
                        f"({base_dir}) — another append or reindex "
                        f"is running, or one hung."
                    )
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _append_row(index: Path, row: list[str]) -> None:
    """One row onto the run index, header created if absent. Callers hold
    the index lock — header creation reads the file too."""
    if not index.exists():
        index.write_text("\t".join(RUN_INDEX_COLS) + "\n", encoding="utf-8")
    with index.open("a", encoding="utf-8") as f:
        f.write("\t".join(c.replace("\t", " ").replace("\n", " ") for c in row) + "\n")


def _write_atomic(path: Path, text: str) -> None:
    """Write via temp file in the same directory + rename: the reader sees
    the old file or the new one, never half of either."""
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _check_run_index(base_dir: Path) -> None:
    """Refuse to run against a run index whose header doesn't match RUN_INDEX_COLS.

    Appending to an old-format runs.tsv would not error — the columns would
    just shift silently, and every row after the format change would be
    misread. Fail before the run instead, with the migration spelled out.
    """
    index = base_dir / "runs.tsv"
    if not index.exists():
        return
    with index.open(encoding="utf-8") as f:
        found = f.readline().rstrip("\n").split("\t")
    if found != RUN_INDEX_COLS:
        raise RuntimeError(
            f"runs.tsv columns {found} don't match this runlog "
            f"({RUN_INDEX_COLS}) — an index written by labkit before 0.21. "
            "Migrate it with labkit 0.47 (`runlog migrate-index <area>`, which "
            "keeps every row verbatim), then come back; appending without it "
            "would shift columns silently."
        )


def _snapshot_script(run_dir: Path) -> str:
    """Copy the running script into the run dir; return its content hash.

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
        (run_dir / f"script-source{src.suffix or '.txt'}").write_bytes(body)
        return hashlib.sha256(body).hexdigest()[:12]
    except OSError:
        return "no-script"


_SNAPSHOT_CAP = 2 * 1024 * 1024  # a "source file" above 2 MB is data


def _snapshot_untracked_sources(run_dir: Path) -> list[str]:
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
            dest.write_bytes(srcf.read_bytes())
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


def _protocol_binding(base_dir: Path, protocol: str | Path | None) -> dict:
    """Which protocol this run belongs to: {"id": ..., "path": ...}.

    The shape never varies — both fields always exist, only the values
    change. A reader never has to tell an absent key from null from an
    object (2026-09-26).

    `id` is the binding; `path` is relative to the area, for lookup and
    diagnosis, and may go stale. An explicit protocol must lie inside the
    area and be one of the PROTOCOL-*.md found there, or the run would bind
    to a file nobody checked. Omitted: one protocol binds, several are a
    hard error (guessing is what this whole mechanism exists to stop), none
    is unbound with a warning.
    """
    found = repo.area_protocols(base_dir)
    if protocol is not None:
        path = Path(protocol)
        if not path.is_absolute():
            path = base_dir / path
        path = path.resolve()
        if path not in [f.resolve() for f in found]:
            raise SystemExit(
                f"runlog: protocol={protocol!r} is not one of the "
                f"PROTOCOL-*.md in the run's area ({base_dir}):\n  "
                + "\n  ".join(f.name for f in found or [Path("(none)")])
            )
    elif len(found) == 1:
        path = found[0].resolve()
    elif not found:
        print(
            f"runlog: WARNING — no PROTOCOL-*.md in {base_dir}; this run "
            f"is recorded as unbound. A kept number needs a protocol "
            f"(AS-003 No run without an intent paragraph)."
        )
        return {"id": None, "path": None}
    else:
        raise SystemExit(
            f"runlog: {len(found)} protocols in {base_dir} — nothing would "
            f"say which one this run belongs to. Name it:\n"
            f"  runlog.run(..., protocol=PROTOCOL)\n  "
            + "\n  ".join(f.name for f in found)
        )

    try:
        rel = str(path.relative_to(base_dir.resolve()))
    except ValueError:
        rel = str(path)
    try:
        pid = protocol_block.head(path.read_text(encoding="utf-8")).id
    except protocol_block.BlockError as exc:
        raise SystemExit(f"runlog: {rel}: {exc}") from exc
    if pid is None:
        print(
            f"runlog: WARNING — {rel} carries no stamped id (`id` in its "
            f"[protocol] table); this run is recorded as unbound."
        )
    return {"id": pid, "path": rel}


# The freeze gate (2026-10-05). `long=True` is the script's declaration of a
# full run (the measure template sets it for the no-flag stage; --probe and
# pilots stay long=False). A full run on a protocol that is not `frozen =
# true`, or whose `preflight_audit` is still empty, produces a number nobody
# registered for — and the rule that forbade it lived only in the skill
# text, which a long session forgets. Hence a refusal in the one place every
# run passes through, before mkdir. Escape hatch for a long PILOT:
# LABKIT_UNFROZEN=1 — the acknowledgement is recorded in config.json so the
# number carries it. The gate follows the cost tier: at `cost = "seconds"`
# the run is rerunnable at will, so the freeze protects nothing — what a
# full run needs there is the registration, written before the number
# (AS-003 No run without an intent paragraph); an instrument change after it is a commit and a rerun, not a
# second freeze (AS-017 The number of audits follows the cost tier). `minutes`, `hours` and an unfilled cost keep the
# freeze. The tier lands in config.json as `cost_tier`.


def _protocol_text(base_dir: Path, binding: dict) -> str | None:
    """The bound protocol's text, or None when the run is unbound."""
    if binding.get("path") is None:
        return None
    path = Path(binding["path"])
    if not path.is_absolute():
        path = base_dir / path
    return path.read_text(encoding="utf-8")


def _freeze_findings(base_dir: Path, binding: dict) -> list[str]:
    """Why a FULL run may not start on this protocol — empty means it may."""
    from labkit.protocol_check import seconds_registration_missing

    text = _protocol_text(base_dir, binding)
    if text is None:
        return [
            "the run is unbound (no protocol) — a full run needs a "
            "registered protocol (AS-003 No run without an intent paragraph)"
        ]
    path = Path(binding["path"])
    if binding.get("id") is None:
        # a full run's number must be bound; an unstamped id binds nothing,
        # and finalize would only say so after the number exists (review 2026-10-07)
        return [
            f"{path.name}: the [protocol] id is not stamped — a full run "
            f"needs a bound protocol (`lib exp` stamps it)"
        ]
    head = protocol_block.head(text)  # read once at binding; valid here
    if head.cost == "seconds":
        missing = seconds_registration_missing(text)
        if not missing:
            return []
        return [
            f'{path.name}: `cost = "seconds"`, but the registration is not '
            f"written: {', '.join(missing)} still empty or a placeholder — at "
            f"seconds the gate is question · criterion · admissibility "
            f"condition, not the freeze (AS-003 No run without an intent paragraph, AS-017 The number of audits follows the cost tier)"
        ]
    out = []
    if not head.frozen:
        out.append(f"{path.name}: not `frozen = true`")
    if not head.preflight_audit:
        out.append(
            f"{path.name}: `preflight_audit` is empty — run `preflight`, "
            f"then the experiment-preflight audit (AS-015 Preflight audit before freezing), and stamp it"
        )
    else:
        drift = audit_stamp_drift(base_dir, head.preflight_audit)
        if drift:
            out.append(f"{path.name}: preflight_audit: {drift}")
    return out


def _promise_snapshot(
    base_dir: Path, text: str | None
) -> tuple["promises.PromiseTables | None", dict | None]:
    """The bound protocol's promise block, parsed once, and the snapshot the
    run records of it — (None, None) without tables.

    Before mkdir, like every refusal here: a malformed block or a declared
    scope naming code that does not exist stops the run — a number bound
    to a promise whose scope cannot be hashed is bound to nothing
    (`promises.declared_scope_sha`).
    """
    if text is None:
        return None, None
    try:
        block = promises.parse_block(text)
        if block is None:
            return None, None
        return block, promises.snapshot(block, base_dir)
    except promises.PromiseError as exc:
        raise SystemExit(f"runlog: promise block: {exc}") from exc


def _registration_refusal(
    binding: dict | None,
    head: "protocol_block.Head | None",
    block: "promises.PromiseTables | None",
    config: dict,
    long: bool,
) -> str | None:
    """The registration's contract, before any gate that can be acknowledged
    and before mkdir (standard 0.19): a frozen protocol and every full run
    carry the promises as data (`promises.promise_tables_owed`), and a run under a
    block records every registered constant unchanged — otherwise the
    number is held to a threshold nobody registered (Durchstich
    2026-10-06). None when it holds, or when the run is unbound (the
    freeze gate refuses an unbound full run on its own)."""
    path = (binding or {}).get("path")
    name = Path(path).name if isinstance(path, str) and path else "(unbound)"
    if head is None:
        return None
    owed = promises.promise_tables_owed(block, frozen=head.frozen, full_run=long)
    if owed:
        return f"{name}: {owed}"
    if block is not None:
        refusal = _constants_refusal(block, config)
        if refusal:
            return f"{name}: {refusal}"
    return None


def _constants_refusal(block: "promises.PromiseTables", config: dict) -> str | None:
    """Why this config may not run under `block`: a registered constant the
    config lacks or carries with another value (type-strict). The guarantee
    behind the record: a run under a block recorded every registered
    constant unchanged (0.71.0)."""
    broken = [r for r in promises.constant_records(block, config) if r.state != "equal"]
    if not broken:
        return None
    lines = [
        f"[{r.promise_id}] {r.name} = {r.promised!r} is registered, the config "
        + ("carries no such key" if r.state == "missing" else f"says {r.recorded!r}")
        for r in broken
    ]
    return (
        "the registered constants are not in this run's config as registered:\n  "
        + "\n  ".join(lines)
        + "\n  read them with promises.all_constants(), not a second copy"
    )


class Run:
    """One measure run: its directory, its frozen config, the outputs it
    registers and the metrics it reports.

    `__init__` refuses, in this order, BEFORE the directory exists:

        1. derived_from names no completed run       → SystemExit
        2. protocol binding unresolvable             → SystemExit
        3. frozen (or seconds) without promise tables → SystemExit
        4. a registered constant missing/different   → SystemExit
        5. detach gate (long run under Claude Code)  → SystemExit
        6. run index header unknown                  → RuntimeError
        7. data split leakage                        → RuntimeError
        8. freeze gate (unfrozen full run, stale stamp) → SystemExit
        9. git / env / model alias read              → their own errors
       10. mkdir, then the record; a failure here removes the dir

    `class run` is the context manager around this; every check is here."""

    def __init__(
        self,
        experiment: str,
        config: dict,
        base_dir: Path,
        data: dict | None = None,
        long: bool = False,
        protocol: str | Path | None = None,
        derived_from: str | None = None,
    ) -> None:
        # A derived run (2026-10-05): the same raw rows, evaluated again —
        # because evaluate() gained a descriptive key, not because anything
        # about the measurement changed. It names its parent so the record
        # shows one measurement with two readings instead of two runs; the
        # parent must be a completed run of this area, or this is a refusal.
        self._derived_from = None
        if derived_from is not None:
            parent = base_dir / "runs" / derived_from
            try:
                state = completion_state(parent) if parent.is_dir() else "missing"
            except RunConfigError as exc:
                raise SystemExit(
                    f"runlog: derived_from={derived_from!r}: {exc}"
                ) from exc
            if state != "completed":
                hint = " (read it with labkit 0.47)" if state == "legacy" else ""
                raise SystemExit(
                    f"runlog: derived_from={derived_from!r} names no completed "
                    f"run under {base_dir / 'runs'} ({state}){hint} — a derived run "
                    f"needs a finished parent"
                )
            self._derived_from = derived_from
        # Before any work: an unresolvable protocol is a refusal, and a
        # refusal must not leave an empty run dir behind (2026-09-26).
        self._protocol = _protocol_binding(base_dir, protocol)
        _ptext = _protocol_text(base_dir, self._protocol)
        _phead = protocol_block.head(_ptext) if _ptext is not None else None
        self._cost_tier = _phead.cost if _phead is not None else None
        _block, self._promises = _promise_snapshot(base_dir, _ptext)
        # Frozen now: what the registration check holds is what config.json records.
        self._config = dict(config)
        refusal = _registration_refusal(
            self._protocol, _phead, _block, self._config, long
        )
        if refusal:
            raise SystemExit(f"runlog: {refusal}")
        _short = self._cost_tier == "seconds"
        # Detach gate (scar 2026-08-13, twice in one evening): a long run
        # started in a Claude Code foreground shell dies with the 10-min tool
        # timeout — the kill takes the whole process group, run and lock with
        # it. `long=True` is the script's own declaration (the --full stage
        # sets it); the gate refuses the foreground start BEFORE any work.
        # A run of seconds (`cost = "seconds"`) cannot meet that timeout and
        # runs in the foreground (2026-10-05).
        if (
            long
            and not _short
            and os.environ.get("CLAUDECODE")
            and os.environ.get("LABKIT_DETACHED") != "1"
        ):
            raise SystemExit(
                "runlog: this run declares long=True and sits in a Claude Code "
                "foreground shell — the tool timeout would kill the process "
                "group mid-run (2026-08-13). Start it detached:\n"
                "  runlog start -- <the same command>\n"
                "or, if the caller already detached it (run_in_background, "
                "nohup+setsid), acknowledge with LABKIT_DETACHED=1."
            )
        self.run_id = time.strftime("%Y-%m-%dT%H-%M-%S") + "_" + uuid.uuid4().hex[:4]
        self.experiment = experiment
        self.script = Path(sys.argv[0]).name if sys.argv[0] else "<interactive>"
        self.base = base_dir
        _check_run_index(base_dir)  # raises before any work
        self._data = _describe(data) if data else {}  # raises on leak, before mkdir
        # Freeze gate, also before mkdir: a full run on an unfrozen protocol
        # is a refusal, not a run with a warning (2026-10-05).
        self._unfrozen_ack = False
        if long:
            findings = _freeze_findings(base_dir, self._protocol)
            if (
                findings and os.environ.get("LABKIT_UNFROZEN") == "1"
            ):  # "0" is no acknowledgement
                self._unfrozen_ack = True
                print(
                    "runlog: WARNING — LABKIT_UNFROZEN=1: full run on an "
                    "unfrozen protocol, acknowledged; recorded in config.json:\n  "
                    + "\n  ".join(findings)
                )
            elif findings:
                raise SystemExit(
                    "runlog: this run declares long=True (a full run), but its "
                    "protocol is not ready for one:\n  "
                    + "\n  ".join(findings)
                    + "\nPilot it with long=False, or freeze first: `preflight "
                    "<AREA>` clean, audit stamped, `frozen = true` "
                    '(at cost = "seconds": question, criterion and admissibility condition written suffice). A '
                    "long PILOT acknowledges with LABKIT_UNFROZEN=1 (recorded)."
                )
        self.dir = base_dir / "runs" / self.run_id
        self._outputs: list[Path] = []
        self._metrics: dict = {}
        self._note = ""
        self._t0 = time.monotonic()
        # Everything that can fail on its own (git, the environment, the
        # model alias) is read BEFORE the directory exists: a failure after
        # mkdir left a directory without config.json, which the listings
        # read as `legacy` — "written before labkit 0.21" (2026-10-09).
        git_state, git_full = _git_state(base_dir), _head(base_dir)
        env = _env_state(base_dir)
        # A derived run re-reads the parent's rows; its model is the one that
        # answered THEN. Resolving the alias now, under today's models.toml,
        # would record a provenance the rows never had — so a derived run
        # records none, and `runs.model_provenance_run` walks derived_from
        # to the run that did (2026-10-08).
        models = {} if self._derived_from else _resolve_models(self._config)
        self.dir.mkdir(parents=True, exist_ok=False)
        try:
            self._write_record(experiment, git_state, git_full, env, models, base_dir)
        except BaseException:
            shutil.rmtree(self.dir, ignore_errors=True)  # no half-made run
            raise

    def _write_record(
        self,
        experiment: str,
        git_state: str,
        git_full: str,
        env: str,
        models: dict,
        base_dir: Path,
    ) -> None:
        """config.json — what this run was, written once at start — plus the
        script snapshot and the dirty-tree patch. Not the protocol's settings
        head (protocol_block.PROTOCOL_HEAD_KEYS)."""
        frozen = {
            "schema_version": RUN_SCHEMA,
            "experiment": experiment,
            "script": self.script,
            "protocol": self._protocol,
            "derived_from": self._derived_from,
            "unfrozen_ack": self._unfrozen_ack,
            "cost_tier": self._cost_tier,
            "promises": self._promises,
            "script_sha": _snapshot_script(self.dir),
            "untracked_sources": _snapshot_untracked_sources(self.dir),
            "pid": os.getpid(),  # lets `active()` tell running from crashed
            "git": git_state,
            "git_full": git_full,
            "python": sys.version.split()[0],
            "env": env,
            "models_resolved": models,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "command": list(sys.argv),  # how to start this run again
            "data": self._data,
            "config": self._config,
        }
        (self.dir / "config.json").write_text(
            json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # A dirty tree makes the commit hash a lie: save what it doesn't cover.
        if _head(base_dir) and repo.git(["status", "--porcelain"], base_dir):
            (self.dir / "uncommitted.patch").write_text(
                repo.git(["diff", "HEAD"], base_dir) or "", encoding="utf-8"
            )

    def output(self, *paths: str | Path) -> None:
        """Register the files this run WRITES (2026-08-18).

        config.json freezes the inputs, but where a run wrote its data lived
        only in the script's code — whoever stood inside runs/<id>/ could not
        answer "where did the data go?" without reading source. Registered
        paths land in `outputs.json` at finalize, with sha256 and line count
        taken AFTER the run, so the record describes the file as the run left
        it. Register the batch.Store target right next to opening it.
        """
        self._outputs.extend(Path(p) for p in paths)

    def save_raw(self, name: str, content: str) -> Path:
        """Write a raw text artefact into the run's directory and return its path."""
        p = self.dir / name
        p.write_text(content, encoding="utf-8")
        return p

    def metrics(self, **kv: object) -> None:
        """Add numbers to the run's metrics.json (written when the run finishes)."""
        self._metrics.update(kv)

    def note(self, text: str) -> None:
        """Set the run's one-line note for the run index."""
        self._note = text

    def _finalize(self) -> None:
        """outputs.json, metrics.json, completion.json, the index row — in that
        order (a break after metrics leaves `unfinalized`). An output problem
        (file absent at the end, a damaged row) is a NOTE in outputs.json and
        does not stop completion: `completed` vouches for the run's record,
        not for its outputs — `finalize` reads outputs.json and holds them."""
        self._metrics.setdefault("duration_s", round(time.monotonic() - self._t0, 1))
        continues: set[str] = set()
        if self._outputs:
            rows = []
            for p in self._outputs:
                if p.exists():
                    with p.open("rb") as fh:
                        text_lines = sum(1 for _ in fh)
                    entry: dict = {
                        "path": str(p),
                        "sha256": _sha256(p)[:16],
                        "lines": text_lines,
                    }
                    # A resumed file holds rows of the run that broke off:
                    # name it, so "this run continues that one" is in the
                    # record, not only in the rows' _prov (2026-10-09).
                    if p.suffix == ".jsonl":
                        try:
                            rr = batch.row_runs(p)
                        except ValueError as exc:
                            entry["note"] = f"rows unreadable: {exc}"
                        else:
                            entry["rows_from"] = dict(sorted(rr.runs.items()))
                            entry["continues"] = sorted(
                                r for r in rr.runs if r != self.run_id
                            )
                            continues.update(entry["continues"])
                    rows.append(entry)
                else:
                    rows.append(
                        {
                            "path": str(p),
                            "sha256": None,
                            "lines": None,
                            "note": "registered, but absent at end of run",
                        }
                    )
            (self.dir / "outputs.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        (self.dir / "metrics.json").write_text(
            json.dumps(self._metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Order matters, and this is the reason for it: results first, then
        # the confirmed completion, then the index. A break after metrics
        # leaves `unfinalized` (numbers on disk, run not finished); a break
        # after completion.json leaves a run the index missed but `reindex`
        # can rebuild in full. Before this file the two looked the same.
        git_end = _git_state(self.base)
        _write_atomic(
            self.dir / "completion.json",
            json.dumps(
                {
                    "schema_version": RUN_SCHEMA,
                    "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "git": git_end,
                    "git_full": _head(self.base),
                    "note": self._note,
                    "continues": sorted(continues),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        row = [
            self.run_id,
            git_end,
            self.script,
            json.dumps(self._data, ensure_ascii=False, sort_keys=True),
            json.dumps(self._config, ensure_ascii=False, sort_keys=True),
            json.dumps(self._metrics, ensure_ascii=False, sort_keys=True),
            self._note,
            self._protocol.get("id") or "",
        ]
        with _index_lock(self.base):
            _append_row(self.base / "runs.tsv", row)
        dur = self._metrics.get("duration_s", 0)
        if os.environ.get("LABKIT_NOTIFY") == "1" or dur >= _NOTIFY_MIN_S:
            _notify(
                f"run finished: {self.experiment}",
                f"{self.run_id} · {dur}s · {len(self._metrics)} metric(s)",
            )


def active(base_dir: str | Path) -> list[dict]:
    """Runs in this area that are not completed, each with its `state`.

    This is what makes parallel work cheap — before starting an experiment you
    LOOK instead of asking: which runs are live, and which files do they read
    and write (their config.json says). `alive` distinguishes a running process
    from a crashed one by checking the recorded pid; `state` says what the run
    directory is (see `run_state`).

        runlog <area>        (the installed console command)
    """
    out = []
    for d in sorted((Path(base_dir) / "runs").glob("*")):
        try:
            cfg = read_run_config(d)
        except RunConfigError as exc:
            out.append(
                {
                    "run_id": d.name,
                    "dir": str(d),
                    "alive": None,
                    "state": "unreadable",
                    "error": str(exc),
                }
            )
            continue
        if cfg is None:
            continue
        alive = is_alive(cfg.get("pid"), cfg.get("script"))
        state = run_state(d, cfg, alive)
        if state in ("completed", "legacy"):  # legacy: ended long ago, not open
            continue
        out.append(
            {"run_id": d.name, "dir": str(d), "alive": alive, "state": state, **cfg}
        )
    return out


class run:
    """Context manager: `with runlog.run("name", config={...}, data={...}) as r:`
    — every refusal and every record is `Run.__init__` (see its docstring);
    `__exit__` finalizes on a clean exit, a crash leaves the dir without
    metrics.json (visible)."""

    def __init__(
        self,
        experiment: str,
        config: dict,
        base_dir: str | Path | None = None,
        data: dict | None = None,
        long: bool = False,
        protocol: str | Path | None = None,
        derived_from: str | None = None,
    ) -> None:
        # `protocol` and `derived_from` last: no existing positional call shifts.
        base = Path(base_dir) if base_dir else Path(sys.argv[0]).resolve().parent
        self._run = Run(
            experiment,
            config,
            base,
            data,
            long=long,
            protocol=protocol,
            derived_from=derived_from,
        )

    def __enter__(self) -> Run:
        return self._run

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> bool:
        if exc_type is None:
            self._run._finalize()  # crash -> dir stays without metrics.json (visible)
        return False


def _newest_output(area: Path) -> str:
    """One line about the freshest file in <area>/output/ — the improvised
    `tail`/`wc` poll, done once and correctly."""
    out_dir = area / "output"
    if not out_dir.is_dir():
        return ""
    files = [p for p in out_dir.iterdir() if p.is_file()]
    if not files:
        return ""
    newest = max(files, key=lambda p: p.stat().st_mtime)
    try:
        lines = sum(1 for _ in newest.open("rb"))
    except OSError:
        return ""
    age = int(time.time() - newest.stat().st_mtime)
    return f"output: {newest.name} {lines} line(s), last write {age}s ago"


def _print_status(area: str, live: list[dict]) -> None:
    if not live:
        print(f"{area}: no open runs")
    for r in live:
        state = r.get("state", "unknown")
        print(f"{r['run_id']}  {state:12s} pid={r.get('pid')}  {r.get('script')}")
        if r.get("error"):
            print(f"    {r['error']}")
        else:
            print(f"    {json.dumps(r.get('config', {}), ensure_ascii=False)[:160]}")


def _print_finished(area: Path) -> None:
    """One line per finished run: what it is, whether its code was committed,
    how it was started — `runlog <area>` after the open runs."""
    runs_dir = Path(area) / "runs"
    if not runs_dir.is_dir():
        return
    done = []
    for d in sorted(runs_dir.glob("*")):
        if not (d / "config.json").is_file():
            continue
        try:
            s = run_summary(d)
        except RunConfigError as exc:
            print(f"  {d.name}  unreadable — {exc}")
            continue
        if s.state == "completed":
            done.append(s)
    if not done:
        return
    print(f"finished runs ({len(done)}, oldest first):")
    for s in done:
        kind = (
            f"derived from {s.derived_from} (its rows re-evaluated)"
            if s.derived_from
            else "fresh run of the script"
            + (f" (models: {', '.join(s.models)})" if s.models else "")
        )
        commit = s.git.removesuffix("+dirty")
        if s.uncommitted_bytes:
            code = (
                f"code {commit} + uncommitted changes "
                f"({s.uncommitted_bytes} B in uncommitted.patch)"
            )
        elif s.git.endswith("+dirty"):
            code = f"code {commit}, tracked files committed (untracked files present)"
        else:
            code = f"code {commit}, committed"
        print(f"  {s.run_id}  {kind} · {code}")
        print(f"      started as: {s.command or '(not recorded — labkit before 0.69)'}")


def _finished_line(area: Path) -> str:
    """The newest COMPLETED run, by its own marker — a run whose metrics
    landed but whose finalization broke off is not a finished run."""
    done = completed_runs(area)
    if not done:
        return "no finished runs"
    m = read_metrics(done[-1] / "metrics.json")
    keys = ", ".join(list(m)[:6])
    return f"last finished: {done[-1].name} ({keys})"


def _wait(
    area: str, max_seconds: float | None, interval: float, follow: bool, notify: bool
) -> int:
    """Block until the area has no open runs. Exit codes are the contract:
    0 = no open runs (finished) · 2 = a run crashed · 3 = still running at
    --max-seconds. The waiter only OBSERVES — the run owns its process group
    and its lock, so a killed waiter is harmless (verified in the detach
    probe: killing the waiter left run and lock untouched)."""
    t0 = time.monotonic()
    apath = Path(area)
    while True:
        live = active(area)
        if not live:
            print(f"{area}: no open runs — {_finished_line(apath)}")
            if notify:
                _notify("runlog --wait", f"{area}: no open runs")
            return 0
        # Exit 2 covers every failed state: a machine only needs "did not
        # finish cleanly", a human tells them apart by state and message.
        WHY = {
            "crashed": "config.json without metrics.json",
            "unfinalized": "metrics.json without completion.json — "
            "finalization broke off, numbers must not be "
            "reported",
            "corrupt": "completion.json without metrics.json — the results are gone",
            "unreadable": "config.json cannot be read — the run's record is damaged",
        }
        failed = [r for r in live if r.get("state") in FAILED_STATES]
        if failed:
            for r in failed:
                state = r.get("state", "?")
                why = r.get("error") or f"{r['dir']}: {WHY.get(state, '')}"
                print(
                    f"{r['run_id']}  {state.upper()}  pid={r.get('pid')}  "
                    f"{r.get('script')}  ({why})"
                )
            if notify:
                _notify("runlog --wait", f"{area}: run {failed[0].get('state')}")
            return 2
        if follow:
            stamp = time.strftime("%H:%M:%S")
            extra = _newest_output(apath)
            print(
                f"[{stamp}] {len(live)} open run(s): "
                + ", ".join(r["run_id"] for r in live)
                + (f" · {extra}" if extra else ""),
                flush=True,
            )
        if max_seconds is not None and time.monotonic() - t0 >= max_seconds:
            extra = _newest_output(apath)
            print(
                f"{area}: still running after {int(max_seconds)}s — "
                + ", ".join(f"{r['run_id']} pid={r.get('pid')}" for r in live)
                + (f" · {extra}" if extra else "")
                + "\nre-check: runlog "
                + area
                + " --wait"
            )
            return 3
        time.sleep(interval)


def _start(argv: list[str]) -> int:
    """runlog start [--log FILE] -- <cmd ...>: detach a run and return.

    setsid puts the run in its OWN process group and session: the shell that
    started it — and any tool timeout that kills that shell's group — cannot
    take the run down with it (scar 2026-08-13). LABKIT_DETACHED=1 tells the
    `long=True` gate inside the script that the detach already happened.
    """
    import argparse

    ap = argparse.ArgumentParser(
        prog="runlog start",
        description="Start a command detached (own session via setsid), "
        "output to a log file, return immediately.",
    )
    ap.add_argument(
        "--log", default=None, help="log file (default: output/start-<ts>.log)"
    )
    ap.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command and arguments")
    args = ap.parse_args(argv)
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        ap.error("no command given — usage: runlog start -- <cmd ...>")
    log = (
        Path(args.log)
        if args.log
        else Path("output") / f"start-{time.strftime('%Y-%m-%dT%H-%M-%S')}.log"
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "LABKIT_DETACHED": "1"}
    with log.open("ab") as fh:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=fh,
            stderr=fh,
            start_new_session=True,
            env=env,
        )
    print(f"started detached: pid={proc.pid}  log={log}")
    print("status:  runlog .        wait:  runlog . --wait")
    return 0


def _read_index(index: Path) -> tuple[list[str], list[list[str]]]:
    """(header, rows) of the run index. Callers hold the lock."""
    if not index.exists():
        return [], []
    lines = index.read_text(encoding="utf-8").splitlines()
    if not lines:
        return [], []
    return lines[0].split("\t"), [ln.split("\t") for ln in lines[1:] if ln]


def reindex(base_dir: Path) -> int:  # noqa: C901 complexity baseline 2026-10-08
    """Rebuild the run index (runs.tsv) from the run folders: append a row for
    every completed run that has none. Never rewrites.

    A row that exists stays untouched. Only runs with both completion
    markers are indexed; a run without `schema_version` is reported — it is
    read with labkit 0.47.
    """
    index = base_dir / "runs.tsv"
    with _index_lock(base_dir):
        header, rows = _read_index(index)
        if header and header != RUN_INDEX_COLS:
            print(
                f"runlog: {index} has old columns {header} — migrate it "
                f"with labkit 0.47 (`runlog migrate-index`) first."
            )
            return 2
        seen: dict[str, int] = {}
        for row in rows:
            if row:
                seen[row[0]] = seen.get(row[0], 0) + 1
        dupes = sorted(rid for rid, n in seen.items() if n > 1)
        if dupes:
            print(
                f"runlog: {index} lists {len(dupes)} run_id(s) more than "
                f"once: {', '.join(dupes[:5])} — repair by hand; a run "
                f"belongs in the index exactly once."
            )
            return 2

        added, skipped_legacy, incomplete, unreadable = 0, [], [], []
        for d in sorted((base_dir / "runs").glob("*")):
            if d.name in seen:
                continue
            try:
                cfg = read_run_config(d)
            except RunConfigError as exc:
                unreadable.append(str(exc))
                continue
            if cfg is None:
                continue
            state = run_state(d, cfg, alive=False)
            if state == "legacy":
                skipped_legacy.append(d.name)
                continue
            if state != "completed":
                incomplete.append(d.name)
                continue
            comp = read_completion(d)
            metrics = read_metrics(d / "metrics.json")
            _append_row(
                index,
                [
                    d.name,
                    str(comp.get("git", "")),
                    cfg.get("script", ""),
                    json.dumps(cfg.get("data", {}), ensure_ascii=False, sort_keys=True),
                    json.dumps(
                        cfg.get("config", {}), ensure_ascii=False, sort_keys=True
                    ),
                    json.dumps(metrics, ensure_ascii=False, sort_keys=True),
                    str(comp.get("note", "")),
                    (cfg.get("protocol") or {}).get("id") or "",
                ],
            )
            added += 1

    print(f"runlog: {added} row(s) appended to {index}.")
    for name in skipped_legacy:
        print(
            f"  {name}: run without schema_version (labkit before 0.21) — "
            f"not indexed; read it with labkit 0.47."
        )
    for name in incomplete:
        print(f"  {name}: not completed — nothing to index.")
    for err in unreadable:
        print(f"  NOT INDEXED: {err}")
    return 2 if unreadable else 0


def main(argv: list[str]) -> int:
    """Status, wait, follow or start — the run monitor of record."""
    if argv and argv[0] == "start":
        return _start(argv[1:])
    if argv and argv[0] == "reindex":
        area = repo.area_path(argv[1]) if len(argv) > 1 else Path(".")
        if not area.is_dir():
            print(f"runlog: {repo.no_such_area(area)}")
            return 2
        return reindex(area)
    import argparse

    ap = argparse.ArgumentParser(
        prog="runlog",
        description="List an experiment area's runs: the open ones (not yet "
        "completed) with state (running/unknown/crashed/unfinalized/corrupt), "
        "script and frozen config; then the finished ones — what each is "
        "(a run, or derived from which), whether its code was committed, "
        "and the command that started it. "
        "'Nachsehen statt nachfragen' — "
        "check this before starting a run in a shared repo. "
        "`--wait` blocks until the area is idle (exit 0), a run "
        "crashed (exit 2) or --max-seconds passed (exit 3); "
        "`--follow` prints a status line per interval until idle; "
        "`runlog start -- <cmd>` detaches a run (own session, "
        "log file) and returns. "
        "`runlog reindex <area>` appends rows for completed "
        "runs the index missed.",
    )
    ap.add_argument(
        "area",
        nargs="?",
        default=".",
        help="experiment area holding a runs/ dir (default: .)",
    )
    ap.add_argument(
        "--wait",
        action="store_true",
        help="block until no open runs; exit 0/2/3 (idle/crashed/"
        "still running at --max-seconds)",
    )
    ap.add_argument(
        "--follow",
        action="store_true",
        help="like --wait but unbounded, one status line per "
        "interval (for a human terminal)",
    )
    ap.add_argument(
        "--max-seconds",
        type=float,
        default=90.0,
        help="--wait: give up after this long (default 90 — "
        "safely under the shell tool's timeout)",
    )
    ap.add_argument(
        "--interval",
        type=float,
        default=None,
        help="poll interval in s (default: 2 for --wait, 5 for --follow)",
    )
    ap.add_argument(
        "--notify", action="store_true", help="macOS notification when the wait ends"
    )
    args = ap.parse_args(argv)
    if args.follow:
        return _wait(args.area, None, args.interval or 5.0, True, args.notify)
    if args.wait:
        return _wait(
            args.area, args.max_seconds, args.interval or 2.0, False, args.notify
        )
    _print_status(args.area, active(args.area))
    _print_finished(Path(args.area))
    return 0


def cli() -> None:
    """Entry point for the installed `runlog` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
