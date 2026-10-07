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

## Round 2: the route's stamp, after the fixes

The first round staged without `--cost`, although the README stages with
it; the count got the full form and the model skeleton. Fixed in the
harness (`d48ea40`: each task is stamped as the house route stamps it),
together with the two false alarms, a blocker recap in the last lines
(`ee4a043`), one field parser for `protocol-fill` (`20fbf52`) and the
placebo advice in the template and the measure skeleton (`d493968`).
Six new cold Sonnet agents at labkit `d48ea40`, scaffold flags `--cost
seconds` (+ `--model haiku` for judge). Scores:
`2026-10-07-sonnet-v2-{count,judge}-{1,2,3}.score.json`.

| run | number | truth / range | bound | wall-clock | gate / unsure lines | reads of source / standard |
|---|---|---|---|---|---|---|
| count-1 | 3.5 | equals truth | yes | 0m53s | 0 / 0 | 0 |
| count-2 | 3.5 | equals truth | yes | 0m56s | 0 / 0 | 0 |
| count-3 | 3.5 | equals truth | yes | 1m03s | 0 / 0 | 0 |
| judge-1 | 0.833 | in [0, 1], null 0.5 | yes | 2m04s | 0 / 0 | 0 |
| judge-2 | 1.0 | in [0, 1], null 0.5 | yes | 1m57s | 0 / 0 | 0 |
| judge-3 | 0.833 | in [0, 1], null 0.5 | yes | 2m04s | 0 / 0 | 0 |

Median wall-clock: count 0m56s (round 1: 1m16s), judge 2m04s (2m23s).
Every count agent filled the 97-line counting skeleton instead of
replacing a model script. All three judge agents chose the constant-answer
placebo the skeleton now names; every null lane landed at 0.5 and [C1]
passed. Not one gate line in six runs.

One false alarm left, fixed after the round (`6dacdc3`): before the first
run, the fields written after it (Answer, Raw output) were listed as open
placeholders; four of six agents read them in the commit hook as errors.

## Still open

Named by four or more of the six round-2 agents. None is a labkit error;
they are where the remaining minute goes.

- The repo `CLAUDE.md` (239 lines, house template) is read whole for a
  20-line seconds track (6 of 6).
- `protocol-check --contract` names the fields the seconds cut owes only in
  its last line (5 of 6).
- Multi-line `<…>` placeholders were filled by regex; no agent found
  `protocol-fill` (4 of 6).
- Judge: `00_prepare.py` must be written to copy twelve clean rows, and the
  stamped parser test fails until `PARSER_CASES` is filled by hand on a
  track without a probe (3 of 3).

Acted on (2026-10-07): the contract opens with the seconds cut and the
`protocol-fill` command, the template names `protocol-fill` (`ea741a7`); the
lab `CLAUDE.md` template points a seconds reader to its one section, the
prepare skeleton copies clean id/text/gold rows by default, the area test
carries the canonical answer forms and owes probe cases only above seconds
(house templates, dotfiles working tree). Not yet re-measured.

## Measured from the transcripts

`usability score <dir> --transcript <agent.jsonl>` (`8c9bbf4`) reads the
agent's session transcript beside its log. All twelve runs, log span vs
transcript (first to last record), tool time vs the rest (the model
thinking and writing):

| run | log | transcript | in tools | rest | calls | files opened | source reads log / transcript |
|---|---|---|---|---|---|---|---|
| r1 count-1 | 1:16 | 1:47 | 25 s | 82 s | 17 | 7 | 0 / 0 |
| r1 count-2 | 1:11 | 1:39 | 27 s | 72 s | 14 | 11 | 0 / 0 |
| r1 count-3 | 2:27 | 3:04 | 53 s | 131 s | 25 | 15 | 0 / 2 |
| r1 judge-1 | 2:23 | 2:52 | 68 s | 104 s | 20 | 12 | 0 / 0 |
| r1 judge-2 | 2:14 | 2:41 | 66 s | 95 s | 17 | 15 | 0 / 0 |
| r1 judge-3 | 2:35 | 3:03 | 67 s | 116 s | 22 | 19 | 0 / 0 |
| r2 count-1 | 0:53 | 1:17 | 23 s | 54 s | 13 | 7 | 0 / 0 |
| r2 count-2 | 0:56 | 1:25 | 22 s | 63 s | 15 | 10 | 0 / 0 |
| r2 count-3 | 1:03 | 1:26 | 20 s | 66 s | 15 | 12 | 0 / 0 |
| r2 judge-1 | 2:04 | 2:38 | 65 s | 93 s | 19 | 14 | 0 / 0 |
| r2 judge-2 | 1:57 | 2:24 | 100 s | 44 s | 17 | 15 | 0 / 0 |
| r2 judge-3 | 2:04 | 2:38 | 73 s | 85 s | 16 | 11 | 0 / 0 |

