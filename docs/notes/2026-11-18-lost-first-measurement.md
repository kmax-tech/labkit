# A measurement whose record is missing keeps counting

2026-11-18. Code: `area_state.measurements_without_record`, `start_check.earlier_measurement_note`, `start_check._committed_registration`, `registration_hold.lost_record_hold`. Tests: `tests/test_rules_registration_hold.py` (`AMeasurementWithoutItsRecordLeavesTheRegistrationUntold`), `tests/test_first_measurement_hint.py` (`AnEarlierMeasurementWithoutItsRecord`), `tests/test_end_to_end.py` (`FirstMeasurementLost`).

## The gap

The run's start held a first measurement to HEAD and skipped the check once a first measurement existed whose record reads (`Measured.firsts`). `Measured.has_measured` also counts a run only the run index lists and a run whose record does not read. So after measurement A was deleted before any commit held it, the next measurement B was treated as the first one again and checked only against the commit of that day. `finalize` then compared B with itself and printed "what the number is about and the promise block are the ones the first measurement registered". Replayed with real commands on the counting skeleton: A measured, its directory deleted, the question rewritten and committed, B measured — `finalize` exited 0. Only the report duty held `report-check`, and only while the head registered no report; with a report registered nothing held the rewritten question.

## The decision

Decided by the author on 2026-11-18:

> A demonstrably started measurement keeps counting even when its records are missing. Losing evidence does not turn a started investigation into an unmeasured state. This holds as far as labkit still has reliable evidence of the measurement, e.g. in the run index or in git; a run removed without any trace cannot be detected.
>
> - Confirmatory: the registration stays binding. If its version at that time can no longer be reconstructed, the check that depends on it must stop; HEAD does not replace it.
> - Exploratory: further development stays allowed; the lost measurement stays visible in the history; if a later result needs its missing evidence, that result's check stops; independent work is not forbidden wholesale.
>
> Align the run start — without deriving a new blanket block for every exploration.

## Three cases

| Case                                                               | What labkit still holds                                    | What it reads                                                                                                  | Behaviour                                                                                                                   |
|--------------------------------------------------------------------|------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| A committed, then its directory deleted                            | the record in git's history (`area_state.committed_runs`)  | A's record and the protocol at A's commit: A is a first measurement as before                                  | unchanged: the start says nothing, `finalize` compares B with A and holds a changed field, with the restore from A's commit |
| A never committed, its directory deleted                           | a row of the local run index `runs.tsv` (`AreaState.lost`) | that A finished and which protocol it was bound to; not the commit it started at, not the protocol text it saw | the start warns and starts; `finalize` holds every number of the protocol as a check not executable                         |
| A's `config.json` does not read                                    | the directory, and whatever of it git holds                | that a run was there; not its kind, its binding or its commit                                                  | as the row above; the record counts for every protocol of its area, since its binding is unknown                            |
| A removed with its index row, or the index deleted, nothing in git | nothing                                                    | nothing                                                                                                        | not detected: B is the first measurement                                                                                    |

The run index lists completed runs only, so a measurement that stopped without a number and was deleted before a commit leaves no row and belongs to the last line.

## What the run start does

`_committed_registration` holds a run to HEAD only while the area has not measured the protocol (`has_measured`). After a measurement without a record the next run is not a first measurement, and HEAD is not named as what binds. `earlier_measurement_note` prints a warning that names the earlier measurement, says that its registration cannot be read from here, and says that `finalize` and `report-check` will hold the number. It refuses nothing: whether a later result needs the missing record is decided where the result is released, not where a run starts.

## What the gate does

`registration_hold.registration_changes` (finalize's registration station, and through `finalize` also `report-check`, `labkit-next` and the adoption) returns one BLOCKER, `lost_record_hold`, before either comparison. The comparison did not run, so the finding is a check not executable under the technical contract, and no later run or commit is compared in A's place. It holds beside a first measurement that reads, too: the lost or unreadable one may have preceded it, and no record orders the two. The ways out are the record back from a commit, a clone or a copy that holds it; where nothing holds it, a new registration (`commands.register_anew`) or the handover (`ways_out.handover`). The report duty reads the same two states the same way (`registered_report.report_duty`).

## Left for the exploratory type

Every protocol is held as confirmatory today; the exploratory workflow is planned, not built ([plan](2026-11-14-exploratory-workflow-plan.md)). When it replaces the comparison with the first measurement by a declared basis per run, `lost_record_hold` applies to an exploratory protocol only where a result names the lost run in its basis or among its sources; a run that builds on another basis is not held. The start's warning needs no change for that: it already refuses nothing.

## Limits

- The run index is a local file git ignores. A clone, or a machine other than the one that measured, sees a run deleted before a commit as never measured.
- The index row of a lost run names the commit the run ended at (`git` column). This is not used to place the run in history or to read the protocol it saw.
- A record that does not read holds every protocol of its area, a newly registered one included. A new registration in an area of its own (`labkit-init exp`) is not affected.
