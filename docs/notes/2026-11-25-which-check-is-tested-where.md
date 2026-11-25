# Which check is tested where — a measurement (2026-11-25)

**Answer.** Of the 264 places that build a gate finding, 37 are reached by a rule test (a test in `tests/test_rules_*.py`); 227 are not. Most of those 227 are tested all the same: 186 are reached by a fast test that calls a function below a whole command, 26 only by scenario files, 5 only through whole commands, and 10 by no test. One condition is often told at several places, each with a sentence of its own; the code holds at least 11 written exceptions that keep one cause from being told twice, 5 of them in `report_check.chain_gaps`.

**Status.** A measurement on commit `763c2e57`, ordered by the author on 2026-11-25. Nothing was built or changed. What to build follows the author's decision ([what the numbers say about the three proposals](#what-the-numbers-say-about-the-three-proposals)).

## Terms

- **Finding site:** a place in the source that builds a gate finding, ends a command with a message (`exit`), or prints a `WARNING:` or `BLOCKER:` line (`printed`); the unit `check_inventory` counts.
- **Rule test:** a test in one of the seven files `tests/test_rules_*.py`. They carry the mark `rule`: no process started, no console command entered.
- **Reached:** the test built a finding at the site during the traced run. Reaching a site is not asserting it.
- **Teller:** a place that turns the result of a condition into a message for the person: a finding site, a note of a hook, a step of `labkit-next`.

## How it was measured

1. `python -m labkit.tools.check_inventory` read the source and listed the sites, their rule assignments and the console commands that reach each site through a static call graph. Exit 0.
2. `python -m labkit.tools.test_inventory` ran the whole suite once with every gate finding traced, alone on the machine. Exit 0; 4628 passed, 2 skipped, 7861 subtests passed in 835 s.
3. The tool deletes its raw trace. Hard links kept the 36 trace files (14 882 findings built). Recounting them reproduces the tool's own table (249 direct, 5 only through commands, 10 unreached, 2576 findings built where no site stands), so the kept trace is complete.
4. Four scripts counted the trace and the source further: sites by the fastest kind of test that reaches them, sites by the gates that reach them, pairs of sites with alike wording, and a seeded sample of ten sites.
5. A phrase search over `labkit/` listed the written exceptions against telling one cause twice. The search was `one cause`, `second time`, `not told again`, `left out beside` and four more phrases; an exception worded otherwise is not in the list.

The complete outputs, the scripts and the trace are kept outside this repository, in the author's evidence repository under `2026-11-25-check-inventories/`.

## The sites

| Channel                        | Sites | Traced by the test inventory |
|--------------------------------|-------|------------------------------|
| gate finding                   | 264   | yes                          |
| `exit` (a message and an exit) | 86    | no                           |
| `printed`                      | 6     | no                           |
| all                            | 356   |                              |

The 264 gate-finding sites stand in `labkit/gates/` (135), `labkit/checks/` (114) and `labkit/formats/` (15). Of the 356 sites, 99 record a rule of the standard as data, 115 a technical contract, 17 an open assignment, 33 a rule the cause passes in, and 92 none (the `exit` and `printed` sites).

## Which test reaches a gate-finding site

Each site counts once, in the first row that applies.

| The closest test that reaches the site                      | Sites |
|-------------------------------------------------------------|-------|
| a rule test                                                 | 37    |
| a fast test that enters at a check or format function       | 90    |
| a fast test that enters at a gate function                  | 96    |
| only tests of scenario files (mark `slow`), below a command | 26    |
| only tests that run a whole command                         | 5     |
| no test                                                     | 10    |
| all                                                         | 264   |

A fast test is a test of a file without the mark `slow`. Of the 186 sites in rows two and three, 49 are reached by one of the seven station files (`tests/test_*_stations.py`).

The same count on 2026-11-10 ([test model](2026-11-10-test-model.md)): 194 sites, 19 of them reached only through whole commands and 30 by no test. Today: 264 sites, 5 and 10.

**Where the rule tests are.** The seven rule files hold 201 tests. Five of them reach 37 sites in six modules: `run_record_check` (14 of 51 sites), `report_decisions` (8 of 10), `registration_hold` (7 of 14), `audit_binding` (4 of 5), `area_state` (3 of 3), `report_exploration` (1 of 2). Two rule files reach no site (`test_rules_report_claims.py`, `test_rules_review_release.py`): the functions they call return data, and another function builds the finding. No rule test reaches a site of `finalize` (21 sites), `preflight` (20), `report_check` (24), `report_hold` (22), `report_replacement` (9), `registered_report` (7), `report_blocks` (10) or `code_check` (9).

**How many tests per site.** The median site is reached by 2 tests; 70 sites by exactly one; 5 sites by 50 or more. The most-reached site is the provenance warning at `labkit/checks/run_record_check.py:817`, with 160 tests, 149 of them through whole commands.

