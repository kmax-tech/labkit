# A measurement whose record is missing keeps counting

2026-11-18. Code: `area_state.measurements_without_record` (`WithoutRecord`), `start_check.earlier_measurement_note`, `start_check._committed_registration`, `registration_hold.lost_record_hold`, `registration_hold.lost_record_warnings`. Tests: `tests/test_rules_registration_hold.py` (`ARunWithoutItsRecord`), `tests/test_first_measurement_hint.py` (`AnEarlierRunWithoutItsRecord`), `tests/test_end_to_end.py` (`FirstMeasurementLost`).

## The gap

The run's start held a first measurement to HEAD and skipped the check once a first measurement existed whose record reads (`Measured.firsts`). `Measured.has_measured` also counts a run only the run index lists and a run whose record does not read. So after measurement A was deleted before any commit held it, the next measurement B was treated as the first one again and checked only against the commit of that day. `finalize` then compared B with itself and printed "what the number is about and the promise block are the ones the first measurement registered". Replayed with real commands on the counting skeleton: A measured, its directory deleted, the question rewritten and committed, B measured — `finalize` exited 0. Only the report duty held `report-check`, and only while the head registered no report; with a report registered the adoption of B exited 0.

## The decisions

Decided by the author on 2026-11-18:

> A demonstrably started measurement keeps counting even when its records are missing. Losing evidence does not turn a started investigation into an unmeasured state. This holds as far as labkit still has reliable evidence of the measurement, e.g. in the run index or in git; a run removed without any trace cannot be detected.
>
> - Confirmatory: the registration stays binding. If its version at that time can no longer be reconstructed, the check that depends on it must stop; HEAD does not replace it.
> - Exploratory: further development stays allowed; the lost measurement stays visible in the history; if a later result needs its missing evidence, that result's check stops; independent work is not forbidden wholesale.
>
> Align the run start — without deriving a new blanket block for every exploration.

Two refinements, decided by the author the same day on the first build, which held every protocol of the area for any run without a record:

1. No blanket hold. The registration station blocks only when what stood registered at the protocol's first measurement can no longer be reconstructed. Where a first measurement reads and only a later run's record is lost, the comparison runs against the readable one as before and the lost run is named in a warning. A later result that needs the lost run's own evidence is stopped by the check of that result.
2. A run whose record does not read holds only the protocol it is unambiguously assigned to. Where it cannot be assigned to exactly one protocol it holds none, and a warning names the run, says that its protocol cannot be determined, and names the way back.

## The evidence: the run index

A run without a record is a run only the local run index `runs.tsv` lists (its directory gone, no commit holding it: `AreaState.lost`) or a run whose `config.json` does not read. For both, the index row is the one evidence labkit has, and `measurements_without_record` reads two things from it (`AreaState.indexed`):

- **The protocol.** The row's `protocol_id` binds the run. A record that does not read counts for that protocol alone. One no row names — the run never finished, or the index is gone — is unassigned.
- **The order.** A run without a record may have been the first measurement unless a measurement of the same protocol whose record reads (no repeat, no probe; a run a commit holds back counts) stands before it in the index. The index is appended when a run ends, and runlog refuses a second measurement of the same script while one is open in the area, so index order is the order the measurements ran in.

Rejected as order: the run id (local time without a zone, `docs/notes/2026-10-27-first-measurement-order.md`) and the commit in the row's `git` column (a short hash of the commit the run ended at, which `repo.commit_known` does not accept as evidence).

## The cases

| Case                                                               | What labkit still holds                                   | Behaviour                                                                                                                                         |
|--------------------------------------------------------------------|-----------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| A committed, then its directory deleted                            | the record in git's history (`area_state.committed_runs`) | unchanged: A is a first measurement read from git; `finalize` compares B with A and holds a changed field, with the restore from A's commit       |
| A never committed, deleted; no measurement that reads before it    | its index row                                             | may have been the first: the start warns and starts; `finalize` holds every number of the protocol as a check not executable                      |
| a run deleted the same way, after a measurement that reads         | its index row, after the readable run's                   | named in a warning at the start and in `finalize`; the comparison with the first measurement runs                                                 |
| a `config.json` that does not read, the run listed in the index    | the directory and its index row                           | as a deleted run of the protocol the row names: held or warned of by its place in the index; no other protocol of the area is touched             |
| a `config.json` that does not read, the run not in the index       | the directory                                             | unassigned: held against no protocol; a warning (check not executable) at the start and in `finalize` of every protocol of the area names the run |
| A removed with its index row, or the index deleted, nothing in git | nothing                                                   | not detected: B is the first measurement                                                                                                          |

## What the run start does

`_committed_registration` holds a run to HEAD only while the protocol has no measurement: none whose record reads and no run without a record that the index binds to it. After such a run the next one is not a first measurement, and HEAD is not named as what binds. An unassigned record counts for no protocol, so a run beside it is held to HEAD as a first measurement would be. `earlier_measurement_note` prints one warning with a sentence per case above. It refuses nothing: whether a later result needs the missing record is decided where the result is released, not where a run starts.

## What the gate does

`registration_hold.registration_changes` (finalize's registration station, and through `finalize` also `report-check`, `labkit-next` and the adoption) returns one BLOCKER, `lost_record_hold`, before either comparison when a run may have been the first measurement. The comparison did not run, so the finding is a check not executable under the technical contract, and no later run or commit is compared in A's place. The ways out are the record back from a commit, a clone or a copy that holds it; where nothing holds it, a new registration (`commands.register_anew`) or the handover (`ways_out.handover`). `check_registration` adds the warnings of `lost_record_warnings` for the later and the unassigned runs; they hold nothing.

## A later result that needs the lost run's evidence

No new hold was built for this; the checks of the result itself stop it:

- The protocol adopted the lost run (`[result] run`): no run answers, a blocker (`answering_run._adopted_choice`, "there is no runs/<id>/ in this area"; `tests/test_report_check.py`, `tests/test_agent_hooks.py`).
- An analysis record names the lost run as the run it read: a blocker (`audit_binding.check_audited_runs_kept`; `tests/test_rules_audit_binding.py`).
- The output file holds rows the lost run wrote, or the answering run derives from or continues it: the row provenance station blocks (`run_record_check.row_provenance_findings`, a broken lineage included), and a file the lost run rewrote is not the file the answering run recorded (finalize's registered outputs). `FirstMeasurementLost.test_the_twin_a_later_run_lost_is_named_and_holds_nothing` replays this with real commands.
- A new run cannot derive from a run whose directory is gone (`start_check._derived_parent`).

## Left for the exploratory type

Every protocol is held as confirmatory today; the exploratory workflow is planned, not built ([plan](2026-11-14-exploratory-workflow-plan.md)). When it replaces the comparison with the first measurement by a declared basis per run, `lost_record_hold` applies to an exploratory protocol only where a result names the lost run in its basis or among its sources; a run that builds on another basis is not held. The start's warning needs no change for that: it already refuses nothing.

## Limits

- The run index is a local file git ignores. A clone, or a machine other than the one that measured, sees a run deleted before a commit as never measured, and a record that does not read as unassigned.
- Index order is the order runs ended in. Two scripts of one area may measure at the same time, and `runlog reindex` appends a row the index missed at the end; in both cases a run can stand after a measurement it preceded, and is then warned of where it would be held.
- The index lists finished runs of every kind. A lost probe counts like a lost measurement, as it does for `has_measured`.
- `Measured.has_measured` and the report duty (`registered_report.report_duty`) still count a record that does not read for every protocol of its area.
