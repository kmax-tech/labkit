# Registered pilot: the registration given, the agent implements (draft, 2026-10-31)

Round 2's lab attempts often failed at their own registration: an agent narrowed
or sharpened the task when it wrote the protocol (Rondônia "clipped to the state
boundary" with no boundary in the data) and was then held to it. labkit holds an
implementation to explicitly encoded intent; it does not write the intent. This
pilot gives every attempt the registration, written from the task text alone,
and measures what is left: implementation, gates, audit, environment.

- `protocols/<task>.md` — the lab arm's protocol (the stage replaces
  `{protocol_id}` with the stamped id), one per task of round 1: 21, 34, 60 (compute),
  15, 71 (fit), pubmedqa50 (apply with a model). Each passes `protocol-check`.
- `plans/<task>.md` — the same content for the control arm as `PLAN.md`, in
  plain words, without labkit's terms; the two arms differ in labkit, not in
  what they are told about the task.

Choices in these drafts that are the researcher's to confirm before any run:
1. 60 is registered as `compute` (a table and a mean over fixed predictions;
   no prediction of ours is judged), not `apply` as round 1's task list had it.
   The MFA, the hit and the rule application follow the task's wording made
   exact: the MFA by count over CCOBRA's response order, a tie to the first;
   a hit 1/n when the MFA is among n predicted responses.
2. 21: no clipping beyond the supplied layers; areas in a projected metric CRS.
3. 34: an index NeuroKit2 cannot compute from this recording stays empty.
4. 15: Morgan fingerprints (radius 2, 2,048 bits) and a random forest; the
   criterion's margin 0.25 above the permuted-label refits.
5. 71: a ridge regression on float32 signals, scored by the mean per-image
   Pearson correlation; margin 0.2. The estimator skeleton scores accuracy, r2
   or auc — an image correlation is an extension the agent has to write.
6. pubmedqa50: the prompt registered verbatim, one call per question, margin
   0.25 over the permuted-label null, at most two unparsable answers. The
   model route through the proxy with an API key is untested.
