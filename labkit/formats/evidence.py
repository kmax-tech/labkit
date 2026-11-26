"""evidence — what an area's committed evidence may become, and the changes
against a commit that break it.

An area's evidence is what labkit wrote under `audits/`, `runs/` and
`run-starts/`. Once a
commit holds it, it stays as written:

    audits/<record>.toml   only its findings' decision lines change —
                           `status`, `reason`, `effect`, which `labkit-audit
                           --decide` writes (`audit_records.without_decisions`) —
                           and their replaced decisions are only added to:
                           a committed entry stays, a committed decision
                           that was replaced is kept as the next entry
                           (`decision_history.history_kept`)
    audits/report-reviews/<review>.toml
                           only its claims' decision lines change
                           (`report_reviews.without_claim_decisions`); one of
                           the format without decisions may move, unchanged,
                           into `report-reviews/superseded/`
                           (`report_reviews.is_undecided_format`)
    audits/attempts.jsonl  appended to, never cut — `attempts` holds it,
                           against HEAD and against its copy in the git
                           directory; this module leaves it out
    audits/ otherwise      never changes: a failed attempt, a review, a kept
                           answer, a handover record
    runs/<run_id>/         never changes or goes once the commit holds the
                           run closed — `completion.json` or `failure.json`
                           in it; a run still open there is runlog's to write
    run-starts/<run_id>.json
                           never changes or goes once a commit holds it: the
                           run's start file, written once at its start
                           (`run_starts`)

Three witnesses, each git's own and exact for what it saw:

    `changes`         the tree (the stop, the post-change hook, `--findings`,
                      report-check, labkit-next) or the index (the commit)
                      against HEAD — and a file
                      git ignores (`ignored`), evidence no commit can carry
    `commit_changes`  each commit since the session began against its first
                      parent: a commit past the pre-commit (`--no-verify`)
                      that rewrote a record (the stop)
    `orphaned_runs`   a closed run in a commit HEAD's reflog held since the
                      session began and HEAD no longer holds: a reset, an
                      amend or a rebase that left it behind (the stop)

Every change found is undone from git, and its way out names the commit
to restore from — so a handover does not acknowledge it: the handover
binds `audits/` as it stands (`undecided.undecided_state`).

Limits: a record or a run no commit ever held has no witness here (the
attempt journal's copy covers the audit attempts); the session's
witnesses end where git's do — a reflog expired or switched off, a commit
made outside a session, a history rewritten before it began. A shortcut
or a slip is caught; an agent that also rewrites git's own records is not.
Why: docs/notes/2026-10-28-evidence-changes.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import shlex
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path

from labkit.formats.commands import checkout_command
from labkit.formats import (
    decision_history,
    findings,
    audit_records,
    handovers,
    report_reviews,
    reviews,
)
from labkit.formats.attempts import evidence_gaps
from labkit.formats.findings import JOURNAL
from labkit.formats.gate import OPEN_RULE, TECHNICAL_RULE
from labkit.formats.gate import (
    NOT_EXECUTABLE,
    GateFinding,
    blocker,
    with_way_out,
)
from labkit.formats.repo import (
    rel_posix,
    GitError,
    UNREAD_OBJECTS_WAY,
    blobs_now,
    files_at,
    git_root,
    git_run,
    head_sha,
    is_ancestor,
    state_text,
    text_at,
)
from labkit.formats.area_state import HistoryUnread, marked_runs
from labkit.formats.commands import audit_command, stage_command
from labkit.formats.run_starts import (
    START_FILES_DIR,
    START_MARK,
    is_start_file,
    start_path,
)
from labkit.formats.runs import (
    COMPLETION_FILE,
    CONFIG_FILE,
    FAILURE_FILE,
    METRICS_FILE,
    OUTPUTS_FILE,
    RUN_ID,
    RUNS_DIR,
    patch_path,
    script_copy_path,
)

#: what git's name-status letter says a path became
_HOW = {"M": "changed", "T": "changed", "D": "deleted"}
#: the files runlog writes directly in a run's folder — the ones `ignored`
#: holds; a raw file (`save_raw`) may carry any name and is left to the lab
RUN_RECORD_FILES = (
    CONFIG_FILE,
    METRICS_FILE,
    OUTPUTS_FILE,
    COMPLETION_FILE,
    FAILURE_FILE,
    patch_path(Path()).name,
    START_MARK,
)
_SCRIPT_COPY = script_copy_path(Path(), "").stem
#: how `broken` names a run's start file among its findings
START_FILE = "start file"
#: how `broken` names a record whose lines stand but which lost a decision
#: the earlier state holds (`decision_lost`)
DECISION_LOST = "record decision lost"
#: the suffixes of the files labkit writes under `audits/` (records,
#: reviews, failed attempts, the journal, kept answers, handover records)
AUDIT_SUFFIXES = (".toml", ".jsonl", ".txt", ".json")


def run_of(rel: str) -> str | None:
    """The run id of REL, a path relative to an area, when it lies in a run's
    folder (`runs/<run_id>/…`); else None."""
    parts = rel.split("/")
    if len(parts) >= 3 and parts[0] == RUNS_DIR and RUN_ID.fullmatch(parts[1]):
        return parts[1]
    return None


def closed_runs(files: Iterable[str]) -> set[str]:
    """The run ids among FILES (paths relative to an area) whose folder holds
    `completion.json` or `failure.json` — closed: runlog writes no more."""
    return {
        run
        for rel in files
        if (run := run_of(rel)) is not None
        and rel.split("/", 2)[2] in (COMPLETION_FILE, FAILURE_FILE)
    }


def record_changed(before: str, after: str) -> bool:
    """Does AFTER, a record's text, differ from BEFORE, the version a commit
    holds, beyond what a decision writes? Yes when a line other than its
    findings' decision lines differs (`audit_records.without_decisions`), or when
    a finding lost a decision BEFORE holds: an entry of its replaced
    decisions changed or gone, or BEFORE's decision replaced without being
    kept (`decision_history.history_kept`). A version whose findings lack
    the decision lines is compared whole. The histories are compared only
    when both versions read as records: one that does not is reported by
    the record's own reader (`audit_records.read`), not here. Pure."""
    stand = other_lines_stand(before, after)
    if stand is None:
        return before != after
    return not stand or decision_lost(before, after)


