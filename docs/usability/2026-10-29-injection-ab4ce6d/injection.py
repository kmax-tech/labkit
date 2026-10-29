#!/usr/bin/env python3
"""Injection benchmark on seven delivered lab states: replay report-check after one mutation each.

    python3 injection.py --states DIR --out DIR [--evidence DIR] [--only M1,M4] [--jobs 4] [--keep]

Inputs: STATES holds the delivered states of the two-arm draw
(`scored-lab-1/{compute-hrv,fit-assay,apply-screen}`, `scored-lab-2/...`,
`scored-lab-s/apply-screen`), each a git repo with a `.venv` that runs only
inside the image `labkit-sandbox:8ce976250133` mounted at /work. The
originals are never touched: every replay works on a `cp -a` copy under
OUT/work/<state>/<mutation>, deleted after the replay unless --keep.

Per state and mutation (M1 ... M7, defined in MUTATIONS; the contract is
assessment-contract.txt beside this file):
  1. copy the state, apply the mutation on the host (every mutation asserts
     that it changed bytes; a mutation with nothing to change records "n/a"),
  2. inside the image: `git add` the changed paths and commit them as a
     probe user through the stamped pre-commit hook; when the hook refuses,
     record that and commit again with --no-verify,
  3. inside the image: `report-check experiments/<area>` and `report-check
     --if-reported REPORT.md`, each followed by its exit code,
  4. write the whole transcript to OUT/replays/<state>/<mutation>.txt and
     the committed diff to <mutation>.diff.
The unmodified copy is replayed first as `baseline`. The BLOCKER/WARNING
lines of a mutated replay minus the baseline's are the new findings; the
TSV OUT/results.tsv carries, per row: state, mutation, hook outcome, both
exit codes, the counts of new blockers and warnings, a mechanical verdict
(blocker / warning / none / n.a.) and the first new finding line. The
verdict "detected" is a person's reading of the full output, not this
script's. With --evidence the whole OUT tree is copied there at the end.

Side effects: writes under OUT (and EVIDENCE); runs up to --jobs docker
containers at a time, no network. Errors: a missing state, image, docker
failure or a mutation that changed nothing raise; nothing is skipped
silently. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

IMAGE = "labkit-sandbox:8ce976250133"
BLOCK_OPEN = "<!-- labkit result:"
BLOCK_CLOSE = "<!-- /labkit result -->"


@dataclass(frozen=True)
class State:
    """One delivered state: where it lies and what its mutations touch."""

    id: str
    src: str  # relative to --states
    area: str
    protocol: str
    run: str  # the run whose metrics M5 edits (the declared run, else the report's)
    metric_key: str
    metric_delta: float
    report_numbers: tuple[tuple[str, str], ...]  # M2: (from, to) outside the block
    block_number: tuple[str, str] | None  # M2b: inside the block, None = no block
    margin: tuple[str, str] | None  # M3: constants line value (from, to); None = hrv
    unit: tuple[str, str] | None  # M3 for hrv: Unit text (from, to)
    seed: tuple[str, str]  # M1: (from, to) line in 01_measure.py
    csv: str  # M7 target under the state
    swap_from: str  # M7 source state id


STATES = [
    State(
        id="lab1-compute-hrv",
        src="scored-lab-1/compute-hrv",
        area="01-compute-hrv",
        protocol="PROTOCOL-compute-hrv.md",
        run="2026-10-29T08-56-05_c833",
        metric_key="rmssd_ms",
        metric_delta=-2.0,
        report_numbers=(("26.21", "24.21"),),
        block_number=("rmssd_ms = 26.21253086204284", "rmssd_ms = 24.21253086204284"),
        margin=None,
        unit=("RMSSD in milliseconds (ms)", "RMSSD in seconds (s)"),
        seed=("signal.butter(4, 0.5, 'hp'", "signal.butter(4, 0.7, 'hp'"),
        csv="pred_results/hrv.csv",
        swap_from="lab2-compute-hrv",
    ),
    State(
        id="lab1-fit-assay",
        src="scored-lab-1/fit-assay",
        area="01-fit-assay",
        protocol="PROTOCOL-fit-assay.md",
        run="2026-10-29T09-02-14_fc13",
        metric_key="c1_score",
        metric_delta=0.05,
        report_numbers=(("0.8675", "0.9175"),),
        block_number=("c1_score = 0.8675183622441006", "c1_score = 0.9175183622441006"),
        margin=("0.25", "0.05"),
        unit=None,
        seed=("SEED = 0\n", "SEED = 1\n"),
        csv="pred_results/test_pred.csv",
        swap_from="lab2-fit-assay",
    ),
    State(
        id="lab1-apply-screen",
        src="scored-lab-1/apply-screen",
        area="01-apply-screen",
        protocol="PROTOCOL-apply-screen.md",
        run="2026-10-29T09-14-37_a4e2",
        metric_key="c1_score",
        metric_delta=0.05,
        report_numbers=(("0.7609", "0.8109"), ("76.09", "81.09")),
        block_number=("c1_score = 0.7608695652173914", "c1_score = 0.8108695652173914"),
        margin=("0.25", "0.05"),
        unit=None,
        seed=("SEED = 0\n", "SEED = 1\n"),
        csv="pred_results/screen_pred.csv",
        swap_from="labs-apply-screen",
    ),
    State(
        id="lab2-compute-hrv",
        src="scored-lab-2/compute-hrv",
        area="01-compute-hrv",
        protocol="PROTOCOL-compute-hrv.md",
        run="2026-10-29T09-22-19_680b",
        metric_key="rmssd_ms",
        metric_delta=-2.0,
        report_numbers=(("26.20", "24.20"),),
        block_number=("rmssd_ms = 26.1978449065568", "rmssd_ms = 24.1978449065568"),
        margin=None,
        unit=("RMSSD in milliseconds.", "RMSSD in seconds."),
        seed=('signal.butter(4, 0.5, "hp"', 'signal.butter(4, 0.7, "hp"'),
        csv="pred_results/hrv.csv",
        swap_from="lab1-compute-hrv",
    ),
    State(
        id="lab2-fit-assay",
        src="scored-lab-2/fit-assay",
        area="01-fit-assay",
        protocol="PROTOCOL-fit-assay.md",
        run="2026-10-29T09-30-06_ab01",  # no declared run; the report's 0.8238 is this run's
        metric_key="c1_score",
        metric_delta=0.05,
        report_numbers=(("0.8238", "0.8738"),),
        block_number=None,
        margin=("0.1", "0.02"),
        unit=None,
        seed=("SEED = 42\n", "SEED = 43\n"),
        csv="pred_results/test_pred.csv",
        swap_from="lab1-fit-assay",
    ),
    State(
        id="lab2-apply-screen",
        src="scored-lab-2/apply-screen",
        area="01-apply-screen",
        protocol="PROTOCOL-apply-screen.md",
        run="2026-10-29T09-38-22_323a",  # no declared run; the one the report cites
        metric_key="c1_score",
        metric_delta=0.05,
        report_numbers=(("0.7609", "0.8109"),),
        block_number=None,
        margin=("0.25", "0.05"),
        unit=None,
        seed=("SEED = 0\n", "SEED = 1\n"),
        csv="pred_results/screen_pred.csv",
        swap_from="labs-apply-screen",
    ),
    State(
        id="labs-apply-screen",
        src="scored-lab-s/apply-screen",
        area="01-apply-screen",
        protocol="PROTOCOL-apply-screen.md",
        run="2026-10-29T09-47-36_21eb",
        metric_key="c1_score",
        metric_delta=0.05,
        report_numbers=(("0.7609", "0.8109"),),
        block_number=("c1_score = 0.7608695652173914", "c1_score = 0.8108695652173914"),
        margin=("0.15", "0.05"),
        unit=None,
        seed=("SEED = 0\n", "SEED = 1\n"),
        csv="pred_results/screen_pred.csv",
        swap_from="lab1-apply-screen",
    ),
]
BY_ID = {s.id: s for s in STATES}

MUTATIONS = ("M1", "M2", "M2b", "M3", "M4", "M5", "M6", "M6b", "M7")

NOT_APPLICABLE = "n/a"


class NotApplicable(Exception):
    """The state has nothing this mutation changes."""


def replace_once(path: Path, old: str, new: str, *, at_least: int = 1) -> int:
    """Replace OLD by NEW in PATH; return the count, raise when below AT_LEAST."""
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n < at_least:
        raise RuntimeError(
            f"{path}: {old!r} found {n} times, expected at least {at_least}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")
    return n


def split_block(text: str) -> tuple[list[str], list[str]]:
    """The report text as outside and inside segments of its generated blocks.

    Returns (segments, kinds): kinds[i] is 'out' or 'in'; joining segments
    gives the text back. A block without its close marker raises.
    """
    segments: list[str] = []
    kinds: list[str] = []
    pos = 0
    while True:
        start = text.find(BLOCK_OPEN, pos)
        if start < 0:
            segments.append(text[pos:])
            kinds.append("out")
            return segments, kinds
        end = text.find(BLOCK_CLOSE, start)
        if end < 0:
            raise RuntimeError("a generated block opens and never closes")
        end += len(BLOCK_CLOSE)
        segments.append(text[pos:start])
        kinds.append("out")
        segments.append(text[start:end])
        kinds.append("in")
        pos = end


def mutate_M1(s: State, copy: Path) -> tuple[list[str], str]:
    """Code changed after the run: one constant of 01_measure.py."""
    rel = f"experiments/{s.area}/scripts/01_measure.py"
    replace_once(copy / rel, s.seed[0], s.seed[1])
    return [rel], f"{rel}: {s.seed[0].strip()!r} -> {s.seed[1].strip()!r}"


def mutate_M2(s: State, copy: Path) -> tuple[list[str], str]:
    """The kept number retyped in REPORT.md outside every generated block."""
    path = copy / "REPORT.md"
    segments, kinds = split_block(path.read_text(encoding="utf-8"))
    total = 0
    for i, kind in enumerate(kinds):
        if kind != "out":
            continue
        for old, new in s.report_numbers:
            total += segments[i].count(old)
            segments[i] = segments[i].replace(old, new)
    if total == 0:
        raise RuntimeError(f"{path}: none of {s.report_numbers} outside the block")
    path.write_text("".join(segments), encoding="utf-8")
    return [
        "REPORT.md"
    ], f"REPORT.md outside the block: {s.report_numbers} ({total} places)"


def mutate_M2b(s: State, copy: Path) -> tuple[list[str], str]:
    """The kept number changed inside the generated block."""
    if s.block_number is None:
        raise NotApplicable("REPORT.md carries no generated block")
    path = copy / "REPORT.md"
    segments, kinds = split_block(path.read_text(encoding="utf-8"))
    total = 0
    for i, kind in enumerate(kinds):
        if kind == "in":
            total += segments[i].count(s.block_number[0])
            segments[i] = segments[i].replace(*s.block_number)
    if total == 0:
        raise RuntimeError(f"{path}: {s.block_number[0]!r} not inside the block")
    path.write_text("".join(segments), encoding="utf-8")
    return [
        "REPORT.md"
    ], f"REPORT.md inside the block: {s.block_number[0]} -> {s.block_number[1]}"


def mutate_M3(s: State, copy: Path) -> tuple[list[str], str]:
    """A registered constant moved: margin in the C1 table, or the Unit text."""
    rel = f"experiments/{s.area}/{s.protocol}"
    path = copy / rel
    if s.margin is not None:
        old = f"constants = {{ margin = {s.margin[0]} }}"
        new = f"constants = {{ margin = {s.margin[1]} }}"
        replace_once(path, old, new)
        return [rel], f"{rel}: {old} -> {new}"
    assert s.unit is not None
    replace_once(path, s.unit[0], s.unit[1])
    return [rel], f"{rel}: Unit {s.unit[0]!r} -> {s.unit[1]!r}"


def mutate_M4(s: State, copy: Path) -> tuple[list[str], str]:
    """The newest analysis audit record deleted (git rm runs in the image)."""
    audits = sorted((copy / "experiments" / s.area / "audits").glob("*-analysis.toml"))
    if not audits:
        raise NotApplicable("no analysis audit record")
    newest = audits[-1]
    rel = str(newest.relative_to(copy))
    newest.unlink()
    return [rel], f"deleted {rel}"


def mutate_M5(s: State, copy: Path) -> tuple[list[str], str]:
    """metrics.json of the answering run edited."""
    rel = f"experiments/{s.area}/runs/{s.run}/metrics.json"
    path = copy / rel
    metrics = json.loads(path.read_text(encoding="utf-8"))
    if s.metric_key not in metrics:
        raise RuntimeError(f"{rel}: no key {s.metric_key}")
    before = metrics[s.metric_key]
    metrics[s.metric_key] = before + s.metric_delta
    path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return [rel], f"{rel}: {s.metric_key} {before} -> {metrics[s.metric_key]}"


NEW_PROMISE = """
[[promise]]
id = "A9"
key = "a9_pass"
sentence = "every scored item carries a parsed answer (registered after the measurement)"
scope = ["scripts/01_measure.py"]
"""


def mutate_M6(s: State, copy: Path) -> tuple[list[str], str]:
    """A promise table added to the TOML block after the measurement."""
    rel = f"experiments/{s.area}/{s.protocol}"
    path = copy / rel
    text = path.read_text(encoding="utf-8")
    start = text.find("```toml")
    if start < 0:
        raise RuntimeError(f"{rel}: no toml block")
    end = text.find("\n```", start + 7)
    if end < 0:
        raise RuntimeError(f"{rel}: toml block never closes")
    path.write_text(text[:end] + "\n" + NEW_PROMISE + text[end:], encoding="utf-8")
    return [rel], f"{rel}: promise A9 added to the TOML block"


def mutate_M6b(s: State, copy: Path) -> tuple[list[str], str]:
    """The registered question text changed after the measurement."""
    rel = f"experiments/{s.area}/{s.protocol}"
    path = copy / rel
    text = path.read_text(encoding="utf-8")
    label = "- **Question / hypothesis:** "
    m = re.search(re.escape(label) + r"(.+)", text)
    if m is None:
        raise RuntimeError(f"{rel}: no Question / hypothesis line")
    old = m.group(1)
    new = old.rstrip() + " (restricted to the first half of the recording)"
    if "compute-hrv" not in s.area:
        new = old.rstrip() + " (on the labelled items with a complete feature vector)"
    path.write_text(text.replace(label + old, label + new, 1), encoding="utf-8")
    return [rel], f"{rel}: question {old!r} -> {new!r}"


def mutate_M7(s: State, copy: Path, states_dir: Path) -> tuple[list[str], str]:
    """The result file overwritten with another state's file of the same task."""
    source = states_dir / BY_ID[s.swap_from].src / s.csv
    target = copy / s.csv
    if source.read_bytes() == target.read_bytes():
        raise RuntimeError(f"{s.csv}: {s.swap_from} holds the same bytes; no swap")
    shutil.copyfile(source, target)
    return [s.csv], f"{s.csv} <- {s.swap_from}"


