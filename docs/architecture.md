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
| 1 · formats and places · `labkit/formats/` | `protocol_block`, `comment_blocks`, `prompts`, `promises`, `protocol_check`, `protocol_history`, `standard_contract`, `runs`, `answering_run`, `repo`, `scope_sha`, `data_manifest`, `rules`, `findings`, `failed_attempts`, `audit_gaps`, `followup`, `reviews`, `report_reviews`, `attempts`, `handovers`, `evidence`, `console`, `gate`, `shell`, `files`, `jsonl`, `deliverable`, `reference`, `criterion_bar`, `timebox` | `protocol_check`, `protocol_history`, `standard_contract`, `rules`, `findings`, `failed_attempts`, `audit_gaps`, `followup`, `reviews`, `report_reviews`, `attempts`, `handovers`, `evidence`, `timebox` |
| 2 · a run and its effects · `labkit/run/` | `runlog`, `provenance`, `code_repos`, `start_check`, `runlog_command`, `detached`, `batch`, `llm`, `llm_specs`, `llm_backends`, `llm_cache`, `endpoint_lease`, `lanes`, `profile` | `lanes`, `profile` |
| 3 · checks · `labkit/checks/` | `intent_check`, `code_check`, `code_scan`, `gate_label_scan`, `import_check`, `prompt_check`, `run_record_check`, `readme_check`, `recheck`, `notes_check`, `audit_binding`, `result_render`, `data_counts`, `report_blocks`, `report_review_inputs`, `protocol_report` | `readme_check`, `notes_check`, `audit_binding`, `result_render`, `report_blocks`, `report_review_inputs`, `protocol_report` |
| 4 · gates · `labkit/gates/` | `preflight`, `finalize`, `report_check`, `report_context`, `report_replacement`, `report_decisions`, `report_hold`, `agent_hooks`, `claude_hooks`, `codex_hooks`, `audit`, `audit_prompt`, `audit_reply`, `audit_decisions`, `decision_review`, `report_review`, `install_hooks`, `ways_out` | `preflight`, `finalize`, `report_check`, `report_context`, `report_replacement`, `report_decisions`, `report_hold`, `agent_hooks`, `claude_hooks`, `codex_hooks`, `audit`, `audit_prompt`, `audit_reply`, `audit_decisions`, `decision_review`, `report_review`, `install_hooks`, `ways_out` |
| tools · `labkit/tools/` | `protocol_fill`, `protocol_edit`, `protocol_result`, `scaffold`, `protocol_cuts`, `repo_check`, `params`, `calltree`, `next_step`, `adopt` | `protocol_fill`, `protocol_edit`, `protocol_result`, `scaffold`, `protocol_cuts`, `calltree`, `next_step`, `adopt` |
| tools · probes · `labkit/probes/` | `usability`, `usability_score`, `usability_command`, `sab_cases`, `agent_transcript`, `cold_reader`, `protocol_reading`, `code_navigation` | `usability`, `usability_score`, `usability_command`, `sab_cases`, `agent_transcript`, `cold_reader`, `protocol_reading`, `code_navigation` |

The third column names the doctrine modules of each row; every other
module in the second column is core.

## Public API

The layer table holds the imports inside labkit; this section is the
contract outward — the names a lab repo may import and rely on, through
`from labkit.run import llm, llm_backends, llm_cache, runlog, batch`. Everything else is internal
and may change in any release with a "Breaking" entry in `CHANGELOG.md`.

**The release rule.** A name, signature or behaviour listed here changes
only after one release in which the old form still works and warns
(`DeprecationWarning`, named in `CHANGELOG.md` under "Deprecated"); the
release after that removes it under "Breaking". A fix that makes a name
do what this table says is no such change. The list starts short and
grows when a lab needs a name — taking one back would break labs.
`tests/test_public_api.py` reads both tables: a listed name that is gone,
a signature or default that changed (for an attribute, its annotation), or a `models.toml` key that a backend
no longer reads fails the suite; the contracts in the third column have a
behaviour test each.

