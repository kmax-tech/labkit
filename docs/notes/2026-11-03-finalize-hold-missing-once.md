# A finalize hold missing once in the correction end-to-end test

> Cause shown on 2026-11-04 and repaired in the test fixture: see the last
> section. The sections before it are the search, kept as evidence.

2026-11-03. Seen three times, cause still unknown. This note keeps the
evidence; it changes no code. The controlled variation (section
"Controlled variation, 2026-11-03 evening" below) found one input that
reproduces both failure signatures exactly — two measurements whose run
ids share the start second — but no evidence that this input occurred.

**What failed.** The pre-commit hook (full suite, `-n auto`) of a
notes-only commit on branch `v1v2-field-values`, whose code was
`e979a637` (the V1/V2 repair before its rebase; on main as `4abc5565`),
failed one test:

```
FAILED tests/test_end_to_end.py::CorrectionThenNewRun::test_t6_a_question_corrected_then_measured_again_holds
1 failed, 2892 passed, 1 skipped, 6926 subtests passed in 187.09s

tests/test_end_to_end.py:1421: held = self.held_as_b_saw(run_b, "Question / hypothesis")
tests/test_end_to_end.py:1264: held = next(
    ln for ln in out.splitlines() if self.HELD in ln and "BLOCKER" in ln
)
E   StopIteration
run_b = '2026-11-03T17-57-51_588e', field = 'Question / hypothesis'
```

`finalize` exited 1 (the assertion before it passed) but printed no
BLOCKER line holding "what the number is about changed after the first
measurement". The full finalize output was not kept; the excerpt above is
all that survives.

**Repetitions, all green.** The test alone three times; the whole
`tests/test_end_to_end.py` with `-n 8` four times on the branch and four
times on the main checkout as it stood then, without V1/V2; the same
commit's hook on the second attempt;
the full suite on the rebased branch (2945 passed). Repetition shows the
failure is rare, not what causes it.

**Seen twice more, the same evening.** The hook of branch `public-4b`
(code `d4be6216` plus a public-API change that touches no finalize, run
or protocol code) failed two runs in a row, each on another test of
this class, while other sessions ran suites (load average 13–18):

```
FAILED tests/test_end_to_end.py::CorrectionThenNewRun::test_t5_the_twin_two_fields_each_released_pass
tests/test_end_to_end.py:1379: AssertionError   # finalize after run B: rc != 0
FAILED tests/test_end_to_end.py::CorrectionThenNewRun::test_t6_a_question_corrected_then_measured_again_holds
```

t5 failed the other way: finalize held where the twin must pass. The
output beyond these lines was not kept. The third hook run and two full
suites by hand passed, as did the class alone and the file with `-n 8`
twice. Load raises the rate; it does not say which order of runs or
commits finalize saw.

**Two conjectures, neither shown.**

1. A timing race in which measurement counts as first: the test makes two
   measurements and several commits within seconds; run ids carry local
   time to the second, commit dates have second resolution, and
   `answering_run.first_measurements` orders by git history, by run id
   only at one commit. If run B were taken as a first measurement, no
   change "after the first measurement" would be held.
2. No link to V1/V2: the new field reading (`protocol_check.field_values`)
   is deterministic and the test passed on every rerun of that code. This
   is an argument from determinism, not a reproduction of the failure on
   older code.

**Next step (its own task).** Vary order and time under control instead
of repeating: put both measurements and their commits into the same
second (fixed `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`, a fixed clock for the
run id), then swap their order, and read which run `first_measurements`
names and what finalize holds. No added sleep and no retry in the test:
either would hide the cause.

## Controlled variation, 2026-11-03 evening

Code `f1ff7723` (main). A probe subclassed `CorrectionThenNewRun`, kept
t6 and the t5 twin, and printed for each test: the run ids, the commit
each run recorded (`git`, `git_full`), the run directory's creation time,
the lab's `git log` with committer dates, what
`first_measurement_groups` returned at every call, and finalize's full
output. A `sitecustomize.py` on the measuring subprocess's `PYTHONPATH`
replaced `runlog._make_run_dir` to mint a given run id; in-process patches
set the record minute (`findings.name_minute`/`date_minute`), injected
`GitError`s, or moved the working directory. Each variation ran both
tests once (the minute steps twice, the same result both times).