def apply_mutation(
    name: str, s: State, copy: Path, states_dir: Path
) -> tuple[list[str], str]:
    """Apply mutation NAME on COPY; return (changed paths, description)."""
    if name == "M7":
        return mutate_M7(s, copy, states_dir)
    fn = globals()[f"mutate_{name}"]
    return fn(s, copy)


def shell_script(s: State, paths: list[str], message: str | None) -> str:
    """The sh script run inside the image: commit the mutation, then replay."""
    lines = ["exec 2>&1", "set +e", "cd /work"]
    if message is not None:
        quoted = " ".join(f"'{p}'" for p in paths)
        commit = (
            "git -c user.name=probe -c user.email=probe@labkit.invalid "
            f"commit -m '{message}'"
        )
        lines += [
            "echo '=== commit'",
            f"git add -A -- {quoted}",
            "git status --short | sed 's/^/  staged: /'",
            f'{commit}; rc=$?; echo "--- hook exit $rc"',
            "if [ $rc -ne 0 ]; then",
            "  echo '=== commit --no-verify'",
            f'  {commit} --no-verify; echo "--- exit $?"',
            "fi",
            "git log -1 --format='  HEAD %h %s'",
        ]
    lines += [
        f"echo '=== report-check experiments/{s.area}'",
        f'.venv/bin/report-check experiments/{s.area}; echo "--- exit $?"',
        "echo '=== report-check --if-reported REPORT.md'",
        '.venv/bin/report-check --if-reported REPORT.md; echo "--- exit $?"',
    ]
    return "\n".join(lines) + "\n"


