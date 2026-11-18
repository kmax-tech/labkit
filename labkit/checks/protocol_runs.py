"""protocol_runs — every run of a protocol, as an analysis audit is shown it.

An exploratory protocol may measure many times, and a run may be chosen
because its number suits. The audit is the control: it is shown every run
of the protocol it audits and of each protocol a source of that run was
measured under — completed or not, present, deleted from the tree or only
in the run index —, never only the runs the answering run builds on. Per
run: its state, its result, its step then, how its registration then
differs from the compared run's, and how its code then differs (commit
plus `uncommitted.patch`, `run_code`): git's file summary in the list,
the whole diff as a RUN DIFF piece of its own while the audit's DIFF_BUDGET
lasts; past it the list names the diff not shown in full, with an excerpt
and the rest unread (`labkit-run-diff` prints it for a person). A finding
asks for such a diff, or one path's section of it, with a `diff:` check
(`findings.diff_request`); once it is decided, every later audit shows it
as a REQUESTED DIFF piece, taken from the budget before any other
(`requested_pieces`). The pieces are in the digest the audit record binds
(`audit_binding.run_shown`), so a new run of such a protocol stales the
audit. Reads files and git, writes only git objects (`run_code`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from labkit.formats import runs
from labkit.formats.area_state import Measured, state_of
from labkit.formats.digests import digest
from labkit.formats.findings import DIFF_CHECK, DiffRequest, diff_request
from labkit.formats.followup import DiffAsked
from labkit.formats.protocol_block import BlockError, find_by_id
from labkit.formats.protocol_history import (
    StepThen,
    registration_differences,
    step_then,
)
from labkit.formats.promises import PromiseError
from labkit.formats.repo import GitError, git_root, layout_root, shown, text_at
from labkit.formats.run_code import CodeThen, code_difference, code_scope, code_then

#: how the label of the piece of the audited run's own protocol opens; its
#: id follows
OWN_LABEL = "RUNS OF THIS PROTOCOL "
#: how the label of the piece of a source run's protocol opens; its id follows
SOURCE_LABEL = "RUNS OF SOURCE PROTOCOL "

#: how a full code difference's piece label opens; "<base> → <run>" follows
DIFF_LABEL = "RUN DIFF "
#: the characters of full diffs one audit is shown, over all its pieces; a
#: diff past it is named not shown, with an excerpt of DIFF_SHOW_LINES
DIFF_BUDGET = 300_000
#: the diff lines of the excerpt of a diff not shown in full
DIFF_SHOW_LINES = 80
#: how a requested diff's piece label opens; "<old> → <new>" and, for a
#: section, ", <path>" follow (`request_label`)
REQUEST_LABEL = "REQUESTED DIFF "
#: how a piece that names evidence without showing it opens
NOT_SHOWN = "not shown:"
#: how a requested piece opens that a follow-up already judged on the
#: text shown (`followup.diff_requests`): served, it takes no more room
JUDGED_SHOWN = "judged:"
#: the characters of a run's metrics.json shown inline
RESULT_SHOW_CHARS = 600

#: what the code comparison covers, and what it does not (`run_code.code_scope`)
CODE_LIMIT = (
    "The code compared is the area's Python files outside runs/ and the "
    "repository's lib/ and src/ only: files git did not track when a run "
    "started, prompts, data files, other repositories (labkit, a framework) "
    "and the environment are not compared — the same code here does not "
    "mean the same influences."
)

#: what every such piece states before its list
READING = (
    "Every run bound to this protocol, oldest first, grouped by the step its "
    "own text declared: completed or not, a repeat or not, deleted from the "
    "tree, or known only to the run index — none is left out. Each is "
    "compared with {base}: the registration as each run saw it, and its code "
    "then (its commit with its uncommitted.patch). Judge whether a run was "
    "chosen because its result suits, and whether a change between runs is "
    "declared and explained. "
    + CODE_LIMIT
    + " Each run's whole diff stands under its own `RUN DIFF <compared> → "
    "<run>` piece. Where the audit's budget for diffs is spent, a diff is "
    "marked not shown in full: the lines past its excerpt are unread, and a "
    "judgement that needs them stays open — write it as an undetermined "
    "BLOCKER closed by `· check: {check}` (the whole diff) or `· check: "
    "{check}:<repository path>` (one file's or folder's section of it): "
    "decided, the follow-up audit is shown it under `REQUESTED DIFF`, ahead "
    "of every other diff. Never judge code you were not shown."
)


def run_diff_command(area: Path, old: str, new: str) -> str:
    """The command that prints the full code difference of run NEW of AREA
    from run OLD (`tools.run_diff`), AREA as the layout root's relative
    path — the piece is bound by its digest, so no spelling of the path
    (on macOS /var is /private/var) may move it."""
    return f"labkit-run-diff {shown(area, layout_root(area))} {old} {new}"


def bound_protocol_file(area: Path, pid: str, recorded: str | None) -> Path:
    """The protocol file of AREA that a run bound to PID was measured
    under, to read its text then from (`protocol_history.as_measured`):
    the one carrying PID now, else the path the run RECORDED, else the
    stamped name — at the run's commit `as_measured` finds the file by the
    id again. The one finding of a run's protocol by its binding."""
    try:
        return find_by_id(area, pid)
    except BlockError:
        if recorded and not Path(recorded).is_absolute():
            return area / recorded
        return area / f"PROTOCOL-{pid}.md"


