"""runlog — minimal per-experiment run tracking (stdlib-only, no service).

Convention (Arbeitsstandard §2/§4): every run — pilots included — goes through
`with runlog.run(...)`. Each run gets a self-contained dir and one append-only
run-index row; PROTOCOL-<task>.md cites run_ids instead of pasting numbers.

    runs/<run_id>/config.json      frozen inputs: params + git state + data
    runs/<run_id>/metrics.json     outputs you declared
    runs/<run_id>/script-source.py  the script AS IT RAN (untracked or dirty
                                   code is in no commit and in no diff)
    runs/<run_id>/uncommitted.patch  the diff, IF the repo was dirty (tracked files only)
    runs/<run_id>/source-untracked/  untracked files next to the script, verbatim
    runs/<run_id>/<raw files>      verbatim model output etc. (save_raw)
    runs.tsv                       run index: run_id git script data config metrics note

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

A crashed run leaves its dir with config.json but no metrics.json — visible,
not silent. The run-index row is written on clean exit only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

RUN_INDEX_COLS = ["run_id", "git", "script", "data", "config", "metrics", "note"]
SPLIT_KEYS = ("train", "dev", "test")


def _git(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.run(["git", *args], cwd=cwd,
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def _git_state(cwd: Path) -> str:
    rev = _git(["rev-parse", "--short", "HEAD"], cwd)
    dirty = _git(["status", "--porcelain"], cwd)
    return f"{rev}{'+dirty' if dirty else ''}" if rev else "no-git"


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
        if "==" in line:
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
    r"git\+(?P<url>[^@\s#]+)(?:@(?P<ref>[^#\s]+))?\s*(?:#.*)?$")
_HEX_REF = re.compile(r"^[0-9a-f]{7,40}$")


def _parse_vcs_pins(lock: Path) -> dict[str, tuple[str, str]]:
    """Git pins that carry an explicit ref: {package: (url, ref)}."""
    out: dict[str, tuple[str, str]] = {}
    for raw in lock.read_text(encoding="utf-8").splitlines():
        m = _VCS_PIN.match(raw.strip())
        if m and m.group("ref"):
            out[m.group("name").lower().replace("_", "-")] = (
                m.group("url"), m.group("ref"))
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
        return _git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                    Path(url[7:])).lower()
    return None


def _direct_url_commit(dist) -> str | None:
    """The commit pip recorded at install time (direct_url.json), if any."""
    try:
        raw = dist.read_text("direct_url.json")
        return json.loads(raw)["vcs_info"]["commit_id"].lower() if raw else None
    except (KeyError, AttributeError, TypeError, ValueError, OSError):
        return None


def _vcs_mismatch(url: str, ref: str, installed_commit: str | None) -> bool:
    """Does the installed commit disagree with the lock's git ref?"""
    want = _resolve_ref(url, ref)
    if want is None:
        return False    # remote tag/branch: unverifiable offline, pinned-any
    if not want:
        return True     # ref does not resolve locally: lock is uninstallable
    if not installed_commit:
        return True     # pinned to a commit, installed from something else
    return not (installed_commit.startswith(want)
                or want.startswith(installed_commit))


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

    pinned = {n: v for n, v in _parse_lock(lock).items()
              if n not in _FREEZE_OMITS}
    vcs = {n: uv for n, uv in _parse_vcs_pins(lock).items()
           if n not in _FREEZE_OMITS}
    installed: dict[str, str] = {}
    vcs_commit: dict[str, str | None] = {}
    for dist in distributions():
        name = (dist.metadata["Name"] or "").lower().replace("_", "-")
        if name and name not in _FREEZE_OMITS:
            installed[name] = dist.version
            if name in vcs:
                vcs_commit[name] = _direct_url_commit(dist)
    drift = sum(1 for n, v in installed.items()
                if n not in pinned or (pinned[n] is not None and pinned[n] != v))
    drift += sum(1 for n in pinned if n not in installed)
    drift += sum(1 for n, (url, ref) in vcs.items()
                 if n in installed and _vcs_mismatch(url, ref, vcs_commit.get(n)))
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
            except Exception:      # never let bookkeeping break a run
                return f"{exe} | requirements.lock:{h} | drift:unknown"
            if drift:
                print(f"runlog: WARNING — {drift} package(s) deviate from "
                      f"requirements.lock. `pip freeze > requirements.lock`, "
                      f"or this run's lock hash describes an environment "
                      f"that does not exist.", file=sys.stderr)
            return f"{exe} | requirements.lock:{h} | drift:{drift}"
    print("runlog: WARNING — no requirements.lock found; env recorded as "
          "'unpinned'. `pip freeze > requirements.lock` to pin, or this run "
          "cannot claim the environment it ran in.", file=sys.stderr)
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
            ["osascript", "-e",
             'display notification "{}" with title "{}"'.format(
                 body.replace('"', "'")[:200], title.replace('"', "'")[:60])],
            capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass


