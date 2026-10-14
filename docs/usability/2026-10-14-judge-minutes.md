# Judge at `minutes` — a cold Sonnet agent, draw 1 (2026-10-14)

*First probe of the judge task staged at `cost = "minutes"`, meant to walk
the full lane (registration, render and instrument checks, preflight, agent
audit, freeze, detached run, finalize, analysis audit). It did not: the
agent moved the head to `seconds` and took the short lane. What it hit on the
way were four faults of labkit's own stamp, all fixed the same day. Score:
`2026-10-14-sonnet-judge-minutes-1.score.json`.*

## Setup

- `usability stage ~/projects/labkit-probe-judge-1 --task judge --cost
  minutes --venv <labkit .venv>` at labkit `4d37c52` (0.89.0 unreleased; the
  stamped pin says v0.88.8, the linked venv runs the checkout). Scaffold sha
  `d81d18828045`.
- Agent: Sonnet as a subagent of the operator's Claude Code session, handed
  `<probe>.prompt.md` verbatim (AGENTS.md + the TASK.md pointer). As a
  subagent it runs outside a session started in the probe, so the probe's
  Claude hooks (`pre-run`, `post-change`, `stop`) did not fire; the git
  pre-commit hook and `runlog` did. Same as the 2026-10-07 re-measure.
- Model in the loop: `haiku` through `claude -p`, 24 calls (12 registered,
  12 null lane), 31 s.

## Result

| | |
|---|---|
| number (`c1_accuracy`) | 0.8333 (10 of 12; misses c08, c12, both not_causal called causal) |
| null lane (`a2_accuracy`) | 0.5, [A2] passes; [C1] passes (threshold 0.75) |
| bound, frozen, tier | yes · no · **seconds** (staged `minutes`) |
| log span / transcript | 2m28s / 2m51s |
| read · run · edit · unsure · gate | 6 · 16 · 4 · 1 · 3 |
| labkit source or standard read | 0 |

The number is right and bound; the lane is not the one staged.

## Findings, each checked against the code

1. **The tier was not held (probe design).** TASK.md said "twelve calls take
   about a minute" and nothing about the stamped tier; the agent logged
   `unsure · head says cost=minutes but task is seconds-lane; switching head
   to seconds`. Changing the tier before the freeze is legitimate in a real
   repo, so labkit stays silent on it; the probe has to say what it
   measures. Fixed in `d0ad9cc`: the sheet names the stamped tier and asks
   to keep it (`usability.tier_sentence`). The sheets also still said
   `CLAUDE.md` is in context while the prompt hands AGENTS.md since
   `4d37c52` — fixed in the same commit.
2. **The stamped prepare step refused (gate, labkit fault).** runlog refuses
   any run under the promise block whose config lacks a registered constant;
   `00_prepare.py` passed none. Every area with a model refused at its first
   step. Fixed in `93e2940`, with a test that runs a freshly stamped prepare
   step.
3. **`02_analyze.py --check` failed right after `--from-run` (gate, labkit
   fault).** The write-back wrote `0.8333333333333334`, the skeleton looked
   for `0.8333`; recheck matches whole tokens. The agent reworded the
   protocol by hand. Fixed in `cca7136`: the skeleton uses recheck's default,
   the form --from-run writes.
4. **`--from-run` never wrote the Answering run line (silent skip, labkit
   fault).** The stamp's `none yet — …` is no `<…>` placeholder; `fill` read
   it as filled and `from_run` swallowed that error. The agent wrote the line
   by hand. Fixed in `ec2dc52`: one answer for "open"
   (`protocol_check.answering_run_open`), shared with finalize; another
   run's id is refused, not skipped.
5. **A WARNING from labkit's own skeleton.** `code-check` flagged the
   stamped `02_analyze.py`'s `spec_from_file_location(… AREA / "scripts" /
   "01_measure.py")` as code the stamp cannot follow; the agent had to judge
   it. Fixed in `6f740a8`: loading a file the area's stamp covers is silent.

Not checked, from the agent's report: `protocol-fill --list` counting more
open fields after `--prompts` ("Model I/O reappeared"); finalize warning on
README placeholders and an untracked output file. Noted in TODO.md.

## Next

Draw 2 on the fixed stamp, same setup: does the agent keep `minutes` and
walk the full lane, and where does that lane cost time? For the Claude hooks
to count, start `claude` in the probe directory instead of a subagent.