def run_in_image(copy: Path, script: str) -> str:
    """Run SCRIPT in the image with COPY mounted at /work; return its output."""
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "-e",
        "GIT_CONFIG_COUNT=1",
        "-e",
        "GIT_CONFIG_KEY_0=safe.directory",
        "-e",
        "GIT_CONFIG_VALUE_0=*",
        "-v",
        f"{copy}:/work",
        IMAGE,
        "sh",
        "-c",
        script,
    ]
    r = subprocess.run(
        cmd, capture_output=True, text=True, errors="replace", timeout=600
    )
    out = r.stdout + (("\n[stderr]\n" + r.stderr) if r.stderr.strip() else "")
    if r.returncode != 0:
        raise RuntimeError(f"docker run exited {r.returncode} for {copy}:\n{out}")
    return out


def committed_diff(copy: Path) -> str:
    """The committed mutation (HEAD) as stat plus the first 60 patch lines."""
    r = subprocess.run(
        ["git", "-C", str(copy), "show", "HEAD", "--stat", "--format=%h %s"],
        capture_output=True,
        text=True,
        check=True,
    )
    p = subprocess.run(
        ["git", "-C", str(copy), "show", "HEAD", "--format=", "--no-color"],
        capture_output=True,
        text=True,
        check=True,
    )
    patch = p.stdout.splitlines()
    cut = "\n".join(patch[:60]) + ("\n[... patch cut]" if len(patch) > 60 else "")
    return r.stdout + "\n" + cut + "\n"


