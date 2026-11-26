"""result_render — the result section as its bound sources render it.

The Recorded results line and the Limitation lines are generated. Where the
run or a run it rests on read stand-in answers (`llm_cache.store_stand_in`,
marked in the call logs), Recorded results opens with one label per alias
(`stand_in_label`): `fixed stand-in answers: 2 logged uses of alias X; not a
measurement of X`, or `includes fixed stand-in answers: …; not a pure
model measurement` beside other answers of X; a run without stand-ins gets
no label. Recorded results then gives the reportable verdict of every registered promise
(`verdicts`, one derivation for every reader): a quality check recorded
as not met leaves every criterion not assessable, so a criterion's own
`True` never reads as a pass beside it; a limitation leaves not
assessable exactly the promises it names, a criterion it does not name
keeping its recorded verdict. The declared run's other
reported keys follow as recorded values — descriptive; the registered
promises' keys stay in `metrics.json`, unchanged, and are not repeated as
values —, a computation's kept number first, named with its unit
(`kept number: HRV_MeanNN = 694.07 ms; also recorded: …`, `kept_phrase`;
the head's `[kept]`), then, for a computation whose head registers a `[reference]`,
the comparison as the run recorded it (`reference 0.62 ± 0.01 (within):
not met, distance 0.145`, or `not comparable: <key> absent` — never a
"met" the run did not record; `comparison_phrase`), then the run id and
one note on the limits, then, for a run that computes from other runs'
outputs, one source per origin run of its inputs, its values as that run
recorded them under the text it was measured under (`source_phrases`; no
verdict of its own). Each Limitation line comes
from a finding decided limitation in the analysis records covering
that run (`audit_binding.covering_analysis`). `protocol-fill --from-run`
writes them, `--render` writes them again, and report-check holds the
protocol to exactly this rendering (`render_gaps`): a generated line that
differs from its sources is a blocker, whatever it says — exact, and
silent on whether a limit is enough (the audit's question). The Summary's
Conclusion and the rest of the prose stay the author's.

    r = result_render.rendering(area, text, run, found=held.reviews)  # what the text should say
    result_render.render_gaps(text, r)              # [] when it says exactly that
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from labkit.checks.audit_binding import (
    AuditError,
    covering_analysis,
    source_protocol_then,
)
from labkit.checks.recheck import LABKIT_KEYS
from labkit.checks.run_record_check import (
    StandInUse,
    logged_uses,
    stand_in_calls,
    stand_in_uses,
)
from labkit.formats import (
    evidence,
    finding_limits,
    promises,
    protocol_block,
    reference,
    reviews,
    runs,
)
from labkit.formats.answering_run import first_registrations
from labkit.formats.area_state import AreaState, state_of
from labkit.formats.gate import TECHNICAL_RULE
from labkit.formats.gate import LAB_011, LAB_015
from labkit.formats.gate import GateFinding, blocker
from labkit.formats.commands import render_command
from labkit.formats.repo import git_root
from labkit.formats.answer_reading import read_answer_reading
from labkit.formats.protocol_check import (
    display_label,
    CONCLUSION_LABEL,
    QUESTION_LABEL,
    RECORDED_RESULTS_LABEL,
    fields,
    recorded_results_field,
    written_line,
)


@dataclass(frozen=True)
class Rendering:
    """What the result section says when it says what its sources say."""

    recorded_results: str  # the Recorded results line's value
    limits: tuple[tuple[str, str], ...]  # (label, value) per limit, in record order
    # the registered question and the author's Conclusion — no recorded
    # verdict —, each on one line, None while not written
    # (`protocol_check.written_line`): the result block shows them verbatim
    # and refuses without them (`report_blocks.block_body`)
    question: str | None
    conclusion: str | None


def kept_phrase(key: str, value: object, unit: str) -> str:
    """`kept number: KEY = VALUE UNIT` — the kept number as the Recorded
    results line opens with it, VALUE written as the run recorded it (as
    `recheck.plain_numbers` writes it); a dimensionless UNIT
    (`protocol_block.DIMENSIONLESS`) writes no unit."""
    suffix = "" if unit == protocol_block.DIMENSIONLESS else f" {unit}"
    return f"kept number: {key} = {value}{suffix}"


def recorded_results_line(
    metrics: dict,
    run_id: str,
    verdict_keys: frozenset[str] = frozenset(),
    comparison: str = "",
    kept: protocol_block.Kept | None = None,
) -> str:
    """`key = value, …; reference … (run <id>)` — every reported key and
    value as the run recorded them but the registered promises' keys
    (VERDICT_KEYS, read as `verdicts`) and the reference verdict's
    (`reference.VERDICT_KEYS`, read as COMPARISON: the phrase of the
    comparison with a stated value, `reference.phrase`, "" without one),
    so `recheck.cited` finds each number and the run id. With KEPT, a
    computation's `[kept]` whose key the run recorded, its value comes first
    (`kept_phrase`) and the rest follows as `also recorded: …`; without it
    (a fit, an apply, or a `[kept]` the run does not hold — finalize names
    that) the values stand in the run's order."""
    rest = {
        k: v
        for k, v in metrics.items()
        if k not in LABKIT_KEYS
        and k not in verdict_keys
        and k not in reference.VERDICT_KEYS
    }
    body = ", ".join(f"{k} = {v}" for k, v in rest.items())
    if (
        kept is not None
        and kept.key is not None
        and kept.unit is not None
        and kept.key in rest
    ):
        first = kept_phrase(kept.key, rest.pop(kept.key), kept.unit)
        also = ", ".join(f"{k} = {v}" for k, v in rest.items())
        body = f"{first}; also recorded: {also}" if also else first
    if comparison:
        body = f"{body}; {comparison}" if body else comparison
    return f"{body} (run {run_id})" if body else f"(run {run_id})"


