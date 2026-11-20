# Prompt binding for a stagekit area — the limited path (2026-11-20)

Step 2 of the [two-stage note](2026-11-20-two-stage-model-measurement.md#steps): the prompts a stagekit area sends are held to the protocol's registration before the first model call. Decided by the author on 2026-11-20 after two rounds; this note replaces the longer first draft (its text is in the git history of this file). No change to stagekit, no change to `lanes`, no model call.

Terms: a *template* is a prompt's text with placeholders, before an item fills it. *Registered* means: the protocol's Prompt field holds the text in a fenced block under a sentence naming it.

## The problem, at the example

argmining27 experiment 02 is a two-stage measurement (objections generated, then judged) written by hand on labkit. Its five templates are constants in `scripts/01_measure.py`; the protocol registers each in a block of its own. labkit reads prompts only as such constants (`prompt_check.prompt_constants`). A stagekit area holds its templates as files that stagekit loads (`register_prompt_dir`, `stagekit/prompts/registry.py:29`), filled with `string.Template` (`$name`, `stagekit/prompts/base.py:38`). labkit cannot import stagekit, so it does not know which templates a stagekit run uses — the area's script does, from stagekit's registry.

## The three parts

1. **`protocol-fill PROTOCOL --prompt-file NAME=PATH …`** writes one block per named template file: the file's text verbatim, under the sentence `` `NAME` — … ``. NAME is stagekit's template name, given explicitly — a file name can differ from the name stagekit registers it under. The other blocks stay as they stand.
2. **`prompt_check.require_registered_templates(protocol, templates)`**, called by the area before the first model call with every template the run uses, `{name: text}` as stagekit's registry holds them. It refuses the start, naming each template, where
   - no block carries its name (*not covered*: a template the run uses that cannot be held to a registration), or
   - its text is not exactly the block's text.

   Before comparing, three things are normalized, and nothing else: line endings (CRLF and CR become LF), the indentation of the opening fence removed from each block line (what the markdown list puts there, not other leading whitespace — a block line without that indentation is refused as unreadable), and one final line ending, which a fenced block cannot show.
3. **A scenario test** with fixed stand-in answers: blocks written from two template files, the check passing, every prompt filled from the checked texts reaching the recording stand-in model; and the counter-case — one block changed by one character — refused before any call.

For the first case each condition gets a complete template of its own (`generate_context`, `generate_no_context`), so every fixed text sent is a registered template. That is no rule for every area: data and how it is prepared stay the area's code and its tests.

## What it shows and what not

- The comparison covers the registered template text, not the whole prompt sent: a template still has placeholders. Their filling is held by the area's test up to the intercepted model call; in labkit the scenario test shows the contract on fixture data, the stagekit path itself is tested in the area (step 3 of the two-stage note).
- An exact comparison does not show that a prompt is scientifically sound; that is the audit's.
- The templates checked are the ones the run uses as long as the area passes the texts from stagekit's registry, which reads each file once at registration. A version comparison after the run is not built until a case shows that other templates can come in between.
- stagekit's JSON outputs into registered row files is a separate part of the later coupling: both forms registered with the run, the conversion tested per stage; the sha256 values show that neither file changed, not that the rows are the right conversion.

## Known limits, unchanged

The line-wise comparison of constants and `lanes` (`protocol_check.unheld_prompt_lines`) stays as it is: a line with a placeholder is never compared; a fixed line need only stand in some block, so order and assignment to a template are not checked; the static check reads only constants named `PROMPT` / `PROMPT_<VARIANT>` (experiment 02's three inserts are not read). Changing that is a contract change of its own.
