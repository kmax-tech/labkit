# Audit 2026-10-28: today's changes (f5e48e7..92029c2)

Scope: the ~50 commits of 2026-10-27/28 — the third audit round's fixes,
`AuditedState`, the journal copy, `--calibrate-null`, the null-lane
station, the merged SAB harness. Ground truth: HEAD passes on a fresh
clone (2173 passed, 1 skipped for want of `requirements.lock`); ruff and
pyright clean; tree clean. Three readers (clarity, drift, homes); every
row below was opened at its lines, B1 replayed.

Evidence: V = lines opened, R = replayed.

## B. Bugs and drift with effect

| id | Finding | Ev. |
|---|---|---|
| B1 | A non-JSON line in the journal copy ends the stop hook in a traceback: `copy_gaps` reads it with `jsonl.objects`, which raises ValueError (`formats/attempts.py:580`), and `area_integrity` catches only AttemptError (`:518`). The docstring promises AttemptError (`:564-573`). | R |
| B2 | `code-check --bundle` skips a file it cannot read without a word (`checks/code_check.py:591-592`, `except OSError: continue`) and still counts it in the returned number (`:596`). | V |
| B3 | AGENTS.md tells high-cost agents to run `--probe` and "keep representative raw examples in the protocol" (`templates/AGENTS.md.template:128-131`); the stamp, the next steps and the field guide say the probe's rows are never reported and Raw output comes from the run (`tools/protocol_cuts.py:425,463`, `tools/scaffold.py:1267`, `docs/protocol-field-guide.md:387-389`). | V |
| B4 | The probe score prints "equals the truth: NO (truth X)" when the number equals the truth but its meaning differs (`probes/usability_score.py:656-661`); `Score.number_ok` is tolerance AND meaning, `sab_cases.number_ok` tolerance only — one name, two checks (`sab_cases.py:494`, `usability_score.py:577`). | V |

## D. Documentation that no longer holds

| id | Finding | Ev. |
|---|---|---|
| D1 | finalize's null-lane blocker is in no list of what finalize holds: its module docstring (`gates/finalize.py:10-50`, step 7 "warnings only" at `:474`), `docs/architecture.md:405` and its chain table, `docs/workflow.md:131-135`, `checks/run_record_check.py:3-11`. | V |
| D2 | The comment "a lane is a scored lane of the run everywhere else" (`tools/scaffold.py:1245`) and `CHANGELOG.md:329` are false: README and `standard_contract.lane` use lane for the repeat-cost lane (`README.md:300`). The title's `repeat_cost = "high"` stays clear; the reason given for it is wrong. | V |
| D3 | `audit_coverage` says "`preflight` for the freeze (runlog, preflight)" (`formats/findings.py:1428`); its one caller is report-check in analysis mode (`gates/report_check.py:666`). Known since K1 of 2026-10-23, kept in today's rewrite. | V |
| D4 | `area_gaps` does not say it holds the tree to the journal copy, in the tree only (`formats/attempts.py:450-459`). | V |
| D5 | The field guide says "calibrate bands … on a subset (`--probe`)" (`docs/protocol-field-guide.md:518-519`); `--probe` is refused at low, and at apply the way is `--calibrate-null`. | V |
| D6 | README's `usability --task count|judge|fit` (`README.md:274`) lacks compute-hrv, fit-assay, apply-screen. | V |
| D7 | The SAB task sheet asks every case, compute-hrv included, for a criterion and an admissibility condition (`templates/usability-task-sab.md.template:16-19`); a computation has none. | V |
| D8 | Small: `git_dir_path` lists what labkit keeps in the git dir without the journal copies (`formats/repo.py:740`); `sab_cases.truth` still says a SCORE mismatch shows as a wrong number (`probes/sab_cases.py:422-427`); `null_reported` is commented "judge:" (`usability_score.py:113`); the apply Raw output placeholder asks for rows where the field guide asks for a prompt+answer pair (`tools/protocol_cuts.py:423`). | V |

## H. Doubled homes

