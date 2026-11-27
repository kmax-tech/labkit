# Repo audit: a Python-version bug in a generated page, drift in five texts, doubled homes

2026-11-27, at commit `417faffe` (0.116.0 plus 94 unreleased commits). The author ran the repo audit. This note is the register of what was found before anything was changed; nothing was fixed in the audit.

## How it was read

Ground truth first: a fresh `git clone` of HEAD into a scratch directory, tags fetched, a new `.venv` with `pip install -e '.[dev]'`, HOME set to an empty directory, then `.githooks/checks full`. ruff, ruff format and pyright reported nothing; pytest ended with exit 1: 1 failed, 4806 passed, 1 skipped, 7952 subtests passed in 593 s. The failing test is the first finding below. The package holds 149 modules (`formats` 51, `gates` 31, `tools` 22, `checks` 19, `run` 16, `probes` 9), about 81 000 lines; the tests about 98 000.

Three readers that did not write the code read in parallel, read-only. The session that ordered them opened the lines of every finding marked "confirmed"; the others rest on the reader alone.

| Reader                   | Question                                                    | What it read                                                                                                                                                                                                     |
|--------------------------|-------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| clarity (`code-clarity`) | where a person approving the diff since 0.116.0 misreads it | a sample: CHANGELOG "Unreleased", the start-point ladder, `code_since_run`, preflight's stations, `hold_changed_paths`; the rest of 215 changed files unread                                                     |
| homes                    | the same logic, list or constant in two places              | greps over all of `labkit/`, both sites of each candidate; `tests/test_one_home.py` passed on this state                                                                                                         |
| drift                    | prose that claims what the code no longer does              | `AGENTS.md`, `README.md`, `docs/*.md` (chain and one-home only scanned for names, paths, links), all 22 commands' `--help`, module docstrings for names, paths and counts; `labkit/docs/` only scanned for names |

## Bug with effect

1. **`docs/gate-stations.md` depends on the Python version (confirmed).** The page renders code expressions with `ast.unparse` (`labkit/tools/check_inventory.py:332`). For a nested f-string, Python 3.15.2 writes `f"…"` where 3.12.7 writes `f'…'`; two rows differ (`registration_hold.release_unchecked`, `finalize.check_kept_number`). The checked-in page was written under 3.12, so `tests/test_gate_stations.py:257` fails in a clone whose `python3` is 3.15 — and with it the pre-push hook. AGENTS.md says the suite passes in a fresh clone; that holds only for an interpreter that unparses as 3.12 does. Not checked: 3.13 and 3.14, and whether `docs/checks-overview.md` has rows of the same shape.

## Doubled homes

| Logic                                                       | Occurrences                                                                                                                                                                                                              | State                                                                                                       |
|-------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| check of a review row (`decision_sha`, `verdict`, `why`)    | `labkit/formats/reviews.py:282`, `labkit/formats/report_reviews.py:637`; readers `reviews.py:232`, `report_reviews.py:597`                                                                                               | confirmed; known as TODO "Reste der Audits", point 2                                                        |
| the repo-local code folders `("lib", "src")`                | `labkit/formats/scope_sha.py:115` (`LOCAL_ROOTS`), `labkit/formats/run_code.py:28` (`SHARED_CODE`)                                                                                                                       | confirmed; the comment at `run_code.py` names `scope_sha` and does not import it                            |
| what in prose counts as a number                            | `labkit/checks/report_blocks.py:1003`, `labkit/checks/recheck.py:649`                                                                                                                                                    | confirmed different masks; two purposes (a hint on stated numbers, a match against metrics) — a decision    |
| the start-point ladder (no commit, no repo, patch, unknown) | `labkit/formats/runs.py:1631` (`start_point`), `labkit/checks/run_record_check.py:563`–`616`                                                                                                                             | confirmed; known as TODO point 7. The copy picks LAB-010 against the technical rule, which the string can't |
| catching `console.Refused` in `main` with exit 2            | 13 sites, e.g. `labkit/gates/finalize.py:1428`                                                                                                                                                                           | known as TODO point 3                                                                                       |
| TOML head of a comment block                                | `labkit/formats/handovers.py:551`, `labkit/checks/report_blocks.py:651`, `:883`                                                                                                                                          | reader                                                                                                      |
| which protocols a commit holds                              | `labkit/formats/protocol_then.py:62`, homes in `labkit/formats/repo.py:329`, `:1236`                                                                                                                                     | reader                                                                                                      |
| rule id → rule name map; shape of a rule id                 | `labkit/tools/check_overview.py:178`, `labkit/tools/gate_stations.py:420`, `labkit/formats/finding_line.py:210`; ids at `labkit/formats/rules.py:54`, `labkit/formats/gate.py:159`, `labkit/formats/finding_line.py:165` | reader                                                                                                      |
| an area's `output/` folder as a literal                     | `labkit/formats/repo.py:326`, `labkit/run/runlog_command.py:54`, `:497`, `labkit/formats/scope_sha.py:1235`, `labkit/tools/scaffold.py:721`                                                                              | reader                                                                                                      |

