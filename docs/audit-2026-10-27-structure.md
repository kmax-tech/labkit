# Audit 2026-10-27 (third) — instructions, drift, homes, structure

*HEAD `2847c1e`, after the handover fixes and the workflow review. Five
readers in parallel: instructions (a stamped scratch lab, every kind at
both costs, the real error path run without a model call), drift (an AST
check of every backticked name in the docs, verified on a known-gone
name first), homes, structure, and code clarity on the day's diff
(`c7b1f8d..2847c1e`). The rows of
[audit-2026-10-27.md](audit-2026-10-27.md) and
[audit-2026-10-27-handover.md](audit-2026-10-27-handover.md) are not
repeated; one still open is named by its id. Evidence: **V** verified
here (lines opened or run), **RR** the reader ran it, **R** read. The
rows describe the state audited; what was done stands under "State" at
the end.*

## Ground truth

- Tree clean; suite green at `2847c1e` (2114 passed, 1 skipped); ruff,
  format, pyright clean; `rules check` 0 problems.
- `labkit/` 36.6k lines; formats 12.1k (23 modules), gates 7.3k (9),
  run 5.3k, checks 4.4k, tools 4.2k, probes 3.2k; 17 `noqa: C901`
  baselines. Largest: `gates/report_check.py` 2092, `gates/audit.py`
  1765, `formats/findings.py` 1758, `tools/scaffold.py` 1429.

## I. Instructions — what a stamped agent is told

| id | Finding | Ev. |
|---|---|---|
| I1 | A4 still open and the instructions lead into it: at `low` the start gate checks the registration is *written* (`run/start_check.py:132-143`), not committed; the run starts uncommitted, the script prints the adopt command, `finalize` is clean, and adoption is refused for good ("was not committed at the first measurement … nothing stood before the number") with no next step; `--findings` then says "no audit record yet" — a circle. | RR (V code) |
| I2 | No stated exit before the first audit: AGENTS.md sends a stuck agent to "the area's printed workflow", printed once at stamping (re-stamping refuses); `--handover` works on a never-run area (exits 0, empty evidence) but nothing says so. | RR |
| I3 | Every "next" printed after a run skips the analysis audit, its decisions and the Conclusion: the skeleton prints the adopt command (`templates/measure-quick-script.py.template:121`, estimator `:566`), finalize says adoption follows "once this finalize is clean" (`gates/finalize.py:158`); AGENTS.md orders audit → decide → Conclusion → adopt. | RR |
| I4 | Whether the analysis audit is owed at `low` depends on the page: the skeleton (`measure-quick-script.py.template:8-10`), the standard (`labkit/docs/standard.md:462`) and the field guide say "when the number is promoted"; AGENTS.md and `--contract` say release at low requires it. | R (refusal RR) |
| I5 | compute with `--model`: `[model] number_describes` is a MUST, but `protocol-fill` cannot set it (`tools/protocol_fill.py:156-161` HEAD_KEYS) and `--list` does not show it. | V |
| I6 | No tool sets `frozen` or `preflight_audit` (not in HEAD_KEYS), and nothing says to edit the head by hand, while AGENTS.md warns against "editing records". | V |
| I7 | The prompt skeleton's `--show`/`--probe` pass on a missing items file ("to measure: 0 of 0", exit 0): `batch.Store.records` returns `[]` for a missing file (`run/batch.py:386-387`) read by `run/lanes.py:275`. | V code, RR run |
| I8 | Graduating an exploration prints `labkit-init exp NAME --kind …` without `--repeat-cost` (`tools/scaffold.py:406`) and stamps the high form with a placeholder cost. | RR |
| I9 | The high form asks for `Data profile`, `Model I/O`, a Prompt block, `--show`/`--probe` and a resolution check without a model and, for compute, without a criterion (`templates/experiment-protocol.md.template:136-148`; the cut tags filter only the low cut, `formats/protocol_check.py:100-102`) — C2 of the first register, still open in the template. | RR |
| I10 | The area README says `runlog .` and `labkit-params .` (`tools/scaffold.py:361-362`); from the root, as AGENTS.md asks, `runlog .` accepts the repo as an area and `--wait` reads a running measurement as idle (exit 0): `repo.area_path` returns any existing directory (`formats/repo.py:97-99`). | V code, RR run |
| I11 | "Raw output" has two jobs and three destinations (probe rows into the protocol; raw answers into the area test; after the run in `--list`). | RR |
| I12 | Small: finalize passes on intent-check's "--metrics FILE" (finalize has none, `checks/intent_check.py:397`); compute areas are told "evaluate() no longer holds its resolution check" (`gates/finalize.py:414`); "no analysis audit saw the area … a change after the audit owes a new one" before any audit (`formats/findings.py:1450-1454`); `--change-kind` compute+model → fit writes "no model call" beside `[model] alias`; the fields each kind's "Next" lists differ from AGENTS.md's "every kind"; `labkit-init lab` omits the `requirements.lock` step AGENTS.md asks for. | RR |

