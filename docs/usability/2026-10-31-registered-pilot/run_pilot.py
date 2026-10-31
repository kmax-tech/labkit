# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# A record of the run, not code of this package: it runs in labkit-paper's .venv
# (agentsandbox, sandboxlab), which this repo does not have.
"""The registered pilot: every attempt gets the analysis plan, the lab arm as its
labkit protocol, the control arm as PLAN.md — can the agent implement a given
plan, with labkit and without? (README.md beside this file, assessment-contract.txt.)

    ~/projects/labkit-paper-main/.venv/bin/python run_pilot.py --show 21 labkit
    ID_PREFIX=rpt ARMS_ONLY=labkit ~/projects/labkit-paper-main/.venv/bin/python run_pilot.py --pilot --only 21 pubmedqa50
    REPS=3 ~/projects/labkit-paper-main/.venv/bin/python run_pilot.py --pilot
    ~/projects/labkit-paper-main/.venv/bin/python run_pilot.py --score

Copy this file, protocols/ and plans/ into a run directory first: the store,
the staged repositories (arms-pilot-<pin>/) and scores.json land beside it.

Held from round 2 (run_round2.py): the task texts (task_texts_v1.jsonl, sha held;
pubmedqa50 the benchmark record's own text and the model route ROUTE, in both
arms), the two arms, the model (the haiku alias), the budgets (2400 s, 500 turns,
20 $), the API key through the proxy, TZ=UTC, the lab arm's PATH and setup
(`arms.LAB_PATH`, `arms.LAB_SETUP`: one labkit, shown in setup.log). No
requirement sentence. What differs: the registration is given — protocols/<task>.md
staged as the lab arm's protocol, stamped for its head (`arms.head_stamp`),
plans/<task>.md as the control arm's PLAN.md — and each arm's sentence says so
(GIVEN). Every protocol's task section must equal the task text of the prompt,
word for word; the runner refuses otherwise.

`--score`: as round 2 (hidden evaluation, REPORT.md, the labkit standard on the
delivered state with the adopted run and the handovers), and per attempt whether
the registration was changed: the control arm's PLAN.md against the staged one,
the lab arm's registered fields and [[promise]] tables against the staged protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

S = Path(__file__).resolve().parent
LAB = Path.home() / "projects" / "labkit-paper-main"
sys.path.insert(0, str(LAB / "lib"))
from agentsandbox import config as sandbox_config  # noqa: E402
from agentsandbox.agents import ClaudeCode, Limits  # noqa: E402
from agentsandbox.attempt import Attempt  # noqa: E402
from labkit import batch, llm  # noqa: E402
from sandboxlab import arms, infra, standard_check  # noqa: E402
from sandboxlab.batch import effort, kept, run_batch, work_dir  # noqa: E402
from sandboxlab.benches import sab  # noqa: E402

TASK_TEXTS = LAB / "experiments" / "14-fewer-silent-deviations-with-labkit" / "data" / "prepared" / "task_texts_v1.jsonl"
TASK_TEXTS_SHA256 = "ed7e50eec4df7bb29f1fba08997b0cfe9dd635cf7f344939e7393f5676b074d8"
TASKS = ("21", "34", "60", "15", "pubmedqa50")
#: pubmedqa50 is the benchmark record's own text with the route to the model, as in round 2
OWN_TEXT = ("pubmedqa50",)
ROUTE = ("In this environment the model is reachable only through the proxy the environment names. In Python: "
         "`anthropic.Anthropic(base_url=os.environ[\"ANTHROPIC_BASE_URL\"], auth_token=os.environ[\"SANDBOX_MODEL_TOKEN\"])` "
         "(the `anthropic` package is installed; the token variable is SANDBOX_MODEL_TOKEN, pass it as `auth_token`, "
         "not `api_key`; one request at a time, never in parallel). Or the installed command-line client "
         "`claude -p --model claude-haiku-4-5-20251001` (slower, about five seconds a call). A direct call to "
         "api.anthropic.com has no network.")
ARMS = ("instructions_only", "labkit")
ARMS_ONLY = tuple(x for x in os.environ.get("ARMS_ONLY", "").split(",") if x)
ALIAS = os.environ.get("PROBE_MODEL", "haiku")
REPS = int(os.environ.get("REPS", "1"))
WORKERS = int(os.environ.get("WORKERS", "8"))
#: rp the pilot, rpt the technical trial run before it
ID_PREFIX = os.environ.get("ID_PREFIX", "rp")
STORE = S / f"store-{ID_PREFIX}"
LIMITS = Limits(timeout_s=int(os.environ.get("PROBE_TIMEOUT", "2400")), max_turns=500, max_budget_usd=20.0)
#: CONTAINER_MEMORY=12g with PROBE_TIMEOUT=3600 for task 15, as round 2 (default 5g)
if os.environ.get("CONTAINER_MEMORY"):
    sandbox_config.CONTAINER_MEMORY = os.environ["CONTAINER_MEMORY"]
API_KEY_ITEM = "labkit-sandbox-api-key"
#: each arm's sentence: the registration is given, implement it, do not change it, say where it fails
GIVEN = {
    "instructions_only": ("PLAN.md in this repository is the plan for this task, written before any work on it: "
                          "implement it, and do not change it. Where it cannot be followed, say so in REPORT.md "
                          "rather than change it. Name next to every number you report the script and command "
                          "that produced it."),
    "labkit": ("This repository uses labkit; AGENTS.md describes how, and `labkit-next` names the next step. "
               "The experiment's protocol is registered in {protocol}, written before any work on this task: "
               "implement it through labkit, and do not change what it registers. Where it cannot be followed, "
               "say so — AGENTS.md describes the handover — rather than change it. Give the labkit run ID next "
               "to every number you report."),
}
#: the protocol fields a registration consists of — the ones protocols/ fill
REGISTERED = ("Terms of this protocol", "Question / hypothesis", "Inference criterion", "Quality check",
              "Data / scope", "Data profile", "Model / tool", "Null condition / anchors (in the same run)",
              "Exclusions / filters", "Unit")
_TASK_BLOCK = re.compile(r"^## Task \(verbatim, as given to the agent\)\n\n.*?\n\n  ```text\n(.*?)\n  ```", re.M | re.S)
_PLAN_TASK_BLOCK = re.compile(r"^## Task \(verbatim\)\n\n  ```text\n(.*?)\n  ```", re.M | re.S)


def area_name(task_id: str) -> str:
    return f"task-{task_id}"


def protocol_path(task_id: str) -> str:
    """Where the stage puts the lab arm's protocol: the first area of a fresh lab."""
    name = area_name(task_id)
    return f"experiments/01-{name}/PROTOCOL-{name}.md"


