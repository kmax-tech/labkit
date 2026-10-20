"""answering_run — which run answers for a protocol, one choice for every reader.

The run facts a choice rests on (state, binding), the repeats of a run
and whether they are comparable (`repeats_of`, `repeat_mismatch`,
`next_draw`), the bound runs of a protocol and the newest one, a tie
within one second refused rather than guessed (`same_second_rival`),
the answering run with the reasons the others were excluded
(`bound_answering_run`), and the run that recorded the model behind a
derived run's rows (`model_provenance_run`). intent-check, finalize,
recheck and labkit-params read the choice here. Read-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from labkit.formats import promises
from labkit.formats.runs import (
    as_stored,
    binding_of,
    COMPLETED,
    JsonObject,
    ProtocolBinding,
    RunState,
    UNREADABLE,
    RECORD_TABLES,
    RunConfigError,
    RunDir,
    read_run_dir,
    completed_runs,
    read_metrics,
    read_run_config,
    repeat_parent,
    run_dirs,
    run_state,
)


@dataclass(frozen=True)
class RunFacts:
    """What a run directory says about itself, read once: its state and its
    binding, and — for a run left out of a choice — why.

    Attributes:
        dir: The run directory.
        state: `unreadable` for a config.json that cannot be read (never
            `corrupt` — that word is completion.json without metrics.json),
            else `run_state` with liveness not asked: a run still
            finalizing in another process reads as `unfinalized`.
        binding: The protocol it was started under; unbound for an
            unreadable run, whose binding is unknowable.
        why: The reason it cannot answer — the RunConfigError's sentence for
            an unreadable run, the exclusion `bound_runs` gives — or None.
    """

    dir: Path
    state: RunState
    binding: ProtocolBinding
    why: str | None = None

    @property
    def metrics(self) -> Path:
        """The run's metrics.json (it may not exist)."""
        return self.dir / "metrics.json"


def run_facts(run_dir: Path) -> RunFacts | None:
    """The `RunFacts` of RUN_DIR, or None for a directory without
    config.json — not a run. An unreadable config.json is a run in state
    `unreadable` with the reason in `why`: it stays in the listing the
    operator reads instead of vanishing, and it is never chosen (review
    2026-10-06). `runlog.active` asks liveness."""
    return _facts(read_run_dir(run_dir))


def _facts(rd: RunDir) -> RunFacts | None:
    if rd.error is not None:
        return RunFacts(rd.dir, UNREADABLE, ProtocolBinding(None, None), rd.error)
    if rd.config is None:
        return None
    return RunFacts(
        rd.dir, run_state(rd.dir, rd.config, alive=False), binding_of(rd.config)
    )


def repeats_of(area: Path, run_id: str) -> list[Path]:
    """The completed repeats of RUN_ID in draw order (2, 3, …) — by the
    recorded `draw`, not by name: run ids carry the start second and a random
    suffix, so two repeats started in one second sort by chance."""
    return [d for _, d in _numbered_repeats(area, run_id)]


def _repeats(area: Path, run_id: str) -> list[tuple[int, RunDir]]:
    """(recorded draw, run) of every repeat of RUN_ID ever started.

    Raises RunConfigError for a run whose config.json cannot be read — it
    cannot say whether it is a draw of RUN_ID, and dropping it would show a
    spread over fewer draws than were taken, or hand its number out again —
    and for a repeat without an integer `draw` (2026-10-15)."""
    found: list[tuple[int, RunDir]] = []
    for rd in run_dirs(area):
        if rd.error is not None:
            raise RunConfigError(rd.error)
        if rd.config is None or repeat_parent(rd.config) != run_id:
            continue
        draw = rd.config.get("draw")
        if not isinstance(draw, int) or isinstance(draw, bool):
            raise RunConfigError(
                f"{rd.dir}/config.json: a repeat without an integer `draw`"
            )
        found.append((draw, rd))
    return found


def _numbered_repeats(area: Path, run_id: str) -> list[tuple[int, Path]]:
    """(recorded draw, run dir) of RUN_ID's completed repeats, by draw. Two
    completed repeats with one draw number raise: the lock reserves each
    number once, so a second holder was copied or written by hand."""
    found = sorted(
        (draw, rd.dir)
        for draw, rd in _repeats(area, run_id)
        if rd.config is not None
        and run_state(rd.dir, rd.config, alive=False) == COMPLETED
    )
    for (a, da), (b, db) in zip(found, found[1:]):
        if a == b:
            raise RunConfigError(
                f"{da.name} and {db.name} both record draw {a} of {run_id}"
            )
    return found