## K. Code clarity — today's diff

| id | Finding | Ev. |
|---|---|---|
| K1 | A malformed handover record hides every other gap of the area: `attempts.area_gaps` re-raises its `HandoverError` as `AttemptError` (`formats/attempts.py:452-456`), and `area_integrity` turns that into one line, dropping the journal gaps already found. | V |
| K2 | `report_check.hold_declared` catches only `UnicodeError` around `state_text` (`gates/report_check.py:2022-2026`); the tree branch's `OSError` (a permission error) now escapes as a traceback instead of exit 2. | V |
| K3 | `handovers.evidence(staged=True)` reaches `repo.indexed_blobs`, which raises `GitError` (a `RuntimeError`) for an unmerged or link entry; `mismatch` catches `HandoverError, OSError, UnicodeError, BlockError` (`formats/handovers.py:577`) — the pre-commit ends in a traceback. | V |
| K4 | `runlog start` exit 0 means "the run named" and "ended without a run"; a new directory of a concurrent start is taken as this one's (`run/runlog_command.py` `_await_run`). | R |
| K5 | `preflight`: when a handover record of another area does not read, its deferred findings are told "set aside for later work" — the opposite claim (`gates/preflight.py:418-427`); `r.findings.index(f)` picks the first of two equal findings (also `gates/audit.py`, `gates/report_check.py`). | V |
| K6 | The estimator template reads `KIND` from the protocol head at import (`templates/measure-estimator-script.py.template:97`); an absent kind is "the most a kind owes" for `--contract` but a `ValueError` in `measure`. | V |
| K7 | Same template: `measure()` with the module-level `CONFIG` and a non-empty `PREDICTOR_FILES` says "predictor dependencies changed since the config snapshot" (`:281`) though nothing changed — the snapshot was never taken. | V |
| K8 | `protocol-fill --handover` writes record, protocol, report in that order; a failure at the report leaves the first two written and the refusal does not say so (`tools/protocol_fill.py` `_handover_file`). | R |
| K9 | A current handover silently drops every acknowledged loss at the stop (`gates/claude_hooks.py` `undecided_blockers`): a pass reads "nothing wrong", not "loss acknowledged". | R |
| K10 | `--findings`' docstring says "Exit 2 on an evidence error, else 0" and has a garbled sentence; the code also exits 2 on a failed call; with `--record` area-wide errors still force 2 (`gates/audit.py:1599-1601`, `:1651`). | V |

## D. Drift — prose against code

