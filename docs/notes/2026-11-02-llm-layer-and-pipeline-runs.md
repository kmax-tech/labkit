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

### agentsandbox: the sibling for agent attempts

`~/projects/agentsandbox` runs one coding-agent attempt (Claude Code, Codex)
in a sealed Docker container whose only exit is a logging proxy; standard
library only, about 3,100 lines. It already is what this plan asks of the
framework: its own package, with two real callers (labkit's usability
probes under `docs/usability/`, `labkit-paper/sandbox/`), and a stated
boundary — task, scoring, staging and token stay with the caller.

In the layers it stands beside the bottom one, not inside it: `labkit.llm`
answers "call a model with a prompt", agentsandbox answers "let an agent
work on a repository". It is not an LLM backend for the framework — one
container per item costs minutes and dollars where a fallacy label needs one
call, and labkit already isolates single Claude CLI calls. It earns its
place when the measured subject is an agent at work. It stays out of
labkit: Docker is a runtime dependency, and the unit differs.

The labkit-paper areas already tie attempts to a labkit run:
`experiments/17-supported-answers-when-agents-plan-themselves/scripts/01_measure.py`
imports `runlog` and runs its attempts through `sandboxlab` (see the runner
section below). The usability scripts under `docs/usability/` use `batch`
but no `runlog.run`; they are dated study records, not the current path.

Recording an agentic experiment, three levels:

| Level | What is recorded | Where |
|---|---|---|
| Attempt | agent, model, CLI version, image digests, limits, command, input hashes and whether the agent modified them, every model call through the proxy, usage, result, CPU; the attempt directory, archived | agentsandbox manifest (`<attempt_id>.manifest.json`, `attempt.py:237`) — exists |
| Row per attempt | attempt id, condition, task, manifest sha256, score, outcome class | `batch.Store` in the caller — exists |
| Series | protocol and question, frozen config (model, limits, prompt sha, image tag), which rows belong to it, the reported number | `runlog.run` — missing |

Rules particular to agents:

1. **An infrastructure failure is its own outcome, never a score of 0.**
   agentsandbox already separates them (`InfrastructureFailure`, HTTP 429,
   a container that did not run); the row keeps the class and the report
   counts the yield.
2. **Pin what changes behaviour.** CLI version, image digest, model id,
   limits and prompt sha are in the manifest; the series freezes them, and a
   resume refuses when one changed.
3. **Several attempts per task, no cache.** Agents are not deterministic;
   the spread is part of the result. Decision 1's cache does not apply to
   attempts at all.
4. **Score from the stored attempt, not during it.** Scoring reads the
   archived attempt directory, so a corrected scorer re-scores without
   re-running agents.
5. **Reference, don't copy.** The labkit record holds the attempt
   directory's path and the manifest's hash; transcripts and proxy logs stay
   where agentsandbox put them.

### The runner for agentic tasks exists: `sandboxlab`

The layer above one attempt is already shared. `labkit-paper/lib/sandboxlab`
(about 1,700 lines; the current branch is the `main-round` worktree
`labkit-paper-main`) holds it:

| Module | What it does |
|---|---|
| `batch` | `run_batch`: the registered attempt list, resumable, `workers` at a time; infrastructure failures to a ledger and rerun in a fresh directory; a rate limit stops the batch |
| `comparison` (since 2026-11-01, `e840f10`) | a two-arm round's shared parts: `attempt_of`, offline `check_setups`, `run_attempts`, `score_attempts` (hidden evaluation, report, effort, tokens per model) |
| `arms`, `benches/sab`, `standard_check` | the arms' wording, the benchmark's task texts, labkit's standard read off a finished attempt |
| `infra`, `config`, `pilot_checks` | images, token, capacity, setup checks |

Areas 16 and 17 run through it under `runlog`. It imports labkit
(`batch.py`: `from labkit import batch`), so it cannot move into
agentsandbox, which is standard library only and labkit-free.

#### The nine usability scripts compared (2026-11-02)

`docs/usability/*/run_*.py`, written 2026-10-27 to 2026-10-31, read by their
top-level definitions. Four generations, each taking a step toward
`sandboxlab`:

| Generation | Scripts | Shape |
|---|---|---|
| 1 | `2026-10-27-sab-cases-haiku`, `2026-10-28-repair-case-haiku-4054343`, `2026-10-28-sab-cases-haiku-main` (101–106 lines) | own loop over `run_attempt`, `to_container(task)`, `score(task)`; three sab-cases tasks |
| 2 | `2026-10-29-two-arms-haiku-ab4ce6d` (161) | arm and draw from the environment, setup per task, `evaluate` and a report replay |
| 3 | `2026-10-29-sab-pressure`, `2026-10-29-sab-round1`, `2026-10-30-gptoss-pilot`, `2026-10-31-sab-round2` (198–297) | `sandboxlab.batch.run_batch`, `arms`, `standard_check`, `benches.sab`; task texts from area 14; requirement and closing sentence; two arms; workers and repeats |
| 4 | `2026-10-31-registered-pilot` (636) | adds registration and venv change checks, staged directories, a check report |

