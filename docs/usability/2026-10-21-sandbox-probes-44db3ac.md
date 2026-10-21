# Count and judge at `seconds` in an agent sandbox — 44db3ac (2026-10-21)

*The same six tasks as the 22483de series
([report](2026-10-20-cold-probes-22483de.md)), each agent now a headless
Claude Code in its own container instead of a subagent of the operator's
session. labkit run by the agents: **44db3ac**; scorer: **b6019d2**. All six
numbers bound, the count right every time, no gate refusal, no path used
outside the probe but the log the task names. The friction left has one
cause: `labkit-audit --decide` numbers only the recorded findings, the
audit prints more, and five of six agents tried to decide what it does not
record. Costs are measured for the first time: 0.39–0.88 USD a probe.
Scores: `2026-10-21-sandbox-44db3ac-<probe>.score.json`, costs
`…-<probe>.costs.json`.*

## Setup

- **Sandbox:** labkit-paper's `agentsandbox`, used by a runner script in
  the series' workspace (`~/projects/labkit-probes-sandbox-44db3ac/run.py`;
  imported, not copied). Per attempt a fresh container, nothing of the
  host inside (no home, no `~/.claude`, no mounts; the probe copied in and
  out), an internal network whose only exit is a proxy holding the
  subscription token and passing `/v1/messages` alone; the agent holds a
  placeholder.
- **Image:** `labkit-probe-sandbox:44db3ac` — labkit-paper's
  `labkit-sandbox:285b82a5a7a3` (Claude Code 2.1.285, Python 3.12.13,
  pytest 9.1.1) with labkit replaced by a wheel of `git archive 44db3ac`
  (sha256 recorded, checked inside the image). No push; labkit-paper
  unchanged.
- **Probes:** stamped on the host by `usability stage` of 44db3ac, then
  moved to the container's paths (TASK.md's log to `/out/probe.log.md`,
  the prompt's repository to `/work`, the host `.venv` link dropped). In the
  container before the agent: `.venv` under `/work` offline from the
  wheel, git identity `sandbox`, the hooks, `requirements.lock`, one
  commit. Agent: `claude -p --setting-sources project`, model
  `claude-sonnet-5-5`, one after another, limits 1800 s · 200 turns ·
  5 USD.
- **What differs from 22483de:** the agents are headless processes, not
  subagents; the probe's own Claude hooks fire (they never did for a
  subagent); the shell starts in the probe. Results compare with care.
- **Scoring:** on a copy of each agent's session transcript with `/work`
  mapped to the copied-back tree, by labkit b6019d2 (it reads Claude Code
  2.1.285's bookkeeping records and takes the probe as `cwd` as proof of
  the transcript; both fixed during this series, `c8f7c9f`, `b6019d2`).
  The scorer never entered the sandbox.

## Isolation, as far as tested

Two checks before the series. A shell stand-in without a model: no
`/Users`, no `~/.claude`, `/tmp` holds the image's files only, no host
mounts but Docker's `resolv.conf`/`hostname`/`hosts`, the placeholder is
the only credential, no DNS or internet, the proxy refuses `/v1/models`
(403). An agent (haiku) told to read host files with Read and Bash: none
reachable, no internet, `/tmp` the container's own; the
`CLAUDE_CODE_MESSAGING_TOKEN` it saw is set by the `claude` process inside
the container (the container receives three variables; the shell check
shows none such) — not the subscription token. In all six probes the
score lists one path outside the probe: `/out/probe.log.md`, the log the
task names.

What this shows: the host file system and direct network access are
restricted by the setup, and the accesses tried failed. Two checks show
the tested limits — not a complete isolation. Shared by construction: the
Docker daemon and the proxy's one path.

## Result

