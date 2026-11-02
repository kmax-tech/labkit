# Plan: one LLM layer, and large pipelines under a labkit run

Date: 2026-11-02. Requested by Max, for discussion. Nothing here is
implemented; the current standard and release rules remain in force. The
open decisions at the end come first; each part below becomes its own task
once they are settled. TODO entry: "LLM-Schicht: öffentliche Schnittstelle,
Cache, Anschluss großer Pipelines".

## Goal

One home for calling a model and recording the call, so a lab repo gets
caching, endpoint safety and provenance by importing labkit instead of
copying a framework. And, for a large pipeline such as
`~/projects/fallacy-detection`, one place where an experiment's protocol,
config, data and run provenance are found together.

## State found (2026-11-02)

Counted from the files named; not run.

- **The framework is copied, not imported.** No repo outside
  `fallacy-detection` imports its registries or executor.
  `arg-images`, `aspect-based-image-generation` (last commits 2026-03) and
  `fallacy-detection-github` carry their own copies of the same registry
  layout (`src/models/model_registry.py`, `src/parsers/parser_registry.py`, …).
  Eight repos in `~/projects` carry "fallac" in their name; whether they are
  labs, copies or dead was not checked.
- **labkit is imported as a package.** 599 `from labkit import …`
  statements in eight lab repos (counterfactual-worlds,
  fallacy-dataset-generation, fallacy-datasets, finance-discourse,
  paper-organization, teaching, uniagent, visual-argument-spec) plus seven
  uniagent worktrees. 316 of them import `llm`; 32 import `llm` alone. Labs
  want "call a model *and* record the run", not a bare client.
- **The bottom layer exists twice.** `fallacy-detection/src/models/backends/`
  (ollama chat and completion, openai, vllm, CLI) with `llm_cache.py`,
  `RunIndex` and `repro_hash`; and `labkit/run/llm_backends.py`, `llm.py`,
  `runlog.py`, `provenance.py`. `fallacy-detection` pins labkit in
  `requirements.txt` but imports nothing from it.
- **Tracking exists three times.** labkit's run record; the framework's
  `RunIndex` + `pipeline_summary.json` (its rule 1: runs are compared only
  there); and MLflow / W&B behind `src/run/tracker.py` `RunTracker`, both off
  in `config/tracking/default.yaml`. `mlflow.db` was last written 2025-12.

### Backends compared

| Capability | fallacy-detection | labkit |
|---|---|---|
| Parallel calls | thread pool, `max_workers` (`src/models/base.py:790`) | thread pool, `complete_many(workers=…)` (`labkit/run/llm.py:519`) |
| Processes for LLM calls | none found | none found |
| Response cache across runs | **yes**: key from prompt text, parser, template hash, backend name; stores the parsed answer; per-shard thread locks and `flock` across processes (`src/models/llm_cache.py:62`) | **no**: resume within one output file (`batch.Store`) |
| Misconfigured reasoning server refused | yes (`vllm_backend.py`) | yes (`reasoning = true`) |
| Several endpoints | round-robin (ollama); failover not found | round-robin and failover |
| Two aliases on one GPU slot | not found | refused across processes (`endpoint_lease.py`) |
| Prompt longer than the context | `num_ctx` set; no refusal found | refused, not cut |
| Backoff long enough for a model load | not checked | yes (~90 s) |
| Usage and cost per call | counter in `run/manager.py`, scope not checked | `last_usage()` |
| Claude CLI isolated from operator settings | not checked | yes, recorded in provenance |

Neither side is better overall: the framework has the cache labkit lacks;
labkit has the endpoint safety the framework lacks.

## Proposal

Three layers, each with one home:

| Layer | Content | Home |
|---|---|---|
| Bottom: call a model, cache, record the call | backends, prompt fit, response cache, provenance, run index | labkit only |
| Middle: pipeline framework | stage base classes, DAG executor, Hydra configs, prompt and parser registries, `repro_hash`, pins | its own installable package on top of labkit — only once a second topic imports it |
| Top: the topic | fallacy stages (`src/stages/llm`, `classify`), fallacy prompts, data loaders | `fallacy-detection` |

The framework does not move into labkit: labkit has no runtime dependencies
and is the tool that checks; Hydra and an executor would break both, and the
thing that runs should not be the thing that audits it.

No separate backend package either: labs import `llm` with `runlog` and
`batch`, so a split would add a second version pin to every repo without a
consumer that needs the backends alone. Trigger for a split: something
outside the labs needs the backends without labkit.

### Part 1 — public API contract