@dataclass(frozen=True)
class RunSeen:
    """One run of the protocol, as the piece reads it.

    Attributes:
        rd: Its record (read back from a commit for a run gone from the
            tree).
        state: What became of it — `runs.run_state`, or gone, or unreadable.
        step: Its step from its own text (`protocol_history.step_then`);
            None for a record that does not read.
    """

    rd: runs.RunDir
    state: str
    step: StepThen | None


@dataclass
class DiffBudget:
    """The characters of full diffs an audit may still be shown (LEFT,
    from DIFF_BUDGET), the RUN DIFF pieces taken so far, and the whole
    differences a requested piece already shows (ASKED, (old run, new run)
    → its label), which a RUN DIFF does not show twice — one budget for
    all the protocol pieces of one audit."""

    left: int
    pieces: list[tuple[str, str]] = field(default_factory=list)
    asked: dict[tuple[str, str], str] = field(default_factory=dict)


def protocol_runs_pieces(
    area: Path, run_dir: Path, requests: Iterable[DiffAsked] = ()
) -> list[tuple[str, str]]:
    """The pieces MODE analysis is shown of the runs around RUN_DIR, the
    run audited: one for its own protocol, compared with RUN_DIR, then one
    per further protocol an origin run of RUN_DIR's inputs was bound to,
    compared with the first such origin run, its origins marked, then one
    per `diff:` check in REQUESTS (`requested_pieces`, served first from
    the budget), then the RUN DIFF pieces. [] for a run bound to no
    protocol or whose record does not read (the record checks name that).
    Raises RuntimeError when git fails."""
    rd = runs.read_run_dir(run_dir)
    if rd.config is None or rd.config.protocol.id is None:
        return []
    state = state_of(area)
    root = git_root(area)
    pid = rd.config.protocol.id
    budget = DiffBudget(DIFF_BUDGET)
    try:
        entries = runs.read_data(run_dir) or []
    except runs.ArtefactError:
        entries = []  # the record checks name it; no source protocol is shown
    origins = [e.origin_run for e in entries if e.origin_run is not None]
    by_protocol: dict[str, list[runs.RunDir]] = {}
    for run_id in dict.fromkeys(origins):
        origin = runs.read_run_dir(runs.run_path(area, run_id))
        opid = origin.config.protocol.id if origin.config is not None else None
        if opid is not None and opid != pid:
            by_protocol.setdefault(opid, []).append(origin)
    listed = [state.measured_of(pid), *map(state.measured_of, by_protocol)]
    asked = requested_pieces(area, root, requests, listed, budget)
    out = [protocol_piece(area, root, listed[0], rd, OWN_LABEL, set(), budget)]
    for (opid, sources), measured in zip(by_protocol.items(), listed[1:]):
        marked = {s.dir.name for s in sources}
        out.append(
            protocol_piece(
                area, root, measured, sources[0], SOURCE_LABEL, marked, budget
            )
        )
    return out + asked + budget.pieces


def request_label(asked: DiffRequest) -> str:
    """The label of the piece that shows ASKED: REQUEST_LABEL, the runs,
    and for a section its path."""
    section = f", {asked.path}" if asked.path else ""
    return f"{REQUEST_LABEL}{asked.old} → {asked.new}{section}"


