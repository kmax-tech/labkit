"""usability — stage a probe lab repo for a cold agent, then score the trace.

    usability stage <dir> [--venv PATH]     a fresh lab repo with one kept-number task
    usability stage <dir> --restamp [--keep PATH ...]   the same probe stamped again with this labkit
    usability log TAG TEXT [--log FILE] [-- CMD ...]     one step line with the time, then CMD
    usability score <dir> [--transcript F] [--agent M]  number · binding · log (· transcript) → one table, one JSON
    usability trace <transcript>            the agent's timeline, one line per tool call

Reading a protocol (protocol_reading), each a prompt for a cold reader and
its score against the run:

    usability reader <dir> / read-score <dir>     the whole protocol
    usability glance <dir> / glance-score <dir>   only its first ten lines
    usability terms <dir>                         the reader's unclear terms vs Summary and Terms

Finding one's way in code (code_navigation):

    usability nav <repo> --questions Q --out P / nav-score ...   "where does the code do X?"
    usability human <repo> --questions Q --out P   a person answers the behaviour questions, timed

Why this exists (2026-10-05): the doctrine grew by scars, every scar added
a gate, and nobody measured what the whole chain costs for the simplest
case — one deterministic number, kept. uniagent area 01 needed four days,
three freezes and three agent audits for a seven-second run. A rule that
costs more than the error it prevents is a rule to cut, but only a trace
shows which one; this is the trace.

stage
    Stamps a lab repo with labkit's own scaffold (`labkit-init lab`, then
    `labkit-init exp <area>`), commits it, plants the task's fixture —
    `--task count` (default): twelve cases and their files, a deterministic
    mean; `--task judge`: twelve sentences with a gold label, a model's
    accuracy, no truth, only a range and a null condition to report;
    `--task compute-hrv | fit-assay | apply-screen`: a ScienceAgentBench-shaped
    task with a known trap and a hidden evaluation of `pred_results/`
    (`sab_cases`; the created venv gets the case's packages) — with a
    known answer (twelve cases, their input files; the answer is recounted
    from the files at score time, never written down) and TASK.md — the
    task sheet, from `usability-task-<task>.md.template`, with the log
    contract and the metrics key the number must land under — and
    `<dir>.prompt.md`, the prompt a cold agent gets: the repo's AGENTS.md
    as a session loads it, then the pointer to TASK.md and the probe's own
    `.tmp/` for temporary files. A venv with the staging interpreter's
    labkit and the rest of requirements.txt is created unless `--venv`
    links an existing one; an editable staging labkit is refused there and
    warned with `--venv` (`labkit_spec_problem`) — a probe measures a fixed
    labkit. What was measured is pinned in `<dir>.probe.json`: the labkit
    the probe venv holds, a sha over the scaffolder and the templates it
    stamps, the flags. Side effects: a git repo with three commits by a
    fixed committer (`PROBE_IDENTITY`, given to each of labkit's own
    commits; no git config is written), a venv or a symlink, `.tmp/`
    (git-ignored), three sidecar files next to <dir> (probe.json, log.md,
    prompt.md).

log
    The agent's step log, one call per step: appends `HH:MM:SS · TAG · TEXT`
    to the log (`--log`, default `log.md` in the working directory) and then
    runs CMD, whose exit code is the command's. Without CMD it only logs (a
    read or an edit done with a tool). Why: logging by hand, with `date` and
    `>>`, tempted every cold agent to batch — three draws wrote their first
    lines after the reads they describe (Haiku H5–H7, 2026-10-13), and the
    log is the measurement.

stage --restamp
    The probe stamped again with this labkit, in place: a fresh stamp with
    the task and flags `<dir>.probe.json` records is laid over <dir> file by
    file — a stamped file whose bytes changed is overwritten, a new one
    added, and every path named with `--keep` (the probe's hand edits: the
    task sheet, the ignore list, a hook of the cloud) stays as it is. The
    kept paths are recorded in `<dir>.probe.json` and are the default next
    time. The probe's venv is rebuilt from the stamped pin (or linked with
    `--venv`), so `requirements.lock` and `labkit-check` agree, and the
    change is committed past the hook (the stamped protocol is placeholders
    by design). The push stays with the operator. Why (2026-10-13): eight
    re-stamps were done by hand, each from memory, and two sessions
    reconstructed the recipe differently — one would have copied the task
    sheet and lost the cloud edits. Refuses a dirty tree and a `--keep`
    path the stamp does not produce.

score
    Reads the latest run of the stamped area — the number under the named
    key, the protocol the run is bound to (and whether it is frozen), the
    repeat cost — and the agent's log (`<dir>.log.md`, one line per step:
    `HH:MM:SS · <tag> · text`, tag in read/run/edit/unsure/gate). Prints
    wall-clock (first to last stamp; the agent's time outside the log is
    not seen), counts per tag and whether the kept number equals the truth.
    Writes `<dir>.score.json`. Exit 0 when the number is right and bound.
    `--transcript` adds what the agent's session transcript shows — the
    log is self-report, the transcript a measurement (agent_transcript).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import time
import shutil
import tempfile
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from labkit.tools import scaffold
from labkit.formats import console, jsonl, repo, runs, scope_sha, standard_contract
from labkit.probes import sab_cases

#: What the scaffold stamps into a repo and an area; their sha pins the measured
#: condition. All of it ships with labkit — the probe needs no house machinery.
#: The skeleton templates come from `standard_contract.SKELETONS`, so the pin
#: holds every template an instrument stamps and the table that picks them.
STAMPED = (
    Path(scaffold.__file__).resolve(),
    Path(standard_contract.__file__).resolve(),
    scaffold.PROTOCOL_TEMPLATE,
    scaffold.TEMPLATES / "AGENTS.md.template",
    *(
        scaffold.TEMPLATES / t
        for t in dict.fromkeys(
            name
            for sk in standard_contract.SKELETONS
            for name in (*(tmpl for tmpl, _ in sk.scripts), sk.test)
        )
    ),
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
    # a fit: the DILI molecules of labkit-paper area 09 (ScienceAgentBench
    # task 18), handed in at `stage --data` — the operator's file, not the
    # package's (2026-10-22, the first probe of the fit lane)
    "fit": {
        "area": "dili-forest",
        "metric_key": "c1_score",
        "template": "usability-task-fit.md.template",
    },
    # SAB-like cases, one per kind: a ScienceAgentBench-shaped task with a
    # known trap and a hidden evaluation (`sab_cases`, 2026-10-27)
    **{
        c.task: {
            "area": c.task,
            "metric_key": c.metric_key,
            "template": "usability-task-sab.md.template",
        }
        for c in sab_cases.CASES.values()
    },
}
#: (repeat cost, kind, model in the loop) per task: what the house route
#: stamps for it (`labkit-init exp --repeat-cost low --kind …`, plus `--model`
#: with a model in the loop). Staged without them, the count got the full
#: form and the model skeleton and every agent spent its time deleting it
#: (probe 2026-10-07) — a cost of the staging, not of the route.
TASK_STAMP: dict[str, tuple[str, str, bool]] = {
    "count": ("low", "compute", False),
    "judge": ("low", "apply", True),
    "fit": ("low", "fit", False),
    # the repeat cost is the agent's to declare, as in a ScienceAgentBench round
    **{c.task: ("unset", c.kind, False) for c in sab_cases.CASES.values()},
}
#: where the fit task's data land in the probe, and the columns the sheet names
FIT_DATA = Path("data") / "raw" / "dili" / "train.csv"
FIT_COLUMNS = ("standardised_smiles", "vDILIConcern")
LOG_TAGS = ("read", "run", "edit", "unsure", "gate")
LOG_LINE = re.compile(r"^(\d\d):(\d\d):(\d\d)\s*·\s*(\w+)\s*·\s*(.*)$")
#: a `read` of these is the agent learning the contract from the wrong place
#: — the area's README card should have sufficed (2026-10-05, four of four read on)
SOURCE_READ = re.compile(
    r"labkit/(\w+/)?\w+\.py"
    r"|labkit[ /](\w+/)?(runlog|recheck|protocol_check|llm|batch|finalize|preflight)"
    r"|labkit/docs/standard|labkit\.(\w+\.)?rules",
    re.I,
)
#: The bar: one kept number in this many minutes. Set by hand (2026-10-05),
#: not derived — the first traces decide whether it is the right one.
TARGET_MINUTES = 5
TOL = 1e-9
#: the committer of labkit's own commits in a probe repo, given to each
#: (`git -c`): staging needs no git identity of the operator's, and the
#: operator's later commits there keep theirs — no git config is written
PROBE_IDENTITY = (("user.name", "labkit probe"), ("user.email", "probe@labkit.invalid"))


def _sh(args: list[str], cwd: Path) -> str:
    """Run a command in `cwd`; a non-zero exit is a refusal with its output.
    git goes through `repo.git_run` (the one runner: timeout, GitError)."""
    try:
        r = (
            repo.git_run(args[1:], cwd)
            if args[0] == "git"
            else subprocess.run(args, cwd=cwd, capture_output=True, text=True)
        )
    except repo.GitError as exc:
        raise console.Refused("usability", f"{exc}") from exc
    if r.returncode != 0:
        raise console.Refused(
            "usability", f"`{' '.join(args)}` failed in {cwd}:\n{r.stdout}{r.stderr}"
        )
    return r.stdout


def _commit(root: Path, title: str, body: str | None = None) -> None:
    """The probe's own commit of what is staged, by PROBE_IDENTITY. It skips the pre-commit
    hook: a freshly stamped protocol is all placeholders by design, and the
    hook is the agent's gate, not the stamper's (`labkit-init exp` sets
    core.hooksPath, 2026-10-05)."""
    _sh(
        [
            "git",
            *(arg for key, value in PROBE_IDENTITY for arg in ("-c", f"{key}={value}")),
            "commit",
            "-q",
            "--no-verify",
            "-m",
            title,
            *(["-m", body] if body else []),
        ],
        root,
    )


def read_probe(path: Path) -> Probe:
    """`<dir>.probe.json` as the record `stage` wrote."""
    return Probe(**json.loads(path.read_text(encoding="utf-8")))


def read_answer(path: Path, who: str) -> str:
    """The answer file a scorer holds to the truth; missing means `who` has
    not answered yet — said so, not a traceback."""
    if not path.is_file():
        raise console.Refused("usability", f"{path} missing — has the {who} answered?")
    return path.read_text(encoding="utf-8")


def other_requirements(text: str) -> list[str]:
    """The requirement lines of a stamped `requirements.txt` besides labkit —
    `pytest` since 0.86.0. They go into the probe venv before the lock is
    frozen: the cloud probe's venv came from requirements.txt, the stamped
    lock knew only labkit, and runlog reported a drift on the first run
    (2026-10-12, draws 1 and 2)."""
    return [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip()
        and not ln.lstrip().startswith("#")
        and repo.requirement_name(ln) != "labkit"
    ]


def _labkit_spec(python: Path) -> str:
    """The labkit line of `pip freeze` under `python` — the one this
    interpreter would import, named the way pip names it."""
    out = _sh([str(python), "-m", "pip", "freeze"], python.parent)
    lines = repo.requirement_lines(out, "labkit")
    if len(lines) != 1:
        raise console.Refused(
            "usability",
            f"expected one labkit line in `pip freeze` of {python}, got {lines!r}",
        )
    return lines[0].strip()


def scaffold_sha() -> str:
    """sha256 (12 hex) over the scaffold and the templates it stamps."""
    for p in STAMPED:
        if not p.is_file():
            raise console.Refused("usability", f"stamped master missing: {p}")
    return scope_sha.tree_digest((p.name, p.read_bytes()) for p in STAMPED)


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
    restamped: str | None = None  # the last `stage --restamp`, if any
    kept: list[str] = field(default_factory=list)  # hand edits a restamp leaves alone


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


def plant_dili(root: Path, data: Path | None) -> None:
    """The fit task's molecules: DATA (the operator's `train.csv`) copied to
    FIT_DATA. Refuses a missing file and one without the columns the task
    sheet names — a probe staged on other data measures another task."""
    if data is None:
        raise console.Refused(
            "usability",
            f"--task fit needs --data <train.csv> (the DILI molecules: columns "
            f"{', '.join(FIT_COLUMNS)}); the package ships no benchmark data",
        )
    if not data.is_file():
        raise console.Refused("usability", f"--data {data}: no such file")
    header = data.read_text(encoding="utf-8").splitlines()[:1]
    missing = [c for c in FIT_COLUMNS if not header or c not in header[0].split(",")]
    if missing:
        raise console.Refused(
            "usability",
            f"--data {data}: column(s) {', '.join(missing)} not in the header",
        )
    dest = root / FIT_DATA
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data.read_bytes())


def plant_task(root: Path, task: str, data: Path | None) -> None:
    """The fixture of TASK into the probe: the count's cases, the fit's
    molecules (DATA, the operator's file), the judge's claims."""
    if task == "count":
        plant_fixture(root)
    elif task == "fit":
        plant_dili(root, data)
    elif task in sab_cases.CASES:
        sab_cases.plant(root, task)
    else:
        plant_claims(root)


def recount(root: Path) -> float:
    """The truth, from the planted files — not from a number on disk."""
    cases = root / "data" / "raw" / "cases.jsonl"
    rows = jsonl.data_rows(cases.read_text(encoding="utf-8"), str(cases))
    counts = [
        sum(
            1
            for f in (root / r["inputs"] / r["case_id"]).iterdir()
            if not f.name.startswith(".")
        )
        for r in rows
    ]
    return sum(counts) / len(counts)


def stamp_flags(
    task: str, repeat_cost: str | None, model: bool
) -> tuple[str | None, str, bool]:
    """(repeat cost or None, kind, model) the scaffolder gets: the task's route
    stamp (TASK_STAMP) unless `repeat_cost` names a tier; "unset" stamps no tier.
    A computation asked for with a model stays one: it is stamped with the
    claim keys (`scaffold.COMPUTE_CLAIM`), never rewritten to an apply."""
    default_cost, kind, default_model = TASK_STAMP[task]
    if repeat_cost is None:
        repeat_cost = default_cost
    model = model or default_model
    return (None if repeat_cost == "unset" else repeat_cost), kind, model


def tier_sentence(repeat_cost: str | None) -> str:
    """The task sheet's sentence on the stamped repeat cost. Without it a cold
    Sonnet agent, staged at `high`, read "twelve calls take about a
    minute", set the head to `low` and took the short lane — the probe
    measured a lane it was not staged for (2026-10-14)."""
    if repeat_cost is None:
        return (
            "Its protocol head names no repeat cost: declaring it is part of the task."
        )
    return (
        f'Its protocol head says `repeat_cost = "{repeat_cost}"`: the number is owed at that '
        f"tier — keep it, and follow the lane AGENTS.md gives for it."
    )


def agent_prompt(root: Path) -> str:
    """The prompt a cold agent gets: the repo's AGENTS.md first, the way a
    session started in the repo loads it into context, then the pointer to
    TASK.md. AGENTS.md is the entry file every agent reads; CLAUDE.md is
    only Claude Code's link to it, and naming it made the probe read as
    Claude-only to a Codex agent (2026-10-14). Handed only a pointer, every
    agent fetched the file with `cat` and read all of it before any section
    marker could steer it — a cost of the probe, not of a real session
    (re-measure 2026-10-07, rounds 1 to 4)."""
    entry = root / "AGENTS.md"
    if not entry.is_file():
        raise console.Refused(
            "usability", f"{entry} missing — the scaffolder stamps it"
        )
    return (
        f"Contents of {entry} (project instructions, loaded the way a "
        f"session in this repository loads them):\n\n"
        f"{entry.read_text(encoding='utf-8')}\n"
        f"---\n\n"
        f"Your working directory is {root} — a lab repository. Read TASK.md "
        f"there and do exactly what it says; it names the log file you keep. "
        f"Every shell command must first `cd` into that directory (your shell "
        f"does not start there). Work only inside it; do not touch sibling "
        f"directories. Temporary files go to {root / SCRATCH}/ — never /tmp, a "
        f"scratchpad your harness names, or any other place outside this "
        f"directory. When done, give the report TASK.md asks for.\n"
    )


#: the probe's own place for temporary files, ignored by its git
SCRATCH = ".tmp"


def probe_scratch(root: Path) -> None:
    """Make ROOT/.tmp/ and ignore it in ROOT/.gitignore (once). Probes
    shared `/tmp` and the operator's scratchpad: judge-2 of 2026-10-20 read
    an earlier probe's audit output there first and wrote its own into the
    scratchpad. A subagent inherits the operator's environment, so no
    TMPDIR can be set for it; the prompt names this directory instead, and
    `usability score` lists the paths a probe used outside it."""
    (root / SCRATCH).mkdir(exist_ok=True)
    ignore = root / ".gitignore"
    text = ignore.read_text(encoding="utf-8") if ignore.is_file() else ""
    if f"{SCRATCH}/" not in text.splitlines():
        ignore.write_text(
            text + ("" if text.endswith("\n") or not text else "\n") + f"{SCRATCH}/\n",
            encoding="utf-8",
        )


def labkit_spec_problem(spec: str, *, linked: bool) -> tuple[str, str] | None:
    """("refuse" | "warn", why) when SPEC, a `pip freeze` line of labkit, is
    an editable install, else None. Built into the probe's own venv
    (LINKED false) it installs from GitHub at the checkout's HEAD — not the
    working tree, and nothing before HEAD is pushed: refused. Linked
    (`--venv`) the probe imports the working tree, which moves under it:
    warned. A probe measures a fixed labkit: a non-editable install of a
    `git archive` of the commit (2026-10-20: a probe linked to the
    developer's venv was bound to no commit)."""
    if not spec.startswith("-e "):
        return None
    if linked:
        return (
            "warn",
            f"--venv runs an editable labkit ({spec}) — the probe imports the "
            f"working tree, which moves under it; for a measurement stage from "
            f"a non-editable install of a `git archive` of the commit",
        )
    return (
        "refuse",
        f"the staging labkit is an editable install ({spec}); the probe venv "
        f"would install it from GitHub at that commit, not this working tree. "
        f"Stage with the interpreter of a non-editable install of a `git "
        f"archive` of the commit (`pip install <archive dir>`), or link a venv "
        f"with --venv",
    )


def sidecar(root: Path, suffix: str) -> Path:
    """The file `<root>.<suffix>` beside the probe directory ROOT."""
    return root.parent / f"{root.name}.{suffix}"


def stage(
    root: Path,
    venv: Path | None,
    repeat_cost: str | None = None,
    task: str = "count",
    model: bool = False,
    data: Path | None = None,
) -> int:
    """Side effects: see module docstring. `task` picks the fixture, the task
    sheet and the default stamp (TASKS); `repeat_cost` overrides the stamped tier
    ("unset" leaves it to the agent), `model` adds the model skeleton; the
    fit task plants DATA (`plant_dili`)."""
    spec = TASKS[task]
    repeat_cost, kind, model = stamp_flags(task, repeat_cost, model)
    area_name, metric_key = spec["area"], spec["metric_key"]
    if root.exists() and any(root.iterdir()):
        raise console.Refused(
            "usability",
            f"{root} exists and is not empty — stage into "
            f"a fresh directory, the probe must start cold",
        )
    if venv is not None and not (venv / "bin" / "python").is_file():
        raise console.Refused("usability", f"--venv {venv} has no bin/python")
    staged_labkit = _labkit_spec(
        venv / "bin" / "python" if venv else Path(sys.executable)
    )
    problem = labkit_spec_problem(staged_labkit, linked=venv is not None)
    if problem and problem[0] == "refuse":
        raise console.Refused("usability", problem[1])
    if problem:
        console.progress("usability", f"WARNING: {problem[1]}")
    sha = scaffold_sha()
    root.mkdir(parents=True, exist_ok=True)
    scaffold.stamp_lab(root, root.name)
    probe_scratch(root)
    _sh(["git", "init", "-q", "."], root)
    _sh(["git", "add", "-A"], root)
    _commit(root, "Scaffold: a probe lab repo for the usability trace")
    area, stamp_report = scaffold.stamp_area(
        root,
        area_name,
        repeat_cost=repeat_cost,
        kind=kind,
        model="haiku" if model else False,
    )
    print(
        stamp_report, file=sys.stderr
    )  # the stamp's log is for the operator, not the probe
    plant_task(root, task, data)
    # the labkit of the staging interpreter, so a probe measures this checkout
    _probe_venv(root, venv, _labkit_spec(Path(sys.executable)))
    if venv is None:
        extra = other_requirements(
            (root / "requirements.txt").read_text(encoding="utf-8")
        )
        if extra:
            _sh([str(root / ".venv" / "bin" / "pip"), "install", "-q", *extra], root)
        if task in sab_cases.CASES:
            _sh(
                [
                    str(root / ".venv" / "bin" / "pip"),
                    "install",
                    "-q",
                    *sab_cases.case(task).packages,
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
    _commit(root, "Probe: requirements.lock and the hooks of the probe venv")
    probe = Probe(
        staged=runs.now_stamp(),
        task=task,
        area=area.name,
        metric_key=metric_key,
        labkit_installed=_labkit_spec(root / ".venv" / "bin" / "python"),
        scaffold_sha=sha,
        scaffold_flags=[
            "lab",
            "exp",
            area_name,
            *(["--repeat-cost", repeat_cost] if repeat_cost else []),
            "--kind",
            kind,
            *(["--model", "haiku"] if model else []),
        ],
        target_minutes=TARGET_MINUTES,
    )
    log = sidecar(root, "log.md")
    log.write_text("", encoding="utf-8")
    sheet = (scaffold.TEMPLATES / spec["template"]).read_text(encoding="utf-8")
    for key, val in (
        ("<metric_key>", metric_key),
        ("<area>", area.name),
        ("<log>", str(log)),
        ("<target>", str(TARGET_MINUTES)),
        ("<tier>", tier_sentence(repeat_cost)),
        (
            "<sab_task>",
            sab_cases.task_text(root, task) if task in sab_cases.CASES else "",
        ),
        (
            "<packages>",
            ", ".join(sab_cases.case(task).packages) if task in sab_cases.CASES else "",
        ),
    ):
        sheet = sheet.replace(key, val)
    (root / "TASK.md").write_text(sheet, encoding="utf-8")
    _sh(["git", "add", "-A"], root)
    _commit(root, "Probe: the area, the fixture and TASK.md")
    sidecar(root, "probe.json").write_text(
        json.dumps(asdict(probe), indent=1), encoding="utf-8"
    )
    prompt = sidecar(root, "prompt.md")
    prompt.write_text(agent_prompt(root), encoding="utf-8")
    print(
        f"staged {root}\n  task:   {root / 'TASK.md'}\n  log:    {log}\n"
        f"  probe:  {sidecar(root, 'probe.json')}\n  prompt: {prompt}\n"
        f"next: hand the prompt file's text to a cold agent (fresh context, no "
        f"history), then `usability score {root} --transcript <its transcript>`"
    )
    return 0


def log_step(log: Path, tag: str, text: str, cmd: list[str]) -> int:
    """`usability log`: see the module docstring. Returns CMD's exit code, 0
    without CMD. Refuses a tag outside LOG_TAGS and an empty text."""
    if tag not in LOG_TAGS:
        raise console.Refused(
            "usability log", f"tag must be one of {', '.join(LOG_TAGS)}, got {tag!r}"
        )
    if not text.strip():
        raise console.Refused("usability log", "the step text is empty")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')} · {tag} · {text.strip()}\n")
    if not cmd:
        return 0
    return subprocess.run(cmd).returncode


@dataclass
class Restamp:
    """What `restamp_files` did, path by path (relative to the probe)."""

    overwritten: list[str]
    added: list[str]
    kept: list[str]  # named in keep and differing from the fresh stamp
    unchanged: list[str]


def restamp_files(
    fresh: Path, target: Path, files: list[str], keep: list[str]
) -> Restamp:
    """Lay the fresh stamp over the probe: FILES (relative paths, the fresh
    stamp's tracked files) are copied from FRESH to TARGET, except that a
    path in KEEP whose bytes differ stays as it is. Side effects: writes
    under TARGET. A KEEP path the stamp does not produce is refused — a typo
    would protect nothing and say so never."""
    unknown = sorted(set(keep) - set(files))
    if unknown:
        raise console.Refused(
            "usability",
            f"--keep names paths the stamp does not produce: {', '.join(unknown)}",
        )
    done = Restamp([], [], [], [])
    for rel in sorted(files):
        src, dst = fresh / rel, target / rel
        if src.is_symlink():  # CLAUDE.md -> AGENTS.md: the link, not its text
            if dst.is_symlink() and os.readlink(dst) == os.readlink(src):
                done.unchanged.append(rel)
                continue
            if rel in keep:
                done.kept.append(rel)
                continue
            if dst.exists() or dst.is_symlink():
                dst.unlink()
                done.overwritten.append(rel)
            else:
                done.added.append(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(os.readlink(src), dst)
            continue
        new = src.read_bytes()
        if dst.is_file() and dst.read_bytes() == new:
            done.unchanged.append(rel)
            continue
        if rel in keep:
            done.kept.append(rel)
            continue
        existed = dst.is_file()
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(new)
        (done.overwritten if existed else done.added).append(rel)
    return done


def _probe_venv(root: Path, venv: Path | None, labkit_spec: str) -> None:
    """The probe's `.venv`: a link to VENV, or built with `labkit_spec`
    installed (`stage`: the staging interpreter's labkit; `--restamp`: the
    stamped pin). Side effects: removes the old one, creates the new one —
    after the check, so a bad --venv leaves the old one standing."""
    if venv is not None and not (venv / "bin" / "python").is_file():
        raise console.Refused("usability", f"--venv {venv} has no bin/python")
    old = root / ".venv"
    if old.is_symlink():
        old.unlink()
    elif old.is_dir():
        shutil.rmtree(old)
    if venv is not None:
        os.symlink(venv.resolve(), old)
        return
    _sh([sys.executable, "-m", "venv", ".venv"], root)
    _sh([str(old / "bin" / "pip"), "install", "-q", labkit_spec], root)


def stamped_repeat_cost(flags: list[str]) -> str:
    """The repeat cost a probe's recorded scaffold flags stamped, "unset" when
    none was named. A probe staged before 0.104.0 recorded `--cost <tier>`;
    that is refused with the mapping, never read as unset — the comparison
    would silently lose its lane."""
    if "--cost" in flags:
        old = (
            flags[flags.index("--cost") + 1]
            if flags.index("--cost") + 1 < len(flags)
            else "?"
        )
        raise console.Refused(
            "usability",
            f"the probe was staged with `--cost {old}` (labkit before 0.104.0); "
            "stage it again with --repeat-cost low|high (seconds is low, minutes "
            "and hours are high) — a restamp does not translate the old flag",
        )
    if "--repeat-cost" in flags:
        return flags[flags.index("--repeat-cost") + 1]
    return "unset"


def restamp(root: Path, keep: list[str] | None, venv: Path | None) -> int:
    """`stage --restamp`: see the module docstring. KEEP None means the
    paths `<dir>.probe.json` recorded last time."""
    probe_file = sidecar(root, "probe.json")
    if not probe_file.is_file():
        raise console.Refused(
            "usability",
            f"{probe_file} missing — {root} was not staged by "
            f"`usability stage`, nothing to restamp",
        )
    if not (root / ".git").is_dir():
        raise console.Refused("usability", f"{root} is not a git repo")
    dirty = _sh(["git", "status", "--porcelain", "--untracked-files=no"], root)
    if dirty.strip():
        raise console.Refused(
            "usability",
            f"{root} has uncommitted changes — commit or stash "
            f"first:\n{dirty.rstrip()}",
        )
    probe = read_probe(probe_file)
    kept_paths = probe.kept if keep is None else keep
    flags = probe.scaffold_flags
    repeat_cost = stamped_repeat_cost(flags)
    model = "--model" in flags
    _probe_venv(root, venv, scaffold.labkit_pin())
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / root.name  # the stamp names the repo after its dir
        with contextlib.redirect_stdout(sys.stderr):  # the stamp's log
            stage(
                fresh,
                root / ".venv",
                repeat_cost=repeat_cost,
                task=probe.task,
                model=model,
                data=root / FIT_DATA if probe.task == "fit" else None,
            )
        files = _sh(["git", "ls-files"], fresh).split("\n")
        done = restamp_files(fresh, root, [f for f in files if f], kept_paths)
        fresh_probe = read_probe(sidecar(fresh, "probe.json"))
    changed = done.overwritten + done.added
    extra = other_requirements((root / "requirements.txt").read_text(encoding="utf-8"))
    if extra and venv is None:
        _sh([str(root / ".venv" / "bin" / "pip"), "install", "-q", *extra], root)
        lock = _sh([str(root / ".venv" / "bin" / "pip"), "freeze"], root)
        if (root / "requirements.lock").read_text(encoding="utf-8") != lock:
            (root / "requirements.lock").write_text(lock, encoding="utf-8")
            if "requirements.lock" not in changed:
                changed.append("requirements.lock")
    probe = replace(
        probe,
        labkit_installed=fresh_probe.labkit_installed,
        scaffold_sha=fresh_probe.scaffold_sha,
        scaffold_flags=fresh_probe.scaffold_flags,
        restamped=runs.now_stamp(),
        kept=list(kept_paths),
    )
    probe_file.write_text(json.dumps(asdict(probe), indent=1), encoding="utf-8")
    # pip freeze names the commit the tag resolved to; the stamped pin names the tag
    pin = repo.requirement_lines(
        (root / "requirements.txt").read_text(encoding="utf-8"), "labkit"
    )[0]
    m = repo.VCS_REQUIREMENT.match(pin)
    label = m.group("ref") if m and m.group("ref") else pin
    report = "\n".join(
        f"  {what:12s}{path}"
        for what, paths in (
            ("overwritten", done.overwritten),
            ("added", done.added),
            ("kept", done.kept),
        )
        for path in paths
    )
    if not changed:
        print(
            f"restamp {root}: nothing to change at labkit {label}"
            + (f"\n{report}" if report else "")
        )
        return 0
    _sh(["git", "add", "--", *sorted(changed)], root)
    _commit(
        root,
        f"Probe re-stamped at labkit {label}",
        f"usability stage --restamp; what changed between the stamps is "
        f"labkit's CHANGELOG.md.\n\n{report}",
    )
    print(
        f"restamp {root}: committed at labkit {label}\n{report}\n"
        f"  probe:      {probe_file}\n"
        f"next: amend the why onto the commit if the changelog is not enough, "
        f"then push — the push stays with you"
    )
    return 0
