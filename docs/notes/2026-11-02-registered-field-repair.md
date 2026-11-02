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
compares, with no list of field names:

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
