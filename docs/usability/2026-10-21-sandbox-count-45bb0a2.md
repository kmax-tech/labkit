# Count at `seconds`, after the count fixes — labkit 45bb0a2 (2026-10-21)

*The three count probes of [bcea990](2026-10-21-sandbox-count-bcea990.md)
again, after its three findings were fixed: `input_dir()` reads under the
frozen `INPUTS` (a record naming another path is refused), the standard
and `docs/promise-block.md` state that a plain count owes no promise table
and no criterion, the skeleton names every blank. Same harness
(`agentsandbox` 1e0c557), image `labkit-probe:1d99e4d77a5c` (wheel of
45bb0a2, pytest 9.1.1), model `claude-sonnet-5-5`; labkit run and scorer
45bb0a2. Both contradictions are gone: no audit finding about `INPUTS`, no
criterion asked of a count. Scores and costs:
`2026-10-21-sandbox-45bb0a2-<probe>.{score,costs}.json`.*

| probe | number | bound | log span | misuse | outside | audit findings recorded | `input_dir` used | total USD |
|---|---|---|---|---|---|---|---|---|
| count-1 | 3.5 ✓ | yes | 1m17s | 0 | 2 (the agent's own `ls` of a missing `tests/`, `git check-ignore` exit 1) | 0 | yes | 0.366 |
| count-2 | 3.5 ✓ | yes | 1m16s | 0 | 0 | 0 | yes | 0.353 |
| count-3 | 3.5 ✓ | yes | 1m46s | 0 | 1 (the same `ls`) | 1 WARNING, dismissed | yes | 0.431 |

Against bcea990: audit findings per run 1 · 1 · 2 → 0 · 0 · 1; the
`INPUTS` warning (every run before) and the criterion asked of a count
(one run before) did not recur. Misuse 0 → 0, no gate refusal, no path
outside the probe but the task's log. Median log span 1m42s → 1m17s,
costs 0.40–0.42 → 0.35–0.43 USD; three runs a side — no speed claim.

The one finding left is new and of another kind: count-3's audit warned
that `visible()` and the `Unit:` field exclude only dot-files, so a
non-dot artefact (an Office lock file `~$…`) would count as a document;
the fixture holds none, and the agent dismissed it after listing the
files. A question of what the count's unit is, not a contradiction of the
stamp.

Observed, not faults (agents' reports):

- `finalize` warns about the untracked output before the run is even
  committed (count-1); the commit before `finalize` stays found by doing
  (count-1, count-2) — still only observed.
- The `seconds` lane says nothing about running the analysis audit in the
  foreground; the minutes lane warns about its length (count-3). It
  finished in time in all three.
- The audit's READ hints were left as hints, as the new list says
  ("no findings to decide" in two runs).
