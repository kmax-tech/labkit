# Next-step guidance audit — 2026-11-24

Checked `9b2db944`, package 0.115.0 plus unreleased changes, without changing product code. The question is whether `labkit-next` names a step that actually advances the area and agrees with the gates. Two guidance defects were reproduced; neither is evidence of an incorrect release of a result.

## Medium — the first evaluation-repair hold omits the correction path

After a completed original run, repair only the evaluation in its measuring script. Before any derived run exists, `labkit-next` correctly holds the changed code, but its only ways out are to measure anew or restore an unintended edit. It does not offer the implemented correction path with `derived_from` and `answer_reading`.

The real temporary fixture from `tests/test_answer_reading_scenario.py` reproduces this. The original run's rows and answer-reading module stay unchanged. The next step says "measure anew with the code as it is now and audit that run", followed by restoration advice. An assertion that this step mentions `answer_reading` fails. The missing advice could send a user to collect new answers unnecessarily; the finding does not show that new model calls are technically required.

Cause: `code_since_run` adds `_or_declared` only while comparing a parent for an already existing child (`labkit/checks/run_record_check.py:203`). For the answering run itself, `child` is None and `_run_code` supplies only `FIX_FIRST`. `next_step._held_step` prints that finding's fix (`labkit/gates/next_step.py:539`). The supported correction is therefore discoverable in this message only after the user has already made a derived run without its declaration. The workflow documents the path, but the first code-change hold does not point to it.

Control: once a declared correction is created in the same temporary fixture, the actual next steps are analysis audit, adoption after an explicit stand-in audit record, and finally nothing held. Adoption and report checking pass; no model or paid audit was called. This validates the later guidance for that fixture, not a production laboratory's scientific conclusion.

Suggested repair scope: offer the correction path conditionally on an evaluation-only repair at the first relevant code-change hold too. Preserve the full code check and the requirement to collect new answers when the measurement changed. Add a test starting before the derived run exists, not only after an undeclared derived run.

## Medium — an existing area without a protocol receives a non-progressing command

For a valid temporary lab layout with `models.toml`, `experiments/01-x/` and no protocol or historical report duty, `labkit-next` recommends `labkit-init exp <name> --kind compute|fit|apply` as the way to stamp the area and its protocol (`labkit/gates/next_step.py:170`).

Executing that command with name `x`, kind `compute` and low repeat cost is refused: "experiment already exists: 01-x" (`labkit/tools/scaffold.py:685`). The area remains without a protocol, and another `labkit-next` repeats the same advice. Creating a different name succeeds, but creates a different area and does not repair the selected one. That successful control also verifies that the refusal is not due to a missing lab layout.

`tests/test_next_step_before_the_chain.py:95` checks only that the guidance contains `labkit-init exp`; it does not execute it. A regression test should take the recommended action and confirm progress for the same selected area. How to recover or complete this area must be specified without deleting existing files or bypassing a historical obligation; the existing orphaned-report restore branch is a separate case and was not implicated by this probe.

## Scope and verification

Read the next-command entry point, state ordering, gate-derived holds and closing steps, the workflow's correction instructions, and relevant tests. Exercised temporary labs only; no original experiment, paid model call, paid audit or release was changed. The correction probe used the existing fixture and its explicit stand-in audit mechanism. It covered a repaired original run before a child exists, a declared corrected run awaiting an audit, an audited corrected run awaiting adoption, and the adopted state with report checking.

Local probe outputs: `/private/tmp/labkit-next-correction-missing-hint.log` (the failing assertion on absent guidance), `/private/tmp/labkit-next-correction-probe.log` (the subsequent complete correction sequence), and `/private/tmp/labkit-next-correction-probe.py` (temporary probe). The existing-area probe was run directly through `next_command.main` and `scaffold.main` on a temporary lab; both refusals and the successful new-area control were inspected.

- Own focused run: `.venv/bin/pytest -q tests/test_next_step_before_the_chain.py tests/test_next_step.py tests/test_answer_reading_scenario.py -n 2 --tb=short`, Exit 0; 47 passed and 5 subtests passed in 361.50 seconds. Output: `/private/tmp/labkit-next-audit-focused.log`. This covers the ordinary count workflow, missing registration fields, open runs and detached starts, audit and adoption, progress accounts and report review, multiple protocols, working-tree/index differences, and the correction's existing positive and negative cases.
- Additional correction-guidance probe: `.venv/bin/python /private/tmp/labkit-next-correction-probe.py`, Exit 0, one test in 74.636 seconds. It records the absent entry hint, then checks the actual sequence through adoption and report checking. The earlier assertion demanding that missing hint failed as recorded above; that was a diagnostic outside the existing test suite.
- A complete `.githooks/checks full` was already running in another session on the same code state; no second full run was started. Its completed output and runner status were inspected: ruff, format, pyright and pytest each Exit 0; 4575 passed, 1 skipped and 7828 subtests passed in 1297.53 seconds. The runner recorded `checks exit 0`. Copies: `/private/tmp/labkit-next-audit-full-checks.log` and `/private/tmp/labkit-next-audit-full-runner.log`. The product code remained the code of `9b2db944`; after the full run, `d58905c6` changed only the TODO to record its result (verified by the diff). The focused run overlapped part of that full run.
- The independent agent `next_audit_reader` read the documentation diff, relevant source and both correction logs. It confirmed both medium findings, independently reproduced the existing-area loop with its successful fresh-area control, and corrected one source line reference. It did not repeat the complete correction sequence. The final verification text was completed after the product-code tests; no product code or repository tests were changed.

These are bounded checks, not proof of correctness for every possible area state. No new end-to-end probe of a model-backed laboratory, a high-cost freeze workflow or every repair type was performed. Both guidance repairs remain separate work.
