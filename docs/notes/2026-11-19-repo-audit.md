# Repo audit: clarity, drift, doubled homes after the start files and the exploratory merge (a3951e92, 2026-11-19)

The author's question: after many changes, is the code clear and maintainable, is the logic clear, is there drift, are there very long lines, and are there duplications in how fields, holds and gates get built in? This follows the [audit of 2026-11-18](../audit-2026-11-18.md) (9a9fb89e), whose ten points are all worked; nothing it lists as done or knowingly open is repeated here. Four readers: clarity of the start-file and lost-measurement code, clarity of the exploratory merge, prose against code, one home per logic. **V** marks a finding the main session opened at the lines named, **R** one that stands on the reader alone. Line numbers are those of a3951e92. The audit reports; nothing was changed.

## State audited

`main` moved during the audit: it began at 9ee71406, and at 18:22 another session fast-forwarded to the merge of the exploratory workflow (standard 0.33; da11645c, then a3951e92). All readers read the merged tree. Since 9a9fb89e that is 187 commits; the package is 71,233 lines in 137 modules (62,360 in 122 on 2026-11-18).

Checks: `ruff check`, `ruff format --check` and `pyright` exited clean on 9ee71406. The full suite was **not** run to its end by this audit: the run started on a tree that changed under it and was stopped, so it counts for nothing. `TODO.md` records a green full run on the merged tree by the merging session (log in labkit-evidence, `test-runs/2026-11-19-integration-standard-0.33-full-checks.log`); this audit did not open that log.

Not read for clarity: `run_code.py`, `input_origins.py`, `protocol_step.py`, `run_diff.py`, `scope_sha.py`, `runs.py`, `protocol_fill.py`, `params.py` (the second clarity reader says so).

## Overall

The structure still holds where a test or a refusing parser binds it: a gate is one function and one line in its entry point's station list, `labkit-next` reads that chain, and a field of a file on disk (start file, run record, index row) has one schema whose reader refuses an unknown key. Neither linter finds anything.

The dominant problem class is **one question decided per entry point, in the two layers added last**: the handling of runs with incomplete evidence (start file, index row, record), and the split between an exploratory and a confirmatory protocol. Each new condition there was built in by hand at up to seven modules, and the hand-kept lists already disagree in three places that can change a verdict. The second class is naming inside the area state: the same field name holds different things on two records.

## Findings

### Can change a verdict

| Finding                                                                                                                                                                                                                                                                                                                                                                                        | Evidence                                                                                                                                               |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| **V** A check that could not run passes silently at the gate that releases. When git's history cannot be listed, the missing start files are left empty; only the post-change hook reads the reason, finalize and report-check say nothing, so the missing-start hold cannot fire. Read from the code, not replayed.                                                                           | `labkit/formats/area_state.py:733`; only reader of `history_unread`: `labkit/gates/hook_post_change.py:143`; `labkit/gates/registration_station.py:55` |
| **V** "May a run without a record have been the first measurement" has two rules. The registration station orders by the start files: a run started after a readable measurement is a warning. The report duty does not ask the order and blocks. The same run would warn in finalize and block in report-check. Read from the code, not replayed; possibly intended, then it is said nowhere. | `labkit/formats/area_state.py:1068`–`:1088`; `labkit/gates/registered_report.py:468`–`:490`                                                            |
| **V** Regrown: "has the area a readable measurement of this protocol" is spelled by hand beside `Measured.has_measured`, the home set on 2026-11-18. Equal today.                                                                                                                                                                                                                              | `labkit/run/start_check.py:178`; home `labkit/formats/area_state.py:221`                                                                               |
| **V** "Is this protocol exploratory" is decided again in the audit prompt, with the extra condition `run is not None`: without a run the prompt compares against the first measurement while the hold compares against the run's own text. **R**: further copies of the branch in `registration_hold.py:1278`, `standard_contract.py:202`, `protocol_check.py:1346`.                           | `labkit/gates/registration_station.py:59`; `labkit/gates/audit_prompt.py:940`                                                                          |
| **V** A field of the area state travels through positional calls: `_measured` takes 12 parameters, six of them `tuple[str, ...]` in a row, called at two sites with hand-written lists, one with two bare `()`. A swapped pair type-checks; missing starts read as unassigned starts would turn a hold into a warning.                                                                         | `labkit/formats/area_state.py:383`–`:396`, `:458`–`:479`, `:572`–`:585`                                                                                |
| **V** "A readable measurement that is no repeat" is written twice.                                                                                                                                                                                                                                                                                                                             | `labkit/formats/area_state.py:1033`–`:1039`; `labkit/formats/answering_run.py:444`                                                                     |
| **R** "The run is adopted" has two answers: `exploration_hold.adopted` is true while an adoption is pending, `registration_hold.declaring_protocol` is None then; both are used in one flow.                                                                                                                                                                                                   | `labkit/gates/exploration_hold.py:105`; `labkit/gates/registration_hold.py:1000`                                                                       |
| **R** Which name is a start file and which entry is a start mark: four spellings and two; the two index readers for runs and start files are twins down to the error sentence.                                                                                                                                                                                                                 | `labkit/formats/run_starts.py:101`, `:251`; `labkit/formats/area_state.py:1109`, `:1220`, `:1234`, `:1243`; `labkit/formats/evidence.py:612`           |

