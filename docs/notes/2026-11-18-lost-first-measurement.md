# A measurement whose record is missing keeps counting

2026-11-18. Code: `area_state.measurements_without_record` (`WithoutRecord`), `area_state.assigned_to`, `start_check.earlier_measurement_note`, `start_check._committed_registration`, `registration_hold.lost_record_hold`, `registration_hold.lost_record_warnings`. Tests: `tests/test_rules_registration_hold.py` (`ARunWithoutItsRecord`), `tests/test_area_state.py` (`AStateBuiltWithoutFiles`), `tests/test_first_measurement_hint.py` (`AnEarlierRunWithoutItsRecord`), `tests/test_end_to_end.py` (`FirstMeasurementLost`).

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

Refinements, decided by the author the same day in four rounds on what was built:

1. No blanket hold. The registration station blocks only when what stood registered at the protocol's first measurement can no longer be reconstructed. Where a first measurement reads and only a later run's record is lost, the comparison runs against the readable one as before and the lost run is named in a warning. A later result that needs the lost run's own evidence is stopped by the check of that result.
2. A run whose record does not read holds only the protocol it is unambiguously assigned to. Where it cannot be assigned to exactly one protocol it holds none, and a warning names the run, says that its protocol cannot be determined, and names the way back.
3. The order must be evidenced. The position of a row in the run index does not make a run "later": `runlog reindex` and a parallel start change it. Where the order is unclear the run may have been the first, the hold stands, and the message says that the order cannot be told.
4. The 26-hour rule below is a conservative auxiliary rule, not evidence. It covers time zones, not a wrongly set machine clock, and its assumption is stated wherever it is applied. It is not to be extended.
5. One assignment for every check. `Measured.has_measured` and the report duty count a record that does not read only for the protocol the index binds it to.
6. No assignment from the number of protocols. Without evidence of the binding a record's protocol stays unknown, in an area of one protocol too. From such a record labkit derives neither an earlier measurement nor a first registration that is established.

## What labkit reads

A run without a record is a run only the local run index `runs.tsv` lists (it finished; `AreaState.lost`), a run only its start file `run-starts/<run_id>.json` names (it started, and broke off or was deleted before it finished; `AreaState.started_only`, of which the measurements count: `Measured.started_only`), or a run whose `config.json` does not read. The start file is described in [its own note](2026-11-18-run-start-record.md). Assignment comes first, order second.

**Which protocol.** The `protocol_id` its start file or its row in the run index names, and nothing else (`area_state.assigned_to`, read once when the area state is assembled). A record that does not read is among the runs of that protocol alone (`Measured.runs`); a row that names no protocol assigns it to none. A record neither names is unassigned (`Measured.unassigned`): it is among no protocol's runs, `has_measured` and the report duty do not count it, and the run's start, `finalize` and report-check's report duty name it with what it leaves open (`area_state.unassigned_record_warning`). Where the two, or one of them and a record that reads, name different protocols, that is a finding of its own and no file wins (`area_state.binding_conflicts`). A time never assigns, and neither does the number of protocols in the area.

**Which started first.** Told only where a start file holds a UTC start for both runs (`Measured.started`), against the measurements of the protocol whose record reads (no repeat, no probe; a run a commit holds back counts). After one of them, the run is taken as later. Before every one of them, or with none that reads, it may have been the first. With a start missing for the run or for one of them — every run from before start files — or two starts in one second, the order is unknown: held like the first, and the clause names the run whose start is missing. Nothing is guessed.

A UTC start removes the time zone from the question, not the clock. That the clocks of the machines that started the runs were right is assumed; labkit does not check it, and the warning that takes a run as the later one says so (`area_state.CLOCKS_ASSUMED`).

Rejected for the order:

- The position of the row in the index. It is the order runs ended in, `runlog reindex` appends a missed row at the end, and two scripts of one area may measure at the same time.
- The commit in the index row's `git` column. It is the commit the run ended at, in short form; a run that started before another and ended after it names the later commit.
- The local start time in the run id (`docs/notes/2026-10-27-first-measurement-order.md`). An intermediate build took two ids as ordered when they lay more than 26 hours apart, the range of the time zones; the author named it a conservative auxiliary rule and no evidence — it covered zones, not a clock set wrong — and had it removed once start files existed.

## The cases