def other_lines_stand(before: str, after: str) -> bool | None:
    """Do BEFORE and AFTER, two versions of a record, agree in every line
    but their findings' decision lines (`audit_records.without_decisions`)? None
    when the findings of one lack those lines. Pure."""
    kept, now = (
        audit_records.without_decisions(before),
        audit_records.without_decisions(after),
    )
    if kept is None or now is None:
        return None
    return kept == now


def decision_lost(before: str, after: str) -> bool:
    """Did a finding of AFTER, a record's text, lose a decision BEFORE holds?
    True when any finding of AFTER fails `decision_history.history_kept`
    against the same finding of BEFORE. Asked of two versions that differ in
    their findings' decision lines alone; False when one of them does not
    read as a record or they hold different numbers of findings. Pure."""
    committed, standing = (
        audit_records.findings_in(before),
        audit_records.findings_in(after),
    )
    if committed is None or standing is None or len(committed) != len(standing):
        return False
    return not all(
        decision_history.history_kept(was, is_now)
        for was, is_now in zip(committed, standing)
    )


def report_review_changed(before: str, after: str) -> bool:
    """Does AFTER, a report review's text, differ from BEFORE beyond its
    claims' decision lines (`report_reviews.without_claim_decisions`)? A
    version whose claims lack those lines is compared whole. Pure."""
    kept = report_reviews.without_claim_decisions(before)
    now = report_reviews.without_claim_decisions(after)
    if kept is None or now is None:
        return before != after
    return kept != now


def is_report_review(rel: str) -> bool:
    """Is REL, a path relative to an area, a report review's record
    (`audits/report-reviews/<minute>-review[-n].toml`) — not a claim review
    beside it, nothing below the folder? Pure."""
    parts = rel.split("/")
    return (
        len(parts) == 3
        and parts[:2] == [findings.DIR, report_reviews.FOLDER]
        and parts[2].endswith(".toml")
        and not report_reviews.CLAIM_REVIEW_NAME.search(parts[2])
    )


def moved_aside(rel: str, added: set[str], before: str | None) -> bool:
    """Was REL, a deleted path relative to an area, moved into the folder
    of superseded report reviews? Yes when ADDED, the paths the same
    change adds, hold it there (`report_reviews.superseded_name`) and
    BEFORE, its text, is a review of the format without decisions
    (`report_reviews.is_undecided_format`) — the one record that may leave
    its place: this labkit reads no claim of it, so moving it lifts no
    hold. A record that reads stays where it was written. Pure."""
    prefix = f"{findings.DIR}/"
    moved = {
        prefix + name
        for path in added
        if path.startswith(prefix)
        and (name := report_reviews.superseded_name(path[len(prefix) :])) is not None
    }
    return (
        rel in moved
        and before is not None
        and report_reviews.is_undecided_format(before)
    )


def broken(
    entries: list[tuple[str, str]],
    closed: set[str],
    texts: Callable[[str], tuple[str | None, str | None]],
    undone: Callable[[str], bool],
    *,
    deletions: bool,
) -> tuple[list[tuple[str, str]], dict[str, list[tuple[str, str]]]]:
    """Which of ENTRIES — (git's letter, path relative to the area) between
    an earlier and a later state — break their rule: the audit paths as
    (rel, what it is), the journal left out, a deletion only with DELETIONS
    (`attempts.gaps` names one against HEAD); a run's start file changed or
    deleted, among them as (rel, "start file changed" or "start file
    deleted"); and per run CLOSED in the
    earlier state its paths changed or deleted, each as (path in the run's
    folder, how). TEXTS reads a record's two versions (earlier, later): one
    whose decisions alone changed breaks nothing, nor does a report review
    whose claims' decisions alone changed (`report_review_changed`) or one
    moved aside (`moved_aside`). UNDONE tells a later
    version that is back as labkit first committed it (`original`): a
    restore breaks nothing either — but a decision the earlier state holds
    and the later lost (DECISION_LOST) is told whatever the first commit
    held: that commit knows no decision. Pure apart from TEXTS and UNDONE."""
    # a start file lies in run-starts/ and in no run's folder: the loop below
    # passes it over, and `start_file_changes` holds it
    audits = start_file_changes(entries, undone)
    runs: dict[str, list[tuple[str, str]]] = {}
    added = {rel for letter, rel in entries if letter == "A"}
    for letter, rel in entries:
        how = _HOW.get(letter)
        run = run_of(rel)
        if how is None or (run is not None and run not in closed):
            continue
        if run is not None:
            if how == "deleted" or not undone(rel):
                runs.setdefault(run, []).append((rel.split("/", 2)[2], how))
            continue
        if rel.split("/")[0] != findings.DIR or rel == f"{findings.DIR}/{JOURNAL}":
            continue
        if how == "deleted":
            if deletions and not moved_aside(rel, added, texts(rel)[0]):
                audits.append((rel, how))
            continue
        what = _changed_audit_file(rel, texts)
        if what is not None and (what == DECISION_LOST or not undone(rel)):
            audits.append((rel, what))
    return audits, runs