def registration(task_id: str) -> tuple[str, str]:
    """(protocol, plan) of a task, as staged."""
    return ((S / "protocols" / f"{task_id}.md").read_text(encoding="utf-8"),
            (S / "plans" / f"{task_id}.md").read_text(encoding="utf-8"))


def task_texts() -> dict[str, dict]:
    sha = hashlib.sha256(TASK_TEXTS.read_bytes()).hexdigest()
    if sha != TASK_TEXTS_SHA256:
        raise SystemExit(f"{TASK_TEXTS}: sha256 {sha[:12]}, registered {TASK_TEXTS_SHA256[:12]}")
    return {r["id"]: r for r in batch.Store(TASK_TEXTS).records()}


def task_of(task_id: str, texts: dict[str, dict]) -> dict:
    task = sab.load_task(sab.task_key(task_id))
    return task if task_id in OWN_TEXT else sab.with_text(task, texts[task_id])


def check_task_sections(texts: dict[str, dict]) -> None:
    """Every protocol's and plan's task section is the prompt's task text, word for word."""
    for t in TASKS:
        want = task_of(t, texts)["task_inst"].strip()
        protocol, plan = registration(t)
        for name, text in (("protocols", protocol), ("plans", plan)):
            m = (_PLAN_TASK_BLOCK if name == "plans" else _TASK_BLOCK).search(text)
            have = "\n".join(line[2:] if line.startswith("  ") else line
                             for line in m.group(1).splitlines()) if m else None
            if have != want:
                raise SystemExit(f"{name}/{t}.md: the task section is not the prompt's task text")


