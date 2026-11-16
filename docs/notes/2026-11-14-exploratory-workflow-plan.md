# Exploratory workflow: one investigation, each run bound to its own intent

> Workflow direction approved by the author on 2026-11-14; the investigation boundary was agreed on 2026-11-16. This is the contract and implementation plan, not an implemented feature. Current standard 0.31 still applies. [TODO](../../TODO.md) holds the work order. No experiment, release or rollout follows from this plan.

One exploratory protocol may contain several related questions and measurements. The investigation develops as results are seen; each run retains the question, procedure, inputs, settings and assessment that it actually investigated. A new protocol is needed for an independent investigation or a separate confirmation, not for every justified refinement within exploration.

## Current behaviour and why it changes

`type` identifies exploratory or confirmatory claims, but `standard_contract.lane` selects obligations by repeat cost and `registration_fields` selects them by experiment kind and whether a model is named. The guide explicitly retains criteria and audits for exploratory fit and apply experiments (`labkit/docs/agent-guide.md`, “Choose the experiment”). `registration_hold.registration_changes` binds later measurements to the first measurement's promises; `scope_changes` also holds changes to what the number is about. These checks have no exploratory exception.

Today, a changed scientific choice usually requires another protocol. Existing successor checks and predecessor evidence protect against making an earlier miss disappear through a changed question. The exploratory workflow must preserve that evidence while allowing related changes within one protocol. It must also preserve the scientific distinction between exploration and a confirming evaluation whose relevant choices preceded the results.

## Agreed workflow contract

| Concern                | Exploratory workflow to implement                                                                 | Confirmatory workflow                                                    |
|------------------------|---------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Unit of work           | One developing investigation, potentially several related questions and runs                      | A separately registered confirming investigation                         |
| Question and procedure | May change between runs, with the change and reason recorded                                      | Relevant choices fixed before the evaluated results                      |
| Success criteria       | Optional unless the task requires an assessment; additions and changes are explicit               | Registered before the relevant measurement where a criterion is required |
| Run evidence           | Each run retains its own intent, code, inputs, settings and results                               | Same provenance, plus the fixed registration                             |
| Selection              | Seeds, variants and runs may be compared; explain selection and its basis                         | Follow the registered selection and analysis plan                        |
| Audit                  | Judge measurement validity, the question actually investigated and the support for the conclusion | Same duties, plus adherence to registration                              |
| Report                 | Identify source runs, relevant changes and decisions made after observation                       | Report the registered comparison and justified deviations                |

The author confirmed on 2026-11-16 that related questions may remain in the same exploratory protocol. The boundary is scientific continuity: refining a question or investigating an observed failure does not by itself require a new protocol. An unrelated investigation or a move to confirmation does. The audit judges that continuity from the stated reason and evidence; text equality cannot establish it.

### What may change

After inspecting a result, the agent may revise the question, method, seed, data selection, filter, analysis or assessment for a subsequent exploratory run. It records what changed and why, including when the reason came from earlier results. This is permitted exploration, not a false claim that the change preceded observation. Explicit task requirements remain owed: a task's requested comparison or answer cannot be dropped by labelling the work exploratory.

A success criterion is not required solely to make an exploratory fit or apply produce a pass/fail verdict. The measurement must still be sufficiently specified to interpret its outputs, and task-required assessments and relevant measurement-validity checks remain. Experiment kind continues to describe what a number asserts: tuning a predictor cannot silently remain an unchanged-predictor application. How such changes are represented is a design question, not permission to mislabel a run.

### What remains bound

The current protocol may evolve; a completed run's evidence does not evolve with it. Its question, settings, data, measurement code, recorded criteria and results remain reconstructible. A later criterion cannot rewrite an earlier verdict. Reanalysis of retained outputs identifies the source measurement and the new analysis separately; it does not overwrite the original measurement.

Each run still needs a current intent when it starts. Recording what the next run does is not a claim that the whole exploration was planned before any results. Reuse the existing commit, patch, configuration and promise-snapshot machinery where sufficient. Before implementing an additional field or file, identify what those sources already retain and which reader needs any missing information. Missing evidence must be named, not reconstructed from memory.

Earlier auditor findings and second-review outcomes remain available. Changing the question alone does not resolve a code fault or erase a rejected decision. For each proposed result, the audit needs the applicable run intent and implementation, the changes relevant to its interpretation, and the selection or comparison on which its conclusion rests. A previous audit cannot silently cover changed inputs or claims.

### What is separate