| id | Finding | Ev. |
|---|---|---|
| D1 | `docs/architecture.md:249` names `handovers.valid`; the gate calls `handovers.acknowledgement` (`gates/claude_hooks.py:964`); `valid` has no caller in labkit. | V |
| D2 | `docs/architecture.md:212` "runs along six links" — the chain table has eight. | V |
| D3 | README's command list (`README.md:245-250`) has no `protocol-fill … --handover` line and shows `protocol-check --contract` without the optional protocol; the **estimator** term (`:329`) says "fitted", while a local apply uses it unfitted. | V |
| D4 | `docs/notes/2026-10-27-handover-recovery.md:18-21` and `CHANGELOG.md:371-377` say `--findings` refuses with no audit and offers the handover only beside a BLOCKER or an evidence problem; since `0667f0a` a failed call does so too. The `--findings` help, README, workflow and template say "if the first audit failed", the code's condition is per mode, code and promises. | V |
| D5 | `CHANGELOG.md:716` names `report_review.after_draw`, removed in `5e1354f` with no entry. | V |
| D6 | Docstrings of an earlier form: `report_check` module (`:92`, `index_text`), `findings.py:94` ("a note in the Answer"), `attempts.area_gaps` (`:426-432`, omits the handover losses), `audit._check_args` (`:1465-1468`, four modes of five), `protocol_fill._run_mode` (omits `--discuss`), `audit` module usage (`:7-8`), `runlog start` refusal usage lines (`run/runlog_command.py:282,287`) and the `runlog` epilog (`:345-346`). | V (sample) |
| D7 | `docs/architecture.md:395` gates row for `claude-hook undecided` names BLOCKERs only; the hook also holds lost or unreadable evidence. | R |
| D8 | `--contract` without a protocol prints five rows; a high computation and a local apply have none (`formats/protocol_report.py:256-279`). | R |

## S. Doubled homes

Still open from the first register, D: minute stamp, answer-line
grammar, prompt assembly, mode names, area test file name, digest of
named contents, flock helper, throwaway flags. New or newly confirmed:

| id | Logic | Occurrences | Home |
|---|---|---|---|
| S1 | The report comment-block scanner and writer, written twice — the handover block a near copy of the discussion block, already diverged (only one handles an empty report) | `checks/report_blocks.py:367-467`, `formats/handovers.py:353-433`, append-at-end a third time `report_blocks.py:165-170` | one `<!-- labkit KIND` scanner/writer in `formats` |
| S2 | Printed commands by hand, one wrong: `--into` names the protocol relative to the report but the report relative to the repo — the printed command fails from the root (RR) | `gates/report_check.py:1459`, `checks/report_blocks.py:222,229`; `protocol-fill {name} kind=…` with a bare name `run/start_check.py:149`; `discuss_command` in `report_blocks.py:306`, not `repo`; `labkit-audit {rel}` `tools/scaffold.py:1175`; `runlog start` `scaffold.py:1274`, `start_check.py:507` | `repo` builders |
| S3 | "Is this a held report place": `held_place` beside three hand copies; the handover accepts `.MD`, report-check holds only `.md` | `gates/report_check.py:1168-1175,1264-1268,1328,1944-1947`; `formats/handovers.py:286` | `held_place` |
| S4 | A completed primary parent run, the same four steps | `run/runlog.py:264-283`, `run/start_check.py:401-420` | `answering_run` |
| S5 | Audit mode vocabulary and kind spelled as literals | `gates/audit.py:136,151-152`, `formats/findings.py:161,573,578,…`; `tools/protocol_cuts.py:483,487,496`, `tools/scaffold.py:598,1193,1233,1242` | `findings.MODES`, `standard_contract.*_KIND` |
| S6 | Run record file names without constants (`config.json`, `completion.json`, `outputs.json`) | `formats/runs.py:132,277,359,420`, `run/runlog.py:521,614,629`, `formats/scope_sha.py:569` | `runs` |
| S7 | Area-test result shown twice; the 10-23 B1 fix landed in one | `gates/finalize.py:389-416`, `gates/preflight.py:495-519` | one renderer |
| S8 | "ref → commit" and "file at a revision" asked of git outside `repo` | `tools/scaffold.py:212-215`, `run/provenance.py:154-157`, `tools/repo_check.py:124,170` | `repo` |
| S9 | `core.hooksPath = .githooks` set in two places; `.githooks` spelled 6× | `tools/scaffold.py:1019-1028`, `gates/install_hooks.py:262-266` | `install_hooks` |

`tests/test_one_home.py` catches none of: the minute stamp `%H-%M`,
`labkit-audit {`, `protocol-fill {…} --into` / `kind=`, `kind ==
"apply"`, `"config.json"`, the `===== {label}` prompt join, `"runs"`
in a set, git through `git_run` outside `repo`, the grade alternation
in a regex (RR: each copy shown unmatched).

Solved well: what a tier owes (`standard_contract.lane`, held in the
templates too); printed decisions and open BLOCKERs (one builder each,
rules that bite); the stop budget derived from the hook timeout.

## M. Structure

