"""run_record_check — what a finished run's record must show before its number counts.

The code that produced the number unchanged since the run
(`code_since_run`), a criterion's denominator against a recorded input
count (`criterion_n_input_mismatches`), the source frozen in the run and
tracked in git (`provenance_findings`), a model that answered named in
the record (`model_provenance_gap`), a single draw where a model was
asked (`single_draw`), every JSONL row held to the runs that wrote it
(`row_provenance_findings`), every arm the protocol names present
(`arm_findings`), a null lane that moved in the kept rows
(`null_lane_findings`), a computation's kept number held as the head's
`[kept] key` names it (`kept_number_gaps`). Each returns findings; finalize's stations decide
their grade. Read-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
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
from labkit.run.provenance import source_digest, visible_files
from labkit.formats import jsonl, promises, protocol_block
from labkit.formats.data_manifest import MANIFEST_NAME, ManifestError, parse_manifest
from labkit.formats.gate import GateFinding, blocker
from labkit.formats.runs import (
    OutputEntry,
    RunConfig,
    RunConfigError,
    read_metrics,
    read_outputs,
    next_output_name,
    read_run_config,
    resolve_recorded,
)
from labkit.formats.answering_run import (
    lineage,
    model_provenance_run,
    repeats_of,
)
from labkit.formats.repo import (
    gate_command,
    measure_anew,
    GitError,
    blobs_now,
    blobs_then,
    commit_known,
    git_root,
    git_run,
    own_path,
    shown,
    text_at,
)


def _tracked(repo: Path, path: Path) -> bool:
    """Is `path` tracked in `repo`? The exit code is the answer — for a
    directory, yes once one file under it is (`_untracked_files` holds a
    directory source file by file)."""
    return git_run(["ls-files", "--error-unmatch", str(path)], repo).returncode == 0


CRITERION_N = promises.CRITERION_N_KEY

#: what a script search in an area passes over: run records, outputs, data
_NOT_CODE = frozenset({"runs", "output", "data", "__pycache__", ".git"})
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
    the command that restores the code as it ran. A blocker that found a
    difference names its run as data (`GateFinding.changed_since`); one
    that could not compare (no script or commit recorded, a commit this
    clone lacks, a helper uncommitted then, a script gone or ambiguous)
    names none. Read-only."""
    try:
        chain = lineage(answering_run)
    except ValueError as exc:
        return [
            blocker(
                f"{answering_run.name}: its runs cannot be followed ({exc})",
                fix=measure_anew(answering_run.parent.parent),
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
                fix=measure_anew(area),
            )
        ], []
    script = script_of(area, cfg)
    kept = script_copy_path(run, Path(cfg.script).suffix)
    if isinstance(script, str):
        return [
            blocker(
                f"{rid}: {script}",
                fix=f"{measure_anew(area)}, with the script where it is now; only "
                f"when it was moved or deleted by mistake, restore it from "
                f"{shown(kept, here)}",
            )
        ], []
    out: list[GateFinding] = []
    if file_digest(script)[:DIGEST_CHARS] != cfg.script_sha:
        out.append(
            replace(
                blocker(
                    f"{shown(script, here)} changed since {rid} ran it — its number "
                    f"came from other code",
                    fix=f"{FIX_FIRST} (`cp {shlex.quote(shown(kept, here))} "
                    f"{shlex.quote(shown(script, here))}`)",
                ),
                changed_since=rid,
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
                fix=f"repair what the error names, then `{gate_command('finalize', area)}`",
            ),
        ], []
    b, w = _helpers_since_run(helpers, script, repo, run, cfg)
    return out + b, w


def script_of(area: Path, cfg: RunConfig) -> Path | str:
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


