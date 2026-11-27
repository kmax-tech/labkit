# Checks overview — what each finding site tells, its rule, and the tests that reach it

Generated, do not edit: `python -m labkit.tools.check_overview` writes this page from the source and from `docs/checks-reach.tsv`, and `tests/test_check_overview.py` holds it equal to what the command writes. After a change to a finding site run the command again; the reach columns change only with a traced run of the suite (`python -m labkit.tools.test_inventory --reach docs/checks-reach.tsv`).

360 finding sites: 265 gate findings, 89 exits (`raise SystemExit(<message>)`), 6 printed lines. Reach as traced: 4808 passed, 4 skipped, 7961 subtests passed in 469.86s (0:07:49). 1 sites are not in that trace (added or reworded since, or the reach file holds no row yet), 1 rows of the trace name a site that is gone and are left out, the 6 printed lines are never traced.

How to read it. *Tells* is the constant text of the site's message, every value as `{…}` — the site's own words, not the name of the condition it checks; which condition a site holds, and whether a test asserts it, is established by reading the code and the test. *Rule* is the rule assignment the finding records as data; an exit and a printed line record none. *Reached*: `direct` — some test entered below a whole command; `only through commands`; `unreached`. Reaching a site is not asserting it. *Rule tests* counts the tests marked `rule` among those that reach the site. The commands of a module are a static estimate (a call graph by name), not a trace. Line numbers are left out on purpose: `python -m labkit.tools.check_inventory` prints them.

## Commands and the modules whose sites their code reaches

| Command | Modules (sites) |
|---|---|
| `claude-hook` | `labkit/checks/audit_binding.py` (5), `labkit/checks/code_check.py` (8), `labkit/checks/code_scan.py` (1), `labkit/checks/import_check.py` (4), `labkit/checks/intent_check.py` (9), `labkit/checks/kept_number_check.py` (2), `labkit/checks/model_check.py` (15), `labkit/checks/notes_check.py` (8), `labkit/checks/origin_check.py` (1), `labkit/checks/prompt_check.py` (5), `labkit/checks/protocol_report.py` (3), `labkit/checks/readme_check.py` (5), `labkit/checks/report_blocks.py` (10), `labkit/checks/result_render.py` (6), `labkit/checks/row_check.py` (5), `labkit/checks/run_record_check.py` (31), `labkit/formats/answering_run.py` (2), `labkit/formats/area_state.py` (3), `labkit/formats/evidence.py` (2), `labkit/formats/protocol_history.py` (3), `labkit/formats/reference.py` (5), `labkit/gates/exploration_hold.py` (4), `labkit/gates/finalize.py` (21), `labkit/gates/preflight.py` (20), `labkit/gates/registered_report.py` (7), `labkit/gates/registration_hold.py` (14), `labkit/gates/report_check.py` (24), `labkit/gates/report_decisions.py` (10), `labkit/gates/report_exploration.py` (2), `labkit/gates/report_hold.py` (22), `labkit/gates/report_replacement.py` (9), `labkit/run/batch.py` (1), `labkit/run/start_check.py` (3) |
| `code-check` | `labkit/checks/code_check.py` (9), `labkit/checks/code_scan.py` (1), `labkit/checks/import_check.py` (4), `labkit/checks/prompt_check.py` (5) |
| `codex-hook` | `labkit/checks/audit_binding.py` (5), `labkit/checks/code_check.py` (8), `labkit/checks/code_scan.py` (1), `labkit/checks/import_check.py` (4), `labkit/checks/intent_check.py` (9), `labkit/checks/kept_number_check.py` (2), `labkit/checks/model_check.py` (15), `labkit/checks/notes_check.py` (8), `labkit/checks/origin_check.py` (1), `labkit/checks/prompt_check.py` (5), `labkit/checks/protocol_report.py` (3), `labkit/checks/readme_check.py` (5), `labkit/checks/report_blocks.py` (10), `labkit/checks/result_render.py` (6), `labkit/checks/row_check.py` (5), `labkit/checks/run_record_check.py` (31), `labkit/formats/answering_run.py` (2), `labkit/formats/area_state.py` (3), `labkit/formats/evidence.py` (2), `labkit/formats/protocol_history.py` (3), `labkit/formats/reference.py` (5), `labkit/gates/exploration_hold.py` (4), `labkit/gates/finalize.py` (21), `labkit/gates/preflight.py` (20), `labkit/gates/registered_report.py` (7), `labkit/gates/registration_hold.py` (14), `labkit/gates/report_check.py` (24), `labkit/gates/report_decisions.py` (10), `labkit/gates/report_exploration.py` (2), `labkit/gates/report_hold.py` (22), `labkit/gates/report_replacement.py` (9), `labkit/run/batch.py` (1), `labkit/run/start_check.py` (3) |
| `finalize` | `labkit/checks/audit_binding.py` (5), `labkit/checks/code_scan.py` (1), `labkit/checks/intent_check.py` (9), `labkit/checks/kept_number_check.py` (2), `labkit/checks/model_check.py` (15), `labkit/checks/origin_check.py` (1), `labkit/checks/readme_check.py` (5), `labkit/checks/row_check.py` (5), `labkit/checks/run_record_check.py` (31), `labkit/formats/answering_run.py` (2), `labkit/formats/area_state.py` (3), `labkit/formats/evidence.py` (2), `labkit/formats/reference.py` (5), `labkit/gates/exploration_hold.py` (4), `labkit/gates/finalize.py` (21), `labkit/gates/preflight.py` (3), `labkit/gates/registration_hold.py` (14), `labkit/run/batch.py` (1) |
| `intent-check` | `labkit/checks/intent_check.py` (6), `labkit/formats/answering_run.py` (2) |
| `labkit-adopt` | `labkit/checks/audit_binding.py` (5), `labkit/checks/code_scan.py` (1), `labkit/checks/intent_check.py` (9), `labkit/checks/kept_number_check.py` (2), `labkit/checks/model_check.py` (15), `labkit/checks/origin_check.py` (1), `labkit/checks/readme_check.py` (5), `labkit/checks/recheck.py` (7), `labkit/checks/result_render.py` (6), `labkit/checks/row_check.py` (5), `labkit/checks/run_record_check.py` (31), `labkit/formats/answering_run.py` (2), `labkit/formats/area_state.py` (3), `labkit/formats/evidence.py` (2), `labkit/formats/reference.py` (5), `labkit/gates/exploration_hold.py` (4), `labkit/gates/finalize.py` (21), `labkit/gates/preflight.py` (3), `labkit/gates/registered_report.py` (7), `labkit/gates/registration_hold.py` (14), `labkit/gates/report_check.py` (24), `labkit/gates/report_decisions.py` (10), `labkit/gates/report_exploration.py` (2), `labkit/gates/report_hold.py` (7), `labkit/gates/report_replacement.py` (9), `labkit/run/batch.py` (1) |
| `labkit-audit` | `labkit/formats/answering_run.py` (2), `labkit/formats/evidence.py` (2), `labkit/gates/audit.py` (2), `labkit/gates/registration_hold.py` (4), `labkit/run/endpoint_lease.py` (1) |
| `labkit-init` | `labkit/checks/audit_binding.py` (5), `labkit/checks/code_scan.py` (1), `labkit/checks/intent_check.py` (9), `labkit/checks/kept_number_check.py` (2), `labkit/checks/model_check.py` (15), `labkit/checks/origin_check.py` (1), `labkit/checks/readme_check.py` (5), `labkit/checks/result_render.py` (6), `labkit/checks/row_check.py` (5), `labkit/checks/run_record_check.py` (31), `labkit/formats/answering_run.py` (2), `labkit/formats/area_state.py` (3), `labkit/formats/evidence.py` (2), `labkit/formats/reference.py` (5), `labkit/gates/exploration_hold.py` (4), `labkit/gates/finalize.py` (21), `labkit/gates/preflight.py` (3), `labkit/gates/registered_report.py` (7), `labkit/gates/registration_hold.py` (14), `labkit/gates/report_check.py` (24), `labkit/gates/report_decisions.py` (10), `labkit/gates/report_exploration.py` (2), `labkit/gates/report_hold.py` (7), `labkit/gates/report_replacement.py` (9), `labkit/run/batch.py` (1), `labkit/run/start_check.py` (3) |
| `labkit-next` | `labkit/checks/audit_binding.py` (5), `labkit/checks/code_scan.py` (1), `labkit/checks/intent_check.py` (9), `labkit/checks/kept_number_check.py` (2), `labkit/checks/model_check.py` (15), `labkit/checks/origin_check.py` (1), `labkit/checks/readme_check.py` (5), `labkit/checks/result_render.py` (6), `labkit/checks/row_check.py` (5), `labkit/checks/run_record_check.py` (31), `labkit/formats/answering_run.py` (2), `labkit/formats/area_state.py` (3), `labkit/formats/evidence.py` (2), `labkit/formats/reference.py` (5), `labkit/gates/exploration_hold.py` (4), `labkit/gates/finalize.py` (21), `labkit/gates/preflight.py` (3), `labkit/gates/registered_report.py` (7), `labkit/gates/registration_hold.py` (14), `labkit/gates/report_check.py` (24), `labkit/gates/report_decisions.py` (10), `labkit/gates/report_exploration.py` (2), `labkit/gates/report_hold.py` (7), `labkit/gates/report_replacement.py` (9), `labkit/run/batch.py` (1), `labkit/run/start_check.py` (3) |
| `labkit-params` | `labkit/formats/answering_run.py` (2) |
| `notes-check` | `labkit/checks/notes_check.py` (8) |
| `preflight` | `labkit/checks/code_check.py` (8), `labkit/checks/code_scan.py` (1), `labkit/checks/import_check.py` (4), `labkit/checks/prompt_check.py` (5), `labkit/formats/evidence.py` (2), `labkit/formats/protocol_history.py` (3), `labkit/gates/preflight.py` (20) |
| `protocol-check` | `labkit/checks/protocol_report.py` (3), `labkit/formats/protocol_history.py` (3) |
| `protocol-fill` | `labkit/gates/registered_report.py` (2) |
| `report-check` | `labkit/checks/audit_binding.py` (5), `labkit/checks/code_scan.py` (1), `labkit/checks/intent_check.py` (9), `labkit/checks/kept_number_check.py` (2), `labkit/checks/model_check.py` (15), `labkit/checks/origin_check.py` (1), `labkit/checks/readme_check.py` (5), `labkit/checks/report_blocks.py` (10), `labkit/checks/result_render.py` (6), `labkit/checks/row_check.py` (5), `labkit/checks/run_record_check.py` (31), `labkit/formats/answering_run.py` (2), `labkit/formats/area_state.py` (3), `labkit/formats/evidence.py` (2), `labkit/formats/reference.py` (5), `labkit/gates/exploration_hold.py` (4), `labkit/gates/finalize.py` (21), `labkit/gates/preflight.py` (3), `labkit/gates/registered_report.py` (7), `labkit/gates/registration_hold.py` (14), `labkit/gates/report_check.py` (24), `labkit/gates/report_decisions.py` (10), `labkit/gates/report_exploration.py` (2), `labkit/gates/report_hold.py` (22), `labkit/gates/report_replacement.py` (9), `labkit/run/batch.py` (1), `labkit/run/start_check.py` (3) |
| `usability` | `labkit/gates/registered_report.py` (2), `labkit/probes/usability.py` (1) |

