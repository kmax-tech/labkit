"""recheck — hold a kept number to its own output.

    from labkit.checks import recheck
    recheck.holds(area=AREA, out=OUT, recompute=evaluate, note=PROTOCOL)

Three mechanics every area's `--check` needs, held here once:

1. **pin** — `out` is the file the chosen run recorded in `outputs.json`
   (runlog keeps a `runs.RECORD_SHA_CHARS`-hex sha256 prefix; the comparison
   is `startswith`, not equality — a full digest never matches a prefix).
2. **agree** — `recompute(rows)` equals `metrics.json`: intent keys
   (`criterion_1_…`, `quality_check_1_…`, `interpretation_1_…`) present on both sides or neither,
   nothing the run reported vanishes (runlog's own keys excepted), every
   shared value identical. Keys the recomputation gained are a derived
   run, reported, not a failure (LAB-041 Generate numbers, don't retype them).
3. **cited** — the note carries every reported number (decimal comma and
   U+2212 minus normalised first) and the run_id.

Before the numbers are compared, the code is (`require_run_code`): a run
whose script or imported modules changed since it ran is refused — equal
numbers from other code would not be a recalculation of that run —, and
where nothing shows that the code here is the code the run ran, the run is
not verifiable (`NotVerifiable`): a missing proof, no failed comparison,
and no number is compared with today's code in its place. The release that
owes the recalculation waits on it — the area's `--check` holds the run
the protocol answers with, and report-check reads the clause
`NOT_VERIFIABLE` off that check's output; a recheck of any other run only
says so.

A run that computes from other runs' outputs (a comparison over its
source runs) is held by `holds_from_inputs`: inputs → scopes → code →
block → agree → cited. The inputs step comes first and stands apart from the
recomputation: every input the run recorded is still the bytes it read —
an input with an origin run still that run's registered output
(`inputs_pinned`, the same condition as finalize's input-origins
station) —, and only then does the computing run's own evaluation over
those inputs have to give the numbers its metrics.json holds (`agree`).
The source runs are not run again.

Any disagreement is a SystemExit with a sentence — the area's `--check`
calls this with no main of labkit's around it (the rule by caller stands
at `console.Refused`); the verdict names what was compared. Rules of the lab standard: LAB-041 Generate numbers, don't retype them, LAB-043 Runs go through `runlog`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import (
    jsonl,
    promises,
    protocol_block,
    runs,
)
from labkit.formats.area_state import state_of
from labkit.formats.protocol_then import as_measured, bound_protocol_file
from labkit.formats.repo import file_text, git_root, path_kind
from labkit.formats.commands import adopt_command
from labkit.checks import run_record_check
from labkit.checks.origin_check import origin_gap, origin_now

#: keys labkit writes into metrics.json itself — not evaluate()'s to
#: reproduce: runlog's duration, llm's retry counter (the stamped evaluate()
#: records it)
LABKIT_KEYS = frozenset({"duration_s", "llm_retries"})
INTENT_KEY = promises.INTENT_KEY


@dataclass(frozen=True)
class Verdict:
    """What a recheck held: the run, the keys compared, what grew, the numbers the note was held to."""

    run_id: str
    out: (
        Path | None
    )  # the output file pinned; None: no output file compared, the run was recomputed from its inputs (`holds_from_inputs`)
    keys_compared: int
    grown: list[str]  # keys the recomputation has and the run did not
    numbers: list[str]  # what the note was held to


#: the clause every `NotVerifiable` refusal carries, written here only
#: (`require_run_code`). report-check looks for it as a substring of what
#: an area's `--check` printed — the one channel a script's exit leaves —
#: to tell a missing proof from a failed comparison
NOT_VERIFIABLE = (
    "is not verifiable — nothing shows that the code here now is the code it ran"
)


class NotVerifiable(SystemExit):
    """A recalculation that could not be made: nothing shows that the code
    here now is the code the run ran. A missing proof, not a failed
    comparison — no number was compared. A SystemExit like every refusal
    of this module, so an area's `--check` ends nonzero with the sentence,
    which carries the clause `NOT_VERIFIABLE`; a caller that looks into a
    run no release waits on catches this class and reports it."""


def chosen_run(area: Path, protocol_text: str, run_id: str | None = None) -> Path:
    """The run a protocol is held to — and the run `--from-run` writes back.

    The choice is `answering_run.bound_answering_run` for the protocol's stamped id,
    the same one finalize and intent-check make; RUN_ID names a run instead,
    which must be completed and bound to that id. Never a repeat draw, named
    or not.
    """
    try:
        pid = protocol_block.head(protocol_text).id
    except protocol_block.BlockError as exc:
        raise SystemExit(f"recheck: {exc}") from exc
    if pid is None:
        raise SystemExit(
            "recheck: the protocol carries no stamped id ([protocol] id) — no run "
            "binds to it; `labkit-init exp` stamps it"
        )
    if run_id is not None:
        return _named_run(runs.run_path(area, run_id), pid)
    choice, blocker, lines = state_of(area).measured_of(pid).told(protocol_text)
    if blocker or choice.run_dir is None:
        why = blocker.message if blocker else "no run answers"
        raise SystemExit(f"recheck: {why}" + "".join(f"\n  {ln}" for ln in lines))
    return choice.run_dir


def _named_run(d: Path, pid: str) -> Path:
    """RUN_ID as the explicit choice: completed, no repeat, bound to PID."""
    try:
        state = runs.completion_state(d) if path_kind(d) == "dir" else "missing"
        if state != runs.COMPLETED:
            raise SystemExit(f"recheck: {d} is not a completed run ({state})")
        cfg = runs.read_run_config(d)
        parent = cfg.repeat_of if cfg else None
    except runs.RunConfigError as exc:
        raise SystemExit(f"recheck: {exc}") from exc
    if parent is not None:
        # no --force past this: a repeat never answers, named or not
        raise SystemExit(
            f"recheck: {d.name} is a repeat of {parent} — supporting "
            f"evidence, never the answer; `02_analyze.py --draws` shows it"
        )
    bound = cfg.protocol.id if cfg else None
    if bound != pid:
        raise SystemExit(
            f"recheck: {d.name} is bound to {bound or 'no protocol'}, not to "
            f"{pid} — it answers another question"
        )
    return d


def run_dir(area: Path, protocol: Path, run_id: str | None = None) -> Path:
    """`chosen_run` for a protocol the area's state holds."""
    return chosen_run(area, state_of(area).text_of(protocol), run_id)


