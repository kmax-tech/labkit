"""usability — stage a probe lab repo for a cold agent, then score the trace.

    usability stage <dir> [--venv PATH]     a fresh lab repo with one kept-number task
    usability score <dir> [--transcript F]  number · binding · log (· transcript) → one table, one JSON
    usability trace <transcript>            the agent's timeline, one line per tool call

Why this exists (2026-10-05): the doctrine grew by scars, every scar added
a gate, and nobody measured what the whole chain costs for the simplest
case — one deterministic number, kept. uniagent area 01 needed four days,
three freezes and three agent audits for a seven-second run. A rule that
costs more than the error it prevents is a rule to cut, but only a trace
shows which one; this is the trace.

stage
    Stamps a lab repo through the house scaffolder (`arbeitsstandard-init.py
    --lab`, then `--exp <area>`), commits it, plants the task's fixture —
    `--task count` (default): twelve cases and their files, a deterministic
    mean; `--task judge`: twelve sentences with a gold label, a model's
    accuracy, no truth, only a range and a null condition to report — with a
    known answer (twelve cases, their input files; the answer is recounted
    from the files at score time, never written down) and TASK.md — the
    task sheet, from `usability-task-<task>.md.template`, with the log
    contract and the metrics key the number must land under — and
    `<dir>.prompt.md`, the prompt a cold agent gets: the repo's CLAUDE.md
    as a session loads it, then the pointer to TASK.md. A venv with
    labkit is created unless `--venv` links an existing one. What was
    measured is pinned in `<dir>.probe.json`: the labkit the probe venv
    holds, a sha over the scaffolder and the templates it stamps, the flags.
    Side effects: a git repo with three commits, a venv or a symlink, three
    sidecar files next to <dir> (probe.json, log.md, prompt.md).

score
    Reads the latest run of the stamped area — the number under the named
    key, the protocol the run is bound to (and whether it is frozen), the
    cost tier — and the agent's log (`<dir>.log.md`, one line per step:
    `HH:MM:SS · <tag> · text`, tag in read/run/edit/unsure/gate). Prints
    wall-clock (first to last stamp; the agent's time outside the log is
    not seen), counts per tag and whether the kept number equals the truth.
    Writes `<dir>.score.json`. Exit 0 when the number is right and bound.
    `--transcript` adds what the agent's session transcript shows — the
    log is self-report, the transcript a measurement (agent_transcript).
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

from labkit import agent_transcript, runs

RES = Path.home() / ".claude" / "resources"
#: The house scaffolder — the thing under test, outside this package.
SCAFFOLDER = RES / "tools" / "arbeitsstandard-init.py"
#: What the scaffolder stamps into an area; their sha pins the measured
#: condition. Script skeletons are house masters (RES); the two protocol
#: forms ship with labkit — the scaffolder's `master_path` reads them there.
STAMPED = (
    *(
        RES / t
        for t in (
            "prepare-script.py.template",
            "measure-script.py.template",
            "analyze-script.py.template",
            "test-area.py.template",
            "measure-quick-script.py.template",
            "test-quick.py.template",
        )
    ),
    Path(__file__).resolve().parent / "experiment-protocol.md.template",
)
#: files per case — twelve cases; the truth is their mean, recounted at score time
DOCS_PER_CASE = (4, 4, 3, 4, 4, 3, 2, 3, 4, 3, 2, 6)
#: twelve sentences, six causal, six not — the judge task's items; the kept
#: number (accuracy) is the model's, so it has no truth to recount, only a range
CLAIMS = (
    ("c01", "Because the road was icy, the bus arrived twenty minutes late.", "causal"),
    ("c02", "The bus arrived twenty minutes late, and the road was icy.", "not_causal"),
    (
        "c03",
        "Sales rose after the price was cut, so the cut drove the demand.",
        "causal",
    ),
    ("c04", "Sales rose in March; the price was cut in the same month.", "not_causal"),
    ("c05", "The bridge collapsed due to corrosion in its main cables.", "causal"),
    ("c06", "The bridge was inspected in May and collapsed in June.", "not_causal"),
    ("c07", "Switching to the new compiler made the build twice as fast.", "causal"),
    (
        "c08",
        "The build is twice as fast on the new machine with the new compiler.",
        "not_causal",
    ),
    ("c09", "Her headache went away because she drank water.", "causal"),
    ("c10", "Her headache went away; she had also drunk some water.", "not_causal"),
    (
        "c11",
        "The vaccine prevented the outbreak from spreading beyond the village.",
        "causal",
    ),
    (
        "c12",
        "The outbreak stayed within the village, where most people were vaccinated.",
        "not_causal",
    ),
)
#: The tasks the harness stages: area name, metrics key, task template.
TASKS = {
    "count": {
        "area": "docs-per-case",
        "metric_key": "mean_docs_per_case",
        "template": "usability-task-count.md.template",
    },
    "judge": {
        "area": "causal-claims-judge",
        "metric_key": "c1_accuracy",
        "template": "usability-task-judge.md.template",
    },
}
#: (cost tier, model in the loop) per task: what the house route stamps for
#: it (`lib exp --cost seconds`, plus `--model` with a model in the loop).
#: Staged without them, the count got the full form and the model skeleton
#: and every agent spent its time deleting it (probe 2026-10-07) — a cost
#: of the staging, not of the route.
TASK_STAMP: dict[str, tuple[str, bool]] = {
    "count": ("seconds", False),
    "judge": ("seconds", True),
}
LOG_TAGS = ("read", "run", "edit", "unsure", "gate")
LOG_LINE = re.compile(r"^(\d\d):(\d\d):(\d\d)\s*·\s*(\w+)\s*·\s*(.*)$")
#: a `read` of these is the agent learning the contract from the wrong place
#: — the area's README card should have sufficed (2026-10-05, four of four read on)
SOURCE_READ = re.compile(
    r"labkit/\w+\.py|labkit[ /](runlog|recheck|protocol_check|llm|batch|finalize|preflight)|arbeitsstandard",
    re.I,
)
#: The bar: one kept number in this many minutes. Set by hand (2026-10-05),
#: not derived — the first traces decide whether it is the right one.
TARGET_MINUTES = 5
TOL = 1e-9


def _sh(args: list[str], cwd: Path) -> str:
    """Run a command in `cwd`; a non-zero exit is a refusal with its output."""
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(
            f"usability: `{' '.join(args)}` failed in {cwd}:\n{r.stdout}{r.stderr}"
        )
    return r.stdout


def _labkit_spec(python: Path) -> str:
    """The labkit line of `pip freeze` under `python` — the one this
    interpreter would import, named the way pip names it."""
    out = _sh([str(python), "-m", "pip", "freeze"], python.parent)
    lines = [
        ln
        for ln in out.splitlines()
        if re.match(r"^(-e\s+.*[/#]labkit\b|labkit\s*[=@])", ln)
    ]
    if len(lines) != 1:
        raise SystemExit(
            f"usability: expected one labkit line in `pip freeze` of "
            f"{python}, got {lines!r}"
        )
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
    task: str  # key into TASKS
    area: str  # the stamped area's directory name
    metric_key: str
    labkit_installed: str  # pip's name for the labkit in the probe venv
    scaffold_sha: str  # scaffolder + stamped templates
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
                f"case {case}, document {k} of {n}\n", encoding="utf-8"
            )
        rows.append({"case_id": case, "inputs": "data/raw/inputs"})
    (root / "data" / "raw" / "cases.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    return recount(root)


def plant_claims(root: Path) -> None:
    """The judge task's items: data/raw/claims.jsonl. Side effects: writes it."""
    raw = root / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "claims.jsonl").write_text(
        "".join(
            json.dumps({"id": i, "text": t, "gold": g}) + "\n" for i, t, g in CLAIMS
        ),
        encoding="utf-8",
    )


