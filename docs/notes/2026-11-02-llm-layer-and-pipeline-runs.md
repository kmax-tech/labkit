# Plan: one LLM layer, and large pipelines under a labkit run

Date: 2026-11-02. Requested by Max, for discussion. Nothing here is
implemented; the current standard and release rules remain in force. All
ten decisions were taken on 2026-11-02 and 2026-11-03 (section
"Decisions"); each part below becomes its own task. TODO entry: "LLM-Schicht: öffentliche Schnittstelle,
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

### The experiment holds its config and prompts (Max, 2026-11-03)

The labkit experiment area keeps what makes this measurement this one — its
protocol, the framework config (models axis, stages, data references with
hashes) and its prompts — and hands them to the framework, which runs them.
One area then shows the run's technicalities next to its question, and
labkit's code audit covers exactly that area instead of the framework's
20,000 lines.

    experiments/NN-<name>/
      protocol.md
      config/experiment.yaml      the framework config of this experiment
      prompts/<id>.txt            id = file name = registry id
      scripts/01_measure.py       thin: opens runlog.run, calls the framework
                                  with this config dir and prompt dir
      runs/                       labkit records; the framework's output is
                                  referenced by repro_hash, not copied

The framework cannot take either from outside today:

- configs: `src/config/paths.py:6` fixes `CONFIG_DIR = PROJECT_ROOT / "config"`,
  and Hydra is initialised with that directory only (`src/run/utils.py:22`).
  Hydra's own way out is a search path (`hydra.searchpath`): the experiment's
  config directory is searched first, the framework's defaults behind it.
- prompts: `src/prompts/catalog.py` registers 27 prompts in code and loads
  them from the package's own directory. Needed: register a prompt
  directory from outside, each file under its name.

