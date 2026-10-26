# Instruction reading probe: recovery after a gate refusal (2026-10-26)

The entry instructions leave concrete recovery decisions unclear. At source
commit `202f7be`, their low lane still prescribes the obsolete prose marker
for a discussed run. They also place the Conclusion after adoption, whereas
the workflow places it before. Independent readers followed these different
orders. A proposed clarification made two new readers, including
`gpt-6-luna`, choose the structured discussion command and the complete
measurement recovery sequence.

This is an instruction comprehension probe, not evidence that an agent
completed a ScienceAgentBench task or that the clarifications improve task
success. No Haiku run was available through the delegation tool.

## Setup and preserved evidence

Work was isolated in the detached worktree
`/tmp/labkit-instructions-probe-20261026` at `202f7be`. Concurrent edits in
the author's main worktree were neither read as task evidence nor modified.
Source documents were copied before readers started. The cases and
assessment criteria were written before their answers.

- [Cases](2026-10-26-instruction-reading-probe/cases.txt): six independent hypothetical situations
  at low repeat cost, kind fit. Readers supply next actions, documented
  commands, current permissible claims, supporting passages and gaps.
- [Assessment criteria](2026-10-26-instruction-reading-probe/assessment-contract.txt).
- [Original entry instructions](2026-10-26-instruction-reading-probe/entry-instructions.md) and
  [workflow](2026-10-26-instruction-reading-probe/workflow-instructions.md).
- [Revised entry instructions](2026-10-26-instruction-reading-probe/revised-entry-instructions.md):
  the exact candidate given to the two additional readers.

Each reader received a fresh context without the parent conversation. They
were explicitly restricted to the assigned instruction files and cases,
and told not to run experiments, inspect source, read other answers or
invent commands. Each wrote one answer before receiving any feedback. The
assignments were:

| Reader | Model selection | Instruction access | Answer |
|---|---|---|---|
| entry | inherited parent model | original entry only | [answer](2026-10-26-instruction-reading-probe/answer-entry.md) |
| workflow | inherited parent model | original entry and workflow | [answer](2026-10-26-instruction-reading-probe/answer-workflow.md) |
| luna | `gpt-6-luna`, medium reasoning | original entry only | [answer](2026-10-26-instruction-reading-probe/answer-luna.md) |
| entry-revised | inherited parent model | revised entry only | [answer](2026-10-26-instruction-reading-probe/answer-entry-revised.md) |
| luna-revised | `gpt-6-luna`, medium reasoning | revised entry only | [answer](2026-10-26-instruction-reading-probe/answer-luna-revised.md) |

The inherited model was not overridden or independently identified. The
weaker-model selection follows the user's explicit request. This is one
response per assignment; it does not separate model, sampling and document
effects sufficiently for a model comparison.

## Observed decisions

| Case | Original entry reader | Original luna reader | Entry plus workflow reader |
|---|---|---|---|
| 1. Clean audit, empty Conclusion, final report requested | Adopt first, then write Conclusion; explicitly notices possible refusal | Writes Conclusion first despite citing the passage that puts it after adoption | Writes Conclusion first and identifies the conflicting instructions |
| 2. Two leakage features named, only one removed, no rerun | Requires complete correction, diagnosis, new run and audit; distinguishes inference from explicit instructions | Requires full correction and diagnosis, but leaves the need for a new measurement explicitly undecided | Requires new run and covering audit; notes that first-time `fixed` has no general independent proof requirement |
| 3. Accepted BLOCKER with `stands`, or rejected decision review | Conclusion then review; no unchanged redraw | Same core sequence; no unchanged redraw | Same, and explicitly carries rejected findings through subsequent closing decisions |
| 4. Failed audit, adoption refused, deadline near | Uses the obsolete prose marker because low lane explicitly prescribes it | Mixes `--discuss` from high with the old low-lane prose marker, while saying high does not apply | Uses `--discuss` and flags the conflict with entry low |
| 5. Conclusion strengthened after an upholding review | Requires a fresh review, but calls later edits an inference from the first-writing example | Requires fresh review and no measurement; part of its answer switches to Dutch | Requires fresh review; cites the explicit change-invalidates-review rule |
| 6. Predictions absent from the externally required root path | Task incomplete; identifies missing gate coverage | Task incomplete; identifies missing gate coverage | Task incomplete; distinguishes provenance checks from external acceptance |

These are content observations, not a numerical pass rate. In particular,
case 4 is a failure of the prescribed low-lane text, even where a reader
followed it faithfully. Case 6 was understood by every initial reader and
is not evidence that those readers would ignore an external path.

## Concrete instruction changes

The proposed diff is limited to `labkit/templates/AGENTS.md.template` in
this worktree. It changes no gate behavior and introduces no new command.

1. Replace the obsolete low-lane prose marker with the existing
   `protocol-fill ... --discuss ... --why ... --into REPORT.md` command.
