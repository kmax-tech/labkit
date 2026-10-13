# Architecture

Where what happens in labkit: the layers, the chain from promise to
reported number, and the one home of each recurring question. Terms are
coined in the README; the promise block in `docs/promise-block.md`.

## Layers

Imports point downward only; no module imports a layer above it, and no
layer imports a tool; tools may import any layer. Every module stands in
the table exactly once. `tests/test_architecture.py` reads this table and
holds the imports to it — a new module or an upward import fails the suite.

| Layer | Modules | Holds |
|---|---|---|
| 1 · formats and places | `protocol_block`, `promises`, `protocol_check`, `runs`, `repo`, `scope_sha`, `rules`, `findings`, `console` | read-only answers: the protocol's TOML block and its head, the promise alphabet and tables, the protocol's prose fields by label, what a run directory says about itself, where the repo, the area's protocols and git are, the standard's rules and every reference to them, an audit's findings as data (`audits/*.toml`: written by `labkit-audit`, decided by the person, read by `preflight`); the one exit of every console command (`console.exit_with`: a reader closing the pipe is exit 0, not a traceback) |
| 2 · a run and its effects | `runlog`, `batch`, `llm`, `endpoint_lease` | writing a run (binding, refusals, provenance, index), resumable output, model calls, the model-slot lease |
| 3 · checks | `intent_check`, `code_check`, `recheck`, `notes_check` | one question each, against code, metrics or a note |
| 4 · gates | `preflight`, `finalize`, `claude_hooks`, `audit`, `install_hooks` | sequence the checks at a decision point; the hooks call the gates; `audit` runs the agent audit through `llm`; `install_hooks` installs the git hooks the gates run in (preflight checks they are there) |
| tools | `protocol_fill`, `scaffold`, `repo_check`, `usability`, `agent_transcript`, `cold_reader`, `protocol_reading`, `code_navigation`, `params`, `calltree` | fill a protocol field; stamp a lab repo and its areas from the shipped templates; say whether a lab repo is on its pin and the pin is current (`labkit-check`); stage and score a cold-agent probe; read what an agent did from its session transcript; what every cold-reader probe shares; how a person reads a protocol; how a newcomer finds their way in code; what one run of a command actually called |

