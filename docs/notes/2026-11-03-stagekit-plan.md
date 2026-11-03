# Plan: stagekit — the framework out of fallacy-detection, step by step

Date: 2026-11-03. Requested by Max. Works out the ten decisions of
[LLM layer and pipeline runs](2026-11-02-llm-layer-and-pipeline-runs.md)
into steps; nothing is implemented yet. Each step is its own task with its
own done-when; a step starts when the one it depends on is done. Revised the
same day after two reviews (identity, cache, API tests, baseline, second
case, durable storage, repo timing).

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
| labkit | public API, LLM calls with a cache of raw responses, run records, checks | labkit |
| stagekit | stages, DAG executor, registries open to the outside, parsing, `repro_hash`, `RunIndex`, pins, tracker hooks | its own repo from step 3c on; interface provisional (0.x) until step 6 passes; published after 6 |
| fallacy topic | fallacy stages, dataset converters, parsers, prompts, data loaders, configs, pins, data manifest | the fallacy repo, split from fallacy-detection with its own history (3c) |
| experiment areas | protocol, config, prompts of one measurement | the lab repos |
| LLM cache, pinned outputs, dataset archives | the artifacts a result rests on | on disk beside the experiment, stored by hash on Ceph, named in git by a sha256 manifest (step 0) |

## What each identity denotes

Three hashes, three meanings; none of them alone says "reproducible".

| Identity | Built from | Proves | Does not cover |
|---|---|---|---|
| `repro_hash` (stagekit) | the config's identity fields (models, stages, data config names and paths), each prompt's version (derived from the template text) and each parser's `cache_id` (bumped by hand) | two runs were configured alike | stage code; parser logic while nobody bumps `cache_id`; the content of the data |
| cache key (labkit, step 2) | `llm.identity` plus the answer-changing spec fields, the prompt text, the sampling values | a stored model answer belongs to this call | parsing — the cache holds raw answers |
| run record (labkit) | commit and `+dirty` patch of every repo whose code ran (lab repo, stagekit, topic repo, labkit), data digests, models, `repro_hash` | this result came from this code, these data, this model | — this is the reproducibility claim |

Equal `repro_hash` values before and after a move prove that the identity
computation survived it. That the behaviour survived is shown only by the
tests and by comparing results.

With stagekit installed editable (`pip install -e`) during development,
labkit's record must name stagekit's and the topic repo's commit and local
changes too, not only the lab repo's: an editable install's metadata gives a
path, not a commit. A documented measurement records every repo's actual
state.

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
- **The current cache stores parsed results and cannot see parser changes:**
  `src/parsers/base.py:81` — "the cache has no way to detect logic changes"
  unless `cache_id` is bumped by hand.
