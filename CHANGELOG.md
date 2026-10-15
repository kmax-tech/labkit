# Changelog

labkit does not carry legacy paths: a format or API change is a break,
announced here with the last version that still has the old behaviour.
Reproduce an old run with the repo's own commit and the labkit version it
pins (`requirements.txt` / `requirements.lock`).

## 0.95.0 — 2026-10-15

Phase B of the audit of 2026-10-15: the audit chain and the hooks.

### Fixed

- **`labkit-audit` stamps the code before the model call.** The stamp was
  taken after the answer (up to 900 s later): a lib module edited meanwhile
  gave a record whose sha no auditor had read, and the freeze gate took it
  as covered. The stamp is taken once, recorded as taken, and a change
  during the call is said (`stamp NOTE`).
- **An audit whose finding lines the parser could not read was recorded as
  covered.** `BLOCKER — …` and `BLOCKER: …` parsed as no finding while the
  verdict counted two; the record then had nothing open and passed the
  freeze gate. The parser reads a dash or colon after the grade too, and
  `findings.write` refuses a verdict that counts more blockers or warnings
  than lines it can record — exit 2, nothing written.
- **preflight holds the audit line's `scope sha` to the code's stamp.** At
  `frozen = true` it never compared them (only protocol-check warned and
  runlog refused at the run), so the pre-freeze gate passed exactly the
  state the freeze gate refuses. A stale sha is a blocker once frozen, a
  warning before.
- **The pre-run hook follows a `cd` and judges throwaway flags per
  command.** `cd AREA && python scripts/01_measure.py` resolved the script
  against the event's cwd and found nothing; one `--probe` anywhere in a
  line freed every command in it. The line is cut at `;`, `&&`, `||`, `|`
  and line breaks (`claude_hooks.command_segments`); each segment is judged
  on its own.
- **Hooks, small:** post-change and stop read `git status -z`, so a file
  name with an umlaut (quoted and escaped in the text form) is checked;
  a `notes/messung/` pair anywhere in the path counts, not only the first
  `notes`; `labkit-hooks install` recognises its own hooks by the command
  as a word, so a foreign `./bin/my-protocol-checker` stays; `claude-hook
  sessions --run` without a value is a usage error, not a traceback.