def pin(run: Path, out: Path) -> None:
    """Refuse rows the chosen run did not write."""
    outputs = runs.read_outputs(run) or []
    recorded = next((o for o in outputs if o.path.resolve() == out.resolve()), None)
    if recorded is None:
        raise SystemExit(
            f"recheck: run {run.name} did not register {out.name} as an output"
        )
    drift = run_record_check.output_drift(runs.output_now(recorded))
    if drift is not None:
        raise SystemExit(
            f"recheck: {out.name} is not the file run {run.name} recorded — "
            f"{drift.why}; rerun the script or name that run"
        )


def scopes_unchanged(run: Path, area: Path) -> None:
    """Refuse a recomputation over code the run did not use, per promise.

    The run recorded a declared-scope hash per promise (config.json `promises`);
    if a declared region changed since, recomputing with today's code
    agrees or disagrees about a different instrument. A scope that gives
    no digest now (`promises.ScopeDrift.unread`) is refused as not
    compared, with its cause's step. Runs without a promise block — and
    run dirs without config.json — have nothing to compare and pass.
    """
    cfg = runs.read_run_config(run)
    drift = promises.scope_drift(cfg.promises if cfg else None, area)
    # a scope without a digest now is not compared: its cause and that
    # cause's step, no change claimed — a rerun is refused over it too
    unread = [d for d in drift if d.unread is not None]
    if unread:
        raise SystemExit(
            f"recheck: declared scope cannot be compared with what run "
            f"{run.name} recorded: "
            + "; ".join(
                f"{d.told} — {promises.scope_way_out(d.promise_id, d.unread)}"
                for d in unread
                if d.unread is not None
            )
            + ", or recheck from that run's commit"
        )
    if drift:
        raise SystemExit(
            f"recheck: declared scope changed since run {run.name}: "
            + "; ".join(d.told for d in drift)
            + " — rerun, or recheck from that run's commit"
        )


