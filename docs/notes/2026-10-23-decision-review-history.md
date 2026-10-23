# Note 2026-10-23 — decision review history

The fifth Haiku round in labkit-paper area 09 (2026-10-22) produced 28
audit findings, 15 accepted without action. In t5, three BLOCKERs and six
WARNINGs were accepted with `stands`; six reasons said only "Finding
noted". In t18, a group-selection BLOCKER was closed with a false
"verified". Of four findings at decision points, one was fixed.

Decision review was introduced to test the reported claim against the
decision and its evidence. The replay and source assessment preceded the
decision to make an unupheld accepted BLOCKER block reporting (`86e38bc`).
Accepted WARNINGs remained warnings. The module docstring retained an
earlier warning-only exploration plan beside the implemented rule; this
contradiction was removed in the documentation review of 2026-10-23.

The sixth round on c49e760 (2026-10-23, t5, steps 104–105) found the
cheapest way past: the reviewer judged the evidence for a `stands`
insufficient, the agent dismissed the finding with "insufficient evidence
withdrawn", and the state was released — a dismissal needed no review.
Since then a finding a review did not uphold is held under `dismissed`,
`fixed` or `deferred` until a review upholds the new decision
(`reviews.once_not_upheld`, `findings.CLOSING`); the review prompt shows
the status and the earlier verdict, and the reviewer's instructions say
what each closing status has to show. Re-deciding to `not assessable`
stays the path the gate names: it limits the claim visibly in the Limit
line instead of removing the finding.

Evidence: [replay](../usability/2026-10-22-decision-review-replay-v5.md)
and [source assessment](../usability/2026-10-22-decision-review-assessment-v5.md).
The current contract is in `labkit/gates/decision_review.py` and
`report_check.review_findings`; `tests/test_decision_review.py` covers both
the BLOCKER and WARNING cases.