Existing cost-based instrument and code checks remain owed; an expensive exploration is not an audit exemption. Approval of an instrument before a costly run must be distinguished from freezing a hypothesis for confirmation. The audit supplies evidence about semantic fit, not proof that an instrument measures the intended construct.

The global release policy approved on 2026-11-16 is a separate work item. Exploration alone does not authorize release despite an audit BLOCKER. Until that policy is implemented, the existing release rules apply. A later implementation must preserve the distinction between exploratory status and permission to release with a documented objection; readable evidence and available measurements remain technical prerequisites.

Confirmation starts a separate protocol that identifies the exploration it builds on. Relevant choices precede the confirming evaluation. Whether the confirming data were already evaluated for that question is judged by the audit; a new path or file is not sufficient evidence. Changing `type` on an existing protocol cannot retroactively turn selected exploratory evidence into confirmation or remove a historical confirmatory miss.

## Walkthrough to make executable during implementation

This is a design example, not a new research experiment. It deliberately requires a report that depends on more than one run.

| Step                       | Work within one exploratory protocol                                                                                                          | Retained evidence and expected behaviour                                                                                                                             |
|----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| A: inspect errors          | Ask which errors predictor X makes and measure its outputs. A success threshold is absent unless the task requires one.                       | Run A retains this question, the data, code, settings, predictions and scores.                                                                                       |
| B: investigate a filter    | Errors in A suggest a filter. Record that reason, implement the filter and measure again.                                                     | Run B retains the revised question and filter. No new protocol is required solely for that refinement; A remains as measured.                                        |
| C: compare                 | Compare retained cases, errors removed and cases lost between A and B. If the analysis changes, record its source runs and analysis code.     | The comparison cites both runs. It does not treat A as if it had used B's filter, or report only the improved score while hiding changed coverage.                   |
| Audit and report           | Audit the measurements and comparison supporting the selected conclusion. Explain why the filter was investigated and whether it is retained. | The auditor sees both relevant run states and selection context; the report identifies the conclusion as exploratory. Applicable findings and release duties remain. |
| Confirmation, if requested | Start a separate confirmatory protocol linked to this exploration.                                                                            | The relationship and prior selection reach the confirming auditor; the old exploratory result is not relabelled as confirmation.                                     |

The example requires no universal numerical definition of a related question. It does require a reason a reviewer can assess. A user may also end the exploration without a result; the existing handover duty must remain usable.

## Record design to settle before code

The first and largest design task is how one reported result can depend on several measurement runs. Compare two representations using the same A–B–comparison walkthrough:

1. **A selected result run with additional sources.** Retain a selected run as the entry point, but explicitly bind the other source runs and the comparison used by its conclusion. Determine where the comparison is stored and how its analysis is checked; a run list alone does not establish the comparison.
2. **A separately recorded analysis of several runs.** Represent the comparison as an analysis with identified source measurements, code and outputs. Decide whether this uses a run, an analysis file or a protocol block; do not assume a new experiment kind or command is needed before inspecting the existing machinery.

Several source runs need not mean several independently adopted results. Compare the concrete files, commands, readers and tests for both representations, then recommend the smallest complete first implementation. A first version may be smaller than the entire implementation sequence, but it must preserve each run's meaning and bind the current claim to its actual sources. It cannot consist solely of removing the exploratory registration lock while rendering an old result through the latest question. If the proposed first version postpones the agreed multi-run comparison, state that limitation and seek an explicit scope decision.

The remaining representation questions must be resolved alongside that choice; none is an additional approved field or command signature.

1. **Intent at each run and reasons for changes.** Inspect `protocol_history.as_measured`, which already reconstructs the protocol from commit and patch, together with run records and promise snapshots. Establish which needed facts are retained and where change reasons belong. Preserve current commit-before-run obligations unless a separate change is explicitly proposed.
2. **Changing kind and working mode.** Specify representation and allowed transitions when an exploration begins tuning a predictor or a confirming investigation becomes exploratory for future work. Historical run types and findings remain; a separate confirmation is never created by changing a label.
3. **Relevant audit coverage.** Decide which run and analysis inputs a proposed conclusion needs, how changes invalidate that coverage, and how follow-up findings are attached. Reuse existing formats where adequate; do not require a fresh model call for every descriptive edit merely for uniformity.
4. **Forms and instrument approval.** Define the minimum exploratory fields and template outputs without a success criterion. Inventory actual `frozen` consumers by purpose: instrument readiness, confirmatory prior commitment or another technical dependency. An occurrence count is not a change count. Identify the smallest central separation before proposing any rename or broad migration.