| Case                                                                                                                                      | What labkit still holds                                   | Behaviour                                                                                                                                                                                                                                                                                                |
|-------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| A committed, then its directory deleted                                                                                                   | the record in git's history (`area_state.committed_runs`) | unchanged: A is a first measurement read from git; `finalize` compares B with A and holds a changed field, with the restore from A's commit                                                                                                                                                              |
| a run deleted before a commit, or broken off and deleted; no measurement that reads, or the start files put it before every one that does | its index row or its start file                           | may have been the first: the start warns and starts; `finalize` holds every number of the protocol as a check not executable                                                                                                                                                                             |
| the same, no start file holding a start for it or for a measurement that reads, or the same second for both                               | its index row or its start file                           | order unknown: held as the row above, the message naming the run whose start is missing                                                                                                                                                                                                                  |
| the same, the start files putting it after a measurement that reads                                                                       | its start file and its index row                          | taken as later under the stated assumption: named in a warning at the start and in `finalize`; the comparison with the first measurement runs                                                                                                                                                            |
| a `config.json` that does not read, the run named by a start file or the index                                                            | the directory, its start file or its index row            | as a deleted run of the protocol the row names, by the same rule for the order; no other protocol of the area is touched                                                                                                                                                                                 |
| a run whose record, start file and index row name different protocols                                                                     | files that disagree                                       | each protocol named is held by a blocker of its own; no file wins                                                                                                                                                                                                                                        |
| a `config.json` that does not read, the run in neither file                                                                               | the directory                                             | unassigned: held against no protocol, counted for none; a warning (check not executable) at the start, in `finalize` and at report-check's report duty names the run, and the note of a registration that compared clean says "the first measurement that reads" and that an earlier one is not excluded |
| A removed with its start file and its index row, nothing in git                                                                           | nothing                                                   | not detected: B is the first measurement                                                                                                                                                                                                                                                                 |

## What the run start does

`_committed_registration` holds a run to HEAD only while the protocol has no measurement: none whose record reads and no run without a record that its start file or the index binds to it. After such a run the next one is not held to HEAD as a first measurement, and HEAD is not named as what binds. `earlier_measurement_note` prints one warning with a sentence per case above. It refuses nothing: whether a later result needs the missing record is decided where the result is released, not where a run starts.

Two paths remain on which a run is checked against today's HEAD although an earlier measurement may have existed. Beside an unassigned record the protocol has no measurement labkit can show, so the run is held to HEAD as a first measurement would be; the warning names the record and says that it shows neither an earlier measurement nor that none came before. After a run removed together with its start file and its index row nothing is left to see.

## What the gate does

`registration_hold.registration_changes` (finalize's registration station, and through `finalize` also `report-check`, `labkit-next` and the adoption) returns one BLOCKER before either comparison: `binding_conflict_hold` when the files contradict each other on a run's protocol, else `lost_record_hold` when a run may have been the first measurement or its order is unknown. The comparison did not run, so the finding is a check not executable under the technical contract, and no later run or commit is compared in its place. The ways out are the record back from a commit, a clone or a copy that holds it; where nothing holds it, a new registration (`commands.register_anew`) or the handover (`ways_out.handover`). `check_registration` adds the warnings of `lost_record_warnings` for the later and the unassigned runs; they hold nothing.

## A later result that needs the lost run's evidence

No new hold was built for this; the checks of the result itself stop it:

- The protocol adopted the lost run (`[result] run`): no run answers, a blocker (`answering_run._adopted_choice`, "there is no runs/<id>/ in this area"; `tests/test_report_check.py`, `tests/test_agent_hooks.py`).
- An analysis record names the lost run as the run it read: a blocker (`audit_binding.check_audited_runs_kept`; `tests/test_rules_audit_binding.py`).
- The output file holds rows the lost run wrote, or the answering run derives from or continues it: the row provenance station blocks (`run_record_check.row_provenance_findings`, a broken lineage included), and a file the lost run rewrote is not the file the answering run recorded (finalize's registered outputs). `FirstMeasurementLost.test_the_twin_a_later_run_lost_is_named_and_holds_nothing` replays this with real commands.
- A new run cannot derive from a run whose directory is gone (`start_check._derived_parent`).

## Left for the exploratory type

Every protocol is held as confirmatory today; the exploratory workflow is planned, not built ([plan](2026-11-14-exploratory-workflow-plan.md)). When it replaces the comparison with the first measurement by a declared basis per run, `lost_record_hold` applies to an exploratory protocol only where a result names the lost run in its basis or among its sources; a run that builds on another basis is not held. The start's warning needs no change for that: it already refuses nothing.

## Limits

- The run index is a local file git ignores, and a start file travels only from the commit that first holds it. A clone, or a machine other than the one that measured, sees a run deleted before a commit as never measured, and a record that does not read as unassigned, unless a committed start file names it.
- A start file that does not read gives no start either: its run's order is unknown, as for a run from before start files ([its note](2026-11-18-run-start-record.md)).
- A run from before start files has no start. Deleted beside a measurement that reads, it holds the protocol although it may have run after it; the hold's ways out apply.
- The run index lists finished runs of every kind and has no column for the kind. A lost run without a start file counts like a lost measurement, as it does for `has_measured`. A start file names its run's kind: a run it lists as a probe or a preparation counts as a measurement for no check, whatever became of its record (`Measured.may_have_measured`).
- The audit stamp's basis (`scope_sha._run_records`) still takes every record that does not read into every protocol's digest: it answers which files an audit covered, not which protocol a run belongs to.
