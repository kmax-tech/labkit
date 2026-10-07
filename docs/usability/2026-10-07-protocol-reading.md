# Protocol reading, round 7 (2026-10-07): how the protocols read for a person

Question: with the 0.57 template (legend out, answer first, lists instead of
chains), do cold agents write protocols a cold reader understands — and
what still stops the reader?

Writers: four cold Sonnet agents (`count` ×2, `judge` ×2), labkit
`5fec2f7`, seconds track; their prompt carried only the seconds section of
the lab CLAUDE.md (round 6 carried the whole file). Readers: one cold
Sonnet agent per protocol, the protocol alone (`usability reader`), answer
held to the run's number (`usability read-score`); for comparison two real
protocols of uniagent (areas 08, 09, written under the old template).
Archive: labkit-paper `data/raw/agent-traces/2026-10-07/round7/`.

| protocol | lines | form lines before the first field | longest field (chars) | reader: number right | reading time | effort 1–5 | unclear terms (of them from the stamped form) |
|---|---|---|---|---|---|---|---|
| count-1 | 52 | 3 | 184 | yes | 19 s | 2 | 9 (8) |
| count-2 | 55 | 3 | 284 | yes | 16 s | 3 | 7 (7) |
| judge-1 | 75 | 3 | 260 | yes | 15 s | 3 | 10 (5) |
| judge-2 | 78 | 3 | 284 | yes | 16 s | 4 | 16 (11) |
| uniagent 08 | 160 | 37 | 1465 | — | 21 s | 5 | 15 (3) |
| uniagent 09 | 176 | 39 | 1592 | — | 21 s | 5 | 21 (2) |

"From the stamped form" is a heuristic: the term's first word occurs in
the template. The uniagent protocols record real, multi-arm experiments;
the probes are toy tasks — the comparison shows the form's share, not that
the template alone halves the effort.

- Every reader got the number right and stated the result and its limit in
  its own words.
- In the new protocols most of what readers could not place comes from the
  stamped form, not from the writer: `AS-015`/`AS-017`/`AS-050`, `scope
  sha`, `preflight audit`, `frozen`, `runlog`, `lib exp`,
  `protocol-fill`/`protocol-check`, and the open placeholder `Analysis
  audit †` (owed later at seconds, stamped now). Sources: the comments in
  the toml head, the pointer line, the placeholder.
- What the writers left unglossed: `MARGIN`, "lane", item ids (`c08`),
  the model alias and `models.toml`.
- In uniagent's protocols the unclear terms are the domain's (areas,
  cases, rule names, arms) — the writer's vocabulary, glossed nowhere a
  reader finds it.

Levers for the next round, one at a time:

1. the toml head without comments (their content is in the field guide);
2. `Analysis audit †` not stamped at seconds (it is owed when the number
   steers a decision, not in this session);
3. the writer glosses its own coined terms in `Terms of this protocol`
   (constants such as `MARGIN`, the lanes) — an instruction, measured by
   the reader's unclear list.
