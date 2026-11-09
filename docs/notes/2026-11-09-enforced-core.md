# What labkit enforces — the blockers by the assurance they protect, 2026-11-09

*Decision basis · for the author · the blocking sites of the inventory at 522e008c, each read through its rule ([rule-per-finding proposal](2026-11-09-rule-per-finding-proposal.md)); before any restructuring of the checks*

labkit supports the lab standard and enforces named parts of it. What it enforces follows from what a check can show and which fault it prevents, not from a rule being mechanically checkable. Three kinds of question:

| Kind                              | What labkit does                          | Example                                                                                             |
|-----------------------------------|-------------------------------------------|-----------------------------------------------------------------------------------------------------|
| A contradiction that can be shown | blocks                                    | the report names another run than the adopted one; the stored number differs from the recomputation |
| Required evidence                 | withholds the release while it is missing | a required audit is absent or does not cover the current code                                       |
| Scientific judgement              | puts it to the audit and the author       | is the null condition sensible; does the result carry the conclusion                                |

A passed check confirms its own condition, never the scientific correctness of the result.

## The chain labkit enforces

| Assurance        | What it holds                                                                                      | Rules its blocking sites cite or are assigned                                                                                                                                                                                                                                                                                                       |
|------------------|----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 Registration   | intent and criteria stand before the measurement; later changes show                               | LAB-003 No run without an intent paragraph, LAB-004 Identifiers make the intent addressable, LAB-011 Required-field check, LAB-007 Render check before the instrument check (the registered prompt), LAB-017 The number of audits follows the cost tier, LAB-038 What the prompt demands, LAB-067 A prompt has one home                             |
| 2 Provenance     | a run names the protocol, code, configuration and data that determine its number                   | LAB-010 Commit before the run, LAB-019 The stamp covers everything that determines the number, LAB-043 Runs go through `runlog`, LAB-103 The audit reads by declared scope, LAB-024 Reproducible, LAB-022 Datasets explain themselves, LAB-041 Generate numbers, don't retype them (the frozen data sources); the protocol id as technical contract |
| 3 Completeness   | an aborted or incomplete run is not given out as a full result                                     | LAB-009 Verdict only at the registered tier, LAB-023 No silent loss, LAB-048 An intermediate number is not a result, LAB-057 One area per idea (one output, one run)                                                                                                                                                                                |
| 4 Audit coverage | the required audits concern the state that counts; their findings are decided or handed over       | LAB-015 Preflight audit before freezing, LAB-050 Analysis audit before reporting, LAB-018 Routine check after every implementation                                                                                                                                                                                                                  |
| 5 Report         | the reported number comes from the adopted run and equals its generated form and its recomputation | LAB-104 A number leaves the area only through its adoption, LAB-041 Generate numbers, don't retype them                                                                                                                                                                                                                                             |

## Count

178 sites block (a gate's BLOCKER or a run's start refusal). A site whose sources hold several rules counts under each assurance it serves.

| Assurance         | A violation | A check left open |
|-------------------|-------------|-------------------|
| 1 Registration    | 47          | 6                 |
| 2 Provenance      | 19          | 5                 |
| 3 Completeness    | 10          | 4                 |
| 4 Audit coverage  | 13          | 8                 |
| 5 Report          | 40          | 8                 |
| outside the chain | 10          | 3                 |

Ten more hold no rule: five preconditions of the gate itself, three the protocol-id contract, one the changed-records candidate, one a wrong command line.

## Outside the chain

The five assurances orient; they are no closed list of the blockers allowed. A blocker outside them is judged by itself, not turned into a warning for being outside.

**Instrument checks and validation** — required checks of the instrument and shown faults, not a claim that the instrument works; a present test or a bound validation study proves neither.

| Site                                     | What it finds                                                                                                                           | Assessment                                                                                                                                                                                                                                                      |
|------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `labkit/gates/preflight.py:586`          | the area's required tests fail (CODE-003 Test the functions that produce numbers)                                                       | can block: a shown fault                                                                                                                                                                                                                                        |
| `labkit/formats/protocol_history.py:357` | a judge's required validation is bound to no adopted protocol (LAB-052 Instance gate before registered use)                             | can block: required evidence missing                                                                                                                                                                                                                            |
| `labkit/gates/preflight.py:418`          | no test file for the resolution check (LAB-016 Resolution check before freezing)                                                        | can block: required evidence missing                                                                                                                                                                                                                            |
| `labkit/checks/prompt_check.py:87`       | a `parse_*` whose name no call in `tests/` carries (LAB-016 Resolution check before freezing)                                           | a name match (`labkit/checks/prompt_check.py:73`) shows no coverage and misses a parser tested through a caller: static evidence by labkit's own tiers, which never blocks — regraded to a static-evidence warning 2026-11-09                                   |
| `labkit/checks/run_record_check.py:405`  | the null lane's answer and gold equal the registered lane's on every item (`null_lane_unmoved`, LAB-034 Null condition in the same run) | an observation: matching answer–gold pairs on every item compared. How the rows came about, and whether the null condition should come out otherwise — what change the registered null condition makes expect — is a further question for the per-blocker check |

**Run operation** — the conditions a run executes under.

| Site                               | What it finds                                                                                           | What it prevents                                                                                      |
|------------------------------------|---------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| `labkit/run/endpoint_lease.py:191` | a second alias on a model slot another stage holds (LAB-028 An endpoint is a model slot, not a service) | a run disturbed by the model being swapped out                                                        |
| `labkit/run/llm_cache.py:202`      | a cache opened without the lab's declaration (LAB-069 No LLM cache unless the lab declares one)         | repetitions that may be falsified by cached answers; what the site checks is the explicit declaration |

