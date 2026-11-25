# Where the suite's time goes — a measurement (2026-11-25)

The whole suite takes 875 s on 11 cores; on 2026-11-10 it took 383 s. This note records what was measured on the cause, on `e4a38cf3`, on the author's Mac. Nothing was changed. The raw outputs, scripts and profiles lie in the internal evidence repository under `2026-11-25-check-inventories/run3-durations/`.

## The whole suite, per test file

One run of `pytest -n auto --durations=0 --durations-min=0.5`, alone on the machine: exit 0, 4645 passed, 1 skipped, 875 s. The tests above 0.5 s sum to 7216 seconds over all workers.

| Share of those seconds                                   | Value |
|----------------------------------------------------------|-------|
| in the 26 files marked `slow`                            | 78 %  |
| in files added after 2026-11-10                          | 32 %  |
| in the six files without the mark that take 60 s or more | 11 %  |

The files added after 2026-11-10 explain about a third of today's time, not the whole doubling. No per-test times exist from 2026-11-10, so the older files cannot be compared. Twelve tests take 60 s or more each under 11 workers; the longest takes 143 s.

The six files without the mark `slow` run in the fast tier before every commit: `test_explored_in.py` (214 s over all workers), `test_decision_review.py` (183 s), `test_claim_review.py` (144 s), `test_audit.py` (88 s), `test_reference_end_to_end.py` (78 s), `test_replacement.py` (71 s).

## Three tests, each run alone

An agent that did not write the tests ran three scenario tests one at a time, without parallel workers: plain, with a log of every child process (a `sitecustomize` that records each `subprocess.Popen`), under `cProfile`, and with the real git binary first on `PATH`. The machine was in use by another session meanwhile (load 3 to 5 on 11 cores).

| Test                                                               | In the suite | Alone  | Alone, real git first on `PATH` |
|--------------------------------------------------------------------|--------------|--------|---------------------------------|
| `test_origin_scenario.py`, a gone origin holds every gate          | 143 s        | 70.0 s | fails after 1.2 s (see below)   |
| `test_repair_paths.py`, a correction then a code repair            | 118 s        | 83.5 s | 48.4 s                          |
| `test_exploration_link_scenario.py`, removing the copy releases it | 69 s         | 36.9 s | 17.3 s                          |

Under 11 workers a test takes 1.4 to 2.0 times as long as alone.

Between 88 % and 95 % of each test is waiting for child processes, and more than 80 % of that for `git`: one test starts 2011 to 5590 git processes, about 14 ms each. Python's start is not a main cause: a labkit console command starts in 83 to 121 ms, and the repair test starts about 70 Python processes (at most 7 s of 83 s). Building the temporary lab is not a main cause either, except in one file (cause 4).

## Four causes

| #   | Cause                                                                                                       | Evidence                                                                                                                                   | What would address it                                                                                   |
|-----|-------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| 1   | `git` on this Mac is the launcher `/usr/bin/git`: 12.0 ms per call, against 4.4 ms for the binary it starts | 40 bare calls each; with the binary's folder first on `PATH` the repair test took 42 % less and the link test 53 % less (measured)         | the real binary first on `PATH` for the checks; no change to the package. Applies to macOS only         |
| 2   | A gate asks git the same question many times within one command                                             | 57 % to 65 % of the git calls repeat an earlier call of the same process word for word; 4 to 7 distinct objects are read 536 to 1280 times | keep an answer that cannot change (an object by its hash) for the process; read `HEAD` once per command |
| 3   | The tree as a run saw it is rebuilt in a temporary index at every question (`repo._in_index_then`)          | 16 % to 23 % of the child time; 459 `git read-tree` for a handful of commits in one test                                                   | keep the result per commit, patch and file list within a command                                        |
| 4   | `test_exploration_link_scenario.py` builds the same adopted two-area state for each of its ten tests        | `setUp` takes 9.9 s of 37.6 s                                                                                                              | build the state once per class and copy it per test, as `StagedLab` does                                |

Causes 2 and 3 are properties of the package, not of the tests: on a one-area lab `labkit-adopt` takes 10.2 s and starts 550 git processes, `labkit-next` 4.7 s and 247, a commit through the pre-commit hook 2.0 s and 241. A person at the gate waits the same time.

Estimates, not measured: with cause 1 addressed the whole suite might take 450 to 550 s on this Mac — extrapolated from two tests. Causes 2 and 3 overlap; the repeats of objects named by hash alone are a quarter of the git calls, the upper bound with `HEAD`-dependent reads is 60 %. Cause 4 would save about a quarter of that one file.

## A test that passes only because git is slow

`tests/test_origin_scenario.py`, `test_a_gone_origin_holds_every_gate_until_restored`, starts two measurements one after the other without waiting for the clock. With the real git binary both start within one second, and finalize refuses ("started in the same second — the run ids cannot say which is newest"); reproduced twice. `CountCommands.measure` in `tests/test_end_to_end.py` waits for the next second; this test does not use it. Any change that makes git or the gates faster turns this test red until it waits. Only three tests were run, so other tests may depend on the same delay.

## What was not measured

- The whole suite with the real git first on `PATH`, and any test beyond the three.
- Why the suite grew from 383 s to 875 s: no older commit was run. More scenario tests, more git calls per gate, or both — not separated.
- Linux, where no launcher stands before git: cause 1 does not apply there.
- Whether keeping a git answer within a command is safe at each call site. A command that commits moves `HEAD` in mid-process; the repeat counts are an upper bound, the reads by hash a lower bound.

