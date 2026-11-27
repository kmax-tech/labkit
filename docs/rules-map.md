# Rules map — each rule of the standard, the code that holds it, and what is not settled

Generated, do not edit: `python -m labkit.tools.rules_map` writes this page from the source, the ledger, the shipped texts, `docs/chain.md`, `docs/checks-reach.tsv` and `docs/rule-gaps.tsv`, and `tests/test_map_of_rules.py` holds it equal to what the command writes. After a change to a finding site run the command again (`just overview`).

97 active rules of the lab standard; 19 are recorded by a finding site, 78 by none. 360 finding sites: 102 record a rule of a standard, 117 a technical contract, 9 an open assignment, 0 a new class, 37 a rule the cause passes in, 95 none (exits and printed lines). 25 more places name an open assignment that a site receives. 1 known gap(s) between a rule's text and its code.

How to read it. A site's *Rule* is the assignment its finding records as data. It says that the rule concerns the case the site holds — not that the code holds all of the rule's text: where the two are known to differ, the rule's section says so (from `docs/rule-gaps.tsv`). What the code does when the condition holds: *Grade* — BLOCKER refuses the step, WARNING tells and lets it pass, `exit` ends the command; *Evidence kind* — `guaranteed` is an exact check, `static evidence` a suspicion read from text or names; *Outcome* — what the finding states (`violated`, `deviation` where the rule is not decided, `suspected`, `not executable` for a check that could not run, `computed` or `variable` where the code decides at run time). *Stations* are the numbered gate stations that can tell the site ([gate stations](gate-stations.md)): in their own code or a function they call, or `(further down)` the call graph — a static estimate that may name a station the site is not reached from at run time; `—` where no numbered station reaches it (a gate without numbered stations, such as `protocol-check`, or an area's script). *Tests that reached it* counts the tests of the last traced run that reached the site, how many carry the mark `rule`, and their files; reaching is not asserting. *Tells* is the constant text of the message, every value as `{…}`.

Its limits. A rule no site records is listed as such: nothing follows from that about an agent audit checking it or a tool ruling it out — only what a source says stands here; a shipped text citing the rule is named, not what it asks. The chain's sections are matched by the functions their **Where:** line names. The stations are a static reading of the call graph (its limits: [gate stations](gate-stations.md)). Line numbers are left out: `python -m labkit.tools.check_inventory` prints them.

## Rules recorded by a finding site

### LAB-003 No run without an intent paragraph

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: *run → report (the registration as first measured)*, *run → report (a report outside the protocol)*.
- Shipped texts citing it: `labkit/agents/experiment-preflight.agent.md`, `labkit/docs/protocol-field-guide.md`.
- Other code strings citing it: `labkit.formats.exploration_link`, `labkit.formats.gate`, `labkit.formats.promises`, `labkit.formats.protocol_block`, `labkit.formats.protocol_check`, `labkit.gates.exploration_hold`, `labkit.gates.hook_pre_run`, `labkit.gates.registration_hold`, `labkit.gates.report_check`, `labkit.gates.report_hold`, `labkit.gates.report_replacement`, `labkit.run.start_check`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `exploration_hold.step_gap_hold` | `labkit/gates/exploration_hold.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down) | 1 (0 marked rule): `tests/test_exploration_hold.py` | run {…} made the step "{…}" on {…}, and its declared changes are not the differences of t… |
| `exploration_hold.unstepped_holds` | `labkit/gates/exploration_hold.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down) | 5 (0 marked rule): `tests/test_exploration_hold.py`, `tests/test_registration_station.py` | run {…} was measured without a step, and its registration differs from the first measurem… |
| `registration_hold.registration_changes` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down) | 3 (0 marked rule): `tests/test_counter_cases.py`, `tests/test_registration_committed.py`, `tests/test_replacement.py` | the first measurements recorded different registrations: {…} — which one stood before the… |
| `registration_hold.types_split_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down) | 1 (0 marked rule): `tests/test_registration_station.py` | the first measurements registered different types: {…} — which workflow binds the runs ca… |
| `registration_hold.type_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down) | 4 (0 marked rule): `tests/test_exploration_hold.py`, `tests/test_registration_station.py` | the type changed after the first measurement {…}: "{…}" → "{…}" ({…}) — the workflow that… |
| `report_check._registration_at` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 1 (0 marked rule): `tests/test_registration_committed.py` | {…} was not committed at {…} ({…}{…}) — nothing stood before the number; the registration… |
| `report_check._registration_at` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 6 (0 marked rule): `tests/test_registration_committed.py` | the registration as committed at {…} ({…}{…}) lacks {…} — the registration is what the co… |
| `report_hold.hold_report` | `labkit/gates/report_hold.py` | WARNING | STATIC_EVIDENCE | suspected | — | 1 (0 marked rule): `tests/test_report_hold_stations.py` | {…} |
| `report_replacement._predecessor` | `labkit/gates/report_replacement.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 1 (0 marked rule): `tests/test_replacement.py` | [replaces] protocol is its own id |

### LAB-004 Identifiers make the intent addressable

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: *promise → code (quality checks)*, *run → report (record)*.
- Shipped texts citing it: `labkit/agents/experiment-preflight.agent.md`, `labkit/docs/protocol-field-guide.md`, `labkit/templates/measure-estimator-script.py.template`, `labkit/templates/measure-script.py.template`.
- Other code strings citing it: `labkit.checks.code_check`, `labkit.checks.intent_check`, `labkit.formats.answering_run`, `labkit.formats.gate`, `labkit.formats.promises`, `labkit.formats.protocol_block`, `labkit.formats.protocol_check`, `labkit.gates.finalize`, `labkit.gates.preflight`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `code_check._intent_id_findings` | `labkit/checks/code_check.py` | WARNING | GUARANTEED | violated | preflight.preflight_area · 4 (further down) | 7 (0 marked rule): `tests/test_apply_skeleton.py`, `tests/test_code_check.py`, `tests/test_code_ids_keywords.py`, `tests/test_unreadable_source.py` | key '{…}_*' is in the intent-id namespace, but the protocol registers no [{…}] · a number… |
| `code_check.quality_check_reads` | `labkit/checks/code_check.py` | WARNING | STATIC_EVIDENCE | suspected | preflight.preflight_area · 4 (further down) | 22 (0 marked rule): 8 files, [checks overview](checks-overview.md) | [{…}] key '{…}' is written but nothing decides on it under its literal name · if no decis… |
| `code_check.constant_copies` | `labkit/checks/code_check.py` | WARNING | STATIC_EVIDENCE | suspected | preflight.preflight_area · 4 (further down) | 4 (0 marked rule): `tests/test_audit_rest.py`, `tests/test_unreadable_source.py` | [{…}] {…}:{…} sets {…} = {…} itself ({…}) · a copy judges by an unregistered value once t… |
| `intent_check.hold` | `labkit/checks/intent_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 3 (further down) | 20 (0 marked rule): `tests/test_area_state.py`, `tests/test_finalize.py`, `tests/test_promises.py`, `tests/test_registration_committed.py`, `tests/test_replacement.py` | {…} |
| `intent_check.hold` | `labkit/checks/intent_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 3 (further down) | 17 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_finalize.py`, `tests/test_intent_check.py`, `tests/test_intent_check_binding.py`, `tests/test_intent_check_choice.py`, `tests/test_origin_scenario.py` | {…} |
| `intent_check.check_block_against_run` | `labkit/checks/intent_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 3 (further down), finalize.finalize_area · 7 (further down) | 12 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_finalize.py`, `tests/test_origin_scenario.py`, `tests/test_promises.py` | {…}: [{…}] declares key '{…}', which the run does not report. |
| `intent_check.check_block_against_run` | `labkit/checks/intent_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 3 (further down), finalize.finalize_area · 7 (further down) | 3 (0 marked rule): `tests/test_promises.py` | {…} |
| `intent_check.unregistered_outcomes` | `labkit/checks/intent_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 3 (further down), finalize.finalize_area · 7 (further down) | 2 (0 marked rule): `tests/test_promises.py` | {…}: [{…}] records {…} = {…}, which is none of its outcomes' names |
| `intent_check.origin_intent_findings` | `labkit/checks/intent_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 7 (further down) | 3 (0 marked rule): `tests/test_intent_check.py`, `tests/test_origin_check.py` | {…} |
| `answering_run.AnsweringRun.explain` | `labkit/formats/answering_run.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down), finalize.finalize_area · 3 (further down), report_check.protocol_verdict · 0 (further down), report_check.chain_gaps · 8 (further down) | 14 (0 marked rule): 8 files, [checks overview](checks-overview.md) | {…} {…} — no answer: a probe or producer run, or a script that reports no registered key |
| `finalize.station_declared_scopes` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 4 | 2 (0 marked rule): `tests/test_audit.py`, `tests/test_registration_contract.py` | {…} recorded no promise block: {…} — a run records the block it was measured under, so th… |
| `preflight.station_promise_sentences` | `labkit/gates/preflight.py` | WARNING | GUARANTEED | violated | preflight.preflight_area · 1 | 2 (0 marked rule): `tests/test_agent_hooks.py`, `tests/test_promise_preflight.py` | [[promise]] {…} still carries the stamp's `<…>` sentence — frozen = true refuses it |

### LAB-010 Commit before the run

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: —.
- Other code strings citing it: `labkit.checks.run_record_check`, `labkit.formats.gate`, `labkit.gates.preflight`, `labkit.gates.report_check`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `run_record_check._helpers_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…}, so the helpers its script imports ({…}) cannot be compared |
| `preflight.station_working_tree` | `labkit/gates/preflight.py` | WARNING | GUARANTEED | violated | preflight.preflight_area · 6 | 20 (0 marked rule): `tests/test_agent_hooks.py`, `tests/test_end_to_end.py`, `tests/test_explored_in.py`, `tests/test_preflight.py`, `tests/test_repeat_cost_lowered_and_waived_audit.py` | uncommitted changes in {…} (commit or stash before the run) |
| `report_check._registration_at` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 2 (0 marked rule): `tests/test_registration_committed.py` | {…} recorded no commit ({…}{…}) — it started outside the history, so the registration can… |

### LAB-011 Required-field check

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: —.
- Other code strings citing it: `labkit.checks.result_render`, `labkit.formats.gate`, `labkit.formats.protocol_block`, `labkit.formats.protocol_check`, `labkit.gates.finalize`, `labkit.gates.preflight`, `labkit.gates.report_check`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `result_render.render_gaps` | `labkit/checks/result_render.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 2 (0 marked rule): `tests/test_replacement.py`, `tests/test_result_render.py` | the Recorded results line is not written |
| `preflight.station_protocol_fields` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 1 | 3 (0 marked rule): `tests/test_agent_hooks.py`, `tests/test_preflight_stations.py` | {…}:{…}: PLACEHOLDER (must): {…} |
| `preflight.station_hooks` | `labkit/gates/preflight.py` | WARNING | GUARANTEED | violated | preflight.preflight_area · 7 | 42 (0 marked rule): 9 files, [checks overview](checks-overview.md) | {…} |
| `report_check.freeze_gaps` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 | 1 (0 marked rule): `tests/test_report_check_areas.py` | {…}: line {…}: {…} still a placeholder |

