# Prompt binding for a stagekit area — design, explained at the two-stage example (2026-11-20)

A plan, no code, no model call. Step 2 of the [two-stage note](2026-11-20-two-stage-model-measurement.md#steps): how a stagekit area holds the prompts it sends to the protocol's registration, as `lanes` does for a one-stage area. Asked by the author on 2026-11-20 in four questions; the conversion of stagekit's outputs into row files is a separate part at the end. Everything below is read at the code of labkit `main` (`5e5ecaa7`), stagekit and argmining27 experiment 02 on 2026-11-20. The author decided its four points the same day, with additions; the last section states them and is the scope of the next build. Nothing is built.

Terms: a *template* is a prompt's text with placeholders, before an item fills it. *Registered* means: the protocol's Prompt field holds the text in a fenced block. A *fixed line* is a template line without a placeholder.

## The example

argmining27 experiment 02 (`experiments/02-missci-objection-coverage`) is a two-stage measurement written by hand on labkit, without stagekit and without `lanes`:

- Two templates as constants in `scripts/01_measure.py:79` and `:91`: `PROMPT_GENERATE`, once per argument and condition, and `PROMPT_JUDGE`, once per gap and lane.
- Three insert templates that fill one placeholder of those: `EXTRA_BACKGROUND`, `EXTRA_CONTEXT`, `CONTEXT_LINE`.
- `render_generate` and `render_judge` (`:155`, `:188`) fill them with `str.format`.
- The protocol registers all five, verbatim, one block each, under a sentence naming the constant (`PROTOCOL-missci-objection-coverage.md:38`).
- No check runs before the paid calls (`ask`, `:320`): the sent prompts are held to the registration by nothing at run time. The static check of `labkit-code-check` (`prompt_check.check_prompt_drift`) reads only constants named `PROMPT` / `PROMPT_<VARIANT>`, so the three inserts are not compared at all.

The stagekit form of the same measurement, as step 3 of the two-stage note would build it: two stages, `generate` and `judge`, whose templates lie as files in the area and are registered with `stagekit.prompts.registry.register_prompt_dir` (`registry.py:29`). Two things differ from experiment 02, read at stagekit's code:

- **Placeholders are `$name`, not `{name}`.** stagekit fills a template with `string.Template.substitute` (`stagekit/prompts/base.py:38`); labkit's comparison takes only `{…}` for a placeholder (`protocol_check.PLACEHOLDER_IN_PROMPT`, `protocol_check.py:1625`). A line `Claim: $claim` would be a fixed line for labkit today.
- **The fields pass a step before the template.** `LLMBaseModel._run_llm_call_with` calls `parser.prepare_fields(fields)` before `PromptRenderer.render` (`stagekit/models/base.py:786`), and the result goes to the backend as one string (`self.backend.generate(ctx.prompt)`, `base.py:692`; labkit's backend passes it to `Cache.complete`, `labkit_backend.py:88`). The parser can change what reaches the prompt.

## 1. How the protocol registers stagekit's prompt files

**Proposal:** the area keeps one directory `prompts/`, one `<name>.txt` per template, the name being the one stagekit's config and stage use (`llm_task.template`, `uses_prompts`). The protocol registers each file as one block under the sentence `` `<name>` — <what it is for; `$x`: how it is filled> ``, the form `protocol-fill --prompts` already writes for constants (`protocol_result.PROMPT_FIELD_NOTE`). `protocol-fill --prompts` reads the files beside the constants (`prompt_check.prompt_constants`, `prompt_check.py:190`) and writes their text verbatim; the sentence names the file's stem.

For the example that gives five blocks as today, named `generate`, `judge`, and the three inserts — if the inserts stay templates of their own. In stagekit they could also become one template per condition (`generate_context`, `generate_no_context`); which form fits the stages is the area's choice, not labkit's.

Why files and not constants: the author's answer of 2026-11-20 (two-stage note, "Questions for the author", question 1) prefers the files stagekit loads, and stagekit then stays unchanged. The cost falls on labkit: the reader of `--prompts`, the static check and the run-time check learn a second source and a second placeholder syntax.

## 2. Where it is checked before the paid call

**Proposal:** in the area's `01_measure.py`, after `register_prompt_dir` and before `runlog.run` opens — as `lanes` does it (`lanes.py:334`: `require_registered_prompts`, then `_run`), so that a refused start leaves no run directory. The check receives the templates as stagekit will use them, not as the files read: the names the config uses and each one's text from stagekit's registry (`get_prompt(name).template_str`). stagekit already lists those names, each with its version, for its `repro_hash` (`stagekit/analysis/repro_hash.py:158`, the stages' `uses_prompts` and each `llm_task.template`; a name it cannot resolve is marked `unregistered`). The area hands labkit that mapping `{name: text}`; labkit imports nothing of stagekit.

The check refuses three cases, each with the name:

1. A template the config uses has no registered block of its name.
2. Its text differs from that block.
3. A name the config uses is not in stagekit's registry (`unregistered` in the `repro_hash` listing).

A protocol without any Prompt block is said aloud and passes, as in `lanes` today.

**What it does not show:** that the paid calls sent these texts. It holds the templates before the run; the filling and the call are question 3.

**Optional, not proposed for the first build:** the run records each template's sha256 in its config (`config["prompt_templates"]`), so a later reader sees which templates the run held, independent of stagekit's 8-character `version` in `config_used.yaml`. That is a record, not evidence of what was sent.

## 3. How a test shows the way from filling to the model call

**Proposal:** a test in the area, with fixture data and no paid call:

1. Bind a stand-in for labkit's cache with `answers_through` (`labkit_backend.py:42`). It records every prompt it receives and returns fixed answers: for `generate` numbered objections, for `judge` a number.
2. Run the pipeline on two fixture arguments with one gap each, so the second stage builds its prompts from the first stage's answers.
3. Build the expected prompts independently of stagekit's code path. Read the blocks from the protocol, not the template files, and fill them with `string.Template` from the fixture's fields and the stand-in's answers.
4. Assert that the recorded prompts equal the expected ones, as a multiset, and that each stage made as many calls as it has jobs (two arguments × two conditions; per gap, one call per lane).

The test passes through `prepare_fields` and the stage's own task building, because it calls the pipeline, not `PromptRenderer`. It ties the protocol's text to the string the backend hands on. `lanes` has the same kind of test with a model that echoes its prompt (`tests/test_lanes.py:169`).

Its limit: it covers the code path at the time of the test, on fixture fields. It does not show what a later paid run sent. labkit's `llm-calls.jsonl` holds each call's key, not its text, and the rendered prompts are not kept per call. That is the open "prompt evidence" function of the two-stage note, not part of this plan.

## 4. What of `lanes` is shared

| Today                                                                                            | Where                    | Shared how                                                                                                                                                                                                                                       |
|--------------------------------------------------------------------------------------------------|--------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `unheld_prompt_lines(prompt, blocks)` — the pure comparison                                      | `protocol_check.py:1675` | takes the placeholder syntax as a parameter (`{name}` for constants, `$name` / `${name}` for stagekit files); stays the one comparison                                                                                                           |
| `registered_prompt_blocks(protocol)`                                                             | `protocol_check.py:1667` | unchanged; the block's naming sentence is read beside it, so a block is found by name                                                                                                                                                            |
| `Lanes.require_registered_prompts` — refuse before the paid call, say when nothing is registered | `lanes.py:358`           | moves to a function `require_registered_prompts(protocol, templates: Mapping[str, str], placeholder)` in the run layer; `lanes` calls it with its lanes' templates, behaviour unchanged; a stagekit area calls it with the mapping of question 2 |
| `check_prompt_drift` — the static check at `labkit-code-check`                                   | `prompt_check.py:219`    | reads the `prompts/*.txt` files beside the constants                                                                                                                                                                                             |
| `protocol-fill --prompts`                                                                        | `protocol_result.py`     | writes blocks for the files too                                                                                                                                                                                                                  |

**A limit of the shared comparison:** it is weaker than "the registered text".

- A line with a placeholder is never compared: `Claim: {claim}` changed to `Statement: {claim}` passes.
- Each fixed line need only stand somewhere in some block, so order and the assignment to a template are not checked.

It was built that way because a block may hold a prompt rendered with real data (`check_prompt_drift`, docstring). For a template read from a file, the block holds the template itself. So the stagekit path can compare exactly: the text of template `<name>` equals the block under the sentence naming `<name>`, after normalizing the line endings and the indentation of the markdown list. Whether `lanes` and the constants move to the exact comparison too is a separate decision (point 2 below). It would be a contract change for existing areas, whose blocks may hold rendered prompts.

## Separate part: stagekit's JSON outputs into registered row files

Since the step-1 build, `recheck` reads row files only and refuses a JSON document by the output's name (`recheck.output_rows`). stagekit writes each stage artifact as one indented JSON document (`stage_outputs/<stage>/<key>.json`, `stagekit/run/artifact_manager.py:76`).

In the example, the conversion is a function of the area per stage, each with its own test on a fixture artifact:

- the generation artifact → rows `{id: "<argument>|<condition>", item, condition, objections}`;
- the judge artifact → rows `{id: "<gap>|<lane>", item, gap, lane, answer}`.

Each row carries `_prov.run`, as experiment 02's rows and fallacy-detection 01 do. Inside `runlog.run` the area writes both row files and registers them together with the stagekit JSON documents they come from (`run.output`), as fallacy-detection 01 registers `pipeline_summary.json` (`01_measure.py:318`). The number is then computed from the two row files, and `02_analyze.py --check` holds it with `recheck.holds_outputs(outs={"generated": …, "judged": …})`.

What this shows and what not: the row files and the JSON documents are each pinned by their sha256. That the rows are the conversion of the documents is held by the conversion's test, not checked per run. A per-run check — convert the registered documents again and compare with the registered rows — would be a check of the area's `--check` of its own and is not proposed until the case shows it is needed.

## Decided 2026-11-20 — the scope of the next build

The author took the four points of the first draft with these additions. Where they differ from the sections above, this section holds.

1. **Prompt files in `prompts/<name>.txt`.** The file's stem is stagekit's prompt name and the name in the block's sentence: one name, three places. A template the config uses that does not come from this directory (a topic's built-in prompt, a file elsewhere) is not left unchecked silently. The check names it as not covered and refuses the start, since a check that could not run blocks the step it guards; the way out is to move it into `prompts/` and register its block.
2. **Exact comparison for templates read from files.** The text of template `<name>` must equal the block under the sentence naming `<name>`. That also catches a changed placeholder line, a changed order and a block under the wrong name. Normalized before the comparison, and nothing else:
   - line endings: CRLF and CR become LF;
   - the indentation the markdown list puts before every line of the block, as the block reader removes it;
   - one final line ending, which a fenced block cannot show.

   Every other character counts, trailing spaces and blank lines included.
