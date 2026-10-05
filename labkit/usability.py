"""usability — stage a probe lab repo for a cold agent, then score the trace.

    usability stage <dir> [--venv PATH]     a fresh lab repo with one kept-number task
    usability score <dir>                   number · binding · log → one table, one JSON

Why this exists (2026-10-05): the doctrine grew by scars, every scar added
a gate, and nobody measured what the whole chain costs for the simplest
case — one deterministic number, kept. uniagent area 01 needed four days,
three freezes and three agent audits for a seven-second run. A rule that
costs more than the error it prevents is a rule to cut, but only a trace
shows which one; this is the trace.

stage
    Stamps a lab repo through the house scaffolder (`arbeitsstandard-init.py
    --lab`, then `--exp docs-per-case`), commits it, plants a fixture with a
    known answer (twelve cases, their input files; the answer is recounted
    from the files at score time, never written down) and TASK.md — the
    prompt a cold agent gets, from `usability-task.md.template`, with the log
    contract and the metrics key the number must land under. A venv with
    labkit is created unless `--venv` links an existing one. What was
    measured is pinned in `<dir>.probe.json`: the labkit the probe venv
    holds, a sha over the scaffolder and the templates it stamps, the flags.
    Side effects: a git repo with two commits, a venv or a symlink, two
    sidecar files next to <dir>.

score
    Reads the latest run of the stamped area — the number under the named
    key, the protocol the run is bound to (and whether it is frozen), the
    cost tier — and the agent's log (`<dir>.log.md`, one line per step:
    `HH:MM:SS · <tag> · text`, tag in read/run/edit/unsure/gate). Prints
    wall-clock (first to last stamp; the agent's time outside the log is
    not seen), counts per tag and whether the kept number equals the truth.
    Writes `<dir>.score.json`. Exit 0 when the number is right and bound.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

RES = Path.home() / ".claude" / "resources"
#: The house scaffolder — the thing under test, outside this package.
SCAFFOLDER = RES / "tools" / "arbeitsstandard-init.py"
#: What the scaffolder stamps into an area; their sha pins the measured
#: condition. Script skeletons are house masters (RES); the two protocol
#: forms ship with labkit — the scaffolder's `master_path` reads them there.
STAMPED = (*(RES / t for t in ("prepare-script.py.template", "measure-script.py.template",
                               "analyze-script.py.template", "test-area.py.template")),
           *(Path(__file__).resolve().parent / t
             for t in ("experiment-protocol.md.template", "measurement-protocol.md.template")))
AREA = "docs-per-case"
METRIC_KEY = "mean_docs_per_case"
#: files per case — twelve cases; the truth is their mean, recounted at score time
DOCS_PER_CASE = (4, 4, 3, 4, 4, 3, 2, 3, 4, 3, 2, 6)
LOG_TAGS = ("read", "run", "edit", "unsure", "gate")
LOG_LINE = re.compile(r"^(\d\d):(\d\d):(\d\d)\s*·\s*(\w+)\s*·\s*(.*)$")
#: The bar: one kept number in this many minutes. Set by hand (2026-10-05),
#: not derived — the first traces decide whether it is the right one.
TARGET_MINUTES = 5
TOL = 1e-9


def _sh(args: list[str], cwd: Path) -> str:
    """Run a command in `cwd`; a non-zero exit is a refusal with its output."""
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"usability: `{' '.join(args)}` failed in {cwd}:\n"
                         f"{r.stdout}{r.stderr}")
    return r.stdout


def _labkit_spec(python: Path) -> str:
    """The labkit line of `pip freeze` under `python` — the one this
    interpreter would import, named the way pip names it."""
    out = _sh([str(python), "-m", "pip", "freeze"], python.parent)
    lines = [ln for ln in out.splitlines()
             if re.match(r"^(-e\s+.*[/#]labkit\b|labkit\s*[=@])", ln)]
    if len(lines) != 1:
        raise SystemExit(f"usability: expected one labkit line in `pip freeze` of "
                         f"{python}, got {lines!r}")
    return lines[0].strip()


def scaffold_sha() -> str:
    """sha256 (12 hex) over the scaffolder and the templates it stamps."""
    h = hashlib.sha256()
    for p in (SCAFFOLDER, *STAMPED):
        if not p.is_file():
            raise SystemExit(f"usability: stamped master missing: {p}")
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


@dataclass(frozen=True)
class Probe:
    """What was staged — pinned so two scores can be told apart."""
    staged: str
    area: str                 # the stamped area's directory name
    metric_key: str
    labkit_installed: str     # pip's name for the labkit in the probe venv
    scaffold_sha: str         # scaffolder + stamped templates
    scaffold_flags: list[str]
    target_minutes: int


def plant_fixture(root: Path) -> float:
    """Twelve cases with a known number of input files each under
    data/raw/inputs/<case>/ and data/raw/cases.jsonl; returns the mean.
    Side effects: writes those files."""
    inputs = root / "data" / "raw" / "inputs"
    rows = []
    for i, n in enumerate(DOCS_PER_CASE, 1):
        case = f"antrag-{i:02d}"
        d = inputs / case
        d.mkdir(parents=True, exist_ok=True)
        for k in range(1, n + 1):
            (d / f"document-{k}.txt").write_text(
                f"case {case}, document {k} of {n}\n", encoding="utf-8")
        rows.append({"case_id": case, "inputs": "data/raw/inputs"})
    (root / "data" / "raw" / "cases.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return recount(root)


def recount(root: Path) -> float:
    """The truth, from the planted files — not from a number on disk."""
    rows = [json.loads(line) for line in
            (root / "data" / "raw" / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    counts = [sum(1 for f in (root / r["inputs"] / r["case_id"]).iterdir()
                  if not f.name.startswith(".")) for r in rows]
    return sum(counts) / len(counts)


def _sidecar(root: Path, suffix: str) -> Path:
    return root.parent / f"{root.name}.{suffix}"


def stage(root: Path, venv: Path | None) -> int:
    """Side effects: see module docstring."""
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"usability: {root} exists and is not empty — stage into "
                         f"a fresh directory, the probe must start cold")
    if not SCAFFOLDER.is_file():
        raise SystemExit(f"usability: scaffolder not found: {SCAFFOLDER}")
    if venv is not None and not (venv / "bin" / "python").is_file():
        raise SystemExit(f"usability: --venv {venv} has no bin/python")
    sha = scaffold_sha()
    flags = ["--lab", "--name", root.name, "--lang", "deutsch"]
    root.mkdir(parents=True, exist_ok=True)
    _sh([sys.executable, str(SCAFFOLDER), str(root), *flags], root)
    _sh(["git", "init", "-q", "."], root)
    _sh(["git", "add", "-A"], root)
    _sh(["git", "commit", "-qm", "Scaffold: a probe lab repo for the usability trace"], root)
    _sh([sys.executable, str(SCAFFOLDER), str(root), "--exp", AREA], root)
    areas = sorted(p.name for p in (root / "experiments").glob(f"*-{AREA}"))
    if len(areas) != 1:
        raise SystemExit(f"usability: expected one stamped area *-{AREA}, got {areas}")
    plant_fixture(root)
    if venv is not None:
        os.symlink(venv.resolve(), root / ".venv")
    else:
        _sh([sys.executable, "-m", "venv", ".venv"], root)
        _sh([str(root / ".venv" / "bin" / "pip"), "install", "-q",
             _labkit_spec(Path(sys.executable))], root)
    probe = Probe(staged=time.strftime("%Y-%m-%dT%H:%M:%S"), area=areas[0],
                  metric_key=METRIC_KEY,
                  labkit_installed=_labkit_spec(root / ".venv" / "bin" / "python"),
                  scaffold_sha=sha, scaffold_flags=flags, target_minutes=TARGET_MINUTES)
    log = _sidecar(root, "log.md")
    log.write_text("", encoding="utf-8")
    task = (Path(__file__).resolve().parent / "usability-task.md.template").read_text(encoding="utf-8")
    for key, val in (("<metric_key>", METRIC_KEY), ("<area>", areas[0]),
                     ("<log>", str(log)), ("<target>", str(TARGET_MINUTES))):
        task = task.replace(key, val)
    (root / "TASK.md").write_text(task, encoding="utf-8")
    _sh(["git", "add", "-A"], root)
    _sh(["git", "commit", "-qm", "Probe: the area, the fixture and TASK.md"], root)
    _sidecar(root, "probe.json").write_text(json.dumps(asdict(probe), indent=1), encoding="utf-8")
    print(f"staged {root}\n  task:  {root / 'TASK.md'}\n  log:   {log}\n"
          f"  probe: {_sidecar(root, 'probe.json')}\n"
          f"next: hand TASK.md to a cold agent (fresh context, no history), "
          f"then `usability score {root}`")
    return 0


@dataclass(frozen=True)
class LogTrace:
    """What the agent's log says: stamps and counts per tag."""
    lines: int
    wall_seconds: int | None    # max − min over the stamps; None below two
    monotonic: bool             # stamps never run backwards
    read: int
    run: int
    edit: int
    unsure: int
    gate: int
    untagged: int               # off-contract lines, counted, never dropped


