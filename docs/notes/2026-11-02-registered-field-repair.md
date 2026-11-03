# 2026-11-02 — a field corrected after the audit, followed to the gate

**Problem.** labkit-paper area 17, c17-t34-labkit-demand-r1 (labkit
0.107.0): the analysis audit flagged the registered Unit field; the agent
rewrote it, decided the finding `fixed`, and `labkit-audit --decide`
answered "measure again". The new run carried the rewritten Unit, and
finalize held it as a change of what the number is about — four audit
rounds later. A probe on labkit `82dfa297` with the count task (record
stand-ins, every other step a real command; internal evidence: labkit-
evidence `usability/2026-11-02-c17-timeouts/probe-registered-field/`)
showed three faults:

1. the decision's line said "measure again" for any edit that moved the
   audited state, a registered field included, and "nothing relevant
   changed … measure and audit again" for a Conclusion rewrite, which owes
   neither;
2. `labkit-next` named only a new audit; an audit of the first run on the
   rewritten Unit or Terms adopted it — the scope hold compared the runs'
   snapshots alone, and the answering run, a first measurement itself, had
   nothing to compare;
3. the rule of 2026-10-28 (a description in the setup corrected in place,
   judged by the follow-up) and the scope hold of 2026-10-31 (a run under a
   changed field is held) left a correction no way through, while the
   unjudged route of 2 stood open.

**Solution.** One correction route, for every prose field the hold
compares, with no list of field names (Question / hypothesis excepted by
the decision of 2026-11-03 below):

- the scope hold compares the protocol as it stands with the first
  measurements too (`finalize.scope_changes`; the comparison is
  `protocol_history.first_measured_differences`, shared with the decision's
  line); the run snapshots are compared first, as before;
- a correction in place is a finding that names the field as its place —
  `<protocol file>:<label>`, the whole label (`Finding.place`,
  `protocol_check.named_field`; a line number or part of a label names no
  field) — decided `fixed` (`findings.corrected_field`);
- the follow-up audit is shown such corrections at every grade beside the
  earlier BLOCKERs (`followup.earlier_corrections`), each with the field as
  the first measurement registered it and as it reads now
  (`audit_prompt.FieldChange`), and judges whether the change describes the
  same run or redefines it (`experiment-preflight.agent.md`);
- finalize releases a field's change only on a `resolved` on that
  correction, bound to the decision as it stands, in an analysis record
  that covers the area now (`finalize.resolved_corrections`) — and names
  each released correction with its old and new value and the verdict's
  why (`corrected_in_place`);
- the decision's line says what the repair owes by what it changed
  (`audit_decisions.repair_hint`): a correction — no new measurement, the
  follow-up's `resolved`; another departure — the way back, the correction
  route, a new registration, never "measure again"; changed code — measure
  again; only the fields read before the run — audit again; nothing the
  record binds — no measurement and no analysis audit by itself (a
  BLOCKER `fixed` in the audited state still waits for its follow-up; the
  decision and report reviews owed stand).

**The protection that works for a moved bar.** Checked before anything
changed there (fit-assay, margin 0.25 → 0.20 after the first measurement):
the intent check holds the run's recorded promise block against the
protocol's at once (`promises` "the promises changed after the run"), the
analysis script's check refuses the same, a new measurement is held by the
registration station (K3), and the restored margin passes. A bar is a
promise, not a field: it has no correction route.

**Limits.** Whether a change describes or redefines is the follow-up
auditor's judgement (agent audit); labkit holds only the binding — the
named field, the decision, the verdict, the state. A run measured under a
corrected field is still held by the snapshot comparison: a correction
releases the unchanged run, not a new one. The decision's line names a
correction only when the decided finding is one; the follow-up shows a
correction even where its field has not changed.

**Twins.** `tests/test_end_to_end.py` `CorrectedDescription` (the
`resolved` path through the real `labkit-audit`: BLOCKER and WARNING
released; no verdict, another field, a later edit, a line-number place and
an `unresolved` redefinition held), `tests/test_repair_paths.py` (the
whole path in a staged lab: edit, decision, `labkit-next`, the named
action, the gate; Conclusion and code repair as twins, the restore),
`tests/test_registration_committed.py` `ScopeAsFirstMeasured` (the tree
compared; restore, reflow and a Conclusion pass), `tests/test_findings.py`
`CorrectedField`.

## Decided 2026-11-03: where a correction ends (contract change, in part built)

**Problem.** F6 of the repair-path probe
([note](2026-11-02-repair-path-probe.md)): Question / hypothesis "mean" →
"median", decided `fixed`, a stand-in `resolved` — adopted. The agent guide
says "in place, never change … the question"; the route above releases
every field the hold compares. A `resolved` shows only that labkit accepts
the stored verdict, not that it is right — and before the record's first
commit not even where it came from
([note](2026-11-02-review-record-forgery.md)). LAB-003's "in a prose field
nothing holds it" predates the scope hold.

**Contract.**

- A correction in place repairs a false description of the unchanged run.
  It never changes a requirement fixed before the run: the question, which
  items count, the rule that drops items, the statistic, what the unit
  means.
- The deciding question for every disagreement between a held field and
  the run: did the old text misdescribe what the run, as required, did — or
  did it state a requirement the run failed? The first is a correction.
  The second is a data or implementation error: repair the run and measure
  again, or, if the requirement itself is to change, register anew. The
  same words can be either: "14 cases" is a miscount when the registered
  set has 12, and a requirement when the task or the registration asks for
  14; "test split" is a wrong label when the registration otherwise names
  the set the run read and nothing asks for the test split, and a
  requirement when the task does. The answer rests on evidence outside the
  changed field — the task, the other registered fields, the data's
  producer — not on whether the new text fits the run.
