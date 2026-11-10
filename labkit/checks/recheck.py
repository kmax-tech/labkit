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

Any disagreement is a SystemExit with a sentence — the area's `--check`
calls this with no main of labkit's around it (the rule by caller stands
at `console.Refused`); the verdict names what was compared. Rules of the lab standard: LAB-041 Generate numbers, don't retype them, LAB-043 Runs go through `runlog`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import (
    jsonl,
    promises,
    protocol_block,
    runs,
)
from labkit.formats.area_state import state_of
from labkit.formats.repo import file_text, path_kind
from labkit.formats.commands import adopt_command
from labkit.checks import run_record_check

#: keys labkit writes into metrics.json itself — not evaluate()'s to
#: reproduce: runlog's duration, llm's retry counter (the stamped evaluate()
#: records it)
LABKIT_KEYS = frozenset({"duration_s", "llm_retries"})
INTENT_KEY = promises.INTENT_KEY


@dataclass(frozen=True)
class Verdict:
    """What a recheck held: the run, the keys compared, what grew, the numbers the note was held to."""

    run_id: str
    out: Path
    keys_compared: int
    grown: list[str]  # keys the recomputation has and the run did not
    numbers: list[str]  # what the note was held to


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
            f"{drift}; rerun the script or name that run"
        )


def scopes_unchanged(run: Path, area: Path) -> None:
    """Refuse a recomputation over code the run did not use, per promise.

    The run recorded a declared-scope hash per promise (config.json `promises`);
    if a declared region changed since, recomputing with today's code
    agrees or disagrees about a different instrument. Runs without a
    promise block — and run dirs without config.json —
    have nothing to compare and pass.
    """
    cfg = runs.read_run_config(run)
    changed = promises.scope_drift(cfg.promises if cfg else None, area)
    if changed:
        raise SystemExit(
            f"recheck: declared scope changed since run {run.name}: "
            + "; ".join(changed)
            + " — rerun, or recheck from that run's commit"
        )


def kept_keys(run: Path, area: Path) -> frozenset[str]:
    """The `[kept]` key of the protocol RUN is bound to — the number a
    computation reports, compared exactly by `agree` —, empty for an
    unbound run or a protocol without the table. Raises SystemExit when the
    protocol's head does not read."""
    cfg = runs.read_run_config(run)
    if cfg is None or cfg.protocol.id is None:
        return frozenset()
    try:
        protocol = protocol_block.find_by_id(area, cfg.protocol.id)
        table = protocol_block.kept(state_of(area).text_of(protocol))
    except protocol_block.BlockError as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    return frozenset({table.key}) if table is not None and table.key else frozenset()


def block_unchanged(run: Path, area: Path) -> None:
    """Refuse to hold a note whose promises changed after the run.

    A lowered threshold can leave the verdict unchanged by chance — the
    recomputation then agrees and the note looks held, against promises
    nobody registered before the number. The bound
    protocol's block must be the one the run recorded.
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
        raise SystemExit(f"recheck: run {run.name} {drift}")


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
    keys (the computation's `[kept]` key, `kept_keys`: the number it
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
) -> tuple[dict, list[str]]:
    """pin → scopes → block → agree for one run, no note: (its metrics, the
    keys the recomputation grew). What `holds` checks before the note, and
    what `02_analyze.py --draws` checks for every draw — a draw shown
    unchecked lets an edited repeat file change the flipped items, an edited
    metrics.json the range. Raises SystemExit on the
    first disagreement."""
    pin(run, out)
    scopes_unchanged(run, area)
    block_unchanged(run, area)
    metrics = runs.read_metrics(runs.metrics_path(run))
    return metrics, agree(
        metrics, recompute(rows_of(out)), ignore, reported=kept_keys(run, area)
    )


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
    """pin → scopes → block → agree → cited, for the run that answers the
    protocol (`chosen_run`; or `run_id`). The protocol is `note` unless
    `protocol` names it — a results note under notes/ carries no head.

    `numbers(metrics)` formats what the note must carry — pass your own when
    the note rounds. Raises SystemExit on the first disagreement."""
    run = run_dir(area, protocol or note, run_id)
    metrics, grown = verified(run, area, out, recompute, ignore)
    wanted = numbers({k: v for k, v in metrics.items() if k not in ignore})
    cited(note, wanted, run.name)
    return Verdict(
        run_id=run.name,
        out=out,
        grown=grown,
        numbers=wanted,
        keys_compared=len(set(metrics) - ignore),
    )
