"""hook_post_change — the post-change hook (`claude-hook post-change`,
PostToolUse on Bash, Write and Edit): protocol-check and notes-check on
every changed protocol and measurement note, the review hint of a report
that discusses a run, and what an area's evidence lost (`post_change`).

Every file the repo now reports as changed (git status, untracked
included) plus the tool's own file_path, filtered to PROTOCOL-*.md and
notes/messung/*.md (not 00-*), is checked with protocol-check or
notes-check. A changed Markdown report that discusses a run (a
discussion block, `report_blocks.discussions`) gets the report review it owes
while no review of this state names no claim
(`report_hold.report_review_owed`, the gate's own finding) — a hint;
the review is one model call and the agent's to start. A report is read at its own path
(`repo.own_path`), as the stop and the commit read it: one that is a
symbolic link is told their refusal and its way out
(`report_hold.link_gap`). An area whose `audits/` or `runs/` git status
names (deleted, changed or new) is told what the stop and the commit
will hold of its evidence — a record gone, a record rewritten beyond its
decision lines, a closed run's file changed — with the restore each line
names, right after the tool did it (`_untold_evidence`); it holds
nothing itself. A per-session cache of content hashes keeps a
file that was already checked or hinted at this content, and an area's
evidence in a state already told, from being reported after every later
command.

Exit 0 always; what it tells is `additionalContext` on stdout. It holds
nothing itself.
"""

from __future__ import annotations

import contextlib
import json
import tempfile
from pathlib import Path

from labkit.gates.hook_session import project_dir
from labkit.gates.hook_session import session_repo
from labkit.gates.hook_session import tell_context
from labkit.formats import (
    findings,
    runs,
)
from labkit.checks import notes_check, protocol_report
from labkit.checks import report_blocks
from labkit.checks.report_blocks import ReportBlockError
from labkit.gates import report_hold
from labkit.formats.area_state import (
    AreaState,
    LOST_RUN_SENTENCE,
    gone_run_restore,
    index_names_gone_runs,
    state_of,
)
from labkit.formats import evidence
from labkit.formats.run_index import RunIndexError
from labkit.formats.repo import (
    rel_posix,
    EXPERIMENTS,
    PROTOCOL_NAME,
    find_area,
    own_path,
    shown,
    status_entries,
)
from labkit.formats.digests import file_digest
from labkit.formats.digests import digest as scope_digest


def _git_changed(repo: Path, entries: list[tuple[str, str]]) -> list[Path]:
    """Every path of ENTRIES (`repo.status_entries` of REPO) git sees as
    changed, untracked included, deletions left out."""
    return [repo / path for xy, path in entries if "D" not in xy]


def evidence_areas(repo: Path, entries: list[tuple[str, str]]) -> list[Path]:
    """The areas whose evidence ENTRIES (`repo.status_entries` of REPO) name
    — a path in an area's `audits/` or `runs/`, deleted, changed or new —,
    each once, in order."""
    out: list[Path] = []
    for _, rel in entries:
        path = repo / rel
        area = find_area(path, repo)
        if area is None:
            continue
        inside = path.resolve().relative_to(area.resolve()).parts
        if inside and inside[0] in (findings.DIR, runs.RUNS_DIR) and area not in out:
            out.append(area)
    return out


def gone_run_areas(repo: Path) -> list[Path]:
    """The areas of REPO's `experiments/` whose run index lists a run whose
    directory is gone. Deleting an untracked run leaves nothing for git
    status to name, so `evidence_areas` does not see it."""
    base = repo / EXPERIMENTS
    if not base.is_dir():
        return []
    return [
        area
        for area in sorted(p for p in base.iterdir() if p.is_dir())
        if index_names_gone_runs(area)
    ]


def index_problems(state: AreaState) -> list[str]:
    """What the deleted runs of an area (its STATE) tell the evidence check:
    each run a commit holds whose directory is gone, with the checkout that
    restores it; each run only the local run index lists, lost; or why git
    could not list the runs it holds — told, never skipped."""
    return (
        ([state.history_unread] if state.history_unread else [])
        + [
            f"run {rd.dir.name}: its directory is gone — {gone_run_restore(rd)}"
            for rd in state.deleted
        ]
        + [
            f"run {r}: its directory is gone — runs.tsv lists it as measured, and "
            f"{LOST_RUN_SENTENCE}, and an audit that read it holds the adoption"
            for r in state.lost
        ]
    )