**The 10 sites no test reaches.**

| Site                                     | Function                  | Grade   |
|------------------------------------------|---------------------------|---------|
| `labkit/checks/intent_check.py:412`      | `origin_intent_findings`  | BLOCKER |
| `labkit/checks/notes_check.py:197`       | `check_file`              | WARNING |
| `labkit/checks/notes_check.py:227`       | `check_file`              | WARNING |
| `labkit/checks/readme_check.py:141`      | `readme_route`            | WARNING |
| `labkit/checks/run_record_check.py:337`  | `_reading_since_run`      | BLOCKER |
| `labkit/checks/run_record_check.py:348`  | `_reading_since_run`      | BLOCKER |
| `labkit/checks/run_record_check.py:1683` | `_metrics_model_findings` | WARNING |
| `labkit/gates/exploration_hold.py:292`   | `live_holds`              | BLOCKER |
| `labkit/gates/finalize.py:590`           | `check_answer_reading`    | BLOCKER |
| `labkit/gates/registration_hold.py:420`  | `types_split_hold`        | BLOCKER |

The 5 sites reached only through whole commands: `labkit/checks/code_check.py:758`, `labkit/checks/intent_check.py:338` and `:343`, `labkit/gates/exploration_hold.py:155` and `:189`. The 26 sites that only scenario files reach lie in `report_hold` (9), `report_check` (7), `registered_report` (4), `report_blocks` (3), `registration_hold` (2) and `notes_check` (1); the fast tier before a commit does not run them.

**The 92 `exit` and `printed` sites are not measured.** The trace follows gate findings only. Of these sites, 73 `exit` sites lie where no console command reaches them through the static call graph: in `labkit/checks/recheck.py` (27), `labkit/checks/prompt_check.py` (2) and `labkit/run/` (44). An area's scripts call them, at the run's start and at the recomputation. Which test holds each of them is open.

## Reached and asserted: a sample of ten

Ten reached sites were drawn with a fixed seed, and one reaching test per site was read. In all ten the test asserts the sentence of that site, and in six also its rule assignment or grade. Three of the ten tests are rule tests. Four call the site's function directly and are no rule tests: they stand in `tests/test_check_stations.py`, `tests/test_reference.py`, `tests/test_finalize.py` and `tests/test_finalize_provenance.py`, two of them with files in a temporary folder. Three run a gate or a check over a temporary area.

The sample is small. It shows that the count "no rule test" understates the tests at function level: the file name `test_rules_*` marks a part of them. It does not show how many of the 227 sites have a test that asserts them.

## One condition at several places

Three things look alike here and differ.

**One site, several gates.** By the static call graph, 254 of the 264 gate-finding sites are reached by two or more gate commands. The largest groups: 115 sites reached by `finalize`, `report-check` and the commit hook; 90 by `report-check` and the commit hook; 17 by `code-check`, `preflight` and the hook; 17 by `preflight` and the hook. This is one home, called from several gates: `report-check` runs `finalize` as its third station, and the commit hook runs the gates. Nothing is doubled.

**One condition, several tellers.** One function decides, and several places tell the result, each with its own sentence, grade, rule assignment and way out. Three examples read in the code:

- A field written twice (`protocol_check.repeated_findings`) has eight tellers: three gate findings (`labkit/gates/finalize.py:705`, `labkit/gates/preflight.py:371`, `labkit/gates/report_check.py:312`), `protocol-check` (`labkit/checks/protocol_report.py:791`), the run's start (`labkit/run/start_check.py:385`), the pre-run hook's note (`labkit/gates/hook_pre_run.py:180`), the next step (`labkit/gates/next_step.py:647`) and the audit's gap sentence (`labkit/formats/audit_gaps.py:308`). They share the way out as one constant; the sentence differs at each.
- The marks that make a run's number unreportable (`runs.unreportable`) are a warning of `finalize` (`labkit/gates/finalize.py:428`) and a blocker of `report-check` (`labkit/gates/report_check.py:577`); `labkit/gates/report_hold.py:943` reads them a third time.
- A declared scope that cannot be compared with the run's record (`promises.scope_drift`) is a blocker of `finalize` (`labkit/gates/finalize.py:653`) and an exit of the recomputation (`labkit/checks/recheck.py:403`).

A count by wording gives a lower bound. Among the 239 sites with 40 or more characters of constant text, 21 pairs in different functions are alike (similarity 0.7 or more); 8 of the pairs cross a module. One pair is word for word the same sentence: `labkit/gates/exploration_hold.py:292` and `labkit/gates/registration_hold.py:554`. The inventory truncates a site's wording at about 90 characters, and tellers with different sentences, like the eight above, are not among the pairs. No tool lists the tellers of a condition today.

