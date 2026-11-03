# Plan: stagekit — the framework out of fallacy-detection, step by step

Date: 2026-11-03. Requested by Max. Works out the ten decisions of
[LLM layer and pipeline runs](2026-11-02-llm-layer-and-pipeline-runs.md)
into steps; nothing is implemented yet. Each step is its own task with its
own done-when; a step starts when the one it depends on is done.

## The name: stagekit (decided 2026-11-03, Max)

Fallacy detection was the first use case; the framework needs a name of its
own: **stagekit** — a kit for running experiments as configured stages,
reproducible by hash.

- **Says what it is:** the framework's core unit is the stage (stage base
  classes, a DAG of stages, stage registries); "kit" puts it beside labkit.
- **Says how it differs from its siblings:** labkit records and checks a
  measurement's intent; agentsandbox runs one sealed agent attempt;
  sandboxlab is labkit's evaluation runner; stagekit runs configured
  pipelines of stages.
- **The house term is inherited, not replaced:** the arbeitsstandard (2H)
  calls the repo that reproduces a paper's numbers the
  *Reproduktions-Repo*. stagekit is the engine such a repo runs on; the
  role keeps its name.
- **Collisions:** no hit in `~/projects` or `~/work` (probe: `labkit`, 46
  hits). PyPI has a `stagekit` 0.0.2 without description; it is installed
  from git like labkit, so this only matters if it is ever published to
  PyPI. "Stage" also means preparing a repository in sandboxlab
  (`stage_arm`) — another repo, another layer.
- **Rejected:** `reprokit` — taken on PyPI by a tool that shrinks a failing
  command to a minimal bug reproduction, the opposite of what "repro" means
  here; `reprorun` — a published agent skill that reproduces papers'
  results; a Latin name like the house's reading tools (perlege, custos,
  verax) would be a pointer, while the lab-tool family (labkit,
  agentsandbox, sandboxlab) names what the tool does.

## Where it ends

| Package | Holds | Repo |
|---|---|---|
| labkit | public API, LLM calls with response cache, run records, checks | labkit |
| stagekit | stages, DAG executor, registries open to the outside, `repro_hash`, `RunIndex`, pins, tracker hooks | its own repo once a second topic imports it (decision 9); until then `stagekit/` inside fallacy-detection |
| fallacy topic | fallacy stages, dataset converters, parsers, prompts, data loaders | fallacy-detection |
| experiment areas | protocol, config, prompts of one measurement | the lab repos |

## Found while planning (2026-11-03)

- **Every registry is closed, not only the data loaders'.** Prompts,
  parsers, data loaders, splits and models each list their modules in the
  framework's source (`PROMPT_MODULE_MAP`, `PARSER_MODULE_MAP`,
  `LOADER_MODULE_MAP`, `STRATEGY_MODULE_MAP`, `MODEL_MODULE_MAP`). All five
  go through one class, `LazyRegistry` (`src/utils/registry.py`) — one
  place opens all of them.
- **Three imports run from the general part into the topic part:**
  `src/run/manager.py:11` imports `src.analysis.repro_hash`,
  `src/run/pins.py:342` imports `src.analysis.run_index`,
  `src/config/validation.py:329` imports
  `src.stages.classify.feature_utils`. `repro_hash` and `run_index` are
  general and move into the core; the third is a check the topic should
  register.
- **Topic and general sit side by side in the same folders:**
  `stages/canonical/` holds `base.py` and `schema.py` (general) beside seven
  dataset converters (`big_bench.py`, `hong.py`, …); `parsers/` holds
  `base.py` and `registry.py` beside nine topic parsers.
- **Moving code keeps `repro_hash` and the cache valid** as long as class
  names and registry ids stay: `parser_id` is the class name, not the module
  path (`src/models/base.py:320`), and `repro_hash` is computed from config
  fields. Step 3c proves it rather than trusting this.

## Steps

### 1 — labkit: public API, held by a test (decision 3)

- **Change:** a "Public API" table in `docs/architecture.md` with the names
  of decision 3; a test that imports each listed name and fails when one is
  missing or renamed; a release rule in the contributing docs: a public
  name breaks only after one release in which the old name still works and
  warns.
- **Done when:** the test is in the pre-commit run; a deliberately removed
  name turns it red (probe).
- **Depends on:** nothing.

### 2 — labkit: the response cache (decisions 1, 2)