The layer table already holds imports inside the package
(`docs/architecture.md`, `tests/test_architecture.py`). Missing is the
outside contract: which names lab repos may use. Candidates: `llm.complete`,
`complete_many`, `resolve`, `spec`, `last_usage`, `last_endpoint`, the
`models.toml` schema, `batch.Store`, `runlog.run`. One list in
`docs/architecture.md`, a test that holds it, and a rule: a public name
breaks only after a release in which the old name still works and warns;
internals change freely. Reason: eleven releases with a Breaking section
since 2026-10-12 ([audit](../audit-2026-10-23.md)), and every lab repo pays
for each.

### Part 2 — the response cache moves into labkit

`llm_cache.py` (~480 lines) uses the standard library (`fcntl`, `hashlib`,
`json`, `threading`) plus one `save_json` helper, so it fits labkit's
no-dependency rule. After the move, `fallacy-detection` calls
`labkit.run.llm` and drops its own backends, gaining endpoint lease,
failover, prompt-fit refusal and usage.

### Part 3 — large pipelines run under a labkit run

Five rules, the usual way trackers attach to frameworks (logger or callback
at the boundary):

1. **One leading system per fact.** labkit leads for "which run belongs to
   which protocol, which number was reported". `output/` with `repro_hash`
   stays the content store and cache, and keeps leading for run comparisons
   and pins (framework rule 1).
2. **Attach at the existing seam.** `RunTracker` is created when the run
   starts (`src/run/manager.py:165`). The stages never see labkit.
3. **labkit gates, it does not just log.** `RunTracker` skips a missing
   backend with a warning; `runlog.run` checks protocol, registration and
   frozen config before the run and may refuse it. The adapter therefore
   sits where the run manager is built and fails loud.
4. **Link by ids both ways, copy nothing.** The labkit record holds
   `repro_hash` and the output path; `pipeline_summary.json` holds the labkit
   run id.
5. **One experiment end to end first**, then the rest.

### Datasets and artifacts of a topic

Three roles, none of them labkit's alone:

| Who | Does what with a dataset or artifact |
|---|---|
| Topic repo (`fallacy-detection`) | provides it: its loaders, stages and prompts register at the framework's extension points |
| Framework (middle layer) | runs it: defines the interfaces (`BaseDataLoader`, stage base classes, prompt and parser registries), stores artifacts in `output/` keyed by `repro_hash`, reloads pinned ones (`preload_artifacts`) |
| labkit | records and checks it: `runlog.run(data=…)` describes the inputs by hash and refuses a leak between splits; `run.output(...)` registers what the run wrote. It stores references, never the data |

The framework never names a topic module; the topic registers itself
(inversion of the dependency). In Python that is either registration on
import of the topic package, or entry points declared in the topic's
`pyproject.toml` (`[project.entry-points."<framework>.datasets"]`) that the
framework discovers. Large data stays outside every repo, addressed in the
config by path and content hash.

Two places in `fallacy-detection` stop this today:

- `src/data_loader/registry.py` lists loader modules in the framework's own
  source (`LOADER_MODULE_MAP = {"argument": "src.data_loader.argument"}`); a
  topic cannot add a loader without editing the framework.
- `src/data_loader/base.py` types the base loader's result as
  `ArgumentDataset`, a domain type in the general layer.

Both have to open before the middle layer can become a package.

## Open decisions

1. **Where the cache lives**: one cache per lab repo, or one shared across
   repos? Shared saves calls between labs but couples them; per repo keeps a
   lab self-contained.
2. **Cache key**: the `models.toml` alias or the resolved model id and
   backend? The alias can be re-pointed; the resolved id is what answered.
   How `prompt_sha` and the cache version enter the run record.
3. **Public API list**: which of the candidates in part 1 are public, and
   whether `lanes` belongs to it.
4. **Division of the run indexes**: confirm the split in part 3 rule 1, or
   let labkit's index also serve run comparisons.
5. **MLflow / W&B**: remove from the framework, or keep as an optional view
   that receives a copy of the metrics and leads nothing.
6. **Pilot**: which `fallacy-detection` experiment runs first under a
   labkit run.
7. **The copies** in `arg-images`, `aspect-based-image-generation` and
   `fallacy-detection-github`: leave, archive, or move onto the shared
   framework once it is a package.
8. **How a topic registers** its loaders, stages and prompts: on import of
   its package (simple, explicit) or via entry points (discovered, works
   across installed packages).

## Not in scope

The fallacy stages, prompts and data loaders stay as they are. Splitting the
framework into its own package waits for its trigger. labkit's standard and
file formats are not stable yet (audit 2026-10-23); part 1 covers the Python
names only.
