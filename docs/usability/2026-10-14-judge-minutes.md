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

## Draw 2 — the cloud, the full lane (labkit 0.89.0)

Probe repo `kmax-tech/labkit-probe-judge` (private), stamped with `usability
stage --task judge --cost minutes` at v0.89.0, venv rebuilt from the GitHub
tag, the cloud edits of the count probe (branch `probe-judge`, `log.md` in the
repo, SessionStart hook). Agent: Sonnet in a claude.ai/code session; `claude
-p` is logged in there, so haiku and the opus audits ran. Score (log only, no
transcript from the cloud): `2026-10-14-cloud-sonnet-judge-minutes-2.score.json`.

| | |
|---|---|
| number | 0.8333 (10 of 12), null 0.5, run `2026-10-14T13-13-29_403f` |
| bound, frozen, tier | yes · **yes** · **minutes** — the full lane, kept |
| log span | 22m35s (12m14s of silence; net 10m21s) |
| read · run · edit · unsure · gate | 4 · 16 · 9 · 0 · 1 |
| labkit source or standard read | 0 |
| audits | preflight: 7 warnings, 1 note (6 fixed, 2 accepted); analysis: 3 warnings, 2 notes |

The tier sentence held: the agent walked render check, probe, code-check,
preflight, the opus preflight audit, the report fields, the freeze, `runlog
start`, finalize, the write-back and the analysis audit.

### Findings

1. **The audits caught real faults.** The preflight audit found a labkit
   template fault: [C1] compared floats, so a lane exactly at null + margin
   failed (5/12 + 0.25 > 8/12 by one ulp) — fixed in `fcc083d`, the
   comparison is in fractions. It also found the readable-only denominator
   against the agent's "all twelve are scored" (a mismatch between the
   skeleton's default and the registration, decided by the agent). The
   analysis audit found a count the agent had retyped wrong into the
   protocol (three "No" where the rows show four) — LAB-041 Generate numbers,
   don't retype them, caught by the audit, not by a gate.
2. **Most of the time was waiting on finished audits.** Each opus audit took
   about 2.5 min (files written 13:03 and 13:16), past the shell's 120 s
   foreground limit; the agent backgrounded it and waited with `until … !
   pgrep -f labkit-audit`, which matches its own command line and never ends.
   The log resumes at 13:12 and 13:21: about 14 of the 22 minutes. Step 7 of
   the AGENTS.md template now says to wait for the background task
   (`c2b794a`).
3. **A stamp no audit saw.** After fixing the preflight findings the agent
   wrote the new scope sha into the head without a second audit, and said so
   in the head ("audited at 041c2f50a1a5"). preflight checks that every
   finding is decided and runlog that the stamp matches the code now; nothing
   holds the stamp to a sha an audit record carries. Open as a rule
   question (TODO.md).
4. **`runlog start` writes its log relative to the working directory**
   (`output/start-<ts>.log` at the repo root when started from there, as the
   sheet says), so the agent looked for it in the area. Noted.
5. **Not labkit:** the push was refused (403) until the Claude GitHub App was
   granted the new repo; the cloud setup script's `cd "$CLAUDE_PROJECT_DIR"`
   did not reach the repo on the first try (an `echo` setup plus the
   SessionStart hook worked).

## Draw 3 — the cloud on 0.90.0

Same repo, re-stamped at v0.90.0 (`usability stage --restamp`), branch
`probe-judge-2`, same prompt. (A first attempt opened the count repo
`labkit-probe` by mistake and counted there on 0.88.7 — not a draw of this
series; its one finding, `protocol-fill --list` listing Result and Answer
among the fields owed before the run, held on 0.90.0 and is fixed in
`897c9c4`.) Score: `2026-10-14-cloud-sonnet-judge-minutes-3.score.json`.

