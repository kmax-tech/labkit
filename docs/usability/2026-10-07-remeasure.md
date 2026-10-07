# Usability re-measure 2026-10-07: n = 3 per task on labkit 0.52

TODO item 2. Six cold Sonnet agents, three per task, each in its own probe
repo stamped by `usability stage <dir> --venv <labkit .venv> --task
count|judge` at labkit `fd4cd60` (0.52.0, hooks installed through
`labkit-hooks install`). Scaffold sha `46ac023ab356`, flags `--lab … --exp
<area>`, no `--cost`: the agent declares the tier. Scores:
`2026-10-07-sonnet-{count,judge}-{1,2,3}.score.json`.

## Result

| run | number | truth / range | bound | wall-clock | gate lines | reads of labkit source / standard |
|---|---|---|---|---|---|---|
| count-1 | 3.5 | equals truth | yes | 1m16s | 1 (noclobber) | 0 |
| count-2 | 3.5 | equals truth | yes | 1m11s | 1 (noclobber) | 0 |
| count-3 | 3.5 | equals truth | yes | 2m27s | 2 (noclobber; pre-commit) | 0 |
| judge-1 | 0.833 | in [0, 1], null reported | yes | 2m23s | 1 (A2 failed) | 0 |
| judge-2 | 0.833 | in [0, 1], null reported | yes | 2m14s | 0 | 0 |
| judge-3 | 0.833 | in [0, 1], null reported | yes | 2m35s | 0 | 0 |

Median wall-clock: count 1m16s, judge 2m23s (log span; the subagent
durations, 100 to 184 s, agree). On 2026-10-05 a single count took 4m20s
to 9m58s. All six declared `cost = "seconds"`, none froze, none opened the
labkit source or the standard.

## Gate lines, sorted by cause

- **True positive (labkit worked).** judge-1: the agent's placebo question
  ("does the sentence contain a number?") correlated with gold; the null lane
  scored 4/12 against an expected 6 ± 1, [A2] failed and the skeleton
  withheld the [C1] verdict (`c1_pass = None`). The agent reported it rather
  than moving the criterion.
- **Agent error, blocker correctly raised.** count-3: the pre-commit hook
  refused the write-back commit with `Raw output` empty. The blocker was
  one line among about 20 placeholder warnings.
- **Not labkit.** noclobber in the agent shell (3 of 3 count runs).
- **Not reproduced.** judge-3 logged `code-check` refusing a relative area
  path; `code-check experiments/01-causal-claims-judge` from the repo root
  exits 0.

## False alarms (target 0), fixed in `3e93af3`

1. `runlog` warned "1 package(s) deviate from requirements.lock" on 6 of 6
   runs: the editable labkit froze as `-e git+…#egg=labkit`, a line the
   lock reader did not parse. It is now a VCS pin compared with the
   checkout's HEAD; the probe locks read drift 0.
2. At `cost = "seconds"` `finalize` and `protocol-check` listed 10 to 20
   placeholders of fields the cut does not owe (every agent named it as a
   time sink; it buried count-3's blocker). Now only the cut's fields count;
   `finalize` on the six probes: all clear.

## Still open

- The stamped area is the full form and the model skeleton when `lib exp`
  gets no `--cost`; every count agent read about 400 lines of model
  scaffolding and replaced `01_measure.py`. The scaffolder lives in the
  house templates, not here.
- With the full form stamped, `protocol-check` still names 2 or 3 lines of
  verbatim template prose at seconds.
- The null lane is the one place where agents had to think, and one in
  three got it wrong. A constant-answer placebo on balanced gold (judge-3:
  "Is the sentence written in English?") lands at chance by construction.
- Fixed in the follow-up: `protocol_fill.open_fields` parsed placeholders a second time (one home);
  it mis-read a label as `extremes)`.