def prompt(task_id: str, arm: str, texts: dict[str, dict]) -> str:
    addendum = GIVEN[arm].format(protocol=protocol_path(task_id))
    if task_id in OWN_TEXT:
        addendum = f"{ROUTE}\n\n{addendum}"
    return sab.build_prompt(task_of(task_id, texts), arm, with_knowledge=True, requirements=None, addendum=addendum)


def attempt_id(task_id: str, arm: str, rep: int) -> str:
    return f"{ID_PREFIX}-t{task_id}-{arm}-r{rep}"


def snapshot(task_id: str, arm: str, image: str) -> Path:
    """The staged repository, per labkit pin and per registration text: a changed
    protocol or plan is a new snapshot, never a stale one."""
    protocol, plan = registration(task_id)
    given = protocol if arm == "labkit" else plan
    digest = hashlib.sha256(given.encode("utf-8")).hexdigest()[:10]
    dest = S / f"arms-pilot-{infra.labkit_pin()}" / f"t{task_id}-{arm}-{digest}"
    if not dest.exists():
        arms.stage_arm(arm, dest, image, name=area_name(task_id), exclude=sab.EXCLUDE,
                       protocol=protocol if arm == "labkit" else None, plan=plan if arm != "labkit" else None)
    wrong = arms.pin_findings(dest, infra.labkit_requirement()) if arm == "labkit" else []
    if wrong:
        raise SystemExit(f"{dest}: staged for another labkit than the image's: {wrong}")
    if arm == "labkit" and not (dest / protocol_path(task_id)).is_file():
        raise SystemExit(f"{dest}: no {protocol_path(task_id)}")
    return dest


def pilot(images: dict[str, str], solver: str, only: list[str]) -> None:
    texts = task_texts()
    check_task_sections(texts)
    todo = []
    for arm in ARMS:
        if ARMS_ONLY and arm not in ARMS_ONLY:
            continue
        for t in TASKS:
            if only and t not in only:
                continue
            for rep in range(1, REPS + 1):
                todo.append(Attempt(attempt_id=attempt_id(t, arm, rep),
                                    labels={"task_id": t, "arm": arm, "rep": rep,
                                            "memory": sandbox_config.CONTAINER_MEMORY},
                                    agent=ClaudeCode(model=solver, auth="api_key",
                                                     extra_env=(("SANDBOX_MODEL_TOKEN", sandbox_config.PLACEHOLDER),
                                                                ("TZ", "UTC"))
                                                     + ((("PATH", arms.LAB_PATH),) if arm == "labkit" else ()),
                                                     setup=arms.LAB_SETUP if arm == "labkit" else None),
                                    prompt=prompt(t, arm, texts),
                                    snapshot=snapshot(t, arm, images["agent"]),
                                    inputs=sab.inputs(sab.load_task(sab.task_key(t))), limits=LIMITS))
    given = {t: {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in zip(("protocol", "plan"), registration(t))}
             for t in TASKS}
    run_batch(todo, STORE, prov={"images": images, "solver_model": solver, "limits": vars(LIMITS),
                                 "labkit_under_test": infra.labkit_pin(), "given": GIVEN, "registration_sha256": given,
                                 "auth": "api_key", "tz": "UTC"},
              images=images, token=api_key(), workers=WORKERS)


