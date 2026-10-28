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
| 1 · formats and places · `labkit/formats/` | `protocol_block`, `comment_blocks`, `prompts`, `promises`, `protocol_check`, `protocol_history`, `standard_contract`, `runs`, `answering_run`, `repo`, `scope_sha`, `rules`, `findings`, `followup`, `reviews`, `report_reviews`, `attempts`, `handovers`, `evidence`, `console`, `gate`, `shell`, `files`, `jsonl` | `protocol_check`, `protocol_history`, `standard_contract`, `rules`, `findings`, `followup`, `reviews`, `report_reviews`, `attempts`, `handovers`, `evidence` |
| 2 · a run and its effects · `labkit/run/` | `runlog`, `provenance`, `start_check`, `runlog_command`, `batch`, `llm`, `llm_specs`, `llm_backends`, `endpoint_lease`, `lanes`, `profile` | `lanes`, `profile` |
| 3 · checks · `labkit/checks/` | `intent_check`, `code_check`, `code_scan`, `gate_label_scan`, `import_check`, `prompt_check`, `run_record_check`, `readme_check`, `recheck`, `notes_check`, `audit_binding`, `result_render`, `report_blocks`, `report_review_inputs`, `protocol_report` | `readme_check`, `notes_check`, `audit_binding`, `result_render`, `report_blocks`, `report_review_inputs`, `protocol_report` |
| 4 · gates · `labkit/gates/` | `preflight`, `finalize`, `report_check`, `report_hold`, `claude_hooks`, `audit`, `decision_review`, `report_review`, `install_hooks`, `ways_out` | `preflight`, `finalize`, `report_check`, `report_hold`, `claude_hooks`, `audit`, `decision_review`, `report_review`, `install_hooks`, `ways_out` |
| tools · `labkit/tools/` | `protocol_fill`, `scaffold`, `protocol_cuts`, `repo_check`, `params`, `calltree` | `protocol_fill`, `scaffold`, `protocol_cuts`, `calltree` |
| tools · probes · `labkit/probes/` | `usability`, `usability_score`, `usability_command`, `sab_cases`, `agent_transcript`, `cold_reader`, `protocol_reading`, `code_navigation` | `usability`, `usability_score`, `usability_command`, `sab_cases`, `agent_transcript`, `cold_reader`, `protocol_reading`, `code_navigation` |

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

One crossing was added on purpose since, and stands on these terms:
`start_check` → `protocol_history` (2026-10-27,
`protocol_history.registration_in_commit`). The run's start refuses a
first measurement at `low` whose registration HEAD does not hold — the
same rule report-check holds that commit to; without it the run started
and could never be adopted. It is the doctrine `start_check` already
crosses for (`protocol_check.low_registration_missing`), not a new kind.
It goes when the doctrine checks at a run's start leave `start_check` as a
whole (a doctrine-side start gate the run writer calls); removing this one
import alone would buy a second mechanism for nothing. It grants no
permission for further crossings.

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

`handovers` holds the immutable handover records, the handover block a
report carries for each (one per protocol, written from the record) and
the check whether a record still acknowledges its area
(`handovers.acknowledgement`). Only stop/commit may acknowledge the bound
evidence loss, with no result declared and no readable BLOCKER left
open. Normal audit and result release keep the integrity refusal.
`attempts` retains expected lost paths from those records across commits. Contract and limits:
[handover recovery](notes/2026-10-27-handover-recovery.md).

`evidence` holds what committed evidence may become: a record changes in
its findings' decision lines alone, another audit file never, a closed
run never; a version back as labkit first committed it is no change. Its
witnesses are git's — the tree or the index against HEAD, at the stop
also the session's commits against their parents and HEAD's reflog — so
every change it names is undone from git, and a handover does not
acknowledge it. Contract and limits:
[evidence changes](notes/2026-10-28-evidence-changes.md).

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
   snapshot and freezes the config — a reseeded repeat's seed excepted,
   which runlog derives under its lock (`start_check.require_valid_reseed` holds
   the conditions first).
2. The start checks cover registration, detachment, the index header,
   data leakage and the freeze gate where required. These refusals occur
   before the run directory is created.
3. Creation records provenance and snapshots. A repeat's draw is reserved
   under the index lock before its record is written.

`provenance` gathers git state, environment, models, data and snapshots.
`provenance.BinaryInput(path)` explicitly marks a binary dependency in a
run's `data` mapping: its bytes are hashed, `rows` is null, and dataset
decoding and row-id leakage checks do not apply to that input. Ordinary
dataset paths retain those checks. The local apply template marks its
declared predictor artifacts this way.
`runlog` writes the run and index; `runlog_command` implements the console
command. `batch` manages resumable output. `lanes` is the run mechanics of
the stamped two-lane judge — jobs per item and lane, batches, resume, the
probe, the balance, the area's command line — doctrine, since the two lanes
and the probe policy per tier are how the lab chooses to measure; the
area's `01_measure.py` keeps the prompts and the formulas, which the audit
reads. `profile` is the data profile per gold class that the prompt
skeleton's `00_prepare.py --audit` prints before any model call — items, mean words,
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
the `stands` decisions of one record (`labkit-audit --review`);
`report_review` runs a cold reader on a report that discusses a run
(`labkit-audit --report-review`) and records its claims
(`formats/report_reviews`), which report-check holds the report to.
`install_hooks` installs the git hooks that run the gates; preflight
checks that they are installed.

### Tools

