# A changed input under an adopted number: two gaps, closed

2026-11-27. A state model of one area's lifecycle (TLA+, checked by TLC; branch `statechart-pilot`, `docs/statechart/`) states one requirement at every repeat cost: an adopted number stays bound to the inputs it was measured on. TLC found two paths that break it. Both were replayed against the real commands before anything changed.

## What held before

| Gap                                  | Where                                                                                                                                                | Replay                                                                                                                                                             | Result before                                                                                  |
|--------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| The reach of the stop and the commit | `scope_sha.areas_touched` read the area's files, its promises' scope, bound validation and imported helpers, not the inputs its adopted run recorded | count walkthrough at `low` (`docs/examples/count-walkthrough.sh`): the last case dropped from `data/raw/cases.jsonl` at the lab root, that file committed alone    | pre-commit exit 0; `report-check AREA` afterwards exit 1 (provenance, `02_analyze.py --check`) |
| The comparison at high               | finalize's provenance station ran at `low` only ("the agent audit covers provenance there")                                                          | the `Estimator` scenario of `tests/test_end_to_end.py` at `high`: one gold label flipped in the write-protected `data/prepared/points_v1.jsonl` after the adoption | pre-commit and `report-check AREA` exit 0, "frozen, finalized, audited, checked", 0 blockers   |

The agent audit could not cover the second gap: it reads the data as they are when it runs, and a later change is not shown to it. The write protection on a prepared file guards against an accident, not against a deliberate edit.

## What holds now

The author decided on 2026-11-27:

1. A commit or a stop that changes a file an adopted run recorded as an input reaches that run's area. The rule is `scope_sha.adopted_inputs`, read by `reached_from_outside`. Every protocol of the area that adopted a run (`[result] run`) contributes the inputs of that run's `data=` record. A changed path counts when it is such an input or lies under a recorded directory. Data that several areas read reach every area whose adopted run recorded them. An adopted run whose record does not read reaches its area, because whether it read the path cannot be told.
2. finalize holds each input the run recorded to the bytes it recorded, at both repeat costs (`file_record_check.recorded_bytes_findings`). A gone input blocks as well. That every input is recorded in `data=`, and that git tracks it or an ignore rule keeps it out, stay owed at `low` only; the author left both out of this change.

The selection triggers the check; whether it blocks is decided by the chain as before. The replays are scenario tests now: `Count.test_06_an_input_outside_the_area_changed_under_the_number_reopens_it` (pre-commit 1, stop 2; restored, both pass) and `Estimator._a_changed_input_holds_the_adopted_number` (pre-commit 1, report-check 1; restored, pre-commit 0). With the code before this change, both fail.

## Limits and open questions

- Only recorded inputs are held. That a run recorded every file it read is not shown by any of this; at `high` it is not even asked.
- The byte blocker cites `LAB-017 The number of audits follows the cost tier`, a rule about the cost tier, at both repeat costs. Which rule a provenance finding should cite is open, together with the tension in `LAB-019 The stamp covers everything that determines the number`: its title claims everything, its list names code and the labkit pin, and the standard's table names "code and data". Not changed here (`TODO.md`, "Offene Entscheidungen" 10).
- The stop hook was replayed only in the low scenario; in the high one its fixture had no stop base.
