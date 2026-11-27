"""run_code_check — the code behind a finished run's number, held to the code now.

The script and the modules it imports of the answering run and of each run
it derives from, compared with the code here now (`code_since_run`): a
blocker where it differs or cannot be compared, a warning where it is not
compared. A derived run that declares its answer reading is held to its
parent's prompts and answers too (`answer_reading_gaps`). Where a run's
script is found (`script_of`, `script_as_run`). Read-only; only the
warnings of `code_since_run` are plain sentences, graded by the finalize
station that takes them.
"""

from __future__ import annotations

import shlex
from dataclasses import replace
from pathlib import Path

from labkit.formats.answer_reading import (
    ANSWER_READING_FILE,
    AnswerReading,
    read_answer_reading,
)
from labkit.formats.commands import checkout_command, gate_command, measure_anew
from labkit.formats.gate import (
    LAB_010,
    LAB_041,
    LAB_067,
    TECHNICAL_RULE,
    GateFinding,
    blocker,
    outcome_of_failed_read,
)
from labkit.formats.repo import (
    GitError,
    blobs_now,
    blobs_then,
    commit_known,
    git_root,
    shown,
)
from labkit.formats.runs import (
    COMPLETED,
    MEASUREMENT,
    NO_GIT,
    NO_SCRIPT,
    PATCH_CONTRADICTION_WAY,
    ArtefactError,
    OutputEntry,
    RunConfig,
    RunConfigError,
    RunDir,
    completion_state,
    kept_script,
    lineage,
    patch_contradicts_record,
    patch_lost,
    patch_path,
    patch_text,
    read_outputs,
    read_run_config,
    script_copy_path,
    script_digest,
    untracked_copy_differs,
    untracked_copy_path,
)
from labkit.formats.scope_sha import (
    SourceError,
    measured_code,
    script_candidates,
    scripts_named,
)


#: the way out of a code change since the run, the fix first: restoring the
#: old code removes the difference, not a fault the change corrected
FIX_FIRST = (
    "measure anew with the code as it is now and audit that run; only when the "
    "change was not meant, restore it as it ran"
)


def code_since_run(
    area: Path, answering_run: Path
) -> tuple[list[GateFinding], list[str]]:
    """(blockers, warnings): compare the code each run behind ANSWERING_RUN's
    number ran with the code here now — a blocker where it differs or
    cannot be compared, a warning where it is not compared. For the run and each
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
    the command that restores the code as it ran; on a run whose record
    allows it as the parent of a corrected evaluation
    (`_could_be_corrected`: a completed measurement, no repeat, with an
    output — not whether the change lies in the evaluation), and beside a
    derived run that declared none, also that correction, with its
    condition: only the evaluation changed. A
    blocker that found a
    difference names its run as data (`GateFinding.changed_since`); one
    that could not compare (no script or commit recorded, a commit this
    clone lacks, a helper uncommitted then, a script gone or ambiguous,
    a patch gone, changes in a patch beside a record of a clean tree)
    names none. Read-only. An extraction exception of the test model
    (docs/notes/2026-11-10-test-model.md): every condition here is an answer
    of git or of the run's kept copies, so the comparison stays one boundary,
    tested against real repositories (`tests/test_run_code.py`).

    How much of a parent's code is compared depends on its child's
    `answer-reading.json` (`answer_reading`):

    - missing (no declaration, a file deleted, a run of an older labkit):
      the parent's script and helpers whole, as before; a difference
      there names the declaration as a way out beside measuring anew;
    - present but not readable: a blocker naming the file, and the parent
      compared whole as well;
    - present: the declared module and the repo-local modules it imports
      (`scope_sha.measured_code` of the module), which must still be among
      the modules the child's script imports — the evaluation may have
      changed since the parent ran, the reading of an answer may not.

    The declaration narrows this comparison for every caller (finalize,
    recheck, the registration hold, the adoption). Only finalize, and
    report-check through it, also holds the prompts field and the answer
    file to the parent's (`answer_reading_gaps`)."""
    try:
        chain = lineage(answering_run)
    except ValueError as exc:
        return [
            blocker(
                f"{answering_run.name}: its runs cannot be followed ({exc})",
                fix=measure_anew(answering_run.parent.parent),
                rule=TECHNICAL_RULE,
            )
        ], []
    blockers: list[GateFinding] = []
    warnings: list[str] = []
    # whether CHILD — the run of the previous pass — had its own code
    # compared there (`_run_code`), which tells a script it cannot compare
    script_told = False
    # each run after the first is the parent of the one before it: the
    # child's declaration decides how much of the parent's code is compared
    for child, run in zip([None, *chain], chain):
        declared: AnswerReading | None = None
        if child is not None:
            try:
                declared = read_answer_reading(child)
            except ArtefactError as exc:
                blockers.append(
                    blocker(
                        f"{child.name}: {exc}",
                        fix=f"restore {ANSWER_READING_FILE} as runlog wrote it "
                        f"(`{checkout_command(child / ANSWER_READING_FILE)}` where "
                        f"git holds it), or {measure_anew(area)}",
                        stated_outcome=outcome_of_failed_read(exc),
                        rule=TECHNICAL_RULE,
                    )
                )
        if child is not None and declared is not None:
            b, w = _reading_since_run(
                area, run, child, declared, script_told=script_told
            )
            script_told = False
        else:
            b, w = _run_code(area, run)
            script_told = True
            # the correction is offered where it could be taken: beside a
            # derived run that declared none, and on a run that could be
            # its parent before any derived run exists
            if child is not None or _could_be_corrected(run):
                b = [_or_declared(f, run.name) for f in b]
        blockers += b
        warnings += w
    return blockers, warnings