| Name | Signature | Contract |
|---|---|---|
| `llm.complete` | `complete(alias, prompt, *, system=None, temperature=None, timeout=300, attempts=6, raw=False, stop=None, max_tokens=None)` | the answer text (`str`); transport failures are retried, and exhausted retries raise `BackendError` (a `RuntimeError`) whatever the backend threw; an HTTP 4xx raises `BackendError` at once; an alias `models.toml` lacks raises `KeyError`; a setting the backend cannot honour (a temperature or a token cap for `claude-cli`) raises `ValueError` |
| `llm.complete_many` | `complete_many(alias, prompts, *, workers=4, **kw)` | `complete` over independent prompts, answers in input order |
| `llm.complete_response` | `complete_response(alias, prompt, *, system=None, temperature=None, timeout=300, attempts=6, raw=False, stop=None, max_tokens=None)` | `complete` with everything the call returned, a `Response` whose `text` is what `complete` returns; arguments, retries and errors as `complete`'s |
| `llm_backends.Response` | `Response(text, thinking, finish_reason, usage, endpoint, body)` | a frozen record of one completion: the answer `text`, the reasoning `thinking` (`""` when none), the `finish_reason` the backend reported (`None` when none), the `usage` (`Usage`), the `endpoint` that answered (`""` for `claude-cli`), the decoded reply `body` (`None` when the backend handed back none) |
| `llm.resolve` | `resolve(alias)` | the spec as a run records it (`backend`, `model`, `endpoint`, …), a new dict each call — what goes into `runlog.run`'s config |
| `llm.spec` | `spec(alias)` | the typed spec every call is made with (`ClaudeCliSpec`, `OllamaSpec`, `OpenAISpec`), frozen per process at first use: an edit of `models.toml` reaches a new process only |
| `llm.identity` | `identity(alias)` | which model answers: `backend` and `model` (`name@digest` for ollama); no endpoint, since a host can change while serving the same weights |
| `llm.last_usage` | `last_usage()` | the token counts of this thread's latest completion (`Usage`); `NO_USAGE` before the first call |
| `llm.last_endpoint` | `last_endpoint()` | the URL this thread's latest attempt went to; `""` when it went to `claude-cli`, and before the first call |
| `llm.retries` | `retries()` | how many transport retries this process has made, for the run's metrics |
| `llm.provenance` | `provenance(alias)` | the per-row stamp for `batch.Store(prov=…)`: `model` (`name@digest` for ollama) and `endpoint` as a callable, evaluated per row; for `claude-cli` also `cli_version`, `cli_flags`, `cli_input` |
| `llm.find_models_toml` | `find_models_toml()` | the lab's `models.toml`, searched upward from the script's directory, then from the working directory; `FileNotFoundError` when neither has one |
| `batch.Store` | `Store(path, id_key='id', prov=None, mode='resume', instrument=None)` | append-only JSONL output under a lock, a context manager; `resume` continues by id, `produce` replaces the file on a clean exit |
| `batch.Store.pending` | `pending(records)` | the records whose id the file does not hold yet; raises `InstrumentError` when the file holds rows of another instrument |
| `batch.Store.append` | `append(record)` | one record as one line, stamped with `_prov` and `_instrument` when given |
| `batch.Store.records` | `records()` | the rows the file holds |
| `batch.write_dataset` | `write_dataset(path, rows, *, about, fields, producer)` | replaces PATH with a `_meta` header line (about, field legend, producer) and one row per line; a row whose keys differ from the legend, or a `TODO` left in ABOUT or the legend, raises `ValueError` before anything is written |
| `runlog.run` | `run(experiment, config, base_dir=None, data=None, run_kind='probe', protocol=None, derived_from=None, repeat_of=None, reseed=False)` | a context manager yielding the `Run`; `config.json` records the config and, per `data` key, path, `sha256` and `rows`; a refusal (split leakage: `RuntimeError`) leaves no run directory; a clean exit writes `metrics.json`, `completion.json` and the `runs.tsv` row; an exception is recorded in the run and re-raised, with no index row |
| `runlog.Run.output` | `output(*paths)` | registers files the run writes; at a clean exit `outputs.json` holds each with `sha256` and `lines`, or a note when it is absent |
| `runlog.Run.metrics` | `metrics(**kv)` | adds numbers to the run's `metrics.json`, written at a clean exit; a value JSON cannot hold raises `TypeError` naming its key |
| `runlog.Run.run_id` | `run_id: str` | the run's id: the name of its directory and its row in `runs.tsv` |
| `runlog.Run.draw` | `draw: int \| None` | a repeat's draw number (2, 3, …); `None` for a run that repeats none |
| `llm_cache.Cache` | `Cache(run, *, replay=False, root=None)` | the cache of raw answers as one run uses it; its mode is `repeat` when the run repeats another (`Run.draw` set), `replay` with `replay=True`, else `normal`; opening writes the run's `llm-cache.json` (cache version, mode, directory); `root` defaults to `cache/llm/` beside the lab's `models.toml`, created with a `.gitignore` of `*` (`FileNotFoundError` when no `models.toml` is above the run); a replay asked of a repeat raises `ValueError` |
| `llm_cache.Cache.complete` | `complete(alias, prompt, *, system=None, temperature=None, timeout=300, attempts=6, raw=False, stop=None, max_tokens=None)` | one completion through the cache, an `Answer`; arguments, retries and errors as `llm.complete`'s. The key is the answering model (`llm.identity`), the spec field that changes the answer, the prompts and the sampling values as sent — not the alias, not the endpoint. `normal` reads a hit and stores a miss's answer, the first under a key staying; `replay` asks no model, a miss raises `CacheMiss` (a `LookupError`); `repeat` asks the model and neither reads nor stores. An ollama model without one weights digest is not cached, said on stderr, and refused by a replay; an entry that is not one raises `CacheCorruptionError` (a `ValueError`). Each call adds a line to the run's `llm-calls.jsonl`: key, alias, `hit`, origin, usage, why not cached |
| `llm_cache.Answer` | `Answer(response, origin)` | the `Response` (for a hit the stored one, with the original call's usage) and its `origin`: `None` when the model was asked |
| `llm_cache.Origin` | `Origin(run, written)` | where a hit came from: the id of the run that stored it (`None` when stored outside a run) and when |

`models.toml`, the keys each table may carry; any other key is refused
when the alias is first resolved (`ValueError` naming the key), and so is
a served backend without `endpoints`:

| Table | Keys |
|---|---|
| `[models.<alias>]` with `backend = "claude-cli"` | `backend`, `input`, `model` |
| `[models.<alias>]` with `backend = "ollama"` | `api_key`, `api_key_env`, `backend`, `endpoints`, `model`, `num_ctx` |
| `[models.<alias>]` with `backend = "openai"` | `api_key`, `api_key_env`, `backend`, `endpoints`, `model`, `reasoning` |
| `[endpoints]` | one name per URL; `endpoints` lists names or literal URLs, and a name the table lacks raises `KeyError` |
| `[audit]` | `model`, the alias `labkit-audit` uses without `--model` |

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
`attempts` retains expected lost paths from those records across commits.
Its journal reader and writer require every analysis/preflight start to
name its promise block and protocol. Old starts lacking either binding are
refused, not migrated; reviews bind their own inputs separately. A failed
file no journal attempt names remains visible without an invented start.
Contract and format boundary:
[audit journal bindings](notes/2026-11-03-audit-journal-format.md).
Contract and limits:
[handover recovery](notes/2026-10-27-handover-recovery.md).

`evidence` holds what committed evidence may become: a record changes in
its findings' decision lines alone, another audit file never, a closed
run never; a version back as labkit first committed it is no change. Its
witnesses are git's — the tree or the index against HEAD (the hooks;
`change_blockers` for every release that reads an area's records:
report-check's first station, an exploration's registered report, a
replacement's predecessor in another area, `labkit-next` before a
handover), at the stop
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
`code_repos` records the code the run imported beyond the lab repo's
commit: every git repository that holds an imported module — labkit, a
framework installed editable, a topic package — with its commit, its
tracked changes as a patch and its untracked imported files copied
(`code.json`, `code/`). It reads at the start and again at a clean finish,
for modules imported during the run; a measurement refuses to start on
untracked code it cannot copy (above 2 MB).
`provenance.BinaryInput(path)` explicitly marks a binary dependency in a
run's `data` mapping: its bytes are hashed, `rows` is null, and dataset
decoding and row-id leakage checks do not apply to that input. Ordinary
dataset paths retain those checks; one that is not UTF-8 text is refused
with a decode error naming the key, the file and this wrapper
(`provenance.BINARY_INPUT_WAY`). The decode decides, not the file type:
a binary file whose bytes happen to decode is read as text, so a binary
input is declared, never recognised. The local apply template marks its
declared predictor artifacts this way; the prepare stamps and AGENTS.md
name it where they ask for every file a run reads.
`runlog` writes the run and index; `runlog_command` implements the console
command; `detached` keeps the record of a command `runlog start` detached,
locked while the command runs, with the exit status its supervisor
writes, so `runlog AREA --wait` sees it before its run opens a record and
fails on it when it ended without one. `batch` manages resumable output. `lanes` is the run mechanics of
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
(the wire calls). `llm_cache` keeps a lab's raw model answers across
runs (`cache/llm/` in the lab repo), keyed on the answering model, the
answer-changing spec fields, the prompts and the sampling values; a run
opens it in one of three modes — normal, replay (no model asked, a miss
stops the run), repeat (never read) — and records the mode and every
call, hits with their origin (`llm-cache.json`, `llm-calls.jsonl`).
`endpoint_lease` manages the model-slot lease.

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
context (`report_context`) supplies this gate's declaration and answering
run; the replacement station stands in `report_replacement`, the stations
on the audit decisions in `report_decisions`. Nested
finalize and the analysis script read their own inputs.

`agent_hooks` calls the gates during an agent session; `claude_hooks` and
`codex_hooks` adapt each harness to those shared checks. `audit` runs the
agent review through `llm`: `audit_prompt` builds what the auditor is shown
and binds it to the stamp, `audit_reply` reads its answer, and
`audit_decisions` lists and stores the person's decisions (`--findings`,
`--decide`); `decision_review` runs the second auditor on
the `stands` decisions of one record (`labkit-audit --review`);
`report_review` runs a cold reader on a report — owed by one that
discusses a run and by the one a head registers
(`labkit-audit --report-review`) and records its claims
(`formats/report_reviews`), which report-check holds the report to.
`install_hooks` installs the git hooks that run the gates; preflight
checks that they are installed.

### Tools