### What a user or agent is told

| Finding                                                                                                                                                                                                                                                                       | Evidence                                                                                                                                                                                      |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **V** The hook prints runs that started and never completed, whose directory stands, under "a run of … is gone … nothing brings its rows back but git"; an unreadable index and an unreadable start file land under the same heading.                                         | `labkit/gates/hook_post_change.py:179`, `:230`, `:252`–`:257`                                                                                                                                 |
| **V** A link to an exploration that resolves to no protocol or to several returns no finding: the same clean result as "no shared inputs". Whether another check reports it was not verified.                                                                                 | `labkit/gates/report_exploration.py:100`                                                                                                                                                      |
| **R** Which entry point tells which condition of a run is a hand-kept list per entry point (finalize, report-check, run start, hook); a contradicted binding and an unassigned unreadable record have no line in the hook. Matrix in the homes reader's report.               | `labkit/gates/registration_station.py:55`, `:92`; `labkit/gates/report_check.py:765`; `labkit/run/start_check.py:223`; `labkit/gates/hook_post_change.py:116`                                 |
| **R** The run start re-spells four sentences of the registration station, already in other words; the hook re-spells two; "bring the record back" is a constant and three variants; "restore the repository's missing objects" is two identical constants and three variants. | `labkit/run/start_check.py:274`–`:294`; `labkit/gates/hook_post_change.py:166`–`:176`; `labkit/formats/area_state.py:821`; `labkit/formats/evidence.py:546`; `labkit/formats/attempts.py:625` |
| **R** The holds for a check that could not run share one skeleton copied per hold; its closing clause stands six times in one module, once with another word. The two scope holds are near twins.                                                                             | `labkit/gates/registration_hold.py:832`, `:865`, `:898`; `:596`, `:721`                                                                                                                       |
| **R** The header of finalize's second station says "registration since the first measurement" also for an exploratory protocol, which is held to each run's own text and step.                                                                                                | `labkit/gates/finalize.py:1157`                                                                                                                                                               |

### Clarity

- **V** `Measured` and `AreaState` use the same field names for different things: `lost` (measurements only, a tuple / every kind, a dict), `started_only`, `conflicts` (sentences / pairs of source and protocol). (`labkit/formats/area_state.py:122`, `:142`, `:172` against `:304`, `:323`, `:327`)
- **V** In `state_of` the variable `gone` holds the runs that still exist, and `held` means "present in the file state". (`labkit/formats/area_state.py:665`, `:673`)
- **V** `station_changes` returns one bool for "confirmatory", "type undecided" and "first measurement untold". (`labkit/gates/registration_station.py:57`, `:63`)
- **V** `EXPLORATORY` is defined twice. (`labkit/formats/standard_contract.py:192`; `labkit/formats/exploration_link.py:38`)
- **V** `unstepped_holds` hides "differs from every first measurement" in `len(gaps) < len(registered) or not gaps`. (`labkit/gates/exploration_hold.py:244`)
- **R** `WithoutRecord` holds sentences in three fields and run ids in the fourth; its caller names the sentences `runs`. (`labkit/formats/area_state.py:957`–`:996`; `labkit/gates/registration_hold.py:919`)
- **R** Three readers answer "which run does the head adopt": one raises on a `[result]` that does not read, one returns None, one returns a run id or a sentence in one string. (`labkit/formats/protocol_block.py:783`, `:841`; `labkit/formats/answering_run.py:706`)
- **R** `_committed_registration` reads as a predicate and is true when something is missing; `scope_changes` documents its parameter `held` as what the area measured; `exploration_changes` takes 8 parameters, four derivable; `scope_now`'s `against` switches the baseline unnamed. (`labkit/run/start_check.py:347`; `labkit/gates/registration_hold.py:425`, `:1083`; `labkit/gates/exploration_hold.py:67`)