def start_file_changes(
    entries: list[tuple[str, str]], undone: Callable[[str], bool]
) -> list[tuple[str, str]]:
    """The start files among ENTRIES (git's letter, path relative to the
    area) that were changed or deleted, each as (rel, "start file changed"
    or "start file deleted"): written once at the run's start, a start
    file never changes or goes once a commit holds it. A deletion is told
    against every state — no other witness names it —, a change unless the
    file is back as first committed (UNDONE). Pure apart from UNDONE."""
    return [
        (rel, f"{START_FILE} {how}")
        for letter, rel in entries
        if is_start_file(rel)
        and (how := _HOW.get(letter)) is not None
        and (how == "deleted" or not undone(rel))
    ]


def _changed_audit_file(
    rel: str, texts: Callable[[str], tuple[str | None, str | None]]
) -> str | None:
    """What the changed audit file REL (relative to an area) is, for
    `broken`'s sentence — "record" or "report review" when it changed
    beyond its decision lines, DECISION_LOST for a record that changed in
    them alone and lost a decision the earlier version holds, "changed" for
    any other audit file — or None when a record's or a report review's
    decisions alone changed and none was lost (TEXTS reads the two
    versions)."""
    parts = rel.split("/")
    is_record = len(parts) == 2 and findings.is_record_name(parts[1])
    if not is_record and not is_report_review(rel):
        return "changed"
    before, after = texts(rel)
    changed = record_changed if is_record else report_review_changed
    if before and after and not changed(before, after):
        return None
    if not is_record:
        return "report review"
    # the other lines stand and the record changed all the same: a decision was lost
    if before and after and other_lines_stand(before, after):
        return DECISION_LOST
    return "record"


def told(
    area: Path,
    root: Path,
    audits: list[tuple[str, str]],
    runs: dict[str, list[tuple[str, str]]],
    where: str,
    restore: str,
) -> list[tuple[str, str]]:
    """`broken`'s findings in AREA (under ROOT) as (sentence, way out): WHERE
    says between which states ("in the tree since HEAD", "by commit …"),
    RESTORE the commit the way out restores from."""
    base = rel_posix(area, root)

    def checkout(rel: str) -> str:
        return f"`{checkout_command(f'{base}/{rel}', restore)}`"

    out: list[tuple[str, str]] = []
    for rel, what in audits:
        if what == "record":
            out.append(
                (
                    f"{rel}: changed beyond its findings' decision lines {where} — "
                    "an audit record keeps what the auditor wrote; only a "
                    "decision changes it",
                    f"restore it ({checkout(rel)}), then decide with the "
                    f"`--decide` command `{audit_command(area, '--findings')}` prints",
                )
            )
        elif what == DECISION_LOST:
            out.append(
                (
                    f"{rel}: a decision on a finding was lost {where} — a "
                    "decision another one replaces stays in the record "
                    f"(`{decision_history.KEY}`), and an entry a commit holds "
                    "never changes",
                    f"restore it ({checkout(rel)}), then decide with the "
                    f"`--decide` command `{audit_command(area, '--findings')}` prints",
                )
            )
        elif what == "report review":
            out.append(
                (
                    f"{rel}: changed beyond its claims' decision lines {where} — "
                    "a report review keeps what the reader wrote; only a "
                    "decision on a claim changes it",
                    f"restore it ({checkout(rel)}), then decide the claim with "
                    f"`{audit_command(area)} --report-review <REPORT> --decide N "
                    f'false-positive --why "<why>" --record {Path(rel).name}`',
                )
            )
        elif what.startswith(START_FILE):
            out.append(
                (
                    f"{rel}: the {what} {where} — a start file stays as the "
                    "run's start wrote it: it says which protocol the run was "
                    "bound to and when it started, also when the run's directory "
                    "is gone",
                    f"restore it ({checkout(rel)})",
                )
            )
        else:
            out.append(
                (
                    f"{rel}: {what} {where} — labkit writes it once, and a record "
                    "of an audit is evidence",
                    f"restore it ({checkout(rel)})",
                )
            )
    for run, files in runs.items():
        named = ", ".join(f"{name} ({how})" for name, how in files)
        out.append(
            (
                f"{RUNS_DIR}/{run}: the closed run's {named} {where} — "
                "a run's record stays as it ran; a new measurement is a new run",
                f"restore it ({checkout(f'{RUNS_DIR}/{run}')})",
            )
        )
    return out


