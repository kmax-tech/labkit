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
import shlex
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
from labkit.formats import jsonl, promises, protocol_block
from labkit.formats.gate import GateFinding, blocker
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
    commit_known,
    git_root,
    git_run,
    shown,
)


def _tracked(repo: Path, path: Path) -> bool:
    """Is `path` tracked in `repo`? The exit code is the answer."""
    return git_run(["ls-files", "--error-unmatch", str(path)], repo).returncode == 0


CRITERION_N = promises.CRITERION_N_KEY

#: what a script search in an area passes over: run records, outputs, data
_NOT_CODE = frozenset({"runs", "output", "data", "__pycache__", ".git"})
#: the way out where the run cannot be held to its code or rows
MEASURE_ANEW = "measure anew and audit that run"
#: the way out of a code change since the run, the fix first: restoring the
#: old code removes the difference, not a fault the change corrected
FIX_FIRST = (
    "measure anew with the code as it is now and audit that run; only when the "
    "change was not meant, restore it as it ran"
)


def code_since_run(
    area: Path, answering_run: Path
) -> tuple[list[GateFinding], list[str]]:
    """(blockers, warnings): the code that produced ANSWERING_RUN's number
    is not the code here now (audit 2026-10-27, A1). For the run and each
    run it derives from (`answering_run.lineage`: a re-evaluation rests on
    its parent's rows): its script against the hash the run recorded
    (`script_sha`), and each module the script imports
    (`scope_sha.measured_code`: beside it, under `lib/` or `src/`) against
    the tree the run started from — its commit with the part of its
    `uncommitted.patch` that touches the module (`repo.blobs_then`), an
    untracked sibling against its copy in the run. Exact over that scope; a
    change made and undone in between and code loaded another way are not
    seen, and a module in another repository (a submodule, a link out of
    the repository) is a warning, not compared. Analysis code and the pin
    are not compared: a fix there needs no new measurement. Each blocker
    names its way out, the fix first: measure anew with the code as it is
    and audit that run — restoring the old code removes the difference,
    not a fault the change corrected —, and only for a change not meant,
    the command that restores the code as it ran. Read-only."""
    try:
        chain = lineage(answering_run)
    except ValueError as exc:
        return [
            blocker(
                f"{answering_run.name}: its runs cannot be followed ({exc})",
                fix=MEASURE_ANEW,
            )
        ], []
    blockers: list[GateFinding] = []
    warnings: list[str] = []
    for run in chain:
        b, w = _run_code(area, run)
        blockers += b
        warnings += w
    return blockers, warnings


def _run_code(area: Path, run: Path) -> tuple[list[GateFinding], list[str]]:
    """`code_since_run` for one RUN, its own record only."""
    cfg = read_run_config(run)
    if cfg is None:
        return [], []  # the answering-run station names an unreadable record
    rid, here = run.name, Path.cwd()
    if cfg.script_sha == "no-script":
        return [
            blocker(
                f"{rid} recorded no script — the code behind its number cannot be compared",
                fix=MEASURE_ANEW,
            )
        ], []
    script = _script_of(area, cfg)
    kept = script_copy_path(run, Path(cfg.script).suffix)
    if isinstance(script, str):
        return [
            blocker(
                f"{rid}: {script}",
                fix="measure anew with the script where it is now and audit that "
                f"run; only when it was moved or deleted by mistake, restore it "
                f"from {shown(kept, here)}",
            )
        ], []
    out: list[GateFinding] = []
    if file_digest(script)[:DIGEST_CHARS] != cfg.script_sha:
        out.append(
            blocker(
                f"{shown(script, here)} changed since {rid} ran it — its number "
                f"came from other code",
                fix=f"{FIX_FIRST} (`cp {shlex.quote(shown(kept, here))} "
                f"{shlex.quote(shown(script, here))}`)",
            )
        )
    repo = git_root(area)
    try:
        helpers = [f for f in measured_code(script, repo or area) if f != script]
    except SourceError as exc:
        return [
            *out,
            blocker(
                f"the code {rid} ran cannot be read now: {exc}",
                fix="repair what the error names, then finalize again",
            ),
        ], []
    b, w = _helpers_since_run(helpers, script, repo, run, cfg)
    return out + b, w


