"""model_check — the model a finished run asked, held to its record.

A model that answered named in the record: each line of the run's call log
backed by a record naming its alias — the run's own, or that of the run
that stored the answer (`call_log_model_findings`,
`model_provenance_findings`); answers that are stand-ins, not a model's,
named (`stand_in_findings`, counted by `stand_in_calls`); a single draw
where a model was asked (`single_draw`); every arm the protocol names
present in the answering run (`arm_findings`). Each returns findings
graded where they are made. Read-only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import protocol_block
from labkit.formats.answering_run import repeats_of
from labkit.formats.commands import checkout_command, measure_anew
from labkit.formats.gate import (
    GUARANTEED,
    LAB_027,
    LAB_036,
    OPEN_RULE,
    TECHNICAL_RULE,
    WARNING,
    GateFinding,
    blocker,
    outcome_of_failed_read,
)
from labkit.formats.repo import git_root, path_kind
from labkit.formats.runs import (
    CONFIG_FILE,
    DERIVED_RUN_CONTRACT,
    LLM_CALLS_FILE,
    ModelCall,
    RunConfigError,
    metrics_path,
    model_provenance_run,
    read_metrics,
    read_model_calls,
    read_run_config,
    run_dir_in_lab,
    source_runs,
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


def single_draw(area: Path, answering_run: Path) -> GateFinding | None:
    """Why the number shows no spread, or None: the run asked a model and
    has no repeat (`runlog` repeat_of). One draw per item cannot show how
    far the number moves — LAB-036 Validate, don't trust a single run. A
    warning, never a blocker: whether a spread is owed is the protocol's.
    A run in the area that cannot say whether it is a draw (unreadable, a
    broken or doubled draw number) is said here, not raised past: a record
    that does not read, the technical contract."""
    if not called_a_model(answering_run):
        return None
    try:
        if repeats_of(area, answering_run.name):
            return None
    except RunConfigError as exc:
        return GateFinding(
            WARNING,
            f"the draws of {answering_run.name} cannot be counted: {exc}",
            rule=TECHNICAL_RULE,
            evidence_kind=GUARANTEED,
        )
    return GateFinding(
        WARNING,
        f"{answering_run.name} is one draw — no spread: `scripts/01_measure.py "
        f"--repeat-of {answering_run.name}` draws it again, `02_analyze.py "
        f"--draws` shows how far the number moves",
        rule=LAB_036,
        evidence_kind=GUARANTEED,
    )


@dataclass(frozen=True)
class StoringRun:
    """The record of a run that stored a cached answer another run read,
    as the station found it: its MODELS_RESOLVED, or — None there — the
    clause UNREAD saying why it could not be read, worded to follow "but"
    in a finding (`no run … is in this area or another area of the lab`,
    `run … has no config.json`, `the record of run … does not read (…)`)."""

    models_resolved: Mapping[str, object] | None
    unread: str | None


def call_log_model_findings(
    run: str,
    calls: Sequence[ModelCall],
    models_resolved: Mapping[str, object],
    *,
    derived_from: str | None,
    storing_runs: Mapping[str, StoringRun],
) -> list[GateFinding]:
    """Whether RUN's call-log lines agree with the model records — LAB-027
    Model discipline, guaranteed: the call log is labkit's own record
    (`runs.read_model_calls`), so the comparison is exact. What it proves
    is that every line the log holds is backed by a record naming its
    alias; not that every answer the run used was logged (a framework that
    replays past labkit's cache leaves no line), and not that a model gave
    the answer: a record that names the alias backs any line of it, also
    an answer stored outside any run without the stand-in mark (a
    hand-written entry), of which nothing shows that a model gave it. Only
    marked stand-ins are told apart (`stand_in_findings`).

    A line is backed by a record that names its alias, a key of a
    `models_resolved`, tried in this order:
      1. RUN's own (MODELS_RESOLVED; not its lineage's — the calls were
         made in this run), for any line;
      2. otherwise, for a hit stored by a run (`origin.run` set), that
         run's record (STORING_RUNS by run id, built by the caller for
         every origin run of CALLS): it says which model gave the stored
         answer.
    A line nothing backs blocks, one blocker per alias and origin: a call
    that asked the model or an answer stored outside any run without the
    alias in RUN's record; a stored answer whose run is not found, does
    not read, or names other aliases. A run with DERIVED_FROM set has no
    record of its own (runlog writes none, `provenance.record_provenance`)
    and by its contract makes no model calls (DERIVED_RUN_CONTRACT, the
    README's "derived run"): its calls that asked the model block, and so
    do answers stored outside any run; only replayed answers whose storing
    run names the alias pass. [] for a run without calls and for one whose
    every line is backed. A record's value, a resolved spec or an
    `unresolved: …` string, is not judged.

    Raises:
        ValueError: An origin run of CALLS missing from STORING_RUNS — the
            caller's contract.
    """
    # by alias and the run that stored the answers: None for the lines only
    # RUN's own record can back (asked, or stored outside any run)
    unbacked: dict[tuple[str, str | None], list[ModelCall]] = {}
    for call in calls:
        if call.alias in models_resolved and derived_from is None:
            continue
        if call.hit and call.origin_run is not None:
            if call.origin_run not in storing_runs:
                raise ValueError(
                    f"call_log_model_findings: no record given for origin run "
                    f"{call.origin_run}"
                )
            stored_by = storing_runs[call.origin_run]
            if (
                stored_by.models_resolved is not None
                and call.alias in stored_by.models_resolved
            ):
                continue
            unbacked.setdefault((call.alias, call.origin_run), []).append(call)
        else:
            unbacked.setdefault((call.alias, None), []).append(call)
    findings: list[GateFinding] = []
    for (alias, origin), lines in unbacked.items():
        if origin is not None:
            findings.append(
                _stored_answer_unbacked(
                    run, alias, origin, storing_runs[origin], len(lines), derived_from
                )
            )
        elif derived_from is not None:
            findings += _derived_run_calls(run, alias, derived_from, lines)
        else:
            findings.append(_own_record_unbacked(run, alias, lines))
    return findings


def _answers(n: int) -> str:
    """`1 answer`, `N answers`."""
    return f"{n} answer{'s' if n != 1 else ''}"


def _name_alias_fix(alias: str) -> str:
    """The way out where the run's own record must name ALIAS."""
    return (
        f"put the alias in this run's config under `model` or `<name>_model` "
        f"(`runlog.run(config={{'model': '{alias}'}})`; runlog resolves it into "
        f"models_resolved) and run again"
    )


def _fresh_run_fix(alias: str, parent: str | None) -> str:
    """The way out for a derived run that needed a model: a fresh run, or —
    with PARENT — replaying only answers stored by a run whose record names
    ALIAS (what `call_log_model_findings` passes), the parent among them
    when its record names it."""
    fresh = (
        f"ask the model in a fresh run — `runlog.run(config={{'model': "
        f"'{alias}'}})` without `derived_from`"
    )
    return (
        fresh
        if parent is None
        else f"{fresh} — or let this run only replay answers stored by a run "
        f"whose record names `{alias}`, such as its parent {parent} if its "
        f"record names it"
    )


def _kinds_of_lines(lines: list[ModelCall]) -> str:
    """LINES counted by kind, three disjoint counts: asked the model,
    stand-ins, and hits stored outside any run without the stand-in mark —
    `1 asked the model, 2 stand-ins, 1 not marked as a stand-in`."""
    asked = sum(not c.hit for c in lines)
    stand_ins = sum(c.hit and c.stand_in for c in lines)
    other = len(lines) - asked - stand_ins
    parts = [f"{asked} asked the model"] if asked else []
    if stand_ins:
        parts.append(f"{stand_ins} stand-in{'s' if stand_ins != 1 else ''}")
    if other:
        parts.append(
            f"{other} stored outside any run, not marked as "
            f"{'a stand-in' if other == 1 else 'stand-ins'}"
        )
    return ", ".join(parts)


def _stand_ins_among(stored: list[ModelCall]) -> str:
    """` (2 of them stand-ins)` for the stand-ins among STORED, "" for none."""
    n = sum(c.stand_in for c in stored)
    if not n:
        return ""
    if len(stored) == 1:
        return " (a stand-in)"
    return f" ({n} of them {'a stand-in' if n == 1 else 'stand-ins'})"


def _own_record_unbacked(run: str, alias: str, lines: list[ModelCall]) -> GateFinding:
    """RUN's asked calls, stand-ins and other answers stored outside any
    run of ALIAS that its own models_resolved does not name
    (`call_log_model_findings`)."""
    return blocker(
        f"{run}'s call log holds {_answers(len(lines))} of alias `{alias}` "
        f"({_kinds_of_lines(lines)}), but its models_resolved does not name "
        f"`{alias}` — no record says which model the alias stood for",
        fix=_name_alias_fix(alias),
        rule=LAB_027,
    )


def _derived_run_calls(
    run: str, alias: str, parent: str, lines: list[ModelCall]
) -> list[GateFinding]:
    """A derived RUN's calls of ALIAS that asked the model, and its answers
    stored outside any run (stand-ins among them): a blocker each
    (`call_log_model_findings`)."""
    asked = sum(not c.hit for c in lines)
    stored = [c for c in lines if c.hit]
    head = f"{run} is a derived run (derived_from {parent}), and {DERIVED_RUN_CONTRACT}"
    out = []
    if asked:
        out.append(
            blocker(
                f"{head} — yet its call log holds {asked} call"
                f"{'s' if asked != 1 else ''} of alias `{alias}` that asked the model",
                fix=_fresh_run_fix(alias, parent),
                rule=LAB_027,
            )
        )
    if stored:
        out.append(
            blocker(
                f"{head} — yet its call log holds {_answers(len(stored))} of alias "
                f"`{alias}` stored outside any run{_stand_ins_among(stored)}, "
                f"which no record names a model for",
                fix=_fresh_run_fix(alias, parent),
                rule=LAB_027,
            )
        )
    return out


def _stored_answer_unbacked(
    run: str,
    alias: str,
    origin: str,
    stored_by: StoringRun,
    n: int,
    derived_from: str | None,
) -> GateFinding:
    """RUN's answers of ALIAS stored by run ORIGIN that ORIGIN's record does
    not back — not found, unreadable, or naming other aliases
    (`call_log_model_findings`)."""
    if stored_by.models_resolved is None:
        why = stored_by.unread
        repair = f"restore the record of run {origin} if it was lost, or "
    else:
        named = ", ".join(f"`{a}`" for a in sorted(stored_by.models_resolved))
        why = f"the models_resolved of run {origin} names {named or 'no alias'}, not `{alias}`"
        repair = f"replay answers of a run whose record names `{alias}`, or "
    return blocker(
        f"{run}'s call log holds {_answers(n)} of alias `{alias}` stored by run "
        f"{origin}, but {why} — no record says which model gave "
        f"{'it' if n == 1 else 'them'}",
        fix=repair
        + (
            _fresh_run_fix(alias, None)
            if derived_from is not None
            else _name_alias_fix(alias)
        ),
        rule=LAB_027,
    )


def storing_runs_of(area: Path, calls: Sequence[ModelCall]) -> dict[str, StoringRun]:
    """The record of every run that stored a hit of CALLS (`origin.run`),
    by run id, found in AREA or another experiment area of its lab
    (`runs.run_dir_in_lab`): its models_resolved, or why it could not be
    read. Read-only."""
    out: dict[str, StoringRun] = {}
    for run_id in sorted({c.origin_run for c in calls if c.origin_run is not None}):
        found = run_dir_in_lab(area, run_id)
        if found is None:
            out[run_id] = StoringRun(
                None, f"no run {run_id} is in this area or another area of the lab"
            )
            continue
        try:
            cfg = read_run_config(found)
        except RunConfigError as exc:
            out[run_id] = StoringRun(
                None, f"the record of run {run_id} does not read ({exc})"
            )
            continue
        out[run_id] = (
            StoringRun(None, f"run {run_id} has no config.json ({found})")
            if cfg is None
            else StoringRun(cfg.models_resolved, None)
        )
    return out


@dataclass(frozen=True)
class StandInUse:
    """How many of the call-log lines of one ALIAS are stand-ins: STAND_INS
    lines marked as stand-ins, of LINES lines of that alias in all —
    asked, replayed or stand-in. Lines, not distinct answers: what a
    framework replays past labkit's cache leaves no line and is not
    counted."""

    alias: str
    stand_ins: int
    lines: int

    @property
    def only_stand_ins(self) -> bool:
        """Every logged line of the alias is a marked stand-in."""
        return self.stand_ins == self.lines


def stand_in_uses(calls: Sequence[ModelCall]) -> list[StandInUse]:
    """One StandInUse per alias of CALLS with at least one marked stand-in
    (`ModelCall.stand_in`), aliases sorted; [] without stand-ins. Sees only
    marked stand-ins: an entry written by hand without the mark counts as
    an answer not marked as a stand-in, which shows no more than that. Pure."""
    stand_ins: dict[str, int] = {}
    lines: dict[str, int] = {}
    for call in calls:
        lines[call.alias] = lines.get(call.alias, 0) + 1
        if call.hit and call.stand_in:
            stand_ins[call.alias] = stand_ins.get(call.alias, 0) + 1
    return [StandInUse(a, n, lines[a]) for a, n in sorted(stand_ins.items())]


@dataclass(frozen=True)
class StandInCalls:
    """The call-log lines the stand-in warning and the result label count:
    OWN, the run's own; SOURCES, those of every run it rests on
    (`runs.source_runs` past the run itself: `derived_from`, continued
    rows, the origin runs of its inputs)."""

    own: list[ModelCall]
    sources: list[ModelCall]


def stand_in_calls(run_dir: Path) -> StandInCalls:
    """RUN_DIR's StandInCalls, read from the call logs
    (`runs.read_model_calls`) of RUN_DIR and of `runs.source_runs`. The one
    provenance read behind finalize's warning (`stand_in_findings`) and the
    result label (`result_render.stand_in_label`).

    Raises:
        ValueError: From `runs.source_runs` or `runs.read_model_calls` — a
            record on the way that does not read, a source run missing.
        OSError: A call log that cannot be opened.
    """
    own, *rest = source_runs(run_dir)
    return StandInCalls(
        read_model_calls(own), [c for run in rest for c in read_model_calls(run)]
    )


def logged_uses(n: int) -> str:
    """`1 logged use`, `N logged uses` — the count of call-log lines marked
    as stand-ins, which need not be distinct answers: a stand-in two runs
    read is logged twice."""
    return f"{n} logged use{'s' if n != 1 else ''}"


#: how the warning names the runs a run rests on (`runs.source_runs`)
SOURCE_RUNS = "the runs it rests on (derived_from, continued rows, input origins)"


def stand_in_findings(
    run: str, own: Sequence[ModelCall], sources: Sequence[ModelCall]
) -> list[GateFinding]:
    """A warning when the call-log lines OWN (RUN's) or SOURCES (the runs
    it rests on; both as `stand_in_calls` reads them) hold stand-ins —
    fixed answers stored with `llm_cache.store_stand_in`, not answers of a
    model: the run's numbers show what its processing does with those
    answers, not what a model answers (LAB-027 Model discipline).
    Guaranteed: the mark is in labkit's own call logs. One warning naming
    each alias with its logged uses (`stand_in_uses`, `logged_uses`), RUN's
    own apart from those of the runs it rests on, so the latter do not read
    as calls of RUN; [] without stand-ins. The same lines, counted
    together, make the result label (`result_render.stand_in_label`).
    Sees only marked stand-ins: an entry written by hand without the mark
    reads as an answer stored outside any run (`call_log_model_findings`)."""
    mine, theirs = stand_in_uses(own), stand_in_uses(sources)
    if not mine and not theirs:
        return []

    def named(uses: list[StandInUse]) -> str:
        return ", ".join(
            f"{logged_uses(u.stand_ins)} of alias `{u.alias}`" for u in uses
        )

    head = (
        f"{run} read stand-in answers ({named(mine)})"
        if mine
        else (f"{run} read no stand-in itself")
    )
    if theirs:
        logged = "logged more" if mine else "logged stand-in answers"
        head += (
            f"; {SOURCE_RUNS} {logged} ({named(theirs)}) — uses those runs "
            f"logged, not calls of {run}"
        )
    return [
        GateFinding(
            WARNING,
            f"{head}: fixed answers stored with `llm_cache.store_stand_in`, not "
            f"answers of a model — its numbers show what the processing does "
            f"with them, not what a model answers",
            rule=LAB_027,
            evidence_kind=GUARANTEED,
        )
    ]


def model_provenance_findings(area: Path, answering_run: Path) -> list[GateFinding]:
    """Where the run's model record and its calls disagree, each a finding,
    and a warning when the run read stand-ins; [] when they agree or nothing
    is owed, and no stand-in was read. Read in this order:

      1. the call log (`runs.read_model_calls`) against the model records
         that can vouch for each line — the run's own `models_resolved`
         (not its lineage's) and, for a stored answer, the record of the
         run that stored it, looked up in AREA's lab (`storing_runs_of`):
         `call_log_model_findings`, blockers.
         A log that does not read, or a run without config.json, blocks:
         the check could not run — technical contract;
      2. only without a finding from 1, the metrics: `llm_retries`
         recorded, or `model_calls` > 0, while no run in the lineage
         recorded `models_resolved` — a warning (LAB-027 Model discipline):
         the alias was not under `model`/`*_model`, the keys runlog
         resolves (one recorded as `judge` is not resolved). A lineage that
         does not read is the technical contract, a warning too;
      3. stand-ins in the call logs of the run and of the runs it rests
         on (`stand_in_calls`), a warning after those of 1 or 2
         (`stand_in_findings`); a record on the way that does not read is
         a warning — its own station holds it, and the result line is not
         rendered without the count.
    Its limit: only what the call log and the metrics hold is compared; a
    run that called a model past labkit's cache and writes neither metrics
    key is not seen."""
    try:
        calls = read_model_calls(answering_run)
    except (OSError, ValueError) as exc:
        return [
            blocker(
                f"model provenance: the call log of {answering_run.name} does not "
                f"read — {exc}",
                fix=f"restore the file as the cache wrote it (`"
                f"{checkout_command(answering_run / LLM_CALLS_FILE)}` where git holds "
                f"it), or {measure_anew(area)}",
                stated_outcome=outcome_of_failed_read(exc),
                rule=TECHNICAL_RULE,
            )
        ]
    cfg = read_run_config(answering_run)
    if cfg is None:
        # the answering run is a completed run, so this is a damaged run
        # directory, not a run that named no model
        return [
            blocker(
                f"model provenance: {answering_run.name} has no config.json — "
                f"which model it recorded cannot be read",
                fix=f"restore the run record as runlog wrote it (`"
                f"{checkout_command(answering_run / CONFIG_FILE)}` where git holds "
                f"it), or {measure_anew(area)}",
                rule=TECHNICAL_RULE,
            )
        ]
    # this run's own models_resolved, not its lineage's: the calls in its
    # call log were made in this run
    gaps = call_log_model_findings(
        answering_run.name,
        calls,
        cfg.models_resolved,
        derived_from=cfg.derived_from,
        storing_runs=storing_runs_of(area, calls),
    )
    try:
        read = stand_in_calls(answering_run)
    except (OSError, ValueError) as exc:
        # a warning, not a blocker: the record that does not read is held
        # by the station of its own path (input origins, the lineage, the
        # call log above), and report-check's rendering of the result line
        # refuses without the count (`result_render.stand_in_label`)
        stand_ins = [
            GateFinding(
                WARNING,
                f"model provenance: the stand-ins behind {answering_run.name} "
                f"cannot be counted — {exc}; the result line cannot be rendered "
                f"until this record reads",
                fix=f"restore the named record as runlog wrote it, or "
                f"{measure_anew(area)}",
                rule=TECHNICAL_RULE,
                evidence_kind=GUARANTEED,
            )
        ]
    else:
        stand_ins = stand_in_findings(answering_run.name, read.own, read.sources)
    if gaps:
        return gaps + stand_ins
    return _metrics_model_findings(answering_run) + stand_ins


def _metrics_model_findings(answering_run: Path) -> list[GateFinding]:
    """Step 2 of `model_provenance_findings`: a warning when the metrics
    show model calls (`called_a_model`) and no run in the lineage recorded
    models_resolved, or when the lineage does not read; [] otherwise."""
    if not called_a_model(answering_run):
        return []
    try:
        if model_provenance_run(answering_run) is not None:
            return []
    except ValueError as exc:
        return [
            GateFinding(
                WARNING,
                f"model provenance: the lineage of {answering_run.name} is broken — {exc}",
                rule=TECHNICAL_RULE,
                evidence_kind=GUARANTEED,
            )
        ]
    return [
        GateFinding(
            WARNING,
            f"{answering_run.name} called a model, but no run in its lineage recorded "
            f"models_resolved — record the alias under `model` (runlog resolves it); "
            f"a spec under another key is not provenance labkit can hold",
            rule=LAB_027,
            evidence_kind=GUARANTEED,
        )
    ]


def arm_findings(text: str, area: Path, answering_run: Path) -> list[GateFinding]:
    """Warnings: every arm the head declares (`[model.arms.<arm>]`: profile,
    fingerprint, alias — `protocol_block.model`) is held to the answering
    run — the profile file exists in the repo, and fingerprint and alias
    stand somewhere in the run's config.json. The table is what a reader of
    the protocol gets instead of opening the register. No arms, no `[model]`, or a
    head that does not read (the head check names that): nothing claimed,
    nothing checked. Each warning records the rule of its cause: an alias
    the run did not record LAB-027 Model discipline, a profile file that is
    not there the technical contract (a reference that leads nowhere), a
    fingerprint the run did not record open."""
    out: list[GateFinding] = []
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
                GateFinding(
                    WARNING,
                    f"arm `{arm}`: the protocol names {a.profile}, no such file "
                    f"under {root}",
                    rule=TECHNICAL_RULE,
                    evidence_kind=GUARANTEED,
                )
            )
        if a.fingerprint not in recorded:
            out.append(
                GateFinding(
                    WARNING,
                    f"arm `{arm}`: the protocol names fingerprint {a.fingerprint}, the "
                    f"answering run recorded no such value — the profile changed after the "
                    f"stamp, or the run did not record its fingerprints",
                    rule=OPEN_RULE,
                    evidence_kind=GUARANTEED,
                )
            )
        if a.alias and a.alias not in recorded:
            out.append(
                GateFinding(
                    WARNING,
                    f"arm `{arm}`: the protocol names alias {a.alias}, the answering run "
                    f"recorded no such alias",
                    rule=LAB_027,
                    evidence_kind=GUARANTEED,
                )
            )
    return out