- Question / hypothesis has no correction route, like the head's kind,
  `[kept]` and `[reference]`: it states the requirement itself, so it
  stands as registered, a typo included. A different question is a new
  protocol; `[replaces]` only when the registration cannot be answered as
  written or was incomplete at its first measurement. This makes the
  guide's existing rule mechanical; it adds no class of fields.
- A release belongs to the run it judged. A new run measured under a
  corrected field is released only by a follow-up that judges the
  correction against that run's inputs and rows; the earlier `resolved`
  alone releases nothing for it (shared with the repair that corrects a
  description and then the code, F5).

Who decides what:

1. labkit (guaranteed): which held field changed, from what to what; code,
   data and run unchanged since the audit; the correction bound to finding,
   decision, text and run; promises, kind, `[kept]`, `[reference]` and now
   Question / hypothesis never released.
2. The follow-up auditor (agent audit): whether the old text misdescribed
   the run or stated a requirement it failed, on evidence it cites outside
   the changed field; whether the new text matches the run's inputs and
   rows.
3. A new registration (existing rule): a changed question, statistic,
   population or exclusion rule.

| Change | Way |
|---|---|
| Typo in Terms, Data / scope, Exclusions / filters, Unit | correction, or leave the typo |
| Typo in Question / hypothesis | restore; it stands as registered |
| Data / scope "14 cases" → "12", the run read 12 | the registered set has 12: correction; 14 were required: data or implementation error — repair, measure again |
| Data / scope "test split" → "dev split", the run read dev | "test" a demonstrably wrong label for the set the registration names: correction; the task asks for the test split: repair the run onto it — or a new protocol |
| mean → median in a promise or the question | held; code computes the median: implementation error; code computes the mean: new protocol |
| mean → median in Terms or Unit | the auditor's `unresolved`; a wrong `resolved` releases it, and finalize's note names old, new and why — the limit of this tier |
| exclusion rule changed in the text only | restore |
| exclusion rule changed in text and code, measured again | held by the snapshot comparison: new registration |
| the same exclusion rule rephrased to match the code | correction |

**Acceptance cases** (beside the twins above): a Question typo `fixed` and
`resolved` is held, and hold and decision line name the way back or a new
protocol, not the correction route; its restore passes; Question "mean" →
"median" with a `resolved` is held; a Unit typo with a `resolved` is still
released; Terms "mean" → "median" with a stand-in `resolved` is released
and the note names the change (the limit, kept visible); a correction
`resolved` for one run, then code repaired and measured again — the old
verdict does not release the new run, a follow-up on the new run that
judges the correction again does; after a released correction, a code
repair is told to measure again. These are the mechanical consequences and
go into labkit's tests. Which side of the pairs "14 cases" and "test
split" a case falls on is the auditor's judgement: it needs probes of the
auditor's instruction with a real model.

**Today against this contract** (F5 reproduction on `4ab018bf`, labkit-
evidence `921eab7e`, `usability/2026-11-03-correction-then-code-fault/`): an earlier
`resolved` already does not release a new run. But a follow-up on the new
run that judges the correction `resolved` does not release it either:
the first branch of `finalize.scope_changes` (the text the answering run
saw against the first measurement) reads no correction; only `scope_now`
(the text as it stands) does. The release belongs in that branch too,
bound to: the field's text the new run saw, the text now and the text the
`resolved` judged are one; the record covers the new run; the field is
correctable. The guidance is wrong there as well: after a released
correction, `--decide` on a code repair answers "restore … decide the
finding again" and `labkit-next` "restore"; both owe "measure again; the
follow-up on the new run judges the correction again". The only way
through in the same protocol today restores the known-false text (three
runs, eight analysis records); a successor with `[replaces]` passes.

**Places.** `findings.corrected_field` (the one home of the exception;
`followup.earlier_corrections`, `finalize.resolved_corrections`,
`audit_decisions.repair_hint` and `labkit-next` read it); the first branch
of `finalize.scope_changes` (the new run's release); the hold in
`finalize.registration_changes`, the decision line and `labkit-next` offer
the correction route only for a correctable field and name "measure again"
after a code repair; `finalize.scope_now`'s docstring;
`labkit/docs/agent-guide.md` (the correction route as its own way out,
apart from the incomplete registration); LAB-003's typo sentence; later,
the follow-up auditor's instruction (`experiment-preflight.agent.md`: the
deciding question above, and the evidence outside the field its `resolved`
cites); CHANGELOG (behaviour, no format break).

**Built.** The question's exception: `protocol_history.correctable`
(`UNCORRECTABLE_FIELDS`), read by `findings.corrected_field` and by
`finalize.correction_way`, the clause the scope hold and the decision's
line give — the correction route only for a changed field it can release,
the question standing as registered, nothing for the head's parts or a
promise (the decision's line had offered the route for a changed promise
too). Twins: `tests/test_end_to_end.py` `CorrectedDescription` (a changed
question held with its `resolved`, its restore, a reflowed question, a
description still offered the route), `tests/test_finalize.py`
`CorrectionWay`, `tests/test_findings.py` `CorrectedField`. Open: the new
run's release and the "measure again" guidance (F5), the agent guide's
correction bullet, LAB-003's typo sentence, the auditor's instruction.

**Not in this contract.** Showing a released correction in the report —
today only finalize's note names it; noted separately, no new report
format here.