def parse_log(text: str) -> LogTrace:
    counts = {t: 0 for t in LOG_TAGS}
    untagged = 0
    stamps: list[int] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        m = LOG_LINE.match(line)
        if not m or m.group(4).lower() not in counts:
            untagged += 1
            continue
        counts[m.group(4).lower()] += 1
        stamps.append(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)))
    wall = (max(stamps) - min(stamps)) if len(stamps) >= 2 else None
    return LogTrace(lines=len(stamps) + untagged, wall_seconds=wall,
                    monotonic=all(a <= b for a, b in zip(stamps, stamps[1:])),
                    untagged=untagged, **counts)


def latest_run(area: Path) -> Path | None:
    """The newest completed run — run_ids start with the timestamp, so
    their sort order is their start order (runlog.Run)."""
    runs = sorted(p for p in (area / "runs").glob("*") if (p / "metrics.json").is_file()) \
        if (area / "runs").is_dir() else []
    return runs[-1] if runs else None


@dataclass(frozen=True)
class Score:
    probe: Probe
    run_id: str | None
    number: float | None       # metrics[metric_key], or None when absent
    expected: float
    number_ok: bool
    bound_to: str | None       # config["protocol"]["path"]
    frozen: bool | None
    cost_tier: str | None
    log: LogTrace | None