2. Put the author's Conclusion before adoption for the ordinary path as
   well as the decision-review path. Remove the later instruction that
   presents it as work remaining after adoption.
3. State the return path after a measurement-code correction: code-check,
   commit corrected code, new measurement, finalize and analysis audit of
   that code and run. An edited script does not repair an old run.
4. Define the intended meaning of `fixed`: complete correction plus any
   requested diagnostic, actually run and assessed. State that the status
   records the decision rather than proving the correction. This does not
   add an automatic verification of every first-time `fixed` decision.
5. Say explicitly that a changed Conclusion or decision invalidates the
   corresponding review; a Conclusion-only edit does not itself require a
   new measurement. Include the already implemented review duty for a
   finding closed after a non-upholding review.
6. Keep earlier audit records, including failures, and explain that a
   failed audit supplies no analysis coverage. This describes the required
   handling without claiming that the snapshot already has an attempt
   journal or mandatory report-review record.
7. Remind readers to verify external deliverable paths, formats and
   contents. This was understood in the initial answers and is a reminder,
   not a demonstrated remedy for their behavior.

## Reading the proposed clarification

Both new readers explicitly choose Conclusion before adoption in case 1,
require the new measurement and analysis audit after correction in case 2,
use `--discuss` without prescribing the old prose marker in case 4, and
require a new decision review without a new measurement in case 5. Neither
claims that `finalize` checks the external root path in case 6. The
entry-revised reader reports no direct contradiction in the relevant low
lane, while still identifying missing task-specific diagnostic commands.

One residual misconception remained in the weaker reader's case 5: it
suggests regenerating the result block so that the changed Conclusion is
in the artifact. The result block contains Recorded results and Limit
lines; it does not copy the Conclusion. The stronger revised reader gets
that distinction right. The final proposed diff explicitly names those two
parts as the block's content and asks the author to write the report's
explanation consistently with the Conclusion. That final addition was not
part of the candidate these readers saw.

The final proposed diff also narrows the sentence about re-reviewing
changed decisions: the current decision must require a review.
`not assessable` limits the claim and does not by itself require a decision
review. This qualification was added after the comprehension responses and
does not have a new cold-reader measurement.

## Verification against the implementation

The parent inspected the relevant implementation after the original
assignments were fixed. This information was not supplied to readers.

- Existing tests for the old prose marker and the valid discussion block
  pass: **2 passed, 37 deselected**.
- A synthetic repository built from the existing test fixture was put
  through the real `report_check.if_reported` path. The old marker gives
  exit **1**, and the generated discussion block gives exit **0**. Its
  output is preserved in [gate-replay.txt](2026-10-26-instruction-reading-probe/gate-replay.txt),
  with the [old report](2026-10-26-instruction-reading-probe/report-old-marker.md) and
  [new report](2026-10-26-instruction-reading-probe/report-discussion-block.md). The fixture was synthetic, not a copied round-8 result;
  its output and report texts are archived here, while the disposable
  fixture repository remains in the isolated worktree. It contains no contradictory success claim and cannot
  establish that t3's actual report would pass semantic review.
- The snapshot still prints the report-review command as a nonblocking
  hint. The proposed instructions do not claim that the pending mandatory
  report-review change is already implemented.
- Focused verification with the parent's existing development environment
  and `PYTHONPATH` pinned to this worktree:
  `python -m pytest -q tests/test_scaffold.py tests/test_report_blocks.py tests/test_workflow_example.py`:
  **77 passed, 5 subtests passed**. The walkthrough exercises the real
  count path; its audit fixture does not measure a live model's judgment.
- `git diff --check` passes. No Python implementation or test was changed.
- An additional independent agent reviewed the final proposal against
  the snapshot's implementation and documentation, including the two
  post-probe wording changes: [proposal review](2026-10-26-instruction-reading-probe/proposal-review.md),
  **0 findings**. This factual and clarity review is separate from the
  cold-reader comprehension responses.

## Limits and next use

The six situations are selected, hypothetical decision points; the
questions themselves draw attention to faults an uninterrupted solver
might miss. Readers answered instructions rather than executing the
scientific task under time pressure. No report-review model, training
pipeline, predictions or Haiku solver was run. There is no measured
reduction in bypasses, cost, duration or scientific errors.

The supported recommendation is to reconcile contradictory entry text and
spell out the recovery branches before adding a new coordinating command.
After merging the concurrent gate changes, verify that the final template
matches their actual interface and measure it in an execution probe with
Haiku. Preserve the generated instructions that probe actually used.

The reading probe and proposal were prepared in isolation without changing
the active worktree. During integration onto `86e026b`, the mandatory
report-review instructions were moved to a shared delivery section that
both lanes reach; the low lane now explicitly directs readers there after
creating a discussion block. That integration follows the newly implemented
review requirement and was not part of the five comprehension responses.
The archived instruction files preserve exactly what those readers saw.
