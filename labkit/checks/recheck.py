"""recheck — hold a kept number to its own output.

    from labkit.checks import recheck
    recheck.holds(area=AREA, out=OUT, recompute=evaluate, note=PROTOCOL)

Three mechanics every area used to re-implement in its `--check`, and two
cold agents got two of them wrong on the first try (2026-10-05):

1. **pin** — `out` is the file the chosen run recorded in `outputs.json`
   (runlog keeps a `runs.RECORD_SHA_CHARS`-hex sha256 prefix; the comparison
   is `startswith`, not equality — a full digest never matches a prefix).
2. **agree** — `recompute(rows)` equals `metrics.json`: intent keys
   (`c1_…`, `a1_…`, `b1_…`) present on both sides or neither,
   nothing the run reported vanishes (runlog's own keys excepted), every
   shared value identical. Keys the recomputation gained are a derived
   run, reported, not a failure (LAB-041 Generate numbers, don't retype them).
3. **cited** — the note carries every reported number (decimal comma and
   U+2212 minus normalised first) and the run_id.

Any disagreement is a SystemExit with a sentence; the verdict names what
was compared. Rules of the lab standard: LAB-041 Generate numbers, don't retype them, LAB-043 Runs go through `runlog`.
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
    scope_sha,
    answering_run,
)
from labkit.formats.repo import adopt_command

#: keys labkit writes into metrics.json itself — not evaluate()'s to
#: reproduce: runlog's duration, llm's retry counter (the stamped evaluate()
#: records it; a cold agent read this module to learn why --check failed)
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
    or not (review 2026-10-15: `--from-run <repeat>` wrote its number).
    Until 0.94.0 this took the area's newest completed run with no look at
    the binding: in an area holding two protocols `protocol-fill --from-run`
    wrote the number of a run bound to the other one (audit 2026-10-15).
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
    choice = answering_run.bound_answering_run(area, pid)
    blocker, lines = choice.explain(promises.registers_ids(protocol_text))
    if blocker or choice.run_dir is None:
        raise SystemExit(f"recheck: {blocker}" + "".join(f"\n  {ln}" for ln in lines))
    return choice.run_dir


def _named_run(d: Path, pid: str) -> Path:
    """RUN_ID as the explicit choice: completed, no repeat, bound to PID."""
    try:
        state = runs.completion_state(d) if d.is_dir() else "missing"
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
    """`chosen_run` for a protocol on disk."""
    return chosen_run(area, protocol.read_text(encoding="utf-8"), run_id)


def pin(run: Path, out: Path) -> None:
    """Refuse rows the chosen run did not write."""
    outputs = runs.read_outputs(run) or []
    recorded = next((o for o in outputs if o.path.resolve() == out.resolve()), None)
    if recorded is None:
        raise SystemExit(
            f"recheck: run {run.name} did not register {out.name} as an output"
        )
    if not out.is_file():
        raise SystemExit(
            f"recheck: {out} is gone — the run's rows are not here to recompute from"
        )
    actual = scope_sha.file_digest(out)
    if not recorded.sha256 or not actual.startswith(recorded.sha256):
        raise SystemExit(
            f"recheck: {out.name} (sha {actual[: runs.RECORD_SHA_CHARS]}) is not the file run {run.name} "
            f"recorded ({recorded.sha256}) — rerun the script or name that run"
        )


def scopes_unchanged(run: Path, area: Path) -> None:
    """Refuse a recomputation over code the run did not use, per promise.

    The run recorded a declared-scope hash per promise (config.json `promises`);
    if a declared region changed since, recomputing with today's code
    agrees or disagrees about a different instrument. Runs without a
    promise block — and run dirs without config.json, which predate it —
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


def block_unchanged(run: Path, area: Path) -> None:
    """Refuse to hold a note whose promises changed after the run.

    A lowered threshold can leave the verdict unchanged by chance — the
    recomputation then agrees and the note looks held, against promises
    nobody registered before the number (Durchstich 2026-10-06). The bound
    protocol's block must be the one the run recorded.
    """
    cfg = runs.read_run_config(run)
    if cfg is None or cfg.protocol.id is None:
        return  # unbound: nothing to hold
    pid = cfg.protocol.id
    try:
        protocol = protocol_block.find_by_id(area, pid)  # by id; the path goes stale
        block = promises.parse_block(protocol.read_text(encoding="utf-8"))
    except (protocol_block.BlockError, promises.PromiseError) as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    drift = promises.block_drift(cfg.promises, block)
    if drift:
        raise SystemExit(f"recheck: run {run.name} {drift}")