Neither changes the cache or `repro_hash`: both key on the prompt text and
the resolved config, not on where the file lies. One home per prompt: an
experiment's prompt lives in the experiment; the framework keeps only
defaults. The area pins the framework's commit, as a lab pins labkit, so a
later framework change does not silently change a finished experiment.

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
2. **The cache key names the answering model, not the alias** (2026-11-02,
   Max). The alias can be re-pointed in `models.toml`; a key on it would
   serve an old answer from another model. The key is built from:
   - `llm.identity(alias)` — backend and model, for ollama with the weights'
     digest; endpoints excluded, as a host can change while serving the same
     weights. One home: the resume check (`lanes.Lanes.instrument`) and the
     row stamp use the same function.
   - the spec fields that change the answer and `identity` leaves out:
     claude-cli `input` (`harness` adds the agent's system prompt),
     openai `reasoning`, ollama `num_ctx`;
   - the prompt text, the parser id and the sampling values (temperature,
     `max_tokens`, seed).

   Not in the key: alias, endpoints, `api_key`/`api_key_env`. An ollama
   model whose digest reads `unavailable` is not cached — the weights it
   would stand for are unknown; the call says so instead of caching.
3. **The public API starts small** (2026-11-03, Max): `llm.complete`,
   `complete_many`, `resolve`, `spec`, `identity`, `last_usage`,
   `last_endpoint`; the `models.toml` schema; `batch.Store`; `runlog.run`
   with `data=` and `run.output()`. `identity` joins because the cache key
   builds on it (decision 2). `lanes` stays internal: it is the stamped
   areas' mechanics and changes with the standard. The list grows when a lab
   needs a name; taking one back would break labs, so it starts short.
4. **One owner per concern** (2026-11-03, Max). labkit owns question and
   protocol → run → reported number, the gate before the run, and
   provenance. The framework's `RunIndex` owns finding, grepping and
   comparing runs and outputs, and the pins. The framework's own tests own
   its code; labkit records which commit ran. labkit's code audit covers the
   experiment area only — config, topic stages, prompts — which the
   experiment holds itself (section "The experiment holds its config and
   prompts"). The table and the measurement: open decision 4 below.
5. **MLflow and W&B stay as an optional view** (2026-11-03, Max). They
   are hooks in the framework: `RunManager` hands `RunTracker` the stage
   metrics, the repro manifest, model usage, LLM stats and parse diagnostics
   (`src/run/manager.py:187`–`:428`). A tracker answers *what* happened
   across many runs and is the right tool for exploring; labkit answers
   *why* a run was made, what was fixed before it, and which number was
   reported. So:
   1. they lead nothing — provenance is labkit's, finding and pins the
      `RunIndex`'s (decision 4);
   2. every tracker run is tagged with the labkit run id and `repro_hash`,
      so a curve in the dashboard leads to the note that says why;
   3. enabled but not installed stops the run instead of warning — an
      empty dashboard must not pass for a recorded one;
   4. off stays the default (`config/tracking/default.yaml`).
   Points 2 and 3 are a small change in `src/run/tracker.py`.
6. **The pilot is the Big-Bench zero-shot baseline with llama3.2**
   (2026-11-03, Max): `published/pins.yaml:56`
   (`baselines/big-bench/llama3.2/zs`, `repro_hash c8f5bb69…`), run
   directory present locally. Local through ollama, so free to repeat;
   pinned with the predictions' sha256, so the proof is the item-wise diff,
   not a tolerance. Part 3 (the run under labkit) must reproduce the pinned
   predictions exactly — labkit records, it does not compute. Part 2 (the
   switch to `labkit.run.llm`) changes the cache key, so the model is asked
   anew; any difference shows per item.
7. **The copies stay where they are; nothing moves now** (2026-11-03, Max).
   Moving one onto the shared framework is possible later, when it is
   worked on again — an image project would then be the image case for the
   contract (open decision 9). Found when deciding: `arg-images` and
   `aspect-based-image-generation` (last commits 2026-03) each carry about
   100 uncommitted changes, `arg-images` with staged renames — unfinished
   work with remotes (GitHub, the Webis GitLab), not dead repos, so no
   archive banner was written into them. `fallacy-detection-github`
   (clean, remote `kmax-tech/bayesian-fallacy-detection`, last commit
   2026-08-19) is published paper code and stays frozen as such.
8. **A topic registers on import, named by the experiment** (2026-11-03,
   Max). The experiment's config names the topic packages to import and its
   own config and prompt directories; the framework loads exactly those and
   never names a topic itself. This covers all three extension points —
   data loaders, configs (Hydra search path), prompts. Not entry points:
   they load whatever is installed, invisible from the experiment — the
   area that holds the config should also show what is loaded. Entry points
   only if several installed topic packages ever run side by side.
9. **The second case is `counterfactual-worlds`** (2026-11-03, Max). It is
   due for an update anyway: it pins labkit `v0.85.0` (`requirements.txt`)
   against `v0.107.0` today, and has to follow the current standards. It
   meets the criteria: text, LLM calls per item (80 Python files call
   `llm.complete`/`complete_many`), clean tree. The update and the contract
   test become one job. Limit to keep in view: it is the counterfactuals
   and fallacy-detection thread, close to the first topic, so it tests
   portability less hard than a distant domain would; the image case stays
   the harder test, when an image project is worked on again (decision 7).
10. **sandboxlab stays in labkit-paper; only `batch` moves, on a trigger**
    (2026-11-02, Max). sandboxlab is the evaluation of labkit and stays in
    labkit-paper — not in labkit, whose evaluation must not live inside it.
    Its general part, `batch` (`run_batch`), moves into agentsandbox as
    `agentsandbox.batch` when the first agentic study outside the labkit
    evaluation starts; the caller passes the resume store (labkit's
    `batch.Store`) in, so agentsandbox stays labkit-free. Recorded in
    agentsandbox's `TODO.md`. Reasoning: the recommendation under open
    decision 10 below.

## Open decisions

All ten are decided above (2026-11-03); the questions below are kept as
first written, with the recommendations that led there.

2. **Cache key**: the `models.toml` alias or the resolved model id and
   backend? The alias can be re-pointed; the resolved id is what answered.
   How `prompt_sha` and the cache version enter the run record.
3. **Public API list**: which of the candidates in part 1 are public, and
   whether `lanes` belongs to it.
4. **Division of the run indexes**: confirm the split in part 3 rule 1, or
   let labkit's index also serve run comparisons.
   Recommendation (2026-11-03), one owner per concern:

   | Who | Owns | Checked by |
   |---|---|---|
   | labkit | question and protocol → run → reported number; the gate before the run; provenance (commit, data hashes, model) | its standard and checks |
   | the framework's `RunIndex` | finding, grepping and comparing runs and outputs (`repro_hash`); pins | the framework's code |
   | the framework's code | computing correctly | the framework's own tests; labkit records only which commit ran |
   | the experiment's code (config, topic stages, prompts) | what this question measures | labkit's code audit, this part only |

   Measured on `fallacy-detection` (2026-11-03): labkit records HEAD
   (`+dirty`), a copy of the started script and a patch of uncommitted
   tracked changes only — never a diff of the whole repo; on 22,322 tracked
   files with a clean tree the check took 0.09 s. The limit is the agent
   audit (`code-check`), whose bundle takes the imported modules: on a
   20,000-line framework it would audit the framework, not the experiment —
   hence the last row.

   Found alongside: `published/pins.yaml` points into `output/`, which
   `.gitignore` excludes (`output/*`, 474 MB, local only). A clone has the
   pins but none of the pinned runs, so the paper's tables cannot be rebuilt
   from it. The reference with sha256 is the right shape; its target needs
   a durable store outside git (an archive or a DVC remote) that the sha256
   lets anyone verify. There are no symlinks in the repo.
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