def script_as_run(area: Path, run: Path) -> tuple[Path | None, str]:
    """(the file that holds the script RUN ran, as it ran it; a note): the
    area's script (`script_of`) when its digest is the `script_sha` the run
    recorded (note ""), else the run's own copy (`runs.script_copy_path`)
    when that copy's is (the note says so and why the tree's is not shown);
    (None, why) when neither is — a script changed since the run is never
    shown as the one it ran. Exact over the script's bytes; the modules it
    imports are `code_since_run`'s question. Read-only."""
    cfg = read_run_config(run)
    if cfg is None:
        return None, f"run {run.name} has no readable record"
    if cfg.script_sha == "no-script":
        return None, f"run {run.name} recorded no script"
    script = script_of(area, cfg)
    if (
        isinstance(script, Path)
        and file_digest(script)[:DIGEST_CHARS] == cfg.script_sha
    ):
        return script, ""
    tree = (
        script
        if isinstance(script, str)
        else f"{script.name} changed since {run.name} ran it"
    )
    kept = script_copy_path(run, Path(cfg.script).suffix)
    if kept.is_file() and file_digest(kept)[:DIGEST_CHARS] == cfg.script_sha:
        return kept, f"the copy {run.name} kept as it ran it — {tree}"
    return None, (
        f"{tree}, and {run.name} keeps no copy whose digest is the "
        f"{cfg.script_sha} it recorded"
    )


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
                    replace(
                        blocker(
                            f"{shown(f, here)} changed since {rid} ran it (it was "
                            f"untracked; the run kept it as {shown(copy, here)})",
                            fix=f"{FIX_FIRST} (`cp {shlex.quote(shown(copy, here))} "
                            f"{shlex.quote(shown(f, here))}`)",
                        ),
                        changed_since=rid,
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
                fix=f"in the repository, {measure_anew(run_dir.parent.parent)}",
            ),
        ], warnings
    if not commit_known(repo, cfg.git_full):
        return [
            *out,
            blocker(
                f"{rid} started at commit {cfg.git_full[:12]}, which this clone "
                f"does not hold",
                fix=f"fetch it (`git fetch --unshallow` in a shallow clone) or "
                f"{measure_anew(run_dir.parent.parent)}",
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
                fix=measure_anew(run_dir.parent.parent),
            ),
        ], warnings
    for f in in_git:
        if then[f] is None:
            out.append(
                blocker(
                    f"{shown(f, here)} was not committed when {rid} started — what "
                    f"it held then is not recorded",
                    fix=f"commit it, then {measure_anew(run_dir.parent.parent)}",
                )
            )
        elif then[f] != now[f]:
            blob = then[f]
            out.append(
                replace(
                    blocker(
                        f"{shown(f, here)} changed since {rid} ran",
                        fix=f"{FIX_FIRST} (`git -C {shlex.quote(shown(repo, here))} "
                        f"cat-file blob {blob} > {shlex.quote(shown(f, here))}`)",
                    ),
                    changed_since=rid,
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


def has_null_lanes(rows: list[dict]) -> bool:
    """Do ROWS hold both NULL_LANES — is there a null comparison to hold?"""
    return {r.get("lane") for r in rows} >= set(NULL_LANES)


@dataclass(frozen=True)
class NullLanes:
    """What `null_lane_findings` found: one BLOCKER per output whose null
    lane did not move (UNMOVED), with its way out, and how many outputs held
    both lanes (EXAMINED) — 0 says the check did not apply, not that it
    passed."""

    unmoved: list[GateFinding]
    examined: int


def null_lane_findings(answering_run: Path) -> NullLanes:
    """The outputs of ANSWERING_RUN (`runs.read_outputs`, its JSONL files)
    held to their null lane (`NullLanes`): an output with both lanes whose
    null did not move (`null_lane_unmoved`) is named — read from the rows
    the run kept, not from a check in the editable script: a cold agent
    deleted the script's own guard before it first ran (SAB-like apply
    case, 2026-10-27). Raises ValueError on an output that does not read."""
    out: list[GateFinding] = []
    examined = 0
    for entry in read_outputs(answering_run) or []:
        if entry.path.suffix != ".jsonl" or not entry.path.is_file():
            continue
        rows = jsonl.data_rows(entry.path.read_text(encoding="utf-8"), str(entry.path))
        if not has_null_lanes(rows):
            continue
        examined += 1
        if null_lane_unmoved(rows):
            out.append(
                blocker(
                    f"{entry.path.name}: the null lane answers what the registered "
                    f"lane answers on every item — it measures no noise floor (an "
                    f"instrument that ignores its labels predicts the same in both "
                    f"lanes; LAB-034 Null condition in the same run)",
                    fix="give the instrument a null of its own, e.g. its predictions "
                    f"against permuted gold, then "
                    f"{measure_anew(answering_run.parent.parent)}",
                )
            )
    return NullLanes(out, examined)


def criterion_n_input_mismatches(answering_run: Path) -> list[str]:
    """Warnings: a criterion's denominator (`criterion_<i>_n` in metrics.json) that
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
    area: Path, answering_run: Path, data_scope: str = ""
) -> tuple[list[GateFinding], list[str], list[str]]:
    """(blockers, warnings, pinned) for a run at low repeat cost: source
    frozen, files tracked (a directory source file by file,
    `_untracked_files`) — or, for a source outside git, pinned: the
    protocol's Data / scope DATA_SCOPE names the checksum the run recorded
    for it, and the bytes there now give that checksum (`pinned_source`,
    the standard's Fixed inputs: large or protected data stay out of the
    repository, which holds their source or access route, version and
    checksum); or named, each untracked file with its sha256, in a tracked
    `MANIFEST.sha256` at or above the source (`_manifest_finding`), every
    file matching its line and the source the bytes the run read. PINNED
    says so per source; bytes changed since the run, or unlike their
    manifest line, are a blocker. Raises GitError when git cannot list a directory
    source's tracked files or say whether an untracked source is ignored
    (`_ignore_rules`): finalize then ends in that error, not in a blocker
    with a way out that may not lead out."""
    blockers: list[GateFinding] = []
    warnings: list[str] = []
    pinned: list[str] = []
    cfg = read_run_config(answering_run)
    data = cfg.data if cfg else {}
    if not data:
        blockers.append(
            blocker(
                "source not frozen — the run carries no `data=`",
                fix="pass data={name: path} to runlog.run so sha and rows are "
                f"recorded, then {measure_anew(area)}",
            )
        )
    sources = [
        (resolve_recorded(v["path"], answering_run), v.get("sha256"))
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
        return blockers, warnings, pinned
    for f, sha in sources:
        found, note = _source_finding(repo, area, f, sha, data_scope)
        if found is not None:
            blockers.append(found)
        if note is not None:
            pinned.append(note)
    # The output rows are born after the run, so on every first pass they are
    # untracked by construction: a warning that names the command, not a
    # blocker that sends the agent round the loop (2026-10-05, five probes).
    # An output that is gone is `output_record_findings`' blocker, on every lane.
    for f in outputs:
        if f.exists() and not _tracked(repo, f):
            warnings.append(
                f"output {f.name} is not yet tracked — `git add {f}` before "
                f"the commit that cites the number"
            )
    return blockers, warnings, pinned


def _source_finding(
    repo: Path, area: Path, source: Path, sha: object, data_scope: str
) -> tuple[GateFinding | None, str | None]:
    """(blocker, pinned note) for one SOURCE the run recorded with checksum
    SHA: gone, untracked and not pinned (`_untracked_source`), pinned but
    changed since the run — or tracked, or pinned and unchanged (the note).
    Raises GitError as `_untracked_files` does."""
    if not source.exists():
        return _gone(source, area), None
    untracked = _untracked_files(repo, source)  # a directory: file by file
    if not untracked:
        return None, None
    held = pinned_source(source, sha, data_scope)
    if held is None:
        named = _manifest_finding(repo, area, source, untracked, sha)
        if named is not None:
            return named
        return _untracked_source(repo, source, untracked, sha), None
    if held == PINNED:
        return None, (
            f"source {source} lies outside git, pinned by the checksum the run "
            f"recorded (sha256 {sha}), which Data / scope names"
        )
    return (
        blocker(
            f"source {source} is not the bytes the run read: {held} — Data / scope "
            f"pins it by the checksum the run recorded (sha256 {sha})",
            fix=f"restore the source the run read from the route Data / scope names, "
            f"or {measure_anew(area)}",
        ),
        None,
    )


#: `pinned_source`'s answer when the bytes are the ones the run read
PINNED = "pinned"


def pinned_source(source: Path, sha: object, data_scope: str) -> str | None:
    """Whether a source outside git is pinned by the protocol: None when the
    run recorded no checksum SHA or DATA_SCOPE (the Data / scope value) does
    not name it; PINNED when it does and SOURCE's bytes now give it
    (`provenance.source_digest`, the digest the run recorded, cut to its
    length); otherwise the sentence why not. Reads SOURCE, writes nothing."""
    if not isinstance(sha, str) or sha not in " ".join(data_scope.split()):
        return None
    now = source_digest(source)[: len(sha)]
    if now == sha:
        return PINNED
    return f"its sha256 is now {now}"


def _source_manifests(repo: Path, source: Path) -> list[Path]:
    """The `MANIFEST.sha256` files git tracks (the index holds them) in
    SOURCE's directory — SOURCE itself for a directory — and each one above
    it up to REPO, nearest first. Raises GitError as `git_run` does."""
    start = source.resolve() if source.is_dir() else own_path(source).parent
    dirs = [d for d in (start, *start.parents) if d == repo or repo in d.parents]
    return [
        d / MANIFEST_NAME for d in dirs if text_at(repo, d / MANIFEST_NAME) is not None
    ]


def _manifest_finding(
    repo: Path, area: Path, source: Path, untracked: list[Path], sha: object
) -> tuple[GateFinding | None, str | None] | None:
    """(blocker, note) for a SOURCE whose UNTRACKED files the tracked
    manifests at or above it name (`_source_manifests`, read as the index
    holds them; `data_manifest`), None when they name none of them — the
    source then falls to `_untracked_source`. A blocker when one is
    unnamed, when a named file's sha256 now differs from its line (every
    one is read again), when the source's bytes are not the ones the run
    recorded (SHA), and when a manifest does not read; else the note that
    the source is named and unchanged."""
    manifests = _source_manifests(repo, source)
    named: dict[Path, str] = {}
    for m in manifests:
        try:
            entries = parse_manifest(text_at(repo, m) or "", shown(m, repo))
        except ManifestError as exc:
            return (
                blocker(
                    f"{exc} — finalize cannot tell which files it names",
                    fix=f"correct the line, check it from the repository root "
                    f"(`shasum -a 256 -c {shown(m, repo)}`) and commit it "
                    f"(`git add {shlex.quote(str(m))}`); finalize reads it as git "
                    f"holds it",
                ),
                None,
            )
        for rel, digest in entries.items():
            named.setdefault(own_path(repo / rel), digest)
    files = [own_path(f) for f in untracked]
    if not any(f in named for f in files):
        return None
    where = ", ".join(shown(m, repo) for m in manifests)
    unnamed = [f for f in files if f not in named]
    if unnamed:
        names = ", ".join(shown(f, repo) for f in unnamed[:NAMED_UNTRACKED])
        more = ", …" if len(unnamed) > NAMED_UNTRACKED else ""
        return (
            blocker(
                f"source {source}: {len(unnamed)} file(s) are neither tracked nor "
                f"named in {where} ({names}{more}) — the number cannot be "
                f"re-derived from the repository",
                fix=f"add their sha256 to {where} (`shasum -a 256` from the "
                f"repository root) and commit it",
            ),
            None,
        )
    changed = [f for f in files if file_digest(f) != named[f]]
    if changed:
        names = ", ".join(shown(f, repo) for f in changed[:NAMED_UNTRACKED])
        more = ", …" if len(changed) > NAMED_UNTRACKED else ""
        return (
            blocker(
                f"source {source}: {len(changed)} file(s) are not the bytes {where} "
                f"names ({names}{more})",
                fix=f"restore them from the copy the manifest describes, or "
                f"{measure_anew(area)} and refresh the manifest with the data",
            ),
            None,
        )
    if not isinstance(sha, str) or source_digest(source)[: len(sha)] != sha:
        return (
            blocker(
                f"source {source} matches {where}, but not the bytes the run read "
                f"(the run recorded sha256 {sha})",
                fix=f"restore the data the run read, or {measure_anew(area)}",
            ),
            None,
        )
    return None, (
        f"source {source} lies outside git, named file by file in {where}: "
        f"each sha256 holds, and the bytes are the ones the run read"
    )


#: the command that ends an area without a number while finalize stays
#: blocked — the handover as the stamped AGENTS.md gives it (a test holds
#: the two together); its <…> parts are the agent's to fill
HANDOVER_COMMAND = (
    'protocol-fill <PROTOCOL> --handover --why "<what blocks>" --tried '
    '"<what you tried>" --into REPORT.md'
)


#: how many untracked files under a directory source its blocker names
NAMED_UNTRACKED = 3


def _untracked_files(repo: Path, source: Path) -> list[Path]:
    """The files of SOURCE that git does not track in REPO, [] when it tracks
    them all: SOURCE itself for a file; for a directory each visible file
    under it (`provenance.visible_files`) — the files the run's digest and
    row count covered, since the record keeps no list of them. A directory
    is tracked only when every one of them is: `git ls-files --error-unmatch
    DIR` succeeds once one file under it is (pilot t21: a committed
    SOURCE.md passed two untracked GeoJSON files). An empty or all-hidden
    directory passes — the run read no file of it. A symbolic link under it
    counts as tracked when git holds the link, not its target's content.
    The directory is resolved first; one outside REPO holds no tracked
    file. Raises GitError when git fails."""
    if not source.is_dir():
        return [] if _tracked(repo, source) else [source]
    base = source.resolve()
    files = visible_files(base)
    if base != repo and repo not in base.parents:
        return files
    # both sides resolved: git lists paths under REPO (git_root resolves it)
    # and BASE is resolved, so a file is the same Path in either set
    listed = git_run(["ls-files", "-z", "--", str(base)], repo)
    if listed.returncode != 0:
        raise GitError(f"git ls-files in {repo}: {listed.stderr.strip()}")
    tracked = {repo / p for p in listed.stdout.split("\0") if p}
    return [f for f in files if f not in tracked]


def _untracked_source(
    repo: Path, source: Path, untracked: list[Path], sha: object
) -> GateFinding:
    """The blocker `provenance_findings` raises for a SOURCE of the run whose
    files UNTRACKED git does not track in REPO (at repeat cost low), its way
    out the two routes the standard's Fixed inputs names: a small input that
    may legally be shared is committed; for large or protected data the
    protocol's Data / scope names its source or access route and version
    (the field guide), beside the checksum SHA the run recorded, which
    `pinned_source` then holds the bytes to. A directory names its untracked files (`NAMED_UNTRACKED` of
    them), and its commit lists each of them, so no file the run did not
    read goes in. When git ignores any of them the sentence names the rule
    (`_ignore_rules`) and the commit adds them past it (`git add -f`): a
    plain `git add` of an ignored path is refused (pilot t60). Raises
    GitError when git fails."""
    rules = _ignore_rules(repo, untracked)
    what, them = f"source {source} is not tracked in git", "it"
    if source.is_dir():
        names = ", ".join(shown(f, source) for f in untracked[:NAMED_UNTRACKED])
        more = ", …" if len(untracked) > NAMED_UNTRACKED else ""
        what += f": {len(untracked)} file(s) under it are not ({names}{more})"
        them = "files under it"
    ignored = f", and git ignores {them} ({'; '.join(rules)})" if rules else ""
    force = " -f" if rules else ""
    if source.is_dir():
        add = f"git add{force} -- " + " ".join(shlex.quote(str(f)) for f in untracked)
    else:
        add = f"git add{force} {shlex.quote(str(source))}"
    past = " past the rule" if rules else ""
    pin = (
        f"large or protected data stay out of git: name the source or access "
        f"route and version in the protocol's Data / scope beside the checksum "
        f"this run recorded, `sha256 {sha}` — finalize then holds the file to it; "
        f"or list each file with its sha256 in a tracked `{MANIFEST_NAME}` at or "
        f"above it, paths from the repository root"
        if isinstance(sha, str)
        else "large or protected data stay out of git, pinned by the checksum a run "
        "records: this run recorded none, so pass the source in `data=` and measure "
        "again"
    )
    return blocker(
        f"{what}{ignored} — the number cannot be re-derived from the repository",
        fix=f"if it is small and may legally be shared, commit it{past} "
        f"(`{add}`); {pin}",
    )


def _ignore_rules(repo: Path, paths: list[Path]) -> list[str]:
    """The rules under which git ignores any of PATHS in REPO, each once, as
    `git check-ignore -v` names them (`<file>:<line>:<pattern>`); [] when no
    rule ignores one. A path outside REPO is left out: no rule of REPO's
    applies, and check-ignore refuses it. Raises GitError when git fails."""
    own = (own_path(p) for p in paths)
    inside = [p for p in own if repo in p.parents]
    if not inside:
        return []
    r = git_run(
        ["check-ignore", "-v", "-z", "--stdin"],
        repo,
        stdin="".join(f"{p}\0" for p in inside),
    )
    if r.returncode not in (0, 1):  # 1: no path is ignored
        raise GitError(f"git check-ignore in {repo}: {r.stderr.strip()}")
    # -z -v: four fields per matched path — rule file, line, pattern, path;
    # a pattern starting with `!` matched to un-ignore the path, so it is no
    # rule that ignores it
    fields = r.stdout.split("\0")
    records = [fields[i : i + 3] for i in range(0, len(fields) - 3, 4)]
    return sorted({":".join(rec) for rec in records if not rec[2].startswith("!")})


def output_drift(entry: OutputEntry) -> str | None:
    """Why the file at ENTRY.path is not the one the run recorded in
    outputs.json, or None when it is: the file is gone, the run ended
    without it (no sha256 recorded), or its sha256 differs from the record.
    The record is the run's, taken after the run (`runlog.Run._finalize`);
    the tree at check time is only compared, never trusted. Reads the file,
    writes nothing."""
    if not entry.path.is_file():
        return "the file is gone"
    if entry.sha256 is None:
        return "the run ended without it (outputs.json records no sha256)"
    actual = file_digest(entry.path)
    if not actual.startswith(entry.sha256):
        return (
            f"its sha256 {actual[: len(entry.sha256)]} is not the recorded "
            f"{entry.sha256}"
        )
    return None


def output_record_findings(answering_run: Path) -> list[GateFinding]:
    """A blocker per output ANSWERING_RUN registered (`runs.read_outputs`)
    whose file is not the one the run recorded (`output_drift`): the
    number's rows, and a deliverable the run wrote for an external task,
    are pinned to the run by path and sha256 — a file swapped, edited or
    removed after the run is no longer what the run produced. Seven
    delivered states had their `pred_results/*.csv` swapped with another
    state's and no gate noticed (injection benchmark, 2026-10-29). Raises
    ArtefactError when outputs.json does not read."""
    return [
        blocker(
            f"{entry.path}: not the file run {answering_run.name} recorded — {why}",
            fix=measure_anew(answering_run.parent.parent),
        )
        for entry in read_outputs(answering_run) or []
        if (why := output_drift(entry)) is not None
    ]


def _gone(f: Path, area: Path) -> GateFinding:
    """A source file of AREA's run is gone: its rows cannot be re-derived."""
    return blocker(
        f"{f} is gone — the run's rows cannot be re-derived",
        fix=f"restore it (`git checkout HEAD -- {shlex.quote(str(f))}` where git "
        f"holds it), or {measure_anew(area)}",
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
    note (a Store without `prov`), not proof of anything (2026-10-09). Rows
    of a continued run whose script differs from this run's are a blocker
    too (`_continued_with_other_code`): the number is that code's. A
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
                fix=measure_anew(answering_run.parent.parent),
            )
        ], []
    for entry in read_outputs(answering_run) or []:
        if entry.path.suffix != ".jsonl" or not entry.path.is_file():
            continue
        try:
            rr = batch.row_runs(entry.path)
        except ValueError as exc:
            blockers.append(
                blocker(
                    f"{entry.path.name}: {exc}",
                    fix=measure_anew(answering_run.parent.parent),
                )
            )
            continue
        ok = allowed | set(entry.continues)
        foreign = sorted(r for r in rr.runs if r not in ok)
        if foreign:
            blockers.append(
                blocker(
                    f"{entry.path.name}: {sum(rr.runs[r] for r in foreign)} row(s) "
                    f"from {', '.join(foreign)} — a run this run neither is, "
                    f"continues nor derives from; a file of two measurements",
                    fix=f"{measure_anew(answering_run.parent.parent)}, into an output "
                    f"file of its own — a new name for the output in the measuring "
                    f"script, e.g. `{next_output_name(entry.path)}`; keep "
                    f"{entry.path.name} and its runs, never delete it: those rows are "
                    f"the other runs' evidence",
                )
            )
        if entry.continues:
            notes.append(
                f"{entry.path.name}: continues {', '.join(entry.continues)} "
                f"({', '.join(f'{r}: {n}' for r, n in sorted(rr.runs.items()))} rows)"
            )
            blockers += _continued_with_other_code(
                answering_run, entry.path, rr.runs, entry.continues
            )
        if rr.unstamped:
            notes.append(
                f"{entry.path.name}: {rr.unstamped} row(s) without _prov — written "
                f"outside a run or by a Store without prov; their run is unknown"
            )
    return blockers, notes


