# Plan: stagekit — the framework out of fallacy-detection, step by step

Date: 2026-11-03. Requested by Max. Works out the ten decisions of
[LLM layer and pipeline runs](2026-11-02-llm-layer-and-pipeline-runs.md)
into steps; nothing of stagekit is implemented yet. Each step is its own
task with its own done-when; a step starts when the one it depends on is
done. Revised the same day after three reviews (identities, cache, API
tests, baseline, second case, durable storage, repo timing, history split,
provenance across repos, replay versus repeat).

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
  hits). PyPI has a `stagekit` 0.0.2 without description; installed from
  git like labkit, this does not matter. Publishing on PyPI would need
  another distribution name or a name transfer (PEP 541). "Stage" also
  means preparing a repository in sandboxlab (`stage_arm`) — another repo,
  another layer.
- **Rejected:** `reprokit` — taken on PyPI by a tool that shrinks a failing
  command to a minimal bug reproduction, the opposite of what "repro" means
  here; `reprorun` — a published agent skill that reproduces papers'
  results; a Latin name like the house's reading tools (perlege, custos,
  verax) would be a pointer, while the lab-tool family (labkit,
  agentsandbox, sandboxlab) names what the tool does.

## Where it ends

| Package | Holds | Repo |
|---|---|---|
| labkit | public API, LLM calls with a cache of raw responses, run records across repos, checks | labkit |
| stagekit | stages, DAG executor, registries open to the outside, parsing, `repro_hash`, `RunIndex`, pins, tracker hooks | a new repo from step 3c on, its history filtered out of fallacy-detection; interface provisional (0.x) until step 6 passes; published after 6 |
| fallacy topic | fallacy stages, dataset converters, parsers, prompts, data loaders, configs, pins, data manifest | fallacy-detection — keeps its name, its remote on git.webis.de and its history; the core leaves it by a normal commit (3c) |
| experiment areas | protocol, config, prompts of one measurement | the lab repos |
| LLM cache, pinned outputs, dataset archives | the artifacts a result rests on | on disk beside the experiment, named in git by a sha256 manifest; **durable storage (Ceph) is still open**, a task of its own |

## What each identity denotes

Three hashes, three meanings; none of them alone says "reproducible".

| Identity | Built from | Proves | Does not cover |
|---|---|---|---|
| `repro_hash` (stagekit) | the config's identity fields (models, stages, data config names and paths), each prompt's version (derived from the template text) and each parser's `cache_id` (bumped by hand) | two runs were configured alike | stage code; parser logic while nobody bumps `cache_id`; the content of the data |
| cache key (labkit, step 2) | `llm.identity` plus the answer-changing spec fields, the prompt text, the sampling values | a stored model answer belongs to this call | parsing — the cache holds raw answers |
| run record (labkit) | commit, `+dirty` patch and untracked code of every repo whose code ran (lab repo, stagekit, topic repo, labkit — step 2b), data digests, models, `repro_hash` | this result came from this code, these data, this model | — this is the reproducibility claim |

Equal `repro_hash` values before and after a move prove that the identity
computation survived it. That the behaviour survived is shown only by the
tests and by comparing results.

## Two ways to run again, named apart

| Mode | Model calls | Stage processing | Answers the question |
|---|---|---|---|
| **replay** | none — every call from the cache of raw responses; a miss stops the run | runs again in full; no stored stage output is reused | does the processing (parsing, stages, evaluation) still give the same result? |
| **repeat** (`--repeat-of`) | all new; the cache is never read | runs in full | how much do the model's answers spread? |

Both are runs under labkit; the run record names the mode.

## Found while planning (2026-11-03)

- **Every registry is closed, not only the data loaders'.** Prompts,
  parsers, data loaders, splits and models each list their modules in the
  framework's source (`PROMPT_MODULE_MAP`, `PARSER_MODULE_MAP`,
  `LOADER_MODULE_MAP`, `STRATEGY_MODULE_MAP`, `MODEL_MODULE_MAP`). All five
  go through one class, `LazyRegistry` (`src/utils/registry.py`) — one
  place opens all of them.