def answer_reading_gaps(
    parent: str,
    child: str,
    prompts: tuple[str | None, str | None],
    outputs: tuple[list[OutputEntry], list[OutputEntry]],
    anew: str,
) -> list[GateFinding]:
    """The BLOCKERs on CHILD, a derived run that declares its answer
    reading, against its PARENT, beyond the code (`code_since_run`): the
    prompts (PROMPTS: the field "Prompt (verbatim, per variant)" as the
    parent's protocol text held it and as the child's does, None where a
    text has none) equal, since a prompt changed after the parent ran
    changes what was measured; and the answers (OUTPUTS, the parent's and
    the child's registered outputs): every file both registered with the
    same sha256 in both records, and at least one such file, since a
    derived run re-reads its parent's output. ANEW is the way out that
    measures anew (`commands.measure_anew`). Empty when both hold. Pure."""
    found: list[GateFinding] = []
    if prompts[0] != prompts[1]:
        found.append(
            blocker(
                f"{child} re-reads the answers of {parent}, but the prompts "
                f"field differs from the text {parent} was measured under — the "
                f"answers were asked with other prompts, and new prompts are a new "
                f"measurement",
                fix=anew,
                rule=LAB_067,
            )
        )
    parent_out, child_out = ({o.path: o.sha256 for o in out} for out in outputs)
    shared = sorted(set(parent_out) & set(child_out))
    if not shared:
        found.append(
            blocker(
                f"{child} registered none of the files {parent} registered as its "
                f"output — a derived run re-reads its parent's answers",
                fix=f"register the answer file {parent} wrote in the derived run "
                f"(`r.output(...)`), or {anew}",
                rule=LAB_041,
            )
        )
    for path in shared:
        if parent_out[path] != child_out[path]:
            found.append(
                blocker(
                    f"{path.name}: {parent} registered sha256 {parent_out[path]}, "
                    f"{child} {child_out[path]} — the answers changed after "
                    f"{parent} ran",
                    fix=f"restore the file as {parent} registered it "
                    f"(`git log -- {path.name}` names its commits), or {anew}",
                    rule=LAB_041,
                )
            )
    return found


def _could_be_corrected(run: Path) -> bool:
    """Whether RUN meets what a derived run that declares its answer reading
    asks of its parent, as far as its record tells: a completed measurement,
    no repeat, with a registered output (docs/workflow.md, 'Correcting the
    evaluation of unchanged answers'). Whether only the evaluation changed
    is not told here: the way out says when it applies, and the derived
    run's own checks hold it. False for a record that does not read (the
    answering-run station names it)."""
    try:
        if completion_state(run) != COMPLETED:
            return False
        cfg = read_run_config(run)
    except RunConfigError:
        return False
    return (
        cfg is not None
        and cfg.run_kind == MEASUREMENT
        and cfg.repeat_of is None
        and bool(read_outputs(run))
    )


