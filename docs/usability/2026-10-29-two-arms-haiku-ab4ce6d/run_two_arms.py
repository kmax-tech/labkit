# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# A record of the run, not code of this package: it ran in labkit-paper's .venv
# (agentsandbox, sandboxlab, labkit 0.85's `labkit.llm`), which this repo does not have.
"""Run one arm of the two-arm experiment (lab: labkit-stamped probe; control:
the same task in a plain repository) over the SAB-like cases, one after
another, in the agentsandbox.

    ARM=lab     DRAW=1 ~/projects/labkit-paper-main/.venv/bin/python run_two_arms.py [task ...]
    ARM=control DRAW=1 ~/projects/labkit-paper-main/.venv/bin/python run_two_arms.py [task ...]

Env: ARM (lab | control), DRAW (1, 2, …), PROBE_MODEL (alias in models.toml,
default haiku), PROBE_TIMEOUT (seconds, default 1800). Probes staged on the
host under probes-<arm>-<draw>/<task> (lab: `usability stage --venv
stage-venv --task <task>`; control: stage_control.py); attempts land in
attempts-<arm>-<draw>/<task>/, the copied-back tree in scored-<arm>-<draw>/
<task> beside the probe's sidecars.

Per probe, as the fifth draw's runner: the host paths in TASK.md and the
prompt become the container's (/work, the log at /out/probe.log.md), the host
venv link goes; the lab arm gets the labkit wheel into .wheels/ (git-excluded)
and, inside before the agent, a venv with the image's packages and this
labkit, the hooks, requirements.lock, one commit; the control arm the same
venv without labkit and without hooks. Agent: Claude Code with the model
alias, `--setting-sources project` (the adapter's), the time limit.

After each attempt: the hidden evaluation of pred_results/ (`sab_cases.
evaluate`, through the stage venv's labkit) into <task>.evaluation.json;
for the lab arm `usability score` and report-check replayed inside the
agent image on the copied-back tree without network, into
<task>.report-check.txt.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
LAB = Path.home() / "projects" / "labkit-paper-main"
sys.path.insert(0, str(LAB / "lib"))
from agentsandbox.agents import ClaudeCode, Limits  # noqa: E402
from agentsandbox.attempt import Attempt, run_attempt  # noqa: E402
from labkit import llm  # noqa: E402
from sandboxlab import infra  # noqa: E402

TASKS = ("compute-hrv", "fit-assay", "apply-screen")
ARM = os.environ["ARM"]
if ARM not in ("lab", "control"):
    raise SystemExit(f"ARM={ARM!r}: lab or control")
DRAW = os.environ["DRAW"]
ALIAS = os.environ.get("PROBE_MODEL", "haiku")
TAG = f"-{ARM}-{DRAW}"
LIMITS = Limits(timeout_s=int(os.environ.get("PROBE_TIMEOUT", "1800")), max_turns=300, max_budget_usd=10.0)
WHEEL = next((S / "wheels").glob("labkit-*.whl"))
STAGE_PY = S / "stage-venv" / "bin" / "python"
GIT_ENV = (("GIT_AUTHOR_NAME", "probe"), ("GIT_AUTHOR_EMAIL", "probe@labkit.invalid"),
           ("GIT_COMMITTER_NAME", "probe"), ("GIT_COMMITTER_EMAIL", "probe@labkit.invalid"))
VENV = "python -m venv --system-site-packages --without-pip .venv && "
SETUP = {
    "lab": VENV
    + "pip --python .venv/bin/python install -q --no-index --no-deps --ignore-installed .wheels/labkit-*.whl && "
    ".venv/bin/labkit-hooks install >/dev/null && "
    "pip --python .venv/bin/python freeze > requirements.lock && "
    "git add -A && git commit -q -m 'Probe: the venv inside the sandbox'",
    "control": VENV
    + "pip --python .venv/bin/python freeze > requirements.lock && "
    "git add -A && git commit -q -m 'Probe: the venv inside the sandbox'",
}


def to_container(task: str) -> str:
    """Move the staged probe to the container's paths; returns the prompt."""
    root = S / f"probes{TAG}" / task
    host_log = str(S / f"probes{TAG}" / f"{task}.log.md")
    sheet = (root / "TASK.md").read_text(encoding="utf-8").replace(host_log, "/out/probe.log.md")
    (root / "TASK.md").write_text(sheet.replace(str(root), "/work"), encoding="utf-8")
    # committed while the host venv still stands: the lab probe's own pre-commit runs its gates from it
    env = {**dict(GIT_ENV), "PATH": "/usr/bin:/bin"}
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root, env=env).returncode:
        subprocess.run(["git", "commit", "-q", "-m", "Probe: container paths"], cwd=root, check=True, env=env)
    venv = root / ".venv"  # ignored by the repo's .gitignore; the setup line builds the container's
    if venv.is_symlink() or venv.exists():
        venv.unlink() if venv.is_symlink() else shutil.rmtree(venv)
    if ARM == "lab":
        (root / ".wheels").mkdir(exist_ok=True)
        shutil.copy2(WHEEL, root / ".wheels" / WHEEL.name)
        with (root / ".git" / "info" / "exclude").open("a", encoding="utf-8") as fh:
            fh.write(".wheels/\n")
    prompt = (S / f"probes{TAG}" / f"{task}.prompt.md").read_text(encoding="utf-8")
    return prompt.replace(host_log, "/out/probe.log.md").replace(str(root), "/work")


