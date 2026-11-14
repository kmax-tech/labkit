# Explain the null comparison without overloading “band”

> Plan requested by the author on 2026-11-14; wording changes are not implemented. [TODO](../../TODO.md) holds the work order. Field renaming and per-run calibration are separate changes.

Readers need to distinguish three quantities: the permitted absolute deviation from the null expectation, the interval around that expectation, and the upper threshold used to compare the measured score with chance. Current text calls several of these a “band”. Clarify the explanations, generated protocol text and messages while retaining the existing `null_band` field and calculation.

## Meaning to explain

Use plain descriptions before the existing field name. The following English wording is proposed for the documentation; it introduces no new identifier or format value.

| Quantity             | Description                                                            | Expression       |
|----------------------|------------------------------------------------------------------------|------------------|
| `null_band`          | Permitted absolute deviation from the null expectation, in score units | `b`              |
| Null-check interval  | Scores within that permitted deviation of the null expectation         | `[E - b, E + b]` |
| Comparison threshold | The upper threshold that the measured score must strictly exceed       | `E + b`          |

Here `E` denotes the null expectation and `b` the value currently stored as `null_band`. Neither is an additional protocol field.

At apply with the permutation calibration, explain the procedure: keep predictions fixed, permute the gold labels, calculate the absolute score deviations from the permutation expectation, take the registered quantile, and round upward to two decimal places. The current stamp supplies 200 permutations and quantile 0.99; these are registered settings, not the universal meaning of the field. The permutation expectation is not the empirical average of the 200 draws.

At fit, the same field provides a reasoned tolerance for the null check; it is not automatically the apply permutation quantile. Keep that distinction visible. Do not transfer the estimator explanation to the model skeleton's `null_band_items`, which uses item-count units.

Suggested result wording: “The measured score exceeds the comparison threshold derived from randomly permuted labels.” Show the score and the threshold when available. Do not describe the deviation width itself as the score threshold, or infer a significance level from the wording. The existing conditions on calibration validity and the unreleased false-alarm derivation remain as documented in the [chance-comparison note](2026-11-14-apply-chance-comparison.md).

## Files and implementation steps

1. **Define once in the agent guide.** Revise the explanation around `null_band` in `labkit/docs/agent-guide.md`. State its role and score units, then distinguish apply calibration from the reasoned fit value. Put the full algorithm and limits in the developer note rather than repeating them everywhere.
2. **Align field help and developer explanation.** Update `labkit/docs/protocol-field-guide.md` and `docs/notes/2026-11-14-apply-chance-comparison.md`. Explain width, interval and threshold separately. Inspect “Noise ceiling → threshold”: a ceiling on achievable performance and a threshold derived from the null serve different purposes. Trace the actual field's uses before proposing a replacement label. Do not rename a parsed label as incidental prose cleanup.
3. **Update the generated forms at their source.** Revise the fit/apply substitutions and optional criterion comments in `labkit/tools/protocol_cuts.py`; inspect shared wording in `labkit/templates/experiment-protocol.md.template`. Describe the null check as an absolute-deviation comparison and criterion-2 as a strict upper-threshold comparison. Preserve fit/apply and model/non-model distinctions. Existing registered protocols and historical runs are not rewritten.
4. **Align the stamped measurement script.** Revise the docstring, explanatory comments, CLI help and calibration output in `labkit/templates/measure-estimator-script.py.template`. Retain `null_band`, numerical rules, metric keys and conditions. Display descriptions can say “permitted deviation”; retain the exact field name where users must edit or diagnose it. A message must not claim a per-run calibration while the implementation only checks the first measurement.
5. **Verify generated output and finish the documentation.** Inspect readers of every changed string or label, update affected assertions and form comparison files, and add an appropriate CHANGELOG entry. Read actual newly generated apply and fit forms and calibration output. Check that a reader can identify the measured score, null expectation, deviation width and comparison threshold without interpreting “band” in several ways.

Changing a template promise's sentence changes the registration generated for new areas even if the formula stays the same. Assess the documentation and compatibility consequences explicitly; do not restamp already measured protocols to adopt improved wording. If the work requires a field rename or altered behaviour, stop that part and plan the corresponding contract change separately.

## Acceptance and boundaries

- The explanation says what the stored value means, how it is obtained in each supported path, and which comparison uses it.
- The strict criterion comparison and the inclusive null-check interval remain unchanged.
- No p-value or error-rate guarantee is introduced; “above the band” is replaced with a description of the actual threshold comparison.
- Field names, output keys and computational results remain unchanged. Update relevant existing tests rather than add tests that merely repeat prose.
- Local links, Markdown layout and changed generated text are checked. Run touched template and stamping tests and the configured commit checks when implementation changes those sources.

The per-run calibration proposal addresses whether the value belongs to the current predictions and items. This plan addresses how that value and its uses are explained. Coordinate the final wording with whichever calibration contract is implemented first, but do not resolve that decision through a wording edit. The exploratory-workflow plan and the criterion-specific non-assessability change also retain their own scope and priority.

## Source locations

- `labkit/docs/agent-guide.md`, registration guidance: short field definition and fit/apply distinction.
- `labkit/docs/protocol-field-guide.md`, “Noise ceiling → threshold”: field guidance.
- `labkit/tools/protocol_cuts.py`, fit/apply substitutions and optional criterion-2: generated registration text.
- `labkit/templates/measure-estimator-script.py.template`, `band_by_rule`, `band_check` and `evaluate_rows`: current calculation, lifetime check and comparisons.
- [Chance-comparison note](2026-11-14-apply-chance-comparison.md): interpretation, reviewed limits and later-run calibration issue.

These are source locations inspected during the terminology discussion, not immutable line references. Re-read their current state before implementation.