### LAB-015 Preflight audit before freezing

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: *run → report (the decisions)*.
- Shipped texts citing it: `labkit/agents/decision-review.agent.md`, `labkit/agents/experiment-preflight.agent.md`.
- Other code strings citing it: `labkit.checks.audit_binding`, `labkit.checks.code_check`, `labkit.checks.result_render`, `labkit.formats.audit_gaps`, `labkit.formats.gate`, `labkit.formats.protocol_block`, `labkit.formats.protocol_check`, `labkit.gates.agent_hooks`, `labkit.gates.audit`, `labkit.gates.finalize`, `labkit.gates.preflight`, `labkit.gates.report_decisions`, `labkit.gates.report_hold`, `labkit.gates.report_replacement`, `labkit.run.start_check`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `audit_binding.check_audit_findings_decided` | `labkit/checks/audit_binding.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 10 (further down) | 10 (1 marked rule): 7 files, [checks overview](checks-overview.md) | {…} — {…} |
| `audit_binding.check_audit_findings_decided` | `labkit/checks/audit_binding.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 10 (further down) | 2 (1 marked rule): `tests/test_finalize_open_findings.py`, `tests/test_rules_audit_binding.py` | {…} — {…} |
| `result_render.render_gaps` | `labkit/checks/result_render.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 3 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_result_render.py` | no "{…}" line — the limit's line belongs in the protocol |
| `result_render.render_gaps` | `labkit/checks/result_render.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 3 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_result_render.py` | "{…}" names a limit no covering record decides — written by hand or from an older record |
| `preflight.station_protocol_fields` | `labkit/gates/preflight.py` | WARNING | STATIC_EVIDENCE | suspected | preflight.preflight_area · 1 | 1 (0 marked rule): `tests/test_repeat_cost_lowered_and_waived_audit.py` | {…} |
| `report_decisions.check_limit_effects_decided` | `labkit/gates/report_decisions.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 4 (1 marked rule): `tests/test_decision_review.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` | {…}: a BLOCKER decided limitation owes its effect on the verdicts |
| `report_decisions.check_limits_upheld` | `labkit/gates/report_decisions.py` | variable | GUARANTEED | violated | report_check.chain_gaps · 7 (further down) | 24 (7 marked rule): `tests/test_decision_review.py`, `tests/test_end_to_end.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` | {…}: `{…}` on a {…} decided limitation {…} — no decision review upholds that {…} |
| `report_decisions.check_contested_closings_upheld` | `labkit/gates/report_decisions.py` | variable | GUARANTEED | violated | report_check.chain_gaps · 7 (further down) | 4 (2 marked rule): `tests/test_decision_review.py`, `tests/test_rules_report_decisions.py` | audit {…} #{…}: `{…}` on a {…} a review said {…} on ({…}) — closing a finding a reviewer … |
| `report_decisions.check_repaired_claims_upheld` | `labkit/gates/report_decisions.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 7 (further down) | 1 (1 marked rule): `tests/test_rules_report_decisions.py` | audit {…} #{…}: `fixed` on a BLOCKER on the Conclusion {…} — no follow-up audit is shown … |
| `report_decisions.check_first_dismissals_upheld` | `labkit/gates/report_decisions.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 7 (further down) | 6 (1 marked rule): `tests/test_decision_review.py`, `tests/test_end_to_end.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` | audit {…} #{…}: `false-positive` on a BLOCKER {…} — a blocking finding is not released by… |
| `report_decisions.check_earlier_blockers_released` | `labkit/gates/report_decisions.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 7 (further down) | 19 (2 marked rule): `tests/test_adopt_per_protocol.py`, `tests/test_audit.py`, `tests/test_counter_cases.py`, `tests/test_decision_review.py`, `tests/test_end_to_end.py`, `tests/test_rules_report_decisions.py` | audit {…}: {…} |
| `report_decisions.check_carried_closings_upheld` | `labkit/gates/report_decisions.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 7 (further down) | 4 (2 marked rule): `tests/test_audit.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` | audit {…} #{…}: a carried finding (from {…}) `{…}` — the follow-up did not find the fault… |
| `report_hold.review_hold` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 8 (further down) | 13 (0 marked rule): `tests/test_claim_review.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_hold_stations.py` | {…}: the report review holds this state ({…}) — {…} |
| `report_replacement._predecessor_open` | `labkit/gates/report_replacement.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 2 (0 marked rule): `tests/test_replacement.py` | its predecessor's BLOCKER is still open — {…} |

### LAB-017 The number of audits follows the cost tier

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: `labkit/agents/experiment-preflight.agent.md`, `labkit/docs/protocol-field-guide.md`, `labkit/templates/measure-quick-script.py.template`.
- Other code strings citing it: `labkit.checks.run_record_check`, `labkit.formats.audit_gaps`, `labkit.formats.gate`, `labkit.formats.protocol_history`, `labkit.formats.standard_contract`, `labkit.gates.audit`, `labkit.gates.hook_pre_run`, `labkit.gates.preflight`, `labkit.gates.report_check`, `labkit.run.start_check`.

**Known gap between text and code** (`run_record_check.provenance_findings`): the rule's text above asks "`finalize` refuses a run … with an output … outside git"; the code warns: on every first pass the output is untracked by construction. Kept as a task: TODO.md, "Regel → Prüfung → Funktion", point 1.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `run_record_check.provenance_findings` | `labkit/checks/run_record_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 6 (further down) | 152 (0 marked rule): 18 files, [checks overview](checks-overview.md) | output {…} is not yet tracked — `{…}` before the commit that cites the number |
| `run_record_check.source_finding` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 6 (further down) | 7 (1 marked rule): `tests/test_finalize_provenance.py`, `tests/test_origin_scenario.py`, `tests/test_rules_run_record_check.py` | source {…} is not the bytes the run read: {…}, the run recorded sha256 {…} |
| `run_record_check._untracked_source` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 6 (further down) | 10 (2 marked rule): `tests/test_end_to_end.py`, `tests/test_explored_in.py`, `tests/test_finalize_provenance.py`, `tests/test_rules_run_record_check.py` | {…} — whether it belongs to the project is left open |
| `audit.early_for_tier` | `labkit/gates/audit.py` | WARNING | GUARANTEED | violated | — | 2 (0 marked rule): `tests/test_audit.py`, `tests/test_check_stations.py` | repeat_cost = "low" and no completed run · the first run is the cheaper probe; one audit … |

### LAB-018 Routine check after every implementation

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: *promise → code (keys, scopes)*.
- Shipped texts citing it: —.
- Other code strings citing it: `labkit.checks.code_check`, `labkit.formats.gate`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `code_check.promise_block_findings` | `labkit/checks/code_check.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 4 (further down) | 12 (0 marked rule): `tests/test_agent_hooks.py`, `tests/test_apply_skeleton.py`, `tests/test_code_check.py`, `tests/test_preflight_stations.py`, `tests/test_promise_preflight.py` | [{…}] declares key '{…}', which no script names as a literal{…} (an assembled key is not … |

### LAB-019 The stamp covers everything that determines the number

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: —.
- Other code strings citing it: `labkit.checks.import_check`, `labkit.formats.gate`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `import_check._import_findings` | `labkit/checks/import_check.py` | WARNING | STATIC_EVIDENCE | suspected | preflight.preflight_area · 4 (further down) | 1 (0 marked rule): `tests/test_code_check.py` | `{…}` resolves to {…}, outside lib/ and src/ · the stamp does not cover it, a change ther… |
| `import_check._coverage_in` | `labkit/checks/import_check.py` | WARNING | STATIC_EVIDENCE | suspected | preflight.preflight_area · 4 (further down) | 2 (0 marked rule): `tests/test_code_check.py` | `sys.path` gains {…} · imports after it may resolve outside lib/ and src/, which the stam… |
| `import_check._coverage_in` | `labkit/checks/import_check.py` | WARNING | STATIC_EVIDENCE | suspected | preflight.preflight_area · 4 (further down) | 2 (0 marked rule): `tests/test_code_check.py` | `{…}(…)` loads code at run time · the stamp follows `import` lines only, so it does not c… |
| `import_check._coverage_in` | `labkit/checks/import_check.py` | WARNING | STATIC_EVIDENCE | suspected | preflight.preflight_area · 4 (further down) | 2 (0 marked rule): `tests/test_code_check.py` | names area `{…}` · this area's stamp does not follow a path into it |

### LAB-027 Model discipline

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: *run → report (model)*.
- Shipped texts citing it: —.
- Other code strings citing it: `labkit.checks.model_check`, `labkit.formats.gate`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `model_check._own_record_unbacked` | `labkit/checks/model_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 8 (4 marked rule): `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py` | {…}'s call log holds {…} of alias `{…}` ({…}), but its models_resolved does not name `{…}… |
| `model_check._derived_run_calls` | `labkit/checks/model_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 2 (1 marked rule): `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py` | {…} — yet its call log holds {…} call{…} of alias `{…}` that asked the model |
| `model_check._derived_run_calls` | `labkit/checks/model_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 2 (2 marked rule): `tests/test_rules_run_record_check.py` | {…} — yet its call log holds {…} of alias `{…}` stored outside any run{…}, which no recor… |
| `model_check._stored_answer_unbacked` | `labkit/checks/model_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 5 (3 marked rule): `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py` | {…}'s call log holds {…} of alias `{…}` stored by run {…}, but {…} — no record says which… |
| `model_check.stand_in_findings` | `labkit/checks/model_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 4 (2 marked rule): `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py`, `tests/test_stand_in_run_through.py` | {…}: fixed answers stored with `llm_cache.store_stand_in`, not answers of a model — its n… |
| `model_check._metrics_model_findings` | `labkit/checks/model_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 2 (0 marked rule): `tests/test_finalize_steps.py` | {…} called a model, but no run in its lineage recorded models_resolved — record the alias… |
| `model_check.arm_findings` | `labkit/checks/model_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 1 (0 marked rule): `tests/test_arm_lines.py` | arm `{…}`: the protocol names alias {…}, the answering run recorded no such alias |

### LAB-034 Null condition in the same run

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: *run → report (the null lane)*.
- Shipped texts citing it: `labkit/templates/measure-estimator-script.py.template`, `labkit/templates/measure-script.py.template`.
- Other code strings citing it: `labkit.checks.row_check`, `labkit.formats.gate`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `row_check.null_lane_findings` | `labkit/checks/row_check.py` | WARNING | STATIC_EVIDENCE | suspected | finalize.finalize_area · 9 (further down) | 2 (1 marked rule): `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py` | {…}: the null lane's answer and gold equal the registered lane's on every item — if the n… |

### LAB-035 Thresholds belong to the run, not to the measure

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: `labkit/docs/protocol-field-guide.md`, `labkit/templates/measure-estimator-script.py.template`, `labkit/templates/measure-script.py.template`.
- Other code strings citing it: `labkit.formats.gate`, `labkit.formats.protocol_block`, `labkit.formats.reference`, `labkit.gates.registration_hold`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `reference.comparison_gaps` | `labkit/formats/reference.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 9 (further down) | 1 (0 marked rule): `tests/test_reference.py` | metrics.json carries {…} and the head registers no [reference] — a comparison is register… |
| `reference.comparison_gaps` | `labkit/formats/reference.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 9 (further down) | 2 (0 marked rule): `tests/test_reference.py` | the run compared with {…}, the head registers {…} — the reference changed after the run, … |

### LAB-036 Validate, don't trust a single run

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: `labkit/templates/analyze-script.py.template`.
- Other code strings citing it: `labkit.checks.model_check`, `labkit.formats.gate`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `model_check.single_draw` | `labkit/checks/model_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 40 (0 marked rule): `tests/test_counter_cases.py`, `tests/test_end_to_end.py`, `tests/test_finalize_steps.py`, `tests/test_handovers.py`, `tests/test_repeats.py` | {…} is one draw — no spread: `scripts/01_measure.py --repeat-of {…}` draws it again, `02_… |

### LAB-041 Generate numbers, don't retype them

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: *kind → kept number*.
- Shipped texts citing it: `labkit/templates/analyze-quick-script.py.template`, `labkit/templates/measure-estimator-script.py.template`, `labkit/templates/measure-quick-script.py.template`, `labkit/templates/measure-script.py.template`.
- Other code strings citing it: `labkit.checks.data_counts`, `labkit.checks.kept_number_check`, `labkit.checks.prompt_check`, `labkit.checks.run_record_check`, `labkit.formats.gate`, `labkit.formats.protocol_check`, `labkit.formats.reference`, `labkit.gates.finalize`, `labkit.gates.report_check`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `kept_number_check.kept_number_gaps` | `labkit/checks/kept_number_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 9 (further down) | 7 (0 marked rule): `tests/test_audit.py`, `tests/test_end_to_end.py`, `tests/test_kept.py`, `tests/test_promises.py`, `tests/test_protocol_fill.py`, `tests/test_reference_end_to_end.py` | the kept number: metrics.json of {…} {…} — the head's [kept] names `{…}` as the number th… |
| `prompt_check.check_parser_fixtures` | `labkit/checks/prompt_check.py` | WARNING | STATIC_EVIDENCE | suspected | preflight.preflight_area · 4 (further down) | 4 (0 marked rule): `tests/test_code_check_gates.py`, `tests/test_preflight.py` | {…}() is called by no test under tests/ · a parser fails silently into a wrong number |
| `run_record_check.answer_reading_gaps` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 4 (further down) | 1 (1 marked rule): `tests/test_rules_run_record_check.py` | {…} registered none of the files {…} registered as its output — a derived run re-reads it… |
| `run_record_check.answer_reading_gaps` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 4 (further down) | 2 (1 marked rule): `tests/test_answer_reading_scenario.py`, `tests/test_rules_run_record_check.py` | {…}: {…} registered sha256 {…}, {…} {…} — the answers changed after {…} ran |
| `run_record_check._run_code` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 31 (0 marked rule): 10 files, [checks overview](checks-overview.md) | {…} changed since {…} ran it — its number came from other code |
| `run_record_check._helpers_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…} changed since {…} ran it (it was untracked; the run kept it as {…}) |
| `run_record_check._helpers_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 5 (0 marked rule): `tests/test_answer_reading_scenario.py`, `tests/test_run_code.py` | {…} changed since {…} ran |
| `run_record_check._recorded_sources` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 6 (further down) | 21 (0 marked rule): 7 files, [checks overview](checks-overview.md) | source not frozen — the run carries no `data=` |
| `reference.comparison_gaps` | `labkit/formats/reference.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 9 (further down) | 1 (0 marked rule): `tests/test_reference.py` | `{…}` {…}, so the registered reference ({…}) cannot be compared and no verdict can be rep… |
| `finalize.station_declared_scopes` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 4 | 3 (0 marked rule): `tests/test_finalize.py`, `tests/test_promises.py` | declared scope changed since {…}: {…} |
| `report_check.recomputation_findings` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | not executable | report_check.chain_gaps · 6 | 2 (0 marked rule): `tests/test_origin_scenario.py`, `tests/test_report_check_areas.py` | {…} |
| `report_check.recomputation_findings` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 6 | 56 (0 marked rule): 17 files, [checks overview](checks-overview.md) | {…} |