`labkit/tools/` provides commands that may use any layer. `protocol_fill`
fills protocol fields and adopts a run: its text edits stand in
`protocol_edit`, the writers of the result section in `protocol_result`.
`scaffold` stamps a lab repo and its areas from the
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
| promise → code (quality checks) | every quality-check key the code writes is tested somewhere (`if`, `and`/`or`/`not`, `all()`/`any()`, a loop over a key tuple) — else the criterion verdict is reported whether the condition held or not | `code_check.quality_check_reads` | `code-check`, `preflight` | static evidence | before the run |
| promise → code (ids, parsers, prompt) | each intent id appears as a key; every `parse_*` is named in a test; every line of a `PROMPT` constant stands in the protocol's prompt block | `code_check.code_findings` (`prompt_check` for parsers and prompt) | `code-check`, `preflight` | guaranteed | before the run |
| promise → code (stamp coverage) | code the audit stamp cannot follow — a `sys.path` edit, a dynamic loader, an import outside `lib/` and `src/` — is named by line | `import_check.stamp_coverage_findings` | `code-check`, `preflight` | static evidence | before the run |
| promise → code (gate labels) | the string comparisons in the evaluation code are extracted into the bundle; whether they match the prompt is the judgement of an agent the lab runs on it (labkit ships none; the preflight audit reads the code whole) — the extraction never judges | `gate_label_scan.gate_labels` | `code-check --bundle`, then the lab's own agent | agent audit, outside labkit | before the run |
| promise → code (meaning) | code does what the promise says | `audit` (experiment-preflight instructions + the area's files + the standard, one `llm` call); or the bundle (`code-check --bundle`) for an agent the lab runs | `labkit-audit --mode preflight` | agent audit | before the run |
| run → report (meaning) | the evaluation means the frozen criterion; every earlier decided BLOCKER (`fixed`, `limitation`, `false-positive` in a record not of the state audited; only the head of each carried chain, `followup.chain`) is shown with its decision, and so is every earlier correction of a protocol field at any grade (a finding naming the field as its place, decided `fixed`; `followup.earlier_corrections`), with the field as first registered and as it reads now (`audit_prompt.FieldChange`); a BLOCKER's verdict other than `resolved` carries the finding into the new record (open, origin text, check kept, `carries`, counted in `blockers` and `carried_blockers`); and the auditor writes one `FIX · <record>#<n> · resolved \| unresolved \| not_assessable · <why>` entry per finding (the why may continue below the line up to a blank line or the next entry, kept whole; an entry naming another shown finding is refused), stored as `[[fix_verdict]]` bound to the decision shown (`findings.decision_digest`); a FIX line that does not read, names a finding not shown, repeats one or carries another word, or a shown decision changed during the call, records nothing; a finding without a line stays unchecked; a finding may require a diagnostic (`· check: <metrics key>`, or `· check: file:<path>` for a file the run declares as a dependency, optionally ` (<note>)` or ` — <note>` to the line's end, the note kept whole as `check_note`; the auditor's, kept by every decision and bound in the digest), whose whole value from the shown metrics.json — or the file shown whole as a `DEPENDENCY` piece — the prompt carries and whose presence each verdict records (`check_present`, from that snapshot, `audit_binding.check_evidence`, the same lookup report-check makes; absent when none is required) (pilot, no gate yet: eighth round, t3) | `audit` in MODE analysis, `audit_reply.parse_fixes`, `followup.earlier_blockers`, `findings.FixVerdict` | `labkit-audit --mode analysis` | agent audit (the verdict); guaranteed (its form and binding) | after the run |
| run → report (the decisions) | a limit whose effect is `stands` claims the verdicts hold within the limit; a second, cold auditor gets the finding, the reason, the finding's required check with its value in the run or that it is missing (`audit_prompt.required_check_line`, the follow-up's wording), the protocol (registration and reported claim), the files the findings name as the auditor read them — when none names a code file, the reviewed run's measuring script as it ran (`run_record_check.script_as_run`: the area's file when its digest is the run's `script_sha`, else the run's own copy, labelled; else a line why none is shown) — and what the auditor was shown of the run, and says per decision `upheld`, `rejected` or `insufficient`; only `upheld` releases, and only when every draw on the decision as decided and claimed now says so (a contested state is settled by deciding again, never by another draw); a changed decision or a rewritten Conclusion makes the review stale (the Recorded results and Limitation lines are generated and bound through the record and the run); report-check blocks on a BLOCKER limitation's `stands` no review upholds and warns on a WARNING limitation's; a finding a review once did not uphold (`reviews.once_not_upheld`) and that is now `false-positive` or `fixed` (`findings.CLOSING`) is held the same way until a review upholds the new decision — the reviewer is asked whether the reason shows it inapplicable, gone or somebody else's (sixth round, t5: a dismissal after `insufficient` released the state); a BLOCKER on the Conclusion decided `fixed` (`findings.fixed_claim`) is held the same way — no follow-up audit is shown a rewritten claim, so the review judges the Conclusion as it stands; the review's record (`audits/<minute>-review.toml`) is held three ways, unequally: bound to its inputs — a changed decision or a rewritten Conclusion makes it stale (guaranteed); once HEAD holds it, a record changed since is refused at the commit and in working-tree release checks, including `labkit-next` and `report-check AREA` (`evidence.change_blockers`, guaranteed); its content is compared with no journal line, kept answer or evidence copy, so `rejected` rewritten to `upheld` before the first commit releases the decision — where what the record says came from is unchecked ([limit](notes/2026-11-02-review-record-forgery.md)) | `decision_review.gather_review`, `decision_review.parse_review`, `reviews.upholding`, `reviews.once_not_upheld`, `report_decisions.review_findings`, `report_decisions.repaired_claims` | `labkit-audit --review`, `report-check` | agent audit (the release condition: guaranteed, on the record as written; the record's origin: unchecked) | after the analysis audit is decided |
| run → report (the follow-up) | an earlier decided BLOCKER (`fixed`, `limitation`, `false-positive` in a record not of the state reported) is released only by a covering analysis record's valid `resolved` — the head of its origin, its decision as it stands, a required check shown — while no covering record holds another verdict on that origin, or carried into a covering record, where it is decided; a carried finding `false-positive` owes an upholding decision review; a BLOCKER `fixed` in the state reported is held; each sentence names the missing step (pilots: [fixed follow-up](usability/2026-10-26-fixed-followup-pilot.md), [second](usability/2026-10-26-fixed-followup-pilot-2.md)) | `followup.release_holds`, `followup.chain`, `report_decisions.followup_findings`, `decision_review.reviewable` | `report-check`; `claude-hook stop`, `.githooks/pre-commit`, `protocol-fill --from-run` | guaranteed (the binding and the release); agent audit (the verdict) | before the number leaves the area |
| run → report (a discussed run, the registered report) | a report discussing a run (a discussion block), and the report a head registers once its result or handover block stands, present as a result nothing the protocol has not adopted and nothing the audit decisions or the adopted result contradict; a cold reader gets the report with line numbers, the adopted run, the discussion blocks, the protocol, the `metrics.json` of the adopted, each discussed and each cited run and every audit record with its decisions and failed attempts, and names the lines as `result` or `contradiction`; recorded in `audits/report-reviews/` with the fingerprint of exactly the inputs it read (its own folder and the attempt journal not among them); report-check holds the report, per protocol its discussions name, until a review of its state — the report and protocol as the gate's state holds them, at the commit only records the index holds and the area's tree equal to the index — names no claim; a committed report discussing a run of an area a change touches is held with the change (`report_hold.discussing_reports`); a claim holds the state — an `--again` draw's as well — and a later clean draw (or `--again`) releases nothing; the command prints the draw and the state apart and exits with the state (0 released, 1 held), a changed input (the report, the protocol, a run's metrics, an audit decision) owes a new review; the post-change hook names its command (pilot: [report review](usability/2026-10-25-report-review-pilot.md)); a report that cites no run is out of its reach; the review's record is held three ways, unequally: bound to the inputs it read — a changed input owes a new review (guaranteed); once HEAD holds it, a record changed since is refused at the commit and in working-tree release checks, including `labkit-next` and `report-check AREA` (`evidence.change_blockers`, guaranteed); its content is compared with no journal line, kept answer or evidence copy, so a claim deleted before the first commit releases the report — where what the record says came from is unchecked ([limit](notes/2026-11-02-review-record-forgery.md)) | `report_review_inputs.review_pieces`, `report_review.parse_claims`, `report_reviews.standing`, `report_hold.report_review_owed` | `labkit-audit --report-review`; `claude-hook stop`, `.githooks/pre-commit` | agent audit (the claims); guaranteed (the record's binding to its inputs and its claim count as written); unchecked (the record's origin) | when a report discusses a run; ending the turn, committing |
| promise → reader | a person who did not build the area can tell what it decides | `audit` in MODE clarity (code-clarity area rules + README, protocol, measure script) | `labkit-audit --mode clarity` | agent audit (static evidence: never a gate) | before freezing |
| code → run | unfrozen full run, unbound run, dangling scope, control leakage: refused before the run dir exists | `runlog.Run` | (every run) | guaranteed | starting the run |
| code → run | a full run's head names the decided preflight record (`preflight_audit = "<minute>-preflight.toml"`), and that record saw the code and the promise block as they are now; an `n/a` or any other text at high repeat cost is refused (nobody waives their own audit) | `runlog.Run`, `audit_gaps.audit_record_gap` | (every full run), `preflight` | guaranteed | starting the run |
| promise → run (tier) | the repeat cost is not lower than in the protocol's first commit — a lower tier owes less | `protocol_history.repeat_cost_lowered` | `protocol-check`, `preflight` | static evidence | before the run |
| code → run | a long pilot's `LABKIT_UNFROZEN=1` rests on a failed audit attempt at the code and promises as they are now (`audits/*-failed.toml`, written by `labkit-audit` when the backend does not answer or answers unproven — `cause`; after an `unproven` attempt `labkit-audit` refuses the same state with the same model, `failed_attempts.stopped_attempt`), else refused; `run_kind`, `unfrozen_ack` and `audit_failed` recorded | `runlog.Run`, `failed_attempts.audit_unavailable` | (every acknowledged full run) | guaranteed | starting the run |
| code → run | block digest, per-promise `declared_scope_sha`, constants, git state, data hashes recorded | `runlog.Run`, `promises.snapshot` | (every run) | guaranteed | starting the run |
| code → run | the estimator skeleton's rows carry the measuring code, so a resume across a code change is refused, naming the runs, what differs and a new output name; a run that continues a finished run's file is told so (its rows count as its own) | `scope_sha.measured_code_sha`, `batch.Store.pending`, `runlog.Run.output` (`continued_warning`), `runs.next_output_name` | (every run) | guaranteed | registering the output, resuming |
| run → report (record) | run completed; declared keys reported; run recorded this block; a block constant not contradicted by the run config | `runs.completion_state`, `intent_check.check_block_against_run` | `intent-check`, `finalize` | guaranteed | after the run |
| run → report (continued rows) | rows that carry their code (`_instrument.code_sha`), continued from a run whose script differs from the answering run's: a blocker — the number is that code's; a model's answers re-read after a parser fix pass | `run_record_check.row_provenance_findings` | `finalize` | guaranteed | before the number leaves the area |
| run → report (the null lane) | an output the run kept with a registered and a null lane: the null answers otherwise on some item, gold included — read from the kept rows, not from the editable script | `run_record_check.null_lane_findings` | `finalize` | guaranteed | after the run |
| run → delivered file | every output the run registered (`run.output`: its rows, and the deliverable of an external task the stamped script writes from the kept rows, `formats/deliverable`) is the file the run recorded — path and sha256 from outputs.json, never from the tree; gone or changed is a blocker | `run_record_check.output_record_findings` | `finalize` | guaranteed | after the run |
| run → report (code) | for the answering run and each run it derives from: the measurement script (the path its command names) unchanged since the run (its recorded `script_sha`), and every module it imports — beside it, under `lib/` or `src/` (`scope_sha.measured_code`) — as the tree the run started from held it (its commit with the part of its `uncommitted.patch` for that module, read in a temporary index); a module in another repository a warning; analysis code and the pin not compared; a change made and undone in between, and code loaded another way, not seen | `run_record_check.code_since_run`, `repo.tree_patch`, `repo.blobs_then`, `repo.blobs_now` | `finalize`, `report-check` | guaranteed | before reporting |
| run → report (scopes) | declared scopes unchanged since the run | `promises.scope_drift` | `finalize`, `recheck` | guaranteed | before reporting |
| run → report (the registration) | at `low`: the registration the lane owes (`standard_contract.registration_fields`) stood in the protocol as committed at the first measurement — the commit its record names (`git_full`); first is what git's history puts first, the run id (local time) orders only runs at one commit, and on diverged history or beside a run git cannot place each first one is held; the protocol not committed there, a field not written there, a kind changed since, or a commit the clone does not hold, blocks (outside a repository: a warning); a field's value changed after that commit is not compared | `answering_run.first_measurements`, `runs.recorded_commit`, `repo.earliest_commits`, `protocol_history.registration_in_commit`, `report_check.registration_gaps` | `report-check` | guaranteed | before the number leaves the area |
| run → report (the registered report, as first measured) | at both repeat costs: the commit of each first measurement fixes `[protocol] report`, including no report. Removal, redirection and late registration are held; unchanged/restored values pass. The setter previews its proposed report field with the same gate, so `--force` can restore the original path but cannot bypass binding. First measurements with conflicting report values are held. An unreadable first commit holds while a report obligation is visible; low's registration station names the same failure without a duplicate. The first measurement requires the tree's report path committed on both lanes; high additionally retains freeze/preflight. Selection reaches a protocol by area or formerly registered report (`formerly_registering`). At stop/commit a current protocol-specific handover ends this obligation without a result; the delivered report still owes its review, and a later protocol change voids the handover. Outside Git, historical binding remains unchecked. | `report_hold.bound_reports`, `report_hold.report_binding_gap`, `report_hold.formerly_registering`, `start_check._committed_registration`, `protocol_fill.report_bound` | `report-check`; `claude-hook stop`, `.githooks/pre-commit`; `runlog`, `protocol-fill` | guaranteed within the stated Git boundary | starting the first run; before the number leaves the area |
| run → report (the registration as first measured) | every lane: the answering run recorded the promise block its protocol's first measurements recorded (ids, keys, sentences through the block digest, scopes, constants — not the code the scopes name); a change is held, every changed sentence, key, constant and scope named from the protocol texts both runs saw, with the way back (restore and measure again, or register anew); first measurements that recorded different blocks are held too — which one stood cannot be told — with the two ways out (a replacement declared against each, or the handover `ways_out.HANDOVER`) | `answering_run.first_registrations`, `protocol_history.as_measured`, `protocol_history.promise_differences` (`promises.snapshot_changes` where a text cannot be read back), `finalize.registration_changes` | `finalize`, and through it `report-check` | guaranteed | before the number leaves the area |
| run → report (what the number is about, as first measured) | every lane and every kind: the protocol the answering run saw holds the question, its terms, the data, the exclusions and the unit (`protocol_history.SCOPE_FIELDS`, whitespace folded, the generated data counts left out) and the head's kind, `[kept]` and `[reference]` as its first measurements saw them; a change is held, each field named with its old and new value, with the way back (restore and measure again, or register anew); the protocol as it stands is held the same way, so a field rewritten after the last measurement is held before any run carries it — unless it is a correction in place: an audit finding that names the field as its place (`<protocol file>:<label>`, the label whole; no line number, no part of a label), decided `fixed`, and a `resolved` on it bound to that decision in an analysis record that covers the area now (code, promises, registration, the fields read before the run, the run) — at every grade; a fresh audit without that verdict, a verdict on another field and a text edited after the verdict release nothing; the head's kind, `[kept]` and `[reference]` name no field and are never corrected so, nor is the question (`protocol_history.UNCORRECTABLE_FIELDS`: it states the requirement, a different question is a protocol of its own) — the hold offers the correction route only where it applies (`finalize.correction_way`), the decision's line explains the condition (`protocol_history.STANDS_AS_REGISTERED` for the question) and names no way of its own; the release names each correction with its old and new value and the verdict's why; a code change measured again under the same fields passes — what the run computes is the analysis audit's question | `answering_run.first_measurement_groups`, `protocol_history.as_measured`, `protocol_history.scope_differences`, `protocol_history.first_measured_differences`, `protocol_history.correctable`, `findings.corrected_field`, `finalize.scope_changes`, `finalize.resolved_corrections` | `finalize`, and through it `report-check` | guaranteed | before the number leaves the area |
| run → report (a declared replacement) | a protocol with `[replaces]`: one predecessor of the repo, no circle, `type = "exploratory"`, every difference of the registration — the kind, the promises, what the number is about as finalize compares it (`scope_differences`: the question, its terms, the data, the exclusions, the unit, `[kept]`, `[reference]`) and the Data profile — against the predecessor's (as each first measurement saw it: commit plus its `uncommitted.patch`, held to the recorded block; against each when they differ) declared as `[[replaces.change]]` and none declared that is not one, the predecessor's open BLOCKERs decided; the generated result opens with the predecessor's verdict (`no verdict` where its registration does not stand); a report that switched its citations to an undeclared successor is static evidence | `protocol_block.replaces`, `protocol_history.registrations_as_first_measured`, `protocol_history.registration_differences`, `report_replacement.replacement_gaps`, `result_render.predecessor_verdict`, `report_hold.replacement_hints` | `report-check` | guaranteed (the hint: static evidence) | before the number leaves the area |
| run → report (the end) | at every repeat cost: frozen (high repeat cost only — at low repeat cost no freeze and no preflight audit are owed), finalize clean with its blockers named, the answering run a full run (`run_kind="measurement"`, not acknowledged unfrozen — a probe's or an acknowledged run's number is refused), an analysis audit record of the code, the promise block, the registration it judged (`registration`: the kind and the fields the kind owes, `protocol_check.registration_stamp`), the answering run and what the audit was shown of it (`shown_sha`: its rows' excerpts and metrics.json, its declared dependencies, the protocol's declared run when that is another one, and the setup's prose the audit read, `protocol_check.audited_texts`; `audit_binding.run_shown`) as they are now, every finding decided, `02_analyze.py --check` passes (the note carries the numbers and the run_id; every skeleton stamps the script, the compute skeleton's since 0.100.0) | `report_check`, `runs.unreportable`, `audit_gaps.audit_coverage`, `recheck.holds` | `report-check` | guaranteed | before the number leaves the area |
| run → report (the declaration) | a protocol whose TOML head declares a result (`[result] run = "<run_id>"`, written by `protocol-fill --from-run`, never typed — the one declaration that a result is reported) goes through report-check at the stop and the commit, with every other protocol of an area a changed, deleted or staged path touches — a path in the area, a file its promises declare in scope, or a shared helper under `lib/`/`src/` its code imports (a script changed or removed under a reported number reopens it; at the commit the protocols are the index's); a protocol declaring none owes nothing (an exploration ends with no reported result); a `[result]` that does not read (a typed id, a stray key) is a blocker where it stands; an Recorded results written under no declaration is a warning | `report_check.if_reported`, `report_check.affected_protocols`, `scope_sha.areas_touched`, `protocol_block.declared_run`, `finalize.declared_run_gaps`, `protocol_check.recorded_results_without_run` | `claude-hook stop`, `.githooks/pre-commit` (`report-check --if-reported --staged`: the answer as the index holds it, the area's tree equal to the index), `protocol-check` | guaranteed (the warning: static evidence) | ending the turn, committing |
| run → report (a report outside the protocol) | a changed or staged Markdown file citing a run (not a protocol, not under `runs/` or `data/`, both tested at its own path): a report that is a symbolic link, wherever it points, blocks alone, naming the copy that replaces it (`report_hold.link_gap`; its other checks follow on the copy); every report result block names its protocol, shows the run that protocol declares now and equals what it renders (Recorded results and Limitation lines; `protocol-fill --into` writes it and replaces the protocol's block after a new run is adopted) — exact for the block, nothing for the prose beside it; every token that reads as a run id names a run of the repo; a cited run that a protocol declares as its result is shown in that protocol's block, else the block is owed; the answering run of a protocol that declares no result is not cited undiscussed — the promotion without the adoption (sixth round, t3 and t18) — and a run only looked at stands in a discussion block (`protocol-fill --discuss RUN --why … --into`: protocol, run and why as TOML in its head, its line written from them; a block without its why, with a line that differs from its head, repeated for one protocol and run, naming a run its protocol's area lacks, or discussing a declared run blocks; any other cited run no protocol declares: a warning); the protocol declaring a cited run goes through report-check as well; an untouched file's old citations reopen nothing; the report a protocol's head registers (`report = "REPORT.md"`, `protocol_block.report_field`), once delivered in the state, carries that protocol's result block of the declared run or its handover block as the record renders it (`handovers.block_mismatch`) — else one blocker with the three ways out (adopt then `--into`, `--discuss` which releases nothing, `--handover`); while nothing is adopted, a discussion block of the run the gates hold the protocol to is its progress account: the commit takes it without a report review, the stop holds it once naming the adoption or the handover (`report_hold.progress_account`, `progress_hold`), and `--into` puts the result block where it stood (`report_blocks.with_block`), run id removed, typed in or discussed alike; before any measurement and with no answering run or adoption, a valid report draft owes no result block; a report not yet written owes nothing, a protocol registering none holds no file to this, and the protocols registering a file among the paths are selected though it lies in no area | `report_check.if_reported`, `report_hold.hold_report`, `report_hold.undeclared_findings`, `report_hold.promotions`, `report_blocks.block_gaps`, `report_blocks.cited_gaps`, `report_blocks.blocks_owed`, `report_blocks.discussions`, `report_blocks.discussion_gaps`, `report_hold.discussion_sources`, `report_hold.report_owed`, `report_hold.registering_protocols`, `report_check.report_findings`, `report_check.hold_registered` | `claude-hook stop`, `.githooks/pre-commit` (the report as the index holds it), `report-check` (station 8) | guaranteed | ending the turn, committing, reporting |
| run → report (unsourced numbers) | numbers in a changed citing report outside every generated block are named with their line: no source is assigned to them — equal values elsewhere do not show where a number came from | `report_blocks.unsourced_numbers` | `claude-hook stop` (shown only beside a blocker), `.githooks/pre-commit`, `report-check --if-reported` | static evidence | ending the turn, committing |
| run → report (the adoption) | the one path that writes the declaration: the lines from the run's metrics.json are written, report-check runs on the written protocol, a blocker puts the file back — a result adopted this way has passed every check | `protocol_fill.adopt`, `report_check.report_check` | `protocol-fill --from-run` | guaranteed | writing the number back |
| run → report (undecided findings) | every finding still `open` in `audits/`, any mode: a BLOCKER blocks, a WARNING warns, each with its file | `finalize.check_open_audit_findings`, `findings.area_records` | `finalize` | guaranteed | after the run |
| run → report (a deleted run) | every analysis record of the area names a run it still holds: a record of a run whose directory is gone is a blocker where the record stands — the record is the evidence that the run existed | `audit_gaps.records_of_gone_runs`, `finalize.check_open_audit_findings` | `finalize` | guaranteed | after the run |
| run → report (the gates that run unasked: the stop sends back once, the commit holds) | an area the session touched, or a staged file lies in — an area deleted whole with its protocol is found by its journal copy on the branch —, holds an audit BLOCKER nobody decided: the stop sends the agent back (the records as the tree holds them), the commit is refused (the records and their decisions as the index holds them); a lost or unreadable record or journal holds both too, except where a current handover binds that loss (`handovers.acknowledgement`) — an open BLOCKER never; committed evidence changed against git — a record beyond its decision lines, another audit file, a closed run's files — or a file of labkit's that git ignores holds both as well, in the state checked against HEAD, at the stop also by a session commit or left behind in HEAD's reflog, and no handover acknowledges it: each line names its `git checkout` | `agent_hooks.undecided_blockers`, `attempts.area_integrity`, `findings.open_blockers`, `agent_hooks.committed_in_session`, `evidence.changes`, `evidence.ignored`, `agent_hooks.session_evidence`, `evidence.change_blockers` | `claude-hook stop`, `.githooks/pre-commit` (`claude-hook undecided`); the change against HEAD also `report-check AREA` and `labkit-next` | guaranteed | ending the turn, committing, before reporting |
| audit → evidence (the attempts) | every model call of `labkit-audit` is an attempt journaled in `audits/attempts.jsonl` — a preflight or analysis audit, a decision review (`review`), a report review (`report-review`, its record under `audits/report-reviews/`) — started before the call, the model's answer kept as `audits/answers/<attempt id>.txt` before anything reads it, ended with its record, its failed-attempt file or why none, and the kept answer (a kept answer releases nothing); a call not made (a state already judged, a refusal before it) is no attempt, and a record older than the journal is named by none; an attempt whose process holds no lock and has no end is marked interrupted by the next; a file an ended attempt names, a file under `audits/` HEAD holds, or a journal line HEAD holds that is gone blocks the next audit, the stop and the commit (at the commit as the index holds them, so a commit restoring a record HEAD lost passes; at the stop HEAD's journal is held to HEAD's files), naming the attempt or the file; in the tree a journal line its copy in the git directory keeps (one per branch, held as a set of lines) that the journal lacks blocks too, with the files its end names — `audits/` deleted whole before a first commit is noticed (not on a detached HEAD, in a fresh clone or with the git directory gone) — a current handover lets the stop and the commit pass on that loss, never the next audit or the adoption (`handovers.missing_paths` keeps its paths owed); a running attempt refuses a second; the check and the start stand under one lock | `attempts.begin`, `attempts.attempt`, `attempts.gaps`, `attempts.area_gaps`, `attempts.journal_copy`, `attempts.copy_gaps` | `labkit-audit`, `claude-hook stop`, `.githooks/pre-commit` (`claude-hook undecided`) | guaranteed | auditing, ending the turn, committing |
| run → report (denominator) | denominator `criterion_<i>_n` matches a recorded input count | `run_record_check.criterion_n_input_mismatches` | `finalize` | static evidence | after the run |
| report → number | output pinned to the run, recomputation agrees, note cites every number and the run id, block unchanged | `recheck.holds` | (an area's `--check`) | guaranteed | keeping a number |
| compute → kept number | a computation's head names its kept number (`[kept]`: key, unit — `protocol_block.kept`, owed by a computation and refused on a fit or an apply, `protocol_check.kept_gaps`; in the registration stamp); the compute skeleton reads the key (`metric_key`), and finalize blocks an answering run whose metrics.json does not hold it as a finite number, naming what it holds instead (`run_record_check.kept_number_gaps`) — the adoption's check runs finalize on the proposal; the Recorded results line names it first with its unit (`result_render.kept_phrase`). The key is bound by name, not by meaning | `protocol_block.kept`, `protocol_check.kept_gaps`, `run_record_check.kept_number_gaps`, `finalize.check_kept_number`, `result_render` | `labkit-init exp --kept --unit`, `protocol-fill kept.key=… kept.unit=…`, `finalize`, `labkit-adopt` | guaranteed | registering, before reporting |
| compute → reference comparison | a computation's head may register the stated value its number is compared with (`[reference]`: value, tolerance, relation, source, compared on the `[kept]` key — `protocol_block.reference`, refused on a kind with a bar naming the criterion, `protocol_check.reference_gap`; in the registration stamp); the run writes the verdict beside the number (`reference.reference_verdict`, one home: `compared` with `ref_met` and the distance, or `not comparable` — the key absent or no finite number; the compute skeleton's `metrics_of`), `--check` recomputes it, the Recorded results line and the result block carry it generated (`result_render.comparison_phrase`), and finalize blocks a verdict the run could not make, a `ref_*` key without a registered reference, and a reference changed after the run (`reference.comparison_gaps`); `not met` is a valid outcome, and without the table no `ref_*` key is written and nothing is owed | `protocol_block.reference`, `reference`, `result_render`, `finalize.check_reference` | `labkit-init exp --reference`, `02_analyze.py --check`, `protocol-fill --from-run`, `finalize` | guaranteed | registering, the run, before reporting |

## One home per question

| Question | Home |
|---|---|
| Is this an intent id / key? | `promises.ID_IN_PROTOCOL`, `promises.ID_KEY` |
| What does the promise block say? | `promises.parse_block`, `promises.load`, `promises.constants` |
| Which code does a promise rest on, and did it change? | `promises.declared_scope_sha`, `promises.scope_drift` |
| What does the protocol's head say (id, type, cost, frozen, audit)? | `protocol_block.head` |
| Which number does a computation report, and does its run hold it? | `protocol_block.kept` (the table, `kept_toml` its writer, `kept_key` the key), `protocol_check.kept_gaps` (owed or refused by kind), `run_record_check.kept_number_gaps` (the run holds it) |
| What stated value does a computation compare with, and did the run meet it? | `protocol_block.reference` (the table, `reference_toml` its writer), `reference.reference_verdict` (the verdict; `with_verdict`, `phrase`, `comparison_gaps` its readers) |
| How is a string written into TOML — a finding's or a review's field, a promise sentence, the head of a report's discussion block? | `protocol_block.toml_string` (one line that reads back through tomllib unchanged; a lone surrogate refused with its cause) |
| Which prompt does a protocol register, and does a sent prompt match it? | `protocol_check.registered_prompt_blocks` (every fence under Prompt but the stamp's unfilled one — `is_stamp_placeholder_block`, never a guess from a leading `<`), `protocol_check.unheld_prompt_lines` (the fixed-line comparison; `prompt_check.check_prompt_drift` reads the scripts' constants statically and warns on one it cannot compute, `lanes.Lanes.prompt_drift` reads the prompts as a run sends them) |
| What does a protocol's field say, as every stamp and comparison reads it? | `protocol_check.field_values` (by `field_name` — case, a gloss and † aside — whitespace folded; a field written twice is all its copies, never one of them): `registration_stamp`, `audited_texts`, `protocol_history.scope_differences` and `registration_differences` read it; `protocol_check.repeated_fields` names a bound field (`BOUND_FIELDS`) written twice, told by `repeated_findings` and refused with `REPEATED_WAY_OUT` by protocol-check, preflight, report-check, finalize, the start check, the run hook and `labkit-next` (`FieldReport.repeated`), and at low repeat cost in the committed registration (`protocol_history.registration_missing`) |
| Which prose fields does a protocol owe, and which are filled? | `protocol_check.FIELDS`, `protocol_check.owed_fields` (by repeat cost, kind and model — `owed`, the result check, the rendered example `example_owed` and `protocol-check PROTOCOL --contract` read it), `protocol_check.check_fields` |
| What does a repeat cost owe — the freeze or the registration, which audits, which cut, the foreground, the provenance check? What does a reported number owe at its release? Which skeleton does an area get, and what is its check? | `standard_contract.lane` (the release reads its `freeze` and `audits`; `report_check`), `standard_contract.skeleton` and `standard_contract.registration_fields` (both by the head's `kind`: what the kept number asserts — a computation has no bar, a fit or an apply registers one; `standard_contract.has_bar`), `standard_contract.CHECK_SCRIPT` — every consumer reads the field it needs; a `repeat_cost == "low"` or a `kind == "compute"` outside the contract is a copy |
| Which protocols does an area hold? Which does the repo? | `repo.area_protocols`; `repo.repo_protocols` (outside `repo.SKIP_DIRS`); `repo.PROTOCOL_GLOB`, `repo.PROTOCOL_NAME` are the name; a protocol is a regular file in the tree and in the index — a symbolic link, valid or broken, is refused with `repo.protocol_link` (`repo.protocol_links` finds them per state; the protocol choice, report-check, protocol-check and the handover ask it) |
| Which area does a bare name name? | `repo.areas_named` (the directory called so and every `NN-<name>` by `repo.AREA_NAME`, `repo.split_area_name`; never a glob); `repo.area_path` for a command's argument, `scaffold.existing_area` for the area `labkit-init exp` promotes or restamps — both refuse a name several areas carry, naming each |
| Which number does a new area get? Does one number name two areas? | `scaffold.next_experiment_number` (one above every number this tree, `_archiv/`, every branch and every other worktree hold — `scaffold.areas_elsewhere` over `repo.branch_refs` and `repo.worktree_roots`), `scaffold.shared_numbers`; `labkit-init numbers --staged` in the pre-commit and the pre-merge-commit |
| Which areas do changed or staged paths touch? | `scope_sha.areas_touched` (the nearest area above each path — `repo.areas_of` — and every area whose promises declare a changed path or whose code imports a changed shared helper; the stop's reported numbers and the commit's undecided findings read the same answer) |
| Where is the repo? Where is the lab? | `repo.git_root` (git), `repo.layout_root` (git, else stamped tree); `repo.lab_root` (the nearest `models.toml`) |
| Run git | `repo.git` (output, loud on failure), `repo.git_run` (exit code is the answer) |
| Print a `labkit-audit` step a person or agent runs next | `repo.audit_command` (quoted, `--protocol` where the area holds several); a check that does not know the working directory names `labkit-audit <area>` and report-check fills it (`gate.Findings(audit=…)`) |
| Ask git about the repository — HEAD, a dirty tree, a path in the git directory, the files a state holds under a folder | `repo.head_sha` (short form, "" outside a repo or unborn), `repo.tree_dirty` (untracked counted or not), `repo.git_dir_path` (this worktree's or the common git dir: locks, stop base, session log), `repo.local_dir` (labkit's local state about a path: in the git dir, else the temp dir — the audit locks, the detached starts), `repo.files_at` (the index's or a revision's files, None where there is no such state — by exit code, not git's words), `repo.branch_refs` (every local and remote-tracking branch), `repo.worktree_roots` (every worktree's directory), `repo.head_before` (the commit HEAD's line stood on before a time, by commit dates) |
| Which directories does an area's `runs/` hold, and what does each say? | `runs.run_dirs` (one walk, metadata read once; an unreadable run is data — the caller refuses, reports or skips) |
| Which runs does an area's run index list, and does the index read? | `runlog.indexed_runs` (by protocol id, deleted runs included); `runlog._read_index` is the one check every reader and writer of `runs.tsv` shares — the current columns (`header_refusal`), every row whole — and raises `RunIndexError`, a refusal naming the line: a short row is never read as no measurement |
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
| Is an output lock's writer still writing? Is a detached start running? | `files.lock_held` (the kernel's `flock`, never a pid: `batch.lock_holder_words`, `detached.starts`) |
| Is a run still open? Is the area busy? | `runlog.still_open` (`open_runs`; the twin refusal reads the open runs of the same script), `runlog.busy` (the open runs and the detached starts no open run names: `labkit-next`, `runlog --wait`, `runlog AREA`) |
| Which protocol does a new run bind to? | `start_check.protocol_binding` |
| What refuses a run before its directory exists, in which order? | `runlog.Run.__init__` (the registration, the detach gate where required and not already detached, the index header, data leakage, then for a full run `start_check.freeze_gate`: undecided blockers, the freeze or the registration, the acknowledgement over a failed audit); `start_check.prepare` refuses what cannot be read before any check |
| Which run answers for a protocol? | `answering_run.bound_answering_run` (the choice; `intent_check.choose_explicit` takes a named run; `recheck.chosen_run` is the same choice behind `--check` and `--from-run`) |
| Is this run a repeat draw, of which, and is it comparable? | `RunConfig.repeat_of`, `answering_run.repeats_of`, `answering_run.repeat_mismatch` (a fit's repeat with `reseed`: its seed held to `answering_run.repeat_seed` of the parent and the draw, the one key a repeat may change; `answering_run.repeat_seed_problem` where draws are read; its own output file `runlog.Run.draw_output`) — a repeat never answers (`bound_runs` leaves it out, `completed_runs(with_repeats=…)` makes every caller decide) |
| Which run recorded the model that answered these rows? | `answering_run.model_provenance_run` (walks `derived_from`; a derived run records none) |
| Is a run's `derived_from` chain whole? | `answering_run.lineage` (every config readable, every parent present, no loop — the whole chain; model provenance, params and row provenance read it) |
| Which protocol does a command hold an area to? | `repo.choose_protocol` (the named one — a path, or a bare file name inside the area, `repo.given_or_in` — else the only one; never a guess) |
| What does one check hold — which protocol text, which file state, which answering run? | `report_context.checked` (`Checked`: built once, read by every station; the state is named — the working tree at the stop, the index at the commit, the written proposal at the adoption; the run is `answering_run.bound_answering_run`'s choice through `audit_binding.audited_run`) |
| How does a registered constant stand against the record? | `promises.constant_records` (equal / different / missing, type-strict); runlog refuses before mkdir, intent-check/finalize block, `labkit-params` shows all three |
| Does a frozen protocol owe a promise block? | `promises.promise_tables_owed` — protocol-check (MUST), preflight and finalize (blocker), runlog (refusal before mkdir) |
| Which state of the area does an audit record bind, and does a record bind the state now? | `findings.AuditedState` (`audit_prompt.bound_prompt` binds it, `Record.state` carries it, `covering_records` compares the two) |
| Which analysis records cover the area now — code, promises, the answering run and what the audit was shown of it? | `audit_binding.covering_analysis` (`analysis_now` the state, `run_shown` the snapshot; report-check's analysis stage and its Limitation lines, `protocol-fill --from-run`) |
| What does the result section say when it says what its sources say — and does it? | `result_render.rendering` (the Recorded results line from the declared run's metrics.json with its note, one Limitation line per decided limitation of the covering records), `result_render.render_gaps` (exact equality, each difference named; report-check's analysis stage, `protocol-fill --from-run` and `--render` write it) |
| Does a report outside the protocol show a reported number as its sources render it? | `report_blocks.blocks`, `report_blocks.block_body`, `report_blocks.block_gaps` (a report result block shows the run its protocol declares now and equals that protocol's Recorded results and full Limitation lines; `protocol-fill --into` writes it), `report_blocks.cited_gaps` (every token that reads as a run id names a run of the repo), `report_blocks.unsourced_numbers` (numbers outside every block — a hint); `report_check.if_reported` holds changed citing reports, the protocols their blocks name and the protocols declaring the runs they cite, and the committed reports citing a run a protocol among the paths newly declares against HEAD (`report_hold.newly_declared`, `report_hold.committed_reports` — the two-step commit of the sixth round, t5) |
| Which file owes a protocol its result, and what releases it? | the head's `report` (`protocol_block.Head.report`, read by `protocol_block.report_field`: repo-relative, inside the repository, not a protocol, Markdown; stamped by `labkit-init exp --report-file`); `report_hold.report_owed` holds the delivered file to the result block of the declared run or the handover block as its record renders it (`handovers.block_mismatch`), and names the three ways out; `report_hold.registering_protocols` finds the protocols a change of that file reaches (pressure pilot 2026-10-29: the run id deleted, the commit passed) |
| Does a review uphold a decision as it stands now, under the claim the protocol makes now? | `reviews.upholding` (a review of that record, its code and its run as shown, of the claim's digest `reviews.claim_digest` over `protocol_check.reported_claim`, holding the decision's digest `findings.decision_digest`, every such draw saying `upheld`), `reviews.contested` (another draw settles nothing), `reviews.once_not_upheld` (was a decision on this finding ever not upheld — then closing it owes a review too), `reviews.state` for the gate's sentence |
| What does a file say at a git state — the index, HEAD? | `repo.text_at` (the index's or a revision's content, None where that state does not hold the file); `repo.state_text` for "the tree or the index" as a gate reads it — both name the file when its bytes are not UTF-8; `repo.indexed_files` for what the next commit carries; `repo.under_root` for whether a given path is the repo's at all |
| What carries a gate finding's sentence — a mechanical check or an indication? | `gate.GateFinding.evidence_kind` (`GUARANTEED` / `STATIC_EVIDENCE`, given at every site, never defaulted; static evidence never blocks, the dotted line names it, the summary counts it; `labkit-params` shows the same constants in its evidence column; the agent audit is the records' kind, `findings.Finding`) |
| Which audit findings are still undecided, and what does each gate make of one? | `findings.open_findings` (every mode, or one; the table of the gates' rules stands in its docstring: preflight warns unfrozen and blocks frozen, runlog refuses on a preflight BLOCKER and tells the rest only on an acknowledged start, finalize every record by grade, the hooks, the handover and `labkit-audit --findings` hold BLOCKERs only (`findings.open_blockers`); the one record the head names is a gap on any open grade, `audit_gaps.audit_record_gap` — the differences are intended) |
| Which code did an audit see, and is it still that code? | `scope_sha.area_snapshot` (the bytes read once and the sha over them; `area_stamp` its sha); the record carries its `scope_sha`, and `audit_gaps.audit_coverage` holds it to the stamp now (area stamp, not per promise) |
| Which package does a requirements line name, and how is labkit pinned? | `repo.requirement_name`, `repo.requirement_lines`, the four `*_REQUIREMENT` grammars (stamp pin line, `labkit-check`, lock parser, probe) |
| What is a run id, when did the run start? | `runs.RUN_ID`, `runs.RUN_ID_TIME`, `runs.run_started`; `runs.COMPLETED` is the one state word every consumer compares to |
| How is a path shown in a report line, a bundle or a refusal? | `repo.shown(path, base)` — relative to the base when below it, else absolute, both resolved; a record's path is `runs.recorded_path`, a stamp's hashed key `scope_sha._key` |
| How does a record state a time? | `runs.now_stamp()` in `runs.RECORD_TIME` (`2026-10-13T14:00:57`, local) — a run's `started`/`finished`, a lock's or lease's holder, a staged probe, a session's stop |
| How does a gate tell what it found, and exit? | `gate.Findings` (`block`, `warn`, `take` for a `GateFinding` built where it was found — `gate.blocker` for a pure check's, `gate.coded` for a code check's, grade, where, rule and fix as fields; `note` for a line counted as nothing, `report`; `Findings(tell=None)` collects the same findings without a console — report-check reads finalize's so, fixes included) — preflight, finalize, report-check, code-check, notes-check |
| Does a hold withdraw a declared result first? | `gate.GateFinding.changed_since`, set by the comparison that found a difference — `run_record_check.code_since_run` (the script or a helper of the run or of a run it derives from) and `finalize.check_declared_scopes` (a declared scope) — never where the code could not be compared; `report_check.held_declaration` reads it and `chain_gaps` puts the withdrawal before every later hold — never read off a finding's words |
| What does a repair decided `fixed` owe next? | `labkit-next` (`next_step.next_step`), the one answer; the line under the decision (`audit_decisions.repair_hint`) explains what `fixed` means for the kind of repair the finding names — a correction of a field in place and its release condition, the question that stands as registered, a repaired Conclusion and its decision review, a repair of code, inputs or configuration — reads no area state, and points to `labkit-next`; it names no action, so it cannot contradict the gates |
| What is the way out of a BLOCKER? | `gate.GateFinding.fix` — required for a BLOCKER (refused without one, every building site held by `tests/test_ways_out_data.py`), told in every form (`<what is refused>. Next: <fix>`, `gate.with_way_out`; a dotted line's last part `Next: <fix>`) and repeated in the summary; every literal way out names its command — a backticked span or a command builder; after a repair by hand, the check run again (`repo.gate_command`) — held by `tests/test_ways_out_data.py`; built where the cause is known, from the shared command builders (`repo.audit_command`, `repo.decide_command`, `repo.measure_command`, `repo.measure_anew`, `repo.gate_command`, `repo.adopt_command`, `findings.decide_way`, `findings.record_way`, `ways_out.register_anew`, `ways_out.HANDOVER`, `ways_out.ANSWER_AGAIN`); the refusals outside the findings carry one the same way — `AuditError` and `AttemptError` take `fix` as a required keyword, runlog's start refusals are `SystemExit(with_way_out(…))`, exemptions listed with their reason in `tests/test_ways_out_data.py`; the ways out by cause, for a person deciding an audit BLOCKER: `ways_out.WAYS_OUT` |
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
    code.json                   the code it imported, per git repository; code/ holds patches and copies
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
| `finalize` | after the run, before the number is written back | the answering run, its registration as the first measurement recorded it, intent-check, the run's code and the declared scopes, open fields, provenance (low), the tests, the registered outputs as the run recorded them, criterion n, the null lane, undecided findings of any mode by grade | no test file: a note; a failing test: a blocker | `report-check` runs it as one station |
| `labkit-audit --mode analysis` | after the run, at every repeat cost | the agent audit of the answering run; every finding decided, a BLOCKER limitation with its effect | — | — |
| `labkit-audit --review` | when a BLOCKER was decided `limitation` with `stands`, and when a finding a review did not uphold was closed instead | a second auditor on the decision | — | — |
| `labkit-audit --report-review` | when a report discusses a run, and on the registered report once its result or handover block stands | a cold reader on the report against the adopted, discussed and cited runs' metrics and the audits; writes `audits/report-reviews/<minute>-review.toml` | — | named by `claude-hook post-change`, owed by `report-check` (blocker until a review of the state names no claim); started by the agent |
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
| `audits/<minute>-<mode>-failed.toml` | `failed_attempts.write_failed` | the attempt an acknowledged run rests on |
| `audits/<minute>-review(-N).toml` | `reviews.write_review` | a second auditor's reading of a decision |
| `audits/report-reviews/<minute>-review.toml` | `report_reviews.write_report_review` | a cold reader's reading of a report (one that discusses a run, or the registered one) |
| `audits/attempts.jsonl`, `audits/answers/<attempt id>.txt` | `attempts.begin` (`Running.keep_answer`, the journal lines) | every model call of `labkit-audit`, its kept answer and how it ended |
| `<git common dir>/labkit-attempts/<branch>/<area>.jsonl` | `attempts._append`, beside every journal line (`attempts.journal_copy`) | the journal's copy outside the working tree, never committed |
| `<git common dir>/labkit-attempts/<branch>/<area>/<path under audits/>` | `attempts.Running.end`, before the end line that names them (`attempts.evidence_copy`) | the record or failed attempt and the kept answer each attempt ended with, as written — the restore of a file deleted before it was staged, never a check of a record's content (`--decide` rewrites the record, not its copy) |
| `audits/handovers/handover-<hex>.json` | `handovers.write_record` | a protocol's end without a result: the audit files by blob id, losses, findings left unsettled, and the run it stands at with what kept that run from adoption (`handovers.RunAccount`, computed by `report_check.adoption_state`: not measured, unusable, held, adoptable); the report's handover block is its projection, without run ids; a measurement after it ends its acknowledgement |
| `runs/<id>/*.json`, `runs.tsv` | `runlog`, `runs.write_failure` | the run: config, outputs, metrics, completion or failure |
| `.git/labkit-sessions.jsonl` | `agent_hooks.record_session` | which runs a session started (no verdict) |

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
| git pre-merge-commit | Runs the pre-commit on the merge's index. git runs it, not pre-commit, for a merge it completes without conflicts; such a merge can still bring a number reported on one branch and its analysis changed on the other together, or two areas of one number. A held merge stays uncommitted until it is fixed and committed (through pre-commit) or aborted. |
| Claude/Codex `pre-run` | Runs preflight for recognized measurement commands; blocks a frozen area's command on blockers. |
| Claude/Codex `post-change` | Reports protocol and note checks after changes, and names `labkit-audit --report-review` for a changed report that discusses a run (a report that is a symbolic link: the refusal the stop and the commit give it, with its way out); for an area whose `audits/` or `runs/` git status names, tells what the stop and the commit will hold of its evidence — gone, rewritten beyond its decisions, a closed run changed — with each line's restore, holding nothing itself (`agent_hooks.evidence_areas`); tracks content and evidence state per session to avoid repeating what was told. |
| Claude/Codex `stop` | Sends the session back for a failed release check or an unresolved audit blocker in an affected area — changed in the tree or committed since the session's stop base (kept by `pre-run` before the first command, moved only past a clean stop on a working tree equal to HEAD; without one, said, the commits dated since the transcript began; with no transcript start either, it holds) — once per turn, and for checks that outrun the stop's budget (`agent_hooks.STOP_BUDGET_S`, under the hook's timeout); the next turn's stop holds again. |

`labkit-hooks install` installs the pinned package's git, Claude and Codex hooks;
`preflight` checks their installation. The run writer and git hooks work
without an agent harness. Codex hooks need project trust and review via
`/hooks`; installation checks inspect files, not runtime trust.
[Codex hooks](codex-hooks.md) defines the adapter and its limits.
Live hook configuration is generated by
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