def recount(root: Path) -> float:
    """The truth, from the planted files — not from a number on disk."""
    rows = [
        json.loads(line)
        for line in (root / "data" / "raw" / "cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    counts = [
        sum(
            1
            for f in (root / r["inputs"] / r["case_id"]).iterdir()
            if not f.name.startswith(".")
        )
        for r in rows
    ]
    return sum(counts) / len(counts)


def stamp_flags(task: str, cost: str | None, model: bool) -> tuple[str | None, bool]:
    """(cost tier or None, model) the scaffolder gets: the task's route stamp
    (TASK_STAMP) unless `cost` names a tier; "unset" stamps none."""
    default_cost, default_model = TASK_STAMP[task]
    if cost is None:
        cost = default_cost
    return (None if cost == "unset" else cost), (model or default_model)


def agent_prompt(root: Path) -> str:
    """The prompt a cold agent gets: the repo's CLAUDE.md first, the way a
    Claude Code session started in the repo loads it into context, then the
    pointer to TASK.md. Handed only a pointer, every agent fetched CLAUDE.md
    with `cat` and read all of it before any section marker could steer
    it — a cost of the probe, not of a real session (re-measure 2026-10-07,
    rounds 1 to 4)."""
    claude = root / "CLAUDE.md"
    if not claude.is_file():
        raise SystemExit(f"usability: {claude} missing — the scaffolder stamps it")
    return (
        f"Contents of {claude} (project instructions, loaded the way a "
        f"session in this repository loads them):\n\n"
        f"{claude.read_text(encoding='utf-8')}\n"
        f"---\n\n"
        f"Your working directory is {root} — a lab repository. Read TASK.md "
        f"there and do exactly what it says; it names the log file you keep. "
        f"Every shell command must first `cd` into that directory (your shell "
        f"does not start there). Work only inside it; do not touch sibling "
        f"directories. When done, give the report TASK.md asks for.\n"
    )


def _sidecar(root: Path, suffix: str) -> Path:
    return root.parent / f"{root.name}.{suffix}"


def stage(
    root: Path,
    venv: Path | None,
    cost: str | None = None,
    task: str = "count",
    model: bool = False,
) -> int:
    """Side effects: see module docstring. `task` picks the fixture, the task
    sheet and the default stamp (TASKS); `cost` overrides the stamped tier
    ("unset" leaves it to the agent), `model` adds the model skeleton."""
    spec = TASKS[task]
    cost, model = stamp_flags(task, cost, model)
    area_name, metric_key = spec["area"], spec["metric_key"]
    if root.exists() and any(root.iterdir()):
        raise SystemExit(
            f"usability: {root} exists and is not empty — stage into "
            f"a fresh directory, the probe must start cold"
        )
    if not SCAFFOLDER.is_file():
        raise SystemExit(f"usability: scaffolder not found: {SCAFFOLDER}")
    if venv is not None and not (venv / "bin" / "python").is_file():
        raise SystemExit(f"usability: --venv {venv} has no bin/python")
    sha = scaffold_sha()
    flags = ["--lab", "--name", root.name, "--lang", "deutsch"]
    root.mkdir(parents=True, exist_ok=True)
    _sh([sys.executable, str(SCAFFOLDER), str(root), *flags], root)
    _sh(["git", "init", "-q", "."], root)
    # The probe's own commits skip the pre-commit hook: a freshly stamped
    # protocol is all placeholders by design, and the hook is the agent's
    # gate, not the stamper's (`lib exp` sets core.hooksPath, 2026-10-05).
    _sh(["git", "add", "-A"], root)
    _sh(
        [
            "git",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            "Scaffold: a probe lab repo for the usability trace",
        ],
        root,
    )
    exp_flags = [
        "--exp",
        area_name,
        *(["--cost", cost] if cost else []),
        *(["--model", "haiku"] if model else []),
    ]
    _sh([sys.executable, str(SCAFFOLDER), str(root), *exp_flags], root)
    areas = sorted(p.name for p in (root / "experiments").glob(f"*-{area_name}"))
    if len(areas) != 1:
        raise SystemExit(
            f"usability: expected one stamped area *-{area_name}, got {areas}"
        )
    if task == "count":
        plant_fixture(root)
    else:
        plant_claims(root)
    if venv is not None:
        os.symlink(venv.resolve(), root / ".venv")
    else:
        _sh([sys.executable, "-m", "venv", ".venv"], root)
        _sh(
            [
                str(root / ".venv" / "bin" / "pip"),
                "install",
                "-q",
                _labkit_spec(Path(sys.executable)),
            ],
            root,
        )
    # The hooks, as a real setup installs them (`labkit-hooks install`, labkit
    # 0.51): pre-commit with finalize, core.hooksPath, the claude-hook entries.
    _sh([str(root / ".venv" / "bin" / "labkit-hooks"), "install"], root)
    # requirements.lock from the probe venv: runlog warns "env unpinned" without
    # it and every cold agent stopped to generate one (2026-10-05).
    (root / "requirements.lock").write_text(
        _sh([str(root / ".venv" / "bin" / "pip"), "freeze"], root), encoding="utf-8"
    )
    _sh(["git", "add", "-A"], root)
    _sh(
        [
            "git",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            "Probe: requirements.lock and the hooks of the probe venv",
        ],
        root,
    )
    probe = Probe(
        staged=time.strftime("%Y-%m-%dT%H:%M:%S"),
        task=task,
        area=areas[0],
        metric_key=metric_key,
        labkit_installed=_labkit_spec(root / ".venv" / "bin" / "python"),
        scaffold_sha=sha,
        scaffold_flags=[*flags, *exp_flags],
        target_minutes=TARGET_MINUTES,
    )
    log = _sidecar(root, "log.md")
    log.write_text("", encoding="utf-8")
    sheet = (Path(__file__).resolve().parent / spec["template"]).read_text(
        encoding="utf-8"
    )
    for key, val in (
        ("<metric_key>", metric_key),
        ("<area>", areas[0]),
        ("<log>", str(log)),
        ("<target>", str(TARGET_MINUTES)),
    ):
        sheet = sheet.replace(key, val)
    (root / "TASK.md").write_text(sheet, encoding="utf-8")
    _sh(["git", "add", "-A"], root)
    _sh(
        [
            "git",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            "Probe: the area, the fixture and TASK.md",
        ],
        root,
    )
    _sidecar(root, "probe.json").write_text(
        json.dumps(asdict(probe), indent=1), encoding="utf-8"
    )
    prompt = _sidecar(root, "prompt.md")
    prompt.write_text(agent_prompt(root), encoding="utf-8")
    print(
        f"staged {root}\n  task:   {root / 'TASK.md'}\n  log:    {log}\n"
        f"  probe:  {_sidecar(root, 'probe.json')}\n  prompt: {prompt}\n"
        f"next: hand the prompt file's text to a cold agent (fresh context, no "
        f"history), then `usability score {root} --transcript <its transcript>`"
    )
    return 0


#: a silence between two stamps this long is not work — an outage, a
#: forgotten agent — and is reported beside the span, not hidden in it
GAP_SECONDS = 600


@dataclass(frozen=True)
class LogTrace:
    """What the agent's log says: stamps and counts per tag."""

    lines: int
    wall_seconds: int | None  # max − min over the stamps; None below two
    gap_seconds: int  # sum of silences ≥ GAP_SECONDS between stamps
    monotonic: bool  # stamps never run backwards
    read: int
    run: int
    edit: int
    unsure: int
    gate: int
    untagged: int  # off-contract lines, counted, never dropped
    source_reads: int  # `read` lines naming labkit's source or docs/arbeitsstandard.md


def parse_log(text: str) -> LogTrace:
    counts = {t: 0 for t in LOG_TAGS}
    untagged = 0
    source_reads = 0
    stamps: list[int] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        m = LOG_LINE.match(line)
        if not m or m.group(4).lower() not in counts:
            untagged += 1
            continue
        counts[m.group(4).lower()] += 1
        if m.group(4).lower() == "read" and SOURCE_READ.search(m.group(5)):
            source_reads += 1
        stamps.append(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)))
    wall = (max(stamps) - min(stamps)) if len(stamps) >= 2 else None
    gaps = sum(b - a for a, b in zip(stamps, stamps[1:]) if b - a >= GAP_SECONDS)
    return LogTrace(
        lines=len(stamps) + untagged,
        wall_seconds=wall,
        gap_seconds=gaps,
        monotonic=all(a <= b for a, b in zip(stamps, stamps[1:])),
        untagged=untagged,
        source_reads=source_reads,
        **counts,
    )