| probe | number | bound | log span | refusals | misuse | gate | outside | repairs | hook output |
|---|---|---|---|---|---|---|---|---|---|
| count-1 | 3.5 ✓ | yes | 1m54s | 0 | 1 (`--decide 3`, record holds 2) | 0 | 2 (agent's own `ls`, `git check-ignore`) | 0 | 3 |
| count-2 | 3.5 ✓ | yes | 1m45s | 0 | 0 | 1 (the audit's warning, exit 1) | 0 | 0 | 3 |
| count-3 | 3.5 ✓ | yes | 1m31s | 0 | 2 (`--decide 1`, `2`, record holds 0) | 0 | 0 | 0 | 3 |
| judge-1 | 0.8333 | yes | 3m18s | 0 | 4 (`--decide 3..6`, record holds 2) | 0 | 0 | 0 | 4 |
| judge-2 | 0.8333 | yes | 2m42s | 0 | 2 (`--decide 4, 5`, record holds 3) | 0 | 0 | 1 (Raw output, after the post hook) | 4 |
| judge-3 | 0.8333 | yes | 2m20s | 0 | 4 (`--decide 3..6`, record holds 2) | 0 | 0 | 0 | 4 |

Misuse counted per refused call. The candidate script of the 22483de
series (marks such as Traceback, `Exit code N`, `no such`) found the
`--decide` refusals in the count runs only; in the judge runs the calls
were chained and the refusal text carries no mark — they were counted
from the transcripts (`no finding N — the record holds finding 1..M`),
and the agents' own reports name them.

- **Against 22483de:** misuse calls 1 → 3 (count), 0 → 10 (judge); every
  one of them is the new `--decide` meeting an unnumbered list. The classes
  fixed before (TOML quoting by hand, the area name, the bare `--from-run`
  file name, open promise sentences) did not recur. All refusals named the
  range; none damaged a record.
- **Wall-clock**, alongside: all six under five minutes (median count
  1m45s, judge 2m42s). Different harness — no speed comparison.
- **Judge numbers:** 0.8333 in all three, one draw each.

## Agent reports, checked against 44db3ac

1. **The audit prints more than `--decide` can reach.** The auditor writes
   BLOCKER, WARNING and READ lines (judge-1: 2, 2 and 6); the record keeps
   the lines `FINDING` matches — BLOCKER, WARNING, NOTE
   (`labkit/gates/audit.py:120`). READ lines are printed and never
   recorded, and no output says which number belongs to which finding.
   Five agents numbered what they saw; count-3 logged "findings are
   unlisted (notes hidden); deciding 1 and 2 blind".
2. **`--from-run` leaves Raw output open** and the post hook flags it
   (judge-2): one more `protocol-fill`. Noted.
3. **Reading the stamped skeleton** stays the largest non-waiting cost
   (judge: `01_measure.py` 436 lines for about six edits) — the TODO row
   "Zählvorlage aus Task-Feldern" again.
4. **The analysis audit** stays the largest wait (about 1–2 minutes) and,
   in the count runs, about half the cost.

## Costs, measured

| probe | agent USD | nested USD | total USD | sessions |
|---|---|---|---|---|
| count-1 | 0.218 | 0.235 | 0.453 | 2 |
| count-2 | 0.191 | 0.225 | 0.416 | 2 |
| count-3 | 0.199 | 0.188 | 0.388 | 2 |
| judge-1 | 0.272 | 0.612 | 0.884 | 26 |
| judge-2 | 0.259 | 0.515 | 0.774 | 26 |
| judge-3 | 0.255 | 0.458 | 0.713 | 26 |

Per session its `cost-state` record, a CLI estimate at list price. The
agent's `total_cost_usd` holds its own model only; the nested sessions are
labkit-audit (opus) and, in the judge, the 24 `haiku` calls of the
measurement. Cross-checked per probe against the proxy (input side from a
reply's start event, output from its end event): every token count of
every model equal. Series total 3.63 USD, plus the isolation check with a
model, 0.035 USD.

Found on the way, in labkit-paper (noted in its
`notes/messung/agent-sandbox-bauplan.md`, not changed here):
`agentsandbox.ClaudeCode.usage` sums both events and counts the input side
twice; the token figures of its manifests in areas 08 and 09 run high.

## What the sandbox package needs, from these runs

Used: one attempt (networks, proxy, container, copy in and out, time
limit, seal, manifest); the proxy with placeholder and path allow-list;
the Claude Code adapter with a setup step before the agent and `TMPDIR`
in the probe; the agent's session found by its project directory among
the nested ones; costs per session with the proxy cross-check (the
corrected count); the two isolation checks; an image derived with a
caller's wheel. Not used: `batch`, `benches`, `arms`, `standard_check`.
Stays with the caller: staging the probe and moving it to the sandbox's
paths, the token from the keychain, scoring.

## Consequence

- Fix next in labkit: `labkit-audit` prints the recorded findings with
  their numbers after recording, and says what READ lines are (printed, not
  recorded, nothing to decide) — or records them; to decide with the
  owner.
- The sandbox package: extract next, scope as above, its own repository.
- No probe touched the host beyond the tested limits; the measurement now
  carries its cost.