def _repo_of(area: Path) -> Path | None:
    """The root of the repository AREA lies in, when git takes it — not a
    bare `.git` directory without one (`repo.files_at`'s test) —, else None."""
    root = git_root(area)
    if root is None or git_run(["rev-parse", "--git-dir"], root).returncode != 0:
        return None
    return root


def _specs(area: Path, root: Path) -> list[str]:
    """The pathspecs of AREA's evidence: its `audits/`, its `runs/` and
    its runs' start files (`run_starts.START_FILES_DIR`)."""
    base = rel_posix(area, root)
    return [
        f"{base}/{findings.DIR}",
        f"{base}/{RUNS_DIR}",
        f"{base}/{START_FILES_DIR}",
    ]


def _name_status(text: str) -> list[tuple[str, str]]:
    """(letter, path) of git's `--name-status -z` output with `--no-renames`."""
    parts = text.split("\0")
    return [(parts[i][:1], parts[i + 1]) for i in range(0, len(parts) - 1, 2)]


def _diff(root: Path, args: list[str]) -> list[tuple[str, str]]:
    """git's name-status ARGS under ROOT as (letter, path from ROOT). Raises
    GitError when git fails."""
    r = git_run(args, root)
    if r.returncode != 0:
        raise GitError(f"git {' '.join(args[:2])} in {root}: {r.stderr.strip()}")
    return _name_status(r.stdout)


def _blob_at(root: Path, rev: str, path: str) -> str | None:
    """The blob id REV holds at PATH (from ROOT) — the index for "" —, or
    None where it holds none."""
    r = git_run(["rev-parse", "--verify", "-q", f"{rev}:{path}"], root)
    return r.stdout.strip() if r.returncode == 0 else None


def _blob_now(root: Path, path: str, *, rev: str | None, staged: bool) -> str | None:
    """PATH's blob id in one state: REV's, else the index's when STAGED, else
    the working tree's (`git hash-object`); None where it holds none."""
    if rev is not None or staged:
        return _blob_at(root, rev or "", path)
    file = root / path
    return blobs_now(root, [file])[file] if file.is_file() else None


def _state_diff(
    root: Path, rev: str, specs: list[str], *, staged: bool
) -> list[tuple[str, str]]:
    """(letter, path from ROOT) of SPECS changed in the index (STAGED) or the
    working tree against REV. A file the index dropped (`git rm --cached`)
    reads as deleted to git's tree diff; the tree is what lies on disk, so
    it counts as changed only when its bytes differ. Raises GitError when
    git fails."""
    args = ["diff", "--name-status", "-z", "--no-renames"]
    args += ["--cached", rev] if staged else [rev]
    entries = _diff(root, [*args, "--", *specs])
    if staged:
        return entries
    out: list[tuple[str, str]] = []
    for letter, path in entries:
        if letter == "D" and (root / path).is_file():
            if _blob_now(root, path, rev=None, staged=False) == _blob_at(
                root, rev, path
            ):
                continue
            letter = "M"
        out.append((letter, path))
    return out


def _in_area(entries: list[tuple[str, str]], base: str) -> list[tuple[str, str]]:
    """ENTRIES (paths from the root) under BASE, as paths relative to it."""
    prefix = base + "/"
    return [(letter, p[len(prefix) :]) for letter, p in entries if p.startswith(prefix)]


def _closed_at(root: Path, area: Path, rev: str) -> set[str]:
    """The runs closed in AREA's `runs/` as REV holds it (`closed_runs`)."""
    held = files_at(root, area / RUNS_DIR, rev) or set()
    return closed_runs(f"{RUNS_DIR}/{rel}" for rel in held)


def original(root: Path, area: Path, rel: str) -> str | None:
    """The commit on HEAD's line that holds REL (a path of AREA's evidence)
    as labkit first committed it: for a run's file the oldest commit that
    added the run's `completion.json` or `failure.json` — the run closed —,
    for an audit file the oldest that added the file. None when no commit
    on that line did. Raises GitError when git fails."""
    base = rel_posix(area, root)
    run = run_of(rel)
    paths = (
        [f"{base}/{RUNS_DIR}/{run}/{name}" for name in (COMPLETION_FILE, FAILURE_FILE)]
        if run is not None
        else [f"{base}/{rel}"]
    )
    args = ["log", "--reverse", "--diff-filter=A", "--format=%H", "--", *paths]
    r = git_run(args, root)
    if r.returncode != 0:
        raise GitError(f"git log --diff-filter=A in {root}: {r.stderr.strip()}")
    first = r.stdout.split()
    return first[0] if first else None