def comparison_phrase(text: str, metrics: dict) -> str:
    """The comparison with the stated value TEXT's head registers
    (`[reference]`, on the `[kept]` key), as METRICS recorded its verdict
    (`reference.phrase`), or "": no table, a table that does not read, no
    kept key, no verdict recorded, or one that does not read — finalize
    names each of those (`reference.comparison_gaps`); the rendering shows
    what can be shown."""
    try:
        ref = protocol_block.reference(text)
        if ref is None or reference.STATE_KEY not in metrics:
            return ""
        key = protocol_block.kept_key(text)
    except protocol_block.BlockError:
        return ""
    try:
        return reference.phrase(metrics, ref, key)
    except ValueError:
        return ""


def kept_of(text: str) -> protocol_block.Kept | None:
    """TEXT's `[kept]` for the rendering, None where the head carries none
    or it does not read — protocol-check and finalize name that."""
    try:
        return protocol_block.kept(text)
    except protocol_block.BlockError:
        return None


def verdicts(
    block: promises.PromiseTables, metrics: dict, unjudged: dict[str, str]
) -> list[str]:
    """The reportable verdict of every promise of BLOCK, in its order, one
    phrase each, from the run's METRICS read through each promise's key and
    UNJUDGED (an id a limitation leaves not assessable → that limit's
    label). A quality check recorded as not met voids every criterion (each
    `[quality-check-…]` says why its failure voids the verdict): each
    criterion reads `not assessable`, with why — also where a limitation
    names that check, since a limit hides verdicts and never restores one.
    A limitation leaves not assessable only the promises it names: a
    quality check it names reads not assessable, the criteria it does not
    name read `met` or `missed` as recorded, unless a quality check is
    recorded as not met (LAB-015 Preflight audit before freezing states a
    decision's effect, standard 0.31). A key not recorded as true or false gives no
    verdict and says so — intent-check holds that run. A branch reads as
    recorded. Pure; the run's metrics are never changed."""
    blocked = [
        f"{p.id} not met"
        for p in block.promises
        if p.kind == "quality-check" and metrics.get(p.key) is False
    ]
    return [_verdict(p, metrics.get(p.key), unjudged, blocked) for p in block.promises]


