# A record of the staging, not code of this package: run with the staging
# venv's python (`stage-venv/bin/python stage_control.py <dir> <task>`).
"""Stage the control arm of a SAB-like case: the same task, data, log and
report as `usability stage --task <task>` hands the lab arm, in a plain
repository without labkit — no protocol, no gates, no hooks, no skeleton.

    stage-venv/bin/python stage_control.py probes-control-1/apply-screen apply-screen

The agent is still asked to write its intent down before the first
measurement (PLAN.md: question, data, exclusions, criterion and
admissibility condition, marking the task's and its own choices), so the
two arms differ in the enforcement, not in the request. Sidecars beside the
directory as the lab arm's: <dir>.log.md, <dir>.probe.json, <dir>.prompt.md.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from labkit.probes import sab_cases, usability

AGENTS = """# AGENTS.md — {name}

A plain research repository. Python is `.venv/bin/python` (it has {packages});
run commands from the repository root. Scripts go under `scripts/`, outputs
under `output/`, the data stays under `data/raw/`. Commit your work (never
push). `TASK.md` names the task, the log and the deliverables.
"""

SHEET = """# TASK — a data-driven scientific task, its number kept

You are a researcher new to this repository. Work only inside this
directory; use `.venv/bin/python` (it has {packages}). Every `.venv/bin/…`
path is relative to the repo root: run commands from there. You may commit
(never push). There is no network. Do not ask questions; make reasonable
choices and note them in your report.

Solve the following task by writing and running Python code in this
repository.

{sab_task}

Before the first measurement, write `PLAN.md` in the repository root: the
question, the data you use and what you exclude, the unit of the number
you keep, and — for a model fitted or applied — the success criterion and
the admissibility condition you will hold your result to; mark what the
task states and what you set yourself. Keep scripts under `scripts/` and
the outputs they write under `output/`. When you are done, write REPORT.md
in the repository root: the numbers you obtained, how you obtained them,
whether they meet the criterion of PLAN.md, and every deviation from the
task.

**The log** matters as much as the number. ONE line per step, BEFORE the
step, in `{log}`:

    HH:MM:SS · <tag> · <the step, in a few words>

Write it with the shell, then do the step:

    printf '%s · %s · %s\\n' "$(date +%H:%M:%S)" <tag> "<the step>" >> {log}

tags: `read` (a file you open) · `run` (a command) · `edit` (a file you
write) · `unsure` (the task leaves you guessing) · `gate` (a check or
error makes you change course). Every step gets a line, written before
the step, never batched afterwards; the log is the measurement.

**Report** when done, in your final answer (REPORT.md is the task's), with
these headings: (1) the number and where it lives · (2) files read with
line counts, commands run, edits made, wall-clock · (3) the three biggest
time sinks, each with the concrete cause · (4) what you had to guess · (5)
what you would cut so that the task takes under {target} minutes. Honest,
not a success story.
"""

GITIGNORE = ".venv/\n.tmp/\n__pycache__/\n"


def sh(args: list[str], cwd: Path) -> None:
    env = {"PATH": "/usr/bin:/bin", "GIT_AUTHOR_NAME": "labkit probe",
           "GIT_AUTHOR_EMAIL": "probe@labkit.invalid", "GIT_COMMITTER_NAME": "labkit probe",
           "GIT_COMMITTER_EMAIL": "probe@labkit.invalid"}
    subprocess.run(args, cwd=cwd, check=True, env=env)


def main(root: Path, task: str) -> None:
    c = sab_cases.case(task)
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"{root} exists and is not empty — the probe must start cold")
    root.mkdir(parents=True, exist_ok=True)
    for d in ("scripts", "output", "notes"):
        (root / d).mkdir()
        (root / d / ".gitkeep").write_text("", encoding="utf-8")
    (root / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (root / ".tmp").mkdir()
    packages = ", ".join(c.packages)
    (root / "AGENTS.md").write_text(AGENTS.format(name=root.name, packages=packages), encoding="utf-8")
    (root / "CLAUDE.md").write_text("AGENTS.md\n", encoding="utf-8")  # the lab arm's stamp links it the same way
    sh(["git", "init", "-q", "."], root)
    sab_cases.plant(root, task)
    log = usability.sidecar(root, "log.md")
    log.write_text("", encoding="utf-8")
    sheet = SHEET.format(
        packages=packages,
        sab_task=sab_cases.task_text(root, task),
        log=str(log),
        target=usability.TARGET_MINUTES,
    )
    (root / "TASK.md").write_text(sheet, encoding="utf-8")
    sh(["git", "add", "-A"], root)
    sh(["git", "commit", "-q", "-m", "Probe: the fixture and TASK.md (control arm, no labkit)"], root)
    usability.sidecar(root, "probe.json").write_text(json.dumps({
        "staged": usability.runs.now_stamp(),
        "task": task,
        "arm": "control",
        "metric_key": c.metric_key,
        "labkit_installed": None,
        "target_minutes": usability.TARGET_MINUTES,
    }, indent=1), encoding="utf-8")
    usability.sidecar(root, "prompt.md").write_text(usability.agent_prompt(root), encoding="utf-8")
    print(f"staged control arm {root}")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), sys.argv[2])
