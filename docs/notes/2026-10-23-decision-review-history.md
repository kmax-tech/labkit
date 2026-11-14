# Note 2026-10-23 — decision review history

## How the check works today — standard 0.29

This check acts after measurement, when an analysis finding is decided and the result is prepared for adoption and reporting. It changes the reportable verdict, never the measured values in the run's `metrics.json`. The workflow stages are [analysis audit, decision review and adoption](../workflow.md#the-steps-at-a-glance).

1. The run records each promise's value. A score of 0.9225 against a target of 0.95 records a missed criterion.
2. The analysis auditor raises a finding. The agent may decide it as a limitation with an effect such as `quality-check-2 not assessable`: the fault prevents judging that promise.
3. Today, `result_render.verdicts` propagates a quality check's non-assessability to every criterion. `result_render.left_unjudged` shows the second auditor all promises affected, beside their recorded verdicts. The second auditor must confirm that the fault prevents judging each one.
4. `report_decisions.check_limits_upheld` holds an unconfirmed decision at the finding's grade: a BLOCKER blocks release, a WARNING warns. Once a review of the current decision does not uphold it, including `insufficient` or conflicting draws, `result_render.limits_of` removes the proposed non-assessability effect. Recorded verdicts reappear and the Limitation line says the limit was proposed but not confirmed. This restores the recorded judgement; it does not establish that the measurement is scientifically valid. An unconfirmed BLOCKER still blocks release.
5. Adoption and report generation use `result_render.rendering`; report-check checks the generated lines against that rendering. Agreement with the rendering is a mechanical check. Whether the fault really prevents judging a promise is the second auditor's semantic judgement.

The second-review duty for non-assessability was added in standard 0.29 (`eb939a4e`, versioned in `0a42e8f7`). The insufficient-review case is covered by `tests/test_decision_review.py`, `test_an_insufficient_review_shows_the_recorded_verdict_and_still_holds` (`0e33157c`). These tests use supplied reviewer answers; they do not establish that reviewer models judge the dependency correctly in real cases.

## Criterion-specific effects — decided 2026-11-14, not implemented

The author decided to replace the blanket propagation for a limitation that leaves a quality check not assessable. The decision must explicitly name the criteria whose assessment the fault prevents and explain the dependency for each. The second auditor must confirm each dependency. Only those criteria lose their verdict; other criteria retain their recorded verdict. An unresolved BLOCKER continues to block release independently of which verdicts remain visible.

For example, uncertainty about a null run does not by itself prevent comparing 0.9225 with the target of 0.95. The result could state that the target was missed while the comparison with chance is not assessable. A fault in the test labels could instead prevent assessment of every criterion relying on those labels. Which dependency holds must be justified from the particular fault; selecting fewer criteria is not sufficient evidence.

This is a future contract change, not current behaviour. Implementation must version the standard, explain migration, and keep the same affected criteria in the decision, reviewer context and result rendering. The decision does not separately settle the automatic effect of a quality check recorded as not met. [TODO](../../TODO.md) holds the implementation status and work order.

## Historical grounds

The fifth Haiku round in labkit-paper area 09 (2026-10-22) produced 28 audit findings, 15 accepted without action. In t5, three BLOCKERs and six WARNINGs were accepted with `stands`; six reasons said only "Finding noted". In t18, a group-selection BLOCKER was closed with a false "verified". Of four findings at decision points, one was fixed.

Decision review was introduced to test the reported claim against the decision and its evidence. The replay and source assessment preceded the decision to make an unupheld accepted BLOCKER block reporting (`86e38bc`). Accepted WARNINGs remained warnings. The module docstring retained an earlier warning-only exploration plan beside the implemented rule; this contradiction was removed in the documentation review of 2026-10-23.

The sixth round on c49e760 (2026-10-23, t5, steps 104–105) found the cheapest way past: the reviewer judged the evidence for a `stands` insufficient, the agent dismissed the finding with "insufficient evidence withdrawn", and the state was released — a dismissal needed no review. The resulting rule held a finding a review did not uphold under `dismissed`, `fixed` or `deferred` until a review upheld the new decision (`reviews.once_not_upheld`, `findings.CLOSING`); the review prompt shows the status and the earlier verdict, and the reviewer's instructions say what each closing status has to show. At that stage, re-deciding to `not assessable` remained a way to limit the claim visibly in the Limit line instead of removing the finding. Standard 0.29 now requires review of that effect as described in the current-behaviour section.

Evidence: [replay](../usability/2026-10-22-decision-review-replay-v5.md) and [source assessment](../usability/2026-10-22-decision-review-assessment-v5.md). The current contract is in `labkit/gates/decision_review.py` and `labkit/gates/report_decisions.py`; `tests/test_decision_review.py` covers both the BLOCKER and WARNING cases.
