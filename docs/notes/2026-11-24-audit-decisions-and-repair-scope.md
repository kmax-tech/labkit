# Audit decisions and bounded repair review — proposal

Status: proposal for the author, 2026-11-24; no implementation, contract change, audit decision, model call, or release. This develops the approved but unimplemented [release-policy direction](2026-11-16-audit-record-lifecycle.md#decisions-by-the-author--2026-11-16-not-implemented). It is not a way to release the current ArgMining experiments under today's rules.

The recommendation is to keep evidence and reproducibility checks strict, make each finding separately decidable, and give scientific disagreements an explicit human decision path. Start by replaying three recorded cases with fixed stand-in audit answers. Implement a contract change only after the author approves that replay and the decisions below.

## 1. Current contract and observed friction

The current [agent guide](../../labkit/docs/agent-guide.md#4-finalize-audit-and-decide) already distinguishes `implementation`, `statement`, and `undetermined`. An implementation finding alleges a departure of code, data handling, or execution from the registration. A statement finding concerns the description or claim. An undetermined finding needs a concrete diagnostic. These are an auditor's classifications, not mechanically established facts.

A `fixed` decision requires a follow-up judgement; a false-positive BLOCKER requires a second review. A changed decision or reviewed state cannot inherit unrelated approval. These safeguards remain useful. The failure mode is treating every disputed scientific reading as a confirmed implementation breach, then asking further reviewers until one agrees. A disagreement about what a sentence means need not have a diagnostic that settles it uniquely.

The examples are development observations, not an evaluation of labkit's error rate. Some loops came from genuine agent errors: wrong denominators, premature repair decisions, and stale descriptions. Some came from software limits, including whole-file checks and a repeated-history prompt exceeding its budget. The proposal must not treat all of them as unnecessary checks.

## 2. Three cases to replay before building

| Case and evidence                                                                                                                                                                                                                               | What must be separated                                                                                                                                                                           | Intended path under the proposal                                                                                                                                                                                                                                |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ArgMining experiment 15: per-draw tables and answer counts included pairs that a revised classification excluded, although the main difference happened to remain unchanged.                                                                    | An actual counting error, versus an unchanged headline value.                                                                                                                                    | A hand-computed regression must fail on the faulty evaluator; repair and re-evaluate the same answers in a new recorded run; follow up on that repair. A human exception cannot make wrong counts correct.                                                      |
| Experiment 15: a scenario describes rare encephalitis with hospitalizations; the added context says increased emergency visits did not culminate in increased hospital admissions.                                                              | An individual event, an aggregate increase, and a causal reading of the context. The tested model's rejection is evidence of its behaviour, not proof that its scenario is logically impossible. | Retain both readings. The author may keep a disputed reading with an explicit limitation or change it to unclear in a declared post-hoc step; preserve the original analysis and show sensitivity. Do not label a confirmed contradiction a harmless ambiguity. |
| Experiment 12: one finding combined a supposedly missing served-instance record with unknown effective sampling. A contemporaneous commit reported the scenario-stage fingerprint before and after; effective server defaults remained unknown. | The existence and limits of a manual instance record, versus the separate sampling gap.                                                                                                          | Separate the claims in subsequent findings, retain the original finding, and evaluate each evidence gap against the result's claim. Finding one claim mistaken does not dismiss the other. A manual note is not upgraded to an automatic run record.            |

The source corpus is the retained ArgMining repository: experiment 15's audit records of 2026-11-24 19:33 and 23:04, original rating run `2026-11-24T19-21-21_4023`, revised classifications and regression tests; experiment 12's 11:28 audit and commit `a882dee`. Some audit records were uncommitted during this episode. Before executable replays, materialize the required excerpts as fixtures with source digests and clear synthetic/redacted boundaries; do not assume a live working-tree file is immutable evidence.

## 3. Decision procedure

**First, one claim per finding.** A finding states the alleged deviation, the registration or claim it affects, the supporting evidence, and what would settle or bound it. Independent faults receive separate findings. Splitting a later explanation must preserve links to the original finding; it must not edit the original auditor's text or silently drop a true component. Whether prose contains multiple scientific claims is semantic review, not a guaranteed parser check.

**Second, choose the action from the change.** Do not add another subject enum for every kind of uncertainty.

| What is established or still disputed              | Required work                                                                                                                              | What remains held                                                                                                                                         |
|----------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| Demonstrated code/data breach                      | Repair, a discriminating test, a recorded run and targeted follow-up. Reuse answers only when the supported unchanged-answer path applies. | Claims depending on the faulty computation.                                                                                                               |
| Description is wrong but execution unchanged       | Correct the named field and obtain the existing follow-up.                                                                                 | Claims misstated by that field; no new model answers merely for a prose correction.                                                                       |
| Evidence is insufficient and a check can settle it | Use the existing `undetermined` diagnostic, recording its result and scope.                                                                | Claims needing that evidence. A diagnostic result does not automatically choose a scientific interpretation.                                              |
| Multiple readings remain defensible                | State the readings, their effect on inclusion and claims, the author's choice, and sensitivity where possible.                             | Clean approval remains unavailable while the audit objection stands; use only the proposed author-selected release policy below or the existing handover. |

Revising a classification after ratings were seen remains post-hoc even when the result does not change. It requires its own recorded step and input version; the earlier result is never relabelled as pre-specified. A disputed interpretation is not automatically a false positive.

## 4. Human decision with an explicitly retained objection

The default remains strict release. The already approved alternative direction is release **with a documented audit objection**, not a clean audit. The author or laboratory selects the policy; the executing agent may not relax it. If it is selected after results were seen, that timing must be explicit. The choice does not retroactively validate the original registration or remove an auditor's rejection.

The proposed alternative requires a persistent decision tied to the protocol, result run, affected finding states, final claim, and author authorization. It records the reason, unresolved readings, changed or withheld claims, and any sensitivity analysis. Adoption and the final report must show the objection and policy prominently. A changed decision or conclusion requires its coverage to be checked again.

Mechanical duties still hold: readable and retained records, available measurements, input/output integrity, declared changes, and a reproducible computation. A demonstrated calculation error is repaired, not waived. Missing evidence is not manufactured by an author signature. Claims that the available provenance cannot support must be reduced or withheld. The author cannot obtain a clean approval merely by selecting the alternative policy.

This is a proposed release contract, not an existing flag. Storage, command spelling, and report fields require the author's decision; introduce no guessed CLI in the meantime. The alternative should check that the decision and limitation are complete and bound to the right state. It must not require another model to agree with the disputed scientific reading, since that would recreate the same loop.

## 5. Bound follow-up to the repaired state

For each repair, present the original objection, current decision, changed evidence or code, regression result, and the exact affected claim. The reviewer checks this delta and the still-applicable obligations. A newly discovered fault must name new evidence or an independently checkable defect; repeating the previous disagreement does not become a new defect just because another model phrases it differently. Do not hide new faults or invalidate related obligations to meet a call budget.

One follow-up per coherent repair is the planning default, not a hard rule that suppresses discoveries. An unchanged rejected decision is not resubmitted for a more favourable draw. A continuing scientific disagreement goes to the author's documented decision path or handover. A further call needs a stated reason and user authorization, not an automatic retry-until-upheld loop.

Bind coverage to the evidence and claims actually checked. Do not restart a full analysis audit solely because an unrelated working report changed. Conversely, a change to answer reading, pair selection, or the result claim is relevant and must not inherit stale coverage. Use the existing [unchanged-answer correction workflow](../workflow.md#correcting-the-evaluation-of-unchanged-answers); do not build a second correction mechanism here.

## 6. Save work independently of result release

The [registered progress account](../workflow.md#3-measure) already permits some pre-adoption commits; improve its use before adding another checkpoint format. The remaining proposal is to allow an explicitly unreviewed work snapshot while continuing to refuse its use as an adopted result. The snapshot must display open findings and its unreviewed status; it does not satisfy audit, adoption, or report-release duties.

First reproduce an actual blocked evidence-saving case. If the current progress-account route already saves it, change guidance rather than the format. If it cannot, specify which draft/code/evidence paths the snapshot may contain, how reports identify the state, and how the gate distinguishes preservation from a released scientific claim. Never teach agents to omit findings or remove evidence to get a commit through.

History remains complete. Showing identical protocol field versions once with explicit references is a separate prompt-packaging task already in TODO. Tests can establish complete evidence and valid references; they cannot guarantee identical stochastic auditor judgements.

## 7. Bounded implementation sequence and acceptance

1. **Replay and proposed contract only:** prepare the three fixtures, map today's decisions and the intended paths, and enumerate the exact refusal or repeated work. No paid audit and no change to a live experiment.
2. **Smallest intervention first:** atomic-finding guidance and bounded follow-up evidence; use existing progress accounts and correction routes. Run fixtures with fixed reviewer answers that include disagreement and newly discovered real faults.
3. **Separate author-approved contract step:** implement the release policy and work-snapshot change only if the replay shows they are still needed. Default strict, preserve existing review bindings, and announce any format/API change with the last compatible version. No rollout into laboratories as a side effect.

Acceptance cases:

- Wrong counts block release, even under the alternative policy; a corrected evaluator and preserved original answers produce a new result with repair coverage.
- A mixed finding cannot be dismissed wholesale by evidence addressing only one component.
- A scientific disagreement retains the original objection, both readings, the author's decision, and post-hoc sensitivity; strict release stays held, while the alternative reports its open objection instead of a clean pass.
- Changed decisions or conclusions do not reuse stale confirmations. A genuinely new fault in follow-up still blocks the affected claim.
- A pending work snapshot is preservable but cannot be rendered as adopted evidence. An existing supported progress-account path is tested before any new format is added.
- Prompt deduplication preserves every required evidence version and its references without claiming unchanged model verdicts.

## 8. Author decisions still needed

1. Approve the three-case replay as the next bounded design task; it authorizes no release-policy implementation yet.
2. Confirm the alternative policy's eligibility and who may select it, including explicit disclosure of selection after results. Technical prerequisites remain mandatory.
3. Decide whether existing progress accounts suffice for evidence preservation; specify a new snapshot contract only after a failing case is demonstrated.

The proposal changes no existing audit, classification, or result. It supplies a reviewable work order; existing TODO priority and the author's subsequent decisions determine implementation.

## Sources and relation to existing work

Current behaviour was checked in labkit checkout `8a00de6f`; the ArgMining laboratory used pinned 0.115.0 during the episode. Current checkout features must not be described as available under that pin.

- [Agent guide: finalize, audit and decide](../../labkit/docs/agent-guide.md#4-finalize-audit-and-decide): subjects, decisions, follow-up and decision-review obligations.
- [Workflow: repair and recovery](../workflow.md#repair-and-recovery): correction routes and stage-specific checks.
- [Audit record lifecycle](2026-11-16-audit-record-lifecycle.md): retained evidence and the approved, unimplemented release-policy direction.
- [Analysis correction on unchanged answers](2026-11-24-analysis-correction-on-unchanged-answers.md): existing correction work, not re-opened here.
- [Keeping a decision taken back](2026-11-25-keep-decisions-taken-back.md): the parallel proposal for preserving superseded decisions; this note neither chooses its format nor changes its review digest.

No synthetic replay, runtime test, external audit, or improvement in research validity is claimed by this document.