def require_run_code(run: Path, area: Path) -> None:
    """Refuse a recalculation of RUN unless the code here now is shown to
    be the code it ran. The code is the run's script and the modules it
    imports, for the run and each run it derives from
    (`run_record_check.code_since_run`, the comparison finalize makes).
    Where that found a difference, SystemExit: a recomputation with other
    code can agree by chance and would be read as a recalculation of that
    run. Where it could not compare — no script or commit recorded, a
    helper uncommitted then, a module in another repository —
    `NotVerifiable` with each reason and the two ways out: the proof is
    missing, and agreeing with today's code would not supply it. Declared
    scopes are `scopes_unchanged`'s, before this. Reads files and git."""
    blockers, warnings = run_record_check.code_since_run(area, run)
    changed = [b.text for b in blockers if b.changed_since is not None]
    if changed:
        raise SystemExit(
            f"recheck: the code that computed run {run.name} is not the code "
            f"here now: {'; '.join(changed)} — recomputing with today's code is "
            f"no recalculation of that run; recheck from that run's commit, or "
            f"compute anew as a run of its own and hold that one"
        )
    unknown = [b.text for b in blockers] + warnings
    if unknown:
        raise NotVerifiable(
            f"recheck: run {run.name} {NOT_VERIFIABLE}: {'; '.join(unknown)}. A "
            f"missing proof, not a failed comparison: no number was compared, "
            f"and agreeing with today's code would be no recalculation of that "
            f"run. Restore the code as the run ran it and what records it (its "
            f"commit, its uncommitted.patch, its script copy), or measure anew "
            f"— a run whose code is recorded in full — and hold that one"
        )


def protocol_as_run_saw(run: Path, area: Path) -> str | None:
    """The text of the protocol RUN is bound to as RUN saw it when it
    started — its commit with its uncommitted.patch, held to the promise
    block it recorded (`protocol_then.as_measured`) —, not as the
    protocol reads now; None for an unbound run. This module's reading of
    `as_measured`, as a refusal. A run that recorded no promise block is
    read from its commit and patch alone: there is no recorded block to
    hold that text to. Raises SystemExit, with
    why and what brings the text back, when it cannot be read back: the
    protocol as it reads now is never read in its place. Reads files and
    git."""
    rd = runs.read_run_dir(run)
    if rd.error is not None:
        raise SystemExit(f"recheck: run {run.name}: {rd.error}")
    if rd.config is None or rd.config.protocol.id is None:
        return None
    binding = rd.config.protocol
    assert binding.id is not None
    protocol = bound_protocol_file(area, binding.id, binding.path)
    text, where = as_measured(protocol, rd, git_root(area), role="run")
    if text is None:
        raise SystemExit(
            f"recheck: the protocol run {run.name} was measured under cannot be "
            f"read back: {where} — what it registered then (its `[kept]` key) is "
            f"not taken from the protocol as it reads now; restore what the "
            f"sentence names, or measure anew and hold that run"
        )
    return text


def kept_keys(run: Path, area: Path) -> frozenset[str]:
    """The `[kept]` key RUN's protocol named when the run started
    (`protocol_as_run_saw`, not the protocol as it reads now) — the number
    it reports, compared exactly by `agree` —, empty for an unbound run or
    a text without the table. Raises SystemExit when that text cannot be
    read back or its head does not read."""
    text = protocol_as_run_saw(run, area)
    if text is None:
        return frozenset()
    try:
        table = protocol_block.kept(text)
    except protocol_block.BlockError as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    return frozenset({table.key}) if table is not None and table.key else frozenset()


def block_unchanged(run: Path, area: Path) -> None:
    """Refuse to hold a note whose promises changed after the run.

    A lowered threshold can leave the verdict unchanged by chance — the
    recomputation then agrees and the note looks held, against promises
    nobody registered before the number. The bound
    protocol's block as it reads now must be the one the run recorded.
    The step of a run the protocol answers with; an older run named for a
    recheck is held under its own text instead (`holds`).
    """
    cfg = runs.read_run_config(run)
    if cfg is None or cfg.protocol.id is None:
        return  # unbound: nothing to hold
    pid = cfg.protocol.id
    try:
        protocol = protocol_block.find_by_id(area, pid)  # by id; the path goes stale
        block = promises.parse_block(state_of(area).text_of(protocol))
    except (protocol_block.BlockError, promises.PromiseError) as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    drift = promises.block_drift(cfg.promises, block)
    if drift:
        raise SystemExit(f"recheck: run {run.name} {drift.why}")


def rows_of(out: Path) -> list[dict]:
    """One JSON object per line; a leading `_meta` header line is skipped
    (`jsonl.data_rows_of`)."""
    return jsonl.data_rows_of(out)