### LAB-043 Runs go through `runlog`

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: —.
- Other code strings citing it: `labkit.formats.answering_run`, `labkit.formats.evidence`, `labkit.formats.gate`, `labkit.formats.protocol_block`, `labkit.gates.finalize`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `finalize.choose_answering_run` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 2 (0 marked rule): `tests/test_finalize.py`, `tests/test_finalize_steps.py` | no stamped protocol id ([protocol] id) — no run is bound to it |

### LAB-050 Analysis audit before reporting

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: `labkit/agents/claim-review.agent.md`, `labkit/agents/decision-review.agent.md`, `labkit/agents/experiment-preflight.agent.md`, `labkit/agents/report-review.agent.md`, `labkit/docs/protocol-field-guide.md`.
- Other code strings citing it: `labkit.formats.gate`, `labkit.formats.standard_contract`, `labkit.gates.report_exploration`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `report_exploration.later_use_findings` | `labkit/gates/report_exploration.py` | WARNING | STATIC_EVIDENCE | suspected | report_check.chain_gaps · 5 (further down) | 5 (0 marked rule): `tests/test_explored_in.py` | data use after the audit: run {…} of {…} recorded {…} — {…}. The run is taken as not show… |

### LAB-057 One area per idea

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: *run → report (continued rows)*.
- Shipped texts citing it: —.
- Other code strings citing it: `labkit.checks.row_check`, `labkit.formats.gate`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `row_check.row_provenance_findings` | `labkit/checks/row_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 9 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_repair_guidance.py`, `tests/test_row_provenance.py`, `tests/test_withdrawal_order.py` | {…}: {…} row(s) from {…} — a run this run neither is, continues nor derives from; a file … |

### LAB-067 A prompt has one home, which the run freezes

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: —.
- Other code strings citing it: `labkit.checks.prompt_check`, `labkit.checks.run_record_check`, `labkit.formats.gate`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `prompt_check.check_prompt_drift` | `labkit/checks/prompt_check.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 4 (further down) | 1 (0 marked rule): `tests/test_prompt_templates.py` | {…} |
| `prompt_check.check_prompt_drift` | `labkit/checks/prompt_check.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 4 (further down) | 8 (0 marked rule): `tests/test_code_check_gates.py`, `tests/test_code_check_prompts.py`, `tests/test_preflight.py`, `tests/test_protocol_fill.py` | prompt block drifted from {…}: {…} of {…} fixed line(s) missing, e.g. {…} |
| `run_record_check.answer_reading_gaps` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 4 (further down) | 2 (1 marked rule): `tests/test_answer_reading_scenario.py`, `tests/test_rules_run_record_check.py` | {…} re-reads the answers of {…}, but the prompts field differs from the text {…} was meas… |

