# The start record: which run started with which protocol and when

2026-11-18. The record of a built design, decided by the author on 2026-11-18 after a draft compared two places for it. Code: `labkit/formats/run_starts.py` (the file's one home), `runlog.Run._write_start_record`, `area_state.assigned_to`, `area_state.binding_conflicts`, `area_state.measurements_without_record`, `registration_hold.binding_conflict_hold`. Tests: `tests/test_run_starts.py`, `tests/test_area_state.py` (`AStateBuiltWithoutFiles`), `tests/test_rules_registration_hold.py` (`ARunWithoutItsRecord`, `ABindingTheFilesContradict`), `tests/test_end_to_end.py` (`FirstMeasurementLost`). What the gates do with it: [a measurement whose record is missing keeps counting](2026-11-18-lost-first-measurement.md).

## Why

Before this file, everything that bound a run to its protocol at its start lay inside the run's own directory (`config.json`, written by `runlog.Run._write_record`). The run index got its row only at a clean end. A measurement that broke off and whose directory was deleted or damaged left nothing that said which protocol it had measured, and no record of a lost run carried a start time with a zone. The order of a lost run and a readable one was therefore read from the local start times in the run ids, under a rule that took two runs as ordered only when the ids lay more than 26 hours apart. The author called that rule what it was, a conservative auxiliary rule and no evidence, and ordered the start record built and the rule removed.

## Two files, two questions

| File                           | Question                                               | Written                                       | Rebuilt                                |
|--------------------------------|--------------------------------------------------------|-----------------------------------------------|----------------------------------------|
| `run-starts.tsv`, start record | which measurement started with which protocol and when | at the start, before the measurement executes | never: only a start writes a row       |
| `runs.tsv`, run index          | which runs reached completion                          | at a clean end, as before                     | `runlog reindex`, from the run records |

The start record has three columns: `run_id`, `protocol_id` ("" for a run that started unbound) and `started_utc` (`2026-11-18T12:03:15+00:00`, the starting machine's clock in UTC, to the second). The two files are linked by the run id. Completion state and results are never kept in the start record. The run index keeps its format, its meaning and the Public API contract of `runlog.run` (`docs/architecture.md`, "Public API"): a clean exit writes the `runs.tsv` row, an exception is re-raised with no index row.

## What the contract asks, and how it is met

1. **Durable before the measurement executes; a failed write refuses the start.** `runlog.Run.__init__` writes the row as the last step of the start, after every refusal and after `config.json`, and before the `with` block of the measure script runs (`_write_start_record`). `run_starts.write_start` appends the row, flushes and syncs the file, and syncs the directory for a new file. When the row cannot be written or synced the start ends with a `SystemExit` naming the file, and the run directory is removed. A start labkit refuses for another reason — the registration, a reseed's conditions, the detach gate, the freeze gate, the run index's own check, an open twin, the repeat's draw — never reaches the write and leaves no row. So a row names a run whose record was written.
2. **Concurrent starts lose no row.** The write runs under the run index's lock (`run_index.index_lock`, an exclusive `flock` on `.runs.tsv.lock` in the area): one lock for both files, one home. A measurement's start now always takes it; before, only a repeat's start did. Readers take the shared lock (`run_starts.read_starts`).
3. **`runlog reindex` keeps it and invents nothing.** `reindex` does not open the start record. A row stays when the run's directory is gone, and a run from before the start record gets no row made up from its id or its `config.json`: only a start writes a row.
4. **Contradicting bindings are their own finding.** A run's own record where it reads, its start row and its index row may name different protocols. `area_state.binding_conflicts` lists every such run; none of the files is taken over another. For each protocol among the ids named, finalize's registration station returns one BLOCKER of a check not executable (`registration_hold.binding_conflict_hold`), before any comparison, and the run's start names the contradiction in its warning. The grade follows the rule that a check that could not run blocks the gated step: which runs the protocol measured cannot be told, so neither can what it registered at its first measurement, and a warning would release a number on a binding nobody can name. A record that does not read and whose two files disagree is assigned to neither protocol.
5. **The 26-hour rule is gone.** `area_state.ZONE_SPREAD` and its wording are removed. The order of two runs is told only where the start record holds a UTC start for both; otherwise it is unknown, said as such with the run whose start is missing, and held as before.

## Assignment first, order second

A file assigns, a time never does. A record that does not read belongs to the protocol its start row or its index row names (`area_state.assigned_to`); a run with neither is unassigned, whatever the number of protocols in the area. Only for a run assigned to a protocol does a time then say whether it may have been that protocol's first measurement. Closeness in time assigns nothing.

A start row makes a broken-off measurement with a missing or damaged record an assigned one: `AreaState.started_only` holds the runs only the start record names (no directory in the working tree, no commit, no index row), and they count as measurements of their protocol (`Measured.has_measured`, the report duty, the registration station).

## What a UTC start does and does not give

It removes the zone from the question: two starts in the start record compare without any margin. It does not make the order certain. The time is the starting machine's clock, and a clock set wrong gives a wrong order on one machine and across machines alike. Correct machine clocks stay an assumption; every message that takes a run as the later one states it (`area_state.CLOCKS_ASSUMED`), and labkit does not check it. Two starts in the same second are not ordered.

## Local, like the index

The start record is a local file beside `runs.tsv`, and the lab stamp ignores it (`scaffold.GITIGNORE`). Tracked, it would change at every start, so every run after the first would begin in a tree that differs from HEAD, and two branches that both measured would conflict in it. The cost: a fresh clone, and a machine other than the one that started the runs, has no start record. There a run deleted before a commit is not seen at all, a record that does not read is unassigned unless the clone's own index lists it, and no order is told — unknown, never guessed.

Only measurements get a row (`run_kind = "measurement"`, repeats included). The three columns carry no run kind, so a row for a probe or a preparation run would count as a started measurement once its directory was gone.

## Rejected: a start row in `runs.tsv`, completed at the end

One file was the alternative: the index row written at the start and completed at the end. It was rejected for what it changes:

- The Public API contract of `runlog.run` says an exception is re-raised "with no index row". A start row breaks that sentence for every caller.
- `runs.tsv` means "the runs that reached completion" to every reader: `run_index.indexed_runs` and `indexed_bindings`, `AreaState.lost` ("measured to the end, as the index says"), `runlog.unindexed` and `reindex`, the stop's evidence line (`hook_post_change.index_problems`), the handover's run account (`report_check`), the report duty. Each would have to tell a started row from a completed one.
- A row is completed by rewriting the file. Today every writer only appends, and a killed process leaves whole rows.
- `runlog reindex` rebuilds rows from run directories. It would have to keep start rows it cannot rebuild and tell them from rows it may write, in one file.
- The index's columns would change: an announced break of the format with a migration, where the start record adds a file and breaks none.

## What changes for a lab

- A lab stamped before this release has no `run-starts.tsv` line in its `.gitignore`. Until the line is added, the file is untracked and every measurement after the first starts in a tree git reports as changed (`+dirty` in the run's `git` field, an `uncommitted.patch` only where tracked files differ).
- Runs from before the start record have no start. Beside a readable measurement their order is unknown and the hold stands; the ways out are the ones of the hold.
- Whether the removed 26-hour rule ever applied in practice was not shown: it is not known that runs of one area start on machines in different zones. `config.json` names no host (`runlog.Run._write_record`: `pid`, `python`, `env`, `command`, no machine), so a lab could only have checked this by knowing which machines start its runs.

## Not built

- The start record names no machine. A host column would let a reader see that two starts came from one clock; it would still not show that the clock was right, and across hosts it would order nothing.
- `hook_post_change.index_problems` lists the runs a commit or the index holds whose directory is gone. It does not list the runs only the start record names; its cheap pre-check (`area_state.index_names_gone_runs`) reads the index alone.
- No command repairs or edits the start record. A row that is wrong is corrected by hand, and a row is never deleted.
