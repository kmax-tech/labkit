"""run_record_check — the files a finished run read and wrote, held to its record.

Each source's bytes equal to the sha256 the run recorded, and the source
tracked in git or ignored by a rule (`provenance_findings`, `source_drift`);
each registered output the file the run recorded (`output_record_findings`,
`output_drift`). The other checks of a finished run: the code behind its
number in `run_code_check`, the model it asked in `model_check`, the rows it
kept in `row_check`, the numbers it reports in `kept_number_check`. Each
returns findings graded where they are made (`gate.blocker`, a
`GateFinding` warning). Read-only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.commands import (
    checkout_command,
    handover_command,
    measure_anew,
    stage_command,
)
from labkit.formats.gate import (
    GUARANTEED,
    LAB_017,
    LAB_041,
    NOT_EXECUTABLE,
    OPEN_RULE,
    TECHNICAL_RULE,
    WARNING,
    GateFinding,
    blocker,
)
from labkit.formats.repo import (
    git_root,
    ignoring_rules,
    own_path,
    path_kind,
    resolves_under,
    shown,
    tracked,
    tracked_under,
)
from labkit.formats.runs import (
    CONFIG_FILE,
    ArtefactError,
    OutputNow,
    declares_no_inputs,
    read_data,
    read_outputs,
    read_run_config,
    resolve_recorded,
)
from labkit.run.provenance import source_digest, visible_files


def provenance_findings(
    area: Path, answering_run: Path
) -> tuple[list[GateFinding], list[GateFinding], list[str]]:
    """(blockers, warnings, outside) for a run at low repeat cost: every
    source the run read is frozen in its record (`data=`), its bytes now
    are the ones the record's sha256 names, and in the repository git
    holds it — tracked, or kept outside on purpose by an ignore rule; a
    source that lies outside the repository is held by its checksum alone
    (`source_finding`, the standard's Fixed inputs: large or protected
    data stay out of the repository, which holds their source or access
    route and version in Data / scope). OUTSIDE names each source kept out
    of git, by an ignore rule or by lying outside the repository, and a
    run's declaration that it reads no input file (`runs.NO_INPUTS_KEY`).
    Raises GitError when git cannot list a directory source's tracked files or
    say which are ignored (`repo.ignoring_rules`): finalize then ends in that
    error, not in a blocker with a way out that may not lead out. A `data=`
    entry naming no path blocks. Outside a git repository every source is
    still held to its record; git's half is skipped with a warning, a check
    that cannot run and the technical contract. A run that registered no
    output is the technical contract too: the checks that hold an output to
    its run have nothing to hold. An output not yet tracked records an open
    assignment: no rule's sentence states it."""
    sources, blockers = _recorded_sources(area, answering_run)
    warnings: list[GateFinding] = []
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
            GateFinding(
                WARNING,
                "no outputs.json — the run registered no output file (run.output)",
                rule=TECHNICAL_RULE,
                evidence_kind=GUARANTEED,
            )
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
            GateFinding(
                WARNING,
                "not a git repository — cannot tell whether source and output "
                "are committed",
                rule=TECHNICAL_RULE,
                evidence_kind=GUARANTEED,
            )
        )
        return blockers, warnings, outside
    # The output rows are born after the run, so on every first pass they are
    # untracked by construction: a warning that names the command, not a
    # blocker that sends the agent round the loop. LAB-017 The number of
    # audits follows the cost tier names the case ("`finalize` refuses a run … with an output … outside git") and asks
    # for a refusal; this warning holds less than that sentence — a known
    # gap between text and code, its own step in TODO.md.
    # An output that is gone is `output_record_findings`' blocker, on every lane.
    for f in outputs:
        if path_kind(f) is not None and not tracked(repo, f):
            warnings.append(
                GateFinding(
                    WARNING,
                    f"output {f.name} is not yet tracked — `{stage_command(f)}` before "
                    f"the commit that cites the number",
                    rule=LAB_017,
                    evidence_kind=GUARANTEED,
                )
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
                rule=TECHNICAL_RULE,
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
                rule=LAB_041,
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
    owed in Data / scope —, or the ignore rule that keeps it out. Other
    bytes than the run recorded, and a source no ignore rule keeps out of
    git, break LAB-017 The number of audits follows the cost tier (what
    `finalize` refuses at low repeat cost); the rule of a gone source is not
    decided yet (OPEN_RULE)."""
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
                rule=LAB_017,
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
    The directory is resolved first and lies in REPO (`source_finding`
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
        add = stage_command(*loose)
    else:
        add = stage_command(source.path)
    return blocker(
        f"{what} — whether it belongs to the project is left open",
        fix=f"if it is small and may legally be shared, commit it (`{add}`); "
        f"large or protected data stay out of git on purpose: an ignore rule for "
        f"it (a `.gitignore` or `.git/info/exclude`) and its source or access "
        f"route and version in the protocol's Data / scope — finalize then holds "
        f"it to the checksum this run recorded, `sha256 {sha}`",
        rule=LAB_017,
    )


#: the causes `output_drift` tells apart: the run recorded no sha256 for
#: the file (whatever stands at its path now); the file the run recorded
#: with a sha256 is gone; it stands with other bytes
OUTPUT_UNRECORDED = "no sha256 recorded"
OUTPUT_GONE = "gone"
OUTPUT_CHANGED = "changed"


@dataclass(frozen=True)
class OutputDrift:
    """Why the file of a registered output is not the one its run recorded
    (`output_drift`).

    Attributes:
        cause: OUTPUT_UNRECORDED, OUTPUT_GONE or OUTPUT_CHANGED — what a
            way out is chosen by (`output_record_findings`).
        why: The cause as a clause of a message.
    """

    cause: str
    why: str


def output_drift(output: OutputNow) -> OutputDrift | None:
    """Why the file of a registered OUTPUT is not the one the run recorded
    in outputs.json, or None when it is. In this order: the record holds no
    sha256 for it (whatever stands at the path now, there is nothing to
    compare it with; why none was recorded is the record's own note, quoted
    where it has one — the missing field alone does not show that the run
    ended without the file), the file is gone, or its sha256 now differs
    from the record. The record is the run's, taken
    after the run (`runlog.Run._finalize`); the tree at check time is only
    compared, never trusted."""
    recorded = output.entry.sha256
    if recorded is None:
        noted = (
            f'; the record notes: "{output.entry.note}"' if output.entry.note else ""
        )
        return OutputDrift(
            OUTPUT_UNRECORDED, f"outputs.json records no sha256 for it{noted}"
        )
    if not output.stands:
        return OutputDrift(OUTPUT_GONE, "the file is gone")
    assert output.sha256 is not None, "output_now hashes a standing recorded file"
    if not output.sha256.startswith(recorded):
        return OutputDrift(
            OUTPUT_CHANGED,
            f"its sha256 {output.sha256[: len(recorded)]} is not the recorded "
            f"{recorded}",
        )
    return None


def _output_way_out(output: OutputNow, drift: OutputDrift, area: Path) -> str:
    """The way out of a registered OUTPUT of AREA's run that is not the
    recorded file (DRIFT). Every cause: measure anew. A gone file may also
    be restored, held to the recorded sha256 by the next check — and said
    as what it is: the bytes of that run, without whatever was written to
    the file after it. A file that stands with other bytes gets no
    restoring way out: it would overwrite what stands there."""
    if drift.cause == OUTPUT_GONE:  # gone, and a sha256 to hold a restored file to
        return (
            f"{measure_anew(area)}; or restore the file from a commit or a copy "
            f"that holds the bytes the run recorded (sha256 {output.entry.sha256}) — "
            f"this check then holds it to that checksum, and rows written to the "
            f"file after the run are not in those bytes"
        )
    return measure_anew(area)


def output_record_findings(
    outputs: Sequence[OutputNow], run_id: str, area: Path
) -> list[GateFinding]:
    """A blocker per registered output of the run RUN_ID of AREA whose file
    is not the one the run recorded (`output_drift`, OUTPUTS as
    `runs.outputs_now` gives them): the number's rows, and a deliverable
    the run wrote for an external task, are pinned to the run by path and
    sha256 — a file swapped, edited or removed after the run is no longer
    what the run produced. The way out follows the cause
    (`_output_way_out`), and so do the basis and the outcome: without a
    recorded sha256, or without the file, the comparison cannot run — the
    technical contract, a check not executable, which states neither that
    the bytes changed nor that a format duty was broken (runlog itself
    records an output absent at the end of the run without a sha256);
    other bytes than the recorded are a deviation whose rule is an open
    assignment. [] when every file is as recorded."""
    out = []
    for o in outputs:
        drift = output_drift(o)
        if drift is None:
            continue
        compared = drift.cause == OUTPUT_CHANGED
        out.append(
            blocker(
                f"{o.entry.path}: not the file run {run_id} recorded — {drift.why}",
                fix=_output_way_out(o, drift, area),
                stated_outcome=None if compared else NOT_EXECUTABLE,
                rule=OPEN_RULE if compared else TECHNICAL_RULE,
            )
        )
    return out


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
        rule=TECHNICAL_RULE,
    )