### LAB-082 In `notes/messung/`, every note carries its kind in the meta line

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: —.
- Shipped texts citing it: —.
- Other code strings citing it: `labkit.checks.notes_check`, `labkit.formats.gate`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `notes_check.check_file` | `labkit/checks/notes_check.py` | WARNING | GUARANTEED | violated | — | 2 (0 marked rule): `tests/test_agent_hooks.py` | {…}:1: MISSING: no italic meta line after the title |
| `notes_check.check_file` | `labkit/checks/notes_check.py` | WARNING | GUARANTEED | violated | — | 2 (0 marked rule): `tests/test_notes_check.py` | {…}:{…}: MISSING: no kind in the meta line |
| `notes_check.check_file` | `labkit/checks/notes_check.py` | WARNING | STATIC_EVIDENCE | suspected | — | 1 (0 marked rule): `tests/test_notes_check.py` | {…}:{…}: MISSING: declared 'Instrument — implementiert' but names no script, function, or… |
| `notes_check.check_file` | `labkit/checks/notes_check.py` | WARNING | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_notes_check.py` | {…}:{…}: warning: Related-Lesart without a citekey — write 'Related-Lesart (<citekey>)' |

### LAB-104 A number leaves the area only through its adoption

- The rule: `labkit/docs/standard.md`.
- The chain (`docs/chain.md`), sections naming a function of its sites: *run → report (a report outside the protocol)*.
- Shipped texts citing it: `labkit/agents/claim-review.agent.md`, `labkit/agents/report-review.agent.md`.
- Other code strings citing it: `labkit.checks.report_blocks`, `labkit.formats.gate`, `labkit.formats.protocol_block`, `labkit.formats.report_reviews`, `labkit.gates.finalize`, `labkit.gates.registered_report`, `labkit.gates.report_check`, `labkit.gates.report_hold`.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `report_blocks.block_gaps` | `labkit/checks/report_blocks.py` | BLOCKER | GUARANTEED | violated | — | 2 (0 marked rule): `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py` | {…}: the protocol has adopted run {…} now |
| `report_blocks.cited_gaps` | `labkit/checks/report_blocks.py` | BLOCKER | GUARANTEED | violated | — | 6 (0 marked rule): `tests/test_next_step.py`, `tests/test_origin_scenario.py`, `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py` | {…} |
| `report_blocks.cited_gaps` | `labkit/checks/report_blocks.py` | WARNING | STATIC_EVIDENCE | suspected | — | 3 (0 marked rule): `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py` | {…} |
| `report_blocks.discussion_gaps` | `labkit/checks/report_blocks.py` | BLOCKER | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_report_blocks.py` | {…} has no why |
| `report_blocks.discussion_gaps` | `labkit/checks/report_blocks.py` | BLOCKER | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_report_blocks.py` | {…}: its line differs from its head |
| `report_check.freeze_gaps` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 | 8 (0 marked rule): `tests/test_audit.py`, `tests/test_protocol_fill.py`, `tests/test_replacement.py`, `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py` | {…}: not `frozen = true` — a reported number owes the freeze |
| `report_hold.through_gap` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 8 (further down) | 3 (0 marked rule): `tests/test_origin_scenario.py`, `tests/test_reported_through.py` | {…}: {…} |
| `report_hold.owed_blocks` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 7 (0 marked rule): `tests/test_next_step.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_source_lines.py` | line {…}: cites run {…}, the adopted result of {…}, without its generated block — the num… |
| `report_hold.report_hints` | `labkit/gates/report_hold.py` | WARNING | STATIC_EVIDENCE | suspected | — | 18 (0 marked rule): `tests/test_counter_cases.py`, `tests/test_next_step.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py` | {…}: no assigned source found for the numbers on {…} line(s) — they stand outside every g… |
| `report_hold.report_hints` | `labkit/gates/report_hold.py` | WARNING | STATIC_EVIDENCE | suspected | — | 1 (0 marked rule): `tests/test_report_blocks.py` | {…}: numbers on {…} line(s) beside a discussed run — a discussed run's number in a report… |
| `report_hold.review_hold` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 8 (further down) | 25 (0 marked rule): 11 files, [checks overview](checks-overview.md) | {…}: {…} and has no clean report review of this state (one naming no claim){…} — a cold r… |
| `report_hold.undeclared_findings` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 2 (0 marked rule): `tests/test_report_blocks.py` | {…}: line {…}: run {…} is discussed as not reported, but {…} has adopted it as its result |
| `report_hold.undeclared_findings` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 9 (0 marked rule): `tests/test_counter_cases.py`, `tests/test_handovers.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py` | {…}: cites {…}, the answering run of {…}, which has adopted no result |
| `report_hold.undeclared_findings` | `labkit/gates/report_hold.py` | WARNING | GUARANTEED | violated | — | 5 (0 marked rule): `tests/test_counter_cases.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py` | {…}: cites {…}, which no protocol has adopted as its result — a reported number is adopte… |

## Rules no finding site records

For each: no finding site records it — no mechanical check evidenced. Where a shipped text or a code string cites the rule, it is named; that is a citation, not a check.

| Rule | Shipped texts citing it | Code strings citing it |
|---|---|---|
| LAB-001 A negative finding is a claim | — | — |
| LAB-005 Pilot before scaling | — | — |
| LAB-006 Does the gold label measure what you are measuring? | — | — |
| LAB-007 Render check before the instrument check | — | — |
| LAB-008 Instrument check before freezing | `labkit/docs/protocol-field-guide.md`, `labkit/templates/measure-estimator-script.py.template` | — |
| LAB-009 Verdict only at the registered tier | `labkit/agents/experiment-preflight.agent.md` | — |
| LAB-012 Protocol is content | — | — |
| LAB-013 Registered branch when the run can answer two questions | `labkit/docs/protocol-field-guide.md` | — |
| LAB-014 One fully rendered example pair per gold class | `labkit/docs/protocol-field-guide.md`, `labkit/templates/test-area.py.template` | `labkit.checks.protocol_report` |
| LAB-016 Resolution check before freezing | `labkit/docs/protocol-field-guide.md`, `labkit/templates/explore-script.py.template`, `labkit/templates/measure-estimator-script.py.template`, `labkit/templates/test-estimator.py.template`, `labkit/templates/vscode-settings.json.template` | `labkit.formats.gate`, `labkit.gates.preflight` |
| LAB-020 Materialize transformations | `labkit/templates/prepare-estimator-script.py.template`, `labkit/templates/prepare-script.py.template` | — |
| LAB-021 No dataset without a producer | `labkit/templates/prepare-estimator-script.py.template`, `labkit/templates/prepare-script.py.template` | — |
| LAB-022 Datasets explain themselves | — | — |
| LAB-023 No silent loss | `labkit/docs/protocol-field-guide.md`, `labkit/templates/measure-estimator-script.py.template`, `labkit/templates/measure-script.py.template` | — |
| LAB-024 Reproducible | — | — |
| LAB-025 Two-user rule: the computation is shared, not the verdict | — | — |
| LAB-026 A reused component brings its bugs with it | — | — |
| LAB-028 An endpoint is a model slot, not a service | `labkit/templates/measure-script.py.template`, `labkit/templates/models.toml.template` | — |
| LAB-029 A harness is not an inference API: its context is isolated and stamped | — | — |
| LAB-030 Reasoning models: the token budget goes to thinking first | `labkit/templates/measure-script.py.template` | — |
| LAB-031 Whoever wants a difference asks for the difference | — | — |
| LAB-032 Free knobs: vary them and report the curve | — | — |
| LAB-033 A parameter that is accepted and discarded is the most expensive bug | — | — |
| LAB-037 Every anchor carries its target and rationale | `labkit/docs/protocol-field-guide.md`, `labkit/templates/measure-estimator-script.py.template`, `labkit/templates/measure-script.py.template` | — |
| LAB-038 What the prompt demands, the gate checks — from the same constant | `labkit/docs/protocol-field-guide.md`, `labkit/templates/measure-script.py.template` | — |
| LAB-039 Anchors include the near cases | — | — |
| LAB-040 Check the output, not just the numbers | — | — |
| LAB-042 Log the outcome — failures too | — | `labkit.gates.ways_out` |
| LAB-044 The check on a confound is code, not a paragraph | `labkit/docs/protocol-field-guide.md` | — |
| LAB-045 The forecast comes before the follow-up run | `labkit/docs/protocol-field-guide.md` | — |
| LAB-046 Notebooks: explore yes, report never | `labkit/templates/explore-script.py.template` | — |
| LAB-047 A partial run is not a random sample — no anchor catches that | — | — |
| LAB-048 An intermediate number is not a result | — | — |
| LAB-049 Long runs go through the harness's background mechanism | — | — |
| LAB-051 Judge instance, not model name | — | — |
| LAB-052 Instance gate before registered use | `labkit/templates/measure-script.py.template` | — |
| LAB-053 Resolution anchor | — | — |
| LAB-054 Self-consistency requirement for logprob readings | — | — |
| LAB-055 Check polarity symmetry | — | — |
| LAB-056 Recompute thresholds unrounded | — | — |
| LAB-058 `data/prepared/` is read-only after writing | — | — |
| LAB-059 Use shared helpers, don't modify them within a run | — | — |
| LAB-060 Look it up instead of asking | — | — |
| LAB-061 Sub-experiment series carry their number in the name | — | `labkit.checks.protocol_report` |
| LAB-062 Reorganizing existing material is allowed — as a package | — | — |
| LAB-063 A research line has one entry point | — | — |
| LAB-064 The pilot is resumable too | — | — |
| LAB-065 No worktree per experiment | — | — |
| LAB-066 Extract only for the second user | — | — |
| LAB-068 New areas start from the template-generated skeleton | — | — |
| LAB-069 No LLM cache unless the lab declares one | `labkit/templates/models.toml.template` | `labkit.formats.protocol_block` |
| LAB-071 The proof is the item-wise diff, not a tolerance band | — | — |
| LAB-072 Identifiers travel in English | — | — |
| LAB-074 Note and commit carry the why; reconcile | — | — |
| LAB-075 Docs carry the state, commits the change | — | `labkit.checks.protocol_report` |
| LAB-076 Restriction convention | — | — |
| LAB-077 Own commits, others' state stays with the user | — | — |
| LAB-079 Self-contained experiment areas | — | — |
| LAB-083 The name carries what it denotes | — | — |
| LAB-084 Double-coinage check — first the field, then the lab, then the existing stock | `labkit/docs/protocol-field-guide.md`, `labkit/templates/terms.md.template` | — |
| LAB-085 Mark your own coinages as such | — | — |
| LAB-086 Values rule (codes are names too) | `labkit/templates/prepare-estimator-script.py.template`, `labkit/templates/prepare-script.py.template` | — |
| LAB-087 Term before use | — | — |
| LAB-088 Look up field notation, don't invent it | — | — |
| LAB-089 Tight prose | — | — |
| LAB-090 Protocols are self-contained | — | — |
| LAB-091 Script docstrings are reference, not explanation | — | — |
| LAB-092 Term layering | `labkit/agents/code-clarity.agent.md` | — |
| LAB-093 Detail budget follows relevance, not analysis effort | — | — |
| LAB-094 Series as list or table, never as a prose chain | — | — |
| LAB-095 Core problem first | — | — |
| LAB-096 "Do I really need this?" | — | — |
| LAB-097 Existing work first | — | — |
| LAB-098 Separate core and rollout | — | — |
| LAB-100 Answer before reasoning | — | — |
| LAB-101 Comparison tables | — | — |
| LAB-102 Cold reader before freezing | — | `labkit.formats.standard_contract`, `labkit.gates.preflight` |
| LAB-103 The audit reads by declared scope, not by import graph | `labkit/agents/experiment-preflight.agent.md` | `labkit.gates.audit_prompt` |

## Other recorded rules

Rules the sites record that are not active rules of the lab standard: the code standard's (`docs/coding-style.md`), or a rule the ledger retired.

### CODE-016 The experiment area reconstructs itself

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `code_check._intent_id_findings` | `labkit/checks/code_check.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 4 (further down) | 13 (0 marked rule): `tests/test_agent_hooks.py`, `tests/test_apply_skeleton.py`, `tests/test_code_check.py`, `tests/test_code_ids_keywords.py`, `tests/test_preflight.py`, `tests/test_promise_preflight.py` | [{…}] is registered, but no script names a '{…}'/'{…}_*' key literal (a key assembled at … |
| `readme_check.readme_route` | `labkit/checks/readme_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 5 (further down) | 1 (0 marked rule): `tests/test_finalize_steps.py` | README.md route: scripts/01_measure.py does not exist |
| `readme_check.readme_route` | `labkit/checks/readme_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 5 (further down) | 1 (0 marked rule): `tests/test_finalize_steps.py` | README.md route: scripts/01_measure.py defines no evaluate_rows |
| `finalize.station_open_fields` | `labkit/gates/finalize.py` | WARNING | STATIC_EVIDENCE | suspected | finalize.finalize_area · 5 | 42 (0 marked rule): `tests/test_counter_cases.py`, `tests/test_end_to_end.py`, `tests/test_finalize_steps.py`, `tests/test_handovers.py`, `tests/test_obligations_scenario.py` | {…} — a stamped placeholder, fill or delete the line |

## Technical contracts

A condition a format or a check needs before it can answer — a file that reads, a reference that leads somewhere, a field written once, a format convention the stamp or the template writes. No rule of the standard is broken by it; the finding says the check could not answer, or the input is not what the format promises.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `audit_binding.source_protocol_finding` | `labkit/checks/audit_binding.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 7 (further down) | 5 (0 marked rule): `tests/test_origin_check.py`, `tests/test_origin_scenario.py` | {…} |
| `audit_binding.check_audit_records_read` | `labkit/checks/audit_binding.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 10 (further down) | 3 (1 marked rule): `tests/test_finalize_open_findings.py`, `tests/test_handovers.py`, `tests/test_rules_audit_binding.py` | {…} |
| `audit_binding.check_audited_runs_kept` | `labkit/checks/audit_binding.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 10 (further down) | 5 (3 marked rule): `tests/test_finalize_open_findings.py`, `tests/test_report_check.py`, `tests/test_rules_audit_binding.py`, `tests/test_rules_registration_hold.py` | {…}: names {…} as the run it read, and there is no runs/{…}/ in this area — the run the r… |
| `code_check.quality_check_reads` | `labkit/checks/code_check.py` | WARNING | GUARANTEED | computed | preflight.preflight_area · 4 (further down) | 1 (0 marked rule): `tests/test_check_stations.py` | quality-check keys: read check not done — {…} |
| `code_check.main` | `labkit/checks/code_check.py` | WARNING | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_check_stations.py` | bundle: {…} could not be read — the reader sees `not readable` in its place |
| `code_scan.unreadable_source` | `labkit/checks/code_scan.py` | BLOCKER | GUARANTEED | computed | finalize.finalize_area · 5 (further down), preflight.preflight_area · 4 (further down) | 13 (0 marked rule): 7 files, [checks overview](checks-overview.md) | {…} · the code cannot be read, so no check over it holds |
| `intent_check.origin_intent_findings` | `labkit/checks/intent_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 7 (further down) | 1 (0 marked rule): `tests/test_intent_check.py` | {…}: {…} |
| `model_check.single_draw` | `labkit/checks/model_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 1 (0 marked rule): `tests/test_repeats.py` | the draws of {…} cannot be counted: {…} |
| `model_check.model_provenance_findings` | `labkit/checks/model_check.py` | BLOCKER | GUARANTEED | computed | finalize.finalize_area · 1 (further down) | 1 (0 marked rule): `tests/test_finalize_steps.py` | model provenance: the call log of {…} does not read — {…} |
| `model_check.model_provenance_findings` | `labkit/checks/model_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 1 (0 marked rule): `tests/test_finalize_steps.py` | model provenance: {…} has no config.json — which model it recorded cannot be read |
| `model_check.model_provenance_findings` | `labkit/checks/model_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 9 (0 marked rule): `tests/test_finalize_provenance.py`, `tests/test_finalize_steps.py`, `tests/test_origin_scenario.py`, `tests/test_registration_committed.py` | model provenance: the stand-ins behind {…} cannot be counted — {…}; the result line canno… |
| `model_check._metrics_model_findings` | `labkit/checks/model_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 1 (0 marked rule): `tests/test_finalize_steps.py` | model provenance: the lineage of {…} is broken — {…} |
| `model_check.arm_findings` | `labkit/checks/model_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 1 (0 marked rule): `tests/test_arm_lines.py` | arm `{…}`: the protocol names {…}, no such file under {…} |
| `notes_check.check_notes` | `labkit/checks/notes_check.py` | WARNING | GUARANTEED | computed | — | 2 (0 marked rule): `tests/test_check_stations.py`, `tests/test_read_causes.py` | {…}: not readable ({…}) |
| `origin_check.origin_finding` | `labkit/checks/origin_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 7 (further down) | 9 (0 marked rule): `tests/test_origin_check.py`, `tests/test_origin_scenario.py`, `tests/test_registration_committed.py` | {…} |
| `prompt_check.check_parser_fixtures` | `labkit/checks/prompt_check.py` | WARNING | GUARANTEED | not executable | preflight.preflight_area · 4 (further down) | 1 (0 marked rule): `tests/test_code_check_gates.py` | cannot be parsed ({…}) · which parsers it calls cannot be told |
| `prompt_check.check_prompt_drift` | `labkit/checks/prompt_check.py` | WARNING | GUARANTEED | not executable | preflight.preflight_area · 4 (further down) | 1 (0 marked rule): `tests/test_code_check_prompts.py` | {…} is not statically readable (a call or a format spec this check does not compute) · pr… |
| `readme_check.readme_route` | `labkit/checks/readme_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 5 (further down) | 3 (0 marked rule): `tests/test_finalize.py`, `tests/test_finalize_steps.py` | README.md: no {…} … {…} block — the route (protocol · runlog · labkit-params · evaluate_r… |
| `readme_check.readme_route` | `labkit/checks/readme_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 5 (further down) | 11 (0 marked rule): `tests/test_adopt_per_protocol.py`, `tests/test_finalize_steps.py`, `tests/test_origin_scenario.py`, `tests/test_protocol_runs.py`, `tests/test_source_lines.py` | README.md route: does not name {…} |
| `readme_check.readme_route` | `labkit/checks/readme_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 5 (further down) | 2 (0 marked rule): `tests/test_finalize.py`, `tests/test_finalize_steps.py` | README.md route: does not name {…} |
| `report_blocks.block_gaps` | `labkit/checks/report_blocks.py` | BLOCKER | GUARANTEED | violated | — | 2 (0 marked rule): `tests/test_origin_scenario.py`, `tests/test_report_blocks.py` | {…}: {…} |
| `report_blocks.block_gaps` | `labkit/checks/report_blocks.py` | BLOCKER | GUARANTEED | violated | — | 11 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py`, `tests/test_result_render.py`, `tests/test_workflow_example.py` | {…} differs from the protocol's rendering — written before its Conclusion, a decision or … |
| `report_blocks.discussion_gaps` | `labkit/checks/report_blocks.py` | BLOCKER | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_report_blocks_text.py` | {…} repeats the block at line {…} — one block per protocol and run |
| `result_render.render_gaps` | `labkit/checks/result_render.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 11 (0 marked rule): 7 files, [checks overview](checks-overview.md) | the Recorded results line differs from its rendering (the run's metrics.json, the stand-i… |
| `result_render.render_gaps` | `labkit/checks/result_render.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 1 (0 marked rule): `tests/test_result_render.py` | "{…}" is written {…} times — one generated line per label |
| `result_render.render_gaps` | `labkit/checks/result_render.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 5 (0 marked rule): `tests/test_decision_review.py`, `tests/test_result_render.py` | "{…}" differs from the record and its decision reviews — a line written before the decisi… |
| `row_check.row_provenance_findings` | `labkit/checks/row_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 2 (0 marked rule): `tests/test_lineage.py`, `tests/test_registration_committed.py` | row provenance: the lineage of {…} is broken — {…} |
| `row_check.row_provenance_findings` | `labkit/checks/row_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 1 (0 marked rule): `tests/test_row_provenance.py` | {…}: {…} |
| `run_record_check.code_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 2 (0 marked rule): `tests/test_registration_committed.py`, `tests/test_run_code.py` | {…}: its runs cannot be followed ({…}) |
| `run_record_check.code_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | computed | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…}: {…} |
| `run_record_check._reading_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…} cannot be compared with what {…} ran: the area lies in no git repository now |
| `run_record_check._reading_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…}: {…} |
| `run_record_check._reading_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | computed | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…} cannot be read now: {…} |
| `run_record_check._reading_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…}: {…} no longer imports it, so it is not what reads the answers |
| `run_record_check._run_code` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 10 (0 marked rule): 8 files, [checks overview](checks-overview.md) | {…} recorded no script — the code behind its number cannot be compared |
| `run_record_check._run_code` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 3 (0 marked rule): `tests/test_run_code.py` | {…}: {…} |
| `run_record_check._run_code` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | computed | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 2 (0 marked rule): `tests/test_finalize.py`, `tests/test_run_code.py` | the code {…} ran cannot be read now: {…} |
| `run_record_check._helpers_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 2 (0 marked rule): `tests/test_run_code.py` | {…}, so the helpers its script imports ({…}) cannot be compared |
| `run_record_check._helpers_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…} started from a tree with changes ({…}), and its uncommitted.patch is gone: the commit… |
| `run_record_check._helpers_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…} {…}, so the helpers its script imports ({…}) cannot be compared |
| `run_record_check._helpers_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…} started at commit {…}, which this clone does not hold |
| `run_record_check._helpers_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 2 (0 marked rule): `tests/test_run_code.py` | the tree {…} started from cannot be read for {…}: {…} |
| `run_record_check._helpers_since_run` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down), finalize.finalize_area · 4 (further down) | 1 (0 marked rule): `tests/test_run_code.py` | {…} is in neither {…}'s commit nor its uncommitted.patch, so it cannot be compared with w… |
| `run_record_check.provenance_findings` | `labkit/checks/run_record_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 6 (further down) | 71 (0 marked rule): 14 files, [checks overview](checks-overview.md) | no outputs.json — the run registered no output file (run.output) |
| `run_record_check.provenance_findings` | `labkit/checks/run_record_check.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 6 (further down) | 27 (0 marked rule): 7 files, [checks overview](checks-overview.md) | not a git repository — cannot tell whether source and output are committed |
| `run_record_check._recorded_sources` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 6 (further down) | 3 (0 marked rule): `tests/test_check_stations.py`, `tests/test_finalize_provenance.py` | {…} |
| `run_record_check._gone` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 6 (further down) | 2 (1 marked rule): `tests/test_finalize_provenance.py`, `tests/test_rules_run_record_check.py` | {…} is not at its recorded path on this machine — deleted, moved or held elsewhere; the r… |
| `area_state.unread_start_warning` | `labkit/formats/area_state.py` | WARNING | GUARANTEED | not executable | finalize.finalize_area · 2 (further down), report_check.chain_gaps · 2 (further down), runlog.Run.__init__ · 2 (further down) | 3 (1 marked rule): `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_rules_registration_hold.py` | {…} — nothing is taken from a start file that does not read |
| `area_state.missing_start_warning` | `labkit/formats/area_state.py` | WARNING | GUARANTEED | not executable | finalize.finalize_area · 2 (further down), report_check.chain_gaps · 2 (further down), runlog.Run.__init__ · 2 (further down) | 6 (2 marked rule): `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_rules_registration_hold.py` | {…} |
| `area_state.unassigned_record_warning` | `labkit/formats/area_state.py` | WARNING | GUARANTEED | not executable | finalize.finalize_area · 2 (further down), report_check.chain_gaps · 2 (further down) | 3 (1 marked rule): `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_rules_registration_hold.py` | the record of run {…} does not read, and neither a start file nor the run index names it:… |
| `protocol_history.check_protocol_id` | `labkit/formats/protocol_history.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 1 (further down) | 6 (0 marked rule): `tests/test_agent_hooks_undecided.py`, `tests/test_exploration_link_scenario.py`, `tests/test_protocol_id.py` | {…}: DUPLICATE protocol id {…} — also carried by {…}. An id binds runs to ONE protocol |
| `protocol_history.check_protocol_id` | `labkit/formats/protocol_history.py` | WARNING | GUARANTEED | violated | preflight.preflight_area · 1 (further down) | 2 (0 marked rule): `tests/test_check_stations.py`, `tests/test_protocol_id.py` | {…}: WARNING: protocol id changed against HEAD ({…} -> {…}) — runs bound to the old id st… |
| `reference.comparison_gaps` | `labkit/formats/reference.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 9 (further down) | 2 (0 marked rule): `tests/test_reference.py`, `tests/test_registration_committed.py` | the head registers [reference] on `{…}`, and the run recorded no verdict (no `{…}` in met… |
| `reference.comparison_gaps` | `labkit/formats/reference.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 9 (further down) | 1 (0 marked rule): `tests/test_reference.py` | the verdict in metrics.json does not read: `{…}` = {…}, `{…}` = {…} — written beside the … |
| `exploration_hold.unknown_step_hold` | `labkit/gates/exploration_hold.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down) | 1 (0 marked rule): `tests/test_exploration_hold.py` | the step a run was measured under cannot be told: {…}{…} — the comparison with its basis … |
| `finalize.station_intent_keys_in_metrics` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 3 | 1 (0 marked rule): `tests/test_finalize.py` | intent-check: {…} |
| `finalize.station_run_code` | `labkit/gates/finalize.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 4 | 1 (0 marked rule): `tests/test_run_code.py` | {…} |
| `finalize.station_answer_reading` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 4 | 1 (0 marked rule): `tests/test_run_code.py` | the prompts {…} re-reads with cannot be held to {…}'s: {…} |
| `finalize.station_open_fields` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 5 | 5 (0 marked rule): `tests/test_field_values.py`, `tests/test_finalize_steps.py`, `tests/test_report_check_areas.py` | {…}: {…} |
| `finalize.station_open_fields` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | computed | finalize.finalize_area · 5 | 1 (0 marked rule): `tests/test_finalize.py` | {…} |
| `finalize.run_file_unread` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | not executable | finalize.finalize_area · 4 (further down), finalize.finalize_area · 7 (further down), finalize.finalize_area · 9 (further down) | 1 (0 marked rule): `tests/test_read_causes.py` | {…} |
| `finalize.run_file_unread` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 4 (further down), finalize.finalize_area · 7 (further down), finalize.finalize_area · 9 (further down) | 4 (0 marked rule): `tests/test_finalize_steps.py`, `tests/test_origin_check.py`, `tests/test_read_causes.py`, `tests/test_reference.py` | {…} |
| `finalize.station_reference` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 9 | 1 (0 marked rule): `tests/test_reference.py` | {…}: {…} |
| `finalize.station_reference` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 9 | 1 (0 marked rule): `tests/test_reference.py` | {…}: {…} |
| `finalize.declared_run_gaps` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 1 (further down) | 8 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_finalize_steps.py`, `tests/test_migration_bar.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py` | {…} |
| `preflight.station_protocol_fields` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 1 | 1 (0 marked rule): `tests/test_field_values.py` | REPEATED (must): {…} |
| `preflight.station_protocol_fields` | `labkit/gates/preflight.py` | WARNING | GUARANTEED | violated | preflight.preflight_area · 1 | 36 (0 marked rule): 8 files, [checks overview](checks-overview.md) | missing (should): {…} |
| `preflight.station_protocol_fields` | `labkit/gates/preflight.py` | WARNING | GUARANTEED | violated | preflight.preflight_area · 1 | 3 (0 marked rule): `tests/test_agent_hooks.py`, `tests/test_preflight_stations.py` | {…}:{…}: placeholder (should): {…} |
| `preflight.station_audit_records` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 3 | 2 (0 marked rule): `tests/test_preflight.py`, `tests/test_preflight_stations.py` | {…} |
| `preflight.station_handed_over_elsewhere` | `labkit/gates/preflight.py` | WARNING | GUARANTEED | violated | preflight.preflight_area · 3 | 2 (0 marked rule): `tests/test_preflight.py`, `tests/test_preflight_stations.py` | {…} |
| `preflight.station_handed_over_elsewhere` | `labkit/gates/preflight.py` | WARNING | GUARANTEED | violated | preflight.preflight_area · 3 | 2 (0 marked rule): `tests/test_preflight.py`, `tests/test_preflight_stations.py` | {…} |
| `preflight.station_scope_stamp` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 5 | 6 (0 marked rule): `tests/test_preflight_stations.py` | cannot stamp the area's scope: {…} |
| `preflight.station_scope_stamp` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | violated | preflight.preflight_area · 5 | 2 (0 marked rule): `tests/test_explored_in.py`, `tests/test_preflight_stations.py` | cannot stamp the area's scope: {…} |
| `preflight.tell_test_run` | `labkit/gates/preflight.py` | WARNING | GUARANTEED | not executable | finalize.finalize_area · 8 (further down), preflight.preflight_area · 8 (further down) | 1 (0 marked rule): `tests/test_finalize_steps.py` | pytest is not installed in this interpreter — tests not run |
| `preflight.tell_test_run` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | not executable | finalize.finalize_area · 8 (further down), preflight.preflight_area · 8 (further down) | 2 (0 marked rule): `tests/test_finalize_steps.py`, `tests/test_read_causes.py` | {…} did not run{…} — {…} |
| `registered_report._undetermined_duty` | `labkit/gates/registered_report.py` | BLOCKER | GUARANTEED | not executable | report_check.protocol_verdict · 0 (further down), report_check.chain_gaps · 2 (further down) | 13 (0 marked rule): `tests/test_audit.py`, `tests/test_end_to_end.py`, `tests/test_registered_report_stations.py`, `tests/test_registration_committed.py` | {…}: whether it owes a report cannot be told — {…} |
| `registered_report.registered_review` | `labkit/gates/registered_report.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 8 (further down) | 1 (0 marked rule): `tests/test_registered_report_stations.py` | {…}: its discussion blocks do not read — {…} |
| `registration_hold.release_unchecked` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down) | 3 (0 marked rule): `tests/test_finalize_steps.py`, `tests/test_unread_registration.py` | whether a correction in place releases what the number is about cannot be checked: {…} |
| `registration_hold.unread_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | violated | finalize.finalize_area · 2 (further down) | 12 (0 marked rule): `tests/test_audit.py`, `tests/test_origin_scenario.py`, `tests/test_registration_committed.py`, `tests/test_unread_registration.py`, `tests/test_ways_out.py` | what the number is about cannot be compared with its first measurement: {…} — the compari… |
| `registration_hold.unread_history_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | not executable | finalize.finalize_area · 2 (further down), report_check.chain_gaps · 2 (further down) | 6 (1 marked rule): `tests/test_finalize_steps.py`, `tests/test_registration_committed.py`, `tests/test_report_check_stations.py`, `tests/test_rules_registration_hold.py`, `tests/test_unread_registration.py` | {…} — the runs and start files a commit holds were not read back, so whether a start file… |
| `registration_hold.binding_conflict_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | not executable | finalize.finalize_area · 2 (further down) | 3 (1 marked rule): `tests/test_end_to_end.py`, `tests/test_registration_station.py`, `tests/test_rules_registration_hold.py` | which protocol a run belongs to is contradicted: {…} — no file is taken over another, so … |
| `registration_hold.missing_start_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | not executable | finalize.finalize_area · 2 (further down) | 6 (1 marked rule): `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_finalize_steps.py`, `tests/test_rules_registration_hold.py` | {…} — which protocol it was bound to at its start and when it started cannot be checked, … |
| `registration_hold.lost_record_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | not executable | finalize.finalize_area · 2 (further down) | 15 (5 marked rule): `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_registration_station.py`, `tests/test_rules_registration_hold.py` | what the number is about cannot be compared with its first measurement: {…} — {…} may hav… |
| `registration_hold.later_record_warning` | `labkit/gates/registration_hold.py` | WARNING | GUARANTEED | violated | finalize.finalize_area · 2 (further down), report_check.chain_gaps · 2 (further down) | 7 (1 marked rule): `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_registration_committed.py`, `tests/test_rules_registration_hold.py` | {…} — the start files put {…} after that of a measurement of this protocol that reads, an… |
| `report_check.repeated_gaps` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 1 (0 marked rule): `tests/test_report_check_areas.py` | {…}: {…} |
| `report_check.registration_gaps` | `labkit/gates/report_check.py` | WARNING | GUARANTEED | violated | report_check.chain_gaps · 2 | 25 (0 marked rule): `tests/test_registration_committed.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py` | not a git repository — the registration cannot be held to the commit of the first measure… |
| `report_check._registration_at` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 1 (0 marked rule): `tests/test_registration_committed.py` | {…} recorded no commit ({…}{…}) — what the run started from is unknown, so the registrati… |
| `report_check._registration_at` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 3 (0 marked rule): `tests/test_registration_committed.py` | {…} ({…}{…}) recorded a commit this repository does not hold (a rewritten history, a shal… |
| `report_check._registration_at` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 2 (0 marked rule): `tests/test_registration_committed.py`, `tests/test_unread_registration.py` | {…} at {…} ({…}{…}) cannot be read: {…} — the registration that stood before the number c… |
| `report_check.analysis_audit_gap` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 3 (0 marked rule): `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py` | no answering run to hold it to — {…} |
| `report_check.analysis_audit_gap` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 3 (0 marked rule): `tests/test_handovers.py`, `tests/test_report_check_stations.py` | the analysis audit cannot be held to the run: {…} |
| `report_check.analysis_audit_gap` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | computed | report_check.chain_gaps · 5 (further down) | 3 (0 marked rule): `tests/test_protocol_fill.py`, `tests/test_report_check_stations.py` | the analysis audit cannot be held to the area: {…} |
| `report_check.analysis_audit_gap` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 5 (further down) | 9 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_handovers.py` | no analysis audit covers the area as it is now, and none can run — {…} |
| `report_check.unreportable_gaps` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 4 | 1 (0 marked rule): `tests/test_report_check_stations.py` | {…}: no config.json in this file state — the run's record cannot be checked |
| `report_check.cut_off_adoption_gaps` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 0 | 1 (0 marked rule): `tests/test_adopt.py` | {…}: an adoption was cut off during its check — the protocol may hold a proposal no check… |
| `report_check.declaration_gaps` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 1 | 3 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py` | {…}: {…} |
| `report_check.recomputation_findings` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | not executable | report_check.chain_gaps · 6 | 1 (0 marked rule): `tests/test_gate_timeouts.py` | {…} — no result, the numbers are not held to the run |
| `report_decisions.limit_gaps` | `labkit/gates/report_decisions.py` | BLOCKER | GUARANTEED | computed | report_check.chain_gaps · 5 (further down) | 4 (0 marked rule): `tests/test_origin_scenario.py`, `tests/test_report_decisions_stations.py` | the result cannot be rendered from {…}: {…} |
| `report_decisions.followup_findings` | `labkit/gates/report_decisions.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 7 | 1 (0 marked rule): `tests/test_report_decisions_stations.py` | the carried findings of {…} do not form a chain: {…} |
| `report_decisions.check_decision_reviews_read` | `labkit/gates/report_decisions.py` | WARNING | GUARANTEED | violated | report_check.chain_gaps · 7 (further down) | 3 (1 marked rule): `tests/test_decision_review.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` | a review nobody can read: {…} |
| `report_exploration.unresolved_link_hold` | `labkit/gates/report_exploration.py` | BLOCKER | GUARANTEED | not executable | report_check.chain_gaps · 2 (further down) | 18 (8 marked rule): `tests/test_exploration_link_scenario.py`, `tests/test_explored_in.py`, `tests/test_rules_report_exploration.py` | exploration link: [explored_in] protocol = {…} names {…} — the exploration this confirmat… |
| `report_hold.staged_area_gap` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 8 (further down) | 17 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_next_step.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_hold_stations.py` | {…}: the working tree differs from the index ({…}) — {…} the tree, the commit holds the i… |
| `report_hold.through_gap` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 8 (further down) | 2 (0 marked rule): `tests/test_reported_through.py` | {…} differs from what the analysis run's record and adoption say now — a stale rendering … |
| `report_hold.through_gaps` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_reported_through.py` | line {…}: the reported-through block of {…} repeats the block at line {…} — one block per… |
| `report_hold.link_gap` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 4 (0 marked rule): `tests/test_agent_hooks.py`, `tests/test_report_blocks.py` | {…}: a symbolic link to {…} — a report is held as a file at its own path, never through a… |
| `report_hold.discussion_sources` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_report_hold_stations.py` | {…} names {…}, and there is no such protocol |
| `report_hold.discussion_sources` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 2 (0 marked rule): `tests/test_area_state.py`, `tests/test_report_blocks.py` | {…}: {…}'s area has no runs/{…}/ — a discussion names a run of its protocol's area |
| `report_hold.review_gap` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 8 (further down) | 2 (0 marked rule): `tests/test_claim_review.py`, `tests/test_report_hold_stations.py` | {…}: its report review cannot be told — {…} |
| `report_hold.review_hold` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 8 (further down) | 2 (0 marked rule): `tests/test_handovers.py`, `tests/test_report_hold_stations.py` | {…}: {…} and has no clean report review of this state — and none can run: {…} |
| `report_hold.undeclared_findings` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_report_hold_stations.py` | {…}: cites a run of a protocol whose head does not read — {…} |
| `report_hold.undeclared_findings` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_report_check.py` | {…}: cites {…}, the answering run of {…}, which adopts it in the working tree but not in … |
| `report_hold.undeclared_findings` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | violated | — | 1 (0 marked rule): `tests/test_handovers.py` | {…}: cites {…}, the answering run of {…}, which has adopted no result — and neither its a… |
| `report_replacement._predecessor` | `labkit/gates/report_replacement.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 2 (0 marked rule): `tests/test_replacement.py` | the replacements run in a circle ({…}) |
| `report_replacement._undeclared_changes` | `labkit/gates/report_replacement.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 1 (0 marked rule): `tests/test_replacement.py` | the registrations cannot be compared — {…} |
| `report_replacement._undeclared_changes` | `labkit/gates/report_replacement.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 6 (0 marked rule): `tests/test_counter_cases.py`, `tests/test_replacement.py` | changed against {…} ({…}) and not declared: {…} {…} → {…} |
| `report_replacement._undeclared_changes` | `labkit/gates/report_replacement.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 2 (0 marked rule): `tests/test_replacement.py` | declares a change the registrations do not show: {…} {…} → {…} (the predecessor {…}, this… |
| `report_replacement._predecessor_open` | `labkit/gates/report_replacement.py` | BLOCKER | GUARANTEED | violated | report_check.chain_gaps · 2 (further down) | 1 (0 marked rule): `tests/test_report_replacement_stations.py` | the predecessor's audit records do not read: {…} |

## Not settled

### Open assignments

The site records that its rule is not decided: no sentence of the standard states its case, or the sentence reaches less far than the check. Why each is open: [the open assignments](notes/2026-11-11-open-assignments.md).

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `kept_number_check._criterion_n_warning` | `labkit/checks/kept_number_check.py` | WARNING | STATIC_EVIDENCE | suspected | finalize.finalize_area · 9 (further down) | not in the last trace | {…} |
| `model_check.arm_findings` | `labkit/checks/model_check.py` | WARNING | GUARANTEED | deviation | finalize.finalize_area · 1 (further down) | 1 (0 marked rule): `tests/test_arm_lines.py` | arm `{…}`: the protocol names fingerprint {…}, the answering run recorded no such value —… |
| `notes_check.check_file` | `labkit/checks/notes_check.py` | WARNING | GUARANTEED | deviation | — | 1 (0 marked rule): `tests/test_notes_check.py` | {…}:{…}: warning: no date in the meta line |
| `notes_check.check_file` | `labkit/checks/notes_check.py` | WARNING | GUARANTEED | deviation | — | 1 (0 marked rule): `tests/test_notes_check.py` | {…}:{…}: warning: none of the named scripts resolve in the repo ({…}{…}) — code paths may… |
| `notes_check.check_file` | `labkit/checks/notes_check.py` | WARNING | GUARANTEED | deviation | — | 1 (0 marked rule): `tests/test_notes_check.py` | {…}:{…}: warning: filename says related-* but the declared kind is {…} |
| `row_check._continued_with_other_code` | `labkit/checks/row_check.py` | BLOCKER | GUARANTEED | deviation | finalize.finalize_area · 1 (further down) | 1 (0 marked rule): `tests/test_row_provenance.py` | {…}: {…} row(s) come from {…}, which ran other code (script {…}, this run's {…}) — {…}'s … |
| `finalize.choose_answering_run` | `labkit/gates/finalize.py` | WARNING | STATIC_EVIDENCE | suspected | finalize.finalize_area · 1 (further down) | 9 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_finalize_steps.py`, `tests/test_protocol_runs.py`, `tests/test_repair_guidance.py`, `tests/test_withdrawal_order.py` | {…}: bound to this protocol and newer by name than the adopted run {…} — if one of them a… |
| `registered_report.report_binding_gap` | `labkit/gates/registered_report.py` | BLOCKER | GUARANTEED | deviation | report_check.chain_gaps · 2 (further down) | 14 (0 marked rule): `tests/test_registration_committed.py` | {…} registered {…} as its report {…}, and its head now registers none — the report a meas… |
| `registered_report.orphaned_report_duties` | `labkit/gates/registered_report.py` | BLOCKER | GUARANTEED | deviation | report_check.protocol_verdict · 0 (further down), report_check.chain_gaps · 2 (further down) | 4 (0 marked rule): `tests/test_registration_committed.py` | {…}: no protocol of the area carries the id {…}, under which it measured ({…}); that prot… |

### The cause passes the rule in

The site takes its assignment from the cause it reports, so the scan cannot read it; which cause carries which rule stands at the cause (the open ones are listed below).

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `code_check.promise_block_findings` | `labkit/checks/code_check.py` | BLOCKER | GUARANTEED | variable | preflight.preflight_area · 4 (further down) | 2 (0 marked rule): `tests/test_promise_preflight.py` | promise block: {…} |
| `code_check.promise_block_findings` | `labkit/checks/code_check.py` | BLOCKER | GUARANTEED | computed | preflight.preflight_area · 4 (further down) | 4 (0 marked rule): `tests/test_audit_robustness.py`, `tests/test_code_check.py`, `tests/test_promise_preflight.py` | [{…}] declared scope: {…} · runlog refuses the run |
| `intent_check.check_block_against_run` | `labkit/checks/intent_check.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 3 (further down), finalize.finalize_area · 7 (further down) | 2 (0 marked rule): `tests/test_intent_check.py`, `tests/test_promises.py` | {…}: {…}. |
| `intent_check.origin_intent_findings` | `labkit/checks/intent_check.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 7 (further down) | 1 (0 marked rule): `tests/test_intent_check.py` | {…}: promise block: {…} |
| `report_blocks.block_gaps` | `labkit/checks/report_blocks.py` | BLOCKER | GUARANTEED | variable | — | 2 (0 marked rule): `tests/test_next_step.py`, `tests/test_report_blocks_text.py` | {…}: {…} — a block shows an adopted result only |
| `report_blocks.block_gaps` | `labkit/checks/report_blocks.py` | BLOCKER | GUARANTEED | variable | — | 3 (0 marked rule): `tests/test_handovers.py`, `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py` | {…}: {…} — a block shows an adopted result only |
| `run_record_check.output_record_findings` | `labkit/checks/run_record_check.py` | BLOCKER | GUARANTEED | computed | finalize.finalize_area · 9 (further down) | 13 (3 marked rule): 8 files, [checks overview](checks-overview.md) | {…}: not the file run {…} recorded — {…} |
| `answering_run.AnsweringRun.explain` | `labkit/formats/answering_run.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 1 (further down), finalize.finalize_area · 3 (further down), report_check.protocol_verdict · 0 (further down), report_check.chain_gaps · 8 (further down) | 62 (0 marked rule): 24 files, [checks overview](checks-overview.md) | {…} |
| `evidence.change_blockers` | `labkit/formats/evidence.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 0 (further down), preflight.preflight_area · 3 (further down), report_check.protocol_verdict · 0 (further down), report_check.chain_gaps · 0 (further down), report_check.chain_gaps · 2 (further down), report_check.chain_gaps · 5 (further down), report_check.chain_gaps · 8 (further down), runlog.Run.__init__ · 2 (further down) | 8 (0 marked rule): `tests/test_evidence.py`, `tests/test_origin_scenario.py`, `tests/test_read_causes.py`, `tests/test_replacement.py`, `tests/test_report_blocks.py` | {…} |
| `evidence.change_blockers` | `labkit/formats/evidence.py` | BLOCKER | GUARANTEED | not executable | finalize.finalize_area · 0 (further down), preflight.preflight_area · 3 (further down), report_check.protocol_verdict · 0 (further down), report_check.chain_gaps · 0 (further down), report_check.chain_gaps · 2 (further down), report_check.chain_gaps · 5 (further down), report_check.chain_gaps · 8 (further down), runlog.Run.__init__ · 2 (further down) | 2 (0 marked rule): `tests/test_evidence_unread.py`, `tests/test_read_causes.py` | {…} |
| `protocol_history.check_annotation_validity` | `labkit/formats/protocol_history.py` | BLOCKER | GUARANTEED | variable | preflight.preflight_area · 1 (further down) | 3 (0 marked rule): `tests/test_annotation_validity.py` | {…} — {…} |
| `exploration_hold.live_holds` | `labkit/gates/exploration_hold.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 2 (further down) | 9 (0 marked rule): `tests/test_adopt_per_protocol.py`, `tests/test_exploration_hold.py`, `tests/test_registration_station.py`, `tests/test_report_check.py`, `tests/test_source_lines.py` | what the number is about changed after the answering run {…}: {…} (as the protocol stands… |
| `finalize.unreportable_warnings` | `labkit/gates/finalize.py` | WARNING | GUARANTEED | variable | finalize.finalize_area · 1 (further down) | 14 (0 marked rule): 9 files, [checks overview](checks-overview.md) | the answering run {…}: {…} — its number cannot be reported (report-check refuses it) |
| `finalize.station_declared_scopes` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | computed | finalize.finalize_area · 4 | 1 (0 marked rule): `tests/test_finalize.py` | declared scope cannot be compared with what {…} recorded: {…} |
| `finalize.station_open_fields` | `labkit/gates/finalize.py` | WARNING | GUARANTEED | variable | finalize.finalize_area · 5 | 20 (0 marked rule): 7 files, [checks overview](checks-overview.md) | {…}:{…}: {…} |
| `finalize.station_data_counts` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 5 (further down) | 3 (0 marked rule): `tests/test_finalize_steps.py` | {…} |
| `finalize.station_kept_number` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 9 | 2 (0 marked rule): `tests/test_kept.py`, `tests/test_reference.py` | {…}: {…}{…} |
| `finalize._refuse` | `labkit/gates/finalize.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 0 | 3 (0 marked rule): `tests/test_finalize.py` | {…} |
| `preflight.preflight_area` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | variable | preflight.preflight_area · 1 | 4 (0 marked rule): `tests/test_preflight.py`, `tests/test_preflight_stations.py` | HEAD (must): {…} |
| `preflight.station_protocol_fields` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | variable | preflight.preflight_area · 1 | 38 (0 marked rule): 10 files, [checks overview](checks-overview.md) | {…} |
| `preflight._owed` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | variable | preflight.preflight_area · 3 (further down), preflight.preflight_area · 8 (further down) | 18 (0 marked rule): 7 files, [checks overview](checks-overview.md) | {…} |
| `preflight._owed` | `labkit/gates/preflight.py` | WARNING | GUARANTEED | variable | preflight.preflight_area · 3 (further down), preflight.preflight_area · 8 (further down) | 37 (0 marked rule): 9 files, [checks overview](checks-overview.md) | {…} |
| `preflight.tell_test_run` | `labkit/gates/preflight.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 8 (further down), preflight.preflight_area · 8 (further down) | 12 (0 marked rule): 9 files, [checks overview](checks-overview.md) | {…} failed{…} — {…} |
| `registered_report.result_owed` | `labkit/gates/registered_report.py` | BLOCKER | GUARANTEED | variable | report_check.chain_gaps · 8 (further down) | 12 (0 marked rule): `tests/test_origin_scenario.py`, `tests/test_report_check.py`, `tests/test_reported_through.py` | {…} registers {…} as its report, and {…} carries neither {…} nor the protocol's handover … |
| `registered_report.missing_report` | `labkit/gates/registered_report.py` | BLOCKER | GUARANTEED | variable | report_check.chain_gaps · 8 (further down) | 1 (0 marked rule): `tests/test_adopt.py` | {…} registers {…} as its report; the report is missing ({…}), and its area holds a measur… |
| `registered_report.missing_report` | `labkit/gates/registered_report.py` | BLOCKER | GUARANTEED | variable | report_check.chain_gaps · 8 (further down) | 5 (0 marked rule): `tests/test_next_step.py`, `tests/test_registration_committed.py`, `tests/test_report_check.py` | {…} registers {…} as its report; the report is missing ({…}), and its area holds a measur… |
| `registration_hold.registration_changes` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 2 (further down) | 6 (0 marked rule): `tests/test_registration_committed.py` | the registration changed after the first measurement {…}{…}: {…} (recorded by the answeri… |
| `registration_hold.seen_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 2 (further down) | 34 (17 marked rule): `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_registration_committed.py`, `tests/test_registration_station.py`, `tests/test_repair_guidance.py`, `tests/test_rules_registration_hold.py` | what the number is about changed after the first measurement {…}{…}: {…} (as the answerin… |
| `registration_hold.split_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 2 (further down) | 8 (0 marked rule): `tests/test_exploration_hold.py`, `tests/test_registration_committed.py` | the first measurements saw different texts of what the number is about: {…} — {…} — which… |
| `registration_hold.now_hold` | `labkit/gates/registration_hold.py` | BLOCKER | GUARANTEED | variable | finalize.finalize_area · 2 (further down) | 24 (15 marked rule): `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_repair_guidance.py`, `tests/test_rules_registration_hold.py`, `tests/test_unread_registration.py` | what the number is about changed after the first measurement {…}{…}: {…} (as the protocol… |
| `report_check.freeze_gaps` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | variable | report_check.chain_gaps · 2 | 15 (0 marked rule): `tests/test_audit.py`, `tests/test_protocol_fill.py`, `tests/test_registration_committed.py`, `tests/test_replacement.py`, `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py` | {…}: {…} |
| `report_check.analysis_audit_gap` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | variable | report_check.chain_gaps · 5 (further down) | 9 (0 marked rule): `tests/test_exploration_link_scenario.py`, `tests/test_explored_in.py`, `tests/test_report_check_stations.py` | no analysis audit covers the area as it is now, and none can until the exploration link r… |
| `report_check.analysis_audit_gap` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | variable | report_check.chain_gaps · 5 (further down) | 107 (0 marked rule): 26 files, [checks overview](checks-overview.md) | {…} |
| `report_check.unreportable_gaps` | `labkit/gates/report_check.py` | BLOCKER | GUARANTEED | variable | report_check.chain_gaps · 4 | 12 (0 marked rule): `tests/test_agent_hooks.py`, `tests/test_finalize_open_findings.py`, `tests/test_protocol_fill.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py` | the answering run {…}: {…} — its number cannot be reported; a reported number owes {…} |
| `report_hold.hold_report` | `labkit/gates/report_hold.py` | BLOCKER | GUARANTEED | variable | — | 1 (0 marked rule): `tests/test_report_hold_stations.py` | {…}: {…} |
| `report_replacement.replacement_gaps` | `labkit/gates/report_replacement.py` | BLOCKER | GUARANTEED | variable | report_check.chain_gaps · 2 | 2 (0 marked rule): `tests/test_report_replacement_stations.py` | {…}: {…} |
| `report_replacement._predecessor` | `labkit/gates/report_replacement.py` | BLOCKER | GUARANTEED | variable | report_check.chain_gaps · 2 (further down) | 2 (0 marked rule): `tests/test_replacement.py`, `tests/test_report_replacement_stations.py` | [replaces] protocol = {…} names {…} |

### Places that name an open assignment a site receives

| Place | Function |
|---|---|
| `labkit/checks/run_record_check.py` | `checks.run_record_check.output_record_findings` |
| `labkit/formats/answering_run.py` | `formats.answering_run.cannot_answer_rule` |
| `labkit/formats/evidence.py` | `formats.evidence.told` |
| `labkit/formats/evidence.py` | `formats.evidence.told` |
| `labkit/formats/evidence.py` | `formats.evidence.told` |
| `labkit/formats/evidence.py` | `formats.evidence.told` |
| `labkit/formats/evidence.py` | `formats.evidence.told` |
| `labkit/formats/promises.py` | `formats.promises.parse_outcomes` |
| `labkit/formats/promises.py` | `formats.promises.parse_outcomes` |
| `labkit/formats/promises.py` | `formats.promises._outcome` |
| `labkit/formats/promises.py` | `formats.promises._outcome` |
| `labkit/formats/promises.py` | `formats.promises.parse_block` |
| `labkit/formats/promises.py` | `formats.promises.parse_block` |
| `labkit/formats/promises.py` | `formats.promises.block_drift` |
| `labkit/formats/protocol_check.py` | `formats.protocol_check.freeze_must_gaps` |
| `labkit/formats/protocol_check.py` | `formats.protocol_check.check_fields` |
| `labkit/formats/protocol_history.py` | `formats.protocol_history.bound_validation` |
| `labkit/formats/protocol_history.py` | `formats.protocol_history.bound_validation` |
| `labkit/gates/finalize.py` | `gates.finalize` |
| `labkit/gates/finalize.py` | `gates.finalize.station_open_fields` |
| `labkit/gates/registered_report.py` | `gates.registered_report.report_owed` |
| `labkit/gates/registered_report.py` | `gates.registered_report.missing_report` |
| `labkit/gates/registration_hold.py` | `gates.registration_hold.scope_rule` |
| `labkit/gates/registration_hold.py` | `gates.registration_hold.registration_rule` |
| `labkit/gates/report_replacement.py` | `gates.report_replacement.replacement_gaps` |

### Sites that record no assignment

An exit (`raise SystemExit(<message>)`) and a printed `WARNING:` or `BLOCKER:` line carry no rule as data.

| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |
|---|---|---|---|---|---|---|---|
| `prompt_check.require_registered_templates` | `labkit/checks/prompt_check.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_prompt_templates.py` | {…}: no such protocol — no template is held to it |
| `prompt_check.require_registered_templates` | `labkit/checks/prompt_check.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_prompt_templates.py` | {…} |
| `prompt_check.require_registered_templates` | `labkit/checks/prompt_check.py` | exit | none | none | — | 3 (0 marked rule): `tests/test_prompt_templates.py`, `tests/test_public_api.py` | {…}: {…} of {…} template(s) the run uses are not registered as they are — refused before … |
| `protocol_report.print_report` | `labkit/checks/protocol_report.py` | WARNING | none | none | — | not traced (printed line) | {…}: WARNING: preflight_audit: {…} |
| `protocol_report.print_report` | `labkit/checks/protocol_report.py` | WARNING | none | none | — | not traced (printed line) | {…}:{…}: WARNING: {…} written before any run — no completed run is bound to this protocol… |
| `protocol_report.print_report` | `labkit/checks/protocol_report.py` | WARNING | none | none | — | not traced (printed line) | {…}: WARNING: {…} |
| `recheck.chosen_run` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_refusals.py` | recheck: {…} |
| `recheck.chosen_run` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_binding.py` | recheck: the protocol carries no stamped id ([protocol] id) — no run binds to it; `labkit… |
| `recheck.chosen_run` | `labkit/checks/recheck.py` | exit | none | none | — | 12 (0 marked rule): `tests/test_answering_run_exhaustive.py`, `tests/test_end_to_end.py`, `tests/test_next_step.py`, `tests/test_protocol_fill.py`, `tests/test_public_api.py`, `tests/test_recheck_binding.py` | recheck: {…}{…} |
| `recheck._named_run` | `labkit/checks/recheck.py` | exit | none | none | — | 2 (0 marked rule): `tests/test_completion_consumers.py`, `tests/test_protocol_fill.py` | recheck: {…} is not a completed run ({…}) |
| `recheck._named_run` | `labkit/checks/recheck.py` | exit | none | none | — | 2 (0 marked rule): `tests/test_completion_consumers.py`, `tests/test_recheck_refusals.py` | recheck: {…} |
| `recheck._named_run` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_repeats.py` | recheck: {…} is a repeat of {…} — supporting evidence, never the answer; `02_analyze.py -… |
| `recheck._named_run` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_binding.py` | recheck: {…} is bound to {…}, not to {…} — it answers another question |
| `recheck.protocol_named` | `labkit/checks/recheck.py` | exit | none | none | — | 3 (0 marked rule): `tests/test_origin_scenario.py`, `tests/test_recheck_per_protocol.py` | recheck: {…} |
| `recheck.script_module` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_refusals.py` | recheck: {…} |
| `recheck.script_module` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_refusals.py` | recheck: run {…}: {…} does not import |
| `recheck.registered_output` | `labkit/checks/recheck.py` | exit | none | none | — | 3 (0 marked rule): `tests/test_recheck_outputs_scenario.py`, `tests/test_recheck_refusals.py` | recheck: run {…} did not register {…} as an output |
| `recheck.pin` | `labkit/checks/recheck.py` | exit | none | none | — | 9 (0 marked rule): 7 files, [checks overview](checks-overview.md) | recheck: {…} is not the file run {…} recorded — {…}; rerun the script or name that run |
| `recheck.scopes_unchanged` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_promises.py` | recheck: declared scope cannot be compared with what run {…} recorded: {…}, or recheck fr… |
| `recheck.scopes_unchanged` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_promises.py` | recheck: declared scope changed since run {…}: {…} — rerun, or recheck from that run's co… |
| `recheck.require_run_code` | `labkit/checks/recheck.py` | exit | none | none | — | 12 (0 marked rule): `tests/test_adopt_per_protocol.py`, `tests/test_end_to_end.py`, `tests/test_exploration_link_scenario.py`, `tests/test_next_step.py`, `tests/test_origin_scenario.py`, `tests/test_run_code.py` | recheck: the code that computed run {…} is not the code here now: {…} — recomputing with … |
| `recheck.protocol_as_run_saw` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_refusals.py` | recheck: run {…}: {…} |
| `recheck.protocol_as_run_saw` | `labkit/checks/recheck.py` | exit | none | none | — | 3 (0 marked rule): `tests/test_recheck_own_text.py`, `tests/test_recheck_refusals.py` | recheck: the protocol run {…} was measured under cannot be read back: {…} — what it regis… |
| `recheck.kept_keys` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_refusals.py` | recheck: run {…}: {…} |
| `recheck.block_unchanged` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_audit_robustness.py` | recheck: run {…}: {…} |
| `recheck.block_unchanged` | `labkit/checks/recheck.py` | exit | none | none | — | 3 (0 marked rule): `tests/test_promises.py`, `tests/test_recheck_own_text.py` | recheck: run {…} {…} |
| `recheck.output_rows` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck.py` | recheck: run {…}: output {…} ({…}) is no row file — {…}. The recomputation reads row file… |
| `recheck.require_agreement` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck.py` | recheck: the kept number is missing — {…}: the number the protocol reports must stand in … |
| `recheck.require_agreement` | `labkit/checks/recheck.py` | exit | none | none | — | 4 (0 marked rule): `tests/test_evidence_unread.py`, `tests/test_recheck.py` | recheck: metrics.json and the recomputation disagree — intent keys on one side only {…}, … |
| `recheck.require_agreement` | `labkit/checks/recheck.py` | exit | none | none | — | 9 (0 marked rule): `tests/test_recheck.py`, `tests/test_recheck_inputs.py`, `tests/test_recheck_outputs_scenario.py`, `tests/test_recheck_own_text.py` | recheck: recomputation differs from metrics.json in the identifiers or the kept number {…} |
| `recheck.cited` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_refusals.py` | recheck: {…}: no such note |
| `recheck.cited` | `labkit/checks/recheck.py` | exit | none | none | — | 24 (0 marked rule): 7 files, [checks overview](checks-overview.md) | recheck: {…} has no answer yet — `{…}` writes it once that run's analysis audit is decide… |
| `recheck.cited` | `labkit/checks/recheck.py` | exit | none | none | — | 3 (0 marked rule): `tests/test_recheck.py` | recheck: numbers not in {…}: {…} |
| `recheck.cited` | `labkit/checks/recheck.py` | exit | none | none | — | 2 (0 marked rule): `tests/test_end_to_end.py`, `tests/test_recheck.py` | recheck: {…} does not cite run {…} |
| `recheck.reads_another_run` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_refusals.py` | recheck: run {…}: {…} |
| `recheck.inputs_pinned` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_refusals.py` | recheck: run {…}: {…} |
| `recheck.inputs_pinned` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_inputs.py` | recheck: run {…} recorded no input file — nothing to recompute from; hold its own output … |
| `recheck.inputs_pinned` | `labkit/checks/recheck.py` | exit | none | none | — | 5 (0 marked rule): `tests/test_origin_scenario.py`, `tests/test_recheck_inputs.py` | recheck: run {…}: {…} — not recomputed from inputs that are not the ones it read |
| `recheck.inputs_pinned` | `labkit/checks/recheck.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_recheck_inputs.py` | recheck: run {…}: data[{…}] = {…} is not the input it read: {…}, the run recorded sha256 … |
| `audit._record` | `labkit/gates/audit.py` | WARNING | none | none | — | not traced (printed line) | scope WARNING: {…} |
| `usability.stage` | `labkit/probes/usability.py` | WARNING | none | none | — | not traced (printed line) | usability |
| `batch.Ledger.require_complete` | `labkit/run/batch.py` | exit | none | none | — | 6 (0 marked rule): `tests/test_batch_ledger.py`, `tests/test_template_items.py` | {…}: the output does not balance its {…} input items — {…}. The run is NOT complete. |
| `batch.Store.__enter__` | `labkit/run/batch.py` | exit | none | none | finalize.finalize_area · 1 (further down) | 8 (0 marked rule): `tests/test_batch.py` | {…} exists — another run is writing this output: {…} {…} |
| `code_repos.require_recordable` | `labkit/run/code_repos.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_code_repos.py` | runlog: the run imports untracked code it cannot record (above {…} MB, in no commit): {…} |
| `detached.main` | `labkit/run/detached.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_run_start_refusals.py` | usage: python -P -m labkit.run.detached FD AREA UNSTARTED LOG -- COMMAND… (started by `ru… |
| `endpoint_lease._refuse` | `labkit/run/endpoint_lease.py` | exit | none | none | — | 6 (0 marked rule): `tests/test_endpoint_lease.py` | llm: endpoint {…} is leased to alias '{…}' (pid {…}, {…}, since {…}) — refusing to run '{… |
| `lanes.Lanes.balance` | `labkit/run/lanes.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_lanes.py` | {…}: rows of {…} instruments — {…} — one file holds one measurement: write a new output f… |
| `lanes.Lanes.require_registered_prompts` | `labkit/run/lanes.py` | exit | none | none | — | 1 (0 marked rule): `tests/test_lanes.py` | {…} |
| `lanes.Lanes.require_registered_prompts` | `labkit/run/lanes.py` | exit | none | none | — | 2 (0 marked rule): `tests/test_lanes.py` | {…}: the prompt this script sends is not the registered one — {…} line(s) the Prompt bloc… |
| `llm_cache._require_declared` | `labkit/run/llm_cache.py` | exit | none | none | — | 2 (0 marked rule): `tests/test_llm_cache.py` | llm_cache: the lab has not declared a cache — a cached answer repeats instead of measurin… |
| `runlog._repeat_parent` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 3 (further down) | 1 (0 marked rule): `tests/test_repeats.py` | runlog: {…} is itself a repeat of {…} |
| `runlog._repeat_draw` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 3 | 1 (0 marked rule): `tests/test_repeats.py` | runlog: repeat_of and derived_from exclude each other — a repeat asks the model again, a … |
| `runlog._repeat_draw` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 3 | 1 (0 marked rule): `tests/test_repeats.py` | runlog: repeat_of={…}: the next draw number cannot be counted — {…} |
| `runlog._repeat_draw` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 3 | 1 (0 marked rule): `tests/test_run_start_refusals.py` | runlog: repeat_of={…}: {…} |
| `runlog._repeat_draw` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 3 | 3 (0 marked rule): `tests/test_repeats.py` | runlog: this run is no repeat of {…} — it measures something else: {…} |
| `runlog._declared_under` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_installed_version.py` | runlog: labkit runs from a source tree that is not installed, so the version this run's a… |
| `runlog._decide_origins_and_warn` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 2 | 7 (0 marked rule): `tests/test_input_origins.py`, `tests/test_public_api.py` | {…} |
| `runlog.Run._write_start_file` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 3 | 1 (0 marked rule): `tests/test_run_starts.py` | runlog: {…} exists — a run with the id {…} started before, and its start file is never ov… |
| `runlog.Run._write_start_file` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 3 | 1 (0 marked rule): `tests/test_run_starts.py` | runlog: the start of {…} could not be recorded in {…}: {…} — the run did not start, and n… |
| `runlog._require_no_open_twin` | `labkit/run/runlog.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_runlog_wait.py` | runlog: {…} is still measuring in {…}: {…} — a second measurement beside it would read an… |
| `start_check.protocol_binding` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down) | 1 (0 marked rule): `tests/test_run_start_refusals.py` | runlog: protocol={…} is not one of the PROTOCOL-*.md in the run's area ({…}): {…} |
| `start_check.protocol_binding` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down) | 2 (0 marked rule): `tests/test_run_start_refusals.py`, `tests/test_run_starts.py` | runlog: {…} protocols in {…} — nothing would say which one this run belongs to: {…} |
| `start_check.protocol_binding` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down) | 4 (0 marked rule): `tests/test_protocol_identity.py`, `tests/test_runlog_freeze_gate.py` | runlog: {…}: {…} |
| `start_check._undecided_findings` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 (further down) | 1 (0 marked rule): `tests/test_runlog_unfrozen_blocker.py` | runlog: {…} |
| `start_check._audit_unavailable` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 (further down) | 1 (0 marked rule): `tests/test_run_start_refusals.py` | runlog: LABKIT_UNFROZEN=1 — the area cannot be stamped ({…}), so no failed audit attempt … |
| `start_check._audit_unavailable` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 (further down) | 1 (0 marked rule): `tests/test_run_start_refusals.py` | runlog: promise block: {…} |
| `start_check._audit_unavailable` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 (further down) | 1 (0 marked rule): `tests/test_runlog_unfrozen_failed_audit.py` | runlog: {…} |
| `start_check._audit_unavailable` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 (further down) | 7 (0 marked rule): `tests/test_runlog_freeze_gate.py`, `tests/test_runlog_unfrozen_failed_audit.py` | runlog: this run declares run_kind='measurement' (a full run) on a protocol not ready for… |
| `start_check._promise_snapshot` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down) | 1 (0 marked rule): `tests/test_promises.py` | runlog: promise block: {…} |
| `start_check.foreground_timeout` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_runlog_freeze_gate.py` | runlog: {…}={…} is not a number of seconds >= 0 |
| `start_check.require_valid_reseed` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_repeats.py` | runlog: reseed draws a repeat's seed anew — it goes with repeat_of |
| `start_check.require_valid_reseed` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_repeats.py` | runlog: reseed: the config holds no integer `{…}` to draw anew ({…}) |
| `start_check.require_valid_reseed` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_repeats.py` | runlog: reseed: the protocol registers `{…}` = {…} — a spread over seeds needs a seed the… |
| `start_check.require_registration` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 3 (0 marked rule): `tests/test_registration_contract.py`, `tests/test_runlog_freeze_gate.py` | runlog: {…}: {…} |
| `start_check.require_registration` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 3 (0 marked rule): `tests/test_promises.py`, `tests/test_registration_contract.py` | runlog: {…}: {…} |
| `start_check.require_answer_reading` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_answer_reading_start.py` | runlog: answer_reading declares what a derived run re-reads its parent's answers with — i… |
| `start_check.require_answer_reading` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_run_start_refusals.py` | runlog: answer_reading: {…} lies in no git repository, so the module cannot be compared w… |
| `start_check.require_answer_reading` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_answer_reading_start.py` | runlog: answer_reading = {…}: no such file |
| `start_check.require_answer_reading` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_answer_reading_start.py` | runlog: answer_reading = {…} lies outside the repository {…} |
| `start_check.require_answer_reading` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_run_start_refusals.py` | runlog: answer_reading: the code {…} imports cannot be read: {…} |
| `start_check.require_answer_reading` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 1 (0 marked rule): `tests/test_answer_reading_start.py` | runlog: answer_reading = {…}: {…} does not import it, so it reads none of the answers |
| `start_check.completed_parent` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down), runlog.Run.__init__ · 3 (further down) | 2 (0 marked rule): `tests/test_repeats.py` | runlog: {…}={…}: {…} |
| `start_check.completed_parent` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down), runlog.Run.__init__ · 3 (further down) | 6 (0 marked rule): `tests/test_builds_on.py`, `tests/test_completion_consumers.py`, `tests/test_repeats.py`, `tests/test_run_completion.py` | runlog: {…}={…} names no completed run under {…} ({…}){…} |
| `start_check._derived_parent` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down) | 1 (0 marked rule): `tests/test_repeats.py` | runlog: derived_from={…} is not a run id |
| `start_check._derived_parent` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down) | 1 (0 marked rule): `tests/test_repeats.py` | runlog: derived_from={…} is a repeat of {…} — supporting evidence, never the answer |
| `start_check.require_step_basis` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down) | 1 (0 marked rule): `tests/test_builds_on.py` | runlog: {…} |
| `start_check.require_step_basis` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down) | 1 (0 marked rule): `tests/test_builds_on.py` | runlog: [builds_on] run = {…} is a repeat of {…} — supporting evidence, never a step's ba… |
| `start_check.require_step_basis` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 (further down) | 1 (0 marked rule): `tests/test_builds_on.py` | runlog: [builds_on] run = {…} is bound to {…}, not to this protocol ({…}) |
| `start_check.require_exploration_link` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 (further down) | 1 (0 marked rule): `tests/test_explored_in.py` | runlog: {…} |
| `start_check.require_exploration_link` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 (further down) | 2 (0 marked rule): `tests/test_explored_in.py` | runlog: this is the first measurement of {…}, and its [explored_in] is no valid link to a… |
| `start_check.prepare` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 1 | 3 (0 marked rule): `tests/test_registration_contract.py`, `tests/test_run_kind.py`, `tests/test_runlog_freeze_gate.py` | runlog: run_kind='probe' is not allowed at repeat_cost='low' — this repeat cost has no se… |
| `start_check.require_detached` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 6 (0 marked rule): `tests/test_audit_robustness.py`, `tests/test_run_record_atomic.py`, `tests/test_runlog_freeze_gate.py`, `tests/test_runlog_wait.py` | runlog: this run declares run_kind='measurement' and sits in a foreground shell an agent … |
| `start_check.freeze_gate` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 2 (0 marked rule): `tests/test_runlog_unfrozen_blocker.py` | runlog: {…}, and a preflight audit found BLOCKER(s) nobody decided — not an unfrozen prot… |
| `start_check.freeze_gate` | `labkit/run/start_check.py` | exit | none | none | runlog.Run.__init__ · 2 | 22 (0 marked rule): `tests/test_exploration_hold.py`, `tests/test_obligations_scenario.py`, `tests/test_runlog_freeze_gate.py`, `tests/test_runlog_unfrozen_failed_audit.py` | runlog: {…}, but its protocol is not ready for one: {…} |
| `protocol_fill._handover_file` | `labkit/tools/protocol_fill.py` | WARNING | none | none | — | not traced (printed line) | WARNING: {…} |