def requested_pieces(
    area: Path,
    root: Path | None,
    requests: Iterable[DiffAsked],
    listed: list[Measured],
    budget: DiffBudget,
) -> list[tuple[str, str]]:
    """One `(label, text)` piece per `diff:` check of REQUESTS
    (`followup.diff_requests`), in their order. Owed whole: the code
    difference of its new run from its old one, both runs of the protocols
    LISTED shows, or the section of it whose file paths are its path or
    lie under it — whole, from BUDGET before any RUN DIFF piece takes from
    it. NOT_SHOWN and why, with nothing of the diff, when a run is listed
    nowhere or its code does not read back, the path names nothing that
    differs, or the text is past what BUDGET has left: a section is the
    narrower request. A whole difference shown is noted in BUDGET.asked.
    Judged already: JUDGED_SHOWN, the verdict and the digest of the text,
    which takes nothing from BUDGET — the verdict stays traceable, the
    text was judged once. Raises RuntimeError when git fails."""
    by_name = {rd.dir.name: rd for m in listed for rd in m.runs}
    out: list[tuple[str, str]] = []
    for a in requests:
        asked = diff_request(a.check)
        label = request_label(asked)
        why, text, files = _requested_text(area, root, asked, by_name)
        if a.judged:
            then = (
                f"its text (digest {digest(text.encode('utf-8'))}) is not shown again"
                if not why
                else f"its text does not read back now: {why}"
            )
            out.append((label, f"{JUDGED_SHOWN} {a.judged} on the diff shown; {then}"))
            continue
        if why:
            out.append((label, f"{NOT_SHOWN} {why}"))
            continue
        if len(text) > budget.left:
            out.append(
                (
                    label,
                    f"{NOT_SHOWN} {len(text)} characters, past the {budget.left} "
                    f"left of the {DIFF_BUDGET} this audit may be shown of all "
                    f"diffs — ask for the section of one path, "
                    f"`{DIFF_CHECK}{asked.old}..{asked.new}:<path>`; the files "
                    f"that differ: {', '.join(files)}",
                )
            )
            continue
        budget.left -= len(text)
        if asked.path is None:
            budget.asked[(asked.old, asked.new)] = label
        out.append((label, text))
    return out


def _requested_text(
    area: Path, root: Path | None, asked: DiffRequest, by_name: dict[str, runs.RunDir]
) -> tuple[str, str, list[str]]:
    """(why not, text, files) of what ASKED names: "" and the text — each
    run's code then, then the diff or its section — with the files that
    differ, or why it cannot be shown and nothing of it."""
    missing = [r for r in (asked.old, asked.new) if r not in by_name]
    if missing:
        return f"run {missing[0]} is no run of the protocols this audit lists", "", []
    if root is None:
        return "the area lies in no git repository", "", []
    old, new = (code_then(by_name[r], root) for r in (asked.old, asked.new))
    if old.tree is None or new.tree is None:
        return (old if old.tree is None else new).where, "", []
    try:
        diff = code_difference(root, code_scope(area, root), old.tree, new.tree)
    except GitError as exc:
        return str(exc), "", []
    text = diff.diff if asked.path is None else diff_section(diff.diff, asked.path)
    files = [ln.split("|")[0].strip() for ln in diff.stat.splitlines() if "|" in ln]
    if not text:
        return (
            f"no file of the code compared at or under `{asked.path or '.'}` "
            f"differs; the files that do: {', '.join(files) or 'none'}",
            "",
            files,
        )
    return "", f"{asked.old}: {old.where}\n{asked.new}: {new.where}\n{text}", files


def diff_section(diff: str, path: str) -> str:
    """The file sections of the unified DIFF (each from its `diff --git`
    line to the next) whose old or new path is PATH or lies under it; ""
    when none does."""
    sections = re.split(r"(?m)^(?=diff --git )", diff)
    path = path.rstrip("/")
    return "".join(
        part
        for part in sections
        if any(
            p == path or p.startswith(f"{path}/")
            for p in _section_paths(part.split("\n", 1)[0])
        )
    )


def _section_paths(line: str) -> list[str]:
    """The old and new path of a `diff --git a/<old> b/<new>` LINE; none
    for any other line (the text before the first section)."""
    m = re.match(r"diff --git a/(.*) b/(.*)$", line)
    return [m[1], m[2]] if m else []


