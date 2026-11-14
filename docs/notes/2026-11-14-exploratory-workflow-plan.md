# Exploratory workflow: bind each run to its own intent

> Plan approved in direction by the author on 2026-11-14; not implemented. Current registration and release rules still apply. [TODO](../../TODO.md) holds the work order. This plan authorizes documentation and design, not an experiment, release or rollout.

An exploratory investigation may change its question, procedure, seeds, filters and assessment after seeing results. Each run must retain the intent, inputs, code and assessment that produced its recorded result. A confirmatory protocol continues to bind its relevant choices before the results are seen. The author requested this distinction because the current exploratory label does not relax the first-measurement registration lock.

## Current behaviour and the gap

`type` identifies exploratory or confirmatory claims, but the obligations in `standard_contract.lane` depend on repeat cost, and `registration_fields` depends on experiment kind and whether a model is named. The guide explicitly retains criteria and audits for exploratory fit and apply experiments (`labkit/docs/agent-guide.md`, “Choose the experiment”). `registration_hold.registration_changes` binds later measurements to the first measurement's promises; `scope_changes` also holds changes to what the number is about. These checks have no exploratory exception.

Today, a changed scientific choice usually requires another protocol. `report_replacement.replacement_gaps` verifies declared changes in a replacement. It leaves the scientific justification of the exploratory or confirmatory label to the audit. A confirmatory replacement's auditor receives predecessor evidence through `audit_prompt.predecessor_evidence`; the scope stamp includes that evidence. The new workflow must preserve that protection while allowing exploration within one protocol.

## Intended contract

| Concern               | Exploratory                                                                         | Confirmatory                                                             |
|-----------------------|-------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Question and analysis | May develop between runs; record the change and its reason                          | Relevant choices fixed before the evaluated results                      |
| Success criteria      | Optional unless the task requires an assessment; additions and changes are explicit | Registered before the relevant measurement where a criterion is required |
| Measurement validity  | Audit whether implementation and analysis answer the stated question                | Same duty, plus adherence to registration                                |
| Evidence              | Each run retains its own intent, data, code, settings and results                   | Same provenance, plus the fixed registration                             |
| Selection             | Seeds, variants and runs may be compared; report the selection and its basis        | Follow the registered selection and analysis plan                        |
| Report                | Describe what was learned and which decisions followed observation                  | Report the registered comparison and justified deviations                |

Optional success criteria do not make measurement validity optional. A score implementation must still use the intended pairs, exclusions and metric. Explicit task requirements remain owed: exploration cannot discard an externally requested target or answer. A failed scientific criterion remains a valid negative result; a faulty measurement requires repair or a qualified claim.

Existing cost-based protections remain in scope: an expensive run still needs the required instrument and code checks before execution. The implementation must distinguish approval of a run's instrument from freezing a hypothesis for confirmation. There is no blanket audit exemption. The audit is evidence about semantic fit, not proof that the instrument measures the intended construct.

## Workflow to implement

1. Start an exploratory protocol with a current question and a description of the intended measurement. Define any task-required assessments and relevant measurement checks. No invented success threshold is required merely because the kind is fit or apply.
2. Before each measurement, retain that run's intent together with the code, inputs and settings it uses. Reuse commit-plus-patch reconstruction and promise snapshots where they suffice. Missing evidence must be an explicit error, never an invented earlier intent.
3. Inspect the result. Record why the next run changes the question, procedure, seed, filter or assessment. Record earlier results as they were; a changed criterion does not rewrite an earlier verdict. Reanalysis of retained outputs must identify its source run and changed analysis, rather than overwrite the measurement evidence.
4. Audit the result proposed for reporting against its own intent and implementation. Reuse the current audit and follow-up machinery where its bindings remain correct. Earlier findings retain their meaning and evidence; a changed question alone does not close them.
5. Report selected results as exploratory, with the compared runs or variants and the reason for selection visible. Retain the difference between descriptive numbers and claims. A report need not reproduce every output, but must not hide selection that changes the conclusion's meaning.
6. For confirmation, create a separate confirmatory protocol identifying the exploration it builds on. Fix the relevant choices before the confirming evaluation. The auditor judges whether those data were already evaluated for that question; new paths alone do not establish independence. Relabelling an existing exploration does not supply confirmation.

A historical confirmatory miss cannot be erased by switching `type`. The recorded type of each run must remain available. An explicit change of working mode may guide future runs; it cannot retroactively release registration violations, rejected decisions or an earlier BLOCKER. The precise transition representation belongs in the format design below.

## Bounded implementation sequence

Each step produces a reviewable change and its validation before the next. The current usage-round repairs retain their existing priority; this is a separate follow-on work item.