- **Four imports and three data couplings run from the core into the
  topic** — counted module by module in the appendix ("The core, file by
  file"). An earlier count named three imports; two of them
  (`src/run/manager.py` → `repro_hash`, `src/run/pins.py` → `run_index`)
  stay inside the core, since `src/analysis/` belongs to it.
- **Topic and general sit side by side in the same folders:**
  `stages/canonical/` holds `base.py` and `schema.py` (general) beside seven
  dataset converters (`big_bench.py`, `hong.py`, …); `parsers/` holds
  `base.py` and `registry.py` beside nine topic parsers.
- **The current cache stores parsed results and cannot see parser changes:**
  `src/parsers/base.py:81` — "the cache has no way to detect logic changes"
  unless `cache_id` is bumped by hand.
- **labkit records only the calling repo's git state** today; an editable
  install's metadata gives a path, not a commit.
- **The history could not be pushed.** `main` was 290 commits ahead of
  `origin/main` (git.webis.de, still at the state of 2026-01-14); those
  commits added 867 MB of blobs — 726 MB in `data/cache` (the LLM cache,
  tracked on purpose since 2026-05-23, 21,733 files) and 116 MB in
  `data/archive` (dataset zips). Step 0 handles it.

## Steps

### 0 — baseline; data apart from code (before 3a)

- **Principle (decided 2026-11-03, Max):** data live apart from code — on
  disk beside the experiment, named in git only by a manifest of sha256
  values. Durable storage on Ceph is a task of its own (fallacy-detection
  `TODO.md`); publishing data is another.
- **Done already (2026-11-03, fallacy-detection, commits "data: LLM cache
  and dataset archives leave git; sha256 manifest instead" and "data:
  untrack the LLM cache and dataset archives"):** the LLM cache
  (`data/cache/llm/`, 21,733 files) and the dataset archives
  (`data/archive/`, 9 zips) left the tree; the files stay on disk, ignored;
  `data/MANIFEST.sha256` lists all 21,742 and verifies against them; rule 8
  of the repo's `CLAUDE.md` says so. Commit references in the repo's
  documents were resolved into date and subject.
- **History:** the unpushed commits still carry the data. `git filter-repo
  --invert-paths --path data/cache/ --path data/archive/ --refs main
  ^origin/main` removes it from them only; the server's commits stay
  untouched, so the push is a fast-forward (about 29 MB instead of about
  900 MB). Dry run on 2026-11-03: 52,429 data changes gone, 293 commits
  become 283 (ten held cache data only). A bundle of the whole repo comes
  first. The rewrite and the push are Max's; the script is prepared.
- **Baseline for the pilot**, recorded before 3a touches any code, in
  `published/baseline-2026-11-03.json` (decided 2026-11-03, Max; it sits
  beside the pins it belongs to, so `.gitignore` gets
  `!published/baseline-*.json` next to `!published/pins.yaml`):
  - the pilot's pinned predictions (`published/pins.yaml:56`) verified
    against the sha256 in `pins.yaml`, and the sha256 of every file in the
    pilot's run directory under `output/`;
  - the cache entries the pilot reads, by path and sha256 (a subset of
    `data/MANIFEST.sha256`, named so that 4a can check it reads only those);
  - `repro_hash` recomputed today for every entry in `published/pins.yaml`
    — the values 3c is compared against.
- **Done when:** the data on disk verify against the manifest; the
  baseline file is committed and its pilot entries verify; the test suite
  passes on the rewritten history; the push is a fast-forward of
  `origin/main`. Durable storage stays open: until Ceph, the only copies of
  the data and of `output/` are on this disk and in the bundle.

### 1 — labkit: public API, held by tests (decision 3)

- **Change:** a "Public API" table in `docs/architecture.md` with the names
  of decision 3; an import test for each listed name; **behaviour tests**
  for the contracts a lab relies on — `runlog.run(data=…)` as a context
  manager (what it records, what it refuses), `run.output()`,
  `llm.complete`'s return and errors, the `models.toml` schema (accepted and
  refused keys). A release rule: a public name or behaviour breaks only
  after one release in which the old one still works and warns.
- **Done when:** the tests are in the pre-commit run; a removed name and a
  changed signature each turn them red (two probes).
- **Depends on:** nothing.

### 2 — labkit: the cache of raw responses (decisions 1, 2)

- **Change:** `labkit/run/llm_cache.py`. The cache stores the model's raw
  response — everything the call returned that a caller may need: text,
  structured content, reasoning trace, finish reason, usage, the endpoint
  that answered. Parsing stays with the caller (stagekit); a corrected
  parser applies at once. Key: `llm.identity(alias)`, the answer-changing
  spec fields (claude-cli `input`, openai `reasoning`, ollama `num_ctx`),
  prompt text, temperature, `max_tokens`, seed — no parser id. Lives in the
  lab repo that uses it. Ported from
  `fallacy-detection/src/models/llm_cache.py` (locking, atomic writes),
  with the stored value changed from parsed to raw.
- **The two modes** of "Two ways to run again" are explicit switches:
  replay reads only from the cache and stops on a miss; repeat
  (`--repeat-of`) never reads it. A normal run reads hits and writes
  misses.
- **Rules held by tests:** repeat never reads the cache; replay never calls
  the model; an ollama model with digest `unavailable` is not cached and
  the call says why; a re-pointed alias misses; a hit is marked as a hit in
  the run record, carries its origin (when, which run wrote it) and the
  usage of the original call, and adds no new usage to the run's cost; the
  cache version and the mode enter the run record.
- **Done when:** one test per rule; the module stands in the layer table
  (`run` layer).
- **Depends on:** 1 (`identity` must be public first).

### 2b — labkit: provenance across repos (new)

- **Change:** a run records, for every repo whose code it imported — the
  lab repo, labkit, stagekit, the topic repo — the commit, a `+dirty` patch
  of tracked changes and the untracked code files it used. Found from the
  imported modules' source paths, so an editable install names its repo,
  not only a path. A documented measurement (a counted run) refuses
  untracked code it cannot record.
- **Done when:** a local, uncommitted change in an editable stagekit
  appears in the run record (probe); an untracked module in the topic repo
  is either copied into the record or refuses a counted run (probe).
- **Depends on:** 1.

### 3 — open the framework, then split the repo (decisions 4, 8)

Three steps, in this order, each with the full test suite green.

- **3a — the boundary as a test.** The module list `CORE` of the appendix
  and a test, after labkit's `tests/test_architecture.py`: no core module
  imports a non-core module. It starts red on the four imports the
  appendix names; cutting them is part of 3a.
- **3b — registration from outside.** `LazyRegistry` takes modules named
  by the experiment's config (`topics: [...]`), imported on load; the five
  `*_MODULE_MAP` keep only the framework's defaults. Hydra gets the
  experiment's config directory as search path (`hydra.searchpath`), in
  front of the framework's. Prompts: a directory registered from outside,
  each file under its name. `ArgumentDataset` becomes a general `Dataset`
  (ids, records, splits, `cache_id`); `components` and
  `component_label2id` move into the record or the topic. The topic also
  registers its artifact schemas and its derived-artifact derivations
  (appendix, couplings by data). A conformance check per extension kind
  (data loader, stage, prompt and parser pair, artifact schema), shipped
  with the framework.
- **3c — stagekit leaves fallacy-detection** (decided 2026-11-03, Max: the
  framework already runs, as copies, in several repos, and
  counterfactual-worlds is planned; the fallacy repo keeps its name and
  remote, stagekit starts as a new repo).
  - **stagekit** gets the core with its history: `git filter-repo --path
    <core paths>` on a clone of fallacy-detection, after step 0, so no data
    follow. The framework's documents go with it — the architecture
    reference (`.claude/commands/experiment.md`), the coding style, the
    `NOTES.md` entries about the engine.
  - **fallacy-detection keeps its history.** No rewrite: the core leaves by
    a normal commit that removes the core paths and installs stagekit
    instead; the push stays a fast-forward on the existing remote.
  - Documents in both repos refer to commits by date and subject, never by
    hash — stagekit's history gets new hashes.
  - fallacy-detection installs stagekit editable during development; a
    counted run records stagekit's state through 2b. The interface stays
    provisional (0.x) until step 6 passes.
  - **Proof, two parts:** `repro_hash` recomputed for every entry in
    `published/pins.yaml` equals step 0's baseline (the identity computation
    survived); the full test suite and a replay of the pilot's stages give
    identical predictions (the behaviour survived).