_NOTIFY_MIN_S = 120   # a pilot finishing under 2 min needs no banner


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
                try:
                    from labkit import llm
                except ImportError:      # vendored flat copy (student repos)
                    import llm
                out[val] = llm.resolve(val)
            except Exception as e:
                out[val] = f"unresolved: {e}"
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ids(path: Path) -> set | None:
    """Row ids of a .jsonl file, or None if they can't be read.

    None means "not checkable", never "no overlap" — the caller records the
    reason so a skipped leakage check stays visible.
    """
    if path.suffix != ".jsonl":
        return None
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "id" not in row:
            return None
        ids.add(row["id"])
    return ids


def _describe(paths: dict) -> dict:
    """path + sha256 + rows per split, and the leakage verdict across splits."""
    out: dict = {}
    for key, p in paths.items():
        p = Path(p)
        if not p.exists():
            raise FileNotFoundError(f"data[{key!r}] does not exist: {p}")
        out[key] = {"path": str(p), "sha256": _sha256(p)[:16],
                    "rows": sum(1 for line in p.open(encoding="utf-8") if line.strip())}
    known = {k: _ids(Path(p)) for k, p in paths.items() if k in SPLIT_KEYS}
    checkable = {k: v for k, v in known.items() if v is not None}
    if len(checkable) < 2:
        out["leakage_check"] = ("skipped: need >=2 of train/dev/test as .jsonl "
                                "with an 'id' field per row")
        return out
    for a, b in ((x, y) for x in checkable for y in checkable if x < y):
        shared = checkable[a] & checkable[b]
        if shared:
            raise RuntimeError(
                f"split leakage: {len(shared)} id(s) in both {a!r} and {b!r}, "
                f"e.g. {sorted(shared)[:5]}. Fix the split before running.")
    out["leakage_check"] = f"ok: no shared ids across {sorted(checkable)}"
    return out


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
            f"({RUN_INDEX_COLS}). Migrate the run index — insert the missing "
            "column in the header and an empty field in each old row — or "
            "move runs.tsv aside; appending would shift columns silently.")


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


_SNAPSHOT_CAP = 2 * 1024 * 1024   # a "source file" above 2 MB is data


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
    try:
        r = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "."],
                           cwd=script_dir, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
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
        print(f"runlog: entry script is UNTRACKED — copied {len(copied)} source "
              f"file(s) to source-untracked/. Best practice: commit BEFORE the "
              f"run, then the diff carries the provenance. ({', '.join(copied[:5])}"
              + (" ...)" if len(copied) > 5 else ")"))
    return copied


