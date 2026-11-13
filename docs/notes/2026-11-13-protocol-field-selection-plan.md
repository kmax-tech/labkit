# Protocol field selection: analysis and proposed simplification

Reviewed commit: `faaf90f4`. Scope: creating and extending protocol forms, selecting scripts, and checking which prose fields are owed. This is a code analysis with a generated-output probe, not a scientific assessment of the fields or authorization to implement the plan. The analysis itself changed no product code.

> **State 2026-11-13.** The author decided the form question of the first finding, and `5670d378` implements it: the full form at low repeat cost now leaves out the fields its kind and model do not owe, as at high repeat cost. The central field selection must keep the output in force since `5670d378`; any further change of behaviour is a separate decision. Steps 2 to 4 are built (the commit after `f590406e`): `protocol_check.in_form` decides inclusion for every template item, the twelve items outside FIELDS stand in `GUIDANCE`, the template carries no cut marks, and `protocol_cuts.form_cut` only lays the form out. The comparison tests pass unchanged; one changed policy entry makes four of them fail. Not done: the inclusion matrix of step 1 as a document (the comparison files are its executable form), and the command scenarios of step 5 beyond the existing suite. The empty line left where the head's mark stood is kept, since removing it changes every stamp.

## Verdict

Keep the existing orchestrator, `scaffold.protocol_stamp`, and make its field selection explicit before rendering. A new orchestration framework is unnecessary. The obligation selector already exists: `protocol_check.FIELDS`, `owed_fields` and `owed` share the checker's decisions with several consumers. The missing simplification is a shared, explicit selection of what the generated form contains, including optional guidance fields.

The author's expected question should have a direct answer: given `apply`, model use, repeat cost and form extent, which fields appear, and which become required at each stage? A field being present and a field being due are different decisions. Making every displayed field mandatory would change the scientific contract.

## Findings

### Medium: initial full-form filtering differs between cost tiers

Kind: inconsistent generated form, reproduced through the stamping function. Resolved in `5670d378` (decision of the author): `protocol_stamp` applies `owed_cut` to every full form, and `tests/test_scaffold.py` (`OwedCut`) compares the fields of both tiers for every kind, with and without a model.

`scaffold.protocol_stamp` chooses the full form when `report` is true or the cost tier is high. It calls `owed_cut` only at high cost. Consequently a low-cost `apply` without a model, created with the full form, retains `Data profile`, `Prompt`, `Raw output` and `Parser cases harvested`; the high-cost form without a model removes them. This does not show a false blocker: the checker can leave a displayed field optional. It does show that task applicability and form extent do not give the same filtering at both tiers.

References: `labkit/tools/scaffold.py:691` (`protocol_stamp`), `labkit/tools/protocol_cuts.py:155` (`owed_cut`), `labkit/formats/protocol_check.py:790` (`full_owed`). Decide whether the extra fields are intentional optional guidance before changing the output.

### Medium: inclusion conditions have several representations

Kind: maintenance risk, not an established incorrect release.

The low form is selected through `<!-- l -->`, `<!-- lb -->` and `<!-- lm -->` in the Markdown template. `protocol_check.FIELDS` repeats these tags as `Field.low_cut`; tests keep the two representations equal. `bar_cut` also uses the template tags to remove bar-related items, whereas `owed_cut` consults the checker's field policy and a separate `STAMP_ONLY_NEEDS` table for Render check and Parser cases harvested.

These paths do not all implement independent doctrine: `owed_cut` already reuses the checker. However, changing an inclusion decision still requires following template markers, field metadata and text-cutting helpers. The tests are synchronization guards, not a single source for the decision.

References: `labkit/formats/protocol_check.py:101` (`FIELDS`), `labkit/formats/protocol_check.py:845` (`in_cut`), `labkit/tools/protocol_cuts.py:108` (`low_cut`), `labkit/tools/protocol_cuts.py:131` (`bar_cut`), `labkit/tools/protocol_cuts.py:152` (`STAMP_ONLY_NEEDS`), `tests/test_protocol_fields.py:37`.

### Low: creating a full form and extending an existing form use different paths

Kind: integration surface that must be covered by the plan; no data-loss defect reproduced.