| id | Finding | Ev. |
|---|---|---|
| M1 | The release gate loads the LLM stack: `import labkit.gates.report_check` (the pre-commit, the stop) pulls 49 modules, `llm` and `llm_backends` among them, through `audit` (`HANDOVER`, `register_anew`, `earlier_of`), `decision_review` and `report_review`. | V |
| M2 | Three import cycles hidden by local imports: `runs` ↔ `protocol_block` (`runs.py:850`, `protocol_block.py:36`); `scope_sha` ↔ `promises` ↔ `answering_run` (`scope_sha.py:185,559`); `audit` ↔ `decision_review`/`report_review` (`audit.py:1498,1510`; the reviewers use the private `audit._report_room`). Nine more local imports have no cycle behind them (e.g. `handovers.py:280`, `protocol_cuts.py` four times); `provenance.py:309` sits inside `except Exception`. | R |
| M3 | `report_check` is two modules: the protocol release stations (to `report_check` at `:983`) and report discovery/holding (`:1106-2052`), joined only by `hold_declared`; a cut reduces coupling. `audit` mixes prompt assembly, follow-up, parsing, the model call, the ways out and the CLI; only the ways-out texts and shared prompt pieces would reduce coupling if moved. | R |
| M4 | Check, file access, display apart — broken where the hooks scrape printed output (`gates/claude_hooks.py:386` captures `preflight_area`'s stdout, which has no `Findings` parameter unlike `finalize_area`; `:520-524` rewrites `protocol_report.main`'s text); `start_check` mixes returned refusals with `SystemExit`; `runlog.reindex` and `usability_score.score` compute, write and print; pure functions named `write_*` (`handovers.write_handover_block`, `report_blocks.write_block`, `write_discussion`). | R |
| M5 | `formats/protocol_report.py` is a command (47 prints, `main`, `cli`) in layer 1 importing doctrine. | R |
| M6 | Dead or nearly dead: no caller `followup.origins_of`, `lanes.ids_of`, `protocol_reading.terms_judge_prompt` (named in a comment only); parameters never passed (`findings.area_records(staged)`, `report_check.refused_link(index_links)`); forwarders `report_check.index_text`; only tests call `handovers.valid`, `runs.run_summary`; a stale `noqa: C901` in `checks/run_record_check.py` (ruff RUF100). A stamped test pins private names (`templates/test-shared-helpers.py.template:38-39`). | V (sample) |
| M7 | Hard to follow: `claude_hooks.pre_run` (17), `post_change` (15), `usability_score.score` (193 lines), `scaffold.next_steps` (142 lines, the apply sentence twice), `audit.bound_prompt` returning an 8-tuple passed on as ten arguments; `decision_review.review` and `report_review.review_report` repeat the journaled call with different exception lists. | R |

Proposals by benefit/risk (structure reader, checked against the
code): (1) the model-free reviewer pieces and the ways-out texts into
one gates module — breaks the audit/reviewer cycle and stops the
pre-commit importing `llm`; (2) one named type for the audited state
(scope, block, run, shown, registration) in `findings`, replacing the
8-tuple and the re-implementation `audit.current`; (3) split
`report_check` at `:1106`, link/index helpers into `repo`; (4) a hashing
module for `digest`/`file_digest`/`tree_digest`, ending both `scope_sha`
cycles; (5) a collector parameter on `preflight_area`; (6)
`protocol_report` into `checks/`; (7) `start_check` returns every
refusal as text; (8) the dead code and stale local imports; (9) pure
`write_*` renamed `with_*`.

## State (2026-10-27, after the fixes)

Each commit carries its tests, red at the parent where a behaviour
changed; the hook ran ruff, format, pyright and the suite on each.