### Reader inventory required for both representations

A reader here means a function or command that consumes protocol or report information, including commands that select or write the reported result. The design must say which facts it takes from the run's retained state, which it takes from the current claim, and what relationship it checks. This is a list of intended responsibilities, not a claim that today's readers already implement them. Do not switch every reader wholesale to the historical protocol.

For example, A measured all cases and B later used a filter. A must remain an all-cases measurement. The current report may compare A and B, but must acknowledge the different case selection and support the comparison with both sources. Historical intent and current interpretation are both needed.

| Reader to inspect                                                                           | Facts from each retained run or analysis                                                        | Facts from the current protocol or report                                                 | Relationship to establish                                                                                                                                                                     |
|---------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Result rendering (`result_render`)                                                          | The run's question, criteria, values, data selection and applicable audit evidence              | Selected result and source runs, comparison being reported, current decision/review state | Each displayed result retains its own meaning; a later filter or criterion does not silently rewrite an earlier result.                                                                       |
| Audit input (`audit_prompt`, analysis and report review inputs)                             | What A and B measured, their code and inputs, relevant findings and any comparison analysis     | Present conclusion, selection reason and explanations of changes                          | The auditor judges whether the present claim follows from the source measurements and analysis. This is semantic judgement, not proof from text equality.                                     |
| Run finalization (`finalize`)                                                               | The run's intent, required outputs, measuring code and recorded inputs                          | The applicable current release context and any explicit repair/correction decision        | Validate the run against its own measuring contract; current edits must not silently replace that contract or erase an unresolved defect. Specify exact checks after inspecting its stations. |
| Promise validation (`intent-check`)                                                         | Promise definitions and expected keys for that run, paired with its actual outputs              | Any request to reuse the result under a changed assessment                                | Check recorded outputs against their own promises; a new assessment needs an explicit analysis rather than pretending it was the original criterion.                                          |
| Recalculation (`recheck`, `labkit/checks/recheck.py`)                                       | Source measurements, recorded settings, the analysis version and inputs that produced the value | The result or comparison currently requested for checking                                 | Recalculate the intended measurement or explicitly identified later analysis; using today's analysis code must not silently redefine an older result.                                         |
| Parameter display (`labkit-params`, `labkit/tools/params.py`)                               | The effective settings kept by each selected source run or analysis                             | Which run or comparison the user asks to inspect, including any default selection         | Display the settings of the identified source, not the live protocol's replacement values; make distinct A/B settings distinguishable.                                                        |
| Next action (`labkit-next`, `labkit/gates/next_step.py`)                                    | Available run states and their applicable validation, audit and review coverage                 | Current investigation question, selected sources and work remaining                       | Propose adoption or repair for the intended result and its sources; do not silently choose the newest run or apply a later question to an older one.                                          |
| Adoption and protocol writing (`protocol-fill --from-run`, `labkit/tools/protocol_fill.py`) | The selected measurement or analysis and all source-run identities required by the result       | The proposed adoption, current conclusion and target protocol/report                      | Write the chosen representation with its evidence bindings; validate it before presenting it as adopted and preserve historical source states.                                                |
| Report release (`report-check`, adoption and report blocks)                                 | Identified source runs, analysis provenance and valid audit/review bindings                     | Current report, conclusion, result selection and effective release requirements           | Every result and comparison is attached to the right evidence; stale coverage and unexplained source mismatches remain visible and are handled under the applicable contract.                 |

For each row and each representation, name the actual functions, files, command arguments and tests. Trace selection through `bound_answering_run` and `area_state` as well as direct calls, and inspect the affected command paths. The listed rows are the starting checklist, not a proof of completeness. An existing caller need not change if it already receives the right state; record that finding instead of scheduling a rewrite. Mark facts already retained, facts needing another reader, and facts genuinely missing. Distinguish exact technical comparisons from the auditor's interpretation. This is how implementation cost becomes comparable without guessing from module or occurrence counts.

These choices must be resolved before format-dependent implementation. They should not expand into a general study-management system, configurable rule engine or rewrite of every gate. A new warning for drifting questions is not part of this plan.

## Bounded implementation sequence

