# Architecture

Where what happens in labkit: the layers, the chain from promise to
reported number, and the one home of each recurring question. Terms are
coined in the README; the promise block in `docs/promise-block.md`.

## Layers

Imports point downward only; no module imports a layer above it, and there
is no cycle (checked 2026-10-06).

| Layer | Modules | Holds |
|---|---|---|
| 1 · formats and places | `promises`, `protocol_check`, `runs`, `repo` | read-only answers: the promise alphabet and block, the protocol's fields and identity, what a run directory says about itself, where the repo, the area's protocols and git are |
| 2 · a run and its effects | `runlog`, `batch`, `llm`, `endpoint_lease` | writing a run (binding, refusals, provenance, index), resumable output, model calls, the model-slot lease |
| 3 · checks | `intent_check`, `code_check`, `scope_sha`, `recheck`, `notes_check` | one question each, against code, metrics or a note |
| 4 · gates | `preflight`, `finalize`, `claude_hooks` | sequence the checks at a decision point; the hooks call the gates |
| tools | `protocol_fill`, `usability` | fill a protocol field; stage and score a cold-agent probe |

`runlog` (layer 2) reads layer 1 and calls `llm` only to record resolved
models; `endpoint_lease` asks `runs.is_alive`, not the writer.

## The chain

labkit's claim — *it detects violations of explicitly encoded scientific
intent across implementation, execution and reporting* — runs along five
links. Each check names its tier: **guaranteed** (exact), **static
evidence** (warns), **agent audit** (semantic).

| Link | Checked | Where | Command | Tier | When |
|---|---|---|---|---|---|
| intent → promise | required protocol fields; promise block parses; prose and block name the same ids | `protocol_check`, `promises.parse_block`, `promises.prose_mismatch` | `protocol-check`, `intent-check` | guaranteed | writing the protocol |
| promise → code | every declared key appears exactly in the code; every declared scope resolves | `code_check.promise_block_findings` | `code-check`, `preflight` | guaranteed | before the run |
| promise → code | each intent id appears as a key; gate labels match the prompt; parser fixtures exist | `code_check` | `code-check`, `preflight` | guaranteed | before the run |
| promise → code | code does what the promise says | audit bundle (`code-check --bundle`) for an agent | `code-check --bundle` | agent audit | before the run |
| code → run | unfrozen full run, unbound run, dangling scope, control leakage: refused before the run dir exists | `runlog.Run` | (every run) | guaranteed | starting the run |
| code → run | block digest, per-promise `declared_scope_sha`, constants, git state, data hashes recorded | `runlog.Run`, `promises.snapshot` | (every run) | guaranteed | starting the run |
| run → report | run completed; declared keys reported; run recorded this block; a block constant not contradicted by the run config | `runs.completion_state`, `intent_check.check_block_against_run` | `intent-check`, `finalize` | guaranteed | after the run |
| run → report | declared scopes unchanged since the run | `promises.scope_drift` | `finalize`, `recheck` | guaranteed | before reporting |
| run → report | denominator `c<i>_n` matches a recorded input count | `finalize.criterion_n_findings` | `finalize` | static evidence | after the run |
| report → number | output pinned to the run, recomputation agrees, note cites every number and the run id, block unchanged | `recheck.holds` | (an area's `--check`) | guaranteed | keeping a number |

## One home per question

| Question | Home |
|---|---|
| Is this an intent id / key? | `promises.ID_IN_PROTOCOL`, `promises.ID_KEY` |
| What does the promise block say? | `promises.parse_block`, `promises.load`, `promises.constants` |
| Which code does a promise rest on, and did it change? | `promises.declared_scope_sha`, `promises.scope_drift` |
| What is the protocol's id? | `protocol_check.protocol_identity` |
| Which protocols does an area hold? | `repo.area_protocols` |
| Where is the repo? | `repo.git_root` (git), `repo.layout_root` (git, else stamped tree) |
| Run git | `repo.git` (output, loud on failure), `repo.git_run` (exit code is the answer) |
| Is this run finished? Which runs are? | `runs.completion_state`, `runs.completed_runs` |
| What does a run's metadata say? | `runs.read_run_config` |
| Is the recording process alive? | `runs.is_alive` |
| Which protocol does a new run bind to? | `runlog._protocol_binding` |
| Which run answers for a protocol? | `intent_check.choose_explicit` / `choose_bound` / `choose_legacy` |
| Which code did an audit see? | `scope_sha` (area stamp, not per promise) |

A second answer to any of these questions is drift: move the caller to the
home, never copy the logic.
