# Connecting a stagekit area to labkit

This page is for an experiment area whose model calls run through a [stagekit](https://github.com/kmax-tech/stagekit) pipeline: several stages, prompt templates kept as files, stage outputs written as JSON documents. labkit's stamped skeleton (`labkit-init exp`) assumes one script that calls `llm.complete` itself. A stagekit area replaces `01_measure.py` and `02_analyze.py` with its own scripts. It still owes labkit the same records: the registered templates, a run that names its model and inputs, row files the number is computed from, and a recheck.

The order below comes from a two-stage trial (generate arguments, then rank them) run without a model. Each step names what it guarantees and what it does not.

## The calls, in order

| Step | Where                                   | Call                                                                                                          |
|------|-----------------------------------------|---------------------------------------------------------------------------------------------------------------|
| 1    | once, before the first run              | `protocol-fill PROTOCOL --prompts --prompt-file NAME=PATH …`                                                  |
| 2    | `01_measure.py`, start                  | set `STAGEKIT_PROJECT_ROOT`; `register_prompt_dir`; `compose_app_config`                                      |
| 3    | `01_measure.py`, before a run           | template list from `instrument_snapshot`; `prompt_check.require_registered_templates(PROTOCOL, templates)`    |
| 4    | `01_measure.py`                         | `runlog.run(…, config={"model": ALIAS, …}, data=config_input_paths(cfg), run_kind="measurement", protocol=…)` |
| 5    | inside the run                          | `llm_cache.Cache(run, …)` bound with stagekit's `answers_through`; `run_pipeline(cfg)`                        |
| 6    | inside the run                          | stage JSON documents → row files; `run.output(…)`; `run.metrics(…)`                                           |
| 7    | after the run                           | `finalize AREA`                                                                                               |
| 8    | `02_analyze.py --check --protocol FILE` | `recheck.holds_outputs` over every row file the number reads                                                  |

A model-free trial adds one step before step 4: store fixed answers with `llm_cache.store_stand_in` and open the cache in replay mode (see [Stand-in answers](#stand-in-answers-for-a-trial-without-a-model)).

### 1. Register each template

`protocol-fill PROTOCOL --prompts --prompt-file NAME=PATH` writes one Prompt block per template file, holding the file's text under a sentence `` `NAME` — … `` that is not sent. NAME is the name the pipeline registers the template under; for a directory registered with stagekit's `register_prompt_dir` it is the file name without `.txt`. Give every template the pipeline may send.

### 2. Compose the stagekit config

- Set `os.environ["STAGEKIT_PROJECT_ROOT"]` to the repository root **unconditionally**, before the first `stagekit` import that resolves a path. Do not use `setdefault`: a value inherited from another checkout makes stagekit read that checkout's config and data while labkit records this one's files. stagekit fixes the root at its first lookup and raises `ProjectRootChangedError` if the variable changes later in the same process.
- Make the topic package importable (stagekit imports it by module name); a script below `experiments/` adds the repository root to `sys.path`.
- Call `stagekit.prompts.registry.register_prompt_dir(PROMPTS)` once per process: a second call with a name already registered raises `ValueError`. A test that composes the config twice runs the script in a subprocess.
- `stagekit.run.utils.compose_app_config(overrides)` builds the config. Set `meta.enable_cache=false` (labkit's cache holds the raw answers; no second, parsed store) and `meta.max_retries=0` (a retry would read the same stored answer).

### 3. Hold the templates to the protocol before any model call

Build `{name: text}` from stagekit: the names from `stagekit.analysis.repro_hash.instrument_snapshot(cfg.to_dict())["prompts"]`, the text from `stagekit.prompts.registry.get_prompt(name).template_str`. Refuse a name whose version is `"unregistered"` or that starts with `llm_task:` — stagekit cannot resolve it, so there is no text to hold. Then call `prompt_check.require_registered_templates(PROTOCOL, templates)` before `runlog.run`.

What this guarantees: every listed template stands in the protocol, exact up to line endings, the block's fence indentation and the template's one final line ending. A template without a block, or with other text, ends the script with `SystemExit` before a run or a call exists.

What it does not guarantee:

- It holds the template text, not the filled prompt. How placeholders are filled is the area's test's to show. A stand-in replay shows it for the fixed cases (below).
- `instrument_snapshot` is a fingerprint, not a record of use. It lists each stage's declared templates (`uses_prompts`, a stage's own `llm_task`) and also the global `llm_task`'s template even when no stage uses it. Registering that one is over-coverage, never evidence that it was sent.
- A template a stage sends without declaring it is not in the list. stagekit refuses it in `LLMWorkflowStage.run_llm_step` (`StageValidationError`) right before sending it, not in advance: earlier steps and stages have already run.
- The block shows no final line ending, but stagekit sends the template file's text, which may end with one. Whoever rebuilds a sent prompt from the block (a stand-in, an audit) appends it.

### 4. Open the run with its model and its inputs

```python
from stagekit.config.inputs import config_input_paths

with runlog.run(
    "argue-rank",
    config={"model": cfg.model.model_name, "stagekit_overrides": OVERRIDES},
    base_dir=AREA,
    data=config_input_paths(cfg),
    run_kind="measurement",
    protocol=PROTOCOL.name,
) as run:
    ...
```

- Put the alias under `model` (or `<name>_model`): runlog resolves only those keys into `models_resolved`. An alias that stands only in an overrides list leaves `models_resolved` empty, and finalize blocks a call log whose alias no record names (LAB-027 Model discipline).
- `config_input_paths(cfg)` returns the input files stagekit resolves from the config (data file, dataset and split file, pinned preloads, stage input paths), by name. labkit records each with its sha256. It does not include the config YAML, `.env`, prompt or parser code, or files a topic's loader opens beyond the listed keys; record what else the number depends on yourself.

### 5. Route stagekit's calls through labkit's cache

```python
from stagekit.main_pipeline import run_pipeline
from stagekit.models.backends.labkit_backend import answers_through

cfg.output_dir = str(run.dir / "stagekit")
with answers_through(llm_cache.Cache(run, replay=REPLAY)):
    stage_run = Path(run_pipeline(cfg))
```

The model config uses stagekit's `labkit` backend (`backend: labkit`, `model_name: <alias>`). Every call then goes through `Cache.complete` and gets one line in the run's `llm-calls.jsonl`; finalize holds each line to a model record.

Do not use stagekit's own replay (`meta.cache_mode=replay`). It answers from stagekit's cache of parsed results, builds no backend and never reaches labkit: the labkit run holds no call line for those answers, and nothing in labkit sees them.

### 6. Turn stage outputs into row files

stagekit writes each stage output as one indented JSON document. labkit's recheck reads row files, one JSON object per line. Find each document with `ArtifactManager.for_run(stage_run).resolve_artifact_path(stage, key)` (from `stagekit.run.artifact_manager`), convert it to rows, write each row with `"_prov": {"run": run.run_id}`, and register the row files — and the JSON documents, if you want their hashes recorded — with `run.output(…)`. Compute the metrics from the rows and record them with `run.metrics(…)`.

stagekit repairs malformed JSON answers before its parser reads them (`json_repair`). With `meta.repair_answers: true` (the default) a cut-off answer can be closed and parsed; stagekit records the repair but does not drop the answer. With `false`, an answer the repair would change is refused as a parse failure. Whether a repaired answer may count is the protocol's evaluation rule, not stagekit's or labkit's: write it into the protocol and make the conversion apply it.

### 7–8. Finalize and recheck

`finalize AREA` checks the run as for any area. `02_analyze.py` must accept `--check --protocol FILE`: `report-check` runs exactly that command. With two or more row files, its check calls `recheck.holds_outputs(area, {"arguments": ARGS, "ranking": RANKING}, recompute, note, protocol=…)`: each file is pinned to the run (registered, recorded sha256), then the scopes, the code and the promise block are held, and the metrics are recomputed from the rows of all files together. `recheck.answering_run_dir(area, protocol)` gives the run to read; of `recheck`, only that name is public API, the rest may change between releases.

Keep the area test (`tests/test_<NN>_<name>.py`) to checks from memory: finalize runs it, so an area test that itself starts `labkit-adopt` runs finalize again inside finalize. Put end-to-end scenarios in a separate test file.

## Stand-in answers for a trial without a model

To run the pipeline without a model, store a fixed answer for each prompt the run will send, then open the cache with `replay=True`. A cache in normal mode reads the stand-ins too, but a call that misses there goes to the model; in replay it ends with `CacheMiss`.

```python
from labkit.run import llm_cache

root = llm_cache.default_root(AREA)
for prompt, answer in cases:  # prompt = registered block + final line ending, filled
    llm_cache.store_stand_in(
        root, cfg.model.model_name, prompt, answer, temperature=cfg.model.temperature
    )
```

Pass the call exactly as stagekit's `labkit` backend will make it: the alias, the filled prompt and the temperature, both taken from the composed config (`cfg.model`) rather than typed again — the key is built from the values as sent, so `0` and `0.0` are different keys; no system prompt, no `max_tokens` argument (the key then holds labkit's default cap, in both paths). `store_stand_in` builds the key with the same functions `Cache.complete` uses. A real call that differs in anything — one line ending, the temperature — finds no entry, and the replay ends with `CacheMiss` before any model is asked. It never hits silently. A completed replay therefore shows that every prompt the pipeline sent was one of the stored ones; it does not show that every stored one was sent.

The entries are marked as stand-ins. The call log says so, and finalize warns that the run read stand-ins: its numbers show what the processing does with fixed answers, not what a model answers. `store_stand_in` also writes the cache directory's `.gitignore`, so the entries stay out of git. The lab must declare the cache in `models.toml` (`[llm_cache] enabled = true`).

Adopting a result needs an analysis audit, which calls a model. A model-free trial can show steps 1–8 but not an adoption.
