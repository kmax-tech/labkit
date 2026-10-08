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
| 1 · formats and places | `protocol_block`, `promises`, `protocol_check`, `runs`, `repo`, `scope_sha` | read-only answers: the protocol's TOML block and its head, the promise alphabet and tables, the protocol's prose fields by label, what a run directory says about itself, where the repo, the area's protocols and git are |
| 2 · a run and its effects | `runlog`, `batch`, `llm`, `endpoint_lease` | writing a run (binding, refusals, provenance, index), resumable output, model calls, the model-slot lease |
| 3 · checks | `intent_check`, `code_check`, `recheck`, `notes_check` | one question each, against code, metrics or a note |
| 4 · gates | `preflight`, `finalize`, `claude_hooks`, `audit`, `install_hooks` | sequence the checks at a decision point; the hooks call the gates; `audit` runs the agent audit through `llm`; `install_hooks` installs the git hooks the gates run in (preflight checks they are there) |
| tools | `protocol_fill`, `usability`, `agent_transcript`, `cold_reader`, `protocol_reading`, `code_navigation` | fill a protocol field; stage and score a cold-agent probe; read what an agent did from its session transcript; what every cold-reader probe shares; how a person reads a protocol; how a newcomer finds their way in code |

`runlog` (layer 2) reads layer 1 and calls `llm` only to record resolved
models; `endpoint_lease` asks `runs.is_alive`, not the writer.

## The chain

labkit's claim — *it detects violations of explicitly encoded scientific
intent across implementation, execution and reporting* — runs along five
links. Each check names its tier: **guaranteed** (exact), **static
evidence** (warns), **agent audit** (semantic).

| Link | Checked | Where | Command | Tier | When |
|---|---|---|---|---|---|
| intent → promise | head parses and is typed; required fields by exact label; promise tables parse; prose and block name the same ids | `protocol_block.head`, `protocol_check.check_fields`, `promises.parse_block`, `promises.prose_mismatch` | `protocol-check`, `intent-check` | guaranteed | writing the protocol |
| promise → code | every declared key appears exactly in the code; every declared scope resolves | `code_check.promise_block_findings` | `code-check`, `preflight` | guaranteed | before the run |
| promise → code | each intent id appears as a key; gate labels match the prompt; parser fixtures exist | `code_check` | `code-check`, `preflight` | guaranteed | before the run |
| promise → code | code does what the promise says | `audit` (experiment-preflight instructions + the area's files + the standard, one `llm` call); or the bundle (`code-check --bundle`) for the code-check agent | `labkit-audit --mode preflight` | agent audit | before the run |
| run → report | the evaluation means the frozen criterion | `audit` in MODE analysis | `labkit-audit --mode analysis` | agent audit | before a number leaves |
| code → run | unfrozen full run, unbound run, dangling scope, control leakage: refused before the run dir exists | `runlog.Run` | (every run) | guaranteed | starting the run |
| code → run | a full run's audit line names the stamp the code has now (`scope sha`), else refused | `runlog.Run`, `scope_sha.audit_stamp_drift` | (every full run) | guaranteed | starting the run |
| code → run | block digest, per-promise `declared_scope_sha`, constants, git state, data hashes recorded | `runlog.Run`, `promises.snapshot` | (every run) | guaranteed | starting the run |
| run → report | run completed; declared keys reported; run recorded this block; a block constant not contradicted by the run config | `runs.completion_state`, `intent_check.check_block_against_run` | `intent-check`, `finalize` | guaranteed | after the run |
| run → report | declared scopes unchanged since the run | `promises.scope_drift` | `finalize`, `recheck` | guaranteed | before reporting |
| run → report | denominator `c<i>_n` matches a recorded input count | `finalize.criterion_n_input_mismatches` | `finalize` | static evidence | after the run |
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
| Is the recording process alive? | `runs.is_alive` |
| Which protocol does a new run bind to? | `runlog._protocol_binding` |
| Which run answers for a protocol? | `runs.bound_answering_run` (the choice; `intent_check.choose_explicit` takes a named run) |
| Which run recorded the model that answered these rows? | `runs.model_provenance_run` (walks `derived_from`; a derived run records none) |
| Which code did an audit see, and is it still that code? | `scope_sha.area_stamp`, `scope_sha.audit_stamp_drift` (area stamp, not per promise) |

A second answer to any of these questions is drift: move the caller to the
home, never copy the logic.