`labkit/tools/` provides commands that may use any layer. `protocol_fill`
fills protocol fields. `scaffold` stamps a lab repo and its areas from the
shipped templates; `protocol_cuts` selects the protocol template for a cost
tier. The estimator script fits models only for `kind = "fit"`; a local
`apply` uses the unchanged predictor, its null lane on labels permuted with
the seed (or a registered fixed null predictor).
Declared predictor artifacts are run inputs, hashed in the config and
output fingerprint so resume and repeats cannot silently change them.
`repo_check`, behind `labkit-check`, compares the installation with
the repo's pin and checks whether that pin is current. `params` displays a
run's values and provenance; `calltree` shows what a command actually called.

### Probes

`labkit/probes/` contains the workflow and reading probes. `usability`
stages a cold-agent probe, `usability_score` scores it, and
`usability_command` implements the command. `sab_cases` holds the
ScienceAgentBench-shaped cases the probe can stage, one per kind, each with
a known trap and an evaluation the agent never sees. `agent_transcript` reads what
an agent did in its session. `cold_reader` holds the shared probe logic;
`protocol_reading` measures how a person reads a protocol, and
`code_navigation` measures how a newcomer finds their way in code.

## The chain

labkit's claim — *it detects violations of explicitly encoded scientific
intent across implementation, execution and reporting* — runs along eight
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
| promise → code (gate labels) | the string comparisons in the evaluation code are extracted into the bundle; whether they match the prompt is the judgement of an agent the lab runs on it (labkit ships none; the preflight audit reads the code whole) — the extraction never judges | `gate_label_scan.gate_labels` | `code-check --bundle`, then the lab's own agent | agent audit, outside labkit | before the run |
| promise → code (meaning) | code does what the promise says | `audit` (experiment-preflight instructions + the area's files + the standard, one `llm` call); or the bundle (`code-check --bundle`) for an agent the lab runs | `labkit-audit --mode preflight` | agent audit | before the run |
| run → report (meaning) | the evaluation means the frozen criterion; every earlier decided BLOCKER (`fixed`, `accepted`, `dismissed`, `deferred` in a record not of the state audited; only the head of each carried chain, `followup.chain`) is shown with its decision; a verdict other than `resolved` carries the finding into the new record (open, origin text, check kept, `carries`, counted in `blockers` and `carried_blockers`); and the auditor writes one `FIX · <record>#<n> · resolved \| unresolved \| not_assessable · <why>` entry per finding (the why may continue below the line up to a blank line or the next entry, kept whole; an entry naming another shown finding is refused), stored as `[[fix_verdict]]` bound to the decision shown (`findings.decision_digest`); a FIX line that does not read, names a finding not shown, repeats one or carries another word, or a shown decision changed during the call, records nothing; a finding without a line stays unchecked; a finding may require a diagnostic (`· check: <metrics key>`, optionally ` (<note>)` or ` — <note>` to the line's end, the note kept whole as `check_note`; the auditor's, kept by every decision and bound in the digest), whose whole value from the shown metrics.json the prompt carries and whose presence each verdict records (`check_present`, from that snapshot; absent when none is required) (pilot, no gate yet: eighth round, t3) | `audit` in MODE analysis, `audit.parse_fixes`, `followup.earlier_blockers`, `findings.FixVerdict` | `labkit-audit --mode analysis` | agent audit (the verdict); guaranteed (its form and binding) | after the run |
| run → report (the decisions) | an accepted finding whose effect is `stands` claims the verdicts hold within the limit; a second, cold auditor gets the finding, the reason, the protocol (registration and reported claim), the files the findings name as the auditor read them and what the auditor was shown of the run, and says per decision `upheld`, `rejected` or `insufficient`; only `upheld` releases, and only when every draw on the decision as decided and claimed now says so (a contested state is settled by deciding again, never by another draw); a changed decision or a rewritten Conclusion makes the review stale (the Recorded results and Limit lines are generated and bound through the record and the run); report-check blocks on an accepted BLOCKER's `stands` no review upholds and warns on an accepted WARNING's; a finding a review once did not uphold (`reviews.once_not_upheld`) and that is now `dismissed`, `fixed` or `deferred` (`findings.CLOSING`) is held the same way until a review upholds the new decision — the reviewer is asked whether the reason shows it inapplicable, gone or somebody else's (sixth round, t5: a dismissal after `insufficient` released the state) | `decision_review.gather_review`, `decision_review.parse_review`, `reviews.upholding`, `reviews.once_not_upheld`, `report_check.review_findings` | `labkit-audit --review`, `report-check` | agent audit (the release condition: guaranteed) | after the analysis audit is decided |
| run → report (the follow-up) | an earlier decided BLOCKER (`fixed`, `accepted`, `dismissed`, `deferred` in a record not of the state reported) is released only by a covering analysis record's valid `resolved` — the head of its origin, its decision as it stands, a required check shown — while no covering record holds another verdict on that origin, or carried into a covering record, where it is decided; a carried finding `dismissed` or `deferred` owes an upholding decision review; a BLOCKER `fixed` in the state reported is held; each sentence names the missing step (pilots: [fixed follow-up](usability/2026-10-26-fixed-followup-pilot.md), [second](usability/2026-10-26-fixed-followup-pilot-2.md)) | `followup.release_holds`, `followup.chain`, `report_check.followup_findings`, `decision_review.reviewable` | `report-check`; `claude-hook stop`, `.githooks/pre-commit`, `protocol-fill --from-run` | guaranteed (the binding and the release); agent audit (the verdict) | before the number leaves the area |
| run → report (a discussed run) | a report discussing a run (a discussion block) states none of its numbers as results and nothing the audit decisions contradict; a cold reader gets the report with line numbers, the protocol, each discussed run's `metrics.json` and every audit record with its decisions and failed attempts, and names the lines as `result` or `contradiction`; recorded in `audits/report-reviews/` with the fingerprint of exactly the inputs it read (its own folder and the attempt journal not among them); report-check holds the report, per protocol its discussions name, until a review of its state — the report and protocol as the gate's state holds them, at the commit only records the index holds and the area's tree equal to the index — names no claim; a committed report discussing a run of an area a change touches is held with the change (`report_hold.discussing_reports`); a claim holds the state — an `--again` draw's as well — and a later clean draw (or `--again`) releases nothing; the command prints the draw and the state apart and exits with the state (0 released, 1 held), a changed input (the report, the protocol, a run's metrics, an audit decision) owes a new review; the post-change hook names its command (pilot: [report review](usability/2026-10-25-report-review-pilot.md)); a report that cites no run is out of its reach | `report_review_inputs.review_pieces`, `report_review.parse_claims`, `report_reviews.standing`, `report_hold.report_review_owed` | `labkit-audit --report-review`; `claude-hook stop`, `.githooks/pre-commit` | agent audit (the claims); guaranteed (the record, its binding and its claim count) | when a report discusses a run; ending the turn, committing |
| promise → reader | a person who did not build the area can tell what it decides | `audit` in MODE clarity (code-clarity area rules + README, protocol, measure script) | `labkit-audit --mode clarity` | agent audit (static evidence: never a gate) | before freezing |
| code → run | unfrozen full run, unbound run, dangling scope, control leakage: refused before the run dir exists | `runlog.Run` | (every run) | guaranteed | starting the run |
| code → run | a full run's head names the decided preflight record (`preflight_audit = "<minute>-preflight.toml"`), and that record saw the code and the promise block as they are now; an `n/a` or any other text at high repeat cost is refused (nobody waives their own audit) | `runlog.Run`, `findings.audit_record_gap` | (every full run), `preflight` | guaranteed | starting the run |
| promise → run (tier) | the repeat cost is not lower than in the protocol's first commit — a lower tier owes less | `protocol_history.repeat_cost_lowered` | `protocol-check`, `preflight` | static evidence | before the run |
| code → run | a long pilot's `LABKIT_UNFROZEN=1` rests on a failed audit attempt at the code and promises as they are now (`audits/*-failed.toml`, written by `labkit-audit` when the backend does not answer or answers unproven — `cause`; after an `unproven` attempt `labkit-audit` refuses the same state with the same model, `findings.stopped_attempt`), else refused; `run_kind`, `unfrozen_ack` and `audit_failed` recorded | `runlog.Run`, `findings.audit_unavailable` | (every acknowledged full run) | guaranteed | starting the run |
| code → run | block digest, per-promise `declared_scope_sha`, constants, git state, data hashes recorded | `runlog.Run`, `promises.snapshot` | (every run) | guaranteed | starting the run |
| run → report (record) | run completed; declared keys reported; run recorded this block; a block constant not contradicted by the run config | `runs.completion_state`, `intent_check.check_block_against_run` | `intent-check`, `finalize` | guaranteed | after the run |
| run → report (the null lane) | an output the run kept with a registered and a null lane: the null answers otherwise on some item, gold included — read from the kept rows, not from the editable script | `run_record_check.null_lane_findings` | `finalize` | guaranteed | after the run |
| run → report (code) | for the answering run and each run it derives from: the measurement script (the path its command names) unchanged since the run (its recorded `script_sha`), and every module it imports — beside it, under `lib/` or `src/` (`scope_sha.measured_code`) — as the tree the run started from held it (its commit with the part of its `uncommitted.patch` for that module, read in a temporary index); a module in another repository a warning; analysis code and the pin not compared; a change made and undone in between, and code loaded another way, not seen | `run_record_check.code_since_run`, `repo.tree_patch`, `repo.blobs_then`, `repo.blobs_now` | `finalize`, `report-check` | guaranteed | before reporting |
| run → report (scopes) | declared scopes unchanged since the run | `promises.scope_drift` | `finalize`, `recheck` | guaranteed | before reporting |
| run → report (the registration) | at `low`: the registration the lane owes (`standard_contract.registration_fields`) stood in the protocol as committed at the first measurement — the commit its record names (`git_full`); first is what git's history puts first, the run id (local time) orders only runs at one commit, and on diverged history or beside a run git cannot place each first one is held; the protocol not committed there, a field not written there, a kind changed since, or a commit the clone does not hold, blocks (outside a repository: a warning); a field's value changed after that commit is not compared | `answering_run.first_measurements`, `runs.recorded_commit`, `repo.earliest_commits`, `protocol_history.registration_in_commit`, `report_check.registration_gaps` | `report-check` | guaranteed | before the number leaves the area |
| run → report (the registration as first measured) | every lane: the answering run recorded the promise block its protocol's first measurements recorded (ids, keys, sentences through the block digest, scopes, constants — not the code the scopes name); a change is held, named per id and constant, with the way back (restore and measure again, or register anew); first measurements that recorded different blocks are held too — which one stood cannot be told — with the two ways out (a replacement declared against each, or the handover `ways_out.HANDOVER`) | `answering_run.first_registrations`, `promises.snapshot_changes`, `report_check.registration_changes` | `report-check` | guaranteed | before the number leaves the area |
| run → report (a declared replacement) | a protocol with `[replaces]`: one predecessor of the repo, no circle, `type = "exploratory"`, every difference of the registration against the predecessor's (as each first measurement saw it: commit plus its `uncommitted.patch`, held to the recorded block; against each when they differ) declared as `[[replaces.change]]` and none declared that is not one, the predecessor's open BLOCKERs decided; the generated result opens with the predecessor's verdict (`no verdict` where its registration does not stand); a report that switched its citations to an undeclared successor is static evidence | `protocol_block.replaces`, `protocol_history.registrations_as_first_measured`, `protocol_history.registration_differences`, `report_check.replacement_gaps`, `result_render.predecessor_verdict`, `report_hold.replacement_hints` | `report-check` | guaranteed (the hint: static evidence) | before the number leaves the area |
| run → report (the end) | at every repeat cost: frozen (high repeat cost only — at low repeat cost no freeze and no preflight audit are owed), finalize clean with its blockers named, the answering run a full run (`run_kind="measurement"`, not acknowledged unfrozen — a probe's or an acknowledged run's number is refused), an analysis audit record of the code, the promise block, the registration it judged (`registration`: the kind and the fields the kind owes, `protocol_check.registration_stamp`), the answering run and what the audit was shown of it (`shown_sha`: its rows' excerpts and metrics.json, `audit_binding.run_shown`) as they are now, every finding decided, `02_analyze.py --check` passes (the note carries the numbers and the run_id; every skeleton stamps the script, the compute skeleton's since 0.100.0) | `report_check`, `runs.unreportable`, `findings.audit_coverage`, `recheck.holds` | `report-check` | guaranteed | before the number leaves the area |
| run → report (the declaration) | a protocol whose TOML head declares a result (`[result] run = "<run_id>"`, written by `protocol-fill --from-run`, never typed — the one declaration that a result is reported) goes through report-check at the stop and the commit, with every other protocol of an area a changed, deleted or staged path touches — a path in the area, a file its promises declare in scope, or a shared helper under `lib/`/`src/` its code imports (a script changed or removed under a reported number reopens it; at the commit the protocols are the index's); a protocol declaring none owes nothing (an exploration ends with no reported result); a `[result]` that does not read (a typed id, a stray key) is a blocker where it stands; an Recorded results written under no declaration is a warning | `report_check.if_reported`, `report_check.affected_protocols`, `scope_sha.areas_touched`, `protocol_block.declared_run`, `finalize.declared_run_gaps`, `protocol_check.recorded_results_without_run` | `claude-hook stop`, `.githooks/pre-commit` (`report-check --if-reported --staged`: the answer as the index holds it, the area's tree equal to the index), `protocol-check` | guaranteed (the warning: static evidence) | ending the turn, committing |
| run → report (a report outside the protocol) | a changed or staged Markdown file citing a run (not a protocol, not under `runs/` or `data/`, both tested at its own path): a report that is a symbolic link, wherever it points, blocks alone, naming the copy that replaces it (`report_hold.link_gap`; its other checks follow on the copy); every report result block names its protocol, shows the run that protocol declares now and equals what it renders (Recorded results and Limit lines; `protocol-fill --into` writes it and replaces the protocol's block after a new run is adopted) — exact for the block, nothing for the prose beside it; every token that reads as a run id names a run of the repo; a cited run that a protocol declares as its result is shown in that protocol's block, else the block is owed; the answering run of a protocol that declares no result is not cited undiscussed — the promotion without the adoption (sixth round, t3 and t18) — and a run only looked at stands in a discussion block (`protocol-fill --discuss RUN --why … --into`: protocol, run and why as TOML in its head, its line written from them; a block without its why, with a line that differs from its head, repeated for one protocol and run, naming a run its protocol's area lacks, or discussing a declared run blocks; any other cited run no protocol declares: a warning); the protocol declaring a cited run goes through report-check as well; an untouched file's old citations reopen nothing | `report_check.if_reported`, `report_hold.hold_report`, `report_hold.undeclared_findings`, `report_hold.promotions`, `report_blocks.block_gaps`, `report_blocks.cited_gaps`, `report_blocks.blocks_owed`, `report_blocks.discussions`, `report_blocks.discussion_gaps`, `report_hold.discussion_sources` | `claude-hook stop`, `.githooks/pre-commit` (the report as the index holds it) | guaranteed | ending the turn, committing |
| run → report (unsourced numbers) | numbers in a changed citing report outside every generated block are named with their line: no source is assigned to them — equal values elsewhere do not show where a number came from | `report_blocks.unsourced_numbers` | `claude-hook stop` (shown only beside a blocker), `.githooks/pre-commit`, `report-check --if-reported` | static evidence | ending the turn, committing |
| run → report (the adoption) | the one path that writes the declaration: the lines from the run's metrics.json are written, report-check runs on the written protocol, a blocker puts the file back — a result adopted this way has passed every check | `protocol_fill.adopt`, `report_check.report_check` | `protocol-fill --from-run` | guaranteed | writing the number back |
| run → report (undecided findings) | every finding still `open` in `audits/`, any mode: a BLOCKER blocks, a WARNING warns, each with its file | `finalize.check_open_audit_findings`, `findings.area_records` | `finalize` | guaranteed | after the run |
| run → report (a deleted run) | every analysis record of the area names a run it still holds: a record of a run whose directory is gone is a blocker where the record stands — the record is the evidence that the run existed | `findings.records_of_gone_runs`, `finalize.check_open_audit_findings` | `finalize` | guaranteed | after the run |
| run → report (the gates that run unasked: the stop sends back once, the commit holds) | an area the session touched, or a staged file lies in, holds an audit BLOCKER nobody decided: the stop sends the agent back (the records as the tree holds them), the commit is refused (the records and their decisions as the index holds them); a lost or unreadable record or journal holds both too, except where a current handover binds that loss (`handovers.acknowledgement`) — an open BLOCKER never; committed evidence changed against git — a record beyond its decision lines, another audit file, a closed run's files — or a file of labkit's that git ignores holds both as well, in the state checked against HEAD, at the stop also by a session commit or left behind in HEAD's reflog, and no handover acknowledges it: each line names its `git checkout` | `claude_hooks.undecided_blockers`, `attempts.area_integrity`, `findings.open_blockers`, `claude_hooks.committed_in_session`, `evidence.changes`, `evidence.ignored`, `claude_hooks.session_evidence` | `claude-hook stop`, `.githooks/pre-commit` (`claude-hook undecided`) | guaranteed | ending the turn, committing |
| audit → evidence (the attempts) | every model call of `labkit-audit` is an attempt journaled in `audits/attempts.jsonl` — a preflight or analysis audit, a decision review (`review`), a report review (`report-review`, its record under `audits/report-reviews/`) — started before the call, the model's answer kept as `audits/answers/<attempt id>.txt` before anything reads it, ended with its record, its failed-attempt file or why none, and the kept answer (a kept answer releases nothing); a call not made (a state already judged, a refusal before it) is no attempt, and a record older than the journal is named by none; an attempt whose process holds no lock and has no end is marked interrupted by the next; a file an ended attempt names, a file under `audits/` HEAD holds, or a journal line HEAD holds that is gone blocks the next audit, the stop and the commit (at the commit as the index holds them, so a commit restoring a record HEAD lost passes; at the stop HEAD's journal is held to HEAD's files), naming the attempt or the file; in the tree a journal line its copy in the git directory keeps (one per branch, held as a set of lines) that the journal lacks blocks too, with the files its end names — `audits/` deleted whole before a first commit is noticed (not on a detached HEAD, in a fresh clone or with the git directory gone) — a current handover lets the stop and the commit pass on that loss, never the next audit or the adoption (`handovers.missing_evidence` keeps its paths owed); a running attempt refuses a second; the check and the start stand under one lock | `attempts.begin`, `attempts.attempt`, `attempts.gaps`, `attempts.area_gaps`, `attempts.journal_copy`, `attempts.copy_gaps` | `labkit-audit`, `claude-hook stop`, `.githooks/pre-commit` (`claude-hook undecided`) | guaranteed | auditing, ending the turn, committing |
| run → report (denominator) | denominator `c<i>_n` matches a recorded input count | `run_record_check.criterion_n_input_mismatches` | `finalize` | static evidence | after the run |
| report → number | output pinned to the run, recomputation agrees, note cites every number and the run id, block unchanged | `recheck.holds` | (an area's `--check`) | guaranteed | keeping a number |

## One home per question

| Question | Home |
|---|---|
| Is this an intent id / key? | `promises.ID_IN_PROTOCOL`, `promises.ID_KEY` |
| What does the promise block say? | `promises.parse_block`, `promises.load`, `promises.constants` |
| Which code does a promise rest on, and did it change? | `promises.declared_scope_sha`, `promises.scope_drift` |
| What does the protocol's head say (id, type, cost, frozen, audit)? | `protocol_block.head` |
| How is a string written into TOML — a finding's or a review's field, a promise sentence, the head of a report's discussion block? | `protocol_block.toml_string` (one line that reads back through tomllib unchanged; a lone surrogate refused with its cause) |
| Which prose fields does a protocol owe, and which are filled? | `protocol_check.FIELDS`, `protocol_check.check_fields` |
| What does a repeat cost owe — the freeze or the registration, which audits, which cut, the foreground, the provenance check? What does a reported number owe at its release? Which skeleton does an area get, and what is its check? | `standard_contract.lane` (the release reads its `freeze` and `audits`; `report_check`), `standard_contract.skeleton` and `standard_contract.registration_fields` (both by the head's `kind`: what the kept number asserts — a computation has no bar, a fit or an apply registers one; `standard_contract.has_bar`), `standard_contract.CHECK_SCRIPT` — every consumer reads the field it needs; a `repeat_cost == "low"` or a `kind == "compute"` outside the contract is a copy |
| Which protocols does an area hold? Which does the repo? | `repo.area_protocols`; `repo.repo_protocols` (outside `repo.SKIP_DIRS`); `repo.PROTOCOL_GLOB`, `repo.PROTOCOL_NAME` are the name; a protocol is a regular file in the tree and in the index — a symbolic link, valid or broken, is refused with `repo.protocol_link` (`repo.protocol_links` finds them per state; the protocol choice, report-check, protocol-check and the handover ask it) |
| Which area does a bare name name? | `repo.areas_named` (the directory called so and every `NN-<name>` by `repo.AREA_NAME`, `repo.split_area_name`; never a glob); `repo.area_path` for a command's argument, `scaffold.existing_area` for the area `labkit-init exp` promotes or restamps — both refuse a name several areas carry, naming each |
| Which number does a new area get? Does one number name two areas? | `scaffold.next_experiment_number` (one above every number this tree, `_archiv/`, every branch and every other worktree hold — `scaffold.areas_elsewhere` over `repo.branch_refs` and `repo.worktree_roots`), `scaffold.shared_numbers`; `labkit-init numbers --staged` in the pre-commit and the pre-merge-commit |
| Which areas do changed or staged paths touch? | `scope_sha.areas_touched` (the nearest area above each path — `repo.areas_of` — and every area whose promises declare a changed path or whose code imports a changed shared helper; the stop's reported numbers and the commit's undecided findings read the same answer) |
| Where is the repo? Where is the lab? | `repo.git_root` (git), `repo.layout_root` (git, else stamped tree); `repo.lab_root` (the nearest `models.toml`) |
| Run git | `repo.git` (output, loud on failure), `repo.git_run` (exit code is the answer) |
| Print a `labkit-audit` step a person or agent runs next | `repo.audit_command` (quoted, `--protocol` where the area holds several); a check that does not know the working directory names `labkit-audit <area>` and report-check fills it (`gate.Findings(audit=…)`) |
| Ask git about the repository — HEAD, a dirty tree, a path in the git directory, the files a state holds under a folder | `repo.head_sha` (short form, "" outside a repo or unborn), `repo.tree_dirty` (untracked counted or not), `repo.git_dir_path` (this worktree's or the common git dir: locks, stop base, session log), `repo.files_at` (the index's or a revision's files, None where there is no such state — by exit code, not git's words), `repo.branch_refs` (every local and remote-tracking branch), `repo.worktree_roots` (every worktree's directory), `repo.head_before` (the commit HEAD's line stood on before a time, by commit dates) |
| Which directories does an area's `runs/` hold, and what does each say? | `runs.run_dirs` (one walk, metadata read once; an unreadable run is data — the caller refuses, reports or skips) |
| Is this run finished? Which runs are? | `runs.completion_state`, `runs.completed_runs` |
| Where is an area's `runs/`, a run's directory, its metrics file? | `runs.runs_path`, `runs.run_path`, `runs.metrics_path` (`RUNS_DIR`, `METRICS_FILE` are the spelling; a message names the path through them too) |
| Which files are an area's code? | `scope_sha.area_files` (the scripts and analysis globs; the audit stamp, code-check, prompt-check, import-check and intent-check read the same set) |
| How are a JSONL file's lines turned into objects? | `jsonl.objects` (every line, `_meta` skipped, an unreadable line named), `jsonl.data_rows`; `batch.Store` keeps the torn-last-line loop that is its own |
| What answers under a models.toml alias today? | `llm.model_entry` (the same lookup as the spec loader, `llm_specs.alias_tables`; the audit's evidence of a bound validation's alias) |
| Where do a protocol's `## ` sections begin and end? | `protocol_block.section_starts`, `protocol_block.section_end` (outside every fence; the prose count, the Runs list, the cuts, the reading probe) |
| How does a command refuse, tell progress, or print its usage? | `console.refuse` (stderr, the caller exits 2), `console.Refused` (raised where the reason is known, `console.exit_with` prints it), `console.progress` (stderr, no exit code), `console.usage` (0 asked, 2 bare) |
| Write a file whole or not at all | `files.write_atomic`, `files.write_atomic_bytes` (every file a run leaves — records, failure, patch, raw artefacts, source snapshots — the lease, a filled protocol, a protocol `labkit-init` promotes or restamps and the stamp files it replaces; the run index is appended under its lock) |
| The digest of a file, or of a set of named contents | `scope_sha.file_digest`, `scope_sha.tree_digest` (`DIGEST_CHARS` is the one recorded width of a stamp) |
| How is a JSONL text split into its records? | `jsonl.record_lines` (at "\n" only — `str.splitlines` also breaks at U+2028, U+2029, U+0085 inside a record) |
| What does a run's metadata say? | `runs.read_run_config` |
| Does an output file account for its input, item by item? | `batch.Store.ledger` (missing, duplicate, stray, stale per expected field); `require_complete()` inside the run keeps it from completing |
| Which runs wrote a JSONL file's rows? | `batch.row_runs` (per-row `_prov.run`); runlog names the runs a resumed file continues, finalize holds every row to the run |
| Is the recording process alive? | `runs.is_alive` |
| Which protocol does a new run bind to? | `start_check.protocol_binding` |
| What refuses a run before its directory exists, in which order? | `runlog.Run.__init__` (the registration, the detach gate where required and not already detached, the index header, data leakage, then for a full run `start_check.freeze_gate`: undecided blockers, the freeze or the registration, the acknowledgement over a failed audit); `start_check.prepare` refuses what cannot be read before any check |
| Which run answers for a protocol? | `answering_run.bound_answering_run` (the choice; `intent_check.choose_explicit` takes a named run; `recheck.chosen_run` is the same choice behind `--check` and `--from-run`) |
| Is this run a repeat draw, of which, and is it comparable? | `RunConfig.repeat_of`, `answering_run.repeats_of`, `answering_run.repeat_mismatch` (a fit's repeat with `reseed`: its seed held to `answering_run.repeat_seed` of the parent and the draw, the one key a repeat may change; `answering_run.repeat_seed_problem` where draws are read; its own output file `runlog.Run.draw_output`) — a repeat never answers (`bound_runs` leaves it out, `completed_runs(with_repeats=…)` makes every caller decide) |
| Which run recorded the model that answered these rows? | `answering_run.model_provenance_run` (walks `derived_from`; a derived run records none) |
| Is a run's `derived_from` chain whole? | `answering_run.lineage` (every config readable, every parent present, no loop — the whole chain; model provenance, params and row provenance read it) |
| Which protocol does a command hold an area to? | `repo.choose_protocol` (the named one, else the only one; never a guess) |
| What does one check hold — which protocol text, which file state, which answering run? | `report_check.checked` (`Checked`: built once, read by every station; the state is named — the working tree at the stop, the index at the commit, the written proposal at the adoption; the run is `answering_run.bound_answering_run`'s choice through `audit_binding.audited_run`) |
| How does a registered constant stand against the record? | `promises.constant_records` (equal / different / missing, type-strict); runlog refuses before mkdir, intent-check/finalize block, `labkit-params` shows all three |
| Does a frozen protocol owe a promise block? | `promises.promise_tables_owed` — protocol-check (MUST), preflight and finalize (blocker), runlog (refusal before mkdir) |
| Which state of the area does an audit record bind, and does a record bind the state now? | `findings.AuditedState` (`audit.bound_prompt` binds it, `Record.state` carries it, `covering_records` compares the two) |
| Which analysis records cover the area now — code, promises, the answering run and what the audit was shown of it? | `audit_binding.covering_analysis` (`analysis_now` the state, `run_shown` the snapshot; report-check's analysis stage and its Limit lines, `protocol-fill --from-run`) |
| What does the result section say when it says what its sources say — and does it? | `result_render.rendering` (the Recorded results line from the declared run's metrics.json with its note, one Limit line per decided limit of the covering records), `result_render.render_gaps` (exact equality, each difference named; report-check's analysis stage, `protocol-fill --from-run` and `--render` write it) |
| Does a report outside the protocol show a reported number as its sources render it? | `report_blocks.blocks`, `report_blocks.block_body`, `report_blocks.block_gaps` (a report result block shows the run its protocol declares now and equals that protocol's Recorded results and full Limit lines; `protocol-fill --into` writes it), `report_blocks.cited_gaps` (every token that reads as a run id names a run of the repo), `report_blocks.unsourced_numbers` (numbers outside every block — a hint); `report_check.if_reported` holds changed citing reports, the protocols their blocks name and the protocols declaring the runs they cite, and the committed reports citing a run a protocol among the paths newly declares against HEAD (`report_hold.newly_declared`, `report_hold.committed_reports` — the two-step commit of the sixth round, t5) |
| Does a review uphold a decision as it stands now, under the claim the protocol makes now? | `reviews.upholding` (a review of that record, its code and its run as shown, of the claim's digest `reviews.claim_digest` over `protocol_check.reported_claim`, holding the decision's digest `findings.decision_digest`, every such draw saying `upheld`), `reviews.contested` (another draw settles nothing), `reviews.once_not_upheld` (was a decision on this finding ever not upheld — then closing it owes a review too), `reviews.state` for the gate's sentence |
| What does a file say at a git state — the index, HEAD? | `repo.text_at` (the index's or a revision's content, None where that state does not hold the file); `repo.state_text` for "the tree or the index" as a gate reads it — both name the file when its bytes are not UTF-8; `repo.indexed_files` for what the next commit carries; `repo.under_root` for whether a given path is the repo's at all |
| What carries a gate finding's sentence — a mechanical check or an indication? | `gate.GateFinding.evidence_kind` (`GUARANTEED` / `STATIC_EVIDENCE`, given at every site, never defaulted; static evidence never blocks, the dotted line names it, the summary counts it; `labkit-params` shows the same constants in its evidence column; the agent audit is the records' kind, `findings.Finding`) |
| Which audit findings are still undecided, and what does each gate make of one? | `findings.open_findings` (every mode, or one; the table of the gates' rules stands in its docstring: preflight warns unfrozen and blocks frozen, runlog refuses on a preflight BLOCKER and tells the rest only on an acknowledged start, finalize every record by grade, the hooks, the handover and `labkit-audit --findings` hold BLOCKERs only (`findings.open_blockers`); the one record the head names is a gap on any open grade, `findings.audit_record_gap` — the differences are intended) |
| Which code did an audit see, and is it still that code? | `scope_sha.area_snapshot` (the bytes read once and the sha over them; `area_stamp` its sha); the record carries its `scope_sha`, and `findings.audit_coverage` holds it to the stamp now (area stamp, not per promise) |
| Which package does a requirements line name, and how is labkit pinned? | `repo.requirement_name`, `repo.requirement_lines`, the four `*_REQUIREMENT` grammars (stamp pin line, `labkit-check`, lock parser, probe) |
| What is a run id, when did the run start? | `runs.RUN_ID`, `runs.RUN_ID_TIME`, `runs.run_started`; `runs.COMPLETED` is the one state word every consumer compares to |
| How is a path shown in a report line, a bundle or a refusal? | `repo.shown(path, base)` — relative to the base when below it, else absolute, both resolved; a record's path is `runs.recorded_path`, a stamp's hashed key `scope_sha._key` |
| How does a record state a time? | `runs.now_stamp()` in `runs.RECORD_TIME` (`2026-10-13T14:00:57`, local) — a run's `started`/`finished`, a lock's or lease's holder, a staged probe, a session's stop |
| How does a gate tell what it found, and exit? | `gate.Findings` (`block`, `warn`, `take` for a `GateFinding` built where it was found — `gate.blocker` for a pure check's, `gate.coded` for a code check's, grade, where, rule and fix as fields; `note` for a line counted as nothing, `report`; `Findings(tell=None)` collects the same findings without a console — report-check reads finalize's so, fixes included) — preflight, finalize, report-check, code-check, notes-check |
| What is the way out of a BLOCKER? | `gate.GateFinding.fix` — required for a BLOCKER (refused without one, every building site held by `tests/test_ways_out_data.py`), told in every form (`… — way out: <fix>`, `gate.with_way_out`; a dotted line's last part) and repeated in the summary; built where the cause is known, from the shared command builders (`repo.audit_command`, `repo.decide_command`, `repo.measure_command`, `repo.adopt_command`, `findings.decide_way`, `findings.record_way`, `ways_out.register_anew`, `ways_out.HANDOVER`, `ways_out.ANSWER_AGAIN`); the refusals outside the findings carry one the same way — `AuditError` and `AttemptError` take `fix` as a required keyword, runlog's start refusals are `SystemExit(with_way_out(…))`, exemptions listed with their reason in `tests/test_ways_out_data.py`; the ways out by cause, for a person deciding an audit BLOCKER: `ways_out.WAYS_OUT` |
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
| `preflight` | before `frozen = true` (high repeat cost) | protocol-check, the lane's duties, the audit record and its coverage, the promises, the tests | no test file: a warning, a blocker once frozen; a failing test: a blocker | `claude-hook pre-run` before a recognised measurement command |
| `labkit-audit --mode preflight` | before the freeze (high repeat cost) | the agent audit of the registration and the code; every finding decided by a person | — | — |
| `runlog` (the run's start) | at every full run | the registration, the binding, leakage, the freeze and the audit coverage the lane owes; undecided preflight findings by grade | — | the run itself |
| `finalize` | after the run, before the number is written back | the answering run, intent-check, the run's code and the declared scopes, open fields, provenance (low), the tests, criterion n, the null lane, undecided findings of any mode by grade | no test file: a note; a failing test: a blocker | `report-check` runs it as one station |
| `labkit-audit --mode analysis` | after the run, at every repeat cost | the agent audit of the answering run; every finding decided, an accepted BLOCKER with its effect | — | — |
| `labkit-audit --review` | when a BLOCKER was accepted with `stands`, and when a finding a review did not uphold was closed instead | a second auditor on the decision | — | — |
| `labkit-audit --report-review` | when a report discusses a run | a cold reader on the report against the discussed run's metrics and the audits; writes `audits/report-reviews/<minute>-review.toml` | — | named by `claude-hook post-change`, owed by `report-check` (blocker until a review of the state names no claim); started by the agent |
| `report-check` | before the number leaves the area, at every repeat cost | the whole chain: declaration, registration, finalize, the analysis record's coverage, the rendered result, `02_analyze.py --check` | through finalize | `claude-hook stop` (`--if-reported`), the pre-commit (`--if-reported --staged`) |
| `claude-hook undecided` | at the stop and the commit | undecided audit BLOCKERs in the areas the session touched, and audit evidence gone or unreadable unless a current handover binds that loss | — | `claude-hook stop`, the pre-commit |

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
| `audits/report-reviews/<minute>-review.toml` | `report_reviews.write_report_review` | a cold reader's reading of a report that discusses a run |
| `audits/attempts.jsonl`, `audits/answers/<attempt id>.txt` | `attempts.begin` (`Running.keep_answer`, the journal lines) | every model call of `labkit-audit`, its kept answer and how it ended |
| `<git common dir>/labkit-attempts/<branch>/<area>.jsonl` | `attempts._append`, beside every journal line (`attempts.journal_copy`) | the journal's copy outside the working tree, never committed |
| `audits/handovers/handover-<hex>.json` | `handovers.write_record` | a protocol's end without a result: the audit files by blob id, losses, findings left unsettled; the report's handover block is its projection |
| `runs/<id>/*.json`, `runs.tsv` | `runlog`, `runs.write_failure` | the run: config, outputs, metrics, completion or failure |
| `.git/labkit-sessions.jsonl` | `claude_hooks.record_session` | which runs a session started (no verdict) |

An audit record names the run it read, not the protocol: the match
against the registration is computed from the protocol as it reads now
(`registration`), and in an area with several protocols the gate
chooses the protocol first (`repo.the_protocol`). Carrying a protocol
id in the record is noted in `TODO.md`, not planned.

## Run and hook enforcement

The Claude Code hooks load only in a session started in the repository
root: Claude Code reads a project's hooks from `.claude/` of the directory
it starts in, with no fallback to a parent; `labkit-hooks install` says so,
and the git pre-commit holds a commit wherever the session started.

`standard_contract.lane` supplies the obligations for a protocol's cost
tier. At `low` there is no freeze or preflight audit; release of a
result still requires a full run, a clean finalize, a decided analysis
audit bound to the current code, promises and answering run, and the
recomputation check. At `high`, the start of a full run also
requires a frozen protocol and matching preflight audit coverage.

The audit field is checked against an actual record under `audits/`.
Changing the bound code or promises invalidates that coverage. An
analysis record additionally names the answering run. Snapshot binding
and the declared-scope hash have separate purposes; see
[promise-block](promise-block.md) and the chain above.

`run_kind="measurement"` declares a measurement; `run_kind="probe"` declares
an instrument check. `run_kind="preparation"` records data preparation
without releasing a result. At low repeat cost a separate probe is refused: the complete
measurement checks the instrument and can be repeated cheaply.
`runs.unreportable` refuses a probe or an acknowledged unfrozen run as the
source of a reported number. At high repeat cost, `LABKIT_UNFROZEN=1` permits
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
| git pre-commit | Checks staged protocols, one number per area where a staged path lies under `experiments/`, affected reported results and unresolved audit blockers. Report checks use the staged answer and require the area's working tree to agree with the index; a staged declaration that differs from HEAD's reaches the committed reports citing that run. |
| git pre-merge-commit | Checks that the merge's index gives every area a number of its own. git runs it, not pre-commit, for a merge it completes without conflicts; the merge is where two branches' areas meet. |
| Claude `pre-run` | Runs preflight for recognized measurement commands; blocks a frozen area's command on blockers. |
| Claude `post-change` | Reports protocol and note checks after changes, and names `labkit-audit --report-review` for a changed report that discusses a run (a report that is a symbolic link: the refusal the stop and the commit give it, with its way out); for an area whose `audits/` or `runs/` git status names, tells what the stop and the commit will hold of its evidence — gone, rewritten beyond its decisions, a closed run changed — with each line's restore, holding nothing itself (`claude_hooks.evidence_areas`); tracks content and evidence state per session to avoid repeating what was told. |
| Claude `stop` | Sends the session back for a failed release check or an unresolved audit blocker in an affected area — changed in the tree or committed since the session's stop base (kept by `pre-run` before the first command, moved only past a clean stop on a working tree equal to HEAD; without one, said, the commits dated since the transcript began; with no transcript start either, it holds) — once per turn, and for checks that outrun the stop's budget (`claude_hooks.STOP_BUDGET_S`, under the hook's timeout); the next turn's stop holds again. |

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
`LABKIT_DETACHED=1`. The low lane allows foreground execution.

An audit's duration is separate from a measurement's repeat cost. Use the
harness's background-task mechanism for a long `labkit-audit` call and
wait for that task, rather than polling process-name matches.