- **Done when:** boundary test green; the fallacy topic loads only through
  3b's route; both parts of 3c's proof hold.
- **Depends on:** 0 for 3c; 3a and 3b can start beside 1 and 2.

### 4 — the pilot under a labkit run (decision 6)

- **Change:** a labkit experiment area in fallacy-detection (decided
  2026-11-03, Max: the pilot reproduces one of its pins, so the proof stays
  where the pin is), holding protocol, `config/experiment.yaml` and the
  prompts of `baselines/big-bench/llama3.2/zs`; its `01_measure.py` opens
  `runlog.run` and calls stagekit with the area's config and prompt
  directories. The labkit record holds `repro_hash`, the output path, the
  mode, and the states of all repos (2b); `pipeline_summary.json` holds the
  labkit run id.
- **4a, embedding:** stagekit's own backends and its existing cache of
  parsed results, as a replay — every call a hit, only the cache entries
  named in step 0's baseline read; a miss stops the run and is a finding.
  The predictions must equal the pinned ones item by item (sha256 of the
  predictions file in `pins.yaml`). This proves the embedding under labkit
  and the preserved results; it does not test the raw-response split,
  because that cache holds parsed results.
- **4b, raw responses → parser:** stagekit calls `labkit.run.llm`. A normal
  run fills the cache of raw responses with real calls; then a **replay**
  from that cache, with the stage processing running again in full and no
  stored stage output reused (`preload_artifacts` and stored pipeline
  outputs off). The replay must equal the first run item by item (the
  split raw → parser is deterministic). The first run against the pin is
  reported item by item with its count of differing items — new calls may
  differ (see Risks); measuring that spread is a **repeat**, not part of
  this step.
