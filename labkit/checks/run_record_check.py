"""run_record_check — what a finished run's record must show before its number counts.

The code that produced the number unchanged since the run
(`code_since_run`), a criterion's denominator against a recorded input
count (`criterion_n_input_mismatches`), each source's bytes equal to the
sha256 the run recorded, and the source tracked in git or ignored by a
rule (`provenance_findings`), a model that answered named in
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
from collections.abc import Mapping, Sequence
from pathlib import Path

from labkit.formats.commands import checkout_command, handover_command
from labkit.formats.commands import register_anew
from labkit.formats.runs import (
    NO_GIT,
    kept_script,
    metrics_path,
    output_file,
    patch_text,
    script_copy_path,
    untracked_copy_differs,
    untracked_copy_path,
)
from labkit.formats.scope_sha import (
    SourceError,
    measured_code,
    script_candidates,
    scripts_named,
)
from labkit.formats.digests import DIGEST_CHARS, file_digest
from labkit.run import batch
from labkit.run.provenance import source_digest, visible_files
from labkit.formats import promises, protocol_block
from labkit.formats.gate import (
    OPEN_RULE,
    cited_rule,
    STATIC_EVIDENCE,
    WARNING,
    GateFinding,
    blocker,
    outcome_of_failed_read,
)
from labkit.formats.runs import (
    CONFIG_FILE,
    ArtefactError,
    DataEntry,
    KeptRows,
    OutputEntry,
    OutputNow,
    RunConfig,
    RunConfigError,
    declares_no_inputs,
    read_data,
    read_metrics,
    read_outputs,
    next_output_name,
    read_run_config,
    resolve_recorded,
)
from labkit.formats.answering_run import repeats_of
from labkit.formats.runs import lineage, model_provenance_run
from labkit.formats.repo import (
    GitError,
    blobs_now,
    blobs_then,
    commit_known,
    git_root,
    ignoring_rules,
    own_path,
    path_kind,
    resolves_under,
    shown,
    tracked,
    tracked_under,
)
from labkit.formats.commands import gate_command, measure_anew


CRITERION_N = promises.CRITERION_N_KEY

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
    is not the code here now. For the run and each
    run it derives from (`runs.lineage`: a re-evaluation rests on
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
    names none. Read-only. An extraction exception of the test model
    (docs/notes/2026-11-10-test-model.md): every condition here is an answer
    of git or of the run's kept copies, so the comparison stays one boundary,
    tested against real repositories (`tests/test_run_code.py`)."""
    try:
        chain = lineage(answering_run)
    except ValueError as exc:
        return [
            blocker(
                f"{answering_run.name}: its runs cannot be followed ({exc})",
                fix=measure_anew(answering_run.parent.parent),
                rule=OPEN_RULE,
            )
        ], []
    blockers: list[GateFinding] = []
    warnings: list[str] = []
    for run in chain:
        b, w = _run_code(area, run)
        blockers += b
        warnings += w
    # every blocker of the comparison carries one rule, not decided yet
    return [replace(b, rule=OPEN_RULE) for b in blockers], warnings


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
                check_outcome=outcome_of_failed_read(exc),
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
    hit = script_candidates(area, repo, named, cfg.script)
    if hit is not None:
        return hit
    found = scripts_named(area, cfg.script)
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
    kept = kept_script(run, Path(cfg.script).suffix, cfg.script_sha)
    if kept is not None:
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
            if untracked_copy_differs(run_dir, rel, f):
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
                f"{rid} recorded no commit, or the area lies in no git repository "
                f"now, so the helpers its script imports ({names}) cannot be compared",
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
    try:
        then = blobs_then(
            repo,
            cfg.git_full,
            patch_text(run_dir),
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
                    f"{shown(f, here)} is in neither {rid}'s commit nor its "
                    f"uncommitted.patch — untracked when the run started, or not yet "
                    f"there — so what the run imported is not recorded",
                    fix=f"commit {shown(f, here)}, then {measure_anew(run_dir.parent.parent)}",
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
    """What `null_lane_findings` found: one static-evidence WARNING per
    output whose null lane did not move (UNMOVED), with its way out, and how
    many outputs held
    both lanes (EXAMINED) — 0 says the check did not apply, not that it
    passed."""

    unmoved: list[GateFinding]
    examined: int


def null_lane_findings(kept: Sequence[KeptRows], area: Path) -> NullLanes:
    """The kept JSONL outputs of a run of AREA (`runs.kept_jsonl_rows`) held
    to their null lane (`NullLanes`): an output with both lanes whose null
    did not move (`null_lane_unmoved`) is named — read from the rows the
    run kept, not from a check in the editable script, which an agent can
    delete before it first runs (LAB-034 Null condition in the same run).
    AREA names the measuring command in the way out."""
    out: list[GateFinding] = []
    examined = 0
    for k in kept:
        if not has_null_lanes(k.rows):
            continue
        examined += 1
        if null_lane_unmoved(k.rows):
            # matching answer-gold pairs are certain; that the null measures
            # nothing is not — a placebo prompt or a fixed null predictor can
            # match honestly — so it warns: static evidence
            out.append(
                GateFinding(
                    WARNING,
                    f"{k.entry.path.name}: the null lane's answer and gold equal the "
                    f"registered lane's on every item — if the null condition "
                    f"should change either, it measures no noise floor (an "
                    f"instrument that ignores its labels predicts the same in both "
                    f"lanes; LAB-034 Null condition in the same run)",
                    fix="if the null should differ, give the instrument a null of its "
                    f"own, e.g. its predictions against permuted gold, then "
                    f"{measure_anew(area)}",
                    evidence_kind=STATIC_EVIDENCE,
                    rule=cited_rule("LAB-034 Null condition in the same run"),
                )
            )
    return NullLanes(out, examined)


def criterion_ns(metrics: Mapping[str, object]) -> dict[str, int]:
    """The criterion denominators of METRICS, a run's metrics.json: every
    `criterion_<i>_n` key that holds an integer — a bool is no count."""
    return {
        k: v
        for k, v in metrics.items()
        if CRITERION_N.match(k) and isinstance(v, int) and not isinstance(v, bool)
    }


def criterion_n_input_mismatches(
    ns: Mapping[str, int],
    inputs: Sequence[DataEntry],
    outputs: Sequence[OutputEntry],
) -> list[GateFinding]:
    """A static-evidence WARNING per criterion denominator of NS
    (`criterion_ns`) that matches no input count the run recorded — the rows
    of its INPUTS (`data=`) and the lines of its OUTPUTS: the size of what
    was counted, not a promised constant (that is
    `intent_check.promised_constant_mismatches`). One WARNING when NS holds
    denominators and the run recorded no count at all; [] when NS is empty
    or every denominator matches. A warning, never a blocker, until its
    false alarm rate is known; the rule is not decided yet (OPEN_RULE)."""
    if not ns:
        return []
    counts: dict[str, int] = {}
    for d in inputs:
        if d.rows is not None:
            counts[f"data[{d.key}].rows"] = d.rows
    for o in outputs:
        if o.lines is not None:
            counts[f"{o.path.name} lines"] = o.lines
    if not counts:
        return [
            _criterion_n_warning(
                f"{', '.join(sorted(ns))} present, but the run recorded no input "
                f"count (no data= rows, no output lines) to hold them to"
            )
        ]
    return [
        _criterion_n_warning(
            f"{k} = {n} matches no recorded count "
            f"({', '.join(f'{a} = {b}' for a, b in sorted(counts.items()))}) — "
            f"a denominator that is not the input is the audits' most "
            f"frequent real finding"
        )
        for k, n in sorted(ns.items())
        if n not in counts.values()
    ]


def _criterion_n_warning(text: str) -> GateFinding:
    """The static-evidence WARNING `criterion_n_input_mismatches` gives."""
    return GateFinding(WARNING, text, rule=OPEN_RULE, evidence_kind=STATIC_EVIDENCE)


def provenance_findings(
    area: Path, answering_run: Path
) -> tuple[list[GateFinding], list[str], list[str]]:
    """(blockers, warnings, outside) for a run at low repeat cost: every
    source the run read is frozen in its record (`data=`), its bytes now
    are the ones the record's sha256 names, and in the repository git
    holds it — tracked, or kept outside on purpose by an ignore rule; a
    source that lies outside the repository is held by its checksum alone
    (`source_finding`, the standard's Fixed inputs: large or protected
    data stay out of the repository, which holds their source or access
    route and version in Data / scope). OUTSIDE names each source kept out
    of git, by an ignore rule or by lying outside the repository, and a
    run's declaration that it reads no input file (`runs.NO_INPUTS_KEY`). Raises GitError when git cannot list a directory source's tracked
    files or say which are ignored (`repo.ignoring_rules`): finalize then ends
    in that error, not in a blocker with a way out that may not lead out.
    A `data=` entry naming no path blocks. Outside a git repository every
    source is still held to its record; git's half is skipped with a
    warning."""
    sources, blockers = _recorded_sources(area, answering_run)
    warnings: list[str] = []
    outside: list[str] = []
    cfg = read_run_config(answering_run)
    if not sources and not blockers and cfg is not None:
        outside.append(
            "the run declares it reads no input file (data=runlog.NO_INPUTS) — "
            "the author's word; the script is not checked for it"
        )
    registered = read_outputs(answering_run)
    outputs: list[Path] = [o.path for o in registered or []]
    if registered is None:
        warnings.append(
            "no outputs.json — the run registered no output file (run.output)"
        )
    repo = git_root(area)
    # outside a repository the bytes are still held to the record; only
    # git's half (tracked or ignored) and the outputs' tracking are skipped
    for f, sha in sources:
        found, note = source_finding(source_now(repo, f, sha), area)
        if found is not None:
            blockers.append(found)
        if note is not None:
            outside.append(note)
    if repo is None:
        warnings.append(
            "not a git repository — cannot tell whether source and output are committed"
        )
        return blockers, warnings, outside
    # The output rows are born after the run, so on every first pass they are
    # untracked by construction: a warning that names the command, not a
    # blocker that sends the agent round the loop.
    # An output that is gone is `output_record_findings`' blocker, on every lane.
    for f in outputs:
        if path_kind(f) is not None and not tracked(repo, f):
            warnings.append(
                f"output {f.name} is not yet tracked — `git add {f}` before "
                f"the commit that cites the number"
            )
    return blockers, warnings, outside


def _recorded_sources(
    area: Path, answering_run: Path
) -> tuple[list[tuple[Path, str]], list[GateFinding]]:
    """(sources, blockers): each `data=` source of ANSWERING_RUN's record as
    (path, recorded sha256), read by `runs.read_data`; a blocker when the
    record holds no `data=` or an entry does not read (no path, no sha256:
    its sentence). Reads the record, writes nothing."""
    try:
        entries = read_data(answering_run) or []
    except ArtefactError as exc:
        return [], [
            blocker(
                str(exc),
                fix="pass every source in `data=` to runlog.run, then "
                f"{measure_anew(area)}",
                rule=OPEN_RULE,
            )
        ]
    if not entries:
        cfg = read_run_config(answering_run)
        if cfg is not None and declares_no_inputs(
            cfg.data, str(answering_run / CONFIG_FILE)
        ):
            return [], []  # the author declared no input file (`provenance_findings`)
        return [], [
            blocker(
                "source not frozen — the run carries no `data=`",
                fix="pass data={name: path} to runlog.run so sha and rows are "
                f"recorded, or data=runlog.NO_INPUTS for a run that reads no "
                f"input file, then {measure_anew(area)}",
                rule=OPEN_RULE,
            )
        ]
    return [
        (resolve_recorded(e.recorded, answering_run), e.sha256) for e in entries
    ], []


@dataclass(frozen=True)
class SourceNow:
    """What the tree and git say now of one source a run recorded
    (`source_now`) — the facts `source_finding` decides on, so the decision
    opens no file and asks no git.

    Attributes:
        path: The source as the record names it, resolved against the repo.
        sha: The sha256 the run recorded for it (cut as recorded).
        kind: "file", "dir" or None when nothing stands at PATH
            (`repo.path_kind`).
        beyond: The source resolves outside the repository: git can neither
            track nor ignore it.
        loose: Its files git neither tracks nor ignores by a rule.
        untracked: Some file of it is untracked, ignored ones included.
        ignore_rules: The rules that keep its untracked files out, sorted.
        drift: Why its bytes are not the recorded ones (`source_drift`),
            None when they are — and None unread when it is gone or LOOSE
            decides first: a large source is not hashed for nothing.
    """

    path: Path
    sha: str
    kind: str | None
    beyond: bool = False
    loose: tuple[Path, ...] = ()
    untracked: bool = False
    ignore_rules: tuple[str, ...] = ()
    drift: str | None = None


def source_now(repo: Path | None, source: Path, sha: str) -> SourceNow:
    """What the tree and git REPO (None: no repository, git's half
    skipped) say now of SOURCE, recorded with SHA (`SourceNow`): its kind,
    whether it lies outside REPO, its untracked files and the ignore rules
    that keep them out, and — only when nothing decided before — whether
    its bytes drifted. Reads SOURCE and asks git; raises GitError as
    `_untracked_files` and `repo.ignoring_rules` do."""
    kind = path_kind(source)
    if kind is None:
        return SourceNow(source, sha, None)
    # git's half only for bytes that lie in the repository: one outside it
    # (a model directory on scratch, reached directly or by a link) git can
    # neither track nor ignore, so a refusal naming either as the way out
    # would not lead out
    beyond = repo is not None and not resolves_under(repo, source)
    # a directory: file by file; ignored files are among the untracked
    untracked = [] if repo is None or beyond else _untracked_files(repo, source)
    rules = {} if repo is None else ignoring_rules(repo, untracked)
    loose = tuple(f for f in untracked if own_path(f) not in rules)
    return SourceNow(
        source,
        sha,
        kind,
        beyond=beyond,
        loose=loose,
        untracked=bool(untracked),
        ignore_rules=tuple(sorted(set(rules.values()))),
        drift=None if loose else source_drift(source, sha),
    )


def source_finding(
    source: SourceNow, area: Path
) -> tuple[GateFinding | None, str | None]:
    """(blocker, outside note) for one SOURCE of a run of AREA, as
    `source_now` read it. The record is the one integrity evidence, git
    status a hygiene rule beside it (docs/notes/2026-11-06-pin-route.md).
    In this order: gone (`_gone`); a file neither tracked nor ignored by a
    rule (`_untracked_source`), even when the bytes match; bytes unlike the
    record — tracked, ignored or outside the repository alike. Otherwise
    no blocker, and the note for a source kept outside git: lying outside
    the repository (its resolved path), where git can neither track nor
    ignore it — held by the checksum alone, its source or access route
    owed in Data / scope —, or the ignore rule that keeps it out. The rule
    is not decided yet (OPEN_RULE)."""
    if source.kind is None:
        return _gone(source.path, area), None
    if source.loose:
        return _untracked_source(source), None
    if source.drift is not None:
        return (
            blocker(
                f"source {source.path} is not the bytes the run read: "
                f"{source.drift}, the run recorded sha256 {source.sha}",
                fix="restore the bytes the run read (from git where it tracks them, "
                "else from the source or access route Data / scope names), or "
                f"{measure_anew(area)}",
                rule=OPEN_RULE,
            ),
            None,
        )
    if source.beyond:
        return None, (
            f"source {source.path} lies outside the repository "
            f"({source.path.resolve()}), pinned by the checksum the run recorded "
            f"(sha256 {source.sha}); its source or access route and version "
            f"belong in Data / scope"
        )
    if not source.untracked:
        return None, None
    return None, (
        f"source {source.path} is kept outside git by an ignore rule "
        f"({'; '.join(source.ignore_rules)}), pinned by the checksum the run "
        f"recorded (sha256 {source.sha})"
    )


def source_drift(source: Path, sha: str) -> str | None:
    """Why SOURCE's bytes are not the ones a run recorded as SHA, None when
    they are: `provenance.source_digest`, the digest runlog records, cut to
    SHA's length. Reads SOURCE, writes nothing."""
    now = source_digest(source)[: len(sha)]
    return None if now == sha else f"its sha256 is now {now}"


#: the command that ends an area without a number while finalize stays
#: blocked — the handover as the stamped AGENTS.md gives it (a test holds
#: the two together); its <…> parts are the agent's to fill
HANDOVER_COMMAND = handover_command(None).line


#: how many untracked files under a directory source its blocker names
NAMED_UNTRACKED = 3


def _untracked_files(repo: Path, source: Path) -> list[Path]:
    """The files of SOURCE that git does not track in REPO — ignored ones
    included, `repo.ignoring_rules` tells them apart —, [] when it tracks them
    all: SOURCE itself for a file; for a directory each visible file
    under it (`provenance.visible_files`) — the files the run's digest and
    row count covered, since the record keeps no list of them. A directory
    is tracked only when every one of them is: `git ls-files --error-unmatch
    DIR` succeeds once one file under it is (a committed SOURCE.md would
    pass the untracked data files beside it). An empty or all-hidden
    directory passes — the run read no file of it. A symbolic link under it
    counts as tracked when git holds the link, not its target's content.
    The directory is resolved first and lies in REPO (`_source_finding`
    passes one outside it over). Raises GitError when git fails."""
    if path_kind(source) != "dir":
        return [] if tracked(repo, source) else [source]
    base = source.resolve()
    files = visible_files(base)
    # both sides resolved: git lists paths under REPO (git_root resolves it)
    # and BASE is resolved, so a file is the same Path in either set
    held = tracked_under(repo, base)
    return [f for f in files if f not in held]


def _untracked_source(source: SourceNow) -> GateFinding:
    """The blocker `source_finding` gives for a SOURCE of the run whose
    files `loose` git neither tracks nor ignores by a rule (at repeat cost
    low), however well their bytes match the checksum (`sha`) the run
    recorded: whether data belong to the versioned project is git's to
    say. The way out is the two routes the standard's Fixed inputs names:
    a small input that may legally be shared is committed; large or
    protected data are kept outside git on purpose, by an ignore rule, with
    their source or access route and version in Data / scope — finalize
    then holds them to it. A directory names its loose files
    (`NAMED_UNTRACKED` of them), and its commit lists each of them, so no
    file the run did not read goes in."""
    loose, sha = source.loose, source.sha
    what = f"source {source.path} is neither tracked in git nor ignored by a rule"
    if source.kind == "dir":
        names = ", ".join(shown(f, source.path) for f in loose[:NAMED_UNTRACKED])
        more = ", …" if len(loose) > NAMED_UNTRACKED else ""
        what += f": {len(loose)} file(s) under it ({names}{more})"
        add = "git add -- " + " ".join(shlex.quote(str(f)) for f in loose)
    else:
        add = f"git add {shlex.quote(str(source.path))}"
    return blocker(
        f"{what} — whether it belongs to the project is left open",
        fix=f"if it is small and may legally be shared, commit it (`{add}`); "
        f"large or protected data stay out of git on purpose: an ignore rule for "
        f"it (a `.gitignore` or `.git/info/exclude`) and its source or access "
        f"route and version in the protocol's Data / scope — finalize then holds "
        f"it to the checksum this run recorded, `sha256 {sha}`",
        rule=OPEN_RULE,
    )


def output_drift(output: OutputNow) -> str | None:
    """Why the file of a registered OUTPUT is not the one the run recorded
    in outputs.json, or None when it is: the file is gone, the run ended
    without it (no sha256 recorded), or its sha256 now differs from the
    record. The record is the run's, taken after the run
    (`runlog.Run._finalize`); the tree at check time is only compared,
    never trusted."""
    recorded = output.entry.sha256
    if output.sha256 is None:
        return "the file is gone"
    if recorded is None:
        return "the run ended without it (outputs.json records no sha256)"
    if not output.sha256.startswith(recorded):
        return (
            f"its sha256 {output.sha256[: len(recorded)]} is not the recorded "
            f"{recorded}"
        )
    return None


def output_record_findings(
    outputs: Sequence[OutputNow], run_id: str, area: Path
) -> list[GateFinding]:
    """A blocker per registered output of the run RUN_ID of AREA whose file
    is not the one the run recorded (`output_drift`, OUTPUTS as
    `runs.outputs_now` gives them): the number's rows, and a deliverable
    the run wrote for an external task, are pinned to the run by path and
    sha256 — a file swapped, edited or removed after the run is no longer
    what the run produced. [] when every file is as recorded."""
    return [
        blocker(
            f"{o.entry.path}: not the file run {run_id} recorded — {why}",
            fix=measure_anew(area),
            rule=OPEN_RULE,
        )
        for o in outputs
        if (why := output_drift(o)) is not None
    ]


def _gone(f: Path, area: Path) -> GateFinding:
    """A source file of AREA's run is gone: its rows cannot be re-derived.
    The way back names both homes a source has: git where it tracks it, the
    route Data / scope gives where an ignore rule keeps it outside."""
    return blocker(
        f"{f} is not at its recorded path on this machine — deleted, moved or "
        f"held elsewhere; the run's rows cannot be re-derived here",
        fix=f"restore it (`{checkout_command(f)}` where git "
        f"holds it; else get it again from the source or access route Data / "
        f"scope names), or {measure_anew(area)}",
        rule=OPEN_RULE,
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
    far the number moves. A warning, never a blocker: whether a spread is owed is the protocol's.
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
    not under `model`/`*_model`, the keys runlog resolves (one recorded as
    `judge` is not resolved). Static evidence:
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
    note (a Store without `prov`), not proof of anything. Rows
    of a continued run whose script differs from this run's are a blocker
    too (`_continued_with_other_code`): the number is that code's. A
    broken lineage (`runs.lineage`) is the one blocker: without
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
                rule=OPEN_RULE,
            )
        ], []
    for entry in read_outputs(answering_run) or []:
        if entry.path.suffix != ".jsonl" or output_file(entry) is None:
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
    # every blocker of the row check carries one rule, not decided yet
    return [replace(b, rule=OPEN_RULE) for b in blockers], notes


def _continued_with_other_code(
    answering_run: Path, path: Path, rows: dict[str, int], continued: tuple[str, ...]
) -> list[GateFinding]:
    """A blocker per run ANSWERING_RUN continues in PATH whose recorded
    script (`script_sha`) is not the answering run's, where the rows declare
    that they depend on code (`_instrument` carries `code_sha`, the
    estimator skeleton's): its ROWS were written by other code, and the
    number counts them as this run's: a fix measured again into the faulty
    run's file keeps every faulty row. Rows without it — a model's answers — do not
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
    the protocol gets instead of opening the register. No arms, no `[model]`, or a
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
        if path_kind(root / a.profile) != "file":
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
            f"before the first measurement — after it, "
            + register_anew(per="per change, the [kept] among them", kind="compute"),
            rule=OPEN_RULE,
        )
    ]