def _script_of(area: Path, cfg: RunConfig) -> Path | str:
    """The script the run ran, as it stands here now: the path its command
    names (`sys.argv[0]`, relative to the area, the repository or the
    area's scripts/ — the working directory then is not recorded), else
    the one file of its name in the area; a sentence when it is gone or
    when several carry its name."""
    named = Path(cfg.command[0]) if cfg.command else Path(cfg.script)
    repo = git_root(area)
    bases = [area, *([repo] if repo else []), area / "scripts"]
    for p in [named] if named.is_absolute() else [b / named for b in bases]:
        if p.is_file() and p.name == cfg.script:
            return p.resolve()
    found = [
        p.resolve()
        for p in area.rglob(cfg.script)
        if p.is_file() and not _NOT_CODE.intersection(p.relative_to(area).parts)
    ]
    if len(found) == 1:
        return found[0]
    here = Path.cwd()
    if found:
        return (
            f"its script {cfg.script} cannot be told apart from "
            f"{', '.join(shown(p, here) for p in found)}"
        )
    return f"its script {named} is gone"


def _helpers_since_run(  # noqa: C901 — one sentence per way a helper can differ
    helpers: list[Path], script: Path, repo: Path | None, run_dir: Path, cfg: RunConfig
) -> tuple[list[GateFinding], list[str]]:
    """(blockers, warnings) for HELPERS, the modules SCRIPT imports: one
    that differs from the run's tree or whose state then is not recorded
    blocks; one in another repository is named, not compared."""
    rid, here = run_dir.name, Path.cwd()
    out: list[GateFinding] = []
    warnings: list[str] = []
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
                    blocker(
                        f"{shown(f, here)} changed since {rid} ran it (it was "
                        f"untracked; the run kept it as {shown(copy, here)})",
                        fix=f"{FIX_FIRST} (`cp {shlex.quote(shown(copy, here))} "
                        f"{shlex.quote(shown(f, here))}`)",
                    )
                )
        elif repo is not None and not _in_repo(f, repo):
            warnings.append(
                f"{shown(f, here)} lies in another repository (a submodule or a link "
                f"out of this one) — not compared with what {rid} ran"
            )
        else:
            in_git.append(f)
    if not in_git:
        return out, warnings
    names = ", ".join(shown(f, here) for f in in_git)
    if repo is None or not cfg.git_full or cfg.git_full == NO_GIT:
        return [
            *out,
            blocker(
                f"{rid} recorded no commit, so the helpers its script imports "
                f"({names}) cannot be compared",
                fix="measure anew in the repository and audit that run",
            ),
        ], warnings
    if not commit_known(repo, cfg.git_full):
        return [
            *out,
            blocker(
                f"{rid} started at commit {cfg.git_full[:12]}, which this clone "
                f"does not hold",
                fix=f"fetch it (`git fetch --unshallow` in a shallow clone) or "
                f"{MEASURE_ANEW}",
            ),
        ], warnings
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
            blocker(
                f"the tree {rid} started from cannot be read for {names}: {exc}",
                fix=MEASURE_ANEW,
            ),
        ], warnings
    for f in in_git:
        if then[f] is None:
            out.append(
                blocker(
                    f"{shown(f, here)} was not committed when {rid} started — what "
                    f"it held then is not recorded",
                    fix=f"commit it, {MEASURE_ANEW}",
                )
            )
        elif then[f] != now[f]:
            blob = then[f]
            out.append(
                blocker(
                    f"{shown(f, here)} changed since {rid} ran",
                    fix=f"{FIX_FIRST} (`git -C {shlex.quote(shown(repo, here))} "
                    f"cat-file blob {blob} > {shlex.quote(shown(f, here))}`)",
                )
            )
    return out, warnings


def _in_repo(path: Path, repo: Path) -> bool:
    """Is PATH a file of REPO itself — inside it once links are resolved,
    and not in a nested repository (a submodule)?"""
    real, root = path.resolve(), repo.resolve()
    if root not in real.parents:
        return False
    inner = git_root(real.parent)
    return inner is not None and inner.resolve() == root


#: the two scored lanes a null comparison runs in, as the skeletons name them
NULL_LANES = ("registered", "null")


def null_lane_unmoved(rows: list[dict]) -> bool:
    """Do ROWS carry a null lane that cannot have moved — for every item
    its null row's answer (`pred`, or `answer`) and gold equal its
    registered row's? Then the null measures no noise floor: an instrument
    that ignores its labels predicts the same in both lanes (LAB-034 Null
    condition in the same run). False without both lanes, or when one item
    differs — a permuted gold (`gold_of`) or another answer is a move."""
    lanes: dict[str, dict[object, tuple[object, object]]] = {k: {} for k in NULL_LANES}
    for r in rows:
        lane = r.get("lane")
        if lane in lanes and "item" in r:
            lanes[lane][r["item"]] = (r.get("pred", r.get("answer")), r.get("gold"))
    registered, null = lanes["registered"], lanes["null"]
    if not registered or not null:
        return False
    return all(registered.get(item) == said for item, said in null.items())


