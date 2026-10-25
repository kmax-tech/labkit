"""run_record_check — what a finished run's record must show before its number counts.

A criterion's denominator against a recorded input count
(`criterion_n_input_mismatches`), the source frozen in the run and
tracked in git (`provenance_findings`), a model that answered named in
the record (`model_provenance_gap`), a single draw where a model was
asked (`single_draw`), every JSONL row held to the runs that wrote it
(`row_provenance_findings`), every arm the protocol names present
(`arm_findings`). Each returns findings; finalize's stations decide
their grade. Read-only.
"""

from __future__ import annotations

import json
from pathlib import Path

from labkit.formats.runs import metrics_path
from labkit.run import batch
from labkit.formats import promises, protocol_block
from labkit.formats.runs import (
    RunConfigError,
    read_metrics,
    read_outputs,
    read_run_config,
    resolve_recorded,
)
from labkit.formats.answering_run import (
    lineage,
    model_provenance_run,
    repeats_of,
)
from labkit.formats.repo import (
    git_root,
    git_run,
)


def _tracked(repo: Path, path: Path) -> bool:
    """Is `path` tracked in `repo`? The exit code is the answer."""
    return git_run(["ls-files", "--error-unmatch", str(path)], repo).returncode == 0


CRITERION_N = promises.CRITERION_N_KEY


def criterion_n_input_mismatches(answering_run: Path) -> list[str]:  # noqa: C901 complexity baseline 2026-10-08
    """Warnings: a criterion's denominator (`c<i>_n` in metrics.json) that
    matches no input count the run recorded — the size of what was counted,
    not a promised constant (that is `intent_check.promised_constant_mismatches`)."""
    metrics_file = metrics_path(answering_run)
    if not metrics_file.is_file():
        return []
    metrics = read_metrics(metrics_file)
    ns = {
        k: v
        for k, v in metrics.items()
        if CRITERION_N.match(k) and isinstance(v, int) and not isinstance(v, bool)
    }
    if not ns:
        return []
    cfg = read_run_config(answering_run)
    counts: dict[str, int] = {}
    for key, d in (cfg.data if cfg else {}).items():
        if isinstance(d, dict) and isinstance(d.get("rows"), int):
            counts[f"data[{key}].rows"] = d["rows"]
    for o in read_outputs(answering_run) or []:
        if o.lines is not None:
            counts[f"{o.path.name} lines"] = o.lines
    if not counts:
        return [
            f"{', '.join(sorted(ns))} present, but the run recorded no input count "
            f"(no data= rows, no output lines) to hold them to"
        ]
    out = []
    for k, n in sorted(ns.items()):
        if n not in counts.values():
            out.append(
                f"{k} = {n} matches no recorded count "
                f"({', '.join(f'{a} = {b}' for a, b in sorted(counts.items()))}) — "
                f"a denominator that is not the input is the audits' most "
                f"frequent real finding"
            )
    return out


def provenance_findings(area: Path, answering_run: Path) -> tuple[list[str], list[str]]:
    """(blockers, warnings) for a run at low repeat cost: source frozen, files tracked."""
    blockers: list[str] = []
    warnings: list[str] = []
    cfg = read_run_config(answering_run)
    data = cfg.data if cfg else {}
    if not data:
        blockers.append(
            "source not frozen — the run carries no `data=`; pass "
            "data={name: path} to runlog.run so sha and rows are recorded"
        )
    sources = [
        resolve_recorded(v["path"], answering_run)
        for v in data.values()
        if isinstance(v, dict) and v.get("path")
    ]
    registered = read_outputs(answering_run)
    outputs: list[Path] = [o.path for o in registered or []]
    if registered is None:
        warnings.append(
            "no outputs.json — the run registered no output file (run.output)"
        )
    repo = git_root(area)
    if repo is None:
        warnings.append(
            "not a git repository — cannot tell whether source and output are committed"
        )
        return blockers, warnings
    for f in sources:
        if not f.exists():
            blockers.append(f"{f} is gone — the run's rows cannot be re-derived")
        elif not _tracked(repo, f):
            blockers.append(
                f"source {f} is not tracked in git — commit it, or the number "
                f"cannot be re-derived"
            )
    # The output rows are born after the run, so on every first pass they are
    # untracked by construction: a warning that names the command, not a
    # blocker that sends the agent round the loop (2026-10-05, five probes).
    for f in outputs:
        if not f.exists():
            blockers.append(f"{f} is gone — the run's rows cannot be re-derived")
        elif not _tracked(repo, f):
            warnings.append(
                f"output {f.name} is not yet tracked — `git add {f}` before "
                f"the commit that cites the number"
            )
    return blockers, warnings


def called_a_model(answering_run: Path) -> bool:
    """Do the run's metrics show model calls (`llm_retries` recorded, or
    `model_calls` > 0)? Static evidence: a run without those keys may still
    have called a model. False when metrics.json cannot be read."""
    try:
        metrics = read_metrics(metrics_path(answering_run))
    except (OSError, ValueError):
        return False
    calls = metrics.get("model_calls")
    return "llm_retries" in metrics or (isinstance(calls, int) and calls > 0)