def agree(
    metrics: dict,
    recomputed: dict,
    ignore: frozenset[str] = LABKIT_KEYS,
    reported: frozenset[str] = frozenset(),
) -> list[str]:
    """metrics.json against the recomputation; returns the keys that grew.
    As LAB-041 Generate numbers, don't retype them states it: the
    registered identifiers (`INTENT_KEY`) are compared exactly — on one side
    only, or with another value, the check fails —, and so are the REPORTED
    keys (the protocol's `[kept]` key, `kept_keys`: the number it
    reports); of the other descriptive keys none may disappear, and a value
    that differs or a key that grew is no failure. Compared as JSON, the way the run recorded it
    (`runs.as_stored`): a tuple from evaluate() is the list in metrics.json,
    not a difference, and `1` is not `true`."""
    recomputed = json.loads(json.dumps(recomputed))
    intent = {k for k in set(metrics) | set(recomputed) if INTENT_KEY.match(k)}
    one_sided = sorted(k for k in intent if (k in metrics) != (k in recomputed))
    vanished = sorted(set(metrics) - set(recomputed) - ignore)
    if one_sided or vanished:
        beside = (
            f" — {vanished} stand in metrics.json, but the evaluation of the kept "
            f"rows does not produce them: compute each in `evaluate_rows()` from "
            f"what the rows carry (a required check too), never beside it"
            if vanished
            else ""
        )
        raise SystemExit(
            f"recheck: metrics.json and the recomputation disagree — "
            f"intent keys on one side only {one_sided}, vanished {vanished}{beside}"
        )
    differing = sorted(
        k
        for k in intent | (reported & set(recomputed))
        if k in metrics and runs.as_stored(recomputed[k]) != runs.as_stored(metrics[k])
    )
    if differing:
        raise SystemExit(
            f"recheck: recomputation differs from metrics.json in the "
            f"identifiers or the kept number {differing}"
        )
    return sorted(set(recomputed) - set(metrics))


def plain_numbers(metrics: dict) -> list[str]:
    """Default: every top-level number, written the way Python prints it —
    `nan`, `inf` and `-inf` for a value that is not finite, as
    `result_render.recorded_results_line` writes it into the protocol."""
    return [
        str(v)
        for v in metrics.values()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]


#: a run id, or a date or a time of day: digit runs a note carries that
#: are never one of its numbers — masked before a number is looked for
_NOT_A_NUMBER = re.compile(
    rf"{runs.RUN_ID.pattern}|\b\d{{4}}-\d{{2}}-\d{{2}}(?:T\d{{2}}:\d{{2}}(?::\d{{2}})?)?\b"
)


#: one number as the note writes it: a sign only where it cannot be a
#: hyphen (`3-5` is 3 and 5, `x=-0.5` is -0.5), a decimal part, an exponent
_NUMBER_TOKEN = re.compile(
    r"(?<![\d.])(?:(?<![A-Za-z0-9_)\]])[-+])?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?!\d)"
)


#: a value no digit writes — NaN and the infinities as `plain_numbers`
#: gives them, with a sign, in any case: a whole word of the note, so `nan`
#: is not in `nanometre` and `inf` not in `info`; a dot may follow (the
#: note's commas are dots by the time it is read)
_NONFINITE_TOKEN = re.compile(r"(?<![\w.])-?(?i:nan|inf)(?!\w)")


def _present(number: str, text: str) -> bool:
    """The number as a whole token of the note, sign and exponent included,
    not as a digit run inside another number or a stamp: `3.5` is not in
    `13.57`, `12` is not in `12.7`, `0.5` is not in `-0.5`, `1` and `5`
    are not in `1e-5`, and `10` is not in the run id `…T10-22-33_ab12` or
    the date `2026-10-05` — the run id is mandatory in every note, so a
    count equal to one of its parts would otherwise pass as cited. A leading `+` is no sign. A value that is not
    finite (`nan`, `inf`, `-inf`) is a whole word of the note, in any
    case, its sign included: the write-back and this check share one
    spelling, so a NaN the run recorded can be cited and proven."""
    n = number.replace("−", "-").replace(",", ".").lstrip("+")
    text = _NOT_A_NUMBER.sub(" ", text.replace("−", "-").replace(",", "."))
    if _NONFINITE_TOKEN.fullmatch(n):
        return any(
            t.group().lower() == n.lower() for t in _NONFINITE_TOKEN.finditer(text)
        )
    return any(t.group().lstrip("+") == n for t in _NUMBER_TOKEN.finditer(text))


ANSWER_OPEN = re.compile(
    r"^\s*[-*]\s+\*\*Recorded results:\*\*\s*(<!--[^>]*-->\s*)?<", re.M
)