def _undone_in(
    root: Path, area: Path, *, rev: str | None, staged: bool
) -> Callable[[str], bool]:
    """Whether a path of AREA's evidence, in the state REV names (else the
    index when STAGED, else the tree), is back as labkit first committed it
    (`original`) — its bytes, a record's apart from its decision lines."""
    base = rel_posix(area, root)

    def undone(rel: str) -> bool:
        first = original(root, area, rel)
        path = f"{base}/{rel}"
        if first is None:
            return False
        now = _blob_now(root, path, rev=rev, staged=staged)
        if now is not None and now == _blob_at(root, first, path):
            return True
        if run_of(rel) is not None or not findings.is_record_name(rel.split("/")[-1]):
            return False
        then = text_at(root, area / rel, first)
        later = (
            text_at(root, area / rel, rev)
            if rev is not None
            else state_text(root, area / rel, staged=staged)
        )
        return bool(then and later) and not record_changed(then or "", later or "")

    return undone


@dataclass(frozen=True)
class EvidenceChange:
    """One finding of `change_findings`: WHY the sentence, FIX its way out,
    COMPARED whether git could run the comparison — False for the one
    finding that says it could not (`unread_finding`), where nothing says
    the evidence changed."""

    why: str
    fix: str
    compared: bool = True


def change_sentences(found: Sequence[EvidenceChange]) -> list[str]:
    """FOUND (`change_findings`, read once into the area state) as
    sentences, each with its way out."""
    return [with_way_out(c.why, c.fix) for c in found]


def change_blockers(found: Sequence[EvidenceChange]) -> list[GateFinding]:
    """FOUND (`change_findings`) as blockers, each with its restore as the
    way out — what a gate that releases on an area's records holds first:
    report-check (its first station, and so `labkit-next`), a replacement
    for its predecessor's area, an exploration's registered report. A
    comparison git could not run (`unread_finding`, its `compared` False)
    is a check not executed: nothing says the evidence changed."""
    return [
        blocker(c.why, fix=c.fix, rule=OPEN_RULE)
        if c.compared
        else blocker(
            c.why, fix=c.fix, stated_outcome=NOT_EXECUTABLE, rule=TECHNICAL_RULE
        )
        for c in found
    ]


def change_findings(area: Path, *, staged: bool = False) -> list[EvidenceChange]:
    """Every change of AREA's evidence against HEAD that breaks its rule, each
    an `EvidenceChange` (sentence, way out) — in the working tree, or STAGED in the index (what
    a commit now would carry): a record changed beyond its decision lines,
    another audit file changed, a run HEAD holds closed whose files changed
    or went, a start file changed or deleted; and, STAGED only, a run the
    index holds whose start file is not staged (`unstaged_start_files`).
    A version back as labkit first committed it is no change
    (`original`): restoring a record a commit past the pre-commit rewrote
    passes. [] outside git and before the first commit; a deleted audit
    file is `attempts.gaps`'s to name. Git unable to read what the
    comparison needs is one finding of its own (`unread_finding`): nothing
    says the evidence stands."""
    root = _repo_of(area)
    if root is None or not head_sha(root):
        return []
    where = f"in the {'index' if staged else 'tree'} since HEAD"
    try:
        return [
            EvidenceChange(why, fix)
            for why, fix in _change_findings(area, root, where, staged=staged)
        ]
    except GitError as exc:
        return [unread_finding(f"the {'index' if staged else 'tree'}", "HEAD", exc)]


def unread_finding(state: str, against: str, exc: GitError) -> EvidenceChange:
    """The finding when git cannot read what comparing STATE with AGAINST
    needs: the comparison did not run (`compared` False), so the evidence
    is not known to stand; its way out is `repo.UNREAD_OBJECTS_WAY`."""
    return EvidenceChange(
        f"the area's evidence in {state} cannot be compared with {against}: "
        f"{' '.join(str(exc).split())} — whether it was changed cannot be told",
        UNREAD_OBJECTS_WAY,
        compared=False,
    )


def _change_findings(
    area: Path, root: Path, where: str, *, staged: bool
) -> list[tuple[str, str]]:
    """`change_findings` in the repository ROOT. Raises GitError when git
    fails."""
    entries = _in_area(
        _state_diff(root, "HEAD", _specs(area, root), staged=staged),
        rel_posix(area, root),
    )
    # 2. what the commit would lack: only the index is asked
    unstaged = unstaged_start_files(area, root) if staged else []
    if not entries:
        return unstaged

    def texts(rel: str) -> tuple[str | None, str | None]:
        path = area / rel
        return text_at(root, path, "HEAD"), state_text(root, path, staged=staged)

    audits, runs = broken(
        entries,
        _closed_at(root, area, "HEAD"),
        texts,
        _undone_in(root, area, rev=None, staged=staged),
        deletions=False,
    )
    return told(area, root, audits, runs, where, "HEAD") + unstaged


