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

## Outside the chain — to decide

| Group                                          | Blocking sites                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | What they prevent                                                                 |
|------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| The instrument works                           | `labkit/checks/prompt_check.py:87` a parser without a test (LAB-016 Resolution check before freezing); `labkit/gates/preflight.py:418` no test file for the resolution check (LAB-016 Resolution check before freezing); `labkit/gates/preflight.py:586` the area's tests fail (CODE-003 Test the functions that produce numbers); `labkit/checks/run_record_check.py:405` the null lane answers what the registered lane answers on every item (LAB-034 Null condition in the same run); `labkit/formats/protocol_history.py:357` a judge's validation bound to no adopted protocol (LAB-052 Instance gate before registered use) | a number from an instrument shown not to measure, or not shown to measure         |
| The measurement is not distorted while it runs | `labkit/run/endpoint_lease.py:191` a second alias on one model slot (LAB-028 An endpoint is a model slot, not a service); `labkit/run/llm_cache.py:202` a cache the lab has not declared (LAB-069 No LLM cache unless the lab declares one)                                                                                                                                                                                                                                                                                                                                                                                        | empty answers from a model swapped out mid-run; a spread of 0 from cached answers |
| House rule                                     | `labkit/checks/notes_check.py:135`, `:146`, `:158`, `:216` a measurement note without its kind in the meta line (LAB-082 In `notes/messung/`, every note carries its kind in the meta line)                                                                                                                                                                                                                                                                                                                                                                                                                                        | a note that does not say what it is; no number depends on it                      |

## Next

Before the checks are restructured: decide the groups outside the chain, then ask of every blocker in the chain which concrete assurance it protects — a rule's name alone does not justify a blocker. The distinguishable failure causes built today stand either way.