| Step                                        | Work and homes to inspect                                                                                                                                                                                                                                                                                                                                   | Completion evidence                                                                                                                                 |
|---------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| 1. Specify the contract and record design   | Map registration, run start, first-measurement locks, audit binding, adoption and reporting. Inspect `standard_contract`, `protocol_check`, `protocol_history`, `promises.snapshot`, run records, `registration_hold` and `report_check.registration_gaps`. Decide the minimal retained representation for run intent, change reasons and later reanalysis. | One concrete walkthrough with two exploratory runs and a changed question; all readers and writers identified; format choices explicit before code. |
| 2. Separate obligations                     | Give exploratory and confirmatory workflows one home in the contract layer. Make exploratory success criteria optional while retaining task requirements, validity checks and cost-based duties. Update field selection, skeletons and generated area tests together.                                                                                       | A criterion-free exploratory fit/apply is usable; a supplied criterion is evaluated; a confirmatory fit/apply still owes its criterion.             |
| 3. Bind exploration per run                 | Make exploration compare each result against its own retained intent. Keep the first-measurement lock for confirmation. Keep historical run types and prevent relabelling from releasing old findings.                                                                                                                                                      | Changed exploratory question or threshold accepted for a new run; same confirmatory change held; historical evidence and verdicts unchanged.        |
| 4. Bind audits and reports to the right run | Show the auditor the intent and changes relevant to the selected run, selection context and any later analysis. Make rendering and adoption use those sources rather than silently interpreting an old run through the current protocol. Update decision review and `next` paths where affected.                                                            | Correct source runs and intent reach audit and report; stale audit or mismatched intent held; open BLOCKER remains held.                            |
| 5. Support confirmation after exploration   | Record the relationship to exploration and show that context to the confirmatory auditor, including when no invalid registration is being replaced. Reuse existing predecessor support where appropriate.                                                                                                                                                   | Context reaches the auditor and its binding; changing the type alone does not turn selected exploratory evidence into confirmation.                 |
| 6. Version and document the whole contract  | Announce the break through a new standard version and CHANGELOG; update workflow, architecture, promise and run-binding docs, templates, agent guidance and migration messages. Reuse existing names; do not create a second parallel protocol system.                                                                                                      | Every reader and template checked; prior completed runs remain reproducible with their original pin; migration is explicit.                         |

The standard and format changes must ship coherently. Do not expose a partly relaxed gate before per-run evidence and reporting are ready. Decide the actual version at implementation time; other approved work may change it first. Keep existing public-API transition requirements where applicable.

## Acceptance scenarios and limits

Use pure checks for conditions, gate tests for wiring and scenarios for real command sequences. Before claiming repair, demonstrate the old refusal for an exploratory change and the corresponding unchanged confirmatory refusal.

1. Compare multiple seeds in an exploratory protocol; retain settings, results and selection reason. No automatic claim of statistical significance follows from selection.
2. Change a question, filter or criterion between two exploratory runs; the old run still shows its original intent and verdict.
3. Reanalyse existing outputs under a new rule; retain source measurement and analysis provenance separately.
4. Attempt the same registration change in a confirmatory protocol; it remains blocked.
5. Repair incorrect measurement code; required audit and follow-up evidence remain necessary.
6. Select an old run while the current protocol describes a later question; no silent reinterpretation or stale audit release is allowed.
7. Switch a protocol's type after a confirmatory miss or rejected decision; neither history nor unresolved findings disappear.
8. Register a confirmation following exploration; its auditor sees the exploratory basis and assesses whether the confirming evaluation supports that status.

Run touched tests during implementation and the configured commit checks; use the full suite for final integration. Technical fixtures can establish binding, rendering and gate behaviour. They cannot establish that model auditors correctly judge scientific validity. A later usability experiment requires a separate research instruction. Rollout to other repositories is also separate.

## Decision record and sources

The author accepted the workflow direction on 2026-11-14 after a read-only inspection showed that `exploratory` currently labels claims without relaxing registration locks. This plan records the accepted direction and proposes the implementation sequence; it does not change standard 0.29.

- [Current workflow](../workflow.md): registration through decision review, adoption and reporting.
- [Architecture](../architecture.md): checks, audit evidence and release responsibilities.
- [Promise contract](../promise-block.md): criteria, measurement validity and reported verdicts.
- [Protocol–run binding](../protocol-run-binding.md): identity and the answering run.
- [Registration-contract history](2026-10-27-new-registration-contracts.md): why the first-measurement lock was introduced; exploratory flexibility must preserve the evidence of moved bars.
- [Decision review](2026-10-23-decision-review-history.md): current and planned non-assessability effects; that approved change remains a separate work item.
