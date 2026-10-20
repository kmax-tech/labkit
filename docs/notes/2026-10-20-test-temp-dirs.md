# One temporary directory per test session — 2026-10-20

## Problem

The pre-commit hook took over seven minutes, 433 s of it in pytest with
only 42 s of CPU time. 349 s fell on `tests/test_preflight.py` alone, about
15 s per test regardless of what the test checked.

Two causes added up:

- 42 test files create directories with `tempfile.mkdtemp()` and never
  remove them: 436 directories per suite run. The system temp directory
  held about 161 000 of them, from roughly 1150 runs.
- Preflight reads the area's siblings as the repo's other areas
  (`check_deferred_elsewhere`, `findings.repo_records`, which globs
  `<parent>/*/audits`). The preflight tests placed the area directly in the
  system temp directory, so every call scanned every leftover. Each run made
  the next one slower. In a real repo the parent is `experiments/` and the
  scan is cheap.

## Decision

- `tests/conftest.py` points `tempfile` and TMPDIR (for subprocesses) at
  one directory per session, and `pytest_sessionfinish` removes it. Tests
  that never clean up leave nothing behind, and no file needs to change.
- The preflight tests place their area at `<tmp>/experiments/<area>`, so
  the area's parent holds nothing else (`_area_dir` in
  `tests/test_preflight.py`, `WaivedAudit.setUp` in
  `tests/test_cost_lowered_and_waived_audit.py`). Their runtime no longer
  depends on what else sits in the temp directory, even with
  `--noconftest`.

Result: full suite 433 s → 54 s; both files 377 s → 5 s; zero new entries
in the system temp directory after a run.

## Notes

- Fixing the 42 files one by one was rejected: the session directory
  covers them and every future test at once.
- The leftovers from before this change stay in the system temp directory
  until deleted by hand
  (`find "$TMPDIR" -maxdepth 1 \( -name 'tmp*' -o -name 'labkit-test-leases-*' \) -type d -mtime +0 -exec rm -rf {} +`).
- The pre-commit hook runs the suite in parallel (pytest-xdist, `-n auto
  --dist loadscope`): 54 s -> 20 s, measured over repeated runs. More
  workers barely help (4: 23 s, 8: 21 s, 11: 20 s) and no single test is
  longer than 8 s; the floor is the cost of starting processes and writing
  files on macOS. `--dist load` is not safe: classes in
  `tests/test_end_to_end.py` build `test_02` on `test_01`.
