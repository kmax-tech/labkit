"""evidence — what an area's committed evidence may become, and the changes
against a commit that break it.

An area's evidence is what labkit wrote under `audits/` and `runs/`. Once a
commit holds it, it stays as written:

    audits/<record>.toml   only its findings' decision lines change —
                           `status`, `reason`, `effect`, which `labkit-audit
                           --decide` writes (`findings.without_decisions`)
    audits/attempts.jsonl  appended to, never cut — `attempts` holds it,
                           against HEAD and against its copy in the git
                           directory; this module leaves it out
    audits/ otherwise      never changes: a failed attempt, a review, a kept
                           answer, a handover record
    runs/<run_id>/         never changes or goes once the commit holds the
                           run closed — `completion.json` or `failure.json`
                           in it; a run still open there is runlog's to write

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
from labkit.formats import findings, handovers, report_reviews, reviews
from labkit.formats.attempts import evidence_gaps
from labkit.formats.findings import JOURNAL
from labkit.formats.gate import OPEN_RULE
from labkit.formats.gate import (
    NOT_EXECUTABLE,
    VIOLATED,
    GateFinding,
    blocker,
    with_way_out,
)
from labkit.formats.repo import (
    rel_posix,
    GitError,
    blobs_now,
    files_at,
    git_root,
    git_run,
    head_sha,
    is_ancestor,
    state_text,
    text_at,
)
from labkit.formats.commands import audit_command
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
)
_SCRIPT_COPY = script_copy_path(Path(), "").stem
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
    """Does AFTER, a record's text, differ from BEFORE beyond its findings'
    decision lines (`findings.without_decisions`)? A version whose findings
    lack those lines is compared whole. Pure."""
    kept, now = findings.without_decisions(before), findings.without_decisions(after)
    if kept is None or now is None:
        return before != after
    return kept != now


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
    (`attempts.gaps` names one against HEAD); and per run CLOSED in the
    earlier state its paths changed or deleted, each as (path in the run's
    folder, how). TEXTS reads a record's two versions (earlier, later): one
    whose decisions alone changed breaks nothing. UNDONE tells a later
    version that is back as labkit first committed it (`original`): a
    restore breaks nothing either. Pure apart from TEXTS and UNDONE."""
    audits: list[tuple[str, str]] = []
    runs: dict[str, list[tuple[str, str]]] = {}
    for letter, rel in entries:
        how = _HOW.get(letter)
        run = run_of(rel)
        parts = rel.split("/")
        if how is None or (run is not None and run not in closed):
            continue
        if run is None and (
            parts[0] != findings.DIR or rel == f"{findings.DIR}/{JOURNAL}"
        ):
            continue
        what = how
        if how == "changed" and run is None and len(parts) == 2:
            if findings.is_record_name(parts[1]):
                before, after = texts(rel)
                if before and after and not record_changed(before, after):
                    continue
                what = "record"
        if how == "deleted" and run is None and not deletions:
            continue
        if how == "changed" and undone(rel):
            continue
        if run is not None:
            runs.setdefault(run, []).append((rel.split("/", 2)[2], how))
        else:
            audits.append((rel, what))
    return audits, runs


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
    base = _base(area, root)

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


def _base(area: Path, root: Path) -> str:
    """AREA's path from ROOT, `/`-separated."""
    return rel_posix(area, root)


def _specs(area: Path, root: Path) -> list[str]:
    """The pathspecs of AREA's evidence: its `audits/` and its `runs/`."""
    base = _base(area, root)
    return [f"{base}/{findings.DIR}", f"{base}/{RUNS_DIR}"]


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
    base = _base(area, root)
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
    base = _base(area, root)

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


def change_sentences(found: Sequence[tuple[str, str]]) -> list[str]:
    """FOUND (`change_findings`, read once into the area state) as
    sentences, each with its way out."""
    return [with_way_out(why, fix) for why, fix in found]