def left_unjudged(
    block: promises.PromiseTables, effect: str, metrics: dict | None
) -> str:
    """What a limitation's EFFECT (`<ID>[, <ID>] not assessable`) leaves
    unjudged under BLOCK, by the rule `verdicts` applies — exactly the
    promises it names, a criterion beside a named quality check only when
    named too —, each with its verdict as METRICS (the run's, None: not
    read) record it, in the block's order: `criterion-1 (recorded as
    missed), quality-check-2 (recorded as met)`. What a decision reviewer
    confirms, promise by promise, the fault prevents judging. A criterion a
    quality check recorded as not met voids is not listed unless named: that
    void follows from the run, not from the decision, and is not reviewed. "" for an
    effect that names no promise (`stands`, or none). Pure."""
    if not finding_limits.leaves_unjudged(effect):
        return ""
    ids = set(finding_limits.effect_ids(effect))
    left = [p for p in block.promises if p.id in ids]

    def recorded(p: promises.Promise) -> str:
        value = None if metrics is None else metrics.get(p.key)
        if not isinstance(value, bool):
            return "not recorded as true or false"
        return "recorded as " + _verdict(p, value, {}, []).removeprefix(f"{p.id} ")

    return ", ".join(f"{p.id} ({recorded(p)})" for p in left)


def _verdict(
    p: promises.Promise, value: object, unjudged: dict[str, str], blocked: list[str]
) -> str:
    """`verdicts` for one promise P, its recorded VALUE; BLOCKED the
    quality checks recorded as not met, which leave a criterion unjudged."""
    if p.kind == "branch":
        return f"{p.id} {value}"
    if p.id in unjudged:
        return f"{p.id} not assessable ({unjudged[p.id]})"
    if p.kind == "criterion" and blocked:
        return f"{p.id} not assessable — {', '.join(blocked)}"
    if value is True:
        return f"{p.id} met"
    if value is False:
        return f"{p.id} {'missed' if p.kind == 'criterion' else 'not met'}"
    return f"{p.id}: no verdict — `{p.key}` not recorded as true or false"


def limits_of(
    area: Path, text: str, run: Path, *, found: Sequence[reviews.Review]
) -> list[tuple[str, str, str]]:
    """(label, value, effect) of every limit with its effect decided — an
    BLOCKER or WARNING decided limitation — in the analysis
    records covering RUN; EFFECT is "" for a lifted one. An effect a
    decision review among FOUND did not uphold as decided and claimed now
    — rejected, insufficient, or draws that disagree (`reviews.contested`)
    — reads as proposed, not confirmed (`finding_limits.UNCONFIRMED`), and an
    `<ID> not assessable` among them is lifted: given as "", so the
    verdicts read as the run recorded them; not confirmed, it does not
    hide a miss. An unreviewed or upheld one reads as its
    effect — report-check holds the unreviewed one at its grade
    (`report_decisions.check_limits_upheld`). FOUND: AREA's decision reviews
    (`evidence.AreaEvidence.reviews`). An area the gate cannot hold to that run gives
    none here: report-check names why (`analysis_audit_gap`)."""
    try:
        records = covering_analysis(area, text, run)
    except (AuditError, FileNotFoundError, ValueError):
        return []
    out: list[tuple[str, str, str]] = []
    for r in records:
        for n, f in r.limits():
            if not f.effect:
                continue
            contested = reviews.contested(r, n, list(found), text)
            # a `not assessable` no review upheld voids no verdict: the miss stands
            lifted = contested and finding_limits.leaves_unjudged(f.effect)
            effect = "" if lifted else f.effect
            out.append(
                (
                    finding_limits.limit_label(r, n),
                    finding_limits.limit_line(f, contested=contested),
                    effect,
                )
            )
    return out