| Step                                 | Work and homes to inspect                                                                                                                                                                                                                               | Completion evidence                                                                                                                                                        |
|--------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1. Specify records and command flow  | Compare the two result representations with the reader inventory first. Inspect retained protocol reconstruction, answering-run selection, adoption and report blocks; then resolve intent storage, audit coverage and the actual meanings of `frozen`. | Both A–B–comparison variants name concrete files, commands, historical/current inputs and checks; recommend the smallest complete version and identify any scope decision. |
| 2. Separate obligations              | Put exploratory and confirmatory duties in the contract layer. Make exploratory success criteria optional while retaining task-required assessments, validity checks and cost-based duties. Update forms, skeletons and generated area tests together.  | A criterion-free exploratory fit/apply works; an explicit criterion is evaluated; a confirmatory fit/apply retains its requirements.                                       |
| 3. Bind exploration per run          | Bind exploratory results to their own intent and changes. Keep the first-measurement lock for confirmation. Preserve old run types and findings.                                                                                                        | A related question or filter changes within exploration without a new protocol; the same prohibited confirmatory change is held; earlier evidence is unchanged.            |
| 4. Bind audits, analysis and reports | Give the auditor the applicable run and analysis states and selection context. Make adoption and rendering honour every source run required by the conclusion. Update `next` and printed repair paths.                                                  | The multi-run comparison and a selected old run retain the right meaning; stale coverage is held and the repair path works.                                                |
| 5. Support separate confirmation     | Record the relationship to exploration and show it to the confirming auditor even when no invalid registration is being replaced. Reuse existing predecessor support where appropriate.                                                                 | The relationship is bound to the audit; changing a type alone cannot establish confirmation.                                                                               |
| 6. Version, document and accept      | Make standard and format changes coherent; write Breaking and migration guidance. Update workflow, architecture, promise and run-binding docs, templates and agent guidance.                                                                            | Old runs remain reproducible with their original commit and pin; all readers are checked; command scenarios and final checks pass.                                         |

The targeted non-assessability change is completed under standard 0.31 (`e97aa0bd`, `4546ffe8`, command replay `8f85253d`); this plan is the subsequent workflow work item. The global release-policy change remains separate. Choose the actual new standard version when implementing, rather than reserving a number here. Respect public-API transition requirements and do not publish a partly relaxed gate before the supporting evidence and report bindings are ready.

## Acceptance scenarios and limits

Use pure tests for conditions, gate tests for selection and wiring, and scenarios with real commands for state passed between commands. Before claiming the new behaviour, show the old exploratory refusal and retain the corresponding confirmatory countercase.

1. Run the A–B–comparison walkthrough within one exploratory protocol. The audit and report identify both source states.
2. Compare several seeds; retain settings and the reason for selection without an automatic significance claim.
3. Change a question, filter or criterion between exploratory runs; old runs retain their original intent and verdicts.
4. Reanalyse existing outputs; keep measurement and analysis provenance distinct.
5. Attempt a prohibited registration change in a confirmatory protocol; it remains blocked.
6. Repair faulty measurement code; the next run is separate evidence and required audit/follow-up duties remain.
7. Select an older run while the live question is newer; no silent reinterpretation or stale audit release is allowed.
8. Change a protocol's type after a confirmatory miss or rejected decision; history and unresolved findings remain.
9. Verify that a criterion-free exploration still reports requested task assessments and measurement defects.
10. Start a separate confirmation linked to exploration; the auditor receives the exploratory basis and the claimed grounds for confirmation.

Run touched tests during implementation and the configured commit checks, followed by the full suite at integration. Review the final change independently and follow printed repair paths in a freshly stamped lab with supplied auditor answers. Those checks establish technical behaviour, not the judgement quality of real auditor models. A usability experiment and rollout to other repositories each require a separate instruction.

## Decision record and sources

The author accepted the workflow direction on 2026-11-14 after inspection showed that `exploratory` labels claims without relaxing registration locks. On 2026-11-16 the author explicitly agreed that an exploratory protocol may contain multiple related questions and runs, and requested this concrete plan. The workflow contract records that agreement; record-design choices remain open. No current rule or implementation is changed by this document.

- [Current workflow](../workflow.md): registration through audit, adoption and reporting.
- [Architecture](../architecture.md): checks, audit evidence and release responsibilities.
- [Promise contract](../promise-block.md): criteria, measurement validity and verdicts.
- [Protocol–run binding](../protocol-run-binding.md): identity and answering-run selection.
- [Registration-contract history](2026-10-27-new-registration-contracts.md): why the first-measurement lock exists; preserve evidence of moved bars.
- [Decision review](2026-10-23-decision-review-history.md): implemented criterion-specific non-assessability under standard 0.31.
- [Audit-record lifecycle](2026-11-16-audit-record-lifecycle.md): retained originals, mutable decisions and the separately approved release policy.
