# Two-stage model measurements — open `lanes` or a second skeleton (2026-11-20)

A draft, no code. Point 1 of the argmining27 usage findings (`TODO.md`, "Nutzungsfunde zu Wartung und Lesbarkeit"), decided by the author on 2026-11-18: show at an existing generate-then-judge experiment what labkit lacks, and which of two ways — open `lanes` for several stages, or stamp a second skeleton — needs fewer special cases. Nothing here is decided; the questions at the end are the author's.

Terms: a *stage* is one round of model calls whose answers are one output file (generation, judging). A *lane* is one prompt variant within a stage, as `lanes.Lanes` uses the word (the registered question, the null question). A *two-stage* measurement is one whose second stage builds its prompts from the first stage's answers.

## The case

argmining27 experiments 02 and 03 (2026-11-17) ask whether the objections Haiku writes against a MISSCI argument hit the reasoning gaps the annotators marked. One run has two stages:

1. Generation: per argument and condition (`context`, `no_context`) the model writes at most five objections. Output `…-objections.jsonl`.
2. Judging: per annotated gap and lane the same model names the candidate that captures the gap, or 0. The lanes are `context` and `no_context` (that argument's objections), `null` (another argument's objections) and `anchor` (the annotator comments of the same argument). Output `…-judgments.jsonl`.

`evaluate_rows(gen_rows, judge_rows, cfg)` computes the numbers from both files. Experiment 03 adds a person's check sheet, read by a derived run. Experiment 04 is one stage — a pairwise judge over the objections experiment 03 froze — and so is not a two-stage case; its open point is input from another area (point 6 of the findings, deferred).

`labkit-init exp … --kind apply --model` stamps the `lanes` skeleton: one stage, one prompt per lane and item, one output file. In all three areas the agent replaced `01_measure.py`, `02_analyze.py` and the area test entirely (argmining27 commits `e8bf110`, `095ba91`, `30406c9`).

## What was lost with the replacement

Read at `scripts/01_measure.py` and `scripts/02_analyze.py` of experiment 02 against `labkit/run/lanes.py`:

| What `lanes` does                                                                                               | In experiment 02                                                                                                                                                          |
|-----------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| refuses a prompt the protocol's Prompt block does not hold, before any paid call (`require_registered_prompts`) | gone: only `code-check` warns statically, after the fact                                                                                                                  |
| balances the rows against their jobs and the items as they are now (`balance`, `item_sha`)                      | the jobs' ledger is kept (`batch.Store.ledger().require_complete()`); no `item_sha`: an item edited after its row was written is not noticed                              |
| one instrument per output file (`balance`)                                                                      | the store still refuses rows of another instrument on resume                                                                                                              |
| `--probe`: N items per lane through the real pipeline, parser cases to paste into the test                      | gone                                                                                                                                                                      |
| `--repeat-of RUN_ID`: a draw of a kept run, its own output file; `02_analyze.py --draws`                        | gone                                                                                                                                                                      |
| `--show N`: the rendered prompts                                                                                | rebuilt by hand (`show`)                                                                                                                                                  |
| the recomputation of the kept number (`recheck.holds`, one output file)                                         | rebuilt by hand: `02_analyze.py --check` recomputes from both files and picks the newest measurement run itself — the helper written five times (point 5 of the findings) |

The probe and the repeat cost little at `low`, the cost all three areas declared; the lost prompt check and the hand-written recomputation are what a reviewer of the number would miss.

## Way 1 — open `lanes` for stages

`Lanes` stays the one-stage form. A run of several stages is a sequence of stage objects, each what `Lanes` is today for one output file: its prompts per lane, its `parse_answer`, its output file, and a `plan` that builds its jobs from the items and the earlier stages' rows (the judge's jobs carry the candidates as a field, which `render` already shows by name). One runner calls the stages in order inside one `runlog.run`, records every output file, and passes the rows of all stages to the area's `evaluate_rows`.

What each mechanism needs:

- **Prompt check:** `prompt_drift` over every stage's templates — no change in kind; the Prompt field holds one block per constant (as `protocol-fill --prompts` writes it since this release).
- **Resume and balance:** per stage, as today; the second stage's jobs depend on the first stage's answers, so a resumed run must refuse a first-stage file that changed under a second stage already begun (the second stage's rows carry the digest of the candidates they were shown, like `item_sha`).
- **Probe:** N items through both stages, the second on the first's probe answers.
- **Repeat:** a draw of every stage, or of the last stage on the kept first-stage rows — a design question (below).
- **Recomputation:** `recheck.holds` takes one `out` and a `recompute(rows)`. It would take the run's output files by name and a `recompute(rows_by_file)`. `recheck` is read by every stamped `02_analyze.py` but is not public API (`docs/architecture.md`, "Public API", lists `llm`, `llm_backends`, `llm_cache`, `runlog` and `batch`): a changed signature is a "Breaking" entry, and areas stamped before it keep their pinned version.

Special cases this adds: stage order and the dependency check between stages; one more argument shape in `recheck`. Everything else is the existing code, tested once.

## Way 2 — a second skeleton

`labkit-init exp … --kind apply --model --stages generate-judge` (name open) stamps a script like experiment 02's: two `batch.Store` files, `ask`, `evaluate_rows` over both, a hand-written `02_analyze.py --check`. The `lanes` module is untouched.

Special cases this adds: a second copy of the run mechanics in a template — resume, balance, prompt check, probe, show — in every stamped area, where a fix no longer reaches areas already stamped (stamps are not edited by hand); a second set of form comparisons (`tests/form_stamps/`); a second recomputation helper, or the same change to `recheck` as in way 1. It keeps `lanes` simple, and a generate-and-judge area reads as one plain script.

## Recommendation

Way 1. The mechanics that matter for the number — the prompt held to its registration before a paid call, rows held to their jobs, the recomputation from the kept files — stay in one tested home, and a fix reaches every area through the pinned version. Way 2 copies exactly these into each area, which is how experiment 02 lost the prompt check. The cost of way 1 is concentrated in two places: the stage dependency on resume, and the `recheck` signature.

A smaller first step that is useful on either way: `recheck.holds` for several output files, and the public function for "the newest completed measurement run of a protocol and its derived runs" (point 5 of the findings). Both remove the hand-written `02_analyze.py --check` of experiments 02 to 04.

## Questions for the author

1. **Which way:** open `lanes` (one home for the mechanics; `recheck` changes its signature, a "Breaking" entry), or a second skeleton (a plain script per area; the mechanics copied into each stamp).
2. **What a repeat draws:** both stages again (the spread of the whole measurement), or the judge only on the kept objections (the spread of the judge; the objections stay those of the answering run). The second is a derived run of its own kind.
3. **One model or one per stage:** experiments 02 and 03 use the same alias for both stages. A model per stage makes the instrument per stage (each output file its own `_instrument`) and the config two `model` fields.
4. **The first step:** build the `recheck` change and the run-choice function first, as their own step, before either way.
