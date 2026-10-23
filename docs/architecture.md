# Architecture

Where what happens in labkit: the layers, the chain from promise to
reported number, and the one home of each recurring question. Terms are
coined in the README; the promise block in `docs/promise-block.md`.

## Layers

Each layer is a package — a folder under `labkit/` — and a module sits in
the folder of its row. Imports point downward only; no module imports a
layer above it, and no layer imports a tool. Tools may import any layer.
The table maps modules to layers and marks doctrine ([Core and
doctrine](#core-and-doctrine) says what that means); the sections below
explain each layer. Every module stands in the table exactly once.
`tests/test_architecture.py` reads this table and holds the imports and
the folders to it — a new module, an upward import or
a module in another row's folder fails the suite. The shipped assets sit
beside the packages: `templates/`, `agents/`, `docs/`, read relative to
`labkit.PACKAGE_DIR`.

| Layer | Modules | Doctrine (the rest is core) |
|---|---|---|
| 1 · formats and places · `labkit/formats/` | `protocol_block`, `promises`, `protocol_check`, `protocol_history`, `protocol_report`, `standard_contract`, `runs`, `answering_run`, `repo`, `scope_sha`, `rules`, `findings`, `reviews`, `console`, `gate`, `shell`, `files`, `jsonl` | `protocol_check`, `protocol_history`, `protocol_report`, `standard_contract`, `rules`, `findings`, `reviews` |
| 2 · a run and its effects · `labkit/run/` | `runlog`, `provenance`, `start_check`, `runlog_command`, `batch`, `llm`, `llm_specs`, `llm_backends`, `endpoint_lease`, `lanes`, `profile` | `lanes`, `profile` |
| 3 · checks · `labkit/checks/` | `intent_check`, `code_check`, `code_scan`, `gate_label_scan`, `import_check`, `prompt_check`, `run_record_check`, `readme_check`, `recheck`, `notes_check`, `audit_binding`, `result_render`, `report_blocks` | `readme_check`, `notes_check`, `audit_binding`, `result_render`, `report_blocks` |
| 4 · gates · `labkit/gates/` | `preflight`, `finalize`, `report_check`, `claude_hooks`, `audit`, `decision_review`, `install_hooks` | `preflight`, `finalize`, `report_check`, `claude_hooks`, `audit`, `decision_review`, `install_hooks` |
| tools · `labkit/tools/` | `protocol_fill`, `scaffold`, `protocol_cuts`, `repo_check`, `params`, `calltree` | `protocol_fill`, `scaffold`, `protocol_cuts`, `calltree` |
| tools · probes · `labkit/probes/` | `usability`, `usability_score`, `usability_command`, `agent_transcript`, `cold_reader`, `protocol_reading`, `code_navigation` | `usability`, `usability_score`, `usability_command`, `agent_transcript`, `cold_reader`, `protocol_reading`, `code_navigation` |

The third column names the doctrine modules of each row; every other
module in the second column is core.

## Core and doctrine

Two kinds of module ship in labkit, and the difference decides what another
lab may change.

**Core** answers what every lab must answer the same way, whatever its
rules: which run made this number, from which code, data and model, under
which protocol, and does the cited number match the run. Traceability —
`runs`, `scope_sha`, `promises`, `answering_run`, `repo`, the run writer.

**Doctrine** is what another lab could decide differently without being
less scientific: the standard and its rules, the protocol's field
catalogue, the templates and skeletons, the order of the gates, the agent
layer, the note conventions, the usability probes.

**The strike test.** Strike the module. Does a number become less
traceable? Core. Does the lab only work differently? Doctrine.

**The import rule.** A core module imports no doctrine module;
`tests/test_architecture.py` holds that against the table above, with the
crossings that stand today listed by name (`KNOWN_CROSSINGS`) until they
are moved (2026-10-15). The list is not extended in passing.

**Not the house.** Doctrine ships in labkit to every lab. The house is what
holds only for this author's lab — the `LOCAL` rules, the dotfiles, the
German notes — and lives outside the package ([Where what
lives](#where-what-lives)).

### 1 · Formats and places

`labkit/formats/` holds the file formats, their contracts, repository
locations and shared technical helpers. Validation and comparison are pure:
input in, result or error out. Each format reads and writes its own files;
a writer names its side effect, as in `findings.write`. Checks return data;
console output goes through `console` and `gate`.

The protocol modules separate the TOML head (`protocol_block`), promise
alphabet and tables (`promises`), prose fields (`protocol_check`), git
history (`protocol_history`) and the report behind `protocol-check`
(`protocol_report`). `standard_contract` derives the obligations of a cost
lane, release or skeleton from facts the caller supplies; it reads no files.

`runs` reads what a run directory says about itself — its config.json as one `RunConfig`, labkit's fields typed where the record is read, the experiment's own `config` free JSON, nested values handed out as copies; `answering_run` selects
the run that answers a protocol. `repo` locates the repository and its
protocols and runs git. `scope_sha` computes scope hashes and audit stamps.
`rules` holds the standard's rules and checks their references. `findings`
reads and writes audit findings: the auditor records them, a person decides
them, and the gates check those decisions. `reviews` reads and writes a
second auditor's verdicts on those decisions (`labkit-audit --review`):
which record, what it saw, and per decision upheld, rejected or
insufficient — bound to the decision as it stood.

The remaining helpers have narrow responsibilities. `files.write_atomic`
writes one file whole or not at all. `shell.segments` reads a shell line as
simple commands, respecting quotes and excluding heredoc bodies; hooks and
transcript readers use the same parser. `console` provides command exits
and refusals: usage errors go to stderr, findings to stdout, and a reader
closing the pipe exits cleanly. `gate.Findings` collects grades, formats
messages and summaries, and returns failure for blockers. It can also
collect findings without printing when one gate runs inside another.

### 2 · A run and its effects

`labkit/run/` records executions, manages resumable output, calls models
and holds model-slot leases. A run starts in three phases, with the order
and conditions visible in `Run.__init__`:

1. `start_check.prepare` resolves the protocol binding, takes the promise
   snapshot and freezes the config.
2. The start checks cover registration, detachment, the index header,
   data leakage and the freeze gate where required. These refusals occur
   before the run directory is created.
3. Creation records provenance and snapshots. A repeat's draw is reserved
   under the index lock before its record is written.

`provenance` gathers git state, environment, models, data and snapshots.
`runlog` writes the run and index; `runlog_command` implements the console
command. `batch` manages resumable output. `lanes` is the run mechanics of
the stamped two-lane judge — jobs per item and lane, batches, resume, the
probe, the balance, the area's command line — doctrine, since the two lanes
and the probe policy per tier are how the lab chooses to measure; the
area's `01_measure.py` keeps the prompts and the formulas, which the audit
reads. `profile` is the data profile per gold class that
`00_prepare.py --audit` prints before any model call — items, mean words,
the markers and confounds the area lists — doctrine too, and static
evidence only: an aid for the judgement the Data profile field owes and
for the audit, never proof that the data fit the question. Model calls are split between
`llm` (aliases, retries and call records), `llm_specs` (one configuration
type per backend, validated when loading `models.toml`) and `llm_backends`
(the wire calls). `endpoint_lease` manages the model-slot lease.

`runlog` calls `llm` to record resolved models. `endpoint_lease` checks
liveness through `runs.is_alive`, without calling the run writer.

### 3 · Checks

`labkit/checks/` answers individual questions about code, recorded metrics
or notes. `intent_check` compares promises with run records. `code_check`
collects the code checks and writes the audit bundle; `code_scan` supplies
the source facts those checks share, such as fields, keys and stages.
`gate_label_scan` extracts string comparisons, `import_check` identifies
code the stamp cannot follow, and `prompt_check` checks parser fixtures
and prompt drift.

`run_record_check` checks what a finished record must show: denominators,
frozen and tracked source, model identity, draws, row provenance and arms.
`readme_check` checks whether an area's README can lead a reader;
`notes_check` checks measurement-note declarations. `audit_binding` answers what an analysis
audit is held to: the answering run it reads (`audited_run`), what it was
shown of that run (`run_shown`, the digest the record carries) and which
records cover the area now (`covering_analysis`) — one answer for
`labkit-audit`, report-check and `protocol-fill --from-run`. Finalize calls the run
record and README checks as separate stations. `recheck` connects recorded
outputs, recomputed metrics and the cited result.

### 4 · Gates

`labkit/gates/` sequences checks at decision points. The entry points
`preflight_area`, `finalize_area` and `report_check` show the stations and
every condition under which a station is skipped. Station functions hold
the detail and report through `gate.Findings`. `report_check` lists its
release stages directly: declaration, freeze or committed registration,
finalize, full-run eligibility, analysis coverage and rendered results,
recomputation, decision reviews, summary. The lane's conditions stand at
those calls; a blocker does not stop later applicable stages. Its Checked
context supplies this gate's declaration and answering run. Nested
finalize and the analysis script read their own inputs.

`claude_hooks` calls the gates during an agent session. `audit` runs the
agent review through `llm`; `decision_review` runs the second auditor on
the `stands` decisions of one record (`labkit-audit --review`).
`install_hooks` installs the git hooks that run the gates; preflight
checks that they are installed.

### Tools

`labkit/tools/` provides commands that may use any layer. `protocol_fill`
fills protocol fields. `scaffold` stamps a lab repo and its areas from the
shipped templates; `protocol_cuts` selects the protocol template for a cost
tier. `repo_check`, behind `labkit-check`, compares the installation with
the repo's pin and checks whether that pin is current. `params` displays a
run's values and provenance; `calltree` shows what a command actually called.

### Probes

`labkit/probes/` contains the workflow and reading probes. `usability`
stages a cold-agent probe, `usability_score` scores it, and
`usability_command` implements the command. `agent_transcript` reads what
an agent did in its session. `cold_reader` holds the shared probe logic;
`protocol_reading` measures how a person reads a protocol, and
`code_navigation` measures how a newcomer finds their way in code.

## The chain

labkit's claim — *it detects violations of explicitly encoded scientific
intent across implementation, execution and reporting* — runs along six
links, several checked more than once (one row per check). Each check
names its tier: **guaranteed** (exact), **static
evidence** (warns), **agent audit** (semantic).

| Link | Checked | Where | Command | Tier | When |
|---|---|---|---|---|---|
| intent → promise | head parses and is typed; required fields by exact label; promise tables parse; prose and block name the same ids | `protocol_block.head`, `protocol_check.check_fields`, `promises.parse_block`, `promises.prose_mismatch` | `protocol-check` (fields, tables); `intent-check` (prose ids = table ids, again after the run) | guaranteed | writing the protocol |
| promise → code (keys, scopes) | every declared key appears exactly in the code; every declared scope resolves | `code_check.promise_block_findings` | `code-check`, `preflight` | guaranteed | before the run |
| promise → code (admissibility) | every [A] key the code writes is tested somewhere (`if`, `and`/`or`/`not`, `all()`/`any()`, a loop over a key tuple) — else the C verdict is reported whether the condition held or not | `code_check.admissibility_reads` | `code-check`, `preflight` | static evidence | before the run |
| promise → code (ids, parsers, prompt) | each intent id appears as a key; every `parse_*` is named in a test; every line of a `PROMPT` constant stands in the protocol's prompt block | `code_check.code_findings` (`prompt_check` for parsers and prompt) | `code-check`, `preflight` | guaranteed | before the run |
| promise → code (stamp coverage) | code the audit stamp cannot follow — a `sys.path` edit, a dynamic loader, an import outside `lib/` and `src/` — is named by line | `import_check.stamp_coverage_findings` | `code-check`, `preflight` | static evidence | before the run |
| promise → code (gate labels) | the string comparisons in the evaluation code are extracted into the bundle; whether they match the prompt is the code-check agent's judgement — the extraction never judges | `gate_label_scan.gate_labels` | `code-check --bundle`, then the code-check agent | agent audit | before the run |
| promise → code (meaning) | code does what the promise says | `audit` (experiment-preflight instructions + the area's files + the standard, one `llm` call); or the bundle (`code-check --bundle`) for the code-check agent | `labkit-audit --mode preflight` | agent audit | before the run |
| run → report (meaning) | the evaluation means the frozen criterion | `audit` in MODE analysis | `labkit-audit --mode analysis` | agent audit | after the run |
| run → report (the decisions) | an accepted finding whose effect is `stands` claims the verdicts hold within the limit; a second, cold auditor gets the finding, the reason, the protocol (registration and reported claim), the files the findings name as the auditor read them and what the auditor was shown of the run, and says per decision `upheld`, `rejected` or `insufficient`; only `upheld` releases, and only when every draw on the decision as decided and claimed now says so (a contested state is settled by deciding again, never by another draw); a changed decision or a rewritten Conclusion makes the review stale (the Recorded results and Limit lines are generated and bound through the record and the run); report-check blocks on an accepted BLOCKER's `stands` no review upholds and warns on an accepted WARNING's | `decision_review.gather_review`, `decision_review.parse_review`, `reviews.upholding`, `report_check.review_findings` | `labkit-audit --review`, `report-check` | agent audit (the release condition: guaranteed) | after the analysis audit is decided |
| promise → reader | a person who did not build the area can tell what it decides | `audit` in MODE clarity (code-clarity area rules + README, protocol, measure script) | `labkit-audit --mode clarity` | agent audit (static evidence: never a gate) | before freezing |
| code → run | unfrozen full run, unbound run, dangling scope, control leakage: refused before the run dir exists | `runlog.Run` | (every run) | guaranteed | starting the run |
| code → run | a full run's head names the decided preflight record (`preflight_audit = "<minute>-preflight.toml"`), and that record saw the code and the promise block as they are now; an `n/a` or any other text at minutes/hours is refused (nobody waives their own audit) | `runlog.Run`, `findings.audit_record_gap` | (every full run), `preflight` | guaranteed | starting the run |
| promise → run (tier) | the cost tier is not lower than in the protocol's first commit — a lower tier owes less | `protocol_history.cost_lowered` | `protocol-check`, `preflight` | static evidence | before the run |
| code → run | a long pilot's `LABKIT_UNFROZEN=1` rests on a failed audit attempt at the code and promises as they are now (`audits/*-failed.toml`, written by `labkit-audit` when the backend does not answer or answers unproven — `cause`; after an `unproven` attempt `labkit-audit` refuses the same state with the same model, `findings.stopped_attempt`), else refused; `run_kind`, `unfrozen_ack` and `audit_failed` recorded | `runlog.Run`, `findings.audit_unavailable` | (every acknowledged full run) | guaranteed | starting the run |
| code → run | block digest, per-promise `declared_scope_sha`, constants, git state, data hashes recorded | `runlog.Run`, `promises.snapshot` | (every run) | guaranteed | starting the run |
| run → report (record) | run completed; declared keys reported; run recorded this block; a block constant not contradicted by the run config | `runs.completion_state`, `intent_check.check_block_against_run` | `intent-check`, `finalize` | guaranteed | after the run |
| run → report (scopes) | declared scopes unchanged since the run | `promises.scope_drift` | `finalize`, `recheck` | guaranteed | before reporting |
| run → report (the registration) | at `seconds`: the registration the lane owes (`standard_contract.registration_fields`) stood in the protocol as committed at the first measurement — the oldest full run bound to the protocol and the commit its record names; the protocol not committed there, or a field not written there, blocks (outside a repository: a warning) | `answering_run.first_measurement`, `runs.recorded_commit`, `protocol_history.registration_in_commit`, `report_check.registration_gaps` | `report-check` | guaranteed | before the number leaves the area |
| run → report (the end) | at every cost tier: frozen (minutes/hours only — at seconds no freeze and no preflight audit are owed), finalize clean with its blockers named, the answering run a full run (`run_kind="measurement"`, not acknowledged unfrozen — a probe's or an acknowledged run's number is refused), an analysis audit record of the code, the promise block, the registration it judged (`registration`: the kind and the fields the kind owes, `protocol_check.registration_stamp`), the answering run and what the audit was shown of it (`shown_sha`: its rows' excerpts and metrics.json, `audit_binding.run_shown`) as they are now, every finding decided, `02_analyze.py --check` passes (the note carries the numbers and the run_id; every skeleton stamps the script, the compute skeleton's since 0.100.0) | `report_check`, `runs.unreportable`, `findings.audit_coverage`, `recheck.holds` | `report-check` | guaranteed | before the number leaves the area |
| run → report (the declaration) | a protocol whose TOML head declares a result (`[result] run = "<run_id>"`, written by `protocol-fill --from-run`, never typed — the one declaration that a result is reported) goes through report-check at the stop and the commit, with every other protocol of an area a changed, deleted or staged path touches — a path in the area, a file its promises declare in scope, or a shared helper under `lib/`/`src/` its code imports (a script changed or removed under a reported number reopens it; at the commit the protocols are the index's); a protocol declaring none owes nothing (an exploration ends with no reported result); a `[result]` that does not read (a typed id, a stray key) is a blocker where it stands; an Recorded results written under no declaration is a warning | `report_check.if_reported`, `report_check.affected_protocols`, `scope_sha.areas_touched`, `protocol_block.declared_run`, `finalize.declared_run_gaps`, `protocol_check.recorded_results_without_run` | `claude-hook stop`, `.githooks/pre-commit` (`report-check --if-reported --staged`: the answer as the index holds it, the area's tree equal to the index), `protocol-check` | guaranteed (the warning: static evidence) | ending the turn, committing |
| run → report (a report outside the protocol) | a changed or staged Markdown file citing a run (not a protocol, not under `runs/` or `data/`): every report result block names its protocol, shows the run that protocol declares now and equals what it renders (Recorded results and Limit lines; `protocol-fill --into` writes it and replaces the protocol's block after a new run is adopted) — exact for the block, nothing for the prose beside it; every token that reads as a run id names a run of the repo; a cited run that a protocol declares as its result is shown in that protocol's block, else the block is owed (a cited run no protocol declares: a warning); the protocol declaring a cited run goes through report-check as well; an untouched file's old citations reopen nothing | `report_check.if_reported`, `report_check.hold_report`, `report_blocks.block_gaps`, `report_blocks.cited_gaps`, `report_blocks.blocks_owed` | `claude-hook stop`, `.githooks/pre-commit` (the report as the index holds it) | guaranteed | ending the turn, committing |
| run → report (unsourced numbers) | numbers in a changed citing report outside every generated block are named with their line: no source is assigned to them — equal values elsewhere do not show where a number came from | `report_blocks.unsourced_numbers` | `claude-hook stop` (shown only beside a blocker), `.githooks/pre-commit`, `report-check --if-reported` | static evidence | ending the turn, committing |
| run → report (the adoption) | the one path that writes the declaration: the lines from the run's metrics.json are written, report-check runs on the written protocol, a blocker puts the file back — a result adopted this way has passed every check | `protocol_fill.adopt`, `report_check.report_check` | `protocol-fill --from-run` | guaranteed | writing the number back |
| run → report (undecided findings) | every finding still `open` in `audits/`, any mode: a BLOCKER blocks, a WARNING warns, each with its file | `finalize.check_open_audit_findings`, `findings.area_records` | `finalize` | guaranteed | after the run |
| run → report (a deleted run) | every analysis record of the area names a run it still holds: a record of a run whose directory is gone is a blocker where the record stands — the record is the evidence that the run existed | `findings.records_of_gone_runs`, `finalize.check_open_audit_findings` | `finalize` | guaranteed | after the run |
| run → report (the gates that run unasked: the stop sends back once, the commit holds) | an area the session touched, or a staged file lies in, holds an audit BLOCKER nobody decided: the stop sends the agent back, the commit is refused | `claude_hooks.undecided_blockers` | `claude-hook stop`, `.githooks/pre-commit` (`claude-hook undecided`) | guaranteed | ending the turn, committing |
| run → report (denominator) | denominator `c<i>_n` matches a recorded input count | `run_record_check.criterion_n_input_mismatches` | `finalize` | static evidence | after the run |
| report → number | output pinned to the run, recomputation agrees, note cites every number and the run id, block unchanged | `recheck.holds` | (an area's `--check`) | guaranteed | keeping a number |

## One home per question

| Question | Home |
|---|---|
| Is this an intent id / key? | `promises.ID_IN_PROTOCOL`, `promises.ID_KEY` |
| What does the promise block say? | `promises.parse_block`, `promises.load`, `promises.constants` |
| Which code does a promise rest on, and did it change? | `promises.declared_scope_sha`, `promises.scope_drift` |
| What does the protocol's head say (id, type, cost, frozen, audit)? | `protocol_block.head` |
| Which prose fields does a protocol owe, and which are filled? | `protocol_check.FIELDS`, `protocol_check.check_fields` |
| What does a cost tier owe — the freeze or the registration, which audits, which cut, the foreground, the provenance check? What does a reported number owe at its release? Which skeleton does an area get, and what is its check? | `standard_contract.lane` (the release reads its `freeze` and `audits`; `report_check`), `standard_contract.skeleton` and `standard_contract.registration_fields` (both by the head's `kind`: what the kept number asserts — a computation has no bar, a fit or an apply registers one; `standard_contract.has_bar`), `standard_contract.CHECK_SCRIPT` — every consumer reads the field it needs; a `cost == "seconds"` or a `kind == "compute"` outside the contract is a copy |
| Which protocols does an area hold? Which does the repo? | `repo.area_protocols`; `repo.repo_protocols` (outside `repo.SKIP_DIRS`); `repo.PROTOCOL_GLOB`, `repo.PROTOCOL_NAME` are the name |
| Which areas do changed or staged paths touch? | `scope_sha.areas_touched` (the nearest area above each path — `repo.areas_of` — and every area whose promises declare a changed path or whose code imports a changed shared helper; the stop's reported numbers and the commit's undecided findings read the same answer) |
| Where is the repo? Where is the lab? | `repo.git_root` (git), `repo.layout_root` (git, else stamped tree); `repo.lab_root` (the nearest `models.toml`) |
| Run git | `repo.git` (output, loud on failure), `repo.git_run` (exit code is the answer) |
| Which directories does an area's `runs/` hold, and what does each say? | `runs.run_dirs` (one walk, metadata read once; an unreadable run is data — the caller refuses, reports or skips) |
| Is this run finished? Which runs are? | `runs.completion_state`, `runs.completed_runs` |
| Write a file whole or not at all | `files.write_atomic`, `files.write_atomic_bytes` (every file a run leaves — records, failure, patch, raw artefacts, source snapshots — the lease, a filled protocol; the run index is appended under its lock) |
| The digest of a file, or of a set of named contents | `scope_sha.file_digest`, `scope_sha.tree_digest` (`DIGEST_CHARS` is the one recorded width of a stamp) |
| How is a JSONL text split into its records? | `jsonl.record_lines` (at "\n" only — `str.splitlines` also breaks at U+2028, U+2029, U+0085 inside a record) |
| What does a run's metadata say? | `runs.read_run_config` |
| Does an output file account for its input, item by item? | `batch.Store.ledger` (missing, duplicate, stray, stale per expected field); `require_complete()` inside the run keeps it from completing |
| Which runs wrote a JSONL file's rows? | `batch.row_runs` (per-row `_prov.run`); runlog names the runs a resumed file continues, finalize holds every row to the run |
| Is the recording process alive? | `runs.is_alive` |
| Which protocol does a new run bind to? | `start_check.protocol_binding` |
| What refuses a run before its directory exists, in which order? | `runlog.Run.__init__` (the registration, the detach gate where required and not already detached, the index header, data leakage, then for a full run `start_check.freeze_gate`: undecided blockers, the freeze or the registration, the acknowledgement over a failed audit); `start_check.prepare` refuses what cannot be read before any check |
| Which run answers for a protocol? | `answering_run.bound_answering_run` (the choice; `intent_check.choose_explicit` takes a named run; `recheck.chosen_run` is the same choice behind `--check` and `--from-run`) |
| Is this run a repeat draw, of which, and is it comparable? | `RunConfig.repeat_of`, `answering_run.repeats_of`, `answering_run.repeat_mismatch` — a repeat never answers (`bound_runs` leaves it out, `completed_runs(with_repeats=…)` makes every caller decide) |
| Which run recorded the model that answered these rows? | `answering_run.model_provenance_run` (walks `derived_from`; a derived run records none) |
| Is a run's `derived_from` chain whole? | `answering_run.lineage` (every config readable, every parent present, no loop — the whole chain; model provenance, params and row provenance read it) |
| Which protocol does a command hold an area to? | `repo.choose_protocol` (the named one, else the only one; never a guess) |
| What does one check hold — which protocol text, which file state, which answering run? | `report_check.checked` (`Checked`: built once, read by every station; the state is named — the working tree at the stop, the index at the commit, the written proposal at the adoption; the run is `answering_run.bound_answering_run`'s choice through `audit_binding.audited_run`) |
| How does a registered constant stand against the record? | `promises.constant_records` (equal / different / missing, type-strict); runlog refuses before mkdir, intent-check/finalize block, `labkit-params` shows all three |
| Does a frozen protocol owe a promise block? | `promises.promise_tables_owed` — protocol-check (MUST), preflight and finalize (blocker), runlog (refusal before mkdir) |
| Which analysis records cover the area now — code, promises, the answering run and what the audit was shown of it? | `audit_binding.covering_analysis` (`analysis_now` the state, `run_shown` the snapshot; report-check's analysis stage and its Limit lines, `protocol-fill --from-run`) |
| What does the result section say when it says what its sources say — and does it? | `result_render.rendering` (the Recorded results line from the declared run's metrics.json with its note, one Limit line per decided limit of the covering records), `result_render.render_gaps` (exact equality, each difference named; report-check's analysis stage, `protocol-fill --from-run` and `--render` write it) |
| Does a report outside the protocol show a reported number as its sources render it? | `report_blocks.blocks`, `report_blocks.block_body`, `report_blocks.block_gaps` (a report result block shows the run its protocol declares now and equals that protocol's Recorded results and full Limit lines; `protocol-fill --into` writes it), `report_blocks.cited_gaps` (every token that reads as a run id names a run of the repo), `report_blocks.unsourced_numbers` (numbers outside every block — a hint); `report_check.if_reported` holds changed citing reports, the protocols their blocks name and the protocols declaring the runs they cite |
| Does a review uphold a decision as it stands now, under the claim the protocol makes now? | `reviews.upholding` (a review of that record, its code and its run as shown, of the claim's digest `reviews.claim_digest` over `protocol_check.reported_claim`, holding the decision's digest `findings.decision_digest`, every such draw saying `upheld`), `reviews.contested` (another draw settles nothing), `reviews.state` for the gate's sentence |
| What carries a gate finding's sentence — a mechanical check or an indication? | `gate.GateFinding.evidence_kind` (`GUARANTEED` / `STATIC_EVIDENCE`, given at every site, never defaulted; static evidence never blocks, the dotted line names it, the summary counts it; `labkit-params` shows the same constants in its evidence column; the agent audit is the records' kind, `findings.Finding`) |
| Which audit findings are still undecided, and what does each gate make of one? | `findings.open_findings` (every mode, or one; the table of the gates' rules stands in its docstring: preflight warns unfrozen and blocks frozen, runlog reads the preflight records by grade, finalize every record by grade, the hooks hold BLOCKERs only — the differences are intended) |
| Which code did an audit see, and is it still that code? | `scope_sha.area_snapshot` (the bytes read once and the sha over them; `area_stamp` its sha); the record carries its `scope_sha`, and `findings.audit_coverage` holds it to the stamp now (area stamp, not per promise) |
| Which package does a requirements line name, and how is labkit pinned? | `repo.requirement_name`, `repo.requirement_lines`, the four `*_REQUIREMENT` grammars (stamp pin line, `labkit-check`, lock parser, probe) |
| What is a run id, when did the run start? | `runs.RUN_ID`, `runs.RUN_ID_TIME`, `runs.run_started`; `runs.COMPLETED` is the one state word every consumer compares to |
| How is a path shown in a report line, a bundle or a refusal? | `repo.shown(path, base)` — relative to the base when below it, else absolute, both resolved; a record's path is `runs.recorded_path`, a stamp's hashed key `scope_sha._key` |
| How does a record state a time? | `runs.now_stamp()` in `runs.RECORD_TIME` (`2026-10-13T14:00:57`, local) — a run's `started`/`finished`, a lock's or lease's holder, a staged probe, a session's stop |
| How does a gate tell what it found, and exit? | `gate.Findings` (`block`, `warn`, `take` for a `GateFinding` built where it was found — `gate.coded` for a code check's, grade, where, rule and fix as fields; `note` for a line counted as nothing, `report`; `Findings(tell=None)` collects the same findings without a console — report-check reads finalize's so) — preflight, finalize, report-check, code-check, notes-check |
| Which rules exist, what do they say, and does a reference name one? | `rules.load_ledger`, `rules.rule_heads`, `rules.check_heads`, `rules.check_ledger`, `rules.check_refs`, `rules.rule_text` (`labkit/docs/standard.md`, `labkit/docs/rules.tsv`) |

A second answer to any of these questions is drift: move the caller to the
home, never copy the logic. `tests/test_one_home.py` greps `labkit/*.py` for
the shapes a copy takes (a hand-spelled sha256, a `git` run outside `repo`,
a `PROTOCOL-*.md` scan, the id letters, a fence regex, …) and fails on a
match outside the home — three audits removed the same copies by hand and
they came back each time (2026-10-15).

## Where what lives

labkit is one of four places that hold the lab's rules, tools and copies.
The split grew by history, not by a principle; this table states it as it
is, so a reader can find a file before it moves. The rule for every move:
**what a lab outside this house needs to work with labkit lives in labkit;
what concerns only this house stays in the author's dotfiles.**

| Place | Holds | Master or copy |
|---|---|---|
| labkit (this repo) | the code and its gates; the lab standard (`labkit/docs/standard.md`, English) and its ledger (`labkit/docs/rules.tsv`: id → name → status, every `LAB` number); the protocol template and its field guide (`labkit/templates/experiment-protocol.md.template`, `labkit/docs/protocol-field-guide.md`); `labkit-init` and the templates it stamps (`labkit/templates/`: script skeletons, area tests, `AGENTS.md`, `models.toml`, editor settings); the audit agents' instructions (`labkit/agents/*.agent.md`) | master |
| labkit (this repo) | `docs/notes/`: the history behind a rule in the code — trigger, rejected approaches, the long why — one dated note per topic, linked from the code that states the rule (`AGENTS.md`, "The current rule first") | master |
| labkit (this repo) | `docs/coding-style.md` | copy, stamped with the master's hash; edit the master, then `lib sync pull` (the house scaffolder's command, not a labkit one) |
| author's dotfiles (`~/.claude/resources/`) | the house standard (`arbeitsstandard.md.template`, German, house chapters), the dated evidence behind every rule (`arbeitsstandard.evidence.md`), the house ledger (`rule-registry.tsv`: `LOCAL` and `CODE` ids, `LAB` rows marked `moved:labkit`), the coding style, the house scaffolder (`tools/local-init.py`: house files, the thread in `~/work`, sync; its lab part hands over to `labkit-init`), the note seeds, the thesis starter | master |
| a lab repo | labkit as a pinned package, which brings the standard; `docs/coding-style.md`, `CLAUDE.md`, the scripts stamped from the templates (a repo pinned below 0.77 still carries its `docs/arbeitsstandard.md` copy) | copies, stamped by the scaffolder |
| author's global `~/.claude/CLAUDE.md` | one-line reflexes that point at rule ids | master (house only) |

**What is still in the dotfiles.** The thesis starter, which carries house
material (lecture links, run snapshots with the author's paths); it stays
in the house layer. Gate
messages and docstrings cite rules by id and English name, and
`tests/test_rules.py` holds every such reference to the ledger.

## Run records

An experiment script enters `runlog.run(...)` with its protocol, config
and input paths. Preparation resolves the binding and records the promise
snapshot; the start checks refuse an inadmissible run before its directory
is created. The context manager confirms completion only on a clean exit.
An interrupted run leaves its start record without confirmed completion.

```text
experiments/NN-name/
  PROTOCOL-name.md
  scripts/                      measurement and recomputation
  output/                       registered output files
  audits/                       findings and their decisions
  runs/<run-id>/
    config.json                 start config, protocol binding, inputs, environment
    metrics.json                values reported through run.metrics(...)
    outputs.json                registered output paths and their digests
    completion.json             confirmed completion and end state
    script-source.py            snapshot of the script as it ran
  runs.tsv                      derived index of completed runs — git-ignored, `runlog reindex` rebuilds it
```

The record can also hold raw model output, a patch and untracked source
snapshots. Consumers read records through `runs`; `answering_run` selects
the completed run bound to the protocol. The run index and the protocol
run list do not choose the answer. Selection and run
relationships are specified in [protocol-run-binding](protocol-run-binding.md).

## The gates in order

The one place the order stands (audit 2026-10-23, C3); `docs/workflow.md`
walks the same steps with the person's commands between them. Every
mechanical gate shares one exit contract (`gate.EXIT_CONTRACT`: 0 clean,
warnings may stand; 1 a blocker; 2 no check) and states it in its
`--help`; `labkit-audit` alone exits 1 on a warning too, by intent
(`audit.AUDIT_EXIT_CONTRACT`: its findings are a person's to decide, not a
hook's to pass — the benchmark of 2026-10-06 found a fault only as a
WARNING). What an undecided audit finding is to each gate:
`findings.open_findings`.

| Gate | When | Holds | Area tests | Where it runs unasked |
|---|---|---|---|---|
| `protocol-check` | after every protocol edit | fields, placeholders, the head, the prose budget | — | `claude-hook post-change`, the pre-commit on staged protocols |
| `code-check` | after every code change | the promises against the code, the prompt constants, static evidence | — | — (`labkit-audit --mode preflight` reads its bundle) |
| `preflight` | before `frozen = true` (minutes/hours) | protocol-check, the lane's duties, the audit record and its coverage, the promises, the tests | no test file: a warning, a blocker once frozen; a failing test: a blocker | `claude-hook pre-run` before a recognised measurement command |
| `labkit-audit --mode preflight` | before the freeze (minutes/hours) | the agent audit of the registration and the code; every finding decided by a person | — | — |
| `runlog` (the run's start) | at every full run | the registration, the binding, leakage, the freeze and the audit coverage the lane owes; undecided preflight findings by grade | — | the run itself |
| `finalize` | after the run, before the number is written back | the answering run, intent-check, declared scopes, open fields, provenance (seconds), the tests, criterion n, undecided findings of any mode by grade | no test file: a note; a failing test: a blocker | `report-check` runs it as one station |
| `labkit-audit --mode analysis` | after the run, at every cost tier | the agent audit of the answering run; every finding decided, an accepted BLOCKER with its effect | — | — |
| `labkit-audit --review` | when a BLOCKER was accepted with `stands` | a second auditor on the decision | — | — |
| `report-check` | before the number leaves the area, at every cost tier | the whole chain: declaration, registration, finalize, the analysis record's coverage, the rendered result, `02_analyze.py --check` | through finalize | `claude-hook stop` (`--if-reported`), the pre-commit (`--if-reported --staged`) |
| `claude-hook undecided` | at the stop and the commit | undecided audit BLOCKERs in the areas the session touched | — | `claude-hook stop`, the pre-commit |

`notes-check` holds the measurement notes (`claude-hook post-change`) and
stands beside the chain, not in it.

## Where verdicts are recorded

Audits, reviews, runs and sessions leave records; the mechanical gates
leave stdout and an exit code — by design, written down here (audit
2026-10-23). A gate's verdict follows from the records and the files as
they are now, and is recomputed at every call: a logged verdict would be a
second truth that drifts from the state it judged (the code moved on, the
record was decided later), and nothing could tell the two apart. "What did
every gate say about run X" is answered by running the gates on X's area
now, which costs seconds; what a person decided, and what a run or an
audit saw, cannot be recomputed and is what the records hold.

| Record | Writer | Carries |
|---|---|---|
| `audits/<minute>-<mode>.toml`, decisions in place | `findings.write`, `findings.write_decision` | the code stamp, the promise block, the registration, the run and what was shown of it, every finding and its decision |
| `audits/<minute>-<mode>-failed.toml` | `findings.write_failed` | the attempt an acknowledged run rests on |
| `audits/<minute>-review(-N).toml` | `reviews.write_review` | a second auditor's reading of a decision |
| `runs/<id>/*.json`, `runs.tsv` | `runlog`, `runs.write_failure` | the run: config, outputs, metrics, completion or failure |
| `.git/labkit-sessions.jsonl` | `claude_hooks.record_session` | which runs a session started (no verdict) |

An audit record names the run it read, not the protocol: the match
against the registration is computed from the protocol as it reads now
(`registration`), and in an area with several protocols the gate
chooses the protocol first (`repo.the_protocol`). Carrying a protocol
id in the record is noted in `TODO.md`, not planned.

## Run and hook enforcement

`standard_contract.lane` supplies the obligations for a protocol's cost
tier. At `seconds` there is no freeze or preflight audit; release of a
result still requires a full run, a clean finalize, a decided analysis
audit bound to the current code, promises and answering run, and the
recomputation check. At `minutes`/`hours`, the start of a full run also
requires a frozen protocol and matching preflight audit coverage.

The audit field is checked against an actual record under `audits/`.
Changing the bound code or promises invalidates that coverage. An
analysis record additionally names the answering run. Snapshot binding
and the declared-scope hash have separate purposes; see
[promise-block](promise-block.md) and the chain above.

`run_kind="measurement"` declares a measurement; `run_kind="probe"` declares
an instrument check. `run_kind="preparation"` records data preparation
without releasing a result. At seconds a separate probe is refused: the complete
measurement checks the instrument and can be repeated cheaply.
`runs.unreportable` refuses a probe or an acknowledged unfrozen run as the
source of a reported number. At minutes/hours, `LABKIT_UNFROZEN=1` permits
an acknowledged run only when a matching failed preflight attempt is
recorded with sufficient timeout. The run records that attempt and the
acknowledgement; the resulting number remains unreportable. An open audit
BLOCKER cannot be overridden this way.

Adoption through `protocol-fill --from-run` writes Recorded results and Runs
lines (the Summary's Conclusion stays the author's sentence), runs
`report-check` against the written protocol and restores the file on
failure. `[result] run` in the head declares a reported result; the hooks
recheck affected areas so later edits are subject to the same contract.
An exploration declares no result and releases none.

| Enforcement point | Role |
|---|---|
| `runlog.Run` | Checks registration, protocol binding, leakage, foreground execution and freeze/audit obligations before a run starts. |
| git pre-commit | Checks staged protocols, affected reported results and unresolved audit blockers. Report checks use the staged answer and require the area's working tree to agree with the index. |
| Claude `pre-run` | Runs preflight for recognized measurement commands; blocks a frozen area's command on blockers. |
| Claude `post-change` | Reports protocol and note checks after changes; tracks content per session to avoid repeating unchanged files. |
| Claude `stop` | Sends the session back for a failed release check or an unresolved audit blocker in an affected area, once per stop cycle. |

`labkit-hooks install` installs the pinned package's git and Claude hooks;
`preflight` checks their installation. The run writer and git hooks work
without Claude. Live hook configuration is generated by
`gates/install_hooks.py`; it is not a second hand-maintained configuration
in the README.

### Long-running commands

A harness that kills foreground commands can interrupt an experiment.
Set `LABKIT_FOREGROUND_TIMEOUT_S` in that harness's environment policy so
every command inherits it; `0` means no limit. Claude Code supplies a
600-second default through `CLAUDECODE` when no explicit value is set.
An export inside a single tool command does not configure later commands.

When the lane requires background execution and a foreground limit is
configured, `runlog` refuses a full run and asks for
`runlog start AREA -- COMMAND`. The command starts a separate session and
writes a log under the area's `output/`; `runlog AREA --wait` monitors its
recorded state. A caller that already detached the process can declare
`LABKIT_DETACHED=1`. The seconds lane allows foreground execution.

An audit's duration is separate from a measurement's cost tier. Use the
harness's background-task mechanism for a long `labkit-audit` call and
wait for that task, rather than polling process-name matches.