### Documentation

- **V** `TODO.md:9`, the paragraph a new session reads first, says `main` carries the exploratory workflow and, further on, that the workflow is on a branch and not in `main`; `TODO.md:3` gives the state as 2026-11-18.
- **V** `docs/workflow.md:24` gives the confirmatory lock only; the page names neither `type` nor a step, and a measurement does not start without `type` (**R**: `labkit/run/start_check.py:404`).
- **V** `docs/architecture.md:275` and the docstring of `state_of` (`labkit/formats/area_state.py:648`) say an unreadable start file raises `RunStartsError`; no reader raises it (`labkit/formats/run_starts.py:53`).
- **R** The two texts a stamped lab's agent reads name no start file, though its commit is a duty (`labkit/docs/agent-guide.md:99`, `labkit/templates/AGENTS.md.template:14`); `labkit/docs/agent-guide.md:77` says the values stay fixed after the first measurement without the exploratory condition of `:38`.
- **R** `README.md:229` and `:146` describe `[kept]` and `--kept` as a computation's only; since 0.33 every kind owes it. `README.md:152`–`:159` lists `protocol-fill` without `--builds-on`, `--step-id`, `--occasion`, `--explored-in`, `--data-counts`.
- **R** `CHANGELOG.md:18`, `:26`, `:28` (Unreleased) still say 0.32 is the standard read; `:56` names `protocol_history.patch_lost` for `runs.patch_lost`.
- **R** The docstring of `Run` gives an order of the start checks the code no longer has and names no start file (`labkit/run/runlog.py:418`–`:445`, `:7`–`:25`; the same in `docs/architecture.md:167`–`:169`). Smaller: `docs/architecture.md:38`, `:77`; `labkit/gates/registration_hold.py:155`, `:281`; `.githooks/checks:12` (16 slow files, 20 now); `docs/promise-block.md:125`; the status lines of `docs/notes/2026-11-14-exploratory-workflow-plan.md:3` and `docs/notes/2026-11-18-lost-first-measurement.md:25`.