`runlog` (layer 2) reads layer 1 and calls `llm` only to record resolved
models; `endpoint_lease` asks `runs.is_alive`, not the writer.

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
| promise → code (ids, labels) | each intent id appears as a key; gate labels match the prompt; parser fixtures exist | `code_check` | `code-check`, `preflight` | guaranteed | before the run |
| promise → code (meaning) | code does what the promise says | `audit` (experiment-preflight instructions + the area's files + the standard, one `llm` call); or the bundle (`code-check --bundle`) for the code-check agent | `labkit-audit --mode preflight` | agent audit | before the run |
| run → report (meaning) | the evaluation means the frozen criterion | `audit` in MODE analysis | `labkit-audit --mode analysis` | agent audit | after the run |
| promise → reader | a person who did not build the area can tell what it decides | `audit` in MODE clarity (code-clarity area rules + README, protocol, measure script) | `labkit-audit --mode clarity` | agent audit (static evidence: never a gate) | before freezing |
| code → run | unfrozen full run, unbound run, dangling scope, control leakage: refused before the run dir exists | `runlog.Run` | (every run) | guaranteed | starting the run |
| code → run | a full run's audit line names the stamp the code has now (`scope sha`), else refused | `runlog.Run`, `scope_sha.audit_stamp_drift` | (every full run) | guaranteed | starting the run |
| code → run | block digest, per-promise `declared_scope_sha`, constants, git state, data hashes recorded | `runlog.Run`, `promises.snapshot` | (every run) | guaranteed | starting the run |
| run → report (record) | run completed; declared keys reported; run recorded this block; a block constant not contradicted by the run config | `runs.completion_state`, `intent_check.check_block_against_run` | `intent-check`, `finalize` | guaranteed | after the run |
| run → report (scopes) | declared scopes unchanged since the run | `promises.scope_drift` | `finalize`, `recheck` | guaranteed | before reporting |
| run → report (denominator) | denominator `c<i>_n` matches a recorded input count | `finalize.criterion_n_input_mismatches` | `finalize` | static evidence | after the run |
| report → number | output pinned to the run, recomputation agrees, note cites every number and the run id, block unchanged | `recheck.holds` | (an area's `--check`) | guaranteed | keeping a number |

## One home per question

| Question | Home |
|---|---|
| Is this an intent id / key? | `promises.ID_IN_PROTOCOL`, `promises.ID_KEY` |
| What does the promise block say? | `promises.parse_block`, `promises.load`, `promises.constants` |
| Which code does a promise rest on, and did it change? | `promises.declared_scope_sha`, `promises.scope_drift` |
| What does the protocol's head say (id, type, cost, frozen, audit)? | `protocol_block.head` |
| Which prose fields does a protocol owe, and which are filled? | `protocol_check.FIELDS`, `protocol_check.check_fields` |
| Which protocols does an area hold? | `repo.area_protocols` |
| Where is the repo? | `repo.git_root` (git), `repo.layout_root` (git, else stamped tree) |
| Run git | `repo.git` (output, loud on failure), `repo.git_run` (exit code is the answer) |
| Is this run finished? Which runs are? | `runs.completion_state`, `runs.completed_runs` |
| What does a run's metadata say? | `runs.read_run_config` |
| Does an output file account for its input, item by item? | `batch.Store.ledger` (missing, duplicate, stray, stale per expected field); `require_complete()` inside the run keeps it from completing |
| Which runs wrote a JSONL file's rows? | `batch.row_runs` (per-row `_prov.run`); runlog names the runs a resumed file continues, finalize holds every row to the run |
| Is the recording process alive? | `runs.is_alive` |
| Which protocol does a new run bind to? | `runlog._protocol_binding` |
| Which run answers for a protocol? | `runs.bound_answering_run` (the choice; `intent_check.choose_explicit` takes a named run) |
| Which run recorded the model that answered these rows? | `runs.model_provenance_run` (walks `derived_from`; a derived run records none) |
| Which protocol does a command hold an area to? | `repo.choose_protocol` (the named one, else the only one; never a guess) |
| How does a registered constant stand against the record? | `promises.constant_records` (equal / different / missing, type-strict); runlog refuses before mkdir, intent-check/finalize block, `labkit-params` shows all three |
| Does a frozen protocol owe a promise block? | `promises.promise_tables_owed` — protocol-check (MUST), preflight and finalize (blocker), runlog (refusal before mkdir) |
| Which code did an audit see, and is it still that code? | `scope_sha.area_stamp`, `scope_sha.audit_stamp_drift` (area stamp, not per promise) |
| Which rules exist, what do they say, and does a reference name one? | `rules.load_registry`, `rules.rule_heads`, `rules.check_registry`, `rules.check_ledger`, `rules.check_refs`, `rules.rule_text` (`docs/standard.md`, `docs/rules.tsv`) |

A second answer to any of these questions is drift: move the caller to the
home, never copy the logic.

## Where what lives

labkit is one of four places that hold the lab's rules, tools and copies.
The split grew by history, not by a principle; this table states it as it
is, so a reader can find a file before it moves. The rule for every move:
**what a lab outside this house needs to work with labkit lives in labkit;
what concerns only this house stays in the author's dotfiles.**

| Place | Holds | Master or copy |
|---|---|---|
| labkit (this repo) | the code and its gates; the lab standard (`labkit/docs/standard.md`, English) and its ledger (`labkit/docs/rules.tsv`: id → name → status, every `LAB` number); the protocol template and its field guide (`labkit/experiment-protocol.md.template`, `labkit/protocol-field-guide.md`); `labkit-init` and the templates it stamps (`labkit/templates/`: script skeletons, area tests, `AGENTS.md`, `models.toml`, editor settings); the audit agents' instructions (`labkit/*.agent.md`) | master |
| labkit (this repo) | `docs/coding-style.md` | copy, stamped with the master's hash; edit the master, then `lib sync pull` (the house scaffolder's command, not a labkit one) |
| author's dotfiles (`~/.claude/resources/`) | the house standard (`arbeitsstandard.md.template`, German — cut down to the house chapters, `TODO.md` item 5), the dated evidence behind every rule (`arbeitsstandard.evidence.md`), the house ledger (`rule-registry.tsv`: `LOCAL` and `CODE` ids, `LAB` rows marked `moved:labkit`), the coding style, the house scaffolder (`tools/local-init.py`: house files, the thread in `~/work`, sync; its lab part hands over to `labkit-init`), the note seeds, the thesis starter | master |
| a lab repo | labkit as a pinned package, which brings the standard; `docs/coding-style.md`, `CLAUDE.md`, the scripts stamped from the templates (a repo pinned below 0.77 still carries its `docs/arbeitsstandard.md` copy) | copies, stamped by the scaffolder |
| author's global `~/.claude/CLAUDE.md` | one-line reflexes that point at rule ids | master (house only) |

**What is still in the dotfiles.** The thesis starter, which carries house
material (lecture links, run snapshots with the author's paths); whether it
is cleaned for labkit or stays house is open (`TODO.md` item 5). Gate
messages and docstrings cite rules by id and English name, and
`tests/test_rules.py` holds every such reference to the ledger.
