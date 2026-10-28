# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# A record of the run, not code of this package: it ran in labkit-paper's .venv
# (agentsandbox, sandboxlab, labkit 0.85's `labkit.llm`), which this repo does not have.
"""The repair case on apply-screen (2026-10-28): a registered area with a planted fault, measured once in the container before the agent starts.

    ~/projects/labkit-paper/.venv/bin/python run_sab_probes.py           # all three
    ~/projects/labkit-paper/.venv/bin/python run_sab_probes.py fit-assay # one

Per probe (staged on the host by `usability stage --venv`): the host paths in
TASK.md and the prompt become the container's (/work, the log at
/out/probe.log.md), the host venv link goes, the labkit wheel of the branch
goes into .wheels/ (git-excluded); inside, before the agent, a venv with the
image's packages and this labkit, the hooks, requirements.lock, one commit.
Agent: Claude Code, haiku, `--setting-sources project` (the adapter's), 600 s.
The attempt lands in attempts/<task>/; the copied-back tree is scored on the
host by `usability score` next to the probe's sidecars (scored/<task>).
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

TASKS = ("apply-screen",)  # the repair case: registered, the first measurement in the container
TAG = os.environ.get("PROBE_TAG", "")          # a second draw lands in probes<TAG>/, attempts<TAG>/, scored<TAG>/
LIMITS = Limits(timeout_s=int(os.environ.get("PROBE_TIMEOUT", "600")), max_turns=300, max_budget_usd=10.0)
WHEEL = next((S / "wheels").glob("labkit-*.whl"))
GIT_ENV = (("GIT_AUTHOR_NAME", "probe"), ("GIT_AUTHOR_EMAIL", "probe@labkit.invalid"),
           ("GIT_COMMITTER_NAME", "probe"), ("GIT_COMMITTER_EMAIL", "probe@labkit.invalid"))
SETUP = ("python -m venv --system-site-packages --without-pip .venv && "
         "pip --python .venv/bin/python install -q --no-index --no-deps --ignore-installed .wheels/labkit-*.whl && "
         ".venv/bin/labkit-hooks install >/dev/null && "
         "pip --python .venv/bin/python freeze > requirements.lock && "
         "git add -A && git commit -q -m 'Probe: the venv inside the sandbox' && "
         # the first measurement, with the venv the agent uses (repair case)
         ".venv/bin/python experiments/01-apply-screen/scripts/01_measure.py > /tmp/first-run.txt 2>&1 && "
         "git add -A && git commit -q -m 'Run: the first measurement under the registration'")


def to_container(task: str) -> str:
    """Move the staged probe to the container's paths; returns the prompt."""
    root = S / f"probes{TAG}" / task
    host_log = str(S / f"probes{TAG}" / f"{task}.log.md")
    sheet = (root / "TASK.md").read_text(encoding="utf-8").replace(host_log, "/out/probe.log.md")
    (root / "TASK.md").write_text(sheet.replace(str(root), "/work"), encoding="utf-8")
    # committed while the host venv still stands: the probe's own pre-commit runs its gates from it
    env = {"GIT_AUTHOR_NAME": "probe", "GIT_AUTHOR_EMAIL": "probe@labkit.invalid",
           "GIT_COMMITTER_NAME": "probe", "GIT_COMMITTER_EMAIL": "probe@labkit.invalid", "PATH": "/usr/bin:/bin"}
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "Probe: container paths"], cwd=root, check=True, env=env)
    venv = root / ".venv"  # ignored by the lab's .gitignore; the setup line builds the container's
    if venv.is_symlink() or venv.exists():
        venv.unlink() if venv.is_symlink() else shutil.rmtree(venv)
    (root / ".wheels").mkdir(exist_ok=True)
    shutil.copy2(WHEEL, root / ".wheels" / WHEEL.name)
    with (root / ".git" / "info" / "exclude").open("a", encoding="utf-8") as fh:
        fh.write(".wheels/\n")
    prompt = (S / f"probes{TAG}" / f"{task}.prompt.md").read_text(encoding="utf-8")
    return prompt.replace(host_log, "/out/probe.log.md").replace(str(root), "/work")


def score(task: str) -> None:
    """The copied-back tree beside the probe's sidecars, scored by the branch's usability."""
    src = S / f"attempts{TAG}" / task / "work"
    dest = S / f"scored{TAG}" / task
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, symlinks=True)
    for suffix in ("probe.json", "prompt.md"):
        shutil.copy2(S / f"probes{TAG}" / f"{task}.{suffix}", S / f"scored{TAG}" / f"{task}.{suffix}")
    log = S / f"attempts{TAG}" / task / "out" / "probe.log.md"
    (S / f"scored{TAG}" / f"{task}.log.md").write_text(log.read_text(encoding="utf-8") if log.is_file() else "",
                                                 encoding="utf-8")
    subprocess.run([str(S / "stage-venv" / "bin" / "usability"), "score", str(dest), "--agent", "haiku-4.5"],
                   check=False)


def main() -> None:
    tasks = sys.argv[1:] or list(TASKS)
    images = infra.build_images()
    token = infra.subscription_token()
    model = llm.resolve("haiku")["model"]
    print(json.dumps({"images": images, "model": model, "wheel": WHEEL.name, "limits": vars(LIMITS)}), flush=True)
    for task in tasks:
        prompt = to_container(task)
        agent = ClaudeCode(model=model, setup=SETUP, extra_env=(*GIT_ENV, ("TMPDIR", "/work/.tmp")))
        a = Attempt(task, {"probe": task}, agent, prompt, S / f"probes{TAG}" / task, limits=LIMITS)
        m = run_attempt(a, images, S / f"attempts{TAG}", token)
        print(json.dumps({"task": task, "seconds": m["container_seconds"], "timed_out": m["timed_out"],
                          "result": m["result"], "requests": m["usage"]["requests"]}), flush=True)
        score(task)


if __name__ == "__main__":
    main()