def _continued_with_other_code(
    answering_run: Path, path: Path, rows: dict[str, int], continued: tuple[str, ...]
) -> list[GateFinding]:
    """A blocker per run ANSWERING_RUN continues in PATH whose recorded
    script (`script_sha`) is not the answering run's, where the rows declare
    that they depend on code (`_instrument` carries `code_sha`, the
    estimator skeleton's): its ROWS were written by other code, and the
    number counts them as this run's. A fix measured again into the faulty
    run's file kept every faulty row, and finalize said only "continues"
    (repair case, 2026-10-28). Rows without it — a model's answers — do not
    depend on the script: a parser fix re-reads them. A run whose record
    does not read is left to the record checks."""
    own = read_run_config(answering_run)
    if own is None or not _rows_carry_code(path):
        return []
    out: list[GateFinding] = []
    for rid in continued:
        other = read_run_config(answering_run.parent / rid)
        if other is None or other.script_sha == own.script_sha:
            continue
        out.append(
            blocker(
                f"{path.name}: {rows.get(rid, 0)} row(s) come from {rid}, which ran "
                f"other code (script {other.script_sha}, this run's "
                f"{own.script_sha}) — {answering_run.name}'s number counts that "
                f"code's rows as its own",
                fix=f"measure anew into an output file of its own — a new name for "
                f"the output in the measuring script, e.g. "
                f"`{next_output_name(path)}` — keep {path.name} and its runs, "
                f"then audit that run",
            )
        )
    return out


