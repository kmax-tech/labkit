# Code clarity and control flow review — 2026-11-12

Reviewed code: `2ae7a110`. Requested assessment: whether responsibilities, control flow and the result of the check restructuring are understandable. This is one reader's focused review, not a complete correctness audit. No product code was changed.

## Verdict

Individual checks have clearer inputs and locally testable conditions. The main entry points show the order and most applicability decisions explicitly. Responsibilities become less clear across the boundaries between the release chain, audit coverage readers and next-step advice. Passing an area state does not mean that all later decisions use the same observation of files. The findings below are maintenance and consistency risks; this review did not establish an incorrect release of an experiment.

## Findings

### Medium: audit coverage is repeatedly rebuilt outside the supplied evidence

Kind: responsibility and consistency risk.

`report_context.checked` supplies an `AreaState` and `AreaEvidence`, and `finalize_findings` passes both into finalize. However, `audit_binding.covering_analysis` reads `findings.area_records(area)` and recomputes `analysis_now`; that recomputation stamps code and reads the shown run contents again. It is called separately by `report_check.analysis_audit_gap`, `report_decisions.limit_gaps`, `review_findings` and `followup_findings`. The audit-coverage station also computes `analysis_now` before calling `covering_analysis`, which computes it again. Rendering can ask for coverage again through `result_render.limits_of`.

References: `labkit/checks/audit_binding.py:331`, `labkit/checks/audit_binding.py:346`, `labkit/gates/report_check.py:458`, `labkit/gates/report_decisions.py:74`, `labkit/gates/report_decisions.py:119`, `labkit/gates/report_decisions.py:155`, `labkit/checks/result_render.py:191`.

Consequence: there is no single owner of the coverage observation for one release chain. Maintenance requires tracking which data came from the supplied evidence and which were read again; repeated stamping also costs work. Files changing between reads could produce different observations, but a concurrent-change failure was not reproduced here.

Possible local correction, not authorized implementation work: compute coverage and its read failure once for the chain, then pass that result to the dependent stations. This does not require a general check registry or migration of other gates.

### Medium: dependent stations return an empty list when they cannot check

Kind: control-flow dependency.

`limit_gaps`, `review_findings` and `followup_findings` catch selected coverage errors and return `[]`, relying on `analysis_audit_gap` to report the failure earlier. The current `chain_gaps` order provides that station. However, the same return value represents no applicable finding and inability to determine the answer. The safety dependency is in docstrings and ordering rather than in the input or result of these functions.

References: `labkit/gates/report_decisions.py:71`, `labkit/gates/report_decisions.py:116`, `labkit/gates/report_decisions.py:152`, `labkit/gates/report_check.py:822`.

Verification: with `covering_analysis` replaced by a function raising `ValueError`, all three stations returned `[]`. A raw `PermissionError` propagates from all three: they do not catch all execution errors uniformly. This probe establishes the return behavior, not a bypass of the current chain.

Consequence: extracting, reordering or calling one of these stations requires knowing its sibling's error ownership. A shared coverage result from the preceding finding would make the prerequisite explicit and prevent repeated error handling.

### Medium: the hook reuses chain results but rebuilds the state for advice

Kind: duplicated reading and inconsistent lifetime of context.

`agent_hooks._stop_checks` calls `hold_reported`, then `missing_reports`, then potentially `steps_for`. Chains are handed forward, but their area states and evidence are not. `missing_reports` calls `state_of(area)` per protocol; `next_step` builds state and evidence again even when a chain was supplied. `steps_for` also calls `reached_by` again. Independently, `repo_sources` calls `present_run_dirs` per protocol rather than per area.

References: `labkit/gates/agent_hooks.py:304`, `labkit/gates/agent_hooks.py:319`, `labkit/gates/agent_hooks.py:394`, `labkit/gates/next_step.py:159`, `labkit/gates/next_step.py:300`, `labkit/gates/report_hold.py:423`.

Verification: a call-count probe with two protocols in the same area produced two calls to `present_run_dirs` in `repo_sources`. The hook and advice rebuilds were traced in the code; their end-to-end count and latency were not measured.

Consequence: reuse avoids rerunning some checks, but it does not establish one shared observation for the hold and the proposed next action. The path is harder to understand than the individual functions. A possible correction is to carry the existing context alongside the chain, only if this boundary is changed for a concrete reason; no new caching framework is proposed.

### Low: the architecture's current-state counts describe an obsolete migration stage

Kind: documentation drift.

`docs/architecture.md:30` states that 194 sites build gate findings, with 14 known rules and 179 open assignments. The current inventory reports 215 gate findings and, across all 278 inventoried sites, 85 known rules, 86 technical contracts, 17 open sites and 27 assignments passed from causes. These are source estimates, not runtime observations; the inventory also reports the other channels separately.

Consequence: the first architectural explanation sends a reader back to a largely undecided proposal, even though much of that work has been completed. Prefer linking to the inventory for changing counts and retaining the stable contract in the architecture document.

## What is already clear

- `finalize_area` names its stations and makes the answering-run and lane conditions visible in its body (`labkit/gates/finalize.py:910`). Its final exit explicitly follows the collected blockers.
- `chain_gaps` shows the release order, proposal exceptions and review conditions in one place (`labkit/gates/report_check.py:822`). `undeclared`, `review` and `file_state` have distinct documented purposes; understanding adoption still requires following their combination.
- `GateFinding` validates grade, evidence kind, explicit rule assignment and stated outcome centrally (`labkit/formats/gate.py:265`). This is a clearer responsibility than reproducing these decisions at each output site.
- Adoption rollback and its pending marker have an explicit owner (`labkit/tools/protocol_fill.py:152`). The convenience command lists and executes its steps in order (`labkit/tools/adopt.py:47`).

These strengths support local maintenance. They do not make the full package small or establish a single immutable snapshot for a whole hook.

## Verification and limits

Focused suite: `.venv/bin/pytest -q tests/test_gate.py tests/test_rules_report_decisions.py tests/test_report_decisions_stations.py tests/test_area_state.py tests/test_architecture.py` — 110 passed, 51 subtests passed, exit 0. The inventory command exited 0. Its output was read, including its summary and explicit estimate limits. The architectural guard's direct-file-access detector was read with its known-positive test; it does not prove absence of transitive reads through format helpers.

No full suite, real model call, concurrent edit experiment or exhaustive review of runlog, backends and writers was performed. The four findings are not instructions to start another general refactoring round. The concrete observations above can guide a separately chosen change; the usage round remains a separate research task.

## Decided by the author on 2026-11-12

The review shows maintenance risks; it does not justify a new abstraction. No wrong release and no diverging observation was reproduced, and the repeated reads were not measured.

1. **The architecture note is corrected.** Its entry no longer repeats counts that change with every decision; it points to `python -m labkit.tools.check_inventory` and the open-assignments note.
2. **A shared audit coverage is deferred.** No work before the usage round. It is taken up again on measured cost, on observations that contradict each other, or on a concrete maintenance problem.
3. **The station dependency is documented, not enforced by the interface** — the precise reading of the second finding. A gate test now holds it: on an area whose coverage does not read, `limit_gaps`, `review_findings` and `followup_findings` give `[]` and `analysis_audit_gap` is the blocker (`tests/test_report_check_stations.py`, `TheDecisionStationsLeaveUnreadableCoverageToTheAuditGap`). Before it, `analysis_audit_gap` was tested alone, and no test held the two halves on one input.
4. **The state rebuilt for the next step at the hook** stays a recorded observation.

