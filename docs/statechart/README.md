# Statechart pilot: one area's lifecycle as a checked model

Pilot of 2026-11-27, on the branch `statechart-pilot`. It tries the `/statechart` skill of pstack (github.com/cursor/plugins, `pstack/skills/statechart`): a TLA+ model, checked by TLC, drawn as a Mermaid statechart.

## What the model holds

`AreaLifecycle.tla` models one area at repeat cost low with one protocol and one registered report. Each action is a command an author runs. Its guard is what that command checks, read from `docs/gate-stations.md` and the code:

- `finalize.finalize_area`
- `report_check.chain_gaps`
- `report_check.hold_changed_paths` with `scope_sha.areas_touched`
- `hook_pre_run.before_run`
- `labkit-adopt`

The ten INVARIANTs are the promises of `docs/workflow.md`. They are stated on the last commit, because the commit hook is where labkit promises them.

## What it leaves out

- repeat cost high: preflight, freeze and instrument probe
- exploratory steps between runs
- derived runs
- several protocols or areas
- `--no-verify` commits and the stop hook
- rejected reviews
- the report review's verdicts

The model is not the code. A path that breaks a rule here counts as a finding only after it is replayed against the real commands.

## Result

- `out-overview/`: `MaxRuns = 1`, `MaxEdits = 0`. TLC finds 361 states, and all ten rules hold. The chart shows the whole lifecycle.
- `out-full/`: `MaxRuns = 2`, `MaxEdits = 1`. One rule breaks: `CommittedNumberFromDataAsRun`. The path is: adopt, commit, change a data file that lies outside the area and outside every promise's scope, commit again. The hook lets the second commit through, because `areas_touched` does not reach the area. The run's recorded inputs are not among what it reads. The other nine rules hold over 202 523 states (`out-full/tlc-nine-rules.log`).
- Replayed on the count walkthrough (`docs/examples/count-walkthrough.sh`), whose run reads `data/raw/cases.jsonl` at the lab root:
  - Dropping the last case and committing that file alone exits 0 through the pre-commit hook.
  - `report-check experiments/01-docs-per-case` then exits 1 with two blockers: the provenance check ("is not the bytes the run read") and `02_analyze.py --check`.
- Mutation check: two guards were weakened, finalize's code comparison and the hold of a missing report. TLC then reported the matching rule broken each time. So these two rules are not vacuous.

## Run it again

Needs Node ≥ 22.18 and Java ≥ 11. The skill's scripts are in a checkout of the pstack plugin. `tla2tools.jar` v1.7.4 has sha256 `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`.

```sh
TLA2TOOLS=/path/to/tla2tools.jar JAVA=$(which java) \
  /path/to/pstack/skills/statechart/scripts/statechart AreaLifecycle.tla \
  --config Overview.cfg --view view.ts --out /tmp/sc-overview
```