3. **One refusal function, its own step first.** `lanes.require_registered_prompts` becomes a call of a shared function in the run layer, its behaviour unchanged. That is shown by the existing lanes tests, run unchanged, in a commit before the stagekit path uses the function. `lanes` keeps the line-wise comparison; its limits are documented (below), not changed — a change of the `lanes` contract is outside this build.

   **The checked templates are the ones the run uses.** The check runs after `register_prompt_dir` and before `runlog.run` opens, on the texts stagekit's registry holds. A file edited after that does not reach the run: `register_prompt_dir` reads each file once into the registry. The function returns the checked mapping with each text's sha256, and the run records it in its config. After `run_pipeline`, inside the run, the area holds stagekit's own record against it: each `prompt` version in `repro_hash` (sha256 of `template_str`, first 8 hex characters) must start the recorded sha256, and no name may stand there that was not checked. A mismatch raises, so the run ends as failed and does not answer.
4. **The conversion into row files stays the area's, with a limited assurance.** Both forms are registered with the run: the stagekit JSON documents and the row files made from them. The conversion has a test per stage. The sha256 values show that neither file changed after the run, not that the rows are the right conversion of the documents. That relation rests on the tested conversion code; no per-run check exists by this, and none is built until a case shows it is needed.

**The area test (question 3) shows the refusal too.** With one registered block changed by one character, the start is refused before any model call: the recording stand-in holds no call, and no run directory exists.

**Known limits of the line-wise comparison**, kept as they are for constants and `lanes` (`protocol_check.unheld_prompt_lines`):

- a line with a placeholder is never compared;
- a fixed line need only stand in some block, so order and assignment to a template are not checked;
- constants not named `PROMPT` / `PROMPT_<VARIANT>` are not read by the static check (experiment 02's three inserts).

Outside this build: new model measurements, any change to stagekit, a run in argmining27, and the `lanes` contract.

Not in this plan: resuming after a break, what a repeat draws, keeping the rendered prompt per call, any change to stagekit, any run in argmining27.