def one_replay(
    s: State, mutation: str, states_dir: Path, out: Path, keep: bool
) -> dict[str, str]:
    """Copy, mutate, commit, replay; write the transcript; return the row."""
    work = out / "work" / s.id / mutation
    if work.exists():
        shutil.rmtree(work)
    work.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-a", str(states_dir / s.src), str(work)], check=True)
    replay_dir = out / "replays" / s.id
    replay_dir.mkdir(parents=True, exist_ok=True)
    transcript = replay_dir / f"{mutation}.txt"
    row = {"state": s.id, "mutation": mutation, "hook": "none"}
    if mutation == "baseline":
        header = f"# {s.id} baseline: unmodified copy of {s.src}\n"
        text = header + run_in_image(work, shell_script(s, [], None))
    else:
        try:
            paths, description = apply_mutation(mutation, s, work, states_dir)
        except NotApplicable as exc:
            text = f"# {s.id} {mutation}: not applicable — {exc}\n"
            transcript.write_text(text, encoding="utf-8")
            row.update(hook=NOT_APPLICABLE, area_exit="", report_exit="")
            if not keep:
                shutil.rmtree(work)
            return row
        header = f"# {s.id} {mutation}: {description}\n# committed paths: {paths}\n"
        text = header + run_in_image(
            work, shell_script(s, paths, f"{mutation}: {description.split(':')[0]}")
        )
        (replay_dir / f"{mutation}.diff").write_text(
            committed_diff(work), encoding="utf-8"
        )
        hook = re.search(r"^--- hook exit (\d+)$", text, re.M)
        if hook is None:
            raise RuntimeError(
                f"{s.id} {mutation}: the commit's exit is missing:\n{text}"
            )
        row["hook"] = "refused" if hook.group(1) != "0" else "accepted"
    transcript.write_text(text, encoding="utf-8")
    exits = re.findall(r"^--- exit (\d+)$", text, re.M)
    if len(exits) < 2:
        raise RuntimeError(
            f"{s.id} {mutation}: fewer than two report-check exits:\n{text}"
        )
    row["area_exit"], row["report_exit"] = exits[-2], exits[-1]
    if not keep:
        shutil.rmtree(work)
    return row


