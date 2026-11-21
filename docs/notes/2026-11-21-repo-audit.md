# Repo audit: clarity, drift, doubled homes since the prompt binding (331869e1, 2026-11-21)

Follows the [audit of 2026-11-19](2026-11-19-repo-audit.md) (a3951e92) and the [audit of 2026-11-18](audit-2026-11-18.md); what they list is repeated here only as "still open". Scope: the 97 commits since a3951e92 (package and tests: 96 files, +6022, −868), plus the modules the 2026-11-19 audit did not read (`run_code.py`, `input_origins.py`, `protocol_step.py`, `run_diff.py`, `scope_sha.py`, `runs.py`, `protocol_fill.py`, `params.py`). Three readers in parallel: clarity (`code-clarity`, area mode), prose against code, one home per logic. **V** marks a finding the main session opened at the lines named or reproduced, **R** one that stands on the reader alone. Line numbers are those of 331869e1. The audit reports; nothing was changed.

## State audited

HEAD 331869e1 (v0.114.0 + 23 commits), extracted with `git archive` into a scratch directory (`git init`, one commit, no remote, no tags) with a fresh `.venv` (`pip install -e '.[dev]'`) and an empty home directory. `.githooks/checks full` there: ruff, ruff format and pyright exit 0; pytest exits 1 — 4247 passed, 1 skipped, 7 failed, 31 errors in 783 s. All 38 come from two causes of that scratch setup, not of HEAD: no release tags (`tests/test_release_tags.py` skips only in a shallow clone) and no labkit line in `pip freeze` of an editable install from a repository without a remote (`usability`, which `test_repair_paths.py`, `test_sab_cases.py`, `test_usability.py` and `test_workflow_example.py` reach). The five files rerun in a real `git clone` of 331869e1 (139 tags, fresh `.venv`, empty home): 107 passed, exit 0. The whole suite was not rerun in the clone.

The package is 72,881 lines in 137 modules (71,233 on 2026-11-19), the tests 89,173 lines in 241 files.

## Overall

The structure holds where `tests/test_one_home.py` or a refusing parser binds it: none of its 70 shapes has regrown, every git call goes through `repo.git_run`, and the new public `recheck.answering_run_dir` is the existing run choice with no rule of its own. No finding changes a gate's verdict on correct input.

The dominant problem class is still **regrowth beside a home, where no test names the shape**: `protocol-fill` keeps six hand-written lists of which flags exclude each other, and one of them already lets a flag drop silently; the new Prompt-block reader and writer copy each other's loop and disagree with the older static reader on an unclosed block. The second class is one crash path at a station whose contract says it never stops a later station.

## Findings

### Effect on what a user or agent sees

| Finding                                                                                                                                                                                                                                                                          | Evidence                                                                                   |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| **V** Preflight's station 5 raises `FileNotFoundError` when a promise declares a scope file that is missing: `scope_stamp_line` catches only `PromiseError` and `ValueError`. Reproduced at the function (fixture of `tests/test_scope_sha.py:311`); no catch in `preflight.py`. | `labkit/gates/preflight.py:591`, `labkit/formats/scope_sha.py:529`                         |
| **V** `protocol-fill --list --prompts` runs `--list` and drops `--prompts` without a word: the dispatch is a first-match chain, and none of the six pair checks pairs these two. **R**: the homes reader ran it on a scratch copy, exit 0.                                       | `labkit/tools/protocol_fill.py:636`, `:638`; checks `:953`–`:1101`                         |
| **V** Two readers of the Prompt field disagree on a block that never closes: the static check's reader lets it run to the end (`markdown.fence_spans`), the run start's reader refuses it. The static drift check can pass where the run start refuses.                          | `labkit/formats/protocol_check.py:1628` (`prompt_blocks`), `:1714` (`named_prompt_blocks`) |
| **R** Preflight's audit station prints "none recorded" after an unreadable audit record, beside the blocker that names the read failure.                                                                                                                                         | `labkit/gates/preflight.py:563`                                                            |
| **R** `labkit-params` refuses a run choice that carries a blocker even with a run chosen; finalize takes the same choice and goes on with that run.                                                                                                                              | `labkit/tools/params.py:388`, `labkit/gates/finalize.py:281`                               |
| **R** A run with a recorded commit read outside a repository is told "recorded no commit".                                                                                                                                                                                       | `labkit/formats/run_code.py:61`                                                            |

### Doubled homes (new since a3951e92 unless marked)