- **The history cannot be pushed as it is.** `main` is 290 commits ahead of
  `origin/main` (git.webis.de); those commits add 867 MB of blobs — 726 MB
  in `data/cache` (the LLM cache, tracked on purpose since 2026-05-23,
  rule 8 of the repo's `CLAUDE.md`, 21,733 files) and 116 MB in
  `data/archive` (dataset zips). The server holds 98 MB. Step 0 handles
  it.

## Steps

### 0 — baseline and durable storage (new, before 3a)

- **Principle (decided 2026-11-03, Max):** data live apart from code. On
  disk beside the experiment for local work, stored by hash on Ceph, named
  in git only by a manifest of sha256 values. Publishing data is a task of
  its own, not a side effect of pushing code.
- **Change:**
  - Done 2026-11-03 (fallacy-detection, commits "data: LLM cache and
    dataset archives leave git; sha256 manifest instead" and "data: untrack
    the LLM cache and dataset archives"): the LLM
    cache (`data/cache/llm/`, 21,733 files) and the dataset archives
    (`data/archive/`, 9 zips) left the tree; the files stay on disk,
    ignored; `data/MANIFEST.sha256` lists all 21,742 and verifies against
    them; rule 8 of the repo's `CLAUDE.md` says so.
  - The unpushed commits still carry the data. `git filter-repo
    --invert-paths --path data/cache/ --path data/archive/ --refs main
    ^origin/main` removes it from them only; the server's history stays,
    the push is a fast-forward. Dry run on 2026-11-03: 52,429 data changes
    gone, 293 commits become 283 (ten held cache data only). A bundle of the
    whole repo comes first; it keeps the old commit hashes named in
    `NOTES.md` and `docs/` resolvable, and filter-repo's commit map can
    rewrite them.
  - For now the data stay local (decided 2026-11-03, Max); storing them on
    Ceph is a task of its own, outside this plan (fallacy-detection
    `TODO.md`).
- **Done when:** the data on disk verify against the manifest; the test
  suite passes on the rewritten history; the push is a fast-forward of
  `origin/main`.
- **Who:** the history rewrite and the push are Max's (irreversible,
  remote); the script is prepared.

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
  lab repo that uses it. Wired into `llm.complete` behind an explicit
  switch. Ported from `fallacy-detection/src/models/llm_cache.py` (locking,
  atomic writes), with the stored value changed from parsed to raw.
- **Rules held by tests:** a repeat run (`--repeat-of`) never reads the
  cache; an ollama model with digest `unavailable` is not cached and the
  call says why; a re-pointed alias misses; a hit is marked as a hit in the
  run record, carries its origin (when, which run wrote it) and the usage of
  the original call, and adds no new usage to the run's cost; the cache
  version enters the run record.
- **Done when:** one test per rule; the module stands in the layer table
  (`run` layer).
- **Depends on:** 1 (`identity` must be public first).

### 3 — fallacy-detection: open the framework, then extract it (decisions 4, 8)

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
- **3c — the repo splits in two, each with its own history** (decided
  2026-11-03, Max: the framework already runs, as copies, in several repos,
  and counterfactual-worlds is planned). After step 0, from two clones:
  - **stagekit:** `git filter-repo --path <core paths>` keeps the core
    (the `CORE` list of 3a) and its history; the framework's documents go
    with it — the architecture reference (`.claude/commands/experiment.md`),
    the coding style, the `NOTES.md` entries about the engine.
  - **fallacy repo:** `git filter-repo --invert-paths --path <core paths>`
    keeps the fallacy-specific code, prompts, configs, pins, the data
    manifest and the topic's notes; its data stay on Ceph.
  - A commit that touched both sides appears in both, each with its part
    and the same message.
  - Documents in both repos refer to commits by date and subject, never by
    hash (done for fallacy-detection on 2026-11-03): both histories get new
    hashes.
  - The fallacy repo installs stagekit editable during development and pins
    a commit for any documented measurement. The interface stays
    provisional (0.x) until step 6 passes.
  - **Name and remote (decided 2026-11-03, Max):** the fallacy repo keeps
    the name `fallacy-detection` and the remote on git.webis.de — the
    server's history and whoever works with it are the topic's; stagekit
    starts as a new repo. The server still holds the state of 2026-01-14;
    after step 0 the push carries about 29 MB instead of about 900 MB.
  Proof, two parts: `repro_hash` recomputed for every entry in
  `published/pins.yaml` is identical before and after (the identity
  computation survived); the full test suite and a rerun of the pilot's
  stages from cache give identical predictions (the behaviour survived).
- **Done when:** boundary test green; the fallacy topic loads only through
  3b's route; both parts of 3c's proof hold.
- **Depends on:** 0 for 3c; 3a and 3b can start beside 1 and 2.

### 4 — the pilot under a labkit run (decision 6)

- **Change:** a labkit experiment area in fallacy-detection (decided
  2026-11-03, Max: the pilot reproduces one of its pins, so the proof stays
  where the pin is), holding protocol, `config/experiment.yaml` and the
  prompts of `baselines/big-bench/llama3.2/zs`; its `01_measure.py` opens
  `runlog.run` and calls stagekit with the area's config and prompt
  directories. The labkit record holds `repro_hash`, the output path and the
  states of all repos (see "What each identity denotes");
  `pipeline_summary.json` holds the labkit run id.
- **4a, embedding:** stagekit's own backends and its existing cache of
  parsed results. Every call must be a cache hit — a miss stops the run
  and is a finding. The predictions must equal the pinned ones item by item
  (`published/pins.yaml:56`, sha256 of the predictions file). This proves
  the embedding under labkit and the preserved results; it does not test
  the raw-response split, because that cache holds parsed results.
- **4b, raw responses → parser:** stagekit calls `labkit.run.llm`; the
  cache of raw responses is filled by real calls, then the run is repeated
  from that cache. The repeat must equal the first run item by item (the
  split raw → parser is deterministic); the first run against the pin is
  reported item by item with its count of differing items (new calls may
  differ, see Risks).
- **Done when:** 4a identical with zero misses; 4b's repeat identical; 4b's
  item-wise diff against the pin in the area's report.
- **Depends on:** 3 for 4a; 2 and 3 for 4b.

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
  finding, written down, and both topics' tests and the pilot run again
  after it. The closing run passes the conformance checks with stagekit
  unchanged.
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
    1 ──► 2 ──────────────────────────────┘
                                    3c ──► 6 ──► 7

## Risks

- **Parallel sessions in labkit.** Its pre-commit hook tests the whole
  working tree; foreign unfinished work blocks unrelated commits (seen
  2026-11-02). Steps 1 and 2 belong in a worktree of their own (`claude -w`).
- **labkit's churn.** Eleven releases with a Breaking section since
  2026-10-12; step 1 limits what reaches the labs, not the standard.
- **An early own repo (3c) before the second case.** The copies show the
  framework is reused, not that one contract fits them all; they may have
  drifted. Hence 0.x until step 6, and step 6's second round.
- **The history rewrite (0).** Irreversible for the rewritten commits;
  backup bundle first, server history untouched, no force push. Until the
  data are on Ceph, the only copies are on this disk and in the bundle — a
  lost disk loses the warm cache.
- **4b may differ from the pin.** New calls at temperature 0 can still
  differ (batch composition on the server). The item-wise diff is the
  result, not a failure of the plan.
