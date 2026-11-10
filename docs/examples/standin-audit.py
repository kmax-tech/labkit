"""STAND-IN for one analysis audit in the examples: the record
`labkit-audit AREA --mode analysis` writes, with labkit's own writer, on the
area's newest run and its protocol as it now reads — no model call.

    python standin-audit.py AREA [PLACE WHAT [SUBJECT]]

Without PLACE, a clean record; with it, one WARNING at
`<the protocol's file name>:PLACE` saying WHAT, about SUBJECT
(`implementation` or `statement`, the default) — for `undetermined` a
BLOCKER closing with the check that settles it, as the format owes
(`findings.undetermined_finding_problem`). Prints the record's path."""

import sys
from pathlib import Path

from labkit.checks import audit_binding
from labkit.formats import findings, promises, protocol_block, protocol_check, scope_sha

area = Path(sys.argv[1])
run = sorted((area / "runs").iterdir())[-1]
(protocol,) = area.glob("PROTOCOL-*.md")
text = protocol.read_text(encoding="utf-8")
found = []
subject = sys.argv[4] if len(sys.argv) > 4 else findings.STATEMENT
grade = "BLOCKER" if subject == findings.UNDETERMINED else "WARNING"
check = (
    " · check: hidden_files_counted — confirms if above 0, clears if 0"
    if subject == findings.UNDETERMINED
    else ""
)
if len(sys.argv) > 2:
    found = [
        (
            grade,
            f"{grade} · {protocol.name}:{sys.argv[2]} · {subject} · {sys.argv[3]} · "
            f"LAB-015 Preflight audit before freezing{check}",
        )
    ]
path = findings.write(
    area,
    "analysis",
    "walkthrough-stand-in",
    scope_sha.area_stamp(area)[0],
    promises.block_stamp(text),
    (
        sum(g == "BLOCKER" for g, _ in found),
        sum(g == "WARNING" for g, _ in found),
        0,
    ),
    found,
    registration=protocol_check.registration_stamp(text),
    protocol_id=protocol_block.head(text).id or "",
    run_id=run.name,
    shown_sha=audit_binding.run_shown(area, run, "", text).sha,
)
print(
    f"wrote {path} — code {scope_sha.area_stamp(area)[0]}, run {run.name}, {len(found)} finding(s)"
)