**Note conventions** — four sites, four conditions (LAB-082 In `notes/messung/`, every note carries its kind in the meta line); for conventions no number depends on, a warning is the fitting grade.

| Site                               | What it finds                                                                                               |
|------------------------------------|-------------------------------------------------------------------------------------------------------------|
| `labkit/checks/notes_check.py:135` | no italic meta line after the title                                                                         |
| `labkit/checks/notes_check.py:146` | a meta line naming no kind                                                                                  |
| `labkit/checks/notes_check.py:158` | an instrument declared implemented that names no script, function or path                                   |
| `labkit/checks/notes_check.py:216` | a note that cannot be read — a check not executed where access is refused, which stays recognisable as such |

## Per-blocker check 2026-11-09

Every blocking site read at its code, six groups by shared check logic; one row per site with finding, evidence kind, assurance, effect and recommendation: [blocker review](2026-11-09-blocker-review.tsv). Spot-checked here: the rename path (`labkit/formats/protocol_history.py:195`) and that `notes-check`'s exit stops nothing in the post-change hook (`labkit/gates/hook_post_change.py:342`). Of 177 sites: 163 keep, 5 warning, 1 remove, 8 decision open.

| Recommendation | Site                                       | Why                                                                                                                                                                                 |
|----------------|--------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| warning        | `labkit/checks/notes_check.py:135`, `:146` | a note convention no number depends on; the hook only reports it                                                                                                                    |
| warning        | `labkit/checks/notes_check.py:158`         | a name pattern over the note's text: an indication                                                                                                                                  |
| warning        | `labkit/checks/notes_check.py:216`         | a note that cannot be read, keeping the check-not-executable mark                                                                                                                   |
| warning        | `labkit/checks/prompt_check.py:69`         | a test file that does not parse hides only the parser check, a warning since 5d01d203                                                                                               |
| remove         | `labkit/formats/reference.py:197`          | the kept key missing or not finite is blocked already at `labkit/checks/run_record_check.py:949`: one cause, two blockers                                                           |
| decision open  | `labkit/checks/run_record_check.py:405`    | matching answer–gold pairs are certain; what change the registered null condition makes expect is the missing basis (a placebo prompt or a fixed null predictor can match honestly) |
| decision open  | `labkit/run/endpoint_lease.py:191`         | whether an endpoint is one model slot is a deployment fact no record states; declared per endpoint, the refusal would be exact                                                      |
| decision open  | `labkit/checks/run_record_check.py:528`    | a run that froze no source: whether a low-cost run reading no file (inputs made by code, model answers only) is legitimate, and how it says so                                      |
| decision open  | `labkit/checks/recheck.py:209`             | the recomputation requires shared descriptive values to be identical; LAB-041 Generate numbers, don't retype them says only that none may disappear                                 |
| decision open  | `labkit/checks/report_blocks.py:359`       | a run-id-shaped token no run carries, matched over prose: a fabricated citation to block, or a pattern to warn (italics `_<id>_` and `<id>-based` are matched)                      |
| decision open  | `labkit/gates/registered_report.py:201`    | a turn ends only on an adoption or a handover once a run exists; whether an honest progress account may end it while the next step is the author's                                  |
| decision open  | `labkit/gates/report_hold.py:934`          | a review model's claim blocks the report; whether a reasoned author decision may release it, as for audit findings                                                                  |
| decision open  | `labkit/gates/report_check.py:379`         | see below: a likely defect, not a grading question                                                                                                                                  |

Found beside the grading, to repair rather than to decide:

1. **A renamed protocol reads as never committed.** `committed_at` looks the protocol up at its present path in the first measurement's commit (`labkit/formats/protocol_history.py:195`); `docs/protocol-run-binding.md` allows renaming. After a rename the registration station says "nothing stood before the number" (`labkit/gates/report_check.py:379`), and `labkit/gates/registered_report.py:308`, `labkit/gates/registration_hold.py:375`, `labkit/gates/report_replacement.py:156` say "cannot be read" with a way out (`git fetch`) that does not help. Shown in the code path, not yet run.
2. **Outcome marks.** `labkit/gates/report_check.py:437` and `labkit/formats/evidence.py:375` mark a refused read or a failed git call as violated; `labkit/gates/preflight.py:586` reports an environment failure of the test run as failed.
3. **Messages that claim more than the condition shows:** `labkit/checks/run_record_check.py:284`, `:319`, `:708`, `labkit/gates/finalize.py:355`, `labkit/gates/report_check.py:472`, `labkit/checks/code_check.py:181`, `:256` (details in the review).
4. **A duty no rule text names:** the decision review a `fixed` or `false-positive` BLOCKER owes (`labkit/gates/report_decisions.py:188`, `:221`, `:290`) rests on a note, not on LAB-015 Preflight audit before freezing.
5. **No way out:** `labkit/gates/report_decisions.py:274` offers only the handover in an area with several protocols, and repeats `labkit/gates/report_check.py:457` once per earlier BLOCKER.

## Next

The assignment above goes through each site's rule, so "nearly every blocker protects the chain" is provisional. Next, every blocker is recorded with five entries — **finding** (what the check actually shows), **evidence kind** (an exact check, or an indication that may be wrong), **assurance** (the concrete duty it protects), **effect** (which action it stops, and why exactly this one), **recommendation** (keep, warning, remove, or *decision open* with the basis that is missing: a scientific requirement, a counter-example not yet at hand). Sites that share one condition have the condition judged once and their effect each. Only then are blockers regraded; the restructuring of the checks stays a separate decision. The distinguishable failure causes built today stand either way.
