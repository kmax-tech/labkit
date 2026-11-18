# The start file: which run started with which protocol, when and as what

2026-11-18. The record of a built design, decided by the author on 2026-11-18 in three steps: a start record outside the run directory, then one row per run of every kind, then one tracked file per run in place of a local list. Code: `labkit/formats/run_starts.py` (the file's one home), `runlog.Run._write_start_file`, `evidence.start_file_changes`, `area_state.assigned_to`, `area_state.binding_conflicts`, `area_state.measurements_without_record`, `registration_hold.binding_conflict_hold`, `hook_post_change.index_problems`. Tests: `tests/test_run_starts.py`, `tests/test_evidence.py` (`CommittedStartFile`), `tests/test_area_state.py` (`AStateBuiltWithoutFiles`), `tests/test_rules_registration_hold.py` (`ARunWithoutItsRecord`, `ABindingTheFilesContradict`), `tests/test_end_to_end.py` (`FirstMeasurementLost`, `ParallelStarts`). What the gates do with it: [a measurement whose record is missing keeps counting](2026-11-18-lost-first-measurement.md).

## Why

Everything that bound a run to its protocol at its start lay inside the run's own directory (`config.json`, written by `runlog.Run._write_record`). The run index got its row only at a clean end. A run that broke off and whose directory was deleted or damaged left nothing that said which protocol it had measured, and no record of a lost run carried a start time with a zone. The order of a lost run and a readable one was therefore read from the local start times in the run ids, under a rule that took two runs as ordered only when the ids lay more than 26 hours apart. The author called that rule what it was, a conservative auxiliary rule and no evidence, and ordered the start information kept outside the run directory and the rule removed.

## The file

One file per run, `run-starts/<run_id>.json` in its area: outside the run's directory and outside `runs/`, so deleting or damaging the run directory — or `runs/` whole — leaves it, and whatever lists `runs/` meets directories only (five fixtures of the suite, and any script of a lab, assume that). A JSON object of exactly four keys, in this order:

```json
{
  "run_id": "2026-11-18T13-00-00_ab12",
  "protocol_id": "p-9e2341c0390948dc",
  "started_utc": "2026-11-18T12:00:00+00:00",
  "run_kind": "measurement"
}
```

`protocol_id` is "" for a run that started unbound, `started_utc` the starting machine's clock in UTC to the second, `run_kind` one of `measurement`, `probe`, `preparation`. `run_starts` is the one home of the name (`START_FILES_DIR`, `START_SUFFIX`, `start_path`, `is_start_file`), the fields (`START_FIELDS`), the reader (`read_starts`, `parse_start`: strict, a file that does not read raises `RunStartsError` naming it) and the writer (`write_start`).

Two files, two questions. The start file says which run started with which protocol, when and as what. The run index `runs.tsv` says which runs reached completion; its format, its meaning and the Public API contract of `runlog.run` (`docs/architecture.md`, "Public API") are untouched: a clean exit writes the `runs.tsv` row, an exception is re-raised with no index row. The two are linked by the run id, and no completion state or result is kept in a start file.

## What the contract asks, and how it is met

1. **Written whole and durably before the run's block executes; a failed write refuses the start.** `runlog.Run.__init__` writes the start file as the last step of the start, after every refusal and after `config.json`, and before the `with` block of the script runs (`_write_start_file`). `run_starts.write_start` writes the text to a temporary file beside the target and syncs it, creates the start file from it in one step, removes the temporary file and syncs the directory. When that fails the start ends with a `SystemExit` naming the file, and the run directory is removed. A start labkit refuses for another reason — the registration, a reseed's conditions, the detach gate, the freeze gate, the run index's own check, an open twin, the repeat's draw — never reaches the write and leaves no start file. So a start file names a run whose record was written.
2. **Never overwritten.** The start file is created by a hard link from the temporary file, which fails when the name exists. Different run ids are different files, so two starts never write into one file and two branches that both ran do not conflict in git the ordinary way. The same run id started twice still collides, and loudly: the second start is refused, the first file stands as written, and no run directory is left (`tests/test_run_starts.py`, `test_a_run_id_whose_start_file_stands_refuses_the_start`). Two branches that each hold a start file of the same id — the same second and the same four random hex digits — conflict in git as any two versions of one file do.
3. **Deleting or changing a committed start file is detected.** The station is the one that already holds a committed run directory and the audit files: `evidence` (`start_file_changes`, in `broken`). It compares the tree or the index with HEAD, and each commit of the session with its parent, and names a start file that was changed or deleted with the restore from the commit that holds it (`git checkout <commit> -- <path>`). A deletion committed earlier is read back from history all the same (below). The finding is a BLOCKER, as every change of committed evidence is there: report-check holds it at its first station (and so `labkit-next` and the adoption), the stop and the commit hold it, and the post-change hook tells it right after the tool that did it. The grade follows the rule that a check that could not run blocks the gated step: without the start file, which protocol a lost run belonged to and when it started cannot be checked. A start file back as first committed is no finding.
4. **A clone has what a commit holds.** The lab stamp does not ignore start files (`scaffold.GITIGNORE`). Once committed, a start file travels with the repository. Before the commit there is expressly no such safeguard: a start file nobody committed exists on the machine that started the run and nowhere else, like the run directory itself. An uncommitted start file leaves the working tree changed. That is an honest display of the state — a run started here and nothing in the repository says so yet — and labkit does not hide it: the next run records its tree as changed at the start (`+dirty`, `provenance.git_state`) until the lab commits.
5. **`runlog reindex` writes none.** `reindex` rebuilds index rows from run directories and does not read or write start files. A run from before start files, or one whose start file was never written, gets none made up from its id or its `config.json`: only a start writes one.
6. **Contradicting bindings are their own finding.** A run's own record where it reads, its start file and its index row may name different protocols. `area_state.binding_conflicts` lists every such run; none of the files is taken over another. For each protocol among the ids named, finalize's registration station returns one BLOCKER of a check not executable (`registration_hold.binding_conflict_hold`), before any comparison, and the run's start names the contradiction in its warning. A record that does not read and whose two files disagree is assigned to neither protocol.
7. **The 26-hour rule is gone.** The order of two runs is told only where a start file holds a UTC start for both; otherwise it is unknown, said as such with the run whose start is missing, and held.

Locking is as it was before start files: the run index's lock (`run_index.index_lock`) is taken at a start only for a repeat's draw, and at every end for the index row. A start file needs none; its creation is one step of the file system.

## Every run kind, and what each reader asks

Every run gets a start file, whatever its kind: a probe can produce numbers, and a run must not be missing for its name. So a start file says "a run started", never "a measurement started", and each reader asks for the kind it means:

| Reader                                                             | What it takes from the start files                                                                                                              |
|--------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| assignment (`area_state.assigned_to`)                              | the protocol id, of any kind                                                                                                                    |
| order (`Measured.started`)                                         | the UTC start, of any kind; the comparison is with the measurements whose record reads (no repeat, no probe), whose kind their own record names |
| runs only a start file names (`AreaState.started_only`)            | every kind; `Measured.started_only` is those with `run_kind = "measurement"`                                                                    |
| lost runs (`AreaState.lost`, the index only)                       | every kind; `Measured.lost` leaves out a run its start file lists as a probe or a preparation                                                   |
| a record that does not read (`Measured.may_have_measured`)         | its start file's kind; without a start file it may have measured                                                                                |
| `Measured.has_measured`, the report duty, the registration station | only runs that may have measured, by the three rows above                                                                                       |
| the post-change hook (`hook_post_change.index_problems`)           | every kind, named in the line                                                                                                                   |

A probe keeps today's meaning. A lost probe whose start file stands is treated as a readable probe is: it binds no registration, and it stays visible in what the post-change hook prints. A run from before start files has none: its kind is unknown where its record is gone, it counts as it did, its order is unknown and the hold stands. No exception is made for it.

## Assignment first, order second

A file assigns, a time never does. A record that does not read belongs to the protocol its start file or its index row names (`area_state.assigned_to`); a run with neither is unassigned, whatever the number of protocols in the area. Only for a run assigned to a protocol does a time then say whether it may have been that protocol's first measurement. Closeness in time assigns nothing.

A start file makes a broken-off run with a missing or damaged record an assigned one: `AreaState.started_only` holds the runs only a start file names (no directory in the working tree, no commit that holds one, no index row), and the measurements among them count for their protocol (`Measured.has_measured`, the report duty, the registration station).

## What a UTC start does and does not give

It removes the zone from the question: two starts compare without any margin. It does not make the order certain. The time is the starting machine's clock, and a clock set wrong gives a wrong order on one machine and across machines alike. Correct machine clocks stay an assumption; every message that takes a run as the later one states it (`area_state.CLOCKS_ASSUMED`), and labkit does not check it. Two starts in the same second are not ordered. The file names no machine (decided: no use was named, and a host guarantees no clock).

## What the post-change hook tells

`hook_post_change.index_problems` keeps an abort and a missing record apart. A run with a start file whose directory stands without a completion "started as a <kind> and never completed": its record is here (`unfinished_starts`; a run whose process still lives is left out, and where that cannot be told the line says so). A run whose directory is gone "is gone", named by its start file ("lists it as a <kind> that started, runs.tsv lists no completion") or by the index ("lists it as measured"). The cheap pre-check that decides which areas get a state built reads both (`area_state.index_names_gone_runs`, `starts_name_open_runs`). A known limit, open and not built: for a start file that is present and names another protocol than the run's record, the hook prints nothing and does not prevent the commit; the release is held by finalize's registration station and by report-check (`registration_hold.binding_conflict_hold`), and the run's start names it. The start itself refuses nothing in any of these cases: a hold is on the number of the protocol concerned, and a new run of that protocol or of another one starts (`tests/test_end_to_end.py`, `LosingTheStartFile`; `tests/test_area_state.py`, `test_a_missing_start_file_bears_on_its_own_protocol_alone`).

## Parallel starts

`ParallelStarts` (`tests/test_end_to_end.py`, slow) starts 8 processes of their own that wait for one signal and then each start and finish 5 runs in one area, in 3 rounds on a fresh area: 120 starts. In every round each run had an id of its own and exactly one start file, each read whole, no temporary file was left, and the run index held the same 40 runs.

## Rejected carriers

The decision followed a comparison of where the start information can live. What a fresh clone knows is the frame: the lab stamp ignores `runs.tsv` and its lock and nothing under `runs/`, so a run directory travels from the commit that first holds it, a directory deleted after a commit is read back from history (`area_state.committed_runs`), and nothing carries an uncommitted file into a clone under any option, since labkit never commits.

1. **A start row in `runs.tsv`, completed at the end.** Rejected: the Public API contract of `runlog.run` says an exception is re-raised "with no index row"; every reader takes the index as "the runs that reached completion" (`run_index.indexed_runs`, `indexed_bindings`, `AreaState.lost`, `runlog.unindexed` and `reindex`, the hook's lost runs, the handover's run account, the report duty); a row would be completed by rewriting a file every writer today only appends to; and `reindex` would have to keep rows it cannot rebuild beside rows it may write.
2. **One local, ignored list beside the index (`run-starts.tsv`).** Built first and replaced before any release. It protected against a damaged run directory on the starting machine and carried nothing into a clone; `git clean -x` removed it; and ignoring it served to keep the dirty detection quiet, which is not what ignoring is for.
3. **The same list, tracked.** Rejected: every start would change one tracked file, two branches that both ran would conflict at its end on every merge, a union merge needs a stamped `.gitattributes` and can leave a run listed twice, and the lock at every start would stay.
4. **The start as a git object under a ref of labkit's own.** Rejected: the working tree would be untouched, but a clone and a push carry only branches and tags unless the lab configures the refspec, and a run outside a repository, which starts today, could not start.

## What changes for a lab

- Start files appear under `run-starts/` in each area and belong in the commit that carries the run. Until committed they are untracked, and git reports the tree as changed.
- Runs from before start files have no start and no kind there. Beside a readable measurement their order is unknown and the hold stands; the ways out are the ones of the hold.
- Whether the removed 26-hour rule ever applied in practice was not shown: it is not known that runs of one area start on machines in different zones. `config.json` names no host (`runlog.Run._write_record`: `pid`, `python`, `env`, `command`, no machine), so a lab could only have checked this by knowing which machines start its runs.

## A start file that is deleted, not staged, or does not read

Three states of a start file are their own cases, each closed after the first build (decided by the author on 2026-11-18).

**Deleted by a commit.** A start file a commit once held and the file state lacks is read back from the last commit that held it, by the reader that brings a deleted run directory back (`area_state.last_committed`, behind `committed_runs` and `committed_starts`). labkit keeps using it for assignment and order: the run stays started, assigned and ordered as that file says, so a committed deletion does not make the documented start disappear. The post-change hook names the deletion with the checkout that restores the file, whenever it was committed (`AreaState.deleted_starts`). A deletion committed earlier blocks no release by its existence alone: nothing is lost that a check needs, since the file is read from history. Only a deletion against HEAD, or by a commit of the session, is the evidence station's blocker with the restore as its way out. History git cannot read is said as it is for runs (`AreaState.history_unread`).

**Not staged or committed.** Where the commit is checked, the start files are the index's (`area_state.indexed_starts`), like everything else of that state: a start file that stands in the working tree and is neither staged nor committed is no part of it. A run of the format with start files needs its start file in that state, whether its record is being staged now or was committed earlier: otherwise a report or an adoption that names the run would be checked against a safeguard the commit's state lacks. The finding holds the commit, with `git add` of the file as the way out (`evidence.unstaged_start_files`).

**The start mark, and what its absence means.** Which runs have a start-file duty is told by the run's own record, never by a guess. A run's start writes a mark into its directory before it writes the start file: `runs/<run_id>/start-file`, holding the start file's path (`run_starts.write_start_mark`, `START_MARK`). A run whose directory contains the mark owes a start file. For a run without it no start-file duty is evidenced, and none is asked, staged now or committed long ago; every run started before start files is such a run. That the run never had a start file is not proven by the missing mark: a mark can be lost. The mark is read as the start files are — from the file state, and from the commit that holds it where the file state lacks it (`area_state.marked_runs`) —, so deleting a committed mark does not lift the duty. The record names no labkit version, and a new field in `config.json` would have been a new record schema that every existing run fails to read, so the mark is a file of its own in the run's directory.

**Marked, and no start file anywhere.** Where a run's directory contains the mark and no start file is found — not in the working tree, not in the index, not in a commit — that is a loss of evidence, said as one and not as a start that is merely unknown (`area_state.missing_start_sentence`). For the protocol the run is assigned to by other evidence — its record, the index — it holds the release: a BLOCKER of a check not executable at finalize's registration station (`registration_hold.missing_start_hold`), and so at report-check, `labkit-next` and the adoption. Not for the area: another protocol is not touched, and a run nothing assigns stays a warning, held against none (`area_state.missing_start_warning`). The run's start and report-check's report duty say where the release is held; the post-change hook names the run. The ways out: the start file back from a commit, a clone or a copy that holds it — never written anew from memory, and no value put in its place —; where nothing keeps it, a new registration or the handover, as for a record that is lost.

**Does not read.** Such a file is its run's incomplete start, not a state of the area. It is represented as a start whose protocol id, start time and run kind are each None — unknown, with why the file does not read beside them (`RunStart.unread`); no default stands in for any of them (`run_starts.start_of`, the one fallback of every reader). Nothing is taken from the file, and it is never rewritten: there is no hand correction, and a value comes only from where it is kept. The protocol and the kind of the run are read from the run's own record where that reads, as for every run. A UTC start is kept nowhere else — `config.json` holds a local `started` without a zone, which is not one —, so the start stays unknown. What depends on a missing value stays open: the order of that run against others is unknown and held where it matters, for the protocol the run belongs to by its record or its index row and for no other (`Measured.unread_starts`); a run nothing else names is unassigned, warned of, and held against no protocol (`Measured.unassigned_starts`). The warning is `area_state.unread_start_warning`, printed at the run's start, in `finalize` and where report-check reads the report duty (`registered_report.unread_start_note`); the hook names the file with why it does not read. A committed start file that does not read keeps the restore from the commit as its way.

## Does losing a start file ease a release?

Compared on 2026-11-18 with real commands on the counting skeleton: the same scenario with the start file and after deleting it while no commit held it, through finalize's registration station, report-check, the run's start check and the post-change hook. The claim "no check that held with the file passes without it" was refuted in two of four cases:

| Scenario                                                      | With the start file                                                           | After deleting it, as first built                                                                |
|---------------------------------------------------------------|-------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| A finished (index row), its directory deleted; B measured     | all four hold or name A                                                       | all four still do: the index row keeps A, its order unknown                                      |
| A stands; a later run deleted; A's start file deleted         | none holds (the later run is warned of)                                       | all four hold or name it: stricter, the order is unknown                                         |
| A broke off (no index row), its directory deleted; B measured | all four hold or name A                                                       | **none does**: the start file was A's only trace, and its mark went with the directory           |
| A stands; its start file names another protocol               | registration station, report-check and the start check hold the contradiction | **none of the three does**: the contradiction was gone with the file, and the loss was a warning |

Decided by the author on 2026-11-18: an evidenced loss holds, and a complete loss is a limit to be said. A run whose record names a start file that is found nowhere now holds its protocol's release (above). The comparison is in the suite (`tests/test_end_to_end.py`, `LosingTheStartFile`), the two cases apart:

| Scenario                                                       | With the start file                             | After deleting it, now                                         |
|----------------------------------------------------------------|-------------------------------------------------|----------------------------------------------------------------|
| A stands, intact (the counter-case)                            | none holds                                      | —                                                              |
| A finished (index row), its directory deleted; B measured      | all four                                        | all four                                                       |
| A stands, its record naming its start file                     | none                                            | all four: the loss is evidenced by the mark                    |
| A stands; its start file names another protocol                | registration station, report-check, start check | all four: the mark still names a start file, and none is found |
| A broke off, its directory deleted; B measured — **the limit** | all four                                        | none                                                           |

**The limit.** When a run's directory and its only start file both vanish before a commit holds either, labkit has no evidence of the run and sees nothing — a different situation from a kept mark, an index row or a commit, each of which keeps the run. Only the commit secures a start file. The last row is asserted in the suite as what is, so that a change is seen; it is a limit, not a guarantee. It is the case the first decision names: a run removed without any trace cannot be detected.

## Limits and open points

1. Whether numbers seen in a probe should bind a registration is a contract question of its own. Nothing was changed for it: a probe binds none.
2. A start file that does not read and that no commit holds stays an incomplete start for good: nothing evidences its start time. The file is left as it is.
3. A run whose directory contains the mark and whose start file stands nowhere — never committed, and deleted — is not held by the commit's unstaged check, since nothing could be staged; the registration station holds it (`missing_start_hold`).

## Proposed text for the lab standard, version 0.32

Released by the author on 2026-11-18 in the wording below (third draft: the mark lies in the run directory, a contradiction holds every protocol the files name, and what is said of an uncommitted start file is that Git's history does not hold it); not yet in `labkit/docs/standard.md`. No further round of release is needed unless the comparison with the code shows a contradiction in substance; the full checks exit 0 before main moves. The author decided the homes (two paragraphs in two rules) and the version: the new duty and the new release rule are a change of the contract, so this is standard 0.32, not a dated change. The first draft was returned for three reasons, which this draft takes up: the three duties of the start file stay apart; a run of unknown assignment "cannot be assigned to a protocol", which states missing knowledge and not a property found; and the text does not decide anew which run kinds count as a measurement that binds a registration.

**In LAB-043 Runs go through `runlog`, a new paragraph:**

> **A run's start is kept outside its directory.** Three things hold, each on its own.
>
> *Before the measurement.* Every run, of every kind, writes a start file beside the run directories before it measures (`run-starts/<run_id>.json`: run id, protocol id, start in UTC, run kind) and a mark in its own directory saying that it did. A run that cannot write it does not start.
>
> *In the commit.* The start file is tracked. A commit that takes a run in holds that run's start file, and once a commit holds it, it is neither changed nor deleted. Until committed, the start file is not preserved in Git history.
>
> *When it is lost.* Where the run directory contains the mark and no start file is found, evidence is lost: no number of the protocol the run is assigned to is released until the file is back from a copy that holds it, or the protocol is registered anew or handed over. Where the files that name a run's protocol contradict each other, none is taken over the others, and the release of every protocol they name is held until the contradiction is resolved. New runs may still start.
>
> For a run without the mark no start-file duty is evidenced. A start file says that a run started and as which kind; which run kinds count as a measurement that binds a registration is not decided here and stays as it was.

**In LAB-003 No run without an intent paragraph, a new paragraph:**

> **A measurement that started keeps counting.** A measurement that demonstrably started keeps counting when its record is missing. Its protocol is read from what still names the run (its start file, its row in the run index), never from a time and never from the number of protocols in the area; a run nothing names cannot be assigned to a protocol, which is said, and it holds none. Where an assigned run may have been the protocol's first measurement, no later run and no later commit stands in for what was registered then: the number is not released until the record is back, or the protocol is registered anew or handed over. It may have been the first unless the start files show that a measurement whose record reads started before it; an order they do not tell is unknown and treated the same. The order rests on the clocks of the machines that started the runs, which nothing checks. Which run kinds count as a measurement is unchanged: a probe binds no registration, whether its record is lost or not.

**What the version step takes, for the session that builds it.** the two paragraphs and the head line of `labkit/docs/standard.md` (0.32, with its one-sentence summary), the version every protocol head names and the check that reads it, the stamps and their comparison files, and the `CHANGELOG.md` entry under "Breaking" naming the last release that reads 0.31. That release is found from the actual release state (the newest tag and the `CHANGELOG.md` heads), not from this note. A protocol not yet run takes the migration the refusal names; one with runs is reproduced with the labkit release it was written for. Release, tag and push stay with the author.

**Left for a decision of its own.** Whether numbers seen in a probe should bind a later confirmation — which results someone may already have seen before a confirmation is registered — is not part of this text.