**Written exceptions against telling one cause twice.** Where two stations of one gate would tell one cause, one of them is left out. The five in `report_check.chain_gaps` all concern `finalize` running as a station of `report-check`:

| Cause                                         | Who tells                                          | Who is left out                   | How                                                           |
|-----------------------------------------------|----------------------------------------------------|-----------------------------------|---------------------------------------------------------------|
| no answering run                              | `finalize`'s run choice                            | the chain's analysis station      | a condition at the call (`labkit/gates/report_check.py:1073`) |
| a field written twice                         | `finalize`'s open-fields station                   | the chain's registration station  | an argument at the call (`labkit/gates/report_check.py:1044`) |
| marks that make the run's number unreportable | the chain's full-run station, as a blocker         | `finalize`'s warning              | picked out by name (`without_unreportable_warnings`)          |
| a `[result]` table that does not read         | the chain's declaration station                    | `finalize`'s blocker              | picked out by name (`without_declaration_blocker`)            |
| a history git could not list                  | the chain's registration station (the report duty) | `finalize`'s registration station | picked out by name (`without_unread_history`)                 |

The first four hold only where `finalize` reads the same text as the chain, that is in every state but the proposal an adoption checks. Three of the five have a test of their own in `tests/test_report_check_stations.py`.

The phrase search found six more such exceptions outside `chain_gaps`:

| Cause                                                        | Who tells                         | Who is left out                                    | Where                                                              |
|--------------------------------------------------------------|-----------------------------------|----------------------------------------------------|--------------------------------------------------------------------|
| no answering run                                             | `finalize`'s run choice           | `finalize`'s intent-check station (a note)         | `labkit/gates/finalize.py:509`                                     |
| metrics that do not read, or no finite kept number           | `finalize`'s kept-number station  | `finalize`'s reference station (a note)            | `labkit/gates/finalize.py:1030`                                    |
| a promise block that does not read                           | `preflight`'s field report        | `preflight`'s code-check station                   | `labkit/gates/preflight.py:603`, `labkit/checks/code_check.py:258` |
| a promise block, scope or script a later station reads again | `preflight`'s code-check station  | the later station, while an earlier blocker stands | `labkit/gates/preflight.py:628`                                    |
| a script that does not read                                  | one finding of `code-check`       | the second check that reports it alike             | `labkit/checks/code_check.py:193`                                  |
| no covering analysis audit                                   | `report-check`'s analysis station | each follow-up hold whose only missing step it is  | `labkit/gates/report_decisions.py:161` and `:421`                  |

So the five in `chain_gaps` are fewer than half of the exceptions found. Each exception is one line of code and a paragraph of docstring at the place that leaves a finding out; no one place lists them.

## What was not measured

- The 92 `exit` and `printed` sites have no trace.
- A subprocess started with an environment of its own is not traced, and 2576 findings were built where no site stands. Nearly all of them are findings a gate rebuilds from another (`dataclasses.replace` at `labkit/gates/finalize.py:309` and `labkit/gates/report_check.py:867`); the site that built the original is counted.
- The commands per site come from a static call graph, an estimate in both directions. It misses a call through a table of functions: `labkit/tools/protocol_fill.py:854` shows no command, and `protocol-fill handover` reaches it.
- Whether a test asserts the site it reaches was read for ten sites only.
- The count of tellers per condition was not made; the three examples were found by reading.
- Why the whole suite takes 835 s (383 s on 2026-11-10) was not examined. This run collected no times per test. The next whole run can collect them with pytest's `--durations` at no extra cost.

## What the numbers say about the three proposals

The author decides on these; the note only orders what was measured.

1. **A generated overview per gate** (station, condition, rule, kind of check, the test file). The data for it exists in the two inventories, except the test file per site, which the test inventory computes and does not print, and the tellers of a condition, which nothing computes. The overview would answer the author's question for the 264 gate findings; the 92 other sites need a trace first.
2. **One table of duties as the only source.** The measurement supports the need at two points: one condition has up to eight tellers with sentences of their own, and at least 11 exceptions against double telling stand scattered in five modules. It does not show what such a table costs; `finalize`, `report_check`, `report_hold` and `preflight`, which hold 87 sites, have no rule test today, so a move would start without the test layer the test model asks for.
3. **Duties a team can switch off.** Nothing measured here bears on it.

Smaller steps the numbers point to, each on its own:

1. Give the 10 unreached sites a test, or remove the site where the code cannot reach it. Six are blockers.
2. Trace the `exit` channel in the test inventory, so that the 86 exit sites, which hold the run's start and the recomputation, are counted too.
3. Print the reaching test files per site in the test inventory. The trace holds them; this note needed a script of its own to read them.
4. Decide what "rule test" means for the count: the file name, the mark `rule`, or any test that calls the site's function directly. By file name it is 37 of 264; with the station files it is 86.
5. List the tellers of one condition, starting from the functions that several gate modules call.