Shared by all: bootstrapping `labkit-paper-main` onto the path; building
`Attempt` with `ClaudeCode` (Codex in the gptoss pilot) and `Limits`;
images and token from `sandboxlab.infra`; attempt ids; staging; prompt;
run; a separate `score` pass.

Specific to a study, and rightly kept there: the task list, task texts and
requirement, the prompt's wording (route, closing, the labkit sentence),
staging details, scoring criteria, per-task budgets (gptoss), the agent
adapter.

Drift in the knobs — the same concept under different environment
variables and defaults, which a config would make one:

- attempt id prefix: `TAG`, `RUN_TAG`, `ID_PREFIX`, `ATTEMPT_PREFIX`
- timeout default: 600, 1800 or 2400 s (`PROBE_TIMEOUT`)
- workers default: 2, 4 or 8 (`WORKERS`)
- store name: `store`, `store-oss`, `store-round2`, `store-rp`, …

One duplicate: `docs/usability/2026-10-31-registered-pilot/pilot_checks.py`
and `labkit-paper-main/lib/sandboxlab/pilot_checks.py` are byte-identical;
labkit's copy is the one `tests/test_pilot_checks.py` tests.

Verdict: the scripts are dated study records and stay as they ran — a
refactor would change what they document. New studies go through
`sandboxlab.comparison`. What is left for the runner: the knobs as one
config instead of environment variables per script, and `pilot_checks.py`
in one home.

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
- `src/data_loader/base.py:84` types the base loader's result as
  `ArgumentDataset`. Most of it is general (`ids`, `texts`, `labels`, split
  indices, `cache_id`); only `components` and `component_label2id` are
  argument-specific.

Both have to open before the middle layer can become a package.

### The extension contract

Half of it exists. The record contract between data and stages is
`CanonicalRecord` (`src/stages/canonical/schema.py`): `id` and `text`
required; `labels`, `context`, `_meta`, `enrichments` (dicts) and
`components` optional; `validate_canonical_record` checks it, and stricter
levels (`ClassificationRecord`, `PredictionRecord`) build on it. What a
general framework still needs:

1. **A general dataset type.** `Dataset` in the framework: ids, records
   (`CanonicalRecord`), split indices, `cache_id`. The two argument fields go
   into the record (`components`, `labels`) or into the topic's own type.
2. **Registration from outside.** `LOADER_MODULE_MAP` goes; the topic
   decorates its loaders (`register_dataset("argument")`, exists), and the
   config names the topic packages to import — the framework never names
   them.
3. **A conformance check every extension must pass**, shipped by the
   framework: ids unique, every record validates, splits disjoint and in
   range, `cache_id` set. The same for stages (declared inputs and outputs
   validate) and for prompt/parser pairs. The contract is that check, not a
   paragraph.
4. **A contract version**, raised when a required field or a check changes.

Limit to test before calling it general: `text` is required, so the
contract is text-only. The image projects that copied the framework
(`arg-images`, `aspect-based-image-generation`) would not fit. Generalize
against one real second case, not in advance.

## Decisions

1. **The cache lives in each lab repo that uses it** (2026-11-02, Max). A
   lab stays self-contained: cloned elsewhere, it gives the same result
   without the machine's state. A repeat run (`--repeat-of`, a new seed)
   bypasses the cache or carries the seed in the key — otherwise every
   repeat is answered from the cache and the measured spread is zero.

## Open decisions

The numbers stay as first written; 1 is decided above.

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
9. **The second case** the contract is tested against before the framework
   becomes a package: a text topic (lower risk) or one of the image
   projects (forces `text` to become optional or an `input` field).
10. **Home of the agentic runner**: it exists as `labkit-paper/lib/sandboxlab`
    and imports labkit, so agentsandbox is ruled out. Open: stay in
    labkit-paper (today's callers are its areas and labkit's usability
    probes, which already put `labkit-paper-main` on their path), or become
    a package of its own once a caller outside the labkit evaluation needs
    it. Smaller and due now: one config for the knobs, and one home for
    `pilot_checks.py`.
    Recommendation (2026-11-02), by what each module is: most of sandboxlab
    is the evaluation of labkit — `arms` (plain, instructions_only, labkit),
    `benches/sab`, `standard_check`, `comparison`'s scoring — and stays in
    labkit-paper. Not into labkit: the instrument that measures whether
    labkit helps must not live inside labkit, and Docker would become its
    dependency. Only `batch` is general ("many attempts, robustly": resume,
    infrastructure-failure ledger, requeue, stop on rate limit; 210 lines);
    it moves into agentsandbox as `agentsandbox.batch` when the first agentic
    study outside the labkit evaluation starts, with the resume store passed
    in by the caller (labkit's `batch.Store`) so agentsandbox stays
    labkit-free. Today every importer of sandboxlab is labkit-paper or a
    record of its runs (`labkit-evidence`, `labkit-anonymous` carry run
    scripts, not code).

## Not in scope

The fallacy stages, prompts and data loaders stay as they are. Splitting the
framework into its own package waits for its trigger. labkit's standard and
file formats are not stable yet (audit 2026-10-23); part 1 covers the Python
names only.
