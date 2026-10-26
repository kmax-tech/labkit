"""Replay the twelve kept answers of pilot 2 through labkit-audit, no model call.

    .venv/bin/python replay_pilot2.py <scratchpad> <answers dir>

Each answer goes to a fresh copy of its case as it stood before the draw;
llm.complete returns the kept answer. Prints per draw: exit code, the FIX
verdict with check / check_present, the why's line count, and the record.
"""
import contextlib
import io
import shutil
import sys
from pathlib import Path
from unittest import mock

from labkit.formats import findings
from labkit.gates import audit

S, answers = Path(sys.argv[1]), Path(sys.argv[2])
for c in "ABCD":
    for d in (1, 2, 3):
        work = S / "pilot2" / "replay" / f"{c}-{d}" / "work"
        shutil.rmtree(work.parent, ignore_errors=True)
        shutil.copytree(S / "pilot2" / c / "work", work, symlinks=True)
        area = work / "experiments" / "01-bulk-modulus"
        text = (answers / f"{c}-{d}.report.txt").read_text(encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", lambda *a, **k: text),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            rc = audit.main([str(area), "--mode", "analysis", "--model", "opus"])
        new = [r for r in findings.area_records(area) if not r.path.name.startswith("2026-10-26T08-")]
        if len(new) != 1:
            print(f"{c}-{d} rc={rc} NO RECORD: {err.getvalue().strip().splitlines()[-1][:200]}")
            continue
        (v,) = new[0].fix_verdicts
        checked = [f"{f.check} ({len(f.check_note)} chars note)" for f in new[0].findings if f.check]
        kept = (area / "audits" / "answers").glob("*.txt")
        same = all(p.read_text(encoding="utf-8") == text for p in kept)
        print(f"{c}-{d} rc={rc} {v.verdict} check={v.check} present={v.check_present} "
              f"why={len(v.why.splitlines())} line(s) new checks={checked} answer kept={same}")
