"""runlog — minimal per-experiment run tracking (stdlib-only, no service).

Convention (Arbeitsstandard §2/§4): every run — pilots included — goes through
`with runlog.run(...)`. Each run gets a self-contained dir and one append-only
ledger row; PROTOCOL-<task>.md cites run_ids instead of pasting numbers.

    runs/<run_id>/config.json      frozen inputs: params + git state + data
    runs/<run_id>/metrics.json     outputs you declared
    runs/<run_id>/script-source.py  the script AS IT RAN (untracked or dirty
                                   code is in no commit and in no diff)
    runs/<run_id>/uncommitted.patch  the diff, IF the repo was dirty (tracked files only)
    runs/<run_id>/source-untracked/  untracked files next to the script, verbatim
    runs/<run_id>/<raw files>      verbatim model output etc. (save_raw)
    runs.tsv                       ledger: run_id git script data config metrics note

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
not silent. The ledger row is written on clean exit only.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

LEDGER_COLS = ["run_id", "git", "script", "data", "config", "metrics", "note"]
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
    they count as pinned-any rather than as drift.
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
    become a check.
    """
    from importlib.metadata import distributions

    pinned = {n: v for n, v in _parse_lock(lock).items()
              if n not in _FREEZE_OMITS}
    installed: dict[str, str] = {}
    for dist in distributions():
        name = (dist.metadata["Name"] or "").lower().replace("_", "-")
        if name and name not in _FREEZE_OMITS:
            installed[name] = dist.version
    drift = sum(1 for n, v in installed.items()
                if n not in pinned or (pinned[n] is not None and pinned[n] != v))
    drift += sum(1 for n in pinned if n not in installed)
    return drift


def _env_state(cwd: Path) -> str:
    """Interpreter + fingerprint of the nearest requirements.lock, plus drift.

    Ties a run to an *environment*, not just a Python version: a changed lock
    changes the hash, so runs from different environments stay distinguishable
    in the ledger. Records "unpinned" when no lock exists — visible, not silent.

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


def _check_ledger(base_dir: Path) -> None:
    """Refuse to run against a ledger whose header doesn't match LEDGER_COLS.

    Appending to an old-format runs.tsv would not error — the columns would
    just shift silently, and every row after the format change would be
    misread. Fail before the run instead, with the migration spelled out.
    """
    ledger = base_dir / "runs.tsv"
    if not ledger.exists():
        return
    with ledger.open(encoding="utf-8") as f:
        found = f.readline().rstrip("\n").split("\t")
    if found != LEDGER_COLS:
        raise RuntimeError(
            f"runs.tsv columns {found} don't match this runlog "
            f"({LEDGER_COLS}). Migrate the ledger — insert the missing "
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
                 data: dict | None = None):
        self.run_id = time.strftime("%Y-%m-%dT%H-%M-%S") + "_" + uuid.uuid4().hex[:4]
        self.experiment = experiment
        self.script = Path(sys.argv[0]).name if sys.argv[0] else "<interactive>"
        self.base = base_dir
        _check_ledger(base_dir)                        # raises before any work
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
        ledger = self.base / "runs.tsv"
        if not ledger.exists():
            ledger.write_text("\t".join(LEDGER_COLS) + "\n", encoding="utf-8")
        row = [self.run_id, _git_state(self.base), self.script,
               json.dumps(self._data, ensure_ascii=False, sort_keys=True),
               json.dumps(self._config, ensure_ascii=False, sort_keys=True),
               json.dumps(self._metrics, ensure_ascii=False, sort_keys=True),
               self._note]
        with ledger.open("a", encoding="utf-8") as f:
            f.write("\t".join(c.replace("\t", " ").replace("\n", " ") for c in row) + "\n")



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
        os.kill(pid, 0)              # Signal 0: nur Existenzpruefung
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
                 base_dir: str | Path | None = None, data: dict | None = None):
        base = Path(base_dir) if base_dir else Path(sys.argv[0]).resolve().parent
        self._run = Run(experiment, config, base, data)

    def __enter__(self) -> Run:
        return self._run

    def __exit__(self, exc_type, _exc, _tb) -> bool:
        if exc_type is None:
            self._run._finalize()   # crash -> dir stays without metrics.json (visible)
        return False


def main(argv: list[str]) -> int:
    """What is running in this area? Lists runs without a metrics.json."""
    import argparse
    ap = argparse.ArgumentParser(
        prog="runlog",
        description="List open runs (dirs with a config.json but no "
                    "metrics.json) in an experiment area: run_id, state "
                    "(running/crashed/unknown via the recorded pid), script, "
                    "and the frozen config. 'Nachsehen statt nachfragen' — "
                    "check this before starting a run in a shared repo.")
    ap.add_argument("area", nargs="?", default=".",
                    help="experiment area holding a runs/ dir (default: .)")
    args = ap.parse_args(argv)
    area = args.area
    live = active(area)
    if not live:
        print(f"{area}: no open runs")
    for r in live:
        state = {True: "running", False: "crashed", None: "unknown"}[r["alive"]]
        print(f"{r['run_id']}  {state:8s} pid={r.get('pid')}  {r.get('script')}")
        print(f"    {json.dumps(r.get('config', {}), ensure_ascii=False)[:160]}")
    return 0


def cli() -> None:
    """Entry point for the installed `runlog` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
