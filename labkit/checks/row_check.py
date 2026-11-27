"""row_check — the rows a finished run kept, held to its record.

Every JSONL row held to the runs that wrote it — this run, the runs it
continues, its derived_from lineage — and to the code that wrote it
(`row_provenance_findings`); the null lane of the kept rows that did not
move (`null_lane_findings`, read from the rows, not from a check in the
editable script). Each returns findings graded where they are made.
Read-only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.commands import measure_anew
from labkit.formats.gate import (
    LAB_034,
    LAB_057,
    OPEN_RULE,
    STATIC_EVIDENCE,
    TECHNICAL_RULE,
    WARNING,
    GateFinding,
    blocker,
)
from labkit.formats.runs import (
    KeptRows,
    lineage,
    next_output_name,
    output_file,
    read_outputs,
    read_run_config,
)
from labkit.run import batch


#: the two scored lanes a null comparison runs in, as the skeletons name them
NULL_LANES = ("registered", "null")


def null_lane_unmoved(rows: list[dict]) -> bool:
    """Do ROWS carry a null lane that cannot have moved — for every item
    its null row's answer (`pred`, or `answer`) and gold equal its
    registered row's? Then the null measures no noise floor: an instrument
    that ignores its labels predicts the same in both lanes (LAB-034 Null
    condition in the same run). False without both lanes, or when one item
    differs — a permuted gold (`gold_of`) or another answer is a move."""
    lanes: dict[str, dict[object, tuple[object, object]]] = {k: {} for k in NULL_LANES}
    for r in rows:
        lane = r.get("lane")
        if lane in lanes and "item" in r:
            lanes[lane][r["item"]] = (r.get("pred", r.get("answer")), r.get("gold"))
    registered, null = lanes["registered"], lanes["null"]
    if not registered or not null:
        return False
    return all(registered.get(item) == said for item, said in null.items())


def has_null_lanes(rows: list[dict]) -> bool:
    """Do ROWS hold both NULL_LANES — is there a null comparison to hold?"""
    return {r.get("lane") for r in rows} >= set(NULL_LANES)


@dataclass(frozen=True)
class NullLanes:
    """What `null_lane_findings` found: one static-evidence WARNING per
    output whose null lane did not move (UNMOVED), with its way out, and how
    many outputs held
    both lanes (EXAMINED) — 0 says the check did not apply, not that it
    passed."""

    unmoved: list[GateFinding]
    examined: int


def null_lane_findings(kept: Sequence[KeptRows], area: Path) -> NullLanes:
    """The kept JSONL outputs of a run of AREA (`runs.kept_jsonl_rows`) held
    to their null lane (`NullLanes`): an output with both lanes whose null
    did not move (`null_lane_unmoved`) is named — read from the rows the
    run kept, not from a check in the editable script, which an agent can
    delete before it first runs (LAB-034 Null condition in the same run).
    AREA names the measuring command in the way out."""
    out: list[GateFinding] = []
    examined = 0
    for k in kept:
        if not has_null_lanes(k.rows):
            continue
        examined += 1
        if null_lane_unmoved(k.rows):
            # matching answer-gold pairs are certain; that the null measures
            # nothing is not — a placebo prompt or a fixed null predictor can
            # match honestly — so it warns: static evidence
            out.append(
                GateFinding(
                    WARNING,
                    f"{k.entry.path.name}: the null lane's answer and gold equal the "
                    f"registered lane's on every item — if the null condition "
                    f"should change either, it measures no noise floor (an "
                    f"instrument that ignores its labels predicts the same in both "
                    f"lanes)",
                    fix="if the null should differ, give the instrument a null of its "
                    f"own, e.g. its predictions against permuted gold, then "
                    f"{measure_anew(area)}",
                    evidence_kind=STATIC_EVIDENCE,
                    rule=LAB_034,
                )
            )
    return NullLanes(out, examined)


def row_provenance_findings(
    answering_run: Path,
) -> tuple[list[GateFinding], list[str]]:
    """(blockers, notes): every JSONL output of the run is held to the runs
    its rows name (`_prov.run`): rows may come from this run, from the runs
    it continues (a resumed file, named in outputs.json), or — for a
    derived run — from its derived_from lineage. Rows from any other run
    are a blocker: a file of two measurements. Rows without `_prov` are a
    note (a Store without `prov`), not proof of anything. Rows
    of a continued run whose script differs from this run's are a blocker
    too (`_continued_with_other_code`; none where that run has no row in
    the file now): the number is that code's. A
    broken lineage (`runs.lineage`) is the one blocker: without
    it no row can be held to a run."""
    blockers: list[GateFinding] = []
    notes: list[str] = []
    try:
        allowed = {run.name for run in lineage(answering_run)}
    except ValueError as exc:
        return [
            blocker(
                f"row provenance: the lineage of {answering_run.name} is broken — {exc}",
                fix=measure_anew(answering_run.parent.parent),
                rule=TECHNICAL_RULE,
            )
        ], []
    for entry in read_outputs(answering_run) or []:
        if entry.path.suffix != ".jsonl" or output_file(entry) is None:
            continue
        try:
            rr = batch.row_runs(entry.path)
        except ValueError as exc:
            blockers.append(
                blocker(
                    f"{entry.path.name}: {exc}",
                    fix=measure_anew(answering_run.parent.parent),
                    rule=TECHNICAL_RULE,
                )
            )
            continue
        ok = allowed | set(entry.continues)
        foreign = sorted(r for r in rr.runs if r not in ok)
        if foreign:
            blockers.append(
                blocker(
                    f"{entry.path.name}: {sum(rr.runs[r] for r in foreign)} row(s) "
                    f"from {', '.join(foreign)} — a run this run neither is, "
                    f"continues nor derives from; a file of two measurements",
                    fix=f"{measure_anew(answering_run.parent.parent)}, into an output "
                    f"file of its own — a new name for the output in the measuring "
                    f"script, e.g. `{next_output_name(entry.path)}`; keep "
                    f"{entry.path.name} and its runs, never delete it: those rows are "
                    f"the other runs' evidence",
                    rule=LAB_057,
                )
            )
        if entry.continues:
            notes.append(
                f"{entry.path.name}: continues {', '.join(entry.continues)} "
                f"({', '.join(f'{r}: {n}' for r, n in sorted(rr.runs.items()))} rows)"
            )
            blockers += _continued_with_other_code(
                answering_run, entry.path, rr.runs, entry.continues
            )
        if rr.unstamped:
            notes.append(
                f"{entry.path.name}: {rr.unstamped} row(s) without _prov — written "
                f"outside a run or by a Store without prov; their run is unknown"
            )
    return blockers, notes


def _continued_with_other_code(
    answering_run: Path, path: Path, rows: dict[str, int], continued: tuple[str, ...]
) -> list[GateFinding]:
    """A blocker per run ANSWERING_RUN continues in PATH whose recorded
    script (`script_sha`) is not the answering run's, where the rows declare
    that they depend on code (`_instrument` carries `code_sha`, the
    estimator skeleton's): its ROWS were written by other code, and the
    number counts them as this run's: a fix measured again into the faulty
    run's file keeps every faulty row. Rows without it — a model's answers — do not
    depend on the script: a parser fix re-reads them. A continued run with
    no row in PATH now is passed over: no row of its code is counted, and
    the file is not the recorded one then, which `output_record_findings`
    holds (runlog names as continued only a run whose rows stand in the
    file at its end). A run whose record does not read is left to the
    record checks. Limits: the two runs' script digests are compared, not
    the `code_sha` the rows carry — a module the script imports, changed
    between the two runs, is not seen here; the estimator skeleton refuses
    it in the script (`batch.Store` with `instrument=` at the resume, the
    ledger's `expect` before a number), and a script that writes no such
    row identity is not covered. Code loaded another way than by import
    is in no digest."""
    own = read_run_config(answering_run)
    if own is None or not _rows_carry_code(path):
        return []
    out: list[GateFinding] = []
    for rid in continued:
        # no row of that run's code is in the file; that the file is not
        # the recorded one then is `output_record_findings`
        if rows.get(rid, 0) == 0:
            continue
        other = read_run_config(answering_run.parent / rid)
        if other is None or other.script_sha == own.script_sha:
            continue
        out.append(
            blocker(
                f"{path.name}: {rows[rid]} row(s) come from {rid}, which ran "
                f"other code (script {other.script_sha}, this run's "
                f"{own.script_sha}) — {answering_run.name}'s number counts that "
                f"code's rows as its own",
                fix=f"measure anew into an output file of its own — a new name for "
                f"the output in the measuring script, e.g. "
                f"`{next_output_name(path)}` — keep {path.name} and its runs, "
                f"then audit that run",
                rule=OPEN_RULE,
            )
        )
    return out


def _rows_carry_code(path: Path) -> bool:
    """Does a row of PATH name the code that wrote it (`_instrument` with a
    `code_sha`)? Raises ValueError on a file that does not read."""
    return any(
        isinstance(r.get("_instrument"), dict) and "code_sha" in r["_instrument"]
        for r in batch.Store(path).records()
    )