def latest_run(area: Path) -> Path | None:
    """The newest completed run — run_ids start with the timestamp, so
    their sort order is their start order (runlog.Run)."""
    try:
        done = runs.completed_runs(area)
    except runs.RunConfigError as exc:
        raise SystemExit(f"usability: {exc}") from exc
    return done[-1] if done else None


@dataclass(frozen=True)
class Score:
    probe: Probe
    run_id: str | None
    number: float | None  # metrics[metric_key], or None when absent
    expected: float | None  # the recounted truth (count), None for a model's number
    number_ok: bool  # equals the truth, or (judge) present and within [0, 1]
    null_reported: (
        bool | None
    )  # judge: an a<i>_* key (admissibility, the null lane) in metrics.json
    bound_to: str | None  # config["protocol"]["path"]
    frozen: bool | None
    cost_tier: str | None
    log: LogTrace | None
    transcript: agent_transcript.TranscriptTrace | None = (
        None  # measured, not self-reported
    )


def archive(root: Path, transcript: Path, dest: Path) -> list[Path]:
    """Keep a probe for later debugging: the transcript (gzip, mtime 0 so
    the bytes depend on the content only), its timeline and the score, as
    `<dest>/<probe>.jsonl.gz`, `.timeline.txt`, `.score.json`. Claude Code
    deletes transcripts after `cleanupPeriodDays` (30 by default), and a
    transcript is what showed an agent's source reads and detours on
    2026-10-07. A file already there with other bytes is refused, never
    overwritten."""
    import gzip

    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        dest / f"{root.name}.jsonl.gz": gzip.compress(transcript.read_bytes(), mtime=0),
        dest / f"{root.name}.timeline.txt": (
            "\n".join(agent_transcript.timeline(transcript)) + "\n"
        ).encode("utf-8"),
        dest / f"{root.name}.score.json": _sidecar(root, "score.json").read_bytes(),
    }
    clash = [p for p, b in payload.items() if p.exists() and p.read_bytes() != b]
    if clash:
        raise SystemExit(
            f"usability: archive refuses to overwrite {', '.join(map(str, clash))} — "
            f"another probe of the same name? archive into another directory"
        )
    for path, body in payload.items():
        path.write_bytes(body)
    return list(payload)