def evaluate(task: str, dest: Path) -> None:
    """The hidden evaluation of the delivered pred_results/, by the stage venv's labkit."""
    code = (
        "import json, sys; from pathlib import Path; from labkit.probes import sab_cases; "
        "v, d = sab_cases.evaluate(Path(sys.argv[1]), sys.argv[2]); "
        "print(json.dumps({'verdict': v, 'detail': d}))"
    )
    out = subprocess.run([str(STAGE_PY), "-c", code, str(dest), task], check=True,
                         capture_output=True, text=True).stdout
    (S / f"scored{TAG}" / f"{task}.evaluation.json").write_text(out, encoding="utf-8")
    print(f"hidden evaluation {task}: {out.strip()}", flush=True)


def replay_report_check(task: str, dest: Path, images: dict[str, str]) -> None:
    """report-check inside the agent image on the copied-back tree, no network."""
    area = next((p for p in sorted((dest / "experiments").iterdir()) if p.is_dir()), None)
    cmd = (f"cd /work && .venv/bin/report-check experiments/{area.name if area else '?'}; "
           f"echo '--- exit' $?; .venv/bin/report-check --if-reported REPORT.md; echo '--- exit' $?")
    r = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{dest}:/work",
                        images["agent"], "sh", "-c", cmd], capture_output=True, text=True)
    (S / f"scored{TAG}" / f"{task}.report-check.txt").write_text(r.stdout + r.stderr, encoding="utf-8")


def score(task: str, images: dict[str, str]) -> None:
    src = S / f"attempts{TAG}" / f"{task}{TAG}" / "work"
    dest = S / f"scored{TAG}" / task
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, symlinks=True)
    for suffix in ("probe.json", "prompt.md"):
        shutil.copy2(S / f"probes{TAG}" / f"{task}.{suffix}", S / f"scored{TAG}" / f"{task}.{suffix}")
    log = S / f"attempts{TAG}" / f"{task}{TAG}" / "out" / "probe.log.md"
    (S / f"scored{TAG}" / f"{task}.log.md").write_text(log.read_text(encoding="utf-8") if log.is_file() else "",
                                                       encoding="utf-8")
    evaluate(task, dest)
    if ARM == "lab":
        subprocess.run([str(S / "stage-venv" / "bin" / "usability"), "score", str(dest), "--agent", ALIAS],
                       check=False)
        replay_report_check(task, dest, images)


def main() -> None:
    tasks = sys.argv[1:] or list(TASKS)
    images = infra.build_images()
    token = infra.subscription_token()
    model = llm.resolve(ALIAS)["model"]
    print(json.dumps({"arm": ARM, "draw": DRAW, "images": images, "model": model,
                      "wheel": WHEEL.name if ARM == "lab" else None, "limits": vars(LIMITS)}), flush=True)
    for task in tasks:
        prompt = to_container(task)
        agent = ClaudeCode(model=model, setup=SETUP[ARM], extra_env=(*GIT_ENV, ("TMPDIR", "/work/.tmp")))
        # the attempt id names the Docker containers and networks: unique per arm
        # and draw, so two lanes can run side by side (the first launch of
        # 2026-10-29 shared `sb-agent-<task>` and each lane removed the other's)
        a = Attempt(f"{task}{TAG}", {"probe": task, "arm": ARM, "draw": DRAW}, agent, prompt,
                    S / f"probes{TAG}" / task, limits=LIMITS)
        m = run_attempt(a, images, S / f"attempts{TAG}", token)
        print(json.dumps({"task": task, "arm": ARM, "draw": DRAW, "seconds": m["container_seconds"],
                          "timed_out": m["timed_out"], "result": m["result"],
                          "requests": m["usage"]["requests"]}), flush=True)
        score(task, images)


if __name__ == "__main__":
    main()