def score(root: Path) -> int:
    probe_file = _sidecar(root, "probe.json")
    if not probe_file.is_file():
        raise SystemExit(f"usability: {probe_file} missing — was {root} staged here?")
    probe = Probe(**json.loads(probe_file.read_text(encoding="utf-8")))
    area = root / "experiments" / probe.area
    expected = recount(root)
    run = latest_run(area)
    number = bound_to = frozen = tier = None
    if run is not None:
        config_file = run / "config.json"
        if not config_file.is_file():
            raise SystemExit(f"usability: {run} has metrics.json but no config.json")
        metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        config = json.loads(config_file.read_text(encoding="utf-8"))
        value = metrics.get(probe.metric_key)
        number = (float(value) if isinstance(value, (int, float))
                  and not isinstance(value, bool) else None)
        bound_to = (config.get("protocol") or {}).get("path")
        tier = config.get("cost_tier")
        if bound_to:
            from labkit.protocol_check import FROZEN_YES  # lazy: labkit modules import each other
            p = Path(bound_to)
            p = p if p.is_absolute() else area / p
            frozen = (bool(FROZEN_YES.search(p.read_text(encoding="utf-8")))
                      if p.is_file() else None)
    log = _sidecar(root, "log.md")
    trace = parse_log(log.read_text(encoding="utf-8")) if log.is_file() else None
    sc = Score(probe=probe, run_id=run.name if run else None, number=number,
               expected=expected,
               number_ok=number is not None and abs(number - expected) <= TOL,
               bound_to=bound_to, frozen=frozen, cost_tier=tier, log=trace)
    _sidecar(root, "score.json").write_text(json.dumps(asdict(sc), indent=1), encoding="utf-8")

    rows = [("labkit in probe", probe.labkit_installed),
            ("scaffold sha", probe.scaffold_sha),
            ("run", sc.run_id or "none"),
            (f"number ({probe.metric_key})", "absent" if number is None else str(number)),
            ("equals the truth", "yes" if sc.number_ok else f"NO (truth {expected})"),
            ("bound to", bound_to or "NOTHING"),
            ("frozen", {True: "yes", False: "no", None: "n/a"}[frozen]),
            ("cost tier", tier or "undeclared")]
    if trace is None:
        rows.append(("log", "missing — no trace, no measurement"))
    else:
        w = trace.wall_seconds
        rows.append(("wall-clock (log span)",
                     f"{w // 60}m{w % 60:02d}s" if w is not None else "n/a"))
        if not trace.monotonic:
            rows.append(("log order", "stamps run backwards — span is unreliable"))
        rows += [(f"steps · {t}", str(getattr(trace, t))) for t in (*LOG_TAGS, "untagged")]
    width = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"  {k:<{width}}  {v}")
    over = (trace is not None and trace.wall_seconds is not None
            and trace.wall_seconds > probe.target_minutes * 60)
    print(f"  target: one kept number under {probe.target_minutes} min"
          + (" — MISSED" if over else ""))
    print(f"→ {_sidecar(root, 'score.json')}")
    return 0 if sc.number_ok and bound_to else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="usability",
                                 description=(__doc__ or "").split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage", help="stamp a probe lab repo with one kept-number task")
    s.add_argument("dir")
    s.add_argument("--venv", help="link this venv instead of creating one")
    c = sub.add_parser("score", help="number, binding and log of a finished probe")
    c.add_argument("dir")
    args = ap.parse_args(argv)
    root = Path(args.dir).resolve()
    if args.cmd == "stage":
        return stage(root, Path(args.venv).resolve() if args.venv else None)
    return score(root)


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
