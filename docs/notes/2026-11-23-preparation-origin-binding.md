# A preparation run held to the measurement's promises

Investigation and proposed change, 2026-11-23. Nothing is built yet; the change waits for the author's decision (TODO, open decision 8).

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