FINDING = re.compile(r"^\s*(BLOCKER|WARNING):\s*(.*)$")


REPLAY_MARK = "=== report-check experiments/"


def findings_of(text: str) -> list[tuple[str, str]]:
    """(grade, text) per distinct BLOCKER/WARNING line of a transcript's
    replay sections (after REPLAY_MARK; the hook's output before it is the
    commit's, recorded by the hook column), in order of first appearance."""
    start = text.find(REPLAY_MARK)
    if start < 0:
        raise RuntimeError("transcript without a replay section")
    seen: dict[tuple[str, str], None] = {}
    for m in map(FINDING.match, text[start:].splitlines()):
        if m:
            seen.setdefault((m.group(1), m.group(2).strip()), None)
    return list(seen)


def score(out: Path, rows: list[dict[str, str]]) -> None:
    """Add the new-finding columns to ROWS against each state's baseline."""
    baselines: dict[str, set[tuple[str, str]]] = {}
    for row in rows:
        if row["mutation"] == "baseline":
            text = (out / "replays" / row["state"] / "baseline.txt").read_text(
                encoding="utf-8"
            )
            baselines[row["state"]] = set(findings_of(text))
    for row in rows:
        if row["hook"] == NOT_APPLICABLE:
            row.update(
                new_blockers="", new_warnings="", verdict=NOT_APPLICABLE, first_new=""
            )
            continue
        text = (out / "replays" / row["state"] / f"{row['mutation']}.txt").read_text(
            encoding="utf-8"
        )
        new = [f for f in findings_of(text) if f not in baselines[row["state"]]]
        blockers = [t for g, t in new if g == "BLOCKER"]
        warnings = [t for g, t in new if g == "WARNING"]
        if row["mutation"] == "baseline":
            verdict = "baseline"
        elif blockers:
            verdict = "blocker"
        elif warnings:
            verdict = "warning"
        else:
            verdict = "none"
        row.update(
            new_blockers=str(len(blockers)),
            new_warnings=str(len(warnings)),
            verdict=verdict,
            first_new=(blockers or warnings or [""])[0][:300],
        )


