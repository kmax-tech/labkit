# Judge at `seconds`, after the decision-list fix — labkit a2302bc (2026-10-21)

*The three judge probes of [45bb0a2](2026-10-21-sandbox-judge-45bb0a2.md)
again, after `labkit-audit` moved its decision list last onto stdout and
gained `--findings`. Same harness (`agentsandbox` 1e0c557), image
`labkit-probe:87761b4b99cd` (wheel of a2302bc, pytest 9.1.1), model
`claude-sonnet-5-5`; labkit run and scorer a2302bc. All three agents piped
the audit through `2>&1 | tail -30`, as the one that lost the list had —
and this time the list was in what they saw. Scores and costs:
`2026-10-21-sandbox-a2302bc-judge-<n>.{score,costs}.json`.*

| probe | number | log span | misuse | repairs | audit records | decisions | list in the piped output | `--help` / `--findings` | source reads | total USD |
|---|---|---|---|---|---|---|---|---|---|---|
| judge-1 | 0.8333 | 3m01s | 0 | 0 | 1 | 3 | yes | 0 / 0 | 0 | 0.813 |
| judge-2 | 0.9167 | 2m37s | 0 | 0 | 1 | 3 | yes | 0 / 0 | 0 | 0.761 |
| judge-3 | 0.8333 | 2m57s | 0 | 0 | 1 | 3 | yes | 0 / 0 | 0 | 0.801 |

Against 45bb0a2: misuse 4 → 0, repairs 3 → 0, audit records 4 → 3 (no
second paid audit), no refusal of any kind, no read of labkit's source;
total cost 3.14 → 2.38 USD. Every candidate failure mark was a false one
(stamped script text, the audit's own finding text). `--findings` was not
needed: the list stood where the agents looked.

What the agents still name, not faults of the decision path:

- Reading the stamped skeleton: `01_measure.py` is 436 lines for about
  six edits (all three) — the TODO row "Zählvorlage aus Task-Feldern".
- The Raw output field shows as open in `--list` before any run exists
  (judge-1); noted earlier, unchanged.
- README placeholders that `finalize` warns about (judge-2, judge-3).