def rendering(
    area: Path, text: str, run: Path, *, found: Sequence[reviews.Review]
) -> Rendering:
    """The result section of TEXT as RUN's `metrics.json`, the covering
    records and AREA's decision reviews FOUND render it (`limits_of`). A
    protocol that replaces another (`[replaces]`)
    opens with the predecessor's verdict as its own sources give it, then
    `this question:` (`predecessor_verdict`): the new answer never reads as
    the earlier question's. Where RUN or a run it rests on read stand-in
    answers, the label (`stand_in_label`) stands before the verdicts and
    values; without stand-ins nothing is added. Raises what
    `runs.read_metrics` raises on a run without readable metrics, and
    ValueError when the stand-ins cannot be counted (`stand_in_label`)."""
    limits = limits_of(area, text, run, found=found)
    note = finding_limits.answer_note([(label, effect) for label, _, effect in limits])
    said, recorded = _verdicts_and_values(area, text, run, limits)
    before = predecessor_verdict(area, text, set())
    drawn = source_phrases(area, run)
    re_read = re_read_phrase(text, run)
    stand_ins = stand_in_label(run)
    recorded_results = (
        (f"{before} · this question: " if before else "")
        + (f"{stand_ins} · " if stand_ins else "")
        + (f"{said} · recorded: " if said else "")
        + recorded
        + note
        + (f" · sources: {'; '.join(drawn)}" if drawn else "")
        + (f" · {re_read}" if re_read else "")
    )
    return Rendering(
        recorded_results,
        tuple((label, value) for label, value, _ in limits),
        written_line(text, QUESTION_LABEL),
        written_line(text, CONCLUSION_LABEL),
    )


def stand_in_clause(use: StandInUse) -> str:
    """The label of one alias's stand-ins, chosen by USE's logged lines:
    `includes fixed stand-in answers: N logged uses of alias X; not a pure
    model measurement` when any logged line of X is not a marked stand-in
    (asked, or replayed without the mark), else `fixed stand-in answers: N
    logged uses of alias X; not a measurement of X` (`logged_uses`). Only
    logged lines are seen (`StandInUse`)."""
    named = f"fixed stand-in answers: {logged_uses(use.stand_ins)} of alias {use.alias}"
    if use.only_stand_ins:
        return f"{named}; not a measurement of {use.alias}"
    return f"includes {named}; not a pure model measurement"


def stand_in_label(run: Path) -> str:
    """One clause per alias (`stand_in_clause`, joined by ` · `) for the
    stand-ins in the call logs of RUN and of every run it rests on
    (`runs.source_runs`: `derived_from`, continued rows, the origin runs of
    its inputs; read by `run_record_check.stand_in_calls`, as finalize's
    warning reads them), counted together (`stand_in_uses`); "" without
    stand-ins. N counts logged uses — call-log lines marked as stand-ins,
    not distinct answers: a stand-in read by two of those runs counts
    twice. An entry without the mark counts as an answer not marked as a
    stand-in — no evidence that a model gave it.

    Raises:
        ValueError: A record on the way does not read — a config.json,
            outputs.json, input record or call log — or a source run is
            missing: then whether a stand-in was read is not known, and no
            line is rendered.
    """
    try:
        read = stand_in_calls(run)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"the stand-in answers behind run {run.name} cannot be counted — {exc}"
        ) from exc
    uses = stand_in_uses([*read.own, *read.sources])
    return " · ".join(stand_in_clause(u) for u in uses)


