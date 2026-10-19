"""report-check — the gate after the last step, before a number leaves the area.

    report-check <AREA> [--protocol PROTOCOL-*.md]
    report-check --if-reported PROTOCOL-*.md ...   every protocol whose answer
                                                   cites a run (the stop hook
                                                   and the pre-commit)

Exit codes: 0 clean, 1 a blocker, 2 usage error.

`finalize` holds the run before the number is written back; what follows it
— the analysis audit, the result written into its note, the note held to the
run by `02_analyze.py --check` — had no gate. In the cloud judge probe at
`minutes` (2026-10-14, draw 3) the agent skipped the check and the result
note, and finalize was green. A gate there cannot be finalize itself: finalize
comes before the analysis audit, so it cannot ask for what follows the audit.
report-check comes last and holds the whole chain, at every cost tier:

  0. protocol      the named PROTOCOL-*.md or the area's only one
  1. frozen        at `minutes`/`hours`: `frozen = true`, and the freeze
                   holds: no must gap `protocol-check` names
                   (`check_fields`) — the [[promise]] tables written, not
                   the stamp's `<…>` sentences. At `cost = "seconds"` no
                   freeze and no preflight audit are owed
                   (LAB-017 The number of audits follows the cost tier), so
                   this station is skipped and says so; until 0.99.0 the whole
                   command exited 0 there, and a probe's number passed as
                   a reported one (TODO 1, 2026-10-19)
  2. finalize      `finalize_area` clean — its blockers are named here —
                   so the answering run is bound to this protocol and the
                   answer cites it; and that run is a full run: `long=True`,
                   not acknowledged unfrozen (`runs.unreportable`) — a
                   reported number owes a full run (frozen at
                   minutes/hours); a probe's or an acknowledged run's number
                   cannot be reported (second haiku round on 0.98.0: t3 and
                   t18 reported a probe, t5 an acknowledged run; plan
                   2026-10-17, A3)
  3. analysis audit  a record `audits/*-analysis.toml` whose `scope_sha` is
                   the area's stamp now, whose `block_sha` is the promise
                   block now and whose `run_id` is the answering run, every
                   finding decided (`findings.audit_coverage`) — code or
                   promises changed after the analysis audit, or a later
                   run, owe a new one (LAB-050 Analysis audit before
                   reporting)
  4. the check     `scripts/02_analyze.py --check` exits 0 under the repo's
                   interpreter: the rows recompute to the run's metrics and
                   the note it names carries every number and the run_id
                   (`recheck.holds`; LAB-041 Generate numbers, don't retype
                   them). At seconds the counting skeleton stamps no
                   analysis script, its `01_measure.py --check` is the
                   recheck (`check_script`); until 0.99.0 this station
                   demanded `02_analyze.py` there and refused every
                   correct count (audit 2026-10-19)

Every station runs; the blockers are summed at the end. It reads and runs,
never writes.

`--if-reported` is the gate the agent cannot choose: `claude-hook stop`
runs it on every changed PROTOCOL-*.md, the stamped pre-commit on every
staged one, and it holds exactly the protocols whose "Answer to the
question" cites a run (`finalize.cited_runs`) — the one line that declares
a result reported, written by `protocol-fill --from-run`. A protocol whose
answer is still open owes nothing here: an exploration ends with no
reported result, probes or not (third haiku round on 0.99.0: t3 and t5
reported a probe's number and never called report-check; TODO 2,
2026-10-19). finalize stays the check before the analysis audit; this is
the check after it.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import subprocess
from pathlib import Path

from labkit.gate import Findings
from labkit import console, findings, promises, protocol_block
from labkit.audit import AuditError, audited_run
from labkit.finalize import cited_runs, finalize_area
from labkit.preflight import area_test_python
from labkit.protocol_check import check_fields
from labkit.repo import choose_protocol, layout_root
from labkit.runs import read_run_config, unreportable
from labkit.scope_sha import area_stamp

#: the analysis script the full skeleton stamps; its `--check` holds the note
ANALYZE_SCRIPT = Path("scripts") / "02_analyze.py"
#: the counting skeleton's one script (`labkit-init exp --cost seconds` without
#: a model): it carries the `--check` itself, no analysis script is stamped
MEASURE_SCRIPT = Path("scripts") / "01_measure.py"
#: how long `--check` may take inside the gate (audit 2026-10-15: no limit)
CHECK_TIMEOUT_S = 300.0


def check_script(area: Path, at_seconds: bool) -> Path | None:
    """The script whose `--check` station 4 runs, relative to AREA, or None
    when the area has none: `02_analyze.py` where the area has one; at
    seconds, where the counting skeleton stamps only `01_measure.py` with
    the `--check` inside (`scaffold.stamp_scripts`, quick), that script."""
    if (area / ANALYZE_SCRIPT).is_file():
        return ANALYZE_SCRIPT
    if at_seconds and (area / MEASURE_SCRIPT).is_file():
        return MEASURE_SCRIPT
    return None


def check_analysis_script(area: Path, repo: Path, at_seconds: bool) -> str | None:
    """Why the area's `--check` (`check_script`) does not pass, or None:
    no script, or a nonzero exit with the last lines it printed."""
    script = check_script(area, at_seconds)
    if script is None:
        owed = (
            f"{ANALYZE_SCRIPT} and no {MEASURE_SCRIPT}"
            if at_seconds
            else ANALYZE_SCRIPT
        )
        return f"no {owed} — the check that holds the note to the run is owed"
    try:
        r = subprocess.run(
            [area_test_python(repo), str(area / script), "--check"],
            cwd=repo,
            capture_output=True,
            text=True,
            errors="replace",  # the tail is quoted, not parsed: a byte no
            # codec reads must not raise out of the gate (audit 2026-10-19)
            timeout=CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"{script} --check did not finish in {CHECK_TIMEOUT_S:g} s"
    if r.returncode == 0:
        return None
    tail = (r.stderr.strip() or r.stdout.strip() or "no output").splitlines()[-3:]
    return f"{script} --check exits {r.returncode}: " + " | ".join(tail)


def freeze_gaps(protocol: Path, frozen: bool) -> list[str]:
    """Station 1: why the freeze does not hold — the flag unset, or a must
    gap protocol-check names (the stamp's `<…>` promise sentences among them)."""
    gaps = [] if frozen else ["not `frozen = true` — a reported number owes the freeze"]
    report = check_fields(protocol.read_text(encoding="utf-8"))
    gaps += report.missing_must
    # a must field still holding its `<…>` placeholder passed here while
    # protocol-check and preflight refused it (audit 2026-10-15)
    gaps += [f"line {n}: {label} still a placeholder" for n, label in report.must_holes]
    return [f"{protocol.name}: {g}" for g in gaps]


def analysis_audit_gap(area: Path, protocol: Path) -> str | None:
    """Station 3: why no decided analysis record covers the code, the promise
    block and the answering run as they are now, or None. Without an
    answering run there is nothing the audit could be held to."""
    try:
        run_dir, why = audited_run(area, protocol)
        if run_dir is None:
            return f"no answering run to hold it to — {why}"
        return findings.audit_coverage(
            area,
            area_stamp(area)[0],
            "analysis",
            promises.block_stamp(protocol.read_text(encoding="utf-8")),
            run_dir.name,
        )
    except (FileNotFoundError, ValueError, AuditError) as exc:
        # ValueError: nothing to stamp, a findings file or the promise block
        # unreadable (FindingsError, PromiseError); AuditError: the head
        return f"the analysis audit cannot be held to the area: {exc}"


def unreportable_gaps(area: Path, protocol: Path, freeze_owed: bool) -> list[str]:
    """Station 2, the run: why the answering run's number cannot be reported
    (`runs.unreportable`), each a blocker. Without an answering run there is
    nothing to hold — finalize says so. FREEZE_OWED names the freeze in the
    sentence (minutes/hours); at seconds a full run is owed, no freeze."""
    try:
        run_dir, _ = audited_run(area, protocol)
    except AuditError as exc:
        return [f"the answering run cannot be chosen: {exc}"]
    if run_dir is None:
        return []
    cfg = read_run_config(run_dir)
    if cfg is None:
        return [f"{run_dir.name}: no config.json — not a run"]
    owed = "a full run (long=True)" + (" on a frozen protocol" if freeze_owed else "")
    return [
        f"the answering run {run_dir.name}: {mark} — its number cannot be "
        f"reported; a reported number owes {owed}"
        for mark in unreportable(cfg)
    ]


def finalize_gaps(area: Path, protocol: Path) -> list[str]:
    """Station 2, the gate before: finalize's blockers, each named here with
    its prefix — inside the stop hook "run it to see them" was a round trip
    the agent did not take. Exit 2 (no protocol to hold) is one blocker."""
    collected = Findings()
    with contextlib.redirect_stdout(io.StringIO()):
        finalized = finalize_area(area, protocol, collected)
    if finalized == 0:
        return []
    if collected.blocked:
        return [f"finalize: {b}" for b in collected.blocked]
    return [f"finalize {area} exits {finalized} — run it to see why"]


def later_gaps(area: Path, protocol: Path, freeze_owed: bool = True) -> list[str]:
    """Stations 2–4: finalize clean and its run a full run, an analysis audit
    of the area now, the check."""
    out = finalize_gaps(area, protocol)
    out += unreportable_gaps(area, protocol, freeze_owed)
    gap = analysis_audit_gap(area, protocol)
    if gap:
        out.append(f"analysis audit: {gap} (LAB-050 Analysis audit before reporting)")
    failed = check_analysis_script(area, layout_root(area), not freeze_owed)
    if failed:
        out.append(f"{failed} (LAB-041 Generate numbers, don't retype them)")
    return out


def report_check(area: Path, protocol: Path | None = None) -> int:
    """Run the stations on AREA; 0 clean, 1 a blocker, 2 no protocol to hold."""
    chosen = choose_protocol(area, protocol, "report-check")
    if chosen is None:
        return 2
    try:
        head = protocol_block.head(chosen.read_text(encoding="utf-8"))
    except protocol_block.BlockError as exc:
        print(f"report-check: {chosen.name}: {exc}")
        return 2
    freeze_owed = head.cost != "seconds"
    findings = Findings()
    if freeze_owed:
        gaps = freeze_gaps(chosen, head.frozen)
    else:
        gaps = []
        print(
            f'  {chosen.name}: cost = "seconds" — no freeze and no preflight audit '
            f"owed (LAB-017 The number of audits follows the cost tier); the full "
            f"run, the analysis audit and the check are"
        )
    for b in gaps + later_gaps(area, chosen, freeze_owed):
        findings.block(b)
    if not findings.blocked:
        held = ("frozen, " if freeze_owed else "") + "finalized, audited, checked"
        print(f"  {chosen.name}: {held}")
    return findings.report("report-check", "reporting")


def if_reported(protocols: list[Path]) -> int:
    """`report-check` for every protocol whose "Answer to the question" cites
    a run — the gate at the stop and the commit: a result declared reported
    is held to the whole chain, a protocol whose answer is still open is
    skipped (an exploration may end with no reported result). Returns the
    worst exit code."""
    worst = 0
    for protocol in protocols:
        try:
            text = protocol.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"report-check: {protocol}: {exc}")
            worst = max(worst, 2)
            continue
        cited = cited_runs(text)
        if not cited:
            continue
        print(f"═══ report-check {protocol} (its answer cites {', '.join(cited)}) ═══")
        worst = max(worst, report_check(protocol.parent.resolve(), protocol))
    return worst


def main(argv: list[str]) -> int:
    """Command line of `report-check`."""
    if argv and argv[0] == "--if-reported":
        return if_reported([Path(a) for a in argv[1:]])
    ap = argparse.ArgumentParser(
        prog="report-check", description=(__doc__ or "").split("\n\n")[0]
    )
    ap.add_argument("area", type=Path)
    ap.add_argument("--protocol", type=Path, default=None)
    a = ap.parse_args(argv)
    if not a.area.is_dir():
        print(f"report-check: {a.area} is not a directory")
        return 2
    return report_check(a.area.resolve(), a.protocol)


def cli() -> None:
    """Console entry point `report-check`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
