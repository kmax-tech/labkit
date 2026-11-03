# A finalize hold missing once in the correction end-to-end test

2026-11-03. Seen once, not reproduced, cause unknown. This note keeps the
evidence until a targeted investigation settles it; it changes no code.

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