| id | Logic | Where | Home |
|---|---|---|---|
| H1 | the last verdict line; the answer-line lead | `audit.parse` reads its verdict itself (`gates/audit.py:761-769`) beside `last_verdict` (`:717`); `REFUSED`, `CLARITY_FINDING` spell the lead by hand, the latter only `·` (`:180-181`) | `last_verdict`, `LEAD`, `SEP` |
| H2 | ref → commit | `commit_known` (`formats/repo.py:815`) repeats `commit_of` (`:800`) | `commit_of` |
| H3 | the `===== FILE: … =====` join | `checks/code_check.py:594` beside `audit.prompt_body` (layer 4, which checks may not import) | a home in `formats` |
| H4 | the run index's header check; its file name | `_check_run_index` (`run/runlog.py:257-279`) beside `index_refusal` (`:801-807`); `"runs.tsv"` at `:201,264,666,867` | `index_refusal`, one constant |
| H5 | audit modes as words | three constants (`formats/findings.py:161`, `formats/standard_contract.py:45-46`, `gates/audit.py:155`) and literals (`decision_review.py:312`, `audit.py:843,1329`, `findings.py:643,1440,1721`) | `standard_contract` |
| H6 | probes: kind and criterion key by hand | `TASK_STAMP[…][1] != "compute"` (`probes/usability_score.py:530,664`) dodges the kind rule; `"c1_accuracy"`, `"c1_score"` (`probes/usability.py:171,179`) beside `sab_cases.CRITERION_KEY` | `standard_contract.has_bar`; one key constant |
| H7 | estimator skeleton | strict predict + `_plain` twice (`apply_rows`, `calibrate_null`), the row dict three times, a lanes literal beside `LANES` | one helper in the template |
| H8 | `"experiments"` and `file://` → path | `"experiments"` 7× (`tools/scaffold.py:137,520,738,1487`, `probes/usability_score.py:193`, `formats/repo.py:104`, `run/runlog_command.py:401`); `url[7:]` 3× (`run/provenance.py:151,178`, `tools/repo_check.py:82`) | constants/helper in `repo` |
| H9 | the calibration's 200 | the next step hard-codes it (`tools/scaffold.py:1278`) beside `NULL_PERMUTATIONS`; `--calibrate-null K` prints "the fixed rule" for any K | the constant; print K |

Solved well: `runs.name_minute`/`date_minute` (no other minute
`strftime`), `preflight.tell_test_run`, `audit.prompt_body`/`last_verdict`
in both reviewers, `repo.commit_of` in its three callers,
`start_check.completed_parent`; no renamed name survives outside the
historical registers.

## C. Clarity

| id | Where a reader misreads | Ev. |
|---|---|---|
| C1 | `*_refusal` means two things: `reseed_refusal`, `registration_refusal` raise (`run/start_check.py:349,378`), `index_refusal`, `_constants_refusal` return a reason (`run/runlog.py:801`, `start_check.py:412`); a bare call reads as a no-op. | V |
| C2 | "shown" twice: `AuditedState.shown_sha` (what the prompt showed of the run) beside `BoundPrompt.shown_now` (the earlier repairs, a `Followup`) (`formats/findings.py:336`, `gates/audit.py:1031`). | V |
| C3 | The null-lane note "moved, or the run keeps no two lanes" covers a pass and a check that did not apply (`gates/finalize.py:424`). | V |
| C4 | `unindexed` drops a run folder without config and says nothing (`run/runlog.py:836-837`; older than today). | V |
| C5 | Docstrings that omit a condition: `post_change` also checks every git-changed file (`gates/claude_hooks.py:487-499`); `before_run` never blocks on an unreadable head or a missing protocol (`:248-299`); `score`'s exit ignores the hidden evaluation (`probes/usability_score.py:478`); `AuditedState` is unhashable (`formats/findings.py:338`). | V |

## Open, each one decision

1. Fix B1–B4.
2. Pull the documentation D1–D8 (D2 corrects a reason of mine).
3. The small homes inside one module: H1, H2, H4, H9.
4. The homes across layers or modules: H3, H5, H8.
5. The probe homes H6, H7.
6. The clarity rows C1–C5 (C1, C2 are renames).

## State (2026-10-28, after the fixes)

All six points done, one commit each: B1–B4 `3a7cba3`, D1–D8 (D2
corrects a reason given the day before) the documentation commit after
it, H1, H2, H4, H9 `2754205`, H3, H5, H8 `3a6874e`, H6, H7 `a3cdfd2`,
C1–C5 the clarity commit. New `tests/test_one_home.py` rules hold the run
index's name, the audit modes, the experiments folder, a `file://` read
and the criterion keys.