Nine more of smaller weight (blob id at a path, streaming JSONL by hand in three modules, the venv as a `Path`, the template directory, the pyproject read in four tools, the transcript timestamp, the current branch twice in `attempts.py`, a gate's name and phase as a literal pair, a long-held `flock`) stand in the reader's report, which was not kept.

## Drift: prose against code

All confirmed except where marked.

1. `labkit/checks/code_scan.py:5` says `data_keys` lives there; it is defined at `labkit/formats/scope_sha.py:1219`. `docs/architecture.md:184` repeats it ("fields, keys and stages"). In `scope_sha.py`, `data_keys` stands after the `if __name__ == "__main__"` block (reader).
2. `README.md:273` names two public `recheck` names; the Public API table (`docs/architecture.md:118`) has a third, `recheck.rows_of`. A lab reads that a name under the release rule may change without warning.
3. `CHANGELOG.md:128` (Unreleased) names `findings.REVIEW_WORD`, `findings.CLAIM_REVIEW_WORD`, `findings.name_ending`; `CHANGELOG.md:93`–`95` of the same section moves them to `audit_files` without a forwarder.
4. `scope-sha --help` opens with a cut-off sentence, and its FILE line names only `lib/` while `LOCAL_ROOTS` holds `src/` too (`labkit/formats/scope_sha.py:1110`, `:1121`; reader).
5. `docs/architecture.md:175` leaves out the answer-reading check between reseed and detach that `labkit/run/runlog.py:523`–`540` runs (reader).
6. `tests/test_run_starts.py:7` points to `tests/test_evidence_start_files.py`, which never existed (reader).
7. `AGENTS.md:39` describes `just guard` without the gate-stations test the recipe runs (`justfile:22`; reader).
8. `docs/architecture.md:288` lists under "Planned" an item the linked note calls not ranked (reader).

## Clarity (sample of the diff)

1. `labkit/checks/run_record_check.py:519` — the docstring of `_helpers_since_run` names two patch states as the early blockers; the code blocks first for no commit and no repository.
2. `labkit/formats/run_code.py:61` — `code_then` checks a run gone from the tree that started dirty before `start_point`; the comment tells history, not why first.
3. `labkit/gates/report_check.py:1362` — `hold_changed_paths`, `hold_declared`, `hold_registered`, `report_hold.hold_report`: four parallel names of different scope.
4. `labkit/checks/run_record_check.py:135` — `code_since_run`'s docstring opens with the blocker case only.
5. `labkit/gates/preflight.py:321` — the station-5 comment hides its condition.
6. `labkit/gates/report_check.py:1394` — `protocols.append` changes `touched.protocols` in place; harmless now, `touched` is read only for `.sources` afterwards (confirmed).

## Large modules

Ten modules hold 1 400–2 000 lines, led by `labkit/checks/run_record_check.py` (1 985), `labkit/formats/protocol_check.py` (1 882), `labkit/formats/runs.py` (1 874). TODO "Fragen an den Autor" already asks whether to cut them.
