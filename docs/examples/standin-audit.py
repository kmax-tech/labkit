"""STAND-IN for one analysis audit in the examples: the record
`labkit-audit AREA --mode analysis` writes, with labkit's own writer, on the
area's newest run and its protocol as it now reads — no model call.

    python standin-audit.py AREA [PLACE WHAT]

Without PLACE, a clean record; with it, one WARNING at
`<the protocol's file name>:PLACE` saying WHAT. Prints the record's path."""

import sys
from pathlib import Path

from labkit.checks import audit_binding
from labkit.formats import findings, promises, protocol_check, scope_sha

area = Path(sys.argv[1])
run = sorted((area / "runs").iterdir())[-1]
(protocol,) = area.glob("PROTOCOL-*.md")
text = protocol.read_text(encoding="utf-8")
found = []
if len(sys.argv) > 2:
    found = [
        (
            "WARNING",
            f"WARNING · {protocol.name}:{sys.argv[2]} · {sys.argv[3]} · "
            "LAB-015 Preflight audit before freezing",
        )
    ]
path = findings.write(
    area,
    "analysis",
    "walkthrough-stand-in",
    scope_sha.area_stamp(area)[0],
    promises.block_stamp(text),
    (0, len(found), 0),
    found,
    registration=protocol_check.registration_stamp(text),
    run_id=run.name,
    shown_sha=audit_binding.run_shown(area, run, "", text).sha,
)
print(
    f"wrote {path} — code {scope_sha.area_stamp(area)[0]}, run {run.name}, {len(found)} finding(s)"
)