def _verdicts_and_values(
    area: Path, text: str, run: Path, limits: list[tuple[str, str, str]]
) -> tuple[str, str]:
    """(the verdicts of TEXT's promises for RUN, "" without a block; the
    other recorded values with the run id) — `verdicts` and
    `recorded_results_line`."""
    metrics = runs.read_metrics(runs.metrics_path(run))
    comparison = comparison_phrase(text, metrics)
    kept = kept_of(text)
    try:
        block = promises.parse_block(text)
    except promises.PromiseError:
        block = None  # the head station names an unreadable block
    if block is None:
        return "", recorded_results_line(
            metrics, run.name, comparison=comparison, kept=kept
        )
    unjudged: dict[str, str] = {}
    for label, _, effect in limits:
        if not effect:  # a contested `not assessable`: lifted (`limits_of`)
            continue
        for pid in finding_limits.effect_ids(effect):
            unjudged.setdefault(pid, label)
    keys = frozenset(p.key for p in block.promises)
    return (
        "; ".join(verdicts(block, metrics, unjudged)),
        recorded_results_line(metrics, run.name, keys, comparison, kept),
    )


def re_read_phrase(text: str, run: Path) -> str:
    """`re-reads the answers of run <parent> (commit <c>) with the code of
    commit <c'>, its answer reading <module> as <parent> ran it[, step <id>
    (<occasion>)]; changed against <parent>: <key> <was> → <now>, …` for
    RUN, a derived run that declares its answer reading (`answer_reading`)
    — the correction it carries, beside the answers it rests on: both
    commits, the step of TEXT's `[builds_on]` when it builds on that parent,
    and each key both runs recorded with another value (runlog's own keys
    aside; `no number changed` when none). "" for a run that declares
    none, or whose declaration, records or metrics do not read — finalize
    and the record checks name those."""
    try:
        declared = read_answer_reading(run)
        cfg = runs.read_run_config(run)
    except (runs.ArtefactError, ValueError):
        return ""
    if declared is None or cfg is None or cfg.derived_from is None:
        return ""
    parent = runs.run_path(run.parent.parent, cfg.derived_from)
    try:
        pcfg = runs.read_run_config(parent)
        was = runs.read_metrics(runs.metrics_path(parent))
        now = runs.read_metrics(runs.metrics_path(run))
    except (runs.ArtefactError, ValueError):
        return ""
    if pcfg is None:
        return ""
    try:
        step = protocol_block.builds_on(text)
    except protocol_block.BlockError:
        step = None
    stepped = (
        f", step {step.id} ({step.occasion})"
        if step is not None and step.run == parent.name
        else ""
    )
    changed = [
        f"{k} {was[k]} → {now[k]}"
        for k in now
        if k in was and k not in LABKIT_KEYS and was[k] != now[k]
    ]
    return (
        f"re-reads the answers of run {parent.name} (commit {pcfg.git}) with the "
        f"code of commit {cfg.git}, its answer reading {declared.module} as "
        f"{parent.name} ran it{stepped}; changed against {parent.name}: "
        + (", ".join(changed) if changed else "no number changed")
    )


def source_phrases(area: Path, run: Path) -> list[str]:
    """One phrase per origin run of RUN's inputs (`runs.read_data`), in
    the inputs' order: `<protocol id> as run <id> saw it: <its values>` —
    the values as that run's metrics.json recorded them, every key, ordered
    and with the comparison as the text it was bound to orders them
    (`source_protocol_then`: its commit with its uncommitted.patch, never
    today's text; `recorded_results_line` with that text's `[kept]` and
    `[reference]`) and no verdict derived — a source is evidence of C's
    number, not a result reported beside it. A preparation is named
    `preparation run <id>`: it reports no result, its values are what it
    wrote. A run bound to no protocol
    reads `no protocol, run <id>: …`; a run gone or whose record does not
    read, a text or metrics that do not read back say so in place of the
    values (finalize holds them, `origin_check`,
    `source_protocol_finding`). [] for a run without origins or whose
    input record does not read (the record checks name that). Raises
    RuntimeError when git fails."""
    try:
        entries = runs.read_data(run) or []
    except runs.ArtefactError:
        return []
    origins = dict.fromkeys(e.origin_run for e in entries if e.origin_run is not None)
    root = git_root(area)
    out: list[str] = []
    for run_id in origins:
        then = source_protocol_then(area, run_id, root)
        source = runs.run_path(area, run_id)
        pid = runs.read_run_config(source)
        # a measurement keeps the short "run"; a preparation says what it is
        called = f"preparation run {run_id}" if then.preparation else f"run {run_id}"
        named = (
            f"{pid.protocol.id} as {called} saw it"
            if pid is not None and pid.protocol.id is not None
            else f"no protocol, {called}"
        )
        if then.bound is None:  # gone, or its record does not read
            out.append(f"run {run_id}: {then.where}")
            continue
        if then.bound and then.text is None:
            out.append(f"{named}: not reconstructable — {then.where}")
            continue
        try:
            metrics = runs.read_metrics(runs.metrics_path(source))
        except (OSError, ValueError) as exc:
            out.append(f"{named}: no values — {exc}")
            continue
        own = then.text or ""
        line = recorded_results_line(
            metrics,
            run_id,
            comparison=comparison_phrase(own, metrics),
            kept=kept_of(own),
        )
        out.append(f"{named}: {line}")
    return out