#: the post-change cache's key of an area's evidence state, before the area
EVIDENCE_KEY = "evidence:"


def _untold_evidence(cache: dict, areas: list[Path], repo: Path) -> list[str]:
    """What happened to each of AREAS' evidence, told right after the tool
    that changed it, once per state (CACHE, updated in place), each line as
    `<area>: <sentence>` with its way out: what the stop and the commit
    hold — every integrity problem (`evidence.AreaEvidence`) and every
    change git can undo (`evidence.AreaEvidence.change_sentences`, `evidence.ignored`) — and,
    apart, what is only lost: a run the index lists whose directory is gone
    (`index_problems`), which neither holds. An area found clean forgets its
    state, so a later problem of the same text is told again."""
    out: list[str] = []
    for area in areas:
        try:
            state = state_of(area)
        except RunIndexError as exc:
            # the index does not read: told as a loss, held by nothing
            state, lost = None, [exc.why]
        else:
            lost = index_problems(state)
        kept = evidence.read_evidence(area, staged=False)
        held = [*kept.problems, *kept.change_sentences(), *kept.ignored]
        lines = held + lost
        key = f"{EVIDENCE_KEY}{area}"
        if not lines:
            cache.pop(key, None)
            continue
        digest = scope_digest("\n".join(lines).encode("utf-8"))
        if cache.get(key) == digest:
            continue
        cache[key] = digest
        shown_area = rel_posix(area, repo)
        if held:
            out.append(
                f"evidence of {shown_area} is gone or changed — restore it now; the "
                "stop and the commit hold what each line names (a current handover "
                "acknowledges a loss, never a change git can undo):\n  "
                + "\n  ".join(f"{shown_area}: {line}" for line in held)
            )
        if lost:
            out.append(
                f"a run of {shown_area} is gone — the stop and the commit do not "
                "hold it, and nothing brings its rows back but git:\n  "
                + "\n  ".join(f"{shown_area}: {line}" for line in lost)
            )
    return out


def wants_check(path: Path) -> str | None:
    """Which checker a path belongs to: 'protocol', 'note' or None."""
    if PROTOCOL_NAME.match(path.name):
        return "protocol"
    parts = path.as_posix().split("/")
    # any `notes/messung/` pair on the way, not the first `notes`: a repo
    # under an ancestor directory named notes would go unchecked
    under_messung = any(
        a == "notes" and b == "messung" for a, b in zip(parts, parts[1:])
    )
    if under_messung and path.suffix == ".md" and not path.name.startswith("00-"):
        return "note"
    return None


def _cache_path(session_id: str | None) -> Path | None:
    if not session_id:
        return None
    d = Path(tempfile.gettempdir()) / "labkit-agent-hook"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{session_id}.json"


def _load_cache(p: Path | None) -> dict:
    if p is None or not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _report_hint(text: str, path: Path, repo: Path) -> str | None:
    """What the stop and the commit will hold the report at PATH (its own
    path, `repo.own_path`; its TEXT) with, said where it is written: a
    report that is a symbolic link (`report_hold.link_gap`, with its way
    out), a block in it that does not read, or the report review it owes
    for discussing a run while no review of this state names no claim
    (`report_hold.report_review_owed` — the gate's own finding, so the
    hook names the review exactly when the gate holds it and falls silent
    once a review stands). None when nothing holds it."""
    root = repo.resolve()
    link_target = report_hold.refused_link(repo, path, staged=False)
    if link_target is not None:
        # named where it lies: `shown` resolves, which follows the link
        rel = rel_posix(path, root)
        return report_hold.link_gap(rel, path, link_target, repo, staged=False).message
    try:
        discussed = report_blocks.discussions(text)
    except ReportBlockError as exc:
        return f"{shown(path, repo)}: {exc}"
    if not discussed:
        return None
    protocols = {(path.parent / d.protocol).resolve() for d in discussed}
    texts = {
        p: p.read_text(encoding="utf-8")
        for p in protocols
        if p.is_file() and not p.is_symlink()
    }
    sources = report_hold.Sources.blank(root, staged=False, texts=texts)
    rel = rel_posix(path, root)
    gaps = report_hold.report_review_owed(path, rel, text, discussed, sources)
    return "; ".join(g.message for g in gaps) or None


