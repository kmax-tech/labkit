"""hook_post_change — the post-change hook: protocol-check and notes-check
on every changed protocol and measurement note, the review hint of a
report that discusses a run, and what the stop and the commit will hold of
an area's evidence (`post_change`). What it tells and why: `agent_hooks`'
docstring, "post-change".
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
    attempts,
    evidence,
    findings,
    runs,
)
from labkit.checks import notes_check, protocol_report
from labkit.checks import report_blocks
from labkit.checks.report_blocks import ReportBlockError
from labkit.gates import report_hold
from labkit.formats.runs import run_path
from labkit.run.runlog import RunIndexError, indexed_runs
from labkit.formats.repo import (
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
    status to name, so `evidence_areas` never saw it: an agent deleted runs/
    five times without a word (reference pilot 2026-11-01, task 60)."""
    base = repo / EXPERIMENTS
    if not base.is_dir():
        return []
    return [
        area
        for area in sorted(p for p in base.iterdir() if p.is_dir())
        if index_problems(area)
    ]


def gone_runs(area: Path) -> list[str]:
    """The runs AREA's run index lists whose directories are gone. Raises
    RunIndexError on an index that does not read."""
    return [r for r in indexed_runs(area) if not run_path(area, r).is_dir()]


def index_problems(area: Path) -> list[str]:
    """What AREA's run index tells the evidence check: each run it lists
    whose directory is gone, or why the index does not read — a damaged
    index hides those runs, so it is told, never skipped."""
    try:
        gone = gone_runs(area)
    except RunIndexError as exc:
        return [exc.why]
    return [
        f"run {r}: its directory is gone — runs.tsv lists it as measured; never delete a "
        f"run: an audit that read it holds the adoption, and only git, where "
        f"it holds the run, restores its rows"
        for r in gone
    ]


#: the post-change cache's key of an area's evidence state, before the area
EVIDENCE_KEY = "evidence:"


def _untold_evidence(cache: dict, areas: list[Path], repo: Path) -> list[str]:
    """What the stop and the commit will hold of each of AREAS' evidence,
    told right after the tool that changed it, once per state (CACHE,
    updated in place): every integrity problem (`attempts.area_integrity`)
    and every change git can undo (`evidence.changes`, `evidence.ignored`),
    as `<area>: <sentence>` with its way out. An area found clean forgets
    its state, so a later problem of the same text is told again."""
    out: list[str] = []
    for area in areas:
        lines = [
            *attempts.area_integrity(area).problems,
            *evidence.changes(area),
            *evidence.ignored(area),
            *index_problems(area),
        ]
        key = f"{EVIDENCE_KEY}{area}"
        if not lines:
            cache.pop(key, None)
            continue
        digest = scope_digest("\n".join(lines).encode("utf-8"))
        if cache.get(key) == digest:
            continue
        cache[key] = digest
        shown_area = area.resolve().relative_to(repo.resolve()).as_posix()
        out.append(
            f"evidence of {shown_area} is gone or changed — restore it now; the "
            "stop and the commit hold what each line names (a current handover "
            "acknowledges a loss, never a change git can undo):\n  "
            + "\n  ".join(f"{shown_area}: {line}" for line in lines)
        )
    return out


def wants_check(path: Path) -> str | None:
    """Which checker a path belongs to: 'protocol', 'note' or None."""
    if PROTOCOL_NAME.match(path.name):
        return "protocol"
    parts = path.as_posix().split("/")
    # any `notes/messung/` pair on the way, not the first `notes`: a repo
    # under an ancestor directory named notes never had its notes checked
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
    once a review stands; until 0.107.0 a hint of its own named the review
    whenever a run was discussed, reviewed or not). None when nothing
    holds it."""
    root = repo.resolve()
    link_target = report_hold.refused_link(repo, path, staged=False)
    if link_target is not None:
        # named where it lies: `shown` resolves, which follows the link
        rel = path.relative_to(root).as_posix()
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
    sources = report_hold.Sources(root, set(), texts, {}, {})
    rel = path.relative_to(root).as_posix()
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
        # the file as pfad:zeile itself — the hook rewrote the absolute
        # path in the printed text before (audit 2026-10-27, third, M4)
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
