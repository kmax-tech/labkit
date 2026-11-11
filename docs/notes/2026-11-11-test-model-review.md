# Independent review of the rule tests (2026-11-11)

> Review of `00aaeaad`, against the baseline `524b93ce` and the [test-model plan](2026-11-10-test-model.md). The reviewer did not author the migration. Verdict: the review is complete, but target 4 remains open because one removed assertion has no adequate replacement. This review approves neither the open rule assignments nor the undecided second-review policy.

## Finding: medium — a removed scenario's replacement misses its caller

**Kind:** test coverage regression. The current implementation is correct in the reproduced case; the defect is in the claim that the removed test's protection is preserved.

`tests/test_rules_registration_hold.py:207` supplies `{"Data / scope"}` directly to `split_released`. This tests what happens when the field is already known to have changed after the answering run. It does not test whether `registration_hold.released_fields` computes that set from the run's text and the current protocol and passes it on (`labkit/gates/registration_hold.py:647`). The removed `CorrectionThenNewRun.test_a_field_edited_after_the_new_run_holds` exercised that connection. Its replacement entry in `2026-11-10-scenario-review.tsv:69` names the pure test and retained command routes, but those routes do not assert this case.

**Why it matters:** a follow-up can judge the current description while the answering run measured under a different description. Without the comparison with the run's text, a favourable verdict on today's text releases the run incorrectly. This is the three-way equality required by `released_fields`' contract and the author decision in [registered-field repair](2026-11-02-registered-field-repair.md), “Decided 2026-11-03”.

**Reproduced without editing the checkout:** in the pytest process only, replace `registration_hold.moved_fields` with `lambda seen, text: set()`. The following current tests remain green together: all of `test_rules_registration_hold.py`, `test_registration_binding.py`, `test_finalize_steps.py`, both retained correction scenario classes (`CorrectedDescription`, `CorrectionThenNewRun`), and `TheLineExplainsAndPointsToNext.test_a_field_edited_after_the_new_run_then_released_on_it` in `test_repair_guidance.py`. Result: 76 passed, 37 subtests passed, exit 0. The last test constructs the relevant state but asserts the decision hint, not finalize's refusal.

As a positive control, restore only the removed method `CorrectionThenNewRun.test_a_field_edited_after_the_new_run_holds` from `524b93ce` to the current class at collection time, with its original `RIGHT_TOO` value. On the unchanged implementation it passes (1 passed, exit 0). With the same mutation it fails (1 failed, exit 1): `held_as_b_saw` expects finalize exit 1 but receives exit 0. The real output says `finalize: 0 blockers, 1 warning(s)` and treats the changed Data / scope as corrected in place. This establishes a lost assertion rather than inferring a gap from a search.

**Required correction:** add a gate composition test through `released_fields`, passing two real protocol texts and stubbing only the resolved correction lookup. A field edited after the run must stay held even when today's text has a resolved correction; the twin with equal field values must release it. The test must fail when `moved_fields` returns the empty set or its result is discarded at the call to `split_released`. Keeping the old scenario is also sufficient. The frozen scenario table remains historical evidence; this note corrects its replacement claim.

## Scope and other conclusions

Read the three new `test_rules_*.py` files against their implementations, the extracted readers and gate callers, the removed correction scenarios, and the cited standard and registered-field repair decisions. The run-record tests distinguish guaranteed byte and presence checks from static evidence about denominators and null lanes. The audit tests keep an undecided finding distinct from an unreadable record and a deleted audited run. The correction tests exercise decision digests, verdicts, individual fields and the question's exclusion from correction in place. These conditions are appropriate at their stated layer; they do not replace a check that the gate supplies the right facts, as the finding demonstrates.

The ten deferred sites in `report_decisions.py`, the 179 open rule assignments, scanner completeness and the timing measurements were not reapproved by this review. The full suite was not rerun; this was an assertion and contract review with focused execution, not another timing run.

## Verification

- Unmodified code: 105 tests and 43 subtests passed, exit 0, across the three rule files, registration binding, finalize stations and guard tests.
- Unmodified code: 276 tests and 104 subtests passed, exit 0, in an additional focused run covering the three rule files, rule metadata, forwarding architecture, output readers, null lanes, provenance, audit findings, gate stations and refusals.
- Mutated process: the 76-test selection above passed; the restored historical test passed without the mutation and failed with it.

The temporary reproduction runner is `/tmp/labkit-review-mutation.py`; it restores the historical method with Python's AST and installs the mutation in the test process only. No package or test file was changed.
