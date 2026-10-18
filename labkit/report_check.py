"""report-check — the gate after the last step, before a number leaves the area.

    report-check <AREA> [--protocol PROTOCOL-*.md]

Exit codes: 0 clean, 1 a blocker, 2 usage error.

`finalize` holds the run before the number is written back; what follows it
— the analysis audit, the result written into its note, the note held to the
run by `02_analyze.py --check` — had no gate. In the cloud judge probe at
`minutes` (2026-10-14, draw 3) the agent skipped the check and the result
note, and finalize was green. A gate there cannot be finalize itself: finalize
comes before the analysis audit, so it cannot ask for what follows the audit.
report-check comes last and holds the whole chain:

  0. protocol      the named PROTOCOL-*.md or the area's only one; at
                   `cost = "seconds"` nothing is owed here (the short lane
                   ends with finalize, the audit comes when the number is
                   promoted — LAB-017 The number of audits follows the cost
                   tier) and the command exits 0
  1. frozen        `frozen = true`, and the freeze holds: no must gap
                   `protocol-check` names (`check_fields`) — the [[promise]]
                   tables written, not the stamp's `<…>` sentences
  2. finalize      `finalize_area` clean (its output is not repeated), and
                   the answering run it holds is a full run: `long=True`,
                   not acknowledged unfrozen (`runs.unreportable`) — a
                   reported number owes a frozen full run; a probe's or an
                   acknowledged run's number cannot be reported (second
                   haiku round on 0.98.0: t3 and t18 reported a probe, t5
                   an acknowledged run; plan 2026-10-17, A3)
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
                   them)

Every station runs; the blockers are summed at the end. It reads and runs,
never writes.
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
from labkit.finalize import finalize_area
from labkit.preflight import area_test_python
from labkit.protocol_check import check_fields
from labkit.repo import choose_protocol, layout_root
from labkit.runs import read_run_config, unreportable
from labkit.scope_sha import area_stamp

#: the analysis script the area skeleton stamps; its `--check` holds the note
ANALYZE_SCRIPT = Path("scripts") / "02_analyze.py"
#: how long `--check` may take inside the gate (audit 2026-10-15: no limit)
CHECK_TIMEOUT_S = 300.0


def check_analysis_script(area: Path, repo: Path) -> str | None:
    """Why `02_analyze.py --check` does not pass, or None: missing, or a
    nonzero exit with the last lines it printed."""
    script = area / ANALYZE_SCRIPT
    if not script.is_file():
        return f"no {ANALYZE_SCRIPT} — the check that holds the note to the run is owed"
    try:
        r = subprocess.run(
            [area_test_python(repo), str(script), "--check"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"{ANALYZE_SCRIPT} --check did not finish in {CHECK_TIMEOUT_S:g} s"
    if r.returncode == 0:
        return None
    tail = (r.stderr.strip() or r.stdout.strip() or "no output").splitlines()[-3:]
    return f"{ANALYZE_SCRIPT} --check exits {r.returncode}: " + " | ".join(tail)


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


def unreportable_gaps(area: Path, protocol: Path) -> list[str]:
    """Station 2, the run: why the answering run's number cannot be reported
    (`runs.unreportable`), each a blocker. Without an answering run there is
    nothing to hold — finalize says so."""
    try:
        run_dir, _ = audited_run(area, protocol)
    except AuditError as exc:
        return [f"the answering run cannot be chosen: {exc}"]
    if run_dir is None:
        return []
    cfg = read_run_config(run_dir)
    if cfg is None:
        return [f"{run_dir.name}: no config.json — not a run"]
    return [
        f"the answering run {run_dir.name}: {mark} — its number cannot be "
        f"reported; a reported number owes a full run (long=True) on a frozen protocol"
        for mark in unreportable(cfg)
    ]


def later_gaps(area: Path, protocol: Path) -> list[str]:
    """Stations 2–4: finalize clean and its run a full run, an analysis audit
    of the area now, the check."""
    out: list[str] = []
    with contextlib.redirect_stdout(io.StringIO()):
        finalized = finalize_area(area, protocol)
    if finalized != 0:
        out.append(f"finalize {area} has blockers — run it to see them")
    out += unreportable_gaps(area, protocol)
    gap = analysis_audit_gap(area, protocol)
    if gap:
        out.append(f"analysis audit: {gap} (LAB-050 Analysis audit before reporting)")
    failed = check_analysis_script(area, layout_root(area))
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
    if head.cost == "seconds":
        print(
            f'report-check: {chosen.name} is at cost = "seconds" — nothing owed here; '
            f"the short lane ends with finalize (LAB-017 The number of audits follows the cost tier)"
        )
        return 0
    findings = Findings()
    for b in freeze_gaps(chosen, head.frozen) + later_gaps(area, chosen):
        findings.block(b)
    if not findings.blocked:
        print(f"  {chosen.name}: frozen, finalized, audited, checked")
    return findings.report("report-check", "reporting")


def main(argv: list[str]) -> int:
    """Command line of `report-check`."""
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