Found equal (**R**, each opened): no `run-starts.tsv`, 26-hour rule or pre-rename name outside history; `docs/protocol-run-binding.md` whole; the layer table with all 13 new modules; the changelog entry for the start files with its ten functions; standard 0.33 against `run_starts.py` and `runlog.py`; all links and anchors of the first-reader pages; 92 of 97 hashes in `TODO.md` (the other five are named as another repo's).

### Size and line length

- 66 lines of the package exceed 120 characters (243 exceed 100 at 9ee71406); 20 of the 66 are in `labkit/tools/protocol_cuts.py` and `protocol_fill.py`, the longest 714 characters, text literals of form fields. `pyproject.toml` sets no line length and selects no length rule, so nothing holds this.
- 27 of 2312 functions exceed 100 lines; the longest are `main` in `labkit/tools/scaffold.py` and `labkit/probes/usability_command.py`. 20 functions take nine or more parameters: `findings.write` and `area_state.assemble` 15, `area_state._measured` 12.
- 22 modules exceed 1000 lines; `labkit/formats/area_state.py` grew by 877 lines since 2026-11-18.

### Small

**R** Replacing one table of a protocol's TOML block is written twice in two new modules (`labkit/tools/protocol_exploration.py:53`, `labkit/tools/protocol_step.py:88`). "Every first measurement, flattened" is written six times while `Measured.firsts` means something else. Three functions in `labkit/gates/registered_report.py:494`–`:514` only forward. `RunStartsError` subclasses `RunIndexError`, so a handler for the index also takes a start-file error. Eleven worktrees of this repo lie under `/private/tmp`, five prunable. `.githooks/pre-merge-commit`, `.answer`, `.claude/`, `.codex/` and the explainer plan under `docs/notes/` are untracked.

## How a hold, a field, a gate is added today

- **A gate**: one `check_*` function and one line in the entry point's station list. No duplication.
- **A field of a file on disk**: two to four places in one or two modules; a forgotten one is refused loudly.
- **A field of the area state**: eight to ten places in one module, positional; a swap between two neighbours of one type is silent.
- **A hold on a run's evidence** (observed on the missing start file): computed and threaded in `area_state`, its sentence and warning there, the hold as a copy of its sibling's skeleton in `registration_hold`, then one hand-written line each in `registration_station`, `registered_report` with `report_check`, `start_check`, `hook_post_change`, and `evidence` for the index's state — seven modules.

## Holding well

`registration_hold.untold_first_holds` (the order of the three holds, once, one caller); `area_state.assigned_to` and `_named` (which protocol a run without a record belongs to, with the conflicts from the same function); `run_starts.start_of` (one fallback for a start file that does not read); `area_state.last_committed`; the builders in `commands` and `ways_out`, through which every new hold's command goes; the run record's schema.

## Open points

1. Tell an unlistable git history at finalize and report-check, and hold where the missing-start check could not run.
2. Decide "may have been the first measurement" once for the registration station and the report duty, or state in one place that the report duty is meant to be stricter.
3. One function that turns an area's `Measured` into the findings every entry point tells, read by finalize, report-check, the run start and the hook; with it the sentences and the hold skeleton once.
4. Decide the workflow (exploratory or confirmatory) once per protocol and pass it on; `station_changes` returns it instead of a bool; one `EXPLORATORY`; one answer for "adopted".
5. Build `Measured` by keyword or from a small input record; rename the same-named fields on `Measured` and `AreaState`, and `gone` and `held` in `state_of`.
6. Give the hook a heading of its own for a run that started and never completed.
7. Report a link to an exploration that does not resolve to one protocol.
8. One documentation commit: `TODO.md:9` and `:3`, `docs/workflow.md`, the agent guide and the stamped `AGENTS.md` (start file, exploratory condition), `README.md`, the Unreleased section of `CHANGELOG.md`, the docstrings and status lines named above.
9. A line-length rule for the package, with the form texts of `protocol_cuts.py` exempt or wrapped.
10. A clarity reading of the eight modules no reader opened.

## Done 2026-11-19

Worked the same day in four parallel worktrees and merged, 20 commits up to 9195dadb; the full checks exited 0, run alone on the unchanged merged tree. Line numbers above are those of a3951e92 and no longer hold.

| Point | State                                                                                                                                                                                                                                                                        |
|-------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1     | Built: a history git cannot list is a blocker at finalize's registration station and at report-check's report duty (`registration_hold.unread_history_hold`). The run start still does not name it.                                                                          |
| 2     | Built as the author decided: the report duty reads the registration station's order (`WithoutRecord`); a run that provably started later warns at both, an unknown order holds at both, a lost run a result needs holds as before. A lost input-origin run was not replayed. |
| 3     | Not built, by the author's decision: the classification and its reasons belong in one place, the messages stay per entry point. [Plan](2026-11-19-shared-run-classification-plan.md).                                                                                        |
| 4     | Built: `protocol_history.workflow_registered` returns a `Workflow`; the station, the audit prompt and the hold read it. Without a run only the prompt compares, against the first measurement; kept, documented and tested.                                                  |
| 5     | Built: `Measured` and the area state are built by keyword; `Measured` has `lost_measurements`, `started_only_measurements`, `conflict_clauses`; `state_of` has `present` and `present_or_committed`.                                                                         |
| 6     | Built: the hook prints three headings (gone; started and never completed; does not read).                                                                                                                                                                                    |
| 7     | Built as a warning: no other gate tells such a link after the first measurement. Warning or blocker is the author's to decide.                                                                                                                                               |
| 8     | Done: 20 of 22 places by the documentation commits, the other two with the code that owns them; the changelog carries the wave's five changes.                                                                                                                               |
| 9     | Built: E501 at 120 characters for the package; the tests and the two form modules are exempt, six verbatim example lines carry a `noqa` with its reason.                                                                                                                     |
| 10    | Read: 30 findings in the eight modules, three that change a result, none releases a number silently. Not opened by the main session, not fixed; listed in `TODO.md`.                                                                                                         |

Readers' full reports, outside the repo and not kept: drift and homes as files in the session's scratchpad, the two clarity reports in the session's transcript.
