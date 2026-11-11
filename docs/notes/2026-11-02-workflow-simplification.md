# Plan to simplify the labkit workflow

2026-11-02, requested by Max; status checked on 2026-11-03.

Correct work should reach a readable report with fewer repeated steps, and the scientific standard stays as strict as before. This note is the work plan for that. The rules in force stay in the standard and in the [workflow](../workflow.md); nothing proposed here changes them.

State on 2026-11-03, all in commit `e754b0c3`:

- Built: package B (a report before the result is adopted); the registered-field repair, the first step of package A (repair guidance and gates compare against the first registration); the fixes from the repair-path probe, absolute and relative thresholds in both the estimator and the prompt template, and the integrity check for committed records.
- Kept: the decision review by a second auditor. The proposal to give auditors a fixed list of verdict grounds was not adopted.
- Done: the check of the four remaining interface reports ([Interface closeout on 2026-11-03](#interface-closeout-on-2026-11-03)) and both maintainability reviews.
- Next: the repairs in the order of the [combined plan](2026-11-03-maintainability-repair-plan.md).

## Evidence from area 17

Area 17 of labkit-paper gave the same three tasks (34, assay and sts512) to 18 attempts with labkit and to 18 control attempts, which worked in an empty repository without labkit. Six of the labkit attempts hit the time limit of 40 minutes; no control attempt did. Five of these six left no report.

This contrast does not show what labkit costs. Four of the six timeouts fell into the same proxy outage, and each of them lost about 16 minutes to retries. No control attempt ran during that outage. The timeouts therefore mix labkit's cost with the outage and must not be reported as labkit's effect alone.

The other two timeouts, both at task 34, fell outside the outage and show where the time went:

- Seven follow-up audits after edits to prose only: about 20 minutes in total. These audits left the numbers unchanged, but one of them found a missing reference.
- Finding out how to register a successor protocol: about 18 minutes across both attempts.
- Repeated calculations: seconds each. No expensive acquisition was repeated.

Sources and limits: [Evidence appendix](#evidence-appendix).

## Work packages

| Package                            | Change                                                                                                                               | Status and next action                                                                                                                                                                                                                                                    |
|------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **B — report before adoption**     | Before the audit loop, the agent saves a readable intermediate report. Adoption replaces its discussion block with the result block. | Built; passes the joint check with the registered-field repair ([Acceptance and verification](#acceptance-and-verification)). Whether B saves time is unmeasured: that needs an agent comparison.                                                                         |
| **A — consistent repair guidance** | When run evidence has changed, the decision hint, `labkit-next` and the release gate give the same answer.                           | The registered-field repair built in `200c6ebb`, example helpers in `4dbf203c`. How to correct: [A: consistent repair guidance](#a-consistent-repair-guidance). The binding of runs to their code is not relaxed in general.                                              |
| **C — decision review**            | Decide whether the decision review by a second auditor can be dropped, or required in fewer cases.                                   | Kept for now: in the BLOCKER limitations examined, the second auditor caught errors. Its prompt now also carries the values of the required checks and the measuring script as it ran. The proposal for fixed verdict grounds failed its replay test and was not adopted. |

B is built in these commits:

- one measurement check shared by all gates: `7c70615f`
- the writer that sets the report path: `410507cc`
- the reader for the registration as first committed: `82a372a5`
- the binding of the report to the registration: `c413182d`
- replacing the discussion block on adoption: `c68e0b0b`
- next step and commit: `4a664163`
- workflow text: `82dfa297`

Commit `e754b0c3` also contains four repairs: how a handover binds the attempt journal `attempts.jsonl`, one comparison for predecessor and successor protocols, a BLOCKER on the Conclusion, and protection against a deleted report. The commit gate and the working-tree gate now compare committed evidence the same way, handovers and predecessor areas included. One limit stays on purpose: labkit cannot verify where a new record came from, so this is no protection of provenance. Contracts and limits: [repair-path note](2026-11-02-repair-path-probe.md), [record-integrity note](2026-11-02-review-record-forgery.md), [handover note](2026-11-03-handover-journal-binding.md).

When an agent writes a field address that `protocol-fill` cannot parse, the error now names the command's existing syntax (`e0837d48`); there is no new input format. Evidence: [Evidence appendix](#evidence-appendix), item "Field addresses".

The proposals after section B are separate work; B does not wait for them. The evaluation stays in the order area 17, then area 18. This plan starts no new agent round.

## B: report before adoption

### Register the report before measuring

A protocol's `kind` says what its number asserts:

- `compute` calculates a quantity;
- `fit` evaluates a model trained or adjusted in the experiment;
- `apply` evaluates a model used unchanged.

When a task requests no threshold, evaluating predictions does not automatically become a `compute`. Task 60 compares against a fixed model; which kind it is stays undecided, and it will not be redesigned before B.

Registration is the same step for all three kinds. The fields each kind requires have one home, [`standard_contract.registration_fields(kind, model)` and `skeleton(...)`](../../labkit/formats/standard_contract.py); `protocol-check PROTOCOL --contract` prints them. Do not copy these field lists into another contract.

If a task requires a report, register it before the first measurement: create the area with `--report-file REPORT.md`, or run `protocol-fill PROTOCOL report=REPORT.md`. Both options existed before; the agent guidance now points to them. None of the 18 protocols in area 17 registered a report, so B could have applied to them only with this step.

Changing the registered report path:

- Before the first measurement, replacing the path needs `--force`.
- The first measurement requires the report path to be committed, at repeat cost `low` and `high` alike.
- After that, removing the path or pointing it to another file blocks. There are two ways out: restore the path, or hand over and register a successor protocol explicitly. The earlier evidence stays.

A new registration is not the normal repair for faulty code.

The first measurement as committed fixes the report path at both repeat costs; raising the repeat cost to `high` does not lift this binding. If the first measurement had no registered report, it fixes that absence too. A report registered later blocks, whether the agent edits the protocol by hand or `protocol-fill` proposes the change. The agent may restore the original path. To change whether a report is owed, the agent hands over and registers a new protocol. At `high`, the freeze and the preflight audit are still required in addition. Decision and tests: [report binding at both costs](2026-11-03-report-binding-both-lanes.md).

Both templates, the estimator and the prompt template, now accept an absolute and a relative threshold through `criterion_bar`; the decision is in the [absolute-bar note](2026-11-02-absolute-task-bar.md). This repair leaves two separate questions open: whether the count skeleton suits its tasks, and which kind task 60 is. Test B on a valid baseline, and do not count a failure of a template against B.

### Save progress, then continue the checks

After a measurement has completed, `labkit-next` asks for an intermediate report before it names the audit BLOCKERs. The agent writes it with the existing command:

```sh
protocol-fill PROTOCOL --discuss RUN --why "what was measured; what remains open" --into REPORT.md
```

The report explains the question, the method, the work done and what is open. Its discussion block names the current answering run and states that it releases no result. Once the report exists, `labkit-next` names the remaining work; it does not answer `nothing` just because progress was saved.

The commit gate accepts this intermediate report. The stop hook reminds the agent once to adopt the result or hand over. All other blocks stay: an intermediate report does not waive an undecided audit BLOCKER, changed run evidence or malformed references.

No extra model review is required before the audit loop. The final report review of this registered report is due once its result block or handover block exists. Until then, the progress text is unreviewed and can be wrong. The final review reads the final report, including any progress text left in it; it does not read earlier Git versions on its own.

On adoption, labkit replaces the matching discussion block with the result block, in the same place. Blocks of other protocols, discussions of other runs and the surrounding prose stay. The final report stays blocked until its required review passes. A valid negative result takes the same path.

### Where the existing workflow changes

| Step in [the workflow](../workflow.md#the-steps-at-a-glance) | What B changes                                                                  |
|--------------------------------------------------------------|---------------------------------------------------------------------------------|
| 0–2: create and register                                     | A required report is registered before the first measurement.                   |
| 3: measure                                                   | The agent saves progress before the audit loop.                                 |
| 4–6: check, audit, decide and review                         | The release requirements stay; the report names the work still owed.            |
| 7–8: adopt and report                                        | Adoption replaces the matching discussion in place; the final text is reviewed. |
| 9: stop and commit                                           | The commit accepts progress, the stop hook reminds once; no result is released. |

B uses the existing writers, report checks and next-step logic. Each command checks its conditions again: an earlier hint is neither a permission nor evidence that a step ran. The registered-field repair and its repair by a new run change steps 4–5 and the recovery. Step 6 keeps the decision review; the proposal for verdict grounds is not adopted.

## Acceptance and verification

| B case               | Required outcome                                                                                                             | Tests                                                                                                                               |
|----------------------|------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Save progress        | A discussion of the current run passes the staged commit; the stop hook reminds once; no adoption and no extra model review. | `tests/test_next_step.py::ProgressAccount`, the registered-report pairs in `tests/test_report_check.py`                             |
| Survive interruption | An interrupted audit leaves a readable report and a valid next step, and claims no success.                                  | `ProgressAccount`, `tests/test_attempts.py`                                                                                         |
| Retain protection    | Open BLOCKERs, changed evidence, stale references and malformed blocks still block where they apply.                         | `ProgressAccount`, `tests/test_report_check.py`, `tests/test_registration_committed.py`                                             |
| Finish cleanly       | The matching discussion is replaced, unrelated content stays, the final review is due; a negative result works the same way. | `tests/test_report_blocks.py::AdoptionReplacesTheAccount`, `tests/test_report_review.py`, `tests/test_counter_cases.py::HonestMiss` |

The combined local probe ran real commands on a registered count protocol, in this order:

1. measure;
2. save a discussion;
3. commit the staged progress;
4. correct a misdescribed document count;
5. decide `fixed`;
6. try to adopt after a fresh audit without a verdict: refused;
7. obtain an explicit `resolved`;
8. adopt;
9. review the final report;
10. pass the staged check.

The progress text stayed in the report while adoption was refused. Adoption replaced it, and the report review was still owed afterwards. A second probe with a registered report took the same path with a missed prediction criterion: the negative result stayed a miss and passed the final review and the staged gate.

The model answers in both probes were fixtures, so the probes check binding and command order, not scientific judgement. The selected regression tests cover next step, report blocks, registration, repair paths, end-to-end runs, counter-cases, the executable workflow and the field commands. The repository's required checks also run before each commit. The protection regression set stays the historical [injection benchmark](../usability/2026-10-29-injection-ab4ce6d.md); the local tests do not replay it. A replay needs valid current baselines and a finding about the intended fault, not only an exit code other than zero.

- [x] Build B's prerequisites, the progress path and the block replacement.
- [x] Map the four acceptance cases and run B together with the registered-field repair.
- [x] The required repository checks passed on `e754b0c3` (ruff, format, pyright, full suite): 2835 tests and 6914 subtests passed, one test skipped. This shows that the commands and the regressions hold; it is no new agent comparison and no injection replay.
- [ ] Before claiming that B saves work, compare agents in a controlled setup that separates infrastructure failures from labkit's cost.

## A: consistent repair guidance

The probe on `82dfa297` found a real bypass. An agent changed Unit or Terms, audited the first run again, and could adopt; measuring again instead ran into the registration block. The decision hint recommended exactly that second path, which did not work. The registered-field repair now compares both the current protocol and the run snapshots with the first registration, and the repair guidance uses the same comparison.

An agent can correct a setup description in place only with three things together:

1. a finding that names the full field label;
2. a `fixed` decision;
3. an explicit `resolved` from the follow-up audit for this state.

A fresh audit alone releases nothing, for WARNINGs too. The question cannot be corrected this way, not even for a typo; standard 0.26, the guide and the code agree on this. labkit checks the binding mechanically. Whether another field still describes the same experiment is the auditor's judgement, based on evidence outside the changed field. The [registered-field note](2026-11-02-registered-field-repair.md) holds the detailed contract, its limits and the tests.

Keep the repair paths apart:

- **Faulty implementation:** repair the code, repeat the affected measurement and checks, obtain the required follow-up evidence.
- **Description of the same run:** the correction route bound to the field can release it. If a later code repair needs a new run, that run needs its own `resolved` verdict, and its recorded, current and judged field values must agree. The old verdict alone releases nothing. Each field needs its own release.
- **Conclusion only:** no new measurement and no new analysis audit for that edit alone; the required decision review and report review stay.
- **Changed scientific choice:** restore it, or register a successor explicitly. The threshold probe found that the existing promise and registration checks already block a moved threshold; this is no exception for corrections of prose.

`--withdraw` removes the adoption and the result blocks; it restores no files and deletes no runs. A commit is a checkpoint, not proof that the repair worked. Do not decide `limitation` automatically: the author must judge the claim that remains. The six timeouts in area 17 give no reason to relax the comparison of code in general or to build a new feature for derived runs, because expensive remeasurement was not what cost time there.

## C: decision review

In the BLOCKER limitations examined, the second auditor caught errors, so the decision review stays required. Some decisions it blocked lacked evidence in its prompt; shared helpers now add the values of the required checks and the measuring script as it ran. Correct numbers alone do not show that a limitation or a conclusion is justified.

The proposal for fixed verdict grounds was not adopted. Its replay stopped after 37 proved answers (41 calls, four of them without a proved outcome), because a stop condition fixed beforehand was broken: on a correct decision whose conclusion had been checked and holds, the reviewer objected to the conclusion in both draws. In that case, the task's method and the conclusion's unqualified wording disagree. The grounds also overlapped. This partial result shows neither that the instructions are equivalent in general nor which case labels are right. This plan starts no further model round. The [verdict-ground note](2026-11-02-review-verdict-grounds.md) holds the proposal and its limits; this plan adds no verdict categories and no review duty.

## Interface closeout on 2026-11-03

The four remaining reports were reproduced on `main` at `a2202e36`, with real commands in fresh count labs and supplied model answers. They say nothing about the quality of an auditor's judgement.

| Case                                                       | Finding and what follows                                                                                                                                                                                                                                                                                                  |
|------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Older progress discussion stays in a final report          | Reproduced. `with_block` keeps the discussions of other runs on purpose, so a result for the newer run and an old discussion stand side by side. labkit deletes nothing automatically. To update an outdated reason, run `protocol-fill --discuss OLD_RUN --why ... --into REPORT`, then review the changed final report. |
| After a withdrawal, progress is asked for the previous run | Reproduced. labkit saves the current run as unapproved progress; the next step then correctly asks to measure the changed code. This follows B's agreed order (progress before gaps) and is no dead end. Changing the order would be a separate product decision.                                                         |
| A finished registered report is called unregistered        | Defect confirmed and repaired. The last step now names the registered path; the guidance for an unregistered report stays for areas that register no path.                                                                                                                                                                |
| A report with prose only is blocked before any measurement | Defect confirmed and repaired. A valid draft can be committed together with the registration; after the measurement, the same file owes progress, a result or a handover. Malformed blocks still block.                                                                                                                   |

Both regression tests failed on the old behaviour. The test for the report label uses `SUMMARY.md`, completes adoption and report review, and then checks the final guidance. The test for the draft commits the first report, rejects a malformed block, measures, checks that the unchanged draft is now blocked, and commits successfully after the progress command. Tests: `tests/test_next_step.py::ProgressAccount` and `tests/test_repair_paths.py::BeforeTheFirstMeasurement`.

This check of the interface is complete. Its deliberate limits, listed in the table above, become neither new general blocks nor a service that records command history. Next comes the maintainability review. Whether B saves work still needs an agent comparison, planned separately.

## Follow-up work, not prerequisites

### Check the scientific coverage

Use the existing sources:

- the standard for what is owed;
- the [chain table](../architecture.md#the-chain) in the architecture for checks and tiers;
- the workflow for the actions;
- the tests for the behaviour that can be observed.

Add only three decision fields to the review of the chain: which error the check prevents and the evidence for it; what it costs on correct work; and whether to keep, move, merge, warn or remove it. Do not create a second map of checks.

For each requirement that applies, record:

- what must hold, and when it applies;
- which evidence the check reads;
- the exact scope and limits of the check;
- the consequence, and the valid way to recover;
- a faulty, a correct and a repaired case.

Checks of the same fact must share one comparison; a partial comparison must not claim that the whole state is unchanged. Run the recommended recovery through the next gate.

| Scientific requirement                  | Evidence needed                                           |
|-----------------------------------------|-----------------------------------------------------------|
| Question and method fit                 | Scientific review.                                        |
| Suitable data, splits and controls      | Checks in code, plus a review of suitability and leakage. |
| Correct metrics, units and denominators | Examples checked by hand, and meaningful faults.          |
| Appropriate randomness and uncertainty  | Design and analysis checks that depend on the task.       |
| Traceable results                       | Binding of registration, code, input, run and report.     |
| Supported conclusion                    | Scientific review of the claim and its limits.            |

A requirement of the standard that is justified, together with a meaningful counterexample, can justify a protection before any incident is observed. Not every task needs every check. Mark explicitly what a mechanical check covers, what a semantic review covers, where the gaps are and where the scope ends. Questions such as which tasks need a null comparison are proposals for the standard; this note does not answer them. This review adds no block.

### Threshold forms in the templates

The existing promise constants now accept exactly one of `at_least` (absolute threshold) and `margin` (relative threshold). Both templates use `labkit/formats/criterion_bar.py`; there is no second syntax for criteria and no separate configuration file. If a threshold comes from outside, its source stays in the criterion sentence. The null checks and quality checks stay. Standard 0.25 allowed the absolute form; 0.26 also sets the limit for correcting the question.

The [absolute-bar note](2026-11-02-absolute-task-bar.md) holds the decision and the tests. The technical declarations stay the authority; whether they are scientifically suitable still needs review. No general redesign of the declarations is planned.

### Command history and test reorganization: deferred

`labkit-next` should explain, from shared rules, which evidence is missing, which action is allowed and which command does it. A progress view can use the existing records and the protocol's requirements. A missing record does not tell whether a step was skipped or not needed, and a hint is no evidence that a step ran.

A full command history would tell apart a recommendation, a start, a success, a refusal and an interruption. How to store and protect it needs its own design. Local files cannot hold a history that an agent cannot change, because the agent can rewrite every copy. B needs neither a history service nor a stored status.

Do not build a table of stages in code before finding logic that is actually duplicated: the next step and the hooks already share `report_gaps`. Tests that cover the same code are not redundant for that reason alone; tests of a function, a gate and a hook protect different things. Reorganize the tests after the behaviour is stable, not before B.

### Maintainability review after the simplification

Max asked for this review once the current simplification is complete. The four confirmed defects in the repair paths and the interface check are done. The [repair-guidance review](2026-11-03-maintainability-review.md) and the [shared-rules review](2026-11-03-shared-rules-review.md) are done too. Their [combined repair plan](2026-11-03-maintainability-repair-plan.md) sets the order:

1. the omitted checks of prompt and scope, and the handling of a malformed run index;
2. the guidance for withdrawal and decisions;
3. the remaining candidates, after each is reproduced.

Findings that both reviews share are handled once. The scope of the report binding and the removal of the old journal stay explicit decisions; they are not assumed as cleanup.

Split large modules only along clear responsibilities. Keep tests that protect distinct failures; size or overlapping coverage alone is no reason to remove them.

For each proposed change, answer one question: does it remove duplicated logic or a special case, or does it add another exception? Judge a simplification by that answer and by the behaviour it preserves, not by line count alone. Where different checks differ for a reason, keep the difference explicit instead of forcing them into one rule.

The first inspection was a targeted review of the structure, not a full audit. It counted about 50,000 tracked Python lines in the package and 55,000 test lines, comments and docstrings included, and eight architecture tests passed. These figures describe that state of the code; they do not show that it is maintainable. The follow-up should deliver concrete findings and small changes, each backed by a faulty, a correct and a repair-path test, and no general rewrite of the framework.

## Evidence appendix

- **Area 17:** labkit-paper `scores_attempts_c17.jsonl`, commit `48c8a2d`, summary `96c7f69c`; [TODO context](../../TODO-history-2026-11-06.md#werkzeuge-und-standard). All 18 attempts called labkit; none registered a report. One other attempt, at task sts512, changed its null band after a failure and passed with warnings, without audit or adoption. This one case proves nothing about the timeouts in general.
- **Timeout assessment:** labkit-evidence `72bf1b01`, `usability/2026-11-02-c17-timeouts/` (`assessment.md`, `rounds.tsv`, `outage.tsv`). Four timeouts overlapped with 502 errors between 06:28 and 06:40 UTC. Fourteen audits completed:
  - five initial audits;
  - one voluntary preflight audit;
  - one audit confirming a repair;
  - seven audits after edits to prose.

  Whether the peak correction and the split finding were correct is not verified. Raw traces and excerpts stay in the evidence repo.
- **Registered-field probe:** `probe-registered-field/` in the same evidence directory, on the archived labkit `82dfa297`, with real commands and stand-in audit records; the [registered-field note](2026-11-02-registered-field-repair.md) links its consequences.
- **Round 2:** [assessment](../../TODO-history-2026-11-06.md#wo-die-vollendung-stirbt--auswertung-der-48-laborversuche-der-runde-2-2026-10-31-nachts). 12 of 48 attempts adopted a result: seven followed the rules, five did not. Six unfinished cases had outdated audits after code edits; four had decided `fixed` without the required measurement and audit. The causes overlap. All 39 attempts counted from transcripts called labkit.
- **Field addresses:** `process_attempts_c17.json`. Of 175 `protocol-fill` calls, 18 ended with exit code 2: ten named a wrong field, seven a field already filled, one edited a frozen protocol; none failed on shell quoting. Two suggestions confused `criterion-1 sentence` with `Inference criterion`. `field_address_hint` now names the existing syntax before it suggests similar fields. CLI tests follow that advice and check that a refused input leaves the files unchanged. Input from a file stays deferred; these small errors are not shown to cause timeouts.
- **Decision review:** [replay](../usability/2026-10-22-decision-review-replay-v5.md), 13 of 15 judgements stable across two runs. The later case assessment and the verdict-ground replay are in labkit-evidence, `usability/2026-11-02-second-review/` and `usability/2026-11-02-review-grounds-replay/`. Whether the judgements are stable and whether the review catches additional errors are separate questions.