def _rows_carry_code(path: Path) -> bool:
    """Does a row of PATH name the code that wrote it (`_instrument` with a
    `code_sha`)? Raises ValueError on a file that does not read."""
    return any(
        isinstance(r.get("_instrument"), dict) and "code_sha" in r["_instrument"]
        for r in batch.Store(path).records()
    )


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


#: how many of the run's other metrics a kept-number blocker names
_HELD_SHOWN = 6


def kept_number_gaps(
    key: str, metrics: dict, run: str, area: Path
) -> list[GateFinding]:
    """A guaranteed blocker when METRICS, the metrics.json of the run RUN of
    AREA, does not hold KEY — the computation's `[kept] key` — as a finite
    number (`protocol_block.finite_number`: a bool, a text, None, NaN or an
    infinity is none), naming the key, the run and what it holds instead;
    [] when it does. The compute skeleton's own check (`kept_number`) sits
    in an agent-editable script; this one reads the head and the run's
    record. It binds the key, not its meaning: a wrong computation stored
    under KEY passes — the area's tests and the analysis audit judge that
    (docs/notes/2026-11-01-kept-key-in-the-head.md)."""
    if key in metrics and protocol_block.finite_number(metrics[key]):
        return []
    others = [(k, v) for k, v in metrics.items() if k != key]
    held = ", ".join(f"{k} = {v!r}"[:60] for k, v in others[:_HELD_SHOWN]) + (
        f", … ({len(others) - _HELD_SHOWN} more)" if len(others) > _HELD_SHOWN else ""
    )
    what = (
        f"holds `{key}` = {metrics[key]!r}, which is no finite number"
        if key in metrics
        else f"holds no `{key}`"
    )
    return [
        blocker(
            f"the kept number: metrics.json of {run} {what} — the head's [kept] "
            f"names `{key}` as the number this computation reports"
            + (f"; it holds {held}" if held else "; it holds nothing else"),
            fix=f"write `{key}` as a finite number from evaluate_rows() (the compute "
            f"skeleton reads the key from the head's [kept]), then "
            f"{measure_anew(area)}; when [kept] names the wrong number, set it "
            f"before the first measurement — after it, register anew "
            f"(`labkit-init exp <new-name> --kind compute`)",
        )
    ]