def next_draw(area: Path, run_id: str) -> int:
    """The draw number a new repeat of RUN_ID gets: the run itself is draw 1,
    every repeat ever started — completed, running or crashed — holds its
    number, so the next is one past the highest. runlog counts it under its
    index lock (Run.draw); a crashed draw leaves a gap, never a reuse."""
    return 1 + max([1, *(draw for draw, _ in _repeats(area, run_id))])


def draws(area: Path, run_id: str) -> list[tuple[int, Path]]:
    """(draw, run dir) for RUN_ID and its completed repeats, draw 1 first —
    what an analysis reads to show the spread of the number."""
    return [(1, area / "runs" / run_id), *_numbered_repeats(area, run_id)]


def repeat_mismatch(parent: JsonObject, new: JsonObject) -> list[str]:
    """Why a run whose config.json would be NEW is no comparable repeat of
    PARENT (both config.json dicts), [] when it is: the same protocol, the
    same promise snapshot (block and every declared scope's digest), the same
    measure script, the same resolved model, the same experiment config
    (prompt digest, model alias, constants, sampling) and the same inputs
    (data= digests and rows) — the job set follows from these. A
    repeat that differs in any of these measures something else, and its
    spread would be noise of the change, not of the model.

    NEW may hold Python values not yet written: it is compared as
    config.json would store it (a tuple as a list), and values are compared
    by their JSON text, so `1` is not `true` and a missing config key is not
    `null`. A record table (`runs.RECORD_TABLES`) absent on one side, null
    on the other or an object on one only differs; a table that is neither
    raises RunConfigError."""
    new = json.loads(json.dumps(new, ensure_ascii=False))
    out: list[str] = [
        f"{key}: {_form(parent, key)} in the parent, {_form(new, key)} here"
        for key in RECORD_TABLES
        if _form(parent, key) != _form(new, key)
    ]
    pid = binding_of(parent).id
    if pid != binding_of(new).id:
        out.append(f"protocol {binding_of(new).id} is not {pid}")
    pp, np_ = _table(parent, "promises"), _table(new, "promises")
    if pp.get("block_sha") != np_.get("block_sha"):
        out.append("the promise block changed")
    elif as_stored(pp) != as_stored(np_):
        # same block, other code: a declared scope's digest moved
        out.append("the code a promise rests on changed (declared_scope_sha)")
    if parent.get("script_sha") != new.get("script_sha"):
        out.append("the measure script changed (script_sha)")
    if as_stored(_table(parent, "models_resolved")) != as_stored(
        _table(new, "models_resolved")
    ):
        out.append("the model resolved differently (models_resolved)")
    pc, nc = _table(parent, "config"), _table(new, "config")
    for key in sorted(set(pc) | set(nc)):
        if key not in pc or key not in nc or as_stored(pc[key]) != as_stored(nc[key]):
            out.append(f"config {key}: {_shown(pc, key)} → {_shown(nc, key)}")

    def digests(cfg: JsonObject) -> JsonObject:
        data = _table(cfg, "data")
        return {
            k: (_table(data, k).get("sha256"), _table(data, k).get("rows"))
            for k in data
            if isinstance(data[k], dict)
        }

    if digests(parent) != digests(new):
        out.append("the inputs (data=) differ")
    return out


def _table(cfg: JsonObject, key: str) -> JsonObject:
    """CFG[KEY] as an object; absent and null give an empty one — whether a
    side has the table at all is `_form`'s question. Raises RunConfigError
    for any other value: a damaged table is not an empty one."""
    value = cfg.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RunConfigError(f"{key} = {value!r}, not an object")
    return cast(JsonObject, value)


def _form(cfg: JsonObject, key: str) -> str:
    """How CFG holds table KEY: absent, null or an object (`_table` refuses
    any other value)."""
    if key not in cfg:
        return "absent"
    if cfg[key] is None:
        return "null"
    _table(cfg, key)
    return "an object"


def _shown(cfg: JsonObject, key: str) -> str:
    return as_stored(cfg[key]) if key in cfg else "(absent)"


def bound_runs(area: Path, pid: str) -> tuple[list[RunFacts], list[RunFacts]]:
    """(runs bound to `pid` and completed, everything else with its `why`),
    oldest first.

    Only the first list may feed an automatic choice. The second carries
    the reason it was left out, for the operator who has to look. The
    binding is the id and nothing else — `protocol.path` is a hint for
    humans, never a selection criterion: it goes stale by design.
    """
    taken: list[RunFacts] = []
    left: list[RunFacts] = []
    for rd in run_dirs(area):
        facts = _facts(rd)
        if facts is None:
            continue
        parent = repeat_parent(rd.config) if rd.config is not None else None
        bound_to = facts.binding.id
        if facts.state != COMPLETED:
            why = facts.why or facts.state
        elif parent is not None:
            why = f"a repeat of {parent} — supporting evidence, never the answer"
        elif bound_to == pid:
            taken.append(facts)
            continue
        elif bound_to:
            why = f"bound to {bound_to}"
        else:
            why = "unbound (no protocol id at run time)"
        left.append(replace(facts, why=why))
    return taken, left