def score(root: Path, transcript: Path | None = None) -> int:
    probe_file = _sidecar(root, "probe.json")
    if not probe_file.is_file():
        raise SystemExit(f"usability: {probe_file} missing — was {root} staged here?")
    probe = Probe(**json.loads(probe_file.read_text(encoding="utf-8")))
    area = root / "experiments" / probe.area
    expected = recount(root) if probe.task == "count" else None
    run = latest_run(area)
    number = bound_to = frozen = tier = None
    null_reported = None
    if run is not None:
        config_file = run / "config.json"  # a completed run always has one
        metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        config = json.loads(config_file.read_text(encoding="utf-8"))
        value = metrics.get(probe.metric_key)
        number = (
            float(value)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None
        )
        binding = config.get("protocol") or {}
        # bound means the run recorded an id; a path alone is a hint that goes stale
        bound_to = binding.get("path") if binding.get("id") else None
        tier = config.get("cost_tier")
        if probe.task != "count":
            null_reported = any(re.match(r"^a\d+_", k) for k in metrics)
        if bound_to:
            from labkit import protocol_block  # lazy: labkit modules import each other

            p = Path(bound_to)
            p = p if p.is_absolute() else area / p
            try:
                frozen = (
                    protocol_block.head(p.read_text(encoding="utf-8")).frozen
                    if p.is_file()
                    else None
                )
            except protocol_block.BlockError as exc:
                print(f"  protocol head unreadable — {exc}")
                frozen = None
    log = _sidecar(root, "log.md")
    trace = parse_log(log.read_text(encoding="utf-8")) if log.is_file() else None
    try:
        measured = (
            agent_transcript.trace(transcript, root, SOURCE_READ)
            if transcript is not None
            else None
        )
    except (agent_transcript.TranscriptError, OSError) as exc:
        raise SystemExit(f"usability: transcript: {exc}") from exc
    sc = Score(
        probe=probe,
        run_id=run.name if run else None,
        number=number,
        expected=expected,
        number_ok=(number is not None and abs(number - expected) <= TOL)
        if expected is not None
        else (number is not None and 0.0 <= number <= 1.0),
        null_reported=null_reported,
        bound_to=bound_to,
        frozen=frozen,
        cost_tier=tier,
        log=trace,
        transcript=measured,
    )
    _sidecar(root, "score.json").write_text(
        json.dumps(asdict(sc), indent=1), encoding="utf-8"
    )

    rows = [
        ("labkit in probe", probe.labkit_installed),
        ("scaffold sha", probe.scaffold_sha),
        ("run", sc.run_id or "none"),
        (f"number ({probe.metric_key})", "absent" if number is None else str(number)),
        (
            "equals the truth" if expected is not None else "within [0, 1]",
            "yes"
            if sc.number_ok
            else (f"NO (truth {expected})" if expected is not None else "NO"),
        ),
        *(
            [("null condition reported", "yes" if null_reported else "NO")]
            if probe.task != "count"
            else []
        ),
        ("bound to", bound_to or "NOTHING"),
        ("frozen", {True: "yes", False: "no", None: "n/a"}[frozen]),
        ("cost tier", tier or "undeclared"),
    ]
    if trace is None:
        rows.append(("log", "missing — no trace, no measurement"))
    else:
        w = trace.wall_seconds
        rows.append(
            (
                "wall-clock (log span)",
                f"{w // 60}m{w % 60:02d}s" if w is not None else "n/a",
            )
        )
        if trace.gap_seconds:
            g = trace.gap_seconds
            net = (w - g) if w is not None else None
            rows.append(
                (
                    f"silences ≥ {GAP_SECONDS // 60} min",
                    f"{g // 60}m{g % 60:02d}s"
                    + (
                        f" → net {net // 60}m{net % 60:02d}s" if net is not None else ""
                    ),
                )
            )
        if not trace.monotonic:
            rows.append(("log order", "stamps run backwards — span is unreliable"))
        rows += [
            (f"steps · {t}", str(getattr(trace, t))) for t in (*LOG_TAGS, "untagged")
        ]
        rows.append(
            (
                "reads of labkit source / standard",
                str(trace.source_reads)
                + ("" if trace.source_reads == 0 else " — the card did not suffice"),
            )
        )
    if measured is not None:
        w, tool = measured.wall_seconds, measured.tool_seconds
        rows += [
            ("transcript · wall-clock", f"{w // 60}m{w % 60:02d}s"),
            ("transcript · in tools / thinking", f"{tool}s / {w - tool}s"),
            ("transcript · tool calls", str(measured.calls)),
            (
                "transcript · labkit commands",
                ", ".join(f"{k} ×{v}" for k, v in sorted(measured.commands.items()))
                or "none",
            ),
            ("transcript · gate refusals", str(measured.refusals)),
            ("transcript · files opened", str(len(measured.files_read))),
            (
                "transcript · source / standard reads",
                str(len(measured.source_reads))
                + (
                    " — " + "; ".join(measured.source_reads[:3])
                    if measured.source_reads
                    else ""
                ),
            ),
        ]
    width = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"  {k:<{width}}  {v}")
    over = (
        trace is not None
        and trace.wall_seconds is not None
        and trace.wall_seconds - trace.gap_seconds > probe.target_minutes * 60
    )
    print(
        f"  target: one kept number under {probe.target_minutes} min"
        + (" — MISSED" if over else "")
    )
    print(f"→ {_sidecar(root, 'score.json')}")
    return 0 if sc.number_ok and bound_to else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="usability", description=(__doc__ or "").split("\n\n")[0]
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage", help="stamp a probe lab repo with one kept-number task")
    s.add_argument("dir")
    s.add_argument("--venv", help="link this venv instead of creating one")
    s.add_argument(
        "--cost",
        choices=("seconds", "minutes", "hours", "unset"),
        metavar="TIER",
        help="the cost tier stamped into the protocol (default: the task's, "
        "seconds); unset = the agent declares it, the full form is stamped",
    )
    s.add_argument(
        "--model",
        action="store_true",
        help="a model in the loop: the full measure skeleton (prompt, parser, "
        "probe) and, at seconds, the three model fields in the cut "
        "(default for --task judge)",
    )
    s.add_argument(
        "--task",
        choices=sorted(TASKS),
        default="count",
        help="which task sheet and fixture: count (deterministic) or judge (a model)",
    )
    c = sub.add_parser("score", help="number, binding and log of a finished probe")
    c.add_argument("dir")
    c.add_argument(
        "--transcript",
        help="the agent's session transcript (JSONL): wall-clock, tool calls, "
        "files and refusals measured instead of self-reported",
    )
    c.add_argument(
        "--archive",
        metavar="DIR",
        help="with --transcript: keep transcript (gzip), timeline and score in DIR",
    )
    tr = sub.add_parser("trace", help="the timeline of one agent transcript")
    tr.add_argument("transcript")
    args = ap.parse_args(argv)
    if args.cmd == "trace":
        try:
            lines = agent_transcript.timeline(Path(args.transcript))
        except (agent_transcript.TranscriptError, OSError) as exc:
            raise SystemExit(f"usability: transcript: {exc}") from exc
        print("\n".join(lines))
        return 0
    root = Path(args.dir).resolve()
    if args.cmd == "stage":
        return stage(
            root,
            Path(args.venv).resolve() if args.venv else None,
            cost=args.cost,
            task=args.task,
            model=args.model,
        )
    if args.archive and not args.transcript:
        ap.error("--archive needs --transcript")
    transcript = Path(args.transcript).resolve() if args.transcript else None
    rc = score(root, transcript)
    if args.archive and transcript is not None:
        for path in archive(root, transcript, Path(args.archive)):
            print(f"  archived {path}")
    return rc


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