def predecessor_verdict(area: Path, text: str, seen: set[str]) -> str:
    """`replaces <id> (<protocol>): <its verdict>` for a TEXT that declares
    `[replaces]`, "" without one — the predecessor's verdict derived from its
    own bound sources (its declared run, its covering records), never from
    the successor's words, its own predecessor before it; `no result
    declared — unresolved` when it declares none, `no verdict — <why>` when
    its declared run answers no registered question (its first
    measurements recorded different registrations, or the run recorded
    another block than theirs — a verdict there is no earlier miss or pass
    to put first); an effect of its limitations that none of its own
    decision reviews upheld voids none of its verdicts, as in its own
    rendering; `unresolved (<why>)` when its sources, its reviews included,
    do not read or the
    chain runs in a circle (report-check holds that). SEEN: the ids already
    rendered. Raises RuntimeError when git fails."""
    try:
        rep = protocol_block.replaces(text)
    except protocol_block.BlockError:
        return ""  # report-check names the malformed table
    if rep is None:
        return ""
    hits = protocol_block.repo_protocol_ids(area).get(rep.protocol, [])
    if len(hits) != 1 or rep.protocol in seen:
        return f"replaces {rep.protocol}: unresolved (no single predecessor to read)"
    pred = hits[0]
    where = f"replaces {rep.protocol} ({pred.parent.name}/{pred.name})"
    try:
        # one build of the predecessor's area: its text and its first
        # measurements are read off the same state
        pred_state = state_of(pred.parent)
        pred_text = pred_state.text_of(pred)
        declared = protocol_block.declared_run(pred_text)
        earlier = predecessor_verdict(pred.parent, pred_text, {*seen, rep.protocol})
        if declared is None:
            verdict = "no result adopted — unresolved"
        else:
            pred_run = runs.run_path(pred.parent, declared)
            unregistered = _unregistered(pred_state, rep.protocol, pred_run)
            if unregistered:
                verdict = f"no verdict — {unregistered}"
            else:
                said, _ = _verdicts_and_values(
                    pred.parent,
                    pred_text,
                    pred_run,
                    # the predecessor's own reviews: an effect none upheld
                    # is lifted there too, so its miss reads as a miss
                    limits_of(
                        pred.parent,
                        pred_text,
                        pred_run,
                        found=evidence.decision_reviews_in_tree(pred.parent),
                    ),
                )
                verdict = said or f"run {declared}, no promise to judge"
    except (OSError, ValueError, protocol_block.BlockError) as exc:
        return f"{where}: unresolved ({exc})"
    return (f"{earlier} · " if earlier else "") + f"{where}: {verdict}"


