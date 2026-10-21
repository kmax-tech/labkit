# Judge at `seconds`, after the skeleton split — labkit be50b1b (2026-10-21)

*Three cold judge probes on the split skeleton: the stamped `01_measure.py`
keeps one block of what to fill and the experiment (config, parser,
counting functions, `evaluate_rows`), the run mechanics are
`labkit.run.lanes`. Harness `agentsandbox` c6a45ea (ten commits from
another session since 1e0c557, among them a proxy change; `agentsandbox
selftest` with the agent check against its images before the series: 20 of
20 held), image `labkit-probe:43b529f699a1`, model `claude-sonnet-5-5`;
labkit run and scorer be50b1b. Same checks and binding: every number bound,
no gate refusal, no misuse. Less to read: the measure script fell from 436
to 255 lines and the largest context an agent call read from 37–41k to
34–38k tokens; the stamped `00_prepare.py` (132 lines) is now the larger
share of what is left. Scores and costs:
`2026-10-21-sandbox-be50b1b-judge-<n>.{score,costs}.json`.*

| probe | number | log span | misuse | repairs | context max | files opened | total USD |
|---|---|---|---|---|---|---|---|
| judge-1 | 1.0 | 2m32s | 0 | 0 | 33,658 | 5 | 0.683 |
| judge-2 | 0.6667 (c1 failed) | 3m51s | 0 | 1 (Raw output: a placeholder, then `--force`) | 38,313 | 9 | 0.871 |
| judge-3 | 0.8333 | 3m03s | 0 | 1 (Raw output after the post hook) | 35,064 | 9 | 0.749 |

Against a2302bc (the same tasks on the full skeleton): context max
37,221 / 39,265 / 41,111 → 33,658 / 38,313 / 35,064; files opened 9–10 →
5–9; misuse 0 → 0; costs 2.38 → 2.30 USD. Three runs a side — the reading
is measured, no speed claim.

judge-2's 0.6667 is its own: its registered prompt asked whether a
sentence "states or implies" a causal claim, broader than a gold that
codes mere juxtaposition as not causal. The analysis audit raised it as a
BLOCKER; the agent accepted it and did not reword the prompt after seeing
the result ("rewording after seeing a failed C1 would be tuning"). The
audit found a real fault of the measurement — the agent audit tier doing
its work.

What the agents still name:

1. **The stamped `00_prepare.py` and its `audit()` TODO.** The prepare
   skeleton (132 lines) leaves its confound profile as a TODO; the
   analysis audit flagged it in two runs (judge-1 as a BLOCKER, judge-3 as
   a warning), as on a2302bc. Now the larger share of the skeleton to read.
2. **Raw output.** `protocol-fill --list` names it as owed before the run,
   `--from-run` does not write it, and the post hook flags it after the
   fact: judge-2 wrote a placeholder and overwrote it with `--force`,
   judge-3 filled it in a second call. Seen before on 45bb0a2.
3. **README placeholders and the untracked-output warning** of `finalize`
   (judge-1, judge-3) — noted again.