def unstaged_start_files(area: Path, root: Path) -> list[tuple[str, str]]:
    """(sentence, way out) per run of AREA whose record in the index says a
    start file was written for it (`run_starts.START_MARK` in the run's
    directory — staged now, or committed earlier) while the index does not
    hold that start file and the working tree does: the commit's state
    would document the run without the file that says which protocol it
    started with and when, and a check of that state — a report or an
    adoption that names the run among them — must not count a safeguard
    it lacks. The way out stages the file. [] when every such run's start
    file is in the index. The mark counts as the index holds it or as a
    commit holds it (`area_state.marked_runs`): deleting a committed mark
    does not lift the duty. For a run without a mark no start-file duty is
    evidenced, and none is asked — its own record decides, never a guess.
    A marked run whose start file stands nowhere is not held here: nothing
    could be staged, a deletion a commit made is `start_file_changes`'s,
    and the loss is told (`area_state.missing_start_warning`). Raises
    GitError when git fails."""
    try:
        marked = sorted(marked_runs(area, root, staged=True))
    except HistoryUnread:
        # the history's marks cannot be read: the index's are asked, and
        # the area state tells the unread history
        marked = sorted(
            rel.split("/")[0]
            for rel in files_at(root, area / RUNS_DIR) or set()
            if rel.count("/") == 1 and rel.endswith(f"/{START_MARK}")
        )
    staged = files_at(root, area / START_FILES_DIR) or set()
    return [
        (
            f"{START_FILES_DIR}/{path.name}: the start file of run {run} stands in "
            f"the working tree and is neither staged nor committed, while the "
            f"index holds the run's record — the commit's state would document "
            f"the run without the file that says which protocol it started with "
            f"and when",
            f"stage it (`{stage_command(path)}`)",
        )
        for run in marked
        if (path := start_path(area, run)).name not in staged and path.is_file()
    ]


def commit_changes(area: Path, since: str) -> list[str]:
    """Every change of AREA's evidence a commit after SINCE up to HEAD made
    against its first parent that breaks its rule and that the working tree
    has not undone — what the pre-commit would have refused, committed past
    it (`--no-verify`), deletions of audit files included. Undone: the tree
    holds the path as the parent did, as labkit first committed it
    (`original`), or a record differing from either in decisions alone; a
    commit stays in the history, and its repair is the restored file,
    committed or not. SINCE "" counts from the first commit. A commit git
    cannot compare with its parent is one line of its own
    (`unread_finding`). Raises GitError when the history itself cannot be
    listed."""
    root = _repo_of(area)
    if root is None or not head_sha(root):
        return []
    specs = _specs(area, root)
    span = f"{since}..HEAD" if since else "HEAD"
    # every commit with its real parents, oldest first; the path limit goes
    # on the diff, where it narrows nothing git compares against
    r = git_run(["rev-list", "--first-parent", "--parents", "--reverse", span], root)
    if r.returncode != 0:
        raise GitError(f"git rev-list {span} in {root}: {r.stderr.strip()}")
    undone_now = _undone_in(root, area, rev=None, staged=False)
    out: list[str] = []
    for line in r.stdout.splitlines():
        commit, *parents = line.split()
        if not parents:
            # the first commit: it can only add
            continue
        try:
            out += _commit_broke(area, root, commit, parents[0], specs, undone_now)
        except GitError as exc:
            unread = unread_finding(
                f"commit {commit[:12]}", f"its parent {parents[0][:12]}", exc
            )
            out.append(with_way_out(unread.why, unread.fix))
    return out


def _commit_broke(
    area: Path,
    root: Path,
    commit: str,
    parent: str,
    specs: list[str],
    undone_now: Callable[[str], bool],
) -> list[str]:
    """`commit_changes` for one COMMIT against its PARENT. Raises GitError
    when git fails."""
    base = rel_posix(area, root)
    closed = _closed_at(root, area, parent)
    tree_args = ["diff-tree", "-r", "-z", "--no-renames", "--name-status"]
    made = _in_area(_diff(root, [*tree_args, parent, commit, "--", *specs]), base)
    if not made:
        return []

    def texts_then(
        rel: str, parent: str = parent, commit: str = commit
    ) -> tuple[str | None, str | None]:
        return text_at(root, area / rel, parent), text_at(root, area / rel, commit)

    undone_then = _undone_in(root, area, rev=commit, staged=False)
    audits, runs = broken(made, closed, texts_then, undone_then, deletions=True)
    suspects = [f"{base}/{rel}" for rel, _ in audits]
    suspects += [
        f"{base}/{RUNS_DIR}/{run}/{name}"
        for run, files in runs.items()
        for name, _ in files
    ]
    if not suspects:
        return []
    # the same paths, the parent against the tree now: what is undone drops
    left = _in_area(_state_diff(root, parent, suspects, staged=False), base)

    def texts_now(rel: str, parent: str = parent) -> tuple[str | None, str | None]:
        path = area / rel
        return text_at(root, path, parent), state_text(root, path, staged=False)

    audits, runs = broken(left, closed, texts_now, undone_now, deletions=True)
    where = f"by commit {commit[:12]} and not undone in the tree"
    return [
        with_way_out(why, fix)
        for why, fix in told(area, root, audits, runs, where, parent[:12])
    ]


def _reflog_since(root: Path, since: datetime) -> list[str]:
    """The commits HEAD's reflog names from SINCE on, newest first, each
    once. [] without a reflog. Raises GitError when git fails."""
    r = git_run(["log", "-g", "-z", "--format=%H %gd", "--date=unix", "HEAD"], root)
    if r.returncode != 0:
        # an unborn HEAD or no reflog: nothing HEAD left behind
        return []
    out: list[str] = []
    for entry in r.stdout.split("\0"):
        sha, _, selector = entry.strip().partition(" ")
        stamp = selector.partition("@{")[2].rstrip("}")
        if not sha or not stamp.isdigit():
            continue
        # the reflog counts whole seconds: a commit in the second the
        # session began belongs to it
        if datetime.fromtimestamp(int(stamp)) < since.replace(microsecond=0):
            break
        if sha not in out:
            out.append(sha)
    return out


