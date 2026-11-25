# Repo audit, 2026-11-25

State read: HEAD `d4ef078a` on `main`, 107 commits after `v0.115.0`. The audit reports; nothing was fixed.

## Ground truth

- HEAD runs. A fresh clone of HEAD with a new venv (Python 3.15.2, `pip install -e '.[dev]'`) passed `.githooks/checks full` with exit 0: ruff, ruff format and pyright clean, `4680 passed, 1 skipped, 7880 subtests passed in 897.46s`. The run was not alone on the machine (a second full check ran in the main checkout from 17:11), so the 897 s is no timing.
- The working tree was not checked: it held open changes of another session in five test files and `TODO.md`.
- Size: `labkit/` 172 files and about 77 000 lines in six directories (formats 45 modules, gates 31, checks 19, tools 19, run 16, probes 9); `tests/` 282 files.
- Who read what: a `code-clarity` reader read the package diff since `v0.115.0` (46 files; five files whole, the rest in the diff with targeted reads); one reader checked prose against code (README, AGENTS.md, `docs/workflow.md`, the justfile, the hooks and the CHANGELOG's Unreleased section whole; `docs/architecture.md` and the agent guide in part); one reader searched `labkit/**/*.py` for doubled logic mechanically and read the hooks, the justfile and one template pair by hand. Not read: the tests, `docs/promise-block.md` and `docs/protocol-run-binding.md` beyond links and names, most templates. Every finding below was opened at its lines before it was written here.

## Findings with an effect

| No  | Finding                                                                                                                                                                                                                                  | Where                                                                                                                                             |
|-----|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| 1   | Messages printed in a lab repo name `docs/workflow.md` and `docs/promise-block.md`; the package ships neither (`pyproject.toml:65`), and `labkit-init` stamps no `docs/`.                                                                | `labkit/checks/run_record_check.py:316`, `labkit/formats/promises.py:400`                                                                         |
| 2   | The shipped standard names two contracts by a path on the author's machine (`~/projects/labkit/docs/…`).                                                                                                                                 | `labkit/docs/standard.md:96`, `labkit/docs/standard.md:319`                                                                                       |
| 3   | The shipped standard names the house command `lib exp` where the package's command is `labkit-init exp`, and calls the area tests preflight's "fifth check"; they are station 8.                                                         | `labkit/docs/standard.md:180` against `labkit/gates/preflight.py:254`                                                                             |
| 4   | The two preparation skeletons end differently: the estimator skeleton records labelled and gold counts, the LLM skeleton only `n_items`, so `protocol-fill --data-counts` writes no labelled or gold counts for an area stamped from it. | `labkit/templates/prepare-script.py.template:146`, `labkit/templates/prepare-estimator-script.py.template:120`, `labkit/checks/data_counts.py:77` |
| 5   | The pre-run hook resolves the project directory itself and stops after the environment variable; `hook_session.project_dir` goes on to the event's `cwd` and the process's.                                                              | `labkit/gates/hook_pre_run.py:319` against `labkit/gates/hook_session.py:52`                                                                      |
| 6   | `test_inventory --reach FILE` exits 0 without writing the file when the suite is green and a process traced no exit; one stderr line says so.                                                                                            | `labkit/tools/test_inventory.py:1052`–`:1078`                                                                                                     |
| 7   | `site_outcome`'s docstring gives an order the code does not follow: a site without `rule=` and with a passed-in evidence kind reads `variable`, not `refused`.                                                                           | `labkit/tools/check_inventory.py:500` against `:523`–`:527`                                                                                       |
| 8   | The release recipe reads the version line with a stricter pattern than the package: a line the package reads can be one `just release` refuses as "no version line".                                                                     | `justfile:85` against `labkit/tools/repo_check.py:73`                                                                                             |

## Doubled homes

| Logic                                                                        | Occurrences                                                                                                                                                                             | How they differ                                                                                                         |
|------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
| What a run saw at its start (no commit, patch gone, commit not held)         | `labkit/formats/protocol_then.py:142`, `labkit/formats/run_code.py:58`                                                                                                                  | diverged: only `code_then` knows a run gone from the tree; `as_measured` reads the patch by hand whether dirty or not   |
| A second reviewer's verdict file and the command's tail                      | `labkit/formats/reviews.py:172`, `labkit/formats/report_reviews.py:547`; `labkit/gates/decision_review.py:546`, `labkit/gates/claim_review.py:392`, `labkit/gates/report_review.py:253` | near: table, row and binding names differ; the refusal for a missing `again` names the last reading version in one only |
| A main catches `console.Refused` and returns 2                               | twelve mains, e.g. `labkit/gates/finalize.py:1418`, `labkit/gates/preflight.py:771`, `labkit/tools/adopt.py:130`; `labkit/tools/run_diff.py:35` lets it pass                            | identical four lines; `console.exit_with` (`labkit/formats/console.py:145`) does the same once                          |
| The keys of `config.json`                                                    | `labkit/run/runlog.py:655`, `labkit/formats/runs.py:1279`                                                                                                                               | identical list kept twice; the strict reader makes a drift fail at the first read                                       |
| Hook event to labkit action                                                  | `labkit/gates/install_hooks.py:180`, `:276`, `labkit/gates/codex_hooks.py:20`                                                                                                           | same three pairs, three spellings                                                                                       |
| The word `"no-script"`                                                       | `labkit/run/provenance.py:589`, `:596`, `:604`, `:606`; `labkit/checks/run_record_check.py:384`, `:469`                                                                                 | no constant; a mistyped word compares false without an error                                                            |
| The metric keys labkit writes                                                | `labkit/run/runlog.py:760`, `labkit/run/lanes.py:259`; listed in `labkit/checks/recheck.py:121`                                                                                         | the list stands in a check, not beside the writers                                                                      |
| Smaller: pin file names, the commit width `[:12]`, `str(exc).strip(chr(39))` | `labkit/probes/usability.py:602`; 34 sites in 16 modules; six sites in the review gates                                                                                                 | identical words without a constant or helper                                                                            |

Solved well: one check script behind both hooks and `just check` (`.githooks/checks`); console commands read from the installed metadata (`labkit/formats/console.py:163`); git started in one place (`labkit/formats/repo.py:1097`, held by `tests/test_one_home.py`); one reader for comment blocks (`labkit/formats/comment_blocks.py:131`); no regex literal occurs twice in the package.

## Clarity

- `answer_reading` names a path argument, a dataclass attribute, a module and a file (`labkit/run/runlog.py:489`, `:548`).
- `DERIVED_RUN_CONTRACT` says a derived run makes no model calls; calls are refused only for one that declares its answer reading (`labkit/formats/runs.py:109`, `labkit/run/runlog.py:947`).
- Finalize's station 4 is labelled "first half", "second half" and "third part" (`labkit/gates/finalize.py:537`, `:624`, `:559`).
- `check_answer_reading` skips the answer-file comparison when a protocol text cannot be read back; its docstring names two other skips, not this one (`labkit/gates/finalize.py:596`, `:605`).
- A blocker for an unreadable `answer-reading.json` also offers "derive a run that declares the module"; the docstring offers it only beside a run that declared none (`labkit/checks/run_record_check.py:215`).
- `check_overview --check` prints "is current" for a page whose reach columns are as old as the last traced run (`labkit/tools/check_overview.py:220`).
- Three modules hold several jobs: `labkit/formats/findings.py` (2530 lines: record format, decision rules, evidence requests, file listing), `labkit/formats/repo.py` (names, argparse helper, links, git), `labkit/formats/runs.py` (record, time, call log, lineage).

## Documentation

- `AGENTS.md:36` and `.githooks/checks:11` give 81 s and 383 s from 2026-11-10 with 13 slow files; `TODO.md:47` records 837 s, and 26 files carry the mark.
- `TODO.md:18` names only the repairs of 2026-11-24 as unreleased; Unreleased holds three Breaking and three Added entries.
- `labkit/formats/answer_reading.py:18` shows `"labkit": "0.116.0"`; a run on HEAD writes 0.115.0, the version that does not know the file.
- `docs/workflow.md:193` says "a labkit before this release" without a version.
- `docs/architecture.md:423` describes the audit record without its replaced decisions.
- `TODO.md:11` links an anchor that needs two hyphens at the dash.

Without finding: every name the Unreleased section cites exists; every flag named in README, AGENTS.md, the docs and the message strings stands in its command's help; no dead link in the entry documents; `python -m labkit.formats.rules check` reports 0 problems.

## Open points

1. Shipped texts that point outside the package (findings 1 to 3): reword them to name the labkit repository or ship the two contracts.
2. The two preparation skeletons (finding 4): decide whether the LLM skeleton records the same counts.
3. The pre-run hook's project directory (finding 5): use `hook_session.project_dir`.
4. The three tool findings (6 to 8): exit status of `--reach`, the docstring order of `site_outcome`, one pattern for the version line.
5. One home for "what a run saw at its start".
6. One format for the two reviewer verdict files.
7. The twelve `Refused` catches: one rule for a main called directly.
8. Constants for `"no-script"`, the metric keys, the pin file names, the commit width.
9. The clarity points on the answer reading (names, contract sentence, station labels, the two docstrings).
10. The documentation points.
11. Splitting `findings.py`, `repo.py` and `runs.py` by job.

## Decided and built, 2026-11-25

The author released open points 1, 3 and 4. Built on `main` after `d12d7622`, unreleased (CHANGELOG, Unreleased, Fixed):

- Findings 1 to 3: the two messages name `docs/workflow.md` and `docs/promise-block.md` as files of the labkit repository, the first also `labkit-next --guide`, step 4, which a lab repo has; the standard names the two contracts the same way, `labkit-init exp`, and preflight's area-tests station without a number.
- Finding 5: the project a session names has one function, `hook_session.named_project_dir`; `project_dir` adds the working directory to it. The pre-run hook keeps its behaviour and uses the first: outside a repository the walk to an area ends at the named project and nowhere when none is named, since the working directory may be the area's `scripts` folder. Taking `project_dir` there would have ended the walk below the area.
- Finding 6: `test_inventory.exit_status` — exit 1 when the reach file asked for was not written.
- Finding 7: `site_outcome` follows its docstring; no site of the package is of the kind, the overview page is unchanged.
- Finding 8: the release recipe imports `repo_check.PYPROJECT_VERSION_RE`. Tried with `just release 9.9.9`, which passed the version line and was refused at the CHANGELOG heading, before any write; a release itself was not run.

Open points 2 and 5 to 11 stand.

## The derived run's contract: what is prevented, seen afterwards, or left to the audit

The README, `runs.DERIVED_RUN_CONTRACT` and runlog's docstring say that a derived run makes no model calls. Read from the code; no run was started for this.

| Case                                                                     | Before the call                                                                             | At finalize                                                                                                                                         |
|--------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| declares `answer_reading`, opened with `with runlog.run(…)`              | every call through `llm` raises `CallRefused`, in every thread (`labkit/run/runlog.py:947`) | as the rows below                                                                                                                                   |
| `derived_from` alone, calls through the answer cache (`llm_cache.Cache`) | nothing                                                                                     | blocker: a line of `llm-calls.jsonl` that asked the model, or an answer stored outside any run (`labkit/checks/run_record_check.py:1253`)           |
| `derived_from` alone, calls `llm.complete` without the cache             | nothing                                                                                     | nothing: no call log is written; the metrics warning stays silent because the parent recorded its models (`labkit/checks/run_record_check.py:1674`) |
| any derived run, a model reached by another client (own HTTP)            | nothing (`labkit/run/llm.py:85` says so)                                                    | nothing                                                                                                                                             |
| a `Run` built and never entered                                          | nothing (`llm.refusing_calls` is entered in `run.__enter__`)                                | as its row above                                                                                                                                    |

The start check of a derived run holds its parent only: completed, no repeat (`labkit/run/start_check.py:847`). A derived run records no models of its own (`labkit/run/provenance.py:689`), so its record shows no trace of a call either. The audit prompt does not name derived runs (`labkit/gates/audit_prompt.py`: no occurrence of the word), and the agent guide names the contract only for the declared correction; the auditor is not asked whether a derived run called a model.

So the sentence holds as a guarantee for one kind of derived run, is seen afterwards for a second, and for a derived run without declaration that calls `llm.complete` directly it is neither prevented nor seen nor asked of the auditor. The design note of the declared correction states the same limit for the call log (`docs/notes/2026-11-24-analysis-correction-on-unchanged-answers.md`, the row "no model call through labkit").

Two ways to make code and sentence agree, the author's decision:

1. The code follows the sentence: runlog refuses model calls for every derived run, declared or not. One condition changes (`labkit/run/runlog.py:947`). A stored answer read in a replay never reaches `llm` (`labkit/run/llm_cache.py:305`), so a derived run that replays keeps working; a derived run that asks a model today ends with `CallRefused` — a break to announce. Another client stays unseen.
2. The sentence follows the code: the README and the constant say that the contract is refused beforehand only with a declared answer reading and seen afterwards only through the answer cache.