def change_blockers(found: Sequence[tuple[str, str]]) -> list[GateFinding]:
    """FOUND (`change_findings`) as blockers, each with its restore as the
    way out — what a gate that releases on an area's records holds first:
    report-check (its first station, and so `labkit-next`), a replacement
    for its predecessor's area, an exploration's registered report. A
    comparison git could not run (`unread_finding`, its way out UNREAD_WAY)
    is a check not executed: nothing says the evidence changed."""
    return [
        blocker(
            why,
            fix=fix,
            # UNREAD_WAY is the way out only `unread_finding` gives
            check_outcome=NOT_EXECUTABLE if fix == UNREAD_WAY else VIOLATED,
            rule=OPEN_RULE,
        )
        for why, fix in found
    ]


def change_findings(area: Path, *, staged: bool = False) -> list[tuple[str, str]]:
    """Every change of AREA's evidence against HEAD that breaks its rule, as
    (sentence, way out) — in the working tree, or STAGED in the index (what
    a commit now would carry): a record changed beyond its decision lines,
    another audit file changed, a run HEAD holds closed whose files changed
    or went. A version back as labkit first committed it is no change
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
        return _change_findings(area, root, where, staged=staged)
    except GitError as exc:
        return [unread_finding(f"the {'index' if staged else 'tree'}", "HEAD", exc)]


#: the way back from evidence git cannot compare: the objects, then the check
UNREAD_WAY = (
    "restore the repository's missing objects (`git fsck` names them; a clone "
    "that holds them `git fetch`es them), then run the check again"
)


def unread_finding(state: str, against: str, exc: GitError) -> tuple[str, str]:
    """(sentence, way out) when git cannot read what comparing STATE with
    AGAINST needs: the comparison did not run, so the evidence is not
    known to stand."""
    return (
        f"the area's evidence in {state} cannot be compared with {against}: "
        f"{' '.join(str(exc).split())} — whether it was changed cannot be told",
        UNREAD_WAY,
    )


def _change_findings(
    area: Path, root: Path, where: str, *, staged: bool
) -> list[tuple[str, str]]:
    """`change_findings` in the repository ROOT. Raises GitError when git
    fails."""
    entries = _in_area(
        _state_diff(root, "HEAD", _specs(area, root), staged=staged), _base(area, root)
    )
    if not entries:
        return []

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
    return told(area, root, audits, runs, where, "HEAD")


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
            out.append(
                with_way_out(
                    *unread_finding(
                        f"commit {commit[:12]}", f"its parent {parents[0][:12]}", exc
                    )
                )
            )
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
    base = _base(area, root)
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
            now = {
                p.relative_to(root).as_posix(): b
                for p, b in blobs_now(root, present).items()
            }
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
        records: The audit records that read (`findings.record_status`).
        gaps: Every record or attempt that is gone, or a journal that does
            not read, each with its restore (`attempts.evidence_gaps`).
        unreadable: Each record that does not read, its sentence
            (`findings.record_status`) — a broken file hides no other.
        changes: Every change of the committed evidence against HEAD that
            breaks its rule, as (sentence, way out) (`evidence.change_findings`);
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
        report_reviews_unread: Why the report reviews could not be read, "".
        handed_over_entries: The findings any handover record of the area lists as
            left over (`handovers.handed_over`, as `handovers.entry` spells
            them), frozenset() when a record does not read.
        handovers_unread: Why the handover records could not be read, "".
    """

    records: tuple[findings.Record, ...]
    gaps: tuple[str, ...]
    unreadable: tuple[str, ...]
    changes: tuple[tuple[str, str], ...]
    ignored: tuple[str, ...]
    reviews: tuple[reviews.Review, ...] = ()
    reviews_unread: str = ""
    report_reviews: tuple[report_reviews.ReportReview, ...] = ()
    report_reviews_unread: str = ""
    handed_over_entries: frozenset[str] = frozenset()
    handovers_unread: str = ""

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
    status = findings.record_status(area, staged=staged)
    found_reviews: tuple[reviews.Review, ...] = ()
    reviews_unread = ""
    try:
        found_reviews = tuple(reviews.area_reviews(area))
    except reviews.ReviewError as exc:
        reviews_unread = str(exc)
    found_report_reviews: tuple[report_reviews.ReportReview, ...] = ()
    report_reviews_unread = ""
    try:
        found_report_reviews = tuple(report_reviews.area_report_reviews(area))
    except report_reviews.ReportReviewError as exc:
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
    )
