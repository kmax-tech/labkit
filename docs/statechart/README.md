# Statechart pilot: one area's lifecycle as a checked model

Pilot of 2026-11-27 on the branch `statechart-pilot`. It tries the `/statechart` skill of pstack (github.com/cursor/plugins, `pstack/skills/statechart`). The skill checks a TLA+ model with TLC and draws it as a Mermaid statechart.

## What the model holds

`AreaLifecycle.tla` models one area with one protocol and one registered report. Its constant `Lane` sets the repeat cost to `"low"` or `"high"`.

Each action is a command an author runs. Its guard is what that command checks, read from `docs/gate-stations.md` and the code:

| Command                    | Guard taken from                                                                                                         |
|----------------------------|--------------------------------------------------------------------------------------------------------------------------|
| start a measurement        | `start_check.freeze_gate`: an undecided preflight BLOCKER refuses; low needs the committed registration, high the freeze |
| start a probe              | nothing; `runs.unreportable` marks it                                                                                    |
| `protocol-fill --freeze`   | registration written, preflight audit decided                                                                            |
| `labkit-adopt`             | `report_check.chain_gaps` on the proposal, without the report station                                                    |
| `git commit`               | `report_check.hold_changed_paths`, for the areas `scope_sha.areas_touched` reaches                                       |
| finalize, inside the chain | answering run, registration, code, provenance (low only)                                                                 |

The fourteen INVARIANTs are the promises of `docs/workflow.md`. Except for one, they are stated on the last commit, because the commit hook is where labkit promises them. The exception, `NoMeasurementWithoutRegistration`, is stated on the working state.

## What it leaves out

- exploratory steps between runs and `[builds_on]`
- derived runs
- `LABKIT_UNFROZEN=1`
- several protocols or areas
- `--no-verify` commits and the stop hook
- rejected reviews and the report review's verdicts
- unfreezing, and editing a frozen protocol before its first run

The model is not the code. A path that breaks a rule here counts as a finding only after it is replayed against the real commands.

## Result

Each data rule states the requirement at every repeat cost: an adopted number stays bound to the inputs it was measured on. The protection is a separate matter. finalize's byte comparison (provenance) runs at low only (`labkit/gates/finalize.py:1338`, "the agent audit covers provenance there"), and the model keeps that guard as the code has it.

| Config                                | Rule or rules                      | States     | Result                                  |
|---------------------------------------|------------------------------------|------------|-----------------------------------------|
| `low-overview.cfg` (1 run, no edits)  | all 14                             | 743        | hold; chart `out-low/chart.mmd`         |
| `high-overview.cfg` (1 run, no edits) | all 14                             | 4 649      | hold; chart `out-high/chart.mmd`        |
| `low-full.cfg` (2 runs, 1 edit each)  | `CommittedNumberFromDataAsRun`     | —          | breaks (`out-before/low-bug/`)          |
| `low-full.cfg`                        | `CommittedNumberFromAreaDataAsRun` | 3 050 849  | holds (`out-low/tlc-area-low.log`)      |
| `low-full.cfg`                        | the other 12                       | 3 050 849  | hold (`out-low/tlc-rest-low.log`)       |
| `high-full.cfg` (2 runs, 1 edit each) | `CommittedNumberFromDataAsRun`     | —          | breaks (`out-before/high-bug/`)         |
| `high-full.cfg`                       | `CommittedNumberFromAreaDataAsRun` | —          | breaks (`out-before/tlc-area-high.log`) |
| `high-full.cfg`                       | the other 12                       | 28 232 777 | hold (`out-high/tlc-rest-high.log`)     |

Two gaps, each replayed against the real commands:

1. **The reach.** `areas_touched` does not read the inputs a run recorded. So a commit that changes only a data file outside the area does not reach the area. Replayed on the count walkthrough at low (`docs/examples/count-walkthrough.sh`, whose run reads `data/raw/cases.jsonl` at the lab root):
   - Dropping the last case and committing that file alone exits 0 through the pre-commit hook.
   - `report-check experiments/01-docs-per-case` then exits 1 with two blockers: provenance, and `02_analyze.py --check`.
2. **The comparison at high.** At high, finalize compares no input bytes, so a changed input passes even when the gates reach the area. Replayed on the high scenario of `tests/test_end_to_end.py` (`Estimator`: preflight, freeze, measurement, adoption, commit). One gold label was flipped in the area's write-protected `data/prepared/points_v1.jsonl`, and in the lab's `data/raw/points.jsonl`. For both files, pre-commit and `report-check AREA` exit 0 with "frozen, finalized, audited, checked" and 0 blockers. The stop hook also exits 0, but in that fixture it had no stop base, so it says nothing. The throwaway test and its log are kept outside this repo, in `labkit-evidence/2026-11-27-statechart-replay/`.

Both gaps are entered in `TODO.md`, under "Bekannte Grenzen" 17 and "Offene Entscheidungen" 10. The model checks recorded inputs only. That a run recorded every input it read is not shown by it.

## After the repair

The author approved both changes on 2026-11-27. With the two guards in the model, all 14 rules hold on both lanes: 3 035 489 states at `low` and 27 752 137 at `high` (`out-after/`). The tables above show the model before the repair, and `out-before/` keeps its counterexamples. The guards are:

- finalize compares each recorded input's bytes on every repeat cost (`file_record_check.recorded_bytes_findings`);
- the stop and the commit reach an area through the inputs its adopted run recorded (`scope_sha.adopted_inputs`).

Both replays are scenario tests: `Count.test_06_…` and `Estimator._a_changed_input_holds_the_adopted_number`. Both fail on the code before the change.

Mutation check: four guards were weakened, and TLC reported a broken rule each time:

| Guard weakened                             | Rule TLC reported broken                                                      |
|--------------------------------------------|-------------------------------------------------------------------------------|
| finalize's code comparison                 | `CommittedNumberFromCodeAsRun`                                                |
| the hold of a missing report               | `CommittedMeasurementHasReport`                                               |
| the freeze at a measurement's start (high) | `NoMeasurementWithoutRegistration`, and alone `CommittedNumberMeasuredFrozen` |
| the full-run station of the chain          | `CommittedNumberFromMeasurement`                                              |

## Reading the high lane

At the commit, the chain asks only whether the protocol is frozen *now* (station 2, `freeze_gaps`). That the measurement *ran* on a frozen protocol rests on the start check in runlog alone. Without that guard, the model reaches a committed number from a measurement started before the freeze. This is a design observation, not a replayed finding: a run record is trusted to have passed its start check.

## Run it again

Needs Node ≥ 22.18 and Java ≥ 11. The skill's scripts are in a checkout of the pstack plugin. `tla2tools.jar` v1.7.4 has sha256 `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`. Before running, raise `CHART_STATES` in `scripts/ir.ts` from 500 to 5000; without it, the overviews (743 and 4 649 states) draw no chart.

```sh
TLA2TOOLS=/path/to/tla2tools.jar JAVA=$(which java) \
  /path/to/pstack/skills/statechart/scripts/statechart AreaLifecycle.tla \
  --config high-overview.cfg --view view.ts --out /tmp/sc-high
java -XX:+UseParallelGC -jar /path/to/tla2tools.jar -config high-full.cfg -workers 4 AreaLifecycle.tla
```