| Logic                                                                         | Occurrences                                                                                                                                                                                    | Effect if they diverge                                                |
|-------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| **V** Which `protocol-fill` operations may stand together                     | `labkit/tools/protocol_fill.py:953`, `:973` (both new), `:994`, `:1020`, `:1044`, `:1069`; dispatch `:628`                                                                                     | a new flag missed in one list is dropped silently (the finding above) |
| **V** Walking the named Prompt blocks, reader and writer                      | `labkit/formats/protocol_check.py:1730`, `labkit/tools/protocol_result.py:481`                                                                                                                 | a change to block naming lands in one of the two                      |
| **R** Refusal sentence for a template with an odd line separator              | `labkit/formats/protocol_check.py:1797`, `labkit/tools/protocol_result.py:363`                                                                                                                 | two wordings of one refusal                                           |
| **R** Every first measurement, flattened by hand (2026-11-19: six, now seven) | `labkit/gates/registration_hold.py:323`, `:365` (new), `:538`, `:1309`; `labkit/gates/exploration_hold.py:219`; `labkit/formats/exploration_link.py:153`; `labkit/checks/protocol_runs.py:519` | a change to what counts as a first measurement misses a site          |
| **R** "Is this file a protocol"                                               | home `labkit/formats/repo.py:231` (`PROTOCOL_GLOB`); `labkit/formats/protocol_then.py:95` (new regex from the glob), `:63`; `labkit/gates/audit_decisions.py:251`                              | `protocol_then.py:63` accepts a name without `.md`                    |
| **R** Reading `models.toml` (older, not named before)                         | `labkit/run/llm.py:240`, `:269`, `:305`, `:331`, `:353`; variant `:220`                                                                                                                        | five copies of one read; the variant finds the file by another route  |

Still open from 2026-11-18/19 (one line each): the TOML head-table replacement twice (`labkit/tools/protocol_exploration.py:53`, `labkit/tools/protocol_step.py:88`); the table-header regex twice (`labkit/formats/findings.py:1911`, `labkit/formats/protocol_block.py:186`); forwarders in `labkit/gates/registered_report.py:496`–`:540`.

Solved well: `recheck`'s one-file forms are thin wrappers over the multi-file forms (`holds` → `holds_outputs`); the workflow decision has one home (`protocol_history.workflow_registered`, read by the hold and the audit prompt); history reads go through `area_state.last_committed`.

### Clarity (where a newcomer misreads)

- **R** `labkit/formats/scope_sha.py:5` — the docstring lists what the stamp covers and says an unchanged stamp means the code is the same; `area_snapshot` (`:545`) also hashes the predecessor and exploration bases.
- **V** `labkit/tools/protocol_step.py:13` — "Writes the protocol file and nothing else"; the module builds the text and writes nothing. It also catches `SystemExit` from `start_check.require_step_basis` (`:50`).
- **R** `labkit/gates/finalize.py:66` — station 5 is described as "fields still holding a placeholder"; it also blocks repeated fields, hand-typed data counts and README route findings.
- **R** `labkit/gates/preflight.py:149` — `area_tests` runs pytest for up to 300 s; the name reads as a lookup.
- **R** `labkit/tools/protocol_fill.py:628` — the `_run_mode` docstring omits `--freeze`; the precedence of the two dispatchers is not written down.

### Documentation (prose that no longer holds)

- **V** `.githooks/checks:13` says 22 files carry the slow mark; 23 do (`tests/test_recheck_outputs_scenario.py` added since).
- **V** `README.md:269` presents `recheck.holds_outputs` as an integration entry; `CHANGELOG.md:9` and the public API say only `recheck.answering_run_dir` is public.
- **V** `CHANGELOG.md:15` writes `answering_run` where the function is `answering_run_dir`.
- **R** `docs/architecture.md:38` — the list of modules with pure checks leaves out `report_exploration` (`unresolved_link_hold`).
- **R** `AGENTS.md:34` — "~1½ min instead of ~6½"; the last recorded logs show 128 s and 1063 s (single runs, load unknown).

### Small things

- An empty directory whose name holds line breaks (`CHANGELOG.md⏎docs/architecture.md⏎docs/notes`, Oct 27) stands in the repo root; git does not see it (empty).
- `.githooks/pre-merge-commit` is untracked: written by `labkit-hooks install` 0.113.0 into labkit's own hook directory; other clones lack it.
- `docs/` holds eleven `audit-*.md` files from 2026-10-15 to 2026-11-18; since 2026-11-19 audits go to `docs/notes/`.
- `CHANGELOG.md` is 657 kB, `README.md` 61 kB.

## Open points

1. Catch the missing scope file at preflight's station 5 (warn "cannot stamp"), with a test.
2. One table of `protocol-fill` operations and their allowed companions, checked once, in place of six lists.
3. One Prompt-block walker for the static reader, the run-start reader and the writer, with one rule for an unclosed block.
4. Fix the five prose lines (slow-mark count, README `holds_outputs`, CHANGELOG name, architecture list, AGENTS timing) in one commit.
5. Fix the five clarity docstrings/names in one commit.
6. Merge the older doubled homes (`models.toml` read, flattened first measurements, protocol-name test) and add their shapes to `tests/test_one_home.py`.
7. Remove the stray empty directory; commit or delete `.githooks/pre-merge-commit`; move the eleven `docs/audit-*.md` into `docs/notes/`.