def api_key() -> str:
    """The API key for the proxy: SANDBOX_UPSTREAM_TOKEN, else the macOS keychain item
    API_KEY_ITEM; never from a file; never the subscription's OAuth token."""
    import subprocess
    key = os.environ.get(sandbox_config.TOKEN_ENV) or subprocess.run(
        ["security", "find-generic-password", "-a", os.environ.get("USER", ""), "-s", API_KEY_ITEM, "-w"],
        capture_output=True, text=True).stdout.strip()
    if not key:
        raise SystemExit(f"no API key — store it once: security add-generic-password -a \"$USER\" -s {API_KEY_ITEM} -w")
    if key.startswith("sk-ant-oat") or not key.startswith("sk-ant-"):
        raise SystemExit(f"the key in {sandbox_config.TOKEN_ENV} or {API_KEY_ITEM} is no API key")
    return key


def registered_part(protocol: str) -> list[str]:
    """The lines a registration consists of: the REGISTERED fields and the [[promise]] tables."""
    lines = [m.group(0) for label in REGISTERED
             for m in re.finditer(rf"^- \*\*{re.escape(label)}:\*\* .*$", protocol, re.M)]
    return lines + re.findall(r"^\[\[promise\]\]\n(?:(?!\[|```).*\n)*", protocol, re.M)


def registration_changed(rec: dict, work: Path) -> bool | None:
    """Whether the delivered state changed the registration it was given; None when
    the registered file is gone (counted apart)."""
    protocol, plan = registration(rec["task_id"])
    if rec["arm"] == "labkit":
        delivered = work / protocol_path(rec["task_id"])
        if not delivered.is_file():
            return None
        return registered_part(delivered.read_text(encoding="utf-8")) != registered_part(protocol)
    delivered = work / "PLAN.md"
    return None if not delivered.is_file() else delivered.read_text(encoding="utf-8") != plan


def score(images: dict[str, str]) -> None:
    rows = []
    for rec in kept(STORE):
        work = work_dir(STORE, rec)
        task = sab.load_task(sab.task_key(rec["task_id"]))
        s = sab.score_attempt(images["agent"], task, work / "pred_results")
        row = {"attempt_id": rec["attempt_id"], "task_id": rec["task_id"], "arm": rec["arm"], "dir": rec["dir"],
               "timed_out": rec["timed_out"], "has_report": (work / "REPORT.md").exists(),
               "valid": s["valid"], "success": s["verdict"], "line": s["line"],
               "registration_changed": registration_changed(rec, work), **effort(rec)}
        if rec["arm"] == "labkit":
            with tempfile.TemporaryDirectory(dir=S) as tmp:
                std = standard_check.check_attempt(rec["images"]["agent"], work, Path(tmp),
                                                   inputs=sab.inputs(task), inputs_sha256=rec["inputs_sha256"])
            row.update(standard_met=std["met"], repeat_cost=std.get("repeat_cost"), gaps=std["gaps"],
                       adopted_run=std.get("adopted_run"), handovers=std.get("handovers", 0))
        rows.append(row)
        print(json.dumps({k: row.get(k) for k in ("attempt_id", "success", "valid", "registration_changed",
                                                   "adopted_run", "handovers", "seconds", "cost_usd") if k in row}),
              flush=True)
    (S / f"scores-{ID_PREFIX}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--show", nargs=2, metavar=("TASK", "ARM"))
    g.add_argument("--pilot", action="store_true")
    g.add_argument("--score", action="store_true")
    ap.add_argument("--only", nargs="*", default=[], help="with --pilot: these tasks only")
    args = ap.parse_args()
    if args.show:
        texts = task_texts()
        check_task_sections(texts)
        print(prompt(args.show[0], args.show[1], texts))
        return
    images = infra.build_images()
    solver = llm.resolve(ALIAS)["model"]
    print(json.dumps({"images": images, "model": solver, "labkit": infra.labkit_pin(), "limits": vars(LIMITS),
                      "workers": WORKERS, "store": STORE.name}), flush=True)
    if args.pilot:
        pilot(images, solver, args.only)
    else:
        score(images)


if __name__ == "__main__":
    main()