def post_change(event: dict) -> int:
    """PostToolUse hook: the tool's file and every file git shows changed
    (`_changed`) — a protocol or a measurement note gets its checker, a
    report that discusses a run the review it owes, as the gate holds it
    (`_report_hint`) —, each told once per content (`_untold`);
    evidence gone or changed in an area whose `audits/` or `runs/` git
    status names gets what the stop and the commit will hold, with its way
    out, once per state (`_untold_evidence`); the findings go back as
    context."""
    found = session_repo(event)
    # outside git only the tool's own file is checked, shown against the
    # project directory
    repo = found if found is not None else project_dir(event)
    candidates: list[Path] = []
    entries = status_entries(repo) if found is not None else []
    candidates.extend(_git_changed(repo, entries))
    fp = (event.get("tool_input") or {}).get("file_path")
    if fp:
        candidates.append(Path(fp))
    named, targets = _changed(candidates, repo)
    marked = [
        (path, hint)
        for path, text in report_hold.report_files(named, repo, staged=False)
        if (hint := _report_hint(text, path, repo))
    ]
    areas = evidence_areas(repo, entries)
    areas += [a for a in gone_run_areas(repo) if a not in areas]
    cache_file = _cache_path(event.get("session_id"))
    cache = _load_cache(cache_file)
    before = dict(cache)
    # an area git status no longer names is as HEAD holds it again: its
    # state told goes, so the same loss later is told again
    held = {f"{EVIDENCE_KEY}{area}" for area in areas}
    for key in [k for k in cache if k.startswith(EVIDENCE_KEY) and k not in held]:
        del cache[key]
    reports = _untold(cache, marked, targets, repo)
    reports += _untold_evidence(cache, areas, repo)
    if cache_file is not None and cache != before:
        cache_file.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    if reports:
        tell_context("PostToolUse", "\n".join(reports))
    return 0


def _changed(
    candidates: list[Path], repo: Path
) -> tuple[list[Path], list[tuple[str, Path]]]:
    """Of CANDIDATES (relative to REPO or absolute): every path as the repo
    names it, a link kept where it lies (`repo.own_path`) — as the stop and
    the commit hold reports; resolved, a linked report would be read where
    it points —, and the (kind, file) pairs a checker wants
    (`wants_check`), each existing file once."""
    seen: set[Path] = set()
    named: list[Path] = []
    targets: list[tuple[str, Path]] = []
    for c in candidates:
        own = own_path(c if c.is_absolute() else repo / c)
        if own not in named:
            named.append(own)
        c = c.resolve()
        if c in seen or not c.is_file():
            continue
        seen.add(c)
        kind = wants_check(c)
        if kind:
            targets.append((kind, c))
    return named, targets


def _untold(
    cache: dict,
    marked: list[tuple[Path, str]],
    targets: list[tuple[str, Path]],
    repo: Path,
) -> list[str]:
    """What the post hook tells, each piece once per state (CACHE, updated
    in place): a report's review hint (MARKED) once per text and hint — a
    hint repeated on every edit of the same state is noise; a changed text,
    or another hint for the same bytes (a link replaced by its copy is then
    a report), is told again —, and each target's checker output once per
    file content."""
    reports = []
    for path, hint in marked:
        key = f"report-review:{path}"
        digest = f"{file_digest(path)}:{scope_digest(hint.encode('utf-8'))}"
        if cache.get(key) != digest:
            cache[key] = digest
            reports.append(hint)
    for kind, path in targets:
        digest = file_digest(path)
        if cache.get(str(path)) == digest:
            continue
        cache[str(path)] = digest
        # from the repo root with the repo-relative path (the hook's cwd is
        # wherever the agent stood): every line the checker tells names
        # the file as pfad:zeile itself
        told: list[str] = []
        named = [Path(shown(path, repo))]
        with contextlib.chdir(repo):
            if kind == "protocol":
                template = protocol_report.template_lines(
                    protocol_report.find_template(None)
                )
                protocol_report.check_files(named, template, tell=told.append)
            else:
                notes_check.check_notes(named, tell=told.append)
        out = "\n".join(told).rstrip()
        if out:
            reports.append(out)
    return reports