def _or_declared(found: GateFinding, parent: str) -> GateFinding:
    """FOUND, a difference in the code PARENT ran, found for a derived run
    that declared no answer reading, with that declaration as a way out
    after measuring anew: when only the evaluation changed, a derived run
    that declares the module reading an answer is compared there only.
    Only a finding whose `changed_since` is PARENT gains it; any other —
    one that could not compare, or a difference in another run — is
    returned as it is."""
    if found.changed_since != parent:
        return found
    return replace(
        found,
        fix=f"{found.fix}; or, when only the evaluation changed — the prompts, the "
        f"answer file and the module that reads an answer as {parent} had them —, "
        f"derive a run from {parent} that declares that module "
        f"(`runlog.run(..., derived_from={parent!r}, answer_reading=MODULE)`): "
        f"its parent is compared in that module only (`labkit-next --guide`, step "
        f"4; the procedure: docs/workflow.md in the labkit repository, "
        f"'Correcting the evaluation of unchanged answers')",
    )


def _reading_since_run(
    area: Path,
    parent: Path,
    child: Path,
    declared: AnswerReading,
    *,
    script_told: bool,
) -> tuple[list[GateFinding], list[str]]:
    """`code_since_run` for PARENT where CHILD declared its answer reading
    DECLARED: the declared module and the repo-local modules it imports,
    as they are now, against PARENT's tree (`_helpers_since_run`); a
    blocker when the area lies in no git repository, the module is no
    longer imported by CHILD's script, or its code cannot be read (gone
    included: `measured_code`'s SourceError). CHILD's script not found (gone
    or ambiguous) is a blocker here only when SCRIPT_TOLD is False: where
    CHILD's own comparison ran (`_run_code`), that one tells why the script
    cannot be compared — gone or ambiguous, with the restore in its way
    out, or none recorded — one cause, one finding."""
    cfg, child_cfg = read_run_config(parent), read_run_config(child)
    if cfg is None or child_cfg is None:
        return [], []  # the answering-run station names an unreadable record
    repo = git_root(area)
    named = f"the answer reading {declared.module} that {child.name} declared"
    if repo is None:
        return [
            blocker(
                f"{named} cannot be compared with what {parent.name} ran: the "
                f"area lies in no git repository now",
                fix=measure_anew(area),
                rule=TECHNICAL_RULE,
            )
        ], []
    module = repo / declared.module
    script = script_of(area, child_cfg)
    if isinstance(script, str):
        if script_told:
            return [], []
        return [
            blocker(
                f"{child.name}: {script}", fix=measure_anew(area), rule=TECHNICAL_RULE
            )
        ], []
    try:
        reading = measured_code(module, repo)
        imported = {f.resolve() for f in measured_code(script, repo)}
    except SourceError as exc:
        return [
            blocker(
                f"{named} cannot be read now: {exc}",
                fix=f"repair what the error names, then `{gate_command('finalize', area)}`",
                stated_outcome=outcome_of_failed_read(exc),
                rule=TECHNICAL_RULE,
            )
        ], []
    if module.resolve() not in imported:
        return [
            blocker(
                f"{named}: {shown(script, Path.cwd())} no longer imports it, so it "
                f"is not what reads the answers",
                fix=measure_anew(area),
                rule=TECHNICAL_RULE,
            )
        ], []
    # the untracked siblings a run copied lie beside its script: the module's
    # neighbours are named from the declaring run's script, as runlog saw them
    return _helpers_since_run(reading, script, repo, parent, cfg)