def newest_with_intent_keys(
    cands: list[RunFacts],
) -> tuple[Path | None, int, bool]:
    """Among already-eligible runs: (metrics path, newer runs skipped for
    reporting no intent key, whether the chosen one reports any).

    The rule from 2026-09-09 (area 71) unchanged, only its input narrowed:
    a producer or probe run writes a metrics.json too, and holding the
    promises against THAT file reports every promise as unimplemented.
    When NO candidate reports an intent key, the newest is returned with
    skipped = 0 and reports_intent_keys = False — the caller says so,
    instead of a probe run passing as the answer (2026-10-09).
    """
    skipped = 0
    for facts in reversed(cands):
        if promises.reported_ids(read_metrics(facts.metrics)):
            return facts.metrics, skipped, True
        skipped += 1
    return (cands[-1].metrics, 0, False) if cands else (None, 0, False)


def start_second(run_dir: Path) -> str:
    """The start second a run id carries (everything before the suffix):
    two runs that share it sort by their random suffix, not by start."""
    return run_dir.name.rsplit("_", 1)[0]


def same_second(a: Path, b: Path) -> bool:
    """Whether two DIFFERENT runs started in the same second — the one rule
    for a tie the run ids cannot break: the answering choice, its
    unreadable-run guard and `newest_completed` all ask here (until 0.97.1
    the scorer compared the seconds itself, audit 2026-10-15)."""
    return a != b and start_second(a) == start_second(b)


def _not_older(run_dir: Path, chosen: Path) -> bool:
    """Whether RUN_DIR may have started after CHOSEN: newer by name, or
    started in the same second — the random suffix orders those by chance
    (2026-10-15)."""
    return run_dir.name > chosen.name or same_second(run_dir, chosen)


def newest_completed(area: Path, *, with_repeats: bool) -> Path | None:
    """The newest completed run of the area (`completed_runs`), None without
    one — refusing a tie: when the last two started in the same second the
    run ids cannot say which is newest. The scorer's run and runlog's
    "last finished" line read here; the answering choice adds the binding
    and the intent keys (`bound_answering_run`).

    Raises:
        RunConfigError: An unreadable run, or two newest runs in one second.
    """
    done = completed_runs(area, with_repeats=with_repeats)
    if len(done) >= 2 and same_second(done[-1], done[-2]):
        raise RunConfigError(
            f"{done[-2].name} and {done[-1].name} started in the same second — "
            f"the run ids cannot say which is newest; move the one that does "
            f"not count out of runs/"
        )
    return done[-1] if done else None


def newer_unreadable(chosen: Path, rest: list[RunFacts]) -> str | None:
    """Why the choice must not stand: a run NEWER than the chosen one, or
    started in the same second, whose config.json cannot be read. Its
    binding is unknowable, so it may be the run that answers — choosing an
    older one past it is what `runs.read_run_config` says must not happen
    (review 2026-10-07)."""
    bad = [f for f in rest if f.state == UNREADABLE and _not_older(f.dir, chosen)]
    if not bad:
        return None
    return (
        f"{len(bad)} newer run(s) cannot say which protocol they belong to — "
        + "; ".join(f.why or UNREADABLE for f in bad)
        + f". Repair or move them aside before {chosen.name} may answer."
    )


def same_second_rival(
    chosen: Path, taken: list[RunFacts], has_keys: bool
) -> str | None:
    """Why the choice must not stand: another bound run of the same standing
    (reporting an intent key, if the chosen one does) started in the same
    second. The run id carries the second and a random suffix, so which of
    the two is newest is chance (2026-10-15)."""
    rivals = [
        f.dir.name
        for f in taken
        if same_second(f.dir, chosen)
        and (not has_keys or promises.reported_ids(read_metrics(f.metrics)))
    ]
    if not rivals:
        return None
    return (
        f"{chosen.name} and {', '.join(rivals)} started in the same second — "
        "the run ids cannot say which is newest. Move the one that does not "
        "answer out of runs/."
    )


@dataclass(frozen=True)
class RunExclusion:
    """A run that could not answer, and why (for the operator who has to look)."""

    run_dir: Path
    why: str