def single_draw(area: Path, answering_run: Path) -> str | None:
    """Why the number shows no spread, or None: the run asked a model and
    has no repeat (`runlog` repeat_of). One draw per item cannot show how
    far the number moves — in the cloud judge probe it moved 10/12 ↔ 11/12
    between runs, and every audit named it (TODO item 4, 2026-10-14). A
    warning, never a blocker: whether a spread is owed is the protocol's.
    A run in the area that cannot say whether it is a draw (unreadable, a
    broken or doubled draw number) is said here, not raised past."""
    if not called_a_model(answering_run):
        return None
    try:
        if repeats_of(area, answering_run.name):
            return None
    except RunConfigError as exc:
        return f"the draws of {answering_run.name} cannot be counted: {exc}"
    return (
        f"{answering_run.name} is one draw — no spread: `scripts/01_measure.py "
        f"--repeat-of {answering_run.name}` draws it again, `02_analyze.py "
        f"--draws` shows how far the number moves"
    )


def model_provenance_gap(answering_run: Path) -> str | None:
    """Why the run's model cannot be named from its record, or None: its
    metrics show model calls (`llm_retries` recorded, or `model_calls` > 0)
    while no run in its lineage recorded `models_resolved` — the alias was
    not under `model`/`*_model`, the keys runlog resolves (uniagent areas
    14–17 recorded it as `judge`; round 15, 2026-10-08). Static evidence:
    a run without those keys may still have called a model."""
    if not called_a_model(answering_run):
        return None
    try:
        if model_provenance_run(answering_run) is not None:
            return None
    except ValueError as exc:
        return (
            f"model provenance: the lineage of {answering_run.name} is broken — {exc}"
        )
    return (
        f"{answering_run.name} called a model, but no run in its lineage recorded "
        f"models_resolved — record the alias under `model` (runlog resolves it); "
        f"a spec under another key is not provenance labkit can hold"
    )


def row_provenance_findings(answering_run: Path) -> tuple[list[str], list[str]]:
    """(blockers, notes): every JSONL output of the run is held to the runs
    its rows name (`_prov.run`): rows may come from this run, from the runs
    it continues (a resumed file, named in outputs.json), or — for a
    derived run — from its derived_from lineage. Rows from any other run
    are a blocker: a file of two measurements. Rows without `_prov` are a
    note (a Store without `prov`), not proof of anything (2026-10-09). A
    broken lineage (`answering_run.lineage`) is the one blocker: without
    it no row can be held to a run."""
    blockers, notes = [], []
    try:
        allowed = {run.name for run in lineage(answering_run)}
    except ValueError as exc:
        return [
            f"row provenance: the lineage of {answering_run.name} is broken — {exc}"
        ], []
    for entry in read_outputs(answering_run) or []:
        if entry.path.suffix != ".jsonl" or not entry.path.is_file():
            continue
        try:
            rr = batch.row_runs(entry.path)
        except ValueError as exc:
            blockers.append(f"{entry.path.name}: {exc}")
            continue
        ok = allowed | set(entry.continues)
        foreign = sorted(r for r in rr.runs if r not in ok)
        if foreign:
            blockers.append(
                f"{entry.path.name}: {sum(rr.runs[r] for r in foreign)} row(s) from "
                f"{', '.join(foreign)} — a run this run neither is, continues nor "
                f"derives from; a file of two measurements"
            )
        if entry.continues:
            notes.append(
                f"{entry.path.name}: continues {', '.join(entry.continues)} "
                f"({', '.join(f'{r}: {n}' for r, n in sorted(rr.runs.items()))} rows)"
            )
        if rr.unstamped:
            notes.append(
                f"{entry.path.name}: {rr.unstamped} row(s) without _prov — written "
                f"outside a run or by a Store without prov; their run is unknown"
            )
    return blockers, notes


def arm_findings(text: str, area: Path, answering_run: Path) -> list[str]:
    """Warnings: every arm the head declares (`[model.arms.<arm>]`: profile,
    fingerprint, alias — `protocol_block.model`) is held to the answering
    run — the profile file exists in the repo, and fingerprint and alias
    stand somewhere in the run's config.json. The table is what a reader of
    the protocol gets instead of opening the register (2026-10-09: "what
    are before and after?" was answered 60 lines below the criterion, and
    the fingerprint nowhere but in the run). No arms, no `[model]`, or a
    head that does not read (the head check names that): nothing claimed,
    nothing checked."""
    out: list[str] = []
    try:
        declared = protocol_block.model(text)
    except protocol_block.BlockError:
        return out
    if declared is None or not declared.arms:
        return out
    cfg = read_run_config(answering_run)
    if cfg is None:
        return out
    recorded = json.dumps(cfg.as_record(), ensure_ascii=False)
    root = git_root(area) or area
    for arm, a in declared.arms.items():
        if not (root / a.profile).is_file():
            out.append(
                f"arm `{arm}`: the protocol names {a.profile}, no such file under {root}"
            )
        if a.fingerprint not in recorded:
            out.append(
                f"arm `{arm}`: the protocol names fingerprint {a.fingerprint}, the "
                f"answering run recorded no such value — the profile changed after the "
                f"stamp, or the run did not record its fingerprints"
            )
        if a.alias and a.alias not in recorded:
            out.append(
                f"arm `{arm}`: the protocol names alias {a.alias}, the answering run "
                f"recorded no such alias"
            )
    return out