- **Done when:** 4a identical with zero misses; 4b's replay identical; 4b's
  item-wise diff against the pin in the area's report; the run records
  show all repos' states (2b) and the mode.
- **Depends on:** 3 and 2b for 4a; 2, 2b and 3 for 4b.

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
- **Two rounds.** The first attempt may change stagekit: each change is a
  finding, written down, and both topics' tests and the pilot's replay run
  again after it. The closing run passes the conformance checks with
  stagekit unchanged.
- **Done when:** the closing run is green without a change to stagekit,
  and fallacy-detection is green on the same stagekit commit.
- **Depends on:** 3; best after 4.

### 7 — publish stagekit (trigger: 6 done)

- **Change:** stagekit leaves 0.x; the public interface is listed and held
  by tests as labkit's is (step 1); consumers pin a release. Public on
  GitHub, installed from git; PyPI only with another distribution name or
  after a name transfer.
- **Done when:** fallacy-detection and counterfactual-worlds run their
  tests against the pinned release; 3c's proof holds once more.

## Order at a glance

    0 ───────────────────────► 3c ─► 4a ─┐
    3a ─► 3b ─────────────────┘           ├──► 4b ──► 5
    1 ──► 2 ──────────────────────────────┤
    1 ──► 2b ─────────────────────────────┘
                                    3c ──► 6 ──► 7

## Risks

- **Parallel sessions in labkit.** Its pre-commit hook tests the whole
  working tree; foreign unfinished work blocks unrelated commits (seen
  2026-11-02 and 2026-11-03). Steps 1, 2 and 2b belong in a worktree of
  their own (`claude -w`).
- **labkit's churn.** Eleven releases with a Breaking section since
  2026-10-12; step 1 limits what reaches the labs, not the standard.
- **An early own repo (3c) before the second case.** The copies show the
  framework is reused, not that one contract fits them all; they may have
  drifted. Hence 0.x until step 6, and step 6's second round.
- **The history rewrite (0).** Irreversible for the rewritten, unpushed
  commits; backup bundle first, server history untouched, no force push.
- **No durable copy yet.** Until the data and `output/` are on Ceph, the
  only copies are on this disk and in the bundle — a lost disk loses the
  warm cache and the pinned runs.
