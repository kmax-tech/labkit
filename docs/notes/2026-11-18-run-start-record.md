# The start record: which run started with which protocol and when

2026-11-18. The record of a built design, decided by the author on 2026-11-18 after a draft compared two places for it. Code: `labkit/formats/run_starts.py` (the file's one home), `runlog.Run._write_start_record`, `area_state.assigned_to`, `area_state.binding_conflicts`, `area_state.measurements_without_record`, `registration_hold.binding_conflict_hold`. Tests: `tests/test_run_starts.py`, `tests/test_area_state.py` (`AStateBuiltWithoutFiles`), `tests/test_rules_registration_hold.py` (`ARunWithoutItsRecord`, `ABindingTheFilesContradict`), `tests/test_end_to_end.py` (`FirstMeasurementLost`, `ParallelStarts`). What the gates do with it: [a measurement whose record is missing keeps counting](2026-11-18-lost-first-measurement.md).

## Why

Before this file, everything that bound a run to its protocol at its start lay inside the run's own directory (`config.json`, written by `runlog.Run._write_record`). The run index got its row only at a clean end. A measurement that broke off and whose directory was deleted or damaged left nothing that said which protocol it had measured, and no record of a lost run carried a start time with a zone. The order of a lost run and a readable one was therefore read from the local start times in the run ids, under a rule that took two runs as ordered only when the ids lay more than 26 hours apart. The author called that rule what it was, a conservative auxiliary rule and no evidence, and ordered the start record built and the rule removed.

## Two files, two questions

| File                           | Question                                                | Written                                       | Rebuilt                                |
|--------------------------------|---------------------------------------------------------|-----------------------------------------------|----------------------------------------|
| `run-starts.tsv`, start record | which run started with which protocol, when and as what | at the start, before the run's block executes | never: only a start writes a row       |
| `runs.tsv`, run index          | which runs reached completion                           | at a clean end, as before                     | `runlog reindex`, from the run records |

The start record has four columns: `run_id`, `protocol_id` ("" for a run that started unbound), `started_utc` (`2026-11-18T12:03:15+00:00`, the starting machine's clock in UTC, to the second) and `run_kind` (`measurement`, `probe` or `preparation`). The two files are linked by the run id. Completion state and results are never kept in the start record. The run index keeps its format, its meaning and the Public API contract of `runlog.run` (`docs/architecture.md`, "Public API"): a clean exit writes the `runs.tsv` row, an exception is re-raised with no index row.

## What the contract asks, and how it is met

1. **Durable before the measurement executes; a failed write refuses the start.** `runlog.Run.__init__` writes the row as the last step of the start, after every refusal and after `config.json`, and before the `with` block of the measure script runs (`_write_start_record`). `run_starts.write_start` appends the row, flushes and syncs the file, and syncs the directory for a new file. When the row cannot be written or synced the start ends with a `SystemExit` naming the file, and the run directory is removed. A start labkit refuses for another reason — the registration, a reseed's conditions, the detach gate, the freeze gate, the run index's own check, an open twin, the repeat's draw — never reaches the write and leaves no row. So a row names a run whose record was written.
2. **Concurrent starts lose no row.** The write runs under the run index's lock (`run_index.index_lock`, an exclusive `flock` on `.runs.tsv.lock` in the area): one lock for both files, one home. Every start now takes it; before, only a repeat's start did. Readers take the shared lock (`run_starts.read_starts`).
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

## Every run kind, and what each reader asks

Every run gets a row, whatever its kind: a probe can produce numbers, and a run must not be missing from the record for its name. So a row says "a run started", never "a measurement started", and each reader asks for the kind it means:

| Reader                                                             | What it takes from the start record                                                                                                                     |
|--------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| assignment (`area_state.assigned_to`)                              | the protocol id of a row of any kind                                                                                                                    |
| order (`Measured.started`)                                         | the UTC start of a row of any kind; the comparison is with the measurements whose record reads (no repeat, no probe), whose kind their own record names |
| runs only the start record names (`AreaState.started_only`)        | every kind; `Measured.started_only` is the rows with `run_kind = "measurement"`                                                                         |
| lost runs (`AreaState.lost`, the index only)                       | every kind; `Measured.lost` leaves out a run its start row lists as a probe or a preparation                                                            |
| a record that does not read (`Measured.may_have_measured`)         | its start row's kind; without a row it may have measured                                                                                                |
| `Measured.has_measured`, the report duty, the registration station | only runs that may have measured, by the three rows above                                                                                               |
| the post-change hook (`hook_post_change.index_problems`)           | every kind, named in the line                                                                                                                           |

A run from before the start record has no row: its kind is unknown where its record is gone, it counts as it did, its order is unknown and the hold stands. No exception is made for it.

## What the post-change hook tells

`hook_post_change.index_problems` keeps an abort and a missing record apart. A run the start record lists whose directory stands without a completion "started as a <kind> and never completed": its record is here (`unfinished_starts`; a run whose process still lives is left out, and where that cannot be told the line says so). A run whose directory is gone "is gone", named by the start record ("lists it as a <kind> that started, runs.tsv lists no completion") or by the index ("lists it as measured"). The cheap pre-check that decides which areas get a state built reads both files (`area_state.index_names_gone_runs`, `starts_name_open_runs`).

## Parallel starts

`ParallelStarts` (`tests/test_end_to_end.py`, slow) starts 8 processes of their own that wait for one signal and then each start and finish 5 runs in one area, in 3 rounds on a fresh area: 120 starts. In every round the start record read whole, held exactly one row per start, and the run index held the same 40 runs. The threads test in `tests/test_run_starts.py` shows the same for 12 writers on separate handles in one process.

## Rejected: a start row in `runs.tsv`, completed at the end

One file was the alternative: the index row written at the start and completed at the end. It was rejected for what it changes:

- The Public API contract of `runlog.run` says an exception is re-raised "with no index row". A start row breaks that sentence for every caller.
- `runs.tsv` means "the runs that reached completion" to every reader: `run_index.indexed_runs` and `indexed_bindings`, `AreaState.lost` ("measured to the end, as the index says"), `runlog.unindexed` and `reindex`, the stop's evidence line (`hook_post_change.index_problems`), the handover's run account (`report_check`), the report duty. Each would have to tell a started row from a completed one.
- A row is completed by rewriting the file. Today every writer only appends, and a killed process leaves whole rows.
- `runlog reindex` rebuilds rows from run directories. It would have to keep start rows it cannot rebuild and tell them from rows it may write, in one file.
- The index's columns would change: an announced break of the format with a migration, where the start record adds a file and breaks none.

## What changes for a lab

- A lab stamped before this release has no `run-starts.tsv` line in its `.gitignore`. Until the line is added, the file is untracked and every run after the first starts in a tree git reports as changed (`+dirty` in the run's `git` field, `provenance.git_state`).
- Runs from before the start record have no start and no kind there. Beside a readable measurement their order is unknown and the hold stands; the ways out are the ones of the hold.
- Whether the removed 26-hour rule ever applied in practice was not shown: it is not known that runs of one area start on machines in different zones. `config.json` names no host (`runlog.Run._write_record`: `pid`, `python`, `env`, `command`, no machine), so a lab could only have checked this by knowing which machines start its runs.

## Not built

- The start record names no machine (decided: no use was named, and a host guarantees no clock).
- No command repairs or edits the start record. A row that is wrong is corrected by hand, and a row is never deleted.

## Open: keeping the start information beyond this machine

Awaiting the author's decision. The author does not accept a local, ignored file as the complete answer: it protects against a damaged run directory on this machine and carries nothing into a clone, and ignoring a file must not serve merely to quiet the dirty detection.

**What a fresh clone knows about a run that started.** The lab stamp ignores three names and nothing under `runs/` (`scaffold.GITIGNORE`, `labkit/tools/scaffold.py:128`): the lock, `runs.tsv` and `run-starts.tsv`. So the run directory with `config.json`, `completion.json`, `metrics.json` and `failure.json` is tracked once someone commits it, and a clone has it from that commit on. For a run whose directory was deleted after a commit, git's history gives the record back (`area_state.committed_runs`, `labkit/formats/area_state.py`, read from the last commit that held `runs/<id>/config.json`), on every clone that holds that commit. For a run never committed, a clone has nothing: neither local file travels.

**Where the start information is lost for good.**

1. A run that was never committed and whose directory is deleted, seen from any other clone or machine. The local files are the only trace, and they are not there.
2. The same run on the starting machine after the local files are removed: `git clean -x` or `-X` deletes ignored files, a fresh checkout of the working tree has none, and nothing rebuilds the start record.
3. A run that broke off, in every clone, unless its directory was committed in that state. Its `config.json` holds the binding; the run index never listed it.
4. The UTC start of any run, in every clone: `config.json` carries a local `started` without a zone, and only the start record has the UTC time.

**The common limit.** Nothing carries an uncommitted start into a clone. A file travels from the commit that first holds it, and labkit never commits. What the options below change is whether the start information is in the repository once the lab commits, and what that costs.

**Options.**

1. **Track `run-starts.tsv`.** The row of a run reaches a clone with the next commit. It breaks three things. Every start changes a tracked file, so every later run starts in a changed tree until someone commits: `provenance.git_state` (`labkit/run/provenance.py:69`) marks it `+dirty`, `runlog` writes an `uncommitted.patch` of the row (`labkit/run/runlog.py`, `_write_record`), and preflight warns of uncommitted changes (`preflight.check_working_tree`, `labkit/gates/preflight.py:599`). Two branches that both ran conflict at the end of the file on every merge; a `merge=union` attribute resolves that and needs a stamped `.gitattributes`, and a cherry-picked or rebased row can then stand twice, which `run_starts` refuses. And a run records the commit it started at before its row exists (`provenance.record_provenance` runs first), so no run's row is ever in the commit that run names.
2. **One tracked file per start**, beside the run directory and outside it (for example `runs/<run_id>.start`). No merge conflict, since two branches never write the same file, and no rewriting. The tree still changes at every start: an untracked file counts as dirty at the next start (`repo.tree_dirty`, `labkit/formats/repo.py:969`, `untracked=True`), exactly as an uncommitted run directory does today. Deleting `runs/` whole takes the files along; deleting one run directory does not.
3. **The start as a git object outside the working tree**, under a ref of labkit's own (for example `refs/labkit/starts/…`). The tree is untouched, so the dirty detection is not involved, and `git clean` does not reach it. It breaks transfer by default: a clone and a push carry only branches and tags unless the lab configures the refspec. It needs a repository at the start, where a run outside one starts today, and `git gc` keeps it only while the ref stands.
4. **Stay local, and name the limit** — today's state. Nothing breaks; cases 1 to 4 above stay as they are.

**Recommendation.** Option 2, with the dirty detection left to say what is true: a start file nobody committed is an uncommitted file, as an uncommitted run directory already is, and it is not ignored. It keeps one home per run, survives the deletion of the run directory it describes, merges without a rule of its own, and reaches a clone with the commit that would carry the run directory anyway. Its cost is a format change of the start record before the first release that ships it, which is cheapest now. It does not close the common limit: a start nobody commits stays local under every option.

**Open choices for the author.**

1. Which carrier: one tracked file (option 1), one tracked file per start (option 2), a ref of labkit's own (option 3), or local as built (option 4).
2. If tracked: whether a start file or row counts for the dirty detection like any other uncommitted file (the recommendation), or is excluded by name — which is the ignoring the author ruled out, under another word.
3. If tracked: whether the stop or the commit hook holds a start that is not committed, so that "nothing carries an uncommitted start" becomes a named state instead of a silent one.
4. Whether the UTC start also goes into `config.json`, where it would travel with the run directory and cost a new record schema.
5. Whether a clone without start information reads an unreadable record as unassigned, as built, or must say that its start record is missing.