Initial creation goes through `protocol_stamp`. Adding report fields to an existing area goes through `promote`, `pilot_and_report` and `insert_report_fields`. Changing the task kind reconstructs old and new stamps and carries authored fields forward. A correction limited to initial creation would leave these consumers to check separately.

References: `labkit/tools/scaffold.py:459` (`promote`), `labkit/tools/scaffold.py:691` (`protocol_stamp`), `labkit/tools/scaffold.py:949` (restamping), `labkit/tools/protocol_cuts.py:294` (`pilot_and_report`), `labkit/tools/protocol_cuts.py:318` (`insert_report_fields`).

## Current responsibilities

| Question                                                | Current owner                                                                 | Keep or change                                                                |
|---------------------------------------------------------|-------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| What does the repeat-cost tier require?                 | `standard_contract.lane`                                                      | Keep.                                                                         |
| Which script and test templates apply?                  | `standard_contract.skeleton`                                                  | Keep.                                                                         |
| Which prose fields can be owed?                         | `protocol_check.FIELDS`, `owed_fields`                                        | Reuse the existing field metadata.                                            |
| Which fields are due now?                               | `protocol_check.owed`, using freeze and adoption state                        | Keep separate from inclusion in a blank form.                                 |
| Which field items appear in a generated form?           | `protocol_stamp` and the cuts over template text                              | Consolidate the inclusion decision.                                           |
| What prose, headings and examples does a field contain? | `experiment-protocol.md.template` and task-specific placeholder substitutions | Keep text in the template; separate content substitution from selection.      |
| Which TOML tables are valid?                            | `protocol_block`, `promises`, kind-specific checks                            | Keep their typed readers; do not force TOML tables into the prose-field list. |

## Generated-output probe

The probe called `scaffold.protocol_stamp` from the reviewed worktree for all 24 combinations of three kinds, two repeat costs, model absent/present, and short/full requested form. It used a fixed valid protocol id, parsed the resulting prose fields with `protocol_check.fields`, and compared them with `owed_fields`. This exercises the protocol-stamping function, not the command-line writer, script execution, promotion or a real audit.

| Kind    | Model named | Low, short | Low, full | High, either form request |
|---------|-------------|-----------:|----------:|--------------------------:|
| compute | no          |          7 |        47 |                        37 |
| compute | yes         |         10 |        47 |                        45 |
| fit     | no          |         11 |        51 |                        47 |
| fit     | yes         |         14 |        51 |                        51 |
| apply   | no          |         11 |        51 |                        47 |
| apply   | yes         |         14 |        51 |                        51 |

The counts were taken at `faaf90f4`. Since `5670d378` the full form at low repeat cost carries the same fields as the high column.

Counts are distinct prose-field labels recognized by the parser, including optional items. They are not numbers of required fields. Every combination contained every label returned by `owed_fields`. The comparison was exercised on nonempty field lists; the form differences above are positive observations. This does not establish scientific sufficiency, absence of contradictory placeholders, or equivalence of all creation paths.

Focused existing tests: `PYTHONPATH=tests:. .venv/bin/python -m unittest test_standard_contract test_protocol_fields test_low_cut` in an isolated worktree and its own venv: 67 tests, exit 0. No full suite, model call or experiment was run.

An independent reader reviewed this analysis and plan against the source and recomputed the 24 generated forms: the counts and inclusion comparison agreed, with zero review findings. This review does not establish the scientific adequacy of the forms.

## Comparison tests before the rebuild (2026-11-13)

Three tests fix the output in force since `5670d378`. The central field selection has to keep this output. They hold only what they cover:

| Path                           | Test                                               | Covered                                                                                                                     | Result today                                                                                                                                                                                                         |
|--------------------------------|----------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| New area, `protocol_stamp`     | `tests/test_form_stamps.py`                        | 24 combinations of kind, repeat cost, model and short or report form, byte for byte against `tests/form_stamps/stamp-*.txt` | kept as found                                                                                                                                                                                                        |
| `--report` on an existing area | `tests/test_form_stamp_paths.py`, `ReportOnAnArea` | 3 kinds × 2 costs × model or not, through `stamp_area`                                                                      | low cost: protocol unchanged (nothing freezes there); high cost: byte for byte against `tests/form_stamps/report-high-*.txt`, and a protocol without its report fields gains the full form's fields and placeholders |
| `--change-kind`                | `tests/test_form_stamp_paths.py`, `ChangeKind`     | 48 cases (every pair of kinds × 2 costs × model or not × short or report form), on unfilled protocols                       | the protocol equals the new kind's stamp under the same id in all 48                                                                                                                                                 |