def _tree_blobs(root: Path, rev: str) -> dict[str, str]:
    """Every file REV holds under ROOT: path from ROOT → blob id. Raises
    GitError when git fails."""
    r = git_run(["ls-tree", "-r", "-z", rev], root)
    if r.returncode != 0:
        raise GitError(f"git ls-tree {rev} in {root}: {r.stderr.strip()}")
    out: dict[str, str] = {}
    for entry in r.stdout.split("\0"):
        meta, _, path = entry.partition("\t")
        fields = meta.split()
        if path and len(fields) == 3 and fields[1] == "blob":
            out[path] = fields[2]
    return out


def orphaned_runs(root: Path, since: datetime) -> list[str]:
    """Every closed run a commit held that HEAD's reflog names from SINCE on
    and HEAD no longer holds — a reset, an amend or a rebase left it behind
    —, whose files the working tree lacks or holds otherwise, under ROOT:
    one sentence per run (`<area>/runs/<run_id>`), the newest such commit
    the one to restore from. Raises GitError when git fails."""
    head = head_sha(root)
    if not head:
        return []
    lost: dict[str, tuple[str, list[str]]] = {}
    for commit in _reflog_since(root, since):
        if is_ancestor(root, commit, head):
            continue
        held = _tree_blobs(root, commit)
        runs: dict[str, dict[str, str]] = {}
        for path, blob in held.items():
            head_part, sep, rel = path.partition(f"/{RUNS_DIR}/")
            run = run_of(f"{RUNS_DIR}/{rel}") if sep else None
            if run is not None:
                runs.setdefault(f"{head_part}/{RUNS_DIR}/{run}", {})[path] = blob
        for folder, files in runs.items():
            closed = any(
                f"{folder}/{n}" in files for n in (COMPLETION_FILE, FAILURE_FILE)
            )
            if folder in lost or not closed:
                continue
            present = [root / p for p in files if (root / p).is_file()]
            now = {rel_posix(p, root): b for p, b in blobs_now(root, present).items()}
            gone = [p for p, b in files.items() if now.get(p) != b]
            if gone:
                lost[folder] = (commit, gone)
    return [
        with_way_out(
            f"{folder}: the closed run's {len(gone)} file(s) gone or changed in "
            f"the tree — commit {commit[:12]} held them, and HEAD no longer "
            "holds that commit (a reset, an amend or a rebase); a run's record "
            "stays as it ran",
            f"restore it (`{checkout_command(folder, commit[:12])}`)",
        )
        for folder, (commit, gone) in lost.items()
    ]


def ignored(area: Path) -> list[str]:
    """Every file labkit writes in AREA that git ignores and so no commit can
    carry — under `audits/` its records, reviews, journal, kept answers and
    handover records (by suffix), in a run's folder its record files
    (`RUN_RECORD_FILES`, the script's copy) —, `.gitignore`,
    `.git/info/exclude` and the global excludes file alike. Other files
    there (a raw output, an editor's litter) are left out. [] outside git.
    Raises GitError when git fails."""
    root = _repo_of(area)
    if root is None:
        return []
    base = rel_posix(area, root)
    args = ["ls-files", "-z", "--others", "--ignored", "--exclude-standard"]
    args += ["--", f"{base}/{findings.DIR}", f"{base}/{RUNS_DIR}"]
    r = git_run(args, root)
    if r.returncode != 0:
        raise GitError(f"git ls-files --ignored in {root}: {r.stderr.strip()}")
    out: list[str] = []
    for path in r.stdout.split("\0"):
        rel = path[len(base) + 1 :] if path.startswith(base + "/") else ""
        name = rel.rsplit("/", 1)[-1]
        run = run_of(rel)
        written = (
            run is not None
            and rel.count("/") == 2
            and (name in RUN_RECORD_FILES or name.startswith(_SCRIPT_COPY))
        ) or (rel.startswith(f"{findings.DIR}/") and name.endswith(AUDIT_SUFFIXES))
        if written:
            out.append(
                with_way_out(
                    f"{rel}: git ignores it — evidence labkit wrote that no "
                    "commit can carry",
                    f"`git check-ignore -v {shlex.quote(path)}` names the rule; "
                    "remove it from its file (a `.gitignore`, `.git/info/exclude` "
                    "or the global excludes file), then stage the evidence",
                )
            )
    return out


