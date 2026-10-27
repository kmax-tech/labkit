"""run_record_check — what a finished run's record must show before its number counts.

The code that produced the number unchanged since the run
(`code_since_run`), a criterion's denominator against a recorded input
count (`criterion_n_input_mismatches`), the source frozen in the run and
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

from labkit.formats.runs import (
    NO_GIT,
    metrics_path,
    patch_path,
    script_copy_path,
    untracked_copy_path,
)
from labkit.formats.scope_sha import (
    DIGEST_CHARS,
    SourceError,
    file_digest,
    measured_code,
)
from labkit.run import batch
from labkit.formats import promises, protocol_block
from labkit.formats.runs import (
    RunConfig,
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
    GitError,
    blobs_now,
    blobs_then,
    git_root,
    git_run,
    shown,
)


def _tracked(repo: Path, path: Path) -> bool:
    """Is `path` tracked in `repo`? The exit code is the answer."""
    return git_run(["ls-files", "--error-unmatch", str(path)], repo).returncode == 0


CRITERION_N = promises.CRITERION_N_KEY

#: where a run's script lives in its area, in the order looked for
SCRIPT_HOMES = ("scripts", ".", "analysis")


def code_since_run(area: Path, answering_run: Path) -> list[str]:
    """Blockers: the code that produced ANSWERING_RUN's number is not the
    code here now (audit 2026-10-27, A1) — its script against the hash the
    run recorded (`script_sha`), each module the script imports
    (`scope_sha.measured_code`: beside it, under `lib/` or `src/`) against
    the tree the run started from (its commit with its `uncommitted.patch`,
    `repo.blobs_then`; an untracked sibling against its copy in the run).
    Exact over what that scope holds; a change made and undone between run
    and now, and code loaded another way, are not seen. Analysis code and
    the pin are not compared: a fix there needs no new measurement. Each
    blocker names its way out — restore the code as it ran, or measure
    anew and audit that run. Read-only."""
    cfg = read_run_config(answering_run)
    if cfg is None:
        return []  # the answering-run station names an unreadable record
    rid = answering_run.name
    anew = "or measure anew and audit that run"
    if cfg.script_sha == "no-script":
        return [
            f"{rid} recorded no script — the code behind its number cannot be compared; {anew[3:]}"
        ]
    homes = [area / d / cfg.script for d in SCRIPT_HOMES]
    script = next((p.resolve() for p in homes if p.is_file()), None)
    kept = script_copy_path(answering_run, Path(cfg.script).suffix)
    here = Path.cwd()
    if script is None:
        return [
            f"{shown(homes[0], here)} is gone — {rid} ran it: restore it from "
            f"{shown(kept, here)} {anew}"
        ]
    out: list[str] = []
    if file_digest(script)[:DIGEST_CHARS] != cfg.script_sha:
        out.append(
            f"{shown(script, here)} changed since {rid} ran it — its number came from "
            f"other code: restore the script as it ran (`cp {shown(kept, here)} "
            f"{shown(script, here)}`) {anew}"
        )
    repo = git_root(area)
    try:
        helpers = [f for f in measured_code(script, repo or area) if f != script]
    except SourceError as exc:
        return [*out, f"the code {rid} ran cannot be read now: {exc}"]
    return out + _helpers_since_run(helpers, script, repo, answering_run, cfg)


def _helpers_since_run(  # noqa: C901 — one sentence per way a helper can differ
    helpers: list[Path], script: Path, repo: Path | None, run_dir: Path, cfg: RunConfig
) -> list[str]:
    """Blockers for HELPERS (the modules SCRIPT imports) that differ from
    the run's tree, or whose state then is not recorded."""
    rid, here = run_dir.name, Path.cwd()
    out: list[str] = []
    copied = set(cfg.untracked_sources)
    in_git: list[Path] = []
    for f in helpers:
        rel = (
            f.relative_to(script.parent).as_posix()
            if script.parent in f.parents
            else None
        )
        if rel is not None and rel in copied:
            copy = untracked_copy_path(run_dir, rel)
            if not copy.is_file() or copy.read_bytes() != f.read_bytes():
                out.append(
                    f"{shown(f, here)} changed since {rid} ran it (it was untracked; "
                    f"the run kept it as {shown(copy, here)}) — restore it from there "
                    f"or measure anew and audit that run"
                )
        else:
            in_git.append(f)
    if not in_git:
        return out
    if repo is None or not cfg.git_full or cfg.git_full == NO_GIT:
        return [
            *out,
            f"{rid} recorded no commit, so the helpers its script imports "
            f"({', '.join(shown(f, here) for f in in_git)}) cannot be compared — "
            f"measure anew in the repository and audit that run",
        ]
    patch = patch_path(run_dir)
    try:
        then = blobs_then(
            repo,
            cfg.git_full,
            patch.read_text(encoding="utf-8") if patch.is_file() else "",
            in_git,
        )
        now = blobs_now(repo, in_git)
    except GitError as exc:
        return [
            *out,
            f"the tree {rid} started from cannot be read: {exc} — measure anew and audit that run",
        ]
    for f in in_git:
        if then[f] is None:
            out.append(
                f"{shown(f, here)} was not committed when {rid} started — what it "
                f"held then is not recorded; commit it, measure anew and audit that run"
            )
        elif then[f] != now[f]:
            out.append(
                f"{shown(f, here)} changed since {rid} ran — restore it as the run's "
                f"tree held it (`git checkout {cfg.git_full[:12]} -- {shown(f, here)}`"
                + (f", then {shown(patch, here)}" if patch.is_file() else "")
                + ") or measure anew and audit that run"
            )
    return out


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
