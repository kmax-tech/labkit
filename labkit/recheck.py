"""recheck — hold a kept number to its own output.

    from labkit import recheck
    recheck.holds(area=AREA, out=OUT, recompute=evaluate, note=PROTOCOL)

Three mechanics every area used to re-implement in its `--check`, and two
cold agents got two of them wrong on the first try (2026-10-05):

1. **pin** — `out` is the file the chosen run recorded in `outputs.json`
   (runlog keeps a 16-hex sha256 prefix; the comparison is `startswith`,
   not equality — a full digest never matches a prefix).
2. **agree** — `recompute(rows)` equals `metrics.json`: intent keys
   (`k1_…`, `s1_…`, `w1_…`, `n1_…`) present on both sides or neither,
   nothing the run reported vanishes (runlog's own keys excepted), every
   shared value identical. Keys the recomputation gained are a derived
   run, reported, not a failure (§2.D2).
3. **cited** — the note carries every reported number (decimal comma and
   U+2212 minus normalised first) and the run_id.

Any disagreement is a SystemExit with a sentence; the verdict names what
was compared. Rules: docs/arbeitsstandard.md §2.D2, §2.D4.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from labkit import promises, runs

#: keys labkit writes into metrics.json itself — not evaluate()'s to
#: reproduce: runlog's duration, llm's retry counter (the stamped evaluate()
#: records it; a cold agent read this module to learn why --check failed)
LABKIT_KEYS = frozenset({"duration_s", "llm_retries"})
INTENT_KEY = promises.INTENT_KEY


@dataclass(frozen=True)
class Verdict:
    run_id: str
    out: Path
    keys_compared: int
    grown: list[str]        # keys the recomputation has and the run did not
    numbers: list[str]      # what the note was held to


def run_dir(area: Path, run_id: str | None = None) -> Path:
    """The run to recheck against: `run_id`, or the newest completed run."""
    runs_dir = area / "runs"
    if run_id is not None:
        d = runs_dir / run_id
        state = runs.completion_state(d) if d.is_dir() else "missing"
        if state != "completed":
            raise SystemExit(f"recheck: {d} is not a completed run ({state})")
        return d
    done = runs.completed_runs(area)
    if not done:
        raise SystemExit(f"recheck: no completed run under {runs_dir}")
    return done[-1]


def pin(run: Path, out: Path) -> None:
    """Refuse rows the chosen run did not write."""
    outputs = json.loads((run / "outputs.json").read_text(encoding="utf-8"))
    recorded = next((o for o in outputs if Path(o["path"]).resolve() == out.resolve()), None)
    if recorded is None:
        raise SystemExit(f"recheck: run {run.name} did not register {out.name} as an output")
    if not out.is_file():
        raise SystemExit(f"recheck: {out} is gone — the run's rows are not here to recompute from")
    actual = hashlib.sha256(out.read_bytes()).hexdigest()
    if not recorded["sha256"] or not actual.startswith(recorded["sha256"]):
        raise SystemExit(
            f"recheck: {out.name} (sha {actual[:16]}) is not the file run {run.name} "
            f"recorded ({recorded['sha256']}) — rerun the script or name that run")


def scopes_unchanged(run: Path, area: Path) -> None:
    """Refuse a recomputation over code the run did not use, per promise.

    The run recorded a declared-scope hash per promise (config.json `promises`);
    if a declared region changed since, recomputing with today's code
    agrees or disagrees about a different instrument. Runs without a
    promise block — and run dirs without config.json, which predate it —
    have nothing to compare and pass.
    """
    recorded = (runs.read_run_config(run) or {}).get("promises")
    changed = promises.scope_drift(recorded, area)
    if changed:
        raise SystemExit(f"recheck: declared scope changed since run {run.name}: "
                         + "; ".join(changed)
                         + " — rerun, or recheck from that run's commit")


def block_unchanged(run: Path, area: Path) -> None:
    """Refuse to hold a note whose promises changed after the run.

    A lowered threshold can leave the verdict unchanged by chance — the
    recomputation then agrees and the note looks held, against promises
    nobody registered before the number (Durchstich 2026-10-06). The bound
    protocol's block must be the one the run recorded.
    """
    cfg = runs.read_run_config(run) or {}
    rel = (cfg.get("protocol") or {}).get("path")
    if rel is None:
        return                              # unbound or legacy: nothing to hold
    protocol = Path(rel) if Path(rel).is_absolute() else area / rel
    block = promises.parse_block(protocol.read_text(encoding="utf-8"))
    drift = promises.block_drift(cfg.get("promises"), block)
    if drift:
        raise SystemExit(f"recheck: run {run.name} {drift}")


def rows_of(out: Path) -> list[dict]:
    """One JSON object per line; a leading `_meta` header line is skipped."""
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return [r for r in rows if "_meta" not in r]


def agree(metrics: dict, recomputed: dict, ignore: frozenset[str] = LABKIT_KEYS) -> list[str]:
    """metrics.json against the recomputation; returns the keys that grew."""
    intent = {k for k in set(metrics) | set(recomputed) if INTENT_KEY.match(k)}
    one_sided = sorted(k for k in intent if (k in metrics) != (k in recomputed))
    vanished = sorted(set(metrics) - set(recomputed) - ignore)
    if one_sided or vanished:
        raise SystemExit(f"recheck: metrics.json and the recomputation disagree — "
                         f"intent keys on one side only {one_sided}, vanished {vanished}")
    differing = sorted(k for k in recomputed if k in metrics and recomputed[k] != metrics[k])
    if differing:
        raise SystemExit(f"recheck: recomputation differs from metrics.json in {differing}")
    return sorted(set(recomputed) - set(metrics))


def plain_numbers(metrics: dict) -> list[str]:
    """Default: every top-level number, written the way Python prints it."""
    return [str(v) for v in metrics.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _present(number: str, text: str) -> bool:
    """The number as a token, not as a digit run inside another number:
    `3.5` is not in `13.57`, `2` is not in `2026-10-05` (2026-10-05)."""
    n = number.lstrip("+").replace(",", ".")
    text = text.replace("−", "-").replace(",", ".")
    return re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", text) is not None


def cited(note: Path, numbers: list[str], run_id: str) -> None:
    text = note.read_text(encoding="utf-8").replace("−", "-").replace(",", ".")
    missing = sorted({n for n in numbers if not _present(n, text)})
    if missing:
        raise SystemExit(f"recheck: numbers not in {note.name}: {missing}")
    if run_id not in text:
        raise SystemExit(f"recheck: {note.name} does not cite run {run_id}")


def holds(area: Path, out: Path, recompute: Callable[[list[dict]], dict], note: Path,
          run_id: str | None = None,
          numbers: Callable[[dict], list[str]] = plain_numbers,
          ignore: frozenset[str] = LABKIT_KEYS) -> Verdict:
    """pin → scopes → block → agree → cited, for `area`'s newest run (or `run_id`).

    `numbers(metrics)` formats what the note must carry — pass your own when
    the note rounds. Raises SystemExit on the first disagreement."""
    run = run_dir(area, run_id)
    pin(run, out)
    scopes_unchanged(run, area)
    block_unchanged(run, area)
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    grown = agree(metrics, recompute(rows_of(out)), ignore)
    wanted = numbers({k: v for k, v in metrics.items() if k not in ignore})
    cited(note, wanted, run.name)
    return Verdict(run_id=run.name, out=out, grown=grown, numbers=wanted,
                   keys_compared=len(set(metrics) - ignore))