**Baseline (no control).** Both runs record the same commit (the
fixture commits before run A and never after it; B is `+dirty` on that
commit), so `first_measurement_groups` returns one group `[A, B]` at
that commit and the run ids alone order them. A and B start 1.7 s
apart: `2026-11-03T19-28-36_3229` → `…19-28-37_4305` (t5 twin),
`…19-28-40_7e41` → `…19-28-41_59ff` (t6). Both pass; t6's last finalize
holds `Question / hypothesis` "as the answering run … saw the protocol".

| Variation | t5 twin | t6 | Signature as observed? |
|---|---|---|---|
| A and B minted in one second, A's suffix first (`…12-00-00_aaaa`, `…_ffff`) | fails, rc 1 | fails, `StopIteration` | **both** |
| the same, B's suffix first (`…_ffff`, `…_aaaa`) | fails, rc 1 | fails, `StopIteration` | **both** |
| B's id a second-earlier time than A's (`12-00-05`, `12-00-03`) | fails, rc 1 | fails, held line names the wrong run (`assertIn`) | t5 only |
| record minute steps at record 1, 2, 3 or 4 (of 3 per test) | pass | pass | — |
| fixed `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` (all commits one second), alone and with a minute step | pass | pass | — |
| `GitError` in `covering_analysis` after B | fails, rc 1 (Data / scope and Unit held) | pass | t5 only |
| `GitError` in `blobs_then` (`as_measured`) after B | fails, rc 0 (no correction line) | fails, rc 0 | neither |
| working directory deleted before setUp | error in setUp | error in setUp | neither |
| working directory a plain directory / another repo; `CLAUDE_PROJECT_DIR` elsewhere / unset | pass | pass | — |

With A and B in one second, t6's last finalize prints:

```
── answering run: PROTOCOL-lines.md ──
  BLOCKER: 2026-11-03T12-00-00_ffff and 2026-11-03T12-00-00_aaaa started in the same second — the run ids cannot say which is newest. Next: move the one that does not answer out of runs/
── registration since the first measurement ──
  no completed run to check
```

`answering_run.same_second_rival` refuses the choice
(`bound_answering_run` returns no run), so the registration station has
nothing to hold: exit 1 without the "changed after the first
measurement" line — t6's `StopIteration` — and exit 1 where the twin
must pass — t5's `rc != 0`. That refusal is the rule as documented, not
a defect: two runs at one commit in one second cannot be ordered.

**Why this is not shown to be the cause.** Run ids carry the second at
which the run directory is made, after run A has finished and the test's
steps between the two measurements have run, so the ids share a second
only when the whole gap is under 1 s. Measured gap, A to B creation
time, `CorrectionThenNewRun` in the full suite with `-n auto`:

| Run | Load (1 min, start → end) | Smallest gaps (s) | Same second |
|---|---|---|---|
| suite 1 | 2.8 → 8.4 | t6 1.68, twin-on-new-run 1.81, t5 twin 1.89 | 0 of 10 pairs |
| suite 2 | 8.4 → 10.8 | t6 2.02, twin-on-new-run 2.28, t5 twin 2.77 | 0 of 10 |
| suite 3 | 10.8 → 7.4 | twin-on-new-run 1.87, t6 1.96, t5 twin 2.27 | 0 of 10 |
| two suites at once (a, b) | 6.8 → 6.7 (5 min: 16.6) | t6 1.62 / 1.63, twin 1.64 / 1.67, t5 twin 2.44 / 2.25 | 0 of 20 |
| probe class ×40 under `-n 16` | → 20.8 | 3.76 (median 6.17) | 0 of 80 |

All five full suites passed (2975 passed). Load lengthens the gap; it
does not shorten it. The macOS clock log (`log show --predicate
'process == "timed"'`, 17:50–18:55, the window of all three failures)
shows two slewed adjustments, −4 ms at 18:11 and +31 ms at 18:44, and no
step that could move a run id back by a second.

