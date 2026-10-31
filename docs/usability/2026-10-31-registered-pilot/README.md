# Registered pilot: an analysis plan given, the agent implements (draft, 2026-10-31)

Round 2's lab attempts often failed at their own registration: an agent narrowed
or sharpened the task when it wrote the protocol (Rondônia "clipped to the state
boundary" with no boundary in the data) and was then held to it. labkit holds an
implementation to explicitly encoded intent; it does not write the intent.

This pilot gives every attempt a registration and asks: **can the agent
implement a given analysis plan correctly, with labkit and without?** The
registration is the task text plus the researcher's analysis plan. Methods,
null conditions, margins, the projection and tie rules are the researcher's
decisions, not the task's; each is marked "researcher's choice" or
"researcher's precision" where it stands.

- `protocols/<task>.md` — the lab arm's protocol (the stage replaces
  `{protocol_id}` with the stamped id), one per task of round 1: 21, 34, 60
  (compute), 15, 71 (fit), pubmedqa50 (apply with a model). Each carries the
  task verbatim in its own section, so the audit, which reads the protocol
  first, sees the full deliverable spec. Each passes `protocol-check` — that
  shows the form, not that the plan is sound.
- `plans/<task>.md` — the same content for the control arm as `PLAN.md`,
  without labkit's terms, written by `make_plans.py`; the two arms differ in
  labkit, not in what they are told about the task.

## The researcher's choices to confirm before a run

1. 21: all supplied roads, the buffer not clipped at a state boundary; that
   every feature lies inside Rondônia is not checked. Areas in EPSG:32720 (UTM
   20S). Checked in the runtime image: EPSG:32720 gives 0.4749, 32723 0.4793,
   5880 0.4755 — under 1 % apart, the benchmark's tolerance is 5 % relative.
2. 34: neurokit2 0.2.12 (the image's), `ecg_peaks` default method without
   artifact correction, `hrv()` at 100 Hz. An empty column only for an index
   `hrv()` returns no value for, with its reason in the report; a missing
   package or an exception is a failed run.
3. 60: registered as `compute` (fixed predictions, nothing of ours is judged).
   The MFA tie goes to the first response in CCOBRA's order and the rule
   application is spelled out — both precisions of the task's wording.
4. 15: Morgan fingerprints (radius 2, 2,048 bits; fitted on nothing, so no
   fold leakage) and `RandomForestClassifier(n_estimators=500,
   random_state=seed)`, 3 folds and 2 permuted-label refits per fold from
   the skeleton's plan, seed 0. Margin 0.25 is a choice without a source; the
   null band 0.1 is wide against a null standard deviation near 0.008.
5. 71: the bar is the mean training response, scored in the same folds; no
   band on it, since images share structure and a mean can correlate with
   each; normalisation (one mean, one deviation per subject) from the
   fitting fold. **Recommended: not in this pilot.** The estimator skeleton
   scores one scalar per item; a 3,400-value target needs an extension of
   the skeleton, and the pilot should not measure that at the same time.
6. pubmedqa50: a strict parser (the whole reply must be yes, no or maybe);
   the null is the permutation expectation of the registered answers,
   computed exactly, its band the 0.99 quantile over 200 permutations. The
   model template's null check sits at half the items, which holds for two
   classes only: the agent has to replace it, as the protocol says. The
   model route through the proxy with an API key is to be tried once before
   the run, apart from any attempt.
