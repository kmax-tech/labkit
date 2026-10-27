# Recovery guidance and a handover with damaged evidence

*2026-10-27. Sources: the instruction review, `tests/test_counter_cases.py`,
and the recovery cases in `tests/test_handovers.py`.*

The plain unresolved-report route worked for a conflicting registration
with no open finding. It did not work with an open BLOCKER or a missing
audit record: the stop/commit checks still held. Replacing more guidance
with prose alone would preserve that dead end.

## Current contract

Read the experiment choices once and use the common workflow as a
reference. On a gate refusal, `labkit-audit AREA --findings` is the
read-only, no-model recovery entry: readable open BLOCKERs, explicit
journal/record errors, complete decision commands and the protocol-specific
handover command. It does not choose a scientific interpretation for the
author. With no audit yet it refuses: there is nothing to decide, and the area's
README and the repo's AGENTS.md name the next step. It offers the
handover only where an open BLOCKER, an evidence problem or a failed
audit call no completed audit covers stands (`0667f0a`); it is not a
second workflow engine. The handover itself works at any point, an
audit or not.

An unresolved readable BLOCKER is explicitly decided `deferred`, with the
reason, before handover. `deferred` is the decision on the finding; the
handover is what happens to the area — both hold at once, and no extra
status says so: the handover record lists the finding by record and
number (`remaining`), and `preflight` of another area tells a deferred
finding it lists as "handed over unresolved — no result released", any
other as "set aside for later work". Both stay listed; a handover settles
nothing. No command automatically decides or resolves a
finding. Even a readable record with an invalid filename retains its
findings in recovery inspection; naming errors are additional data.

`protocol-fill PROTOCOL --handover --why TEXT --tried TEXT --into REPORT`
creates an immutable schema-1 JSON record in `audits/handovers/`, withdraws
the protocol's result declaration and writes the record's handover block
into the report: one block per protocol, replaced in place, the rest of
the report kept. The block names the findings left open or deferred by
record file and number, never their text. Reports cannot be protocols or
evidence. Reasons and attempted
steps name the protocol, not run ids: a run cited in a report remains
subject to the result/discussion contract.

The handover record binds the protocol projection, the report it names,
available audit paths and blob ids, known expected paths, the unsettled
findings and explicit evidence errors. Raw evidence, including a malformed journal, is kept;
the handover does not append invented events to that journal. The format
has one home in `formats/handovers.py`. `attempts` keeps its normal loss
checks and also retains expected lost paths from handover records, so a
loss does not disappear when the handover commit becomes HEAD.

Only the stop/undecided commit check can acknowledge those exact integrity
gaps. It still checks every readable open BLOCKER. All protocols in the
area must declare no result, and the handover block and evidence must
match the handover in the state checked: tree at stop, index at commit. Missing
staging, a changed block or additional evidence invalidates the
acknowledgement; prose beside the block does not. A new handover can document the new state; older records
remain. Interrupted publication grants nothing before all files match.

Normal audits and result release use the original integrity checks, never
the terminal acknowledgement. Acknowledged loss is not restoration, an
upheld audit or provenance proof. Restoring evidence actually repairs the
gap; a handover does not. Free prose is still not mechanically proven true.

Same day, after the second audit
([register](../audit-2026-10-27-handover.md), H3): the first form wrote a
whole report and compared it byte for byte, and every printed command
named the same `REPORT.md`. A second area handed over there, or a
discussion block added later, voided the first acknowledgement, and the
report could not name the findings left open. The block form follows the
result and discussion blocks of `report_blocks`.

## Verification scope

The recovery tests use the real judge skeleton, simulated model answers
through the audit parser, the report writer and the stop/commit checks.
They cover missing never-staged records, malformed and non-UTF-8 journals,
open older findings behind a newer record, invalid record names, stale and
partially staged acknowledgements, protected report destinations, result
withdrawal and continuing refusal of normal audit/adoption.

A separate temporary-repository check invokes the actual CLI, installs
the generated hooks, stages the handover and commits through the installed
pre-commit hook. It succeeds with a missing audit record and a simulated
audit answer. Independent review also supplied the protected-destination,
renamed-record and unstaged-new-evidence counter-cases above.

Final verification: 2068 tests passed, one existing lock-file test skipped,
6429 subtests passed; Ruff checks/format and Pyright clean. Independent
review reported no remaining concrete findings.

These are mechanical recovery counter-cases, not a new live agent run or
evidence that an agent diagnoses scientific errors correctly. Historical
experiment instructions and pins remain as used in those experiments.