- The log misses 24 to 37 s per run: reading TASK.md before the first
  line and writing the report after the last. The medians move from
  0:56 / 2:04 (log, round 2) to 1:25 / 2:38 (transcript).
- Most of the wall-clock is the model, not the tools: 54 to 82 s of a
  count run is outside any tool call. Fewer files to read shortens that
  part too; the tools take 20 to 27 s.
- The log hid one source read: r1 count-3 called
  `inspect.signature(runlog.run)` and `inspect.signature(recheck.holds)`
  in a Python one-liner to learn the API (round 1, model skeleton
  replaced by hand). Round 2: none.
- r1 judge-3's "code-check refuses a relative area path" was a call from
  inside the area with the repo-relative path; the message now names the
  working directory it resolved against.

## Round 3: house templates after the four time sinks

Templates as committed in dotfiles `b099122` (the lab `CLAUDE.md` points a
seconds reader to its section and names `protocol-fill`; the prepare
skeleton copies clean rows; the area test carries the canonical answer
forms), labkit `dd82f3e` (`--contract` opens with the seconds cut and
`protocol-fill`). Scaffold sha `452851b23832`. Scores, now with the
transcript: `2026-10-07-sonnet-v3-{count,judge}-{1,2,3}.score.json`.

| run | number | right / bound | log | transcript | in tools | rest | calls | files opened | source reads |
|---|---|---|---|---|---|---|---|---|---|
| count-1 | 3.5 | yes / yes | 0:52 | 1:16 | 14 s | 62 s | 14 | 7 | 0 |
| count-2 | 3.5 | yes / yes | 0:53 | 1:21 | 17 s | 64 s | 16 | 9 | 0 |
| count-3 | 3.5 | yes / yes | 1:03 | 1:25 | 18 s | 67 s | 16 | 10 | 0 |
| judge-1 | 0.833 | yes / yes | 1:57 | 2:23 | 57 s | 86 s | 17 | 7 | 0 |
| judge-2 | 0.667 | yes / yes | 1:49 | 2:13 | 54 s | 79 s | 16 | 13 | 0 |
| judge-3 | 0.917 | yes / yes | 1:53 | 2:18 | 59 s | 79 s | 17 | 14 | 0 |

Median by transcript: count 1:21 (round 2: 1:25), judge 2:18 (2:38).
Every null lane at 0.5. judge-2's own prompt let haiku call five of six
non-causal sentences causal: 0.667 against a threshold of 0.75, [C1]
failed and was written back as failed — the chain held on a negative
result too.

- Five of six agents filled the protocol with `protocol-fill` (round 2:
  none). The transcript counts only calls in command position; agents
  that wrapped it in a shell function or variable are undercounted.
- Six of six still read the whole lab `CLAUDE.md` (246 lines): the pointer
  at its top says where to read, but not where the section ends.
- The two "refusals" the transcript flags (count-1, judge-1) are
  `protocol-check` must-field verdicts on a protocol not yet filled — no
  gate stopped work; the heuristic counts verdicts, not only blocks.
- "finalize printed twice" (two agents): the commit hook runs
  `finalize --if-reported`, then the agent ran it again in the same call.
- Fixed after the round (`41f09f7`): `--contract` wrote `(--list: what is
  open)` after the `protocol-fill` line; one agent read it as a
  `protocol-check` flag.

Remaining time is the model's own (62 to 86 s outside tools) — reading and
writing — and the prompt block, the one protocol part `protocol-fill`
cannot fill.