What the measurements do show: in every suite the three tests with the
smallest A–B gap are t6, the twin on a new run, and the t5 twin — the
two tests that failed and one that has not. That fits a cause that
needs a short gap; it is not evidence of one.

**Side findings (not the flake; each its own task).**

1. A git failure inside `protocol_history.as_measured` (`blobs_then`)
   makes finalize pass a changed question: exit 0, and the station says
   "what the number is about and the promise block are the ones the first
   measurement registered". `scope_changes` passes over a text that cannot
   be read back; its docstring says another station names that state, and
   in this case none did. A check that could not run passed.
2. `finalize.resolved_corrections` and `awaiting_followup` catch
   `RuntimeError` (a `GitError` included) and return no release; a failing
   git there turns a released field into a hold whose sentence names the
   field, not the failed check.

**Open.** The cause of the three failures is not shown. The output of
each was lost because the pre-commit hook prints only the last 25 lines
(`.githooks/pre-commit`, `tail -25`), and t6 fails in `next()` without
finalize's output. The next failure settles it only if its full finalize
output is kept: (a) let `held_as_b_saw` fail with finalize's output as its
message, and (b) let the hook keep pytest's full output in a file under
`.git/`. Both are done since `d217ec4a` (`labkit-pre-commit.log` in the
worktree's git dir). If that output shows the same-second
blocker, the fixture is the place to repair (its two measurements on one
commit, ordered by run id alone); labkit's refusal stays.

## Seen twice more in hooks, 2026-11-03 night

The hook of the M2 commit (branch `m2-repair-guidance`, code later
`51456690`, the old hook still printing 25 lines) refused twice in a row:
first t6 (`StopIteration` at `held_as_b_saw`, as before), then t5 (finalize
`rc != 0` where the twin must pass). Load average 8–12. The same code had
passed two full suites by hand just before, and the hook passed on the
next attempt once (b) above was in place. Kept: only the 25-line tails
(session scratchpad, not in the repository); finalize's output is lost
again. Every failure seen so far ran inside a pre-commit hook; no run by
hand has failed. That is an observation, not a cause: the git variables a
hook exports (`GIT_INDEX_FILE`, a temporary one for a path commit,
`GIT_AUTHOR_DATE`) were checked and are dropped by `tests/conftest.py`
before any test runs, so they are ruled out as the carrier.

## Cause shown, 2026-11-04

With the hook keeping its whole output (`d217ec4a`), two refusals were
caught in full, on branch `unread-checks-block` (load average 7–13):

```
FAILED tests/test_end_to_end.py::CorrectionThenNewRun::test_t6_a_question_corrected_then_measured_again_holds
E   AssertionError: no hold naming Question / hypothesis; runs ['2026-11-04T10-10-50_4c7a', '2026-11-04T10-10-50_4f01'], B 2026-11-04T10-10-50_4c7a:
E     BLOCKER: 2026-11-04T10-10-50_4f01 and 2026-11-04T10-10-50_4c7a started in the same second — the run ids cannot say which is newest.

FAILED tests/test_end_to_end.py::CorrectionThenNewRun::test_the_twin_on_a_new_run_a_question_beside_a_correction_holds_the_same
E   AssertionError: no hold naming Question / hypothesis; runs ['2026-11-04T10-25-54_3bb5', '2026-11-04T10-25-54_f8f7'], …
E     BLOCKER: 2026-11-04T10-25-54_f8f7 and 2026-11-04T10-25-54_3bb5 started in the same second …
```

Runs A and B of the fixture started in one second, so the answering
run's choice was refused (`answering_run.same_second_rival`, documented)
and the expected hold could not be made — the failure the controlled
variation above produced on purpose. The directory times measured there
did not show it; the run ids, which carry the second the choice reads, do.
The refusal is labkit's rule, not the defect: the fixture wrote a history
no lab writes by hand. Repair: `CountCommands.measure` waits until the
clock's second is later than every run the area holds, then measures — a
condition, not a guessed sleep; a test holds that two measurements back to
back carry different seconds. Whether labkit itself should refuse or
avoid a run started in the second of another (a script starting draws in
a loop could) is a question of its own, not decided here.

