# One report binding at both repeat costs

2026-11-03. N4 of the [combined plan](2026-11-03-maintainability-repair-plan.md).
Max authorized the same committed-first-measurement binding at low and
high, and refusal of late report registration when no first measurement
registered one. This is an announced behavioural break, not a run-schema
or scientific-standard change; 0.107.0 is the last release with the old
behaviour.

**Problem.** The report setter refused changes on both lanes, but the
historical gate compared only low registrations. Preflight's promise and
registration digests do not bind the report field. Freeze therefore did
not supply the missing report-path guarantee. Low also allowed a manually
added late report while its setter refused it.

**Contract.** `report_hold.bound_reports` reads every first measurement's
committed head without a lane filter. `report_binding_gap` compares that
value (including None) with the supplied head, with normalized paths.
Unchanged/restored values pass; removal, redirection and late registration
hold with restoration or handover/new-registration as the way out.
Unreadable first commits are held while a report obligation is visible;
low's registration station already reports those commits, so the binding
station suppresses only that duplicate. A missing first run cannot prove
a visible report binding either; restore the run evidence. Absence of a
Git repository remains outside historical binding, as at the release gate.

The setter previews only report assignments with the normal editor and
asks this same gate. Previewing with force lets a binding refusal precede
the ordinary overwrite refusal; the actual write still requires --force
for a different current path. Restoration is now allowed through the
setter too. There is no new spelling for deleting a report field: invalid
path values remain invalid. Removing the head entry by hand is checked
against the same original binding.

The start check reads HEAD's report path on both lanes before the first
measurement; uncommitted report changes refuse the start. Low's other
committed-registration requirements and high's freeze/preflight remain
separate, since they establish different conditions.

**Verification.** The same historical, setter and start tests run at both
repeat costs. They cover equivalent path spelling, removal/redirection,
restoration, late registration, conflicting first measurements, unreadable
history, staged selection by area/former report, and switching low to high.
The high start test isolates preflight-audit coverage while checking report
commitment; it does not claim to validate an auditor's semantic judgement.
A current protocol-specific handover ends the obligation at stop/commit
without releasing a result; its delivered report still owes the report
review. `protocol_handed_over(..., staged=True)` checks the index's actual
handover and protocol before that endpoint bypasses the historical binding.
Any later protocol edit invalidates the handover and restores the hold.
The test isolates report review from binding; the existing repair-path
suite exercises the report review itself with fixed model replies.
A successor is registered in a new area, preserving the predecessor's
handover. Adding another unadopted protocol in the old area is not itself
refused; adopting a result there would violate the handover's area-wide
requirement that no protocol declares a result.