@dataclass(frozen=True)
class AreaEvidence:
    """An area's audit evidence as one file state holds it — what the stop
    and the commit hold beside report-check, what `labkit-audit --findings`
    lists, what a handover records (`attempts`, `findings`, `evidence`
    read once).

    Attributes:
        records: The audit records that read (`audit_records.record_status`).
        gaps: Every record or attempt that is gone, or a journal that does
            not read, each with its restore (`attempts.evidence_gaps`).
        unreadable: Each record that does not read, its sentence
            (`audit_records.record_status`) — a broken file hides no other.
        changes: Every change of the committed evidence against HEAD that
            breaks its rule, each an `EvidenceChange` (`evidence.change_findings`);
            `change_sentences` and `change_blockers` render them.
        ignored: Every file labkit wrote that git ignores, with its way out
            (`evidence.ignored`).
        reviews: The area's decision reviews, oldest first
            (`reviews.area_reviews`, the tree's), () when one does not read.
        reviews_unread: Why the decision reviews could not be read
            (`reviews.ReviewError`'s sentence), "" when they could.
        report_reviews: The area's report reviews, oldest first
            (`report_reviews.area_report_reviews`, the tree's), () when one
            does not read.
        report_reviews_unread: Why the report reviews or the claim reviews
            could not be read, "".
        claim_reviews: The area's claim reviews — a second reviewer's
            verdicts on decided claims —, oldest first
            (`report_reviews.area_claim_reviews`, the tree's), () when a
            report review or a claim review does not read.
        handed_over_entries: The findings any handover record of the area lists as
            left over (`handovers.handed_over`, as `handovers.entry` spells
            them), frozenset() when a record does not read.
        handovers_unread: Why the handover records could not be read, "".
    """

    records: tuple[findings.Record, ...]
    gaps: tuple[str, ...]
    unreadable: tuple[str, ...]
    changes: tuple[EvidenceChange, ...]
    ignored: tuple[str, ...]
    reviews: tuple[reviews.Review, ...] = ()
    reviews_unread: str = ""
    report_reviews: tuple[report_reviews.ReportReview, ...] = ()
    report_reviews_unread: str = ""
    handed_over_entries: frozenset[str] = frozenset()
    handovers_unread: str = ""
    claim_reviews: tuple[report_reviews.ClaimReview, ...] = ()

    @property
    def problems(self) -> tuple[str, ...]:
        """GAPS and UNREADABLE together: every problem that keeps the rest
        from counting."""
        return (*self.gaps, *self.unreadable)

    @property
    def open_blockers(self) -> list[findings.OpenFinding]:
        """The findings still `open` in RECORDS graded BLOCKER
        (`findings.open_blockers`): what the stop and the commit hold."""
        return findings.open_blockers(self.records)

    def change_sentences(self) -> list[str]:
        """CHANGES as sentences with their way out (`change_sentences`)."""
        return change_sentences(self.changes)

    def change_blockers(self) -> list[GateFinding]:
        """CHANGES as blockers with their restore (`change_blockers`)."""
        return change_blockers(self.changes)


def read_evidence(area: Path, staged: bool) -> AreaEvidence:
    """AREA's audit evidence (`AreaEvidence`) as the tree or, STAGED, the
    index holds it, each reader called once; the reviews and the handover
    records are the tree's in either state (their readers know no index),
    and a file that does not read is carried as its sentence, never
    raised. Raises RuntimeError when git fails."""
    status = audit_records.record_status(area, staged=staged)
    found_reviews: tuple[reviews.Review, ...] = ()
    reviews_unread = ""
    try:
        found_reviews = tuple(reviews.area_reviews(area))
    except reviews.ReviewError as exc:
        reviews_unread = str(exc)
    found_report_reviews: tuple[report_reviews.ReportReview, ...] = ()
    report_reviews_unread = ""
    found_claim_reviews: tuple[report_reviews.ClaimReview, ...] = ()
    try:
        found_report_reviews = tuple(report_reviews.area_report_reviews(area))
        found_claim_reviews = tuple(report_reviews.area_claim_reviews(area))
    except (report_reviews.ReportReviewError, findings.FindingsError) as exc:
        # FindingsError: a file in the folder whose name tells no age
        # (`findings.written_order`)
        found_report_reviews, found_claim_reviews = (), ()
        report_reviews_unread = str(exc)
    handed: frozenset[str] = frozenset()
    handovers_unread = ""
    try:
        handed = frozenset(handovers.handed_over(area))
    except handovers.HandoverError as exc:
        handovers_unread = str(exc)
    return AreaEvidence(
        tuple(status.records),
        tuple(evidence_gaps(area, staged=staged)),
        tuple(status.errors),
        tuple(change_findings(area, staged=staged)),
        tuple(ignored(area)),
        found_reviews,
        reviews_unread,
        found_report_reviews,
        report_reviews_unread,
        handed,
        handovers_unread,
        found_claim_reviews,
    )


def decision_reviews_in_tree(area: Path) -> list[reviews.Review]:
    """AREA's decision reviews as the working tree holds them, for a review
    to be drawn or a rendering to be written. A review has no other file
    state: a check of the index reads the tree's too (`read_evidence`), so
    these are the reviews every gate judges by. Raises `reviews.ReviewError`
    when one does not read: a decision judged or a line written past it
    would read as unreviewed. Raises RuntimeError when git fails."""
    held = read_evidence(area, staged=False)
    if held.reviews_unread:
        raise reviews.ReviewError(
            f"a decision review does not read: {held.reviews_unread} — repair it first"
        )
    return list(held.reviews)
