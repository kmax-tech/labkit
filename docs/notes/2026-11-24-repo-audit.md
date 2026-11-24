# Repository audit — 2026-11-24

Audited `1632dad9` on `main`, two TODO-only commits after release `v0.115.0` (`e39cb323`). Package version: 0.115.0; standard: 0.33. Tracked files were unchanged at the start. Existing untracked agent configuration, `.answer` and rendered note files were left alone. This is an audit, not an implementation or a rollout.

## Findings

### Medium — rechecking accepts a missing registered result

Bug and contract inconsistency: `recheck.agree` promises to compare the protocol's `[kept]` key exactly, but its one-sided-key check includes only intent identifiers. Its later value comparison excludes keys absent from the recorded metrics (`labkit/checks/recheck.py:578`, `labkit/checks/recheck.py:593`).

`agree({}, {"mean": 3.0}, reported=frozenset({"mean"}))` returns `["mean"]` instead of refusing; with both dictionaries empty it returns `[]`. The positive control with equal recorded and recomputed values passes; different values refuse. A new descriptive key may legitimately grow; a registered result that was never recorded must not receive that treatment.

Reproduced through the real two-output scenario from `tests/test_recheck_outputs_scenario.py`, using its existing `TwoOutputFiles` fixture. Baseline `verified_outputs` returns `{"lines_mean": 3.0, "duration_s": 0.1}`. Deleting only `lines_mean` from the temporary run's `metrics.json` leaves verification successful, returning `{"duration_s": 0.1}` after recomputing the registered result. No check was mocked. The metrics were restored and the fixture removed. This proves a gap in the recheck API; it does not establish that every later adoption or reporting gate accepts that damaged run.

Suggested repair scope: require the registered kept key in both recorded metrics and recomputation. Preserve additional descriptive keys. Cover missing from either side and both, with equal and unequal values as controls.

### Medium — concurrent cache initialization shares a temporary file

Bug: `files._stage` names its temporary file using only target name and process id (`labkit/formats/files.py:122`). Two threads writing the same target stage into the same file. The first rename removes the second writer's staging path; the second rename raises `FileNotFoundError`.

A concrete caller is `llm_cache._make_root`: check for a missing `.gitignore`, then write through `write_atomic` (`labkit/run/llm_cache.py:204`). Two simultaneous first users can both pass the check. Both `Cache` and `store_stand_in` use this path.

Reproduced without mocks: for each of 50 fresh temporary cache directories, two threads released by `threading.Barrier(2)` called `_make_root` on the same directory. Every pair produced one `FileNotFoundError` naming `..gitignore.tmp<PID>`. No model was called. This establishes a startup failure; corruption of a model answer was not demonstrated. `write_once` already uses a process-and-thread staging name; ordinary `write_atomic` does not.

Suggested repair scope: give each atomic write its own staging file and check simultaneous cache initialization. Test two writers as well as a reader against one writer; `tests/test_files.py` currently exercises the latter.

## Scope and limits

Read the current TODO, architecture and workflow contracts, release state, report/example readers and shared Markdown walker, preparation-origin handling and audit evidence, recheck API, cache persistence, and suite runner. The findings were exercised locally. No production laboratory, historical protocol, paid model, release, tag or remote was changed.

Format/rule-version coupling, probe origins and the ambiguous missing-run role are already recorded in TODO; they are not new findings. The report-example reader documents remaining fence limitations; this audit does not claim a complete Markdown implementation. The inspected preparation exemption preserves the source-text and byte checks and does not exempt a measurement origin.

## Verification

- `.githooks/checks full`: Exit 0; ruff, format and pyright passed; pytest reported 4523 passed, 1 skipped and 7787 subtests passed in 1120.23 seconds. Product code stayed unchanged throughout. Full output was copied to `/private/tmp/labkit-audit-2026-11-24-checks.log`; the runner's summary is `/private/tmp/labkit-audit-2026-11-24-full.log`. Only this documentation's verification record was completed afterwards.
- `.venv/bin/python -m labkit.formats.rules check`: Exit 0.
- Focused run of report blocks, origin scenarios, two-output rechecking and cache tests: 103 passed and 31 cache tests failed because the sandbox refused binding their local HTTP servers. Repeating `tests/test_llm_cache.py -n 2` outside the sandbox: 31 passed, Exit 0. A separate `tests/test_origin_scenario.py -x --tb=short` run: 5 passed, Exit 0. The full suite above also ran outside the sandbox and needs no production service.
- The independent agent `audit_reader` read the audit note, TODO diff and source substantiation. It confirmed both findings and the medium severities, independently repeated the missing-key checks and reproduced 20 cache-start errors in 20 thread pairs. It did not repeat the full two-output scenario; that reproduction is the primary auditor's evidence. Its reading found no factual correction to the report.

No product code or tests were changed; the existing suite remains green with these uncovered cases. Repairing either finding is a separate task.
