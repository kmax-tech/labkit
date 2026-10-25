# A two-turn claude-cli answer without tools is a cut answer

2026-10-25. Seventh haiku round of area 09 on e9f088f, t18: the second
analysis audit (opus) failed `unproven` with `num_turns=2`,
`stop_reason=end_turn`, `subtype=success`, `is_error=false`, one model in
`modelUsage`. Open question from the round's report: is that really an
incomplete answer, or did labkit refuse a whole one?

## Probe (CLI 2.1.308, haiku, `--setting-sources "" --tools ""`)

- `CLAUDE_CODE_MAX_OUTPUT_TOKENS=1200`, a prompt that needs more: the
  stream shows the first assistant message cut mid-word, then a user turn
  the CLI wrote itself — "Output token limit hit. Resume directly — no
  apology, no recap … Pick up mid-thought if that is where the cut
  happened." — then the continuation. Final reply: `subtype=success`,
  `stop_reason=end_turn`, `num_turns=2`, `is_error=false`, one model;
  `result` begins mid-word ("ty-two\n143 …"). Exactly t18's fields.
- With a cap of 300 the CLI resumed three times and then gave up with
  `is_error=true` and "API Error: Claude's response exceeded the 300
  output token maximum".
- `CLAUDE_CODE_MAX_OUTPUT_TOKENS=1000000` on a short prompt: accepted,
  one turn.

## Verdict

The refusal was right: t18's audit answer was cut, `result` held only the
part after the cut. The message was wrong — it said "2 turns" and offered
another model, where the cause is the output limit. Since this note the
message names `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (`llm_backends._cli_provenance`).

Not settled: the CLI's default limit for opus, and whether thinking
tokens filled it at t18 (the audit report itself is far below any
plausible default). Whether labkit raises the limit itself for its calls
is open in `TODO.md`.