## `labkit/checks/audit_binding.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `source_protocol_finding` | {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 5 | 0 | `tests/test_origin_check.py`, `tests/test_origin_scenario.py` |
| `check_audit_records_read` | {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 1 | `tests/test_finalize_open_findings.py`, `tests/test_handovers.py`, `tests/test_rules_audit_binding.py` |
| `check_audit_findings_decided` | {…} — {…} | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 10 | 1 | `tests/test_adopt_per_protocol.py`, `tests/test_end_to_end.py`, `tests/test_finalize_open_findings.py`, `tests/test_handovers.py`, `tests/test_next_step.py`, `tests/test_protocol_runs.py`, `tests/test_rules_audit_binding.py` |
| `check_audit_findings_decided` | {…} — {…} | finding | WARNING | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 2 | 1 | `tests/test_finalize_open_findings.py`, `tests/test_rules_audit_binding.py` |
| `check_audited_runs_kept` | {…}: names {…} as the run it read, and there is no runs/{…}/ in this area — the run the r… | finding | BLOCKER | GUARANTEED | technical contract | direct | 5 | 3 | `tests/test_finalize_open_findings.py`, `tests/test_report_check.py`, `tests/test_rules_audit_binding.py`, `tests/test_rules_registration_hold.py` |

## `labkit/checks/code_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `_intent_id_findings` | [{…}] is registered, but no script names a '{…}'/'{…}_*' key literal (a key assembled at … | finding | BLOCKER | GUARANTEED | CODE-016 The experiment area reconstructs itself | direct | 13 | 0 | `tests/test_agent_hooks.py`, `tests/test_apply_skeleton.py`, `tests/test_code_check.py`, `tests/test_code_ids_keywords.py`, `tests/test_preflight.py`, `tests/test_promise_preflight.py` |
| `_intent_id_findings` | key '{…}_*' is in the intent-id namespace, but the protocol registers no [{…}] · a number… | finding | WARNING | GUARANTEED | LAB-004 Identifiers make the intent addressable | direct | 7 | 0 | `tests/test_apply_skeleton.py`, `tests/test_code_check.py`, `tests/test_code_ids_keywords.py`, `tests/test_unreadable_source.py` |
| `promise_block_findings` | promise block: {…} | finding | BLOCKER | GUARANTEED | variable | direct | 2 | 0 | `tests/test_promise_preflight.py` |
| `promise_block_findings` | [{…}] declared scope: {…} · runlog refuses the run | finding | BLOCKER | GUARANTEED | variable | direct | 4 | 0 | `tests/test_audit_robustness.py`, `tests/test_code_check.py`, `tests/test_promise_preflight.py` |
| `promise_block_findings` | [{…}] declares key '{…}', which no script names as a literal{…} (an assembled key is not … | finding | BLOCKER | GUARANTEED | LAB-018 Routine check after every implementation | direct | 12 | 0 | `tests/test_agent_hooks.py`, `tests/test_apply_skeleton.py`, `tests/test_code_check.py`, `tests/test_preflight_stations.py`, `tests/test_promise_preflight.py` |
| `quality_check_reads` | quality-check keys: read check not done — {…} | finding | WARNING | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_check_stations.py` |
| `quality_check_reads` | [{…}] key '{…}' is written but nothing decides on it under its literal name · if no decis… | finding | WARNING | STATIC_EVIDENCE | LAB-004 Identifiers make the intent addressable | direct | 22 | 0 | `tests/test_agent_hooks.py`, `tests/test_code_check.py`, `tests/test_codex_hooks.py`, `tests/test_preflight.py`, `tests/test_promise_preflight.py`, `tests/test_repeat_cost_lowered_and_waived_audit.py`, `tests/test_runlog_freeze_gate.py`, `tests/test_unreadable_source.py` |
| `constant_copies` | [{…}] {…}:{…} sets {…} = {…} itself ({…}) · a copy judges by an unregistered value once t… | finding | WARNING | STATIC_EVIDENCE | LAB-004 Identifiers make the intent addressable | direct | 4 | 0 | `tests/test_audit_rest.py`, `tests/test_unreadable_source.py` |
| `main` | bundle: {…} could not be read — the reader sees `not readable` in its place | finding | WARNING | GUARANTEED | technical contract | only through commands | 1 | 0 | `tests/test_check_stations.py` |

## `labkit/checks/code_scan.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `unreadable_source` | {…} · the code cannot be read, so no check over it holds | finding | BLOCKER | GUARANTEED | technical contract | direct | 13 | 0 | `tests/test_code_check.py`, `tests/test_code_ids_keywords.py`, `tests/test_finalize.py`, `tests/test_finalize_steps.py`, `tests/test_preflight_stations.py`, `tests/test_read_causes.py`, `tests/test_unreadable_source.py` |

## `labkit/checks/import_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `_import_findings` | `{…}` resolves to {…}, outside lib/ and src/ · the stamp does not cover it, a change ther… | finding | WARNING | STATIC_EVIDENCE | LAB-019 The stamp covers everything that determines the number | direct | 1 | 0 | `tests/test_code_check.py` |
| `_coverage_in` | `sys.path` gains {…} · imports after it may resolve outside lib/ and src/, which the stam… | finding | WARNING | STATIC_EVIDENCE | LAB-019 The stamp covers everything that determines the number | direct | 2 | 0 | `tests/test_code_check.py` |
| `_coverage_in` | `{…}(…)` loads code at run time · the stamp follows `import` lines only, so it does not c… | finding | WARNING | STATIC_EVIDENCE | LAB-019 The stamp covers everything that determines the number | direct | 2 | 0 | `tests/test_code_check.py` |
| `_coverage_in` | names area `{…}` · this area's stamp does not follow a path into it | finding | WARNING | STATIC_EVIDENCE | LAB-019 The stamp covers everything that determines the number | direct | 2 | 0 | `tests/test_code_check.py` |

## `labkit/checks/intent_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `hold` | {…} | finding | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | direct | 20 | 0 | `tests/test_area_state.py`, `tests/test_finalize.py`, `tests/test_promises.py`, `tests/test_registration_committed.py`, `tests/test_replacement.py` |
| `hold` | {…} | finding | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | direct | 17 | 0 | `tests/test_end_to_end.py`, `tests/test_finalize.py`, `tests/test_intent_check.py`, `tests/test_intent_check_binding.py`, `tests/test_intent_check_choice.py`, `tests/test_origin_scenario.py` |
| `check_block_against_run` | {…}: [{…}] declares key '{…}', which the run does not report. | finding | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | direct | 12 | 0 | `tests/test_end_to_end.py`, `tests/test_finalize.py`, `tests/test_origin_scenario.py`, `tests/test_promises.py` |
| `check_block_against_run` | {…}: {…}. | finding | BLOCKER | GUARANTEED | variable | direct | 2 | 0 | `tests/test_intent_check.py`, `tests/test_promises.py` |
| `check_block_against_run` | {…} | finding | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | only through commands | 3 | 0 | `tests/test_promises.py` |
| `unregistered_outcomes` | {…}: [{…}] records {…} = {…}, which is none of its outcomes' names | finding | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | direct | 2 | 0 | `tests/test_promises.py` |
| `origin_intent_findings` | {…}: promise block: {…} | finding | BLOCKER | GUARANTEED | variable | direct | 1 | 0 | `tests/test_intent_check.py` |
| `origin_intent_findings` | {…} | finding | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | direct | 3 | 0 | `tests/test_intent_check.py`, `tests/test_origin_check.py` |
| `origin_intent_findings` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_intent_check.py` |

## `labkit/checks/kept_number_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `_criterion_n_warning` | {…} | finding | WARNING | STATIC_EVIDENCE | open assignment | not in the last trace | — | — | — |
| `kept_number_gaps` | the kept number: metrics.json of {…} {…} — the head's [kept] names `{…}` as the number th… | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 7 | 0 | `tests/test_audit.py`, `tests/test_end_to_end.py`, `tests/test_kept.py`, `tests/test_promises.py`, `tests/test_protocol_fill.py`, `tests/test_reference_end_to_end.py` |

## `labkit/checks/model_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `single_draw` | the draws of {…} cannot be counted: {…} | finding | WARNING | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_repeats.py` |
| `single_draw` | {…} is one draw — no spread: `scripts/01_measure.py --repeat-of {…}` draws it again, `02_… | finding | WARNING | GUARANTEED | LAB-036 Validate, don't trust a single run | direct | 40 | 0 | `tests/test_counter_cases.py`, `tests/test_end_to_end.py`, `tests/test_finalize_steps.py`, `tests/test_handovers.py`, `tests/test_repeats.py` |
| `_own_record_unbacked` | {…}'s call log holds {…} of alias `{…}` ({…}), but its models_resolved does not name `{…}… | finding | BLOCKER | GUARANTEED | LAB-027 Model discipline | direct | 8 | 4 | `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py` |
| `_derived_run_calls` | {…} — yet its call log holds {…} call{…} of alias `{…}` that asked the model | finding | BLOCKER | GUARANTEED | LAB-027 Model discipline | direct | 2 | 1 | `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py` |
| `_derived_run_calls` | {…} — yet its call log holds {…} of alias `{…}` stored outside any run{…}, which no recor… | finding | BLOCKER | GUARANTEED | LAB-027 Model discipline | direct | 2 | 2 | `tests/test_rules_run_record_check.py` |
| `_stored_answer_unbacked` | {…}'s call log holds {…} of alias `{…}` stored by run {…}, but {…} — no record says which… | finding | BLOCKER | GUARANTEED | LAB-027 Model discipline | direct | 5 | 3 | `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py` |
| `stand_in_findings` | {…}: fixed answers stored with `llm_cache.store_stand_in`, not answers of a model — its n… | finding | WARNING | GUARANTEED | LAB-027 Model discipline | direct | 4 | 2 | `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py`, `tests/test_stand_in_run_through.py` |
| `model_provenance_findings` | model provenance: the call log of {…} does not read — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_finalize_steps.py` |
| `model_provenance_findings` | model provenance: {…} has no config.json — which model it recorded cannot be read | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_finalize_steps.py` |
| `model_provenance_findings` | model provenance: the stand-ins behind {…} cannot be counted — {…}; the result line canno… | finding | WARNING | GUARANTEED | technical contract | direct | 9 | 0 | `tests/test_finalize_provenance.py`, `tests/test_finalize_steps.py`, `tests/test_origin_scenario.py`, `tests/test_registration_committed.py` |
| `_metrics_model_findings` | model provenance: the lineage of {…} is broken — {…} | finding | WARNING | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_finalize_steps.py` |
| `_metrics_model_findings` | {…} called a model, but no run in its lineage recorded models_resolved — record the alias… | finding | WARNING | GUARANTEED | LAB-027 Model discipline | direct | 2 | 0 | `tests/test_finalize_steps.py` |
| `arm_findings` | arm `{…}`: the protocol names {…}, no such file under {…} | finding | WARNING | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_arm_lines.py` |
| `arm_findings` | arm `{…}`: the protocol names fingerprint {…}, the answering run recorded no such value —… | finding | WARNING | GUARANTEED | open assignment | direct | 1 | 0 | `tests/test_arm_lines.py` |
| `arm_findings` | arm `{…}`: the protocol names alias {…}, the answering run recorded no such alias | finding | WARNING | GUARANTEED | LAB-027 Model discipline | direct | 1 | 0 | `tests/test_arm_lines.py` |

## `labkit/checks/notes_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `check_file` | {…}:1: MISSING: no italic meta line after the title | finding | WARNING | GUARANTEED | LAB-082 In `notes/messung/`, every note carries its kind in the meta line | direct | 2 | 0 | `tests/test_agent_hooks.py` |
| `check_file` | {…}:{…}: MISSING: no kind in the meta line | finding | WARNING | GUARANTEED | LAB-082 In `notes/messung/`, every note carries its kind in the meta line | direct | 2 | 0 | `tests/test_notes_check.py` |
| `check_file` | {…}:{…}: warning: no date in the meta line | finding | WARNING | GUARANTEED | open assignment | direct | 1 | 0 | `tests/test_notes_check.py` |
| `check_file` | {…}:{…}: MISSING: declared 'Instrument — implementiert' but names no script, function, or… | finding | WARNING | STATIC_EVIDENCE | LAB-082 In `notes/messung/`, every note carries its kind in the meta line | direct | 1 | 0 | `tests/test_notes_check.py` |
| `check_file` | {…}:{…}: warning: none of the named scripts resolve in the repo ({…}{…}) — code paths may… | finding | WARNING | GUARANTEED | open assignment | direct | 1 | 0 | `tests/test_notes_check.py` |
| `check_file` | {…}:{…}: warning: filename says related-* but the declared kind is {…} | finding | WARNING | GUARANTEED | open assignment | direct | 1 | 0 | `tests/test_notes_check.py` |
| `check_file` | {…}:{…}: warning: Related-Lesart without a citekey — write 'Related-Lesart (<citekey>)' | finding | WARNING | GUARANTEED | LAB-082 In `notes/messung/`, every note carries its kind in the meta line | direct | 1 | 0 | `tests/test_notes_check.py` |
| `check_notes` | {…}: not readable ({…}) | finding | WARNING | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_check_stations.py`, `tests/test_read_causes.py` |

## `labkit/checks/origin_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `origin_finding` | {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 9 | 0 | `tests/test_origin_check.py`, `tests/test_origin_scenario.py`, `tests/test_registration_committed.py` |

## `labkit/checks/prompt_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `check_parser_fixtures` | cannot be parsed ({…}) · which parsers it calls cannot be told | finding | WARNING | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_code_check_gates.py` |
| `check_parser_fixtures` | {…}() is called by no test under tests/ · a parser fails silently into a wrong number | finding | WARNING | STATIC_EVIDENCE | LAB-041 Generate numbers, don't retype them | direct | 4 | 0 | `tests/test_code_check_gates.py`, `tests/test_preflight.py` |
| `require_registered_templates` | {…}: no such protocol — no template is held to it | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_prompt_templates.py` |
| `require_registered_templates` | {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_prompt_templates.py` |
| `require_registered_templates` | {…}: {…} of {…} template(s) the run uses are not registered as they are — refused before … | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_prompt_templates.py`, `tests/test_public_api.py` |
| `check_prompt_drift` | {…} | finding | BLOCKER | GUARANTEED | LAB-067 A prompt has one home, which the run freezes | direct | 1 | 0 | `tests/test_prompt_templates.py` |
| `check_prompt_drift` | {…} is not statically readable (a call or a format spec this check does not compute) · pr… | finding | WARNING | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_code_check_prompts.py` |
| `check_prompt_drift` | prompt block drifted from {…}: {…} of {…} fixed line(s) missing, e.g. {…} | finding | BLOCKER | GUARANTEED | LAB-067 A prompt has one home, which the run freezes | direct | 8 | 0 | `tests/test_code_check_gates.py`, `tests/test_code_check_prompts.py`, `tests/test_preflight.py`, `tests/test_protocol_fill.py` |

## `labkit/checks/protocol_report.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `print_report` | {…}: WARNING: preflight_audit: {…} | printed | WARNING | none | not recorded | not traced (printed line) | — | — | — |
| `print_report` | {…}:{…}: WARNING: {…} written before any run — no completed run is bound to this protocol… | printed | WARNING | none | not recorded | not traced (printed line) | — | — | — |
| `print_report` | {…}: WARNING: {…} | printed | WARNING | none | not recorded | not traced (printed line) | — | — | — |

## `labkit/checks/readme_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `readme_route` | README.md: no {…} … {…} block — the route (protocol · runlog · labkit-params · evaluate_r… | finding | WARNING | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_finalize.py`, `tests/test_finalize_steps.py` |
| `readme_route` | README.md route: does not name {…} | finding | WARNING | GUARANTEED | technical contract | direct | 11 | 0 | `tests/test_adopt_per_protocol.py`, `tests/test_finalize_steps.py`, `tests/test_origin_scenario.py`, `tests/test_protocol_runs.py`, `tests/test_source_lines.py` |
| `readme_route` | README.md route: does not name {…} | finding | WARNING | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_finalize.py`, `tests/test_finalize_steps.py` |
| `readme_route` | README.md route: scripts/01_measure.py does not exist | finding | WARNING | GUARANTEED | CODE-016 The experiment area reconstructs itself | direct | 1 | 0 | `tests/test_finalize_steps.py` |
| `readme_route` | README.md route: scripts/01_measure.py defines no evaluate_rows | finding | WARNING | GUARANTEED | CODE-016 The experiment area reconstructs itself | direct | 1 | 0 | `tests/test_finalize_steps.py` |

## `labkit/checks/recheck.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `chosen_run` | recheck: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_refusals.py` |
| `chosen_run` | recheck: the protocol carries no stamped id ([protocol] id) — no run binds to it; `labkit… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_binding.py` |
| `chosen_run` | recheck: {…}{…} | exit | exit | none | not recorded | direct | 12 | 0 | `tests/test_answering_run_exhaustive.py`, `tests/test_end_to_end.py`, `tests/test_next_step.py`, `tests/test_protocol_fill.py`, `tests/test_public_api.py`, `tests/test_recheck_binding.py` |
| `_named_run` | recheck: {…} is not a completed run ({…}) | exit | exit | none | not recorded | direct | 2 | 0 | `tests/test_completion_consumers.py`, `tests/test_protocol_fill.py` |
| `_named_run` | recheck: {…} | exit | exit | none | not recorded | direct | 2 | 0 | `tests/test_completion_consumers.py`, `tests/test_recheck_refusals.py` |
| `_named_run` | recheck: {…} is a repeat of {…} — supporting evidence, never the answer; `02_analyze.py -… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_repeats.py` |
| `_named_run` | recheck: {…} is bound to {…}, not to {…} — it answers another question | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_binding.py` |
| `protocol_named` | recheck: {…} | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_origin_scenario.py`, `tests/test_recheck_per_protocol.py` |
| `script_module` | recheck: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_refusals.py` |
| `script_module` | recheck: run {…}: {…} does not import | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_refusals.py` |
| `registered_output` | recheck: run {…} did not register {…} as an output | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_recheck_outputs_scenario.py`, `tests/test_recheck_refusals.py` |
| `pin` | recheck: {…} is not the file run {…} recorded — {…}; rerun the script or name that run | exit | exit | none | not recorded | direct | 9 | 0 | `tests/test_exploration_hold.py`, `tests/test_public_api.py`, `tests/test_recheck.py`, `tests/test_recheck_outputs_scenario.py`, `tests/test_repair_guidance.py`, `tests/test_repeats.py`, `tests/test_withdrawal_order.py` |
| `scopes_unchanged` | recheck: declared scope cannot be compared with what run {…} recorded: {…}, or recheck fr… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_promises.py` |
| `scopes_unchanged` | recheck: declared scope changed since run {…}: {…} — rerun, or recheck from that run's co… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_promises.py` |
| `require_run_code` | recheck: the code that computed run {…} is not the code here now: {…} — recomputing with … | exit | exit | none | not recorded | direct | 12 | 0 | `tests/test_adopt_per_protocol.py`, `tests/test_end_to_end.py`, `tests/test_exploration_link_scenario.py`, `tests/test_next_step.py`, `tests/test_origin_scenario.py`, `tests/test_run_code.py` |
| `protocol_as_run_saw` | recheck: run {…}: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_refusals.py` |
| `protocol_as_run_saw` | recheck: the protocol run {…} was measured under cannot be read back: {…} — what it regis… | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_recheck_own_text.py`, `tests/test_recheck_refusals.py` |
| `kept_keys` | recheck: run {…}: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_refusals.py` |
| `block_unchanged` | recheck: run {…}: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_audit_robustness.py` |
| `block_unchanged` | recheck: run {…} {…} | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_promises.py`, `tests/test_recheck_own_text.py` |
| `output_rows` | recheck: run {…}: output {…} ({…}) is no row file — {…}. The recomputation reads row file… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck.py` |
| `require_agreement` | recheck: the kept number is missing — {…}: the number the protocol reports must stand in … | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck.py` |
| `require_agreement` | recheck: metrics.json and the recomputation disagree — intent keys on one side only {…}, … | exit | exit | none | not recorded | direct | 4 | 0 | `tests/test_evidence_unread.py`, `tests/test_recheck.py` |
| `require_agreement` | recheck: recomputation differs from metrics.json in the identifiers or the kept number {…} | exit | exit | none | not recorded | direct | 9 | 0 | `tests/test_recheck.py`, `tests/test_recheck_inputs.py`, `tests/test_recheck_outputs_scenario.py`, `tests/test_recheck_own_text.py` |
| `cited` | recheck: {…}: no such note | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_refusals.py` |
| `cited` | recheck: {…} has no answer yet — `{…}` writes it once that run's analysis audit is decide… | exit | exit | none | not recorded | direct | 24 | 0 | `tests/test_deliverable.py`, `tests/test_end_to_end.py`, `tests/test_exploration_link_scenario.py`, `tests/test_handovers.py`, `tests/test_origin_scenario.py`, `tests/test_protocol_runs.py`, `tests/test_recheck.py` |
| `cited` | recheck: numbers not in {…}: {…} | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_recheck.py` |
| `cited` | recheck: {…} does not cite run {…} | exit | exit | none | not recorded | direct | 2 | 0 | `tests/test_end_to_end.py`, `tests/test_recheck.py` |
| `reads_another_run` | recheck: run {…}: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_refusals.py` |
| `inputs_pinned` | recheck: run {…}: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_refusals.py` |
| `inputs_pinned` | recheck: run {…} recorded no input file — nothing to recompute from; hold its own output … | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_inputs.py` |
| `inputs_pinned` | recheck: run {…}: {…} — not recomputed from inputs that are not the ones it read | exit | exit | none | not recorded | direct | 5 | 0 | `tests/test_origin_scenario.py`, `tests/test_recheck_inputs.py` |
| `inputs_pinned` | recheck: run {…}: data[{…}] = {…} is not the input it read: {…}, the run recorded sha256 … | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_recheck_inputs.py` |

## `labkit/checks/report_blocks.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `block_gaps` | {…}: {…} — a block shows an adopted result only | finding | BLOCKER | GUARANTEED | variable | direct | 2 | 0 | `tests/test_next_step.py`, `tests/test_report_blocks_text.py` |
| `block_gaps` | {…}: {…} — a block shows an adopted result only | finding | BLOCKER | GUARANTEED | variable | direct | 3 | 0 | `tests/test_handovers.py`, `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py` |
| `block_gaps` | {…}: the protocol has adopted run {…} now | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 2 | 0 | `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py` |
| `block_gaps` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_origin_scenario.py`, `tests/test_report_blocks.py` |
| `block_gaps` | {…} differs from the protocol's rendering — written before its Conclusion, a decision or … | finding | BLOCKER | GUARANTEED | technical contract | direct | 11 | 0 | `tests/test_end_to_end.py`, `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py`, `tests/test_result_render.py`, `tests/test_workflow_example.py` |
| `cited_gaps` | {…} | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 6 | 0 | `tests/test_next_step.py`, `tests/test_origin_scenario.py`, `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py` |
| `cited_gaps` | {…} | finding | WARNING | STATIC_EVIDENCE | LAB-104 A number leaves the area only through its adoption | direct | 3 | 0 | `tests/test_report_blocks.py`, `tests/test_report_blocks_text.py` |
| `discussion_gaps` | {…} repeats the block at line {…} — one block per protocol and run | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_report_blocks_text.py` |
| `discussion_gaps` | {…} has no why | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 1 | 0 | `tests/test_report_blocks.py` |
| `discussion_gaps` | {…}: its line differs from its head | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 1 | 0 | `tests/test_report_blocks.py` |

## `labkit/checks/result_render.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `render_gaps` | the Recorded results line is not written | finding | BLOCKER | GUARANTEED | LAB-011 Required-field check | direct | 2 | 0 | `tests/test_replacement.py`, `tests/test_result_render.py` |
| `render_gaps` | the Recorded results line differs from its rendering (the run's metrics.json, the stand-i… | finding | BLOCKER | GUARANTEED | technical contract | direct | 11 | 0 | `tests/test_end_to_end.py`, `tests/test_reference.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_result_render.py`, `tests/test_source_lines.py`, `tests/test_workflow_example.py` |
| `render_gaps` | "{…}" is written {…} times — one generated line per label | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_result_render.py` |
| `render_gaps` | no "{…}" line — the limit's line belongs in the protocol | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 3 | 0 | `tests/test_end_to_end.py`, `tests/test_result_render.py` |
| `render_gaps` | "{…}" differs from the record and its decision reviews — a line written before the decisi… | finding | BLOCKER | GUARANTEED | technical contract | direct | 5 | 0 | `tests/test_decision_review.py`, `tests/test_result_render.py` |
| `render_gaps` | "{…}" names a limit no covering record decides — written by hand or from an older record | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 3 | 0 | `tests/test_end_to_end.py`, `tests/test_result_render.py` |

## `labkit/checks/row_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `null_lane_findings` | {…}: the null lane's answer and gold equal the registered lane's on every item — if the n… | finding | WARNING | STATIC_EVIDENCE | LAB-034 Null condition in the same run | direct | 2 | 1 | `tests/test_finalize_steps.py`, `tests/test_rules_run_record_check.py` |
| `row_provenance_findings` | row provenance: the lineage of {…} is broken — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_lineage.py`, `tests/test_registration_committed.py` |
| `row_provenance_findings` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_row_provenance.py` |
| `row_provenance_findings` | {…}: {…} row(s) from {…} — a run this run neither is, continues nor derives from; a file … | finding | BLOCKER | GUARANTEED | LAB-057 One area per idea | direct | 9 | 0 | `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_repair_guidance.py`, `tests/test_row_provenance.py`, `tests/test_withdrawal_order.py` |
| `_continued_with_other_code` | {…}: {…} row(s) come from {…}, which ran other code (script {…}, this run's {…}) — {…}'s … | finding | BLOCKER | GUARANTEED | open assignment | direct | 1 | 0 | `tests/test_row_provenance.py` |

## `labkit/checks/run_record_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `code_since_run` | {…}: its runs cannot be followed ({…}) | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_registration_committed.py`, `tests/test_run_code.py` |
| `code_since_run` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `answer_reading_gaps` | {…} re-reads the answers of {…}, but the prompts field differs from the text {…} was meas… | finding | BLOCKER | GUARANTEED | LAB-067 A prompt has one home, which the run freezes | direct | 2 | 1 | `tests/test_answer_reading_scenario.py`, `tests/test_rules_run_record_check.py` |
| `answer_reading_gaps` | {…} registered none of the files {…} registered as its output — a derived run re-reads it… | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 1 | 1 | `tests/test_rules_run_record_check.py` |
| `answer_reading_gaps` | {…}: {…} registered sha256 {…}, {…} {…} — the answers changed after {…} ran | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 2 | 1 | `tests/test_answer_reading_scenario.py`, `tests/test_rules_run_record_check.py` |
| `_reading_since_run` | {…} cannot be compared with what {…} ran: the area lies in no git repository now | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `_reading_since_run` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `_reading_since_run` | {…} cannot be read now: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `_reading_since_run` | {…}: {…} no longer imports it, so it is not what reads the answers | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `_run_code` | {…} recorded no script — the code behind its number cannot be compared | finding | BLOCKER | GUARANTEED | technical contract | direct | 10 | 0 | `tests/test_audit.py`, `tests/test_explored_in.py`, `tests/test_origin_scenario.py`, `tests/test_promises.py`, `tests/test_protocol_fill.py`, `tests/test_recheck.py`, `tests/test_recheck_inputs.py`, `tests/test_run_code.py` |
| `_run_code` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_run_code.py` |
| `_run_code` | {…} changed since {…} ran it — its number came from other code | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 31 | 0 | `tests/test_adopt_per_protocol.py`, `tests/test_answer_reading_scenario.py`, `tests/test_end_to_end.py`, `tests/test_exploration_link_scenario.py`, `tests/test_finalize.py`, `tests/test_next_step.py`, `tests/test_origin_scenario.py`, `tests/test_repair_guidance.py`, `tests/test_run_code.py`, `tests/test_withdrawal_order.py` |
| `_run_code` | the code {…} ran cannot be read now: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_finalize.py`, `tests/test_run_code.py` |
| `_helpers_since_run` | {…} changed since {…} ran it (it was untracked; the run kept it as {…}) | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 1 | 0 | `tests/test_run_code.py` |
| `_helpers_since_run` | {…}, so the helpers its script imports ({…}) cannot be compared | finding | BLOCKER | GUARANTEED | LAB-010 Commit before the run | direct | 1 | 0 | `tests/test_run_code.py` |
| `_helpers_since_run` | {…}, so the helpers its script imports ({…}) cannot be compared | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_run_code.py` |
| `_helpers_since_run` | {…} started from a tree with changes ({…}), and its uncommitted.patch is gone: the commit… | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `_helpers_since_run` | {…} {…}, so the helpers its script imports ({…}) cannot be compared | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `_helpers_since_run` | {…} started at commit {…}, which this clone does not hold | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `_helpers_since_run` | the tree {…} started from cannot be read for {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_run_code.py` |
| `_helpers_since_run` | {…} is in neither {…}'s commit nor its uncommitted.patch, so it cannot be compared with w… | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `_helpers_since_run` | {…} changed since {…} ran | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 5 | 0 | `tests/test_answer_reading_scenario.py`, `tests/test_run_code.py` |
| `provenance_findings` | no outputs.json — the run registered no output file (run.output) | finding | WARNING | GUARANTEED | technical contract | direct | 71 | 0 | `tests/test_agent_hooks.py`, `tests/test_area_state.py`, `tests/test_check_stations.py`, `tests/test_codex_hooks.py`, `tests/test_end_to_end.py`, `tests/test_explored_in.py`, `tests/test_finalize_provenance.py`, `tests/test_kept.py`, `tests/test_protocol_fill.py`, `tests/test_registration_committed.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py`, `tests/test_run_code.py` |
| `provenance_findings` | not a git repository — cannot tell whether source and output are committed | finding | WARNING | GUARANTEED | technical contract | direct | 27 | 0 | `tests/test_check_stations.py`, `tests/test_finalize_provenance.py`, `tests/test_kept.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py`, `tests/test_run_code.py` |
| `provenance_findings` | output {…} is not yet tracked — `{…}` before the commit that cites the number | finding | WARNING | GUARANTEED | LAB-017 The number of audits follows the cost tier | direct | 152 | 0 | `tests/test_adopt.py`, `tests/test_adopt_per_protocol.py`, `tests/test_counter_cases.py`, `tests/test_deliverable.py`, `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_exploration_link_scenario.py`, `tests/test_finalize_provenance.py`, `tests/test_handovers.py`, `tests/test_next_step.py`, `tests/test_obligations_scenario.py`, `tests/test_origin_scenario.py`, `tests/test_protocol_runs.py`, `tests/test_reference_end_to_end.py`, `tests/test_repair_guidance.py`, `tests/test_source_lines.py`, `tests/test_unread_registration.py`, `tests/test_withdrawal_order.py` |
| `_recorded_sources` | {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_check_stations.py`, `tests/test_finalize_provenance.py` |
| `_recorded_sources` | source not frozen — the run carries no `data=` | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 21 | 0 | `tests/test_area_state.py`, `tests/test_finalize_provenance.py`, `tests/test_kept.py`, `tests/test_registration_committed.py`, `tests/test_report_blocks.py`, `tests/test_report_check_areas.py`, `tests/test_run_code.py` |
| `source_finding` | source {…} is not the bytes the run read: {…}, the run recorded sha256 {…} | finding | BLOCKER | GUARANTEED | LAB-017 The number of audits follows the cost tier | direct | 7 | 1 | `tests/test_finalize_provenance.py`, `tests/test_origin_scenario.py`, `tests/test_rules_run_record_check.py` |
| `_untracked_source` | {…} — whether it belongs to the project is left open | finding | BLOCKER | GUARANTEED | LAB-017 The number of audits follows the cost tier | direct | 10 | 2 | `tests/test_end_to_end.py`, `tests/test_explored_in.py`, `tests/test_finalize_provenance.py`, `tests/test_rules_run_record_check.py` |
| `output_record_findings` | {…}: not the file run {…} recorded — {…} | finding | BLOCKER | GUARANTEED | variable | direct | 13 | 3 | `tests/test_audit.py`, `tests/test_deliverable.py`, `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_repair_guidance.py`, `tests/test_rules_run_record_check.py`, `tests/test_unread_registration.py`, `tests/test_withdrawal_order.py` |
| `_gone` | {…} is not at its recorded path on this machine — deleted, moved or held elsewhere; the r… | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 1 | `tests/test_finalize_provenance.py`, `tests/test_rules_run_record_check.py` |

## `labkit/formats/answering_run.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `AnsweringRun.explain` | {…} | finding | BLOCKER | GUARANTEED | variable | direct | 62 | 0 | `tests/test_agent_hooks.py`, `tests/test_answering_run.py`, `tests/test_answering_run_exhaustive.py`, `tests/test_area_state.py`, `tests/test_audit.py`, `tests/test_audit_robustness.py`, `tests/test_codex_hooks.py`, `tests/test_end_to_end.py`, `tests/test_exploration_link_scenario.py`, `tests/test_finalize.py`, `tests/test_finalize_open_findings.py`, `tests/test_finalize_steps.py`, `tests/test_intent_check.py`, `tests/test_intent_check_binding.py`, `tests/test_next_step.py`, `tests/test_origin_scenario.py`, `tests/test_params.py`, `tests/test_protocol_fill.py`, `tests/test_public_api.py`, `tests/test_recheck_binding.py`, `tests/test_registration_committed.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py`, `tests/test_reported_through.py` |
| `AnsweringRun.explain` | {…} {…} — no answer: a probe or producer run, or a script that reports no registered key | finding | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | direct | 14 | 0 | `tests/test_answering_run.py`, `tests/test_answering_run_exhaustive.py`, `tests/test_area_state.py`, `tests/test_counter_cases.py`, `tests/test_end_to_end.py`, `tests/test_intent_check_choice.py`, `tests/test_origin_scenario.py`, `tests/test_recheck_binding.py` |

## `labkit/formats/area_state.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `unread_start_warning` | {…} — nothing is taken from a start file that does not read | finding | WARNING | GUARANTEED | technical contract | direct | 3 | 1 | `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_rules_registration_hold.py` |
| `missing_start_warning` | {…} | finding | WARNING | GUARANTEED | technical contract | direct | 6 | 2 | `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_rules_registration_hold.py` |
| `unassigned_record_warning` | the record of run {…} does not read, and neither a start file nor the run index names it:… | finding | WARNING | GUARANTEED | technical contract | direct | 3 | 1 | `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_rules_registration_hold.py` |

## `labkit/formats/evidence.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `change_blockers` | {…} | finding | BLOCKER | GUARANTEED | variable | direct | 8 | 0 | `tests/test_evidence.py`, `tests/test_origin_scenario.py`, `tests/test_read_causes.py`, `tests/test_replacement.py`, `tests/test_report_blocks.py` |
| `change_blockers` | {…} | finding | BLOCKER | GUARANTEED | variable | direct | 2 | 0 | `tests/test_evidence_unread.py`, `tests/test_read_causes.py` |

## `labkit/formats/protocol_history.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `check_protocol_id` | {…}: DUPLICATE protocol id {…} — also carried by {…}. An id binds runs to ONE protocol | finding | BLOCKER | GUARANTEED | technical contract | direct | 6 | 0 | `tests/test_agent_hooks_undecided.py`, `tests/test_exploration_link_scenario.py`, `tests/test_protocol_id.py` |
| `check_protocol_id` | {…}: WARNING: protocol id changed against HEAD ({…} -> {…}) — runs bound to the old id st… | finding | WARNING | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_check_stations.py`, `tests/test_protocol_id.py` |
| `check_annotation_validity` | {…} — {…} | finding | BLOCKER | GUARANTEED | variable | direct | 3 | 0 | `tests/test_annotation_validity.py` |

## `labkit/formats/reference.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `comparison_gaps` | metrics.json carries {…} and the head registers no [reference] — a comparison is register… | finding | BLOCKER | GUARANTEED | LAB-035 Thresholds belong to the run, not to the measure | direct | 1 | 0 | `tests/test_reference.py` |
| `comparison_gaps` | the head registers [reference] on `{…}`, and the run recorded no verdict (no `{…}` in met… | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_reference.py`, `tests/test_registration_committed.py` |
| `comparison_gaps` | `{…}` {…}, so the registered reference ({…}) cannot be compared and no verdict can be rep… | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 1 | 0 | `tests/test_reference.py` |
| `comparison_gaps` | the verdict in metrics.json does not read: `{…}` = {…}, `{…}` = {…} — written beside the … | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_reference.py` |
| `comparison_gaps` | the run compared with {…}, the head registers {…} — the reference changed after the run, … | finding | BLOCKER | GUARANTEED | LAB-035 Thresholds belong to the run, not to the measure | direct | 2 | 0 | `tests/test_reference.py` |

## `labkit/gates/audit.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `early_for_tier` | repeat_cost = "low" and no completed run · the first run is the cheaper probe; one audit … | finding | WARNING | GUARANTEED | LAB-017 The number of audits follows the cost tier | direct | 2 | 0 | `tests/test_audit.py`, `tests/test_check_stations.py` |
| `_record` | scope WARNING: {…} | printed | WARNING | none | not recorded | not traced (printed line) | — | — | — |

## `labkit/gates/exploration_hold.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `unknown_step_hold` | the step a run was measured under cannot be told: {…}{…} — the comparison with its basis … | finding | BLOCKER | GUARANTEED | technical contract | only through commands | 1 | 0 | `tests/test_exploration_hold.py` |
| `step_gap_hold` | run {…} made the step "{…}" on {…}, and its declared changes are not the differences of t… | finding | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | only through commands | 1 | 0 | `tests/test_exploration_hold.py` |
| `unstepped_holds` | run {…} was measured without a step, and its registration differs from the first measurem… | finding | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | direct | 5 | 0 | `tests/test_exploration_hold.py`, `tests/test_registration_station.py` |
| `live_holds` | what the number is about changed after the answering run {…}: {…} (as the protocol stands… | finding | BLOCKER | GUARANTEED | variable | direct | 9 | 0 | `tests/test_adopt_per_protocol.py`, `tests/test_exploration_hold.py`, `tests/test_registration_station.py`, `tests/test_report_check.py`, `tests/test_source_lines.py` |

## `labkit/gates/finalize.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `choose_answering_run` | no stamped protocol id ([protocol] id) — no run is bound to it | finding | BLOCKER | GUARANTEED | LAB-043 Runs go through `runlog` | direct | 2 | 0 | `tests/test_finalize.py`, `tests/test_finalize_steps.py` |
| `choose_answering_run` | {…}: bound to this protocol and newer by name than the adopted run {…} — if one of them a… | finding | WARNING | STATIC_EVIDENCE | open assignment | direct | 9 | 0 | `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_finalize_steps.py`, `tests/test_protocol_runs.py`, `tests/test_repair_guidance.py`, `tests/test_withdrawal_order.py` |
| `unreportable_warnings` | the answering run {…}: {…} — its number cannot be reported (report-check refuses it) | finding | WARNING | GUARANTEED | variable | direct | 14 | 0 | `tests/test_agent_hooks.py`, `tests/test_end_to_end.py`, `tests/test_finalize_open_findings.py`, `tests/test_promises.py`, `tests/test_protocol_fill.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py` |
| `station_intent_keys_in_metrics` | intent-check: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_finalize.py` |
| `station_run_code` | {…} | finding | WARNING | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `station_answer_reading` | the prompts {…} re-reads with cannot be held to {…}'s: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_run_code.py` |
| `station_declared_scopes` | {…} recorded no promise block: {…} — a run records the block it was measured under, so th… | finding | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | direct | 2 | 0 | `tests/test_audit.py`, `tests/test_registration_contract.py` |
| `station_declared_scopes` | declared scope cannot be compared with what {…} recorded: {…} | finding | BLOCKER | GUARANTEED | variable | direct | 1 | 0 | `tests/test_finalize.py` |
| `station_declared_scopes` | declared scope changed since {…}: {…} | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 3 | 0 | `tests/test_finalize.py`, `tests/test_promises.py` |
| `station_open_fields` | {…}:{…}: {…} | finding | WARNING | GUARANTEED | variable | direct | 20 | 0 | `tests/test_counter_cases.py`, `tests/test_end_to_end.py`, `tests/test_finalize.py`, `tests/test_finalize_steps.py`, `tests/test_handovers.py`, `tests/test_high_compute_workflow.py`, `tests/test_report_blocks.py` |
| `station_open_fields` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 5 | 0 | `tests/test_field_values.py`, `tests/test_finalize_steps.py`, `tests/test_report_check_areas.py` |
| `station_open_fields` | {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_finalize.py` |
| `station_open_fields` | {…} — a stamped placeholder, fill or delete the line | finding | WARNING | STATIC_EVIDENCE | CODE-016 The experiment area reconstructs itself | direct | 42 | 0 | `tests/test_counter_cases.py`, `tests/test_end_to_end.py`, `tests/test_finalize_steps.py`, `tests/test_handovers.py`, `tests/test_obligations_scenario.py` |
| `station_data_counts` | {…} | finding | BLOCKER | GUARANTEED | variable | direct | 3 | 0 | `tests/test_finalize_steps.py` |
| `run_file_unread` | {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_read_causes.py` |
| `run_file_unread` | {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 4 | 0 | `tests/test_finalize_steps.py`, `tests/test_origin_check.py`, `tests/test_read_causes.py`, `tests/test_reference.py` |
| `station_reference` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_reference.py` |
| `station_reference` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_reference.py` |
| `station_kept_number` | {…}: {…}{…} | finding | BLOCKER | GUARANTEED | variable | direct | 2 | 0 | `tests/test_kept.py`, `tests/test_reference.py` |
| `_refuse` | {…} | finding | BLOCKER | GUARANTEED | variable | direct | 3 | 0 | `tests/test_finalize.py` |
| `declared_run_gaps` | {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 8 | 0 | `tests/test_end_to_end.py`, `tests/test_finalize_steps.py`, `tests/test_migration_bar.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py` |

## `labkit/gates/preflight.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `preflight_area` | HEAD (must): {…} | finding | BLOCKER | GUARANTEED | variable | direct | 4 | 0 | `tests/test_preflight.py`, `tests/test_preflight_stations.py` |
| `station_protocol_fields` | {…} | finding | BLOCKER | GUARANTEED | variable | direct | 38 | 0 | `tests/test_agent_hooks.py`, `tests/test_codex_hooks.py`, `tests/test_explored_in.py`, `tests/test_preflight.py`, `tests/test_preflight_stations.py`, `tests/test_promise_preflight.py`, `tests/test_repeat_cost_lowered_and_waived_audit.py`, `tests/test_runlog_freeze_gate.py`, `tests/test_scope_sha.py`, `tests/test_unreadable_source.py` |
| `station_protocol_fields` | REPEATED (must): {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_field_values.py` |
| `station_protocol_fields` | {…}:{…}: PLACEHOLDER (must): {…} | finding | BLOCKER | GUARANTEED | LAB-011 Required-field check | direct | 3 | 0 | `tests/test_agent_hooks.py`, `tests/test_preflight_stations.py` |
| `station_protocol_fields` | {…} | finding | WARNING | STATIC_EVIDENCE | LAB-015 Preflight audit before freezing | direct | 1 | 0 | `tests/test_repeat_cost_lowered_and_waived_audit.py` |
| `station_protocol_fields` | missing (should): {…} | finding | WARNING | GUARANTEED | technical contract | direct | 36 | 0 | `tests/test_agent_hooks.py`, `tests/test_preflight.py`, `tests/test_preflight_stations.py`, `tests/test_promise_preflight.py`, `tests/test_protocol_id.py`, `tests/test_runlog_freeze_gate.py`, `tests/test_scope_sha.py`, `tests/test_unreadable_source.py` |
| `station_protocol_fields` | {…}:{…}: placeholder (should): {…} | finding | WARNING | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_agent_hooks.py`, `tests/test_preflight_stations.py` |
| `station_promise_sentences` | [[promise]] {…} still carries the stamp's `<…>` sentence — frozen = true refuses it | finding | WARNING | GUARANTEED | LAB-004 Identifiers make the intent addressable | direct | 2 | 0 | `tests/test_agent_hooks.py`, `tests/test_promise_preflight.py` |
| `_owed` | {…} | finding | BLOCKER | GUARANTEED | variable | direct | 18 | 0 | `tests/test_agent_hooks.py`, `tests/test_codex_hooks.py`, `tests/test_preflight.py`, `tests/test_preflight_stations.py`, `tests/test_promise_preflight.py`, `tests/test_repeat_cost_lowered_and_waived_audit.py`, `tests/test_runlog_freeze_gate.py` |
| `_owed` | {…} | finding | WARNING | GUARANTEED | variable | direct | 37 | 0 | `tests/test_agent_hooks.py`, `tests/test_explored_in.py`, `tests/test_preflight.py`, `tests/test_preflight_stations.py`, `tests/test_promise_preflight.py`, `tests/test_repeat_cost_lowered_and_waived_audit.py`, `tests/test_runlog_freeze_gate.py`, `tests/test_scope_sha.py`, `tests/test_unreadable_source.py` |
| `station_audit_records` | {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_preflight.py`, `tests/test_preflight_stations.py` |
| `station_handed_over_elsewhere` | {…} | finding | WARNING | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_preflight.py`, `tests/test_preflight_stations.py` |
| `station_handed_over_elsewhere` | {…} | finding | WARNING | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_preflight.py`, `tests/test_preflight_stations.py` |
| `station_scope_stamp` | cannot stamp the area's scope: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 6 | 0 | `tests/test_preflight_stations.py` |
| `station_scope_stamp` | cannot stamp the area's scope: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_explored_in.py`, `tests/test_preflight_stations.py` |
| `station_working_tree` | uncommitted changes in {…} (commit or stash before the run) | finding | WARNING | GUARANTEED | LAB-010 Commit before the run | direct | 20 | 0 | `tests/test_agent_hooks.py`, `tests/test_end_to_end.py`, `tests/test_explored_in.py`, `tests/test_preflight.py`, `tests/test_repeat_cost_lowered_and_waived_audit.py` |
| `station_hooks` | {…} | finding | WARNING | GUARANTEED | LAB-011 Required-field check | direct | 42 | 0 | `tests/test_agent_hooks.py`, `tests/test_codex_hooks.py`, `tests/test_end_to_end.py`, `tests/test_explored_in.py`, `tests/test_high_compute_workflow.py`, `tests/test_next_step.py`, `tests/test_preflight.py`, `tests/test_preflight_stations.py`, `tests/test_repeat_cost_lowered_and_waived_audit.py` |
| `tell_test_run` | pytest is not installed in this interpreter — tests not run | finding | WARNING | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_finalize_steps.py` |
| `tell_test_run` | {…} did not run{…} — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_finalize_steps.py`, `tests/test_read_causes.py` |
| `tell_test_run` | {…} failed{…} — {…} | finding | BLOCKER | GUARANTEED | variable | direct | 12 | 0 | `tests/test_agent_hooks.py`, `tests/test_area_tests_root.py`, `tests/test_end_to_end.py`, `tests/test_finalize.py`, `tests/test_finalize_steps.py`, `tests/test_preflight.py`, `tests/test_preflight_stations.py`, `tests/test_read_causes.py`, `tests/test_reference_end_to_end.py` |

## `labkit/gates/registered_report.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `result_owed` | {…} registers {…} as its report, and {…} carries neither {…} nor the protocol's handover … | finding | BLOCKER | GUARANTEED | variable | direct | 12 | 0 | `tests/test_origin_scenario.py`, `tests/test_report_check.py`, `tests/test_reported_through.py` |
| `_undetermined_duty` | {…}: whether it owes a report cannot be told — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 13 | 0 | `tests/test_audit.py`, `tests/test_end_to_end.py`, `tests/test_registered_report_stations.py`, `tests/test_registration_committed.py` |
| `report_binding_gap` | {…} registered {…} as its report {…}, and its head now registers none — the report a meas… | finding | BLOCKER | GUARANTEED | open assignment | direct | 14 | 0 | `tests/test_registration_committed.py` |
| `orphaned_report_duties` | {…}: no protocol of the area carries the id {…}, under which it measured ({…}); that prot… | finding | BLOCKER | GUARANTEED | open assignment | direct | 4 | 0 | `tests/test_registration_committed.py` |
| `missing_report` | {…} registers {…} as its report; the report is missing ({…}), and its area holds a measur… | finding | BLOCKER | GUARANTEED | variable | direct | 1 | 0 | `tests/test_adopt.py` |
| `missing_report` | {…} registers {…} as its report; the report is missing ({…}), and its area holds a measur… | finding | BLOCKER | GUARANTEED | variable | direct | 5 | 0 | `tests/test_next_step.py`, `tests/test_registration_committed.py`, `tests/test_report_check.py` |
| `registered_review` | {…}: its discussion blocks do not read — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_registered_report_stations.py` |

## `labkit/gates/registration_hold.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `registration_changes` | the first measurements recorded different registrations: {…} — which one stood before the… | finding | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | direct | 3 | 0 | `tests/test_counter_cases.py`, `tests/test_registration_committed.py`, `tests/test_replacement.py` |
| `registration_changes` | the registration changed after the first measurement {…}{…}: {…} (recorded by the answeri… | finding | BLOCKER | GUARANTEED | variable | direct | 6 | 0 | `tests/test_registration_committed.py` |
| `types_split_hold` | the first measurements registered different types: {…} — which workflow binds the runs ca… | finding | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | direct | 1 | 0 | `tests/test_registration_station.py` |
| `type_hold` | the type changed after the first measurement {…}: "{…}" → "{…}" ({…}) — the workflow that… | finding | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | direct | 4 | 0 | `tests/test_exploration_hold.py`, `tests/test_registration_station.py` |
| `release_unchecked` | whether a correction in place releases what the number is about cannot be checked: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_finalize_steps.py`, `tests/test_unread_registration.py` |
| `seen_hold` | what the number is about changed after the first measurement {…}{…}: {…} (as the answerin… | finding | BLOCKER | GUARANTEED | variable | direct | 34 | 17 | `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_registration_committed.py`, `tests/test_registration_station.py`, `tests/test_repair_guidance.py`, `tests/test_rules_registration_hold.py` |
| `split_hold` | the first measurements saw different texts of what the number is about: {…} — {…} — which… | finding | BLOCKER | GUARANTEED | variable | direct | 8 | 0 | `tests/test_exploration_hold.py`, `tests/test_registration_committed.py` |
| `now_hold` | what the number is about changed after the first measurement {…}{…}: {…} (as the protocol… | finding | BLOCKER | GUARANTEED | variable | direct | 24 | 15 | `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_repair_guidance.py`, `tests/test_rules_registration_hold.py`, `tests/test_unread_registration.py` |
| `unread_hold` | what the number is about cannot be compared with its first measurement: {…} — the compari… | finding | BLOCKER | GUARANTEED | technical contract | direct | 12 | 0 | `tests/test_audit.py`, `tests/test_origin_scenario.py`, `tests/test_registration_committed.py`, `tests/test_unread_registration.py`, `tests/test_ways_out.py` |
| `unread_history_hold` | {…} — the runs and start files a commit holds were not read back, so whether a start file… | finding | BLOCKER | GUARANTEED | technical contract | direct | 6 | 1 | `tests/test_finalize_steps.py`, `tests/test_registration_committed.py`, `tests/test_report_check_stations.py`, `tests/test_rules_registration_hold.py`, `tests/test_unread_registration.py` |
| `binding_conflict_hold` | which protocol a run belongs to is contradicted: {…} — no file is taken over another, so … | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 1 | `tests/test_end_to_end.py`, `tests/test_registration_station.py`, `tests/test_rules_registration_hold.py` |
| `missing_start_hold` | {…} — which protocol it was bound to at its start and when it started cannot be checked, … | finding | BLOCKER | GUARANTEED | technical contract | direct | 6 | 1 | `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_finalize_steps.py`, `tests/test_rules_registration_hold.py` |
| `lost_record_hold` | what the number is about cannot be compared with its first measurement: {…} — {…} may hav… | finding | BLOCKER | GUARANTEED | technical contract | direct | 15 | 5 | `tests/test_end_to_end.py`, `tests/test_registration_committed.py`, `tests/test_registration_station.py`, `tests/test_rules_registration_hold.py` |
| `later_record_warning` | {…} — the start files put {…} after that of a measurement of this protocol that reads, an… | finding | WARNING | GUARANTEED | technical contract | direct | 7 | 1 | `tests/test_end_to_end.py`, `tests/test_exploration_hold.py`, `tests/test_registration_committed.py`, `tests/test_rules_registration_hold.py` |

## `labkit/gates/report_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `freeze_gaps` | {…}: not `frozen = true` — a reported number owes the freeze | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 8 | 0 | `tests/test_audit.py`, `tests/test_protocol_fill.py`, `tests/test_replacement.py`, `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py` |
| `freeze_gaps` | {…}: {…} | finding | BLOCKER | GUARANTEED | variable | direct | 15 | 0 | `tests/test_audit.py`, `tests/test_protocol_fill.py`, `tests/test_registration_committed.py`, `tests/test_replacement.py`, `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py` |
| `freeze_gaps` | {…}: line {…}: {…} still a placeholder | finding | BLOCKER | GUARANTEED | LAB-011 Required-field check | direct | 1 | 0 | `tests/test_report_check_areas.py` |
| `repeated_gaps` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_report_check_areas.py` |
| `registration_gaps` | not a git repository — the registration cannot be held to the commit of the first measure… | finding | WARNING | GUARANTEED | technical contract | direct | 25 | 0 | `tests/test_registration_committed.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py` |
| `_registration_at` | {…} recorded no commit ({…}{…}) — it started outside the history, so the registration can… | finding | BLOCKER | GUARANTEED | LAB-010 Commit before the run | direct | 2 | 0 | `tests/test_registration_committed.py` |
| `_registration_at` | {…} recorded no commit ({…}{…}) — what the run started from is unknown, so the registrati… | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_registration_committed.py` |
| `_registration_at` | {…} ({…}{…}) recorded a commit this repository does not hold (a rewritten history, a shal… | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_registration_committed.py` |
| `_registration_at` | {…} at {…} ({…}{…}) cannot be read: {…} — the registration that stood before the number c… | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_registration_committed.py`, `tests/test_unread_registration.py` |
| `_registration_at` | {…} was not committed at {…} ({…}{…}) — nothing stood before the number; the registration… | finding | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | direct | 1 | 0 | `tests/test_registration_committed.py` |
| `_registration_at` | the registration as committed at {…} ({…}{…}) lacks {…} — the registration is what the co… | finding | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | direct | 6 | 0 | `tests/test_registration_committed.py` |
| `analysis_audit_gap` | no answering run to hold it to — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py` |
| `analysis_audit_gap` | the analysis audit cannot be held to the run: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_handovers.py`, `tests/test_report_check_stations.py` |
| `analysis_audit_gap` | the analysis audit cannot be held to the area: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_protocol_fill.py`, `tests/test_report_check_stations.py` |
| `analysis_audit_gap` | no analysis audit covers the area as it is now, and none can run — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 9 | 0 | `tests/test_end_to_end.py`, `tests/test_handovers.py` |
| `analysis_audit_gap` | no analysis audit covers the area as it is now, and none can until the exploration link r… | finding | BLOCKER | GUARANTEED | variable | direct | 9 | 0 | `tests/test_exploration_link_scenario.py`, `tests/test_explored_in.py`, `tests/test_report_check_stations.py` |
| `analysis_audit_gap` | {…} | finding | BLOCKER | GUARANTEED | variable | direct | 107 | 0 | `tests/test_adopt.py`, `tests/test_adopt_per_protocol.py`, `tests/test_agent_hooks.py`, `tests/test_answer_reading_scenario.py`, `tests/test_audit.py`, `tests/test_codex_hooks.py`, `tests/test_deliverable.py`, `tests/test_end_to_end.py`, `tests/test_evidence_unread.py`, `tests/test_exploration_hold.py`, `tests/test_exploration_link_scenario.py`, `tests/test_explored_in.py`, `tests/test_handovers.py`, `tests/test_next_step.py`, `tests/test_origin_scenario.py`, `tests/test_protocol_fill.py`, `tests/test_protocol_runs.py`, `tests/test_registration_committed.py`, `tests/test_repair_guidance.py`, `tests/test_replacement.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py`, `tests/test_report_check_stations.py`, `tests/test_source_lines.py`, `tests/test_withdrawal_order.py` |
| `unreportable_gaps` | {…}: no config.json in this file state — the run's record cannot be checked | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_report_check_stations.py` |
| `unreportable_gaps` | the answering run {…}: {…} — its number cannot be reported; a reported number owes {…} | finding | BLOCKER | GUARANTEED | variable | direct | 12 | 0 | `tests/test_agent_hooks.py`, `tests/test_finalize_open_findings.py`, `tests/test_protocol_fill.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py` |
| `cut_off_adoption_gaps` | {…}: an adoption was cut off during its check — the protocol may hold a proposal no check… | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_adopt.py` |
| `declaration_gaps` | {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 3 | 0 | `tests/test_end_to_end.py`, `tests/test_report_check.py`, `tests/test_report_check_areas.py` |
| `recomputation_findings` | {…} — no result, the numbers are not held to the run | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_gate_timeouts.py` |
| `recomputation_findings` | {…} | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 2 | 0 | `tests/test_origin_scenario.py`, `tests/test_report_check_areas.py` |
| `recomputation_findings` | {…} | finding | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | direct | 56 | 0 | `tests/test_adopt_per_protocol.py`, `tests/test_audit.py`, `tests/test_deliverable.py`, `tests/test_end_to_end.py`, `tests/test_evidence_unread.py`, `tests/test_exploration_hold.py`, `tests/test_exploration_link_scenario.py`, `tests/test_handovers.py`, `tests/test_next_step.py`, `tests/test_origin_scenario.py`, `tests/test_protocol_fill.py`, `tests/test_protocol_runs.py`, `tests/test_registration_committed.py`, `tests/test_repair_guidance.py`, `tests/test_replacement.py`, `tests/test_report_check_areas.py`, `tests/test_withdrawal_order.py` |

## `labkit/gates/report_decisions.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `limit_gaps` | the result cannot be rendered from {…}: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 4 | 0 | `tests/test_origin_scenario.py`, `tests/test_report_decisions_stations.py` |
| `followup_findings` | the carried findings of {…} do not form a chain: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_report_decisions_stations.py` |
| `check_limit_effects_decided` | {…}: a BLOCKER decided limitation owes its effect on the verdicts | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 4 | 1 | `tests/test_decision_review.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` |
| `check_decision_reviews_read` | a review nobody can read: {…} | finding | WARNING | GUARANTEED | technical contract | direct | 3 | 1 | `tests/test_decision_review.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` |
| `check_limits_upheld` | {…}: `{…}` on a {…} decided limitation {…} — no decision review upholds that {…} | finding | variable | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 24 | 7 | `tests/test_decision_review.py`, `tests/test_end_to_end.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` |
| `check_contested_closings_upheld` | audit {…} #{…}: `{…}` on a {…} a review said {…} on ({…}) — closing a finding a reviewer … | finding | variable | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 4 | 2 | `tests/test_decision_review.py`, `tests/test_rules_report_decisions.py` |
| `check_repaired_claims_upheld` | audit {…} #{…}: `fixed` on a BLOCKER on the Conclusion {…} — no follow-up audit is shown … | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 1 | 1 | `tests/test_rules_report_decisions.py` |
| `check_first_dismissals_upheld` | audit {…} #{…}: `false-positive` on a BLOCKER {…} — a blocking finding is not released by… | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 6 | 1 | `tests/test_decision_review.py`, `tests/test_end_to_end.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` |
| `check_earlier_blockers_released` | audit {…}: {…} | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 19 | 2 | `tests/test_adopt_per_protocol.py`, `tests/test_audit.py`, `tests/test_counter_cases.py`, `tests/test_decision_review.py`, `tests/test_end_to_end.py`, `tests/test_rules_report_decisions.py` |
| `check_carried_closings_upheld` | audit {…} #{…}: a carried finding (from {…}) `{…}` — the follow-up did not find the fault… | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 4 | 2 | `tests/test_audit.py`, `tests/test_report_decisions_stations.py`, `tests/test_rules_report_decisions.py` |

## `labkit/gates/report_exploration.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `later_use_findings` | data use after the audit: run {…} of {…} recorded {…} — {…}. The run is taken as not show… | finding | WARNING | STATIC_EVIDENCE | LAB-050 Analysis audit before reporting | direct | 5 | 0 | `tests/test_explored_in.py` |
| `unresolved_link_hold` | exploration link: [explored_in] protocol = {…} names {…} — the exploration this confirmat… | finding | BLOCKER | GUARANTEED | technical contract | direct | 18 | 8 | `tests/test_exploration_link_scenario.py`, `tests/test_explored_in.py`, `tests/test_rules_report_exploration.py` |

## `labkit/gates/report_hold.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `staged_area_gap` | {…}: the working tree differs from the index ({…}) — {…} the tree, the commit holds the i… | finding | BLOCKER | GUARANTEED | technical contract | direct | 17 | 0 | `tests/test_end_to_end.py`, `tests/test_next_step.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_hold_stations.py` |
| `through_gap` | {…}: {…} | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 3 | 0 | `tests/test_origin_scenario.py`, `tests/test_reported_through.py` |
| `through_gap` | {…} differs from what the analysis run's record and adoption say now — a stale rendering … | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_reported_through.py` |
| `through_gaps` | line {…}: the reported-through block of {…} repeats the block at line {…} — one block per… | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_reported_through.py` |
| `owed_blocks` | line {…}: cites run {…}, the adopted result of {…}, without its generated block — the num… | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 7 | 0 | `tests/test_next_step.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_source_lines.py` |
| `hold_report` | {…}: {…} | finding | BLOCKER | GUARANTEED | variable | direct | 1 | 0 | `tests/test_report_hold_stations.py` |
| `hold_report` | {…} | finding | WARNING | STATIC_EVIDENCE | LAB-003 No run without an intent paragraph | direct | 1 | 0 | `tests/test_report_hold_stations.py` |
| `link_gap` | {…}: a symbolic link to {…} — a report is held as a file at its own path, never through a… | finding | BLOCKER | GUARANTEED | technical contract | direct | 4 | 0 | `tests/test_agent_hooks.py`, `tests/test_report_blocks.py` |
| `discussion_sources` | {…} names {…}, and there is no such protocol | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_report_hold_stations.py` |
| `discussion_sources` | {…}: {…}'s area has no runs/{…}/ — a discussion names a run of its protocol's area | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_area_state.py`, `tests/test_report_blocks.py` |
| `report_hints` | {…}: no assigned source found for the numbers on {…} line(s) — they stand outside every g… | finding | WARNING | STATIC_EVIDENCE | LAB-104 A number leaves the area only through its adoption | direct | 18 | 0 | `tests/test_counter_cases.py`, `tests/test_next_step.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py` |
| `report_hints` | {…}: numbers on {…} line(s) beside a discussed run — a discussed run's number in a report… | finding | WARNING | STATIC_EVIDENCE | LAB-104 A number leaves the area only through its adoption | direct | 1 | 0 | `tests/test_report_blocks.py` |
| `review_gap` | {…}: its report review cannot be told — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_claim_review.py`, `tests/test_report_hold_stations.py` |
| `review_hold` | {…}: {…} and has no clean report review of this state — and none can run: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_handovers.py`, `tests/test_report_hold_stations.py` |
| `review_hold` | {…}: the report review holds this state ({…}) — {…} | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 13 | 0 | `tests/test_claim_review.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_hold_stations.py` |
| `review_hold` | {…}: {…} and has no clean report review of this state (one naming no claim){…} — a cold r… | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 25 | 0 | `tests/test_agent_hooks.py`, `tests/test_area_state.py`, `tests/test_claim_review.py`, `tests/test_handovers.py`, `tests/test_next_step.py`, `tests/test_origin_scenario.py`, `tests/test_registration_committed.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py`, `tests/test_report_hold_stations.py`, `tests/test_reported_through.py` |
| `undeclared_findings` | {…}: line {…}: run {…} is discussed as not reported, but {…} has adopted it as its result | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 2 | 0 | `tests/test_report_blocks.py` |
| `undeclared_findings` | {…}: cites a run of a protocol whose head does not read — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_report_hold_stations.py` |
| `undeclared_findings` | {…}: cites {…}, the answering run of {…}, which adopts it in the working tree but not in … | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_report_check.py` |
| `undeclared_findings` | {…}: cites {…}, the answering run of {…}, which has adopted no result — and neither its a… | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_handovers.py` |
| `undeclared_findings` | {…}: cites {…}, the answering run of {…}, which has adopted no result | finding | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 9 | 0 | `tests/test_counter_cases.py`, `tests/test_handovers.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py` |
| `undeclared_findings` | {…}: cites {…}, which no protocol has adopted as its result — a reported number is adopte… | finding | WARNING | GUARANTEED | LAB-104 A number leaves the area only through its adoption | direct | 5 | 0 | `tests/test_counter_cases.py`, `tests/test_report_blocks.py`, `tests/test_report_check.py` |

## `labkit/gates/report_replacement.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `replacement_gaps` | {…}: {…} | finding | BLOCKER | GUARANTEED | variable | direct | 2 | 0 | `tests/test_report_replacement_stations.py` |
| `_predecessor` | [replaces] protocol is its own id | finding | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | direct | 1 | 0 | `tests/test_replacement.py` |
| `_predecessor` | [replaces] protocol = {…} names {…} | finding | BLOCKER | GUARANTEED | variable | direct | 2 | 0 | `tests/test_replacement.py`, `tests/test_report_replacement_stations.py` |
| `_predecessor` | the replacements run in a circle ({…}) | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_replacement.py` |
| `_undeclared_changes` | the registrations cannot be compared — {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_replacement.py` |
| `_undeclared_changes` | changed against {…} ({…}) and not declared: {…} {…} → {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 6 | 0 | `tests/test_counter_cases.py`, `tests/test_replacement.py` |
| `_undeclared_changes` | declares a change the registrations do not show: {…} {…} → {…} (the predecessor {…}, this… | finding | BLOCKER | GUARANTEED | technical contract | direct | 2 | 0 | `tests/test_replacement.py` |
| `_predecessor_open` | the predecessor's audit records do not read: {…} | finding | BLOCKER | GUARANTEED | technical contract | direct | 1 | 0 | `tests/test_report_replacement_stations.py` |
| `_predecessor_open` | its predecessor's BLOCKER is still open — {…} | finding | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | direct | 2 | 0 | `tests/test_replacement.py` |

## `labkit/probes/usability.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `stage` | usability | printed | WARNING | none | not recorded | not traced (printed line) | — | — | — |

## `labkit/run/batch.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `Ledger.require_complete` | {…}: the output does not balance its {…} input items — {…}. The run is NOT complete. | exit | exit | none | not recorded | direct | 6 | 0 | `tests/test_batch_ledger.py`, `tests/test_template_items.py` |
| `Store.__enter__` | {…} exists — another run is writing this output: {…} {…} | exit | exit | none | not recorded | direct | 8 | 0 | `tests/test_batch.py` |

## `labkit/run/code_repos.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `require_recordable` | runlog: the run imports untracked code it cannot record (above {…} MB, in no commit): {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_code_repos.py` |

## `labkit/run/detached.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `main` | usage: python -P -m labkit.run.detached FD AREA UNSTARTED LOG -- COMMAND… (started by `ru… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_run_start_refusals.py` |

## `labkit/run/endpoint_lease.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `_refuse` | llm: endpoint {…} is leased to alias '{…}' (pid {…}, {…}, since {…}) — refusing to run '{… | exit | exit | none | not recorded | direct | 6 | 0 | `tests/test_endpoint_lease.py` |

## `labkit/run/lanes.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `Lanes.balance` | {…}: rows of {…} instruments — {…} — one file holds one measurement: write a new output f… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_lanes.py` |
| `Lanes.require_registered_prompts` | {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_lanes.py` |
| `Lanes.require_registered_prompts` | {…}: the prompt this script sends is not the registered one — {…} line(s) the Prompt bloc… | exit | exit | none | not recorded | direct | 2 | 0 | `tests/test_lanes.py` |

## `labkit/run/llm_cache.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `_require_declared` | llm_cache: the lab has not declared a cache — a cached answer repeats instead of measurin… | exit | exit | none | not recorded | direct | 2 | 0 | `tests/test_llm_cache.py` |

## `labkit/run/runlog.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `_repeat_parent` | runlog: {…} is itself a repeat of {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_repeats.py` |
| `_repeat_draw` | runlog: repeat_of and derived_from exclude each other — a repeat asks the model again, a … | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_repeats.py` |
| `_repeat_draw` | runlog: repeat_of={…}: the next draw number cannot be counted — {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_repeats.py` |
| `_repeat_draw` | runlog: repeat_of={…}: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_run_start_refusals.py` |
| `_repeat_draw` | runlog: this run is no repeat of {…} — it measures something else: {…} | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_repeats.py` |
| `_declared_under` | runlog: labkit runs from a source tree that is not installed, so the version this run's a… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_installed_version.py` |
| `_decide_origins_and_warn` | {…} | exit | exit | none | not recorded | direct | 7 | 0 | `tests/test_input_origins.py`, `tests/test_public_api.py` |
| `Run._write_start_file` | runlog: {…} exists — a run with the id {…} started before, and its start file is never ov… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_run_starts.py` |
| `Run._write_start_file` | runlog: the start of {…} could not be recorded in {…}: {…} — the run did not start, and n… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_run_starts.py` |
| `_require_no_open_twin` | runlog: {…} is still measuring in {…}: {…} — a second measurement beside it would read an… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_runlog_wait.py` |

## `labkit/run/start_check.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `protocol_binding` | runlog: protocol={…} is not one of the PROTOCOL-*.md in the run's area ({…}): {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_run_start_refusals.py` |
| `protocol_binding` | runlog: {…} protocols in {…} — nothing would say which one this run belongs to: {…} | exit | exit | none | not recorded | direct | 2 | 0 | `tests/test_run_start_refusals.py`, `tests/test_run_starts.py` |
| `protocol_binding` | runlog: {…}: {…} | exit | exit | none | not recorded | direct | 4 | 0 | `tests/test_protocol_identity.py`, `tests/test_runlog_freeze_gate.py` |
| `_undecided_findings` | runlog: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_runlog_unfrozen_blocker.py` |
| `_audit_unavailable` | runlog: LABKIT_UNFROZEN=1 — the area cannot be stamped ({…}), so no failed audit attempt … | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_run_start_refusals.py` |
| `_audit_unavailable` | runlog: promise block: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_run_start_refusals.py` |
| `_audit_unavailable` | runlog: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_runlog_unfrozen_failed_audit.py` |
| `_audit_unavailable` | runlog: this run declares run_kind='measurement' (a full run) on a protocol not ready for… | exit | exit | none | not recorded | direct | 7 | 0 | `tests/test_runlog_freeze_gate.py`, `tests/test_runlog_unfrozen_failed_audit.py` |
| `_promise_snapshot` | runlog: promise block: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_promises.py` |
| `foreground_timeout` | runlog: {…}={…} is not a number of seconds >= 0 | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_runlog_freeze_gate.py` |
| `require_valid_reseed` | runlog: reseed draws a repeat's seed anew — it goes with repeat_of | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_repeats.py` |
| `require_valid_reseed` | runlog: reseed: the config holds no integer `{…}` to draw anew ({…}) | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_repeats.py` |
| `require_valid_reseed` | runlog: reseed: the protocol registers `{…}` = {…} — a spread over seeds needs a seed the… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_repeats.py` |
| `require_registration` | runlog: {…}: {…} | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_registration_contract.py`, `tests/test_runlog_freeze_gate.py` |
| `require_registration` | runlog: {…}: {…} | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_promises.py`, `tests/test_registration_contract.py` |
| `require_answer_reading` | runlog: answer_reading declares what a derived run re-reads its parent's answers with — i… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_answer_reading_start.py` |
| `require_answer_reading` | runlog: answer_reading: {…} lies in no git repository, so the module cannot be compared w… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_run_start_refusals.py` |
| `require_answer_reading` | runlog: answer_reading = {…}: no such file | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_answer_reading_start.py` |
| `require_answer_reading` | runlog: answer_reading = {…} lies outside the repository {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_answer_reading_start.py` |
| `require_answer_reading` | runlog: answer_reading: the code {…} imports cannot be read: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_run_start_refusals.py` |
| `require_answer_reading` | runlog: answer_reading = {…}: {…} does not import it, so it reads none of the answers | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_answer_reading_start.py` |
| `completed_parent` | runlog: {…}={…}: {…} | exit | exit | none | not recorded | direct | 2 | 0 | `tests/test_repeats.py` |
| `completed_parent` | runlog: {…}={…} names no completed run under {…} ({…}){…} | exit | exit | none | not recorded | direct | 6 | 0 | `tests/test_builds_on.py`, `tests/test_completion_consumers.py`, `tests/test_repeats.py`, `tests/test_run_completion.py` |
| `_derived_parent` | runlog: derived_from={…} is not a run id | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_repeats.py` |
| `_derived_parent` | runlog: derived_from={…} is a repeat of {…} — supporting evidence, never the answer | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_repeats.py` |
| `require_step_basis` | runlog: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_builds_on.py` |
| `require_step_basis` | runlog: [builds_on] run = {…} is a repeat of {…} — supporting evidence, never a step's ba… | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_builds_on.py` |
| `require_step_basis` | runlog: [builds_on] run = {…} is bound to {…}, not to this protocol ({…}) | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_builds_on.py` |
| `require_exploration_link` | runlog: {…} | exit | exit | none | not recorded | direct | 1 | 0 | `tests/test_explored_in.py` |
| `require_exploration_link` | runlog: this is the first measurement of {…}, and its [explored_in] is no valid link to a… | exit | exit | none | not recorded | direct | 2 | 0 | `tests/test_explored_in.py` |
| `prepare` | runlog: run_kind='probe' is not allowed at repeat_cost='low' — this repeat cost has no se… | exit | exit | none | not recorded | direct | 3 | 0 | `tests/test_registration_contract.py`, `tests/test_run_kind.py`, `tests/test_runlog_freeze_gate.py` |
| `require_detached` | runlog: this run declares run_kind='measurement' and sits in a foreground shell an agent … | exit | exit | none | not recorded | direct | 6 | 0 | `tests/test_audit_robustness.py`, `tests/test_run_record_atomic.py`, `tests/test_runlog_freeze_gate.py`, `tests/test_runlog_wait.py` |
| `freeze_gate` | runlog: {…}, and a preflight audit found BLOCKER(s) nobody decided — not an unfrozen prot… | exit | exit | none | not recorded | direct | 2 | 0 | `tests/test_runlog_unfrozen_blocker.py` |
| `freeze_gate` | runlog: {…}, but its protocol is not ready for one: {…} | exit | exit | none | not recorded | direct | 22 | 0 | `tests/test_exploration_hold.py`, `tests/test_obligations_scenario.py`, `tests/test_runlog_freeze_gate.py`, `tests/test_runlog_unfrozen_failed_audit.py` |

## `labkit/tools/protocol_fill.py`

| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |
|---|---|---|---|---|---|---|---|---|---|
| `_handover_file` | WARNING: {…} | printed | WARNING | none | not recorded | not traced (printed line) | — | — | — |