def cited(note: Path, numbers: list[str], run_id: str) -> None:
    """Refuse unless the note contains every reported number and cites the run.

    A Recorded results line still holding the stamp's placeholder is named as such —
    "numbers not in PROTOCOL" before the write-back would read as a failed
    check; the cure is one command."""
    found = file_text(note)
    if found is None:
        raise SystemExit(f"recheck: {note}: no such note")
    text = found.replace("−", "-").replace(",", ".")
    missing = sorted({n for n in numbers if not _present(n, text)})
    if missing and ANSWER_OPEN.search(text):
        raise SystemExit(
            f"recheck: {note.name} has no answer yet — "
            f"`{adopt_command(note, run_id)}` writes it once that run's "
            f"analysis audit is decided and report-check shows no other blocker"
        )
    if missing:
        raise SystemExit(f"recheck: numbers not in {note.name}: {missing}")
    if run_id not in text:
        raise SystemExit(f"recheck: {note.name} does not cite run {run_id}")


def verified(
    run: Path,
    area: Path,
    out: Path,
    recompute: Callable[[list[dict]], dict],
    ignore: frozenset[str] = LABKIT_KEYS,
    *,
    hold_block_now: bool = True,
) -> tuple[dict, list[str]]:
    """pin → scopes → code → block (if HOLD_BLOCK_NOW) → agree for one run, no note: (its metrics, the
    keys the recomputation grew). What `holds` checks before the note, and
    what `02_analyze.py --draws` checks for every draw — a draw shown
    unchecked lets an edited repeat file change the flipped items, an edited
    metrics.json the range. The block step holds the protocol as it reads
    now to the block the run recorded (`block_unchanged`) unless
    HOLD_BLOCK_NOW is False — an older run rechecked after the protocol moved on; the
    kept key is always the one of the run's own text (`kept_keys`). Raises
    SystemExit on the first disagreement, `NotVerifiable` where the code
    step finds no proof."""
    pin(run, out)
    scopes_unchanged(run, area)
    require_run_code(run, area)
    if hold_block_now:
        block_unchanged(run, area)
    metrics = runs.read_metrics(runs.metrics_path(run))
    grown = agree(
        metrics, recompute(rows_of(out)), ignore, reported=kept_keys(run, area)
    )
    return metrics, grown


def holds(
    area: Path,
    out: Path,
    recompute: Callable[[list[dict]], dict],
    note: Path,
    run_id: str | None = None,
    numbers: Callable[[dict], list[str]] = plain_numbers,
    ignore: frozenset[str] = LABKIT_KEYS,
    protocol: Path | None = None,
) -> Verdict:
    """pin → scopes → code → block → agree → cited, for the run that answers the
    protocol (`chosen_run`; or `run_id`). The protocol is `note` unless
    `protocol` names it — a results note under notes/ carries no head.
    The answering run (no RUN_ID) also holds the protocol as it reads now
    to the block it recorded; a run named by RUN_ID is rechecked under its
    own text — the block it recorded and the `[kept]` key of the protocol
    as it started under it —, whatever the protocol registers now.
    The code step (`require_run_code`) refuses a run whose script or
    imported modules changed since it ran, and raises `NotVerifiable` for
    a run whose code cannot be compared with the code here.

    `numbers(metrics)` formats what the note must carry — pass your own when
    the note rounds. Raises SystemExit on the first disagreement,
    `NotVerifiable` where the code step finds no proof."""
    run = run_dir(area, protocol or note, run_id)
    answering = run_id is None  # no run named: the one the protocol answers with
    metrics, grown = verified(
        run, area, out, recompute, ignore, hold_block_now=answering
    )
    return _cited_verdict(run, out, metrics, grown, note, numbers, ignore)


def _cited_verdict(
    run: Path,
    out: Path | None,
    metrics: dict,
    grown: list[str],
    note: Path,
    numbers: Callable[[dict], list[str]],
    ignore: frozenset[str],
) -> Verdict:
    """The last step of `holds` and `holds_from_inputs`: NOTE carries every
    number of RUN's METRICS as NUMBERS formats them, and the run id
    (`cited`); the Verdict. Raises SystemExit as `cited` does."""
    wanted = numbers({k: v for k, v in metrics.items() if k not in ignore})
    cited(note, wanted, run.name)
    return Verdict(
        run_id=run.name,
        out=out,
        grown=grown,
        numbers=wanted,
        keys_compared=len(set(metrics) - ignore),
    )


