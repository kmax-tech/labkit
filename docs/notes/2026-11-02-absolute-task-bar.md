# 2026-11-02 — a bar the task states is registered as an absolute value

**Problem.** In labkit-paper area 17 (round of 2026-11-02), two of three
labkit attempts had a task that stated an absolute bar ("Spearman at least
0.95", "ROC-AUC at least 0.90"). The estimator skeleton offers one
criterion form, `bar = null value + margin`
(`measure-estimator-script.py.template`, `evaluate_rows`), so both agents
translated the task's number into a `margin`: 0.05 for "at least 0.95"
(bar 0.05) and 0.40 over a refit mean of 0.4856 (bar 0.8856). Both runs
recorded `criterion_1_pass = true` for a value below the task's bar; only
the analysis audit found it.

Reproduced at 0.107.0 + HEAD (`5308239`) in temporary labs with the real
templates and commands and a fixed lookup predictor:

- a false pass runs mechanically clean to adoption: `protocol-check`,
  `code-check`, runlog, the area test, `finalize`, `--from-run`,
  `report-check` and `labkit-next` ("nothing — the number may be
  reported"); only an agent audit stands in between;
- the area test catches `margin = 0.90` for accuracy only by accident
  (null + 0.90 exceeds 1, so a perfect lane fails), and its message does
  not name the confusion;
- for accuracy at apply, the null value is the permutation expectation of
  the predictions themselves, and at fit the mean of random refits: no
  `margin` written before the run puts the bar at 0.90 for every outcome
  (0.89 against E = 0.498 passed with `margin = 0.38`, which was exact for
  E = 0.52). Spearman (E = 0) and AUC (E = 1/2) at apply hit the bar
  only because their expectation is a constant.

The relative form was not a template oversight: LAB-035 Thresholds belong
to the run, not to the measure said a threshold without reference to the
null condition is a number without a unit.

**Decision (the author's).** Two questions are kept apart: does the
measured value meet the stated requirement (the success criterion), and
how does the method behave against the null condition (a quality check).

- Standard 0.25 adds an exception to LAB-035 Thresholds belong to the run,
  not to the measure: a success bar set from outside the experiment (task,
  client, cited benchmark) is registered as that absolute value before the
  first measurement, its source named in the protocol, and the criterion
  compares with exactly that value. A bar the experimenter chooses stays
  relative to the null condition. The version follows the standard's own
  rule (a changed rule is the next version), although the change forbids
  nothing.
- The estimator skeleton registers exactly one of `at_least` (absolute)
  and `margin` (over the null value) in [criterion-1]'s table; both or
  neither are refused. The null lane and [quality-check-2] stay unchanged.

**Rejected.**

- An absolute bar as a second criterion beside the relative one: it does
  not avoid LAB-035 Thresholds belong to the run, not to the measure — an
  absolute second bar needs the same exception — and stamps a second
  promise into every area.
- `[reference]` on a fit or an apply: a format change for what a free
  promise constant already carries (registered, digested, held by runlog).
- A check of the number in the criterion sentence against the computed
  bar: static evidence at best; the sentence's meaning is the audit's.

The prompt skeleton (`measure-script.py.template`) has the same single
form; moving it is a separate step.