COLUMNS = (
    "state",
    "mutation",
    "hook",
    "area_exit",
    "report_exit",
    "new_blockers",
    "new_warnings",
    "verdict",
    "first_new",
)


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--states", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--evidence", type=Path)
    ap.add_argument("--only", help="comma-separated mutations (baseline always runs)")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--keep", action="store_true", help="keep the mutated copies")
    args = ap.parse_args()
    if args.jobs < 1 or args.jobs > 4:
        raise SystemExit("--jobs must be 1 to 4 (the image's container budget)")
    for s in STATES:
        if not (args.states / s.src / ".venv").is_dir():
            raise SystemExit(f"state {s.id} missing at {args.states / s.src}")
    mutations = ("baseline", *MUTATIONS)
    if args.only:
        chosen = tuple(m.strip() for m in args.only.split(","))
        unknown = set(chosen) - set(MUTATIONS)
        if unknown:
            raise SystemExit(f"unknown mutations {sorted(unknown)}")
        mutations = ("baseline", *chosen)
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = [(s, m) for s in STATES for m in mutations]
    rows: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [
            pool.submit(one_replay, s, m, args.states, args.out, args.keep)
            for s, m in jobs
        ]
        for (s, m), fut in zip(jobs, futures):
            row = fut.result()
            rows.append(row)
            print(
                f"{s.id:18} {m:8} hook={row['hook']:9} exits={row.get('area_exit')}/{row.get('report_exit')}"
            )
    score(args.out, rows)
    tsv = args.out / "results.tsv"
    with tsv.open("w", encoding="utf-8") as f:
        f.write("\t".join(COLUMNS) + "\n")
        for row in rows:
            f.write("\t".join(row.get(c, "") for c in COLUMNS) + "\n")
    print(f"wrote {tsv}")
    if args.evidence:
        if args.evidence.exists():
            shutil.rmtree(args.evidence)
        shutil.copytree(args.out, args.evidence, ignore=shutil.ignore_patterns("work"))
        print(f"copied to {args.evidence}")


if __name__ == "__main__":
    sys.exit(main())