def reads_another_run(run: Path) -> bool:
    """Does RUN compute from another run's output — does an input it
    recorded name an origin run? Such a run's number is owed the
    recalculation from its inputs (`verified_from_inputs`); a run over
    plain inputs is held by its own rows (`holds`). Raises SystemExit when
    the input record does not read."""
    try:
        entries = runs.read_data(run) or []
    except runs.ArtefactError as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    return any(e.origin_run is not None for e in entries)


def inputs_pinned(run: Path, area: Path) -> dict[str, Path]:
    """Every input RUN recorded (`data=`), by its key, each held to be the
    bytes the run read before anything is recomputed from it: an input
    whose record names an origin run is still that run's registered output
    with those bytes (`origin_check.origin_gap`, the condition finalize's
    input-origins station holds), a plain input still has the sha256 the
    run recorded (`run_record_check.source_drift`). The paths resolved
    against the area, as the run's start resolved them. Raises SystemExit
    naming the input and the part that fails, and for a record without
    inputs or one that does not read."""
    try:
        entries = runs.read_data(run)
    except runs.ArtefactError as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    if not entries:
        raise SystemExit(
            f"recheck: run {run.name} recorded no input file — nothing to "
            f"recompute from; hold its own output with `holds`"
        )
    pinned: dict[str, Path] = {}
    for entry in entries:
        path = runs.resolve_recorded(entry.recorded, area)
        if entry.origin_run is not None:
            gap = origin_gap(origin_now(area, entry))
            if gap is not None:
                raise SystemExit(
                    f"recheck: run {run.name}: {gap.told} — not recomputed "
                    f"from inputs that are not the ones it read"
                )
        else:
            drift = run_record_check.source_drift(path, entry.sha256)
            if drift is not None:
                raise SystemExit(
                    f"recheck: run {run.name}: data[{entry.key!r}] = "
                    f"{entry.recorded} is not the input it read: {drift}, the "
                    f"run recorded sha256 {entry.sha256}"
                )
        pinned[entry.key] = path
    return pinned


def verified_from_inputs(
    run: Path,
    area: Path,
    recompute: Callable[[Mapping[str, Path]], dict],
    ignore: frozenset[str] = LABKIT_KEYS,
    *,
    hold_block_now: bool = True,
) -> tuple[dict, list[str]]:
    """inputs → scopes → code → block (if HOLD_BLOCK_NOW) → agree for RUN, no note: (its metrics, the
    keys the recomputation grew). First every recorded input is the bytes
    the run read (`inputs_pinned`); only then RECOMPUTE — the run's own
    evaluation, given each input's path by its `data=` key — is compared
    with metrics.json as `verified` compares it, HOLD_BLOCK_NOW as there. The source runs are not
    run again. Raises SystemExit on the first disagreement, `NotVerifiable`
    where the code step finds no proof; a failed input or code step leaves
    RECOMPUTE uncalled."""
    pinned = inputs_pinned(run, area)
    scopes_unchanged(run, area)
    require_run_code(run, area)
    if hold_block_now:
        block_unchanged(run, area)
    metrics = runs.read_metrics(runs.metrics_path(run))
    grown = agree(metrics, recompute(pinned), ignore, reported=kept_keys(run, area))
    return metrics, grown


def holds_from_inputs(
    area: Path,
    recompute: Callable[[Mapping[str, Path]], dict],
    note: Path,
    run_id: str | None = None,
    numbers: Callable[[dict], list[str]] = plain_numbers,
    ignore: frozenset[str] = LABKIT_KEYS,
    protocol: Path | None = None,
) -> Verdict:
    """`holds` for a run that computes from its recorded inputs — a
    comparison over source runs' outputs: inputs → scopes → code → block →
    agree → cited (`verified_from_inputs`, `_cited_verdict`), for the run
    that answers the protocol (`chosen_run`; or RUN_ID). The code step is
    `holds`'s, and as there a run named by RUN_ID is rechecked under its
    own text, not held to the promise block as it reads now. Raises SystemExit on the first disagreement, `NotVerifiable`
    where the code step finds no proof."""
    run = run_dir(area, protocol or note, run_id)
    answering = run_id is None  # no run named: the one the protocol answers with
    metrics, grown = verified_from_inputs(
        run, area, recompute, ignore, hold_block_now=answering
    )
    return _cited_verdict(run, None, metrics, grown, note, numbers, ignore)