| | draw 2 (0.89.0) | draw 3 (0.90.0) |
|---|---|---|
| number | 0.8333 | 0.9167 (11 of 12) |
| frozen, tier | yes · minutes | yes · minutes |
| log span / net of silences ≥ 10 min | 22m35s / 10m21s | 15m30s / 5m12s |
| preflight audits | 1, stamp rewritten by hand afterwards | **2** — the head carries the second audit's sha |
| start log | repo root | the area's `output/` |

What held: the strict gate (`35d406b`) — after the first audit's blocker
the agent fixed the code and audited again (`97c1b40e024d` → `ff25b350978c`),
the head names the second; `runlog start AREA` put the log in the area.

What did not:
1. **The first audit's wait again.** Audit started 14:15, its record is dated
   14:17, the log resumes 14:25: about 8 minutes. The agent ended its turn to
   be woken by the background task (as the template now says); the labkit
   Stop hook re-prompted it on the way (a WIP commit). Where the minutes went
   is not visible without the cloud transcript.
2. **The denominator, second time.** Both cloud draws' preflight audits
   flagged that the skeleton's accuracy divides by readable answers while
   the registration says "over all twelve". A skeleton default every audit
   flags is a decision to take, not a finding to repeat (TODO.md).
3. **`labkit-init exp --report` from the area directory** called it "not a
   lab repo" — fixed in `feb3387`: it walks up to the lab as git does.
4. **Not done:** the result note and `02_analyze.py --check`; finalize was
   green without them.
5. **Probe, not labkit:** the run is `+dirty` by `log.md` alone — the agent
   pushed a WIP commit with the log tracked, and the next log line changed
   it.

## Draw 4 — the cloud on 0.91.1: the whole lane, report-check clean

Re-stamped at v0.91.1, branch `probe-judge-3`, same prompt. Score:
`2026-10-14-cloud-sonnet-judge-minutes-4.score.json`.

| | draw 2 (0.89.0) | draw 3 (0.90.0) | draw 4 (0.91.1) |
|---|---|---|---|
| number | 0.8333 | 0.9167 | 0.8333 |
| log span | 22m35s | 15m30s | **7m26s** |
| wait on a finished audit | ~14 min | ~8 min | none (audit 15:46 → read 15:48) |
| preflight audits | 1, stamp by hand | 2 | 1, no code change after it |
| analysis audit, `--check`, `report-check` | audit only | none | **all three, clean** |
| denominator finding | yes | yes (blocker) | no |

`report-check` is clean in the cloud and, run on a fresh local clone of the
branch, clean here too: the repo-relative paths of 0.91.x hold off the
machine that measured (draws 2 and 3 failed `--check` locally on absolute
paths).

Findings:
1. **Placeholder promise sentences in a frozen head.** The three `[[promise]]`
   sentences stayed as stamped (`<the criterion in one sentence: …>`); the
   agent said so. Only an empty sentence is refused (`promises.py:219`); a
   stamp placeholder is frozen, hashed into the run's block digest and passes
   preflight, finalize and report-check. Open as a decision (TODO.md).
2. **The strict audit rule pulls toward "accepted".** The agent: "Fixing code
   after an audit changes the scope sha and means re-auditing. So I recorded
   the code-level findings as accepted or deferred." Statuses over both audits:
   8 accepted, 3 fixed, 2 dismissed, 1 deferred. Draw 3 fixed and re-audited.
   One draw; worth watching, not yet a finding about the rule.
3. **The probe, not labkit:** the agent committed the cloud `.venv/` (1969
   files) with a broad `git add -f` — the sheet said "add it with `git add -f
   log.md`". The sheet now says `-f` for that one file only.
4. From the report, unchecked: `protocol-fill` refuses a whole multi-field
   call when one field is filled (by design: all or nothing).

## Next

The full lane is measured three times (draws 2–4); draw 4 is the first that
walks it to the end.

## Next

The full lane is measured twice.
## Next

The full lane is measured once. Before more draws: decide finding 3, and
whether a 12-call count at `minutes` should owe two opus audits at all (the
agent's own cut: the seconds lane owes eight fields and no audit).