def _run_code(area: Path, run: Path) -> tuple[list[GateFinding], list[str]]:
    """`code_since_run` for one RUN, its own record only."""
    cfg = read_run_config(run)
    if cfg is None:
        return [], []  # the answering-run station names an unreadable record
    rid, here = run.name, Path.cwd()
    if cfg.script_sha == NO_SCRIPT:
        return [
            blocker(
                f"{rid} recorded no script — the code behind its number cannot be compared",
                fix=measure_anew(area),
                rule=TECHNICAL_RULE,
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
                rule=TECHNICAL_RULE,
            )
        ], []
    out: list[GateFinding] = []
    if script_digest(script) != cfg.script_sha:
        out.append(
            replace(
                blocker(
                    f"{shown(script, here)} changed since {rid} ran it — its number "
                    f"came from other code",
                    fix=f"{FIX_FIRST} (`cp {shlex.quote(shown(kept, here))} "
                    f"{shlex.quote(shown(script, here))}`)",
                    rule=LAB_041,
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
                stated_outcome=outcome_of_failed_read(exc),
                rule=TECHNICAL_RULE,
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
    if cfg.script_sha == NO_SCRIPT:
        return None, f"run {run.name} recorded no script"
    script = script_of(area, cfg)
    if isinstance(script, Path) and script_digest(script) == cfg.script_sha:
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
    """(blockers, warnings) for HELPERS, the modules SCRIPT imports, in
    this order:

    1. a helper the run kept a copy of (untracked then) against that copy;
       a helper in another repository is a warning, not compared;
    2. the rest, the helpers in git, only when the tree the run started
       from is known — else one blocker for all and the comparison ends:
       no commit recorded or the area in no repository (LAB-010 Commit
       before the run, when the run started outside git); the run's patch gone after a changed tree
       (`runs.patch_lost`); a patch with content beside a record of a clean
       tree (`runs.patch_contradicts_record`); a commit this clone lacks;
       that tree unreadable;
    3. each helper in git against that tree: one not in it (untracked then)
       or changed since blocks.

    The early blockers repeat the conditions of `runs.start_point` and
    keep their own sentences, since the first of them picks its rule."""
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
                            rule=LAB_041,
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
    no_commit = not cfg.git_full or cfg.git_full == NO_GIT
    if repo is None or no_commit:
        # each cause that holds is named, and no other
        causes: list[str] = []
        if no_commit:
            causes.append(f"{rid} recorded no commit")
        if repo is None:
            causes.append("the area lies in no git repository now")
        why = (
            f"{' and '.join(causes)}, so the helpers its script imports "
            f"({names}) cannot be compared"
        )
        fix = f"in the repository, {measure_anew(run_dir.parent.parent)}"
        # NO_GIT is the run's own word that it started outside the history;
        # every other cause only leaves the comparison without its basis
        if repo is not None and cfg.git == NO_GIT:
            return [*out, blocker(why, fix=fix, rule=LAB_010)], warnings
        return [*out, blocker(why, fix=fix, rule=TECHNICAL_RULE)], warnings
    rd = RunDir(run_dir, cfg, None)
    if patch_lost(rd):
        return [
            *out,
            blocker(
                f"{rid} started from a tree with changes ({cfg.git}), and its "
                f"uncommitted.patch is gone: the commit alone is not what it "
                f"started from, so the helpers its script imports ({names}) "
                f"cannot be compared",
                fix=f"restore {shown(patch_path(run_dir), here)} from git or a "
                f"backup, or {measure_anew(run_dir.parent.parent)}",
                rule=TECHNICAL_RULE,
            ),
        ], warnings
    contradiction = patch_contradicts_record(rd)
    if contradiction is not None:
        return [
            *out,
            blocker(
                f"{rid} {contradiction}, so the helpers its script imports "
                f"({names}) cannot be compared",
                fix=f"{PATCH_CONTRADICTION_WAY}: {measure_anew(run_dir.parent.parent)}",
                rule=TECHNICAL_RULE,
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
                rule=TECHNICAL_RULE,
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
                rule=TECHNICAL_RULE,
            ),
        ], warnings
    for f in in_git:
        if then[f] is None:
            out.append(
                blocker(
                    f"{shown(f, here)} is in neither {rid}'s commit nor its "
                    f"uncommitted.patch, so it cannot be compared with what the "
                    f"run imported — untracked when the run started, or not yet "
                    f"there: the record does not say which, nor whether the run "
                    f"used it",
                    fix=f"commit {shown(f, here)}, then {measure_anew(run_dir.parent.parent)}",
                    rule=TECHNICAL_RULE,
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
                        rule=LAB_041,
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
