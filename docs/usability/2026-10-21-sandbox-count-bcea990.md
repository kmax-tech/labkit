# Count at `seconds` in the agentsandbox package — labkit bcea990 (2026-10-21)

*Three cold count probes, the first run through the extracted
`agentsandbox` package (1e0c557) instead of labkit-paper's copy. labkit run
by the agents and scorer: **bcea990** (it holds the `--decide` numbering,
the closed TOML block of the count stamp and both scorer fixes). All three
numbers right and bound, no gate refusal, no misuse of labkit, no repair,
nothing used outside the probe but the task's log. The `--decide` friction
of the 44db3ac series is gone. What is left are three findings on the
count's stamp and the standard, found by the audit and the agents' reports.
Scores and costs: `2026-10-21-sandbox-bcea990-<probe>.{score,costs}.json`.*

## Setup

- **Runner** `~/projects/labkit-probes-sandbox-bcea990/run.py` on the
  `agentsandbox` package (installed from 1e0c557): the attempt, the proxy,
  the Claude Code adapter with its setup step (the probe's `.venv` under
  `/work` from the wheel, git identity, hooks, lock, one commit), the
  costs. Token from the keychain, staging on the host and scoring stay in
  the runner.
- **Images** `agentsandbox-agent:8547fbd3b04c` and
  `agentsandbox-proxy:a8c0140296d2` (the package's), the probe image
  `labkit-probe:99a1bc588a26` derived with labkit as a wheel of
  `git archive bcea990` and pytest 9.1.1. `agentsandbox selftest` against
  these images before the series: 20 of 20 held (shell and agent check).
- Model `claude-sonnet-5-5`, one probe after another, the same task sheet
  and fixture as before.

## Result

| probe | number | bound | log span | misuse | gate | outside | repairs | `--decide` | total USD |
|---|---|---|---|---|---|---|---|---|---|
| count-1 | 3.5 ✓ | yes | 1m47s | 0 | 1 (the audit's warning, exit 1) | 0 | 0 | 1 of 1 | 0.411 |
| count-2 | 3.5 ✓ | yes | 1m39s | 0 | 1 (the audit's warning, exit 1) | 0 | 0 | 1 of 1 | 0.397 |
| count-3 | 3.5 ✓ | yes | 1m42s | 0 | 0 | 1 (the agent's own `ls` of a wrong path) | 0 | 2 of 2 | 0.419 |

Classified as in the 22483de and 44db3ac series (candidates from the
marks, read one by one, plus the transcripts searched for `no finding N`).

- **Against the 44db3ac count runs:** misuse 3 → 0; every agent decided
  exactly the recorded findings, by the numbers `labkit-audit` now prints,
  with no refusal. Wall-clock median 1m45s → 1m42s, costs 0.39–0.45 →
  0.40–0.42 USD; same harness, three runs a side — no speed claim.
- **Costs:** agent about 0.19 USD, the nested analysis audit about
  0.22 USD — more than half of every probe; cross-checked at the proxy.

## Findings, checked against bcea990

1. **The count's fixture and its skeleton freeze different things.** The
   fixture gives every case its own `inputs` path (`cases.jsonl`:
   `{"case_id": …, "inputs": "data/raw/inputs"}`); the skeleton freezes the
   constant `INPUTS` (`measure-quick-script.py.template:80`). Every agent
   read the path from the record, so the number follows a value the run
   does not freeze — the analysis audit warned in all three runs, rightly,
   and every agent dismissed it after checking that all twelve values
   equal `INPUTS`. Either the skeleton reads the case directories from
   `INPUTS` and refuses a record that names another, or the fixture drops
   the per-record path. To decide.
2. **The standard does not state that a count owes no criterion.** The
   exemption — a count at `seconds` whose prose names no `[C]/[A]/[B]` id
   owes no promise table and no criterion — lives in the code
   (`labkit/formats/promises.py:371`, since 0.87.1) and in the stamped
   AGENTS.md, not in `labkit/docs/standard.md`, which the auditor reads
   (searched for the code's own wording; the control search for a known
   passage finds it). In count-3 the audit asked for a criterion and a
   `[[promise]]` table "standard 0.19 requires at seconds"; the agent
   dismissed it, citing the lane.
3. **The skeleton under-counts its own blanks.** Its docstring says "Fill
   the constants and the three TODOs" (`measure-quick-script.py.template:13`);
   `INPUTS` carries a TODO of its own, and one agent left its comment
   behind.
4. **The second commit before `finalize`** (output and runs) is named only
   in the lane text; two agents called it easy to miss. Noted, not a fault:
   `finalize` checks it.

## Consequence

- Next in labkit, in order of evidence: (1) the count's frozen inputs
  (every run), (2) the count exemption into the standard (an audit false
  positive in one of three), (3) the skeleton's docstring.
- The package carried the series without a change; labkit-paper moves to it
  as its own task.