def protocol_piece(
    area: Path,
    root: Path | None,
    measured: Measured,
    base: runs.RunDir,
    label: str,
    sources: set[str],
    budget: DiffBudget,
) -> tuple[str, str]:
    """`(label, text)`: every run of MEASURED's protocol (`Measured.runs`
    and the ids only the run index lists), grouped by step, each compared
    with BASE; the runs named in SOURCES marked as sources of the run
    audited. Raises RuntimeError when git fails."""
    assert base.config is not None, "a base whose record reads"
    protocol = bound_protocol_file(area, measured.pid, base.config.protocol.path)
    base_step = step_then(protocol, base, root)
    base_code = code_then(base, root) if root is not None else None
    scope = code_scope(area, root) if root is not None else []
    firsts = {rd.dir.name for group in measured.first_groups for rd in group}
    states = {f.dir.name: f.state for f in measured.run_facts}
    seen = [_seen(protocol, rd, root, states) for rd in measured.runs]
    lines = [
        READING.format(
            base=f"run {base.dir.name}", check=f"{DIFF_CHECK}{base.dir.name}..<run>"
        ),
        "",
        f"Compared with: run {base.dir.name}, its text {base_step.where}; its "
        f"code {base_code.where if base_code else 'not read: no git repository'}.",
    ]
    shown_trees: dict[str, str] = {}
    if base_code is not None and base_code.tree is not None:
        shown_trees[base_code.tree] = base.dir.name
    for heading, group in _grouped(seen):
        lines += ["", heading]
        for run in group:
            lines += _run_lines(
                area,
                root,
                run,
                base,
                base_step,
                base_code,
                scope,
                shown_trees,
                budget,
                firsts=firsts,
                sources=sources,
            )
    if measured.lost:
        lines += ["", "Known only to the run index (deleted, never committed):"]
        lines += [f"- {run_id}: nothing left to read" for run_id in measured.lost]
    return (f"{label}{measured.pid}", "\n".join(lines))


def _seen(
    protocol: Path, rd: runs.RunDir, root: Path | None, states: dict[str, str]
) -> RunSeen:
    """RD as the piece reads it: its state (STATES, run id → state as the
    area state read it) and its step then."""
    if rd.config is None:
        return RunSeen(rd, f"unreadable: {rd.error}", None)
    if rd.from_commit is not None:
        state = f"gone from the tree; commit {rd.from_commit[:12]} holds it"
    else:
        state = states.get(rd.dir.name, "no record")
    return RunSeen(rd, state, step_then(protocol, rd, root))


def _grouped(seen: Iterable[RunSeen]) -> list[tuple[str, list[RunSeen]]]:
    """SEEN grouped under one heading per step, in the order each step
    first appears: runs without a step, each declared step (its id, basis,
    occasion and reason), runs whose step cannot be told."""
    groups: dict[str, list[RunSeen]] = {}
    for run in seen:
        groups.setdefault(_heading(run), []).append(run)
    return list(groups.items())


def _heading(run: RunSeen) -> str:
    """The heading of RUN's step group."""
    if run.step is None:
        return "Runs whose record does not read:"
    if run.step.unknown is not None:
        return f"Step unknown — {run.step.unknown}:"
    step = run.step.step
    if step is None:
        return "No step declared (a first measurement, or a run without a step):"
    return (
        f'Step "{step.id}" on run {step.run} ({step.occasion}): {step.why}'
        + "".join(
            f"\n  declared change: {c.what}: {c.from_} → {c.to}"
            + (f" — {c.why}" if c.why else "")
            for c in step.changes
        )
    )


def _run_lines(
    area: Path,
    root: Path | None,
    run: RunSeen,
    base: runs.RunDir,
    base_step: StepThen,
    base_code: CodeThen | None,
    scope: list[str],
    shown_trees: dict[str, str],
    budget: DiffBudget,
    *,
    firsts: set[str],
    sources: set[str],
) -> list[str]:
    """The lines of one run: what it is, its result, its registration and
    its code against BASE's."""
    rd = run.rd
    name = rd.dir.name
    marks = [run.state]
    if rd.config is not None:
        repeat = rd.config.repeat_of
        marks.append(f"repeat of {repeat}" if repeat else str(rd.config.run_kind))
    if name in firsts:
        marks.append("first measurement")
    if name == base.dir.name:
        marks.append("the run compared with")
    if name in sources:
        marks.append("a source of the run audited")
    out = [f"- {name}: {', '.join(marks)}"]
    out.append(f"    result: {_result(root, rd)}")
    if rd.config is None or name == base.dir.name:
        return out
    out.append(f"    registration: {_registration(run.step, base_step)}")
    if run.state != runs.COMPLETED:
        out.append("    code: not compared — the run did not complete")
        return out
    out += _code_lines(area, root, rd, base, base_code, scope, shown_trees, budget)
    return out