- **Change:** `labkit/run/llm_cache.py`, ported from
  `fallacy-detection/src/models/llm_cache.py` (standard library; `save_json`
  replaced by labkit's atomic write). Key: `llm.identity(alias)`, the
  answer-changing spec fields (claude-cli `input`, openai `reasoning`,
  ollama `num_ctx`), prompt text, parser id, temperature, `max_tokens`,
  seed. Lives in the lab repo that uses it. Wired into `llm.complete` behind
  an explicit switch.
- **Rules held by tests:** a repeat run (`--repeat-of`) never reads the
  cache; an ollama model with digest `unavailable` is not cached and the
  call says why; a re-pointed alias misses; the cache version enters the
  run record.
- **Done when:** the ported tests of fallacy-detection pass against the new
  module, plus one test per rule above; the module stands in the layer
  table (`run` layer).
- **Depends on:** 1 (`identity` must be public first).

### 3 — fallacy-detection: open the framework (decisions 4, 8)

Three commits, in this order, each with the full test suite green.

- **3a — the boundary as a test.** A module list `CORE` (pipeline, run,
  models, config, utils, splits, registries and bases, `stages/base.py`,
  `stages/canonical/{base,schema}.py`, `repro_hash`, `run_index`) and a
  test, after labkit's `tests/test_architecture.py`: no core module
  imports a non-core module. It starts red on the three imports above;
  fixing them is part of 3a.
- **3b — registration from outside.** `LazyRegistry` takes modules named
  by the experiment's config (`topics: [...]`), imported on load; the five
  `*_MODULE_MAP` keep only the framework's defaults. Hydra gets the
  experiment's config directory as search path (`hydra.searchpath`), in
  front of the framework's. Prompts: a directory registered from outside,
  each file under its name. `ArgumentDataset` becomes a general `Dataset`
  (ids, records, splits, `cache_id`); `components` and
  `component_label2id` move into the record or the topic. A conformance
  check per extension kind (data loader, stage, prompt and parser pair),
  shipped with the framework.
- **3c — the core becomes the package `stagekit/`** inside the repo, by a
  mechanical move (`git mv`, imports rewritten), behaviour unchanged.
  Proof: `repro_hash` recomputed for every entry in `published/pins.yaml`
  is identical before and after; the cache keys of a sample of entries
  likewise.
- **Done when:** boundary test green; the fallacy topic loads only through
  3b's route (its own `MODULE_MAP` entries gone from the core); 3c's hash
  proof holds for all pins.
- **Depends on:** nothing in labkit; can run beside 1 and 2.

### 4 — the pilot under a labkit run (decision 6)

- **Change:** a labkit experiment area for the pilot, holding protocol,
  `config/experiment.yaml` and the prompts of
  `baselines/big-bench/llama3.2/zs`; its `01_measure.py` opens
  `runlog.run` and calls stagekit with the area's config and prompt
  directories. The labkit record holds `repro_hash` and the output path;
  `pipeline_summary.json` holds the labkit run id.
- **4a, wiring:** stagekit's own backends. The predictions must equal the
  pinned ones item by item (`published/pins.yaml:56`, sha256 of the
  predictions file).
- **4b, labkit's calls:** stagekit calls `labkit.run.llm` instead of its
  own backends (they go). The cache key changes, so the model is asked
  anew; differences are reported item by item, not as a tolerance.
- **Done when:** 4a identical; 4b's item-wise diff written into the
  area's report with its count of differing items.
- **Depends on:** 3 for 4a; 2 and 3 for 4b.
- **Where the area lives (decided 2026-11-03, Max):** in fallacy-detection
  itself — the pilot reproduces one of its pins, so the proof stays where
  the pin is; outside use is step 6's test.

### 5 — tracker hooks (decision 5)

- **Change:** `RunTracker` tags every MLflow / W&B run with the labkit run
  id and `repro_hash`; enabled but not installed raises instead of
  warning; off stays the default.
- **Done when:** a test per point; one run with MLflow on shows both tags.
- **Depends on:** 4 (the labkit run id exists).

### 6 — counterfactual-worlds as the second case (decisions 7, 9)

- **Change:** labkit from `v0.85.0` to the current release, in new areas
  only (01–73 stay under the old standard, its `TODO.md`); one new area
  runs a measurement through stagekit from outside — its config and
  prompts in the area, its topic registered on import, the run under
  `runlog.run`.
- **Done when:** the area passes stagekit's conformance checks without a
  single change inside stagekit made for it; whatever had to change is the
  finding, written down.
- **Depends on:** 3; best after 4.

### 7 — stagekit gets its own repo (trigger: 6 done)

- **Change:** `stagekit/` moves into its own repo (history kept with
  `git filter-repo`), installed from git with a pinned commit, like labkit;
  fallacy-detection and counterfactual-worlds pin it.
- **Done when:** both consumers run their tests against the pinned
  stagekit; 3c's hash proof holds once more.

## Order at a glance

    1 ──► 2 ──────────────┐
                          ├──► 4b ──► 5
    3a ─► 3b ─► 3c ─► 4a ─┘
                      └──────────► 6 ──► 7

## Risks

- **Parallel sessions in labkit.** Its pre-commit hook tests the whole
  working tree; foreign unfinished work blocks unrelated commits (seen
  2026-11-02). Steps 1 and 2 belong in a worktree of their own (`claude -w`).
- **labkit's churn.** Eleven releases with a Breaking section since
  2026-10-12; step 1 limits what reaches the labs, not the standard.
- **The move in 3c.** Safe only while class names and registry ids stay;
  the hash proof decides, not this note.
- **4b may show differences.** A changed cache key means real calls; at
  temperature 0 ollama can still differ (batch composition). The item-wise
  diff is the result, not a failure of the plan.