@dataclass(frozen=True)
class AnsweringRun:
    """The outcome of choosing the run that answers for a protocol.

    Attributes:
        run_dir: The chosen run; None whenever `blocker` is set, so a caller
            that reads only run_dir cannot take a run that must not answer.
        skipped_newer: Newer bound runs passed over for reporting no intent
            key (a probe or producer run).
        reports_intent_keys: False when no bound run reports an intent key
            and the newest was taken anyway — a probe or producer run, not
            an answer; the caller names it.
        exclusions: Every run left out, with its reason.
        blocker: Why no choice stands — no completed bound run, or a newer
            run whose binding cannot be read — or None.
    """

    run_dir: Path | None
    skipped_newer: int
    exclusions: tuple[RunExclusion, ...]
    blocker: str | None
    reports_intent_keys: bool = True

    def explain(self, ids_registered: bool) -> tuple[str | None, list[str]]:
        """(why no run may answer, or None; the lines that say what was
        looked at) — ONE telling for finalize, intent-check, recheck, params
        and the audit, which each rendered this four ways with four
        semantics (audit 2026-10-15). A chosen run that reports no intent
        key while the protocol registers ids is a blocker here, everywhere:
        a probe or producer run is not an answer."""
        if self.run_dir is None:
            return self.blocker, [f"{x.run_dir.name}: {x.why}" for x in self.exclusions]
        if ids_registered and not self.reports_intent_keys:
            return (
                f"{self.run_dir.name} is the newest bound run, and no bound run "
                f"reports an intent key — a probe or producer run, not an answer",
                [],
            )
        lines: list[str] = []
        if self.skipped_newer:
            lines.append(
                f"skipped {self.skipped_newer} newer bound run(s) without intent keys"
            )
        return None, lines


def bound_answering_run(area: Path, pid: str) -> AnsweringRun:
    """The run every check holds the protocol to: the newest COMPLETED run
    bound to `pid` that reports an intent key. The binding is the run's own
    record, so the choice is a filter, not a guess; an unfinalized or corrupt
    run has numbers and no finish, a run bound elsewhere answers another
    question. A newer run whose config.json cannot be read (`unreadable`)
    blocks the choice: it may be the one that answers — then run_dir is
    None and `blocker` says why. So does a rival started in the same
    second, whose order the run ids cannot tell."""
    if not (area / "runs").is_dir():
        return AnsweringRun(
            None,
            0,
            (),
            f"no completed run bound to {pid} — no runs/ directory in {area}",
        )
    taken, rest = bound_runs(area, pid)
    exclusions = tuple(RunExclusion(f.dir, f.why or f.state) for f in rest)
    if not taken:
        return AnsweringRun(None, 0, exclusions, f"no completed run bound to {pid}")
    mpath, skipped, has_keys = newest_with_intent_keys(taken)
    assert mpath is not None, "taken is non-empty, so a metrics file exists"
    blocker = newer_unreadable(mpath.parent, rest) or same_second_rival(
        mpath.parent, taken, has_keys
    )
    if blocker:
        return AnsweringRun(None, skipped, exclusions, blocker, has_keys)
    return AnsweringRun(mpath.parent, skipped, exclusions, None, has_keys)


def model_provenance_run(run_dir: Path) -> Path | None:
    """The run whose `models_resolved` says which model answered the rows
    `run_dir` reads: the run itself when it recorded one, else the nearest
    ancestor along `derived_from` that did (a derived run records none —
    its rows are the parent's, and resolving the alias anew would be
    provenance the rows never had). None when no run in the chain recorded
    a model.

    Raises:
        ValueError: If an ancestor is missing or the chain loops.
    """
    seen: list[str] = []
    here = run_dir
    while True:
        cfg = read_run_config(here)
        if cfg is None:
            raise ValueError(
                f"{here}: no config.json — the lineage of {run_dir.name} breaks here"
            )
        if cfg.get("models_resolved"):
            return here
        parent = cfg.get("derived_from")
        if parent is None:
            return None
        if not isinstance(parent, str) or not parent:
            raise ValueError(
                f"{here.name}: derived_from must name a run, not {parent!r}"
            )
        if parent in seen or parent == here.name:
            raise ValueError(
                f"{run_dir.name}: derived_from loops: {' -> '.join([*seen, here.name, parent])}"
            )
        seen.append(here.name)
        here = here.parent / parent
        if not here.is_dir():
            raise ValueError(
                f"{run_dir.name}: derived_from names {parent}, which is not under {run_dir.parent}"
            )