| Rows | Done | Commit |
|---|---|---|
| S2 | `repo.into_command`, runnable from where the agent stands | `3c0e11c` |
| K1, K3, K5 | a broken handover record is one more gap; git's refusal a sentence; preflight says it cannot tell | `7467806` |
| K2 | an unreadable protocol is a refusal | `fa56fc0` |
| I10 | `runlog` refuses the lab root; the README names the area | `89f5a72` |
| I7 | the prompt skeleton refuses a missing items file | `3f39fe2` |
| I1 (A4) | a first measurement at low needs its registration committed — a deliberate new known core→doctrine crossing (`start_check`→`protocol_history`) | `5760496` |
| I2, I3, I4, I8 | `repo.next_after_run`; one reading of the low audit; the exit before the first audit; `--repeat-cost` after exploring | `65b59b3` |
| I5, I6 | `number_describes` settable; the freeze said to be set by hand | `f31c032` |
| I9 (C2, checker) | `protocol_check.full_owed`; `--list` sets unowed placeholders apart | `5e47136` |
| D1–D8, K10 | drift in docs, help, docstrings, `--contract` rows | `51418de` |
| K4, K6–K8, I12 (part) | small messages | `031033b` |
| S1 | `formats/comment_blocks`, one scanner for report blocks | `218ef25` |
| S5, S6, S9 | run record names, kinds, modes, the hooks path; one-home rules | `49a1d99` |
| M6 | dead code and parameters, a stale noqa, local imports | `c62f2da` |

Done in the second round (the order agreed: model-free moves, the
collector, the split, the stamp, the rests):

| Rows | Done | Commit |
|---|---|---|
| I1 crossing | the exception documented with reason and removal target | `a589b33` |
| M1 | the release gate loads no model backend (`ways_out`, `report_review_inputs`, moves to `report_reviews`, `protocol_check`, `repo`) | `d7ce46d` |
| M4 | `preflight_area` takes a collector; the pre-run hook reads data | `e0a5b88` |
| M5 | `protocol_report` in `checks/` | `ae2a2d4` |
| M3 | `report_check` split; `report_hold` finds and holds reports | `89b8287` |
| I9 stamp | `protocol_cuts.owed_cut`: the stamp carries only owed fields | `347b70b` |
| K9 | a stop a handover lets pass names the loss | `4dc4c56` |
| test session (1) | finalize holds an unmoved null lane from the kept rows | `8b500c6` |
| K5, S3 | finding numbers by identity; one report suffix | `2497092` |

Done in the third round (2026-10-27/28):

| Rows | Done | Commit |
|---|---|---|
| S rest | minute stamp, answer-line grammar and prompt join, parent run (S4), area-test rendering (S7), "ref → commit" (S8), each with its `test_one_home` rule | `fddb01b`, `073f1f8`, `e3c6279`, `79dc96b`, `df0e9a9` |
| I11 | Raw output: one real output per finding, from the run's rows, owed only with a model (`not_owed` covers the after-run fields) | `af49126` |
| I12 rest | the next steps name every kind's fields and say `repeat_cost`, not "lane"; finalize no longer offers `--metrics FILE`; a fit with a model is not stamped "no model call" | `d009626`, `493b745`, `10a8e96` |
| M4 rest | the post hook runs the checkers from the repo root; every start check raises; `usability score` and `runlog reindex` read, write and show in steps; pure `write_*` renamed `with_*` | `afd2c3a`, `bfe8a00`, `92d2daa`, `c1d0a7b`, `f991d84` |
| M7 | `BoundPrompt`; one journaled call and one refusal list for the reviewers; the hook handlers in named steps; one estimator sentence | `352341f`, `67a3b4c`, `bfe9865`, `6dc1cb6` |
| — | the stop-budget test under load (3 s → 10 s) | `8a2248b` |

Plan (7) went the other way: every start check now raises
(`SystemExit` with its sentence) instead of returning text — six of the
eight already raised, and the module text said so. Plan (2) is half done:
`BoundPrompt` names the bound state, but `audit.current` still matches a
record field by field instead of one named type in `findings`.

Still open:

- **Plan (2) rest** — one named audited-state type in `findings`, used
  by `bound_prompt`'s `current` and the record.
- **`scaffold.next_steps`** — 142 lines; the doubled sentence is gone,
  the length is not.
- **Test session (3)** — the task's key against the skeleton's
  `c1_score` is a decision in the probe module of `sab-like-cases` /
  `sab-cases-on-main` (another session's branches): name the key in the
  skeleton's output, or accept the skeleton's key in the score.
- **Test session (4)** — 724–1238 s against ten minutes; the agent's
  time, no gate's.