def null_lane_findings(answering_run: Path) -> list[GateFinding]:
    """One sentence per output of ANSWERING_RUN (`runs.read_outputs`, its
    JSONL files) whose null lane did not move (`null_lane_unmoved`) — read
    from the rows the run kept, not from a check in the editable script: a
    cold agent deleted the script's own guard before it first ran (SAB-like
    apply case, 2026-10-27). Raises ValueError on an output that does not
    read."""
    out: list[GateFinding] = []
    for entry in read_outputs(answering_run) or []:
        if entry.path.suffix != ".jsonl" or not entry.path.is_file():
            continue
        rows = jsonl.data_rows(entry.path.read_text(encoding="utf-8"), str(entry.path))
        if null_lane_unmoved(rows):
            out.append(
                blocker(
                    f"{entry.path.name}: the null lane answers what the registered "
                    f"lane answers on every item — it measures no noise floor (an "
                    f"instrument that ignores its labels predicts the same in both "
                    f"lanes; LAB-034 Null condition in the same run)",
                    fix="give the instrument a null of its own, e.g. its predictions "
                    "against permuted gold, then measure again and audit that run",
                )
            )
    return out


def criterion_n_input_mismatches(answering_run: Path) -> list[str]:
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


def provenance_findings(
    area: Path, answering_run: Path
) -> tuple[list[GateFinding], list[str]]:
    """(blockers, warnings) for a run at low repeat cost: source frozen, files tracked."""
    blockers: list[GateFinding] = []
    warnings: list[str] = []
    cfg = read_run_config(answering_run)
    data = cfg.data if cfg else {}
    if not data:
        blockers.append(
            blocker(
                "source not frozen — the run carries no `data=`",
                fix="pass data={name: path} to runlog.run so sha and rows are "
                "recorded, then measure again",
            )
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
            blockers.append(_gone(f))
        elif not _tracked(repo, f):
            blockers.append(
                blocker(
                    f"source {f} is not tracked in git — the number cannot be "
                    f"re-derived",
                    fix=f"commit it (`git add {shlex.quote(str(f))}`)",
                )
            )
    # The output rows are born after the run, so on every first pass they are
    # untracked by construction: a warning that names the command, not a
    # blocker that sends the agent round the loop (2026-10-05, five probes).
    for f in outputs:
        if not f.exists():
            blockers.append(_gone(f))
        elif not _tracked(repo, f):
            warnings.append(
                f"output {f.name} is not yet tracked — `git add {f}` before "
                f"the commit that cites the number"
            )
    return blockers, warnings


def _gone(f: Path) -> GateFinding:
    """A file the run recorded is gone: its rows cannot be re-derived."""
    return blocker(
        f"{f} is gone — the run's rows cannot be re-derived",
        fix=f"restore it (`git checkout HEAD -- {shlex.quote(str(f))}` where git "
        f"holds it), or {MEASURE_ANEW}",
    )


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


def row_provenance_findings(
    answering_run: Path,
) -> tuple[list[GateFinding], list[str]]:
    """(blockers, notes): every JSONL output of the run is held to the runs
    its rows name (`_prov.run`): rows may come from this run, from the runs
    it continues (a resumed file, named in outputs.json), or — for a
    derived run — from its derived_from lineage. Rows from any other run
    are a blocker: a file of two measurements. Rows without `_prov` are a
    note (a Store without `prov`), not proof of anything (2026-10-09). A
    broken lineage (`answering_run.lineage`) is the one blocker: without
    it no row can be held to a run."""
    blockers: list[GateFinding] = []
    notes: list[str] = []
    try:
        allowed = {run.name for run in lineage(answering_run)}
    except ValueError as exc:
        return [
            blocker(
                f"row provenance: the lineage of {answering_run.name} is broken — {exc}",
                fix=MEASURE_ANEW,
            )
        ], []
    for entry in read_outputs(answering_run) or []:
        if entry.path.suffix != ".jsonl" or not entry.path.is_file():
            continue
        try:
            rr = batch.row_runs(entry.path)
        except ValueError as exc:
            blockers.append(blocker(f"{entry.path.name}: {exc}", fix=MEASURE_ANEW))
            continue
        ok = allowed | set(entry.continues)
        foreign = sorted(r for r in rr.runs if r not in ok)
        if foreign:
            blockers.append(
                blocker(
                    f"{entry.path.name}: {sum(rr.runs[r] for r in foreign)} row(s) "
                    f"from {', '.join(foreign)} — a run this run neither is, "
                    f"continues nor derives from; a file of two measurements",
                    fix="measure anew into an output file of its own and audit that run",
                )
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
