# A two-turn claude-cli answer without tools is a cut answer

2026-10-25. Seventh haiku round of area 09 on e9f088f, t18: the second
analysis audit (opus) failed `unproven` with `num_turns=2`,
`stop_reason=end_turn`, `subtype=success`, `is_error=false`, one model in
`modelUsage`, no `safety_stops` field (CLI 2.1.285). Open question from the
round's report: is that really an incomplete answer, or did labkit refuse
a whole one?

## What happened at t18 (the attempt's API proxy log)

`t18-labkit-r1/proxy/requests.jsonl`, the two opus requests of session
`e695feeb` (bodies 00072, 00073), both `max_tokens = 128000`, effort
`medium`:

- 00072: 10206 output tokens, all of them thinking — no answer text.
- 00073: the same prompt, then a user turn the CLI wrote itself: "Your
  response above was stopped by a safety classifier — this is not a tool
  or API error. The rest of it was withheld … Do not produce that content
  again, even reworded." 626 output tokens; that is the `result` labkit
  saw.

A safety stop, and the same model continued; the CLI of the day did not
count it. The refusal was right; the audit prompt (a drug-induced liver
injury dataset) likely met a false positive of a classifier. The output
limit was not near: the CLI already sends the model's own cap.

## Probe of the other cause (CLI 2.1.308, haiku 5.5, `--setting-sources "" --tools ""`)

- `CLAUDE_CODE_MAX_OUTPUT_TOKENS=1200`, a prompt that needs more: the first
  message cut mid-word, then the CLI's own user turn "Output token limit
  hit. Resume directly — no apology, no recap …", then the continuation.
  Final reply: `num_turns=2`, `stop_reason=end_turn`, `safety_stops=0`, one
  model; `result` begins mid-word.
- Without the variable, a 9000-line list: also two turns, 145166 output
  tokens in all — the first turn was cut, so the default cap was reached,
  and it lies above 72 k (the second turn ended on its own below it).
- The CLI accepts any value of the variable (200000 too, on opus 5.5 and
  haiku 4.5) without an error.

## Verdict

Two turns without tools are a cut answer either way; `result` holds only
the part after the last cut, and labkit refuses it. The reply does not
tell the cause: `safety_stops = 0` would name the output limit only on a
CLI shown to count every safety stop, and none is (2.1.285 counted none,
t18's stop included). The message says so — the answer not shown whole,
the cause not read from the reply (`llm_backends._cli_provenance`). The
proxy log is what names t18's cause.

Raising the limit would not have helped t18: for opus 5.5 the CLI already
sent 128000, the models' own cap; for haiku 5.5 its default lies above
72 k (measured above, not read). Decided 2026-10-25: labkit sets no limit
and allows no retry on a changed variable — the CLI takes any value
without a word, so a value labkit set would not be the limit in force.