def _unregistered(state: AreaState, pid: str, run_dir: Path) -> str | None:
    """Why RUN_DIR, the run the protocol stamped PID declares, answers no
    registered question: its first measurements, as STATE (its area's
    state) holds them, recorded different registrations, or the
    run recorded a block other than the one they recorded. None when it
    holds theirs, or when no block was recorded (another station names
    that)."""
    registered = first_registrations(state.measured_of(pid).first_groups)
    if len(registered) > 1:
        return "its first measurements recorded different registrations"
    cfg = runs.read_run_config(run_dir)
    now = cfg.promises if cfg is not None else None
    if not registered or now is None:
        return None
    ((sha, (first, _)),) = registered.items()
    if now["block_sha"] != sha:
        return f"its registration changed after the first measurement {first.dir.name}"
    return None


#: the step that writes a protocol's result section from its run and records
#: the two projections of an adoption the result section's holds name
RENDER = render_command()
FROM_RUN = render_command(from_run=True)


def render_gaps(text: str, expected: Rendering) -> list[GateFinding]:
    """Why TEXT's result section is not EXPECTED, one blocker each with the
    `protocol-fill` step that writes it, or []:
    the Recorded results line missing or differing, a Limitation line missing or differing,
    a Limitation line no covering record decides, a generated label written more
    than once (every line of a label is held, not the last one). Exact:
    the comparison is equality of the rendered values, no reading of what
    they say."""
    gaps: list[GateFinding] = []
    recorded_results = recorded_results_field(text)
    if recorded_results is None:
        gaps.append(
            blocker(
                "the Recorded results line is not written",
                fix=f"`{FROM_RUN}` writes it from the run",
                step=FROM_RUN,
                rule=LAB_011,
            )
        )
    elif recorded_results != expected.recorded_results:
        gaps.append(
            blocker(
                "the Recorded results line differs from its rendering (the run's "
                "metrics.json, the stand-ins in the call logs and the records' "
                "limits)",
                fix=f"`{RENDER}` writes it again",
                step=RENDER,
                # one equality over the whole generated line — stand-in
                # label, verdicts, values, run id, limits note —, whichever
                # part differs
                rule=TECHNICAL_RULE,
            )
        )
    labels = [display_label(f.label) for f in fields(text)]
    generated = [
        label
        for label in dict.fromkeys(labels)
        if label == RECORDED_RESULTS_LABEL
        or label.startswith(finding_limits.LIMIT_PREFIX)
    ]
    for label in generated:
        n = labels.count(label)
        if n > 1:
            # a dict of the fields would keep the last line only, and a first
            # line saying anything would pass beside a correct second one
            gaps.append(
                blocker(
                    f'"{label}" is written {n} times — one generated line per label',
                    fix="remove the extra line(s) by hand (`--render` rewrites one "
                    "and leaves the others)",
                    step=RENDER,
                    rule=TECHNICAL_RULE,
                )
            )
    have = {display_label(f.label): f.value for f in fields(text)}
    for label, value in expected.limits:
        got = have.get(label)
        if got is None:
            gaps.append(
                blocker(
                    f'no "{label}" line — the limit\'s line belongs in the protocol',
                    fix=f"`{RENDER}` writes it from the record",
                    step=RENDER,
                    rule=LAB_015,
                )
            )
        elif got != value:
            gaps.append(
                blocker(
                    f'"{label}" differs from the record and its decision reviews — '
                    f"a line written before the decision or a review changed it, "
                    f"or by hand: a stale rendering, no objection to the number",
                    fix=f"`{RENDER}` writes the record's line",
                    step=RENDER,
                    # equality with the rendering, as for Recorded results: a
                    # stale line is no finding of the audit's rule
                    rule=TECHNICAL_RULE,
                )
            )
    expected_labels = {label for label, _ in expected.limits}
    for label in have:
        if (
            label.startswith(finding_limits.LIMIT_PREFIX)
            and label not in expected_labels
        ):
            gaps.append(
                blocker(
                    f'"{label}" names a limit no covering record decides — written '
                    f"by hand or from an older record",
                    fix=f"`{RENDER}` drops it",
                    step=RENDER,
                    rule=LAB_015,
                )
            )
    return gaps
