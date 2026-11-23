# A preparation run held to the measurement's promises

Investigation and change, 2026-11-23. Part 1 of the proposal is built (`finalize.check_source_protocols`, scenario `tests/test_origin_scenario.py`, `PreparationOfTheOnlyProtocol`), and so are the standard's clause and the auditor's text (last section); part 2 waits for the author (TODO, open decision 8).

## The case

argmining27, experiment 12 (`experiments/12-generated-scenario-stability`), labkit 0.114.0. One script, two stages:

| Run                        | `run_kind`    | `protocol=` in the script | Recorded binding                                |
|----------------------------|---------------|---------------------------|-------------------------------------------------|
| `2026-11-23T18-28-40_d9e1` | `preparation` | not given                 | `p-1b7e6d4f9f4949be` (the area's only protocol) |
| `2026-11-23T19-18-55_2038` | `measurement` | given                     | `p-1b7e6d4f9f4949be`                            |

The protocol says in Setup: "`--stage scenarios` is a preparation run bound to no protocol". The measurement reads the scenario file the preparation wrote; its start recorded the preparation as that input's origin. The measurement's metrics report every registered key, `quality_check_1_pass` and `quality_check_2_pass` among them.

Reproduced on a copy of the repository (argmining27's own venv, 0.114.0, and labkit `main` at `d84d1262`): `finalize` exits 1 with four blockers, all "origin run 2026-11-23T18-28-40_d9e1, held to the protocol as it saw it": no `quality_check_1`/`quality_check_2` key, and the declared keys `quality_check_1_pass`/`quality_check_2_pass` not reported. No other blocker. The way out it offers, "measure the origin anew", would mean new scenarios, new model calls and a new hand check.

## Cause

Two rules that each hold alone disagree on a preparation.

1. **Binding at the start** (`run/start_check.protocol_binding`): a run without `protocol=` binds to the area's only protocol, whatever its `run_kind`. There is no way to say "bound to none" while the area has one protocol: `protocol=None` means "the only one".
2. **The origin's promises at finalize** (`gates/finalize.check_source_protocols` → `checks/intent_check.origin_intent_findings`, its only call): a bound origin run must report every promise its text registered, as an answering run must. That was built for an origin that is itself a measurement of another protocol (`tests/test_origin_scenario.py`, `TwoProtocolsOfOneArea`).

The standard and the docs assume a preparation is unbound: "An origin run bound to no protocol, such as a preparation, owes no text" (`labkit/docs/standard.md:331`), and the 2026-11-17 decision "Required means the origin run recorded a protocol id" (`docs/notes/2026-11-14-exploratory-workflow-plan.md`). The README says a preparation "cannot supply a reported result". In every area with one protocol, a preparation is bound, and its output's reader then owes the preparation the measurement's keys. The tests did not see it: the station's origin runs are unbound because their area has no protocol, and none is a preparation (`tests/test_origin_check.py`, `_Area`, `Station`).

## Proposal

Three parts, kept apart as the author asked.

1. **Existing records — a preparation origin owes no promise (recommended now).** In `finalize.check_source_protocols`, an origin run whose record says `run_kind = "preparation"` is not held to its text's promises (`origin_intent_findings` is not called); the station notes that a preparation reports no result. Unchanged: the input's bytes against the origin's registered output (station 7, first part), the origin's record reading, and the bound text reading back as the run started (`source_protocol_finding`) — the auditor is still shown it. Unchanged too: every check of the measurement run, its quality checks included. This releases experiment 12 without touching a file of either run. It also covers a preparation bound by an explicit `protocol=`: a preparation reports no result whichever way it was bound.
2. **Implicit binding at the start — a preparation without `protocol=` starts unbound (optional, a separate step).** This makes the record say what the protocol and the standard say. It does not heal old runs, so it does not replace part 1. Before building it, check every reader of a preparation's binding: the run-start file (`protocol_id` ""), the step basis and promise snapshot at the start, run lists per protocol. `protocol-fill --data-counts` is not affected: it finds the preparation by `run_kind`, not by binding (`tools/protocol_fill.newest_preparation`).
3. **Explicit `protocol=` on a preparation stays bound.** Its text is read back and shown to the auditor (part 1 keeps that); it owes no promise.

The standard's sentence needs one clause for part 1, which makes it a versioned standard change: "…and the origin run reports what that text registered — a preparation reports no result and owes none of its promises, while its text is still read back." This clause is the author's decision.

## Tests the change owes

- A preparation origin bound to the area's only protocol, whose metrics lack the measurement's keys: no blocker at finalize (rule test from data in memory, and one scenario as in the case above). Without the change this test is red.
- Twin: a measurement origin of another protocol that does not report its promise still blocks (`TwoProtocolsOfOneArea` holds this today; keep it green).
- Integrity stays: the preparation's output changed after the run still blocks; a bound preparation whose text cannot be read back still blocks.
- The measurement keeps its own duties: a measurement that drops `quality_check_1_pass` still blocks.
- Part 2 only: a preparation started without `protocol=` in a one-protocol area records `id` None; with `protocol=` it records the id.

## Not covered

The investigation read the code and reproduced finalize on a copy. It did not run `report-check` or `labkit-adopt` on the case; both run finalize as a station, so they are expected to hold the same four blockers and release with part 1, unchecked. Whether other areas carry the same pattern was not surveyed.

## After part 1 (2026-11-23)

On the same copy, with labkit `main` and part 1: `finalize` exits 0; the station notes the preparation, reads its text back, and holds the scenario file's bytes. `report-check` exits 1 with two blockers, both ordinary next steps — the analysis audit has not run, and the protocol has no adopted answer (`labkit-adopt` after that audit). With 0.114.0 it held the same two and the four preparation blockers. The audit and the adoption were not run here (the audit calls a model). argmining27 pins 0.114.0: it reaches the change only with a release and a raised pin.

The stamped prepare script (`labkit/templates/prepare-script.py.template`) starts without `protocol=`, so every stamped area with one protocol, a preparation and a registered promise met this. The scenario test was red on the old finalize for that reason: the preparation held to `[criterion-1]`.

## The standard's clause and the auditor's text (2026-11-23)

The author decided both on 2026-11-23.

**The standard.** LAB-043 Runs go through `runlog`, "An input's origin run is recorded and held", now says that a preparation reports no result: as an origin it owes none of its text's promises, bound or not, while its output's bytes and, where it was bound, the read-back of its text stay held. This alters what the rule demands. The standard makes that its next version, 0.34. The text is corrected under the standard's "Changes", as for 0.20 on 2026-10-19, and the stamp is the author's release step. A bump now would touch 45 tracked files (the `STANDARD` constant and its migration sentence, the template, the field guide, 30 stamped forms under `tests/form_stamps/`, test fixtures), and the release reading 0.34 would refuse every protocol stamped 0.33: argmining27 has six, experiment 12 among them, the case this clause releases.

**The auditor's text.** The analysis audit showed a bound preparation's text as "the question, criteria and method this origin run was measured under". Now `audit_binding.source_protocol_pieces` shows it as context (`PREPARATION_THEN`): the text the preparation was bound to; a preparation reports no result and is held to none of its promises. The run's kind is read once, with its binding, into `SourceProtocolThen.preparation`; finalize's station reads the same field, and `finalize.is_preparation` is gone. A measurement origin's piece is unchanged. The auditor's instructions (`experiment-preflight.agent.md`) say how to read such a piece; they are not in the record's digest.

**Which audit records this invalidates.** The source pieces are in the digest an analysis record binds (`shown_sha`). The text changes only for an analysis record of a run with an input whose origin is a preparation run bound to a protocol whose text reads back. Surveyed on 2026-11-23, read-only: every `runs/*/config.json` under `~/projects/*` (outside virtual environments), each input's `origin_run` looked up in its area, and each such area's `audits/*.toml`.

| Area                                                      | Run reading a recorded origin | Origin                                          | Audit records in the area | Invalidated              |
|-----------------------------------------------------------|-------------------------------|-------------------------------------------------|---------------------------|--------------------------|
| argmining27 `experiments/12-generated-scenario-stability` | `2026-11-23T19-18-55_2038`    | `2026-11-23T18-28-40_d9e1`, a bound preparation | none (no `audits/`)       | none                     |
| argmining27 `experiments/08-missci-repair-weighting`      | `2026-11-23T13-36-52_9e1a`    | two measurements of the same protocol           | none                      | none (not a preparation) |

No other run in `~/projects/*` records an origin. No stored audit record or prompt in this repo or in labkit-evidence shows a source protocol piece (a grep for `SOURCE PROTOCOL` finds only instructions and the changelog). So no audit record is invalidated; experiment 12's first analysis audit will be made under the new text. The survey covered records on this machine only, not clones elsewhere.
