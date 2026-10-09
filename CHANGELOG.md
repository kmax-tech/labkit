# Changelog

labkit does not carry legacy paths: a format or API change is a break,
announced here with the last version that still has the old behaviour.
Reproduce an old run with the repo's own commit and the labkit version it
pins (`requirements.txt` / `requirements.lock`).

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
  acknowledgeable (`promises.block_owed`, the one home of the rule).
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