def _result(root: Path | None, rd: runs.RunDir) -> str:
    """RD's metrics.json in one line, cut at RESULT_SHOW_CHARS with the cut
    named; for a run gone from the tree as the commit holding it has it."""
    if rd.from_commit is not None:
        if root is None:
            return "not read: no git repository"
        text = text_at(root, runs.metrics_path(rd.dir), rd.from_commit)
    else:
        text = runs.metrics_text(rd.dir)
    if text is None:
        return "none (no metrics.json)"
    try:
        data = json.loads(text)
        flat = json.dumps(data, sort_keys=True, ensure_ascii=False)
    except json.JSONDecodeError:
        flat = " ".join(text.split())
    if len(flat) <= RESULT_SHOW_CHARS:
        return flat
    return (
        f"{flat[:RESULT_SHOW_CHARS]} … [cut: {len(flat)} characters, the rest "
        f"unread here — runs/{rd.dir.name}/metrics.json holds it]"
    )


def _registration(step: StepThen | None, base_step: StepThen) -> str:
    """How the registration STEP's run saw differs from BASE_STEP's."""
    if step is None or step.text is None:
        return f"not read back — {step.where if step else 'no record'}"
    if base_step.text is None:
        return f"not compared — the compared run's text: {base_step.where}"
    try:
        diffs = registration_differences(base_step.text, step.text)
    except (BlockError, PromiseError) as exc:
        return f"not compared — a text does not read: {exc}"
    if not diffs:
        return f"the same as the compared run's ({step.where})"
    changed = "; ".join(f"{what}: {old!r} → {new!r}" for what, old, new in diffs)
    return f"{step.where}; differs — {changed}"


def _code_lines(
    area: Path,
    root: Path | None,
    rd: runs.RunDir,
    base: runs.RunDir,
    base_code: CodeThen | None,
    scope: list[str],
    shown_trees: dict[str, str],
    budget: DiffBudget,
) -> list[str]:
    """RD's code against BASE's: the same, the same as a run shown before,
    or git's file summary in full and the whole diff as its own RUN DIFF
    piece in BUDGET; past the budget the diff is named not shown in full,
    with an excerpt of DIFF_SHOW_LINES and the rest marked unread."""
    if root is None or base_code is None:
        return ["    code: not compared — no git repository"]
    code = code_then(rd, root)
    if code.tree is None:
        return [f"    code: not read back — {code.where}"]
    if base_code.tree is None:
        return [f"    code ({code.where}): not compared — {base_code.where}"]
    if code.tree in shown_trees:
        return [f"    code ({code.where}): the same as run {shown_trees[code.tree]}'s"]
    shown_trees[code.tree] = rd.dir.name
    try:
        diff = code_difference(root, scope, base_code.tree, code.tree)
    except GitError as exc:
        return [f"    code ({code.where}): not compared — {exc}"]
    if not diff.diff:
        return [f"    code ({code.where}): the same as the compared run's"]
    out = [f"    code ({code.where}), files changed:"]
    out += [f"      {line}" for line in diff.stat.splitlines()]
    label = f"{DIFF_LABEL}{base.dir.name} → {rd.dir.name}"
    asked = budget.asked.get((base.dir.name, rd.dir.name))
    if asked is not None:
        out.append(f"      the whole diff: under {asked}")
        return out
    if len(diff.diff) <= budget.left:
        budget.left -= len(diff.diff)
        budget.pieces.append((label, diff.diff))
        out.append(f"      the whole diff: under {label}")
        return out
    rows = diff.diff.splitlines()
    shown = rows[:DIFF_SHOW_LINES]
    out += [f"      {line}" for line in shown]
    out.append(
        f"      [not shown in full: {len(diff.diff)} characters, past the "
        f"{DIFF_BUDGET} this audit may be shown of all diffs; {len(shown)} of "
        f"{len(rows)} diff lines above, the rest unread — a judgement that "
        f"needs it stays open: ask for it with "
        f"`· check: {DIFF_CHECK}{base.dir.name}..{rd.dir.name}[:<path>]`; "
        f"`{run_diff_command(area, base.dir.name, rd.dir.name)}` prints all for a person]"
    )
    return out
