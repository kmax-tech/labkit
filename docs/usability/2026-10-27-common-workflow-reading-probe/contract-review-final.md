# Final contract and clarity review

Independent rereading of the final `labkit/templates/AGENTS.md.template`, following the first report in `contract-review.md`. This is static evidence about instruction clarity and the current API contract, not measured execution success. No models, tests or experiments were run; concurrent Python changes were consulted only where necessary to establish the contract.

All four earlier findings are addressed:

- Lines 132–135 explicitly unfreeze before the high-cost repair cycle, preserve the registration, and require renewed preflight coverage and freeze before the new measurement. This matches the warning/blocking distinction in `labkit/gates/preflight.py:381`.
- Lines 157–158 require review for carried BLOCKERs closed as dismissed or deferred even without an earlier rejection, matching `labkit/gates/decision_review.py:119` and the release hold in `labkit/gates/report_check.py:832`.
- Lines 8–10 require `--protocol <PROTOCOL>` for audit, decision and review commands when several protocols exist and preserve it in printed commands, matching `labkit/formats/repo.py:120`, `labkit/formats/repo.py:778` and effect validation in `labkit/gates/audit.py:1572`.
- Lines 149–150 restore a real prompt/answer pair per finding from the kept output, matching LAB-040 in `labkit/docs/standard.md:755`.

The added C/A/B definitions agree with `labkit/formats/promises.py`. The complete show and probe commands use the repo interpreter and area script; the estimator's optional probe size makes the bare `--probe` valid (`labkit/templates/measure-estimator-script.py.template:387`), and the prompt skeleton documents and delegates the same form (`labkit/templates/measure-script.py.template:7`, :251).

No remaining concrete misleading instruction was found within this review's scope. High-cost compute still explicitly skips show/probe while retaining preflight and freeze; low cost retains its single analysis-audit obligation; kind, repeat cost and scientific type remain separate. Accepted not-assessable effects and failed admissibility govern generated reportable verdicts while raw metrics stay unchanged, as `labkit/checks/result_render.py:64` specifies.

verdict: 0 findings