def rows_of(out: Path) -> list[dict]:
    """One JSON object per line; a leading `_meta` header line is skipped."""
    rows = [
        json.loads(line)
        for line in jsonl.record_lines(out.read_text(encoding="utf-8"))
        if line.strip()
    ]
    return [r for r in rows if "_meta" not in r]


def agree(
    metrics: dict, recomputed: dict, ignore: frozenset[str] = LABKIT_KEYS
) -> list[str]:
    """metrics.json against the recomputation; returns the keys that grew.
    The recomputation is compared as JSON, the way the run recorded it
    (`runs.as_stored`): a tuple from evaluate() is the list in metrics.json,
    not a difference, and `1` is not `true`."""
    recomputed = json.loads(json.dumps(recomputed))
    intent = {k for k in set(metrics) | set(recomputed) if INTENT_KEY.match(k)}
    one_sided = sorted(k for k in intent if (k in metrics) != (k in recomputed))
    vanished = sorted(set(metrics) - set(recomputed) - ignore)
    if one_sided or vanished:
        raise SystemExit(
            f"recheck: metrics.json and the recomputation disagree — "
            f"intent keys on one side only {one_sided}, vanished {vanished}"
        )
    differing = sorted(
        k
        for k in recomputed
        if k in metrics and runs.as_stored(recomputed[k]) != runs.as_stored(metrics[k])
    )
    if differing:
        raise SystemExit(
            f"recheck: recomputation differs from metrics.json in {differing}"
        )
    return sorted(set(recomputed) - set(metrics))


def plain_numbers(metrics: dict) -> list[str]:
    """Default: every top-level number, written the way Python prints it."""
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


def _present(number: str, text: str) -> bool:
    """The number as a whole token of the note, sign and exponent included,
    not as a digit run inside another number or a stamp: `3.5` is not in
    `13.57`, `12` is not in `12.7`, `0.5` is not in `-0.5`, `1` and `5`
    are not in `1e-5` (review 2026-10-20), and `10` is not in the run id
    `…T10-22-33_ab12` or the date `2026-10-05` — the run id is mandatory
    in every note, so a count equal to one of its parts passed as cited
    (audit 2026-10-15). A leading `+` is no sign."""
    n = number.replace("−", "-").replace(",", ".").lstrip("+")
    text = _NOT_A_NUMBER.sub(" ", text.replace("−", "-").replace(",", "."))
    return any(t.group().lstrip("+") == n for t in _NUMBER_TOKEN.finditer(text))


ANSWER_OPEN = re.compile(
    r"^\s*[-*]\s+\*\*Recorded results:\*\*\s*(<!--[^>]*-->\s*)?<", re.M
)


def cited(note: Path, numbers: list[str], run_id: str) -> None:
    """Refuse unless the note contains every reported number and cites the run.

    A Recorded results line still holding the stamp's placeholder is named as such —
    "numbers not in PROTOCOL" before the write-back read as a failed check
    (Haiku 5.5, 2026-10-13); the cure is one command."""
    text = note.read_text(encoding="utf-8").replace("−", "-").replace(",", ".")
    missing = sorted({n for n in numbers if not _present(n, text)})
    if missing and ANSWER_OPEN.search(text):
        raise SystemExit(
            f"recheck: {note.name} has no answer yet — "
            f"`{adopt_command(note, run_id)}` writes it"
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
    unchecked let an edited repeat file change the flipped items, an edited
    metrics.json the range (review 2026-10-15). Raises SystemExit on the
    first disagreement."""
    pin(run, out)
    scopes_unchanged(run, area)
    block_unchanged(run, area)
    metrics = runs.read_metrics(runs.metrics_path(run))
    return metrics, agree(metrics, recompute(rows_of(out)), ignore)


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
