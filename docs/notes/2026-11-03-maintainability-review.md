# Maintainability review of repair guidance

2026-11-03. Code inspected: `e5fdf363`; subsequent main `a4710b40`
changes only Stagekit documentation. This is the bounded follow-up to the
[workflow simplification](2026-11-02-workflow-simplification.md), not a
whole-repository audit or a new scientific rule. No production code was
changed by this review.

## Consolidated review and work order

The [combined repair plan](2026-11-03-maintainability-repair-plan.md) owns
the current priorities and dispositions of these findings. It distinguishes
reproduced defects from inspection candidates and records overlaps and
contract decisions; the original observations below remain evidence for
the inspected state.

## Findings

### M1 — medium: presentation text controls withdrawal order

`report_check.held_declaration` searches finalized findings for the words
`changed since <declared run>`. `next_step._held_step` uses that result
to choose withdrawal alone, then reread the gates. The cause has already
been checked; the caller reconstructs it from its display text.

Probe: adopt A, change the measuring implementation and measure B. The
ordinary advice correctly says to withdraw A first. Replace only
`changed since` with the synonymous `differs from` in the finalized
findings. Grades, evidence kinds, fixes and experiment files stay the
same, but `held_declaration` becomes None and the next step asks for
another measurement into a renamed output. Withdrawing A actually
reveals B and requires its analysis audit, not a third measurement.

This is demonstrated refactoring fragility, not a spontaneous failure of
the unmodified program. It matters because editing a message can undo the
recent repair that prevents unnecessary measurement. Other control also
reads fix text (`next_step._refused_measurement`); that is a related
inspection target, not a separately reproduced defect here.

Smallest direction: carry the checked withdrawal requirement as data from
the relevant check to its callers. Do not infer it from prose and do not
reimplement the code/scope comparison. No workflow engine or stored status
is needed. Regression: rewording a finding must preserve withdrawal-first
order; unrelated blockers must not gain that requirement.

### M2 — medium: decision guidance reasons from a different state

`audit_decisions.repair_hint` and the gates share several comparison
helpers, but independently choose what action the current repair needs.
Two command paths still disagree:

| State | Decision hint | Gate-derived next step |
|---|---|---|
| Description corrected and measuring code changed before deciding the correction | No new measurement; follow up the correction | Measure again, then follow up on that run |
| Repaired code already measured as B before deciding the code finding on A | Measure again | Audit B |

In the first case the own-field branch returns before checking the code
change. In the second, a mismatch with the old audit record is treated as
proof that another measurement is needed, even though B already exists.
An old audit no longer covering the area does not establish the absence
of a current measurement.

Relevant sites: `audit_decisions.repair_hint`, `_awaiting_after_code`;
`finalize.scope_changes`; and the shared answering-run selection used by
`report_context.checked`. The probe uses the real commands and supplied
audit replies; it establishes contradictory guidance, not a false release.

Smallest direction: use the shared answering-run and code comparisons to
determine whether the implementation is already measured. Keep the old
record's review binding separate from that question. Tests must cover both
orders of decision and measurement, a description-only correction, and a
changed question beside a pending correction. Do not solve this by adding
another wording exception or by automatically deciding a finding.

## What to keep

The architecture and one-home checks, and the tested correction routes,
are useful constraints. Targeted validation: 28 tests and 48 subtests
passed (`test_architecture`, `test_one_home`, `test_adoption_order`,
`CorrectionThenNewRun`). Those tests pass despite M1 and M2: their missing
invariants are presentation independence and the two command orders above.

An AST comparison of exact function bodies with at least three statements,
excluding docstrings, found only two short identical exception constructors. This is no proof against
semantic duplication, but gives no reason for a bulk deduplication pass.
Large file size alone also supplies no reason to split modules or delete
tests. Start with the two demonstrated sources of drift.

## Evidence and next step

The executable probe, results and command log are in labkit-evidence,
commit `ca57d387`, `usability/2026-11-03-maintainability/`. It uses existing count-test
fixtures, preserves the evidence, and substitutes only model answers and,
for M1, the display wording in memory. No real model calls were made.

First make withdrawal order independent of display text; then reconcile
the decision hint with the current measurement. Keep them as separate,
small changes with correct counterparts. No additional audit duty,
provenance system, general stage table or broad module split follows from
this review.