- **4b may differ from the pin.** New calls at temperature 0 can still
  differ (batch composition on the server). The item-wise diff is the
  result, not a failure of the plan.

## Appendix: the core, file by file (2026-11-03)

Built from an import map of all 136 modules under `src/` (each module's
`src.*` imports, read with `ast`), a first-match rule per module path, a
search for topic module names written as strings, and a search for topic
words in core data definitions. Probe: the data-loader registry's one
known topic entry (`argument`) is found. The boundary test of 3a is the
lasting home of this list.

### Core — moves to stagekit (68 modules, about 11,200 lines)

| Package | Modules |
|---|---|
| entry | `main_pipeline` |
| `analysis/` | `repro_hash`, `run_index`, `run_record`, `scanner`, `table_aggregator` |
| `config/` | `classes`, `io`, `paths`, `resolution`, `schema`, `validation` |
| `data_loader/` | `base`, `registry` |
| `models/` | `base`, `llm_cache`, `llm_model`, `registry`, `bert_text`; `backends/`: `backends_base`, `cli_backend`, `factory`, `ollama_backend`, `ollama_completion_backend`, `openai_backend`, `vllm_backend` |
| `parsers/` | `base`, `registry` |
| `pipeline/` | `data_store`, `executor`, `preflight`, `registry` |
| `prompts/` | `base`, `registry`, `debug_utils` |
| `run/` | `artifact_manager`, `combinator`, `context`, `manager`, `pins`, `tracker`, `utils` |
| `splits/` | `base`, `config`, `manager`, `registry`, `strategies` |
| `stages/` | `base`, `artifact_readers`, `artifact_schemas` (mechanism only), `derived_artifacts` (mechanism only); `canonical/`: `base`, `schema` |
| `utils/` | `registry`, `serialization`, `reproducibility`, `parse_diagnostics`, `text` |

(plus the packages' `__init__` files)

### Topic — stays in fallacy-detection (68 modules, about 11,700 lines)

`analysis/tournament_stats`; `data_loader/argument`; nine parsers
(`argument`, `bayes`, `casa`, `classification`, `counterfactual`, `cq`,
`explanation`, `sentence`, `tournament`); `prompts/catalog` and the prompt
text files; seven dataset builders in `stages/canonical/`
(`arg_microtexts`, `big_bench`, `casa`, `fallacies`, `hong`, `sahai`,
`touchefallacy`); `stages/classify/` (12), `stages/derive/` (22),
`stages/llm/` (8), `stages/preprocessing/`; `stages/variant_mapping`
(the counterfactual story variants); `utils/argument_text`,
`utils/likelihood`, `utils/nli_features`, `utils/nli_pairs`.

### What 3a cuts — imports from core into topic (4, in 3 modules)

1. `config/validation` → `stages/classify/feature_utils` — a check the
   topic registers.
2. `config/validation` → `stages/variant_mapping`.
3. `run/combinator` → `stages/variant_mapping` — the counterfactual
   variants as an axis of run combination; the topic registers the axis.
4. `stages/derived_artifacts` → `stages/llm/counterfactual`
   (`_derive_cf_likelihoods`) — a derivation the topic registers.

### What 3b opens — couplings by name or data (not seen by imports)

- Module maps naming topic modules as strings: `pipeline/registry` (52
  stage entries), `prompts/registry` (48), `parsers/registry` (23),
  `data_loader/registry` (1). They keep only framework defaults; the topic
  registers the rest. The split and model maps carry no topic entries.
- `stages/artifact_schemas`: the enforcement is general; the schemas for
  counterfactual, tournament and CASA artifacts are the topic's.
- `stages/derived_artifacts`: the mechanism is general; each derivation is
  registered by the topic that owns the stage.

### Borderline, decided for 3c: stay with the topic for now

Moved into stagekit only when a second topic needs them (step 6):

- `stages/classify/` (k-fold, SVM, BERT, stacked, `eval_predictions`;
  2,471 lines) — general machine learning, but `feature_utils` builds its
  features from topic artifacts.
- the generic derive stages `drop_empty`, `export_jsonl`,
  `validate_derived_integrity`.
- `utils/likelihood` (log-likelihood ratio, 34 lines).
