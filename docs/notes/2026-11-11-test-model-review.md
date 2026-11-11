# Independent review of the rule tests (2026-11-11)

> Review of `00aaeaad`, against the baseline `524b93ce` and the [test-model plan](2026-11-10-test-model.md). The reviewer did not author the migration. Verdict: the review is complete, but target 4 remains open because one removed assertion has no adequate replacement. This review approves neither the open rule assignments nor the undecided second-review policy.
>
> Since `29290169` the assertion is restored ([Correction](#correction-2026-11-11)); the related second call got its test in `cd615bb5`, and a measurement over the callers of every pure check found and closed one more unheld caller ([below](#the-callers-of-every-pure-check-2026-11-11)).

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

## Correction (2026-11-11)

A second session repeated the mutation on the whole suite at `00aaeaad`, not only on the 76 selected tests: with `registration_hold.moved_fields` answering the empty set, 3 333 tests passed and none failed (exit 0). No test held the comparison.

`29290169` adds the required test, `tests/test_rules_registration_hold.py::TheReleaseReadsWhichFieldTheRunSawOtherwise`. It passes two protocol texts through `released_fields` and stubs only `resolved_corrections`. A field edited after the run stays held although its correction is resolved; the twin with equal texts releases it; an edit of another field releases it too. Under the mutation the first test fails (1 failed, 2 passed); on the unchanged code all three pass.

Closed in `cd615bb5` (`TheFollowUpLeadsOnlyForAFieldTheRunSawAsItStands`), at first without a test: `scope_changes` calls `moved_fields` a second time (`labkit/gates/registration_hold.py:284`) and hands the result to `waiting_refs`, which decides whether a hold leads with the follow-up audit as its way out. The same mutation covers that call, and the suite stayed green. The call decides the way out a hold names first, not whether the field is held. A test of it needs `scope_changes` with a first measurement in a repository.

## The callers of every pure check (2026-11-11)

The finding above raised the question whether other callers are unheld in the same way. A second session answered it by measurement at `cd615bb5`. For 16 of the 17 functions the rule tests call under `pure_call`, and for the comparison `moved_fields`, one run of the suite replaced the function's answer by "nothing found" (an empty list, an empty mapping, nothing released, nothing waiting). A call from a file under `tests/` kept the original, so the rule tests stayed what they are; a call from the package got the replacement. A run stopped at its first failing test.

| Function                                                                                            | Result                                          | First failing test                                              |
|-----------------------------------------------------------------------------------------------------|-------------------------------------------------|-----------------------------------------------------------------|
| `registration_hold.moved_fields` (the comparison of this review)                                    | survived at `00aaeaad`; killed since `29290169` | `TheReleaseReadsWhichFieldTheRunSawOtherwise`                   |
| `registration_hold.waiting_refs`                                                                    | killed, by the test `cd615bb5` added            | `TheFollowUpLeadsOnlyForAFieldTheRunSawAsItStands`              |
| `registration_hold.split_released` (keeps every difference)                                         | killed                                          | `TheReleaseReadsWhichFieldTheRunSawOtherwise`                   |
| `registration_hold.now_hold`                                                                        | killed                                          | `tests/test_unread_registration.py::UnreadFirstMeasurement`     |
| `registration_hold.description_added`                                                               | killed                                          | `TheWayBackNamesWhatEachFieldHas`                               |
| `followup.awaited_corrections`                                                                      | killed, in the slow tier only                   | `tests/test_end_to_end.py::CorrectionThenNewRun`                |
| `followup.released_corrections`                                                                     | killed                                          | `tests/test_unread_registration.py::ReleaseThatCannotBeChecked` |
| `protocol_history.scope_differences`                                                                | killed                                          | `tests/test_replacement.py::Differences`                        |
| `audit_prompt.carried_of`                                                                           | killed                                          | `tests/test_audit.py::Carried`                                  |
| `audit_binding.check_audit_findings_decided`, `check_audit_records_read`, `check_audited_runs_kept` | killed, each                                    | `tests/test_finalize_open_findings.py::OpenFindings`            |
| `run_record_check.criterion_n_input_mismatches`, `criterion_ns`                                     | killed, each                                    | `tests/test_finalize.py::TestOneRunForEveryStation`             |
| `run_record_check.output_record_findings`                                                           | killed                                          | `tests/test_deliverable.py::CountDelivers`                      |
| `run_record_check.source_finding`                                                                   | killed                                          | `tests/test_finalize_provenance.py::Provenance`                 |
| `run_record_check.null_lane_findings` (every null lane moved)                                       | **survived**; killed since the test below       | `tests/test_finalize_steps.py::NullLaneStation`                 |

One more caller was unheld: finalize's null-lane station. With the check answering that every null lane moved, the fast and the slow tier passed. `tests/test_finalize_steps.py::NullLaneStation` now gives the kept rows and calls the station: an unmoved null lane reaches the findings as a static-evidence warning, a moved one leaves none. The run under the mutant fails at that test.

What the measurement does not show:

- It replaces a check's answer, not its inputs. A caller that computes a wrong input for a check stays unseen unless the function that computes the input is replaced, as `moved_fields` was. The three gate tests added today are the only ones written against that kind of fault.
- A run stops at its first failure. For `waiting_refs` and `split_released` the first failing test is one added today; whether an older test fails too was not measured.
- `seen_hold` returns one finding and has no "nothing found" answer; it was not replaced.
- `awaited_corrections` is held only by a scenario test of the slow tier, so a fault there shows at the push, not at the commit.

The runner was a session script and is not kept in the repository: it set the replacement at interpreter start, so the test process, its workers and the commands a test starts all ran with it.