## After two changes to the tests (2026-11-25)

Built after this measurement, in the tests only. Every measurement a test starts waits for a later second than the runs its area holds (`Lab.measure` in `tests/test_end_to_end.py`, the one home of the wait), so the origin test no longer depends on how long git takes: alone with the direct git it passes in 31 s, where it took 70 s. And on macOS the suite calls git's binary through one link first on `PATH` (`tests/conftest.py`, `_direct_git`): 3.5 ms a call against 11.7 ms through the launcher, 100 calls each.

The whole suite with both, run alone: exit 0, 4659 passed, 1 skipped, 746 s — against 831 s and 875 s before, about 12 % less. The estimate above (450 to 550 s) was extrapolated from two tests run alone and did not hold under 11 workers. Why the gain is smaller there was not examined. No other test depended on the slow git.

## After keeping git answers within a command (2026-11-25)

Built for cause 2 and cause 3, in the package: while a console command runs, an answer about a git object named by its full hash is asked once (`console.once_per_command`, `repo._once_by_hash`). Kept are a blob's content, a full hash that names a commit, and the tree a run started from per commit, patch and file list. Nothing that depends on `HEAD`, the index or the working tree is kept, and nothing at all outside a console command.

Measured on `tests/test_repair_paths.py`, a correction then a code repair, run alone without parallel workers, with the direct git and the log of every child process, alternately from a worktree of the commit before (`73918ea0`) and from the changed checkout, twice each. The machine was in use by another session (load 2 to 6 on 11 cores), so the times are a direction, the counts are exact and were the same in both runs of a pair.

| Count                                             | Before | After  | Change |
|---------------------------------------------------|--------|--------|--------|
| git processes in the whole test                   | 5590   | 3317   | −41 %  |
| in the six calls of `labkit-next`                 | 1448   | 600    | −59 %  |
| in the first `labkit-adopt`                       | 452    | 198    | −56 %  |
| in the two later calls of `labkit-adopt`          | 1095   | 430    | −61 %  |
| in the seven calls of the stand-in audit answer   | 496    | 496    | 0      |
| in the nine calls of `02_analyze.py --check`      | 178    | 178    | 0      |
| `git read-tree`, `git write-tree`, `git cat-file` | 1263   | 165    | −87 %  |
| `git rev-parse`                                   | 2089   | 1288   | −38 %  |
| the test's call, seconds (two runs each)          | 65, 78 | 51, 54 |        |

The expectation before the build was that a quarter to a half of a command's git calls go; for the labkit commands it is 56 % to 61 %, for the whole test 41 %. A measure script and the analysis script keep nothing, as built: their counts did not change (the two measure starts read 79 against 81, and 12 `pip freeze` git calls appear only in the runs from the worktree — a difference between the two trees' installs, not of the change; together 14 of the 2273 fewer processes).

What remains is mostly what was left out on purpose: `git rev-parse` (1288), `git log` (566), `git ls-files` (414) and `git show` (281) read `HEAD`, the index or history by name. Keeping those needs a rule for when a kept answer still holds — a command that commits moves `HEAD` in mid-process.

Not measured: the whole suite's time against the 746 s before (one run after the change gives the exit status, not a comparison — sequential runs drift), and any other test. The measurement was taken before an independent reader's findings were worked in; those changed names, one docstring and a refusal of nested commands, not which answers are kept. Logs and scripts: internal evidence repository, `2026-11-25-check-inventories/run6-kept-answers/`.

## A start test that failed once in a whole run (2026-11-25)

`tests/test_runlog_wait.py`, `test_a_bare_name_starts_the_run_in_its_area`, failed once in a whole run and passed alone three times and in the next whole run. Its message: `runlog start: run …: its record does not read — …/config.json: unreadable run metadata (Expecting value: line 1 column 1 (char 0))` — an empty file.

Reproduced with a controlled delay, three ways for the stand-in command to write its record (script: internal evidence repository, `2026-11-25-check-inventories/run7-start-record/`):

| The stand-in command                                                       | `runlog start`            |
|----------------------------------------------------------------------------|---------------------------|
| leaves `config.json` empty for 1.5 s, then writes the record               | exit 2, the same sentence |
| leaves the run folder without a record for 1.5 s, then renames it in place | exit 0                    |
| renames the record in place at once                                        | exit 0                    |

So `runlog start` waits for a run folder whose record is not there yet, and refuses a record that is there and does not read. A run publishes its record by rename (`files.write_atomic`), so it is never seen half written; the test's stand-in wrote it with `shutil.copy`, which creates the file empty and then fills it. The fault was the stand-in's, not the command's and not a time limit. Four stand-in commands of that file wrote the record that way; they now write it beside and rename it (`RECORD_BY_RENAME`). No wait was added and no limit raised.

Not examined: other test files whose stand-in commands write a record straight to `config.json`.


## The two tiers timed (2026-11-25)

One run each on 11 cores, on `2153095c`, 27 test files carrying the mark `slow`: the fast tier (`.githooks/checks fast`: ruff, format, pyright and the suite without the scenario files) 124 s; the whole suite alone (`pytest -n auto`, after the git answers were kept) 525 s. `AGENTS.md` and `.githooks/checks` cite these two numbers; they cited 81 s and 383 s from 2026-11-10, when 13 files carried the mark. Sequential runs drift by about 15 %, so neither number is more than an order of size.