Checked against a known positive: with the condition of `5670d378` reverted, `test_form_stamps.py` fails in the four combinations that commit changed.

Two observations from the `--report` path, at first recorded as found: at high repeat cost a computation gained `Noise ceiling → threshold`, and without a model `Answer form + resolution`, which its full form leaves out, because `promote` inserted the template's daggered items without the field policy of `owed_cut`; and the inserted items kept the template's long placeholders, not the one-line hints and estimator wording of the stamp. The author decided that both ways to the full form must give the same fields and placeholders. Since then `scaffold.report_blocks` takes the report fields from the full form `protocol_stamp` writes for the protocol's own head. Only the two kept files `report-high-compute-*.txt` changed, each by exactly those fields. `ReportOnAnArea.test_the_fields_it_adds_are_the_full_forms` removes the report fields from a stamped protocol, runs `--report` and compares every field and placeholder with the full form; with the old code it fails for all six kind and model combinations.

Not covered: `--change-kind` with fields the author filled in (held by `tests/test_scaffold.py`), protocols stamped by an earlier labkit version, the command-line parsing of `labkit-init exp`, and the consumers that read fields afterwards (`protocol-fill`, preflight, finalize).

## Implementation plan for approval

1. **Record the intended inclusion matrix.** For the 24 combinations above, distinguish fields included in the form, fields due before measurement, and fields due after freeze or adoption. Include optional items absent from `FIELDS`. The low-cost full-form discrepancy is resolved (`5670d378`); do not silently turn a display cleanup into a new duty. Preserve the task-dependent placeholder meaning and the current TOML contracts.
2. **Centralize inclusion beside the existing field policy.** Extend or reuse `Field` metadata and the existing pure selectors rather than introduce a registry, plugin mechanism, configurable rule profiles or another orchestrator. The template remains the home of wording and section order. The inclusion decision must be computed from explicit inputs before filtering the template; template tags must cease to be an independent decision source. Add no new module unless the actual dependency boundary requires it. Unregistered guidance items must receive an explicit inclusion policy without becoming required fields.
3. **Simplify initial rendering.** Have `protocol_stamp` obtain the inclusion selection once, retain the selected items in one field-filtering pass, then apply task-specific wording and structural TOML operations. Preserve the necessary distinction between field selection and promise-table generation. Remove only cuts whose decisions are actually replaced; retain parsing and rendering helpers that still serve another purpose. Compare old and new generated forms, allowing only explicitly agreed differences.
4. **Connect existing consumers.** Apply the same inclusion policy when adding report fields and restamping a different kind. Preserve authored content during these operations; do not automatically delete filled fields from an existing protocol. Keep `owed` as the lifecycle decision and make `--contract` explain the same applicable field policy. Trace consumers in protocol editing, preflight and finalize before removing or moving a helper.
5. **Verify the contract through real commands.** Use memory-level tests for the selector, generator tests for layout and placeholders, and a bounded set of command scenarios for initial creation, adding report fields, and changing kind. Cover low/high cost and model/no-model branches, including the reproduced full-form case. Check that the form contains each applicable required field, excludes agreed inapplicable guidance, preserves authored work, and does not shift when existing duties become due. Read generated Markdown and TOML, not only exit codes. Obtain an independent code review before implementation commits and run the project's required checks at completion.

## Completion criterion and boundaries

The change is complete when one can answer field inclusion from one pure policy, initial creation and later form changes use that policy, and checking uses the same field definitions with an explicit lifecycle decision. The change should remove competing inclusion decisions, not place a new layer over the old ones. No line-count reduction or usability gain is claimed in advance.

This plan does not change scientific requirements, introduce laboratory-selectable rules, redesign report reviews or repair the usage-round findings by assumption. The known missing comparison in an apply task needs its own evidence and contract check; central field selection alone does not supply that comparison.