class Run:
    def __init__(self, experiment: str, config: dict, base_dir: Path,
                 data: dict | None = None, long: bool = False):
        # Detach gate (scar 2026-08-13, twice in one evening): a long run
        # started in a Claude Code foreground shell dies with the 10-min tool
        # timeout — the kill takes the whole process group, run and lock with
        # it. `long=True` is the script's own declaration (the --full stage
        # sets it); the gate refuses the foreground start BEFORE any work.
        if (long and os.environ.get("CLAUDECODE")
                and not os.environ.get("LABKIT_DETACHED")):
            raise SystemExit(
                "runlog: this run declares long=True and sits in a Claude Code "
                "foreground shell — the tool timeout would kill the process "
                "group mid-run (2026-08-13). Start it detached:\n"
                "  runlog start -- <the same command>\n"
                "or, if the caller already detached it (run_in_background, "
                "nohup+setsid), acknowledge with LABKIT_DETACHED=1.")
        self.run_id = time.strftime("%Y-%m-%dT%H-%M-%S") + "_" + uuid.uuid4().hex[:4]
        self.experiment = experiment
        self.script = Path(sys.argv[0]).name if sys.argv[0] else "<interactive>"
        self.base = base_dir
        _check_run_index(base_dir)                        # raises before any work
        self._data = _describe(data) if data else {}   # raises on leak, before mkdir
        self.dir = base_dir / "runs" / self.run_id
        self.dir.mkdir(parents=True, exist_ok=False)
        self._config = dict(config)
        self._outputs: list[Path] = []
        self._metrics: dict = {}
        self._note = ""
        self._t0 = time.monotonic()
        frozen = {"experiment": experiment, "script": self.script,
                  "script_sha": _snapshot_script(self.dir),
                  "untracked_sources": _snapshot_untracked_sources(self.dir),
                  "pid": os.getpid(),          # lets `active()` tell running from crashed
                  "git": _git_state(base_dir),
                  "git_full": _git(["rev-parse", "HEAD"], base_dir),
                  "python": sys.version.split()[0],
                  "env": _env_state(base_dir),
                  "models_resolved": _resolve_models(self._config),
                  "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                  "data": self._data,
                  "config": self._config}
        (self.dir / "config.json").write_text(
            json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
        # A dirty tree makes the commit hash a lie: save what it doesn't cover.
        if _git(["status", "--porcelain"], base_dir):
            (self.dir / "uncommitted.patch").write_text(
                _git(["diff", "HEAD"], base_dir), encoding="utf-8")

    def output(self, *paths) -> None:
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
        p = self.dir / name
        p.write_text(content, encoding="utf-8")
        return p

    def metrics(self, **kv) -> None:
        self._metrics.update(kv)

    def note(self, text: str) -> None:
        self._note = text

    def _finalize(self) -> None:
        self._metrics.setdefault("duration_s", round(time.monotonic() - self._t0, 1))
        if self._outputs:
            rows = []
            for p in self._outputs:
                if p.exists():
                    text_lines = sum(1 for _ in p.open("rb"))
                    rows.append({"path": str(p), "sha256": _sha256(p)[:16],
                                 "lines": text_lines})
                else:
                    rows.append({"path": str(p), "sha256": None, "lines": None,
                                 "note": "registered, but absent at end of run"})
            (self.dir / "outputs.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.dir / "metrics.json").write_text(
            json.dumps(self._metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        index = self.base / "runs.tsv"
        if not index.exists():
            index.write_text("\t".join(RUN_INDEX_COLS) + "\n", encoding="utf-8")
        row = [self.run_id, _git_state(self.base), self.script,
               json.dumps(self._data, ensure_ascii=False, sort_keys=True),
               json.dumps(self._config, ensure_ascii=False, sort_keys=True),
               json.dumps(self._metrics, ensure_ascii=False, sort_keys=True),
               self._note]
        with index.open("a", encoding="utf-8") as f:
            f.write("\t".join(c.replace("\t", " ").replace("\n", " ") for c in row) + "\n")
        dur = self._metrics.get("duration_s", 0)
        if os.environ.get("LABKIT_NOTIFY") == "1" or dur >= _NOTIFY_MIN_S:
            _notify(f"run finished: {self.experiment}",
                    f"{self.run_id} · {dur}s · {len(self._metrics)} metric(s)")



def _command_of(pid: int) -> str | None:
    """Command line of a process, or None if unreadable."""
    try:
        r = subprocess.run(["ps", "-o", "command=", "-p", str(pid)],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None


def _is_alive(pid, script) -> bool | None:
    """Is THIS run still going? True / False / None (undecidable).

    The PID alone is not enough, and that is no theoretical concern: on
    2026-08-15 `runlog` reported a run from August 13 as running because the
    OS had meanwhile recycled the PID to a macOS service
    (`RemoteManagement`). Anyone following the working standard's "look,
    don't ask" got a wrong answer — and would not have restarted a run that
    was long dead.

    So the command line is additionally checked for the recorded script
    name. If that cannot be decided (no `ps`, no script name), the answer
    is **None**, not `True`: an "unknown" is usable, a false "running" is
    not.
    """
    if not isinstance(pid, int):
        return None
    try:
        os.kill(pid, 0)              # signal 0: existence check only
    except ProcessLookupError:
        return False
    except PermissionError:
        pass                         # exists, belongs to someone else
    cmd = _command_of(pid)
    if cmd is None or not script:
        return None
    return script in cmd


# Public name for the same check: the endpoint lease needs it too, and PID
# liveness must have ONE home (the recycled-PID scar above was expensive
# enough once).
is_alive = _is_alive


def active(base_dir: str | Path) -> list[dict]:
    """Runs in this area that never finished: dir with config.json, no metrics.json.

    This is what makes parallel work cheap — before starting an experiment you
    LOOK instead of asking: which runs are live, and which files do they read
    and write (their config.json says). `alive` distinguishes a running process
    from a crashed one by checking the recorded pid.

        runlog <area>        (the installed console command)
    """
    out = []
    for d in sorted((Path(base_dir) / "runs").glob("*")):
        cfg_file = d / "config.json"
        if not cfg_file.is_file() or (d / "metrics.json").is_file():
            continue
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        alive = _is_alive(cfg.get("pid"), cfg.get("script"))
        out.append({"run_id": d.name, "dir": str(d), "alive": alive, **cfg})
    return out


class run:
    """Context manager: `with runlog.run("name", config={...}, data={...}) as r:`"""

    def __init__(self, experiment: str, config: dict,
                 base_dir: str | Path | None = None, data: dict | None = None,
                 long: bool = False):
        base = Path(base_dir) if base_dir else Path(sys.argv[0]).resolve().parent
        self._run = Run(experiment, config, base, data, long=long)

    def __enter__(self) -> Run:
        return self._run

    def __exit__(self, exc_type, _exc, _tb) -> bool:
        if exc_type is None:
            self._run._finalize()   # crash -> dir stays without metrics.json (visible)
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
        state = {True: "running", False: "crashed", None: "unknown"}[r["alive"]]
        print(f"{r['run_id']}  {state:8s} pid={r.get('pid')}  {r.get('script')}")
        print(f"    {json.dumps(r.get('config', {}), ensure_ascii=False)[:160]}")


def _finished_line(area: Path) -> str:
    runs = sorted(area.glob("runs/*/metrics.json"))
    if not runs:
        return "no finished runs"
    m = json.loads(runs[-1].read_text(encoding="utf-8"))
    keys = ", ".join(list(m)[:6])
    return f"last finished: {runs[-1].parent.name} ({keys})"


def _wait(area: str, max_seconds: float | None, interval: float,
          follow: bool, notify: bool) -> int:
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
        crashed = [r for r in live if r["alive"] is False]
        if crashed:
            for r in crashed:
                print(f"{r['run_id']}  CRASHED  pid={r.get('pid')}  "
                      f"{r.get('script')}  ({r['dir']}: config.json without "
                      f"metrics.json)")
            if notify:
                _notify("runlog --wait", f"{area}: run crashed")
            return 2
        if follow:
            stamp = time.strftime("%H:%M:%S")
            extra = _newest_output(apath)
            print(f"[{stamp}] {len(live)} open run(s): "
                  + ", ".join(r["run_id"] for r in live)
                  + (f" · {extra}" if extra else ""), flush=True)
        if max_seconds is not None and time.monotonic() - t0 >= max_seconds:
            extra = _newest_output(apath)
            print(f"{area}: still running after {int(max_seconds)}s — "
                  + ", ".join(f"{r['run_id']} pid={r.get('pid')}" for r in live)
                  + (f" · {extra}" if extra else "")
                  + "\nre-check: runlog " + area + " --wait")
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
                    "output to a log file, return immediately.")
    ap.add_argument("--log", default=None,
                    help="log file (default: output/start-<ts>.log)")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="-- command and arguments")
    args = ap.parse_args(argv)
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        ap.error("no command given — usage: runlog start -- <cmd ...>")
    log = Path(args.log) if args.log else \
        Path("output") / f"start-{time.strftime('%Y-%m-%dT%H-%M-%S')}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "LABKIT_DETACHED": "1"}
    with log.open("ab") as fh:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=fh,
                                stderr=fh, start_new_session=True, env=env)
    print(f"started detached: pid={proc.pid}  log={log}")
    print("status:  runlog .        wait:  runlog . --wait")
    return 0


def main(argv: list[str]) -> int:
    """Status, wait, follow or start — the run monitor of record."""
    if argv and argv[0] == "start":
        return _start(argv[1:])
    import argparse
    ap = argparse.ArgumentParser(
        prog="runlog",
        description="List open runs (dirs with a config.json but no "
                    "metrics.json) in an experiment area: run_id, state "
                    "(running/crashed/unknown via the recorded pid), script, "
                    "and the frozen config. 'Nachsehen statt nachfragen' — "
                    "check this before starting a run in a shared repo. "
                    "`--wait` blocks until the area is idle (exit 0), a run "
                    "crashed (exit 2) or --max-seconds passed (exit 3); "
                    "`--follow` prints a status line per interval until idle; "
                    "`runlog start -- <cmd>` detaches a run (own session, "
                    "log file) and returns.")
    ap.add_argument("area", nargs="?", default=".",
                    help="experiment area holding a runs/ dir (default: .)")
    ap.add_argument("--wait", action="store_true",
                    help="block until no open runs; exit 0/2/3 (idle/crashed/"
                         "still running at --max-seconds)")
    ap.add_argument("--follow", action="store_true",
                    help="like --wait but unbounded, one status line per "
                         "interval (for a human terminal)")
    ap.add_argument("--max-seconds", type=float, default=90.0,
                    help="--wait: give up after this long (default 90 — "
                         "safely under the shell tool's timeout)")
    ap.add_argument("--interval", type=float, default=None,
                    help="poll interval in s (default: 2 for --wait, "
                         "5 for --follow)")
    ap.add_argument("--notify", action="store_true",
                    help="macOS notification when the wait ends")
    args = ap.parse_args(argv)
    if args.follow:
        return _wait(args.area, None, args.interval or 5.0, True, args.notify)
    if args.wait:
        return _wait(args.area, args.max_seconds, args.interval or 2.0,
                     False, args.notify)
    _print_status(args.area, active(args.area))
    return 0


def cli() -> None:
    """Entry point for the installed `runlog` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