- **A gate's subprocess has a time limit.** An area test or `02_analyze.py
  --check` that hangs hung preflight, finalize and report-check until the
  hook's own timeout killed them, wordless; after 300 s it is a failing
  test or check, said in the finding (`preflight.AREA_TEST_TIMEOUT_S`,
  `report_check.CHECK_TIMEOUT_S`).

## 0.94.0 — 2026-10-15

Phase A of the audit of 2026-10-15 (`docs/audit-2026-10-15.md`): the bugs
of the guaranteed tier.

### Fixed

- **`protocol-fill --from-run` and `--check` chose the run without its
  binding.** `recheck.run_dir` took the area's newest completed run; in an
  area holding two protocols the number of a run bound to protocol B was
  written into A, and a newer producer run made `--check` of a correct
  area block. The choice is `runs.bound_answering_run` now — the same one
  finalize and intent-check make (`recheck.chosen_run`); a run named
  with `--from-run RUN_ID` must be bound to the protocol.
- **`runlog <typo>` read as idle.** A misspelt area printed "no open runs"
  with exit 0, and `--wait` reported it as finished. Status, `--wait` and
  `--follow` resolve the area like `reindex` and refuse one that is not a
  directory (exit 2).
- **A server's 4xx was retried as an outage.** `HTTPError` is a `URLError`:
  a wrong model id (404) or a missing key (401) went through six attempts
  and 13 minutes of backoff. A status below 500 is now a `BackendError` at
  once, with the sentence naming the alias; 5xx keeps the retry.
- **`claude -p` reads the prompt from stdin.** As one argv entry a 200 kB
  audit prompt was `OSError: Argument list too long` on Linux (128 kB per
  entry); only macOS let it through.
- **Every record file of a run is written whole or not at all.** config,
  outputs and metrics went through `write_text`; only completion.json was
  atomic, while `docs/architecture.md` claimed the whole record was
  (CODE-013).
- **A number inside the run id counted as cited.** `recheck.cited` found
  `10` in `…T10-22-33_ab12` and `12` in `12.7`; the run id is mandatory in
  every note, so a count equal to a date or time part passed. Run ids,
  dates and times are masked before a number is looked for, and a number
  followed by `.<digit>` is another number.
- **report-check passed a must field still holding its placeholder.**
  Station 1 read protocol-check's missing fields only; the `<…>` holes
  count now, as in protocol-check and preflight.
- **A scope file that is not Python is one blocker, not a traceback.** With
  a `lib/` or `src/` in the repo, preflight station 3 and code-check raised
  from the import walk on a stale `analysis/old.py` with a syntax error —
  exit 1, and so not blocking in the pre-run hook. `scope_sha.SourceError`
  names the file; code-check and preflight report it as `BLOCKER`.
- Small: a split file with a damaged line names file and line instead of a
  bare `JSONDecodeError`; `recheck.agree` compares the recomputation as JSON
  (a tuple is the list the run recorded); `finalize` looks for the area's
  tests under the layout root like preflight (a stamped tree before `git
  init` read "none"); `runlog` no longer passes `maxsplit` positionally
  (a DeprecationWarning on 3.13).

### Breaking

- `recheck.run_dir(area, protocol, run_id=None)` takes the protocol; an
  area stamped before 0.94.0 calls `recheck.run_dir(AREA, NOTE)` in
  `02_analyze.py --draws`. `recheck.holds(..., protocol=)` names the
  protocol when `note` is a results note without a head. Last version with
  the newest-run choice: 0.93.0.

## 0.93.0 — 2026-10-15

### Added — repeat draws: the spread of a model's number

- **`runlog.run(..., repeat_of=RUN_ID)`** — the same measurement asked
  again: new model calls, its own model record, `repeat_of` and `draw` (2,
  3, …) in config.json. Refused before mkdir unless RUN_ID is a completed
  primary run with the same protocol, the same promise snapshot (block and
  every declared scope's digest), the same measure script and resolved
  model, the same experiment config and inputs (`runs.repeat_mismatch`), and
  never with `derived_from` (which re-reads old rows without a model call).
  The draw number is reserved once, under runlog's index lock, and exposed
  as `run.draw`; a crashed draw keeps its number. Damaged `repeat_of` or
  `draw` values make the run unreadable, not a primary.
- **A repeat never answers** — not by default, not by name: `runs.bound_runs`
  leaves it out of the answering choice, and `recheck.run_dir` (behind
  `--from-run` and `--check`) refuses a repeat named explicitly, with no
  `--force` past it. `runs.completed_runs` takes a required `with_repeats=`.
- **The skeleton:** `01_measure.py --repeat-of RUN_ID` writes
  `<name>_draw<N>.jsonl` by `run.draw`; `02_analyze.py --draws` holds every
  draw like the kept number (`recheck.verified`: output pinned, scopes and
  block unchanged, metrics recomputed) and then prints c1 per draw, its
  range and the items that flip. `runs.next_draw`, `runs.draws`.
- **finalize warns** "one draw — no spread" for a run that asked a model
  and has no repeat (static evidence).

### Breaking

- `runs.completed_runs(area)` needs `with_repeats=True|False`.

### Fixed

- **A judge area stamped at `seconds` failed its first run** (TypeError in
  MeasureConfig): the seconds cut commented out the constants the full
  measure skeleton reads. Broken since 0.87.0; the stamp keeps them now.

## 0.92.0 — 2026-10-14

### Added

- **`batch.Store(..., instrument={...})`** — what makes two answers
  comparable (the prompt's digest, the model alias). Every appended row
  carries it as `_instrument`, and `pending()` raises `InstrumentError` when
  the file holds a row of another instrument (or none): a changed prompt or
  model is a new measurement, a new output file. Resume by id alone let a
  new prompt keep the old prompt's answers (found by the cloud judge
  probe's analysis audit).

### Changed

- **The measure skeleton** passes `{prompt_sha, model}` to the Store;
  `measure(cfg, jobs, out, prov)` takes the config instead of the model
  alias (`instrument(cfg)` builds the dict). Areas stamped earlier keep
  their `measure`; a re-stamp brings the new one.
- **The probe's print names the area's real test file and `PROBE_CASES`**
  (it said `tests/test_<NN>_<name>.py PARSER_CASES`), and the `max_empty`
  comment no longer derives the value from "2 of 96".

## 0.91.2 — 2026-10-14

### Fixed

- **A frozen head carried the stamp's `<…>` promise sentences** and passed
  every gate (only an empty sentence was refused). At the freeze or a full
  run a `[[promise]]` sentence that is one `<…>` placeholder is a must gap
  now (`promises.promise_tables_owed`, `placeholder_sentences`) — in
  protocol-check, preflight and runlog alike; an unfrozen pilot may carry
  it. `report-check` holds the freeze to protocol-check's must gaps, not to
  the flag alone. The template's hint says to state the promise explicitly
  instead of "the same as the Intent field".

## 0.91.1 — 2026-10-14

### Fixed

- **`data=` inputs recorded absolute paths too** (0.91.0 fixed only the
  outputs): after a checkout moved, finalize found the frozen source
  "gone" — a blocker at `seconds` — and a relative `data=` path was kept
  relative to whatever the working directory was. One pair for both,
  `runs.recorded_path` / `runs.resolve_recorded`; `recorded_output_path`
  (0.91.0) is gone.
- **The analysis script has one name:** LAB-041, the field guide and the
  protocol template said `analysis/<note>.py --check`; the stamp writes,
  and `report-check` holds, `scripts/02_analyze.py`.

## 0.91.0 — 2026-10-14

### Added — the lane has an end gate

- **`report-check <AREA>`** — the last gate at `minutes`/`hours`, after the
  analysis audit: `frozen = true`, finalize clean, an analysis audit record
  of the code as it is now with every finding decided, and
  `scripts/02_analyze.py --check` passing. At `seconds` nothing is owed
  there. finalize could not ask for these without a circle (it comes before
  the analysis audit); in the cloud judge probe an agent skipped the check
  and the note with finalize green. The AGENTS.md template's step 11 ends
  with it.
- **`findings.audit_coverage(area, sha, mode)`** replaces
  `preflight_coverage` (0.90.0): one answer for the freeze and the report.

### Changed

- **The measure skeleton's accuracy is over every item of the lane**; an
  empty or unreadable answer is not correct (and still counted as
  `*_empty`). Over readable answers only, a model gained accuracy by not
  answering, and both cloud preflight audits flagged it. The stamped [C1]
  sentence and the area test say the same.
- **`protocol-fill --list`** prints the fields `--from-run` writes (Result,
  Answer to the question) last, under "after the run".
- **`labkit-init exp`** finds the lab repo above the working directory.

### Fixed

- **outputs.json recorded absolute paths**, so `02_analyze.py --check`
  failed in every checkout but the one that measured (a cloud run's
  `/home/user/...`). A path inside the repo is recorded relative to its
  root and resolved on read; records written before keep their absolute
  paths.

## 0.90.0 — 2026-10-14

### Breaking — the frozen code is the audited code; `runlog start` names its area

Both from the cloud judge probe at `minutes` (`docs/usability/2026-10-14-judge-minutes.md`).
Last version with the old behaviour: 0.89.0.

- **A full run's audit stamp must be one a preflight audit record saw.**
  runlog's freeze gate (and `preflight`, a blocker once `frozen = true`)
  now needs a record `audits/*-preflight.toml` whose `scope_sha` is the
  code's stamp now, every finding decided (`findings.preflight_coverage`).
  Writing a new `scope sha` into the head after fixing the findings, without
  a second audit, is refused; `n/a — <reason>` stays a visible waiver.
  Every frozen area audited before `labkit-audit` wrote records (all 21 in
  uniagent) owes a fresh preflight audit before its next full run under a
  raised pin.
- **`runlog start AREA [--log FILE] -- <cmd>`.** The area is a required
  argument; the default log is `AREA/output/start-<ts>.log` (was `output/`
  under the working directory) and the printed wait command names AREA.
  `runlog start -- <cmd>` is a usage error.

### Fixed

- **[C1] in the measure skeleton compared floats:** a registered lane
  exactly at null + margin failed (5/12 + 0.25 > 8/12 by one ulp). It is
  computed in fractions now — found by the probe's opus preflight audit.
- **The AGENTS.md template** says an audit takes minutes: start it in the
  background and wait for that task, not with a `pgrep` loop (which finds
  its own command line; about 14 of the probe's 22 minutes).

## 0.89.0 — 2026-10-14

### Breaking — the legacy paths are out, one home per question

A repo audit (2026-10-13: the seven largest modules, the drift between
modules, the docs against the code) found the readers of old formats
still in place and a dozen second answers to questions
`docs/architecture.md` gives one home. Last version with every old
path: 0.88.8.

- **No `legacy` run state.** A `config.json` without `schema_version >= 2`
  (a run of labkit before 0.21) is unreadable run metadata like a damaged
  file: `runs.read_run_config` raises naming the file and the version that
  reads it (0.47); listings show `unreadable` with the reason, `runlog
  --wait` exits 2 on it, `reindex` reports it and exits 2, no choice ever
  takes it. `runs.completion_state` raises for a directory without
  `config.json` (not a run) instead of answering `legacy`.
- **`endpoint = "<url>"` in `models.toml` is not read.** `llm.resolve`
  refuses it with the list spelling to write (`endpoints = ["..."]`); the
  stamped `models.toml` documents only the list.
- **`promises.DIGEST_CHARS` is gone** — it shadowed `scope_sha.DIGEST_CHARS`
  (the comment said so). The digests themselves are unchanged.
- **The probe's scaffold sha changes shape:** `usability.scaffold_sha`
  computes through `scope_sha.tree_digest` (name + content digest per file)
  instead of raw bytes. Only new probes record it; a score compares a
  probe with its own record.
- **`llm.complete(keep_alive=)` is gone** — no caller ever passed it;
  `llm.OLLAMA_KEEP_ALIVE` (10m) is the one value.
- Smaller: the documented-runs heading no longer matches `ledger` (the word
  left the vocabulary 2026-09-26); the usability source-read pattern no
  longer matches `arbeitsstandard`; `runlog <area>` prints `(not recorded)`
  for a run without a command instead of naming labkit 0.69.

### Changed — one home for what was answered twice

- **`repo.the_protocol(area, protocol)`** raises `ProtocolChoiceError`
  (the candidates in the message); `repo.choose_protocol` prints it.
  `preflight`, `code-check` and `labkit-audit` carried their own copies of
  the rule — three wordings of one refusal.
- **`protocol_block.id_of(text)`** is the one tolerant reader of a head's
  id (`protocol_check`, scaffold's uniqueness scan); scaffold reads `cost`
  through `protocol_block.head`, the area's protocols through
  `repo.area_protocols`, the tiers from `protocol_block.COST_TIERS`.
- **`scope_sha.area_files`** sorts and is the one list of an area's scripts
  (`intent-check`, `labkit-audit` had their own globs).
- **`runs.run_dirs(area)`** walks `runs/` once with every directory's
  metadata read once; `completed_runs`, `bound_runs`, `runlog.active`, the
  finished listing and `reindex` go through it (six loops, six decisions
  before). **`runs.write_atomic`** replaces two private copies (`runlog`,
  `endpoint_lease`). **`scope_sha.file_digest`** and
  **`scope_sha.tree_digest`** are the one file digest and the one stamp
  shape (area stamp, declared scope, directory source — byte-identical).
- **`protocol_check.check_protocol(path, text, tmpl)`** returns a
  `FileReport` with every finding as data (`clean`, `musts`, `blocks`);
  `print_report` renders it, `main` loops. Fields parsed once per file;
  `prose_lines` is the one walk behind the whole-protocol budget
  (`PROSE_LINE_BUDGET`) and the section budgets. Output unchanged.
- **`scaffold.stamp_area` returns `(area, report)`** and prints nothing;
  `labkit-init` prints. `runlog` reads the bound protocol once at binding
  (text and head travel with the record; before: three reads, three
  parses per run start). `usability` writes its probe commit, probe
  record, answer-file and venv helpers once instead of four times.
- **README's command list comes from `--help`** and is held by
  `tests/test_readme_commands.py`; the hook JSON, the gates' stations and
  `Develop` describe the current code; `protocol-fill --from-run` is
  documented to write `Answering run` too (template, finalize's hint).
  The field guide places `Answering run` and `Deviations after freeze`
  under Result, as the template does, and knows the `deferred` status.
- **One grammar for a requirement line** (`repo.VCS_REQUIREMENT`,
  `EDITABLE_REQUIREMENT`, `EDITABLE_PATH_REQUIREMENT`, `VERSION_REQUIREMENT`,
  `repo.requirement_name` / `requirement_lines`): the stamp's pin line,
  `labkit-check`, runlog's lock parser and the probe's pip-freeze line read
  through it (four spellings before). **One shape for a run id**
  (`runs.RUN_ID`, `RUN_ID_TIME`, `run_started`): runlog writes with it,
  protocol-check and finalize find a cited run, the stop hook reads the
  start time. `runs.COMPLETED` replaces nine string comparisons.
- `protocol_check.fields` parses a text once (seven readers before);
  `code_check` reads a bare name and a string literal in one place each;
  `llm` builds the ollama options and the empty-content notice once.

### Added

- **The detach gate holds under any agent.** `runlog` refused a long run in
  a foreground shell only under Claude Code (`CLAUDECODE`); under Codex or
  another agent the run died with that harness's timeout.
  `LABKIT_FOREGROUND_TIMEOUT_S` (seconds, `0` = no limit), set in the
  environment the harness gives its shell, names the limit for any agent;
  `CLAUDECODE` alone still counts as 600 s. `runlog.foreground_timeout()`
  answers which limit applies and who named it.
- **`code-check` warns on an [A] key nothing decides on.** An
  admissibility key the code writes but never tests (`if`, `and`/`or`/
  `not`, `all()`/`any()`, a loop over a key tuple) permits nothing: the C
  verdict is reported either way. Static evidence — a WARNING, and code
  this reader does not follow stays silent.

### Fixed

- **`code-check` crashed on an empty prompt fence** (`IndexError` reading
  the first line of an empty block) instead of reporting the drift as a
  blocker.
- **`labkit-params` missed a script copy in upper case:** `MIN_F1` for the
  registered `min_f1` stood as a separate evidence row and the registered
  row said only "not recorded". The copy now stands in the registered row.
- **`labkit-check` called a tag pin and its lock STALE:** the lock from
  `pip freeze` names the commit the requirements tag points at. The pin
  line resolves the tag at the source and compares commits.
- **The usability task sheets** say that every `.venv/bin/…` path holds
  from the repo root (Haiku H8 called it from the area: exit 127).
- **The stamped skeleton tripped its own gates** (a cold Sonnet agent, judge
  at `minutes`): `00_prepare.py` passed no registered constants, so runlog
  refused the first step of every area with a model; `02_analyze.py
  --check` looked for `:.4f` numbers while `--from-run` writes them as
  Python prints them; `--from-run` skipped the stamped `Answering run: none
  yet` line silently (another run's id is now refused, not skipped); and
  `code-check` warned on `02_analyze.py` loading its own `01_measure.py`.
- **`usability stage`:** the task sheet names the stamped cost tier, and
  says AGENTS.md (not CLAUDE.md) is in the agent's context.
- **A dead run held "running" by a namesake:** `runs.is_alive` matched the
  recorded script as a substring (`not_01_measure.py` for `01_measure.py`);
  `runs.runs_script` now bounds the name.
- **The Stop hook crashed on a run-id-shaped name with no date**
  (`2026-02-30T…`): `runs.run_started` answers None for it.
- **`read_outputs` coerced `rows_from` with `int()`**; a count that is not
  an integer is now an `ArtefactError` naming the entry.
- **Endpoint leases:** the lease directory is named by the canonical URL
  (lower-case scheme and host, no trailing slash) and its digest instead
  of a slug, so `a-b`/`a_b` are two slots and `Host`/`host` one; two
  writers in the same second no longer both yield. A process of an
  earlier labkit leases under the old directory name and does not see a
  0.89.0 lease on the same slot — let running stages finish before
  switching.
- **`protocol-check` cached the repo's protocol ids for the process**;
  `check_protocol` and `check_protocol_id` now take the index
  (`repo_protocol_ids`) as an argument, so an API caller sees a duplicate
  made after its first check.

## 0.88.8 — 2026-10-13

### Fixed — the stamper refuses a version its templates do not belong to

- **`labkit_pin()` compares the installed metadata with the source
  checkout** and refuses when they differ: an editable install keeps the
  version of its last `pip install -e` while the templates are read live,
  and the first `usability stage --restamp` after the 0.88.7 release pinned
  `v0.88.5` under 0.88.7 templates. A wheel install has no source beside
  the package and is unaffected. The release recipe (`just release`)
  reinstalls the editable labkit before the commit, so the two never drift on
  the author's machine.

## 0.88.7 — 2026-10-13

### Added — four cuts from the Haiku series on 0.88.5 (H5–H7, median 1m00s)

- **`protocol-fill PROTOCOL "LABEL=VALUE" ...`** fills several fields in one
  call, all or nothing (`type=exploratory` sets the head). Every cold agent
  filled six fields in six calls and named it the largest sink. The one-field
  form `FIELD VALUE...` stays; the stamped `AGENTS.md` names the one-call
  form.
- **The seconds cut without a model says what a count owes** in its
  placeholders: `Terms of this protocol` → "one line per coined house word —
  or n/a — no coinage" (the check allowed n/a, the stamp never said so;
  three agents wrote a Terms sentence for a plain count), `Question /
  hypothesis` → "what is counted, over which items — a count tests no
  hypothesis" (H7 invented an expectation, then reworded it with `--force`).
  The labels stay: one name per field, in the standard, the check and every
  reader.
- **The counting skeleton freezes what the rows read:** `INPUTS` names the
  directory beyond `SOURCE` (a count of documents per case reads the case
  directories), and `data=` carries both. Before, `data=` froze the case
  list only and a changed document went unnoticed by `--check` (all three
  draws).
- **`usability log TAG TEXT [--log FILE] [-- CMD ...]`** writes the agent's
  step line with the current time and then runs the command. Logging by hand
  tempted every draw to batch: three wrote their first lines after the reads
  they describe. The task sheets name it.

### Changed

- **`protocol-check`: the stamped Runs entry is not a leftover before the
  run.** It is written by `--from-run`; counted as "still verbatim template
  text", it made every registration read as unfinished and two agents
  stopped to see whether it blocks. The check now says so in one line; a
  frozen protocol with the stamped entry is still a leftover (the scar of
  uniagent area 08). The pattern has one home, `protocol_check.RUNS_PLACEHOLDER`.

### Decided, not built

- The area test stays in the seconds lane (H6 would skip it): a
  number-producing function gets a test, three seconds.
- A pre-filled counting skeleton for the directory-per-item source (every
  draw's other sink) is open — not to be cut to the weakest model.

## 0.88.6 — 2026-10-13

### Added — `usability stage --restamp`: the probe stamped again, by the tool

- **`usability stage DIR --restamp [--keep PATH ...]`** lays a fresh stamp
  (task and flags from `<dir>.probe.json`) over an existing probe file by
  file: a stamped file whose bytes changed is overwritten, a new one added,
  a `--keep` path (the probe's hand edits: `TASK.md`, `.gitignore`, the
  cloud's `.claude/settings.json`) left alone and remembered in
  `probe.json` (`kept`, `restamped`). The venv is rebuilt from the stamped
  pin (or linked with `--venv`), `requirements.lock` comes from it, the
  change is committed past the hook; the push stays with the operator. A
  `--keep` path the stamp does not produce and a dirty tree are refused.
  Why: eight re-stamps of `labkit-probe` were done by hand from memory, and
  on 2026-10-13 two sessions reconstructed the recipe differently — one
  would have copied the task sheet and lost the cloud edits.

### Fixed

- The stamped `.gitignore` ignored `.venv/` — a directory only. With
  `--venv` the probe's `.venv` is a symlink, and `git add -A` committed it
  (the first `--restamp` found the link in the fresh stamp's tracked
  files). The pattern is `.venv` now: directory or link.

## 0.88.5 — 2026-10-13

### Fixed — three things a cold agent tripped over (Haiku 5.5, draw H4)

- **A reader that closes the pipe is not a crash.** `protocol-check
  --contract P | head` ended in a BrokenPipe traceback and exit 120. Every
  console command now exits through `labkit.console.exit_with`: a closed
  pipe is exit 0, nothing printed — one home for the one exit.
- **`protocol-check PROTOCOL --contract`** read the flag as a file name
  ("not readable: '--contract'"). `--contract` and `--guide` are flags
  anywhere on the line.
- **`--check` before the write-back** said "numbers not in PROTOCOL", which
  read as a failed check. When the Answer line still holds the stamp's
  placeholder, `recheck` now says so and names the command:
  `protocol-fill PROTOCOL --from-run <run_id>`.

The code landed in `16d7510`; this entry, the version and the draw's notes
follow in the next commit, and the tag was moved onto it.

## 0.88.4 — 2026-10-13

### Changed — a run's own products no longer make it `+dirty`

- **`completion.json` and the `runs.tsv` git column** record the state at
  the end of the run over tracked files only. The run's own products
  (`runs/<id>/`, `output/`, `runs.tsv`) are untracked until committed, so
  every finished run read `+dirty` whatever the tree looked like — 74 of
  74 index rows in one lab repo, and a cloud agent reported
  "`beae3bf+dirty` but `uncommitted.patch` is empty" (Haiku 5.5,
  2026-10-13). `config.json`'s `git` (the state at start) still counts
  untracked files: a file git does not know may have been run. Rows
  written by labkit up to 0.88.3 carry the old flag; `reindex` does not
  rewrite rows.

## 0.88.3 — 2026-10-13

### Added — `protocol-fill` knows the head's `type`

- **`protocol-fill PROTOCOL --list`** names the TOML head's `type` first
  while it is still the stamped placeholder, and **`protocol-fill PROTOCOL
  type exploratory`** (or `confirmatory`) sets it. Before, `--list` showed
  only the prose fields: an agent filled those, the post-edit hook answered
  "MISSING (must): [protocol] type", and the head was edited by hand (cloud
  probe, Haiku 5.5, 2026-10-13).

### Fixed

- The stamped `AGENTS.md`'s seconds lane still asked for a success
  criterion and an admissibility condition at a count — the 0.87.0 cut had
  dropped both from the contract, and the agent logged the contradiction.
  Step 2 now follows `--list` and says what a count owes and what only a
  model adds.

## 0.88.2 — 2026-10-13

### Added — the score names the model

- **`usability score --agent M`** writes the model that drew into
  `<dir>.score.json` (`"agent": "fable-5.1"`) and the table's first row. A
  cloud session leaves no transcript, so the operator states it; without
  the flag the field is `null`, never guessed. The twelve cloud score files
  under `docs/usability/` carry it now, taken from their file names.

## 0.88.1 — 2026-10-13

### Changed — a count's README carries no blank

- **`labkit-init exp --cost seconds` (no model)** stamps the area README
  without a placeholder: the one-question line points to the protocol's
  Question field, the contract paragraph names `METRIC_KEY` and the
  write-back gate. The question and the contract live once, in the
  protocol; the README's blank was the one gate line left in the cloud
  probe (draw 11, `docs/usability/2026-10-12-cloud-fable.md`), reported by
  `finalize` only after the run. Skeleton stamps (a model, or
  minutes/hours) keep their placeholders.

### Fixed

- The README's state box named the area test with the slug's hyphens
  (`tests/test_01_docs-per-case.py`); the stamped file has underscores. The
  line now names the file that exists.

## 0.88.0 — 2026-10-12

### Added — `protocol-fill --from-run`: the number is written back, never retyped

- **`protocol-fill PROTOCOL --from-run [RUN_ID]`** writes the Answer line,
  the Summary's Result line and the Runs entry from the run's
  `metrics.json` (the area's newest completed run by default): every
  reported key and value as recorded, plus the run_id — exactly what
  `--check` (`recheck.cited`) holds the protocol to. labkit's own keys
  (`duration_s`, `llm_retries`) stay out; a filled line is refused without
  `--force`; the stamped `<run_id>` placeholder becomes the entry.
- The counting and the full measure skeleton print that command after the
  run; the seconds lane and the area README name it. Why: twelve cold
  agents in the cloud (Fable, Sonnet, Haiku; 2026-10-12) typed the number
  into three lines by hand, every one named it as the retyping LAB-041
  Generate numbers, don't retype them forbids, and one `--check` failed on
  it.

## 0.87.1 — 2026-10-12

### Fixed — the gates agree with the 0.87.0 stamp: a count registers nothing and owes no table

The sixth cloud probe ran on the 0.87.0 stamp and hit two gates the cut had
not been told about (3m36s, one read of labkit source "because the gate
forced it"): `protocol-check` demanded `[[promise]]` tables the stamp
leaves out, and `runlog` refused the run for the criterion and the
admissibility condition the cut no longer carries.

- **`promises.promise_tables_owed` takes `registers`**: a protocol whose
  prose names no [C]/[A]/[B] id owes no tables unless it is frozen —
  there is nothing to hold (`promises.registers_ids`). protocol-check,
  runlog and finalize pass it; finalize says "n/a — the protocol registers
  no promise id" instead of blocking a count's run for a missing block.
- **The seconds gate of runlog is the question** — with a model named also
  criterion and admissibility condition (`protocol_check.seconds_registration_missing`).
- The seconds lane names the Result line as the summary; Limits and Next
  step belong to the full form.

## 0.87.0 — 2026-10-12

### Breaking — the seconds cut is what a count owes, and the stamp carries hints, not the guide

Three decisions after five cold-agent probes in the cloud (count task,
Fable, 0.85.0 → 0.86.2, 4m27s → ~2m10s; every agent named the same
cuts). Last version with the old seconds cut: 0.86.2.

- **A count registers no promise.** At `cost = "seconds"` without a model
  the stamp has no `[[promise]]` tables, and `Success / failure criterion`
  and `Admissibility condition` are not owed (`sm` fields: with a model
  they are, together with the C1/A1/A2 tables). Five agents each invented a
  tautological [C1] for a mean; the number is held by `--check` and
  `finalize` — `intent-check` has nothing to hold without ids.
- **The Summary at seconds is the Result line.** `Limits` and `Next step`
  belong to the full form; the after-run check and the cut agree
  (`protocol_check.unreported` takes the tier).
- **Every stamped placeholder is one line.** The template's placeholders
  carry the field guide's prose — a third of every probe's reading time;
  `scaffold.short_placeholders` keeps the label and a one-line hint,
  `protocol-check --guide` is the long form. The seconds stamp went from
  102 to 40 lines, the full form from 182 to 120.

## 0.86.2 — 2026-10-12

### Fixed — a path example in a code span is not a README placeholder

- **`finalize.readme_placeholders` ignores code spans and fenced blocks.**
  `` `<inputs>/<case_id>/` `` in an area README was read as a stamped
  blank; the fourth cloud probe (0.86.1, 2m09s, right and bound) spent a
  gate line, a reword and a second finalize on it.

## 0.86.1 — 2026-10-12

### Fixed — what the second cloud probe found (0.86.0: 2m28s, right and bound)

- **The counting skeleton writes its rows inside the run, each with
  `_prov.run`.** It wrote the file before opening the run, so finalize noted
  twelve rows without provenance on every seconds area.
- **`usability stage` installs the stamped requirements beyond labkit into
  the probe venv before freezing the lock** (`other_requirements`). The lock
  knew only labkit, the cloud venv came from requirements.txt with pytest,
  and runlog reported a drift on the first run — in both draws.
- **`Raw output` is owed only with a model** (`sm` in the template and the
  checker): a count has no prompt+answer pair to show; the probe filled the
  field with n/a.
- **`code-check` says at cost seconds that schema, gate labels and
  placeholders are not owed** instead of pointing at `--bundle`; the probe
  never found out what the bundle was or whether it mattered.
- **The seconds lane names `--show 2` only with a model, and the area README's
  state box names `--probe` only where the skeleton has one.** The counting
  skeleton has neither flag; the probe skipped both and said so.

## 0.86.0 — 2026-10-12

### Fixed — three defects of the seconds stamp, found by the first cloud probe

The first cold-agent probe in a claude.ai/code cloud session (count task,
labkit 0.85.0, no house directory, no skills): number right and bound in
4m27s, 0 reads of labkit source — and three of its five "what I would cut"
items were template bugs, not agent trouble
(`docs/usability/2026-10-12-cloud-fable-count-1.score.json`).

- **`labkit-init lab` stamps `pytest` into `requirements.txt`.** The
  stamped area test needs it, preflight and finalize run it, AGENTS.md
  names it — and the lab's requirements listed only labkit. The probe
  installed it by hand, which made runlog record a lock drift and cost a
  second run.
- **The seconds skeleton's function is `evaluate_rows`**, as in the full
  skeleton, the analysis script and the README route the stamp writes.
  It was `evaluate`, so finalize warned twice on every seconds area that
  the route names a function the script does not define.
- **The seconds cut without a model stamps no null-lane table.** `[[promise]]`
  A2 (the null condition) stood in every seconds protocol; without a model
  there is no null lane, and the probe deleted the table by hand. The
  example `constants = {…}` lines become one commented hint instead of
  vanishing: a count registers no threshold, but a criterion that names
  one must register it, and the probe read the promises docstring to learn
  the field.
- The protocol template's Terms field names the lab glossary by its new
  name, `notes/theorie/terms.md`.

## 0.85.0 — 2026-10-12

Four levers from reading uniagent's 23 preflight and 21 analysis audits
(2026-10-12): what the audits found is now data, what the stamp cannot
follow is a mechanical warning, a criterion that noise can fail is a scar,
and an audit at cost `seconds` before the first run says it is early.

### Changed — the scar table knows a criterion that noise can fail

- **New row in LAB-015's scar table, "Criterion fails on noise"**: a
  criterion on model output that one vote of a component the change does
  not touch can fail — every rejection counts, no majority over draws, no
  restriction to the component under test (uniagent area 26: [C3] fell to a
  single vote of an unchanged rule; the preflight audit, working the table,
  had no row for it). Audit column `preflight`, rules LAB-036 and LAB-016.
- **LAB-015 says what no audit sees**: model behaviour on the cases. In
  uniagent four criteria fell to it and no audit had flagged one; the probe
  for that is the instrument check on the boundary cases (LAB-008, LAB-014),
  not a second audit.

### Changed — `labkit-audit --mode preflight` says when it is early

- **At `cost = "seconds"` with no completed run** the command prints one
  WARNING on stderr and goes on: the first run is the cheaper probe, one
  audit in mode analysis after it covers the preflight rows (LAB-017 The
  number of audits follows the cost tier). uniagent area 01 had two
  preflight audits and an analysis audit at seconds; its protocol says one
  after the first run would have done.

### Added — `labkit-init lab` stamps the lab's glossary

- **`notes/theorie/terms.md`**, empty, with the four columns the
  standard's chapter 5 names (everyday word · lab term · code word · field
  term) and the pointer to LAB-084 Double-coinage check. The standard has
  said since 0.77.0 that this file is the one home of a lab term; nothing
  stamped it, and the house template still carried a "core glossary" table
  inside its inherited block — "fill this in" next to "edit the master, not
  here", empty in all nine labs (2026-10-12). The house block now points
  here; the table moves out of it.

### Added — static evidence: code the stamp cannot follow (`code-check` 1d)

- **`code_check.stamp_coverage_findings`**, run by `code-check` and by
  `preflight` station 3: a WARNING naming the line for a `sys.path` edit
  that does not point at `lib/` or `src/`, a dynamic loader (`importlib`,
  `runpy`, `exec`, `__import__`), a path string naming another area
  (`experiments/14-…/scripts/01_measure.py`) and an import that resolves to
  a repo file outside `lib/` and `src/` — code that determines the number
  and that the audit stamp does not see (LAB-019 The stamp covers
  everything that determines the number). Never a blocker. The stamped
  template's own `sys.path.insert(0, REPO / "lib")` is silent, and a
  loader inside a shared helper is not charged to every area that imports
  it. Why: in uniagent five audits (areas 15, 16, 17, 22, 23) found a
  script loaded from another area by reading; on the same areas the check
  now names the lines (15 and 16 load area 14, 16 and 22 load area 05).

### Added — audit findings as data (`labkit.findings`)

- **`labkit-audit --mode preflight|analysis` writes its findings into the
  area**: `audits/<date>-<mode>.toml`, an `[audit]` table (date, mode,
  model, scope sha, counts) and one `[[finding]]` per BLOCKER/WARNING/NOTE
  line, every one `status = "open"`. The person sets the status — fixed,
  accepted, deferred, dismissed — and a reason; `accepted`, `deferred` and
  `dismissed` without a reason do not read.
- **`preflight` has a station for it**: a finding still `open` is a
  warning before the freeze and a blocker once `frozen = true`; a
  `deferred` finding in any other area of the repo is printed as a
  reminder and never counted; an unreadable findings file is a blocker.
- Why: in uniagent a finding deferred in area 16 as "its own task" bit in
  area 17; the same finding was accepted three times; 13 of 44 audit lines
  end in accepted/dismissed and what they decided sits in a 400-character
  protocol line. Now the deferred ones stay visible and an audit's yield
  can be counted instead of read.

## 0.84.0 — 2026-10-12

### Added — `labkit-check`: is this repo current?

- **One command, five lines**: the pin (`requirements.txt` / `.lock`), the
  installed labkit against it, the newest release tag at the pin's source
  (a local checkout with `git tag`, a remote with `git ls-remote`;
  `--offline` skips the remote), the hook (`labkit-hooks check`) and every
  rule reference in the repo's `.md` and `.py` files (`labkit.rules
  check_refs`). Each line ends OK, STALE or UNDECIDED; exit 0 / 1 / 2. It
  reports and changes nothing: the pin is raised on purpose.
- Why: the three checks existed apart and were forgotten; nothing compared
  installed with pinned, and on 2026-10-12 the installed labkit lagged the
  pin in all four active lab repos. A commit pin is STALE — the house sync
  refuses it, and only a tag says which release a run used.

## 0.83.0 — 2026-10-11

### Changed — a cut ollama prompt fails loud

- **`num_ctx` in `models.toml`** for an ollama alias: the context window
  ollama allots, sent with every call (chat and raw). Unset, the server's
  default applies. On any other backend, or as anything but a positive
  integer, `resolve` raises — an OpenAI-compatible server sets its window
  at start and refuses longer prompts itself.
- **`llm.PromptTruncated`**: ollama fits a prompt longer than its window
  by dropping tokens and answers with HTTP 200 (0.23.1 on leguin: a
  25,272-character prompt at `num_ctx` 2048 read exactly 2,048 tokens).
  `complete` now raises when `prompt_eval_count` reaches `num_ctx`, or lies
  far below the prompt's length (more than 10 characters per token on a
  prompt of 4,000 characters or more). Not retried. A call that 0.82.0
  answered from a cut prompt raises under 0.83.0 — that answer was never a
  reading of the whole prompt.
- `labkit-audit` reports it as "no audit" (exit 2), like a backend failure.

## 0.82.0 — 2026-10-11

### Breaking — rule identifiers: `LAB` / `LOCAL` / `CODE` instead of `AS` / `HS` / `CS`

- **Three families, named by scope, not origin.** `LAB-nnn` is the shipped
  lab standard (was `AS-nnn`, for *Arbeitsstandard*), `LOCAL-nnn` a lab's
  own rules in its own ledger (was `HS-nnn`), `CODE-nnn` the coding style
  (was `CS-nnn`). Number for number: `AS-015 Preflight audit before
  freezing` is `LAB-015 Preflight audit before freezing`.
- **Hard cut, no alias, no reader of the old families.** `labkit.rules`
  knows only the new prefixes; `python -m labkit.rules show AS-015` fails
  under 0.82.0. 0.81.0 is the last version that reads `AS`/`HS`/`CS`;
  material written before the cut (frozen protocols, run snapshots,
  reports, this changelog) keeps its old identifiers and is reproduced with
  its commit and pin. The standard carries the one-time note in its
  *Identifiers* paragraph; identifier rule 3 (an id never changes) holds for
  the published families from here on.
- **The seven house numbers left the shipped ledger**: AS-002, -070, -073,
  -078, -080, -081, -099 live on as `LOCAL-002` … `LOCAL-099` in the
  authoring lab's ledger; `rules.tsv` keeps them as gaps (a new id is the
  highest ever given + 1, so they are never reused). The status `house` is
  gone with them.
- Every living file of the package follows: standard, ledger, code,
  templates, agent instructions, docs, tests. `docs/coding-style.md` is
  re-vendored from its master with `CODE-nnn`.

## 0.81.0 — 2026-10-11

### Added — what a call cost

- **`llm.last_usage()`**: the token counts of this thread's most recent
  completion as the backend reported them (`Usage`: prompt tokens with
  cache hits included, output tokens, the cached part, USD where the
  backend prices the call), `NO_USAGE` where it reported none; reset per
  attempt like `last_thinking()`. Every backend fills it: claude-cli from
  its JSON reply, ollama from `prompt_eval_count`/`eval_count`,
  OpenAI-style servers from `usage`.
- **`labkit-audit` prints it** on stderr beside the prompt size
  (`labkit-audit: tokens · prompt 61,234 (8,671 cached) · output 1,902 ·
  0.41 USD`) in every mode — the stamp's facts can carry what the audit
  cost. Why (2026-10-11): 30 Claude Code transcripts of labkit and
  uniagent summed to seven billion cache-read tokens, the old subagent
  audits at 3.65 M per audit, and no labkit line said what one call cost.
- **`agent_transcript.tokens`** reads the `usage` blocks of a Claude Code
  transcript (`Tokens`: calls, input, output, cache read, cache creation,
  the largest context one call read); `TranscriptTrace.tokens` carries
  it, `usability score --transcript` shows a `transcript · tokens` row and
  `usability trace` ends with a `tokens:` line.

### Breaking

- **claude-cli runs `claude -p --output-format json`** and reads the
  answer from the reply's `result` field; plain text on stdout, a reply
  without `result` or one with `is_error` is a `BackendError`. Callers
  see the same answer text as before. A test that fakes
  `subprocess.run` for this backend returns `{"result": "…"}` now
  (0.80.0 was the last version that took plain stdout).

## 0.80.0 — 2026-10-11

### Added — AS-103 The audit reads by declared scope, not by import graph

- **New rule in the standard, chapter 2A** (ledger row AS-103). The stamp
  covers everything that determines the number (AS-019); the audit reads
  what its question needs: the scripts, the files the `[[promise]]` tables
  declare as scope, and the repo-local modules those import directly.
  Deeper modules are the instrument's internals: an index, read on
  assignment.
- **`labkit-audit` builds the prompt that way.** `audit.gather` returns a
  `Reading`: code in full (scripts, analysis files, declared scopes,
  direct imports via `scope_sha.repo_imports`) and the indexed rest of
  `imported_repo_helpers`; `audit.module_index` renders path, line count,
  top-level signatures and the first docstring line under one
  `===== INDEX: … =====` piece. The auditor's `scope:` list names what it
  read in full; the command adds the indexed modules before holding the
  list to the stamp. A declared scope file that does not exist refuses
  the audit (exit 2). uniagent area 22: 444 kB → the scripts, one declared
  function's file, five direct imports and an index of the other ~30
  modules.

## 0.79.0 — 2026-10-10

### Breaking — `labkit-audit` is the one runner of the experiment-preflight audit

- **The Claude subagent copy of the instructions is gone.** AS-015 named two
  ways, the subagent `experiment-preflight` and the command; the standard
  now names the command only. The subagent read on its own (uniagent,
  50 audits: median 295k fresh tokens and 33 tool calls each, the standard
  read 88 times) and its copy drifted from the shipped text once
  (2026-10-07). Last version whose standard names the subagent: 0.78.0.
- **The auditor gets the rules its instructions cite, not the whole
  standard.** `audit.cited_rules` reads the `AS-nnn` ids from
  `experiment-preflight.agent.md` (AS-015 Preflight audit before freezing
  with the scar table and the severity legend, AS-017 The number of audits
  follows the cost tier, AS-004 Identifiers make the intent addressable,
  AS-050 Analysis audit before reporting) and inlines their blocks — about
  18 kB instead of 117 kB. A finding no rule names is "new class".
- **MODE analysis inlines the answering run's rows.** The instructions told
  the auditor to read the first 50 and last 20 output rows; the command
  never gave them (an auditor without tools read code alone). Now every
  output the run registered comes as `===== ROWS <path> … =====` with
  numbered rows (a row over 2000 chars cut and marked), plus the run's
  `metrics.json`; a protocol without an id or a run says so in one line.
- `labkit/templates/models.toml.template` stamps the alias `opus` the
  command calls by default (`claude-cli`, `claude-opus-5-5`).

### Fixed

- **`claude-hook pre-run` fires only on a file the command RUNS.** It
  matched every `.py` path in the command and read it for `runlog.run(`;
  in uniagent 85 of 272 hook lines in one session said a lib module
  "opens a run" because someone was reading it with `sed`, `cat` or a path
  in a heredoc. `claude_hooks.executed_py` now wants an interpreter before
  the file (flags allowed), a command-segment start, or `./x.py`.
- **`labkit-hooks` replaces every hook an earlier labkit wrote, under any
  event.** A jq one-liner running `protocol-check` on each PROTOCOL write
  (an install before `claude-hook post-change`) survived three installs in
  uniagent and doubled every report; `check` saw nothing because it looked
  for missing entries only. A hook command naming `claude-hook`,
  `protocol-check` or `notes-check` is labkit's: `check` names it with its
  event, `install` drops it (`install_hooks.stale_entries`).

## 0.78.0 — 2026-10-10

### Added — `labkit-init`: a lab repo and its areas from labkit's own templates

- **`labkit-init lab [DIR]`** lays out a lab repo: `AGENTS.md` (with
  `CLAUDE.md` pointing at it), `requirements.txt` pinning this labkit at its
  release tag on GitHub (`--labkit-ref` for a pushed commit), `models.toml`,
  editor and type-checker settings, `experiments/`, `data/raw` →
  `data/prepared`, `lib/`, `notes/{theorie,messung,results}`, and the guard
  test that the shared helpers resolve to the package. The lab standard is
  not copied; it comes with the pin.
- **`labkit-init exp <NAME>`** stamps an area — protocol (pilot part,
  `--report` for the † fields, `--cost seconds` for the seconds cut), script
  skeletons, README, the area's test — and `--explore` the entry before an
  area exists. Ported from the house scaffolder; its `sync`, thread and
  legacy-copy detection stay out.
- The templates ship in `labkit/templates/`; none names a house path.

### Changed

- **`usability stage`** stamps its probe repo with `labkit.scaffold`, not
  the house scaffolder under `~/.claude/resources`: the probe runs without
  the author's machine, and the stamped condition is labkit's own (English
  `AGENTS.md`, no copy of the standard). `scaffold_sha` hashes the scaffold
  and its templates.
- Messages and docs name `labkit-init exp` where they said `lib exp`.

## 0.77.0 — 2026-10-10

### Breaking — the lab standard ships with labkit, in English

- **`labkit/docs/standard.md` is the lab standard; `labkit/docs/rules.tsv`
  its ledger.** Both are package data. The German standard was translated
  block by block, reviewed and adapted for labs outside the author's house
  (`docs/standard-translation.md`). A lab refers to the standard through its
  pin, never a copy.
- **`labkit-audit` reads the packaged standard**, not the repo's
  `docs/arbeitsstandard.md`; the code-check bundle quotes the severity
  legend from it. Last version that reads `docs/arbeitsstandard.md`: 0.76.0.
- **Rule names in messages and docstrings are English** (`AS-015 Preflight
  audit before freezing`, was `AS-015 Preflight-Audit vor dem Einfrieren`);
  ids are unchanged. Last version with the German names: 0.76.0.

### Added — `labkit.rules`

- **The one home of the rule ledger, the head parser and three checks**:
  `check_registry` (heads against ledger), `check_ledger` (the ledger only
  grows), `check_refs` (every reference exists and names its rule).
  `python -m labkit.rules check | ledger | refs | show`; a house rule's
  number is listed with status `house`, and `show` says its text is not
  distributed; a row marked `moved:<where>` is left to the ledger it moved
  to. `tests/test_rules.py` holds every living reference in labkit to the
  ledger.

## 0.76.0 — 2026-10-09

### Added — `batch.Store.ledger`: the balance of an item-by-item run

- **Every input item on exactly one row, or the run does not complete.**
  `store.ledger(records, expect={...})` returns a `Ledger`: missing,
  duplicate, stray ids, rows without an id, and per expected field the
  rows that carry another value (`expect` takes a constant — a prompt
  hash — or a function of the row's input record — an item hash).
  `ledger.counts()` goes into `run.metrics`; `ledger.require_complete()`
  raises SystemExit naming every gap, and raised inside
  `with runlog.run(...)` it keeps the run from writing completion.json and
  its runs.tsv row. Guaranteed tier: exact, by id. Whether a row's answer
  is valid stays the experiment's. Before, scripts hand-rolled this
  (fallacy-dataset-generation, area 01) because `status` only reported.

## 0.75.1 — 2026-10-09

### Fixed — `batch.Store.status` names duplicate ids

- **A doubled row no longer hides a missing one.** `status` counted the
  output's ids as a set, so a file with one item missing and another on
  two lines looked whole. It now lists ids on more than one row under
  `duplicate` (absent when there are none). Found in
  fallacy-dataset-generation, area 01, whose script had hand-rolled the
  balance for exactly this case.

## 0.75.0 — 2026-10-09

### Added — `labkit-calltree`

- **The call tree of one real run, cut to the command's package.**
  `labkit-calltree labkit-audit -- <args>` (or `module:function`) runs the
  command under a profiler and prints, per call path, `module.qualname
  path:line ×N` — only functions of the target's top-level package; one
  called through the stdlib hangs under the nearest package function. The
  editor's call hierarchy says what code could call; this says what one
  run did, from the entry point down. Stdlib `trace --trackcalls` gave a
  flat edge list across every module. A reading aid, not a check: no tier.

## 0.74.4 — 2026-10-09

### Changed — Terms before the question

- **The Terms field is the first field of the Intent**, in three parts per
  word — *everyday word · house term · code word*. Four cold readers met
  every house term 60–90 lines before its definition while the field sat
  under Context, after Result. Template and field guide; the checker reads
  the field by label, so protocols written before keep theirs where it is
  (no standard bump). The README names the home of each kind of word:
  tool (this README), method (the lab standard), lab (`notes/theorie/
  begriffe.md`), protocol (Terms).

## 0.74.3 — 2026-10-09

### Fixed

- **`preflight .` / `finalize .` find the area's test.** A relative area
  path has no `.name`; the test pattern read `tests/test_.py` and the
  area's own test counted as absent ("no tests/test_.py — the resolution
  check has no permanent form"). `area_tests` resolves the path first.
  Found on a thesis repo, 2026-10-09.

## 0.74.2 — 2026-10-09

### Changed — entry points and docstrings (part 3 of the cold reading)

- README: the Terms table now defines promise, criterion, admissibility,
  branch, binding, answering run, derived run, scope hash vs stamp, and
  freezing; "five layers; the first and the last cannot be forgotten";
  `runlog`, `preflight`, `usability`, `labkit-audit` lines say what they
  list or are not (`labkit-audit --mode preflight` is the agent audit, not
  the `preflight` gate).
- architecture: six links, one row per check, each row named by what it
  checks; `intent-check` placed at both stages it runs.
- runlog: the file list carries outputs.json and completion.json; the
  index refers to `RUN_INDEX_COLS`; `_prov` / `continues` / `derived_from`
  contrasted in one table; `Run.__init__` lists its ten refusals in order
  with their exception types; `_finalize` says output problems are notes
  and `completed` vouches for the record, not the outputs.
- batch.Store names its two modes; finalize names station 1's checks with
  their grades and station 5 as "frozen source and tracked files", the
  summary line says "review the warnings above"; preflight's stations are
  numbered 1–7 flat, the printed-never-counted lines marked, the early end
  on an unparseable head named; scope_sha says exactly what the stamp
  covers and what not; intent-check's exit codes 0/1/2 documented.

## 0.74.1 — 2026-10-09

### Changed — names (part 2 of the cold reading)

One word, one thing. Every reader in the package, its tests and docs
renamed with it; no alias kept.

| was | is | because |
|---|---|---|
| `protocol_check.id_in_head` | `id_in_git_head` | it reads git HEAD, not the protocol head |
| `promises.PromiseBlock` | `PromiseTables` | "block" is also the whole ```toml block |
| `promises.block_owed` | `promise_tables_owed` | same; the docstring now holds the owed table |
| `promises.registered_ids` | `ids_in_prose` | "registered" is also the data side |
| `protocol_check.intent_missing` | `seconds_registration_missing` | "intent" is also the promise ids |

`protocol_check` no longer repeats the owed condition around the call;
`finalize` no longer shadows `dataclasses.field` with a local.

## 0.74.0 — 2026-10-09

Four cold readers over the package (code-clarity, one per layer, 38
findings): what a newcomer gets wrong. This release fixes what was
behaviour, 0.74.1 the names, 0.74.2 the entry points and docstrings.

### Breaking

- **Run state `unreadable`.** A run whose config.json cannot be read was
  listed as `corrupt` — the word for completion.json without
  metrics.json. It is now `unreadable` (`runs.run_facts`,
  `runlog.active`, `runlog` listings, `FAILED_STATES`); a reader of the
  state no longer has two meanings for one word. Last version with the
  shared word: 0.73.1.

### Changed

- **`AnsweringRun.run_dir` is None whenever `blocker` is set.** A newer
  run with an unreadable binding returned the older run's directory next
  to the blocker; a caller reading only `run_dir` took a run the function
  forbade. `reports_intent_keys` (new) is False when no bound run reports
  an intent key and the newest was taken anyway: `finalize` blocks (a
  probe or producer run is not an answer — only when the protocol
  registers ids), `intent-check` says so.
- **A run directory exists only with its config.json.** Git, environment
  and model alias are read before mkdir; a failure while writing the
  record removes the directory. Before, the leftover read as `legacy`.
- **`protocol-check` names the should-fields** a pilot still owes in its
  pilot note; the `missing (should)` loop that never printed is gone.
- **`labkit-audit`** prints a NOTE when the report lists BLOCKER/WARNING
  lines while the verdict line sums to zero; the verdict line still
  decides (an auditor may correct itself).

## 0.73.1 — 2026-10-09

### Added

- **Arm lines in `Model / tool`, held by finalize.** A protocol that
  compares two profiles names them — `Arm \`before\`: register/profiles/x.toml
  @ <fingerprint>, model=<alias>` — and `finalize` warns when the profile
  file is missing, or the fingerprint or alias is not in the answering
  run's config.json (the profile changed after the stamp, or the run did
  not record it). Optional: no arm line, nothing checked. Template and
  field guide say the form; the diff between the profiles goes verbatim
  under Prompt. Asked 2026-10-09: "what are before and after?" — the
  answer sat 60 lines below the criterion and the fingerprint only in
  the run.

## 0.73.0 — 2026-10-09

### Added

- **`labkit-audit --mode clarity` — a newcomer's reading of an area.** The
  code-clarity agent's area mode ships with the package
  (`code-clarity.agent.md`): README, protocol and `scripts/01_measure.py`
  read in the order a person opens them, findings only where that reader
  would get the behaviour wrong (template residue, a term before its
  definition, a docstring that omits a conjunct, a case id without its
  kind, two languages with no shared word), each with its line and the
  smallest fix; `verdict: N findings (M would be answered wrong)`. Exit 1
  on findings, 0 on none, 2 on no reading. Static evidence: it stamps
  nothing and never blocks; `preflight` names it as due before freezing.
  Measured first on uniagent area 18 (10 findings, 6 wrong readings; the
  README's template residue on top).

## 0.72.3 — 2026-10-09

### Added

- **A resumed output file names the run it continues.** `batch.row_runs`
  reads which runs wrote a JSONL file's rows (`_prov.run` per row);
  runlog records per output `rows_from` (run_id → rows) and `continues`
  (the runs whose rows the file already held), and `completion.json`
  carries `continues` — "this run continues that one" stands in the
  record, not only in the rows. `finalize` holds every JSONL output to
  the run: rows may come from the run itself, from the runs it continues,
  or — for a derived run — from its derived_from lineage; rows from any
  other run are a blocker (a file of two measurements), rows without
  `_prov` a note. Additive keys; older records read as before.

## 0.72.2 — 2026-10-08

### Added

- `finalize` warns when the answering run called a model (`llm_retries`
  recorded or `model_calls` > 0) and no run in its lineage recorded
  `models_resolved` — the alias was not under `model`/`*_model`
  (`finalize.model_provenance_gap`). `labkit-params` marks a resolved
  model spec recorded under another key (`judge`) as static evidence:
  recorded, not provenance labkit holds. Neither reads the old key.

## 0.72.1 — 2026-10-08

### Added

- **`Answering run` field** in the protocol's Result block: one run_id a
  person reads instead of deriving it from the answer line (round 15: the
  fresh run was named, not the derived one that answers). A projection of
  `runs.bound_answering_run`, never a second binding: `finalize` refuses
  the line when it names another run, warns while it still says "none
  yet"; `protocol-fill` writes it. Protocols without the line are unaffected.
- Template: the Summary opens with `Question †`, the Result is its answer;
  `Deviations after freeze` beside the pre-freeze `Changed`; the head's
  legend points to `protocol-check --contract` for what a tier owes.

## 0.72.0 — 2026-10-08

### Breaking

**Protocol standard 0.19: this labkit reads standard 0.19 only.** What
the standard changes: **every reportable run is held to a registration
that is data** — a frozen protocol and every full run (`long=True`; at
`cost = "seconds"` every run) owe the `[[promise]]` tables, and a run
records every registered constant unchanged. Only an unfrozen pilot
(`long=False`) runs without tables; `finalize` blocks an answering run
that recorded none. The seconds cut is a registration in prose AND in
tables, so the machine chain (block digest, scope hashes, constants)
holds for every run a number is reported from.

Versions, two statements kept apart: the last version that *reads*
`standard = "0.18"` is 0.71.0; the last version that *runs the 0.18
contract* is **0.70.0** — 0.71.0 enforced the new rule on 0.18 protocols
and is a transitional release, not one to reproduce an old registration
with. A protocol stamped under 0.18 stays unchanged and is checked, run
and reproduced with the repo's commit and labkit ≤ 0.70.0. A repo may
raise its pin regardless, since the hooks check only staged protocols —
only an edit to an old protocol at the new pin is refused (`[protocol]
standard = "0.18", this labkit reads "0.19"`). Two standards in one
labkit would be a legacy path; `standard` is stamped and never edited.

## 0.71.0 — 2026-10-08

### Breaking

**Frozen protocols require promises, and every promised constant must be
present and equal in the run config.** Last permissive version: 0.70.0.

- `frozen = true` without a `[[promise]]` table is a MUST failure in
  `protocol-check`, a blocker in `preflight` and `finalize`, and `runlog`
  refuses every run bound to such a protocol before `mkdir` — not
  acknowledgeable (`promises.promise_tables_owed`, the one home of the rule).
- `runlog.run(config=...)` under a block refuses the run before `mkdir`
  when a registered constant is missing from `config` or carries another
  value — type-strict (`True` is not `1`, `1` is not `1.0`). The record
  therefore guarantees: every registered constant, unchanged. Whether the
  formula uses it right stays the agent audit's question.
- A constant is named like the config key it is recorded under —
  `^[a-z][a-z0-9_]*$` — and stands in exactly one promise;
  `promises.parse_block` refuses `MIN_F1` and a name declared twice.
  `promises.all_constants(block)` is what a script passes to its config
  object. `constant_records` moved from `intent_check` to `promises`.
- `intent-check`/`finalize`: a registered constant absent from the record
  is a finding (it was invisible); the message names the last permissive
  version for old runs.
- The protocol template stamps the tables (`[C1]` margin, `[A1]`
  max_empty, `[A2]` null_band_items, scope `scripts/01_measure.py`); the
  measure template builds its `MeasureConfig` from them
  (`promises.all_constants(promises.load(PROTOCOL))`), the stamped test
  holds every registered constant to a field. A `--quick` stamp keeps the
  tables without constants.

### Rollout

Only forward: an existing frozen protocol is a registration — adding
tables to it is a new registration, not a migration. Repos with frozen
protocols without tables (uniagent 01–14) stay on their pin (0.70.0) and
raise it when a new area starts there; `finalize` would otherwise block
their frozen areas.

## 0.70.0 — 2026-10-08

### Breaking

- **A derived run records no model resolution.** `runlog.run(...,
  derived_from=...)` leaves `models_resolved` empty: its rows are the
  parent's, and resolving the alias under today's `models.toml` recorded a
  provenance the rows never had. `runs.model_provenance_run(run_dir)` walks
  `derived_from` to the run that recorded the model (None when none did,
  loud on a missing ancestor or a loop). Last version resolving on derived
  runs: 0.69.1.

### Added

- **`labkit-params <AREA> [--run ID] [--protocol FILE]`** — the values the
  answering run ran with, one table: the protocol's registered constants
  against the record (equal / different / missing), every recorded config
  key, the model that answered (from the `models_resolved` of the run that
  recorded it, walking `derived_from`), and UPPER_CASE module constants
  the record does not carry. Each row names its home and its tier; the
  view claims nothing about the record's completeness (round 13: "where
  to start" between protocol, script and runs).
- `intent_check.constant_records` (states equal / different / missing);
  `promised_constant_mismatches` reads `different` from it, unchanged.
- `repo.choose_protocol(area, protocol, tool)` — finalize's choice of the
  area's protocol, now shared.
- `finalize` step 4 warns when the area's README has no
  `<!-- labkit:route -->` block, or the block does not name the protocol,
  `runlog`, `labkit-params`, `scripts/01_measure.py:evaluate_rows` and
  `config.json`, or the script defines no `evaluate_rows`
  (`finalize.readme_route`). The README points; it copies no question,
  answer, run id or threshold — a hand-written formula pointer went stale
  within a day (area 08, 2026-10-08). The stamp writes the block.

### Changed

- **One choice of the run that answers**: `runs.bound_answering_run(area,
  pid)` → `AnsweringRun(run_dir, skipped_newer, exclusions, blocker)`;
  `intent-check` and `finalize` present its outcome instead of choosing
  twice (`run_facts`, `bound_runs`, `newest_with_intent_keys`,
  `newer_unreadable` moved from `intent_check` to `runs`).

## 0.69.1 — 2026-10-08

### Added

- `finalize` step 4 warns on stamped `<…>` placeholders left in the area's
  README (`finalize.readme_placeholders`): a README that still carries the
  stamp's blanks tells a reader nothing and looks as if it did (round 11).

## 0.69.0 — 2026-10-08

### Added

- **A run records the command that started it** (`command` in
  config.json, `sys.argv`), and **`runlog <area>` lists the finished runs**
  after the open ones: one line per run — a fresh run of the script or
  derived from which run (its rows re-evaluated), the commit and whether
  there were uncommitted changes (and how large the patch is), and the
  command — the facts a person returning to an area collected from
  config.json keys and a patch file and got wrong (code-navigation
  round 11: 1 of 8). `runs.run_summary` is the one reader of those facts.
  Runs from before 0.69 show "(not recorded)" for the command.

## 0.68.2 — 2026-10-08

### Changed

Found by the new `code-clarity` agent (dotfiles) on finalize:

- The module docstring numbers the steps like `finalize_area`, 0 to 7,
  flat (it still said "2b" and "4b").
- One word, one thing: the measurement run is `measurement_run` in every
  station, not `run_dir` beside it; the collector of blockers and warnings
  is `Findings`, not `Gate` (the gate is the whole command).
- The provenance step says "n/a — protocol cost is not 'seconds'" instead
  of "not a run of seconds", which used "run" for the protocol's cost tier
  three lines from the measurement run. The only output change; exit codes
  unchanged on five areas.

## 0.68.1 — 2026-10-08

### Changed

- Every run artefact has one loader in `runs.py`, each refusing a wrong
  shape with a sentence naming the file (`ArtefactError`): `read_metrics`
  (an object), `read_outputs` (typed `OutputEntry` rows as `runlog` writes
  them, None when the run registered none), `read_completion` (an object).
  finalize, recheck and runlog read through them instead of parsing the
  JSON in place; `completion_state` still decides a run's state by its
  markers. finalize output unchanged on four real areas.

## 0.68.0 — 2026-10-08

### Breaking

Last version with the old names: **v0.67.1**. Python names only.

- One public name, one thing: `preflight.run` is `preflight_area` (beside
  `finalize_area`; `runlog.run` stays the run writer experiments call),
  `protocol_block.load` is `parse_toml_block` (`promises.load` stays the
  script API), `notes_check.collect` / `protocol_check.collect` are
  `collect_notes` / `collect_protocols`.

### Added

- `tests/test_architecture.py` holds the code to the map: it reads the
  layer table of `docs/architecture.md`, fails when a module is missing
  from it or imports upward, and when a public name other than `main` /
  `cli` stands in two modules. The table now lists `cold_reader`,
  `protocol_reading` and `code_navigation` as tools and `install_hooks` as
  a gate (preflight checks the hooks are there).

### Changed

- ruff: every signature annotated (`ANN`, tests exempt), every public
  module, class and function documented (`D1xx`), complexity capped
  (`C901`, 19 functions carry a visible baseline marker); pyright strict
  for `cold_reader`, `code_navigation`, `protocol_reading`.
  `runs.is_alive` answers None for a script name that is not text instead
  of crashing.

## 0.67.1 — 2026-10-08

### Fixed

- **A metrics.json that is not a JSON object could pass the guaranteed
  intent check:** `["c1_pass"]` read as metrics reported `c1`. One loader,
  `runs.read_metrics`, refuses anything but an object with a sentence
  naming the file (`MetricsError`); intent-check, finalize, recheck, runlog
  and usability all read metrics through it (intent-check's own copy and
  its second, direct read are gone).
- `criterion_n_input_mismatches` no longer takes `true` for a count of 1.
- The test fixture for a dead run no longer uses pid 1, which lives in
  many containers; it takes the pid of a process that has ended.

## 0.67.0 — 2026-10-08

### Breaking

Last version with the old names: **v0.66.1**. Python names only.

- `finalize.run` is `finalize_area`; its `run_dir` is `measurement_run`,
  and its plan says once what a measurement run is. A person reading the
  function took "no run" for "the protocol is missing": the function, the
  experiment's run and the variable all said "run".
- `finalize.provenance_owed` is gone: the condition stands where it
  decides, `if head.cost != "seconds"`. Behind a negated helper name the
  same person read that provenance is checked for cost = hours.

### Changed

- The last line of `finalize_area` says what `report` returns (1 if any
  step found a blocker, else 0). Output and exit codes unchanged on six
  areas, two without a run.

## 0.66.1 — 2026-10-08

### Changed

- `finalize.run` shows the whole flow and every condition that decides
  whether a step runs: its docstring is a flat-numbered plan (0 to 7, each
  with its condition, and that a blocker never stops a step), and the body
  carries the `if`s — skip without a run, provenance only for seconds, the
  only early end at step 0. The stations print no header and check no
  `None` any more; a station that needs a run takes `run_dir: Path`. Why:
  a person answering behaviour questions (code-navigation round 8) missed
  exactly the conditions that sat one level down, in both earlier
  versions; sub-numbers like "2b" confused. Output and exit codes
  unchanged — compared on seven real areas and on two areas without a run
  (cost seconds and hours).

## 0.66.0 — 2026-10-08

### Added

- **`usability human`** — a person answers behaviour questions about a
  repo at the keyboard: one question at a time with numbered choices, the
  time per question, optionally how many questions went to an assistant
  meanwhile (`--count-help`); the verdict (right, missed, invented) only at
  the end, written to `<out>.human.json`. The logic (`human_session`,
  `parse_picks`) takes its input and clock as arguments and is tested.

## 0.65.1 — 2026-10-07

### Added

- Behaviour answers are scored beyond right/wrong: the right choices an
  answer **missed** and the ones it **invented** (a dependency or a path
  the code does not have).
- `usability nav --shuffle SEED` draws the question order from a seed, so
  agents compared across two versions of the code do not all meet the
  questions in one order.

## 0.65.0 — 2026-10-07

### Added

- **`usability nav`: behaviour questions** (`[[choice]]`). A question about
  how the code behaves — what still runs when a step fails, which step a
  later one depends on, which condition yields which exit code — answered
  by picking from a fixed set of choices and scored by exact set match;
  a truth outside its choices refuses at load, an answer outside them at
  scoring. Built to test whether an orchestrator that reads as named steps
  is understood better, not only found faster. A question file may now
  hold only flows or choices.

## 0.64.1 — 2026-10-07

### Changed

- `usability.load_probe_run` reads a staged probe and its latest run once
  (`ProbeRun`: probe, run, config, metrics, the protocol it names, whether
  it is bound by id, the cost tier); `score` and the reading probes use it
  instead of each reading probe.json, config.json and metrics.json
  themselves (the last open finding of the 0.64.0 audit). Scores of the
  round-9 probes recomputed: identical.

## 0.64.0 — 2026-10-07

Worked off a code audit of everything changed since 0.58.1 (two fresh
reviewers, correctness and structure; every finding checked in the code).

### Breaking

Last version with the old names: **v0.63.2**. Python names only; no file
format changes.

- `protocol_reading.score_answer` is `score_reader_answer`, `score_glance`
  is `score_glance_answer`; `code_navigation.score` is `score_nav_answer`,
  `prompt` is `nav_prompt`; the usability handlers are `cmd_reader`,
  `cmd_read_score`, `cmd_glance`, `cmd_glance_score`, `cmd_terms`,
  `cmd_nav`, `cmd_nav_score` (the console commands are unchanged).
- `finalize.check_intent_ids` is `check_intent_keys_in_metrics` — it was a
  second function of the same name as `code_check.check_intent_ids`, doing
  something else.
- The scorers refuse instead of scoring wrong: a yes/no given as a string
  ("true"), a pass flag in metrics.json that is not true/false, a named
  number missing from metrics.json, a place that is not "path:line", a
  flow answer that is not a list of strings, a line-range truth outside
  its file, a flow step pattern that does not compile (refused at load,
  before the agent runs).

### Fixed

- Terms coverage matches a term as a word of its own ("RAG" no longer
  occurs in "paragraph") and keeps short abbreviations (CI, N), which were
  dropped; a Terms link with an anchor (`g.md#x`) is read. Today's
  measurements were rechecked: none changed.
- `nav-score` finds an absolute path inside the repo; two flow steps named
  in one answer item both count.
- `finalize`: every blocker and warning goes through `Gate.block` /
  `Gate.warn` — blockers of the completion station and open fields now
  print with the same `BLOCKER:` / `warning:` prefix as the others.

### Changed

- New module `labkit/cold_reader.py`: what every cold-reader probe shares
  (the newcomer persona, the answer hand-off, loading and reading the
  answer) — it was copied three and four times.
- Module docstrings of `protocol_reading` and `usability` name everything
  they hold; docstrings for the finalize stations and the new dataclasses.

## 0.63.2 — 2026-10-07

### Changed

- `finalize.run` reads as its seven stations, one call each
  (`check_completion` … `check_criterion_n`), over a `Gate` that collects
  blockers and warnings; the decisions inside got names and tests of their
  own — `choose_protocol`, `answering_run`, `cited_run_mismatch`,
  `provenance_owed`. Output and exit codes are unchanged, checked line by
  line on six real uniagent areas. Why: CS-006 One function, one thing —
  and keep I/O at the edges (210 lines of stations separated by section
  comments, the data each station depends on hidden in shared variables),
  not findability — code-navigation round 5 found the inline version
  followed without a miss.

## 0.63.1 — 2026-10-07

### Changed

- `usability nav-score` counts an answer whose path names a file by its
  tail alone (`runlog.py` for `labkit/runlog.py`) when that tail names
  exactly one file in the repo; an ambiguous tail does not count. Round 6:
  one agent found all five places and dropped the package folder from
  every path, scoring 0/5.

## 0.63.0 — 2026-10-07

### Added

- **`usability nav`: line ranges and flow questions.** A truth may be a
  line range (`path:L120-L135`) for logic that has no name of its own — a
  range holds for the commit it was read on. A `[[flow]]` question asks for
  an entry point's steps in order and is scored by how many registered
  steps the answer names in the registered order. Built to test whether an
  entry point that reads as a sequence of named steps is easier to follow.

## 0.62.0 — 2026-10-07

### Breaking

Last version with the old names: **v0.61.0**. Run records and protocols do
not change (the recorded key `declared_scope_sha` stays); only Python
names do.

- `protocol_block.HEAD_FIELDS` is `PROTOCOL_HEAD_KEYS` — the settings at
  the end of every protocol, told apart from the run's `config.json`.
- `scope_sha.imported_lib` is `imported_repo_helpers` — the helper files
  the area's scripts import, told apart from one promise's declared-scope
  digest (`promises.declared_scope_sha`, whose docstring now says so).
- `intent_check.constant_findings` is `promised_constant_mismatches`;
  `finalize.criterion_n_findings` is `criterion_n_input_mismatches` — two
  checks against what a run recorded, named for what they compare.

### Added

- `preflight.area_test_python` — the interpreter that runs an area's tests
  has a name of its own (was four lines inside `area_tests`).

Why: in code-navigation round 3 a weaker reader (Haiku) found 5 of 10 in
labkit against 9 of 10 in uniagent; every labkit miss sat at one of these
pairs or at the unnamed interpreter choice (CS-015 Make the code findable
by name; `docs/usability/2026-10-07-code-navigation.md`).

## 0.61.0 — 2026-10-07

### Added

- **`usability nav` / `nav-score`** (`labkit/code_navigation.py`) — how
  fast a newcomer finds their way in a repo's code. A cold agent gets
  questions that describe a behaviour, never a name, and answers each with
  `path:line`; the truth is a function, class or module-level name in a
  TOML question file, resolved from the source with `ast` (a truth that no
  longer exists refuses to score). Effort comes from the agent's
  transcript: calls by tool, files opened, seconds. Built to measure before
  a navigation rule enters the coding style.

## 0.60.1 — 2026-10-07

### Changed

- The Summary's Result says whether the bar set before the run was met:
  four readers of the first ten lines took the number and the limit away
  from the 0.59 probes but not the verdict (the uniagent Summaries, which
  said it, were read right).

### Fixed

- `protocol_reading.entry_for` returned the first line that mentioned a
  term — often a protocol's pointer to the glossary — so the explanation
  judge saw no definition. It now splits the glossary into entries (a
  bullet with its continuation, each `*term* — …` inside a Terms line) and
  takes the one whose label names the term; a shorter label inside the
  term ("Position" in "Positions-Zuordner") no longer wins.

## 0.60.0 — 2026-10-07

### Added

- **`usability glance` / `glance-score`** — a reader who sees only the first
  ten lines of the file, as they are (head or form text using them up is
  the finding). `protocol_reading.glance` reports the excerpt's characters
  beside its lines (one field per long line holds more than a wrapped one)
  and, mechanically, which Summary fields begin inside it. Round 9 showed
  that asking a whole-protocol reader what it knew at line ten is
  self-report.
- **`usability terms`** — the reader's unclear terms against two layers: a
  term in the Summary must be plain there; a term elsewhere may occur in
  Terms or in a glossary note Terms links. Occurrence is static evidence;
  `terms_judge_prompt` asks a reader whether the entry explains the term.
  Ids match as patterns (digit runs → NN).

## 0.59.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.58.1**.

- **A protocol with a documented run owes a Summary for a person:**
  `Result` (at most two plain sentences carrying the question, no ids, keys
  or run_ids), `Limits` and `Next step` — on every tier, seconds included
  (they are in the seconds cut). `Status` is gone; `Next step` moved from
  Follow-up into the Summary (protocols that have it in Follow-up keep it
  valid). A protocol with a run but no `Limits` fails protocol-check, and
  the message names the missing field instead of "Result/Raw output".
- **The stamped protocol opens with the Summary;** the pointer to the
  field guide and the toml head stand at the end under `## Head`.
  protocol-check reads the head anywhere; the Head section counts neither
  as template text nor as form before the first field.

### Changed

- The criterion's placeholder shows how an id is written (`[C…]` with its
  number, C1 → `c1_pass`); a writer missed it in round 8.
- The cold reader (`usability reader`) is a newcomer, not a colleague, and
  answers checkable questions — the number, whether the criterion held,
  whether admissibility held — that `read-score` holds to the run
  (`protocol_reading.Truth`), plus what it understood after ten lines.

## 0.58.1 — 2026-10-07

### Added

- **`llm.last_thinking()`** — the reasoning trace of this thread's most
  recent completion (ollama `thinking`, OpenAI-style `reasoning_content` /
  `reasoning`), "" when the backend returns none; reset before every
  attempt, so a call never shows a previous call's trace. labkit read the
  field and dropped it; uniagent could not explain a false classifier answer
  afterwards because only the answer was kept.

## 0.58.0 — 2026-10-07

### Changed

- **Less form in front of a reader.** The stamped toml head carries keys
  only — what each key means is in the field guide. `Analysis audit †` is
  no longer stamped at `cost = "seconds"`: there the audit comes when the
  number is promoted or steers a decision, and the field is added then.
- **Terms of this protocol asks for the writer's own coinages**: constants,
  lanes or arms, item and case ids, the model alias.

Cold readers of round 7 (`docs/usability/2026-10-07-protocol-reading.md`)
could place the writers' results; most of what they could not place came
from the stamped form, the rest from unglossed coinages.

## 0.57.0 — 2026-10-07

### Changed

- **Protocols open with the answer for a person.** The stamped protocol
  starts with a three-line pointer and the toml head; the legend (cuts,
  † fields, intent ids, rule references, budgets) moved into
  `protocol-field-guide.md`. The Summary lists **Result** first: at most
  three plain sentences, result not procedure, the limit inside the
  sentence, no ids, keys or run_ids. "One field, one line" became "one
  field, one statement": more than two items as a list or a small table
  under the label; the Answer field gives the verdict per id, the run_id
  and the numbers as a table. Labels are unchanged; existing protocols
  stay valid.
- The auditor's MODE analysis adds two `READ` points: a Summary that does
  not open with the result (or carries ids and keys), and a `·` chain of
  more than two items.

From a reader's assessment of uniagent's protocols ("strong in content,
read like audit papers for the system"): about 65 lines of form came
before the first sentence for a person.

## 0.56.0 — 2026-10-07

### Changed — may block where 0.55.0 passed

- **A frozen protocol owes its area test.** `preflight` turns a missing
  `tests/test_<NN>_<name>.py` from a warning into a blocker once
  `frozen = true` — the permanent resolution check (AS-016) is a gap like
  any other at the freeze.
- **`finalize` runs the area's tests, on every tier.** A failing test is a
  blocker before a number is reported; a missing one is no finding there.
  At `cost = "seconds"`, where preflight is not owed, this is the only
  place they run.

### Fixed

- Area tests are found by the stamped name (`test_<NN>_<name>.py`, split
  files `test_<NN>_<name>_*.py`), no longer by `test_*<name>*.py`: area 08
  of uniagent ran area 09's test, whose name extends its own.
- Area tests run with the repo's interpreter (`.venv/bin/python`), not the
  caller's: a gate started from another venv failed them on a missing
  package.

## 0.55.0 — 2026-10-07

### Added

- **A session log, for debugging what an agent did before a run.** Every
  `claude-hook stop` appends one line to the repo's
  `.git/labkit-sessions.jsonl` (inside .git: local, never committed):
  session id, transcript path, time, and the runs made since that
  session's previous stop. `claude-hook sessions --run RUN_ID` finds the
  session — and so the transcript — a run came from.
- `usability score --archive DIR` keeps a probe's transcript (gzip),
  timeline and score; `usability trace` reads a `.jsonl.gz` as well.
  Claude Code deletes transcripts after `cleanupPeriodDays` (30 by default).

## 0.54.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.53.1**.

- **`src/` is a repo-local root beside `lib/`, and imports resolve to the
  module, not the package.** The audit stamp and the key search follow
  `import a.b`, `from a import b` and `from a.b import c` to the module and
  the `__init__.py` files on the way — no longer every file of a package.
  A repo whose measured code lives in `src/` (uniagent) gets a stamp that
  finally covers it; any repo importing from a package gets a narrower,
  exact one. Either way an existing `preflight_audit` stamp reads as
  changed: restamp after looking, or re-audit.

### Fixed

- **`code-check` finds registered keys in imported repo code.** It read
  only the area's scripts, so a key written in `src/measure/comparison.py`
  made four promises "absent" — blockers against correct code, found on
  the first real upgrade (uniagent 0.45 → 0.53).

## 0.53.1 — 2026-10-07

### Fixed

- **`labkit-hooks install` no longer erases a repo's own hook.** A
  `.githooks/pre-commit` that labkit-hooks did not write is kept as
  `pre-commit.before-labkit` (a second one refuses), and the versioned hook
  runs the repo's own `.githooks/pre-commit.local` when it is executable —
  the repo owns that file, labkit-hooks never writes it. Found on the first
  real upgrade (uniagent): its hook ran a replay test of runs 07/08.

## 0.53.0 — 2026-10-07

What six rounds of cold-agent probes (`docs/usability/2026-10-07-remeasure.md`)
and one reader's feedback on a frozen protocol turned up.

### Changed — may block where 0.52.0 passed

- **The prompt drift check runs on stamped areas.** `PROMPT` constants are
  computed statically (names, `+`, f-strings, `str.join` over a constant);
  the skeleton's `PROMPT = "..." + ANSWER_LINE` used to be unreadable, so the
  check never ran on a stamped area. Every fenced block under the Prompt
  field counts (one block per variant is a written form). A prompt it
  cannot compute is a WARNING, never a silent pass.

### Added

- `protocol-fill PROTOCOL --prompts` writes the Prompt block from the area
  scripts' `PROMPT` / `PROMPT_<VARIANT>` constants.
- `protocol-check` names stamped list placeholders left behind (`- <run_id>
  — <…>`, `- <…>`) and warns on a field that references another area
  without a link ("wie Bereich 07").
- `code-check`, `finalize`, `preflight` and `runlog reindex` take an area
  by its bare name as `lib exp` prints it (`01-<name>` or `<name>`).
- `usability score --transcript F` and `usability trace F`: what a probe
  agent did, measured from its session transcript (`agent_transcript`);
  `usability stage` stamps each task as the house route does and writes
  `<dir>.prompt.md` (the repo's CLAUDE.md first, as a session loads it).
- The auditor agent's MODE analysis adds `READ` lines on the protocol's
  readability; they enter no verdict.
- Field guide rule 8 (write for the reader who opens only this file) and a
  legend line in the template; the template names `protocol-fill` and the
  safest placebo for a null lane.

### Fixed

- `runlog`'s lock check reads an editable install's freeze line (`-e
  git+…#egg=labkit`) and compares it with the checkout's HEAD; a lock
  written by `pip freeze` no longer reports drift against itself.
- At `cost = "seconds"` only the cut's fields count as open placeholders,
  and fields written after the run only once a run is documented.
- `finalize` and `protocol-check` repeat their blockers in the last lines.
- `protocol-fill` reads fields through `protocol_check.fields` (one parser;
  `protocol_fill.open_fields` is gone — use
  `protocol_check.placeholder_fields`).
- "no such area" names the directory a relative path resolved against.
- `--contract` opens with the seconds cut and marks its lists as the full
  form.


### Changed (rule references)

- **Rule references are AS-/CS- code + name.** Messages, the shipped
  protocol template, the field guide and the auditor agent cite rules of the
  Arbeitsstandard as `AS-015 Preflight-Audit vor dem Einfrieren` instead of
  `§2.A12` (the ledger is `~/.claude/resources/rule-registry.tsv`; every old
  §-id stays resolvable as an alias in the register). A finding line's rule
  field reads `AS-nnn <title>`; `labkit-audit` never parsed that field, so
  nothing breaks. Dated records in `docs/usability/` keep their §-ids.

## 0.52.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.51.0**.

- **The audit stamp follows every import form, transitively.** `from lib
  import x`, `import lib.x`, `from lib.x import y`, relative imports inside
  `lib/` and packages are resolved from the syntax tree, and a lib module's
  own imports are followed; `from lib import scoring` used to be read as a
  module `lib`, so lib/scoring.py could change under an unchanged stamp.
  Stamps of areas importing that way move. Code that does not parse refuses
  the stamp instead of a guess.
- **A function scope includes its decorators**: `@cache` → `@retry` moves
  `declared_scope_sha`. Runs recorded with a decorated scope function show
  that scope as changed.
- **batch** raises on an unparseable line anywhere but the last (file and
  line named); a torn last line is cut before a resume appends.
- **Run metadata is checked for shape** in `read_run_config`: not an
  object, a non-integer `schema_version` or a malformed `protocol` binding is
  a `RunConfigError`, not a later AttributeError.

### Added

- `labkit-audit` holds the auditor's `scope:` list against the stamp and
  warns on every file only one side names.
- The `dev` extra carries the coding style's tools: `pytest`, `ruff`,
  `pyright`; a one-off usability script is excluded from ruff.

### Fixed

- The suite writes no lease into `~/.labkit` (`tests/conftest.py`), and the
  `ps` integration test skips where `ps` is missing.

## 0.51.0 — 2026-10-07

### Added

- `labkit-hooks install|check`: the hooks come with the pinned labkit —
  `.githooks/pre-commit` (protocol-check, finalize --if-reported, guard
  test), `git core.hooksPath` (a manual step per clone before, so the hook
  silently did nothing) and the claude-hook entries in
  `.claude/settings.json` (foreign hooks and keys kept). Each hook names the
  labkit version that wrote it; rerun `install` after a pin raise.
  `preflight` warns when hooks are missing or from another version.
- `claude-hook stop`: before the agent ends its turn, every protocol
  changed in the session whose answer cites a run goes through `finalize`;
  blockers send the agent back (exit 2), once per stop.

## 0.50.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.49.1**.

- **A full run checks its audit line.** At minutes/hours `preflight_audit`
  must name the `scope sha` the area's code has now (`labkit-audit` and
  `scope-sha` print it), or say `n/a — <reason>`; a line without a stamp,
  or with the stamp of code that changed since, refuses the run. The line
  was written by hand and never checked — an invented or stale audit looked
  like a real one. `protocol-check` warns on the same drift (after the run
  analysis scripts change legitimately). `scope_sha` moved to layer 1.

### Added

- `finalize --if-reported PROTOCOL...` — the commit gate: every protocol
  whose "Answer to the question" cites a run goes through finalize; the
  house pre-commit hook calls it. `finalize` also blocks when the answer
  cites another run than the one the checks hold. Nothing showed whether
  finalize ever ran before a number entered the history.

## 0.49.1 — 2026-10-07

### Changed

- A promise scope given as an absolute path is refused: scopes are relative
  to the protocol's directory (`../../lib/x.py` stays allowed).

### Added

- `code-check` warns (static evidence) when a declared scope sets a promise
  constant itself as a literal — `MIN_MEAN = 1.4` against 1.5 in the block —
  instead of reading `promises.constants()`.

### Fixed

- Field labels in numbered lists (`1. **Unit:**`) are read; fields inside a
  multi-line HTML comment are not.
- A bare label with sub-bullets or an indented paragraph below it is filled,
  not a placeholder (found migrating the thesis starter's example).
- `usability score` on an unreadable run, `intent-check --metrics` on a legacy
  run and a numeric `standard` end in a sentence that says what to do.
- `protocol-check` scans the repo's protocol ids once per invocation.
- The type checker reads the repo's own `.venv` (`[tool.pyright]`); the 19
  errors it then showed are fixed — two test classes overwrote
  `TestCase.run` with a path.

## 0.49.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.48.1**.

- **Stricter fields.** A placeholder is `<…>` (opened and closed), `TODO`,
  a bare `n/a — <why>` or an empty label without a code block; `TODO`
  used to count as filled. Every † field is owed: Intent/Setup ones at
  freeze, Summary/Result ones once frozen and a run is documented (new
  level `report`, Analysis audit included). `Data / scope`, `Unit` and
  `Model / tool` are musts in the full form. `frozen = true` at cost
  seconds is a must finding.
- **A full run on an unstamped protocol id is refused** before the run dir
  exists.
- **The promise digest** is over the promises as read (normalized) and
  recorded with its format; a run from 0.46/0.47 is reported as such, not as
  "the promises changed".
- **One audit stamp**: `scope_sha.area_stamp` (scripts, imported `lib/`,
  extra files, pin; paths relative to the repo root) feeds `scope-sha`,
  `preflight` and `labkit-audit`. Stamps from earlier versions differ.
- **Vendored flat copies are gone**: the `except ImportError` fallbacks for
  student repos had stopped working (modules they needed were never
  copied) and are removed. A student repo pins labkit or stays on its copy.

### Fixed

- A newer run with an unreadable `config.json` is no longer passed over
  silently: `intent-check` and `finalize` refuse the older choice.
- A deleted or unparsable declared scope, a renamed protocol (recheck now
  finds it by id), a non-table `[[promise]]` entry, an unreadable head in
  `usability score` and a broken parent in `derived_from` end in a
  sentence, not a traceback.
- `LABKIT_UNFROZEN`, `LABKIT_DETACHED` and `LABKIT_NO_ENDPOINT_LEASE` act on
  `1` only; `0` used to count as set.
- A ```toml example inside a prompt's code block is no second head; fences
  nest by marker length.
- runlog freezes a directory source (digest over visible files, rows =
  files); `repo.layout_root(".")` climbs.
- `protocol-check` no longer reports comment lines or open placeholders as
  left-over template text.

## 0.48.1 — 2026-10-07

### Fixed (audit of 0.48.0)

- `finalize` judged a different run than its own intent-check: intent-check
  skips newer runs without intent keys (a probe), the other stations took
  the newest bound run. One choice now feeds every station — scope drift,
  provenance and the `c1_n` check ran on the probe and said all clear.
- Ids in the letters K/S/W/N passed `intent-check` as "no intent ids
  registered" with exit 0, every promise unchecked. They are now refused:
  a MUST finding in `protocol-check`, exit 2 in `intent-check` — detected,
  never read.
- A field value written on the line below its label (`- **Question /
  hypothesis:**` + indented text) read as unwritten, so the seconds gate
  refused a written registration. Field values now include their
  continuation lines.

## 0.48.0 — 2026-10-07

### Breaking

Last version that reads the old formats: **v0.47.0**. A repo with frozen
protocols in the old head, runs without `schema_version` or an old run
index stays on its pin until new work starts there.

- **The protocol head is data** (TODO 8). `Standard`, `Protocol id`, `Type`,
  `Cost`, `Frozen before run` and `Preflight audit` moved from prose lines
  into the `[protocol]` table of the protocol's one ```toml block (Standard
  0.18), read by the new `labkit.protocol_block` — `tomllib`, exact keys,
  typed values. A typo is an error naming the field: `Cost: second` used to
  read as undeclared and so as `hours`. A protocol without the table is
  refused by every command.
- **Prose fields by exact template label.** `protocol-check` holds each
  field by its label (`protocol_check.FIELDS`), not by keywords searched in
  the whole file: a word anywhere satisfied a field (`prompt` in a sentence
  covered "Model I/O"), a narrow word failed a filled one (`**Terms:**`). A
  test binds `FIELDS` to the template and the seconds cut to its markers.
  "Answer to the question", "Raw output" and "Analysis audit" are owed after
  the run (the run-unreported check), no longer before it. Removed:
  `check_text`, `graduate`, `severity_of`, `cost_tier_of`, `FROZEN_YES`,
  `TYPE_MEASUREMENT`, `protocol_identity`, `protocol_check.protocol_id_of`
  (`intent_check.protocol_id_of` stays, reading the head), `criterion_present`; new: `check_fields`, `fields`, `owed`.
- **The promise digest covers the `[[promise]]` tables only** (canonical
  JSON), not the block text: freezing or stamping the audit line in the
  head must not read as a changed promise. Runs recorded under 0.46/0.47
  carry the old digest; `recheck` against them reports a changed block.
- **Legacy paths removed:** the intent letters K/S/W/N (only C/A/B are
  ids); protocols below Standard 0.16 and the area-based run choice
  (`choose_legacy`, `gate_metrics`, `latest_metrics`, `runs_by_intent_keys`);
  runs without `schema_version` (state `legacy`, never `completed`);
  `runlog migrate-index`; the measurement short form (`Type: measurement`
  — the seconds cut replaced it); the old admissibility words (`stop
  rule`, `kill`, `Abbruch`); `intent_check.ledger_ids`.
- An unstamped protocol id binds nothing: `intent-check` needs `--metrics`,
  `finalize` reports a blocker.

## 0.47.0 — 2026-10-07

### Changed

- **Template and field guide speak C/A/B** (TODO 7): the protocol template
  stamps `[C]` criterion, `[A]` admissibility condition, `[B]` registered
  branch, with keys `c1_pass`, `a1_pass`, `b1_branch`. The field "Stop rule"
  is now "Admissibility condition", "Registered fork" is "Registered
  branch"; null conditions and anchors carry `[A]` ids. `protocol-check`
  accepts the new label; the old labels (`stop rule`, `kill`, `Abbruch`) and
  the letters K/S/W/N are still read and go with the legacy release (TODO 8).

### Added

- `labkit-audit <AREA> --mode preflight|analysis`: the experiment-preflight
  audit as a command through `labkit.llm` (any `models.toml` alias, default
  `opus`), synchronous with a timeout; the instructions ship with the
  package (`experiment-preflight.agent.md`). Exit 1 on a blocker OR a
  warning, 2 when no audit could be made.

## 0.46.0 — 2026-10-06

### Breaking

Last version with the old names: **v0.45.0**.

- **Run read side moved to `labkit.runs`.** `is_alive`, `run_state`,
  `read_run_config`, `RunConfigError`, `completion_state`,
  `completed_runs`, `FAILED_STATES` are no longer in `labkit.runlog`.
  `runlog._is_alive` and `runlog.is_alive` are one name: `runs.is_alive`.
- **`promises.scope_sha` is `promises.declared_scope_sha`.** Runs record
  `config.json → promises.ids.<id>.declared_scope_sha` (was `scope_sha`).
  The area audit stamp `scope-sha` is unchanged.
- **`code_check.find_protocols` / `find_repo` are `repo.area_protocols` /
  `repo.layout_root`.**

### Stricter (correct inputs pass as before; these now fail loud)

- A v2 run with `metrics.json` but no `completion.json` is no longer
  chosen or accepted by `recheck`, `runlog.Run(derived_from=…)`,
  intent-check's choice for protocols without an id, or `usability score`.
- An unreadable `config.json` shows as `corrupt` in `runlog`, makes
  `runlog --wait` and `runlog reindex` exit 2, and is listed, never chosen,
  by intent-check. An unreadable `metrics.json` ends intent-check with exit
  2 instead of falling back to an older run.
- A git failure inside a repository raises `repo.GitError`; it used to read
  as an empty answer ("clean tree").
- `runlog` no longer swallows an unreadable protocol and names a malformed
  `Protocol id:` in its warning.
- Promise block (protocols that carry one):
  - `code-check` / `preflight` block a malformed block, a declared scope that
    does not resolve, and a declared key that appears nowhere in the code.
  - `finalize` blocks a declared scope changed since the run.
  - `recheck` refuses a note whose promise block or declared scope changed
    since the run.
  - `intent-check` / `finalize` report a block constant the run recorded
    under the same name with another value.
- `finalize` holds `c<i>_n` to the recorded inputs like `k<i>_n`.
- `llm` calls `claude -p` with `--tools ""`: a judgement runs without the
  CLI's built-in tools, so a prompt that says "read <file>" cannot send the
  model to its working directory instead of the inlined text.

### Added

- `labkit.promises`: the promise block — one fenced TOML block of
  `[[promise]]` entries (id `C`/`A`/`B`, key, sentence, declared scope,
  constants); `runlog` records its digest and a hash per declared scope.
  Contract: `docs/promise-block.md`.
- `labkit.runs` (read a run), `labkit.repo` (area protocols, repo root,
  git), `protocol_check.protocol_identity` (one reading of `Protocol id:`).
- `code-check` reads intent keys passed as keyword arguments
  (`r.metrics(c1_pass=…)` drew a false blocker before).
- `endpoint_lease`: atomic record writes under a directory `flock`; an
  unreadable record counts as busy for `UNREADABLE_GRACE_S`, then is
  removed with a message.
- `AGENTS.md` (with `CLAUDE.md` as a symlink), `docs/architecture.md`,
  `docs/coding-style.md` (vendored), `pip install -e '.[dev]'` for tests.

### Unchanged behaviour, new structure

- `intent_check._main` dispatches to `choose_explicit` / `choose_bound` /
  `choose_legacy`; `llm._complete_once` dispatches to one adapter per
  backend.
