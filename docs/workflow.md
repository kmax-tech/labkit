# The workflow: from a registered question to a kept number

Use `labkit-next <AREA>` for the current next action. This page explains
when each step applies, what may change, what the command writes, and what
allows progress. It describes current behaviour; proposed simplifications
are in the [plan](notes/2026-11-02-workflow-simplification.md).

Commands run from the repository root with its venv active, or through
`.venv/bin/<command>`. `AREA` means an experiment directory; `PROTOCOL`
means its protocol file. A **measurement** is a full run, not a probe or
preparation. A check being clean establishes only the conditions it checks.
Exact conditions, static hints and semantic audits have different limits;
see [the evidence tiers](../README.md#what-the-checks-establish).

The [executable count walkthrough](examples/count-walkthrough.sh) takes a
small task through these steps. Its audit record is explicitly a stand-in,
so the example needs no model call. `tests/test_workflow_example.py` checks
the real commands and the resulting artifacts.

## The steps at a glance

| Step | Purpose | Main command |
|---|---|---|
| 0. Area | Create the question's workspace and skeleton. | `labkit-init exp` |
| 1. Code | Implement and test the measurement. | `code-check AREA` |
| 2. Registration | Record and commit the scientific choices. | `protocol-fill`, `protocol-check` |
| 3. Run | Measure with recorded inputs and code. | The area's measurement script |
| 4. Finalize | Check the completed run. | `finalize AREA` |
| 5. Analysis audit | Review the evidence and decide findings. | `labkit-audit AREA --mode analysis` |
| 6. Decision review | Check decisions that require another reviewer. | `labkit-audit AREA --review` |
| 7. Adoption | Select and generate the reported result. | `labkit-adopt AREA` |
| 8. Report | Complete the text and its required review. | `protocol-fill --into`, `labkit-audit --report-review` |
| 9. Stop and commit | Check the delivered state. | Hooks; `report-check` |

Code and registration may be developed together before measurement.
Later changes use the [repair path](#repair-and-recovery); they do not
rewrite the evidence of earlier work. The steps below describe repeat cost
`low`, with additional `high` requirements where relevant.

## 0. The area

**When:** a new question needs its own experiment area.

**Allowed changes:** choose `compute`, `fit` or `apply` by what the number
asserts. Choose the repeat cost and register a report path when the task
requires one. The [field contract](../README.md#run-an-experiment) determines
the skeleton and obligations.

**Command and output:** `labkit-init lab <dir>` creates the lab once;
`labkit-init exp <name> --repeat-cost low --kind compute` creates the area,
protocol, scripts and test. Add `--report-file REPORT.md` for a required
report. Use the actual kind and any model options the task needs.

**Done / way out:** the numbered area exists. `protocol-check PROTOCOL
--contract` explains its requirements. If numbering conflicts, run
`labkit-init numbers` and resolve the named areas.

## 1. The measurement code

**When:** the area exists and its instrument is not yet implemented.

**Allowed changes:** fill the scripts and area tests. Test the functions
that produce numbers with independently checked examples. A local `apply`
uses an unchanged predictor; declare its loaded artifacts as run inputs.

**Command and output:** edit the code, run the area tests, then
`code-check AREA`. That command reads the code and promises and writes
nothing unless a bundle is requested.

**Done / way out:** correct tests pass and required structural references
are present. Fix missing keys, prompt declarations or parser fixtures as
named. Structural checks do not establish scientific meaning. At `high`,
complete the instrument probe where the skeleton provides one before
freezing. Details: [checks and their limits](architecture.md#the-chain).

## 2. The registration

**When:** before the first measurement; scientific choices remain open.

**Allowed changes:** fill the fields required for this kind. Use
`protocol-check PROTOCOL --contract` for the applicable list and
`protocol-fill PROTOCOL --list` for missing values. Choose the kind correctly
before measuring; `labkit-init exp NAME --kind KIND --change-kind` restamps
an eligible unmeasured area.

**Command and output:** `protocol-fill PROTOCOL "Question / hypothesis=…"`
fills the named field; `protocol-check PROTOCOL` validates registration.
Commit the protocol and relevant implementation, naming only your paths
in `git add` and `git commit -- <paths>` so other staged work stays out.

**Done / way out:** at `low`, the required registration stands in the commit
of the first measurement. A required report can be added to an existing
unmeasured protocol with `protocol-fill PROTOCOL report=REPORT.md`; a
pre-measurement replacement needs `--force`. The registered path must be
committed before the first measurement. A valid report draft can be
committed with the registration before any measurement; it owes no result
block yet. After measurement, save its progress account. Removing or moving that bound path
later holds release: restore it, or explicitly hand over and register anew.
`--force` does not bypass the binding. At both `low` and `high`, the first
measurement's commit fixes the report path, including the absence of one:
a report cannot be registered later in the same protocol. The setter and
gates use the same comparison; `--force` can restore the original path but
cannot redirect it. At `high`, additionally pass preflight, decide its
audit, set the matching freeze evidence and freeze the protocol. Freeze
is not a substitute for report-path commitment.

See [the promise format](promise-block.md#the-block) for technical fields
and [the chain](architecture.md#the-chain) for registration binding. A missed
registered criterion is a valid result; it does not justify changing the bar.

## 3. The run

**When:** the registration and the lane's start requirements hold.

**Allowed changes:** run the instrument; let runlog write its records.
Do not edit a completed run's metrics or outputs to repair the experiment.

**Command and output:** run `.venv/bin/python AREA/scripts/01_measure.py`.
It records the run under `runs/<run_id>/`, its inputs, code and protocol
binding, outputs and completion, and updates the run index. Commit the
relevant source, outputs and records using explicit paths.

**Done / way out:** the measurement completed. With a registered report and
nothing adopted, `labkit-next` names the progress account next, before the
audit and before any gap: `protocol-fill PROTOCOL --discuss RUN_ID --why
"WHAT WAS MEASURED, WHAT IS STILL OPEN" --into REPORT.md`. It saves the state
and releases nothing; the next call names the remaining gap as before. A
start refusal names the missing prerequisite before creating the run. A
failed execution uses the repair path. For long commands use [detached execution and waiting](architecture.md#long-running-commands).
Run-record details: [protocol/run binding](protocol-run-binding.md).

## 4. finalize

**When:** a completed run answers the protocol.

**Allowed changes:** none through this command; it only reads evidence.

**Command and output:** `finalize AREA` checks the selected answering run,
registration, code, provenance, outputs, promises, area tests and audit
evidence. It prints findings and writes no result declaration.

**Done / way out:** no blocker remains. This permits the next checks; it
does not release a result. A real implementation repair needs a new run
and affected follow-up checks. Restore source only for accidental changes.
The [answering-run rules](protocol-run-binding.md#the-answering-run) select
the run; [the chain](architecture.md#the-chain) lists the exact checks.

## 5. The analysis audit and the decisions

**When:** a completed run needs analysis review, or a decided correction
needs follow-up. Both repeat costs require analysis review before release.
A hold awaiting that follow-up is resolved through this step.

**Allowed changes:** record decisions on findings through the decision tool.
Keep the original findings. A corrected setup description needs the exact
field named in the finding, a `fixed` decision and the follow-up audit's
`resolved` for this state. A fresh audit alone does not release it. A run
measured again under the corrected field, after a code repair, is released
only by a follow-up on that run whose `resolved` judges the correction
again; the verdict on the earlier run does not carry over. Follow the
repair path for changed code or scientific choices.

**Command and output:** `labkit-audit AREA --mode analysis` calls the auditor
and writes its bound record under `audits/`. Use `labkit-audit AREA --findings`
to inspect it without a model call, then `labkit-audit AREA --decide N STATUS
--why "REASON" --record FILE` for each decision.

**Done / way out:** required decisions and follow-up evidence cover the
current state. `fixed` records a repair decision, not proof that the old
run is corrected. Earlier undecided BLOCKERs must be decided before the
next analysis audit. A limitation must state what claims remain supported
or which promises cannot be assessed. See [audit and follow-up contracts](architecture.md#the-chain)
and [decision guidance](../labkit/docs/agent-guide.md#4-finalize-audit-and-decide).

## 6. The decision review — when a BLOCKER was decided `limitation` with `stands`

**When:** an accepted BLOCKER says its verdicts stand within a limitation,
or another decision falls under the existing review rules. These include
closing a previously unconfirmed decision and dismissing a carried finding.

**Allowed changes:** correct the Conclusion, decision or supporting evidence
as required. Changing the reviewed claim or decision makes its review stale.

**Command and output:** write the Conclusion through `protocol-fill`, then
run `labkit-audit AREA --review [--record FILE]`. It writes the second
reviewer's verdicts under `audits/`.

**Done / way out:** required decisions are upheld. On `rejected`, change the
claim, decision or faulty work; on `insufficient`, supply the missing evidence.
Repeated draws do not erase a rejection. Details and exceptional cases:
[decision review in the chain](architecture.md#the-chain). An accepted WARNING
with `stands` does not carry the general BLOCKER review duty.

## 7. The adoption

**When:** the run and decisions meet the release requirements.

**Allowed changes:** write the author's Conclusion; generate the numerical
result and limitations from their sources through the tools.

**Command and output:** `labkit-adopt AREA [RUN_ID]` adopts the result, writes
the registered report block — where the run's progress account stood, which
it replaces — and checks the chain. For the protocol alone,
`protocol-fill PROTOCOL --from-run RUN_ID` writes `[result]`, Recorded
results, limitations and the Runs entry; a failed adoption check restores
that protocol edit.

**Done / way out:** the result is adopted and generated blocks agree with
its sources. A registered report still needs its final text and review
(step 8). If a later stage of `labkit-adopt` fails, read which earlier
writes remain and resume after fixing the named issue. To repair an adopted
result, withdraw first. See [the declared run](protocol-run-binding.md#the-declared-run).

## 8. The report block — the number outside the protocol

**When:** the result has been adopted, or the report discusses a run without
adopting it.

**Allowed changes:** edit the report's prose. Use tools for generated blocks
and values. Store measured quantities in the run rather than retyping them.

**Command and output:** `protocol-fill PROTOCOL --into REPORT.md` writes or
updates that protocol's result block: the registered question (`Question:`),
the Conclusion (`Answer:`), the Recorded results line and the Limitation
lines, each as the protocol renders them; it refuses while the question or
the Conclusion is not written. For a run only discussed, use
`protocol-fill PROTOCOL --discuss RUN_ID --why "REASON" --into REPORT.md`.
Then `labkit-audit AREA --report-review REPORT.md` writes the required
semantic review for the final state.

**Done / way out:** generated blocks match their sources and any required
review names no unsupported claim. A registered report takes its final
form with a result or handover block and still owes review of its final text. Before
the adoption, a discussion of the run the gates hold the protocol to is its
progress account: the commit takes it without a review; it releases no
result. Any other discussion, and a discussion in a report the head does not
register, owes review under the applicable report rules. Correct the text or
evidence and review the changed state. Do not redraw an unchanged claimed
state until it passes. A missing registered report after measurement holds
the stop.

The block guarantees exact rendering of bound values, not the meaning of
prose beside it. Numbers outside blocks are static hints. Exact report,
review, citation and file rules are in [the chain](architecture.md#the-chain).

## 9. The gate — at the stop and the commit

**When:** the agent ends its turn or commits changed work.

**Allowed changes:** none by the checks themselves. Fix the named issue
through the appropriate command or repair path.

**Command and output:** hooks check automatically; `report-check AREA` runs
the result gate explicitly. `report-check --if-reported [--staged] PATH...`
checks affected delivered work. The stop reads the working tree; the commit
reads staged evidence. These checks print findings and do not write approval.

**Done / way out:** the applicable checks have no blocker. A registered
report carrying only the progress account passes the commit; the stop holds
it once, naming the audit and the adoption or the handover — the commit rule
for this intermediate state is deliberately looser, the release requirements
are not. A clean commit check alone does not mean every scientific claim was
assessed. If work must end without a result, record a handover through the commands below.
Selection and enforcement: [run and hook enforcement](architecture.md#run-and-hook-enforcement).

## Repair and recovery

1. Inspect `labkit-next AREA` and `labkit-audit AREA --findings`. Their
   messages name the held evidence, allowed action and next command.
2. If repairing an adopted result, use `protocol-fill PROTOCOL --withdraw
   --why "REASON" --into REPORT.md` for the affected report. This withdraws
   the result and generated blocks; it does not restore source or delete
   the old run and audits.
3. Choose the repair that matches the change:
   - **Implementation:** repair code and tests, record the decision, repeat
     the affected measurement, then finalize and obtain the required
     follow-up audit and reviews. Adopt the new result.
   - **Setup description of the same run:** correct the named field and
     decide its finding `fixed`. Obtain an explicit `resolved` on that
     finding in a follow-up audit of the current state; no new measurement
     is needed for this correction. A fresh audit without that verdict
     does not suffice, even for a WARNING. Whether it describes the same
     experiment is the auditor's judgement; see the [correction contract](notes/2026-11-02-registered-field-repair.md).
   - **Conclusion alone:** update the claim; this alone needs no new
     measurement or analysis audit. Required decision and report reviews
     still apply. A BLOCKER on the Conclusion decided `fixed` is released
     by the decision review of the claim as it stands (`labkit-audit AREA
     --review --record FILE`), not by a follow-up audit, which is not
     shown a rewritten claim.
4. A changed registered scientific choice needs an explicit new registration
   with the departure and earlier results retained. An accidental edit needs
   restoration from the named source, not a changed scientific explanation.
   Do not clear holds by deleting evidence or resetting the repository.

To end without a result, use `protocol-fill PROTOCOL --handover --why
"REASON" --tried "WHAT WAS TRIED" --into REPORT.md`. It records the remaining
state and writes its handover block. Stage the related protocol, report and
evidence together. A handover does not approve a result or let new audits
ignore lost evidence. Other citations may still need correction.

For failed audit calls and missing evidence, follow the specific recovery
commands from `--findings`; an execution failure is not an audit verdict.
The [handover recovery contract](notes/2026-10-27-handover-recovery.md)
explains retained losses, open findings and when an acknowledgement expires.
Detailed command options are in the [command reference](../README.md#command-reference)
and [agent guide](../labkit/docs/agent-guide.md#when-you-are-stuck--both-repeat-costs).

## The questions a reader should be able to answer

- **Which run supplies this number?** The protocol's declared result must
  be its [answering run](protocol-run-binding.md#the-answering-run).
- **Which decision still needs review?** Follow the finding's printed
  command; the [chain](architecture.md#the-chain) states the review rules.
- **What does `--from-run` change?** The protocol only. `labkit-adopt`
  additionally writes the registered report block and checks the chain.
- **What remains scientific judgement?** Whether the method and claim are
  justified. Matching records and generated values establish narrower facts.
